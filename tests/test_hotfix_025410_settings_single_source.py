"""v0.25.4.10 regression: one canonical FreshAirIQ configuration surface."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'custom_components/freshairiq'
FLOW=(COMP/'config_flow.py').read_text(encoding='utf-8')
CARD=(COMP/'frontend/freshairiq-card.js').read_text(encoding='utf-8')

def test_room_subentry_is_add_only_and_quick_setup_offers_manual_or_ha_import():
    start=FLOW.index('class FreshAirIQRoomSubentryFlow')
    end=FLOW.index('class FreshAirIQOptionsFlow',start)
    block=FLOW[start:end]
    assert 'async def async_step_reconfigure' not in block
    assert 'menu_options=["create_room", "import_ha_room"]' in block
    assert 'async def async_step_create_room' in block
    assert 'async def async_step_import_ha_room' in block
    assert 'async def async_step_import_ha_room_details' in block

def test_parent_options_remain_complete_including_residents_and_room_lifecycle():
    for step in ('residents','rooms','add_room','import_ha_rooms','edit_room_select','remove_room','sort_rooms'):
        assert f'async def async_step_{step}' in FLOW
    assert 'menu_options=["outdoor", "building", "residents", "levels", "rooms", "back_to_main"]' in FLOW

def test_dashboard_has_no_duplicate_integration_settings_entry_point():
    assert 'id="settings-gear"' not in CARD
    assert 'data-support-open-settings=' not in CARD
    assert 'Geräte & Dienste → FreshAirIQ → Konfigurieren' in CARD

def test_dashboard_card_editor_is_presentation_only():
    start=CARD.index('class FreshAirIQCardEditor')
    editor=CARD[start:]
    assert 'data-global-sensor-key' not in editor[editor.index('    _render() {'):]
    for key in ('show_branding','show_rooms_button','show_support_button','show_rec_ventilate','show_rec_close'):
        assert key in editor

def test_de_en_quick_setup_and_central_settings_copy_exist():
    de=json.loads((COMP/'translations/de.json').read_text(encoding='utf-8'))
    en=json.loads((COMP/'translations/en.json').read_text(encoding='utf-8'))
    assert de['config_subentries']['room']['step']['user']['menu_options']['import_ha_room']=='Aus Home Assistant importieren'
    assert en['config_subentries']['room']['step']['user']['menu_options']['import_ha_room']=='Import from Home Assistant'
    assert 'Bewohner' in json.dumps(de['options'],ensure_ascii=False)
    assert 'Residents' in json.dumps(en['options'],ensure_ascii=False)
