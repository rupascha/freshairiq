"""House map editor (owner request 31.10.): interior doors and passages placed on a wall between two rooms.

The editor stores them as ordinary openings (kind door / passage) on the shared wall; the air-path model must
read them as the link of both rooms – a passage always open, a door by its contact – and never as an outside
opening with a facade.
"""
from __future__ import annotations

from custom_components.freshairiq.house_airflow import _openings, air_paths
from custom_components.freshairiq.house_layout import normalise, validate

LAYOUT = normalise({
    "schema_version": 1, "revision": 1, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
    "floors": [{"id": "f", "name": "EG", "level_key": "ground_floor", "order": 0}],
    "rooms": [{"id": "r_bad", "room_key": "bad", "floor_id": "f", "polygon": [[0, 4], [4, 4], [4, 8], [0, 8]]},
              {"id": "r_flur", "room_key": "flur", "floor_id": "f", "polygon": [[0, 0], [8, 0], [8, 4], [0, 4]]}],
    # what the editor's "Tap an interior door" / "Tap a passage" produce (edge 0 of the bath is the shared wall)
    "openings": [{"id": "o_door", "room_id": "r_bad", "edge": 0, "offset": 0.65, "width_m": 0.9, "kind": "door", "mechanics": "door",
                  "contacts": ["binary_sensor.bad_tuer"], "provenance": "user"},
                 {"id": "o_pass", "room_id": "r_flur", "edge": 2, "offset": 0.8, "width_m": 1.0, "kind": "passage", "mechanics": "unknown",
                  "contacts": [], "provenance": "user"}],
    "connections": [], "shading": [],
})


def test_interior_openings_are_valid_and_link_both_rooms() -> None:
    assert validate(LAYOUT, ["bad", "flur"]) == []
    live = {"bad": {"contacts": {"binary_sensor.bad_tuer": {"state": "open", "pending": False, "three_state": False}}}}
    found = _openings(LAYOUT, live, {"available": False})
    assert found["o_door"]["target"] == "r_flur" and found["o_door"]["exposure"] == "interior" and found["o_door"]["facade_deg"] is None
    assert found["o_pass"]["target"] == "r_bad" and found["o_pass"]["state"] == "open" and found["o_pass"]["size"] == "large"
    closed = _openings(LAYOUT, {"bad": {"contacts": {"binary_sensor.bad_tuer": {"state": "closed", "pending": False}}}}, {"available": False})
    assert closed["o_door"]["state"] == "closed"
    result = air_paths(LAYOUT, live, {"available": False})
    assert set(result["openings"]) == {"o_door", "o_pass"}


# --- hotfix F01/F05: one rule for the editor and the air paths (shared fixture with frontend_tests) ----------
import json
from pathlib import Path

import pytest

from custom_components.freshairiq.house_layout import opening_neighbour, opening_samples

FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "frontend_tests" / "fixtures" / "interior_openings.json").read_text())


def _pair(case):
    opening = {"id": "o", "room_id": "a", "kind": "passage", "contacts": [], **case["opening"]}
    layout = normalise({"schema_version": 1, "floors": [{"id": "f"}], "openings": [opening], "connections": [],
                        "rooms": [{"id": "a", "room_key": "a", "floor_id": "f", "polygon": FIXTURE["room_a"]},
                                  {"id": "b", "room_key": "b", "floor_id": "f", "polygon": case["b"]}]})
    return layout, layout["openings"][0]


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: c["name"])
def test_an_interior_opening_needs_its_whole_span_on_the_other_rooms_wall(case) -> None:
    layout, opening = _pair(case)
    assert opening_neighbour(layout, "a", opening) == case["target"]
    target = air_paths(layout, {}, {"available": False})["openings"]["o"]["target"]
    assert target == (case["target"] or "outside")


def test_rule_edges() -> None:
    layout, opening = _pair(FIXTURE["cases"][0])
    assert opening_neighbour(layout, "missing", opening) is None
    other_floor = dict(layout, rooms=[layout["rooms"][0], dict(layout["rooms"][1], floor_id="g")])
    assert opening_neighbour(other_floor, "a", opening) is None
    samples = opening_samples([tuple(p) for p in FIXTURE["room_a"]], {"edge": 1, "offset": None, "width_m": 0.4})
    assert samples[0] == pytest.approx((2.0, 0.8)) and samples[-1] == pytest.approx((2.0, 1.2))
