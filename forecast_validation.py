"""Objective forecast validation for completed FreshAirIQ ventilation sessions.

The validation layer is deliberately read-only with respect to adaptive learning:
it measures forecast quality but never changes model coefficients.  This keeps
model validation independent from the mechanism it is validating.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from math import sqrt
from typing import Any

from .energy import ventilation_cost_for_duration, ventilation_cost_for_temperature_path
from .forecast import horizon_forecast

VALIDATION_RETENTION_DAYS = 30
VALIDATION_MAX_RECORDS = 500


START_FORECAST_CONTEXT_VERSION = 2

_FORECAST_CONTROL_KEYS = (
    "min_return_next_5_min_ml",
    "max_temp_loss_next_5_min_c",
    "min_efficiency_ml_per_01c",
    "min_duration_min",
    "max_duration_min",
    "operating_profile",
)

_ENERGY_OPTION_KEYS = (
    "heating_system",
    "electricity_price_per_kwh",
    "heat_pump_cop",
    "gas_price_per_kwh",
    "gas_efficiency",
    "district_price_per_kwh",
    "district_efficiency",
    "oil_price_per_liter",
    "oil_kwh_per_liter",
    "oil_efficiency",
)


def freeze_start_forecast_context(
    forecast_args: dict[str, Any],
    *,
    target_ah: float,
    options: dict[str, Any],
    start_ah: float,
    start_source_ah: float,
    start_temp_c: float,
    start_source_temp_c: float,
) -> dict[str, Any]:
    """Freeze everything needed to replay the START forecast at any duration.

    The user's actual closing time is not known when a ventilation starts.
    Storing one arbitrary 5/15/20 minute number therefore creates a time-basis
    mismatch for almost every real session.  Instead FreshAirIQ freezes the
    *start model state*.  At session end that immutable state can be evaluated
    at the actually measured duration without using any measurements that
    arrived after the start.
    """
    args = deepcopy(dict(forecast_args or {}))
    args.update({
        "current_ah": float(start_ah),
        "source_ah": float(start_source_ah),
        "current_temp_c": float(start_temp_c),
        "source_temp_c": float(start_source_temp_c),
        # A start forecast must never contain live-session corrections that were
        # learned only after the window had already been open for a while.
        "running": False,
        "session_elapsed_min": 0.0,
        "session_fresh_measurements": 0,
        "recent_observed_removed_ml_min": None,
    })
    return {
        "version": START_FORECAST_CONTEXT_VERSION,
        "forecast_args": args,
        "target_ah": float(target_ah),
        "controls": {key: deepcopy(options.get(key)) for key in _FORECAST_CONTROL_KEYS},
        "energy_options": {key: deepcopy(options.get(key)) for key in _ENERGY_OPTION_KEYS},
    }


def evaluate_start_forecast_at_duration(
    context: dict[str, Any] | None,
    duration_min: float,
) -> dict[str, Any] | None:
    """Replay a frozen start model at the actual measurement duration.

    This is a genuine start forecast: only start-time state/model inputs are
    used.  The end timestamp selects the point on that frozen forecast curve;
    it does not feed any end measurement into the prediction.
    """
    if not isinstance(context, dict) or int(context.get("version", 0) or 0) != START_FORECAST_CONTEXT_VERSION:
        return None
    try:
        duration = float(duration_min)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (1.0 <= duration <= 120.0):
        return None

    args = deepcopy(context.get("forecast_args") or {})
    required = {"current_ah", "source_ah", "current_temp_c", "source_temp_c", "volume_m3", "rate_per_min", "airflow_bonus"}
    if not required.issubset(args):
        return None

    # JSON persistence converts integer weather-boundary keys to strings.
    boundaries = args.get("future_source_boundaries")
    if isinstance(boundaries, dict):
        normalized: dict[int, dict[str, Any]] = {}
        for key, value in boundaries.items():
            try:
                minute = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                normalized[minute] = value
        args["future_source_boundaries"] = normalized or None

    controls = dict(context.get("controls") or {})
    forecast = horizon_forecast(
        horizon_min=duration,
        target_ah=float(context.get("target_ah")),
        cap_positive_to_target=duration > 5.0,
        min_return_next_5_min_ml=float(controls.get("min_return_next_5_min_ml", 25.0)),
        max_temp_loss_next_5_min_c=float(controls.get("max_temp_loss_next_5_min_c", 0.6)),
        min_efficiency_ml_per_01c=float(controls.get("min_efficiency_ml_per_01c", 8.0)),
        min_duration_min=float(controls.get("min_duration_min", 3.0)),
        max_duration_min=float(controls.get("max_duration_min", 20.0)),
        operating_profile=str(controls.get("operating_profile", "comfort")),
        **args,
    )

    energy_options = dict(context.get("energy_options") or {})
    temperature_path = forecast.get("temperature_path") or []
    if temperature_path:
        _delivered, _purchased, cost = ventilation_cost_for_temperature_path(
            float(args["volume_m3"]),
            float(args["rate_per_min"]),
            float(args["airflow_bonus"]),
            temperature_path,
            energy_options,
        )
    else:
        _delivered, _purchased, cost = ventilation_cost_for_duration(
            float(args["volume_m3"]),
            float(args["current_temp_c"]),
            float(args["source_temp_c"]),
            float(args["rate_per_min"]),
            duration,
            float(args["airflow_bonus"]),
            energy_options,
        )
    if float(forecast.get("temperature_change_c", 0.0) or 0.0) >= 0.0:
        cost = 0.0

    return {
        "duration_min": round(duration, 3),
        "predicted_removed_ml": float(forecast.get("net_moisture_change_ml", 0.0) or 0.0),
        "predicted_temperature_change_c": float(forecast.get("temperature_change_c", 0.0) or 0.0),
        "predicted_cost": float(cost or 0.0),
        "confidence": int(forecast.get("confidence", 0) or 0),
        "method": str(forecast.get("method") or "unknown"),
        "forecast": forecast,
    }


def prediction_duration_comparable(actual_duration_min: float, forecast_horizon_min: float) -> bool:
    """Return whether a frozen start forecast may be scored against a session.

    Forecast calibration must compare like with like. The previous tolerance
    (35% with a three-minute floor) allowed a 20-minute prediction to be
    learned from sessions as short as 13 minutes. Keep the tolerance tight:
    10% of the horizon, bounded to one-to-two minutes.
    """
    try:
        actual = max(float(actual_duration_min), 0.0)
        horizon = max(float(forecast_horizon_min), 1.0)
    except (TypeError, ValueError):
        return False
    tolerance = min(2.0, max(1.0, horizon * 0.10))
    return abs(actual - horizon) <= tolerance


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _rmse(values: list[float]) -> float | None:
    return sqrt(sum(value * value for value in values) / len(values)) if values else None


def _same_direction(predicted: float, actual: float, deadband_ml: float = 5.0) -> bool:
    """Return whether forecast and observation describe the same moisture direction."""
    if abs(predicted) <= deadband_ml and abs(actual) <= deadband_ml:
        return True
    if abs(predicted) <= deadband_ml or abs(actual) <= deadband_ml:
        return False
    return (predicted > 0) == (actual > 0)


def _timeline_rows(item: dict[str, Any], actual_removed: float | None, actual_temp: float | None) -> list[dict[str, Any]]:
    """Normalize one room's time-resolved forecast trajectory for diagnostics."""
    rows: list[dict[str, Any]] = []
    raw_rows = item.get("forecast_timeline") or []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        predicted_final = _number(raw.get("predicted_final_removed_ml"))
        predicted_temp = _number(raw.get("predicted_final_temperature_change_c"))
        row = {
            "kind": str(raw.get("kind") or "live"),
            "checkpoint_min": _number(raw.get("checkpoint_min")),
            "captured_at": raw.get("captured_at"),
            "elapsed_min": _number(raw.get("elapsed_min")),
            "timing_error_min": _number(raw.get("timing_error_min")),
            "actual_removed_ml": _number(raw.get("actual_removed_ml")),
            "actual_temperature_change_c": _number(raw.get("actual_temperature_change_c")),
            "predicted_final_removed_ml": predicted_final,
            "predicted_final_temperature_change_c": predicted_temp,
            "remaining_horizon_min": _number(raw.get("remaining_horizon_min")),
            "next_5_min_net_moisture_change_ml": _number(raw.get("next_5_min_net_moisture_change_ml")),
            "next_5_min_temperature_change_c": _number(raw.get("next_5_min_temperature_change_c")),
            "confidence": _number(raw.get("confidence")),
            "method": raw.get("method"),
            "measurement_frame_quality": raw.get("measurement_frame_quality"),
            "measurement_frame_skew_s": _number(raw.get("measurement_frame_skew_s")),
            "measurement_frame_max_age_s": _number(raw.get("measurement_frame_max_age_s")),
        }
        if predicted_final is not None and actual_removed is not None:
            error = actual_removed - predicted_final
            row["final_moisture_error_ml"] = round(error, 1)
            row["final_moisture_abs_error_ml"] = round(abs(error), 1)
        else:
            row["final_moisture_error_ml"] = None
            row["final_moisture_abs_error_ml"] = None
        if predicted_temp is not None and actual_temp is not None:
            terr = actual_temp - predicted_temp
            row["final_temperature_error_c"] = round(terr, 2)
            row["final_temperature_abs_error_c"] = round(abs(terr), 2)
        else:
            row["final_temperature_error_c"] = None
            row["final_temperature_abs_error_c"] = None
        rows.append(row)
    return rows


def build_validation_record(
    result: dict[str, Any],
    sessions: list[dict[str, Any]],
    *,
    model_version: str,
) -> dict[str, Any]:
    """Build one immutable validation record from a completed house ventilation.

    Only room sessions whose frozen start forecast has the same time basis as
    the measured result participate in forecast-error metrics.  Non-comparable
    sessions remain represented in the record so rejected samples stay visible.
    """
    comparable = [
        dict(item) for item in sessions
        if isinstance(item, dict) and bool(item.get("prediction_comparable"))
    ]

    predicted_removed = [
        _number(item.get("predicted_removed_ml")) for item in comparable
    ]
    actual_removed = [_number(item.get("validation_removed_ml")) if item.get("validation_removed_ml") is not None else _number(item.get("removed_ml")) for item in comparable]
    moisture_pairs = [
        (predicted, actual)
        for predicted, actual in zip(predicted_removed, actual_removed)
        if predicted is not None and actual is not None
    ]

    predicted_total = sum(pair[0] for pair in moisture_pairs) if moisture_pairs else None
    actual_total = sum(pair[1] for pair in moisture_pairs) if moisture_pairs else None
    moisture_error = (
        actual_total - predicted_total
        if predicted_total is not None and actual_total is not None
        else None
    )
    moisture_abs_error = abs(moisture_error) if moisture_error is not None else None
    moisture_rel_error = None
    if moisture_abs_error is not None and predicted_total is not None and actual_total is not None:
        moisture_rel_error = moisture_abs_error / max(abs(predicted_total), abs(actual_total), 1.0) * 100.0

    temp_errors: list[float] = []
    cost_errors: list[float] = []
    duration_errors: list[float] = []
    confidences: list[float] = []
    timeline_start_errors: list[float] = []
    timeline_latest_errors: list[float] = []
    timeline_improved_flags: list[bool] = []
    room_rows: list[dict[str, Any]] = []

    for item in sessions:
        if not isinstance(item, dict):
            continue
        is_comparable = bool(item.get("prediction_comparable"))
        predicted_moisture = _number(item.get("predicted_removed_ml"))
        actual_moisture = _number(item.get("validation_removed_ml")) if item.get("validation_removed_ml") is not None else _number(item.get("removed_ml"))
        predicted_temp = _number(item.get("predicted_temperature_change_c"))
        actual_temp = _number(item.get("validation_temp_delta_c")) if item.get("validation_temp_delta_c") is not None else _number(item.get("temp_delta_c"))
        predicted_cost = _number(item.get("predicted_cost"))
        actual_cost = _number(item.get("cost"))
        horizon = _number(item.get("prediction_horizon_min"))
        duration = _number(item.get("validation_duration_min")) if item.get("validation_duration_min") is not None else _number(item.get("duration_min"))
        confidence = _number(item.get("prediction_confidence"))

        row: dict[str, Any] = {
            "event_id": item.get("event_id"),
            "validation_session_id": item.get("validation_session_id") or item.get("event_id"),
            "key": str(item.get("key") or "unknown"),
            "name": str(item.get("name") or item.get("key") or "unknown"),
            "comparable": is_comparable,
            "predicted_removed_ml": round(predicted_moisture, 1) if predicted_moisture is not None else None,
            "actual_removed_ml": round(actual_moisture, 1) if actual_moisture is not None else None,
            "predicted_temperature_change_c": round(predicted_temp, 2) if predicted_temp is not None else None,
            "actual_temperature_change_c": round(actual_temp, 2) if actual_temp is not None else None,
            "predicted_cost": round(predicted_cost, 4) if predicted_cost is not None else None,
            "actual_cost": round(actual_cost, 4) if actual_cost is not None else None,
            "forecast_horizon_min": round(horizon, 1) if horizon is not None else None,
            "actual_duration_min": round(duration, 1) if duration is not None else None,
            "forecast_confidence": round(confidence, 1) if confidence is not None else None,
            "moisture_source_contaminated": bool(item.get("moisture_source_contaminated")),
            "measurement_frame_learning_eligible": item.get("measurement_frame_learning_eligible"),
            "session_measurement_quality": item.get("session_measurement_quality"),
            "session_timestamp_activity_gate_passed": item.get("session_timestamp_activity_gate_passed"),
            "session_temperature_reports": item.get("session_temperature_reports"),
            "session_humidity_reports": item.get("session_humidity_reports"),
            "start_measurement_frame_quality": item.get("start_measurement_frame_quality"),
            "start_measurement_frame_skew_s": _number(item.get("start_measurement_frame_skew_s")),
            "start_measurement_frame_max_age_s": _number(item.get("start_measurement_frame_max_age_s")),
            "prediction_measurement_frame_quality": item.get("prediction_measurement_frame_quality"),
            "prediction_measurement_frame_skew_s": _number(item.get("prediction_measurement_frame_skew_s")),
            "prediction_measurement_frame_max_age_s": _number(item.get("prediction_measurement_frame_max_age_s")),
            "end_measurement_frame_quality": item.get("end_measurement_frame_quality"),
            "end_measurement_frame_skew_s": _number(item.get("end_measurement_frame_skew_s")),
            "end_measurement_frame_max_age_s": _number(item.get("end_measurement_frame_max_age_s")),
            "learning_effectiveness": deepcopy(item.get("learning_effectiveness")) if isinstance(item.get("learning_effectiveness"), dict) else None,
        }
        timeline = _timeline_rows(item, actual_moisture, actual_temp)
        row["forecast_timeline"] = timeline
        scored_timeline = [
            point for point in timeline
            if point.get("predicted_final_removed_ml") is not None
            and point.get("final_moisture_abs_error_ml") is not None
            and point.get("measurement_frame_quality") in {None, "legacy", "excellent", "acceptable"}
        ] if is_comparable else []
        if scored_timeline:
            start_point = next((point for point in scored_timeline if point.get("kind") == "start"), scored_timeline[0])
            live_points = [point for point in scored_timeline if point.get("kind") == "live"]
            latest_point = live_points[-1] if live_points else start_point
            best_point = min(scored_timeline, key=lambda point: float(point.get("final_moisture_abs_error_ml") or 0.0))
            row["timeline_start_abs_error_ml"] = start_point.get("final_moisture_abs_error_ml")
            row["timeline_latest_abs_error_ml"] = latest_point.get("final_moisture_abs_error_ml")
            row["timeline_best_abs_error_ml"] = best_point.get("final_moisture_abs_error_ml")
            row["timeline_improved"] = bool(
                _number(latest_point.get("final_moisture_abs_error_ml")) is not None
                and _number(start_point.get("final_moisture_abs_error_ml")) is not None
                and float(latest_point["final_moisture_abs_error_ml"]) < float(start_point["final_moisture_abs_error_ml"])
            )
            row["timeline_point_count"] = len(scored_timeline)
        else:
            row["timeline_start_abs_error_ml"] = None
            row["timeline_latest_abs_error_ml"] = None
            row["timeline_best_abs_error_ml"] = None
            row["timeline_improved"] = None
            row["timeline_point_count"] = 0

        if is_comparable and predicted_moisture is not None and actual_moisture is not None:
            error = actual_moisture - predicted_moisture
            row["moisture_error_ml"] = round(error, 1)
            row["moisture_abs_error_ml"] = round(abs(error), 1)
            row["direction_correct"] = _same_direction(predicted_moisture, actual_moisture)
        else:
            row["moisture_error_ml"] = None
            row["moisture_abs_error_ml"] = None
            row["direction_correct"] = None

        if is_comparable and predicted_temp is not None and actual_temp is not None:
            temp_error = actual_temp - predicted_temp
            temp_errors.append(temp_error)
            row["temperature_error_c"] = round(temp_error, 2)
        else:
            row["temperature_error_c"] = None

        if is_comparable and predicted_cost is not None and actual_cost is not None:
            cost_error = actual_cost - predicted_cost
            cost_errors.append(cost_error)
            row["cost_error"] = round(cost_error, 4)
        else:
            row["cost_error"] = None

        if is_comparable and horizon is not None and duration is not None:
            duration_error = duration - horizon
            duration_errors.append(duration_error)
            row["close_time_error_min"] = round(duration_error, 1)
        else:
            row["close_time_error_min"] = None

        if is_comparable and confidence is not None:
            confidences.append(confidence)
        start_err = _number(row.get("timeline_start_abs_error_ml"))
        latest_err = _number(row.get("timeline_latest_abs_error_ml"))
        if is_comparable and start_err is not None:
            timeline_start_errors.append(start_err)
        if is_comparable and latest_err is not None:
            timeline_latest_errors.append(latest_err)
        if is_comparable and row.get("timeline_improved") is not None:
            timeline_improved_flags.append(bool(row.get("timeline_improved")))

        room_rows.append(row)

    valid = bool(moisture_pairs)
    if valid:
        invalid_reason = None
    elif sessions:
        session_rows = [item for item in sessions if isinstance(item, dict)]
        if any(bool(item.get("prediction_time_aligned")) for item in session_rows):
            if any(bool(item.get("moisture_source_contaminated")) for item in session_rows):
                invalid_reason = "Zeitgleiche Startprognose vorhanden, aber wegen erkannter interner Feuchtequelle nicht objektiv bewertbar."
            elif any(
                item.get("session_timestamp_activity_gate_passed") is False
                for item in session_rows
                if bool(item.get("prediction_time_aligned"))
            ):
                invalid_reason = "Zeitgleiche Startprognose vorhanden, aber Temperatur und Luftfeuchtigkeit lieferten während der Lüftung nicht beide einen neueren Sensor-Zeitstempel. Die Session bleibt deshalb von Lernen und objektiver Prognosebewertung ausgeschlossen."
            else:
                invalid_reason = "Zeitgleiche Startprognose vorhanden, aber keine Session erfüllte alle objektiven Validierungskriterien."
        elif any(item.get("prediction_reference") == "session_start_curve_v2" for item in session_rows):
            invalid_reason = "Eingefrorene Startprognose vorhanden, konnte aber nicht auf dieselbe Messdauer der abgeschlossenen Lüftung ausgewertet werden."
        else:
            invalid_reason = "Keine Startprognose mit eingefrorener, verlässlicher Zeitbasis für die abgeschlossene Lüftung vorhanden."
    else:
        invalid_reason = "Keine abgeschlossenen Raum-Sessions vorhanden."

    return {
        "validation_version": 2,
        "model_version": str(model_version),
        "started_at": result.get("started_at"),
        "ended_at": result.get("ended_at"),
        "valid": valid,
        "invalid_reason": invalid_reason,
        "session_count": len([item for item in sessions if isinstance(item, dict)]),
        "comparable_session_count": len(comparable),
        "comparable_room_count": len({str(item.get("key") or "unknown") for item in comparable}),
        "predicted_removed_ml": round(predicted_total, 1) if predicted_total is not None else None,
        "actual_removed_ml": round(actual_total, 1) if actual_total is not None else None,
        "moisture_error_ml": round(moisture_error, 1) if moisture_error is not None else None,
        "moisture_abs_error_ml": round(moisture_abs_error, 1) if moisture_abs_error is not None else None,
        "moisture_relative_error_percent": round(moisture_rel_error, 1) if moisture_rel_error is not None else None,
        "direction_correct": (
            _same_direction(predicted_total, actual_total)
            if predicted_total is not None and actual_total is not None
            else None
        ),
        "temperature_mae_c": round(_mean([abs(value) for value in temp_errors]), 3) if temp_errors else None,
        "temperature_rmse_c": round(_rmse(temp_errors), 3) if temp_errors else None,
        "cost_mae": round(_mean([abs(value) for value in cost_errors]), 4) if cost_errors else None,
        "close_time_mae_min": round(_mean([abs(value) for value in duration_errors]), 2) if duration_errors else None,
        "forecast_confidence_mean": round(_mean(confidences), 1) if confidences else None,
        "timeline_start_mae_ml": round(_mean(timeline_start_errors), 1) if timeline_start_errors else None,
        "timeline_latest_mae_ml": round(_mean(timeline_latest_errors), 1) if timeline_latest_errors else None,
        "timeline_improvement_percent": (
            round(sum(timeline_improved_flags) / len(timeline_improved_flags) * 100.0, 1)
            if timeline_improved_flags else None
        ),
        "total_result_removed_ml": result.get("removed_ml"),
        "total_result_duration_min": result.get("duration_min"),
        "room_results": room_rows,
    }


def prune_validation_history(
    records: list[dict[str, Any]],
    now: datetime,
    *,
    retention_days: int = VALIDATION_RETENTION_DAYS,
    max_records: int = VALIDATION_MAX_RECORDS,
) -> list[dict[str, Any]]:
    """Keep the persisted validation dataset bounded and restart-safe."""
    cutoff = now.date() - timedelta(days=max(int(retention_days), 1) - 1)
    kept: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        raw = record.get("ended_at") or record.get("started_at")
        try:
            stamp = datetime.fromisoformat(str(raw))
        except (TypeError, ValueError):
            continue
        if stamp.date() >= cutoff:
            kept.append(record)
    return kept[-max(int(max_records), 1):]


def append_validation_record(
    records: list[dict[str, Any]],
    record: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    """Append one validation record exactly once and prune old data."""
    out = [dict(item) for item in records if isinstance(item, dict)]
    identity = (str(record.get("started_at")), str(record.get("ended_at")))
    if not any((str(item.get("started_at")), str(item.get("ended_at"))) == identity for item in out):
        out.append(dict(record))
    return prune_validation_history(out, now)


def validation_summary(records: list[dict[str, Any]], *, days: int = 30) -> dict[str, Any]:
    """Return objective aggregate quality metrics for the requested period."""
    days = max(1, min(int(days), VALIDATION_RETENTION_DAYS))
    valid_records = [item for item in records if isinstance(item, dict) and item.get("valid")]
    if valid_records:
        latest_raw = valid_records[-1].get("ended_at") or valid_records[-1].get("started_at")
        try:
            anchor = datetime.fromisoformat(str(latest_raw))
        except (TypeError, ValueError):
            anchor = datetime.now()
    else:
        anchor = datetime.now()
    cutoff = anchor.date() - timedelta(days=days - 1)

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

    valid = [item for item in scoped if item.get("valid")]
    moisture_abs = [float(item["moisture_abs_error_ml"]) for item in valid if _number(item.get("moisture_abs_error_ml")) is not None]
    moisture_signed = [float(item["moisture_error_ml"]) for item in valid if _number(item.get("moisture_error_ml")) is not None]
    temp_mae = [float(item["temperature_mae_c"]) for item in valid if _number(item.get("temperature_mae_c")) is not None]
    close_mae = [float(item["close_time_mae_min"]) for item in valid if _number(item.get("close_time_mae_min")) is not None]
    cost_mae = [float(item["cost_mae"]) for item in valid if _number(item.get("cost_mae")) is not None]
    directions = [bool(item.get("direction_correct")) for item in valid if item.get("direction_correct") is not None]
    timeline_start_mae = [float(item["timeline_start_mae_ml"]) for item in valid if _number(item.get("timeline_start_mae_ml")) is not None]
    timeline_latest_mae = [float(item["timeline_latest_mae_ml"]) for item in valid if _number(item.get("timeline_latest_mae_ml")) is not None]
    timeline_improvement = [float(item["timeline_improvement_percent"]) for item in valid if _number(item.get("timeline_improvement_percent")) is not None]

    per_room: dict[str, dict[str, Any]] = {}
    for item in valid:
        for room in item.get("room_results") or []:
            if not isinstance(room, dict) or not room.get("comparable"):
                continue
            key = str(room.get("key") or "unknown")
            bucket = per_room.setdefault(key, {
                "key": key,
                "name": str(room.get("name") or key),
                "samples": 0,
                "moisture_abs_errors": [],
                "temperature_abs_errors": [],
                "close_abs_errors": [],
                "directions": [],
            })
            moisture_err = _number(room.get("moisture_abs_error_ml"))
            temp_err = _number(room.get("temperature_error_c"))
            close_err = _number(room.get("close_time_error_min"))
            if moisture_err is not None:
                bucket["moisture_abs_errors"].append(abs(moisture_err))
                bucket["samples"] += 1
            if temp_err is not None:
                bucket["temperature_abs_errors"].append(abs(temp_err))
            if close_err is not None:
                bucket["close_abs_errors"].append(abs(close_err))
            if room.get("direction_correct") is not None:
                bucket["directions"].append(bool(room.get("direction_correct")))

    room_summary = []
    for bucket in per_room.values():
        directions_room = bucket.pop("directions")
        moisture_room = bucket.pop("moisture_abs_errors")
        temperature_room = bucket.pop("temperature_abs_errors")
        close_room = bucket.pop("close_abs_errors")
        bucket["moisture_mae_ml"] = round(_mean(moisture_room), 1) if moisture_room else None
        bucket["temperature_mae_c"] = round(_mean(temperature_room), 3) if temperature_room else None
        bucket["close_time_mae_min"] = round(_mean(close_room), 2) if close_room else None
        bucket["direction_accuracy_percent"] = round(sum(directions_room) / len(directions_room) * 100.0, 1) if directions_room else None
        room_summary.append(bucket)
    room_summary.sort(key=lambda item: (-int(item.get("samples", 0)), str(item.get("name", ""))))

    return {
        "validation_engine": "v2",
        "period_days": days,
        "record_count": len(scoped),
        "valid_record_count": len(valid),
        "invalid_record_count": len(scoped) - len(valid),
        "moisture_mae_ml": round(_mean(moisture_abs), 1) if moisture_abs else None,
        "moisture_rmse_ml": round(_rmse(moisture_signed), 1) if moisture_signed else None,
        "moisture_bias_ml": round(_mean(moisture_signed), 1) if moisture_signed else None,
        "temperature_mae_c": round(_mean(temp_mae), 3) if temp_mae else None,
        "close_time_mae_min": round(_mean(close_mae), 2) if close_mae else None,
        "cost_mae": round(_mean(cost_mae), 4) if cost_mae else None,
        "direction_accuracy_percent": round(sum(directions) / len(directions) * 100.0, 1) if directions else None,
        "timeline_start_mae_ml": round(_mean(timeline_start_mae), 1) if timeline_start_mae else None,
        "timeline_latest_mae_ml": round(_mean(timeline_latest_mae), 1) if timeline_latest_mae else None,
        "timeline_improvement_percent": round(_mean(timeline_improvement), 1) if timeline_improvement else None,
        "latest": scoped[-1] if scoped else None,
        "rooms": room_summary,
    }
