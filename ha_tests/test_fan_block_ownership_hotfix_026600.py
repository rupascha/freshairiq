"""Hotfix 0.26.6.0 (1): a switch-off at the start of a lock period that failed keeps the run FreshAirIQ's.

Before: ownership was dropped when the switch-off was sent; after a failed call or a device that never
reported "off", the fan ran on through the night, the room was no longer FreshAirIQ's and nothing tried
again – the status read "stopping". Now the failure keeps ownership and the failed state, the switch-off
is tried again after FAN_BLOCK_RETRY_S (at most FAN_BLOCK_ATTEMPTS times), the status says "failed"
(please switch off by hand) and the trace records each result. A fan switched by hand stays the user's.

Real controller, Home Assistant states, recorded service calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from custom_components.freshairiq.actuator_control import FAN_BLOCK_ATTEMPTS, FAN_BLOCK_RETRY_S
from custom_components.freshairiq.fan_automation import room_fan_automation
from ha_tests.test_audit_026504c import SHARED, _controller, _room, _services

NIGHT = {"exhaust_fan_block_start": "22:00", "exhaust_fan_block_end": "07:00"}
RETRY_MIN = FAN_BLOCK_RETRY_S / 60


def _local(*args) -> datetime:
    return datetime(*args, tzinfo=dt_util.get_default_time_zone())


async def _cycle(hass, freezer, coordinator, controller, minutes: float = 0.5, **sources: bool) -> None:
    freezer.tick(timedelta(minutes=minutes))
    coordinator.data = {"rooms": {key: {"moisture_source_active": active} for key, active in sources.items()}}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


async def _running_before_the_night(hass, freezer, *, report: bool = True):
    freezer.move_to(_local(2026, 11, 2, 21, 50))
    log = _services(hass, report=report)
    hass.states.async_set(SHARED, "off")
    _entry, coordinator, controller = await _controller(hass, [{**_room("bad", [SHARED]), **NIGHT}])
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    if not report:
        hass.states.async_set(SHARED, "on")
        await _cycle(hass, freezer, coordinator, controller, minutes=0.1, bad=True)
    assert log[0] == ("turn_on", [SHARED]) and controller.fan_snapshot("bad")["owned"]
    return log, coordinator, controller


def _status(controller, fan_on: bool) -> dict:
    room = {"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": [SHARED], "mechanical_exhaust_active": fan_on}}
    return room_fan_automation(room, controller.fan_snapshot("bad"))


async def test_a_failed_switch_off_keeps_ownership_and_is_tried_again_by_rule(hass, freezer) -> None:
    log, coordinator, controller = await _running_before_the_night(hass, freezer)
    hass.services.async_remove("homeassistant", "turn_off")       # the switch-off cannot be sent
    freezer.move_to(_local(2026, 11, 2, 22, 1))
    await _cycle(hass, freezer, coordinator, controller, minutes=0, bad=True)
    snap = controller.fan_snapshot("bad")
    assert (snap["owned"], snap["command"], snap["command_state"], snap["reason"]) == (True, "off", "failed", "block_time")
    status = _status(controller, fan_on=True)
    assert (status["state"], status["label_key"], status["user_action_needed"]) == ("failed", "failed_off", True)  # not "stopping"
    assert controller.fan_trace()[-1]["result"] == "failed" and controller.fan_trace()[-1]["reason"] == "block_time"
    rows = len(controller.fan_trace())
    # inside the retry time nothing is sent and nothing new is traced
    await _cycle(hass, freezer, coordinator, controller, minutes=RETRY_MIN - 1, bad=True)
    assert len(controller.fan_trace()) == rows and controller.fan_snapshot("bad")["owned"]
    # the switch works again: the next retry switches the fan off, and only then is the run no longer FreshAirIQ's
    log2 = _services(hass)
    await _cycle(hass, freezer, coordinator, controller, minutes=1.5, bad=True)
    assert log2 == [("turn_off", [SHARED])]
    await _cycle(hass, freezer, coordinator, controller, minutes=0.5, bad=True)
    snap = controller.fan_snapshot("bad")
    assert (snap["owned"], snap["command_state"]) == (False, "confirmed")
    assert _status(controller, fan_on=False)["state"] == "blocked_time"
    for _ in range(3):  # the rest of the night: no start, no further switching
        await _cycle(hass, freezer, coordinator, controller, minutes=30, bad=True)
    assert log2 == [("turn_off", [SHARED])] and log == [("turn_on", [SHARED])]
    await controller.async_stop()


async def test_a_device_that_never_reports_off_is_retried_at_most_the_set_number_of_times(hass, freezer) -> None:
    log, coordinator, controller = await _running_before_the_night(hass, freezer, report=False)
    freezer.move_to(_local(2026, 11, 2, 22, 0, 30))
    for _ in range(FAN_BLOCK_ATTEMPTS + 3):
        await _cycle(hass, freezer, coordinator, controller, minutes=2, bad=True)            # the command times out
        await _cycle(hass, freezer, coordinator, controller, minutes=RETRY_MIN, bad=True)    # retry time is over
    offs = [call for call in log if call[0] == "turn_off"]
    assert len(offs) == FAN_BLOCK_ATTEMPTS  # tried again by rule, never endlessly
    snap = controller.fan_snapshot("bad")
    assert (snap["owned"], snap["command_state"]) == (True, "failed")  # the missing switch-off stays visible
    assert _status(controller, fan_on=True)["user_action_needed"] is True
    assert [row["result"] for row in controller.fan_trace() if row["reason"] == "block_time"].count("failed") == FAN_BLOCK_ATTEMPTS
    await controller.async_stop()


async def test_after_a_failed_switch_off_the_user_takes_over_by_hand(hass, freezer) -> None:
    log, coordinator, controller = await _running_before_the_night(hass, freezer)
    hass.services.async_remove("homeassistant", "turn_off")
    freezer.move_to(_local(2026, 11, 2, 22, 1))
    await _cycle(hass, freezer, coordinator, controller, minutes=0, bad=True)
    assert controller.fan_snapshot("bad")["owned"]
    hass.states.async_set(SHARED, "off")                         # the user switches it off by hand
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    assert controller.fan_snapshot("bad")["owned"] is False      # no longer FreshAirIQ's
    log2 = _services(hass)
    hass.states.async_set(SHARED, "on")                          # and on again by hand later in the night
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, minutes=RETRY_MIN + 1, bad=True)
    assert log2 == [] and hass.states.get(SHARED).state == "on"  # the user's run is never switched off
    await controller.async_stop()


async def test_another_automation_taking_the_fan_after_a_failed_switch_off_is_left_alone(hass, freezer) -> None:
    lock = "input_boolean.alexa"
    hass.states.async_set(lock, "off")
    freezer.move_to(_local(2026, 11, 2, 21, 50))
    log = _services(hass)
    hass.states.async_set(SHARED, "off")
    _entry, coordinator, controller = await _controller(hass, [{**_room("bad", [SHARED]), **NIGHT, "exhaust_fan_external_lock": lock}])
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    hass.services.async_remove("homeassistant", "turn_off")
    freezer.move_to(_local(2026, 11, 2, 22, 1))
    await _cycle(hass, freezer, coordinator, controller, minutes=0, bad=True)
    log2 = _services(hass)
    hass.states.async_set(lock, "on")                            # the other automation runs the fan now
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, minutes=RETRY_MIN + 1, bad=True)
    assert log2 == [] and log == [("turn_on", [SHARED])]
    assert controller.fan_snapshot("bad")["owned"] is False
    await controller.async_stop()


async def test_an_unknown_fan_state_is_no_proven_switch_off(hass, freezer) -> None:
    log, coordinator, controller = await _running_before_the_night(hass, freezer)
    hass.services.async_remove("homeassistant", "turn_off")
    freezer.move_to(_local(2026, 11, 2, 22, 1))
    await _cycle(hass, freezer, coordinator, controller, minutes=0, bad=True)
    hass.states.async_set(SHARED, "unavailable")
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    assert controller.fan_snapshot("bad")["owned"] is True and controller.fan_snapshot("bad")["command_state"] == "failed"
    await controller.async_stop()
