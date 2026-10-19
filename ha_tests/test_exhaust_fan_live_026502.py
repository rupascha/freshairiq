"""0.26.5.2 (community: "automatic exhaust fan enabled, a ventilation
recommendation came, but the fan did not start").

Two causes: switching the control on for an existing room only took effect
after a restart, and a room without its own window contact is told "ventilate
indirectly", which the recommendation mode ignored.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq.actuator_control import fan_demand
from custom_components.freshairiq.const import CONF_ROOM_EXHAUST_FAN, CONF_ROOM_EXHAUST_FAN_CONTROL
from ha_tests.test_actuator_control_20261017 import FAN, _calls, _services
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload


def test_a_room_without_window_runs_its_fan_on_indirect_ventilation() -> None:
    assert fan_demand("recommendation", source_active=False, recommendation="ventilate_indirectly", window_open=False)
    assert not fan_demand("recommendation", source_active=False, recommendation="ventilate_later", window_open=False)


async def test_enabling_the_fan_control_works_without_a_restart(hass) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(FAN, "off")
    entry = await _setup(hass, _entry(rooms=[{**_room(), CONF_ROOM_EXHAUST_FAN: [FAN]}]))
    coordinator = entry.runtime_data
    controller = coordinator.actuator_controller
    assert controller._rooms == []

    # the user switches "follow the recommendation" on in the room setup
    room = {**entry.data["rooms"][0], CONF_ROOM_EXHAUST_FAN_CONTROL: "recommendation"}
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [room]})
    coordinator.data["rooms"]["wohnzimmer"]["house_aligned_action"] = "ventilate_indirectly"
    await controller.async_reload()
    await hass.async_block_till_done()
    assert _calls(calls["turn_on"]) == [([FAN], None)]
    hass.states.async_set(FAN, "on")

    # switched off again: the fan FreshAirIQ started is switched off
    room = {**room, CONF_ROOM_EXHAUST_FAN_CONTROL: "off"}
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [room]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert _calls(calls["turn_off"]) == [([FAN], None)]
    assert controller._rooms == []
    await _unload(hass, entry)


async def test_a_room_edit_reloads_the_controller(hass) -> None:
    controller = SimpleNamespace(async_reload=AsyncMock())
    coordinator = SimpleNamespace(async_rebuild_listeners=AsyncMock(), async_request_refresh=AsyncMock(),
                                  actuator_controller=controller)
    flow = cf.FreshAirIQRoomSubentryFlow()
    flow.hass = hass
    flow._get_entry = lambda: SimpleNamespace(runtime_data=coordinator)
    flow._schedule_room_runtime_update()
    await hass.async_block_till_done()
    controller.async_reload.assert_awaited_once()
