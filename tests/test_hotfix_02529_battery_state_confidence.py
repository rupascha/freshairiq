from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")

def test_stale_unknown_keeps_last_confirmed_physical_truth():
    assert 'contact_modes[entity_id] = str(stable_contacts[entity_id])' in COORD
    branch = COORD.split('if current_mode == "unknown" and stable_contacts.get(entity_id)', 1)[1].split('continue', 1)[0]
    assert 'contact_modes[entity_id] = "unknown"' not in branch
    assert 'contact_modes[entity_id] = "closed"' not in branch

def test_30_seconds_is_confidence_boundary_not_state_expiry():
    assert 'unknown_age > THREE_STATE_UNKNOWN_HOLD_SECONDS' in COORD
    assert 'three_state_stale_contacts.append(entity_id)' in COORD
    assert 'mem["session_learning_quarantined"] = True' in COORD
    assert 'mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006"' in COORD

def test_proven_three_state_stable_truth_bypasses_legacy_restore_guard():
    assert 'lifecycle_contacts_known = all(' in COORD
    assert 'contact_id in proven_three_state and stable_session_modes.get(contact_id) in {"closed", "open", "tilted"}' in COORD
    assert 'if mem.get("session_active") and not lifecycle_contacts_known:' in COORD
