"""Pure energy/cost calculations used by FreshAirIQ."""
from __future__ import annotations
from typing import Any

from .robustness import finite_float

AIR_DENSITY_KG_M3 = 1.204
AIR_CP_KJ_KG_K = 1.005
KJ_PER_KWH = 3600.0
AIR_HEAT_CAPACITY_KWH_M3K = AIR_DENSITY_KG_M3 * AIR_CP_KJ_KG_K / KJ_PER_KWH


def exchanged_air_fraction(rate_per_min: float, minutes: float, bonus: float = 1.0) -> float:
    """Learned exchanged-air fraction, bounded to a physically plausible range."""
    rate = min(max(finite_float(rate_per_min, 0.0) or 0.0, 0.0), 0.95)
    minutes = max(finite_float(minutes, 0.0) or 0.0, 0.0)
    effective = min(rate * max(finite_float(bonus, 0.0) or 0.0, 0.0), 0.95)
    # Same exponential replacement model used by the supplied V14.2.1 YAML
    # for full-session predictions. This avoids linear overestimation at long durations.
    return min(max(1.0 - ((1.0 - effective) ** minutes), 0.0), 0.95)


def ventilation_heat_energy_kwh(volume_m3: float, indoor_c: float, source_c: float, exchange_fraction: float) -> float:
    """Sensible heat carried by exchanged air; not building thermal mass."""
    volume = max(finite_float(volume_m3, 0.0) or 0.0, 0.0)
    fraction = min(max(finite_float(exchange_fraction, 0.0) or 0.0, 0.0), 1.0)
    indoor = finite_float(indoor_c, 0.0) or 0.0
    source = finite_float(source_c, indoor)
    exchanged_volume = volume * fraction
    return exchanged_volume * AIR_HEAT_CAPACITY_KWH_M3K * abs(indoor - (source if source is not None else indoor))


def purchased_energy_kwh(delivered_heat_kwh: float, options: dict[str, Any]) -> float:
    """Purchased energy equivalent in kWh for the selected heating system."""
    system = options.get("heating_system", "heat_pump")
    delivered_heat_kwh = finite_float(delivered_heat_kwh, 0.0) or 0.0
    if delivered_heat_kwh <= 0:
        return 0.0
    if system == "heat_pump":
        return delivered_heat_kwh / max(finite_float(options.get("heat_pump_cop", 3.5), 3.5) or 3.5, 1.0)
    if system == "gas":
        eff = finite_float(options.get("gas_efficiency", options.get("heating_efficiency", 0.92)), 0.92) or 0.92
        return delivered_heat_kwh / min(max(eff, 0.5), 1.0)
    if system == "oil":
        eff = finite_float(options.get("oil_efficiency", options.get("heating_efficiency", 0.88)), 0.88) or 0.88
        return delivered_heat_kwh / min(max(eff, 0.5), 1.0)
    if system == "district_heating":
        eff = finite_float(options.get("district_efficiency", options.get("heating_efficiency", 0.98)), 0.98) or 0.98
        return delivered_heat_kwh / min(max(eff, 0.5), 1.0)
    return delivered_heat_kwh


def energy_price_per_kwh_equivalent(options: dict[str, Any]) -> float:
    """Return a comparable purchased-energy price for the selected system."""
    system = options.get("heating_system", "heat_pump")
    if system in {"heat_pump", "electric"}:
        return max(finite_float(options.get("electricity_price_per_kwh", options.get("energy_price_per_kwh", 0.30)), 0.30) or 0.0, 0.0)
    if system == "gas":
        return max(finite_float(options.get("gas_price_per_kwh", 0.11), 0.11) or 0.0, 0.0)
    if system == "district_heating":
        return max(finite_float(options.get("district_price_per_kwh", 0.15), 0.15) or 0.0, 0.0)
    if system == "oil":
        liters_kwh = max(finite_float(options.get("oil_kwh_per_liter", 10.0), 10.0) or 10.0, 0.1)
        return max(finite_float(options.get("oil_price_per_liter", 1.0), 1.0) or 0.0, 0.0) / liters_kwh
    return max(finite_float(options.get("energy_price_per_kwh", 0.30), 0.30) or 0.0, 0.0)


def ventilation_cost(volume_m3: float, indoor_c: float, source_c: float, exchange_fraction: float, options: dict[str, Any]) -> tuple[float, float, float]:
    """Return delivered heat, purchased energy-equivalent and reheating cost."""
    delivered = ventilation_heat_energy_kwh(volume_m3, indoor_c, source_c, exchange_fraction)
    purchased = purchased_energy_kwh(delivered, options)
    cost = purchased * energy_price_per_kwh_equivalent(options)
    return round(delivered, 4), round(purchased, 4), round(cost, 4)


def heating_cost_context(delivered_heat_kwh: float, options: dict[str, Any]) -> dict[str, Any]:
    """Human-facing, heating-system-specific fuel/energy context."""
    system = options.get("heating_system", "heat_pump")
    purchased = purchased_energy_kwh(delivered_heat_kwh, options)
    if system == "oil":
        kwh_l = max(finite_float(options.get("oil_kwh_per_liter", 10.0), 10.0) or 10.0, 0.1)
        amount = purchased / kwh_l
        return {"amount": round(amount, 4), "unit": "l", "label": "Heizöl"}
    if system == "gas":
        return {"amount": round(purchased, 4), "unit": "kWh Gas", "label": "Gas"}
    if system == "district_heating":
        return {"amount": round(purchased, 4), "unit": "kWh", "label": "Fernwärme"}
    return {"amount": round(purchased, 4), "unit": "kWh Strom", "label": "Strom"}


def ventilation_cost_for_duration(
    volume_m3: float,
    indoor_c: float,
    source_c: float,
    rate_per_min: float,
    minutes: float,
    bonus: float,
    options: dict[str, Any],
) -> tuple[float, float, float]:
    """Cumulative sensible ventilation heat load for an arbitrary duration.

    Concentration forecasts saturate because room air approaches source air.
    Energy loss does not: every additional parcel of incoming cold air must be
    heated again.  Therefore this uses cumulative exchanged volume instead of
    the concentration replacement fraction.
    """
    minutes = max(finite_float(minutes, 0.0) or 0.0, 0.0)
    rate = finite_float(rate_per_min, 0.0) or 0.0
    airflow_bonus = finite_float(bonus, 0.0) or 0.0
    effective_rate = min(max(rate * max(airflow_bonus, 0.0), 0.0), 0.95)
    volume = max(finite_float(volume_m3, 0.0) or 0.0, 0.0)
    indoor = finite_float(indoor_c, 0.0) or 0.0
    source = finite_float(source_c, indoor)
    exchanged_volume = volume * effective_rate * minutes
    delivered = exchanged_volume * AIR_HEAT_CAPACITY_KWH_M3K * max(indoor - (source if source is not None else indoor), 0.0)
    purchased = purchased_energy_kwh(delivered, options)
    cost = purchased * energy_price_per_kwh_equivalent(options)
    return round(delivered, 4), round(purchased, 4), round(cost, 4)


def ventilation_cost_for_temperature_path(
    volume_m3: float,
    rate_per_min: float,
    bonus: float,
    temperature_path: list[dict[str, Any]] | None,
    options: dict[str, Any],
) -> tuple[float, float, float]:
    """Cumulative reheating load from the rolling forecast temperature path.

    Each simulation slice uses the *predicted room temperature at the start of
    that slice* and the weather/reference temperature valid for that future
    slice. This keeps the energy/cost forecast consistent with the rolling
    moisture/temperature model instead of pricing the whole horizon against
    today's single temperature difference.
    """
    if not temperature_path:
        return 0.0, 0.0, 0.0
    volume = max(finite_float(volume_m3, 0.0) or 0.0, 0.0)
    rate = finite_float(rate_per_min, 0.0) or 0.0
    airflow_bonus = finite_float(bonus, 0.0) or 0.0
    effective_rate = min(max(rate * max(airflow_bonus, 0.0), 0.0), 0.95)
    delivered = 0.0
    for row in temperature_path:
        try:
            minutes = max(float(row.get("duration_min", 0.0)), 0.0)
            room_start = float(row.get("room_start_c"))
            source = float(row.get("source_c"))
        except (TypeError, ValueError, OverflowError):
            continue
        if minutes <= 0.0:
            continue
        exchanged_volume = volume * effective_rate * minutes
        delivered += exchanged_volume * AIR_HEAT_CAPACITY_KWH_M3K * max(room_start - source, 0.0)
    purchased = purchased_energy_kwh(delivered, options)
    cost = purchased * energy_price_per_kwh_equivalent(options)
    return round(delivered, 4), round(purchased, 4), round(cost, 4)
