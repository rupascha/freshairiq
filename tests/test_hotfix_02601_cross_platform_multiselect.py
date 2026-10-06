from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()

def test_settings_multiselect_uses_explicit_checkboxes_not_native_multiple_select():
    assert 'data-setting-multi-value=' in CARD
    assert 'data-setting-multi-group=' in CARD
    assert 'Array.from(el.selectedOptions || []).map(x => x.value)' not in CARD

def test_resident_multiselect_is_explicit_and_stateful():
    assert 'data-resident-value=' in CARD
    assert 'profile[field] = selected' in CARD

def test_notification_test_button_remains_available():
    assert 'id="settings-test-notification"' in CARD
    assert 'Legacy-notify-Dienste und moderne notify-Entitäten über notify.send_message.' in CARD
