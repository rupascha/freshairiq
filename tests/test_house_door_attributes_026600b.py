"""0.26.6.0(2): door hinge and swing per opening, locked wall lengths per room – layout schema contract.

``door_hinge`` (left/right, seen from inside the room the door belongs to) and ``door_swing`` (in/out) on an
opening, ``locked_walls`` (edge indices) on a room. Valid values are kept through normalise (saving, loading,
import), unknown values are dropped (the door is then drawn as before), and plans without these attributes
load unchanged – nothing is added, no door moves. The editor and the house map read the same attributes
(frontend_tests/house.spec.mjs).
"""
from __future__ import annotations

import copy

from custom_components.freshairiq.house_layout import DOOR_HINGES, DOOR_SWINGS, errors, normalise, validate

BASE = {
    "schema_version": 1, "revision": 2, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
    "floors": [{"id": "f", "name": "EG", "level_key": "ground_floor", "order": 0}],
    "rooms": [{"id": "a", "room_key": "a", "floor_id": "f", "polygon": [[0, 0], [4, 0], [4, 3], [0, 3]]},
              {"id": "b", "room_key": "b", "floor_id": "f", "polygon": [[4, 0], [7, 0], [7, 3], [4, 3]]}],
    "openings": [{"id": "d", "room_id": "a", "edge": 1, "offset": 0.5, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": []}],
    "connections": [], "shading": [],
}


def test_old_plans_load_unchanged() -> None:
    out = normalise(copy.deepcopy(BASE))
    assert "door_hinge" not in out["openings"][0] and "door_swing" not in out["openings"][0]
    assert all("locked_walls" not in room for room in out["rooms"])
    assert out["openings"][0]["offset"] == 0.5 and out["rooms"][0]["polygon"] == BASE["rooms"][0]["polygon"]
    assert validate(out, ["a", "b"]) == []


def test_valid_door_attributes_and_locks_survive_save_and_load() -> None:
    raw = copy.deepcopy(BASE)
    raw["openings"][0].update(door_hinge="right", door_swing="out")
    raw["rooms"][0]["locked_walls"] = [2, 0, 2]
    out = normalise(normalise(raw))   # saved, then loaded again
    assert (out["openings"][0]["door_hinge"], out["openings"][0]["door_swing"]) == ("right", "out")
    assert out["rooms"][0]["locked_walls"] == [0, 2]
    assert errors(validate(out, ["a", "b"])) == []
    assert DOOR_HINGES == ("left", "right") and DOOR_SWINGS == ("in", "out")


def test_unknown_values_are_dropped_not_guessed() -> None:
    raw = copy.deepcopy(BASE)
    raw["openings"][0].update(door_hinge="up", door_swing=3)
    raw["rooms"][0]["locked_walls"] = [7, -1, True, "1"]
    raw["rooms"][1]["locked_walls"] = "all"
    out = normalise(raw)
    assert "door_hinge" not in out["openings"][0] and "door_swing" not in out["openings"][0]
    assert "locked_walls" not in out["rooms"][0] and "locked_walls" not in out["rooms"][1]
