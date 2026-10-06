from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/'custom_components/freshairiq/config_flow.py').read_text()
DE=json.loads((ROOT/'custom_components/freshairiq/translations/de.json').read_text())
EN=json.loads((ROOT/'custom_components/freshairiq/translations/en.json').read_text())

def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values(): yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj: yield from _walk(v)

def test_room_reconfigure_has_no_separate_orientation_or_delay_menu():
    assert 'menu_options=["room_basics", "room_goals", "room_references", "save_room"]' in FLOW

def test_unified_opening_schema_orders_reference_delay_orientation_cover():
    block=FLOW[FLOW.index('def _single_contact_reference_schema'):FLOW.index('def _apply_single_contact_reference')]
    keys=['vol.Optional("reference_temperature"','vol.Optional("reference_humidity"','vol.Required("delay_seconds"','vol.Required("orientation"','vol.Optional("covers"']
    positions=[block.index(k) for k in keys]
    assert positions == sorted(positions)

def test_unified_opening_persists_delay_and_orientation():
    block=FLOW[FLOW.index('def _apply_single_contact_reference'):FLOW.index('def _normalise_room')]
    assert 'room[CONF_CONTACT_ORIENTATIONS] = orientations' in block
    assert 'room[CONF_CONTACT_DELAYS] = delays' in block

def test_german_resident_names_have_comma_example_everywhere():
    hits=[]
    for d in _walk(DE):
        dd=d.get('data_description')
        if isinstance(dd,dict) and 'adult_resident_names' in dd:
            hits.append(dd['adult_resident_names'])
    assert hits and all('Paul, Lydia' in x and 'Komma' in x for x in hits)

def test_german_unified_opening_copy_present():
    c=DE['options']['step']['contact_references']
    assert c['data']['delay_seconds']=='Öffnungsverzögerung'
    assert c['data']['orientation']=='Himmelsrichtung'
    assert '120 s' in c['data_description']['delay_seconds']

def test_english_parity_for_unified_opening():
    c=EN['options']['step']['contact_references']
    assert c['data']['delay_seconds']=='Opening delay'
    assert c['data']['orientation']=='Compass orientation'
