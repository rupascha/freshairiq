"""FreshAirIQ phase 5: adaptive resident strategy learning.

Learns which *type* of recommendation a household tends to follow and which
recommendations also achieve a useful physical result.  This layer may break
ties between similarly good physical options, but it must never overrule high
health pressure or hard real-time states.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _ewma(old: float | None, value: float, samples: int) -> float:
    if old is None or samples <= 0:
        return float(value)
    alpha = 0.30 if samples < 5 else 0.16 if samples < 15 else 0.09
    return float(old) * (1.0 - alpha) + float(value) * alpha


def strategy_key(option_id: str | None, duration_min: float | None) -> str:
    option = str(option_id or "unknown")
    if option.startswith("wait_"):
        family = option
    elif option == "night":
        family = "night"
    else:
        family = "now"
    duration = float(duration_min or 0.0)
    if duration <= 0:
        bucket = "none"
    elif duration <= 7:
        bucket = "short"
    elif duration <= 12:
        bucket = "medium"
    else:
        bucket = "long"
    return f"{family}|{bucket}"


def ensure_strategy_defaults(room: dict[str, Any]) -> None:
    defaults = {
        "strategy_buckets": {},
        "strategy_samples": 0,
        "strategy_follow_samples": 0,
        "strategy_outcome_samples": 0,
    }
    for key, value in defaults.items():
        room.setdefault(key, value.copy() if isinstance(value, dict) else value)


def learn_strategy_opportunity(
    room: dict[str, Any], option_id: str | None, duration_min: float | None,
    followed: bool, follow_delay_min: float | None = None,
) -> None:
    """Learn whether an issued recommendation style was acted on."""
    ensure_strategy_defaults(room)
    key = strategy_key(option_id, duration_min)
    buckets = room.get("strategy_buckets")
    if not isinstance(buckets, dict):
        buckets = {}
        room["strategy_buckets"] = buckets
    row = buckets.setdefault(key, {
        "opportunities": 0, "followed": 0, "follow_rate": None,
        "avg_follow_delay_min": None, "outcomes": 0, "successful_outcomes": 0,
        "success_rate": None,
    })
    row["opportunities"] = min(int(row.get("opportunities", 0) or 0) + 1, 10000)
    if followed:
        row["followed"] = min(int(row.get("followed", 0) or 0) + 1, 10000)
        room["strategy_follow_samples"] = min(int(room.get("strategy_follow_samples", 0) or 0) + 1, 100000)
        if follow_delay_min is not None:
            n = max(int(row.get("followed", 0)) - 1, 0)
            row["avg_follow_delay_min"] = round(_ewma(row.get("avg_follow_delay_min"), _clamp(follow_delay_min, 0, 180), n), 1)
    row["follow_rate"] = round(100.0 * int(row.get("followed", 0)) / max(int(row.get("opportunities", 0)), 1), 1)
    room["strategy_samples"] = min(int(room.get("strategy_samples", 0) or 0) + 1, 100000)


def learn_strategy_outcome(
    room: dict[str, Any], option_id: str | None, duration_min: float | None,
    *, successful: bool, observed_at: datetime | None = None,
) -> None:
    """Learn whether a followed recommendation style achieved a useful result."""
    ensure_strategy_defaults(room)
    key = strategy_key(option_id, duration_min)
    buckets = room.get("strategy_buckets")
    if not isinstance(buckets, dict):
        buckets = {}
        room["strategy_buckets"] = buckets
    row = buckets.setdefault(key, {
        "opportunities": 0, "followed": 0, "follow_rate": None,
        "avg_follow_delay_min": None, "outcomes": 0, "successful_outcomes": 0,
        "success_rate": None,
    })
    row["outcomes"] = min(int(row.get("outcomes", 0) or 0) + 1, 10000)
    if successful:
        row["successful_outcomes"] = min(int(row.get("successful_outcomes", 0) or 0) + 1, 10000)
    row["success_rate"] = round(100.0 * int(row.get("successful_outcomes", 0)) / max(int(row.get("outcomes", 0)), 1), 1)
    room["strategy_outcome_samples"] = min(int(room.get("strategy_outcome_samples", 0) or 0) + 1, 100000)
    if observed_at is not None:
        dates = room.get("strategy_observation_dates")
        if not isinstance(dates, list):
            dates = []
        day = observed_at.date().isoformat()
        if day not in dates:
            dates.append(day)
        room["strategy_observation_dates"] = dates[-730:]


def strategy_fit(room: dict[str, Any], option_id: str | None, duration_min: float | None) -> dict[str, float]:
    """Return learned adherence/effectiveness estimate for one option style.

    Neutral values are returned until enough data exists. Bayesian-style priors
    prevent a handful of early choices from dominating the Decision Engine.
    """
    ensure_strategy_defaults(room)
    buckets = room.get("strategy_buckets")
    row = buckets.get(strategy_key(option_id, duration_min)) if isinstance(buckets, dict) else None
    if not isinstance(row, dict):
        return {"fit": 0.5, "follow": 0.5, "success": 0.5, "maturity": 0.0}
    opp = int(row.get("opportunities", 0) or 0)
    followed = int(row.get("followed", 0) or 0)
    outcomes = int(row.get("outcomes", 0) or 0)
    successes = int(row.get("successful_outcomes", 0) or 0)
    # Conservative priors: 3 virtual neutral observations.
    follow = (followed + 1.5) / (opp + 3.0)
    success = (successes + 1.5) / (outcomes + 3.0)
    maturity = min((opp + outcomes) / 16.0, 1.0)
    fit = (follow * 0.62 + success * 0.38) * maturity + 0.5 * (1.0 - maturity)
    return {
        "fit": round(_clamp(fit, 0.15, 0.90), 3),
        "follow": round(_clamp(follow, 0.10, 0.90), 3),
        "success": round(_clamp(success, 0.10, 0.90), 3),
        "maturity": round(maturity * 100.0, 1),
    }


def strategy_maturity(room: dict[str, Any]) -> float:
    ensure_strategy_defaults(room)
    rows = room.get("strategy_buckets")
    if not isinstance(rows, dict) or not rows:
        return 0.0
    useful = [r for r in rows.values() if isinstance(r, dict) and int(r.get("opportunities", 0) or 0) >= 3]
    breadth = min(len(useful) / 5.0, 1.0)
    depth = min(int(room.get("strategy_samples", 0) or 0) / 30.0, 1.0)
    outcomes = min(int(room.get("strategy_outcome_samples", 0) or 0) / 15.0, 1.0)
    return round((breadth * 0.35 + depth * 0.40 + outcomes * 0.25) * 100.0, 1)


def household_strategy_fit(rooms: list[dict[str, Any]], option_id: str | None, duration_min: float | None) -> dict[str, float]:
    values = [strategy_fit(room, option_id, duration_min) for room in rooms]
    mature = [v for v in values if v["maturity"] > 0]
    if not mature:
        return {"fit": 0.5, "follow": 0.5, "success": 0.5, "maturity": 0.0}
    weights = [max(v["maturity"] / 100.0, 0.10) for v in mature]
    denom = sum(weights)
    return {
        "fit": round(sum(v["fit"] * w for v, w in zip(mature, weights)) / denom, 3),
        "follow": round(sum(v["follow"] * w for v, w in zip(mature, weights)) / denom, 3),
        "success": round(sum(v["success"] * w for v, w in zip(mature, weights)) / denom, 3),
        "maturity": round(sum(v["maturity"] * w for v, w in zip(mature, weights)) / denom, 1),
    }
