"""Hotfix 0.26.6.0 (9) F04: a wind with a direction but an unknown speed is not available.

Before, ``wind_state`` set ``available`` from direction, age and calm only – a missing speed or an unsupported speed
unit left ``available = True``, so the house map drew wind streams, the airflow model judged facades by pressure and
the dashboard animated a wind nobody measured. Now an unknown speed is its own reason (``no_speed``), different from a
measured calm; the airflow model then stays topological (no pressure-based inlet/outlet).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq import house_airflow as air
from custom_components.freshairiq import house_wind as wind
from tests.test_house_map_026504 import _house, _live


@pytest.mark.parametrize(("speed", "unit"), [(None, "m/s"), ("unknown", "km/h"), (12, "furlong/fortnight"), (float("nan"), "m/s"), (-3, "m/s")])
def test_an_unknown_speed_is_not_available_and_not_calm(speed, unit) -> None:
    state = wind.wind_state(bearing=270, speed=speed, unit=unit)
    assert (state["available"], state["reason"], state["calm"], state["speed_ms"]) == (False, "no_speed", False, None)
    assert state["from_deg"] == 270.0                       # the direction itself is still published
    assert wind.facade_exposure(0, state) == {"exposure": "unknown", "angle_deg": None, "pressure": None}


def test_calm_stale_direction_and_valid_wind_keep_their_meaning() -> None:
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    assert wind.wind_state(bearing=270, speed=0.2, unit="m/s")["reason"] == "calm"          # a measured calm
    assert wind.wind_state(bearing=None, speed=None)["reason"] == "no_direction"            # direction first
    assert wind.wind_state(bearing=270, speed=5, unit="m/s", observed_at=now - timedelta(hours=4), now=now)["reason"] == "stale"
    ok = wind.wind_state(bearing=270, speed=18, unit=None)                                   # missing unit: HA default km/h
    assert (ok["available"], ok["unit_assumed"], ok["speed_ms"]) == (True, True, 5.0)


def test_the_airflow_model_does_not_judge_facades_without_a_speed() -> None:
    result = air.air_paths(_house(), _live(bad="open", wohnen="open"), wind.wind_state(bearing=315, speed=None, unit="m/s"))
    assert result["model_level"] == "topology_only"
    assert all(o.get("pressure") is None for o in result["openings"].values())
    assert not any(p["direction"] == "directed" for p in result["paths"])                    # no invented cross flow
    measured = air.air_paths(_house(), _live(bad="open", wohnen="open"), wind.wind_state(bearing=315, speed=5, unit="m/s"))
    assert measured["model_level"] != "topology_only"
