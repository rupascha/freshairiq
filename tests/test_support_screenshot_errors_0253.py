from pathlib import Path
from custom_components.freshairiq.runtime_health import RuntimeHealthMonitor

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"freshairiq"

def test_runtime_user_summary_is_bounded_and_screenshot_safe():
    m=RuntimeHealthMonitor()
    for i in range(8):
        try:
            raise RuntimeError(f"secret entity sensor.room_{i}")
        except RuntimeError as err:
            m.record_exception("coordinator", f"operation_{i}", err, f"2026-10-04T12:0{i}:00+02:00")
    summary=m.user_summary
    assert summary["active_problem"] is True
    assert summary["active_count"] == 8
    assert len(summary["incidents"]) == 5
    rendered=str(summary)
    assert "sensor.room" not in rendered and "secret" not in rendered
    assert all(row["code"] == "FAIQ-RUNTIME-UNKNOWN-001" for row in summary["incidents"])

def test_user_visible_failure_surfaces_have_stable_codes():
    card=(COMP/"frontend"/"freshairiq-card.js").read_text()
    panel=(COMP/"frontend"/"freshairiq-panel.js").read_text()
    loader=(COMP/"frontend"/"freshairiq-loader.js").read_text()
    sensor=(COMP/"sensor.py").read_text()
    pdf=(COMP/"ventilation_log_api.py").read_text()
    diagnostics=(COMP/"diagnostics.py").read_text()
    settings=(COMP/"feedback_api.py").read_text()
    assert '"support_status": self.coordinator.runtime_health.user_summary' in sensor
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert "FAIQ-UI-PANEL-001" in panel and "FAIQ-UI-LOADER-001" in loader
    assert "FAIQ-PDF-BUILD-001" in pdf
    assert "FAIQ-DIAG-RUNTIME-001" in diagnostics
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).

def test_runtime_user_summary_omits_resolved_incidents():
    m=RuntimeHealthMonitor()
    try:
        raise RuntimeError("x")
    except RuntimeError as err:
        m.record_exception("coordinator", "update", err, "2026-10-04T12:00:00+02:00")
    row=next(iter(m._incidents.values()))
    row["status"]="resolved"
    summary=m.user_summary
    assert summary["active_problem"] is False
    assert summary["active_count"] == 0
    assert summary["incidents"] == []
