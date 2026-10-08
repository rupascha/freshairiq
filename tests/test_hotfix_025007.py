"""Regression contracts for 0.25.0.7 validation-session hotfix."""
from custom_components.freshairiq.forecast_validation import build_validation_record


def _result():
    return {"started_at": "2026-09-16T06:00:00+02:00", "ended_at": "2026-09-16T06:10:00+02:00", "removed_ml": 10, "duration_min": 10}


def test_invalid_reason_distinguishes_measurement_frame_rejection():
    rec = build_validation_record(_result(), [{
        "event_id": "room:event", "validation_session_id": "room:start", "key": "room", "name": "Room",
        "prediction_time_aligned": True, "prediction_comparable": False,
        "prediction_measurement_frame_quality": "held", "end_measurement_frame_quality": "excellent",
        "session_timestamp_activity_gate_passed": False,
        "predicted_removed_ml": 12, "removed_ml": 10,
    }], model_version="0.25.0.7")
    assert rec["valid"] is False
    assert "Sensor-Zeitstempel" in rec["invalid_reason"]
    assert rec["room_results"][0]["validation_session_id"] == "room:start"


def test_invalid_reason_reports_missing_frozen_start_forecast():
    rec = build_validation_record(_result(), [{
        "event_id": "room:event", "key": "room", "name": "Room",
        "prediction_time_aligned": False, "prediction_comparable": False,
    }], model_version="0.25.0.7")
    assert "Keine Startprognose" in rec["invalid_reason"]
