from datetime import datetime, timedelta

from custom_components.freshairiq.forecast_validation import (
    append_validation_record,
    build_validation_record,
    validation_summary,
)


def _session(key, predicted, actual, *, temp_pred=-0.4, temp_actual=-0.3, horizon=15, duration=16, comparable=True):
    return {
        "key": key,
        "name": key,
        "prediction_comparable": comparable,
        "predicted_removed_ml": predicted,
        "removed_ml": actual,
        "predicted_temperature_change_c": temp_pred,
        "temp_delta_c": temp_actual,
        "predicted_cost": 0.04,
        "cost": 0.05,
        "prediction_horizon_min": horizon,
        "duration_min": duration,
        "prediction_confidence": 82,
    }


def test_validation_compares_only_equal_time_basis():
    result = {"started_at": "2026-09-11T20:00:00+02:00", "ended_at": "2026-09-11T20:16:00+02:00", "removed_ml": 210, "duration_min": 16}
    record = build_validation_record(
        result,
        [_session("a", 100, 110), _session("b", 90, 100), _session("c", 500, 5, comparable=False)],
        model_version="0.20.3.1",
    )
    assert record["valid"] is True
    assert record["predicted_removed_ml"] == 190.0
    assert record["actual_removed_ml"] == 210.0
    assert record["moisture_abs_error_ml"] == 20.0
    assert record["direction_correct"] is True
    assert record["comparable_session_count"] == 2


def test_validation_invalid_when_no_comparable_start_snapshot():
    result = {"started_at": "2026-09-11T20:00:00+02:00", "ended_at": "2026-09-11T23:00:00+02:00", "removed_ml": 300, "duration_min": 180}
    record = build_validation_record(result, [_session("a", 100, 300, comparable=False)], model_version="0.20.3.1")
    assert record["valid"] is False
    assert record["predicted_removed_ml"] is None
    assert record["moisture_abs_error_ml"] is None
    assert "Zeitbasis" in record["invalid_reason"]


def test_validation_summary_reports_objective_metrics_and_rooms():
    now = datetime.fromisoformat("2026-09-11T22:00:00+02:00")
    result = {"started_at": "2026-09-11T21:40:00+02:00", "ended_at": now.isoformat(), "removed_ml": 210, "duration_min": 20}
    record = build_validation_record(result, [_session("wohn", 100, 110), _session("bad", 90, 100)], model_version="0.20.3.1")
    records = append_validation_record([], record, now)
    summary = validation_summary(records, days=30)
    assert summary["valid_record_count"] == 1
    assert summary["moisture_mae_ml"] == 20.0
    assert summary["direction_accuracy_percent"] == 100.0
    assert summary["temperature_mae_c"] == 0.1
    assert summary["close_time_mae_min"] == 1.0
    assert {room["key"] for room in summary["rooms"]} == {"wohn", "bad"}


def test_validation_history_is_deduplicated():
    now = datetime.fromisoformat("2026-09-11T22:00:00+02:00")
    result = {"started_at": "2026-09-11T21:45:00+02:00", "ended_at": now.isoformat(), "removed_ml": 100, "duration_min": 15}
    record = build_validation_record(result, [_session("a", 90, 100)], model_version="0.20.3.1")
    records = append_validation_record([], record, now)
    records = append_validation_record(records, record, now + timedelta(seconds=1))
    assert len(records) == 1


def test_validation_v2_scores_forecast_timeline_convergence():
    result = {"started_at": "2026-09-11T20:00:00+02:00", "ended_at": "2026-09-11T20:15:00+02:00", "removed_ml": 120, "duration_min": 15}
    session = _session("wohn", 100, 120, horizon=15, duration=15)
    session["forecast_timeline"] = [
        {
            "kind": "start", "checkpoint_min": 0, "elapsed_min": 0.3,
            "predicted_final_removed_ml": 100, "predicted_final_temperature_change_c": -0.4,
            "actual_removed_ml": 0, "actual_temperature_change_c": 0,
        },
        {
            "kind": "live", "checkpoint_min": 5, "elapsed_min": 5.1,
            "predicted_final_removed_ml": 112, "predicted_final_temperature_change_c": -0.32,
            "actual_removed_ml": 44, "actual_temperature_change_c": -0.1,
        },
        {
            "kind": "live", "checkpoint_min": 10, "elapsed_min": 10.0,
            "predicted_final_removed_ml": 118, "predicted_final_temperature_change_c": -0.31,
            "actual_removed_ml": 83, "actual_temperature_change_c": -0.2,
        },
        {
            "kind": "end", "checkpoint_min": 15, "elapsed_min": 15,
            "predicted_final_removed_ml": None, "actual_removed_ml": 120,
            "actual_temperature_change_c": -0.3,
        },
    ]
    record = build_validation_record(result, [session], model_version="0.20.3.1")
    room = record["room_results"][0]
    assert record["validation_version"] == 2
    assert room["timeline_start_abs_error_ml"] == 20.0
    assert room["timeline_latest_abs_error_ml"] == 2.0
    assert room["timeline_best_abs_error_ml"] == 2.0
    assert room["timeline_improved"] is True
    assert room["timeline_point_count"] == 3
    assert record["timeline_start_mae_ml"] == 20.0
    assert record["timeline_latest_mae_ml"] == 2.0
    assert record["timeline_improvement_percent"] == 100.0


def test_validation_v2_does_not_score_timeline_for_non_comparable_session():
    result = {"started_at": "2026-09-11T20:00:00+02:00", "ended_at": "2026-09-11T21:00:00+02:00", "removed_ml": 200, "duration_min": 60}
    session = _session("wohn", 100, 200, horizon=15, duration=60, comparable=False)
    session["forecast_timeline"] = [
        {"kind": "start", "checkpoint_min": 0, "predicted_final_removed_ml": 100},
        {"kind": "live", "checkpoint_min": 5, "predicted_final_removed_ml": 130},
    ]
    record = build_validation_record(result, [session], model_version="0.20.3.1")
    room = record["room_results"][0]
    assert room["forecast_timeline"]
    assert room["timeline_point_count"] == 0
    assert room["timeline_improved"] is None
    assert record["timeline_start_mae_ml"] is None
