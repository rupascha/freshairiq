from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
CONST = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")


def test_unknown_confidence_is_bounded_to_30_seconds():
    assert "THREE_STATE_UNKNOWN_HOLD_SECONDS = 30.0" in CONST
    assert "unknown_age > THREE_STATE_UNKNOWN_HOLD_SECONDS" in COORD
    assert 'contact_modes[entity_id] = str(stable_contacts[entity_id])' in COORD
    assert 'three_state_stale_contacts.append(entity_id)' in COORD


def test_stale_unknown_quarantines_specialist_learning_without_inventing_closed():
    assert 'mem["session_learning_quarantined"] = True' in COORD
    assert 'mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006"' in COORD
    assert 'not mem.get("session_learning_quarantined")' in COORD
    stale_block = COORD.split('if unknown_age is None or unknown_age > THREE_STATE_UNKNOWN_HOLD_SECONDS:', 1)[1].split('continue', 1)[0]
    assert 'contact_modes[entity_id] = "closed"' not in stale_block


def test_stale_unknown_does_not_falsely_mark_specialist_mode_mixed():
    assert 'if started_specialist and not three_state_stale_contacts and (' in COORD


def test_physical_start_uses_stable_three_state_mode_and_timestamp():
    assert "def _room_physical_opened_at(" in COORD
    assert "contact_modes: dict[str, str] | None = None" in COORD
    assert "contact_since: dict[str, datetime] | None = None" in COORD
    assert "contact_modes=stable_session_modes, contact_since=stable_since" in COORD


def test_stale_state_is_visible_in_diagnostics():
    assert '"three_state_stale_contacts": list(mem.get("three_state_stale_contacts") or [])' in COORD
    assert 'FAIQ-OPENING-3STATE-006' in COORD
