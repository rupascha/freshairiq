"""0.26.6.0 UI hotfix (F01): an interior door or passage never silently becomes an outside opening.

The editor marks doors and passages it places between two rooms with ``interior: true``. ``validate`` refuses
such an opening (error ``E_OPENING_INTERIOR`` – saving is blocked) when its span no longer lies on a wall
shared with another room, e.g. after it was moved onto an outside wall. Plans without the flag keep the
earlier behaviour (a passage off a shared wall is only a warning). The browser side has the same rule
(G.validateLayout) and refuses such a move while dragging (frontend_tests/house.spec.mjs).
"""
from __future__ import annotations

import copy

from custom_components.freshairiq.house_layout import errors, normalise, validate

BASE = {
    "schema_version": 1, "revision": 2, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
    "floors": [{"id": "f", "name": "EG", "level_key": "ground_floor", "order": 0}],
    "rooms": [{"id": "a", "room_key": "a", "floor_id": "f", "polygon": [[0, 0], [4, 0], [4, 3], [0, 3]]},
              {"id": "b", "room_key": "b", "floor_id": "f", "polygon": [[4, 0], [7, 0], [7, 3], [4, 3]]}],
    # edge 1 of room a is the wall a and b share
    "openings": [{"id": "d", "room_id": "a", "edge": 1, "offset": 0.5, "width_m": 0.9, "kind": "door", "mechanics": "door", "contacts": [], "interior": True}],
    "connections": [], "shading": [],
}


def test_an_interior_door_on_the_shared_wall_is_valid() -> None:
    layout = normalise(copy.deepcopy(BASE))
    assert layout["openings"][0]["interior"] is True
    assert validate(layout, ["a", "b"]) == []


def test_an_interior_door_moved_onto_an_outside_wall_blocks_saving() -> None:
    raw = copy.deepcopy(BASE)
    raw["openings"][0]["edge"] = 3   # the left outside wall of room a
    issues = validate(normalise(raw), ["a", "b"])
    assert errors(issues) == [{"code": "E_OPENING_INTERIOR", "object": "opening", "id": "d"}]


def test_without_the_flag_nothing_changes_for_older_plans() -> None:
    raw = copy.deepcopy(BASE)
    raw["openings"][0].pop("interior")
    raw["openings"][0]["edge"] = 3
    assert errors(validate(normalise(raw), ["a", "b"])) == []          # an outside door, as before
    raw["openings"][0]["interior"] = "yes"                               # only True counts
    out = normalise(raw)
    assert "interior" not in out["openings"][0] and errors(validate(out, ["a", "b"])) == []
