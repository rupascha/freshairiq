from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
INIT = (COMP / "__init__.py").read_text(encoding="utf-8")


def _setup_block() -> str:
    return INIT.split("async def async_setup", 1)[1].split("def _async_sync_room_subentries", 1)[0]


def test_storage_resource_and_global_loader_are_mutually_exclusive():
    setup = _setup_block()
    assert "resource_registered = await _async_register_lovelace_resource(hass)" in setup
    assert "if not resource_registered:" in setup
    assert setup.count("add_extra_js_url(hass, _FRONTEND_MODULE)") == 1
    assert setup.index("await _async_register_lovelace_resource(hass)") < setup.index("add_extra_js_url(hass, _FRONTEND_MODULE)")


def test_storage_registration_reports_success_and_fallback_cases():
    func = INIT.split("async def _async_register_lovelace_resource", 1)[1].split("async def _async_execute_intervention_service", 1)[0]
    assert "-> bool:" in INIT
    assert func.count("return True") == 2
    assert func.count("return False") >= 3


def test_stale_loader_and_duplicate_storage_resources_are_cleaned():
    assert "_FRONTEND_OLD_LOADER_BASE" in INIT
    assert "resources.async_update_item" in INIT
    assert "resources.async_delete_item" in INIT
    assert "for duplicate in matching[1:]" in INIT


def test_active_resource_is_direct_card_not_proxy_loader():
    assert '_FRONTEND_MODULE = f"{_FRONTEND_URL}/freshairiq-card.js?v={VERSION}"' in INIT
    setup = _setup_block()
    assert "freshairiq-loader.js" not in setup


def test_release_version_is_consistent():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.25.0.76"
    assert 'VERSION = "0.25.0.76"' in (COMP / "const.py").read_text(encoding="utf-8")
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.76";' in (COMP / "frontend" / name).read_text(encoding="utf-8")
