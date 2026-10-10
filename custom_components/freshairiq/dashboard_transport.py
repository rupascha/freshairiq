"""Dashboard transport shaping (0.26.4.7).

The dashboard receives FreshAirIQ's live state through entity attributes. Every
coordinator cycle (about every 10 s) Home Assistant pushes changed attributes to
every open dashboard. The per-room hourly charts (up to 30 days × 24 h of
temperature and humidity) were part of that push – about 35 KB per room, sent
twice (status entity + the room's action entity) and resent every cycle because
the newest hourly point is updated continuously. Support exports showed status
attributes of 200–620 KB.

The hourly chart series are only needed when a room's detail view is open, so
they are served on demand by ``/api/freshairiq/room-history/<entry_id>``. The
coordinator data, diagnostics and every other attribute stay unchanged.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from typing import Any

# Chart-only series removed from the live attributes.
ON_DEMAND_ROOM_KEYS = ("temperature_history_14d", "humidity_history_14d")
DETAILS_API = "room_history_v1"


def slim_room(room: Any) -> Any:
    """Room payload for live attributes: identical except the on-demand chart series."""
    if not isinstance(room, dict) or not any(key in room for key in ON_DEMAND_ROOM_KEYS):
        return room
    slim = {key: value for key, value in room.items() if key not in ON_DEMAND_ROOM_KEYS}
    slim["history_on_demand"] = True
    return slim


def slim_rooms(rooms: Any) -> Any:
    if not isinstance(rooms, dict):
        return rooms
    return {key: slim_room(room) for key, room in rooms.items()}


def room_history_payload(rooms: Any, room_key: str | None = None) -> dict[str, Any]:
    """On-demand chart series for one room (``room_key``) or all rooms."""
    source = rooms if isinstance(rooms, dict) else {}
    keys = [room_key] if room_key else list(source)
    out: dict[str, Any] = {}
    for key in keys:
        room = source.get(key)
        if not isinstance(room, dict):
            continue
        out[str(key)] = {name: list(room.get(name) or []) for name in ON_DEMAND_ROOM_KEYS}
    return {"api": DETAILS_API, "rooms": out}
