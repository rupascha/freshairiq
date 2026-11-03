"""House map layout: versioned schema, plan geometry and validation (pure).

The optional house map draws FreshAirIQ rooms as free polygons on their floors,
with openings sitting on a concrete wall. The layout is a separate, versioned
document; it never changes the room configuration (volume, contacts, …) and it
never feeds the ventilation decision.

Plan coordinates are metres (or schematic units, ``building.units``) with x to
the right and y **up** (mathematical orientation). ``building.north_deg`` is the
compass bearing of the plan's "up" direction (0 = up is north, 90 = up is east).
Polygons are stored counter-clockwise; an edge ``i`` runs from vertex ``i`` to
vertex ``i + 1`` and its outward normal points to the right of that direction.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

SCHEMA_VERSION = 1
LIMITS = {
    "floors": 30, "rooms": 200, "vertices": 64, "openings": 800, "connections": 800,
    "text": 120, "coordinate": 10000.0, "contacts": 8,
}
UNITS = ("m", "schematic")
OPENING_KINDS = ("window", "door", "roof_window", "passage", "vent")
OPENING_MECHANICS = ("unknown", "turn_tilt", "casement", "tilt_only", "sliding", "roof", "door", "fixed_vent")
CONNECTION_KINDS = ("open_passage", "door", "stairs", "shaft", "duct")
PROVENANCE = ("ha", "config", "estimated", "schematic", "auto", "unplaced", "traced", "user")
OUTSIDE = "outside"
EPS = 1e-6
WALL_TOLERANCE = 0.05  # 5 cm (or 0.05 schematic units): walls closer than this are shared
# Hotfix 0.26.6.0: a wall two rooms really share is at least as long as the narrowest opening (as in the card)
MIN_SHARED_WALL = 0.3
PHYSICAL_CONNECTIONS = ("door", "open_passage")
# 0.26.6.0(2): optional door attributes (absent in older plans = drawn as before: hinge at the wall's start, into the room)
DOOR_HINGES = ("left", "right")   # seen from inside the room the door belongs to, facing the wall
DOOR_SWINGS = ("in", "out")       # into that room, or to the other side of the wall  # a way through the shared wall; stairs, shafts and ducts are not


# --------------------------------------------------------------------------- geometry
def signed_area(points: list[tuple[float, float]]) -> float:
    """Shoelace area; positive for counter-clockwise polygons."""
    total = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, tol: float = EPS) -> bool:
    if abs(_orient(a, b, p)) > tol * max(1.0, math.dist(a, b)):
        return False
    return min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol


def segments_cross(a, b, c, d) -> bool:
    """True when the open segments ab and cd cross in a single interior point."""
    d1, d2, d3, d4 = _orient(c, d, a), _orient(c, d, b), _orient(a, b, c), _orient(a, b, d)
    return ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and ((d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS))


def self_intersects(points: list[tuple[float, float]]) -> bool:
    """Any two non-adjacent edges touching or crossing (simple polygons only)."""
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            c, d = points[j], points[(j + 1) % n]
            if segments_cross(a, b, c, d) or _on_segment(a, b, c) or _on_segment(a, b, d) or _on_segment(c, d, a) or _on_segment(c, d, b):
                return True
    return False


def point_in_polygon(point: tuple[float, float], points: list[tuple[float, float]]) -> str:
    """``inside``, ``outside`` or ``boundary``."""
    n = len(points)
    inside = False
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        if _on_segment(a, b, point, WALL_TOLERANCE / 10):
            return "boundary"
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x:
                inside = not inside
    return "inside" if inside else "outside"


def interior_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    """A point strictly inside a simple counter-clockwise polygon (centroid of its first ear)."""
    n = len(points)
    for i in range(n):
        a, b, c = points[i - 1], points[i], points[(i + 1) % n]
        if _orient(a, b, c) <= EPS:
            continue
        centre = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0)
        if point_in_polygon(centre, points) == "inside":
            return centre
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (sum(xs) / n, sum(ys) / n)


def polygons_overlap(first: list[tuple[float, float]], second: list[tuple[float, float]]) -> bool:
    """Interiors overlap (touching along a shared wall is allowed)."""
    for i in range(len(first)):
        a, b = first[i], first[(i + 1) % len(first)]
        for j in range(len(second)):
            if segments_cross(a, b, second[j], second[(j + 1) % len(second)]):
                return True
    if any(point_in_polygon(p, second) == "inside" for p in first) or any(point_in_polygon(p, first) == "inside" for p in second):
        return True
    return point_in_polygon(interior_point(first), second) == "inside" or point_in_polygon(interior_point(second), first) == "inside"


def edge(points: list[tuple[float, float]], index: int) -> tuple[tuple[float, float], tuple[float, float]]:
    return points[index], points[(index + 1) % len(points)]


def edge_point(points: list[tuple[float, float]], index: int, offset: float) -> tuple[float, float]:
    (x1, y1), (x2, y2) = edge(points, index)
    return (x1 + (x2 - x1) * offset, y1 + (y2 - y1) * offset)


def outward_normal(points: list[tuple[float, float]], index: int) -> tuple[float, float]:
    """Unit outward normal of edge ``index`` – for either orientation of the polygon (a clockwise room has its
    outside on the other side of each wall; corner indices are never reordered)."""
    (x1, y1), (x2, y2) = edge(points, index)
    length = math.hypot(x2 - x1, y2 - y1) or 1.0
    sign = -1.0 if signed_area(points) < 0 else 1.0
    return (sign * (y2 - y1) / length, -sign * (x2 - x1) / length)


def normal_bearing(normal: tuple[float, float], north_deg: float) -> float:
    """Compass bearing (0–360) a plan direction faces, given the plan's north offset."""
    return (math.degrees(math.atan2(normal[0], normal[1])) + north_deg) % 360.0


def edge_bearing(points: list[tuple[float, float]], index: int, north_deg: float) -> float:
    """Compass bearing the outside of wall ``index`` faces."""
    return normal_bearing(outward_normal(points, index), north_deg)


def shared_length(a1, a2, b1, b2, tol: float = WALL_TOLERANCE) -> float:
    """Length along which two wall segments lie on top of each other."""
    length = math.dist(a1, a2)
    if length < EPS:
        return 0.0
    ux, uy = (a2[0] - a1[0]) / length, (a2[1] - a1[1]) / length
    for p in (b1, b2):
        if abs((p[0] - a1[0]) * uy - (p[1] - a1[1]) * ux) > tol:
            return 0.0
    t1 = (b1[0] - a1[0]) * ux + (b1[1] - a1[1]) * uy
    t2 = (b2[0] - a1[0]) * ux + (b2[1] - a1[1]) * uy
    lo, hi = max(0.0, min(t1, t2)), min(length, max(t1, t2))
    return max(hi - lo, 0.0)


def neighbour_at(layout: dict[str, Any], room_id: str, point: tuple[float, float]) -> str | None:
    """The other room on the same floor whose wall contains ``point`` (None = exterior wall)."""
    rooms = {r["id"]: r for r in layout.get("rooms", [])}
    own = rooms.get(room_id)
    if own is None:
        return None
    for other in layout.get("rooms", []):
        if other["id"] == room_id or other.get("floor_id") != own.get("floor_id"):
            continue
        pts = [tuple(p) for p in other["polygon"]]
        for i in range(len(pts)):
            a, b = edge(pts, i)
            if _on_segment(a, b, point, WALL_TOLERANCE):
                return str(other["id"])
    return None


def opening_samples(points: list[tuple[float, float]], opening: dict[str, Any], count: int = 5) -> list[tuple[float, float]]:
    """Points along the whole span of an opening on its wall (width as drawn: stored, else min(0.9, 40 %))."""
    a, b = edge(points, int(opening["edge"]))
    length = math.dist(a, b) or 1.0
    width = _finite(opening.get("width_m")) or min(0.9, length * 0.4)
    half = min(max(width, 0.0), length) / length / 2.0
    offset = _finite(opening.get("offset"))
    offset = 0.5 if offset is None else offset
    lo, hi = max(offset - half, 0.0), min(offset + half, 1.0)
    return [edge_point(points, int(opening["edge"]), lo + (hi - lo) * k / (count - 1)) for k in range(count)]


def shared_wall_length(first: dict[str, Any], second: dict[str, Any]) -> float:
    """Longest stretch along which two rooms of the same floor share a wall (0 for another floor)."""
    if first.get("floor_id") != second.get("floor_id"):
        return 0.0
    a_pts, b_pts = [tuple(p) for p in first["polygon"]], [tuple(p) for p in second["polygon"]]
    return max((shared_length(*edge(a_pts, i), *edge(b_pts, j)) for i in range(len(a_pts)) for j in range(len(b_pts))), default=0.0)


def _geometry_issues(layout: dict[str, Any], rooms: dict[str, dict[str, Any]], valid_rooms: set[str]) -> list[dict[str, Any]]:
    """Hotfix 0.26.6.0: ways through a wall that the geometry does not carry (also after a room was moved).

    ``E_OPENING_INTERIOR`` (0.26.6.0 UI hotfix, blocks saving): an opening the editor placed as interior
    (``interior: true``) that does not lie on a wall shared with another room.

    ``W_OPENING_NOT_SHARED``: a passage whose span does not lie on a wall shared with another room (it counts
    as an outside opening). ``W_CONNECTION_NO_WALL``: a door or open passage between two rooms that share no
    wall of at least MIN_SHARED_WALL – the air paths keep it as a link, the house map never draws air through it.
    """
    issues: list[dict[str, Any]] = []
    for opening in layout["openings"]:
        room_id = _text(opening.get("room_id"))
        # an opening placed as interior that no longer lies on a shared wall is an error – never silently an outside door
        if opening.get("interior") is True and room_id in valid_rooms and isinstance(opening.get("edge"), int) \
                and 0 <= opening["edge"] < len(rooms[room_id]["polygon"]) and opening_neighbour(layout, room_id, opening) is None:
            issues.append(_issue("E_OPENING_INTERIOR", "opening", _text(opening.get("id"))))
            continue
        if opening.get("kind") == "passage" and room_id in valid_rooms and isinstance(opening.get("edge"), int) \
                and 0 <= opening["edge"] < len(rooms[room_id]["polygon"]) and opening_neighbour(layout, room_id, opening) is None:
            issues.append(_issue("W_OPENING_NOT_SHARED", "opening", _text(opening.get("id"))))
    for connection in layout["connections"]:
        a, b = rooms.get(_text(connection.get("a"))), rooms.get(_text(connection.get("b")))
        if connection.get("kind") in PHYSICAL_CONNECTIONS and a and b and a["id"] in valid_rooms and b["id"] in valid_rooms \
                and a["id"] != b["id"] and shared_wall_length(a, b) < MIN_SHARED_WALL:
            issues.append(_issue("W_CONNECTION_NO_WALL", "connection", _text(connection.get("id"))))
    return issues


def opening_neighbour(layout: dict[str, Any], room_id: str, opening: dict[str, Any]) -> str | None:
    """The room on the other side of an opening – only when its whole span lies on that room's wall.

    House map hotfix: a shared corner or a wall a few centimetres away is no shared wall. The editor uses
    exactly this rule (``openingTarget`` in freshairiq-house-trace.js) with the same tolerance.
    """
    rooms = {r["id"]: r for r in layout.get("rooms", [])}
    own = rooms.get(room_id)
    if own is None:
        return None
    samples = opening_samples([tuple(p) for p in own["polygon"]], opening)
    for other in layout.get("rooms", []):
        if other["id"] == room_id or other.get("floor_id") != own.get("floor_id"):
            continue
        pts = [tuple(p) for p in other["polygon"]]
        walls = [edge(pts, i) for i in range(len(pts))]
        if all(any(_on_segment(a, b, p, WALL_TOLERANCE) for a, b in walls) for p in samples):
            return str(other["id"])
    return None


# --------------------------------------------------------------------------- schema
def empty_layout() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "revision": 0, "building": {"north_deg": 0.0, "units": "schematic", "north_confirmed": False},
            "floors": [], "rooms": [], "openings": [], "connections": [], "shading": []}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()[: LIMITS["text"]]


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalise(raw: Any) -> dict[str, Any]:
    """Coerce a stored or submitted layout into schema v1 (shape only; see ``validate``)."""
    out = empty_layout()
    if not isinstance(raw, dict):
        return out
    out["revision"] = max(int(_finite(raw.get("revision")) or 0), 0)
    building = raw.get("building") if isinstance(raw.get("building"), dict) else {}
    north = _finite(building.get("north_deg"))
    out["building"] = {
        "north_deg": (north % 360.0) if north is not None else 0.0,
        "units": building.get("units") if building.get("units") in UNITS else "schematic",
        "north_confirmed": bool(building.get("north_confirmed")),
    }
    for key in ("floors", "rooms", "openings", "connections", "shading"):
        items = raw.get(key)
        out[key] = [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    for room in out["rooms"]:
        polygon = room.get("polygon")
        room["polygon"] = [[_finite(p[0]), _finite(p[1])] for p in polygon if isinstance(p, (list, tuple)) and len(p) == 2] if isinstance(polygon, list) else []
        room["id"], room["room_key"], room["floor_id"] = _text(room.get("id")), _text(room.get("room_key")), _text(room.get("floor_id"))
        if room.get("provenance") not in PROVENANCE:
            room["provenance"] = "user"
        # 0.26.6.0(2): walls whose length the user locked (edge indices); 0.26.6.0(10): corners whose angle the user
        # locked (corner indices) – only valid indices, each once; an empty list is dropped
        for key in ("locked_walls", "locked_corners"):
            if key in room:
                locked = room.get(key) if isinstance(room.get(key), list) else []
                room[key] = sorted({i for i in locked if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(room["polygon"])})
                if not room[key]:
                    room.pop(key)
    for opening in out["openings"]:
        opening["contacts"] = [_text(c) for c in opening.get("contacts", []) if _text(c)][: LIMITS["contacts"]] if isinstance(opening.get("contacts"), list) else []
        if opening.get("kind") not in OPENING_KINDS:
            opening["kind"] = "window"
        if opening.get("mechanics") not in OPENING_MECHANICS:
            opening["mechanics"] = "unknown"
        # 0.26.6.0 UI hotfix: an interior door or passage placed by the editor between two rooms (True only)
        if "interior" in opening and opening.get("interior") is not True:
            opening.pop("interior")
        for key, allowed in (("door_hinge", DOOR_HINGES), ("door_swing", DOOR_SWINGS)):
            if key in opening and opening.get(key) not in allowed:
                opening.pop(key)  # an unknown value is dropped – the door is drawn as before
    for floor in out["floors"]:
        floor["id"], floor["name"], floor["level_key"] = _text(floor.get("id")), _text(floor.get("name")), _text(floor.get("level_key"))
    return out


def migrate(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Stored layout → schema v1. Unknown newer schemas are refused, never guessed."""
    if raw is None:
        return empty_layout(), None
    if not isinstance(raw, dict):
        return None, "E_SCHEMA"
    version = raw.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        return None, "E_SCHEMA_VERSION"
    return normalise(raw), None


def ccw(points: list[list[float]]) -> list[list[float]]:
    """The same polygon in counter-clockwise order."""
    pts = [tuple(p) for p in points]
    return [list(p) for p in (pts if signed_area(pts) >= 0 else list(reversed(pts)))]


def _issue(code: str, kind: str, ident: str, index: int | None = None) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "object": kind, "id": ident}
    if index is not None:
        issue["index"] = index
    return issue


def _validate_polygon(room: dict[str, Any]) -> list[dict[str, Any]]:
    rid, polygon = room["id"], room.get("polygon") or []
    if len(polygon) < 3:
        return [_issue("E_POLY_POINTS", "room", rid)]
    if len(polygon) > LIMITS["vertices"]:
        return [_issue("E_LIMIT_VERTICES", "room", rid)]
    if any(x is None or y is None or abs(x) > LIMITS["coordinate"] or abs(y) > LIMITS["coordinate"] for x, y in polygon):
        return [_issue("E_POLY_NONFINITE", "room", rid)]
    pts = [tuple(p) for p in polygon]
    for i in range(len(pts)):
        if math.dist(*edge(pts, i)) < WALL_TOLERANCE:
            return [_issue("E_POLY_DEGENERATE", "room", rid, i)]
    if self_intersects(pts):
        return [_issue("E_POLY_SELF_INTERSECT", "room", rid)]
    if abs(signed_area(pts)) < WALL_TOLERANCE:
        return [_issue("E_POLY_AREA", "room", rid)]
    return []


def _validate_ids(layout: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key, limit in (("floors", "floors"), ("rooms", "rooms"), ("openings", "openings"), ("connections", "connections")):
        if len(layout[key]) > LIMITS[limit]:
            issues.append(_issue(f"E_LIMIT_{key.upper()}", key[:-1], ""))
        seen: set[str] = set()
        for item in layout[key]:
            ident = _text(item.get("id"))
            if not ident or ident in seen:
                issues.append(_issue("E_ID", key[:-1], ident))
            seen.add(ident)
    return issues


def _validate_openings(layout: dict[str, Any], rooms: dict[str, dict[str, Any]], valid_rooms: set[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for opening in layout["openings"]:
        oid, room = _text(opening.get("id")), rooms.get(_text(opening.get("room_id")))
        if room is None:
            issues.append(_issue("E_OPENING_ROOM", "opening", oid))
            continue
        if room["id"] not in valid_rooms:
            continue
        index, offset, width = opening.get("edge"), _finite(opening.get("offset")), _finite(opening.get("width_m"))
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(room["polygon"]):
            issues.append(_issue("E_OPENING_EDGE", "opening", oid))
            continue
        length = math.dist(*edge([tuple(p) for p in room["polygon"]], index))
        if offset is None or not 0.0 <= offset <= 1.0:
            issues.append(_issue("E_OPENING_OFFSET", "opening", oid))
        elif width is not None and (width <= 0 or width > length + WALL_TOLERANCE):
            issues.append(_issue("E_OPENING_WIDTH", "opening", oid))
    return issues


def validate(layout: dict[str, Any], room_keys: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Errors (``E_*``) and warnings (``W_*``) with the object they belong to."""
    issues = _validate_ids(layout)
    floors = {f["id"] for f in layout["floors"]}
    rooms = {r["id"]: r for r in layout["rooms"]}
    known = set(room_keys) if room_keys is not None else None
    drawn: dict[str, str] = {}
    valid_rooms: set[str] = set()
    for room in layout["rooms"]:
        if room.get("floor_id") not in floors:
            issues.append(_issue("E_FLOOR_UNKNOWN", "room", room["id"]))
        if room.get("room_key") in drawn:
            issues.append(_issue("E_ROOM_DUPLICATE", "room", room["id"]))
        drawn[room.get("room_key", "")] = room["id"]
        if known is not None and room.get("room_key") not in known:
            issues.append(_issue("W_ROOM_ORPHANED", "room", room["id"]))
        polygon_issues = _validate_polygon(room)
        issues.extend(polygon_issues)
        if not polygon_issues:
            valid_rooms.add(room["id"])
    by_floor: dict[str, list[dict[str, Any]]] = {}
    for room in layout["rooms"]:
        if room["id"] in valid_rooms:
            by_floor.setdefault(room.get("floor_id", ""), []).append(room)
    for members in by_floor.values():
        for i, first in enumerate(members):
            for second in members[i + 1:]:
                if polygons_overlap([tuple(p) for p in first["polygon"]], [tuple(p) for p in second["polygon"]]):
                    issues.append(_issue("E_ROOM_OVERLAP", "room", second["id"]))
    issues.extend(_validate_openings(layout, rooms, valid_rooms))
    for connection in layout["connections"]:
        ends = (_text(connection.get("a")), _text(connection.get("b")))
        if any(end != OUTSIDE and end not in rooms for end in ends) or ends[0] == ends[1] or connection.get("kind") not in CONNECTION_KINDS:
            issues.append(_issue("E_CONNECTION", "connection", _text(connection.get("id"))))
    issues.extend(_geometry_issues(layout, rooms, valid_rooms))
    return issues


def errors(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in issues if str(i.get("code", "")).startswith("E_")]


def reconcile(layout: dict[str, Any], room_keys: Iterable[str]) -> dict[str, list[str]]:
    """Rooms configured but not drawn, and drawn rooms whose FreshAirIQ room no longer exists."""
    keys = list(room_keys)
    drawn = {r.get("room_key") for r in layout.get("rooms", [])}
    return {
        "missing": [k for k in keys if k not in drawn],
        "orphaned": sorted(str(r["id"]) for r in layout.get("rooms", []) if r.get("room_key") not in set(keys)),
    }
