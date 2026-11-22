"""Useful close (0.26.7.1): close a running airing whose humidity target is still open once its benefit is exhausted.

Default strategy (``goals_reached``): reached goals close as before. With the goal still open the airing continues while
the uncapped IQ2 benefit of the next five minutes (the larger of the airing effect and the outdoor removal – never the
net change) is at least the room's own threshold, and closes with its own cause ("benefit_exhausted") once two new
humidity reports in a row confirm it below. Sources, CO2, cooling, protection limits, the room's minimum duration and
the explicit ``keep_drying`` strategy keep their priority. The close is no reached goal.

Wellness support case (diagnostics 13980253, 17.11.2026, 19:21–21:08): 48.3 m³, target 58 %, dehumidify profile,
shower/sauna sources, outdoor 9.6–10.3 °C / 91–93 %. Missing in the case data: the screenshot the order refers to, a CO2
sensor, the full order text with its further check paths, and readings after 21:08 – the replay asserts only what the
recorded readings decide and does not presuppose that the screenshot meant "close".
"""
from __future__ import annotations

import asyncio
import copy
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import coordinator_golden as golden  # noqa: E402 – installs the Home Assistant stub of the golden harness

from custom_components.freshairiq.const import DEFAULT_OPTIONS  # noqa: E402
from custom_components.freshairiq.decision_brain import build_unified_decision  # noqa: E402
from custom_components.freshairiq.live_coach import r07_time_fields, refine_live_recommendation  # noqa: E402
from custom_components.freshairiq.localize import Translator  # noqa: E402
from custom_components.freshairiq.close_wording import benefit_close, close_cause, fan_stop_message, goal_close  # noqa: E402
from custom_components.freshairiq.consolidation import stabilise_recommendation  # noqa: E402
from custom_components.freshairiq.model import (  # noqa: E402
    AIR_NO_LONGER_HELPS_CLOSE_REASON, BENEFIT_CLOSE_KIND, RoomInput, evaluate_room,
)
from custom_components.freshairiq.room_close_strategy import (  # noqa: E402
    BENEFIT_CHECK_KEY, CLOSE_CHECK_KEY, apply_benefit_close, benefit_close_state, benefit_next5_ml, benefit_threshold_ml,
    room_close_options,
)
from custom_components.freshairiq.room_recommendation import _recommendation  # noqa: E402
from custom_components.freshairiq.iq2_runtime import update_goal_history  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
BASE = {**DEFAULT_OPTIONS, "target_rh": 58.0, "min_duration_min": 3.0, "close_delta": 0.4,
        "min_return_next_5_min_ml": 25.0, "operating_profile": "dehumidify"}
KEEP = {"close_strategy": "keep_drying"}


def _room(**extra) -> RoomInput:
    values = dict(key="well", name="Wellnessraum", temperature=20.3, humidity=65.0, reference_temperature=9.7,
                  reference_humidity=92.0, volume_m3=48.3, contact_open=True, contact_open_seconds=1800, session_active=True,
                  session_elapsed_min=30.0, session_start_temp=20.3, learning_rate=0.03, session_fresh_measurements=6)
    values.update(extra)
    return RoomInput(**values)


def _forecast(effect, outdoor=None, *, weight=0.94, live=True):
    return {"moisture_effect_ml": effect, "outdoor_transport_ml": effect if outdoor is None else outdoor,
            "live_adapted": live, "live_observation_weight": weight, "method": "hybrid_live_measured"}


def _step(mem, forecast, stamp, *, quality="excellent", cfg=None, options=None, **room):
    """One coordinator cycle of a running airing: room model, room text, close latch, benefit check."""
    opts = room_close_options({**BASE, **(options or {})}, cfg or {})
    room_input = _room(close_notified=bool(mem.get("close_notified")), close_notified_kind=mem.get("close_notified_kind"),
                       session_goals_reached=bool(mem.get("session_goals_reached")), **room)
    result = evaluate_room(room_input, opts, False)
    action, reason, reasons = _recommendation(result, opts, pollen=0.0, co2=room_input.co2, airflow=1.0,
                                              wind_bearing=None, wind_speed=None)
    result.action, result.reason = action, reason
    # the latch of coordinator_room_model._room_recommendation_state
    mem["close_notified"] = bool(result.close_recommended)
    kind, stored = (result.close_kind if result.close_recommended else None), mem.get("close_notified_kind")
    mem["close_notified_kind"] = (kind if stored is None or kind == "goals_reached" else stored) if kind else None
    update_goal_history(mem, result)
    apply_benefit_close(mem, result, forecast, {"quality": quality, "humidity_reported_at": stamp}, opts,
                        room_input.volume_m3, reasons, running=True)
    return result


def _mem():
    return {"session_active": True}


def _stamp(i):
    return f"2026-11-17T20:{i:02d}:00+01:00"


# ------------------------------------------------------------------------------------------------ threshold and value

def test_the_threshold_follows_the_room_size_both_ways_and_the_profile():
    small, typical, wellness, hall = (benefit_threshold_ml(25.0, v, "comfort") for v in (9.4, 30.0, 48.3, 120.0))
    assert small == pytest.approx(7.83, abs=0.01) and typical == 25.0
    assert wellness == pytest.approx(40.25, abs=0.01) and hall == 100.0          # no fixed millilitre limit for all rooms
    assert benefit_threshold_ml(25.0, 2.0, "comfort") == pytest.approx(6.25)   # at least a quarter in tiny rooms
    assert benefit_threshold_ml(25.0, 48.3, "dehumidify") == pytest.approx(24.15, abs=0.01)
    assert benefit_threshold_ml(25.0, 48.3, "summer_cooling") == pytest.approx(20.13, abs=0.01)
    assert benefit_threshold_ml("x", None, None) == 25.0


def test_the_benefit_is_the_uncapped_removal_never_the_net_change():
    # a running source makes the room wetter (net -40 ml) while the window still takes 60 ml out: the benefit is 60 ml
    forecast = {"moisture_effect_ml": 12, "outdoor_transport_ml": 60, "net_room_change_ml": -40, "internal_moisture_effect_ml": 52}
    assert benefit_next5_ml(forecast) == 60
    assert benefit_next5_ml({"moisture_effect_ml": 3}) == 3
    assert benefit_next5_ml({"method": "unavailable", "moisture_effect_ml": 0}) is None
    assert benefit_next5_ml(None) is None and benefit_next5_ml({"moisture_effect_ml": "nan"}) is None


# ------------------------------------------------------------------------------------------------ confirmation

def test_two_new_reports_below_the_threshold_close_with_their_own_cause():
    mem = _mem()
    first = _step(mem, _forecast(18, 20), _stamp(1))
    assert first.action == "Continue ventilating" and not first.close_recommended
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1 and not mem[BENEFIT_CHECK_KEY]["latched"]
    second = _step(mem, _forecast(17, 20), _stamp(3))
    assert second.action == "Close" and second.close_recommended and second.close_kind == BENEFIT_CLOSE_KIND
    assert "Schwelle für diesen Raum 24 ml" in second.reason and "Feuchteziel von 58 % noch nicht erreicht" in second.reason
    assert Translator().text(second.reason).endswith(
        "Further airing hardly removes moisture any more (confirmed about 20 ml in 5 min, threshold for this room 24 ml) – "
        "close although the humidity target of 58 % is not reached yet (now 65 %)")
    # an exhausted benefit is no reached goal
    assert mem["close_notified_kind"] == BENEFIT_CLOSE_KIND and not mem.get("session_goals_reached")
    assert not second.goals_reached_now
    assert close_cause([{"close_recommended": True, "close_kind": BENEFIT_CLOSE_KIND}])[0] == BENEFIT_CLOSE_KIND


def test_the_same_old_report_twice_held_frames_and_an_unadapted_forecast_confirm_nothing():
    mem = _mem()
    _step(mem, _forecast(10), _stamp(1))
    assert _step(mem, _forecast(10), _stamp(1)).action == "Continue ventilating"         # same report, second evaluation
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1
    for quality in ("held", "uncertain", "stale"):
        assert _step(mem, _forecast(10), _stamp(5), quality=quality).action == "Continue ventilating"
    assert _step(mem, _forecast(10, weight=0.3), _stamp(6)).action == "Continue ventilating"
    assert _step(mem, _forecast(10, live=False), _stamp(7)).action == "Continue ventilating"
    assert _step(mem, _forecast(10), None).action == "Continue ventilating"
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1
    assert _step(mem, _forecast(10), _stamp(8)).action == "Close"


def test_a_benefit_between_the_two_lines_breaks_the_confirmation():
    mem = _mem()
    _step(mem, _forecast(18), _stamp(1))
    assert _step(mem, _forecast(26), _stamp(3)).action == "Continue ventilating"      # 24.15 ≤ 26 < 1.25 × 24.15
    assert _step(mem, _forecast(18), _stamp(5)).action == "Continue ventilating"
    assert _step(mem, _forecast(18), _stamp(7)).action == "Close"


# ------------------------------------------------------------------------------------------------ hysteresis

def test_the_close_holds_against_drier_air_and_is_lifted_only_by_two_clearly_better_forecasts():
    mem = _mem()
    _step(mem, _forecast(10), _stamp(1))
    _step(mem, _forecast(10), _stamp(3))
    # the drier air alone (fresh, confirmed readings, delta far above close_delta) does not lift the stored close
    assert _step(mem, _forecast(28), _stamp(5)).action == "Close"                    # inside the band
    assert _step(mem, _forecast(31), _stamp(7)).action == "Close"                    # first clearly better report
    assert _step(mem, _forecast(31), _stamp(7)).action == "Close"                    # the same report again
    reopened = _step(mem, _forecast(31), _stamp(9))
    assert reopened.action == "Continue ventilating" and not reopened.close_recommended and reopened.close_kind is None
    assert "Kurzfristiger Schließcheck (5 min): voraussichtlich 31 ml Feuchteabbau" in reopened.reason
    assert not mem["close_notified"] and mem["close_notified_kind"] is None
    # a fluctuating forecast never flips the advice every cycle
    actions = [_step(mem, _forecast(v), _stamp(10 + i)).action for i, v in enumerate((20, 30, 20, 30, 20, 20, 30, 20))]
    assert actions == ["Continue ventilating"] * 5 + ["Close"] * 3


def test_the_room_model_keeps_a_stored_benefit_close_while_the_air_is_still_drier():
    room = _room(close_notified=True, close_notified_kind=BENEFIT_CLOSE_KIND)
    result = evaluate_room(room, room_close_options(BASE, {}), False)
    assert result.action == "Close" and result.close_kind == BENEFIT_CLOSE_KIND
    assert result.delta_g_m3 > 2.0                                                   # clearly drier, still no release
    # moisture coming in is the protective cause, not the exhausted benefit
    wet = evaluate_room(_room(reference_temperature=21.0, reference_humidity=95.0, close_notified=True,
                              close_notified_kind=BENEFIT_CLOSE_KIND), room_close_options(BASE, {}), False)
    assert wet.close_kind == "air_no_longer_helps" and wet.reason == AIR_NO_LONGER_HELPS_CLOSE_REASON


# ------------------------------------------------------------------------------------------------ priorities

def _never_closes(mem, **room):
    actions = [_step(mem, _forecast(5), _stamp(i), **room).action for i in range(1, 6)]
    return actions, mem.get(BENEFIT_CHECK_KEY)


def test_an_active_moisture_source_keeps_the_window_open():
    actions, check = _never_closes(_mem(), moisture_source_active=True, moisture_source_rate_ml_min=8.0)
    assert set(actions) == {"Continue ventilating"} and check is None
    actions, check = _never_closes(_mem(), moisture_source_recovery=True, moisture_source_ended_min=2.0)
    assert set(actions) == {"Continue ventilating"} and check is None


def test_a_source_that_starts_during_a_benefit_close_reopens_it():
    mem = _mem()
    _step(mem, _forecast(5), _stamp(1))
    assert _step(mem, _forecast(5), _stamp(3)).action == "Close"
    reopened = _step(mem, _forecast(5), _stamp(5), moisture_source_active=True, moisture_source_rate_ml_min=8.0)
    assert reopened.action == "Continue ventilating" and not reopened.close_recommended
    assert mem.get(BENEFIT_CHECK_KEY) is None and not mem["close_notified"]


def test_co2_keeps_the_window_open_and_restarts_the_confirmation():
    mem = _mem()
    _step(mem, _forecast(5), _stamp(1))
    assert _step(mem, _forecast(5), _stamp(3), co2=1150.0).action == "Continue ventilating"
    assert mem.get(BENEFIT_CHECK_KEY) is None
    assert _step(mem, _forecast(5), _stamp(5), co2=600.0).action == "Continue ventilating"     # one new confirmation
    assert _step(mem, _forecast(5), _stamp(7), co2=600.0).action == "Close"


def test_useful_cooling_keeps_the_window_open():
    actions, check = _never_closes(_mem(), temperature=27.0, reference_temperature=17.0, reference_humidity=60.0,
                                   options={"operating_profile": "summer_cooling"})
    assert "Close" not in actions and check is None


def test_the_temperature_limit_stays_the_protective_cause():
    mem = _mem()
    result = _step(mem, _forecast(5), _stamp(1), temperature=17.0, options={"airing_min_room_temp_c": 18.0})
    assert result.action == "Close" and result.close_kind == "temperature_limit"


def test_reached_goals_stay_a_goal_close():
    mem = _mem()
    result = _step(mem, _forecast(5), _stamp(1), humidity=57.0)
    assert result.close_kind == "goals_reached" and mem["session_goals_reached"]


def test_keep_drying_rooms_keep_the_earlier_behaviour():
    actions, check = _never_closes(_mem(), cfg=KEEP)
    assert set(actions) == {"Continue ventilating"} and check is None
    assert benefit_close_state({}, _forecast(5), room_close_options(BASE, KEEP), 48.3)["close_benefit_threshold_ml"] is None


def test_every_opening_keeps_its_own_minimum_duration():
    # a window opened later has its own clock: before its minimum no benefit close, afterwards it is confirmed anew
    mem = _mem()
    assert [_step(mem, _forecast(5), _stamp(i), session_elapsed_min=2.0).action for i in (1, 2, 3)] == ["Continue ventilating"] * 3
    assert mem.get(BENEFIT_CHECK_KEY) is None
    assert _step(mem, _forecast(5), _stamp(4), session_elapsed_min=3.5).action == "Continue ventilating"
    assert _step(mem, _forecast(5), _stamp(5), session_elapsed_min=5.5).action == "Close"


@pytest.mark.parametrize("volume,benefit,expected", [(9.4, 4.0, "Close"), (9.4, 6.0, "Continue ventilating"),
                                                     (120.0, 50.0, "Close"), (120.0, 70.0, "Continue ventilating")])
def test_small_and_large_rooms_use_their_own_threshold(volume, benefit, expected):
    mem = _mem()
    _step(mem, _forecast(benefit), _stamp(1), volume_m3=volume)
    assert _step(mem, _forecast(benefit), _stamp(3), volume_m3=volume).action == expected


def test_an_unreachable_target_ends_with_the_exhausted_benefit_instead_of_an_endless_airing():
    # target 40 % in a damp autumn evening: the goal is out of reach, the air still a little drier
    mem = _mem()
    opts = {"target_rh": 40.0}
    results = [_step(mem, _forecast(6, 9), _stamp(i), options=opts, humidity=55.0) for i in (1, 3)]
    assert results[-1].close_kind == BENEFIT_CLOSE_KIND and "Feuchteziel von 40 %" in results[-1].reason


def test_a_weather_change_with_clearly_drier_air_lifts_the_close():
    mem = _mem()
    _step(mem, _forecast(10), _stamp(1))
    assert _step(mem, _forecast(10), _stamp(3)).action == "Close"
    drier = {"reference_temperature": 2.0, "reference_humidity": 70.0}
    assert _step(mem, _forecast(45), _stamp(5), **drier).action == "Close"
    assert _step(mem, _forecast(45), _stamp(7), **drier).action == "Continue ventilating"


def test_fan_and_house_wording_name_the_exhausted_benefit():
    room = {"close_recommended": True, "close_kind": BENEFIT_CLOSE_KIND, "delta_g_m3": 2.5}
    assert fan_stop_message(room) == "Weiteres Lüften entfernt kaum noch Feuchtigkeit. Lüfter ausschalten."
    assert Translator().text(fan_stop_message(room)) == "Further airing hardly removes moisture any more. Switch off the fan."
    assert Translator().text(close_cause([room])[1]) == "Further airing hardly removes moisture any more – the humidity target is not reached yet"


def test_the_house_aggregate_keeps_a_confirmed_benefit_close():
    # the rooms' combined effect (60 ml) is above the aggregate threshold – the room's own confirmed decision stands
    def rooms(kind):
        base = dict(data_quality="ok", active=True, open=True, action="Close", close_recommended=True, close_kind=kind,
                    session_elapsed_min=12.0, temperature_change_c=-0.3, delta_g_m3=2.6, forecast_5_min_moisture_effect_ml=30, volume_m3=48.3,
                    forecast_5_min_temperature_change_c=-0.1, efficiency_ml_per_01c=50.0)
        return {k: dict(base, key=k, name=k) for k in ("well", "bad")}
    options = {"min_return_next_5_min_ml": 25.0, "close_delta": 0.4, "min_duration_min": 3.0}
    kept = rooms(BENEFIT_CLOSE_KIND)
    assert stabilise_recommendation({"kind": "close", "room_keys": list(kept)}, kept, options)["kind"] == "close"
    physical = rooms("air_no_longer_helps")
    assert stabilise_recommendation({"kind": "close", "room_keys": list(physical)}, physical, options)["kind"] == "continue"
    assert benefit_close(kept["well"]) and not goal_close(kept["well"]) and not benefit_close(physical["well"])
    assert not benefit_close(dict(kept["well"], close_recommended=False)) and not benefit_close(None)


def test_the_check_skips_invalid_data_and_names_its_close_also_without_a_check_line():
    class Result:
        data_quality, action, close_recommended, close_kind, benefit_close_ready = "ok", "Continue ventilating", False, None, True
        humidity, reason = 64.0, "Raumluftfeuchte 64 % liegt über dem Lüftungsstartwert 62 %"

    opts = room_close_options(BASE, {})
    mem = {"session_active": True, BENEFIT_CHECK_KEY: {"frame": _stamp(1), "low": 1, "high": 0, "latched": False}}
    broken = Result()
    broken.data_quality = "error"
    assert apply_benefit_close(mem, broken, _forecast(5), {"quality": "excellent", "humidity_reported_at": _stamp(2)}, opts,
                               48.3, [], running=True) is False
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1                                      # missing data never resets the check
    result, reasons = Result(), [Result.reason]
    assert apply_benefit_close(mem, result, _forecast(5), {"quality": "excellent", "humidity_reported_at": _stamp(2)}, opts,
                               48.3, reasons, running=True)
    assert result.action == "Close" and reasons[0].startswith("Weiteres Lüften entfernt kaum noch Feuchtigkeit (bestätigt")
    assert result.reason == f"{reasons[0]}; {Result.reason}" and mem["close_notified_kind"] == BENEFIT_CLOSE_KIND
    # the room's final measurement after closing ends the check
    assert apply_benefit_close(mem, Result(), _forecast(5), {}, opts, 48.3, [], running=False) and mem[BENEFIT_CHECK_KEY] is None


# ------------------------------------------------------------------------------------------------ time and explanation

def _live_room(**extra):
    room = {"key": "well", "name": "Wellnessraum", "active": True, "open": True, "data_quality": "ok", "action": "Continue ventilating",
            "session_elapsed_min": 40.0, "volume_m3": 48.3, "delta_g_m3": 2.6, "close_decision_ready": True,
            "forecast_5_min_moisture_effect_ml": 11, "forecast_5_min_benefit_ml": 20, "close_benefit_threshold_ml": 24.1,
            "forecast_5_min_confidence": 61, "result_ml": 120}
    room.update(extra)
    return room


def test_a_reassessed_airing_names_why_no_remaining_time_exists_and_shows_no_old_target():
    rooms = {"well": _live_room(forecast_5_min_benefit_ml=30)}
    rec = {"kind": "continue", "room_keys": ["well"], "duration_min": 3.0}
    live = refine_live_recommendation(rooms, {**BASE, "max_duration_min": 20.0}, rec)
    assert live["live_coach_time_state"] == "reassessing" and live["live_coach_remaining_min"] is None
    reason = "Restzeit nicht bestimmbar – geschlossen wird, sobald zwei neue Messungen unter 24 ml in 5 min liegen (jetzt etwa 30 ml)"
    assert live["live_coach_time_reason"] == reason
    assert Translator().text(reason) == ("Remaining time cannot be determined – the airing closes once two new readings are below 24 ml in "
                                  "5 min (now about 30 ml)")
    # Issue #30: already below the threshold but not confirmed – the text names the readings the confirmation needs
    below = refine_live_recommendation({"well": _live_room()}, {**BASE, "max_duration_min": 20.0}, rec)["live_coach_time_reason"]
    assert below == ("Restzeit nicht bestimmbar – geschlossen wird, sobald zwei neue, geeignete Feuchtemeldungen weniger als 24 ml in "
                     "5 min bestätigen (jetzt etwa 20 ml, noch unbestätigt: nötig sind frische Feuchtewerte und ausreichend aktuelle "
                     "Raum- und Außentemperaturen)")
    assert Translator().text(below) == ("Remaining time cannot be determined – the airing closes once two new, suitable humidity reports confirm "
                                 "less than 24 ml in 5 min (now about 20 ml, not confirmed yet: fresh humidity values and sufficiently "
                                 "recent room and outdoor temperatures are needed)")
    brain = build_unified_decision(live, rooms, BASE)["decision_brain"]
    assert brain["action_line"] == reason and "Ziel etwa" not in brain["action_line"]
    time = r07_time_fields(live, rooms, active=True, remaining=None, displayed_recommended=3.0, max_elapsed=40.0)
    assert time["remaining_duration_state"] == "reassessing" and time["remaining_duration_reason"] == reason
    # other causes are named as such
    for extra, cause in (({"moisture_source_active": True}, "eine Feuchtequelle ist noch aktiv"),
                         ({"comfort_cooling_active": True}, "weitergelüftet wird zum Kühlen"),
                         ({"close_benefit_threshold_ml": None}, "geschlossen wird, sobald die Außenluft nicht mehr trocknet")):
        out = refine_live_recommendation({"well": _live_room(**extra)}, {**BASE, "max_duration_min": 20.0}, dict(rec))
        assert out["live_coach_time_reason"] == f"Restzeit nicht bestimmbar – {cause}"
        assert "Restzeit nicht bestimmbar" not in Translator().text(out["live_coach_time_reason"])


def test_a_countdown_keeps_its_honest_remaining_time():
    rooms = {"well": _live_room(session_elapsed_min=1.0, forecast_5_min_moisture_effect_ml=60, forecast_5_min_benefit_ml=60)}
    live = refine_live_recommendation(rooms, {**BASE, "max_duration_min": 20.0}, {"kind": "continue", "room_keys": ["well"], "duration_min": 9.0})
    assert live["live_coach_time_state"] == "countdown" and live["live_coach_time_reason"] is None
    brain = build_unified_decision(live, rooms, BASE)["decision_brain"]
    assert brain["action_line"].startswith("Ziel etwa ") and "noch ca." in brain["action_line"]


def test_both_cards_read_the_integrations_reason_and_compute_no_time_of_their_own():
    front = ROOT / "custom_components" / "freshairiq" / "frontend"
    card = (front / "freshairiq-card-data.js").read_text(encoding="utf-8")
    tile = card[card.index("    _iqTime(st) {"):card.index("    _statusEntity() {")]
    assert 'st.remaining_duration_state === "reassessing" && st.remaining_duration_reason' in tile
    house = (front / "freshairiq-house-card.js").read_text(encoding="utf-8")
    assert 'reassessing: !!f.live && p.remaining_duration_state === "reassessing", why: p.remaining_duration_reason || null' in house
    panels = (front / "freshairiq-house-panels.js").read_text(encoding="utf-8")
    assert 'f.reassessing ? `⏱ ${esc(f.why || c._t("moist_room_reassess"))}`' in panels
    assert "Date.now" not in tile and "session_elapsed_min" not in tile


# ------------------------------------------------------------------------------------------------ wellness replay

H_ATTR = {"device_class": "humidity", "unit_of_measurement": "%"}
T_ATTR = {"device_class": "temperature", "unit_of_measurement": "°C"}
# time, window, room °C, room %, outdoor °C, outdoor % (diagnostics 13980253)
WELLNESS = (
    ("19:21:53", 0, 20.1, 64, 10.3, 93), ("19:37:18", 0, 20.3, 69, 10.3, 93), ("19:40:18", 0, 20.3, 69, 10.3, 93),
    ("19:42:42", 0, 20.3, 73, 10.3, 93), ("19:43:28", 1, 20.3, 73, 10.3, 93), ("19:45:57", 1, 20.3, 75, 9.7, 92),
    ("19:48:18", 1, 20.3, 72, 9.7, 92), ("19:49:10", 1, 20.3, 72, 9.7, 92), ("19:51:17", 1, 20.3, 72, 9.7, 92),
    ("19:53:18", 1, 20.3, 72, 9.7, 92), ("19:54:18", 1, 20.3, 71, 9.7, 92), ("19:56:18", 1, 20.3, 71, 9.7, 92),
    ("19:58:18", 1, 20.3, 70, 9.7, 92), ("20:00:19", 1, 20.3, 69, 9.7, 92), ("20:02:19", 1, 20.3, 68, 9.7, 92),
    ("20:04:22", 1, 20.3, 67, 9.7, 92), ("20:06:29", 1, 20.3, 67, 9.7, 92), ("20:08:47", 1, 20.3, 67, 9.7, 92),
    ("20:10:55", 1, 20.3, 66, 9.7, 92), ("20:13:09", 1, 20.3, 65, 9.7, 92), ("20:15:19", 1, 20.3, 65, 9.7, 92),
    ("20:17:19", 1, 20.4, 65, 9.7, 92), ("20:19:29", 1, 20.4, 65, 9.7, 92), ("20:21:29", 1, 20.4, 65, 9.7, 92),
    ("20:23:30", 1, 20.4, 65, 9.7, 92), ("20:25:41", 1, 20.4, 65, 9.7, 92), ("20:27:42", 1, 20.2, 64, 9.7, 92),
    ("20:29:58", 1, 20.2, 64, 9.7, 92), ("20:32:19", 1, 20.2, 64, 9.7, 92), ("20:34:28", 1, 20.2, 64, 9.7, 92),
    ("20:36:58", 1, 20.2, 64, 9.7, 92), ("20:38:58", 1, 20.2, 64, 9.7, 92), ("20:41:18", 1, 20.2, 64, 9.6, 91),
    ("20:43:18", 1, 20.2, 64, 9.6, 91), ("20:45:18", 1, 20.2, 64, 9.6, 91), ("20:47:18", 1, 20.2, 64, 9.6, 91),
    ("20:49:18", 1, 20.2, 64, 9.6, 91), ("20:51:18", 1, 20.2, 63, 9.6, 91), ("20:53:18", 1, 20.2, 63, 9.6, 91),
    ("20:55:18", 1, 20.2, 63, 9.6, 91), ("20:57:26", 1, 20.2, 63, 9.6, 91), ("20:59:58", 1, 20.2, 63, 9.6, 91),
    ("21:04:19", 1, 20.2, 63, 9.6, 91), ("21:06:21", 1, 20.2, 63, 9.6, 91), ("21:08:29", 1, 20.2, 62, 9.6, 91),
)
WELLNESS_OPTIONS = {"target_rh": 58.0, "close_delta": 0.4, "min_duration_min": 3.0, "max_duration_min": 20.0,
                    "min_return_next_5_min_ml": 25.0, "max_temp_loss_next_5_min_c": 0.6, "min_efficiency_ml_per_01c": 8.0,
                    "co2_warn": 1000.0, "co2_critical": 1400.0, "co2_release": 0.0, "operating_profile": "dehumidify",
                    "thermal_preference": "balanced", "personal_priority": "climate"}


def _wellness_states(row):
    _, window, temp, rh, out_t, out_rh = row
    return {"sensor.t": (temp, T_ATTR), "sensor.h": (rh, H_ATTR), "binary_sensor.f": ("on" if window else "off", {"device_class": "window"}),
            "sensor.aussen_t": (out_t, T_ATTR), "sensor.aussen_h": (out_rh, H_ATTR)}


@pytest.fixture(scope="module")
def wellness():
    at = [datetime.fromisoformat(f"2026-11-17T{row[0]}").replace(tzinfo=TZ) for row in WELLNESS]
    steps = [{"advance": max(int((b - a).total_seconds()), 1), "set": _wellness_states(row)} for a, b, row in zip(at, at[1:], WELLNESS[1:])]
    room = golden._room("wellnessraum", "Wellnessraum", "ground_floor", temp=["sensor.t"], hum=["sensor.h"], contacts=["binary_sensor.f"],
                        volume=48.3, orientation="south", extra={"moisture_sources": ["shower", "sauna"]})
    seen = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append(copy.deepcopy(result))
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    scenario = {"start": at[0], "initial": _wellness_states(WELLNESS[0]), "steps": steps,
                "options": {**golden.BASE_OPTIONS, **WELLNESS_OPTIONS},
                "data": {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": [room],
                         "levels": ["ground_floor"]}}
    try:
        asyncio.run(golden._run_scenario("audit", scenario, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return list(zip((row[0][:5] for row in WELLNESS[1:]), seen[1:]))


def test_wellness_replay_closes_on_the_confirmed_exhausted_benefit_not_before_the_source_is_over(wellness):
    rooms = [(t, c["rooms"]["wellnessraum"], c) for t, c in wellness]
    closes = [t for t, r, _ in rooms if r["action"] == "Close"]
    assert closes, "the recorded readings confirm an exhausted benefit"
    first = closes[0]
    # never during the shower/sauna and its follow-up, never before the benefit fell below the room's threshold twice
    for t, r, _ in rooms:
        if t < first and r.get("active"):
            assert r["action"] == "Continue ventilating"
        if r.get("moisture_source_active"):
            assert r["action"] != "Close"
    t, room, cycle = next(x for x in rooms if x[0] == first)
    assert room["close_kind"] == BENEFIT_CLOSE_KIND and room["humidity"] > 58
    assert room["close_benefit_threshold_ml"] == pytest.approx(24.1, abs=0.1)
    assert room["forecast_5_min_benefit_ml"] < room["close_benefit_threshold_ml"]
    assert "Feuchteziel von 58 % noch nicht erreicht" in room["reason"]
    rec = cycle["intelligent_recommendation"]
    assert rec["kind"] == "close" and cycle["close_reason_kind"] == BENEFIT_CLOSE_KIND
    assert rec["live_coach_reason"].startswith("Weiteres Lüften entfernt kaum noch Feuchtigkeit")
    assert rec["summary"].startswith("Weiteres Lüften entfernt kaum noch Feuchtigkeit")              # house close
    assert any(str(r).startswith("Weiteres Lüften entfernt kaum noch Feuchtigkeit (bestätigt etwa ")       # room push
               for r in room["recommendation_reasons"])
    assert not room.get("goals_reached_now")
    # no flapping: the close stays for the rest of the recorded airing (benefit 17–20 ml, threshold 24 ml)
    assert all(r["action"] == "Close" for t, r, _ in rooms if t >= first)


def test_wellness_replay_time_display_matches_the_decision(wellness):
    for _, cycle in wellness:
        rec = cycle["intelligent_recommendation"]
        brain = rec.get("decision_brain") or {}
        state = cycle.get("remaining_duration_state")
        if state == "reassessing":
            assert cycle["remaining_duration_reason"].startswith("Restzeit nicht bestimmbar – ")
            assert cycle["remaining_duration_min"] is None
            assert "Ziel etwa" not in str(brain.get("action_line") or "")
        if state == "countdown":
            assert cycle["remaining_duration_min"] > 0 and cycle["remaining_duration_reason"] is None
        if rec.get("kind") == "close":
            assert state in {"close", "overrun"}
        room = cycle["rooms"]["wellnessraum"]
        if room.get("active") and room.get("open"):
            assert room["time_state"] == ("close" if room["action"] == "Close" else room["time_state"])


# ------------------------------------------------------------------------------------------------ Issue #30: staggered reports

def _held(stamp, *, humidity_age=40.0, temperature_age=900.0, reference_age=1200.0, reference_skew=0.0, quality="held"):
    """A measurement frame of a slow battery sensor: a new humidity report, a temperature reported only on a change."""
    return {"quality": quality, "humidity_reported_at": stamp, "temperature_reported_at": "2026-11-17T19:30:00+01:00",
            "reference_temperature_reported_at": "2026-11-17T19:20:00+01:00", "reference_humidity_reported_at": "2026-11-17T19:20:00+01:00",
            "age_humidity_s": humidity_age, "age_temperature_s": temperature_age, "age_reference_temperature_s": reference_age,
            "age_reference_humidity_s": reference_age + reference_skew, "reference_skew_s": reference_skew, "skew_s": temperature_age - humidity_age}


HELD_ROOM = dict(temperature=24.0, humidity=70.0, reference_temperature=24.0, reference_humidity=45.0, session_start_temp=24.0)


def _rh(i):
    """The humidity value of report ``i``: a drying room reports a new whole percent with every report."""
    return 70.0 - i


def _held_step(mem, benefit, frame, *, fraction=0.25, humidity=None, **room):
    """One cycle at 24 °C inside and outside with a staggered frame (wellness room 48.3 m³, threshold 24 ml)."""
    opts = room_close_options(BASE, {})
    stamp = frame.get("humidity_reported_at") or ""
    index = int(stamp[14:16]) if stamp[11:13] == "20" else 0
    room_input = _room(close_notified=bool(mem.get("close_notified")), close_notified_kind=mem.get("close_notified_kind"),
                       session_goals_reached=bool(mem.get("session_goals_reached")),
                       **{**HELD_ROOM, "humidity": _rh(index) if humidity is None else humidity, **room})
    result = evaluate_room(room_input, opts, False)
    action, reason, reasons = _recommendation(result, opts, pollen=0.0, co2=room_input.co2, airflow=1.0, wind_bearing=None, wind_speed=None)
    result.action, result.reason = action, reason
    mem["close_notified"] = bool(result.close_recommended)
    kind, stored = (result.close_kind if result.close_recommended else None), mem.get("close_notified_kind")
    mem["close_notified_kind"] = (kind if stored is None or kind == "goals_reached" else stored) if kind else None
    update_goal_history(mem, result)
    forecast = {**_forecast(benefit), "exchange_fraction": fraction, "temperature_change_c": 0.0}
    original = copy.deepcopy(frame)
    apply_benefit_close(mem, result, forecast, frame, opts, room_input.volume_m3, reasons, running=True)
    assert frame == original                                     # time stamps and the frame grade stay as they were
    return result


def _good_step(mem, benefit, i, **room):
    """A regular cycle (excellent frame) of report ``i`` at 24 °C, with the humidity value of that report."""
    return _step(mem, _forecast(benefit), _stamp(i), **{**HELD_ROOM, "humidity": _rh(i), **room})


def _held_mem():
    # the airing started at 19:40; the last humidity report seen before the check (71 %) is the reference for a new value
    return {"session_active": True, "session_started": "2026-11-17T19:40:00+01:00",
            CLOSE_CHECK_KEY: {"humidity": {"at": "2026-11-17T19:59:00+01:00", "value": 71.0, "new": False},
                              "temperature": {"at": "2026-11-17T19:30:00+01:00", "value": 24.0, "new": False}, "state": None}}


def _state(mem):
    return benefit_close_state(mem, _forecast(8), room_close_options(BASE, {}), 48.3)


def test_staggered_two_new_humidity_values_with_an_older_temperature_confirm_a_low_benefit_at_24_degrees():
    mem = _held_mem()
    first = _held_step(mem, 8, _held(_stamp(1)))
    assert first.action == "Continue ventilating" and mem[BENEFIT_CHECK_KEY]["low"] == 1 and mem[BENEFIT_CHECK_KEY]["staggered"] == 1
    assert 0 < mem[BENEFIT_CHECK_KEY]["margin_ml"] < 24.1 - 8 and _state(mem)["close_check"] == "confirming"
    second = _held_step(mem, 8, _held(_stamp(3), temperature_age=1020.0))
    assert second.action == "Close" and second.close_recommended and second.close_kind == BENEFIT_CLOSE_KIND
    assert "Weiteres Lüften entfernt kaum noch Feuchtigkeit (bestätigt etwa 8 ml in 5 min, Schwelle für diesen Raum 24 ml)" in second.reason
    assert _state(mem)["close_check"] == "confirmed_staggered" and _state(mem)["close_benefit_basis"] == "staggered"
    # time-shifted outdoor values (reported together, 50 min ago) can still be used
    mem = _held_mem()
    for i in (1, 3):
        result = _held_step(mem, 6, _held(_stamp(i), reference_age=3000.0))
    assert result.action == "Close"


def test_a_held_report_that_fails_its_margin_counts_once_in_the_regular_path_after_a_new_temperature():
    """Issue #30 regression: the draft reset the series on a held report and then skipped the same report as a good frame."""
    mem = _held_mem()
    assert _good_step(mem, 18, 1).action == "Continue ventilating" and mem[BENEFIT_CHECK_KEY]["low"] == 1
    # the second humidity report arrives with the old temperature: 18 ml plus its possible error is above 24 ml
    assert _held_step(mem, 18, _held(_stamp(3))).action == "Continue ventilating"
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1 and mem[BENEFIT_CHECK_KEY]["frame"] == _stamp(1)      # nothing reset, nothing used up
    # ten seconds later the temperature is reported: the same pair is excellent and counts in the regular path
    closed = _good_step(mem, 18, 3)
    assert closed.action == "Close" and closed.close_kind == BENEFIT_CLOSE_KIND
    assert mem[BENEFIT_CHECK_KEY]["low"] == 2 and mem[BENEFIT_CHECK_KEY]["basis"] == "regular" and "staggered" not in mem[BENEFIT_CHECK_KEY]
    # further evaluations of the same report confirm nothing more
    before = copy.deepcopy(mem[BENEFIT_CHECK_KEY])
    for _ in range(3):
        assert _good_step(mem, 18, 3).action == "Close"
        assert _held_step(mem, 18, _held(_stamp(3))).action == "Close"
    assert mem[BENEFIT_CHECK_KEY] == before


def test_a_report_counted_on_the_staggered_path_never_counts_again_with_a_better_grade():
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))
    for temperature_age in (30.0, 60.0):                                         # only the temperature was reported again
        assert _held_step(mem, 8, _held(_stamp(1), temperature_age=temperature_age)).action == "Continue ventilating"
    assert _good_step(mem, 8, 1).action == "Continue ventilating"                 # the same report in a synchronous frame
    assert _held_step(mem, 8, _held(_stamp(1), quality="uncertain")).action == "Continue ventilating"
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1 and mem[BENEFIT_CHECK_KEY]["staggered"] == 1


@pytest.mark.parametrize("frame,humidity", [
    (_held(_stamp(3)), _rh(1)),                    # a new time stamp of the same value (restart, substituted stamp)
    (_held("2026-11-17T20:00:30+01:00"), 68.0),    # older than the counted report
    (_held("2026-11-17T19:39:00+01:00"), 68.0),    # reported before the opening
    (_held("2026-11-17T20:03:00"), 68.0),          # a report time without its zone is never compared with zoned ones
])
def test_repeated_values_old_reports_and_reports_before_the_opening_confirm_nothing(frame, humidity):
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))
    assert _held_step(mem, 8, frame, humidity=humidity).action == "Continue ventilating"
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1


def test_the_basis_names_the_path_the_confirmations_came_from():
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))                                        # staggered first …
    assert _good_step(mem, 8, 3).action == "Close"                              # … then a regular report
    assert mem[BENEFIT_CHECK_KEY]["staggered"] == 1 and mem[BENEFIT_CHECK_KEY]["basis"] == "staggered"
    _good_step(mem, 8, 5)                                                       # a second regular report carries the close alone
    assert mem[BENEFIT_CHECK_KEY]["basis"] == "regular" and _state(mem)["close_check"] == "confirmed"
    # without a forecast the check waits and keeps its confirmations
    opts = room_close_options(BASE, {})
    result = _held_step(mem, 8, _held(_stamp(7)))
    apply_benefit_close(mem, result, {"method": "unavailable"}, _held(_stamp(7)), opts, 48.3, [], running=True)
    assert mem[CLOSE_CHECK_KEY]["state"] == "no_forecast" and mem[BENEFIT_CHECK_KEY]["latched"]


def _temp_frame(i, *, temperature_age=40.0, humidity_age=900.0, reference_age=1200.0, quality="held"):
    """A frame whose temperature has just reported (report ``i``) while the humidity keeps its older value."""
    frame = _held(_stamp(i), humidity_age=humidity_age, temperature_age=temperature_age, reference_age=reference_age, quality=quality)
    frame.update({"humidity_reported_at": "2026-11-17T19:30:00+01:00", "temperature_reported_at": _stamp(i),
                  "skew_s": humidity_age - temperature_age})
    return frame


def _paired(mem, frame):
    """The coordinator's report state of one working sensor that delivers both channels (as in coordinator_room_session)."""
    mem["session_climate_report_state"] = {"0": {"available": True, "reports": {"temperature": frame["temperature_reported_at"],
                                                                                "humidity": frame["humidity_reported_at"]}}}
    return frame


@pytest.mark.parametrize("path", ["regular", "staggered", "mixed"])
def test_a_clear_counter_measurement_ends_the_series_8_60_8(path):
    """8 → 60 → 8 ml (threshold 24 ml): the 60 ml report ends the series, the last 8 ml is the first new confirmation."""
    mem = _held_mem()
    steps = {"regular": [("good", 8, 1), ("good", 60, 3), ("good", 8, 5)],
             "staggered": [("held", 8, 1), ("held", 60, 3), ("held", 8, 5)],
             "mixed": [("good", 8, 1), ("held", 60, 3), ("good", 8, 5)]}[path]
    for kind, benefit, i in steps:
        result = _good_step(mem, benefit, i) if kind == "good" else _held_step(mem, benefit, _held(_stamp(i)))
        assert result.action == "Continue ventilating", (path, benefit, i)
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1 and not mem[BENEFIT_CHECK_KEY]["latched"]
    assert ((_good_step(mem, 8, 7) if path != "staggered" else _held_step(mem, 8, _held(_stamp(7)))).action == "Close")


def test_an_unclear_report_is_no_counter_measurement():
    """26 ml with an older temperature: its possible error reaches below the threshold – it neither confirms nor ends the series."""
    mem = _held_mem()
    _good_step(mem, 8, 1)
    assert _held_step(mem, 26, _held(_stamp(3))).action == "Continue ventilating"
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1
    assert _good_step(mem, 8, 5).action == "Close"


def test_constant_humidity_two_new_temperature_values_confirm_once_each():
    mem = _held_mem()
    for i in (1, 3):
        result = _held_step(mem, 6, _temp_frame(i), temperature=24.0 + 0.1 * i)
    assert result.action == "Close" and mem[BENEFIT_CHECK_KEY]["channel"] == "temperature"
    assert mem[BENEFIT_CHECK_KEY]["staggered"] == 2
    # the same temperature report again, and the same value with a new time stamp, add nothing
    mem = _held_mem()
    _held_step(mem, 6, _temp_frame(1), temperature=24.1)
    _held_step(mem, 6, _temp_frame(1, temperature_age=70.0), temperature=24.1)
    _held_step(mem, 6, _temp_frame(3), temperature=24.1)
    assert mem[BENEFIT_CHECK_KEY]["low"] == 1


def test_the_older_channel_of_a_working_sensor_does_not_block_by_its_time_stamp_alone():
    # the temperature has not changed for 50 min (frame stale by that time stamp alone), the same sensor reports humidity
    old = dict(temperature_age=3000.0, quality="stale")
    mem = _held_mem()
    for i in (1, 3):
        result = _held_step(mem, 6, _paired(mem, _held(_stamp(i), **old)))
    assert result.action == "Close" and _state(mem)["close_check"] == "confirmed_staggered"
    assert _held_step(mem, 6, _paired(mem, _held(_stamp(3), humidity_age=200.0, **old))).action == "Close"   # held, not withdrawn
    # temperature and humidity from different sensors: the silent one stays a block (existing rule)
    mem = _held_mem()
    for i in (1, 3):
        result = _held_step(mem, 6, _held(_stamp(i), **old))
    assert result.action == "Continue ventilating" and not (mem.get(BENEFIT_CHECK_KEY) or {}).get("low")
    # the constant humidity of a sensor that reports its temperature: the same
    mem = _held_mem()
    for i in (1, 3):
        result = _held_step(mem, 6, _paired(mem, _temp_frame(i, humidity_age=3000.0, quality="stale")), temperature=24.0 + 0.1 * i)
    assert result.action == "Close"
    # a detected outage still withdraws the close, and so does an outdoor reference that is too old
    assert _held_step(mem, 6, _temp_frame(3), humidity=float("nan"), temperature=24.3).action == "Check sensor"
    assert not mem[BENEFIT_CHECK_KEY]["latched"]
    mem = _held_mem()
    for i in (1, 3):
        _held_step(mem, 6, _paired(mem, _held(_stamp(i), **old)))
    withdrawn = _held_step(mem, 6, _paired(mem, _held(_stamp(3), humidity_age=200.0, reference_age=3700.0, **old)))
    assert withdrawn.action == "Continue ventilating" and _state(mem)["close_check"] == "released_stale"


def test_coordinator_ticks_without_a_new_report_confirm_nothing_and_send_no_second_push():
    from custom_components.freshairiq.notification_policy import room_notification_events

    class Store:
        def __init__(self):
            self.data, self.rooms = {}, {}

        def room(self, key):
            return self.rooms.setdefault(key, {})

    store, mem, closes = Store(), _held_mem(), []
    now = datetime(2026, 11, 17, 20, 0, tzinfo=TZ)
    cycles = [(8, _held(_stamp(1))), (8, _held(_stamp(3)))] + [(8, _held(_stamp(3), humidity_age=40.0 + 30 * i)) for i in range(1, 6)]
    for i, (benefit, frame) in enumerate(cycles):
        result = _held_step(mem, benefit, frame)
        room = {**result.as_dict(), "key": "well", "name": "Wellnessraum", "active": True, "open": True, "contact_count": 1,
                "goal_state": {"hard_close": False, "goals": []}}
        events, _ = room_notification_events({"well": room}, store, now.replace(minute=i), {"notify_close": True, "action_reminder_min": None},
                                             None, sensor_alerts=lambda r: False)
        closes += events["Close"]
    assert mem[BENEFIT_CHECK_KEY]["low"] == 2 and len(closes) == 1


def test_the_class_boundary_uncertain_counts_like_held():
    """A pair closer together (uncertain: up to 180 s apart) is no worse evidence than a held one (up to 30 min).

    The draft accepted only "held" and so dropped the closer pair; the staggered path now takes both grades. The
    regular path keeps its own grades and its 90 s limit.
    """
    for quality, temperature_age in (("uncertain", 160.0), ("held", 700.0)):
        mem = _held_mem()
        for i in (1, 3):
            result = _held_step(mem, 8, _held(_stamp(i), temperature_age=temperature_age, quality=quality))
        assert result.action == "Close", quality
    assert _step(_held_mem(), _forecast(8), _stamp(1), quality="uncertain").action == "Continue ventilating"


@pytest.mark.parametrize("frame", [
    _held(_stamp(3), humidity_age=420.0),          # the humidity report is no longer new
    _held(_stamp(3), temperature_age=2600.0),      # the temperature is too old
    _held(_stamp(3), reference_age=3700.0),        # the outdoor reference is too old
    _held(_stamp(3), temperature_age=2200.0),      # would turn stale within the five minutes the benefit refers to
    _held(_stamp(3), reference_age=3400.0),
    {"quality": "held", "humidity_reported_at": _stamp(3)},   # ages unknown
    {k: v for k, v in _held(_stamp(3)).items() if k != "reference_skew_s"},   # the reference pair's offset unknown
    _held(_stamp(3), quality="stale"),
    {**_held(_stamp(3)), "max_future_offset_s": 120.0},   # a time stamp in the future
])
def test_staggered_unusable_or_missing_readings_confirm_nothing(frame):
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))
    assert _held_step(mem, 8, frame).action == "Continue ventilating"
    assert not mem[BENEFIT_CHECK_KEY]["latched"] and mem[BENEFIT_CHECK_KEY]["low"] == 1


def test_staggered_unavailable_values_and_a_missing_air_volume_confirm_nothing():
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))
    assert _held_step(mem, 8, _held(_stamp(3)), fraction=None).action == "Continue ventilating"
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))
    unavailable = _held_step(mem, 8, _held(_stamp(3)), humidity=float("nan"))   # an unavailable sensor: no close of this kind
    assert unavailable.action == "Check sensor" and not unavailable.close_recommended and not mem[BENEFIT_CHECK_KEY]["latched"]


def test_staggered_cases_near_the_threshold_and_a_drifting_outdoor_pair_confirm_nothing_and_keep_the_series():
    for benefit, frame in ((18, _held(_stamp(3))),                                   # 18 ml + possible error > 24 ml
                           (8, _held(_stamp(3), reference_skew=1500.0)),             # outdoor temperature and humidity far apart
                           (8, _held(_stamp(3), temperature_age=2300.0))):           # the room temperature may have drifted too far
        mem = _held_mem()
        _held_step(mem, benefit, _held(_stamp(1)))
        assert _held_step(mem, benefit, frame).action == "Continue ventilating", (benefit, frame)
        # the draft broke the series here (low 0); a report that does not confirm now leaves the series as it is
        assert (mem.get(BENEFIT_CHECK_KEY) or {}).get("low", 0) == (1 if benefit == 8 else 0)


def test_staggered_frames_never_lift_a_close_and_the_regular_path_is_unchanged():
    mem = _held_mem()
    _held_step(mem, 8, _held(_stamp(1)))
    assert _held_step(mem, 8, _held(_stamp(3))).action == "Close"
    for i in (5, 7):
        assert _held_step(mem, 60, _held(_stamp(i))).action == "Close"              # a staggered frame never opens again
    # excellent / acceptable frames keep their own rule (here: close and lift with the release factor)
    for i in (9, 11):
        result = _good_step(mem, 60, i)
    assert result.action == "Continue ventilating"
    # other causes keep their priority: a running moisture source keeps the window open on staggered frames too
    mem = _held_mem()
    for i in (1, 3):
        assert _held_step(mem, 8, _held(_stamp(i)), moisture_source_active=True).action != "Close"
    assert _state(mem)["close_check"] == "moisture_source"


def test_a_staggered_close_is_withdrawn_with_its_confirmation_when_its_readings_turn_stale_or_unavailable():
    for quality in ("stale", "unavailable"):
        mem = _held_mem()
        _good_step(mem, 8, 1)                                                        # one regular confirmation
        assert _held_step(mem, 8, _held(_stamp(3))).action == "Close"
        assert mem[BENEFIT_CHECK_KEY]["basis"] == "staggered"
        if quality == "stale":
            withdrawn = _held_step(mem, 8, _held(_stamp(3), humidity_age=2500.0, temperature_age=3400.0, quality="stale"))
            assert withdrawn.action == "Continue ventilating" and _state(mem)["close_check"] == "released_stale"
        else:
            assert _held_step(mem, 8, _held(_stamp(3)), humidity=float("nan")).action == "Check sensor"
        check = mem[BENEFIT_CHECK_KEY]
        assert not check["latched"] and check["low"] == 1 and "basis" not in check   # the regular confirmation stays
        # a new staggered report confirms again
        assert _held_step(mem, 8, _held(_stamp(5))).action == "Close"
    # a close confirmed by two regular frames is not withdrawn by stale readings (unchanged behaviour)
    mem = _held_mem()
    for i in (1, 3):
        _good_step(mem, 8, i)
    assert _held_step(mem, 8, _held(_stamp(3), humidity_age=2500.0, temperature_age=3400.0, quality="stale")).action == "Close"
    # an independently valid close keeps its priority over the withdrawal
    mem = _held_mem()
    for i in (1, 3):
        _held_step(mem, 8, _held(_stamp(i)))
    opts = room_close_options({**BASE, "airing_min_room_temp_c": 16.0}, {})
    room_input = _room(close_notified=True, close_notified_kind=BENEFIT_CLOSE_KIND, temperature=15.5, humidity=69.0,
                       reference_temperature=5.0, reference_humidity=80.0)
    result = evaluate_room(room_input, opts, False)
    reasons = []
    apply_benefit_close(mem, result, {**_forecast(8), "exchange_fraction": 0.25}, _held(_stamp(3), humidity_age=2500.0,
                        temperature_age=3400.0, quality="stale"), opts, 48.3, reasons, running=True)
    assert not (mem[BENEFIT_CHECK_KEY] or {}).get("latched")
    assert result.action == "Close" and result.close_kind == "temperature_limit" and mem["close_notified"]


# the bathroom of Issue #30 as an end-to-end replay (sensor states → coordinator → room, house and coach): 24 °C inside and outside,
# the battery sensor reports the humidity every two minutes and the temperature only once. A constructed course with the pattern
# of the report; the user's recorded course is in the 0.26.7.1 issue text only as a summary.
def _replay(name, start, init, steps, room, options):
    seen, original = [], golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append(copy.deepcopy(result))
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    try:
        asyncio.run(golden._run_scenario(name, {"start": start, "initial": init, "steps": steps, "options": {**golden.BASE_OPTIONS, **options},
                                                "data": {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h",
                                                         "rooms": [room], "levels": [room["floor"]]}}, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return seen


def _bath(mode):
    start = datetime(2026, 11, 18, 19, 0, tzinfo=TZ)
    init = {"sensor.t": ("24.0", T_ATTR), "sensor.h": ("78", H_ATTR), "binary_sensor.f": ("off", {"device_class": "window"}),
            "sensor.aussen_t": ("24.0", T_ATTR), "sensor.aussen_h": ("60", H_ATTR)}
    steps, rh = [{"advance": 120, "set": {"binary_sensor.f": ("on", {"device_class": "window"})}}], 78
    for i in range(20):
        rh = max(rh - 1, 66)
        change = {"sensor.h": (str(rh), H_ATTR)} if mode == "humidity" else {"sensor.t": ("24.1" if i % 2 else "24.0", T_ATTR)}
        if i % 15 == 14:
            change.update({"sensor.aussen_t": ("24.0", T_ATTR), "sensor.aussen_h": ("60", H_ATTR)})
        steps.append({"advance": 120, "set": change})
    room = golden._room("bad", "Bad", "ground_floor", temp=["sensor.t"], hum=["sensor.h"], contacts=["binary_sensor.f"], volume=9.4)
    options = {"target_rh": 55.0, "min_duration_min": 3.0, "close_delta": 0.4, "min_return_next_5_min_ml": 25.0}
    return _replay("bath", start, init, steps, room, options)


def test_bath_replay_closes_on_new_humidity_reports_with_the_old_temperature_and_shows_it():
    cycles = _bath("humidity")
    rooms = [c["rooms"]["bad"] for c in cycles]
    first = next(i for i, r in enumerate(rooms) if r["action"] == "Close")
    room, cycle = rooms[first], cycles[first]
    assert room["close_kind"] == BENEFIT_CLOSE_KIND and room["measurement_frame_quality"] == "held"
    assert room["forecast_5_min_benefit_ml"] < room["close_benefit_threshold_ml"] and room["close_benefit_confirmations"] == 2
    assert room["close_check"] == "confirmed_staggered" and room["close_benefit_basis"] == "staggered"
    assert room["humidity"] > 55 and not room.get("goals_reached_now")
    rec = cycle["intelligent_recommendation"]
    assert rec["kind"] == "close" and cycle["close_reason_kind"] == BENEFIT_CLOSE_KIND
    assert rec["summary"].startswith("Weiteres Lüften entfernt kaum noch Feuchtigkeit")
    # before the close the coach says what the confirmation needs; no close before two counted humidity reports
    waiting = [c.get("remaining_duration_reason") or "" for c, r in zip(cycles[:first], rooms[:first]) if r.get("close_benefit_confirmations") == 1]
    assert waiting and all("geeignete Feuchtemeldungen" in w for w in waiting)
    # the temperature stays unchanged on a sensor that keeps reporting its humidity: a working device – the close holds also
    # when the unchanged temperature is older than a held pair may be (frame "stale" only by that time stamp)
    later = [r for r in rooms[first:] if r.get("open")]
    assert all(r["action"] == "Close" for r in later)
    assert any(r["measurement_frame_quality"] == "stale" for r in later)


def test_bath_replay_with_constant_humidity_closes_on_two_new_temperature_values():
    """The other constant channel: the humidity stays at 78 %, the same sensor reports the temperature every two minutes."""
    cycles = _bath("temperature")
    rooms = [c["rooms"]["bad"] for c in cycles]
    first = next(i for i, r in enumerate(rooms) if r["action"] == "Close")
    assert rooms[first]["close_kind"] == BENEFIT_CLOSE_KIND and rooms[first]["close_check"] == "confirmed_staggered"
    assert {r["humidity"] for r in rooms} == {78}
    # never before two counted temperature reports, and each report counted once
    assert rooms[first - 1]["close_benefit_confirmations"] == 1 and all(r["action"] != "Close" for r in rooms[:first])
    assert all(r["action"] == "Close" for r in rooms[first:] if r.get("open"))


# ------------------------------------------------------------------------------------------------ field cases 19./20.11.

def _field(start, init, events, end, *, key, volume, sources, tick=120):
    """Replay of a recorded airing: sensors report only at the listed times (value changes visible in the export)."""
    timeline, at = [], start
    for when, change in sorted(events, key=lambda e: e[0]):
        moment = datetime.fromisoformat(f"{start.date().isoformat()}T{when}").replace(tzinfo=TZ)
        while (moment - at).total_seconds() > tick:
            at = at + timedelta(seconds=tick)
            timeline.append((at, {}))
        timeline.append((moment, change))
        at = moment
    steps, now = [], start
    for moment, change in timeline:
        sets = {}
        for entity, value in change.items():
            attrs = {"device_class": "window"} if entity.startswith("binary_sensor") else H_ATTR if entity.endswith("h") else T_ATTR
            sets[entity] = (str(value), attrs)
        steps.append({"advance": int(round((moment - now).total_seconds())), "set": sets, "label": moment.strftime("%H:%M:%S")})
        now = moment
        if moment.strftime("%H:%M:%S") >= end:
            break
    room = golden._room(key, key, "basement", temp=["sensor.t"], hum=["sensor.h"], contacts=["binary_sensor.f"], volume=volume,
                        orientation="south", extra={"moisture_sources": sources})
    seen = _replay(key, start, init, steps, room, WELLNESS_OPTIONS)
    return [(step["label"], cycle["rooms"][key], cycle) for step, cycle in zip(steps, seen[1:])]


OUT = ("sensor.aussen_t", "sensor.aussen_h")
# wellness room 19.11. (diagnostics 2026-11-20T08-15-58Z, installed 0.26.7.2): the export keeps only routine samples during the
# airing, so a report time is the first sample showing the new value (at most ~2 min late); repeated reports of an unchanged
# value are not in the export. The outdoor reference changed about once an hour.
WELLNESS_1911 = [
    ("19:45:31", {OUT[0]: 8.6, OUT[1]: 92}), ("19:49:47", {"sensor.t": 20.6}), ("19:51:39", {"sensor.h": 71}),
    ("19:52:00", {"binary_sensor.f": "on"}),
    ("19:52:29", {"sensor.h": 72}), ("19:54:58", {"sensor.h": 74}), ("19:59:08", {"sensor.h": 73}), ("20:01:32", {"sensor.h": 72}),
    ("20:04:08", {"sensor.h": 71}), ("20:08:38", {"sensor.h": 70}), ("20:10:45", {"sensor.h": 68}), ("20:12:46", {"sensor.h": 67}),
    ("20:16:58", {"sensor.h": 66}), ("20:20:58", {"sensor.t": 20.5}), ("20:26:58", {"sensor.h": 65}), ("20:41:57", {"sensor.h": 64}),
    ("20:46:08", {"sensor.t": 20.1}), ("20:52:30", {OUT[0]: 8.1, OUT[1]: 91}), ("20:56:41", {"sensor.h": 63}),
    ("21:20:54", {"sensor.t": 19.8}), ("21:38:08", {"sensor.h": 62}), ("21:40:33", {"sensor.t": 19.7}),
    ("21:50:20", {OUT[0]: 7.6, OUT[1]: 90}), ("22:21:58", {"sensor.t": 19.5}), ("22:34:40", {"sensor.t": 19.4, "sensor.h": 61}),
    ("22:51:35", {OUT[0]: 6.8, OUT[1]: 95}), ("22:55:43", {"sensor.h": 60}), ("23:01:59", {"sensor.t": 19.3}),
    ("23:09:40", {"binary_sensor.f": "off"}),
]
WELLNESS_1911_INIT = {"sensor.t": ("20.3", T_ATTR), "sensor.h": ("71", H_ATTR), "binary_sensor.f": ("off", {"device_class": "window"}),
                      "sensor.aussen_t": ("8.2", T_ATTR), "sensor.aussen_h": ("91", H_ATTR)}


def _wellness_1911(extra=()):
    return _field(datetime(2026, 11, 19, 19, 40, tzinfo=TZ), WELLNESS_1911_INIT, WELLNESS_1911 + list(extra), "23:09:30",
                  key="wellnessraum", volume=48.3, sources=["shower", "sauna"])


def test_wellness_1911_replay_closes_on_the_two_last_recorded_reports():
    """197 min, 71 → 60 % with target 58 %: why 0.26.7.2 as installed gave no close.

    Shower/sauna and its follow-up keep the window open first. From about 20:46 the benefit stays just below the room's
    threshold (19–23 ml against 24 ml), but no humidity report meets a synchronous pair: room temperature and humidity are
    reported apart and the outdoor reference only about once an hour – nothing could count. The staggered path counts the
    humidity report at 22:55 and the temperature report at 23:01 (the other reports stay within their possible error of the
    threshold): close at 23:01, eight minutes before the window was closed by hand.
    """
    rows = _wellness_1911()
    assert {r.get("close_check") for t, r, _ in rows if "19:57" <= t <= "20:10"} == {"moisture_source"}
    below = [(t, r) for t, r, _ in rows if t >= "20:47" and r.get("active")]
    assert all(r["forecast_5_min_benefit_ml"] < r["close_benefit_threshold_ml"] for _, r in below)
    assert {r["measurement_frame_quality"] for _, r in below} <= {"uncertain", "held", "stale"}
    assert next(t for t, r in below if r["close_check"] == "confirming") == "22:55:43"
    first = next(t for t, r in below if r["action"] == "Close")
    assert first == "23:01:59"
    assert all(r["close_kind"] == BENEFIT_CLOSE_KIND and r["close_benefit_basis"] == "staggered" for t, r in below if t >= first)


def test_wellness_1911_replay_with_outdoor_reports_every_five_minutes_closes_on_staggered_reports():
    """Not recorded: the same airing with an outdoor reference reporting every 5 min (same values) closes at 21:40."""
    extra, at = [], datetime(2026, 11, 19, 19, 55, tzinfo=TZ)
    while at.strftime("%H:%M") < "23:09":
        when = at.strftime("%H:%M:%S")
        current = [e[1] for e in WELLNESS_1911 if e[0] <= when and OUT[0] in e[1]][-1]   # the value recorded at that time
        extra.append((when, {OUT[0]: current[OUT[0]], OUT[1]: current[OUT[1]]}))
        at += timedelta(minutes=5)
    rows = _wellness_1911(extra)
    first = next((t, r, c) for t, r, c in rows if r["action"] == "Close")
    assert first[0] == "21:40:33" and first[1]["close_kind"] == BENEFIT_CLOSE_KIND
    assert first[1]["close_check"] == "confirmed_staggered" and first[1]["close_benefit_basis"] == "staggered"
    assert first[2]["intelligent_recommendation"]["kind"] == "close"


# bathroom 20.11. (same export): 31.2 m³, constant 20.3 °C; humidity 60 % at the opening, 59 % from about 07:07, 58 % (the
# target) reported at 07:21:25 – the close came in the same second, 21 s before the window was closed. The export holds no
# temperature report during the airing; a close on that report shows that one arrived (with the temperature older than
# 30 min the frame would be stale) – its time is not recorded, here 07:20:10.
BATH_2011 = [
    ("06:48:46", {"sensor.t": 20.3}), ("07:01:44", {OUT[0]: 3.8, OUT[1]: 92}), ("07:04:44", {"sensor.h": 60}),
    ("07:04:50", {"binary_sensor.f": "on"}), ("07:07:01", {"sensor.h": 59}), ("07:20:10", {"sensor.t": 20.3}),
    ("07:21:25", {"sensor.h": 58}), ("07:21:46", {"binary_sensor.f": "off"}),
]


def test_bath_2011_replay_closes_when_the_target_is_reported_and_the_benefit_never_ran_out():
    init = {"sensor.t": ("20.4", T_ATTR), "sensor.h": ("56", H_ATTR), "binary_sensor.f": ("off", {"device_class": "window"}),
            "sensor.aussen_t": ("3.9", T_ATTR), "sensor.aussen_h": ("91", H_ATTR)}
    rows = _field(datetime(2026, 11, 20, 6, 40, tzinfo=TZ), init, BATH_2011, "07:21:40", key="badezimmer", volume=31.2,
                  sources=["shower", "bath"])
    first = next(t for t, r, _ in rows if r["action"] == "Close")
    assert first == "07:21:25"
    _, room, cycle = next(x for x in rows if x[0] == first)
    assert room["close_kind"] == "goals_reached" and room["humidity"] == 58
    assert cycle["intelligent_recommendation"]["kind"] == "close"
    # the 5-minute benefit stayed above the room's threshold (15.6 ml) – there was no exhausted benefit to confirm earlier
    running = [r for t, r, _ in rows if r.get("active") and t < first]
    assert running and all(r["forecast_5_min_benefit_ml"] >= r["close_benefit_threshold_ml"] for r in running)
    assert room["close_benefit_threshold_ml"] == pytest.approx(15.6, abs=0.1)


def test_diagnostics_keep_the_state_of_the_check_for_an_airing_room_only():
    from custom_components.freshairiq.diagnostics_privacy import _ROOM_KEYS, _TREND_ROOM_KEYS, _pick

    opts = room_close_options(BASE, {})
    mem = _held_mem()
    for i in (1, 3):
        _held_step(mem, 8, _held(_stamp(i)))
    airing = {"key": "well", **benefit_close_state(mem, _forecast(8), opts, 48.3)}
    idle = {"key": "bad", **benefit_close_state({"session_active": False, CLOSE_CHECK_KEY: None}, _forecast(8), opts, 9.4)}
    assert _pick(airing, _TREND_ROOM_KEYS) == {"key": "well", "close_check": "confirmed_staggered", "close_benefit_basis": "staggered"}
    assert _pick(idle, _TREND_ROOM_KEYS) == {"key": "bad"}                       # nothing added to the other rooms' samples
    assert _pick(airing, _ROOM_KEYS)["close_benefit_threshold_ml"] == pytest.approx(24.1, abs=0.1)
    assert _pick(airing, _ROOM_KEYS)["close_benefit_confirmations"] == 2

    class Broken:
        data_quality = "error"

    assert benefit_close_state(mem, _forecast(8), opts, 48.3, Broken())["close_check"] == "sensor_unavailable"
