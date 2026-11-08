"""0.26.7.0 (owner request): optional global automation lock (e.g. input_boolean.urlaub).

Real controller, Home Assistant states and recorded service calls; the status entity and the options page.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq.actuator_controller import ActuatorController
from custom_components.freshairiq.binary_sensor import AutomationLockSensor
from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.fan_automation import room_fan_automation
from ha_tests.test_audit_026504c import PRIVATE, SHARED, _room, _services

LOCK = "input_boolean.urlaub"


async def _controller(hass, rooms, options=None):
    entry = MockConfigEntry(domain=DOMAIN, entry_id="lock", data={"rooms": rooms, "levels": ["EG"]},
                            options={"automation_lock_entity": LOCK} if options is None else options)
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(data={"rooms": {}}, options={}, async_add_listener=lambda cb: (lambda: None))
    controller = ActuatorController(hass, coordinator, entry)
    await controller.async_start()
    return entry, coordinator, controller


async def _cycle(hass, coordinator, controller, **sources: bool) -> None:
    coordinator.data = {"rooms": {key: {"moisture_source_active": active} for key, active in sources.items()}}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


async def test_no_new_action_while_locked_own_fan_ends_once_nothing_is_queued(hass) -> None:
    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    hass.states.async_set(LOCK, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("bad", [SHARED]), _room("kueche", [PRIVATE])])
    await _cycle(hass, coordinator, controller, bad=True)
    assert log == [("turn_on", [SHARED])] and controller.fan_snapshot("bad")["owned"]
    # holidays: FreshAirIQ ends the airing it started itself – once – and starts nothing new
    hass.states.async_set(LOCK, "on")
    await hass.async_block_till_done()
    assert log[-1] == ("turn_off", [SHARED])
    snap = controller.fan_snapshot("bad")
    assert snap["automation_lock"] and not snap["owned"] and snap["reason"] == "automation_lock"
    assert any(row["reason"] == "automation_lock" for row in controller.fan_trace())
    for _ in range(3):
        await _cycle(hass, coordinator, controller, bad=True, kueche=True)   # demand everywhere: still nothing
    assert log == [("turn_on", [SHARED]), ("turn_off", [SHARED])]
    assert controller.fan_snapshot("bad")["command_state"] == "confirmed"
    # the lock ends: the situation at that moment decides (here: only the kitchen needs its fan) – no command of the
    # locked time is caught up, the bath's earlier demand is not repeated
    coordinator.data = {"rooms": {"bad": {"moisture_source_active": False}, "kueche": {"moisture_source_active": True}}}
    hass.states.async_set(LOCK, "off")
    await hass.async_block_till_done()
    assert log == [("turn_on", [SHARED]), ("turn_off", [SHARED]), ("turn_on", [PRIVATE])]
    await _cycle(hass, coordinator, controller, bad=False, kueche=True)
    assert log == [("turn_on", [SHARED]), ("turn_off", [SHARED]), ("turn_on", [PRIVATE])]
    await controller.async_stop()


async def test_a_fan_freshairiq_does_not_own_is_never_touched_and_covers_stay(hass) -> None:
    log = _services(hass)
    hass.states.async_set(SHARED, "on")   # switched on by hand
    hass.states.async_set(LOCK, "on")
    _entry, coordinator, controller = await _controller(hass, [_room("bad", [SHARED])])
    controller._async_covers = AsyncMock(return_value=False)
    # plus a room with covers only (no fan control): nothing to end there either
    controller._rooms = [{**controller._rooms[0], "covers": ["cover.bad"]}, {"key": "flur", "exhaust_fan_control": "off", "covers": ["cover.flur"]}]
    await _cycle(hass, coordinator, controller, bad=True)
    await controller._async_evaluate(fans=False)   # a contact changed
    assert log == [] and hass.states.get(SHARED).state == "on"
    controller._async_covers.assert_not_awaited()
    await controller.async_stop()


async def test_a_switch_off_that_does_not_arrive_is_followed_to_its_result(hass, freezer) -> None:
    log = _services(hass, report=False)   # the fan never reports off
    hass.states.async_set(SHARED, "off")
    hass.states.async_set(LOCK, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("bad", [SHARED])])
    await _cycle(hass, coordinator, controller, bad=True)
    hass.states.async_set(SHARED, "on")
    hass.states.async_set(LOCK, "on")
    await hass.async_block_till_done()
    assert log[-1] == ("turn_off", [SHARED]) and controller.fan_snapshot("bad")["command_state"] == "pending"
    room = {"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": [SHARED], "mechanical_exhaust_active": True}}
    assert room_fan_automation(room, controller.fan_snapshot("bad"))["state"] == "stopping"
    freezer.tick(600)
    await _cycle(hass, coordinator, controller, bad=True)
    assert controller.fan_snapshot("bad")["command_state"] == "failed"
    assert room_fan_automation(room, controller.fan_snapshot("bad"))["state"] == "failed"
    await controller.async_stop()


async def test_an_unavailable_or_missing_lock_does_not_lock(hass) -> None:
    log = _services(hass)
    hass.states.async_set(SHARED, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("bad", [SHARED])])
    assert controller.automation_lock() == {"configured": True, "entity_id": LOCK, "active": False, "source_state": "missing"}
    hass.states.async_set(LOCK, "unavailable")
    await _cycle(hass, coordinator, controller, bad=True)
    assert log == [("turn_on", [SHARED])]
    await controller.async_stop()
    _entry2, _c2, free = await _controller(hass, [], options={})
    assert free.automation_lock() == {"configured": False, "entity_id": None, "active": False, "source_state": None}


async def test_status_entity_follows_the_lock_for_other_automations(hass) -> None:
    hass.states.async_set(LOCK, "off")
    entry = MockConfigEntry(domain=DOMAIN, entry_id="lock-status", data={"rooms": []}, options={"automation_lock_entity": LOCK})
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(data={"rooms": {}}, last_update_success=True, async_add_listener=lambda cb, ctx=None: (lambda: None))
    sensor = AutomationLockSensor(coordinator, entry)
    sensor.hass = hass
    sensor.entity_id = "binary_sensor.freshairiq_automation_lock"
    sensor.async_write_ha_state = lambda: written.append(sensor.is_on)
    written: list = []
    await sensor.async_added_to_hass()
    assert sensor.entity_registry_enabled_default is True and sensor.is_on is False
    hass.states.async_set(LOCK, "on")
    await hass.async_block_till_done()
    assert written == [True] and sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs["lock_entity"] == LOCK and attrs["lock_entity_state"] == "on" and attrs["configured"] is True
    assert attrs["freshairiq_entity_key"] == "automation_lock"
    plain = MockConfigEntry(domain=DOMAIN, entry_id="no-lock", data={"rooms": []}, options={})
    plain.add_to_hass(hass)
    off = AutomationLockSensor(coordinator, plain)
    off.hass = hass
    await off.async_added_to_hass()
    assert off.entity_registry_enabled_default is False and off.is_on is False and off.extra_state_attributes["lock_entity"] is None


async def test_the_options_page_sets_and_clears_the_lock(hass) -> None:
    from homeassistant.data_entry_flow import FlowResultType
    from ha_tests.test_cov_options_flow import _entry as _opt_entry, _open, _room as _opt_room, _submit

    hass.states.async_set(LOCK, "off")
    entry = _opt_entry(rooms=[_opt_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "notification_energy_settings", "automation_lock")
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "automation_lock"
    result = await _submit(hass, result, {"automation_lock_entity": LOCK})
    assert result["step_id"] == "notification_energy_settings"
    result = await _open(hass, entry, "finish")
    assert entry.options["automation_lock_entity"] == LOCK
    # shown again with the stored entity, then cleared: the lock is gone (not kept from before)
    result = await _open(hass, entry, "notification_energy_settings", "automation_lock")
    key = next(k for k in result["data_schema"].schema if str(k) == "automation_lock_entity")
    assert key.description == {"suggested_value": LOCK}
    result = await _submit(hass, result, {})
    result = await _open(hass, entry, "finish")
    assert entry.options["automation_lock_entity"] is None
