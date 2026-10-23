"""Open connections between rooms without a door or contact (pure, 0.26.5.3).

Community request (HarryP): a hallway that ends in the living room without a
door, a serving hatch, … Air moves through such openings all the time, but
FreshAirIQ only knew connections through doors with a contact.

The option ``open_connections`` maps a room key to the room keys it is openly
connected with. It is always kept symmetric; links to rooms that no longer
exist are ignored when read. Effects:

* a connected room counts as strongly linked for the passive ventilation
  estimate (like an explicit cross-zone connection);
* messages: a room whose connected neighbour is being aired is not asked to
  air separately, and a room is not asked to close while a connected open room
  keeps airing (both share the same air).
"""
from __future__ import annotations

from typing import Any, Iterable

OPTION = "open_connections"


def connection_map(options: dict[str, Any], room_keys: Iterable[str] | None = None) -> dict[str, set[str]]:
    """Symmetric ``room -> connected rooms`` (self links and unknown rooms dropped)."""
    raw = options.get(OPTION) if isinstance(options.get(OPTION), dict) else {}
    known = {str(k) for k in room_keys} if room_keys is not None else None
    out: dict[str, set[str]] = {}
    for key, others in raw.items():
        for other in others if isinstance(others, (list, tuple, set)) else []:
            a, b = str(key), str(other)
            if a == b or (known is not None and (a not in known or b not in known)):
                continue
            out.setdefault(a, set()).add(b)
            out.setdefault(b, set()).add(a)
    return out


def with_connections(options: dict[str, Any], room_key: str, connected: Iterable[str]) -> dict[str, list[str]]:
    """The option value after setting ``room_key``'s connections to ``connected``."""
    mapping = connection_map(options)
    room_key = str(room_key)
    for other in mapping.pop(room_key, set()):
        mapping.get(other, set()).discard(room_key)
    for other in {str(x) for x in connected} - {room_key}:
        mapping.setdefault(room_key, set()).add(other)
        mapping.setdefault(other, set()).add(room_key)
    return {key: sorted(values) for key, values in sorted(mapping.items()) if values}


def connected_pairs(options: dict[str, Any]) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, others in connection_map(options).items() for b in others}
