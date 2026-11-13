"""0.26.7.0 F11: there is no maximum airing duration.

Owner rule: as long as the outdoor/reference air is drier and still removes moisture, FreshAirIQ never ends an airing
because of time – not at 5/10/20/30/60/120 min, not at the target humidity, not at the planned duration, not on a
small predicted return and not on a humidity plateau. It may close when the air no longer helps (case C: moisture
coming in, difference at most ``close_delta``, room already too dry) or when the user's own, explicitly configured
temperature limit is reached (case D; the reason names the temperature). There is no hidden second time limit.
"""
from __future__ import annotations

import inspect

import pytest

from custom_components.freshairiq import model
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.consolidation import stabilise_recommendation
from custom_components.freshairiq.live_coach import refine_live_recommendation
from custom_components.freshairiq.model import (
    AIR_NO_LONGER_HELPS_CLOSE_REASON,
    ROOM_TOO_DRY_CLOSE_REASON,
    TEMPERATURE_LIMIT_CLOSE_REASON,
    RoomInput,
    absolute_humidity,
    evaluate_room,
    temperature_limit_reached,
)
from custom_components.freshairiq.validation import option_relationship_error, repair_option_relationships
from tests._source import COMP

MINUTES = (5.0, 10.0, 20.0, 30.0, 60.0, 120.0)
PROFILES = ("comfort", "balanced", "dehumidify", "energy_saving")


def _options(**extra) -> dict:
    return {**DEFAULT_OPTIONS, "min_duration_min": 3.0, "max_duration_min": 20.0, **extra}


def _room(minutes: float = 30.0, **extra) -> RoomInput:
    """Living room 21 °C / 60 %, outdoor 6 °C / 80 % (about 4 g/m³ drier), readings fresh."""
    values = dict(key="wz", name="Wohnzimmer", temperature=21.0, humidity=60.0, reference_temperature=6.0,
                  reference_humidity=80.0, volume_m3=40.0, contact_open=True, contact_open_seconds=int(minutes * 60),
                  session_active=True, session_elapsed_min=minutes, session_start_temp=21.5, learning_rate=0.03,
                  session_fresh_measurements=4, session_target_min=10.0,
                  session_start_ah=absolute_humidity(21.5, 64.0))
    values.update(extra)
    return RoomInput(**values)


def _continues(room: RoomInput, options: dict | None = None, cross: bool = False) -> bool:
    result = evaluate_room(room, options or _options(), cross)
    return result.action == "Continue ventilating" and not result.close_recommended


# --------------------------------------------------------------------------------------------------- case A

@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("minutes", MINUTES)
def test_a_drier_outdoor_air_never_ends_by_time(minutes, profile):
    assert _continues(_room(minutes), _options(operating_profile=profile)), (minutes, profile)


@pytest.mark.parametrize("minutes", MINUTES)
@pytest.mark.parametrize("volume", [6.0, 12.0, 40.0, 80.0, 200.0])
def test_a_small_and_large_rooms(minutes, volume):
    assert _continues(_room(minutes, volume_m3=volume)), (minutes, volume)


@pytest.mark.parametrize("minutes", MINUTES)
def test_a_cross_ventilation_and_several_windows(minutes):
    assert _continues(_room(minutes), cross=True)
    assert _continues(_room(minutes, airflow_factor=1.6) if "airflow_factor" in RoomInput.__dataclass_fields__ else _room(minutes), cross=True)


@pytest.mark.parametrize("minutes", MINUTES)
def test_a_below_the_target_humidity_and_with_a_small_return(minutes):
    below_target = _room(minutes, humidity=50.0, session_start_ah=absolute_humidity(21.5, 51.0))
    assert _continues(below_target, _options(target_rh=58.0))
    small_return = _room(minutes, learning_rate=0.003)
    result = evaluate_room(small_return, _options(), False)
    assert result.moisture_effect_next_5_min_ml < _options()["min_return_next_5_min_ml"]
    assert result.action == "Continue ventilating"


@pytest.mark.parametrize("minutes", MINUTES)
def test_a_plateau_does_not_close_while_the_air_still_dries(minutes):
    assert _continues(_room(minutes, humidity_plateau=True))
    assert _continues(_room(minutes, humidity_plateau=True, mechanical_only=True))   # room aired by its exhaust fan


def test_a_planned_duration_and_the_stored_maximum_are_no_end_point():
    for minutes in (9.9, 10.0, 10.5, 20.0, 20.1, 40.0):
        assert _continues(_room(minutes, session_target_min=10.0)), minutes
    # a stored small maximum (older setups) does not shorten anything
    assert _continues(_room(31.0), _options(max_duration_min=5.0))


# --------------------------------------------------------------------------------------------------- case B

@pytest.mark.parametrize("minutes", MINUTES)
def test_b_humidity_rising_inside_with_drier_air_keeps_ventilating(minutes):
    # source active but not (yet) recognised: the room got more humid since the start although aired
    rising = _room(minutes, humidity=66.0, session_start_ah=absolute_humidity(21.0, 62.0))
    assert _continues(rising)
    recognised = _room(minutes, humidity=66.0, moisture_source_active=True, moisture_source_label="Dusche")
    result = evaluate_room(recognised, _options(), False)
    assert result.action == "Continue ventilating" and result.reason.startswith("Active internal moisture source")


# --------------------------------------------------------------------------------------------------- case C

@pytest.mark.parametrize("minutes", MINUTES)
def test_c_air_no_longer_drier_closes(minutes):
    exhausted = _room(minutes, reference_temperature=20.0, reference_humidity=62.0)   # ~0.1 g/m³ drier
    result = evaluate_room(exhausted, _options(), False)
    assert result.delta_g_m3 <= _options()["close_delta"]
    assert result.action == "Close" and result.reason == AIR_NO_LONGER_HELPS_CLOSE_REASON


def test_c_moisture_coming_in_closes_even_before_the_minimum_duration():
    wet = _room(2.0, reference_temperature=21.0, reference_humidity=75.0)
    assert evaluate_room(wet, _options(), False).action == "Close"


def test_c_room_already_too_dry_closes_with_its_own_reason():
    # Testvermerk 0.26.7.0 final hotfix F11-B: this test (added in the previous round) pinned the reported defect – the
    # lower humidity setting ``humidify_below_rh`` closed on its own. It is no close reason any more.
    dry = _room(30.0, humidity=33.0, reference_temperature=-5.0, session_start_ah=absolute_humidity(21.5, 36.0))
    result = evaluate_room(dry, _options(), False)
    assert result.delta_g_m3 > _options()["close_delta"]
    assert result.action == "Continue ventilating" and result.reason != ROOM_TOO_DRY_CLOSE_REASON


# --------------------------------------------------------------------------------------------------- case D

def test_d_without_a_configured_limit_there_is_no_temperature_close():
    cold_room = _room(60.0, temperature=16.0, session_start_temp=21.0)
    assert not temperature_limit_reached(cold_room, _options())
    assert _continues(cold_room)


@pytest.mark.parametrize("minutes", [5.0, 60.0])
def test_d_the_configured_limit_closes_and_names_the_temperature(minutes):
    options = _options(airing_min_room_temp_c=18.0)
    above = _room(minutes, temperature=19.0)
    assert _continues(above, options)
    reached = _room(minutes, temperature=18.0)
    result = evaluate_room(reached, options, False)
    assert result.action == "Close" and result.reason == TEMPERATURE_LIMIT_CLOSE_REASON
    assert "temperature" in result.reason and "not because enough moisture" in result.reason


def test_d_the_limit_does_not_apply_while_outdoor_air_is_warmer_or_urgent():
    options = _options(airing_min_room_temp_c=18.0)
    warm_outside = _room(30.0, temperature=17.5, reference_temperature=19.0, reference_humidity=40.0)
    assert not temperature_limit_reached(warm_outside, options)
    critical_co2 = _room(30.0, temperature=17.5, co2=1800.0)
    assert evaluate_room(critical_co2, options, False).action != "Close"


def test_d_limit_is_validated_and_repaired():
    assert option_relationship_error({**DEFAULT_OPTIONS, "airing_min_room_temp_c": 0.0}) is None
    assert option_relationship_error({**DEFAULT_OPTIONS, "airing_min_room_temp_c": 18.0}) is None
    for bad in (2.0, 35.0):
        assert option_relationship_error({**DEFAULT_OPTIONS, "airing_min_room_temp_c": bad}) == "invalid_airing_temperature_limit"
        assert repair_option_relationships({**DEFAULT_OPTIONS, "airing_min_room_temp_c": bad})["airing_min_room_temp_c"] == 0.0
    assert DEFAULT_OPTIONS.get("airing_min_room_temp_c", 0.0) == 0.0   # no hidden default limit


# --------------------------------------------------------------------------------------------------- CO2

@pytest.mark.parametrize("minutes", MINUTES)
def test_co2_only_and_co2_with_humidity(minutes):
    options = _options(co2_warn=1000, co2_critical=1400)
    co2_high = _room(minutes, co2=1200.0, session_co2_only=True, co2_lead_latched=True)
    assert _continues(co2_high, options)
    combined = _room(minutes, co2=1200.0, co2_lead_latched=True)
    assert _continues(combined, options)
    # CO2 down, air still drier: not ended by time either
    assert _continues(_room(minutes, co2=600.0, session_co2_only=True), options)


# --------------------------------------------------------------------------------------------------- stored close

def test_stored_close_is_lifted_when_drying_is_proven_again_and_kept_otherwise():
    exhausted = dict(reference_temperature=20.0, reference_humidity=62.0)
    first = evaluate_room(_room(30.0, **exhausted), _options(), False)
    assert first.action == "Close"
    still = evaluate_room(_room(31.0, close_notified=True, **exhausted), _options(), False)
    assert still.action == "Close"
    proven = evaluate_room(_room(32.0, close_notified=True), _options(), False)          # outdoor air ~4 g/m³ drier again
    assert proven.action == "Continue ventilating"
    stale = evaluate_room(_room(32.0, close_notified=True, measurements_stale=True), _options(), False)
    assert stale.action == "Close"                                                      # not lifted on stale readings


# --------------------------------------------------------------------------------------------------- sensor states

@pytest.mark.parametrize("minutes", [20.0, 120.0])
def test_stale_and_missing_readings_do_not_bring_back_a_time_limit(minutes):
    stale = _room(minutes, measurements_stale=True)
    assert evaluate_room(stale, _options(), False).action != "Close"
    fallback = _room(minutes, session_fresh_measurements=0)
    result = evaluate_room(fallback, _options(), False)
    assert result.action == "Continue ventilating"


@pytest.mark.parametrize("bad", [{"humidity": float("nan")}, {"reference_humidity": float("nan")}, {"temperature": float("inf")}])
def test_unavailable_or_contradictory_values_never_close(bad):
    result = evaluate_room(_room(120.0, **bad), _options(), False)
    assert result.action != "Close" and not result.close_recommended


# --------------------------------------------------------------------------------------------------- house / floor / coach

def _active(key, floor, minutes, **extra):
    room = {"key": key, "name": key.title(), "floor": floor, "calculation_enabled": True, "data_quality": "ok",
            "active": True, "opening_state": "open", "close_decision_ready": True, "session_elapsed_min": minutes,
            "session_target_min": 10.0, "action": "Continue ventilating", "close_recommended": False, "delta_g_m3": 3.0,
            "volume_m3": 40.0, "forecast_5_min_moisture_effect_ml": 6.0, "moisture_effect_next_5_min_ml": 6.0,
            "forecast_5_min_temperature_change_c": -0.1, "efficiency_ml_per_01c": 40.0,
            "goal_state": {"hard_close": False, "goals": []}}
    room.update(extra)
    return room


@pytest.mark.parametrize("minutes", MINUTES)
def test_house_floor_and_coach_do_not_add_a_time_limit(minutes):
    rooms = {"wz": _active("wz", "eg", minutes), "bad": _active("bad", "og", minutes), "kueche": _active("kueche", "eg", minutes)}
    rec = {"kind": "continue", "status": "ventilation_running", "room_keys": list(rooms), "duration_min": 1.0, "reasons": []}
    coach = refine_live_recommendation(rooms, _options(), dict(rec))
    assert coach["kind"] == "continue"
    if minutes > 10.0:
        assert "noch ca." not in coach["instruction"]           # no countdown that reads like a time limit
    final = stabilise_recommendation(dict(coach), rooms, _options())
    assert final["kind"] == "continue"
    # exhausted air: the coach and the house close as before
    for room in rooms.values():
        room["delta_g_m3"] = 0.2
    assert refine_live_recommendation(rooms, _options(), dict(rec))["kind"] == "close"


# --------------------------------------------------------------------------------------------------- no hidden limit

def test_no_hidden_time_limit_in_the_decision_code():
    running_close = inspect.getsource(model._running_close)
    assert "max_duration" not in running_close
    coach = (COMP / "live_coach.py").read_text(encoding="utf-8")
    close_block = coach[coach.index("air_no_longer_helps ="):coach.index('"kind": "close", "status": "close_windows", "title": "Jetzt schließen",\n            "instruction": close_instruction(active),\n            "summary": "FreshAirIQ hat')]
    assert "max_duration" not in close_block
    consolidation = (COMP / "consolidation.py").read_text(encoding="utf-8")
    hard = consolidation[consolidation.index("hard_closing = ["):consolidation.index("closing_keys =")]
    assert "max_duration" not in hard and "session_elapsed_min" not in hard
    # the long-opening monitor only damps a close of a room that itself says Close – never a drying room
    tolerated = consolidation[consolidation.index("tolerated_long_open = ["):consolidation.index("tolerated_keys =")]
    assert 'r.get("close_recommended")' in tolerated
    room_model = (COMP / "coordinator_room_model.py").read_text(encoding="utf-8")
    assert room_model.count("max_duration_min=NO_DURATION_LIMIT_MIN") == 2   # forecasts run without an end point


# --------------------------------------------------------------------------------------------------- end to end

def _golden():
    import sys
    from pathlib import Path
    tools = Path(__file__).resolve().parents[1] / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import coordinator_golden as golden  # noqa: PLC0415 – the harness installs its Home Assistant stub
    return golden


def _chain(outdoor_after: tuple[float, float] | None = None) -> list[dict]:
    """Real coordinator chain: one bedroom aired 125 min against clearly drier outdoor air; the humidity falls and
    then stays flat (plateau, small return). Optionally the outdoor air turns humid at the end."""
    import asyncio
    from datetime import datetime

    golden = _golden()
    temp = {"device_class": "temperature", "unit_of_measurement": "°C"}
    hum = {"device_class": "humidity", "unit_of_measurement": "%"}
    rooms = [golden._room("s", "Schlafzimmer", "ground_floor", temp=["sensor.s_t"], hum=["sensor.s_h"],
                          contacts=["binary_sensor.s_f"], volume=40, sort=0)]
    initial = {"sensor.aussen_t": (6.0, temp), "sensor.aussen_h": (80.0, hum), "sensor.s_t": (21.0, temp),
               "sensor.s_h": (68.0, hum), "binary_sensor.s_f": ("off", {"device_class": "window"})}
    steps = [{"advance": 60, "label": "idle"}, {"advance": 60, "set": {"binary_sensor.s_f": "on"}, "label": "open"}]
    h = 68.0
    for i in range(125):
        h = max(h - 0.8, 58.0)
        steps.append({"advance": 60, "set": {"sensor.s_h": round(h + (0.01 if i % 2 else 0.0), 2)}})
    if outdoor_after:
        steps.append({"advance": 60, "set": {"sensor.aussen_t": outdoor_after[0], "sensor.aussen_h": outdoor_after[1]}})
        steps.append({"advance": 60, "set": {"sensor.s_h": 58.02}})
        steps.append({"advance": 60, "set": {"sensor.s_h": 58.0}})
    data = {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": rooms, "levels": ["ground_floor"]}
    scenario = {"start": datetime(2026, 11, 10, 18, 0, tzinfo=golden.TZ), "data": data,
                "options": {**golden.BASE_OPTIONS, "min_duration_min": 3, "max_duration_min": 20}, "steps": steps, "initial": initial}
    seen: list[dict] = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append(result)
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    try:
        asyncio.run(golden._run_scenario("f11", scenario, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return seen


def test_end_to_end_no_close_by_time_from_sensor_to_dashboard_and_push():
    from custom_components.freshairiq.notification_policy import effective_room_action

    cycles = _chain()
    running = [c for c in cycles if c["rooms"]["s"].get("active") and _minutes(c) >= 5.0]
    assert running and max(_minutes(c) for c in running) >= 120.0
    for data in running:
        room, rec = data["rooms"]["s"], data["intelligent_recommendation"]
        assert room["action"] == "Continue ventilating" and not room["close_recommended"], _minutes(data)
        assert rec["kind"] == "continue", (_minutes(data), rec["kind"], rec.get("status"))
        assert effective_room_action(room, rec, data["rooms"]) != "Close"
        assert room.get("house_aligned_action") != "close"


def test_end_to_end_close_comes_when_the_outdoor_air_no_longer_dries():
    from custom_components.freshairiq.notification_policy import effective_room_action

    final = _chain(outdoor_after=(14.0, 93.0))[-1]
    room, rec = final["rooms"]["s"], final["intelligent_recommendation"]
    assert room["action"] == "Close" and room["close_recommended"]
    assert rec["kind"] == "close"
    assert effective_room_action(room, rec, final["rooms"]) == "Close"


def _minutes(data: dict) -> float:
    try:
        return float(data["rooms"]["s"].get("session_elapsed_min") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def test_invalid_temperature_limit_values_never_close():
    for bad in ("x", [], {}):
        assert not temperature_limit_reached(_room(30.0, temperature=10.0), _options(airing_min_room_temp_c=bad))


def test_reachable_other_goal_holds_a_low_return_close_once_the_air_no_longer_dries():
    from custom_components.freshairiq.consolidation import aggregate_close_allowed
    goal = {"hard_close": False, "goals": [{"id": "humidity", "active": True}, "x",
                                           {"id": "co2", "active": True, "reached": False, "achievable_now": True}]}
    rooms = [{"key": "a", "action": "Continue ventilating", "close_decision_ready": True, "session_elapsed_min": 30.0,
              "delta_g_m3": 0.2, "goal_state": goal}]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=False) is False
    rooms[0]["goal_state"] = {"hard_close": False, "goals": []}
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=False) is True


def test_fan_switched_off_at_its_maximum_runtime_is_completed_not_manual_off():
    from custom_components.freshairiq.fan_automation import _own_state
    room = {"configured_actuators": {"window_open": False}}
    snap = {"blocked": True, "reason": "max_runtime"}
    assert _own_state("recommendation", False, False, "continue_ventilating", room, snap, "off", "confirmed") == ("completed", None)
    by_hand = {"blocked": True, "reason": "manual_off"}
    assert _own_state("recommendation", False, False, "continue_ventilating", room, by_hand, "off", "confirmed") == ("manual_off", None)
