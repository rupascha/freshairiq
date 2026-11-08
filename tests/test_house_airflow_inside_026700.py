"""0.26.7.0: the house map shows outside air only where a real outside opening is open.

Scenarios of the order: all contacts closed, only an inside door open, only an outside window open, inside and
outside openings open, exhaust fan alone. An opening drawn on an outside wall that cannot exchange air with the
outside (a doorless passage, a contact configured as an inside door) is a geometry conflict, never an air path.
"""
from __future__ import annotations

import copy

from custom_components.freshairiq import house_airflow as air
from tests.test_house_map_026504 import NW, _house, _layout, _live


def _paths(result, kind=None):
    return [p for p in result["paths"] if kind is None or p["kind"] == kind]


def _closed():
    return _live(bad="closed", wohnen="closed", door="closed", kammer="closed")


def test_all_closed_no_air_path_and_only_an_inside_door_open_no_air_path_either() -> None:
    assert _paths(air.air_paths(_house(), _closed(), NW)) == []
    door_open = _live(bad="closed", wohnen="closed", door="open_unspecified", kammer="open_unspecified")
    result = air.air_paths(_house(), door_open, NW)
    assert _paths(result) == []                                                    # doors join rooms, they bring no outside air
    assert any(e["state"] == "open" for e in result["edges"])                      # … the connection itself is shown open


def test_only_an_outside_window_open_gives_one_single_sided_path_inside_and_outside_open_join_rooms() -> None:
    only_window = air.air_paths(_house(), _live(bad="open_unspecified", wohnen="closed", door="closed"), NW)
    assert [p["kind"] for p in _paths(only_window)] == ["single_sided"]
    both = air.air_paths(_house(), _live(bad="open_unspecified", wohnen="open", door="open_unspecified"), NW)
    rooms_in_paths = {r for p in _paths(both) for r in p["rooms"]}
    assert {"bad", "wohnen"} <= rooms_in_paths                                      # the open inside door joins both rooms


def test_exhaust_fan_alone_is_shown_as_unconfirmed_replacement_air_not_as_an_outside_opening() -> None:
    live = _closed()
    live["bad"].update({"exhaust_fan": "switch.bad_luefter", "exhaust_fans": {"switch.bad_luefter": True}, "mechanical_exhaust_active": True})
    result = air.air_paths(_house(), live, NW)
    assert [p["kind"] for p in _paths(result)] == ["exhaust_replacement_unconfirmed"]


def _exterior_conflicts():
    rooms = [("bad", "bad", "f_g", [[0, 0], [4, 0], [4, 4], [0, 4]]), ("flur", "flur", "f_g", [[4, 0], [8, 0], [8, 4], [4, 4]])]
    openings = [
        {"id": "p_out", "room_id": "bad", "edge": 0, "offset": 0.5, "kind": "passage"},                       # passage on the south wall
        {"id": "d_in", "room_id": "flur", "edge": 1, "offset": 0.5, "kind": "door", "contacts": ["binary_sensor.innentuer"]},  # east wall
        {"id": "w_ok", "room_id": "flur", "edge": 0, "offset": 0.5, "contacts": ["binary_sensor.fenster"]},
    ]
    return _layout(rooms, openings, [], north=0.0, confirmed=True)


def test_passage_or_inside_door_drawn_on_an_outside_wall_is_a_conflict_not_an_air_path() -> None:
    live = {"bad": {"contacts": {}}, "flur": {"contacts": {"binary_sensor.innentuer": {"state": "open_unspecified"},
                                                             "binary_sensor.fenster": {"state": "closed"}},
                                                "inside_contacts": ["binary_sensor.innentuer"]}}
    result = air.air_paths(_exterior_conflicts(), live, NW)
    assert result["openings"]["p_out"]["state"] == "geometry_conflict" and result["openings"]["p_out"]["conflict"] == "passage_on_outside_wall"
    assert result["openings"]["d_in"]["conflict"] == "inside_door_on_outside_wall"
    assert _paths(result) == []                                                    # everything else closed: no outside air at all
    # the same door as an outside door (older setups, nothing configured) still is a real outside opening
    legacy = copy.deepcopy(live)
    legacy["flur"].pop("inside_contacts")
    result = air.air_paths(_exterior_conflicts(), legacy, NW)
    assert "conflict" not in result["openings"]["d_in"] and [p["kind"] for p in _paths(result)] == ["single_sided"]


def test_f06_an_inside_contact_never_opens_an_outside_opening_with_a_second_contact() -> None:
    """F06: an outside opening with an inside and an outside contact – inside open, outside closed gave an outside path."""
    rooms = [("bad", "bad", "f_g", [[0, 0], [4, 0], [4, 4], [0, 4]])]
    opening = {"id": "w", "room_id": "bad", "edge": 0, "offset": 0.5, "contacts": ["binary_sensor.innen", "binary_sensor.aussen"]}
    layout = _layout(rooms, [opening], [], north=0.0, confirmed=True)
    def live(inner, outer):
        return {"bad": {"contacts": {"binary_sensor.innen": {"state": inner}, "binary_sensor.aussen": {"state": outer}},
                        "inside_contacts": ["binary_sensor.innen"]}}
    inner_open = air.air_paths(layout, live("open_unspecified", "closed"), NW)
    assert inner_open["openings"]["w"]["state"] == "closed" and _paths(inner_open) == []
    outer_open = air.air_paths(layout, live("closed", "open_unspecified"), NW)
    assert outer_open["openings"]["w"]["state"] == "open_unspecified" and [p["kind"] for p in _paths(outer_open)] == ["single_sided"]
    legacy = live("open_unspecified", "closed"); legacy["bad"].pop("inside_contacts")
    assert air.air_paths(layout, legacy, NW)["openings"]["w"]["state"] == "open_unspecified"      # older setups: both still count
