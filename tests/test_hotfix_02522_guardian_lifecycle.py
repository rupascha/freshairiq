from custom_components.freshairiq.runtime_health import RuntimeHealthMonitor
from custom_components.freshairiq.diagnostic_transport import problem_fingerprint


def _finding(code="FAIQ-GUARDIAN-DECISION-001", component="recommendation", invariant="canonical_visible_recommendation_consistency"):
    return {"code": code, "component": component, "invariant": invariant, "severity": "high", "evidence": {"affected_room_count": 1}}


def test_guardian_incident_resolves_only_after_two_clean_cycles_and_keeps_history():
    monitor = RuntimeHealthMonitor()
    monitor.reconcile_guardian_findings([_finding()], "2026-10-01T06:00:00+02:00")
    first = monitor.snapshot
    assert first["active_problem"] is True and first["active_incident_count"] == 1
    assert first["incidents"][0]["status"] == "active"

    monitor.reconcile_guardian_findings([], "2026-10-01T06:01:00+02:00")
    monitoring = monitor.snapshot
    assert monitoring["active_problem"] is True
    assert monitoring["incidents"][0]["healthy_confirmations"] == 1

    monitor.reconcile_guardian_findings([], "2026-10-01T06:02:00+02:00")
    resolved = monitor.snapshot
    row = resolved["incidents"][0]
    assert resolved["active_problem"] is False
    assert resolved["active_incident_count"] == 0 and resolved["resolved_incident_count"] == 1
    assert row["status"] == "resolved" and row["occurrences"] == 1
    assert row["resolved_at"] == "2026-10-01T06:02:00+02:00"
    monitor.reconcile_guardian_findings([], "2026-10-01T06:03:00+02:00")
    still_resolved = monitor.snapshot["incidents"][0]
    assert still_resolved["status"] == "resolved"
    assert still_resolved["healthy_confirmations"] == 2
    assert still_resolved["resolved_at"] == "2026-10-01T06:02:00+02:00"


def test_guardian_recurrence_reopens_same_incident_without_losing_history():
    monitor = RuntimeHealthMonitor()
    monitor.reconcile_guardian_findings([_finding()], "2026-10-01T06:00:00+02:00")
    monitor.reconcile_guardian_findings([], "2026-10-01T06:01:00+02:00")
    monitor.reconcile_guardian_findings([], "2026-10-01T06:02:00+02:00")
    monitor.reconcile_guardian_findings([_finding()], "2026-10-01T06:03:00+02:00")
    row = monitor.snapshot["incidents"][0]
    assert row["status"] == "active" and row["healthy_confirmations"] == 0
    assert row["resolved_at"] is None and row["occurrences"] == 2


def test_sensor_002_uses_same_confirmed_recovery_lifecycle():
    monitor = RuntimeHealthMonitor()
    sensor = _finding("FAIQ-GUARDIAN-SENSOR-002", "sensor_recovery", "unavailable_sources_require_recovery_guard")
    monitor.reconcile_guardian_findings([sensor], "2026-10-01T06:00:00+02:00")
    monitor.reconcile_guardian_findings([], "2026-10-01T06:01:00+02:00")
    assert monitor.snapshot["active_problem"] is True
    monitor.reconcile_guardian_findings([], "2026-10-01T06:02:00+02:00")
    assert monitor.snapshot["active_problem"] is False


def test_resolved_guardian_history_does_not_keep_errors_mode_fingerprint_alive():
    monitor = RuntimeHealthMonitor()
    monitor.reconcile_guardian_findings([_finding()], "2026-10-01T06:00:00+02:00")
    assert problem_fingerprint({"runtime_health": monitor.snapshot}) is not None
    monitor.reconcile_guardian_findings([], "2026-10-01T06:01:00+02:00")
    monitor.reconcile_guardian_findings([], "2026-10-01T06:02:00+02:00")
    assert problem_fingerprint({"runtime_health": monitor.snapshot}) is None
