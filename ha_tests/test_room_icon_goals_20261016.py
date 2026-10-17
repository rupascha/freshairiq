"""H32 / S73 (2026-10-16): saving a room icon and then the ventilation priorities never errors."""
from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType

from custom_components.freshairiq.const import CONF_ROOM_GOAL_PRIORITIES, CONF_ROOM_ICON
from ha_tests.test_cov_options_flow import _entry, _open, _room, _room_input, _submit


async def test_edit_room_icon_then_goal_priorities_saves_without_error(hass) -> None:
    entry = _entry(rooms=[_room(contacts=["binary_sensor.w1"], co2=True)])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    assert result["step_id"] == "edit_room"

    form = _room_input("Wohnzimmer", "wohnzimmer", contacts=["binary_sensor.w1"], co2=True, floor="EG")
    form["identity"][CONF_ROOM_ICON] = "mdi:sofa"
    result = await _submit(hass, result, form)
    assert result["step_id"] == "room_goals" and not result.get("errors")
    assert entry.data["rooms"][0][CONF_ROOM_ICON] == "mdi:sofa"

    result = await _submit(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "humidity"})
    assert result["step_id"] == "contact_references" and not result.get("errors")
    result = await _submit(hass, result, {"delay_seconds": 10, "orientation": "s"})
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "rooms"

    room = entry.data["rooms"][0]
    assert room[CONF_ROOM_ICON] == "mdi:sofa"
    assert room[CONF_ROOM_GOAL_PRIORITIES] == ["co2", "humidity"]
