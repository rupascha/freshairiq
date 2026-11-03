"""Deterministic first proposal for the house map (pure).

Home Assistant knows room names and floors, not wall coordinates. The proposal
therefore only uses what FreshAirIQ really has – floors, room dimensions or
volumes, door contacts shared by two rooms, configured open connections and
window orientations – and marks every object with where it came from. A contact
used by several rooms is a door only when the setup or Home Assistant says so;
a shared window (or a shared contact of unknown kind) is drawn once as a window
(see ``contact_role`` and ``window_homes``):

* ``config``   – length × width from the room setup;
* ``estimated``– floor area from volume ÷ height (2.5 m when unknown), square;
* ``schematic``– no size known: a 4 × 4 unit box without metric meaning.

Rooms are placed per floor without overlap: the best-connected room becomes the
spine (corridor) with its neighbours on both sides; otherwise rooms are packed
in rows. Two candidates are scored by explicit criteria and the better one wins.
The same input always gives the same layout. Existing (user) rooms are never
moved by ``add_missing``.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from .house_layout import (
    SCHEMA_VERSION, edge_bearing, empty_layout, polygons_overlap, shared_length,
)
from .house_wind import angle_between

ASSUMED_HEIGHT_M = 2.5
SCHEMATIC_SIDE = 4.0
GAP = 0.0
ORIENTATION_DEG = {"n": 0.0, "ne": 45.0, "e": 90.0, "se": 135.0, "s": 180.0, "sw": 225.0, "w": 270.0, "nw": 315.0}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def room_size(room: dict[str, Any]) -> tuple[float, float, str]:
    """Width, depth and provenance of a room's first footprint."""
    length, width = _number(room.get("length")), _number(room.get("width"))
    if length and width:
        return round(length, 2), round(width, 2), "config"
    volume, height = _number(room.get("volume")), _number(room.get("height"))
    if volume:
        side = math.sqrt(volume / (height or ASSUMED_HEIGHT_M))
        return round(side, 2), round(side, 2), "estimated"
    return SCHEMATIC_SIDE, SCHEMATIC_SIDE, "schematic"


def _contacts(room: dict[str, Any]) -> list[str]:
    contacts = room.get("contacts")
    if isinstance(contacts, str):
        return [contacts]
    return [str(c) for c in contacts if c] if isinstance(contacts, list) else []


DOOR_CLASSES = {"door", "garage_door"}


def contact_role(rooms: list[dict[str, Any]], contact: str, contact_classes: dict[str, Any] | None = None) -> str:
    """What a contact is, from what the setup and Home Assistant say – never from how often it is used.

    ``door``: stated as a door (contact kind or "door to a neighbouring room") in a room using it, or a door
    sensor in Home Assistant (device class door/garage_door); ``window``: stated as a window or a window sensor;
    ``unknown``: nothing says which. A contact used by several rooms (e.g. a guest WC window that also airs the
    hall) is still one physical opening in one place."""
    kinds = set()
    passage = False
    for room in rooms:
        if contact not in _contacts(room):
            continue
        stated = room.get("contact_kinds") if isinstance(room.get("contact_kinds"), dict) else {}
        doors = room.get("contact_passage_doors") if isinstance(room.get("contact_passage_doors"), dict) else {}
        kinds.add(stated.get(contact))
        passage = passage or doors.get(contact) is True
    device_class = str((contact_classes or {}).get(contact) or "")
    if "door" in kinds or passage or (not kinds & {"window"} and device_class in DOOR_CLASSES):
        return "door"
    if "window" in kinds or device_class == "window":
        return "window"
    return "unknown"


def adjacency(rooms: list[dict[str, Any]], open_connections: dict[str, Iterable[str]] | None = None,
              contact_classes: dict[str, Any] | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    """Known neighbour pairs: shared door contacts and configured open connections.

    Hotfix after review (F02): a contact used by two rooms is a door between them only when it is known to be a door.
    A shared window – and a shared contact of unknown kind, like an unknown contact of one room – is no connection:
    it is drawn once as a window (see ``window_homes``)."""
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    owners: dict[str, list[str]] = {}
    for room in rooms:
        for contact in _contacts(room):
            owners.setdefault(contact, []).append(str(room["key"]))
    for contact, keys in sorted(owners.items()):
        role = contact_role(rooms, contact, contact_classes) if len(set(keys)) > 1 else "single"
        if role != "door":
            continue
        for i, a in enumerate(sorted(set(keys))):
            for b in sorted(set(keys))[i + 1:]:
                pairs.setdefault((a, b), {"kind": "door", "contacts": []})["contacts"].append(contact)
    for key, others in sorted((open_connections or {}).items()):
        for other in sorted(others):
            a, b = sorted((str(key), str(other)))
            if a != b:
                pairs.setdefault((a, b), {"kind": "open_passage", "contacts": []})
    return pairs


def _box(x: float, y: float, w: float, d: float) -> list[list[float]]:
    return [[round(x, 3), round(y, 3)], [round(x + w, 3), round(y, 3)], [round(x + w, 3), round(y + d, 3)], [round(x, 3), round(y + d, 3)]]


def _shelf(rooms: list[dict[str, Any]], sizes: dict[str, tuple[float, float, str]]) -> dict[str, list[list[float]]]:
    total = sum(sizes[r["key"]][0] * sizes[r["key"]][1] for r in rooms)
    row_width = max(math.sqrt(total) * 1.5, max((sizes[r["key"]][0] for r in rooms), default=0.0))
    placed: dict[str, list[list[float]]] = {}
    x = y = row_depth = 0.0
    for room in rooms:
        w, d, _ = sizes[room["key"]]
        if x > 0 and x + w > row_width + 1e-9:
            x, y, row_depth = 0.0, y - row_depth - GAP, 0.0
        placed[room["key"]] = _box(x, y - d, w, d)
        x += w + GAP
        row_depth = max(row_depth, d)
    return placed


def _spine(rooms: list[dict[str, Any]], sizes: dict[str, tuple[float, float, str]], pairs: dict[tuple[str, str], Any]) -> dict[str, list[list[float]]] | None:
    keys = [r["key"] for r in rooms]
    degree = {k: sum(1 for a, b in pairs if k in (a, b) and a in keys and b in keys) for k in keys}
    hub = max(keys, key=lambda k: (degree[k], -keys.index(k)))
    neighbours = [k for k in keys if k != hub and tuple(sorted((hub, k))) in pairs]
    if len(neighbours) < 2:
        return None
    above, below = neighbours[0::2], neighbours[1::2]
    width_above = sum(sizes[k][0] for k in above)
    width_below = sum(sizes[k][0] for k in below)
    hub_w, hub_d, _ = sizes[hub]
    spine_len = max(width_above, width_below, hub_w)
    spine_depth = max(hub_w * hub_d / spine_len, 1.0)
    placed = {hub: _box(0.0, 0.0, spine_len, spine_depth)}
    x = 0.0
    for key in above:
        placed[key] = _box(x, spine_depth, sizes[key][0], sizes[key][1]); x += sizes[key][0]
    x = 0.0
    for key in below:
        placed[key] = _box(x, -sizes[key][1], sizes[key][0], sizes[key][1]); x += sizes[key][0]
    rest = [r for r in rooms if r["key"] not in placed]
    if rest:
        offset = spine_len + 1.0
        for key, polygon in _shelf(rest, sizes).items():
            placed[key] = [[round(p[0] + offset, 3), round(p[1] + spine_depth, 3)] for p in polygon]
    return placed


def _touching(first: list[list[float]], second: list[list[float]]) -> float:
    best = 0.0
    for i in range(len(first)):
        a1, a2 = tuple(first[i]), tuple(first[(i + 1) % len(first)])
        for j in range(len(second)):
            best = max(best, shared_length(a1, a2, tuple(second[j]), tuple(second[(j + 1) % len(second)])))
    return best


def _shared_offset(a1: tuple[float, float], a2: tuple[float, float], other: list[list[float]]) -> float:
    """Centre (0–1) of the longest stretch of wall ``a1–a2`` that ``other`` shares (0.5 when none)."""
    length = math.dist(a1, a2)
    ux, uy = (a2[0] - a1[0]) / length, (a2[1] - a1[1]) / length
    best, centre = 0.0, 0.5
    for j in range(len(other)):
        b1, b2 = tuple(other[j]), tuple(other[(j + 1) % len(other)])
        shared = shared_length(a1, a2, b1, b2)
        if shared > best:
            t1, t2 = sorted(((b1[0] - a1[0]) * ux + (b1[1] - a1[1]) * uy, (b2[0] - a1[0]) * ux + (b2[1] - a1[1]) * uy))
            best, centre = shared, (max(t1, 0.0) + min(t2, length)) / 2 / length
    return round(centre, 3)


def _free_offset(a1: tuple[float, float], a2: tuple[float, float], others: list[list[list[float]]]) -> float | None:
    """Centre (0–1) of the longest stretch of wall ``a1–a2`` not shared with another room (None = fully shared)."""
    length = math.dist(a1, a2)
    ux, uy = (a2[0] - a1[0]) / length, (a2[1] - a1[1]) / length
    covered: list[tuple[float, float]] = []
    for polygon in others:
        for j in range(len(polygon)):
            b1, b2 = tuple(polygon[j]), tuple(polygon[(j + 1) % len(polygon)])
            if shared_length(a1, a2, b1, b2) > 0:
                t = sorted(((b1[0] - a1[0]) * ux + (b1[1] - a1[1]) * uy, (b2[0] - a1[0]) * ux + (b2[1] - a1[1]) * uy))
                covered.append((max(t[0], 0.0), min(t[1], length)))
    best, start = (0.0, 0.0), 0.0
    for lo, hi in sorted(covered) + [(length, length)]:
        if lo - start > best[1] - best[0]:
            best = (start, lo)
        start = max(start, hi)
    return round((best[0] + best[1]) / 2 / length, 3) if best[1] - best[0] > 0.05 else None


def _exterior_edges(key: str, placed: dict[str, list[list[float]]]) -> dict[int, float]:
    """Exterior walls of a room and where on each wall the outside is (offset 0–1)."""
    own = placed[key]
    others = [p for k, p in placed.items() if k != key]
    out: dict[int, float] = {}
    for i in range(len(own)):
        offset = _free_offset(tuple(own[i]), tuple(own[(i + 1) % len(own)]), others)
        if offset is not None:
            out[i] = offset
    return out


def score(placed: dict[str, list[list[float]]], pairs: dict[tuple[str, str], Any], windows: dict[str, list[str]]) -> dict[str, Any]:
    keys = sorted(placed)
    overlaps = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]
                if polygons_overlap([tuple(p) for p in placed[a]], [tuple(p) for p in placed[b]])]
    unmet = sorted(f"{a}+{b}" for (a, b) in pairs if a in placed and b in placed and _touching(placed[a], placed[b]) < 0.5)
    no_facade = sorted(k for k, contacts in windows.items() if contacts and k in placed and not _exterior_edges(k, placed))
    return {"value": len(overlaps) * 100 + len(unmet) * 10 + len(no_facade) * 5, "overlaps": len(overlaps),
            "unmet_adjacency": unmet, "windows_without_facade": no_facade}


def _best_edge(key: str, placed: dict[str, list[list[float]]], orientation: str | None) -> tuple[int, float | None, str]:
    """Wall, position on it (None = no free exterior stretch) and provenance for a window."""
    pts = [tuple(p) for p in placed[key]]
    exterior = _exterior_edges(key, placed)
    if not exterior:
        return 0, None, "auto"
    if orientation in ORIENTATION_DEG:
        wanted = ORIENTATION_DEG[str(orientation)]
        index = min(exterior, key=lambda i: (angle_between(edge_bearing(pts, i, 0.0), wanted), i))
        return index, exterior[index], "config"
    index = min(exterior)
    return index, exterior[index], "auto"


def window_homes(rooms: list[dict[str, Any]], sizes: dict[str, tuple[float, float, str]], pairs: dict[tuple[str, str], Any]) -> dict[str, str]:
    """The one room a window used by several rooms is drawn in (a shared door is drawn between them).

    The room that states it as a window wins, then the room with fewer contacts (a bathroom or guest WC lists its
    own window, a hall borrows its neighbours' windows on top of its own), then the smaller room, then the room key –
    the same input always gives the same place; the editor can move it."""
    in_pairs = {c for info in pairs.values() for c in info.get("contacts", [])}
    users: dict[str, list[dict[str, Any]]] = {}
    for room in rooms:
        for contact in _contacts(room):
            users.setdefault(contact, []).append(room)
    homes = {}
    for contact, members in users.items():
        if len({str(r["key"]) for r in members}) < 2 or contact in in_pairs:
            continue
        homes[contact] = str(min(members, key=lambda r, c=contact: _home_rank(r, c, sizes))["key"])
    return homes


def _home_rank(room: dict[str, Any], contact: str, sizes: dict[str, tuple[float, float, str]]) -> tuple[bool, int, float, str]:
    stated = room.get("contact_kinds") if isinstance(room.get("contact_kinds"), dict) else {}
    size = sizes.get(room["key"])
    return (stated.get(contact) != "window", len(_contacts(room)), size[0] * size[1] if size else math.inf, str(room["key"]))


def _openings(rooms: list[dict[str, Any]], placed: dict[str, list[list[float]]], pairs: dict[tuple[str, str], Any],
              homes: dict[str, str] | None = None) -> list[dict[str, Any]]:
    shared = {c for info in pairs.values() for c in info.get("contacts", [])}
    openings: list[dict[str, Any]] = []
    per_edge: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for room in rooms:
        key = room["key"]
        orientations = room.get("contact_orientations") if isinstance(room.get("contact_orientations"), dict) else {}
        kinds = room.get("contact_kinds") if isinstance(room.get("contact_kinds"), dict) else {}  # 0.26.5.5
        for contact in _contacts(room):
            if contact in shared or (homes or {}).get(contact, key) != key:
                continue
            orientation = orientations.get(contact) or room.get("window_orientation")
            index, offset, provenance = _best_edge(key, placed, orientation if orientation in ORIENTATION_DEG else None)
            item = {"id": f"o_{key}_{len([o for o in openings if o['room_id'] == f'r_{key}'])}", "room_id": f"r_{key}", "edge": index,
                    "offset": 0.5 if offset is None else offset, "width_m": None,
                    # a contact stated as a door is an outside door, every other one a window (as before)
                    "kind": "door" if kinds.get(contact) == "door" else "window", "mechanics": "door" if kinds.get(contact) == "door" else "unknown",
                    "contacts": [contact], "provenance": provenance if offset is not None else "unplaced"}
            openings.append(item)
            if offset is not None:
                per_edge.setdefault((key, index), []).append(item)
    for (a, b), info in sorted(pairs.items()):
        if info["kind"] != "door" or a not in placed or b not in placed or _touching(placed[a], placed[b]) < 0.5:
            continue
        pts_a = placed[a]
        index = max(range(len(pts_a)), key=lambda i: (_touching([pts_a[i], pts_a[(i + 1) % len(pts_a)]], placed[b]), -i))
        # hotfix after review: the door sits in the middle of the stretch both rooms share, not of the whole wall
        offset = _shared_offset(tuple(pts_a[index]), tuple(pts_a[(index + 1) % len(pts_a)]), placed[b])
        item = {"id": f"d_{a}_{b}", "room_id": f"r_{a}", "edge": index, "offset": offset, "width_m": None, "kind": "door",
                "mechanics": "door", "contacts": list(info["contacts"]), "provenance": "auto"}
        openings.append(item)  # hotfix after review: a door stays on the shared stretch – only windows are spread
    for items in per_edge.values():
        if len(items) > 1:  # several windows on one wall: spread them over the wall's free stretch
            centre = items[0]["offset"]
            for n, item in enumerate(items):
                item["offset"] = round(min(max(centre + (n - (len(items) - 1) / 2) * 0.8 / len(items), 0.05), 0.95), 3)
    return openings


def propose(rooms: list[dict[str, Any]], levels: list[str], open_connections: dict[str, Iterable[str]] | None = None,
            contact_classes: dict[str, Any] | None = None) -> dict[str, Any]:
    """A complete proposal for the configured rooms (calculated rooms with a key only).

    ``contact_classes``: Home Assistant device class per contact entity (door, window, …) where known."""
    rooms = [r for r in rooms if isinstance(r, dict) and r.get("key")]
    layout = empty_layout()
    floors = list(dict.fromkeys([str(level) for level in levels] + [str(r.get("floor") or "unassigned") for r in rooms]))
    layout["floors"] = [{"id": f"f_{level}", "name": level, "level_key": level, "order": i} for i, level in enumerate(floors)]
    pairs = adjacency(rooms, open_connections, contact_classes)
    sizes = {r["key"]: room_size(r) for r in rooms}
    homes = window_homes(rooms, sizes, pairs)
    windows = {r["key"]: [c for c in _contacts(r) if homes.get(c, r["key"]) == r["key"]] for r in rooms}
    quality: dict[str, Any] = {"floors": {}, "provenance": {k: v[2] for k, v in sizes.items()}}
    for level in floors:
        members = sorted((r for r in rooms if str(r.get("floor") or "unassigned") == level), key=lambda r: (int(r.get("sort_order", 0) or 0), r["key"]))
        if not members:
            continue
        floor_pairs = {p: v for p, v in pairs.items() if p[0] in {r["key"] for r in members} and p[1] in {r["key"] for r in members}}
        candidates = [c for c in (_spine(members, sizes, floor_pairs), _shelf(members, sizes)) if c is not None]
        scored = [(score(c, floor_pairs, {r["key"]: windows[r["key"]] for r in members}), c) for c in candidates]
        best_score, placed = min(scored, key=lambda item: item[0]["value"])
        quality["floors"][level] = {**best_score, "candidates": len(candidates)}
        for room in members:
            layout["rooms"].append({"id": f"r_{room['key']}", "room_key": room["key"], "floor_id": f"f_{level}",
                                    "polygon": placed[room["key"]], "provenance": sizes[room["key"]][2]})
        layout["openings"].extend(_openings(members, placed, floor_pairs, homes))
    doors = {o["id"] for o in layout["openings"] if o["kind"] == "door"}
    for (a, b), info in sorted(pairs.items()):
        if f"d_{a}_{b}" in doors:
            continue  # the door is drawn on the shared wall; its contact carries the state
        layout["connections"].append({"id": f"c_{a}_{b}", "a": f"r_{a}", "b": f"r_{b}", "kind": info["kind"],
                                      "contacts": list(info.get("contacts", [])), "confirmed": info["kind"] == "open_passage",
                                      "provenance": "config"})
    layout["building"]["units"] = "m" if any(v[2] != "schematic" for v in sizes.values()) else "schematic"
    layout["schema_version"] = SCHEMA_VERSION
    return {"layout": layout, "quality": quality}


def add_missing(layout: dict[str, Any], rooms: list[dict[str, Any]], levels: list[str]) -> dict[str, Any]:
    """Add configured rooms that are not drawn yet next to each floor's drawing; nothing existing moves."""
    drawn = {r.get("room_key") for r in layout.get("rooms", [])}
    missing = [r for r in rooms if isinstance(r, dict) and r.get("key") and r["key"] not in drawn]
    if not missing:
        return layout
    proposal = propose(missing, levels)["layout"]
    floor_ids = {f["id"] for f in layout.get("floors", [])}
    for floor in proposal["floors"]:
        if floor["id"] not in floor_ids:
            layout.setdefault("floors", []).append({**floor, "order": len(layout.get("floors", []))})
    for room in proposal["rooms"]:
        existing = [p for r in layout.get("rooms", []) if r.get("floor_id") == room["floor_id"] for p in r.get("polygon", [])]
        shift = (max(p[0] for p in existing) + 1.0) if existing else 0.0
        layout.setdefault("rooms", []).append({**room, "polygon": [[round(p[0] + shift, 3), p[1]] for p in room["polygon"]]})
    layout.setdefault("openings", []).extend(o for o in proposal["openings"] if o["kind"] == "window")
    return layout
