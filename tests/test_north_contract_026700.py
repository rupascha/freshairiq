"""0.26.7.0: north_deg is the compass bearing the plan's top faces – one contract for facades, wind and sun.

The same table is checked in the browser (frontend_tests/house.spec.mjs, NORTH_CONTRACT) against the JavaScript
geometry; both sides must give the same bearing for the same plan direction.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.house_layout import normal_bearing

NORTH_CONTRACT = [(0, (0, 1), 0), (0, (1, 0), 90), (90, (0, 1), 90), (90, (1, 0), 180), (180, (0, 1), 180), (270, (0, 1), 270),
                  (270, (-1, 0), 180), (345, (0, 1), 345), (345, (0, -1), 165)]


@pytest.mark.parametrize(("north", "normal", "bearing"), NORTH_CONTRACT)
def test_plan_directions_face_the_same_compass_bearing_as_in_the_browser(north, normal, bearing) -> None:
    assert round(normal_bearing(normal, north)) % 360 == bearing


def test_the_browser_table_is_the_same_table() -> None:
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "frontend_tests/house.spec.mjs").read_text(encoding="utf-8")
    js = "[" + ", ".join(f"[{n}, [{v[0]}, {v[1]}], {b}]" for n, v, b in NORTH_CONTRACT) + "]"
    assert f"const NORTH_CONTRACT = {js};" in text
