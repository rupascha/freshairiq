"""Regression contract for v0.25.0.43 device-registry cleanup hotfix."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "custom_components/freshairiq/__init__.py"

def test_cleanup_iterates_device_entries_not_mapping_keys():
    # 0.26.4.6: the former ``getattr(devices, "data", devices)`` iteration still
    # yielded mapping keys (device IDs). Behaviour is covered in
    # tests/test_room_deletion_026406.py.
    text = INIT.read_text(encoding="utf-8")
    assert 'getattr(registered_devices, "data", registered_devices)' not in text
    assert 'for device in device_registry.devices:' not in text
    assert 'for device in _iter_device_entries(device_registry, entry.entry_id):' in text

def test_cleanup_skips_unexpected_registry_items_without_blocking_setup():
    text = INIT.read_text(encoding="utf-8")
    assert 'if item is None or not hasattr(item, "identifiers") or not hasattr(item, "id"):' in text
    assert 'Skipping unexpected device-registry item during room cleanup' in text
