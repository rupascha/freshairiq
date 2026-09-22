from pathlib import Path

from custom_components.freshairiq.forecast_validation import build_validation_record

ROOT = Path(__file__).resolve().parents[1]


def test_validation_prefers_time_aligned_objective_outcome_fields():
    session = {
        "key": "room-a",
        "name": "Room A",
        "prediction_comparable": True,
        "predicted_removed_ml": 20.0,
        "removed_ml": 99.0,
        "validation_removed_ml": 22.0,
        "predicted_temperature_change_c": -0.5,
        "temp_delta_c": -2.0,
        "validation_temp_delta_c": -0.6,
        "predicted_cost": 0.0,
        "cost": 0.0,
        "prediction_horizon_min": 10.0,
        "duration_min": 30.0,
        "validation_duration_min": 10.0,
        "prediction_confidence": 80,
        "prediction_measurement_frame_quality": "excellent",
        "end_measurement_frame_quality": "acceptable",
    }
    record = build_validation_record({"started_at": "a", "ended_at": "b"}, [session], model_version="0.25.0.47")
    assert record["valid"] is True
    assert record["actual_removed_ml"] == 22.0
    assert record["moisture_abs_error_ml"] == 2.0
    assert record["temperature_mae_c"] == 0.1
    assert record["close_time_mae_min"] == 0.0


def test_coordinator_has_independent_validation_clock_and_strict_timestamp_gate():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'mem["session_validation_started"] = now.isoformat()' in source
    assert 'measurement_frame.get("validation_eligible")' in source
    assert 'session_activity_eligible = bool(session_quality.get("timestamp_gate_passed"))' in source
    assert '(now - last_validation_at).total_seconds() <= 120.0' not in source
    assert 'evaluate_start_forecast_at_duration(start_context, validation_elapsed)' in source
    assert '"validation_removed_ml"' in source


def test_release_version_025027_is_consistent():
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    manifest = (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    card = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    package = (ROOT / "package.json").read_text(encoding="utf-8")
    assert 'VERSION = "0.25.0.47"' in const
    assert '"version": "0.25.0.47"' in manifest
    assert 'const FAIQ_VERSION = "0.25.0.47";' in card
    assert '"version": "0.25.0.47"' in package
