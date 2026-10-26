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

0.26.5.3 (community: recorder load): an entity writes a recorder row whenever
any attribute changes, also one excluded from the database. The room payload on
the room action entity carried counters that grow every cycle (ages of the
readings in seconds, the length of the moisture-source window, the duration of
high humidity, the evaluation time as "last measurement"). ``stable_room_payload``
publishes the report times instead, so the entity changes only when a reading
or a result changes. The dashboard reads the complete live payload through the
live channel (``dashboard_live``), which never touches the recorder.

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


# Counters that change every cycle -> left out of the recorded room payload.
VOLATILE_ROOM_KEYS = (
    "frame_age_temp_s", "frame_age_humidity_s", "frame_age_reference_temp_s", "frame_age_reference_humidity_s",
    "measurement_frame_max_age_s", "moisture_source_window_min", "humidity_high_duration_min",
    "air_exchange",  # 0.26.5.4: changes every cycle while airing; the dashboard gets it over the live channel
)
_ROOM_STAMPS = ("frame_temp_reported_at", "frame_humidity_reported_at")
_ALL_STAMPS = (*_ROOM_STAMPS, "frame_reference_temp_reported_at", "frame_reference_humidity_reported_at")


def stable_room_payload(room: Any) -> Any:
    """Room payload for the room action entity: no per-cycle counters.

    ``last_measurement_at`` becomes the newest report of the room's own
    sensors (the evaluation time changed every cycle), and the oldest report
    of the frame replaces its maximum age.
    """
    room = slim_room(room)
    if not isinstance(room, dict):
        return room
    stable = {key: value for key, value in room.items() if key not in VOLATILE_ROOM_KEYS}
    room_stamps = [str(room[key]) for key in _ROOM_STAMPS if room.get(key)]
    all_stamps = [str(room[key]) for key in _ALL_STAMPS if room.get(key)]
    if "last_measurement_at" in stable:
        stable["last_measurement_at"] = max(room_stamps) if room_stamps else None
    stable["measurement_frame_oldest_at"] = min(all_stamps) if len(all_stamps) == len(_ALL_STAMPS) else None
    return stable


# The moisture-source detector re-fits its sliding window every cycle; outside an
# active source (or its recovery) these values carry no news.
SOURCE_DETAIL_KEYS = (
    "moisture_source_rate_ml_min", "moisture_source_ah_rise_g_m3",
    "moisture_source_observed_change_ml_window", "moisture_source_generated_ml_window",
)


def hold_source_details(room: Any, held: dict[str, Any] | None) -> tuple[Any, dict[str, Any] | None]:
    """Room payload with the detector values of the last source while none is active.

    Returns the payload to publish and the values to hold for the next cycle.
    """
    if not isinstance(room, dict):
        return room, held
    if room.get("moisture_source_active") or room.get("moisture_source_recovery"):
        return room, {key: room.get(key) for key in SOURCE_DETAIL_KEYS}
    return {**room, **(held or dict.fromkeys(SOURCE_DETAIL_KEYS))}, held


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
