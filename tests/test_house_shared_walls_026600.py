"""Hotfix 0.26.6.0 (5): a way through a wall needs a wall the two rooms really share.

The house map's air streams use a drawn opening only when its whole span lies on the wall both rooms share,
and a door or open passage connection only where they share at least MIN_SHARED_WALL. ``validate`` reports
the plan places that do not hold (also after a room was moved): a passage off any shared wall
(``W_OPENING_NOT_SHARED``) and a door or open passage connection without such a wall (``W_CONNECTION_NO_WALL``).
Warnings never block saving. The same cases are checked in the browser against ``passage`` (shared fixture).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.freshairiq.house_layout import (
    MIN_SHARED_WALL, PHYSICAL_CONNECTIONS, errors, normalise, opening_neighbour, shared_wall_length, validate,
)

FX = json.loads((Path(__file__).resolve().parents[1] / "frontend_tests" / "fixtures" / "shared_walls.json").read_text(encoding="utf-8"))


def _layout(case: dict) -> dict:
    opening = case.get("opening")
    return normalise({
        "schema_version": 1, "revision": 1, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
        "floors": [{"id": "f", "name": "EG", "level_key": "ground_floor", "order": 0}, {"id": "g", "name": "OG", "level_key": "upper_floor", "order": 1}],
        "rooms": [{"id": "a", "room_key": "a", "floor_id": "f", "polygon": FX["room_a"]},
                  {"id": "b", "room_key": "b", "floor_id": case.get("floor_b", "f"), "polygon": case["b"]}],
        "openings": [{"id": "o", "room_id": "a", "mechanics": "unknown", "contacts": [], **opening}] if opening else [],
        "connections": [{"id": "c", "a": "a", "b": "b", "kind": case["connection"], "confirmed": True}] if case["connection"] else [],
        "shading": [],
    })


@pytest.mark.parametrize("case", FX["cases"], ids=[c["name"] for c in FX["cases"]])
def test_validate_reports_ways_through_walls_the_geometry_does_not_carry(case: dict) -> None:
    layout = _layout(case)
    issues = validate(layout, ["a", "b"])
    assert errors(issues) == []                                  # warnings only: saving stays possible
    assert sorted(i["code"] for i in issues) == sorted(case["warnings"])
    rooms = {r["id"]: r for r in layout["rooms"]}
    physical = case["connection"] in PHYSICAL_CONNECTIONS and shared_wall_length(rooms["a"], rooms["b"]) >= MIN_SHARED_WALL
    through_opening = bool(layout["openings"]) and opening_neighbour(layout, "a", layout["openings"][0]) == "b"
    assert (physical or through_opening) == (case["passage"] is not None)   # the same answer as the house map


def test_shared_wall_length_rules() -> None:
    a = {"floor_id": "f", "polygon": FX["room_a"]}
    assert shared_wall_length(a, {"floor_id": "f", "polygon": [[2, 0], [4, 0], [4, 2], [2, 2]]}) == pytest.approx(2.0)
    assert shared_wall_length(a, {"floor_id": "f", "polygon": [[2, 2], [4, 2], [4, 4], [2, 4]]}) == 0.0   # a corner
    assert shared_wall_length(a, {"floor_id": "g", "polygon": [[2, 0], [4, 0], [4, 2], [2, 2]]}) == 0.0   # another floor


def test_the_existing_plans_stay_without_warnings() -> None:
    """A valid interior door/passage and a connection on a real shared wall give no warning."""
    case = FX["cases"][0]
    assert validate(_layout(case), ["a", "b"]) == []
