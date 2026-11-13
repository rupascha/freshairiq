"""Passive shadow comparison of a candidate moisture formula (pure, observation only).

The candidate formula ``humidity-hybrid-2026-10-31-r1`` is computed next to the active
start forecast and scored against the same measured result. It is never used by the
room model, the forecast, the house decision, the live coach, notifications, fans,
entities or learning: its only consumers are the completed-session event, the
validation record, the published comparison summary and diagnostics.

Fair pairing: both formulas see the same frozen start state (start room AH, start
reference AH, room volume, cross-ventilation known at the start, frozen production
curve) and are read at the same measured duration (``validation_elapsed``). The
duration only selects the point on the two curves; no end measurement, later
reference value, later learned rate or later cross-ventilation state is used.
Any failure yields ``None`` plus a reason code; production keeps running unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import exp, expm1, isfinite, log, sqrt
from typing import Any

from .forecast_validation import START_FORECAST_CONTEXT_VERSION, evaluate_start_forecast_at_duration
from .learning_effectiveness import (
    MIN_EFFECT_PERCENT,
    MIN_EVIDENCE_DAYS,
    MIN_EVIDENCE_SAMPLES,
    MIN_EVIDENCE_SESSIONS,
    MIN_WIN_RATE,
    _record_id,
)

COMPARISON_SCHEMA_VERSION = 1
SHADOW_START_VERSION = 1
CANDIDATE_FORMULA_ID = "humidity-hybrid-2026-10-31-r1"
# The active start forecast: ``forecast.horizon_forecast`` replayed on the frozen start
# curve (start context v2). Bump the revision with every change of that calculation;
# tests/test_forecast_shadow_026505.py pins the source of forecast.py to this ID.
PRODUCTION_FORMULA_ID = f"start-curve-v{START_FORECAST_CONTEXT_VERSION}-horizon-forecast-r2"  # r2: final hotfix F11-C (no max-duration end point)
# 0.26.7.0 (owner order point 7): the prepared successor – the same versioned formula and coefficients as the
# candidate, but fed with the physical start replay (the production side since #28) instead of the target-limited
# one, matching the time-unlimited close decision (F11). Pure shadow: recorded per session next to the candidate,
# never used anywhere. Its coefficients are NOT recalibrated (no new data): its error is measured, not claimed.
SUCCESSOR_FORMULA_ID = "humidity-hybrid-2026-11-13-r2-physical-input"
SUCCESSOR_STATUS = "shadow_only_uncalibrated"
TIE_ML = 1.0  # same tie band as the learning-effectiveness comparison
CROSS_FULL_RATIO = 0.95  # a cross-ventilated start must stay cross-ventilated (sampling slack)
CROSS_NONE_RATIO = 0.05
FUTURE_TOLERANCE_MIN = 10.0


def shadow_removed_ml(*, room_ah_start_g_m3: float, source_ah_start_g_m3: float, volume_m3: float,
                      horizon_min: float, is_cross_ventilated: bool, legacy_start_forecast_ml: float) -> float:
    """Candidate ``humidity-hybrid-2026-10-31-r1``: removed moisture in ml (coefficients of the formula study)."""
    vals = (room_ah_start_g_m3, source_ah_start_g_m3, volume_m3, horizon_min, legacy_start_forecast_ml)
    if not all(isfinite(float(x)) for x in vals):
        raise ValueError("Non-finite shadow input")
    if not 1.0 <= volume_m3 <= 500.0 or not 0.0 <= horizon_min <= 120.0:
        raise ValueError("Shadow outside calibrated range")
    if horizon_min == 0.0:
        return 0.0
    k = exp(-5.24466443 + (0.93384866 if is_cross_ventilated else 0.0)
            - 0.24775893 * log(min(max(volume_m3 / 40.0, 0.1), 4.0)))
    length = min(horizon_min, 20.0) + 0.55 * max(horizon_min - 20.0, 0.0)
    physical_ml = ((room_ah_start_g_m3 - source_ah_start_g_m3) * volume_m3
                   * (-expm1(-k * horizon_min)) - 0.03705066 * length)
    return (0.20102258 * legacy_start_forecast_ml
            + 0.79897742 * physical_ml
            + 1.17503054 * (1.0 - exp(-horizon_min)))


def _successor(args: dict[str, Any], shadow: dict[str, Any], horizon: float, production: float,
               out: dict[str, Any]) -> float | None:
    """The prepared successor next to the candidate (shadow only); its own reason when it cannot be computed."""
    out["successor_formula_id"] = SUCCESSOR_FORMULA_ID
    out["successor_status"] = SUCCESSOR_STATUS
    out["successor_input_basis"] = "physical_start_replay"
    try:
        value = shadow_removed_ml(
            room_ah_start_g_m3=float(args["current_ah"]), source_ah_start_g_m3=float(args["source_ah"]),
            volume_m3=float(args["volume_m3"]), horizon_min=horizon,
            is_cross_ventilated=bool(shadow.get("cross_ventilated")), legacy_start_forecast_ml=production)
    except (KeyError, TypeError, OverflowError, ValueError) as err:
        out["successor_exclusion_reason"] = "outside_calibrated_range" if "range" in str(err) else "invalid_input"
        return None
    out["successor_predicted_removed_ml"] = round(value, 1)
    return value


def freeze_shadow_start(*, cross_ventilated: bool, integration_version: str) -> dict[str, Any]:
    """What the shadow comparison needs from the opening, stored inside the frozen start context."""
    return {
        "version": SHADOW_START_VERSION,
        "cross_ventilated": bool(cross_ventilated),
        "integration_version": str(integration_version),
        "production_formula_id": PRODUCTION_FORMULA_ID,
        "candidate_formula_id": CANDIDATE_FORMULA_ID,
    }


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _record(shadow: dict[str, Any], **values: Any) -> dict[str, Any]:
    return {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "production_formula_id": shadow.get("production_formula_id") or PRODUCTION_FORMULA_ID,
        "candidate_formula_id": shadow.get("candidate_formula_id") or CANDIDATE_FORMULA_ID,
        "freshairiq_version_at_start": shadow.get("integration_version"),
        "start_context_version": values.pop("start_context_version", None),
        "prediction_horizon_min": None,
        "production_predicted_removed_ml": None,
        "candidate_predicted_removed_ml": None,
        "measured_removed_ml": None,
        "production_abs_error_ml": None,
        "candidate_abs_error_ml": None,
        # null model "always 0 ml" (formula study: the error measure rewards predictions near zero)
        "null_abs_error_ml": None,
        "opening_learning_quarantined": None,
        "paired_valid": False,
        "exclusion_reason": None,
        **values,
    }


def _exclusion(*, comparable: bool, measured: float | None, contaminated: bool,
               reference_reversal: bool, cross_start: bool, cross_ratio: float | None) -> str | None:
    if measured is None:
        return "no_measurement"
    if contaminated:
        return "moisture_source"
    if reference_reversal:
        return "reference_reversal"
    if not comparable:
        return "measurement_quality"
    if cross_ratio is None or (cross_ratio < CROSS_FULL_RATIO if cross_start else cross_ratio > CROSS_NONE_RATIO):
        return "cross_mode_changed"
    return None


def shadow_forecast_record(start_context: Any, *, horizon_min: Any, production_predicted_ml: Any,
                           measured_removed_ml: Any, comparable: bool, time_aligned: bool,
                           contaminated: bool = False, reference_reversal: bool = False,
                           cross_ratio: Any = None, no_measurement: bool = False,
                           quarantined: bool = False) -> dict[str, Any] | None:
    """The pair of one completed session (None when the session started before the shadow existed).

    Never raises: any problem becomes ``exclusion_reason`` with ``paired_valid = False``.
    """
    try:
        context = start_context if isinstance(start_context, dict) else {}
        shadow = context.get("shadow") if isinstance(context.get("shadow"), dict) else None
        if shadow is None or shadow.get("version") != SHADOW_START_VERSION:
            return None  # unavailable – never a made-up shadow run
        version = context.get("version")
        if version != START_FORECAST_CONTEXT_VERSION:
            return _record(shadow, start_context_version=version, exclusion_reason="start_context_unsupported")
        args = context.get("forecast_args") if isinstance(context.get("forecast_args"), dict) else {}
        horizon = _number(horizon_min)
        production = _number(production_predicted_ml)
        measured = _number(measured_removed_ml)
        out = _record(shadow, start_context_version=version,
                      prediction_horizon_min=round(horizon, 3) if horizon is not None else None,
                      production_predicted_removed_ml=round(production, 1) if production is not None else None,
                      measured_removed_ml=round(measured, 1) if measured is not None else None,
                      # marked, not excluded: the study calibrated without these sessions (hub usable_for)
                      opening_learning_quarantined=bool(quarantined))
        if no_measurement:
            out["exclusion_reason"] = "no_measurement"
            return out
        if horizon is None or production is None or not time_aligned:
            out["exclusion_reason"] = "production_unavailable"
            return out
        # 0.26.7.0 (#28): the candidate was calibrated on the target-limited start replay ("legacy" forecast). The
        # production side is now the physical replay; the candidate keeps its own input so it stays the same
        # versioned formula. Its input is replayed from the same frozen start at the same measured duration.
        try:
            limited = evaluate_start_forecast_at_duration(context, horizon, limit_to_target=True)
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            out["exclusion_reason"] = "invalid_input"  # e.g. a non-finite value in the frozen start
            return out
        candidate_input = _number(limited.get("predicted_removed_ml")) if isinstance(limited, dict) else None
        if candidate_input is None:
            needed = {"current_ah", "source_ah", "volume_m3", "current_temp_c", "source_temp_c", "rate_per_min", "airflow_bonus"}
            out["exclusion_reason"] = "production_unavailable" if needed <= set(args) else "start_context_incomplete"
            return out
        out["candidate_input_basis"] = "target_limited_start_replay"
        try:
            candidate = shadow_removed_ml(
                room_ah_start_g_m3=float(args["current_ah"]), source_ah_start_g_m3=float(args["source_ah"]),
                volume_m3=float(args["volume_m3"]), horizon_min=horizon,
                is_cross_ventilated=bool(shadow.get("cross_ventilated")), legacy_start_forecast_ml=candidate_input)
        except (KeyError, TypeError, OverflowError):
            out["exclusion_reason"] = "start_context_incomplete"
            return out
        except ValueError as err:
            out["exclusion_reason"] = "outside_calibrated_range" if "range" in str(err) else "invalid_input"
            return out
        out["candidate_predicted_removed_ml"] = round(candidate, 1)
        successor = _successor(args, shadow, horizon, production, out)
        reason = _exclusion(comparable=bool(comparable), measured=measured,
                            contaminated=bool(contaminated), reference_reversal=bool(reference_reversal),
                            cross_start=bool(shadow.get("cross_ventilated")), cross_ratio=_number(cross_ratio))
        if reason is None and measured is not None:
            out.update(production_abs_error_ml=round(abs(measured - production), 1),
                       candidate_abs_error_ml=round(abs(measured - candidate), 1),
                       null_abs_error_ml=round(abs(measured), 1), paired_valid=True)
            if successor is not None:
                out["successor_abs_error_ml"] = round(abs(measured - successor), 1)
        out["exclusion_reason"] = reason
        return out
    except Exception:  # noqa: BLE001 - an observation must never break the session end
        return {"comparison_schema_version": COMPARISON_SCHEMA_VERSION, "paired_valid": False,
                "exclusion_reason": "shadow_error", "candidate_formula_id": CANDIDATE_FORMULA_ID,
                "production_formula_id": PRODUCTION_FORMULA_ID}


def _stamp(record: dict[str, Any]) -> datetime | None:
    """Audit N01: the end (else start) time in UTC; a naive time is read as UTC, an unreadable one is None."""
    try:
        stamp = datetime.fromisoformat(str(record.get("ended_at") or record.get("started_at")))
    except (TypeError, ValueError):
        return None
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)


def _scoped(records: list[Any], days: int, now: datetime | None) -> list[dict[str, Any]]:
    """Audit N02: the last ``days`` × 24 h before now – not before the newest record."""
    reference = now or datetime.now(timezone.utc)
    reference = reference.replace(tzinfo=timezone.utc) if reference.tzinfo is None else reference
    cutoff = reference.astimezone(timezone.utc) - timedelta(days=max(1, int(days)))
    # Hotfix F02: nothing from the future – only a clock running a few minutes ahead (time sync jitter of
    # the device that wrote the record) is tolerated
    latest = reference.astimezone(timezone.utc) + timedelta(minutes=FUTURE_TOLERANCE_MIN)
    return [r for r in records if isinstance(r, dict) and (stamp := _stamp(r)) is not None and cutoff <= stamp <= latest]


def _observation(record: dict[str, Any], cluster: str, shadow: dict[str, Any]) -> dict[str, Any]:
    """One reported pair; ``valid`` only with both errors. The null error is None when unknown (audit N03)."""
    production = _number(shadow.get("production_abs_error_ml"))
    candidate = _number(shadow.get("candidate_abs_error_ml"))
    null = _number(shadow.get("null_abs_error_ml"))
    measured = _number(shadow.get("measured_removed_ml"))
    if null is None and measured is not None:
        null = abs(measured)  # pairs from before the null field: derived from the measurement
    stamp = _stamp(record)
    return {"valid": bool(shadow.get("paired_valid")) and production is not None and candidate is not None,
            "reason": str(shadow.get("exclusion_reason") or "unknown"), "ended": stamp.isoformat() if stamp else "",
            "production": production, "candidate": candidate, "null": null, "cluster": cluster,
            "quarantined": shadow.get("opening_learning_quarantined") is True, "day": str(record.get("ended_at") or "")[:10],
            "production_formula_id": shadow.get("production_formula_id"), "candidate_formula_id": shadow.get("candidate_formula_id")}


def _formula_pair(item: dict[str, Any]) -> tuple[str, str]:
    return str(item.get("production_formula_id") or ""), str(item.get("candidate_formula_id") or "")


CURRENT_FORMULA_PAIR = (PRODUCTION_FORMULA_ID, CANDIDATE_FORMULA_ID)


def _rank(item: dict[str, Any]) -> tuple[Any, ...]:
    """Audit F03/N05: a valid pair beats an exclusion, then the latest report, then the current formula
    pair; remaining ties are broken by value and formula ids, so the order of the reports never decides."""
    return (item["valid"], item["ended"], _formula_pair(item) == CURRENT_FORMULA_PAIR, item["production"] or 0.0,
            item["candidate"] or 0.0, _formula_pair(item), item["reason"])


def _pairs(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    best: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):  # dicts only (see shadow_comparison_summary)
        cluster = _record_id(record, index)
        for position, room in enumerate(record.get("room_results") or []):
            shadow = room.get("shadow_forecast") if isinstance(room, dict) else None
            if not isinstance(shadow, dict):
                continue  # sessions before the shadow existed: unavailable, not counted
            # one observation per session, whatever the order of the reports (restart, merged histories)
            session_id = str(room.get("validation_session_id") or room.get("event_id") or "") or f"unnamed:{index}:{position}"
            item = _observation(record, cluster, shadow)
            if session_id not in best or _rank(item) > _rank(best[session_id]):
                best[session_id] = item
    pairs = [item for item in best.values() if item["valid"]]
    excluded: dict[str, int] = defaultdict(int)
    for item in best.values():
        if not item["valid"]:
            excluded[item["reason"]] += 1
    return pairs, dict(excluded)


def published_comparison(records: Any, *, days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    """The summary for the status and diagnostics; a broken history never breaks the cycle."""
    try:
        return shadow_comparison_summary(list(records or []), days=days, now=now)
    except Exception:  # noqa: BLE001 - observation only
        return {"comparison_schema_version": COMPARISON_SCHEMA_VERSION, "status": "unavailable",
                "observational_only": True, "auto_activation": False, "samples": 0}


def _null_check(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit N03 / hotfix F03: the null model is judged only on the same sessions as the headline.

    Nothing is filled in for unknown null errors. The null MAE of the known ones is shown with its count;
    whether a formula beats "always 0 ml" is only stated when every headline pair has a known null error.
    """
    known = [p for p in pairs if p["null"] is not None]
    if not known:
        return {"null_samples": 0, "null_mae_ml": None, "candidate_beats_null": None, "production_beats_null": None}
    null_mae = sum(p["null"] for p in known) / len(known)
    complete = len(known) == len(pairs)
    candidate = sum(p["candidate"] for p in known) / len(known)
    production = sum(p["production"] for p in known) / len(known)
    return {"null_samples": len(known), "null_mae_ml": round(null_mae, 1),
            "candidate_beats_null": (candidate < null_mae - TIE_ML) if complete else None,
            "production_beats_null": (production < null_mae - TIE_ML) if complete else None}


def _other_formula_pairs(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit N04: earlier or other formula revisions, each on its own – never mixed into the headline."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for p in pairs:
        groups[_formula_pair(p)].append(p)
    return [{"production_formula_id": key[0] or None, "candidate_formula_id": key[1] or None, "samples": len(items),
             "production_mae_ml": round(sum(p["production"] for p in items) / len(items), 1),
             "candidate_mae_ml": round(sum(p["candidate"] for p in items) / len(items), 1)}
            for key, items in sorted(groups.items())]


def shadow_comparison_summary(records: list[dict[str, Any]], *, days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    """Paired comparison production vs. candidate on the same sessions (observational only).

    Only pairs of the current formula pair enter the headline; other revisions are listed apart.
    Same conservative evidence rules as the learning-effectiveness comparison: minimum
    samples, independent ventilations (one mean per validation record) and distinct
    days, a positive 95 % interval of the clustered gain, a minimum effect and win rate.
    "Better" additionally needs the candidate to beat the null model "always 0 ml" clearly
    (formula study 2026-10-31: the null model was almost as good as the candidate).
    """
    every, excluded = _pairs(_scoped(records, days, now))
    pairs = [p for p in every if _formula_pair(p) == CURRENT_FORMULA_PAIR]
    others = _other_formula_pairs([p for p in every if _formula_pair(p) != CURRENT_FORMULA_PAIR])
    distinct_days = sorted({p["day"] for p in pairs if p["day"]})
    base = {"comparison_schema_version": COMPARISON_SCHEMA_VERSION, "observational_only": True,
            "auto_activation": False, "period_days": max(1, int(days)),
            "production_formula_ids": [PRODUCTION_FORMULA_ID] if pairs else [],
            "candidate_formula_ids": [CANDIDATE_FORMULA_ID] if pairs else [],
            "other_formula_pairs": others, "other_formula_samples": sum(o["samples"] for o in others),
            "excluded": excluded, "excluded_total": sum(excluded.values()), "samples": len(pairs),
            "quarantined_pairs": sum(1 for p in pairs if p["quarantined"]),
            "distinct_days": len(distinct_days), "first_day": distinct_days[0] if distinct_days else None,
            "last_day": distinct_days[-1] if distinct_days else None, **_null_check(pairs)}
    if not pairs:
        return {**base, "status": "no_data", "production_mae_ml": None, "candidate_mae_ml": None,
                "mae_difference_ml": None, "improvement_percent": None, "independent_sessions": 0,
                "candidate_wins": 0, "production_wins": 0, "ties": 0, "ci95_low_ml": None, "ci95_high_ml": None}
    production_mae = sum(p["production"] for p in pairs) / len(pairs)
    candidate_mae = sum(p["candidate"] for p in pairs) / len(pairs)
    improvement = (production_mae - candidate_mae) / production_mae * 100.0 if production_mae > 0 else None
    wins = sum(1 for p in pairs if p["production"] - p["candidate"] > TIE_ML)
    losses = sum(1 for p in pairs if p["candidate"] - p["production"] > TIE_ML)
    clusters: dict[str, list[float]] = defaultdict(list)
    for p in pairs:
        clusters[p["cluster"]].append(p["production"] - p["candidate"])
    gains = [sum(v) / len(v) for v in clusters.values()]
    mean_gain = sum(gains) / len(gains)
    ci_low = ci_high = None
    if len(gains) >= 2:
        margin = 1.96 * sqrt(sum((g - mean_gain) ** 2 for g in gains) / (len(gains) - 1)) / sqrt(len(gains))
        ci_low, ci_high = mean_gain - margin, mean_gain + margin
    cluster_wins = sum(1 for g in gains if g > TIE_ML)
    cluster_losses = sum(1 for g in gains if g < -TIE_ML)
    enough = len(pairs) >= MIN_EVIDENCE_SAMPLES and len(gains) >= MIN_EVIDENCE_SESSIONS and len(distinct_days) >= MIN_EVIDENCE_DAYS
    if not enough:
        status = "collecting"
    elif (ci_low is not None and ci_low > 0 and improvement is not None and improvement >= MIN_EFFECT_PERCENT
          and cluster_wins / len(gains) >= MIN_WIN_RATE and base["candidate_beats_null"] is True):
        status = "candidate_better"  # only when it also clearly beats "always 0 ml" on known null errors
    elif (ci_high is not None and ci_high < 0 and improvement is not None and improvement <= -MIN_EFFECT_PERCENT
          and cluster_losses / len(gains) >= MIN_WIN_RATE):
        status = "candidate_worse"
    else:
        status = "inconclusive"
    return {**base, "status": status, "production_mae_ml": round(production_mae, 1),
            "candidate_mae_ml": round(candidate_mae, 1), "mae_difference_ml": round(candidate_mae - production_mae, 1),
            "improvement_percent": round(improvement, 1) if improvement is not None else None,
            "independent_sessions": len(gains), "candidate_wins": wins, "production_wins": losses,
            "ties": len(pairs) - wins - losses,
            "ci95_low_ml": round(ci_low, 1) if ci_low is not None else None,
            "ci95_high_ml": round(ci_high, 1) if ci_high is not None else None,
            "evidence_rules": {"minimum_samples": MIN_EVIDENCE_SAMPLES, "minimum_independent_sessions": MIN_EVIDENCE_SESSIONS,
                               "minimum_distinct_days": MIN_EVIDENCE_DAYS, "minimum_effect_percent": MIN_EFFECT_PERCENT,
                               "minimum_win_rate_percent": round(MIN_WIN_RATE * 100.0, 1),
                               "requires_positive_clustered_ci95": True, "requires_beating_null_model": True}}
