"""0.26.6.0 (10): rooms fitted together in the editor have the same topology in the backend.

The browser fits the separately measured rooms of ``house_join_rooms.json`` with ``G.joinRooms`` and checks that the
result equals ``joined`` in the fixture (house.spec.mjs); here the backend reads exactly that geometry: the walls the
rooms now share are interior walls (``shared_wall_length``), the door on the shared wall links the two rooms
(``opening_neighbour``) and validation is clean. Pulled apart again, the door links nothing – no stale air path.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from custom_components.freshairiq.house_layout import MIN_SHARED_WALL, normalise, opening_neighbour, shared_wall_length, validate

FX = json.loads((Path(__file__).resolve().parents[1] / "frontend_tests" / "fixtures" / "house_join_rooms.json").read_text(encoding="utf-8"))
KEYS = ["wohnen", "kueche", "flur"]


def _layout(polygons: dict | None) -> dict:
    raw = copy.deepcopy(FX["layout"])
    for room in raw["rooms"]:
        if polygons:
            room["polygon"] = polygons[room["id"]]
    return normalise(raw)


def test_the_fitted_rooms_share_their_walls_and_the_door_links_them() -> None:
    layout = _layout(FX["joined"])
    rooms = {r["id"]: r for r in layout["rooms"]}
    for a, b in (("r_wohn", "r_kueche"), ("r_wohn", "r_flur"), ("r_kueche", "r_flur")):
        assert shared_wall_length(rooms[a], rooms[b]) >= MIN_SHARED_WALL, (a, b)
    door = next(o for o in layout["openings"] if o["id"] == "d_wk")
    window = next(o for o in layout["openings"] if o["id"] == "w_k")
    assert opening_neighbour(layout, "r_wohn", door) == "r_kueche"
    assert opening_neighbour(layout, "r_kueche", window) is None          # still on the outside wall
    assert validate(layout, KEYS) == []


def test_measured_lengths_and_locks_survive_the_fit() -> None:
    before, after = _layout(None), _layout(FX["joined"])
    for old, new in zip(before["rooms"], after["rooms"]):
        assert new.get("locked_walls") == old.get("locked_walls")
        n = len(old["polygon"])
        for i in old.get("locked_walls", []):
            la = ((old["polygon"][i][0] - old["polygon"][(i + 1) % n][0]) ** 2 + (old["polygon"][i][1] - old["polygon"][(i + 1) % n][1]) ** 2) ** 0.5
            lb = ((new["polygon"][i][0] - new["polygon"][(i + 1) % n][0]) ** 2 + (new["polygon"][i][1] - new["polygon"][(i + 1) % n][1]) ** 2) ** 0.5
            assert abs(la - lb) < 0.002


def test_pulled_apart_the_door_links_nothing() -> None:
    layout = _layout(None)
    door = next(o for o in layout["openings"] if o["id"] == "d_wk")
    assert opening_neighbour(layout, "r_wohn", door) is None
    rooms = {r["id"]: r for r in layout["rooms"]}
    assert shared_wall_length(rooms["r_wohn"], rooms["r_kueche"]) == 0.0
    assert validate(layout, KEYS) == []          # an outside door then – valid, and no air path between the two rooms


def test_locked_corners_survive_save_and_load() -> None:
    raw = copy.deepcopy(FX["layout"])
    raw["rooms"][0]["locked_corners"] = [3, 1, 1, 9, -1, True, "2"]
    out = normalise(raw)
    assert out["rooms"][0]["locked_corners"] == [1, 3]
    raw["rooms"][0]["locked_corners"] = []
    assert "locked_corners" not in normalise(raw)["rooms"][0]
