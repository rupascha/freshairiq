"""0.26.5.5 (community report): a delayed door must not act before its delay – also in fan rooms.

Fall A (0.26.5.4) made the reference air respect the opening delay. A room with its
own automatic exhaust fan still read the door's raw state elsewhere: passing through
a door with a 120 s delay switched the fan off (``window_open`` = no fan demand),
changed the fan state and the messages. Here the whole chain runs in a real Home
Assistant: recommendation → fan → door opened for 30 s → closed again.
"""
from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq.const import CONF_CONTACT_DELAYS
from ha_tests.test_cov_setup_and_platforms import _entry, _setup, _unload
from ha_tests.test_fan_automation_026504 import DOOR, FAN, NOTIFY, START, _climate, _cycle, _garage, _switch


async def _running(hass, freezer, delay: int):
    freezer.move_to(START)
    log: list = []
    _switch(hass, log)
    pushes = async_mock_service(hass, "notify", "phone")
    events: list = []
    for name in ("freshairiq_notification", "freshairiq_room_action", "freshairiq_fan_automation"):
        hass.bus.async_listen(name, lambda e, name=name: events.append((name, dict(e.data))))
    _climate(hass, garage_rh=86.0)
    hass.states.async_set(FAN, "off")
    hass.states.async_set(DOOR, "off", {"device_class": "door"})
    entry = await _setup(hass, _entry(rooms=[_garage(**{CONF_CONTACT_DELAYS: {DOOR: delay}})], options=NOTIFY))
    coordinator = entry.runtime_data
    for _ in range(6):
        await _cycle(hass, freezer, coordinator)
    assert [s for s, _ in log] == ["turn_on"] and hass.states.get(FAN).state == "on"
    return entry, coordinator, log, pushes, events


def _snapshot(coordinator) -> tuple:
    room = coordinator.data["rooms"]["garage"]
    automation = room.get("fan_automation") or {}
    return room.get("house_aligned_action"), automation.get("state"), automation.get("user_action_needed")


async def test_passing_through_a_delayed_door_keeps_the_fan_and_sends_nothing(hass, freezer) -> None:
    entry, coordinator, log, pushes, events = await _running(hass, freezer, 120)
    before, pushed = _snapshot(coordinator), len(pushes)
    events.clear()
    hass.states.async_set(DOOR, "on", {"device_class": "door"})
    await _cycle(hass, freezer, coordinator)          # 30 s open – inside the delay
    assert _snapshot(coordinator) == before
    assert coordinator.data["rooms"]["garage"]["configured_actuators"]["window_open"] is False
    hass.states.async_set(DOOR, "off", {"device_class": "door"})
    for _ in range(3):
        await _cycle(hass, freezer, coordinator)
    assert [s for s, _ in log] == ["turn_on"]         # never switched off by the passing
    assert hass.states.get(FAN).state == "on"
    assert _snapshot(coordinator) == before
    assert len(pushes) == pushed and events == []
    await _unload(hass, entry)


async def test_a_door_held_open_past_its_delay_still_counts(hass, freezer) -> None:
    entry, coordinator, log, _pushes, _events = await _running(hass, freezer, 60)
    hass.states.async_set(DOOR, "on", {"device_class": "door"})
    await _cycle(hass, freezer, coordinator)
    assert coordinator.data["rooms"]["garage"]["configured_actuators"]["window_open"] is False
    for _ in range(3):
        await _cycle(hass, freezer, coordinator)
    assert coordinator.data["rooms"]["garage"]["configured_actuators"]["window_open"] is True
    await _unload(hass, entry)


async def test_without_a_delay_the_door_counts_at_once(hass, freezer) -> None:
    entry, coordinator, _log, _pushes, _events = await _running(hass, freezer, 0)
    hass.states.async_set(DOOR, "on", {"device_class": "door"})
    await _cycle(hass, freezer, coordinator)
    assert coordinator.data["rooms"]["garage"]["configured_actuators"]["window_open"] is True
    await _unload(hass, entry)
