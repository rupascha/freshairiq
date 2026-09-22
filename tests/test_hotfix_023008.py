from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
INIT = (ROOT / 'custom_components/freshairiq/__init__.py').read_text()
CARD = (ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
MANIFEST = json.loads((ROOT / 'custom_components/freshairiq/manifest.json').read_text())


def test_direct_card_module_is_active_frontend_resource():
    assert '_FRONTEND_MODULE = f"{_FRONTEND_URL}/freshairiq-card.js?v={VERSION}"' in INIT
    assert 'freshairiq-loader.js?v=' not in INIT


def test_direct_registration_uses_exactly_one_active_path():
    setup = INIT.split('async def async_setup', 1)[1].split('def _async_sync_room_subentries', 1)[0]
    assert 'resource_registered = await _async_register_lovelace_resource(hass)' in setup
    assert 'if not resource_registered:' in setup
    assert 'add_extra_js_url(hass, _FRONTEND_MODULE)' in setup
    assert setup.index('await _async_register_lovelace_resource(hass)') < setup.index('add_extra_js_url(hass, _FRONTEND_MODULE)')


def test_card_registers_public_element_directly():
    assert 'customElements.define(FAIQ_CARD, FreshAirIQCard)' in CARD
    assert 'freshairiq-card-impl' not in CARD
    assert 'FreshAirIQEarlyProxy' not in CARD


def test_generated_dashboard_is_full_freshairiq_card():
    assert 'cards: [{ type: "custom:freshairiq-card" }]' in CARD
    assert 'navigation_path:"/freshairiq-safe"' not in CARD


def test_panel_custom_no_longer_required():
    assert 'panel_custom' not in MANIFEST.get('dependencies', [])
    assert '_async_register_safe_panel' not in INIT


def test_version_is_current():
    assert MANIFEST['version'] == '0.25.0.48'
    assert 'const FAIQ_VERSION = "0.25.0.48";' in CARD


def test_old_loader_resource_is_migrated_not_used():
    assert '_FRONTEND_OLD_LOADER_BASE' in INIT
    assert 'freshairiq-loader.js' in INIT
    assert 'async_update_item' in INIT
    assert 'async_delete_item' in INIT
    assert '_FRONTEND_MODULE = f"{_FRONTEND_URL}/freshairiq-card.js?v={VERSION}"' in INIT
