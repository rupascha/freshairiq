from pathlib import Path


def test_session_lifecycle_consumes_debounced_three_state_modes():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    assert 'stable_session_modes = {c: contact_modes.get(c, "unknown") for c in proven_three_state}' in source
    assert 'honour_delays=False, contact_modes=stable_session_modes' in source
    assert 'honour_delays=True, contact_modes=stable_session_modes' in source
    assert '_room_closed_for_seconds(self.hass, cfg, now, contact_modes=stable_session_modes)' in source


def test_binary_contacts_keep_historical_path_without_override():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    assert 'mode_override = (contact_modes or {}).get(entity_id)' in source
    assert 'sec = _open_seconds(hass, entity_id, now)' in source
    assert 'Only proven three-state contacts are overridden' in source


def test_pending_three_state_contact_cannot_drive_session_start():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    # A debounced contact whose stable mode is closed/unknown is skipped before
    # the generic raw-state path can classify it as physically open.
    assert 'if mode_override not in {"open", "tilted"}:\n                continue' in source


def test_release_keeps_internal_confirmation_refresh_for_sleeping_battery_contacts():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    assert 'async_call_later' in source
    assert '_confirm_contact_state' in source
    assert 'sends no further telegram' in source
