from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text(encoding='utf-8')
DE = json.loads((ROOT / 'custom_components/freshairiq/translations/de.json').read_text(encoding='utf-8'))
EN = json.loads((ROOT / 'custom_components/freshairiq/translations/en.json').read_text(encoding='utf-8'))

def test_passage_door_is_rendered_per_opening_with_static_translatable_field():
    assert 'vol.Optional("passage_door", default=current)' in FLOW
    assert 'async_step_room_passage_door' in FLOW
    assert 'async_step_contact_passage_door' in FLOW
    assert '__freshairiq_passage_door' not in FLOW

def test_passage_door_wording_keeps_required_meaning_and_hardware_warning():
    de = json.dumps(DE, ensure_ascii=False)
    en = json.dumps(EN, ensure_ascii=False)
    assert 'Durchgangstür, die von außen zugezogen wird' in de
    assert 'echter Drei-Zustands-Kontaktsensor im Türbeschlag' in de
    assert 'Nicht für Drei-Zustands-Helfer' in de
    assert 'Passage door that can be pulled shut from outside' in en
    assert 'genuine three-state contact sensor in the door hardware' in en
    assert 'Do not enable it for three-state helpers' in en

def test_existing_persisted_contact_mapping_is_used_as_default_and_storage_contract_stays_same():
    assert 'room.get(CONF_CONTACT_PASSAGE_DOORS)' in FLOW
    assert '_apply_passage_door' in FLOW
    assert 'mapping[contact] = True' in FLOW
