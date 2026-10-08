"""Paired learning-effectiveness validation for FreshAirIQ.

The engine is deliberately observational. It never changes adaptive-learning
state, forecast coefficients, Shadow Learning or recommendations. For every
new objectively comparable ventilation it compares the exact frozen production
forecast with an unlearned physical baseline using the same start state,
weather boundary, controls and measured duration.

The primary comparison answers whether learned forecast parameters reduce
prediction error versus the same forecast engine without those learned terms.
When a prior distinct forecast snapshot exists, the same real session also
replays that immediately previous observed model generation. This second,
strictly observational comparison shows whether model evolution itself moved
forecast accuracy in the right direction.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
from math import isfinite, sqrt
from typing import Any, Callable

EFFECTIVENESS_SCHEMA_VERSION = 1
BASELINE_RATE_PER_MIN = 0.03
MIN_EVIDENCE_SAMPLES = 12
MIN_EVIDENCE_SESSIONS = 8
MIN_EVIDENCE_DAYS = 4
MIN_EFFECT_PERCENT = 5.0
MIN_WIN_RATE = 0.55


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _safe_int(value: Any, default: int = 0) -> int:
    number = _number(value)
    return max(int(number), 0) if number is not None else default


def _bucket_count(value: Any) -> str:
    count = _safe_int(value)
    if count == 0:
        return "0"
    if count <= 2:
        return "1-2"
    if count <= 5:
        return "3-5"
    if count <= 9:
        return "6-9"
    if count <= 19:
        return "10-19"
    if count <= 39:
        return "20-39"
    return "40+"


def _horizon_bucket(minutes: Any) -> str:
    value = _number(minutes)
    if value is None:
        return "unknown"
    if value <= 5:
        return "0-5"
    if value <= 10:
        return "5-10"
    if value <= 15:
        return "10-15"
    if value <= 30:
        return "15-30"
    return "30+"


def _source_temperature_bucket(value: Any) -> str:
    temp = _number(value)
    if temp is None:
        return "unknown"
    if temp < 0:
        return "<0"
    if temp < 10:
        return "0-10"
    if temp < 20:
        return "10-20"
    if temp < 30:
        return "20-30"
    return "30+"


def _gradient_bucket(current_ah: Any, source_ah: Any) -> str:
    current = _number(current_ah)
    source = _number(source_ah)
    if current is None or source is None:
        return "unknown"
    delta = current - source
    if delta <= 0:
        return "<=0"
    if delta < 1:
        return "0-1"
    if delta < 2:
        return "1-2"
    if delta < 4:
        return "2-4"
    return "4+"


def _season(raw_timestamp: Any) -> str:
    try:
        month = datetime.fromisoformat(str(raw_timestamp)).month
    except (TypeError, ValueError):
        return "unknown"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _same_direction(predicted: float, actual: float, deadband_ml: float = 5.0) -> bool:
    if abs(predicted) <= deadband_ml and abs(actual) <= deadband_ml:
        return True
    if abs(predicted) <= deadband_ml or abs(actual) <= deadband_ml:
        return False
    return (predicted > 0) == (actual > 0)


def _snapshot_id(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_model_snapshot(room_state: dict[str, Any], forecast_args: dict[str, Any]) -> dict[str, Any]:
    """Return an immutable, privacy-safe description of the forecast-learning state."""
    source_residual = _number(forecast_args.get("learned_source_ml_min"))
    thermal_residual = _number(forecast_args.get("learned_thermal_residual_c_min"))
    snapshot = {
        "rate_per_min": round(_number(forecast_args.get("rate_per_min")) or BASELINE_RATE_PER_MIN, 5),
        "learned_source_ml_min": round(source_residual, 4) if source_residual is not None else None,
        "learned_thermal_residual_c_min": round(thermal_residual, 5) if thermal_residual is not None else None,
        # horizon_forecast deliberately caps learned residual maturity at six
        # observations; keeping the same cap makes the signature represent the
        # actual forecast behaviour rather than an ever-growing counter.
        "observation_samples": min(_safe_int(forecast_args.get("observation_samples")), 6),
        "learning_samples": _safe_int(room_state.get("learning_samples")),
        # Context-only counters are exported for diagnostics. They are NOT part
        # of model_snapshot_id because outcome/shadow factors currently affect
        # recommendation simulation, not horizon_forecast itself.
        "outcome_feedback_samples": _safe_int(room_state.get("outcome_feedback_samples")),
        "shadow_promotions": _safe_int(room_state.get("shadow_learning_promotions")),
    }
    exact_signature = {
        key: snapshot[key]
        for key in (
            "rate_per_min",
            "learned_source_ml_min",
            "learned_thermal_residual_c_min",
            "observation_samples",
        )
    }
    snapshot["model_snapshot_id"] = _snapshot_id(exact_signature)
    snapshot["learning_stage_id"] = "|".join((
        f"physics:{_bucket_count(snapshot['learning_samples'])}",
        f"forecast:{_bucket_count(snapshot['observation_samples'])}",
    ))
    snapshot["context_learning_stage_id"] = "|".join((
        snapshot["learning_stage_id"],
        f"feedback:{_bucket_count(snapshot['outcome_feedback_samples'])}",
        f"shadow:{snapshot['shadow_promotions']}",
    ))
    return snapshot


def previous_model_snapshot_from_history(
    records: Any,
    room_key: Any,
    current_snapshot_id: Any,
) -> dict[str, Any] | None:
    """Return the newest distinct forecast snapshot previously observed for a room."""
    if not isinstance(records, list) or not room_key or not current_snapshot_id:
        return None
    wanted_key = str(room_key)
    current_id = str(current_snapshot_id)
    for record in reversed(records):
        if not isinstance(record, dict):
            continue
        for room in reversed(record.get("room_results") or []):
            if not isinstance(room, dict) or str(room.get("key") or "") != wanted_key:
                continue
            sample = room.get("learning_effectiveness")
            if not isinstance(sample, dict) or not sample.get("valid"):
                continue
            snapshot = sample.get("model_snapshot")
            if not isinstance(snapshot, dict):
                continue
            snapshot_id = snapshot.get("model_snapshot_id")
            if snapshot_id and str(snapshot_id) != current_id:
                return deepcopy(snapshot)
    return None


def _context_with_model_snapshot(start_context: Any, snapshot: Any) -> dict[str, Any] | None:
    """Replay one historic forecast snapshot under the current physical start state."""
    if not isinstance(start_context, dict) or not isinstance(snapshot, dict):
        return None
    replay = deepcopy(start_context)
    replay.pop("learning_effectiveness", None)
    args = replay.get("forecast_args")
    if not isinstance(args, dict):
        return None
    required = ("rate_per_min", "observation_samples")
    if any(key not in snapshot for key in required):
        return None
    rate = _number(snapshot.get("rate_per_min"))
    if rate is None:
        return None
    args["rate_per_min"] = rate
    args["learned_source_ml_min"] = _number(snapshot.get("learned_source_ml_min"))
    args["learned_thermal_residual_c_min"] = _number(snapshot.get("learned_thermal_residual_c_min"))
    args["observation_samples"] = _safe_int(snapshot.get("observation_samples"))
    return replay


def freeze_learning_effectiveness_context(
    start_context: dict[str, Any],
    room_state: dict[str, Any],
    *,
    history: Any = None,
    room_key: Any = None,
) -> dict[str, Any] | None:
    """Freeze baseline and, when available, the prior distinct forecast generation."""
    if not isinstance(start_context, dict):
        return None
    production_args = start_context.get("forecast_args")
    if not isinstance(production_args, dict):
        return None
    baseline_context = deepcopy(start_context)
    baseline_context.pop("learning_effectiveness", None)
    baseline_args = baseline_context.get("forecast_args")
    if not isinstance(baseline_args, dict):
        return None

    # Remove only adaptive forecast terms. Everything describing the physical
    # event stays identical: room/start climate, airflow, target, future weather,
    # controls, energy assumptions and the subsequently measured duration.
    baseline_args["rate_per_min"] = BASELINE_RATE_PER_MIN
    baseline_args["learned_source_ml_min"] = None
    baseline_args["learned_thermal_residual_c_min"] = None
    baseline_args["observation_samples"] = 0
    baseline_args["model_maturity_pct"] = 55.0
    baseline_args["recent_observed_removed_ml_min"] = None
    baseline_args["running"] = False
    baseline_args["session_elapsed_min"] = 0.0
    baseline_args["session_fresh_measurements"] = 0
    model_snapshot = build_model_snapshot(room_state, production_args)
    previous_snapshot = previous_model_snapshot_from_history(
        history, room_key, model_snapshot.get("model_snapshot_id")
    )
    previous_context = _context_with_model_snapshot(start_context, previous_snapshot)
    return {
        "schema_version": EFFECTIVENESS_SCHEMA_VERSION,
        "model_snapshot": model_snapshot,
        "baseline_context": baseline_context,
        "baseline_definition": "rate=0.03/min; no learned moisture/thermal residuals; same start state, source boundary, controls and measured duration",
        "previous_model_snapshot": previous_snapshot,
        "previous_model_context": previous_context,
        "generation_definition": "current forecast snapshot versus newest distinct previously observed snapshot for the same room; identical current start state, source boundary, controls and measured duration",
    }


def baseline_context_from_start(start_context: Any) -> dict[str, Any] | None:
    if not isinstance(start_context, dict):
        return None
    frozen = start_context.get("learning_effectiveness")
    if not isinstance(frozen, dict):
        return None
    try:
        schema_version = int(frozen.get("schema_version", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if schema_version != EFFECTIVENESS_SCHEMA_VERSION:
        return None
    baseline = frozen.get("baseline_context")
    return deepcopy(baseline) if isinstance(baseline, dict) else None


def previous_model_context_from_start(start_context: Any) -> dict[str, Any] | None:
    if not isinstance(start_context, dict):
        return None
    frozen = start_context.get("learning_effectiveness")
    if not isinstance(frozen, dict):
        return None
    try:
        schema_version = int(frozen.get("schema_version", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if schema_version != EFFECTIVENESS_SCHEMA_VERSION:
        return None
    previous = frozen.get("previous_model_context")
    return deepcopy(previous) if isinstance(previous, dict) else None


def build_effectiveness_sample(
    start_context: Any,
    *,
    duration_min: Any,
    production_prediction: Any,
    baseline_prediction: Any,
    previous_model_prediction: Any = None,
    actual_removed_ml: Any,
    ended_at: Any,
) -> dict[str, Any] | None:
    """Build one paired production-vs-baseline score for the same real session."""
    if not isinstance(start_context, dict):
        return None
    frozen = start_context.get("learning_effectiveness")
    if not isinstance(frozen, dict) or frozen.get("schema_version") != EFFECTIVENESS_SCHEMA_VERSION:
        return None
    if not isinstance(production_prediction, dict) or not isinstance(baseline_prediction, dict):
        return None
    production = _number(production_prediction.get("predicted_removed_ml"))
    baseline = _number(baseline_prediction.get("predicted_removed_ml"))
    actual = _number(actual_removed_ml)
    duration = _number(duration_min)
    if production is None or baseline is None or actual is None or duration is None:
        return None

    production_error = abs(actual - production)
    baseline_error = abs(actual - baseline)
    gain = baseline_error - production_error
    relative = gain / max(baseline_error, 1.0) * 100.0
    if abs(production_error - baseline_error) <= 1.0:
        winner = "tie"
    elif production_error < baseline_error:
        winner = "learned"
    else:
        winner = "baseline"

    args = start_context.get("forecast_args") if isinstance(start_context.get("forecast_args"), dict) else {}
    snapshot = frozen.get("model_snapshot") if isinstance(frozen.get("model_snapshot"), dict) else {}
    previous_snapshot = frozen.get("previous_model_snapshot") if isinstance(frozen.get("previous_model_snapshot"), dict) else {}
    result = {
        "schema_version": EFFECTIVENESS_SCHEMA_VERSION,
        "valid": True,
        "ended_at": ended_at,
        "duration_min": round(duration, 3),
        "horizon_bucket": _horizon_bucket(duration),
        "season": _season(ended_at),
        "source_temperature_bucket": _source_temperature_bucket(args.get("source_temp_c")),
        "ah_gradient_bucket": _gradient_bucket(args.get("current_ah"), args.get("source_ah")),
        "uses_future_weather": bool(args.get("future_source_boundaries")),
        "production_predicted_removed_ml": round(production, 1),
        "baseline_predicted_removed_ml": round(baseline, 1),
        "actual_removed_ml": round(actual, 1),
        "production_abs_error_ml": round(production_error, 1),
        "baseline_abs_error_ml": round(baseline_error, 1),
        "paired_error_gain_ml": round(gain, 1),
        "paired_improvement_percent": round(relative, 1),
        "winner": winner,
        "production_direction_correct": _same_direction(production, actual),
        "baseline_direction_correct": _same_direction(baseline, actual),
        "model_snapshot_id": snapshot.get("model_snapshot_id"),
        "learning_stage_id": snapshot.get("learning_stage_id"),
        "context_learning_stage_id": snapshot.get("context_learning_stage_id"),
        "model_snapshot": deepcopy(snapshot),
        "baseline_definition": frozen.get("baseline_definition"),
        "generation_valid": False,
    }
    previous = (
        _number(previous_model_prediction.get("predicted_removed_ml"))
        if isinstance(previous_model_prediction, dict) else None
    )
    if previous is not None and previous_snapshot.get("model_snapshot_id"):
        previous_error = abs(actual - previous)
        generation_gain = previous_error - production_error
        generation_relative = generation_gain / max(previous_error, 1.0) * 100.0
        if abs(production_error - previous_error) <= 1.0:
            generation_winner = "tie"
        elif production_error < previous_error:
            generation_winner = "current"
        else:
            generation_winner = "previous"
        result.update({
            "generation_valid": True,
            "previous_model_predicted_removed_ml": round(previous, 1),
            "previous_model_abs_error_ml": round(previous_error, 1),
            "generation_error_gain_ml": round(generation_gain, 1),
            "generation_improvement_percent": round(generation_relative, 1),
            "generation_winner": generation_winner,
            "previous_model_direction_correct": _same_direction(previous, actual),
            "previous_model_snapshot_id": previous_snapshot.get("model_snapshot_id"),
            "previous_model_snapshot": deepcopy(previous_snapshot),
            "generation_definition": frozen.get("generation_definition"),
        })
    return result


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cluster_gains(samples: list[dict[str, Any]]) -> list[float]:
    clusters: dict[str, list[float]] = defaultdict(list)
    for index, sample in enumerate(samples):
        cluster_id = str(sample.get("validation_record_id") or f"sample-{index}")
        gain = _number(sample.get("paired_error_gain_ml"))
        if gain is not None:
            clusters[cluster_id].append(gain)
    return [sum(values) / len(values) for values in clusters.values() if values]


def _paired_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    production_errors = [float(x["production_abs_error_ml"]) for x in samples]
    baseline_errors = [float(x["baseline_abs_error_ml"]) for x in samples]
    gains = [float(x["paired_error_gain_ml"]) for x in samples]
    production_mae = _mean(production_errors)
    baseline_mae = _mean(baseline_errors)
    gain_mean = _mean(gains)
    improvement = (
        (baseline_mae - production_mae) / max(baseline_mae, 1.0) * 100.0
        if baseline_mae is not None and production_mae is not None else None
    )
    wins = sum(1 for x in samples if x.get("winner") == "learned")
    baseline_wins = sum(1 for x in samples if x.get("winner") == "baseline")
    ties = len(samples) - wins - baseline_wins
    days = {str(x.get("ended_at"))[:10] for x in samples if x.get("ended_at")}

    # Simultaneously ventilated rooms are correlated. Confidence therefore uses
    # one mean paired gain per completed validation record, not every room as an
    # independent observation. This prevents false confidence from many rooms in
    # one ventilation event.
    clustered_gains = _cluster_gains(samples)
    ci_low = ci_high = None
    cluster_gain_mean = _mean(clustered_gains)
    if len(clustered_gains) >= 2 and cluster_gain_mean is not None:
        variance = sum((value - cluster_gain_mean) ** 2 for value in clustered_gains) / (len(clustered_gains) - 1)
        margin = 1.96 * sqrt(variance) / sqrt(len(clustered_gains))
        ci_low = cluster_gain_mean - margin
        ci_high = cluster_gain_mean + margin

    cluster_wins = sum(1 for value in clustered_gains if value > 1.0)
    cluster_losses = sum(1 for value in clustered_gains if value < -1.0)
    cluster_ties = len(clustered_gains) - cluster_wins - cluster_losses
    cluster_win_rate = cluster_wins / len(clustered_gains) if clustered_gains else None

    enough_evidence = (
        len(samples) >= MIN_EVIDENCE_SAMPLES
        and len(clustered_gains) >= MIN_EVIDENCE_SESSIONS
        and len(days) >= MIN_EVIDENCE_DAYS
    )
    if not enough_evidence:
        status = "collecting"
        label = "Sammelt Vergleichsdaten"
    elif (
        ci_low is not None and ci_low > 0
        and improvement is not None and improvement >= MIN_EFFECT_PERCENT
        and cluster_win_rate is not None and cluster_win_rate >= MIN_WIN_RATE
    ):
        status = "improving"
        label = "Lernmodell besser belegt"
    elif (
        ci_high is not None and ci_high < 0
        and improvement is not None and improvement <= -MIN_EFFECT_PERCENT
        and cluster_win_rate is not None and (1.0 - cluster_win_rate) >= MIN_WIN_RATE
    ):
        status = "regressing"
        label = "Lernmodell schlechter belegt"
    else:
        status = "inconclusive"
        label = "Noch kein eindeutiger Lerneffekt"

    return {
        "samples": len(samples),
        "independent_sessions": len(clustered_gains),
        "distinct_days": len(days),
        "production_mae_ml": round(production_mae, 1) if production_mae is not None else None,
        "baseline_mae_ml": round(baseline_mae, 1) if baseline_mae is not None else None,
        "paired_error_gain_ml": round(gain_mean, 1) if gain_mean is not None else None,
        "session_mean_paired_error_gain_ml": round(cluster_gain_mean, 1) if cluster_gain_mean is not None else None,
        "improvement_percent": round(improvement, 1) if improvement is not None else None,
        "learned_wins": wins,
        "baseline_wins": baseline_wins,
        "ties": ties,
        "learned_win_rate_percent": round(wins / len(samples) * 100.0, 1) if samples else None,
        "independent_session_wins": cluster_wins,
        "independent_session_losses": cluster_losses,
        "independent_session_ties": cluster_ties,
        "independent_session_win_rate_percent": round(cluster_win_rate * 100.0, 1) if cluster_win_rate is not None else None,
        "paired_gain_ci95_low_ml": round(ci_low, 1) if ci_low is not None else None,
        "paired_gain_ci95_high_ml": round(ci_high, 1) if ci_high is not None else None,
        "production_direction_accuracy_percent": round(sum(bool(x.get("production_direction_correct")) for x in samples) / len(samples) * 100.0, 1) if samples else None,
        "baseline_direction_accuracy_percent": round(sum(bool(x.get("baseline_direction_correct")) for x in samples) / len(samples) * 100.0, 1) if samples else None,
        "status": status,
        "status_label": label,
        "improvement_claim_supported": status == "improving",
    }


def _generation_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize current-vs-previous observed model generations on paired sessions."""
    comparable: list[dict[str, Any]] = []
    transitions: set[str] = set()
    for sample in samples:
        current_error = _number(sample.get("production_abs_error_ml"))
        previous_error = _number(sample.get("previous_model_abs_error_ml"))
        gain = _number(sample.get("generation_error_gain_ml"))
        if not sample.get("generation_valid") or current_error is None or previous_error is None or gain is None:
            continue
        winner = str(sample.get("generation_winner") or "tie")
        comparable.append({
            **sample,
            "production_abs_error_ml": current_error,
            "baseline_abs_error_ml": previous_error,
            "paired_error_gain_ml": gain,
            "winner": "learned" if winner == "current" else "baseline" if winner == "previous" else "tie",
            "production_direction_correct": bool(sample.get("production_direction_correct")),
            "baseline_direction_correct": bool(sample.get("previous_model_direction_correct")),
        })
        previous_id = str(sample.get("previous_model_snapshot_id") or "unknown")
        current_id = str(sample.get("model_snapshot_id") or "unknown")
        transitions.add(f"{previous_id}->{current_id}")
    summary = _paired_summary(comparable)
    return {
        "mode": "current_vs_previous_observed_generation",
        "observational_only": True,
        "samples": summary["samples"],
        "independent_sessions": summary["independent_sessions"],
        "distinct_days": summary["distinct_days"],
        "transition_count": len(transitions),
        "current_model_mae_ml": summary["production_mae_ml"],
        "previous_model_mae_ml": summary["baseline_mae_ml"],
        "generation_error_gain_ml": summary["paired_error_gain_ml"],
        "session_mean_generation_error_gain_ml": summary["session_mean_paired_error_gain_ml"],
        "improvement_percent": summary["improvement_percent"],
        "current_generation_wins": summary["learned_wins"],
        "previous_generation_wins": summary["baseline_wins"],
        "ties": summary["ties"],
        "independent_session_wins": summary["independent_session_wins"],
        "independent_session_losses": summary["independent_session_losses"],
        "independent_session_ties": summary["independent_session_ties"],
        "independent_session_win_rate_percent": summary["independent_session_win_rate_percent"],
        "generation_gain_ci95_low_ml": summary["paired_gain_ci95_low_ml"],
        "generation_gain_ci95_high_ml": summary["paired_gain_ci95_high_ml"],
        "current_direction_accuracy_percent": summary["production_direction_accuracy_percent"],
        "previous_direction_accuracy_percent": summary["baseline_direction_accuracy_percent"],
        "status": summary["status"],
        "status_label": (
            "Aktuelle Modellgeneration besser belegt" if summary["status"] == "improving" else
            "Aktuelle Modellgeneration schlechter belegt" if summary["status"] == "regressing" else
            "Sammelt Generationenvergleiche" if summary["status"] == "collecting" else
            "Noch kein eindeutiger Generationseffekt"
        ),
        "improvement_claim_supported": summary["improvement_claim_supported"],
    }


def _scope_records(records: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    stamps: list[datetime] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        raw = item.get("ended_at") or item.get("started_at")
        try:
            stamps.append(datetime.fromisoformat(str(raw)))
        except (TypeError, ValueError):
            continue
    anchor = max(stamps) if stamps else datetime.now()
    cutoff = anchor.date() - timedelta(days=max(1, int(days)) - 1)
    scoped: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        raw = item.get("ended_at") or item.get("started_at")
        try:
            stamp = datetime.fromisoformat(str(raw))
        except (TypeError, ValueError):
            continue
        if stamp.date() >= cutoff:
            scoped.append(item)
    return scoped


def _record_id(record: dict[str, Any], index: int) -> str:
    payload = {
        "started_at": record.get("started_at"),
        "ended_at": record.get("ended_at"),
        "model_version": record.get("model_version"),
        "index": index,
    }
    return _snapshot_id(payload)


def _extract_samples(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        if not isinstance(record, dict) or not record.get("valid"):
            continue
        validation_record_id = _record_id(record, record_index)
        for room in record.get("room_results") or []:
            if not isinstance(room, dict) or not room.get("comparable"):
                continue
            sample = room.get("learning_effectiveness")
            if not isinstance(sample, dict) or not sample.get("valid"):
                continue
            if _number(sample.get("production_abs_error_ml")) is None or _number(sample.get("baseline_abs_error_ml")) is None:
                continue
            samples.append(dict(
                sample,
                room_key=str(room.get("key") or "unknown"),
                room_name=str(room.get("name") or room.get("key") or "unknown"),
                validation_record_id=validation_record_id,
                model_version=str(record.get("model_version") or "unknown"),
            ))
    samples.sort(key=lambda x: str(x.get("ended_at") or ""))
    return samples


def _grouped(samples: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], str], *, label_key: str = "bucket") -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        buckets[str(key_fn(sample))].append(sample)
    return [{label_key: key, **_paired_summary(bucket)} for key, bucket in buckets.items()]


def _progression(samples: list[dict[str, Any]]) -> dict[str, Any] | None:
    ordered_ids: list[str] = []
    for sample in samples:
        record_id = str(sample.get("validation_record_id") or "")
        if record_id and record_id not in ordered_ids:
            ordered_ids.append(record_id)
    if len(ordered_ids) < 12:
        return None
    midpoint = len(ordered_ids) // 2
    earlier_ids = set(ordered_ids[:midpoint])
    recent_ids = set(ordered_ids[midpoint:])
    earlier = [sample for sample in samples if str(sample.get("validation_record_id") or "") in earlier_ids]
    recent = [sample for sample in samples if str(sample.get("validation_record_id") or "") in recent_ids]
    return {
        "observational_only": True,
        "earlier": _paired_summary(earlier),
        "recent": _paired_summary(recent),
    }


def learning_effectiveness_summary(records: list[dict[str, Any]], *, days: int = 30) -> dict[str, Any]:
    """Summarize whether learned forecasts beat the fixed baseline on paired sessions."""
    scoped = _scope_records(records, days)
    samples = _extract_samples(scoped)
    overall = _paired_summary(samples)

    room_names = {str(x.get("room_key")): str(x.get("room_name")) for x in samples}
    by_room = _grouped(samples, lambda x: str(x.get("room_key")), label_key="key")
    for row in by_room:
        row["name"] = room_names.get(str(row.get("key")), str(row.get("key")))
    by_room.sort(key=lambda x: (-int(x.get("samples", 0)), str(x.get("name", ""))))

    horizon_order = {"0-5": 0, "5-10": 1, "10-15": 2, "15-30": 3, "30+": 4, "unknown": 5}
    by_horizon = _grouped(samples, lambda x: str(x.get("horizon_bucket") or "unknown"))
    by_horizon.sort(key=lambda x: horizon_order.get(str(x.get("bucket")), 99))

    season_order = {"spring": 0, "summer": 1, "autumn": 2, "winter": 3, "unknown": 4}
    by_season = _grouped(samples, lambda x: str(x.get("season") or "unknown"))
    by_season.sort(key=lambda x: season_order.get(str(x.get("bucket")), 99))

    temp_order = {"<0": 0, "0-10": 1, "10-20": 2, "20-30": 3, "30+": 4, "unknown": 5}
    by_source_temperature = _grouped(samples, lambda x: str(x.get("source_temperature_bucket") or "unknown"))
    by_source_temperature.sort(key=lambda x: temp_order.get(str(x.get("bucket")), 99))

    gradient_order = {"<=0": 0, "0-1": 1, "1-2": 2, "2-4": 3, "4+": 4, "unknown": 5}
    by_ah_gradient = _grouped(samples, lambda x: str(x.get("ah_gradient_bucket") or "unknown"))
    by_ah_gradient.sort(key=lambda x: gradient_order.get(str(x.get("bucket")), 99))

    by_stage = _grouped(samples, lambda x: str(x.get("learning_stage_id") or "unknown"), label_key="learning_stage_id")
    stage_order: list[str] = []
    for sample in samples:
        stage = str(sample.get("learning_stage_id") or "unknown")
        if stage not in stage_order:
            stage_order.append(stage)
    by_stage.sort(key=lambda x: stage_order.index(str(x.get("learning_stage_id"))) if str(x.get("learning_stage_id")) in stage_order else 999)

    return {
        "effectiveness_engine": "v1",
        "mode": "paired_same_session_baseline",
        "observational_only": True,
        "period_days": max(1, int(days)),
        "record_count": len(scoped),
        "tracking_started_at": samples[0].get("ended_at") if samples else None,
        "latest_sample_at": samples[-1].get("ended_at") if samples else None,
        **overall,
        "by_room": by_room,
        "by_horizon": by_horizon,
        "by_season": by_season,
        "by_source_temperature": by_source_temperature,
        "by_ah_gradient": by_ah_gradient,
        "by_learning_stage": by_stage,
        "progression": _progression(samples),
        "generation_effectiveness": _generation_summary(samples),
        "baseline_definition": "Unlearned physical reference with 0.03/min exchange rate and no learned moisture/thermal residuals; all other start conditions, source boundaries, controls and measured duration are identical to production.",
        "evidence_rules": {
            "minimum_samples": MIN_EVIDENCE_SAMPLES,
            "minimum_independent_sessions": MIN_EVIDENCE_SESSIONS,
            "minimum_distinct_days": MIN_EVIDENCE_DAYS,
            "minimum_effect_percent": MIN_EFFECT_PERCENT,
            "minimum_independent_session_win_rate_percent": round(MIN_WIN_RATE * 100.0, 1),
            "requires_positive_clustered_ci95": True,
        },
        "limitations": [
            "Tracking starts only with sessions recorded after this engine was installed; historic baselines are not reconstructed.",
            "The 95% interval is an approximate normal interval over one mean paired gain per completed ventilation record.",
            "The baseline comparison validates learned horizon-forecast parameters. The generation comparison replays the newest distinct prior observed forecast snapshot for the same room under the current session's physical start state.",
            "Shadow/outcome factors that only affect recommendation simulation are intentionally not credited as forecast improvements or model-generation changes.",
            "Season and weather buckets remain descriptive until they contain enough independent evidence themselves.",
        ],
    }
