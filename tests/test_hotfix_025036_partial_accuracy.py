"""Regression contracts for v0.25.0.75 partial forecast validation hotfix."""
from datetime import datetime
from pathlib import Path
from custom_components.freshairiq.ventilation_result import finalise_ventilation_group

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _session(key: str, predicted: float, actual: float, comparable: bool) -> dict:
    return {
        "key": key, "name": key.title(), "volume_m3": 30.0,
        "started_at": "2026-09-19T08:00:00+02:00", "duration_min": 20.0,
        "removed_ml": actual, "moisture_measurement_valid": True,
        "predicted_removed_ml": predicted, "prediction_time_aligned": True,
        "prediction_comparable": comparable,
        "learning_valid": comparable,
    }


def test_partial_house_validation_keeps_strict_subset_and_excludes_async_room():
    group = {"started_at": "2026-09-19T08:00:00+02:00", "sessions": [
        _session("bad", 80, 100, True),
        _session("schlafzimmer", 20, 70, False),
    ]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-09-19T08:20:00+02:00"))
    assert result is not None
    assert result["prediction_alignment_quality"] == "partial_validated"
    assert result["prediction_accuracy_percent"] == 80
    assert result["predicted_removed_ml"] == 80
    assert result["prediction_actual_removed_ml"] == 100
    assert result["prediction_error_ml"] == 20
    assert result["prediction_comparable_rooms"] == 1
    assert result["prediction_time_aligned_rooms"] == 2
    assert result["prediction_excluded_sessions"] == 1
    assert result["prediction_excluded_rooms"] == 1
    statuses = {r["key"]: r["prediction_validation_status"] for r in result["room_results"]}
    assert statuses == {"bad": "valid", "schlafzimmer": "not_comparable"}


def test_no_strict_room_still_has_no_accuracy():
    group = {"started_at": "2026-09-19T08:00:00+02:00", "sessions": [_session("bad", 20, 70, False)]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-09-19T08:20:00+02:00"))
    assert result is not None
    assert result["prediction_alignment_quality"] == "informational"
    assert result["prediction_accuracy_percent"] is None
    assert "keine Genauigkeitswertung" in result["prediction_status_text"]



def test_room_with_mixed_aligned_sessions_is_restricted():
    group = {"started_at": "2026-09-19T08:00:00+02:00", "sessions": [
        _session("bad", 80, 100, True),
        _session("bad", 20, 70, False),
    ]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-09-19T08:20:00+02:00"))
    assert result is not None
    statuses = {r["key"]: r["prediction_validation_status"] for r in result["room_results"]}
    assert statuses["bad"] == "restricted"

def test_release_version_025036():
    assert 'VERSION = "0.25.0.75"' in (COMP / "const.py").read_text()
    assert '"version": "0.25.0.75"' in (COMP / "manifest.json").read_text()
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.75";' in (COMP / "frontend" / name).read_text()
