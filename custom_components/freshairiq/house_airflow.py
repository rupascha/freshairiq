"""Air paths for the house map: a graph hypothesis with explicit evidence (pure).

Nodes are drawn rooms plus ``outside``; edges are openings (with their live
contact state) and configured connections. The result explains *plausible*
paths – it is never used by the ventilation decision, the learning or the
forecast, and it never claims air speeds or flow rates.

Model levels (strictly increasing evidence):

* ``topology_only`` – known connections and contact states only, no direction;
* ``wind_heuristic`` – usable wind and facade orientation: directions from
  windward to leeward openings, pressure only qualitative;
* ``opening_aware`` – additionally every active exterior opening has a known
  opening class (proven tilt/open or a configured passage).

``calibrated`` is deliberately never produced: FreshAirIQ has no documented
calibration of per-path flows.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from .house_layout import OUTSIDE, edge_bearing, opening_neighbour
from .house_wind import facade_exposure

ORIENTATION_DEG = {"n": 0.0, "ne": 45.0, "e": 90.0, "se": 135.0, "s": 180.0, "sw": 225.0, "w": 270.0, "nw": 315.0}
OPEN_STATES = ("open", "tilted", "open_unspecified")
INLET_PRESSURE = 0.3
MAX_PATHS = 24


def contact_state(contacts: list[str], live: dict[str, Any]) -> tuple[str, bool]:
    """Combined state of an opening's contacts and whether its opening is still unconfirmed (delay)."""
    states = [live.get(c) if isinstance(live.get(c), dict) else None for c in contacts]
    known = [s for s in states if s is not None]
    if not known:
        return "unknown", False
    open_ones = [s for s in known if s.get("state") in OPEN_STATES]
    if open_ones:
        pending = all(bool(s.get("pending")) for s in open_ones)
        for wanted in ("open", "open_unspecified", "tilted"):
            if any(s.get("state") == wanted for s in open_ones):
                return wanted, pending
    if len(known) < len(states) or any(s.get("state") not in ("closed",) for s in known):
        return "unknown", False
    return "closed", False


def live_contact(raw_state: str, *, three_state: bool, stable_mode: str | None, room_active: bool, delay_s: float,
                 open_seconds: float | None = None) -> dict[str, Any]:
    """Map state for one contact of one room.

    ``raw_state`` is the normalised HA opening state (open/tilted/closed/unknown).
    A binary contact never claims "fully open": its open state is
    ``open_unspecified``. Proven three-state contacts use FreshAirIQ's debounced
    stable mode. The physical state, the configured delay and the room's session
    are kept apart: an open contact is ``pending`` only while its own opening
    delay is still running (open for less than ``delay_s`` seconds) and no
    session runs – an open window without a session for other reasons (no
    valid climate data, monitoring only, unsuitable weather) is simply open.
    """
    if three_state:
        state = stable_mode if stable_mode in ("open", "tilted", "closed") else "unknown"
    elif raw_state in ("open", "tilted"):
        state = "open_unspecified"
    elif raw_state == "closed":
        state = "closed"
    else:
        state = "unknown"
    delay_running = open_seconds is not None and open_seconds < delay_s
    return {"state": state, "pending": state in OPEN_STATES and not room_active and delay_running, "three_state": three_state,
            "delay_s": delay_s, "open_s": round(open_seconds) if open_seconds is not None and state in OPEN_STATES else None}


def _opening_state(opening: dict[str, Any], live: dict[str, Any]) -> tuple[str, bool]:
    if opening.get("kind") == "passage":
        return "open", False
    if not opening.get("contacts"):
        return "no_sensor", False
    return contact_state(opening["contacts"], live)


def _size_class(opening: dict[str, Any], state: str) -> str:
    if opening.get("kind") == "passage" or state == "open":
        return "large"
    return "small" if state == "tilted" else "unknown"


def _facade(layout: dict[str, Any], room: dict[str, Any], opening: dict[str, Any], orientations: dict[str, Any]) -> tuple[float | None, str]:
    building = layout.get("building", {})
    pts = [tuple(p) for p in room["polygon"]]
    if building.get("north_confirmed"):
        return round(edge_bearing(pts, int(opening["edge"]), float(building.get("north_deg", 0.0))), 1), "geometry"
    for contact in opening.get("contacts", []):
        if str(orientations.get(contact) or "") in ORIENTATION_DEG:
            return ORIENTATION_DEG[str(orientations[contact])], "configured_orientation"
    return None, "none"


def sensor_states(rooms_live: dict[str, Any], *prefer: Any, field: str = "contacts") -> dict[str, Any]:
    """Live state of every contact by its entity – wherever the setup uses it.

    Hotfix after review (F01): where a window is drawn (its room), which sensor it has and which room it airs are
    independent: a guest WC window drawn in the WC whose contact is set up only for the hall still shows the hall's
    live state of that sensor (``field="orientations"``: its configured facade). The rooms named in ``prefer`` (e.g.
    the room the opening is drawn in) win, then the other rooms in key order – the decision of every room is not
    touched."""
    merged: dict[str, Any] = {}
    order = [k for k in prefer if k in rooms_live] + sorted((k for k in rooms_live if k not in prefer), key=str)
    for key in order:
        room = rooms_live.get(key)
        values = room.get(field) if isinstance(room, dict) and isinstance(room.get(field), dict) else {}
        for contact, value in values.items():
            merged.setdefault(contact, value)
    return merged


def inside_contacts(rooms_live: dict[str, Any]) -> set[str]:
    """Contacts configured as inside doors in any room (contact_sides.py)."""
    return {str(c) for room in rooms_live.values() if isinstance(room, dict) for c in (room.get("inside_contacts") or [])}


def geometry_conflict(opening: dict[str, Any], target: str, inside: set[str]) -> str | None:
    """An opening drawn on an outside wall that cannot exchange air with the outside (0.26.7.0).

    A doorless passage is always open and only exists between rooms; a contact configured as an
    inside door leads into another room. Drawn on an outside wall either would invent a permanent
    or false outside air path, so the map shows the conflict instead of the path.
    """
    if target != OUTSIDE:
        return None
    if opening.get("kind") == "passage":
        return "passage_on_outside_wall"
    contacts = [str(c) for c in opening.get("contacts") or []]
    if contacts and all(c in inside for c in contacts):
        return "inside_door_on_outside_wall"
    return None


def _openings(layout: dict[str, Any], rooms_live: dict[str, Any], wind: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rooms = {r["id"]: r for r in layout.get("rooms", [])}
    inside = inside_contacts(rooms_live)
    out: dict[str, dict[str, Any]] = {}
    for opening in layout.get("openings", []):
        room = rooms.get(opening.get("room_id"))
        if room is None:
            continue
        # the whole span must lie on the other room's wall (a shared corner is no shared wall)
        target = opening_neighbour(layout, room["id"], opening) or OUTSIDE
        # F06: on an outside wall only outside contacts confirm the opening – an inside door's contact never opens it
        counted = {**opening, "contacts": [c for c in opening.get("contacts") or [] if str(c) not in inside]} if target == OUTSIDE else opening
        state, pending = _opening_state(counted, sensor_states(rooms_live, room.get("room_key")))
        conflict = geometry_conflict(opening, target, inside)
        if conflict:
            state, pending = "geometry_conflict", False
        facade_deg, facade_basis = _facade(layout, room, opening, sensor_states(rooms_live, room.get("room_key"), field="orientations")) if target == OUTSIDE else (None, "interior")
        out[str(opening["id"])] = {
            "room": room["id"], "target": target, "state": state, "pending": pending,
            "size": _size_class(opening, state), "facade_deg": facade_deg, "facade_basis": facade_basis,
            **(facade_exposure(facade_deg, wind) if target == OUTSIDE else {"exposure": "interior", "angle_deg": None, "pressure": None}),
            **({"conflict": conflict} if conflict else {}),
        }
    return out


def _edges(layout: dict[str, Any], openings: dict[str, dict[str, Any]], rooms_live: dict[str, Any]) -> list[dict[str, Any]]:
    keys = {r["id"]: r.get("room_key") for r in layout.get("rooms", [])}
    edges = []
    for oid, item in openings.items():
        if item["target"] != OUTSIDE:
            active = item["state"] in OPEN_STATES and not item["pending"]
            edges.append({"id": oid, "a": item["room"], "b": item["target"], "state": "open" if active else item["state"], "confirmed": True})
    for connection in layout.get("connections", []):
        kind = connection.get("kind")
        state = "open" if kind == "open_passage" else "unknown"
        if kind != "open_passage" and connection.get("contacts"):
            live = sensor_states(rooms_live, keys.get(connection.get("a")), keys.get(connection.get("b")))
            combined, pending = contact_state(list(connection["contacts"]), live)
            state = "open" if combined in OPEN_STATES and not pending else combined
        edges.append({"id": str(connection.get("id")), "a": connection.get("a"), "b": connection.get("b"), "state": state,
                      "confirmed": bool(connection.get("confirmed"))})
    return edges


def _components(room_ids: list[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    adjacency: dict[str, set[str]] = {r: set() for r in room_ids}
    for e in edges:
        if e["state"] == "open" and e["a"] in adjacency and e["b"] in adjacency:
            adjacency[e["a"]].add(e["b"]); adjacency[e["b"]].add(e["a"])
    component: dict[str, int] = {}
    for start in room_ids:
        if start in component:
            continue
        queue = deque([start]); component[start] = len(set(component.values()))
        while queue:
            node = queue.popleft()
            for other in adjacency[node]:
                if other not in component:
                    component[other] = component[start]; queue.append(other)
    return component


def _route(start: str, goal: str, edges: list[dict[str, Any]]) -> tuple[list[str], list[str]] | None:
    """Shortest room route over open edges (rooms, edge ids)."""
    previous: dict[str, tuple[str, str] | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            rooms, via = [node], []
            while previous[node] is not None:
                node, edge_id = previous[node]  # type: ignore[misc]
                rooms.append(node); via.append(edge_id)
            return list(reversed(rooms)), list(reversed(via))
        for e in edges:
            if e["state"] != "open" or OUTSIDE in (e["a"], e["b"]):
                continue
            for a, b in ((e["a"], e["b"]), (e["b"], e["a"])):
                if a == node and b not in previous:
                    previous[b] = (node, e["id"]); queue.append(b)
    return None


def _level(wind: dict[str, Any], exterior: list[dict[str, Any]]) -> str:
    if not wind.get("available") or not exterior or any(o["facade_deg"] is None for o in exterior):
        return "topology_only"
    return "opening_aware" if all(o["size"] != "unknown" for o in exterior) else "wind_heuristic"


def _component_paths(level: str, members: set[str], exterior: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unknown_edges = sorted(e["id"] for e in edges if e["state"] != "open" and (e["a"] in members or e["b"] in members))
    assumptions = ["no_obstacles", "no_measured_flow"]
    paths: list[dict[str, Any]] = []
    if level != "topology_only":
        inlets = [(oid, o) for oid, o in exterior.items() if (o["pressure"] or 0) >= INLET_PRESSURE]
        outlets = [(oid, o) for oid, o in exterior.items() if (o["pressure"] or 0) <= -INLET_PRESSURE]
        for in_id, inlet in inlets:
            for out_id, outlet in outlets:
                rooms, via = _route(inlet["room"], outlet["room"], edges) or ([], [])  # same component: always reachable
                paths.append({"kind": "cross", "direction": "directed", "from": in_id, "to": out_id, "rooms": rooms, "via": via,
                              "confidence": "medium" if level == "opening_aware" else "low",
                              "basis": ["wind", "facade", "opening_state"] + (["opening_class"] if level == "opening_aware" else []),
                              "assumptions": assumptions, "unknowns": unknown_edges})
    if paths:
        return paths
    if len(exterior) >= 2:
        ids = sorted(exterior)
        rooms = sorted({o["room"] for o in exterior.values()})
        return [{"kind": "cross_possible", "direction": "bidirectional", "from": ids[0], "to": ids[-1], "rooms": rooms, "via": [],
                 "confidence": "low", "basis": ["opening_state", "topology"], "assumptions": assumptions,
                 "unknowns": unknown_edges + (["wind"] if level == "topology_only" else [])}]
    if len(exterior) == 1:
        oid, item = next(iter(exterior.items()))
        return [{"kind": "single_sided", "direction": "bidirectional", "from": oid, "to": oid, "rooms": [item["room"]], "via": [],
                 "confidence": "low", "basis": ["opening_state"], "assumptions": assumptions, "unknowns": unknown_edges}]
    return []


def fan_entities(value: Any) -> list[str]:
    """Configured fan/stage entities of a room (scalar or list, as in the room setup), unique and in order."""
    if isinstance(value, str):
        return [value] if value else []
    return list(dict.fromkeys(str(v) for v in value if v)) if isinstance(value, (list, tuple, set)) else []


def _exhaust_paths(layout: dict[str, Any], rooms_live: dict[str, Any], component: dict[str, int],
                   exterior: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    devices: dict[str, dict[str, Any]] = {}
    paths: list[dict[str, Any]] = []
    for room in layout.get("rooms", []):
        live = rooms_live.get(room.get("room_key")) if isinstance(rooms_live.get(room.get("room_key")), dict) else {}
        fans = fan_entities(live.get("exhaust_fan"))
        if not fans:
            continue
        states = live.get("exhaust_fans") if isinstance(live.get("exhaust_fans"), dict) else {}
        for fan in fans:  # one device per entity: the same fan in several rooms is one device, whatever the list order
            device = devices.setdefault(fan, {"fan": fan, "rooms": [], "active": False})
            if room["id"] not in device["rooms"]:
                device["rooms"].append(room["id"])
            device["active"] = device["active"] or bool(states[fan] if fan in states else live.get("mechanical_exhaust_active"))
        if not live.get("mechanical_exhaust_active"):
            continue
        supply = [(oid, o) for oid, o in exterior.items() if component.get(o["room"]) == component.get(room["id"])]
        for oid, item in supply:
            route = _route(item["room"], room["id"], edges) or ([room["id"]], [])
            paths.append({"kind": "exhaust", "direction": "directed", "from": oid, "to": room["id"], "rooms": route[0], "via": route[1],
                          "confidence": "low", "basis": ["fan_on", "opening_state"], "assumptions": ["fan_underpressure", "no_measured_flow"],
                          "unknowns": ["infiltration"]})
        if not supply:
            paths.append({"kind": "exhaust_replacement_unconfirmed", "direction": "unknown", "from": None, "to": room["id"],
                          "rooms": [room["id"]], "via": [], "confidence": "low", "basis": ["fan_on"],
                          "assumptions": ["fan_underpressure", "reference_is_not_airflow"], "unknowns": ["replacement_air_path"]})
    return paths, sorted(devices.values(), key=lambda d: d["fan"])


def air_paths(layout: dict[str, Any], rooms_live: dict[str, Any], wind: dict[str, Any]) -> dict[str, Any]:
    """Opening states, the model level and plausible paths for a validated layout."""
    openings = _openings(layout, rooms_live, wind)
    edges = _edges(layout, openings, rooms_live)
    room_ids = [r["id"] for r in layout.get("rooms", [])]
    component = _components(room_ids, edges)
    exterior_all = {oid: o for oid, o in openings.items() if o["target"] == OUTSIDE and o["state"] in OPEN_STATES and not o["pending"]}
    level = _level(wind, list(exterior_all.values()))
    paths: list[dict[str, Any]] = []
    for comp in sorted(set(component.values())):
        members = {r for r, c in component.items() if c == comp}
        exterior = {oid: o for oid, o in exterior_all.items() if o["room"] in members}
        paths.extend(_component_paths(level, members, exterior, edges))
    exhaust, devices = _exhaust_paths(layout, rooms_live, component, exterior_all, edges)
    paths.extend(exhaust)
    return {
        "model_level": level,
        "openings": openings,
        "edges": edges,
        "paths": paths[:MAX_PATHS],
        "devices": devices,
        "pending_openings": sorted(oid for oid, o in openings.items() if o["pending"]),
    }
