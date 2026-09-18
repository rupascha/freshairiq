"""FreshAirIQ seasonal and long-term learning.

The model separates recent seasonal behaviour from a slowly changing long-term
baseline. Stored observations decay by age when used, so stale years never keep
the same influence forever.
"""
from __future__ import annotations

from datetime import datetime
from math import exp, isfinite, log
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def season_key(when: datetime) -> str:
    """Meteorological season; simple and location-independent."""
    m = int(when.month)
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    return "autumn"


def ensure_seasonal_defaults(room: dict[str, Any]) -> None:
    defaults = {
        "seasonal_source_profiles": {},
        "seasonal_samples": 0,
        "long_term_source_ml_min": None,
        "long_term_source_samples": 0,
        "long_term_updated_at": None,
        "seasonal_observation_days": {},
    }
    for key, value in defaults.items():
        room.setdefault(key, value.copy() if isinstance(value, dict) else value)


def _ewma(old: float | None, value: float, samples: int, *, slow: bool = False) -> float:
    if old is None or samples <= 0:
        return value
    if slow:
        alpha = 0.10 if samples < 20 else 0.045
    else:
        alpha = 0.24 if samples < 8 else 0.12 if samples < 30 else 0.065
    return float(old) * (1.0 - alpha) + value * alpha


def learn_seasonal_source(room: dict[str, Any], when: datetime, source_ml_min: float) -> None:
    """Update current-season profile and slow long-term baseline."""
    ensure_seasonal_defaults(room)
    value = _clamp(float(source_ml_min), -5.0, 35.0)
    key = season_key(when)
    profiles = room.get("seasonal_source_profiles")
    if not isinstance(profiles, dict):
        profiles = {}
        room["seasonal_source_profiles"] = profiles
    row = profiles.setdefault(key, {"rate_ml_min": None, "samples": 0, "last_seen": None})
    samples = int(row.get("samples", 0) or 0)
    row["rate_ml_min"] = round(_ewma(row.get("rate_ml_min"), value, samples), 4)
    row["samples"] = min(samples + 1, 20000)
    row["last_seen"] = when.isoformat()
    room["seasonal_samples"] = min(int(room.get("seasonal_samples", 0) or 0) + 1, 200000)

    # Calendar evidence is deliberately independent from raw sample volume.
    # Thousands of 12-minute observations in one week are still only one week
    # of seasonal experience. Store unique usable observation days per
    # meteorological season/year so maturity cannot be accelerated by polling.
    obs = room.get("seasonal_observation_days")
    if not isinstance(obs, dict):
        obs = {}
    period_year = when.year - 1 if key == "winter" and when.month in (1, 2) else when.year
    period = f"{period_year}:{key}"
    days = obs.get(period)
    if not isinstance(days, list):
        days = []
    day = when.date().isoformat()
    if day not in days:
        days.append(day)
        days = sorted(set(days))[-100:]
    obs[period] = days
    room["seasonal_observation_days"] = obs

    lt_samples = int(room.get("long_term_source_samples", 0) or 0)
    room["long_term_source_ml_min"] = round(
        _ewma(room.get("long_term_source_ml_min"), value, lt_samples, slow=True), 4
    )
    room["long_term_source_samples"] = min(lt_samples + 1, 200000)
    room["long_term_updated_at"] = when.isoformat()


def _age_weight(last_seen: Any, now: datetime, half_life_days: float = 120.0) -> float:
    """Exponential half-life. A 120-day-old profile contributes half weight."""
    if not last_seen:
        return 0.0
    try:
        seen = datetime.fromisoformat(str(last_seen))
        age_days = max((now - seen).total_seconds() / 86400.0, 0.0)
    except (TypeError, ValueError):
        return 0.0
    return exp(-log(2.0) * age_days / max(float(half_life_days), 1.0))


def seasonal_context(room: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Return bounded seasonal factor and maturity for the current season."""
    ensure_seasonal_defaults(room)
    key = season_key(now)
    profiles = room.get("seasonal_source_profiles")
    row = profiles.get(key) if isinstance(profiles, dict) else None
    if not isinstance(row, dict) or row.get("rate_ml_min") is None:
        return {
            "season": key, "factor": 1.0, "maturity": 0.0, "age_weight": 0.0,
            "season_rate_ml_min": None, "long_term_rate_ml_min": room.get("long_term_source_ml_min"),
        }

    samples = int(row.get("samples", 0) or 0)
    age_weight = _age_weight(row.get("last_seen"), now)
    long_term = room.get("long_term_source_ml_min")
    season_rate = _f(row.get("rate_ml_min"))
    if long_term is None or abs(_f(long_term)) < 0.15:
        raw_factor = 1.0
    else:
        raw_factor = season_rate / max(_f(long_term), 0.15)

    sample_maturity = min(samples / 24.0, 1.0)
    maturity = sample_maturity * age_weight
    # Blend to neutral when data are sparse/stale and cap the effect.
    factor = 1.0 + (_clamp(raw_factor, 0.55, 1.65) - 1.0) * maturity
    factor = _clamp(factor, 0.70, 1.45)

    return {
        "season": key,
        "factor": round(factor, 3),
        "maturity": round(maturity * 100.0, 1),
        "age_weight": round(age_weight, 3),
        "season_rate_ml_min": round(season_rate, 3),
        "long_term_rate_ml_min": round(_f(long_term), 3) if long_term is not None else None,
        "samples": samples,
    }


def seasonal_adjust_rate(room: dict[str, Any], now: datetime, base_rate: float) -> tuple[float, dict[str, Any]]:
    context = seasonal_context(room, now)
    factor = _f(context.get("factor"), 1.0)
    return float(base_rate) * factor, context


def seasonal_house_maturity(rooms: list[dict[str, Any]], now: datetime) -> float:
    vals = [float(seasonal_context(r, now).get("maturity", 0.0)) for r in rooms]
    return round(sum(vals) / len(vals), 1) if vals else 0.0
