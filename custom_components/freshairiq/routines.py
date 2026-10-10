"""FreshAirIQ phase 4: time-of-day routine learning.

Learns observed internal moisture generation and recommendation response patterns
without assuming a fixed household schedule.  The model is deliberately low
resolution (weekday/weekend × hour) and only influences forecasts once a bucket
has enough observations.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .seasonality import ensure_seasonal_defaults, seasonal_adjust_rate_prepared


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def routine_bucket_key(when: datetime) -> str:
    day_type = "weekend" if when.weekday() >= 5 else "weekday"
    return f"{day_type}_{when.hour:02d}"


_ROUTINE_DEFAULT_KEYS = (
    "routine_source_buckets",
    "routine_response_buckets",
    "routine_observation_at",
    "routine_source_samples",
    "routine_response_samples",
    "routine_observation_dates",
)


def ensure_routine_defaults(room: dict[str, Any]) -> None:
    # Hot path (called per forecast step): skip building defaults when the room
    # is already complete. Semantics are identical to the former setdefault loop.
    if all(key in room for key in _ROUTINE_DEFAULT_KEYS):
        return
    defaults = {
        "routine_source_buckets": {},
        "routine_response_buckets": {},
        "routine_observation_at": None,
        "routine_source_samples": 0,
        "routine_response_samples": 0,
        "routine_observation_dates": [],
    }
    for key, value in defaults.items():
        room.setdefault(key, value.copy() if isinstance(value, dict) else value)


def _ewma(old: float | None, value: float, samples: int) -> float:
    if old is None or samples <= 0:
        return value
    alpha = 0.28 if samples < 5 else 0.14 if samples < 15 else 0.08
    return float(old) * (1.0 - alpha) + value * alpha


def learn_source_pattern(room: dict[str, Any], when: datetime, source_ml_min: float, *, minimum_interval_min: float = 12.0) -> bool:
    """Learn a closed-room internal moisture source rate for the current time bucket."""
    ensure_routine_defaults(room)
    last_raw = room.get("routine_observation_at")
    if last_raw:
        try:
            age = (when - datetime.fromisoformat(str(last_raw))).total_seconds() / 60.0
            if age < minimum_interval_min:
                return False
        except (TypeError, ValueError):
            pass

    # Reject implausible spikes; showers/cooking can still be represented but a
    # sensor glitch must not dominate a long-term routine model.
    value = _clamp(float(source_ml_min), -5.0, 35.0)
    key = routine_bucket_key(when)
    buckets = room.get("routine_source_buckets")
    if not isinstance(buckets, dict):
        buckets = {}
        room["routine_source_buckets"] = buckets
    row = buckets.setdefault(key, {"rate_ml_min": None, "samples": 0, "last_seen": None})
    samples = int(row.get("samples", 0) or 0)
    row["rate_ml_min"] = round(_ewma(row.get("rate_ml_min"), value, samples), 4)
    row["samples"] = min(samples + 1, 10000)
    row["last_seen"] = when.isoformat()
    room["routine_source_samples"] = min(int(room.get("routine_source_samples", 0) or 0) + 1, 100000)
    room["routine_observation_at"] = when.isoformat()
    dates = room.get("routine_observation_dates")
    if not isinstance(dates, list):
        dates = []
    day = when.date().isoformat()
    if day not in dates:
        dates.append(day)
        dates = dates[-400:]
    room["routine_observation_dates"] = dates
    return True


def learn_response_pattern(room: dict[str, Any], issued_at: datetime, followed: bool, delay_min: float | None = None) -> None:
    """Learn whether recommendations issued at this time are usually followed."""
    ensure_routine_defaults(room)
    key = routine_bucket_key(issued_at)
    buckets = room.get("routine_response_buckets")
    if not isinstance(buckets, dict):
        buckets = {}
        room["routine_response_buckets"] = buckets
    row = buckets.setdefault(key, {"opportunities": 0, "followed": 0, "follow_rate": None, "avg_delay_min": None})
    row["opportunities"] = min(int(row.get("opportunities", 0) or 0) + 1, 10000)
    if followed:
        row["followed"] = min(int(row.get("followed", 0) or 0) + 1, 10000)
        if delay_min is not None:
            prior_samples = max(int(row["followed"]) - 1, 0)
            row["avg_delay_min"] = round(_ewma(row.get("avg_delay_min"), _clamp(delay_min, 0.0, 180.0), prior_samples), 1)
    row["follow_rate"] = round(100.0 * int(row.get("followed", 0)) / max(int(row.get("opportunities", 0)), 1), 1)
    room["routine_response_samples"] = min(int(room.get("routine_response_samples", 0) or 0) + 1, 100000)


def _bucket_source_rate(room: dict[str, Any], bucket_key: str) -> tuple[float | None, int]:
    """Look up one learned bucket; the caller guarantees routine defaults."""
    buckets = room.get("routine_source_buckets")
    row = buckets.get(bucket_key) if isinstance(buckets, dict) else None
    if not isinstance(row, dict) or row.get("rate_ml_min") is None:
        return None, 0
    return float(row["rate_ml_min"]), int(row.get("samples", 0) or 0)


def expected_source_rate(room: dict[str, Any], when: datetime) -> tuple[float | None, int]:
    ensure_routine_defaults(room)
    return _bucket_source_rate(room, routine_bucket_key(when))


def response_pattern(room: dict[str, Any], when: datetime) -> dict[str, Any] | None:
    ensure_routine_defaults(room)
    buckets = room.get("routine_response_buckets")
    row = buckets.get(routine_bucket_key(when)) if isinstance(buckets, dict) else None
    if not isinstance(row, dict) or int(row.get("opportunities", 0) or 0) <= 0:
        return None
    return dict(row)


def routine_maturity(room: dict[str, Any]) -> float:
    """0..100 based on breadth and depth of learned source buckets."""
    ensure_routine_defaults(room)
    buckets = room.get("routine_source_buckets")
    if not isinstance(buckets, dict):
        return 0.0
    useful = [row for row in buckets.values() if isinstance(row, dict) and int(row.get("samples", 0) or 0) >= 3]
    breadth = min(len(useful) / 16.0, 1.0)  # 16 useful hour buckets is already meaningful.
    depth = 0.0
    if useful:
        depth = sum(min(int(x.get("samples", 0)) / 12.0, 1.0) for x in useful) / len(useful)
    return round((breadth * 0.55 + depth * 0.45) * 100.0, 1)


def project_generation_ml(rooms: list[dict[str, Any]], start: datetime, minutes: float, *, fallback_rates: dict[str, float] | None = None) -> tuple[float, float]:
    """Project internally generated moisture using learned time buckets.

    Returns (ml, maturity_0_100). Missing/immature buckets fall back to the
    caller-provided current source rate and therefore never create invented data.
    """
    minutes = _clamp(minutes, 0.0, 720.0)
    if minutes <= 0 or not rooms:
        return 0.0, 0.0
    fallback_rates = fallback_rates or {}
    total = 0.0
    weighted_maturity = 0.0
    steps = max(1, int((minutes + 14.999) // 15))
    step_min = minutes / steps
    # Performance (0.26.4.6): defaults are ensured once per room instead of once
    # per room *and* 15-minute step, and room-invariant values are hoisted.
    # Every arithmetic step and its order are unchanged, so results are
    # bit-identical to the previous implementation.
    prepared: list[tuple[dict[str, Any], float]] = []
    for room in rooms:
        ensure_routine_defaults(room)
        ensure_seasonal_defaults(room)
        key = str(room.get("key") or "")
        prepared.append((room, float(fallback_rates.get(key, room.get("forecast_source_rate_ml_min", 0.0) or 0.0))))
    for idx in range(steps):
        at = start + timedelta(minutes=step_min * (idx + 0.5))
        bucket_key = routine_bucket_key(at)
        for room, fallback in prepared:
            learned, samples = _bucket_source_rate(room, bucket_key)
            if learned is not None and samples >= 3:
                weight = min(samples / 12.0, 1.0)
                rate = learned * weight + fallback * (1.0 - weight)
                weighted_maturity += weight
            else:
                rate = fallback
            rate, seasonal = seasonal_adjust_rate_prepared(room, at, rate)
            # Seasonal maturity contributes only as a small confidence refinement;
            # routine maturity remains the primary gate.
            weighted_maturity += min(float(seasonal.get("maturity", 0.0)) / 100.0, 1.0) * 0.15
            total += max(rate, 0.0) * step_min
    denom = steps * len(rooms)
    return round(total, 1), round(min((weighted_maturity / max(denom, 1)) / 1.15, 1.0) * 100.0, 1)
