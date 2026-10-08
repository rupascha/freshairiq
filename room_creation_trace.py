"""Privacy-safe diagnostics for the room-creation configuration path."""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from homeassistant.core import HomeAssistant


def _digest(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _room_subentries(entry: Any) -> list[Any]:
    return [
        subentry
        for subentry in getattr(entry, "subentries", {}).values()
        if getattr(subentry, "subentry_type", None) == "room"
    ]


def room_creation_snapshot(entry: Any, *, room_key: Any = None) -> dict[str, Any]:
    """Return counts/fingerprints only; never names, entities or raw room data."""
    rooms = entry.data.get("rooms", []) if isinstance(getattr(entry, "data", None), dict) else []
    if not isinstance(rooms, list):
        rooms = []
    subentries = _room_subentries(entry)
    return {
        "parent_room_count": len(rooms),
        "parent_room_fingerprints": sorted(filter(None, (_digest(room.get("key")) for room in rooms if isinstance(room, dict)))),
        "room_subentry_count": len(subentries),
        "room_subentry_fingerprints": sorted(filter(None, (_digest((getattr(sub, "unique_id", "") or "").removeprefix("room:")) for sub in subentries))),
        "target_room_fingerprint": _digest(room_key),
    }


def trace_room_creation(
    hass: HomeAssistant,
    entry: Any,
    *,
    source: str,
    stage: str,
    room_key: Any = None,
    outcome: str | None = None,
    error_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Schedule a sparse trace without delaying or changing configuration logic."""
    coordinator = getattr(entry, "runtime_data", None)
    recorder = getattr(coordinator, "diagnostics", None)
    if recorder is None or not hasattr(recorder, "async_record_room_creation_trace"):
        return
    event = {
        "source": str(source),
        "stage": str(stage),
        "outcome": str(outcome) if outcome else None,
        "error_type": str(error_type)[:80] if error_type else None,
        **room_creation_snapshot(entry, room_key=room_key),
    }
    if extra:
        for key, value in extra.items():
            if key in {"attempt", "commit_wait_ms", "reload_scheduled", "validation_error_keys"}:
                event[key] = value
    hass.async_create_task(recorder.async_record_room_creation_trace(event))


def trace_room_creation_after_reload(
    hass: HomeAssistant,
    entry_id: str,
    *,
    source: str,
    room_key: Any = None,
    delay_seconds: float = 2.0,
) -> None:
    """Capture the canonical/subentry state after the scheduled reload had time to run."""
    async def _later() -> None:
        await asyncio.sleep(delay_seconds)
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return
        trace_room_creation(
            hass, entry, source=source, stage="post_reload_state",
            room_key=room_key, outcome="observed",
        )

    hass.async_create_task(_later())
