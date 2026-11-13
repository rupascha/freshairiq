"""0.26.7.0 final hotfix: three reproduced close/forecast defects (F11-A, F11-B, F11-C) and the binding rule.

Rule: while the airing still takes moisture out according to reliable physical data, FreshAirIQ never asks to close
– unless the explicitly configured temperature limit (``airing_min_room_temp_c``) is reached.

F11-A  summer_cooling, room 28 °C / 70 %, outdoor 27.5 °C / 35 % (≈ 9.76 g/m³ drier), window open: was "Close"
       ("outdoor air no longer cooler"). The summer warming close now needs air that no longer dries.
F11-B  dehumidify, room 22 °C / 30 %, outdoor 10 °C / 20 % (≈ 3.93 g/m³ drier): was "Close" because the room was
       below ``humidify_below_rh``. That setting is no close reason on its own any more.
F11-C  forecast horizon 60 min, 10 min running, ``max_duration_min=20``: the forecast reported "optimal close in
       10 min, reason max_duration". The stored maximum is no end point; a running airing shows no forecast close time.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.consolidation import aggregate_close_allowed, stabilise_recommendation
from custom_components.freshairiq.forecast import horizon_forecast
from custom_components.freshairiq.model import (
    SUMMER_WARMING_CLOSE_REASON, TEMPERATURE_LIMIT_CLOSE_REASON, RoomInput, absolute_humidity, evaluate_room,
)
from tests._source import COMP


def _room(t, rh, rt, rrh, minutes=20.0, **extra) -> RoomInput:
    values = dict(key="r", name="Raum", temperature=t, humidity=rh, reference_temperature=rt, reference_humidity=rrh,
                  volume_m3=40.0, contact_open=True, contact_open_seconds=int(minutes * 60), session_active=True,
                  session_elapsed_min=minutes, session_start_temp=t, learning_rate=0.03, session_fresh_measurements=4)
    values.update(extra)
    return RoomInput(**values)


SUMMER = {**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}
DEHUMIDIFY = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify"}


# --------------------------------------------------------------------------------------------------- F11-A

def test_f11_a_summer_profile_keeps_ventilating_while_the_air_dries():
    result = evaluate_room(_room(28.0, 70.0, 27.5, 35.0), SUMMER, False)
    assert result.delta_g_m3 == pytest.approx(9.76, abs=0.05)
    assert result.action == "Continue ventilating" and not result.close_recommended
    assert result.reason != SUMMER_WARMING_CLOSE_REASON


@pytest.mark.parametrize("minutes", [5.0, 20.0, 60.0, 120.0])
def test_f11_a_warmer_room_without_a_user_limit_is_no_close_reason(minutes):
    for outdoor in (27.5, 28.0, 30.0):           # outdoor air as warm as or warmer than the room
        result = evaluate_room(_room(28.0, 70.0, outdoor, 30.0, minutes), SUMMER, False)
        assert result.delta_g_m3 > 0.4 and result.action == "Continue ventilating", (minutes, outdoor)


def test_f11_a_summer_warming_still_closes_when_the_air_no_longer_dries():
    result = evaluate_room(_room(26.0, 50.0, 29.0, 60.0, 5.0), SUMMER, False)      # outdoor warmer and more humid
    assert result.action == "Close" and result.reason == SUMMER_WARMING_CLOSE_REASON


def test_f11_a_cooling_start_temperature_is_no_close_limit():
    for start in (20.0, 24.0, 30.0):
        options = {**SUMMER, "cooling_start_temp_c": start}
        assert evaluate_room(_room(28.0, 70.0, 27.5, 35.0), options, False).action == "Continue ventilating", start


# --------------------------------------------------------------------------------------------------- F11-B

def test_f11_b_lower_humidity_setting_is_no_close_reason():
    result = evaluate_room(_room(22.0, 30.0, 10.0, 20.0), DEHUMIDIFY, False)
    assert result.delta_g_m3 == pytest.approx(3.93, abs=0.05)
    assert result.action == "Continue ventilating" and not result.close_recommended


@pytest.mark.parametrize("profile", ["comfort", "balanced", "dehumidify", "energy_saving"])
@pytest.mark.parametrize("limit", [30.0, 35.0, 45.0])
def test_f11_b_below_the_lower_setting_in_every_profile(profile, limit):
    options = {**DEFAULT_OPTIONS, "operating_profile": profile, "humidify_below_rh": limit}
    assert evaluate_room(_room(22.0, 28.0, 10.0, 20.0), options, False).action == "Continue ventilating"


def test_f11_b_the_setting_keeps_its_other_use():
    from custom_components.freshairiq import intervention
    assert "humidify_below_rh" in (COMP / "intervention.py").read_text(encoding="utf-8")
    assert hasattr(intervention, "__name__")


# --------------------------------------------------------------------------------------------------- F11-C

def _forecast(**extra):
    args = dict(current_ah=12.0, source_ah=6.0, current_temp_c=21.0, source_temp_c=8.0, volume_m3=40.0,
                rate_per_min=0.03, airflow_bonus=1.0, horizon_min=60, running=True, session_elapsed_min=10,
                session_fresh_measurements=4, max_duration_min=20, max_temp_loss_next_5_min_c=99.0,
                min_efficiency_ml_per_01c=0.0, min_return_next_5_min_ml=0.0)
    args.update(extra)
    return horizon_forecast(**args)


@pytest.mark.parametrize("max_duration", [5.0, 20.0, 30.0, 60.0, 120.0])
@pytest.mark.parametrize("elapsed", [0.0, 10.0, 19.0, 59.0])
def test_f11_c_max_duration_is_no_forecast_end_point(max_duration, elapsed):
    result = _forecast(max_duration_min=max_duration, session_elapsed_min=elapsed)
    assert result["optimal_close_reason"] != "max_duration"


def test_f11_c_reproduction_and_bounded_horizon():
    result = _forecast()
    assert result["optimal_close_reason"] != "max_duration"
    assert result["horizon_min"] == 60                      # the forecast horizon itself stays bounded
    assert _forecast(horizon_min=5)["horizon_min"] == 5


def test_f11_c_running_airing_shows_no_forecast_close_time():
    source = (COMP / "coordinator_room_result.py").read_text(encoding="utf-8")
    assert '"forecast_optimal_close_in_min": None if mem.get("session_active") else dynamic.get("optimal_close_in_min")' in source
    assert '"forecast_physical_end_in_min": dynamic.get("optimal_close_in_min")' in source
    forecast = (COMP / "forecast.py").read_text(encoding="utf-8")
    assert 'optimal_close_reason = "max_duration"' not in forecast


# --------------------------------------------------------------------------------------------------- the table of point 7

DRY = dict(t=21.0, rh=62.0, rt=6.0, rrh=80.0)


def _dry(minutes, **extra):
    return _room(DRY["t"], DRY["rh"], DRY["rt"], DRY["rrh"], minutes, **extra)


@pytest.mark.parametrize("minutes", [20.0, 60.0, 120.0])
def test_open_window_keeps_drying_without_a_time_close(minutes):
    assert evaluate_room(_dry(minutes), DEFAULT_OPTIONS, False).action == "Continue ventilating"


def test_target_reached_with_drier_air_is_no_close():
    room = _room(21.0, 50.0, 6.0, 80.0, 30.0, session_target_min=10.0)
    assert evaluate_room(room, {**DEFAULT_OPTIONS, "target_rh": 55.0}, False).action == "Continue ventilating"


def test_rising_humidity_from_an_internal_source_keeps_ventilating():
    rising = _room(21.0, 70.0, 6.0, 80.0, 15.0, session_start_ah=absolute_humidity(21.0, 64.0))
    assert evaluate_room(rising, DEFAULT_OPTIONS, False).action == "Continue ventilating"
    source = _room(21.0, 70.0, 6.0, 80.0, 15.0, moisture_source_active=True, moisture_source_label="Dusche")
    assert evaluate_room(source, DEFAULT_OPTIONS, False).action == "Continue ventilating"


def test_explicit_temperature_limit_closes_with_its_reason():
    options = {**DEFAULT_OPTIONS, "airing_min_room_temp_c": 18.0}
    result = evaluate_room(_room(18.0, 62.0, 6.0, 80.0, 30.0), options, False)
    assert result.action == "Close" and result.reason == TEMPERATURE_LIMIT_CLOSE_REASON
    summer = evaluate_room(_room(18.0, 70.0, 12.0, 35.0, 30.0), {**SUMMER, "airing_min_room_temp_c": 18.0}, False)
    assert summer.action == "Close" and summer.reason == TEMPERATURE_LIMIT_CLOSE_REASON


@pytest.mark.parametrize("bad", [{"humidity": float("nan")}, {"reference_humidity": float("nan")},
                                 {"measurements_stale": True}, {"session_fresh_measurements": 0, "session_elapsed_min": 5.0}])
def test_insufficient_sensor_quality_gives_no_false_certain_statement(bad):
    result = evaluate_room(_dry(30.0, **bad), DEFAULT_OPTIONS, False)
    assert not result.close_recommended
    if bad.get("session_fresh_measurements") == 0:
        assert not result.close_decision_ready      # no close decision without readings (and no invented benefit)


def test_stored_close_is_released_once_its_cause_is_gone():
    exhausted = evaluate_room(_room(21.0, 62.0, 20.0, 66.0, 30.0), DEFAULT_OPTIONS, False)
    assert exhausted.action == "Close"
    released = evaluate_room(_dry(31.0, close_notified=True), DEFAULT_OPTIONS, False)
    assert released.action == "Continue ventilating"
    # an old stored close from the removed summer / lower-humidity reasons is released as well
    summer = evaluate_room(_room(28.0, 70.0, 27.5, 35.0, 30.0, close_notified=True), SUMMER, False)
    dry_room = evaluate_room(_room(22.0, 30.0, 10.0, 20.0, 30.0, close_notified=True), DEHUMIDIFY, False)
    assert summer.action == "Continue ventilating" and dry_room.action == "Continue ventilating"


def test_several_rooms_and_floors_decide_consistently():
    rooms = [{"key": k, "action": "Continue ventilating", "close_decision_ready": True, "session_elapsed_min": 60.0,
              "delta_g_m3": 3.0, "floor": floor} for k, floor in (("a", "eg"), ("b", "og"), ("c", "og"))]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=True) is False
    from custom_components.freshairiq.house_decision import floor_ventilation_decision
    from custom_components.freshairiq.live_coach import refine_live_recommendation
    full = [{**r, "name": r["key"], "volume_m3": 30.0, "forecast_5_min_net_moisture_change_ml": 0.5,
             "forecast_5_min_temperature_change_c": -0.9, "data_quality": "ok", "active": True,
             "calculation_enabled": True, "opening_state": "open"} for r in rooms]
    for house_mode in (True, False):
        rec: dict = {}
        floor_ventilation_decision(active=full, cross=False, forecast_confidence=70, forecast_cost=0.1,
                                   house_ventilation_mode=house_mode, intelligent_recommendation=rec,
                                   night_strategy={}, options=DEFAULT_OPTIONS, valid=full)
        assert rec["kind"] == "continue", house_mode           # small return + heat loss, but the air still dries
        coach = refine_live_recommendation({r["key"]: r for r in full}, DEFAULT_OPTIONS, dict(rec))
        assert coach["kind"] == "continue"
        final = stabilise_recommendation(dict(coach), {r["key"]: r for r in full}, DEFAULT_OPTIONS)
        assert final["kind"] == "continue"


def test_co2_protection_is_kept():
    options = {**DEFAULT_OPTIONS, "co2_warn": 1000, "co2_critical": 1400}
    room = _room(21.0, 50.0, 21.0, 50.0, 30.0, co2=1200.0, co2_lead_latched=True, session_co2_only=True)
    assert evaluate_room(room, options, False).action == "Continue ventilating"   # CO2 still needs the air


# --------------------------------------------------------------------------------------------------- end to end

def _golden():
    tools = Path(__file__).resolve().parents[1] / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import coordinator_golden as golden  # noqa: PLC0415
    return golden


def test_end_to_end_summer_case_no_close_from_sensor_to_push():
    from custom_components.freshairiq.notification_policy import effective_room_action
    golden = _golden()
    temp = {"device_class": "temperature", "unit_of_measurement": "°C"}
    hum = {"device_class": "humidity", "unit_of_measurement": "%"}
    rooms = [golden._room("s", "Schlafzimmer", "ground_floor", temp=["sensor.s_t"], hum=["sensor.s_h"],
                          contacts=["binary_sensor.s_f"], volume=40, sort=0)]
    initial = {"sensor.aussen_t": (27.5, temp), "sensor.aussen_h": (35.0, hum), "sensor.s_t": (28.0, temp),
               "sensor.s_h": (70.0, hum), "binary_sensor.s_f": ("off", {"device_class": "window"})}
    steps = [{"advance": 60}, {"advance": 60, "set": {"binary_sensor.s_f": "on"}}]
    for i in range(40):
        steps.append({"advance": 60, "set": {"sensor.s_h": round(70.0 - 0.1 * i + (0.01 if i % 2 else 0.0), 2)}})
    data = {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": rooms, "levels": ["ground_floor"]}
    scenario = {"start": datetime(2026, 7, 10, 18, 0, tzinfo=golden.TZ), "data": data,
                "options": {**golden.BASE_OPTIONS, "operating_profile": "summer_cooling", "min_duration_min": 3},
                "steps": steps, "initial": initial}
    seen: list[dict] = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append(result)
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    try:
        asyncio.run(golden._run_scenario("f11a", scenario, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    running = [d for d in seen if d["rooms"]["s"].get("active") and float(d["rooms"]["s"].get("session_elapsed_min") or 0) >= 3]
    assert running
    for data in running:
        room, rec = data["rooms"]["s"], data["intelligent_recommendation"]
        assert room["action"] != "Close" and not room["close_recommended"]
        assert rec["kind"] != "close" and effective_room_action(room, rec, data["rooms"]) != "Close"
        assert room.get("forecast_optimal_close_in_min") is None        # no forecast close time while running
