"""Hotfix after the independent review of 0.26.6.0 (F01–F03, pure logic).

F01 – where an opening is drawn, which sensor it has and which room it airs are independent: the live state of a
      contact is found by the sensor, also when the contact belongs to another room's setup.
F02 – a contact used by several rooms is a door only when the setup or Home Assistant says so; a shared window is
      drawn once; a shared contact of unknown kind is drawn once as a window, like an unknown contact of one room.
F03 – wall normals follow the polygon's real orientation (clockwise rooms), in Python like in JS; the shared join
      fixture with clockwise rooms gives the same house as the counter-clockwise one.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from custom_components.freshairiq import house_autolayout as auto
from custom_components.freshairiq import house_layout as hl
from custom_components.freshairiq.house_airflow import air_paths, sensor_states

FIX = Path(__file__).resolve().parents[1] / "frontend_tests" / "fixtures"
CCW = json.loads((FIX / "house_join_rooms.json").read_text(encoding="utf-8"))
CW = json.loads((FIX / "house_join_rooms_cw.json").read_text(encoding="utf-8"))
WIN, DOOR = "binary_sensor.wc_fenster", "binary_sensor.wc_tuer"


def _room(key, contacts, **extra):
    return {"key": key, "floor": "eg", "contacts": contacts, **extra}


# ---- F02: what a contact is ------------------------------------------------------------------------------------
def test_contact_role_comes_from_the_setup_and_home_assistant_never_from_the_number_of_users() -> None:
    rooms = lambda **wc: [_room("wc", [WIN], **wc), _room("flur", [WIN])]  # noqa: E731
    assert auto.contact_role(rooms(), WIN) == "unknown"
    assert auto.contact_role(rooms(contact_kinds={WIN: "window"}), WIN) == "window"
    assert auto.contact_role(rooms(), WIN, {WIN: "window"}) == "window"
    assert auto.contact_role(rooms(contact_kinds={WIN: "door"}), WIN) == "door"
    assert auto.contact_role(rooms(contact_passage_doors={WIN: True}), WIN) == "door"
    assert auto.contact_role(rooms(), WIN, {WIN: "door"}) == "door"
    assert auto.contact_role(rooms(), WIN, {WIN: "garage_door"}) == "door"
    # a window stated in the setup wins over a door device class; a sensor of another kind says nothing
    assert auto.contact_role(rooms(contact_kinds={WIN: "window"}), WIN, {WIN: "door"}) == "window"
    assert auto.contact_role(rooms(), WIN, {WIN: "opening"}) == "unknown"
    assert auto.contact_role([{"key": "x", "contacts": "binary_sensor.other"}], WIN) == "unknown"


def test_adjacency_draws_doors_only_for_door_contacts() -> None:
    # 3: one contact in two rooms' setup – a window: no pair at all (it is no way between the rooms)
    assert auto.adjacency([_room("wc", [WIN]), _room("flur", [WIN])], None, {WIN: "window"}) == {}
    # unknown kind: no pair either (drawn once as a window, like an unknown contact of one room)
    assert auto.adjacency([_room("wc", [WIN]), _room("flur", [WIN])]) == {}
    # 4: a real shared door contact (stated, or a door sensor) is a door between the rooms
    pairs = auto.adjacency([_room("wc", [DOOR], contact_kinds={DOOR: "door"}), _room("flur", [DOOR, WIN])], {"flur": ["wohnen"]})
    assert pairs == {("flur", "wc"): {"kind": "door", "contacts": [DOOR]}, ("flur", "wohnen"): {"kind": "open_passage", "contacts": []}}
    # a single room's contact is never a pair
    assert auto.adjacency([_room("wc", [WIN, DOOR])]) == {}


def test_window_homes_draw_a_shared_window_once_in_one_room() -> None:
    sizes = {"wc": (1.2, 1.5, "config"), "flur": (5.0, 2.0, "config"), "bad": (3.0, 3.0, "config")}
    rooms = [_room("flur", [WIN]), _room("wc", [WIN])]
    assert auto.window_homes(rooms, sizes, {}) == {WIN: "wc"}                         # the smaller room
    # the room that lists fewer contacts (a hall borrows its neighbours' windows) – before the size
    assert auto.window_homes([_room("bad", [WIN]), _room("flur", [WIN, DOOR])], sizes, {}) == {WIN: "bad"}
    stated = [_room("flur", [WIN], contact_kinds={WIN: "window"}), _room("wc", [WIN])]
    assert auto.window_homes(stated, sizes, {}) == {WIN: "flur"}                      # the room that states it wins
    assert auto.window_homes([_room("flur", [WIN]), _room("zz", [WIN])], sizes, {}) == {WIN: "flur"}   # unknown size last
    assert auto.window_homes([_room("bad", [WIN]), _room("abc", [WIN])], {"bad": (2, 2, "c"), "abc": (2, 2, "c")}, {}) == {WIN: "abc"}
    assert auto.window_homes(rooms, sizes, {("flur", "wc"): {"contacts": [WIN]}}) == {}  # a shared door is no window
    assert auto.window_homes([_room("wc", [WIN])], sizes, {}) == {}


def test_proposal_keeps_a_shared_window_a_window_and_a_shared_door_a_door() -> None:
    wc = _room("wc", [WIN, DOOR], length=1.5, width=1.2, contact_kinds={WIN: "window", DOOR: "door"})
    flur = _room("flur", [WIN, DOOR, "binary_sensor.flur_fenster"], length=5, width=2)
    result = auto.propose([wc, flur], ["eg"])
    layout = hl.normalise(result["layout"])
    assert hl.validate(layout, ["wc", "flur"]) == []
    by_contact = {c: [(o["room_id"], o["kind"]) for o in layout["openings"] if c in o["contacts"]] for c in (WIN, DOOR)}
    assert by_contact == {WIN: [("r_wc", "window")], DOOR: [("r_flur", "door")]}
    assert not [c for c in layout["connections"] if WIN in c.get("contacts", [])]
    door = next(o for o in layout["openings"] if DOOR in o["contacts"])
    assert hl.opening_neighbour(layout, "r_flur", door) == "r_wc"                     # drawn on the shared wall
    # the hall's window list for the facade check no longer claims the WC window
    assert "flur" not in result["quality"]["floors"]["eg"]["windows_without_facade"]


# ---- F01: live state by sensor -------------------------------------------------------------------------------
def test_sensor_states_find_a_contact_wherever_it_is_set_up() -> None:
    live = {"flur": {"contacts": {WIN: {"state": "open_unspecified", "pending": False}}, "orientations": {WIN: "w"}},
            "wc": {"contacts": {DOOR: {"state": "closed", "pending": False}}}, "junk": "x",
            "bad": {"contacts": {WIN: {"state": "closed", "pending": True}}}}
    merged = sensor_states(live, "wc")
    assert merged[WIN]["state"] == "closed" and merged[DOOR]["state"] == "closed"     # rooms in key order: "bad" first
    assert sensor_states(live, "flur")[WIN]["state"] == "open_unspecified"           # the preferred room wins
    assert sensor_states(live, "nowhere", field="orientations") == {WIN: "w"}
    assert sensor_states({}, "wc") == {}


def _wc_layout(clockwise: bool) -> dict:
    wc = [[0, 2], [1.5, 2], [1.5, 3.5], [0, 3.5]] if not clockwise else [[0, 2], [0, 3.5], [1.5, 3.5], [1.5, 2]]
    north, south = (2, 0) if not clockwise else (1, 3)
    return {
        "schema_version": 1, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
        "floors": [{"id": "f", "name": "EG", "level_key": "eg", "order": 0}],
        "rooms": [{"id": "r_flur", "room_key": "flur", "floor_id": "f", "polygon": [[0, 0], [5, 0], [5, 2], [0, 2]]},
                  {"id": "r_wc", "room_key": "wc", "floor_id": "f", "polygon": wc}],
        "openings": [{"id": "w_wc", "room_id": "r_wc", "edge": north, "offset": 0.5, "width_m": 0.6, "kind": "window", "contacts": [WIN]},
                     {"id": "d_wc", "room_id": "r_wc", "edge": south, "offset": 0.5, "width_m": 0.8, "kind": "door", "contacts": [DOOR]}],
        "connections": [],
    }


def test_wc_window_drawn_in_the_wc_takes_the_halls_sensor_state_in_both_orientations() -> None:
    # 1 + 2 + 6: the contacts belong to the hall's setup only; the WC (no contacts) has the window and the door drawn
    live = {"flur": {"contacts": {WIN: {"state": "open_unspecified", "pending": False}, DOOR: {"state": "closed", "pending": False}},
                     "orientations": {WIN: "s"}}, "wc": {"contacts": {}}}
    wind = {"available": True, "from_deg": 0.0, "speed_ms": 4.0, "calm": False}
    results = []
    for clockwise in (False, True):
        layout = hl.normalise(_wc_layout(clockwise))
        assert hl.validate(layout, ["flur", "wc"]) == []
        openings = air_paths(layout, live, wind)["openings"]
        results.append((openings["w_wc"]["state"], openings["w_wc"]["target"], openings["w_wc"]["facade_deg"], openings["w_wc"]["exposure"],
                        openings["d_wc"]["state"], openings["d_wc"]["target"]))
    assert results[0] == results[1] == ("open_unspecified", "outside", 0.0, "windward", "closed", "r_flur")
    # without north the configured orientation of the hall's contact is used
    layout = hl.normalise(_wc_layout(True))
    layout["building"]["north_confirmed"] = False
    window = air_paths(layout, live, wind)["openings"]["w_wc"]
    assert (window["facade_deg"], window["facade_basis"]) == (180.0, "configured_orientation")
    # the door between WC and hall: its own sensor, a connection from the hall's setup works the same way
    layout["openings"] = layout["openings"][:1]
    layout["connections"] = [{"id": "c", "a": "r_wc", "b": "r_flur", "kind": "door", "contacts": [DOOR], "confirmed": True}]
    live["flur"]["contacts"][DOOR] = {"state": "open_unspecified", "pending": False}
    paths = air_paths(layout, live, wind)
    assert paths["openings"]["w_wc"]["state"] == "open_unspecified" and paths["paths"]


# ---- F03: orientation ------------------------------------------------------------------------------------------
def test_outward_normal_and_facade_follow_the_real_orientation() -> None:
    ccw = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
    cw = [(0.0, 0.0), (0.0, 3.0), (4.0, 3.0), (4.0, 0.0)]
    assert hl.outward_normal(ccw, 0) == (0.0, -1.0) and hl.outward_normal(cw, 3) == (0.0, -1.0)    # south wall, both
    assert hl.outward_normal(cw, 0) == (-1.0, 0.0)                                                 # west wall
    assert [round(hl.edge_bearing(ccw, i, 0.0)) for i in range(4)] == [180, 90, 0, 270]
    assert [round(hl.edge_bearing(cw, i, 0.0)) for i in range(4)] == [270, 0, 90, 180]


def test_join_fixture_with_clockwise_rooms_gives_the_same_house() -> None:
    # 6 + 7 + 9: the same rooms drawn clockwise fit together exactly like the counter-clockwise ones
    assert len(CW["matches"]) == len(CCW["matches"]) == 3
    for rid, polygon in CW["joined"].items():
        assert sorted(map(tuple, polygon)) == sorted(map(tuple, CCW["joined"][rid])), rid
    assert [c["code"] for c in CW["conflicts"]] == ["length_differs"]
    for room in CW["layout"]["rooms"]:   # every locked length kept, corner order as drawn
        before, after = room["polygon"], CW["joined"][room["id"]]
        for i in room.get("locked_walls", []):
            assert math.isclose(math.dist(before[i], before[(i + 1) % 4]), math.dist(after[i], after[(i + 1) % 4]), abs_tol=1e-3)
    joined = copy.deepcopy(CW["layout"])
    for room in joined["rooms"]:
        room["polygon"] = CW["joined"][room["id"]]
    layout = hl.normalise(joined)
    assert hl.validate(layout) == []
    door = next(o for o in layout["openings"] if o["id"] == "d_wk")
    window = next(o for o in layout["openings"] if o["id"] == "w_k")
    assert hl.opening_neighbour(layout, "r_wohn", door) == "r_kueche"
    assert hl.opening_neighbour(layout, "r_kueche", window) is None
    kitchen = next(r for r in layout["rooms"] if r["id"] == "r_kueche")
    assert round(hl.edge_bearing([tuple(p) for p in kitchen["polygon"]], window["edge"], 0.0)) == 90   # east stays east
    rooms = {r["id"]: r for r in layout["rooms"]}
    assert hl.shared_wall_length(rooms["r_kueche"], rooms["r_flur"]) >= hl.MIN_SHARED_WALL
