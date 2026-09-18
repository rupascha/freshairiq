"""Repair issue support for FreshAirIQ.

FreshAirIQ only raises a repair when a configured *required* entity has actually
been removed from Home Assistant. A temporarily unavailable entity is not a
configuration repair and must not create a persistent user-facing warning.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .typing import FreshAirIQConfigEntry
from .const import (
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOMS,
    DOMAIN,
)

_ISSUE_PREFIX = "missing_required_entities_"


def _required_entity_references(entry: FreshAirIQConfigEntry) -> list[tuple[str, str]]:
    """Return required entity IDs with a human-readable configuration context."""
    refs: list[tuple[str, str]] = []
    data = entry.data if isinstance(entry.data, Mapping) else {}

    weather = str(data.get(CONF_OUTDOOR_WEATHER) or "").strip()
    if weather:
        refs.append((weather, "Außenwetter"))
    else:
        temperature = str(data.get(CONF_OUTDOOR_TEMPERATURE) or "").strip()
        humidity = str(data.get(CONF_OUTDOOR_HUMIDITY) or "").strip()
        if temperature:
            refs.append((temperature, "Außentemperatur"))
        if humidity:
            refs.append((humidity, "Außenfeuchte"))

    raw_rooms = data.get(CONF_ROOMS, [])
    if not isinstance(raw_rooms, list):
        return refs
    for room in raw_rooms:
        if not isinstance(room, Mapping) or not room.get(CONF_ROOM_INCLUDE_CALCULATIONS, True):
            continue
        room_name = str(room.get("name") or room.get("key") or "Raum")
        temperature = str(room.get(CONF_ROOM_TEMPERATURE) or "").strip()
        humidity = str(room.get(CONF_ROOM_HUMIDITY) or "").strip()
        if temperature:
            refs.append((temperature, f"{room_name}: Temperatur"))
        if humidity:
            refs.append((humidity, f"{room_name}: Luftfeuchte"))
        contacts = room.get(CONF_ROOM_CONTACTS) or []
        if isinstance(contacts, str):
            contacts = [contacts]
        if isinstance(contacts, list):
            for contact in contacts:
                entity_id = str(contact or "").strip()
                if entity_id:
                    refs.append((entity_id, f"{room_name}: Fenster/Tür"))
    return refs


def _entity_was_removed(hass: HomeAssistant, registry: er.EntityRegistry, entity_id: str) -> bool:
    """Return True only when an entity no longer exists in state or registry."""
    return hass.states.get(entity_id) is None and registry.async_get(entity_id) is None


def missing_required_entities(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> list[tuple[str, str]]:
    """Return required references that were actually removed from Home Assistant."""
    registry = er.async_get(hass)
    seen: set[str] = set()
    missing: list[tuple[str, str]] = []
    for entity_id, context in _required_entity_references(entry):
        if entity_id in seen:
            continue
        seen.add(entity_id)
        if _entity_was_removed(hass, registry, entity_id):
            missing.append((entity_id, context))
    return missing


def issue_id_for_entry(entry: FreshAirIQConfigEntry) -> str:
    """Return the stable repair issue ID for one FreshAirIQ config entry."""
    return f"{_ISSUE_PREFIX}{entry.entry_id}"


def async_sync_missing_entity_issue(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> None:
    """Create or clear the actionable missing-entity repair issue."""
    issue_id = issue_id_for_entry(entry)
    missing = missing_required_entities(hass, entry)
    if not missing:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    summary = ", ".join(f"{context} ({entity_id})" for entity_id, context in missing)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="missing_required_entities",
        translation_placeholders={
            "entry_title": str(getattr(entry, "title", None) or "FreshAirIQ"),
            "entities": summary,
        },
        data={
            "entry_id": entry.entry_id,
            "entities": ",".join(entity_id for entity_id, _context in missing),
        },
    )


def async_clear_missing_entity_issue(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> None:
    """Remove the repair issue when the config entry is unloaded or removed."""
    ir.async_delete_issue(hass, DOMAIN, issue_id_for_entry(entry))
