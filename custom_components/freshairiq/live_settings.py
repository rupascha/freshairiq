"""Every saved setting takes effect at once (pure helpers, 0.26.5.3).

Owner requirement: a change made anywhere – options pages, room sub-entries,
an automation writing the entry – must work immediately, never only after a
Home Assistant restart. The coordinator applies each config-entry change via
``async_sync_runtime_config``; these helpers decide what that change needs:

* rooms added, removed or renamed: their entities and devices are created per
  room, so the integration is reloaded (an open settings dialog stays open);
* a room that now has covers / moisture sources gets its shading / moisture
  source sensor enabled (it was created disabled while unconfigured);
* changed diagnostics settings trigger the diagnostics check at once.
"""
from __future__ import annotations

from typing import Any

DIAGNOSTICS_OPTION_KEYS = frozenset({"diagnostics_reporting_mode", "diagnostics_consent", "diagnostics_include_client_context"})


def room_structure(data: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Room keys and names the entities and devices were created with."""
    rooms = data.get("rooms") if isinstance(data.get("rooms"), list) else []
    return tuple(sorted(
        (str(room.get("key")), str(room.get("name") or room.get("key")))
        for room in rooms if isinstance(room, dict) and room.get("key")
    ))


def changed_option_keys(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def optional_room_sensors(data: dict[str, Any]) -> dict[str, bool]:
    """Unique-id suffix of each optional room sensor and whether the room now uses it."""
    rooms = data.get("rooms") if isinstance(data.get("rooms"), list) else []
    out: dict[str, bool] = {}
    for room in rooms:
        if isinstance(room, dict) and room.get("key"):
            out[f"{room['key']}_shading"] = bool(room.get("contact_covers") or room.get("covers"))
            out[f"{room['key']}_moisture_source"] = bool(room.get("moisture_sources"))
    return out
