"""Focused notification-format tests without a Home Assistant runtime."""
from __future__ import annotations

import sys
import types

if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:  # pragma: no cover - type placeholder only
        pass

    core.HomeAssistant = HomeAssistant
    ha.core = core
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core

from custom_components.freshairiq.notifications import _continuation


def test_continuation_uses_configured_horizon_and_matching_values():
    text = _continuation({
        "forecast_horizon_min": 15,
        "forecast_moisture_effect_ml": 123,
        "forecast_temperature_change_c": -0.8,
        "forecast_cost": 0.07,
        # Deliberately conflicting legacy 5-minute values: these must not leak.
        "next_5_min_ml": 9,
        "temp_next_5_min_c": -0.1,
        "next_5_min_cost": 0.01,
    })
    assert "Weitere 15 Min" in text
    assert "−123 ml" in text
    assert "−0.8 °C" in text
    assert "0.07 €" in text
    assert "Weitere 5 Min" not in text
