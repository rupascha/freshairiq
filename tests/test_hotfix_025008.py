"""Regression contracts for 0.25.0.8 validation-accuracy hotfix."""
from datetime import datetime
from pathlib import Path

from custom_components.freshairiq.ventilation_result import finalise_ventilation_group

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _session(*, predicted: float, actual: float, comparable: bool) -> dict:
    return {
        "key": "wohnkuche",
        "name": "Wohnküche",
        "volume_m3": 85.8,
        "started_at": "2026-09-16T07:00:00+02:00",
        "ended_at": "2026-09-16T07:40:00+02:00",
        "removed_ml": actual,
        "duration_min": 40.0,
        "predicted_removed_ml": predicted,
        "prediction_time_aligned": True,
        "prediction_comparable": comparable,
        "outcome_feedback_action": "skipped" if not comparable else "applied",
    }


def test_informational_same_duration_replay_does_not_publish_accuracy():
    group = {"started_at": "2026-09-16T07:00:00+02:00", "sessions": [_session(predicted=10, actual=186, comparable=False)]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-09-16T07:40:00+02:00"))
    assert result is not None
    assert result["removed_ml"] == 186
    assert result["aligned_predicted_removed_ml"] == 10
    assert result["aligned_prediction_actual_removed_ml"] == 186
    assert result["aligned_prediction_accuracy_percent"] is None
    assert result["prediction_accuracy_percent"] is None
    assert result["prediction_alignment_quality"] == "informational"
    assert "keine Genauigkeitswertung" in result["prediction_status_text"]


def test_mixed_house_result_scores_only_strict_comparable_subset():
    valid = _session(predicted=80, actual=100, comparable=True)
    valid["key"] = "bad"
    valid["name"] = "Bad"
    invalid = _session(predicted=20, actual=86, comparable=False)
    group = {"started_at": "2026-09-16T07:00:00+02:00", "sessions": [valid, invalid]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-09-16T07:40:00+02:00"))
    assert result is not None
    assert result["prediction_accuracy_percent"] == 80  # strict subset retained for diagnostics
    assert result["aligned_prediction_accuracy_percent"] is None  # full-house aligned score remains suppressed
    assert result["prediction_alignment_quality"] == "partial_validated"
    assert result["prediction_comparable_rooms"] == 1
    assert result["prediction_time_aligned_rooms"] == 2
    assert result["prediction_excluded_rooms"] == 1
    assert "1 von 2" in result["prediction_status_text"]


def test_valid_same_duration_comparison_still_scores_normally():
    group = {"started_at": "2026-09-16T07:00:00+02:00", "sessions": [_session(predicted=80, actual=100, comparable=True)]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-09-16T07:40:00+02:00"))
    assert result is not None
    assert result["prediction_accuracy_percent"] == 80
    assert result["aligned_prediction_accuracy_percent"] == 80
    assert result["prediction_alignment_quality"] == "validated"


def test_frontend_uses_only_strict_prediction_metrics_for_accuracy_card():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    block = js[js.index("_ventilationResultCard(last"):js.index("_hero(st, rooms", js.index("_ventilationResultCard(last"))]
    assert "last.aligned_prediction_accuracy_percent" not in block
    assert "last.aligned_predicted_removed_ml" not in block
    assert "last.prediction_accuracy_percent" in block
    assert "scoreValidated" in block
    assert "partial_validated" in block
    assert "wegen nicht ausreichend synchroner Messdaten ausgeschlossen" in block


def test_forecast_accuracy_remains_strict_after_followup_learning_hotfix():
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert 'snapshot_frame_valid = bool(session_activity_eligible)' in source
    assert 'session_activity_eligible\n            and validation_end_ah is not None' in source


def test_release_version_is_025008():
    assert 'VERSION = "0.25.0.40"' in (COMP / "const.py").read_text(encoding="utf-8")
    import json
    assert json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"] == "0.25.0.40"
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.40";' in (COMP / "frontend" / name).read_text(encoding="utf-8")
