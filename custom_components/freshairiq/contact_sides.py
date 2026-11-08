"""Where an opening leads: outside or into another room (pure).

Every opening contact of a room is either an *outside* opening (window, terrace,
balcony or front door) or an *inside* opening (a door into another room). Only
outside openings exchange air with the outside: they start airings, choose the
incoming air, count for the contact mode "all", feed learning and statistics and
make up cross ventilation. An inside door never does any of that on its own. It
only tells whether two rooms are actually connected while an airing runs.

``contact_sides`` stores ``"inside"`` for inside openings only; a contact without
an entry is an outside opening. Configurations from before this setting therefore
behave exactly as they did until the user changes a contact.

``contact_connected_rooms`` optionally names the room an inside opening leads to.
The same inside contact configured in two rooms connects those two rooms as well.
No connection is ever guessed beyond that.
"""
from __future__ import annotations

from typing import Any, Iterable

from .const import (
    CONF_CONTACT_CONNECTED_ROOMS,
    CONF_CONTACT_SIDES,
    CONF_ROOM_CONTACT,
    CONF_ROOM_CONTACTS,
    CONTACT_SIDE_INSIDE,
    CONTACT_SIDE_OUTSIDE,
)

#: runtime-only room key with the inside contacts (never stored)
RUNTIME_INSIDE_CONTACTS = "_inside_contacts"
#: runtime-only room key with every configured contact (never stored)
RUNTIME_ALL_CONTACTS = "_all_contacts"
OPEN_MODES = {"open", "tilted"}


def configured_contacts(room: dict[str, Any]) -> list[str]:
    """Every configured opening contact of a stored room (legacy single contact included)."""
    if isinstance(room.get(RUNTIME_ALL_CONTACTS), list):
        return [str(c) for c in room[RUNTIME_ALL_CONTACTS] if c]
    contacts = room.get(CONF_ROOM_CONTACTS)
    if isinstance(contacts, str):
        return [contacts] if contacts else []
    if isinstance(contacts, list):
        return list(dict.fromkeys(str(c) for c in contacts if c))
    legacy = room.get(CONF_ROOM_CONTACT)
    return [str(legacy)] if legacy else []


def side(room: dict[str, Any], contact: str) -> str:
    """``outside`` unless the contact is explicitly configured as an inside opening."""
    sides = room.get(CONF_CONTACT_SIDES)
    if isinstance(sides, dict) and sides.get(contact) == CONTACT_SIDE_INSIDE:
        return CONTACT_SIDE_INSIDE
    return CONTACT_SIDE_OUTSIDE


def connected_room(room: dict[str, Any], contact: str) -> str | None:
    """The room an inside opening leads to, when the user named one."""
    if side(room, contact) != CONTACT_SIDE_INSIDE:
        return None
    rooms = room.get(CONF_CONTACT_CONNECTED_ROOMS)
    value = rooms.get(contact) if isinstance(rooms, dict) else None
    value = str(value or "").strip()
    return value if value and value != str(room.get("key") or "") else None


def side_conflicts(rooms: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    """Contacts configured in several rooms with different sides: ``contact -> room keys``."""
    seen: dict[str, dict[str, str]] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        key = str(room.get("key") or "")
        for contact in configured_contacts(room):
            seen.setdefault(contact, {})[key] = side(room, contact)
    return {c: sorted(by_room) for c, by_room in seen.items() if len(set(by_room.values())) > 1}


def conflicting_side(rooms: Iterable[dict[str, Any]], room_key: str, contact: str, wanted: str) -> str | None:
    """Name of another room that classifies ``contact`` differently from ``wanted`` (config flow check)."""
    for room in rooms:
        if not isinstance(room, dict) or str(room.get("key") or "") == str(room_key):
            continue
        if contact in configured_contacts(room) and side(room, contact) != wanted:
            return str(room.get("name") or room.get("key") or "")
    return None


def runtime_view(room: dict[str, Any], conflicts: Iterable[str] = ()) -> dict[str, Any]:
    """The room as the ventilation logic sees it: ``contacts`` holds only outside openings.

    A contact with conflicting sides in several rooms keeps the previous (outside)
    behaviour; the conflict is reported separately and never resolved silently.
    """
    contacts = configured_contacts(room)
    conflicted = set(conflicts)
    inside = [c for c in contacts if side(room, c) == CONTACT_SIDE_INSIDE and c not in conflicted]
    view = dict(room)
    view[RUNTIME_ALL_CONTACTS] = contacts
    view[RUNTIME_INSIDE_CONTACTS] = inside
    if inside:
        view[CONF_ROOM_CONTACTS] = [c for c in contacts if c not in inside]
        view.pop(CONF_ROOM_CONTACT, None)
    return view


def inside_contacts(room: dict[str, Any]) -> list[str]:
    """Inside openings of a runtime room (empty for stored rooms without the runtime view)."""
    value = room.get(RUNTIME_INSIDE_CONTACTS)
    return [str(c) for c in value] if isinstance(value, list) else []


def _sensor_pairs(rooms: Iterable[dict[str, Any]]) -> dict[str, set[frozenset[str]]]:
    """Every room pair each inside sensor claims: named connected rooms plus the implicit pair of a sensor in exactly two rooms.

    A runtime room uses its runtime classification only – an empty runtime list (e.g. a side conflict) never
    falls back to the stored classification.
    """
    claims: dict[str, set[frozenset[str]]] = {}
    owners: dict[str, set[str]] = {}
    room_list = [r for r in rooms if isinstance(r, dict)]
    keys = {str(r.get("key") or "") for r in room_list}
    for room in room_list:
        key = str(room.get("key") or "")
        if isinstance(room.get(RUNTIME_INSIDE_CONTACTS), list):
            inside = inside_contacts(room)
        else:
            inside = [c for c in configured_contacts(room) if side(room, c) == CONTACT_SIDE_INSIDE]
        for contact in inside:
            owners.setdefault(contact, set()).add(key)
            claims.setdefault(contact, set())
            other = connected_room(room, contact)
            if other and other in keys:
                claims[contact].add(frozenset({key, other}))
    for contact, holders in owners.items():
        if len(holders) == 2:          # a door joins two rooms; in three or more the sensor names no single pair
            claims[contact].add(frozenset(holders))
    return claims


def door_links(rooms: Iterable[dict[str, Any]]) -> dict[frozenset[str], set[str]]:
    """Room pairs joined by an inside opening: ``{room_a, room_b} -> inside contacts``.

    Only explicit knowledge counts: a named connected room, or the same inside contact configured in exactly two
    rooms. One sensor watches one door: when its named and implicit pairs disagree (F05, e.g. shared by A and B
    but named A → C) it joins no rooms at all – see ``door_link_conflicts``.
    """
    links: dict[frozenset[str], set[str]] = {}
    for contact, pairs in _sensor_pairs(rooms).items():
        if len(pairs) == 1:
            links.setdefault(next(iter(pairs)), set()).add(contact)
    return links


def door_link_conflicts(rooms: Iterable[dict[str, Any]]) -> dict[str, list[list[str]]]:
    """Inside sensors whose configuration claims more than one room pair (reported, never resolved silently)."""
    return {c: sorted(sorted(p) for p in pairs) for c, pairs in _sensor_pairs(rooms).items() if len(pairs) > 1}


def door_path(links: dict[frozenset[str], set[str]], a: str, b: str, modes: dict[str, str]) -> str | None:
    """``open``/``closed`` for a pair joined only by known inside openings, ``None`` without such knowledge.

    ``modes`` maps contact -> normalised state. An unknown state is no evidence
    of a closed door, so the pair then keeps its previous treatment (``None``).
    """
    doors = links.get(frozenset({a, b}))
    if not doors:
        return None
    states = [modes.get(d, "unknown") for d in doors]
    if any(s in OPEN_MODES for s in states):
        return "open"
    if all(s == "closed" for s in states):
        return "closed"
    return None
