"""F24/F25: FreshAirIQ's registry helpers use no deprecated device-registry API."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq import _iter_device_entries
from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.room_devices import ROOM_PREFIX, assign_room_devices, room_device_identifier


async def test_room_registry_helpers_emit_no_deprecation(hass, caplog) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="FreshAirIQ")
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={room_device_identifier(DOMAIN, entry.entry_id, "bad")},
        name="Bad",
    )
    caplog.set_level(logging.WARNING)
    found = _iter_device_entries(registry, entry.entry_id)
    assert [d.id for d in found] == [device.id]
    # The room device exists outside its sub-entry: the lookup path runs for real.
    fake_entry = SimpleNamespace(entry_id=entry.entry_id, subentries={"sub": SimpleNamespace(subentry_type="room", unique_id=f"{ROOM_PREFIX}bad", subentry_id="sub")})
    assign_room_devices(registry, er.async_get(hass), er.async_entries_for_device, fake_entry, DOMAIN)
    deprecations = [r.getMessage() for r in caplog.records if "deprecated" in r.getMessage()]
    assert deprecations == []
