"""v0.26.6.1 (#21), real Home Assistant runtime: a room's Mold Indicator helper as its surface-RH source.

HA state + entity registry -> coordinator (RoomInput) -> evaluate_room -> room payload / surface sensor / mould risk
-> diagnostics. Rooms without a helper are unchanged; each room uses its own source.
"""
from __future__ import annotations

from homeassistant.helpers import entity_registry as er

from custom_components.freshairiq.diagnostics import async_get_config_entry_diagnostics
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

HELPER = "sensor.dach_schimmel"


async def _cycle(hass, entry):
    await hass.async_block_till_done()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    return entry.runtime_data.data["rooms"]


async def test_each_room_uses_its_own_source_and_falls_back_safely(hass) -> None:
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", "mold_indicator", "dach-1", suggested_object_id="dach_schimmel")
    registry.async_get_or_create("sensor", "demo", "flur-rh", suggested_object_id="flur_luftfeuchte")
    _set_sources(hass, "dach", "bad")
    hass.states.async_set(HELPER, "95", {"unit_of_measurement": "%", "device_class": "humidity"})
    rooms = [{**_room("dach", "Dachzimmer"), "mold_indicator": HELPER}, _room("bad", "Bad")]
    entry = await _setup(hass, _entry(rooms=rooms))
    data = await _cycle(hass, entry)
    dach, bad = data["dach"], data["bad"]
    assert (dach["surface_rh"], dach["mould_level"], dach["surface_rh_source"], dach["surface_rh_source_entity"]) == (95, "Very high", "ha_mold_indicator", HELPER)
    assert "surface_rh_source" not in bad and bad["surface_rh"] < 95                   # no helper: published exactly as before
    assert hass.states.get("sensor.dachzimmer_estimated_surface_humidity").state == "95"
    # unavailable, NaN, wrong unit, out of range: the internal estimate, with the reason
    for state, attrs, issue in (("unavailable", {"unit_of_measurement": "%"}, "unavailable"), ("nan", {"unit_of_measurement": "%"}, "invalid"),
                                ("95", {"unit_of_measurement": "g/m³"}, "wrong_unit"), ("101", {"unit_of_measurement": "%"}, "out_of_range")):
        hass.states.async_set(HELPER, state, attrs)
        dach = (await _cycle(hass, entry))["dach"]
        assert (dach["surface_rh_source"], dach["surface_rh_source_issue"]) == ("internal_estimate", issue), state
        assert dach["surface_rh"] == bad["surface_rh"]                                  # same climate in both rooms -> same estimate
    # available again: the helper again; 0 and 100 are taken as they are
    for value in ("0", "100", "95"):
        hass.states.async_set(HELPER, value, {"unit_of_measurement": "%"})
        dach = (await _cycle(hass, entry))["dach"]
        assert (dach["surface_rh"], dach["surface_rh_source"]) == (int(value), "ha_mold_indicator")
    # diagnostics show the source, never the helper's entity id
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert HELPER not in str(diagnostics)
    assert "ha_mold_indicator" in str(diagnostics) and "internal_estimate" in str(diagnostics)
    # helper removed (or renamed: the stored id no longer exists) -> internal estimate, reason "missing"
    registry.async_remove(HELPER)
    hass.states.async_remove(HELPER)
    dach = (await _cycle(hass, entry))["dach"]
    assert (dach["surface_rh_source"], dach["surface_rh_source_issue"]) == ("internal_estimate", "missing")
    assert dach["surface_rh"] == bad["surface_rh"] != 95
    await _unload(hass, entry)
    # a room humidity sensor of another integration is never taken as surface RH, even if configured by hand
    hass.states.async_set("sensor.flur_luftfeuchte", "97", {"unit_of_measurement": "%", "device_class": "humidity"})
    wrong = await _setup(hass, _entry(rooms=[{**_room("dach", "Dachzimmer"), "mold_indicator": "sensor.flur_luftfeuchte"}], entry_id="wrong"))
    dach = (await _cycle(hass, wrong))["dach"]
    assert (dach["surface_rh_source"], dach["surface_rh_source_issue"]) == ("internal_estimate", "not_mold_indicator") and dach["surface_rh"] != 97
    await _unload(hass, wrong)


async def test_the_helper_survives_reload_and_a_room_edit_can_remove_it(hass) -> None:
    er.async_get(hass).async_get_or_create("sensor", "mold_indicator", "dach-1", suggested_object_id="dach_schimmel")
    _set_sources(hass, "dach")
    hass.states.async_set(HELPER, "88", {"unit_of_measurement": "%"})
    entry = await _setup(hass, _entry(rooms=[{**_room("dach", "Dachzimmer"), "mold_indicator": HELPER}]))
    assert (await _cycle(hass, entry))["dach"]["surface_rh"] == 88
    assert await hass.config_entries.async_reload(entry.entry_id)                       # like a restart of Home Assistant
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.data["rooms"][0]["mold_indicator"] == HELPER
    assert (await _cycle(hass, entry))["dach"]["surface_rh_source"] == "ha_mold_indicator"
    # the helper changes its value: the room follows on the next cycle (listener on the helper state)
    hass.states.async_set(HELPER, "91", {"unit_of_measurement": "%"})
    assert (await _cycle(hass, entry))["dach"]["surface_rh"] == 91
    # removed from the room's setup: back to the internal estimate, no source fields
    rooms = [{k: v for k, v in entry.data["rooms"][0].items() if k != "mold_indicator"}]
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": rooms})
    assert await hass.config_entries.async_reload(entry.entry_id)
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    room = (await _cycle(hass, entry))["dach"]
    assert "surface_rh_source" not in room and room["surface_rh"] != 91
    await _unload(hass, entry)
