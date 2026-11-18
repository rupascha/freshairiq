"""K02 (0.26.7.1): the room editor stores the optional close strategy and own temperature limit.

Default since IQ2 (0.26.7.1): "close once the goals are reached" and no own limit (the global one applies). An emptied
limit is removed again, so the room inherits the global value; an edit that touches nothing keeps both settings.
Testvermerk 0.26.7.1 (IQ2, owner decision of 15.11.2026): the default changed from "continue_while_drying" to
"goals_reached"; the deliberate alternative is "keep_drying". Earlier builds stored the form's default with every save,
so a stored "continue_while_drying" is no deliberate choice and becomes the default on the next save.
"""
from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType

from custom_components.freshairiq.room_close_strategy import CONF_ROOM_AIRING_MIN_TEMP, CONF_ROOM_CLOSE_STRATEGY
from ha_tests.test_clearable_fields_026503 import _replay, _submission
from ha_tests.test_room_edit_keeps_settings_026503 import EDIT_ROOM, _entry_with


async def _edit(hass, entry, properties: dict, drop: tuple = ()) -> None:
    result = await _replay(hass, entry, EDIT_ROOM)
    assert result["step_id"] == "edit_room"
    data = _submission(result["data_schema"])
    target = data["properties"] if isinstance(data.get("properties"), dict) else data
    target.update(properties)
    for key in drop:
        target.pop(key, None)
    result = await hass.config_entries.options.async_configure(result["flow_id"], data)
    while result["type"] is FlowResultType.FORM:
        result = await hass.config_entries.options.async_configure(result["flow_id"], _submission(result["data_schema"]))
    if result["type"] is FlowResultType.MENU:
        hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()


async def test_room_close_strategy_and_limit_are_stored_kept_and_cleared(hass) -> None:
    entry = _entry_with({})
    entry.add_to_hass(hass)
    await _edit(hass, entry, {})
    room = entry.data["rooms"][0]
    assert room[CONF_ROOM_CLOSE_STRATEGY] == "goals_reached" and CONF_ROOM_AIRING_MIN_TEMP not in room

    await _edit(hass, entry, {CONF_ROOM_CLOSE_STRATEGY: "keep_drying", CONF_ROOM_AIRING_MIN_TEMP: 16.5})
    room = entry.data["rooms"][0]
    assert (room[CONF_ROOM_CLOSE_STRATEGY], room[CONF_ROOM_AIRING_MIN_TEMP]) == ("keep_drying", 16.5)

    await _edit(hass, entry, {})                              # unchanged pass keeps both
    room = entry.data["rooms"][0]
    assert (room[CONF_ROOM_CLOSE_STRATEGY], room[CONF_ROOM_AIRING_MIN_TEMP]) == ("keep_drying", 16.5)

    await _edit(hass, entry, {}, drop=(CONF_ROOM_AIRING_MIN_TEMP,))   # emptied: inherit the global limit again
    room = entry.data["rooms"][0]
    assert CONF_ROOM_AIRING_MIN_TEMP not in room and room[CONF_ROOM_CLOSE_STRATEGY] == "keep_drying"

    await _edit(hass, entry, {CONF_ROOM_AIRING_MIN_TEMP: 0})          # explicit 0 = no limit for this room
    assert entry.data["rooms"][0][CONF_ROOM_AIRING_MIN_TEMP] == 0.0


async def test_room_without_the_new_keys_behaves_as_before(hass) -> None:
    entry = _entry_with({CONF_ROOM_CLOSE_STRATEGY: "bogus", CONF_ROOM_AIRING_MIN_TEMP: "x"})
    entry.add_to_hass(hass)
    await _edit(hass, entry, {}, drop=(CONF_ROOM_AIRING_MIN_TEMP,))
    room = entry.data["rooms"][0]
    assert room[CONF_ROOM_CLOSE_STRATEGY] == "goals_reached" and CONF_ROOM_AIRING_MIN_TEMP not in room


async def test_stored_former_default_becomes_the_new_default_and_a_deliberate_choice_stays(hass) -> None:
    entry = _entry_with({CONF_ROOM_CLOSE_STRATEGY: "continue_while_drying"})
    entry.add_to_hass(hass)
    await _edit(hass, entry, {})                              # untouched save of a room written by a test build
    assert entry.data["rooms"][0][CONF_ROOM_CLOSE_STRATEGY] == "goals_reached"
    await _edit(hass, entry, {CONF_ROOM_CLOSE_STRATEGY: "keep_drying"})
    await _edit(hass, entry, {})
    assert entry.data["rooms"][0][CONF_ROOM_CLOSE_STRATEGY] == "keep_drying"
