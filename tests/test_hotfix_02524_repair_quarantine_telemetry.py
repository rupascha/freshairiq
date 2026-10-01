from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")

def test_repair_path_inherits_stale_three_state_quarantine():
    assert 'mem["session_learning_quarantined"] = bool(three_state_stale_contacts)' in COORD
    assert 'mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006" if three_state_stale_contacts else None' in COORD

def test_completed_session_exports_opening_learning_quarantine_evidence():
    for field in ("opening_learning_mode", "opening_learning_quarantined", "opening_learning_quarantine_code"):
        assert f'"{field}"' in COORD
