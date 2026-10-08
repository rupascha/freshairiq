"""FreshAirIQ house-wide strategy learning.

Learns outcomes of ventilation patterns across rooms/floors, cross ventilation
and occupancy. It is deliberately advisory: health and physical room rules stay
authoritative.
"""
from __future__ import annotations
from math import isfinite
from typing import Any
from datetime import datetime


def _f(v: Any, default: float = 0.0) -> float:
    try:
        number = float(v)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if isfinite(number) else default


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(float(v), lo), hi)


def ensure_house_defaults(store: dict[str, Any]) -> None:
    store.setdefault("house_strategy_buckets", {})
    store.setdefault("house_strategy_samples", 0)
    store.setdefault("house_strategy_successes", 0)
    store.setdefault("house_strategy_total_removed_ml", 0.0)
    store.setdefault("house_strategy_total_minutes", 0.0)
    store.setdefault("house_strategy_observation_dates", [])


def occupancy_bucket(expected_total: float) -> str:
    if expected_total < 0.5:
        return "away"
    if expected_total <= 2.5:
        return "normal"
    return "busy"


def strategy_signature(
    room_keys: list[str],
    room_meta: dict[str, dict[str, Any]],
    *,
    cross: bool,
    expected_occupants: float,
) -> str:
    keys = [k for k in room_keys if k in room_meta]
    floors = {str(room_meta[k].get("floor") or "unknown") for k in keys}
    if len(keys) <= 1:
        scope = "single"
    elif len(floors) <= 1:
        scope = "same_floor"
    else:
        scope = "multi_floor"
    airflow = "cross" if cross else "normal"
    occ = occupancy_bucket(expected_occupants)
    return f"{scope}|{airflow}|{occ}"


def _ewma(old: float | None, value: float, samples: int) -> float:
    if old is None or samples <= 0:
        return float(value)
    alpha = 0.25 if samples < 6 else 0.13 if samples < 20 else 0.07
    return float(old) * (1.0-alpha) + float(value) * alpha


def learn_house_outcome(
    store: dict[str, Any],
    events: list[dict[str, Any]],
    room_meta: dict[str, dict[str, Any]],
    *,
    cross: bool,
    expected_occupants: float,
    observed_at: datetime | None = None,
) -> bool:
    """Learn one completed house ventilation batch."""
    ensure_house_defaults(store)
    # House-strategy physics may learn only from sessions with a trustworthy
    # measured moisture outcome. A real ventilation with insufficient climate
    # timestamp evidence remains a behaviour/statistics event, but must not be
    # interpreted as a synthetic 0 ml physical result. Legacy events without the
    # explicit flag remain compatible when they contain a numeric removed_ml.
    useful = [
        e for e in events
        if _f(e.get("duration_min")) >= 1.0
        and bool(e.get("moisture_measurement_valid", e.get("removed_ml") is not None))
        and e.get("removed_ml") is not None
    ]
    if not useful:
        return False

    keys = [str(e.get("key") or "") for e in useful]
    sig = strategy_signature(keys, room_meta, cross=cross, expected_occupants=expected_occupants)
    buckets = store.get("house_strategy_buckets")
    if not isinstance(buckets, dict):
        buckets = {}
        store["house_strategy_buckets"] = buckets
    row = buckets.setdefault(sig, {
        "samples": 0, "successes": 0, "success_rate": None,
        "avg_removed_ml": None, "avg_duration_min": None,
        "avg_removed_ml_min": None, "avg_cost_per_100ml": None,
    })
    samples = int(row.get("samples", 0) or 0)
    # Preserve the signed physical outcome. Positive = moisture removed;
    # negative = moisture added. Bad ventilation sessions must reduce the
    # learned efficiency of the corresponding house strategy instead of being
    # flattened to the same zero result as a neutral session.
    removed = sum(_f(e.get("removed_ml")) for e in useful)
    duration = max((_f(e.get("duration_min")) for e in useful), default=0.0)
    cost = sum(max(_f(e.get("cost")), 0.0) for e in useful)
    rate = removed / max(duration, 1.0)

    predicted = sum(max(_f(e.get("predicted_removed_ml")), 0.0) for e in useful)
    if predicted >= 40:
        successful = removed >= predicted * 0.70
    else:
        successful = removed >= 60 and rate >= 5.0

    row["samples"] = min(samples + 1, 10000)
    if successful:
        row["successes"] = min(int(row.get("successes", 0) or 0) + 1, 10000)
    row["success_rate"] = round(100.0 * int(row.get("successes", 0)) / max(int(row["samples"]),1), 1)
    row["avg_removed_ml"] = round(_ewma(row.get("avg_removed_ml"), removed, samples), 1)
    row["avg_duration_min"] = round(_ewma(row.get("avg_duration_min"), duration, samples), 1)
    row["avg_removed_ml_min"] = round(_ewma(row.get("avg_removed_ml_min"), rate, samples), 2)
    cost100 = cost / max(abs(removed), 1.0) * 100.0
    row["avg_cost_per_100ml"] = round(_ewma(row.get("avg_cost_per_100ml"), cost100, samples), 4)

    store["house_strategy_samples"] = min(int(store.get("house_strategy_samples",0) or 0)+1,100000)
    if successful:
        store["house_strategy_successes"] = min(int(store.get("house_strategy_successes",0) or 0)+1,100000)
    store["house_strategy_total_removed_ml"] = round(_f(store.get("house_strategy_total_removed_ml")) + removed, 1)
    store["house_strategy_total_minutes"] = round(_f(store.get("house_strategy_total_minutes")) + duration, 1)
    if observed_at is not None:
        dates = store.get("house_strategy_observation_dates")
        if not isinstance(dates, list):
            dates = []
        day = observed_at.date().isoformat()
        if day not in dates:
            dates.append(day)
        store["house_strategy_observation_dates"] = dates[-730:]
    return True


def house_strategy_fit(
    store: dict[str, Any],
    room_keys: list[str],
    room_meta: dict[str, dict[str, Any]],
    *,
    cross: bool,
    expected_occupants: float,
) -> dict[str, Any]:
    ensure_house_defaults(store)
    sig = strategy_signature(room_keys, room_meta, cross=cross, expected_occupants=expected_occupants)
    buckets = store.get("house_strategy_buckets")
    row = buckets.get(sig) if isinstance(buckets, dict) else None
    if not isinstance(row, dict):
        return {"signature": sig, "maturity": 0.0, "fit": 0.5, "success_probability": 0.5, "efficiency_factor": 1.0, "samples": 0}

    samples = int(row.get("samples",0) or 0)
    successes = int(row.get("successes",0) or 0)
    # Neutral Bayesian prior prevents tiny samples from dominating.
    success_p = (successes + 2.0) / (samples + 4.0)
    maturity = min(samples / 18.0, 1.0)

    global_minutes = max(_f(store.get("house_strategy_total_minutes")), 1.0)
    global_rate = _f(store.get("house_strategy_total_removed_ml")) / global_minutes
    local_rate = _f(row.get("avg_removed_ml_min"))
    if global_rate >= 1.0 and local_rate > 0:
        raw_eff = local_rate / global_rate
    else:
        raw_eff = 1.0
    eff = 1.0 + (_clamp(raw_eff,0.65,1.45)-1.0) * maturity

    cost = max(_f(row.get("avg_cost_per_100ml")), 0.0)
    cost_score = 1.0 / (1.0 + cost * 20.0)
    fit_raw = success_p * 0.58 + _clamp(eff/1.25,0.0,1.0)*0.30 + cost_score*0.12
    fit = 0.5 + (fit_raw-0.5)*maturity
    return {
        "signature": sig, "maturity": round(maturity*100.0,1),
        "fit": round(_clamp(fit,0.2,0.9),3),
        "success_probability": round(success_p,3),
        "efficiency_factor": round(eff,3),
        "samples": samples,
        "avg_removed_ml_min": row.get("avg_removed_ml_min"),
        "avg_cost_per_100ml": row.get("avg_cost_per_100ml"),
    }


def house_maturity(store: dict[str, Any]) -> float:
    ensure_house_defaults(store)
    buckets = store.get("house_strategy_buckets")
    if not isinstance(buckets, dict):
        return 0.0
    useful = [r for r in buckets.values() if isinstance(r,dict) and int(r.get("samples",0) or 0) >= 3]
    breadth = min(len(useful)/6.0,1.0)
    depth = min(int(store.get("house_strategy_samples",0) or 0)/36.0,1.0)
    return round((breadth*0.45 + depth*0.55)*100.0,1)
