from pathlib import Path

from custom_components.freshairiq.guardian import evaluate_guardian

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_guardian_decision_incident_explains_mismatch_class_without_identity():
    result = evaluate_guardian({"rooms": {"secret-room": {
        "action": "Close", "canonical_action": "Continue ventilating",
        "temperature": 21, "humidity": 55, "absolute_humidity": 10,
    }}})
    finding = next(x for x in result["findings"] if x["code"] == "FAIQ-GUARDIAN-DECISION-001")
    assert finding["evidence"] == {
        "affected_room_count": 1,
        "keep_to_close_count": 1,
        "missing_alignment_override_count": 1,
    }
    assert "secret-room" not in str(finding)


def test_sensor_quality_diagnostics_export_reason_age_and_recovery_aggregates():
    source = (COMP / "diagnostics.py").read_text()
    for token in (
        '"issue_reason_counts"', '"issue_age_buckets"',
        '"sensor_recovery_active"', '"sensor_recovery_unavailable_sources"',
        '"lt_60s"', '"60_300s"', '"gt_300s"',
    ):
        assert token in source


def test_coordinator_records_phase_specific_runtime_metrics():
    source = (COMP / "coordinator.py").read_text()
    for metric in (
        "coordinator_phase_core_ms", "coordinator_phase_guardian_ms",
        "coordinator_phase_notifications_ms", "coordinator_phase_persistence_ms",
        "coordinator_phase_diagnostics_ms",
    ):
        assert metric in source
