from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def test_unknown_three_state_holds_last_confirmed_physical_truth():
    assert 'if current_mode == "unknown" and stable_contacts.get(entity_id) in {"closed", "open", "tilted"}' in COORD
    assert 'contact_modes[entity_id] = str(stable_contacts[entity_id])' in COORD


def test_unknown_hold_does_not_mutate_stable_timestamp_or_count_as_transition():
    block = COORD.split('if current_mode == "unknown" and stable_contacts.get(entity_id)', 1)[1].split('continue', 1)[0]
    assert 'stable_since[' not in block
    assert 'transition_suppressed = True' not in block


def test_unknown_gap_is_diagnostic_and_session_auditable():
    assert 'mem["three_state_unknown_contacts"] = sorted(three_state_unknown_contacts)' in COORD
    assert 'mem["session_three_state_unknown_observed"] = True' in COORD
    assert 'FAIQ-OPENING-3STATE-005' in COORD


def test_specialist_provenance_consumes_held_contact_modes_after_unknown_handling():
    hold = COORD.index('contact_modes[entity_id] = str(stable_contacts[entity_id])')
    provenance = COORD.index('specialist_opening_mode, specialist_opening_signature = specialist_opening_provenance(contact_modes, proven_three_state)')
    assert hold < provenance


def test_physical_consumers_receive_same_held_truth():
    assert 'stable_session_modes = {c: contact_modes.get(c, "unknown") for c in proven_three_state}' in COORD
    assert 'physical_contact_modes = {' in COORD
