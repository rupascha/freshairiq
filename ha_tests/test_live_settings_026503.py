"""0.26.5.3 (owner requirement): every saved setting works at once, wherever it is changed.

Covers changes written straight into the config entry (as any editor does),
the options-flow room wizard with newly added contacts (community report:
the pages of two new door contacts only appeared after a reload) and the
kinds of change that need more than a refresh: new/renamed rooms (entities
and devices), optional room sensors that become relevant, diagnostics.
"""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ha_tests.test_clearable_fields_026503 import SUBMIT, _replay, _submission
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

WINDOW = "binary_sensor.wohnzimmer_window"
DOOR_1, DOOR_2 = "binary_sensor.badezimmertuer", "binary_sensor.schiebetuer"


async def _save(hass, entry, *, data=None, options=None) -> None:
    hass.config_entries.async_update_entry(entry, **({"data": data} if data is not None else {}), **({"options": options} if options is not None else {}))
    await hass.async_block_till_done()


async def test_a_room_added_or_renamed_anywhere_gets_its_entities_at_once(hass) -> None:
    _set_sources(hass, "wohnzimmer", "bad")
    entry = await _setup(hass, _entry())
    first = entry.runtime_data
    await _save(hass, entry, data={**entry.data, "rooms": [*entry.data["rooms"], _room("bad", "Bad")]})
    assert entry.runtime_data is not first  # reloaded
    registry = er.async_get(hass)
    assert any(e.unique_id.startswith(f"{entry.entry_id}_bad_") for e in er.async_entries_for_config_entry(registry, entry.entry_id))

    rooms = [dict(r) for r in entry.data["rooms"]]
    rooms[1]["name"] = "Badezimmer"
    second = entry.runtime_data
    await _save(hass, entry, data={**entry.data, "rooms": rooms})
    assert entry.runtime_data is not second
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    device = next(d for d in devices if ("freshairiq", f"{entry.entry_id}:room:bad") in d.identifiers)
    assert "Badezimmer" in (device.name or "")
    await _unload(hass, entry)


async def test_a_sensor_for_a_newly_used_feature_is_enabled_at_once(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    registry = er.async_get(hass)
    shading = registry.async_get_entity_id("binary_sensor", "freshairiq", f"{entry.entry_id}_wohnzimmer_shading")
    assert registry.async_get(shading).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    room = {**entry.data["rooms"][0], "contact_covers": {WINDOW: ["cover.rollo"]}}
    await _save(hass, entry, data={**entry.data, "rooms": [room]})
    assert registry.async_get(shading).disabled_by is None
    assert hass.states.get(shading) is not None
    await _unload(hass, entry)


async def test_options_apply_at_once_without_a_reload(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    with patch.object(coordinator, "async_request_refresh") as refresh, patch.object(coordinator.telemetry, "request_check") as check:
        await _save(hass, entry, options={**entry.options, "start_rh": 61})
        assert refresh.called and not check.called
        await _save(hass, entry, options={**entry.options, "diagnostics_reporting_mode": "off"})
        assert check.called
    assert entry.runtime_data is coordinator  # no reload for plain settings
    await _unload(hass, entry)


async def test_new_contacts_get_their_pages_in_the_room_wizard(hass) -> None:
    """Community report: two door contacts added – their pages must follow at once."""
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(DOOR_1, "off")
    hass.states.async_set(DOOR_2, "off")
    entry = await _setup(hass, _entry())
    form = await _replay(hass, entry, ["home_setup", "rooms", "edit_room_select", SUBMIT])
    data = _submission(form["data_schema"])
    data["sensors"]["contacts"] = [WINDOW, DOOR_1, DOOR_2]
    result = await hass.config_entries.options.async_configure(form["flow_id"], data)
    pages = []
    while result["type"] is FlowResultType.FORM and result["step_id"] == "contact_references":
        pages.append((result["description_placeholders"]["contact_entity"], result["description_placeholders"]["contact_position"]))
        result = await hass.config_entries.options.async_configure(result["flow_id"], _submission(result["data_schema"]))
        await hass.async_block_till_done()
    assert pages == [(WINDOW, "1"), (DOOR_1, "2"), (DOOR_2, "3")]
    assert result["step_id"] == "rooms"
    hass.config_entries.options.async_abort(result["flow_id"])
    # and the running integration watches the new doors right away
    assert {DOOR_1, DOOR_2} <= entry.runtime_data._contact_entities
    await _unload(hass, entry)


async def test_the_settings_dialog_follows_changes_made_elsewhere(hass) -> None:
    """A change saved outside the open dialog is not overwritten by its stale copy."""
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    menu = await _replay(hass, entry, ["home_setup"])
    room = {**entry.data["rooms"][0], "contacts": [WINDOW, DOOR_1]}
    await _save(hass, entry, data={**entry.data, "rooms": [room]})
    form = await hass.config_entries.options.async_configure(menu["flow_id"], {"next_step_id": "outdoor"})
    await hass.config_entries.options.async_configure(form["flow_id"], _submission(form["data_schema"]))
    await hass.async_block_till_done()
    assert entry.data["rooms"][0]["contacts"] == [WINDOW, DOOR_1]
    await _unload(hass, entry)


async def test_a_listener_rebuild_also_cancels_pending_final_measurements(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    cancelled = []
    coordinator._final_measurement_unsubs["wohnzimmer"] = lambda: cancelled.append(True)
    room = {**entry.data["rooms"][0], "contacts": [WINDOW, DOOR_1]}
    await _save(hass, entry, data={**entry.data, "rooms": [room]})  # new source -> rebuild
    assert cancelled == [True] and coordinator._final_measurement_unsubs == {}
    await _unload(hass, entry)
