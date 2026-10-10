"""Room devices belong to their room subentry (0.26.4.9).

Community feedback (Nordlicht-13): under *Settings → Devices & services →
FreshAirIQ* every room was listed twice – once as a device in the group
"Devices that don't belong to a sub-entry" and once more, empty, as the room's
own sub-entry at the bottom. The room sub-entries are needed (rooms are edited
there), so the room devices now live *inside* their sub-entry instead:

* new room entities are added with ``config_subentry_id`` of their room;
* existing installations are moved once at start-up – entities first, then the
  device. Home Assistant removes entities that stay in a device's previous
  sub-entry when the device moves, so this order keeps every entity (IDs,
  names, history and customisations stay untouched).

Pure logic: no Home Assistant imports – the registries are passed in.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

_LOGGER = logging.getLogger(__name__)
ROOM_PREFIX = "room:"


def room_subentry_ids(entry: Any) -> dict[str, str]:
    """``{room_key: subentry_id}`` of the entry's room sub-entries."""
    found: dict[str, str] = {}
    for subentry_id, sub in dict(getattr(entry, "subentries", None) or {}).items():
        unique_id = str(getattr(sub, "unique_id", "") or "")
        if getattr(sub, "subentry_type", None) == "room" and unique_id.startswith(ROOM_PREFIX):
            key = unique_id.removeprefix(ROOM_PREFIX)
            if key:
                found[key] = str(getattr(sub, "subentry_id", None) or subentry_id)
    return found


def room_device_identifier(domain: str, entry_id: str, room_key: str) -> tuple[str, str]:
    return (domain, f"{entry_id}:room:{room_key}")


def add_entities_by_room(
    async_add_entities: Callable[..., Any],
    entry: Any,
    house_entities: list[Any],
    room_entities: dict[str, list[Any]],
) -> None:
    """Add house entities normally and each room's entities to its sub-entry."""
    if house_entities:
        async_add_entities(house_entities)
    subentries = room_subentry_ids(entry)
    for key, entities in room_entities.items():
        if not entities:
            continue
        subentry_id = subentries.get(key)
        if subentry_id:
            async_add_entities(entities, config_subentry_id=subentry_id)
        else:  # room without sub-entry (should not happen): keep it visible
            async_add_entities(entities)


def assign_room_devices(
    device_registry: Any,
    entity_registry: Any,
    entries_for_device: Callable[..., Iterable[Any]],
    entry: Any,
    domain: str,
) -> list[str]:
    """Move existing room devices (and their entities) into the room sub-entry.

    Returns the room keys whose device was moved. Never raises: a registry
    that cannot move devices simply keeps the previous layout.
    """
    moved: list[str] = []
    entry_id = str(getattr(entry, "entry_id", ""))
    for key, subentry_id in sorted(room_subentry_ids(entry).items()):
        try:
            device = device_registry.async_get_device(identifiers={room_device_identifier(domain, entry_id, key)})
            if device is None or getattr(device, "config_subentry_id", None) == subentry_id:
                continue
            # Entities first: a device move drops entities left in the old sub-entry.
            for entity in entries_for_device(entity_registry, device.id, include_disabled_entities=True):
                if getattr(entity, "config_entry_id", entry_id) == entry_id and getattr(entity, "config_subentry_id", None) != subentry_id:
                    entity_registry.async_update_entity(entity.entity_id, config_subentry_id=subentry_id)
            device_registry.async_update_device(device.id, new_config_subentry_id=subentry_id)
            moved.append(key)
        except Exception:  # noqa: BLE001 - layout only; never block setup
            _LOGGER.debug("Could not move FreshAirIQ room device %s into its sub-entry", key, exc_info=True)
    return moved
