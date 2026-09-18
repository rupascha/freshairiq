"""Coverage and non-finite hardening for energy/cost calculations."""
from __future__ import annotations

import math

from custom_components.freshairiq.energy import (
    energy_price_per_kwh_equivalent,
    exchanged_air_fraction,
    heating_cost_context,
    purchased_energy_kwh,
    ventilation_cost_for_duration,
    ventilation_cost_for_temperature_path,
    ventilation_heat_energy_kwh,
)


def test_energy_systems_and_contexts_cover_all_supported_heating_modes():
    delivered = 10.0
    systems = {
        "heat_pump": ({"heating_system": "heat_pump", "heat_pump_cop": 4}, 2.5, "kWh Strom"),
        "gas": ({"heating_system": "gas", "gas_efficiency": 0.8}, 12.5, "kWh Gas"),
        "oil": ({"heating_system": "oil", "oil_efficiency": 0.8, "oil_kwh_per_liter": 10}, 12.5, "l"),
        "district_heating": ({"heating_system": "district_heating", "district_efficiency": 0.8}, 12.5, "kWh"),
        "electric": ({"heating_system": "electric"}, 10.0, "kWh Strom"),
    }
    for options, expected, unit in systems.values():
        assert purchased_energy_kwh(delivered, options) == expected
        assert heating_cost_context(delivered, options)["unit"] == unit
    assert purchased_energy_kwh(0, {}) == 0.0


def test_energy_price_uses_system_specific_sources_and_safe_defaults():
    assert energy_price_per_kwh_equivalent({"heating_system": "gas", "gas_price_per_kwh": 0.12}) == 0.12
    assert energy_price_per_kwh_equivalent({"heating_system": "district_heating", "district_price_per_kwh": 0.2}) == 0.2
    assert energy_price_per_kwh_equivalent({"heating_system": "oil", "oil_price_per_liter": 1.2, "oil_kwh_per_liter": 10}) == 0.12
    assert energy_price_per_kwh_equivalent({"heating_system": "electric", "electricity_price_per_kwh": 0.3}) == 0.3
    assert energy_price_per_kwh_equivalent({"heating_system": "unknown", "energy_price_per_kwh": 0.4}) == 0.4


def test_non_finite_energy_inputs_degrade_to_finite_neutral_values():
    values = [
        exchanged_air_fraction(float("nan"), float("inf"), float("nan")),
        ventilation_heat_energy_kwh(float("nan"), 21, float("inf"), float("nan")),
        purchased_energy_kwh(float("nan"), {"heating_system": "heat_pump", "heat_pump_cop": float("nan")}),
        energy_price_per_kwh_equivalent({"heating_system": "gas", "gas_price_per_kwh": float("nan")}),
    ]
    assert all(math.isfinite(v) for v in values)
    assert all(v >= 0 for v in values)


def test_duration_cost_only_counts_positive_heating_delta():
    options = {"heating_system": "electric", "electricity_price_per_kwh": 0.3}
    cold = ventilation_cost_for_duration(100, 21, 0, 0.05, 10, 1.0, options)
    hot = ventilation_cost_for_duration(100, 21, 30, 0.05, 10, 1.0, options)
    assert cold[0] > 0
    assert hot == (0.0, 0.0, 0.0)


def test_temperature_path_cost_skips_bad_rows_and_uses_each_slice():
    options = {"heating_system": "electric", "electricity_price_per_kwh": 0.3}
    path = [
        {"duration_min": 5, "room_start_c": 21, "source_c": 10},
        {"duration_min": 5, "room_start_c": 20, "source_c": 12},
        {"duration_min": -1, "room_start_c": 20, "source_c": 0},
        {"duration_min": "bad", "room_start_c": 20, "source_c": 0},
    ]
    delivered, purchased, cost = ventilation_cost_for_temperature_path(80, 0.04, 1.0, path, options)
    assert delivered > 0
    assert purchased == delivered
    assert cost > 0
    assert ventilation_cost_for_temperature_path(80, 0.04, 1.0, None, options) == (0.0, 0.0, 0.0)
