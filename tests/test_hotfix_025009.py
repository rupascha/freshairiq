"""Regression contracts for 0.25.0.9 battery-sensor learning hotfix."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_strict_accuracy_and_adaptive_learning_are_separate_gates():
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    start = source.index("prediction_learning_eligible = bool(")
    end = source.index('mem["session_prediction_snapshot_valid"]', start)
    block = source[start:end]
    assert "prediction_comparable" not in block
    assert "original_snapshot_valid" in block
    assert "prediction_time_aligned" in block
    assert "start_learning_valid" in block
    assert "end_learning_valid" in block


def test_timestamp_activity_gate_supersedes_legacy_held_frame_shortcut():
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert 'snapshot_frame_valid = bool(session_activity_eligible)' in source
    assert 'start_learning_valid = session_activity_eligible' in source
    assert 'end_learning_valid = session_activity_eligible' in source
    assert 'mem["session_prediction_learning_weight"] = activity_weight if session_activity_eligible else 0.0' in source


def test_uncertain_and_stale_are_not_promoted_by_room_only_fallback():
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    start = source.index("start_learning_valid =")
    end = source.index('mem["session_prediction_snapshot_valid"]', start)
    block = source[start:end]
    assert "end_room_learning_valid" not in block
    assert "ROOM_HELD_MAX_AGE_S" not in source
    assert "FRAME_HELD_SKEW_S" not in source


def test_frontend_does_not_claim_non_scored_comparison_is_learning_blocked():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "dieser Vergleich ist für Prognoselernen gesperrt" not in js
    assert "Keine Genauigkeitswertung · Messdaten nicht streng genug synchronisiert" in js
    assert "für Genauigkeitswertung verwertbar" in js


def test_release_version_is_025009():
    import json
    assert 'VERSION = "0.25.0.75"' in (COMP / "const.py").read_text(encoding="utf-8")
    assert json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"] == "0.25.0.75"
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.75";' in (COMP / "frontend" / name).read_text(encoding="utf-8")
