"""Regression (F12, 2026-10-16): a room added in the options flow gets its entities.

The room wizard persists its pages with ``reload_entry=False`` so the options
dialog survives. The deferred structural reload at the end of the wizard used
to compare against the already persisted room list, saw no change and never
reloaded, so the new room had no entities until a manual reload.
"""
from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from ha_tests.test_cov_options_flow import _open, _room_input, _submit
from ha_tests.test_cov_setup_and_platforms import _entry, _set_sources, _setup, _unload


def _room_entity_ids(hass, entry, room_key: str) -> set[str]:
    registry = er.async_get(hass)
    return {
        item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if room_key in item.unique_id
    }


async def _finish(hass, result) -> None:
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(flow_id, {"next_step_id": "back_to_home_setup"})
    assert result["step_id"] == "home_setup"
    result = await hass.config_entries.options.async_configure(flow_id, {"next_step_id": "back_to_main"})
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(flow_id, {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_contactless_room_added_in_options_gets_entities(hass) -> None:
    _set_sources(hass, "wohnzimmer", "bad")
    entry = await _setup(hass, _entry())
    assert not _room_entity_ids(hass, entry, "bad")

    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    result = await _submit(hass, result, _room_input("Bad", "bad", floor="EG"))
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "rooms"
    await hass.async_block_till_done()

    # the reload ran while the dialog stayed usable
    assert _room_entity_ids(hass, entry, "bad")
    await _finish(hass, result)
    assert _room_entity_ids(hass, entry, "bad")
    assert [room["key"] for room in entry.data["rooms"]] == ["wohnzimmer", "bad"]
    await _unload(hass, entry)


async def test_room_with_contacts_added_in_options_gets_entities(hass) -> None:
    _set_sources(hass, "wohnzimmer", "kueche")
    entry = await _setup(hass, _entry())

    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    result = await _submit(
        hass, result, _room_input("Küche", "kueche", contacts=["binary_sensor.kueche_window"], floor="EG")
    )
    assert result["step_id"] == "contact_references"
    await hass.async_block_till_done()
    # 0.26.5.3 (owner requirement: every saved change works at once): the saved
    # room has its entities right away, the wizard simply continues
    assert _room_entity_ids(hass, entry, "kuche")

    result = await _submit(hass, result, {"delay_seconds": 10, "orientation": "s"})
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "rooms"
    await hass.async_block_till_done()
    assert _room_entity_ids(hass, entry, "kuche")

    await _finish(hass, result)
    assert _room_entity_ids(hass, entry, "kuche")
    await _unload(hass, entry)
