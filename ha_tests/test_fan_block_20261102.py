"""0.26.5.5 (02.11.): lock period of the automatic exhaust fan control, and window/door per contact in the forms.

Real controller, Home Assistant states, time-change timers and recorded service calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from pytest_homeassistant_custom_component.common import async_fire_time_changed
from homeassistant.util import dt as dt_util

from custom_components.freshairiq.config_flow_rooms import (
    _apply_single_contact_reference,
    _normalise_room_control,
    _single_contact_reference_schema,
)
from ha_tests.test_audit_026504c import PRIVATE, SHARED, _controller, _room, _services

NIGHT = {"exhaust_fan_block_start": "22:00", "exhaust_fan_block_end": "07:00"}


def _local(*args) -> datetime:
    return datetime(*args, tzinfo=dt_util.get_default_time_zone())


async def _cycle(hass, freezer, coordinator, controller, minutes: float = 0.5, **sources: bool) -> None:
    freezer.tick(timedelta(minutes=minutes))
    coordinator.data = {"rooms": {key: {"moisture_source_active": active} for key, active in sources.items()}}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


async def _start(hass, freezer, rooms, at, fans=(SHARED,)):
    freezer.move_to(at)
    log = _services(hass)
    for fan in fans:
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, rooms)
    return log, coordinator, controller


async def test_a_running_fan_goes_off_when_the_lock_period_starts_on_time(hass, freezer) -> None:
    log, coordinator, controller = await _start(hass, freezer, [{**_room("bad", [SHARED]), **NIGHT}], _local(2026, 11, 2, 21, 50))
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    assert log == [("turn_on", [SHARED])]
    # the lock period begins at 22:00 – the timer switches the fan off without a coordinator update
    freezer.move_to(_local(2026, 11, 2, 22, 0, 0))
    async_fire_time_changed(hass, _local(2026, 11, 2, 22, 0, 0))
    await hass.async_block_till_done()
    assert log[-1] == ("turn_off", [SHARED])
    snap = controller.fan_snapshot("bad")
    assert snap["block_time"] and snap["reason"] == "block_time" and not snap["owned"]
    assert any(row["reason"] == "block_time" for row in controller.fan_trace())
    # the moisture source goes on: no start, no repeated attempts during the night
    for _ in range(5):
        await _cycle(hass, freezer, coordinator, controller, minutes=30, bad=True)
    assert log == [("turn_on", [SHARED]), ("turn_off", [SHARED])]
    # 07:00: normal control again while the demand is there
    freezer.move_to(_local(2026, 11, 3, 7, 0, 0))
    async_fire_time_changed(hass, _local(2026, 11, 3, 7, 0, 0))
    await hass.async_block_till_done()
    coordinator.data = {"rooms": {"bad": {"moisture_source_active": True}}}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()
    assert log[-1] == ("turn_on", [SHARED]) and not controller.fan_snapshot("bad")["block_time"]
    await controller.async_stop()


async def test_a_fan_switched_on_by_hand_or_by_another_automation_is_left_alone(hass, freezer) -> None:
    lock = "input_boolean.alexa"
    hass.states.async_set(lock, "off")
    rooms = [{**_room("bad", [SHARED]), **NIGHT, "exhaust_fan_external_lock": lock}]
    log, coordinator, controller = await _start(hass, freezer, rooms, _local(2026, 11, 2, 23, 0))
    hass.states.async_set(SHARED, "on")            # by hand during the lock period
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    assert log == [] and hass.states.get(SHARED).state == "on"
    hass.states.async_set(lock, "on")               # another automation runs it
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    assert log == []
    await controller.async_stop()


async def test_a_shared_fan_is_not_started_by_a_room_without_its_own_lock_period(hass, freezer) -> None:
    rooms = [{**_room("bad", [SHARED]), **NIGHT}, _room("wc", [SHARED]), _room("kueche", [PRIVATE])]
    log, coordinator, controller = await _start(hass, freezer, rooms, _local(2026, 11, 2, 23, 30), fans=(SHARED, PRIVATE))
    await _cycle(hass, freezer, coordinator, controller, bad=False, wc=True, kueche=True)
    assert log == [("turn_on", [PRIVATE])]   # the device under the lock stays off, an independent fan starts
    assert controller.fan_snapshot("wc")["block_time"] is True
    await controller.async_stop()


async def test_restart_inside_the_period_and_a_disabled_period(hass, freezer) -> None:
    rooms = [{**_room("bad", [SHARED]), **NIGHT}]
    log, coordinator, controller = await _start(hass, freezer, rooms, _local(2026, 11, 2, 21, 0))
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    memory = controller._memory
    await controller.async_stop()
    freezer.move_to(_local(2026, 11, 2, 22, 30))      # Home Assistant restarts inside the period
    _entry, coordinator2, controller2 = await _controller(hass, rooms, entry_id="audit-restart")
    controller2._memory = memory
    await _cycle(hass, freezer, coordinator2, controller2, bad=True)
    assert log[-1] == ("turn_off", [SHARED])
    await controller2.async_stop()
    # without both times (or equal times) there is no lock period
    for times in ({"exhaust_fan_block_start": "22:00"}, {"exhaust_fan_block_start": "22:00", "exhaust_fan_block_end": "22:00"}):
        hass.states.async_set(SHARED, "off")
        _entry, coordinator3, controller3 = await _controller(hass, [{**_room("bad", [SHARED]), **times}], entry_id=f"x{len(times)}{times.get('exhaust_fan_block_end')}")
        await _cycle(hass, freezer, coordinator3, controller3, bad=True)
        assert log[-1] == ("turn_on", [SHARED])
        await controller3.async_stop()


async def test_an_unreachable_fan_and_the_maximum_runtime_stay_as_before(hass, freezer) -> None:
    rooms = [{**_room("bad", [SHARED]), **NIGHT, "exhaust_fan_max_runtime_min": 30}]
    log, coordinator, controller = await _start(hass, freezer, rooms, _local(2026, 11, 2, 21, 0))
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    for _ in range(4):
        await _cycle(hass, freezer, coordinator, controller, minutes=10, bad=True)
    assert ("turn_off", [SHARED]) in log  # maximum runtime before the lock period, unchanged
    hass.states.async_set(SHARED, "on")
    controller._memory["fans"]["bad"].update(owned=True, command="on", command_state="confirmed")
    freezer.move_to(_local(2026, 11, 2, 22, 5))
    log2 = _services(hass, report=False)   # the device does not report back
    await _cycle(hass, freezer, coordinator, controller, minutes=0, bad=True)
    assert log2 == [("turn_off", [SHARED])]
    await _cycle(hass, freezer, coordinator, controller, minutes=2, bad=True)
    assert controller.fan_snapshot("bad")["command_state"] == "failed" and log2 == [("turn_off", [SHARED])]  # no endless retries
    await controller.async_stop()


def test_lock_period_and_contact_kind_in_the_forms() -> None:
    room = {"exhaust_fan_control": "moisture_source", "exhaust_fan_block_start": "22:00:00", "exhaust_fan_block_end": "7:00"}
    _normalise_room_control(room, {})
    assert (room["exhaust_fan_block_start"], room["exhaust_fan_block_end"]) == ("22:00", "07:00")
    cleared = {"exhaust_fan_control": "moisture_source"}
    _normalise_room_control(cleared, {"exhaust_fan_block_start": "22:00", "exhaust_fan_block_end": "07:00"})
    assert cleared["exhaust_fan_block_start"] is None and cleared["exhaust_fan_block_end"] is None  # emptied in the form
    other_page = {}
    _normalise_room_control(other_page, {"exhaust_fan_block_start": "22:00", "exhaust_fan_block_end": "07:00"})
    assert other_page["exhaust_fan_block_start"] == "22:00"  # another page keeps the stored period
    # window/door per contact: default "not stated", saved, edited, cleared; older rooms without the field work
    contact = "binary_sensor.fenster"
    old = {"contacts": [contact]}
    assert _single_contact_reference_schema(old, contact)({})["contact_kind"] == "unknown"
    assert _apply_single_contact_reference(old, contact, {"contact_kind": "window"}) and old["contact_kinds"] == {contact: "window"}
    assert _single_contact_reference_schema(old, contact)({})["contact_kind"] == "window"
    assert _apply_single_contact_reference(old, contact, {"contact_kind": "door"}) and old["contact_kinds"] == {contact: "door"}
    assert _apply_single_contact_reference(old, contact, {"contact_kind": "unknown"}) and old["contact_kinds"] == {}
    assert _apply_single_contact_reference(old, contact, {"contact_kind": "garage"}) and old["contact_kinds"] == {}


async def test_a_failed_switch_off_at_the_start_of_the_period_is_reported_once(hass, freezer) -> None:
    rooms = [{**_room("bad", [SHARED]), **NIGHT}]
    log, coordinator, controller = await _start(hass, freezer, rooms, _local(2026, 11, 2, 21, 30))
    await _cycle(hass, freezer, coordinator, controller, bad=True)
    hass.services.async_remove("homeassistant", "turn_off")   # the switch-off cannot be sent
    freezer.move_to(_local(2026, 11, 2, 22, 1))
    await _cycle(hass, freezer, coordinator, controller, minutes=0, bad=True)
    snap = controller.fan_snapshot("bad")
    assert (snap["command"], snap["command_state"], snap["reason"]) == ("off", "failed", "block_time")
    await _cycle(hass, freezer, coordinator, controller, minutes=5, bad=True)
    assert log == [("turn_on", [SHARED])]   # nothing else is sent during the period
    await controller.async_stop()
