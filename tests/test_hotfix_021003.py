from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
INIT = (COMP / "__init__.py").read_text(encoding="utf-8")


def test_lovelace_dependency_and_version():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.25.0.72"
    assert "lovelace" in manifest["dependencies"]


def test_frontend_has_single_registration_with_global_fallback():
    setup = INIT.split("async def async_setup", 1)[1].split("def _async_sync_room_subentries", 1)[0]
    assert "resource_registered = await _async_register_lovelace_resource(hass)" in setup
    assert "if not resource_registered:" in setup
    assert "add_extra_js_url(hass, _FRONTEND_MODULE)" in setup
    assert setup.index("await _async_register_lovelace_resource(hass)") < setup.index("add_extra_js_url(hass, _FRONTEND_MODULE)")
    assert '"res_type": "module"' in INIT
    assert "resources.async_create_item" in INIT


def test_resource_storage_is_loaded_before_items_or_create():
    load_at = INIT.index("await resources.async_get_info()")
    items_at = INIT.index("resources.async_items()")
    create_at = INIT.index("resources.async_create_item")
    assert load_at < items_at < create_at


def test_existing_resource_is_updated_not_duplicated():
    assert "_is_freshairiq_resource" in INIT
    assert "resources.async_update_item" in INIT
    assert "current.get(CONF_URL) != _FRONTEND_MODULE" in INIT


def test_frontend_registration_failure_cannot_break_backend_setup():
    assert "except Exception" in INIT
    assert "global frontend module fallback remains active" in INIT


def test_all_version_markers_match():
    assert 'VERSION = "0.25.0.72"' in (COMP / "const.py").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.72";' in (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert "Current release:" not in (ROOT / "README.md").read_text(encoding="utf-8")
