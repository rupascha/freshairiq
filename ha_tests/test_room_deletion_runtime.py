"""0.26.4.6: deleted rooms disappear from the real Home Assistant registries."""
from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.freshairiq as integration
from custom_components.freshairiq.const import DOMAIN


async def test_removed_room_device_and_entities_are_deleted(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"rooms": [{"key": "kitchen", "name": "Küche"}]})
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    kept = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}:room:kitchen")})
    stale = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}:room:test")})
    entity = entities.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_test_humidity", config_entry=entry, device_id=stale.id)
    disabled = entities.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_test_learning", config_entry=entry, device_id=stale.id,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    assert {d.id for d in integration._iter_device_entries(devices, entry.entry_id)} >= {kept.id, stale.id}
    integration._async_cleanup_removed_room_registry_entries(hass, entry)

    assert devices.async_get(stale.id) is None
    assert devices.async_get(kept.id) is not None
    assert entities.async_get(entity.entity_id) is None
    assert entities.async_get(disabled.entity_id) is None


async def test_room_subentry_deleted_by_user_is_dropped_from_parent_data(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"rooms": [{"key": "kitchen", "name": "Küche"}, {"key": "test", "name": "Test"}],
              "room_subentry_keys": ["kitchen", "test"]},
    )
    entry.add_to_hass(hass)
    integration._async_sync_room_subentries(hass, entry)
    test_subentry = next(sub for sub in entry.subentries.values() if sub.unique_id == "room:test")
    hass.config_entries.async_remove_subentry(entry, test_subentry.subentry_id)

    assert integration._rooms_pending_subentry_deletion(entry) == {"test"}
    assert integration._async_drop_rooms_deleted_as_subentries(hass, entry) == {"test"}
    integration._async_sync_room_subentries(hass, entry)
    integration._async_remember_room_subentries(hass, entry)

    assert [room["key"] for room in entry.data["rooms"]] == ["kitchen"]
    assert {sub.unique_id for sub in entry.subentries.values()} == {"room:kitchen"}
    assert entry.data["room_subentry_keys"] == ["kitchen"]
