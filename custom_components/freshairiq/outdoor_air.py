"""Outdoor fine-dust (PM2.5) protection for FreshAirIQ (0.26.4.7).

User wish (feedback 2026-10-08): "Luftsensor draußen – bei Sensoren für draußen
auch Sensoren von draußen einbinden, um nicht schlechte Luft von draußen nach
drinnen zu holen. Sensor Community bietet die regionale Feinstaubbelastung an."

Works exactly like the pollen rule: when the outdoor PM2.5 value is above the
configured limit, a normal airing recommendation is postponed ("Fenster vorerst
geschlossen lassen"). Health-critical situations (critical CO₂, critical
surface humidity) keep priority – the room then still gets a short, necessary
air exchange. Nothing happens unless at least one outdoor PM2.5 sensor is
selected. Several sensors may be selected; the highest valid value counts.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

DEFAULT_OUTDOOR_PM25_MAX = 35.0  # µg/m³, upper end of "moderate" in common AQI scales
OUTDOOR_PM25_PLAUSIBLE_MAX = 1000.0


def plausible_pm25(value: Any) -> float | None:
    """A PM2.5 reading in µg/m³, or ``None`` when missing/implausible."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number < 0 or number > OUTDOOR_PM25_PLAUSIBLE_MAX:
        return None
    return number


def outdoor_pm25_limit(options: dict[str, Any]) -> float:
    limit = plausible_pm25(options.get("outdoor_pm25_max", DEFAULT_OUTDOOR_PM25_MAX))
    return limit if limit is not None and limit > 0 else DEFAULT_OUTDOOR_PM25_MAX


def outdoor_pm25_blocked(options: dict[str, Any], pm25: Any) -> bool:
    """True when outdoor fine dust should postpone normal (non-urgent) airing."""
    if not bool(options.get("outdoor_pm25_enabled", True)):
        return False
    value = plausible_pm25(pm25)
    return value is not None and value > outdoor_pm25_limit(options)


def veto_cause(pollen_blocked: bool, pm25_blocked: bool) -> str | None:
    """Machine-readable cause of an outdoor-air veto."""
    if pollen_blocked and pm25_blocked:
        return "pollen_and_pm25"
    if pm25_blocked:
        return "pm25"
    if pollen_blocked:
        return "pollen"
    return None


def pm25_reason(pm25: Any, options: dict[str, Any]) -> str:
    value = plausible_pm25(pm25) or 0.0
    return f"Feinstaub draußen (PM2.5) {value:.0f} µg/m³ liegt über dem eingestellten Grenzwert {outdoor_pm25_limit(options):.0f} µg/m³"
