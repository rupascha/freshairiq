"""v0.26.6.1 (#25), real Home Assistant runtime: cross-ventilation pairs written with room names.

Options flow -> stored keys -> coordinator -> binary sensor / house data (the one flag recommendations, sessions,
the cross learning model and the ventilation log read). Stored name pairs from older versions are migrated once.
"""
from __future__ import annotations

import logging

from homeassistant.data_entry_flow import FlowResultType

from custom_components.freshairiq.const import CONF_ROOM_FLOOR, CONF_ROOM_NAME
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

ROOMS = [("schlafzimmer", "Schlafzimmer", "EG"), ("wohnzimmer", "Wohnzimmer", "EG"), ("esszimmer", "Esszimmer", "OG"), ("kuche", "Küche", "EG")]


def _rooms():
    return [{**_room(key, name), CONF_ROOM_FLOOR: floor} for key, name, floor in ROOMS]


async def _flow(hass, entry, pairs, zones=""):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    for step in ("ventilation_settings", "cross_ventilation"):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": step})
    return await hass.config_entries.options.async_configure(result["flow_id"], {"cross_ventilation_pairs": pairs, "cross_zone_connections": zones})


async def _windows(hass, entry, **states):
    for key, state in states.items():
        hass.states.async_set(f"binary_sensor.{key}_window", state)
    await hass.async_block_till_done()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    return entry.runtime_data.data["cross_ventilation"], hass.states.get("binary_sensor.freshairiq_cross_ventilation").state


async def test_names_in_the_options_flow_are_stored_as_keys_and_drive_cross_ventilation(hass) -> None:
    _set_sources(hass, *(key for key, _n, _f in ROOMS))
    entry = await _setup(hass, _entry(rooms=_rooms(), options={}))
    # invalid input is rejected with the reason, nothing is stored
    result = await _flow(hass, entry, "Schlafzimmer+Dachboden")
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cross_pairs_invalid"}
    assert "Dachboden" in result["description_placeholders"]["error_detail"]
    assert entry.options.get("cross_ventilation_pairs", "") == ""
    # the reported input: names, case and umlauts -> keys
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"cross_ventilation_pairs": "Schlafzimmer+Wohnzimmer,Esszimmer+Küche", "cross_zone_connections": ""})
    await hass.async_block_till_done()
    assert result["step_id"] == "ventilation_settings"
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["cross_ventilation_pairs"] == "schlafzimmer+wohnzimmer,esszimmer+kuche"
    # same floor: on only while both rooms are open
    assert await _windows(hass, entry, schlafzimmer="on", wohnzimmer="off") == (False, "off")
    assert await _windows(hass, entry, wohnzimmer="on") == (True, "on")
    assert await _windows(hass, entry, schlafzimmer="off", wohnzimmer="off") == (False, "off")
    # different floors (Esszimmer OG, Küche EG): only with an explicit zone connection – also written as names
    assert await _windows(hass, entry, esszimmer="on", kuche="on") == (False, "off")
    result = await _flow(hass, entry, "schlafzimmer+wohnzimmer,esszimmer+kuche", "Küche+Esszimmer")
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["cross_zone_connections"] == "kuche+esszimmer"
    assert await _windows(hass, entry) == (True, "on")
    # reload keeps the keys and the behaviour
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["cross_ventilation_pairs"] == "schlafzimmer+wohnzimmer,esszimmer+kuche"
    assert await _windows(hass, entry) == (True, "on")
    await _unload(hass, entry)


async def test_stored_name_pairs_are_migrated_once_and_what_cannot_be_resolved_is_logged_once(hass, caplog) -> None:
    _set_sources(hass, *(key for key, _n, _f in ROOMS))
    options = {"cross_ventilation_pairs": "Schlafzimmer+Wohnzimmer, Dachboden+Küche", "cross_zone_connections": "Esszimmer+Küche"}
    caplog.set_level(logging.WARNING)
    entry = await _setup(hass, _entry(rooms=_rooms(), options=options))
    assert entry.options["cross_ventilation_pairs"] == "schlafzimmer+wohnzimmer,Dachboden+Küche"
    assert entry.options["cross_zone_connections"] == "esszimmer+kuche"
    warnings = [r.getMessage() for r in caplog.records if "Cross-ventilation pairs" in r.getMessage()]
    assert warnings == ["Cross-ventilation pairs that name no known room are not used: cross_ventilation_pairs: Dachboden+Küche"]
    # the resolved pair works; a reload changes nothing and does not log again
    assert await _windows(hass, entry, schlafzimmer="on", wohnzimmer="on") == (True, "on")
    caplog.clear()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["cross_ventilation_pairs"] == "schlafzimmer+wohnzimmer,Dachboden+Küche"
    assert not [r for r in caplog.records if "Cross-ventilation pairs" in r.getMessage()]
    # valid key pairs of an existing installation stay exactly as they are
    await _unload(hass, entry)
    keys = await _setup(hass, _entry(rooms=_rooms(), options={"cross_ventilation_pairs": "schlafzimmer+wohnzimmer"}, entry_id="keys"))
    assert keys.options["cross_ventilation_pairs"] == "schlafzimmer+wohnzimmer"
    await _unload(hass, keys)
