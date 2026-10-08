"""Historical forecast backtesting for FreshAirIQ.

The backtest layer evaluates immutable validation records only.  It never writes
adaptive-learning state and never changes live forecast coefficients.  This
keeps retrospective model assessment independent from production decisions.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite, sqrt
from typing import Any, Iterable

BACKTEST_MIN_VERSION_SAMPLES = 3


def _number(value: Any) -> float | None:
    """Return a finite float or ``None`` for corrupt diagnostic input."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def _rmse(values: Iterable[float]) -> float | None:
    values = list(values)
    return sqrt(sum(value * value for value in values) / len(values)) if values else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * max(0.0, min(percentile, 1.0))
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _accuracy_percent(predicted: float, actual: float) -> float:
    """Return a bounded magnitude accuracy for calibration diagnostics.

    A 25 ml floor prevents tiny near-zero sessions from dominating the metric.
    Direction accuracy remains a separate metric and is not hidden by this score.
    """
    error = abs(actual - predicted)
    scale = max(abs(predicted), abs(actual), 25.0)
    return max(0.0, min(100.0, 100.0 * (1.0 - error / scale)))


def _horizon_bucket(minutes: float | None) -> str:
    if minutes is None:
        return "unknown"
    if minutes <= 5.0:
        return "0-5"
    if minutes <= 10.0:
        return "5-10"
    if minutes <= 15.0:
        return "10-15"
    if minutes <= 30.0:
        return "15-30"
    return "30+"


def _confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence < 60.0:
        return "0-59"
    if confidence < 75.0:
        return "60-74"
    if confidence < 85.0:
        return "75-84"
    if confidence < 95.0:
        return "85-94"
    return "95-100"


def _checkpoint_bucket(checkpoint: float | None) -> str:
    if checkpoint is None:
        return "unknown"
    if checkpoint <= 0.5:
        return "start"
    rounded = int(round(checkpoint / 5.0) * 5)
    return f"+{max(5, rounded)}"


def _record_stamp(item: dict[str, Any]) -> datetime | None:
    raw = item.get("ended_at") or item.get("started_at")
    try:
        return datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


def _scope_records(records: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    valid_stamps = [stamp for item in records if isinstance(item, dict) if (stamp := _record_stamp(item))]
    anchor = max(valid_stamps) if valid_stamps else datetime.now()
    cutoff = anchor.date() - timedelta(days=max(1, int(days)) - 1)
    scoped: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        stamp = _record_stamp(item)
        if stamp is not None and stamp.date() >= cutoff:
            scoped.append(item)
    return scoped


def _metric_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    moisture_signed = [float(sample["moisture_error_ml"]) for sample in samples if _number(sample.get("moisture_error_ml")) is not None]
    moisture_abs = [abs(value) for value in moisture_signed]
    temperature_abs = [abs(float(sample["temperature_error_c"])) for sample in samples if _number(sample.get("temperature_error_c")) is not None]
    close_abs = [abs(float(sample["close_time_error_min"])) for sample in samples if _number(sample.get("close_time_error_min")) is not None]
    cost_abs = [abs(float(sample["cost_error"])) for sample in samples if _number(sample.get("cost_error")) is not None]
    direction = [bool(sample["direction_correct"]) for sample in samples if sample.get("direction_correct") is not None]
    accuracy = [float(sample["magnitude_accuracy_percent"]) for sample in samples if _number(sample.get("magnitude_accuracy_percent")) is not None]
    return {
        "samples": len(samples),
        "moisture_mae_ml": round(_mean(moisture_abs), 1) if moisture_abs else None,
        "moisture_rmse_ml": round(_rmse(moisture_signed), 1) if moisture_signed else None,
        "moisture_bias_ml": round(_mean(moisture_signed), 1) if moisture_signed else None,
        "moisture_p90_abs_error_ml": round(_percentile(moisture_abs, 0.90), 1) if moisture_abs else None,
        "temperature_mae_c": round(_mean(temperature_abs), 3) if temperature_abs else None,
        "close_time_mae_min": round(_mean(close_abs), 2) if close_abs else None,
        "cost_mae": round(_mean(cost_abs), 4) if cost_abs else None,
        "direction_accuracy_percent": round(sum(direction) / len(direction) * 100.0, 1) if direction else None,
        "magnitude_accuracy_percent": round(_mean(accuracy), 1) if accuracy else None,
    }


def _room_samples(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict) or not record.get("valid"):
            continue
        version = str(record.get("model_version") or "unknown")
        ended_at = record.get("ended_at")
        for room in record.get("room_results") or []:
            if not isinstance(room, dict) or not room.get("comparable"):
                continue
            predicted = _number(room.get("predicted_removed_ml"))
            actual = _number(room.get("actual_removed_ml"))
            moisture_error = _number(room.get("moisture_error_ml"))
            sample = {
                "model_version": version,
                "ended_at": ended_at,
                "key": str(room.get("key") or "unknown"),
                "name": str(room.get("name") or room.get("key") or "unknown"),
                "forecast_horizon_min": _number(room.get("forecast_horizon_min")),
                "forecast_confidence": _number(room.get("forecast_confidence")),
                "predicted_removed_ml": predicted,
                "actual_removed_ml": actual,
                "moisture_error_ml": moisture_error,
                "temperature_error_c": _number(room.get("temperature_error_c")),
                "close_time_error_min": _number(room.get("close_time_error_min")),
                "cost_error": _number(room.get("cost_error")),
                "direction_correct": room.get("direction_correct"),
                "magnitude_accuracy_percent": (
                    _accuracy_percent(predicted, actual)
                    if predicted is not None and actual is not None else None
                ),
                "timeline": room.get("forecast_timeline") or [],
            }
            samples.append(sample)
    return samples



def _reliability_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Return empirical model quality separately from evidence maturity.

    The score is diagnostic only and never feeds the live forecast.  Magnitude
    accuracy, direction accuracy and confidence calibration remain visible as
    separate fields so the composite cannot hide a weak dimension.
    """
    summary = _metric_summary(samples)
    count = len(samples)
    magnitude = _number(summary.get("magnitude_accuracy_percent"))
    direction = _number(summary.get("direction_accuracy_percent"))
    calibration_pairs = [
        (
            _number(sample.get("forecast_confidence")),
            _number(sample.get("magnitude_accuracy_percent")),
        )
        for sample in samples
    ]
    calibration_gaps = [abs(empirical - reported) for reported, empirical in calibration_pairs if reported is not None and empirical is not None]
    calibration_mae = _mean(calibration_gaps) if calibration_gaps else None
    calibration_score = max(0.0, 100.0 - calibration_mae) if calibration_mae is not None else None
    evidence = min(count / 20.0, 1.0) * 100.0
    parts: list[tuple[float, float]] = []
    if magnitude is not None:
        parts.append((magnitude, 0.60))
    if direction is not None:
        parts.append((direction, 0.25))
    if calibration_score is not None:
        parts.append((calibration_score, 0.15))
    weight = sum(w for _, w in parts)
    empirical_quality = sum(v * w for v, w in parts) / weight if weight else None
    # Limited evidence must remain visible in the result.  Even excellent early
    # samples cannot present as fully established reliability.
    score = empirical_quality * (0.65 + 0.35 * evidence / 100.0) if empirical_quality is not None else None
    if count == 0:
        status = "Keine Vergleichsdaten"
    elif count < 3:
        status = "Erste Daten"
    elif evidence < 50:
        status = "Lernt"
    elif score is not None and score >= 90:
        status = "Sehr zuverlässig"
    elif score is not None and score >= 78:
        status = "Zuverlässig"
    elif score is not None and score >= 65:
        status = "Beobachten"
    else:
        status = "Noch instabil"
    return {
        "samples": count,
        "score_percent": round(score, 1) if score is not None else None,
        "empirical_quality_percent": round(empirical_quality, 1) if empirical_quality is not None else None,
        "evidence_maturity_percent": round(evidence, 1),
        "magnitude_accuracy_percent": round(magnitude, 1) if magnitude is not None else None,
        "direction_accuracy_percent": round(direction, 1) if direction is not None else None,
        "confidence_calibration_mae_points": round(calibration_mae, 1) if calibration_mae is not None else None,
        "status": status,
        "score_formula": "empirical quality = 60% magnitude + 25% direction + 15% confidence calibration; reliability is evidence-weighted until 20 comparable room samples",
    }

def _group_summary(samples: list[dict[str, Any]], key_fn) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(key_fn(sample))].append(sample)
    rows = []
    for key, bucket in grouped.items():
        row = {"bucket": key, **_metric_summary(bucket)}
        rows.append(row)
    return rows


def _timeline_replay(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        actual = _number(sample.get("actual_removed_ml"))
        if actual is None:
            continue
        for point in sample.get("timeline") or []:
            if not isinstance(point, dict):
                continue
            predicted = _number(point.get("predicted_final_removed_ml"))
            if predicted is None:
                continue
            bucket = _checkpoint_bucket(_number(point.get("checkpoint_min")))
            error = actual - predicted
            buckets[bucket].append({
                "moisture_error_ml": error,
                "temperature_error_c": _number(point.get("final_temperature_error_c")),
                "close_time_error_min": None,
                "cost_error": None,
                "direction_correct": ((predicted >= 0) == (actual >= 0)) if abs(predicted) > 5.0 and abs(actual) > 5.0 else abs(predicted - actual) <= 5.0,
                "magnitude_accuracy_percent": _accuracy_percent(predicted, actual),
            })
    order = {"start": 0}
    rows = []
    for bucket, points in buckets.items():
        row = {"checkpoint": bucket, **_metric_summary(points)}
        rows.append(row)
    rows.sort(key=lambda row: order.get(row["checkpoint"], int(str(row["checkpoint"]).lstrip("+") or 999) if str(row["checkpoint"]).startswith("+") else 999))
    return rows


def _version_comparison(version_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [row for row in version_rows if int(row.get("samples", 0)) >= BACKTEST_MIN_VERSION_SAMPLES]
    if len(eligible) < 2:
        return None
    # Preserve chronological occurrence order as represented by the source data.
    previous, current = eligible[-2], eligible[-1]
    metrics = {}
    for key in ("moisture_mae_ml", "temperature_mae_c", "close_time_mae_min"):
        old = _number(previous.get(key))
        new = _number(current.get(key))
        metrics[key] = round(new - old, 3) if old is not None and new is not None else None
    old_dir = _number(previous.get("direction_accuracy_percent"))
    new_dir = _number(current.get("direction_accuracy_percent"))
    metrics["direction_accuracy_delta_points"] = round(new_dir - old_dir, 1) if old_dir is not None and new_dir is not None else None
    old_acc = _number(previous.get("magnitude_accuracy_percent"))
    new_acc = _number(current.get("magnitude_accuracy_percent"))
    metrics["magnitude_accuracy_delta_points"] = round(new_acc - old_acc, 1) if old_acc is not None and new_acc is not None else None
    return {
        "previous_version": previous.get("version"),
        "current_version": current.get("version"),
        "minimum_samples_per_version": BACKTEST_MIN_VERSION_SAMPLES,
        "delta_current_minus_previous": metrics,
    }


def backtest_summary(records: list[dict[str, Any]], *, days: int = 30) -> dict[str, Any]:
    """Replay historical immutable forecasts against their measured outcomes.

    This is an observational backtest.  It does not re-run today's model against
    old sensor streams; instead it replays the exact forecast snapshots that were
    actually produced at the time.  That distinction is explicit in the output.
    """
    scoped = _scope_records(records, days)
    samples = _room_samples(scoped)

    horizon_rows = _group_summary(samples, lambda sample: _horizon_bucket(_number(sample.get("forecast_horizon_min"))))
    horizon_order = {"0-5": 0, "5-10": 1, "10-15": 2, "15-30": 3, "30+": 4, "unknown": 5}
    horizon_rows.sort(key=lambda row: horizon_order.get(str(row.get("bucket")), 99))

    confidence_rows = _group_summary(samples, lambda sample: _confidence_bucket(_number(sample.get("forecast_confidence"))))
    confidence_order = {"0-59": 0, "60-74": 1, "75-84": 2, "85-94": 3, "95-100": 4, "unknown": 5}
    confidence_rows.sort(key=lambda row: confidence_order.get(str(row.get("bucket")), 99))
    for row in confidence_rows:
        values = [
            _number(sample.get("forecast_confidence"))
            for sample in samples
            if _confidence_bucket(_number(sample.get("forecast_confidence"))) == row["bucket"]
        ]
        values = [value for value in values if value is not None]
        row["mean_reported_confidence_percent"] = round(_mean(values), 1) if values else None
        mean_conf = _number(row.get("mean_reported_confidence_percent"))
        empirical = _number(row.get("magnitude_accuracy_percent"))
        row["calibration_gap_points"] = round(empirical - mean_conf, 1) if empirical is not None and mean_conf is not None else None

    version_order: list[str] = []
    version_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        version = str(sample.get("model_version") or "unknown")
        if version not in version_order:
            version_order.append(version)
        version_buckets[version].append(sample)
    versions = [{"version": version, **_metric_summary(version_buckets[version])} for version in version_order]

    room_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    room_names: dict[str, str] = {}
    for sample in samples:
        key = str(sample.get("key") or "unknown")
        room_buckets[key].append(sample)
        room_names[key] = str(sample.get("name") or key)
    rooms = []
    for key, bucket in room_buckets.items():
        rooms.append({"key": key, "name": room_names.get(key, key), **_metric_summary(bucket), "reliability": _reliability_summary(bucket)})
    rooms.sort(key=lambda row: (-int(row.get("samples", 0)), str(row.get("name", ""))))

    outlier_candidates = [
        sample for sample in samples
        if _number(sample.get("moisture_error_ml")) is not None
    ]
    outlier_candidates.sort(key=lambda sample: abs(float(sample["moisture_error_ml"])), reverse=True)
    outliers = [{
        "ended_at": sample.get("ended_at"),
        "room_key": sample.get("key"),
        "room_name": sample.get("name"),
        "model_version": sample.get("model_version"),
        "horizon_min": sample.get("forecast_horizon_min"),
        "predicted_removed_ml": sample.get("predicted_removed_ml"),
        "actual_removed_ml": sample.get("actual_removed_ml"),
        "absolute_error_ml": round(abs(float(sample["moisture_error_ml"])), 1),
    } for sample in outlier_candidates[:5]]

    valid_record_count = sum(1 for item in scoped if isinstance(item, dict) and item.get("valid"))
    distinct_days = {str(sample.get("ended_at"))[:10] for sample in samples if sample.get("ended_at")}
    return {
        "backtest_engine": "v2",
        "mode": "historical_snapshot_replay",
        "period_days": max(1, int(days)),
        "record_count": len(scoped),
        "valid_record_count": valid_record_count,
        "room_sample_count": len(samples),
        "distinct_validation_days": len(distinct_days),
        "overall": _metric_summary(samples),
        "reliability": _reliability_summary(samples),
        "by_horizon": horizon_rows,
        "by_confidence": confidence_rows,
        "by_version": versions,
        "version_comparison": _version_comparison(versions),
        "timeline_replay": _timeline_replay(samples),
        "rooms": rooms,
        "largest_outliers": outliers,
        "limitations": [
            "Replays the immutable forecasts actually produced at the time; it does not apply the current model to historical raw sensor streams.",
            "Only sessions marked comparable by the Validation Engine are scored.",
        ],
    }
