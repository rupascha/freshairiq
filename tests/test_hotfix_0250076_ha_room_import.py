from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text(encoding='utf-8')


def test_native_ha_area_and_floor_registries_are_used():
    assert 'area_registry as ar' in FLOW
    assert 'floor_registry as fr' in FLOW
    assert 'ar.async_get(self.hass)' in FLOW
    assert 'fr.async_get(self.hass)' in FLOW
    assert 'area.floor_id' in FLOW


def test_room_import_is_explicit_and_multi_select():
    assert '"import_ha_rooms"' in FLOW
    assert 'async_step_import_ha_rooms' in FLOW
    assert 'multiple=True' in FLOW
    assert 'async_step_import_ha_room_details' in FLOW


def test_import_does_not_invent_room_physics():
    block = FLOW.split('async def async_step_import_ha_room_details', 1)[1].split('async def async_step_add_room', 1)[0]
    assert 'CONF_ROOM_INCLUDE_CALCULATIONS: False' in block
    assert 'CONF_ROOM_VOLUME:' not in block
    assert '_room_section_schema' in block
    assert '_normalise_room' in block


def test_existing_room_names_are_not_offered_again():
    assert 'existing_names' in FLOW
    assert 'area.name.strip().casefold() in existing_names' in FLOW


def test_import_strings_exist_in_both_languages():
    for language in ('de', 'en'):
        data = json.loads((ROOT / f'custom_components/freshairiq/translations/{language}.json').read_text(encoding='utf-8'))
        steps = data['options']['step']
        assert 'import_ha_rooms' in steps
        assert 'import_ha_room_details' in steps
        assert 'import_ha_rooms' in steps['rooms']['menu_options']


def test_current_version():
    assert '0.25.1.6' in (ROOT / 'custom_components/freshairiq/const.py').read_text(encoding='utf-8')
