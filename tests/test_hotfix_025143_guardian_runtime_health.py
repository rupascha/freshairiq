import importlib.util
from pathlib import Path
P=Path(__file__).parents[1]/"custom_components/freshairiq/runtime_health.py"
spec=importlib.util.spec_from_file_location("rh_guardian",P); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_guardian_finding_is_privacy_filtered_and_aggregated():
    monitor=m.RuntimeHealthMonitor()
    monitor.record_guardian_finding({"code":"FAIQ-GUARDIAN-X","component":"forecast","invariant":"x","severity":"high","evidence":{"count":2,"secret":"drop"},"auto_healable":True}, "2026-09-29T20:00:00")
    snap=monitor.snapshot
    assert snap["incident_count"]==1
    row=snap["incidents"][0]
    assert row["classification"]["category"]=="guardian_invariant"
    assert row["evidence"]["count"]==2 and "secret" not in row["evidence"]
    assert row["evidence"]["auto_healable"] is True

def test_guardian_finding_defaults_and_nonmapping_evidence():
    monitor=m.RuntimeHealthMonitor(); monitor.record_guardian_finding({"evidence":"nope"})
    row=monitor.snapshot["incidents"][0]
    assert row["classification"]["support_code"]=="FAIQ-GUARDIAN-UNKNOWN"
