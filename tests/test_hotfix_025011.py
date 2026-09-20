"""Regression contracts for 0.25.0.39 pure-logic coverage hotfix."""

from pathlib import Path

from custom_components.freshairiq.forecast_validation import build_validation_record

ROOT = Path(__file__).resolve().parents[1]


def _non_comparable_session(**overrides):
    session = {
        "key": "room",
        "name": "Room",
        "prediction_comparable": False,
        "prediction_time_aligned": True,
        "prediction_reference": "session_start_curve_v2",
        "predicted_removed_ml": 25,
        "removed_ml": 30,
        "prediction_measurement_frame_quality": "excellent",
        "end_measurement_frame_quality": "acceptable",
        "moisture_source_contaminated": False,
    }
    session.update(overrides)
    return session


def test_invalid_reason_for_time_aligned_session_with_internal_moisture_source():
    record = build_validation_record(
        {},
        [_non_comparable_session(moisture_source_contaminated=True)],
        model_version="coverage",
    )
    assert record["valid"] is False
    assert record["invalid_reason"] == (
        "Zeitgleiche Startprognose vorhanden, aber wegen erkannter interner "
        "Feuchtequelle nicht objektiv bewertbar."
    )


def test_invalid_reason_for_time_aligned_session_failing_other_objective_criteria():
    record = build_validation_record(
        {},
        [_non_comparable_session()],
        model_version="coverage",
    )
    assert record["valid"] is False
    assert record["invalid_reason"] == (
        "Zeitgleiche Startprognose vorhanden, aber keine Session erfüllte alle "
        "objektiven Validierungskriterien."
    )


def test_invalid_reason_when_frozen_start_curve_cannot_be_time_aligned():
    record = build_validation_record(
        {},
        [_non_comparable_session(prediction_time_aligned=False)],
        model_version="coverage",
    )
    assert record["valid"] is False
    assert record["invalid_reason"] == (
        "Eingefrorene Startprognose vorhanden, konnte aber nicht auf dieselbe "
        "Messdauer der abgeschlossenen Lüftung ausgewertet werden."
    )


def test_pure_logic_ci_gate_is_hard_100_percent():
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    assert "--cov-fail-under=100" in workflow
    assert "--cov-fail-under=95" not in workflow
