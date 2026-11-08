"""0.26.7.0 (owner request): a compass text is a valid wind direction for the ventilation logic as on the house map."""
from __future__ import annotations

import pytest

from custom_components.freshairiq.coordinator_sources import _weather_wind


@pytest.mark.parametrize(("bearing", "expected"), [
    (250, 250.0), ("250", 250.0), ("270,5", 270.5), ("NW", 315.0), ("nnw", 337.5), ("NNO", 22.5), ("NNE", 22.5),
    ("O", 90.0), ("E", 90.0), ("SSW", 202.5), ("SW", 225.0), (360, 0.0), ("xyz", None), (400, None), (-5, None), (None, None),
])
async def test_weather_entity_bearing_number_or_compass_text(hass, bearing, expected) -> None:
    hass.states.async_set("weather.home", "rainy", {"wind_bearing": bearing, "wind_speed": 22})
    assert _weather_wind(hass, "weather.home") == (expected, 22.0)


async def test_no_entity_or_state_gives_nothing(hass) -> None:
    assert _weather_wind(hass, None) == (None, None)
    assert _weather_wind(hass, "weather.missing") == (None, None)
