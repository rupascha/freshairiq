"""Current weather situation for the dashboard mascot (0.26.4.8).

Until 0.26.4.7 the dashboard showed Freshy with a leaf umbrella whenever the
night strategy expected rain at some point during the coming night (forecast
probability ≥ 55 %). That was true on many dry evenings, so the "rain" picture
appeared far too often. The mascot now reacts to the weather *now* and to rain
that really starts soon:

* ``raining`` / ``snowing`` / ``thunder`` – from the weather entity's current
  condition (``rainy``, ``pouring``, ``snowy`` …);
* ``rain_in_min`` – minutes until the first forecast hour with real
  precipitation (≥ 0.3 mm or ≥ 70 % or a rainy condition) inside the next two
  hours; ``0`` while it rains;
* ``frost`` / ``heat`` – from the outdoor temperature.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

RAIN_CONDITIONS = frozenset({"rainy", "pouring", "lightning-rainy", "hail", "snowy-rainy"})
SNOW_CONDITIONS = frozenset({"snowy", "snowy-rainy"})
THUNDER_CONDITIONS = frozenset({"lightning", "lightning-rainy"})
RAIN_SOON_WINDOW_MIN = 120
RAIN_SOON_MM = 0.3
RAIN_SOON_PROBABILITY = 70.0
FROST_C = 0.0
HEAT_C = 28.0


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN guard


def _rain_row(row: dict[str, Any]) -> bool:
    return (
        (_num(row.get("precipitation_mm")) or 0.0) >= RAIN_SOON_MM
        or (_num(row.get("precipitation_probability")) or 0.0) >= RAIN_SOON_PROBABILITY
        or str(row.get("condition") or "") in RAIN_CONDITIONS
    )


def minutes_until_rain(rows: Any, now: datetime, window_min: int = RAIN_SOON_WINDOW_MIN) -> int | None:
    """Minutes until the first hourly forecast slot with real precipitation."""
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = row.get("datetime")
        if not isinstance(start, datetime):
            continue
        # An hourly slot covers [start, start + 60 min): the current hour counts as now.
        delta = (start - now).total_seconds() / 60.0
        if delta < -60:
            continue
        if delta > window_min:
            break
        if _rain_row(row):
            return max(0, int(round(delta)))
    return None


def weather_now(condition: Any, rows: Any, now: datetime, outdoor_temperature: Any) -> dict[str, Any]:
    """Compact, display-only description of the current outdoor situation."""
    state = str(condition or "").strip().lower() or None
    if state in {"unknown", "unavailable"}:
        state = None
    raining = state in RAIN_CONDITIONS
    temperature = _num(outdoor_temperature)
    rain_in = 0 if raining else minutes_until_rain(rows, now)
    return {
        "condition": state,
        "raining": raining,
        "snowing": state in SNOW_CONDITIONS,
        "thunder": state in THUNDER_CONDITIONS,
        "rain_in_min": rain_in,
        "rain_soon": rain_in is not None and not raining,
        "outdoor_temperature": round(temperature, 1) if temperature is not None else None,
        "frost": temperature is not None and temperature <= FROST_C,
        "heat": temperature is not None and temperature >= HEAT_C,
    }
