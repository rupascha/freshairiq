"""Wind for the house map: direction, speed units, age and facade exposure (pure).

Meteorological convention: the bearing says where the wind comes **from**
(0/360 = north, 90 = east); the air moves towards ``(bearing + 180) % 360``.
Speeds are converted to m/s for a known unit only; an unsupported unit leaves
the speed unknown instead of guessing. The result is presentation only – the
ventilation decision keeps its own wind input.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

POINTS_16_EN = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
POINTS_16_DE = ("N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
_TEXT_BEARINGS = {**{p: i * 22.5 for i, p in enumerate(POINTS_16_EN)}, **{p: i * 22.5 for i, p in enumerate(POINTS_16_DE)}}
_TO_MS = {"m/s": 1.0, "km/h": 1 / 3.6, "mph": 0.44704, "kn": 0.514444, "kt": 0.514444, "knots": 0.514444, "ft/s": 0.3048}
CALM_MS = 0.5
STALE_AFTER_S = 3 * 3600
WINDWARD_MAX_DEG = 45.0
LEEWARD_MIN_DEG = 135.0


def parse_bearing(value: Any) -> float | None:
    """Degrees 0–360 from a number, a numeric text or a 16-point compass text (EN/DE)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().upper()
        if text in _TEXT_BEARINGS:
            return _TEXT_BEARINGS[text]
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return None
    if not math.isfinite(number) or number < 0 or number > 360:
        return None
    return number % 360.0


def speed_ms(value: Any, unit: Any) -> tuple[float | None, bool]:
    """Speed in m/s and whether the unit was assumed (missing unit → km/h, the HA weather default)."""
    if value is None or isinstance(value, bool):
        return None, False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, False
    if not math.isfinite(number) or number < 0:
        return None, False
    if unit in (None, ""):
        return number / 3.6, True
    factor = _TO_MS.get(str(unit).strip().lower())
    return (number * factor, False) if factor is not None else (None, False)


def compass_label(bearing: float | None, language: str = "en") -> str | None:
    if bearing is None:
        return None
    points = POINTS_16_DE if language == "de" else POINTS_16_EN
    return points[int(((bearing % 360.0) + 11.25) // 22.5) % 16]


def angle_between(first: float, second: float) -> float:
    """Smallest angle between two bearings (0–180)."""
    diff = abs((first - second) % 360.0)
    return 360.0 - diff if diff > 180.0 else diff


def wind_state(*, bearing: Any, speed: Any, unit: Any = None, gust: Any = None, source: str | None = None,
               observed_at: datetime | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Normalised wind for the map, with the reason when it cannot be shown."""
    from_deg = parse_bearing(bearing)
    ms, assumed = speed_ms(speed, unit)
    gust_ms, _ = speed_ms(gust, unit)
    age = (now - observed_at).total_seconds() if isinstance(now, datetime) and isinstance(observed_at, datetime) else None
    stale = age is not None and age > STALE_AFTER_S
    calm = ms is not None and ms < CALM_MS
    if from_deg is None:
        reason = "no_direction"
    elif ms is None:  # Hotfix (9) F04: speed missing or in an unsupported unit – unknown, not calm and not shown
        reason = "no_speed"
    elif stale:
        reason = "stale"
    elif calm:
        reason = "calm"
    else:
        reason = None
    return {
        "available": reason is None,
        "reason": reason,
        "from_deg": round(from_deg, 1) if from_deg is not None else None,
        "to_deg": round((from_deg + 180.0) % 360.0, 1) if from_deg is not None else None,
        "speed_ms": round(ms, 2) if ms is not None else None,
        "gust_ms": round(gust_ms, 2) if gust_ms is not None else None,
        "unit": None if unit in (None, "") else str(unit),
        "unit_assumed": assumed,
        "calm": calm,
        "stale": stale,
        "age_s": round(age) if age is not None else None,
        "source": source,
        "observed_at": observed_at.isoformat() if isinstance(observed_at, datetime) else None,
        "label_en": compass_label(from_deg, "en"),
        "label_de": compass_label(from_deg, "de"),
    }


def facade_exposure(facade_deg: float | None, wind: dict[str, Any]) -> dict[str, Any]:
    """Qualitative wind exposure of a wall whose outside faces ``facade_deg``.

    ``windward`` (wind hits the wall within 45°), ``leeward`` (wall faces away,
    more than 135°), ``side`` in between, ``calm``/``unknown`` without usable wind
    or orientation. ``pressure`` is cos(angle) as a relative, unitless hint – not
    a measured pressure coefficient.
    """
    if facade_deg is None or not wind.get("available"):
        return {"exposure": "calm" if wind.get("calm") else "unknown", "angle_deg": None, "pressure": None}
    angle = angle_between(float(facade_deg), float(wind["from_deg"]))
    exposure = "windward" if angle <= WINDWARD_MAX_DEG else "leeward" if angle >= LEEWARD_MIN_DEG else "side"
    return {"exposure": exposure, "angle_deg": round(angle, 1), "pressure": round(math.cos(math.radians(angle)), 2)}
