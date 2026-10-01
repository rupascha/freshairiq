from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_quick_setup_contract_and_translations_are_present():
    source = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text(encoding='utf-8')
    assert 'QUICK_SETUP_HEIGHT_M = 2.40' in source
    assert 'area * QUICK_SETUP_HEIGHT_M' in source
    assert 'async_step_quick_room' in source
    assert '"quick", "exact", "later"' in source
    for language in ('de', 'en'):
        data = json.loads((ROOT / f'custom_components/freshairiq/translations/{language}.json').read_text(encoding='utf-8'))
        assert 'quick_room' in data['config']['step']
        assert 'setup_mode' in data['selector']
        text = json.dumps(data['config']['step']['quick_room'], ensure_ascii=False)
        assert ('2,40' in text or '2.40' in text)


def test_support_is_separate_from_settings_and_details():
    card = (ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')
    assert 'id="settings"' in card
    assert 'id="support"' in card
    assert '_supportPanel(st)' in card
    settings_home = card[card.index('_settingsHome()'):card.index('_settingsGroupMenu(name)')]
    assert 'Feedback & Fehler melden' not in settings_home
    details = card[card.index('_details(st, rooms)'):card.index('async _exportDiagnostics()')]
    assert 'DIAGNOSE & TEST' not in details


def test_native_data_learning_no_longer_mixes_diagnostics_support():
    source = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text(encoding='utf-8')
    block = source[source.index('async def async_step_data_learning_settings'):source.index('# Compatibility aliases')]
    assert 'diagnostics_sharing' not in block
