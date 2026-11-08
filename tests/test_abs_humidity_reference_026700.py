"""0.26.7.0 UI hotfix: the house map's outdoor absolute humidity uses FreshAirIQ's own formula.

The weather chip and the weather window of the house map compute the absolute humidity in the browser only when the
integration's own value (``outdoor_absolute_humidity``) is missing – e.g. for a weather entity chosen in the card.
``frontend_tests/fixtures/abs_humidity_reference.json`` holds ``model.absolute_humidity`` for a grid of temperatures and
humidities; the browser test compares freshairiq-house-weather.js ``absoluteHumidity`` with it, this test proves the file is
exactly what the integration computes (no second, differing formula).
"""
from __future__ import annotations

import json
from pathlib import Path

from custom_components.freshairiq.model import absolute_humidity

FIXTURE = Path(__file__).resolve().parents[1] / "frontend_tests" / "fixtures" / "abs_humidity_reference.json"
TEMPS = [-29.5, -20.0, -5.0, 0.0, 3.7, 10.0, 18.25, 25.0, 33.3, 45.0, 59.5]
HUMS = [0.0, 1.0, 35.0, 50.0, 72.5, 99.0, 100.0]


def reference() -> list[list[float]]:
    return [[t, h, round(absolute_humidity(t, h), 9)] for t in TEMPS for h in HUMS]


def test_fixture_is_the_integrations_formula() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == reference()


def test_fixture_spans_the_valid_range() -> None:
    rows = reference()
    assert len(rows) == len(TEMPS) * len(HUMS)
    assert min(r[0] for r in rows) > -30 and max(r[0] for r in rows) < 60
    assert all(r[2] == 0 for r in rows if r[1] == 0)
