"""0.26.5.4: fixes from the independent code review (A01, A02, A03, A05, A04, A09, A10 pure parts).

A04  the wall (mould) model compares with the room's default reference (outdoor
     air), never with the supply air of an exhaust fan or of a single window.
A02  FreshAirIQ's own switch-off that the device has not reported yet is
     "stopping", never "manual" (no "switch off the fan" for the user).
A03  a command to a device that reports no state still fails after the timeout.
A05  with several fans a switch-on is only confirmed when every fan reports on.
A09  the air-exchange display stops at 95 % ("practically complete").
A01  names only: moisture coming in and "reference air barely drier" are told apart
     in the model; the close decisions stay the same (golden master).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S, FAN_CONTROL_RECOMMENDATION, decide_fan
from custom_components.freshairiq.air_exchange import advance_air_exchange
from custom_components.freshairiq.close_wording import fan_stop_message
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.fan_automation import auto_stop, handled_label, room_fan_automation
from custom_components.freshairiq.model import RoomInput, evaluate_room, surface_relative_humidity

T0 = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
OPTIONS = {**DEFAULT_OPTIONS}


def _bath(**overrides) -> RoomInput:
    values = dict(key="bad", name="Bad", temperature=22.0, humidity=70.0, reference_temperature=22.0, reference_humidity=30.0,
                  volume_m3=9.0, contact_open=False, contact_open_seconds=None, learning_rate=0.03)
    values.update(overrides)
    return RoomInput(**values)


# --------------------------------------------------------------------------- A04

def test_the_mould_model_keeps_the_outdoor_wall_reference_with_fan_supply_air() -> None:
    factor = float(OPTIONS["surface_factor"])
    outdoor = evaluate_room(_bath(surface_reference_temperature=-5.0), OPTIONS, False)
    expected = surface_relative_humidity(22.0, 70.0, -5.0, factor)
    assert outdoor.surface_rh == pytest.approx(expected, abs=0.1) and outdoor.surface_rh > 85
    # the supply air (warm hallway) is not the wall: before, the surface humidity fell to the room's 70 %
    assert outdoor.surface_rh > evaluate_room(_bath(), OPTIONS, False).surface_rh + 10
    # the reference air itself still decides the airing (delta), only the wall model changed
    assert outdoor.delta_g_m3 == evaluate_room(_bath(), OPTIONS, False).delta_g_m3
    # without a separate wall reference the behaviour is unchanged
    assert evaluate_room(_bath(surface_reference_temperature=None), OPTIONS, False).surface_rh == evaluate_room(_bath(), OPTIONS, False).surface_rh


# --------------------------------------------------------------------------- A02

def _garage(fan_on: bool) -> dict:
    return {"key": "garage", "name": "Garage", "house_aligned_action": "close", "close_recommended": True,
            "configured_actuators": {"exhaust_fan": "switch.g", "exhaust_fan_control": "recommendation", "mechanical_exhaust_active": fan_on}}


def test_own_switch_off_not_yet_reported_is_stopping_not_manual() -> None:
    room = _garage(True)
    room["fan_automation"] = room_fan_automation(room, {"owned": False, "command": "off", "command_state": "pending", "reason": "goal_reached"})
    assert room["fan_automation"]["state"] == "stopping" and room["fan_automation"]["user_action_needed"] is False
    assert auto_stop(room) and handled_label(room, "close") == "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung"
    assert "ausschalten" not in fan_stop_message(room)
    # a fan someone switched on by hand stays manual
    assert room_fan_automation(_garage(True), {})["state"] == "manual"
    # a switch-off the device never carried out still asks the user
    failed = room_fan_automation(_garage(True), {"command": "off", "command_state": "failed"})
    assert failed["state"] == "failed" and failed["user_action_needed"] is True


# --------------------------------------------------------------------------- A03 / A05

def _decide(mem, *, fan_on, seconds, demand=True, all_on=None):
    return decide_fan(mode=FAN_CONTROL_RECOMMENDATION, fan_on=fan_on, demand=demand, now=T0 + timedelta(seconds=seconds),
                      follow_up_min=10, max_runtime_min=60, mem=mem, all_on=all_on)


@pytest.mark.parametrize("command", ["on", "off"])
def test_an_unavailable_device_does_not_keep_a_command_pending_forever(command) -> None:
    mem = {"owned": command == "on", "command": command, "command_state": "pending", "command_at": T0.isoformat()}
    assert _decide(mem, fan_on=None, seconds=FAN_COMMAND_TIMEOUT_S - 1) is None and mem["command_state"] == "pending"
    assert _decide(mem, fan_on=None, seconds=FAN_COMMAND_TIMEOUT_S + 15) is None
    assert mem["command_state"] == "failed" and mem["reason"] == "device_unavailable"
    assert mem["owned"] is False
    if command == "on":
        assert mem["blocked"] is True  # no blind retry while the device is gone
    idle = {"command": "on", "command_state": "confirmed", "command_at": T0.isoformat()}
    assert _decide(idle, fan_on=None, seconds=500) is None and idle["command_state"] == "confirmed"


def test_with_several_fans_a_switch_on_needs_every_fan() -> None:
    mem = {"owned": True, "since": T0.isoformat(), "command": "on", "command_state": "pending", "command_at": T0.isoformat()}
    assert _decide(mem, fan_on=True, all_on=False, seconds=10) is None and mem["command_state"] == "pending"
    _decide(mem, fan_on=True, all_on=False, seconds=FAN_COMMAND_TIMEOUT_S + 1)
    # audit P1-06 (0.26.5.4): only part of the group came on – not confirmed, but FreshAirIQ keeps the
    # fans it started (before: "failed" and released, the fan that came on ran unattended)
    assert mem["command_state"] == "partial" and mem["owned"] is True
    both = {"owned": True, "since": T0.isoformat(), "command": "on", "command_state": "pending", "command_at": T0.isoformat()}
    _decide(both, fan_on=True, all_on=True, seconds=10)
    assert both["command_state"] == "confirmed"
    single = {"owned": True, "since": T0.isoformat(), "command": "on", "command_state": "pending", "command_at": T0.isoformat()}
    _decide(single, fan_on=True, seconds=10)  # one fan (no all_on given): unchanged
    assert single["command_state"] == "confirmed"


# --------------------------------------------------------------------------- A09

def test_air_exchange_display_stops_at_95_percent() -> None:
    mem = {"session_started": "s1"}
    advance_air_exchange(mem, active=True, elapsed_min=0, now=T0, rate_per_min=0.03, factor=1.0, learned=True)
    for minutes in (200, 600, 1200):
        shown = advance_air_exchange(mem, active=True, elapsed_min=minutes, now=T0 + timedelta(minutes=minutes),
                                     rate_per_min=0.03, factor=1.0, learned=True)
        assert shown["exchanged_percent"] == 95 and shown["minutes_to_95"] == 0.0


# --------------------------------------------------------------------------- A11 / A12 (risks checked, behaviour kept)

def test_two_temperature_reports_count_as_fresh_evidence_by_design() -> None:
    """A11: Home Assistant reports a sensor value only when it changes – an unchanged humidity is no stale humidity."""
    from custom_components.freshairiq.climate_sources import advance_climate_report_activity

    start = T0.isoformat()
    first = {"bad": {"available": True, "reports": {"temperature": (T0 + timedelta(minutes=1)).isoformat(), "humidity": start}}}
    previous, counts, fresh = advance_climate_report_activity({"bad": {"reports": {"temperature": start, "humidity": start}}}, {}, first,
                                                              window_start=T0)
    second = {"bad": {"available": True, "reports": {"temperature": (T0 + timedelta(minutes=2)).isoformat(), "humidity": start}}}
    _previous, _counts, fresh = advance_climate_report_activity(previous, counts, second, window_start=T0)
    assert fresh == 2


def test_a_silent_humidity_sensor_is_a_plateau_and_the_age_guard_stays_separate() -> None:
    """A12: a value that has not changed for 15 minutes is a plateau; a dead sensor is caught by the age guard."""
    from custom_components.freshairiq.humidity_plateau import PLATEAU_WINDOW_MIN, humidity_plateau, record_sample
    from custom_components.freshairiq.measurement_frame import ROOM_HELD_MAX_AGE_S

    window: list = []
    for minute in range(int(PLATEAU_WINDOW_MIN) + 1):
        window = record_sample(window, float(minute), 66.0, 12.0)
    assert humidity_plateau(window, PLATEAU_WINDOW_MIN, 66.0, 12.0) is True
    assert humidity_plateau(window, PLATEAU_WINDOW_MIN, 60.0, 10.9) is False  # still falling: no plateau
    assert ROOM_HELD_MAX_AGE_S / 60 > PLATEAU_WINDOW_MIN  # a reading this old is "stale", not a plateau
