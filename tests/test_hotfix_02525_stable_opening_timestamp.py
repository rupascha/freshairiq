from datetime import datetime, timedelta, timezone
from pathlib import Path

from custom_components.freshairiq.opening_state import stable_state_seconds


def test_stable_state_age_uses_stable_timestamp_not_new_raw_candidate_time():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    stable_since = now - timedelta(minutes=10)
    assert stable_state_seconds(now, stable_since) == 600.0


def test_stable_state_age_is_non_negative_and_defensive():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    assert stable_state_seconds(now, now + timedelta(seconds=2)) == 0.0
    assert stable_state_seconds(now, None) == 0.0
    assert stable_state_seconds(now, "invalid") == 0.0


def test_coordinator_pairs_debounced_mode_with_persisted_timestamp():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    assert 'mem.get("stable_opening_since")' in source
    assert 'mem["stable_opening_since"]' in source
    assert 'contact_since=stable_since' in source
    assert 'stable_since = (contact_since or {}).get(entity_id)' in source
    assert 'sec = stable_state_seconds(now, stable_since)' in source


def test_stable_timestamp_is_pruned_to_current_contacts_and_binary_path_unchanged():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    assert 'if str(k) in configured_contacts' in source
    assert 'sec = _open_seconds(hass, entity_id, now)' in source
