"""Floor plan editor order: interior doors in the first proposal and confirmed partition walls.

Befund 5: an inside door configured in one room with its connected room is a door between those rooms – the first
proposal never puts it into an outside wall. Without a shared wall it is left for placing in the editor.
Partition walls ("take as shared wall"): two rooms a wall's thickness apart keep their inner sizes; a door on one
side links both rooms, the wall alone makes no way for air, and stored plans without it load as before.
"""
from __future__ import annotations

import json

from custom_components.freshairiq.house_airflow import air_paths
from custom_components.freshairiq.house_autolayout import propose
from custom_components.freshairiq.house_layout import (
    MAX_PARTITION_M,
    migrate,
    normalise,
    opening_neighbour,
    partition_tolerance,
    shared_wall_length,
    validate,
)

DOOR = "binary_sensor.bad_tuer"


def _room(key, floor="eg", **extra):
    return {"key": key, "name": key.title(), "floor": floor, "length": 4.0, "width": 3.0, "height": 2.5, **extra}


def _inside(connected=None):
    extra = {"contacts": [DOOR], "contact_sides": {DOOR: "inside"}}
    if connected:
        extra["contact_connected_rooms"] = {DOOR: connected}
    return extra


def _exterior_openings_with(layout, contact):
    return [o for o in layout["openings"] if contact in o.get("contacts", []) and opening_neighbour(layout, o["room_id"], o) is None]


def test_inside_door_with_its_connected_room_is_a_door_between_the_rooms_never_in_an_outside_wall():
    layout = normalise(propose([_room("bad", **_inside("flur")), _room("flur"), _room("kueche")], ["eg"])["layout"])
    assert _exterior_openings_with(layout, DOOR) == []
    doors = [o for o in layout["openings"] if DOOR in o["contacts"]]
    links = [c for c in layout["connections"] if DOOR in c.get("contacts", [])]
    assert doors or links
    for door in doors:
        assert door["kind"] == "door"
        assert {door["room_id"], opening_neighbour(layout, door["room_id"], door)} == {"r_bad", "r_flur"}
    assert not [i for i in validate(layout, ["bad", "flur", "kueche"]) if i["code"].startswith("E_")]


def test_inside_door_without_a_shared_wall_is_offered_for_placing_not_drawn_outside():
    # the connected room is on another floor: no wall to share – a door connection carries the contact
    layout = propose([_room("bad", **_inside("flur")), _room("flur", floor="og")], ["eg", "og"])["layout"]
    assert _exterior_openings_with(layout, DOOR) == []
    assert not [o for o in layout["openings"] if DOOR in o["contacts"]]
    assert [c["kind"] for c in layout["connections"] if DOOR in c.get("contacts", [])] == ["door"]
    # an inside door without a known room behind it (or naming a room that is not set up) is not drawn at all
    for extra in (_inside(), _inside("garage")):
        layout = propose([_room("bad", **extra), _room("flur")], ["eg"])["layout"]
        assert not [o for o in layout["openings"] if DOOR in o["contacts"]]


def test_outside_contacts_and_shared_door_contacts_keep_their_proposal():
    rooms = [_room("bad", contacts=["binary_sensor.bad_fenster"]), _room("flur")]
    layout = normalise(propose(rooms, ["eg"])["layout"])
    window = next(o for o in layout["openings"] if o["contacts"] == ["binary_sensor.bad_fenster"])
    assert window["kind"] == "window" and opening_neighbour(layout, window["room_id"], window) is None
    # the same inside contact in two rooms joins them, also without a named room; a configured connection adds to it
    shared = [_room("bad", **_inside()), _room("flur", contacts=[DOOR], contact_sides={DOOR: "inside"}, contact_connected_rooms={DOOR: "bad"})]
    layout = normalise(propose(shared, ["eg"])["layout"])
    assert _exterior_openings_with(layout, DOOR) == []
    assert [o["contacts"] for o in layout["openings"] if DOOR in o["contacts"]] in ([[DOOR]], [])


def _partition_plan(thickness=None):
    flur = {"id": "r_flur", "room_key": "flur", "floor_id": "f", "polygon": [[0, 0], [3, 0], [3, 4], [0, 4]]}
    wohnen = {"id": "r_wohnen", "room_key": "wohnen", "floor_id": "f", "polygon": [[3.14, 0], [6, 0], [6, 4], [3.14, 4]]}
    if thickness is not None:
        flur["partitions"] = [{"room": "r_wohnen", "thickness_m": thickness}]
        wohnen["partitions"] = [{"room": "r_flur", "thickness_m": thickness}]
    door = {"id": "d1", "room_id": "r_flur", "edge": 1, "offset": 0.5, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": [DOOR]}
    return normalise({"schema_version": 1, "floors": [{"id": "f", "name": "EG", "level_key": "eg"}], "rooms": [flur, wohnen], "openings": [door]})


def test_a_confirmed_partition_wall_links_a_door_on_it_and_makes_no_air_path_alone():
    apart, wall = _partition_plan(), _partition_plan(0.14)
    door = wall["openings"][0]
    assert opening_neighbour(apart, "r_flur", door) is None                      # 14 cm apart: an outside door before
    assert opening_neighbour(wall, "r_flur", door) == "r_wohnen"                 # confirmed wall: the door links both rooms
    assert shared_wall_length(*wall["rooms"]) == 4.0 and shared_wall_length(*apart["rooms"]) == 0.0
    assert [r["polygon"] for r in wall["rooms"]] == [r["polygon"] for r in apart["rooms"]]   # inner sizes kept
    live = {"flur": {"contacts": {DOOR: {"state": "open", "pending": False}}, "inside_contacts": [DOOR]}}
    paths = air_paths(wall, live, {"available": False})
    assert paths["openings"]["d1"]["target"] == "r_wohnen"
    assert [(e["a"], e["b"]) for e in paths["edges"]] == [("r_flur", "r_wohnen")]
    # the wall without a door: no edge between the rooms, nothing in an outside wall
    no_door = dict(wall, openings=[])
    assert air_paths(no_door, {}, {"available": False})["edges"] == []
    interior = dict(wall, openings=[dict(door, interior=True)])
    assert not [i for i in validate(interior, ["flur", "wohnen"]) if i["code"] == "E_OPENING_INTERIOR"]
    assert [i["code"] for i in validate(dict(apart, openings=[dict(door, interior=True)]), ["flur", "wohnen"]) if i["code"] == "E_OPENING_INTERIOR"] == ["E_OPENING_INTERIOR"]


def test_partition_values_are_cleaned_and_old_plans_load_unchanged():
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    b = {"id": "r_b", "room_key": "b", "floor_id": "f", "polygon": [[1.2, 0], [2, 0], [2, 1], [1.2, 1]]}
    room = {"id": "r_a", "room_key": "a", "floor_id": "f", "polygon": square, "partitions": [
        {"room": "r_b", "thickness_m": 0.123456, "wall": 1, "other_wall": 3}, {"room": "r_b", "thickness_m": 0.2, "wall": 1, "other_wall": 3},
        {"room": "r_b", "thickness_m": 0.2, "wall": 9, "other_wall": 3}, {"room": "r_b", "thickness_m": 0.2, "wall": True, "other_wall": 3},
        {"room": "r_a", "thickness_m": 0.1}, {"room": "r_c", "thickness_m": MAX_PARTITION_M + 0.01}, {"room": "r_d", "thickness_m": 0},
        {"room": "", "thickness_m": 0.1}, {"room": "r_x", "thickness_m": 0.1}, {"thickness_m": "x"}, "junk"]}
    other_floor = dict(b, id="r_o", floor_id="g")
    out = normalise({"rooms": [room, b, other_floor, dict(room, id="r_z", partitions="junk"), dict(room, id="r_y", partitions=[{"room": "r_a", "thickness_m": -1}]),
                               dict(room, id="r_w", partitions=[{"room": "r_o", "thickness_m": 0.2, "wall": 1, "other_wall": 3}])]})
    # the last valid entry per pair of walls; a wall index the room does not have or a boolean is no wall – the
    # 20 cm entry with walls 9 / True is then a stored pair without walls: one wall pair faces at 20 cm, so it is taken
    assert out["rooms"][0]["partitions"] == [{"room": "r_b", "thickness_m": 0.2, "wall": 1, "other_wall": 3}]
    assert all("partitions" not in r for r in out["rooms"][2:])
    stored = {"schema_version": 1, "rooms": [{"id": "r_a", "room_key": "a", "floor_id": "f", "polygon": square}]}
    layout, code = migrate(stored)
    assert code is None and "partitions" not in layout["rooms"][0]
    # a stored pair without walls and a broken polygon: nothing to measure, the confirmation stays open
    broken = normalise({"rooms": [dict(room, polygon=[[0, 0], [1, "x"], [1, 1]], partitions=[{"room": "r_b", "thickness_m": 0.2}]), b]})
    assert "partitions" not in broken["rooms"][0]
    a, c = {"id": "r_a"}, {"id": "r_b", "partitions": ["junk", {"room": "r_a", "thickness_m": "x", "wall": 0, "other_wall": 2},
                                                   {"room": "r_a", "thickness_m": 0.2, "wall": 0, "other_wall": 2}]}
    assert partition_tolerance(a, c, 2, 0) == partition_tolerance(c, a, 0, 2) == 0.2 + 0.05
    assert partition_tolerance(a, c, 1, 0) == partition_tolerance(a, c, 2, 1) == 0.05          # only the confirmed walls
    assert partition_tolerance(a, {"id": "r_b", "partitions": [{"room": "r_a", "thickness_m": 0.9, "wall": 0, "other_wall": 2}]}, 2, 0) == 0.05


# U-shaped room around a neighbour: 20 cm to its left, 18 cm to its right; a door in the left arm
U_ROOM = [[0, 0], [6, 0], [6, 5], [4.5, 5], [4.5, 2], [1.5, 2], [1.5, 5], [0, 5]]
U_MIDDLE = [[1.7, 2.6], [4.32, 2.6], [4.32, 7], [1.7, 7]]


def _u_plan(partitions=None, middle=U_MIDDLE):
    u = {"id": "r_u", "room_key": "u", "floor_id": "f", "polygon": U_ROOM}
    m = {"id": "r_m", "room_key": "m", "floor_id": "f", "polygon": middle}
    if partitions is not None:
        u["partitions"], m["partitions"] = partitions
    door = {"id": "d_left", "room_id": "r_u", "edge": 5, "offset": 0.7, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": [DOOR]}
    right = {"id": "d_right", "room_id": "r_u", "edge": 3, "offset": 0.3, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": []}
    return normalise({"schema_version": 1, "floors": [{"id": "f", "name": "EG", "level_key": "eg"}], "rooms": [u, m], "openings": [door, right]})


def test_a_partition_confirmed_on_one_wall_of_a_u_shaped_room_does_not_reach_its_other_arm():
    from custom_components.freshairiq.house_layout import facing_walls

    assert sorted((i, j, round(g, 2)) for i, j, g in facing_walls(_u_plan()["rooms"][0], _u_plan()["rooms"][1])) == [(3, 1, 0.18), (5, 3, 0.2)]
    assert facing_walls({"polygon": [[1.5, 2.6], [1.6, 2.6], [1.6, 2.7], [1.5, 2.7]]}, {"polygon": U_MIDDLE}) == []   # walls too short to share
    confirmed = ([{"room": "r_m", "thickness_m": 0.18, "wall": 3, "other_wall": 1}], [{"room": "r_u", "thickness_m": 0.18, "wall": 1, "other_wall": 3}])
    plan = _u_plan(confirmed)
    left, right = plan["openings"]
    assert opening_neighbour(plan, "r_u", right) == "r_m"            # the confirmed right wall links its door
    assert opening_neighbour(plan, "r_u", left) is None              # the left door still leads outside (20 cm, not confirmed)
    paths = air_paths(plan, {"u": {"contacts": {DOOR: {"state": "open", "pending": False}}}}, {"available": False})
    assert paths["openings"]["d_left"]["target"] == "outside" and paths["openings"]["d_right"]["target"] == "r_m"
    # saved and loaded again: the walls stay as confirmed
    layout, code = migrate(json.loads(json.dumps(plan)))
    assert code is None and layout["rooms"][0]["partitions"] == confirmed[0] and layout["rooms"][1]["partitions"] == confirmed[1]
    assert opening_neighbour(layout, "r_u", layout["openings"][0]) is None


def test_a_stored_partition_without_walls_is_taken_only_where_one_wall_pair_fits():
    one = _u_plan(([{"room": "r_m", "thickness_m": 0.18}], [{"room": "r_u", "thickness_m": 0.18}]))
    assert one["rooms"][0]["partitions"] == [{"room": "r_m", "thickness_m": 0.18, "wall": 3, "other_wall": 1}]
    assert one["rooms"][1]["partitions"] == [{"room": "r_u", "thickness_m": 0.18, "wall": 1, "other_wall": 3}]
    # 20 cm to both arms: two candidates – left for the editor to confirm; a thickness no wall pair has: the same
    even = [[1.7, 2.6], [4.3, 2.6], [4.3, 7], [1.7, 7]]
    for thickness, middle in ((0.2, even), (0.19, U_MIDDLE)):
        open_ = _u_plan(([{"room": "r_m", "thickness_m": thickness}], [{"room": "r_u", "thickness_m": thickness}]), middle)
        assert all("partitions" not in r for r in open_["rooms"])
        assert opening_neighbour(open_, "r_u", open_["openings"][1]) is None


def test_rooms_overlapping_flush_along_one_wall_are_an_overlap_touching_is_not():
    from custom_components.freshairiq.house_layout import polygons_overlap

    low, high = [[0, 0], [4, 0], [4, 4], [0, 4]], [[0, 3.7], [4, 3.7], [4, 7.7], [0, 7.7]]
    assert polygons_overlap(low, high) and polygons_overlap(high, low)
    assert polygons_overlap(low, list(reversed(high)))                                      # either corner order
    assert not polygons_overlap(low, [[0, 4], [4, 4], [4, 8], [0, 8]])                       # a shared wall
    assert not polygons_overlap(low, [[4, 4], [8, 4], [8, 8], [4, 8]])                       # a shared corner
    assert not polygons_overlap(low, [[4, 1], [8, 1], [8, 3], [4, 3]])                       # side by side along a wall part
    assert not polygons_overlap([[0, 4], [4, 4], [4, 4], [4, 8], [0, 8]], low)               # a doubled corner changes nothing
    plan = {"schema_version": 1, "floors": [{"id": "f", "name": "EG", "level_key": "eg"}],
            "rooms": [{"id": "r_a", "room_key": "a", "floor_id": "f", "polygon": low}, {"id": "r_b", "room_key": "b", "floor_id": "f", "polygon": high}]}
    assert [i["code"] for i in validate(normalise(plan), ["a", "b"]) if i["code"] == "E_ROOM_OVERLAP"] == ["E_ROOM_OVERLAP"]


def test_a_partition_confirmed_for_the_lower_part_of_a_split_wall_counts_only_there_after_saving_and_loading():
    # a 4 m wall split by a corner at 2 m: only the lower part (wall 1) is confirmed against the hall's wall 3; an
    # outside door sits in the upper part (wall 2) – the editor keeps that corner, the air paths keep the door outside
    bad = {"id": "r_bad", "room_key": "bad", "floor_id": "f", "polygon": [[0, 0], [4, 0], [4, 2], [4, 4], [0, 4]],
           "partitions": [{"room": "r_flur", "thickness_m": 0.14, "wall": 1, "other_wall": 3}]}
    flur = {"id": "r_flur", "room_key": "flur", "floor_id": "f", "polygon": [[4.14, 0], [8, 0], [8, 4], [4.14, 4]],
            "partitions": [{"room": "r_bad", "thickness_m": 0.14, "wall": 3, "other_wall": 1}]}
    up = {"id": "d_out", "room_id": "r_bad", "edge": 2, "offset": 0.5, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": [DOOR]}
    low = {"id": "d_low", "room_id": "r_bad", "edge": 1, "offset": 0.5, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": []}
    saved = normalise({"schema_version": 1, "floors": [{"id": "f", "name": "EG", "level_key": "eg"}], "rooms": [bad, flur], "openings": [up, low]})
    layout, code = migrate(json.loads(json.dumps(saved)))
    assert code is None and layout["rooms"][0]["partitions"] == bad["partitions"] and layout["rooms"][1]["partitions"] == flur["partitions"]
    assert opening_neighbour(layout, "r_bad", layout["openings"][0]) is None
    assert opening_neighbour(layout, "r_bad", layout["openings"][1]) == "r_flur"
    paths = air_paths(layout, {"bad": {"contacts": {DOOR: {"state": "open", "pending": False}}}}, {"available": False})
    assert paths["openings"]["d_out"]["target"] == "outside" and paths["openings"]["d_low"]["target"] == "r_flur"
    assert [(e["a"], e["b"]) for e in paths["edges"]] == [("r_bad", "r_flur")]
    assert shared_wall_length(*layout["rooms"]) == 2.0                           # the confirmed lower 2 m only
