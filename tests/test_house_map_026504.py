"""Optional house map (0.26.5.4): layout schema, wind, auto layout and air-path hypothesis."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq import house_airflow as air
from custom_components.freshairiq import house_autolayout as auto
from custom_components.freshairiq import house_layout as hl
from custom_components.freshairiq import house_wind as wind

SQUARE = [[0, 0], [4, 0], [4, 4], [0, 4]]
L_SHAPE = [[0, 0], [6, 0], [6, 3], [3, 3], [3, 6], [0, 6]]
U_SHAPE = [[0, 0], [6, 0], [6, 5], [4, 5], [4, 2], [2, 2], [2, 5], [0, 5]]
T_SHAPE = [[2, 0], [4, 0], [4, 3], [6, 3], [6, 5], [0, 5], [0, 3], [2, 3]]
SLANTED = [[0, 0], [5, 0], [4, 4], [0, 3]]
PENTAGON = [[0, 0], [4, 0], [5, 3], [2, 5], [-1, 3]]


def _layout(rooms, openings=(), connections=(), north=0.0, confirmed=True, floors=("f_g",)):
    return hl.normalise({
        "schema_version": 1, "building": {"north_deg": north, "units": "m", "north_confirmed": confirmed},
        "floors": [{"id": f, "name": f, "level_key": f} for f in floors],
        "rooms": [{"id": rid, "room_key": key, "floor_id": floor, "polygon": poly} for rid, key, floor, poly in rooms],
        "openings": list(openings), "connections": list(connections),
    })


# --------------------------------------------------------------------------- geometry
@pytest.mark.parametrize("polygon", [SQUARE, L_SHAPE, U_SHAPE, T_SHAPE, SLANTED, PENTAGON])
def test_free_shapes_are_valid_and_have_an_inside_point(polygon) -> None:
    pts = [tuple(p) for p in polygon]
    assert hl.signed_area(pts) > 0
    assert not hl.self_intersects(pts)
    assert hl.point_in_polygon(hl.interior_point(pts), pts) == "inside"
    assert hl.validate(_layout([("r1", "a", "f_g", polygon)]), ["a"]) == []


def test_concave_hit_testing_and_boundaries() -> None:
    pts = [tuple(p) for p in U_SHAPE]
    assert hl.point_in_polygon((3, 4), pts) == "outside"  # the notch of the U
    assert hl.point_in_polygon((1, 4), pts) == "inside"
    assert hl.point_in_polygon((0, 2), pts) == "boundary"
    assert hl.ccw([[0, 0], [0, 4], [4, 4], [4, 0]]) == [[4, 0], [4, 4], [0, 4], [0, 0]]
    assert hl.ccw(SQUARE) == SQUARE


def test_interior_point_falls_back_to_the_mean() -> None:
    assert hl.interior_point([(0, 0), (1, 0), (2, 0)]) == (1.0, 0.0)


@pytest.mark.parametrize(("north", "edge", "expected"), [
    (0.0, 0, 180.0), (0.0, 1, 90.0), (0.0, 2, 0.0), (0.0, 3, 270.0), (90.0, 2, 90.0), (-45.0, 2, 315.0), (307.5, 2, 307.5),
])
def test_wall_bearing_uses_the_plan_north(north, edge, expected) -> None:
    assert hl.edge_bearing([tuple(p) for p in SQUARE], edge, north) == pytest.approx(expected % 360)


def test_shared_walls_and_neighbours() -> None:
    assert hl.shared_length((0, 0), (4, 0), (2, 0), (6, 0)) == pytest.approx(2.0)
    assert hl.shared_length((0, 0), (4, 0), (0, 1), (4, 1)) == 0.0
    assert hl.shared_length((0, 0), (0, 0), (0, 0), (1, 0)) == 0.0
    layout = _layout([("a", "a", "f_g", SQUARE), ("b", "b", "f_g", [[4, 0], [8, 0], [8, 4], [4, 4]])])
    assert hl.neighbour_at(layout, "a", (4, 2)) == "b"
    assert hl.neighbour_at(layout, "a", (0, 2)) is None
    assert hl.neighbour_at(layout, "missing", (0, 0)) is None


@pytest.mark.parametrize(("polygon", "code"), [
    ([[0, 0], [1, 0]], "E_POLY_POINTS"),
    ([[0, 0], [1, 0], [float("nan"), 1]], "E_POLY_NONFINITE"),
    ([[0, 0], [1, 0], [99999, 1]], "E_POLY_NONFINITE"),
    ([[0, 0], [1, 0], [1, 0], [0, 1]], "E_POLY_DEGENERATE"),
    ([[0, 0], [4, 4], [4, 0], [0, 4]], "E_POLY_SELF_INTERSECT"),
    ([[0, 0], [2, 0], [4, 0.01]], "E_POLY_AREA"),
    ([[i, (i % 2) * 0.5] for i in range(70)], "E_LIMIT_VERTICES"),
])
def test_broken_polygons_get_a_clear_error_at_the_room(polygon, code) -> None:
    issues = hl.validate(_layout([("r1", "a", "f_g", polygon)]))
    assert issues[0]["code"] == code and issues[0]["id"] == "r1"


def test_overlap_duplicates_floors_and_orphans() -> None:
    inner = [[1, 1], [3, 1], [3, 3], [1, 3]]
    layout = _layout([("a", "a", "f_g", SQUARE), ("b", "b", "f_g", inner), ("c", "a", "f_x", SQUARE),
                      ("d", "d", "f_g", [[10, 0], [14, 0], [14, 4], [10, 4]]), ("e", "e", "f_g", [[10, 0], [14, 0], [14, 4], [10, 4]])])
    codes = {(i["code"], i["id"]) for i in hl.validate(layout, ["a", "b", "d"])}
    assert ("E_ROOM_OVERLAP", "b") in codes and ("E_ROOM_OVERLAP", "e") in codes
    assert ("E_FLOOR_UNKNOWN", "c") in codes and ("E_ROOM_DUPLICATE", "c") in codes
    assert ("W_ROOM_ORPHANED", "e") in codes
    crossing = _layout([("a", "a", "f_g", SQUARE), ("b", "b", "f_g", [[2, -1], [6, -1], [6, 2], [2, 2]])])
    assert hl.validate(crossing)[0]["code"] == "E_ROOM_OVERLAP"


def test_openings_and_connections_are_checked_against_their_wall() -> None:
    openings = [
        {"id": "o1", "room_id": "a", "edge": 1, "offset": 0.5, "width_m": 1.0},
        {"id": "o2", "room_id": "a", "edge": 9, "offset": 0.5},
        {"id": "o3", "room_id": "a", "edge": 1, "offset": 1.5},
        {"id": "o4", "room_id": "a", "edge": 1, "offset": 0.5, "width_m": 9.0},
        {"id": "o5", "room_id": "zz", "edge": 0, "offset": 0.5},
        {"id": "o6", "room_id": "bad", "edge": 0, "offset": 0.5},
        {"id": "o7", "room_id": "a", "edge": True, "offset": 0.5},
    ]
    connections = [{"id": "c1", "a": "a", "b": "outside", "kind": "door"}, {"id": "c2", "a": "a", "b": "a", "kind": "door"},
                   {"id": "c3", "a": "a", "b": "nope", "kind": "door"}, {"id": "c4", "a": "a", "b": "outside", "kind": "teleport"}]
    layout = _layout([("a", "a", "f_g", SQUARE), ("bad", "bad", "f_g", [[0, 0]])], openings, connections)
    codes = {(i["code"], i["id"]) for i in hl.validate(layout)}
    assert ("E_OPENING_EDGE", "o2") in codes and ("E_OPENING_OFFSET", "o3") in codes and ("E_OPENING_WIDTH", "o4") in codes
    assert ("E_OPENING_ROOM", "o5") in codes and ("E_OPENING_EDGE", "o7") in codes
    assert not any(i["id"] in ("o1", "o6", "c1") for i in hl.validate(layout))
    assert {"c2", "c3", "c4"} <= {i["id"] for i in hl.validate(layout) if i["code"] == "E_CONNECTION"}


def test_ids_and_limits() -> None:
    layout = _layout([("a", "a", "f_g", SQUARE), ("a", "b", "f_g", [[5, 0], [9, 0], [9, 4], [5, 4]])])
    layout["floors"] = [{"id": "f_g"}] * (hl.LIMITS["floors"] + 1)
    codes = {i["code"] for i in hl.validate(layout)}
    assert {"E_ID", "E_LIMIT_FLOORS"} <= codes


def test_normalise_migrate_and_reconcile() -> None:
    assert hl.normalise("junk") == hl.empty_layout()
    raw = {"revision": "3", "building": {"north_deg": 370, "units": "parsec"}, "rooms": [{"id": 1, "polygon": [[0, "x"], "bad", [1, 1]], "provenance": "alien"}, "skip"],
           "openings": [{"kind": "porthole", "mechanics": "magic", "contacts": ["a", "", None]}, {"contacts": "x"}], "floors": "nope"}
    out = hl.normalise(raw)
    assert out["revision"] == 3 and out["building"] == {"north_deg": 10.0, "units": "schematic", "north_confirmed": False}
    assert out["rooms"][0]["polygon"] == [[0.0, None], [1.0, 1.0]] and out["rooms"][0]["provenance"] == "user"
    assert out["openings"][0]["kind"] == "window" and out["openings"][0]["mechanics"] == "unknown" and out["openings"][0]["contacts"] == ["a"]
    assert out["openings"][1]["contacts"] == [] and out["floors"] == []
    out = hl.normalise({"building": {"north_deg": None}, "rooms": [{"polygon": "x"}]})
    assert out["building"]["north_deg"] == 0.0 and out["rooms"][0]["polygon"] == []
    assert hl.migrate(None)[0] == hl.empty_layout()
    assert hl.migrate([1]) == (None, "E_SCHEMA")
    assert hl.migrate({"schema_version": 2}) == (None, "E_SCHEMA_VERSION")
    assert hl.migrate({"schema_version": 1, "revision": 2})[0]["revision"] == 2
    assert hl.errors([{"code": "W_X"}, {"code": "E_Y"}]) == [{"code": "E_Y"}]
    layout = _layout([("a", "a", "f_g", SQUARE), ("z", "z", "f_g", [[5, 0], [9, 0], [9, 4], [5, 4]])])
    assert hl.reconcile(layout, ["a", "b"]) == {"missing": ["b"], "orphaned": ["z"]}


# --------------------------------------------------------------------------- wind
@pytest.mark.parametrize(("value", "expected"), [
    (0, 0.0), (22.5, 22.5), (45, 45.0), (89.9, 89.9), (90, 90.0), (180, 180.0), (225, 225.0), (270, 270.0),
    (307.5, 307.5), (359.9, 359.9), (360, 0.0), ("NW", 315.0), ("nnw", 337.5), ("W", 270.0), ("NO", 45.0), ("SSO", 157.5),
    ("12,5", 12.5), (None, None), (True, None), ("unknown", None), ("unavailable", None), (float("nan"), None), (-1, None), (361, None),
])
def test_bearing_parsing(value, expected) -> None:
    assert wind.parse_bearing(value) == expected


@pytest.mark.parametrize(("value", "unit", "expected", "assumed"), [
    (18, "km/h", 5.0, False), (5, "m/s", 5.0, False), (10, "mph", 4.4704, False), (10, "kn", 5.14444, False),
    (10, "ft/s", 3.048, False), (36, None, 10.0, True), (5, "Bft", None, False), (None, "m/s", None, False),
    ("x", "m/s", None, False), (-1, "m/s", None, False), (True, "m/s", None, False), (float("inf"), "m/s", None, False),
])
def test_speed_units(value, unit, expected, assumed) -> None:
    ms, was_assumed = wind.speed_ms(value, unit)
    assert (ms if ms is None else round(ms, 5)) == expected and was_assumed is assumed


def test_wind_state_from_to_labels_age_and_reasons() -> None:
    now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
    state = wind.wind_state(bearing=307, speed=18, unit="km/h", gust=36, source="weather.home", observed_at=now - timedelta(minutes=5), now=now)
    assert state["available"] and state["from_deg"] == 307.0 and state["to_deg"] == 127.0
    assert state["label_en"] == "NW" and state["label_de"] == "NW" and state["gust_ms"] == 10.0 and state["age_s"] == 300
    assert wind.wind_state(bearing=None, speed=5, unit="m/s")["reason"] == "no_direction"
    assert wind.wind_state(bearing=90, speed=0.2, unit="m/s")["reason"] == "calm"
    stale = wind.wind_state(bearing=90, speed=5, unit="m/s", observed_at=now - timedelta(hours=4), now=now)
    assert stale["reason"] == "stale" and not stale["available"]
    assert wind.compass_label(None) is None and wind.compass_label(100, "de") == "O"
    assert wind.angle_between(350, 10) == 20.0 and wind.angle_between(0, 180) == 180.0


def test_facade_exposure() -> None:
    nw = wind.wind_state(bearing=315, speed=5, unit="m/s")
    assert wind.facade_exposure(315, nw)["exposure"] == "windward"
    assert wind.facade_exposure(135, nw)["exposure"] == "leeward"
    assert wind.facade_exposure(45, nw)["exposure"] == "side"
    assert wind.facade_exposure(None, nw)["exposure"] == "unknown"
    assert wind.facade_exposure(0, wind.wind_state(bearing=0, speed=0, unit="m/s"))["exposure"] == "calm"
    assert wind.facade_exposure(315, nw)["pressure"] == 1.0


# --------------------------------------------------------------------------- auto layout
ROOMS = [
    {"key": "flur", "floor": "ground_floor", "length": 6, "width": 2, "contacts": ["binary_sensor.haustuer", "binary_sensor.bad_tuer"]},
    {"key": "bad", "floor": "ground_floor", "volume": 20, "height": 2.5, "contacts": ["binary_sensor.bad_fenster", "binary_sensor.bad_tuer"],
     "contact_orientations": {"binary_sensor.bad_fenster": "nw"}},
    {"key": "wohnen", "floor": "ground_floor", "length": 5, "width": 4, "contacts": ["binary_sensor.w1", "binary_sensor.w2"],
     "window_orientation": "se"},
    {"key": "buero", "floor": "ground_floor", "contacts": "binary_sensor.buero_fenster"},
    {"key": "schlaf", "floor": "upper_floor", "volume": 36, "contacts": ["sensor.schlaf_lage"]},
    {"key": "keller", "volume": 30},
    "junk", {"name": "no key"},
]


def test_room_size_provenance() -> None:
    assert auto.room_size({"length": 5, "width": 4}) == (5.0, 4.0, "config")
    assert auto.room_size({"volume": 25, "height": 2.5}) == (3.16, 3.16, "estimated")
    assert auto.room_size({"volume": 40}) == (4.0, 4.0, "estimated")
    assert auto.room_size({"volume": "x"}) == (4.0, 4.0, "schematic")
    assert auto.room_size({"volume": -3}) == (4.0, 4.0, "schematic")


# Hotfix after review (F02, requirement change): a contact used by two rooms is drawn as a door between them only when
# it is known to be a door – here, as in Home Assistant, by the sensor's device class "door" (ws_propose passes it).
# The same contact without any known kind is no door any more – like an unknown contact of one room it is drawn as a
# window, once (see the unknown-kind check at the end).
DOOR_CLASSES = {"binary_sensor.bad_tuer": "door"}


def test_proposal_is_deterministic_valid_and_honest() -> None:
    first = auto.propose(ROOMS, ["ground_floor", "upper_floor"], {"flur": ["wohnen", "buero", "flur"]}, DOOR_CLASSES)
    second = auto.propose(ROOMS, ["ground_floor", "upper_floor"], {"flur": ["wohnen", "buero", "flur"]}, DOOR_CLASSES)
    assert first == second
    layout = hl.normalise(first["layout"])
    assert hl.validate(layout, ["flur", "bad", "wohnen", "buero", "schlaf", "keller"]) == []
    assert first["quality"]["provenance"] == {"flur": "config", "bad": "estimated", "wohnen": "config", "buero": "schematic",
                                              "schlaf": "estimated", "keller": "estimated"}
    assert [f["level_key"] for f in layout["floors"]] == ["ground_floor", "upper_floor", "unassigned"]
    assert first["quality"]["floors"]["ground_floor"]["value"] == 0
    doors = [o for o in layout["openings"] if o["kind"] == "door"]
    assert [d["contacts"] for d in doors] == [["binary_sensor.bad_tuer"]]
    assert not any(c["id"] == "c_bad_flur" for c in layout["connections"])
    assert {c["id"] for c in layout["connections"]} == {"c_buero_flur", "c_flur_wohnen"}
    # every window sits on an outside wall, at a free stretch of it
    for opening in layout["openings"]:
        if opening["kind"] == "window":
            room = next(r for r in layout["rooms"] if r["id"] == opening["room_id"])
            point = hl.edge_point([tuple(p) for p in room["polygon"]], opening["edge"], opening["offset"])
            assert hl.neighbour_at(layout, room["id"], point) is None, opening
    wohnen = [o for o in layout["openings"] if o["room_id"] == "r_wohnen"]
    assert len(wohnen) == 2 and wohnen[0]["offset"] != wohnen[1]["offset"]
    bad_window = next(o for o in layout["openings"] if o["id"] == "o_bad_0")
    room = next(r for r in layout["rooms"] if r["id"] == "r_bad")
    assert wind.angle_between(hl.edge_bearing([tuple(p) for p in room["polygon"]], bad_window["edge"], 0.0), 315.0) <= 45.0
    assert layout["building"]["units"] == "m"
    # the same shared contact with nothing saying what it is: no door and no connection – one window (in the bath)
    unknown = hl.normalise(auto.propose(ROOMS, ["ground_floor", "upper_floor"], {"flur": ["wohnen", "buero", "flur"]})["layout"])
    assert [(o["room_id"], o["kind"]) for o in unknown["openings"] if "binary_sensor.bad_tuer" in o["contacts"]] == [("r_bad", "window")]
    assert not [c for c in unknown["connections"] if "binary_sensor.bad_tuer" in c.get("contacts", [])]


def test_shelf_layout_without_connections_and_schematic_units() -> None:
    rooms = [{"key": f"r{i}", "floor": "g", "contacts": [f"binary_sensor.w{i}"]} for i in range(5)]
    result = auto.propose(rooms, ["basement", "g"])
    layout = hl.normalise(result["layout"])
    assert hl.validate(layout) == [] and layout["building"]["units"] == "schematic"
    assert result["quality"]["floors"]["g"]["candidates"] == 1 and "basement" not in result["quality"]["floors"]
    assert [f["level_key"] for f in layout["floors"]] == ["basement", "g"]


def test_enclosed_room_window_is_marked_unplaced() -> None:
    placed = {"mid": auto._box(4, 4, 4, 4), "n": auto._box(0, 8, 12, 4), "s": auto._box(0, 0, 12, 4),
              "w": auto._box(0, 4, 4, 4), "e": auto._box(8, 4, 4, 4)}
    rooms = [{"key": "mid", "contacts": ["binary_sensor.x"]}]
    opening = auto._openings(rooms, placed, {})[0]
    assert opening["provenance"] == "unplaced"
    assert auto._best_edge("mid", placed, "n") == (0, None, "auto")
    quality = auto.score(placed, {("mid", "zz"): {}}, {"mid": ["binary_sensor.x"]})
    assert quality["windows_without_facade"] == ["mid"] and quality["value"] == 5


def test_spine_rest_rooms_and_untouched_doors() -> None:
    rooms = [{"key": "hall"}, {"key": "a"}, {"key": "b"}, {"key": "c"}, {"key": "loner"}]
    sizes = {r["key"]: auto.room_size(r) for r in rooms}
    pairs = {("a", "hall"): {"kind": "open_passage"}, ("b", "hall"): {"kind": "open_passage"}, ("c", "hall"): {"kind": "open_passage"}}
    placed = auto._spine(rooms, sizes, pairs)
    assert set(placed) == {"hall", "a", "b", "c", "loner"}
    assert auto.score(placed, pairs, {})["overlaps"] == 0
    assert auto._spine(rooms, sizes, {}) is None
    doors = auto._openings([{"key": "a"}, {"key": "loner"}], placed, {("a", "loner"): {"kind": "door", "contacts": ["d"]}})
    assert doors == []


def test_add_missing_keeps_existing_geometry() -> None:
    layout = hl.normalise(auto.propose(ROOMS[:2], ["ground_floor"])["layout"])
    before = [r["polygon"] for r in layout["rooms"]]
    out = auto.add_missing(layout, ROOMS, ["ground_floor", "upper_floor"])
    assert [r["polygon"] for r in out["rooms"][:2]] == before
    assert {r["room_key"] for r in out["rooms"]} >= {"wohnen", "buero", "schlaf"}
    assert hl.validate(hl.normalise(out)) == []
    assert auto.add_missing(out, ROOMS, []) is out
    empty = auto.add_missing(hl.empty_layout(), [{"key": "x", "floor": "g"}], ["g"])
    assert empty["rooms"][0]["polygon"][0] == [0.0, -4.0]


# --------------------------------------------------------------------------- air paths
def _house(confirmed=True, north=0.0):
    rooms = [("bad", "bad", "f_g", [[0, 4], [4, 4], [4, 8], [0, 8]]), ("flur", "flur", "f_g", [[0, 0], [8, 0], [8, 4], [0, 4]]),
             ("wohnen", "wohnen", "f_g", [[4, 4], [8, 4], [8, 8], [4, 8]]), ("kammer", "kammer", "f_g", [[8, 0], [12, 0], [12, 4], [8, 4]])]
    openings = [
        {"id": "o_bad", "room_id": "bad", "edge": 2, "offset": 0.5, "contacts": ["binary_sensor.bad_fenster"]},       # north wall
        {"id": "o_wohnen", "room_id": "wohnen", "edge": 1, "offset": 0.5, "contacts": ["sensor.wohnen_lage"]},          # east wall
        {"id": "d_bad", "room_id": "bad", "edge": 0, "offset": 0.5, "kind": "door", "contacts": ["binary_sensor.bad_tuer"]},
        {"id": "p_wohnen", "room_id": "wohnen", "edge": 0, "offset": 0.5, "kind": "passage"},
        {"id": "o_kammer", "room_id": "kammer", "edge": 0, "offset": 0.5},
    ]
    connections = [{"id": "c_stairs", "a": "flur", "b": "outside", "kind": "stairs"},
                   {"id": "c_kammer", "a": "flur", "b": "kammer", "kind": "door", "contacts": ["binary_sensor.kammer_tuer"]}]
    return _layout(rooms, openings, connections, north=north, confirmed=confirmed)


def _live(bad="open_unspecified", wohnen="tilted", door="open_unspecified", pending=False, kammer="closed"):
    return {
        "bad": {"contacts": {"binary_sensor.bad_fenster": {"state": bad, "pending": pending}, "binary_sensor.bad_tuer": {"state": door}},
                "orientations": {"binary_sensor.bad_fenster": "n"}},
        "wohnen": {"contacts": {"sensor.wohnen_lage": {"state": wohnen}}, "orientations": {"sensor.wohnen_lage": "e"}},
        "flur": {"contacts": {"binary_sensor.kammer_tuer": {"state": kammer}}},
        "kammer": {},
    }


NW = wind.wind_state(bearing=315, speed=5, unit="m/s")
NE = wind.wind_state(bearing=45, speed=5, unit="m/s")


def test_live_contact_mapping() -> None:
    # audit (10) P1: "pending" only while the contact's own delay runs (the first version said pending
    # for every open contact of a room without a session – that expectation encoded the bug)
    assert air.live_contact("open", three_state=False, stable_mode=None, room_active=False, delay_s=120, open_seconds=30) == {
        "state": "open_unspecified", "pending": True, "three_state": False, "delay_s": 120, "open_s": 30}
    assert air.live_contact("open", three_state=True, stable_mode="tilted", room_active=True, delay_s=0)["state"] == "tilted"
    assert air.live_contact("open", three_state=True, stable_mode=None, room_active=True, delay_s=0)["state"] == "unknown"
    assert air.live_contact("closed", three_state=False, stable_mode=None, room_active=False, delay_s=0)["state"] == "closed"
    assert air.live_contact("unknown", three_state=False, stable_mode=None, room_active=False, delay_s=0)["state"] == "unknown"


def test_contact_state_combination() -> None:
    assert air.contact_state(["a"], {}) == ("unknown", False)
    assert air.contact_state(["a", "b"], {"a": {"state": "tilted"}, "b": {"state": "open"}}) == ("open", False)
    assert air.contact_state(["a", "b"], {"a": {"state": "tilted", "pending": True}, "b": {"state": "closed"}}) == ("tilted", True)
    assert air.contact_state(["a", "b"], {"a": {"state": "closed"}}) == ("unknown", False)
    assert air.contact_state(["a"], {"a": {"state": "weird"}}) == ("unknown", False)
    assert air.contact_state(["a"], {"a": {"state": "closed"}}) == ("closed", False)
    assert air.contact_state(["a"], {"a": "bad"}) == ("unknown", False)


def test_windward_to_leeward_path_through_open_door() -> None:
    result = air.air_paths(_house(), _live(), NW)
    assert result["model_level"] == "wind_heuristic"  # binary window: opening class unknown
    cross = [p for p in result["paths"] if p["kind"] == "cross"]
    assert cross and cross[0]["from"] == "o_bad" and cross[0]["to"] == "o_wohnen"
    assert cross[0]["rooms"] == ["bad", "flur", "wohnen"] and cross[0]["via"] == ["d_bad", "p_wohnen"]
    assert cross[0]["confidence"] == "low" and "no_measured_flow" in cross[0]["assumptions"]
    assert result["openings"]["o_bad"]["exposure"] == "windward" and result["openings"]["o_wohnen"]["exposure"] == "leeward"
    assert result["openings"]["o_wohnen"]["size"] == "small" and result["openings"]["o_bad"]["size"] == "unknown"
    assert result["openings"]["o_kammer"]["state"] == "no_sensor"
    assert {e["id"]: e["state"] for e in result["edges"]}["c_kammer"] == "closed"
    assert {e["id"]: e["state"] for e in result["edges"]}["c_stairs"] == "unknown"


def test_proven_opening_classes_raise_the_level() -> None:
    live = _live(bad="open")
    result = air.air_paths(_house(), live, NW)
    assert result["model_level"] == "opening_aware"
    assert [p["confidence"] for p in result["paths"] if p["kind"] == "cross"] == ["medium"]


def test_closed_inner_door_stops_the_path() -> None:
    result = air.air_paths(_house(), _live(door="closed"), NW)
    kinds = sorted(p["kind"] for p in result["paths"])
    assert "cross" not in kinds and kinds.count("single_sided") == 2
    assert all(p["direction"] == "bidirectional" for p in result["paths"])


def test_one_window_without_exit_is_only_single_sided() -> None:
    result = air.air_paths(_house(), _live(wohnen="closed"), NW)
    assert [p["kind"] for p in result["paths"]] == ["single_sided"]


def test_no_wind_or_side_wind_never_invents_a_direction() -> None:
    none = air.air_paths(_house(), _live(), wind.wind_state(bearing=None, speed=None))
    assert none["model_level"] == "topology_only"
    assert [p["kind"] for p in none["paths"]] == ["cross_possible"] and "wind" in none["paths"][0]["unknowns"]
    side = air.air_paths(_house(), _live(), wind.wind_state(bearing=180, speed=5, unit="m/s"))
    assert [p["kind"] for p in side["paths"]] == ["cross_possible"] and "wind" not in side["paths"][0]["unknowns"]


def test_pending_opening_is_not_an_active_airing() -> None:
    result = air.air_paths(_house(), _live(pending=True), NW)
    assert result["pending_openings"] == ["o_bad"]
    assert [p["kind"] for p in result["paths"]] == ["single_sided"]
    door_pending = air.air_paths(_house(), {**_live(), "flur": {"contacts": {"binary_sensor.kammer_tuer": {"state": "open_unspecified", "pending": True}}}}, NW)
    assert {e["id"]: e["state"] for e in door_pending["edges"]}["c_kammer"] == "open_unspecified"


def test_unconfirmed_north_uses_configured_orientation_or_nothing() -> None:
    result = air.air_paths(_house(confirmed=False, north=90.0), _live(), NW)
    assert result["openings"]["o_bad"]["facade_basis"] == "configured_orientation" and result["openings"]["o_bad"]["facade_deg"] == 0.0
    live = _live()
    live["bad"]["orientations"] = {}
    result = air.air_paths(_house(confirmed=False), live, NW)
    assert result["openings"]["o_bad"]["facade_deg"] is None and result["model_level"] == "topology_only"


def test_rotated_building_changes_the_exposure() -> None:
    assert air.air_paths(_house(north=0.0), _live(), NE)["openings"]["o_bad"]["exposure"] == "windward"
    assert air.air_paths(_house(north=180.0), _live(), NE)["openings"]["o_bad"]["exposure"] == "leeward"


def test_exhaust_fan_paths_and_shared_device() -> None:
    live = _live(bad="closed", wohnen="closed")
    live["bad"].update(exhaust_fan="fan.abluft", mechanical_exhaust_active=True)
    live["kammer"] = {"exhaust_fan": "fan.abluft", "mechanical_exhaust_active": False}
    result = air.air_paths(_house(), live, NW)
    assert result["devices"] == [{"fan": "fan.abluft", "rooms": ["bad", "kammer"], "active": True}]
    assert [p["kind"] for p in result["paths"]] == ["exhaust_replacement_unconfirmed"]
    assert "reference_is_not_airflow" in result["paths"][0]["assumptions"]
    live = _live(bad="closed")
    live["bad"].update(exhaust_fan="fan.abluft", mechanical_exhaust_active=True)
    result = air.air_paths(_house(), live, NW)
    exhaust = [p for p in result["paths"] if p["kind"] == "exhaust"]
    assert exhaust and exhaust[0]["from"] == "o_wohnen" and exhaust[0]["rooms"] == ["wohnen", "flur", "bad"]


def test_rooms_without_live_data_and_dangling_openings() -> None:
    layout = _house()
    layout["openings"].append({"id": "o_ghost", "room_id": "ghost", "edge": 0, "offset": 0.5, "contacts": []})
    result = air.air_paths(layout, {"bad": "junk"}, NW)
    assert "o_ghost" not in result["openings"] and result["openings"]["o_bad"]["state"] == "unknown"
    assert air._route("bad", "nowhere", []) is None
    many = air.air_paths(layout, _live(), NW)
    assert len(many["paths"]) <= air.MAX_PATHS


def test_the_hypothesis_never_states_flow_rates() -> None:
    result = air.air_paths(_house(), _live(bad="open"), NW)
    text = repr(result)
    assert "m3" not in text and "speed" not in text and "calibrated" not in text
    assert math.isclose(result["openings"]["o_bad"]["pressure"], 0.71)


# --------------------------------------------------------------------------- demo + budgets
def test_synthetic_demo_house_is_valid_and_explains_its_airing() -> None:
    import json
    from pathlib import Path

    layout = hl.normalise(json.loads((Path(__file__).resolve().parents[1] / "docs/examples/house_map_demo.json").read_text(encoding="utf-8")))
    assert hl.validate(layout) == []
    assert {f["level_key"] for f in layout["floors"]} == {"basement", "ground_floor", "upper_floor"}
    assert len(next(r for r in layout["rooms"] if r["id"] == "r_wohnen")["polygon"]) == 6  # L shape
    kueche = [tuple(p) for p in next(r for r in layout["rooms"] if r["id"] == "r_kueche")["polygon"]]
    assert hl.edge_bearing(kueche, 1, 20.0) % 90 != 0  # slanted outside wall
    live = {
        "wohnen": {"contacts": {"sensor.wohnen_fenster_lage": {"state": "tilted"}}},
        "kueche": {"contacts": {"binary_sensor.kueche_fenster": {"state": "open_unspecified"}}},
        "bad": {"contacts": {"binary_sensor.bad_tuer": {"state": "closed"}, "sensor.bad_fenster_lage": {"state": "closed"}},
                "exhaust_fan": "fan.abluft", "mechanical_exhaust_active": True},
        "wc": {"exhaust_fan": "fan.abluft", "mechanical_exhaust_active": True},
    }
    result = air.air_paths(layout, live, wind.wind_state(bearing=200, speed=4, unit="m/s"))
    assert result["devices"] == [{"fan": "fan.abluft", "rooms": ["r_bad", "r_wc"], "active": True}]
    assert result["openings"]["o_wohnen_s"]["size"] == "small" and result["openings"]["o_kueche_o"]["state"] == "open_unspecified"
    # wind from 200°: the living room wall is windward, the slanted kitchen wall only side-on -> no invented direction
    assert result["openings"]["o_wohnen_s"]["exposure"] == "windward" and result["openings"]["o_kueche_o"]["exposure"] == "side"
    assert {p["kind"] for p in result["paths"]} == {"cross_possible", "exhaust_replacement_unconfirmed"}
    # the stairs connection without a sensor never carries a path between floors
    assert all("c_stairs" not in p["via"] for p in result["paths"])


def _big_house(rooms_per_floor=20, floors=2, windows=4):
    rooms, openings = [], []
    for f in range(floors):
        for i in range(rooms_per_floor):
            x, y = (i % 5) * 4, (i // 5) * 4
            rid = f"r{f}_{i}"
            rooms.append((rid, rid, f"f{f}", [[x, y], [x + 4, y], [x + 4, y + 4], [x, y + 4]]))
            for e in range(windows):
                openings.append({"id": f"o{rid}_{e}", "room_id": rid, "edge": e, "offset": 0.5, "contacts": [f"binary_sensor.{rid}_{e}"]})
    return _layout(rooms, openings, floors=tuple(f"f{f}" for f in range(floors)))


def test_large_house_budget() -> None:
    import time

    layout = _big_house()
    assert len(layout["rooms"]) == 40 and len(layout["openings"]) == 160
    live = {r["room_key"]: {"contacts": {c: {"state": "open_unspecified"} for o in layout["openings"] if o["room_id"] == r["id"] for c in o["contacts"]}}
            for r in layout["rooms"]}
    started = time.perf_counter()
    issues = hl.validate(layout)
    result = air.air_paths(layout, live, NW)
    elapsed = time.perf_counter() - started
    assert issues == [] and len(result["paths"]) <= air.MAX_PATHS
    assert elapsed < 3.0, elapsed  # budget for one live push of a 40-room house (measured ≈0.3 s locally)


# --------------------------------------------------------------------------- audit (10)
@pytest.mark.parametrize(("delay", "open_s", "active", "pending"), [
    (0, 5, False, False),      # no delay, no session (e.g. no valid climate data): simply open
    (120, 30, False, True),    # delay still running
    (120, 130, False, False),  # delay over, session not started for another reason: open, not "confirmation running"
    (120, 30, True, False),    # session runs (re-open)
    (120, None, False, False),  # unknown opening time: no invented confirmation
])
def test_pending_means_a_running_opening_delay_only(delay, open_s, active, pending) -> None:
    result = air.live_contact("open", three_state=False, stable_mode=None, room_active=active, delay_s=delay, open_seconds=open_s)
    assert result["state"] == "open_unspecified" and result["pending"] is pending
    assert air.live_contact("closed", three_state=False, stable_mode=None, room_active=False, delay_s=120, open_seconds=5)["open_s"] is None


def test_open_window_without_session_still_gets_its_air_path() -> None:
    live = _live()
    for room in live.values():
        for contact in (room.get("contacts") or {}).values():
            contact["pending"] = False  # open for longer than any delay, no session running
    result = air.air_paths(_house(), live, NW)
    assert result["pending_openings"] == [] and [p["kind"] for p in result["paths"]] == ["cross"]


def test_same_fans_in_any_order_are_the_same_devices() -> None:
    assert air.fan_entities(["fan.a", "fan.b", "fan.a", ""]) == ["fan.a", "fan.b"]
    assert air.fan_entities("fan.a") == ["fan.a"] and air.fan_entities(None) == [] and air.fan_entities("") == []
    live = _live(bad="closed", wohnen="closed")
    live["bad"].update(exhaust_fan=["fan.a", "fan.b"], exhaust_fans={"fan.a": True, "fan.b": False}, mechanical_exhaust_active=True)
    live["kammer"] = {"exhaust_fan": ["fan.b", "fan.a"], "exhaust_fans": {"fan.a": True, "fan.b": False}, "mechanical_exhaust_active": False}
    devices = air.air_paths(_house(), live, NW)["devices"]
    assert devices == [{"fan": "fan.a", "rooms": ["bad", "kammer"], "active": True}, {"fan": "fan.b", "rooms": ["bad", "kammer"], "active": False}]
