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
from datetime import datetime
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
from custom_components.freshairiq.localize import to_english  # noqa: E402
from custom_components.freshairiq.close_wording import benefit_close, close_cause, fan_stop_message, goal_close  # noqa: E402
from custom_components.freshairiq.consolidation import stabilise_recommendation  # noqa: E402
from custom_components.freshairiq.model import (  # noqa: E402
    AIR_NO_LONGER_HELPS_CLOSE_REASON, BENEFIT_CLOSE_KIND, RoomInput, evaluate_room,
)
from custom_components.freshairiq.room_close_strategy import (  # noqa: E402
    BENEFIT_CHECK_KEY, apply_benefit_close, benefit_close_state, benefit_next5_ml, benefit_threshold_ml,
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
    assert to_english(second.reason).endswith(
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
    assert to_english(fan_stop_message(room)) == "Further airing hardly removes moisture any more. Switch off the fan."
    assert to_english(close_cause([room])[1]) == "Further airing hardly removes moisture any more – the humidity target is not reached yet"


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
    rooms = {"well": _live_room()}
    rec = {"kind": "continue", "room_keys": ["well"], "duration_min": 3.0}
    live = refine_live_recommendation(rooms, {**BASE, "max_duration_min": 20.0}, rec)
    assert live["live_coach_time_state"] == "reassessing" and live["live_coach_remaining_min"] is None
    reason = "Restzeit nicht bestimmbar – geschlossen wird, sobald zwei neue Messungen unter 24 ml in 5 min liegen (jetzt etwa 20 ml)"
    assert live["live_coach_time_reason"] == reason
    assert to_english(reason) == ("Remaining time cannot be determined – the airing closes once two new readings are below 24 ml in "
                                  "5 min (now about 20 ml)")
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
        assert "Restzeit nicht bestimmbar" not in to_english(out["live_coach_time_reason"])


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
