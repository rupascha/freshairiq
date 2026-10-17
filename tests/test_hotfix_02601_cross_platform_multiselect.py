from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()

def test_settings_multiselect_uses_explicit_checkboxes_not_native_multiple_select():
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert 'Array.from(el.selectedOptions || []).map(x => x.value)' not in CARD

# test_resident_multiselect_is_explicit_and_stateful: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_resident_room_selection_is_multi_select_and_reopens_with_saved_rooms

# test_notification_test_button_remains_available: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_notification_targets_and_test_send_cover_services_and_notify_entities
