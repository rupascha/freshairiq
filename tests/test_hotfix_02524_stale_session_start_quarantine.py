from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def _session_start_block():
    return COORD.split('if session_should and not mem["session_active"] and measurements_valid:', 1)[1].split('# Hotfix 0.20.2.6:', 1)[0]


def test_session_start_inherits_current_unknown_evidence():
    block = _session_start_block()
    assert 'mem["session_three_state_unknown_observed"] = bool(three_state_unknown_contacts)' in block


def test_stale_session_start_is_quarantined_immediately():
    block = _session_start_block()
    assert 'mem["session_learning_quarantined"] = bool(three_state_stale_contacts)' in block
    assert 'mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006" if three_state_stale_contacts else None' in block


def test_stale_start_does_not_replace_last_confirmed_physical_state():
    branch = COORD.split('if current_mode == "unknown" and stable_contacts.get(entity_id)', 1)[1].split('continue', 1)[0]
    assert 'contact_modes[entity_id] = str(stable_contacts[entity_id])' in branch
    assert 'contact_modes[entity_id] = "closed"' not in branch
