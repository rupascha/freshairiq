"""Regression contract for v0.25.0.43 device-registry cleanup hotfix."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "custom_components/freshairiq/__init__.py"

def test_cleanup_iterates_device_entries_not_mapping_keys():
    text = INIT.read_text(encoding="utf-8")
    assert 'registered_devices.values()' in text
    assert 'for device in device_registry.devices:' not in text

def test_cleanup_skips_unexpected_registry_items_without_blocking_setup():
    text = INIT.read_text(encoding="utf-8")
    assert 'if not hasattr(device, "identifiers") or not hasattr(device, "id"):' in text
    assert 'Skipping unexpected device-registry item during room cleanup' in text
