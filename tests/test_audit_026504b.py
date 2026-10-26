"""0.26.5.4: preventive audit of the 0.26.5.4 artefact (P1-03, P1-04, P1-06, P1-07, P2-08, P1-05).

* P1-03: the 50 ppm CO2 hold band was ignored by the small-return and the
  humidity-plateau close – a CO2 airing closed at 975 ppm (warning 1000).
* P1-04: a CO2 sensor without a value was taken for "CO2 is down".
* P1-06: only part of a fan group came on – the group was released and the fan
  that came on ran unattended.
* P1-07: a humidity value that was merely held (silent sensor) made a plateau.
* P2-08: the switch-off sent when the fan control was removed stayed "sent".
* P1-05: several fans, only some on – visible as such.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.actuator_control import (
    FAN_COMMAND_TIMEOUT_S, FAN_CONTROL_RECOMMENDATION, decide_fan, settle_removed_off,
)
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.fan_automation import room_fan_automation
from custom_components.freshairiq.humidity_plateau import PLATEAU_WINDOW_MIN, humidity_plateau, record_sample, track_session
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room
from custom_components.freshairiq.room_recommendation import _recommendation

OPTIONS = {**DEFAULT_OPTIONS, "co2_warn": 1000, "co2_critical": 1400}
T0 = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def _room(**extra) -> RoomInput:
    values = dict(key="wz", name="Wohnzimmer", temperature=22.0, humidity=50.0, reference_temperature=22.0, reference_humidity=50.0,
                  volume_m3=30.0, contact_open=True, contact_open_seconds=600, learning_rate=0.03, session_active=True,
                  session_elapsed_min=17.0, session_fresh_measurements=3, session_target_min=30.0,
                  session_start_ah=absolute_humidity(22.0, 51.0), session_start_temp=22.0)
    values.update(extra)
    return RoomInput(**values)


def _action(room: RoomInput, options=OPTIONS) -> str:
    return evaluate_room(room, options, False).action


# --------------------------------------------------------------------------- P1-03

@pytest.mark.parametrize("plateau", [False, True])
@pytest.mark.parametrize(("co2", "latched", "kept"), [(1010, False, True), (1000, False, True), (975, True, True),
                                                       (950, True, True), (949, True, False), (975, False, False)])
def test_the_co2_hold_band_keeps_a_co2_airing_open_on_every_close_path(co2, latched, kept, plateau) -> None:
    action = _action(_room(co2=co2, co2_lead_latched=latched, session_co2_only=True, humidity_plateau=plateau))
    assert (action == "Continue ventilating") is kept, (co2, latched, plateau, action)


def test_the_hold_band_does_not_override_the_maximum_duration() -> None:
    assert _action(_room(co2=975, co2_lead_latched=True, session_co2_only=True, session_elapsed_min=41.0, contact_open_seconds=2460)) == "Close"


# --------------------------------------------------------------------------- P1-04

def test_a_co2_sensor_without_value_is_not_co2_reached() -> None:
    blind = dict(co2=None, session_co2_only=True, session_elapsed_min=8.0, session_target_min=10.0)
    assert _action(_room(**blind, co2_sensor_missing=True)) == "Continue ventilating"
    assert _action(_room(**blind)) == "Close"  # a switched-off CO2 goal: the CO2 airing has no task left
    # after the plan made when it was opened, the airing ends by the usual rules
    assert _action(_room(**{**blind, "session_elapsed_min": 11.0}, co2_sensor_missing=True)) == "Close"


def test_the_room_says_that_the_co2_sensor_reports_no_value() -> None:
    result = evaluate_room(_room(co2=None, session_co2_only=True, session_elapsed_min=8.0, session_target_min=10.0, co2_sensor_missing=True), OPTIONS, False)
    action, _reason, reasons = _recommendation(result, OPTIONS, pollen=0.0, co2=None, airflow=1.0, wind_bearing=None, wind_speed=None)
    assert action == "Continue ventilating"
    assert reasons[-1].startswith("Der CO₂-Sensor liefert keinen Wert") and "erreicht" not in " ".join(reasons)


# --------------------------------------------------------------------------- P1-07

def _window(reports_then: int, rh: float = 60.0) -> list:
    return record_sample([], 0.0, rh, absolute_humidity(21.0, rh), reports_then)


def test_a_held_value_without_new_report_is_no_plateau() -> None:
    ah = absolute_humidity(21.0, 60.0)
    assert humidity_plateau(_window(3), PLATEAU_WINDOW_MIN, 60.0, ah, 3) is False  # silent sensor
    assert humidity_plateau(_window(3), PLATEAU_WINDOW_MIN, 60.0, ah, 4) is True   # reported, really flat
    assert humidity_plateau(_window(3), PLATEAU_WINDOW_MIN, 60.0, ah) is True      # no report count known
    old = [{"t": 0.0, "rh": 60.0, "ah": round(ah, 3)}]  # stored before this version: unchanged behaviour
    assert humidity_plateau(old, PLATEAU_WINDOW_MIN, 60.0, ah, 0) is True


def test_track_session_counts_the_reports() -> None:
    mem: dict = {}
    for minute in range(0, 17):
        plateau = track_session(mem, session_active=True, elapsed_min=float(minute), temp_c=21.0, rh=60.0, reports=2)
    assert plateau is False and mem["session_humidity_window"][-1]["n"] == 2
    assert track_session(mem, session_active=True, elapsed_min=17.0, temp_c=21.0, rh=60.0, reports=3) is True


# --------------------------------------------------------------------------- P1-06 / P1-05

def _decide(mem, *, fan_on, seconds, demand=True, all_on=None):
    return decide_fan(mode=FAN_CONTROL_RECOMMENDATION, fan_on=fan_on, demand=demand, now=T0 + timedelta(seconds=seconds),
                      follow_up_min=10, max_runtime_min=60, mem=mem, all_on=all_on)


def test_a_partial_group_start_keeps_the_fans_and_stops_them_later() -> None:
    mem: dict = {}
    assert _decide(mem, fan_on=False, all_on=False, seconds=0) == "on"
    assert _decide(mem, fan_on=True, all_on=False, seconds=FAN_COMMAND_TIMEOUT_S + 1) is None
    assert mem["command_state"] == "partial" and mem["owned"] is True and not mem.get("blocked") and mem["reason"] == "partial_start"
    # the demand ends: FreshAirIQ switches off what it switched on
    assert _decide(mem, fan_on=True, all_on=False, seconds=FAN_COMMAND_TIMEOUT_S + 100, demand=False) == "off"


def test_a_start_where_no_fan_came_on_still_fails() -> None:
    mem: dict = {}
    _decide(mem, fan_on=False, all_on=False, seconds=0)
    _decide(mem, fan_on=False, all_on=False, seconds=FAN_COMMAND_TIMEOUT_S + 1)
    assert mem["command_state"] == "failed" and mem["owned"] is False


def test_an_incomplete_fan_group_is_visible() -> None:
    room = {"configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": True, "mechanical_exhaust_active": True},
            "house_aligned_action": "ventilate"}
    group = room_fan_automation(room, {"fans_total": 2, "fans_on": 1})
    assert group["fans_on"] == 1 and group["fans_total"] == 2 and group["group_incomplete"] is True
    assert room_fan_automation(room, {"fans_total": 2, "fans_on": 2})["group_incomplete"] is False
    assert "group_incomplete" not in room_fan_automation(room, {})


# --------------------------------------------------------------------------- P2-08

def test_the_switch_off_on_control_removal_gets_its_result() -> None:
    sent = {"reason": "control_removed", "command": "off", "command_state": "pending", "command_at": T0.isoformat(), "off_entities": ["fan.x"]}
    assert settle_removed_off(dict(sent), True, T0 + timedelta(seconds=10)) is False
    confirmed = dict(sent)
    assert settle_removed_off(confirmed, False, T0 + timedelta(seconds=10)) is True and confirmed["command_state"] == "confirmed"
    assert "off_entities" not in confirmed
    failed = dict(sent)
    assert settle_removed_off(failed, None, T0 + timedelta(seconds=FAN_COMMAND_TIMEOUT_S)) is True and failed["command_state"] == "failed"
    assert settle_removed_off({**sent, "reason": "goal_reached"}, False, T0) is False
