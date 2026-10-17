from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_notify_entity_service_registry_contract():
 s=(ROOT/'custom_components/freshairiq/notifications.py').read_text(); assert '"entity_id": entity_id' in s; assert '"target": {"entity_id": entity_id}' not in s
def test_pdf_runtime_loading_returns_503_path():
 s=(ROOT/'custom_components/freshairiq/ventilation_log_api.py').read_text(); assert 'except RuntimeError:' in s and 'status_code=503' in s
def test_device_registry_no_deprecated_values_mapping():
 # 0.26.4.6: iterating devices.data yielded device IDs, so cleanup silently skipped every device.
 # F24 (2026-10-16): no mapping access at all (.data/.values() break in HA 2027.9); plain iteration.
 s=(ROOT/'custom_components/freshairiq/__init__.py').read_text(); assert 'def _iter_device_entries(' in s; assert 'raw.values()' not in s and 'getattr(collection, "data"' not in s; assert 'for item in list(collection if collection is not None else []):' in s
# test_room_editor_search_filtered_contacts_and_laundry: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_contact_picker_offers_real_and_helper_three_state_sources

def test_enrollment_409_recovers_locally_owned_legacy_token():
 s=(ROOT/'custom_components/freshairiq/telemetry.py').read_text(); assert 'status == 409' in s; assert '_async_recover_enrollment_token' in s; assert 'diagnostics_upload.*' in s
