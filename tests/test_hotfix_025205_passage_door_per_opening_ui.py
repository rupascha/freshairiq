from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def test_passage_door_is_rendered_as_contact_local_boolean_not_room_multiselect():
    assert 'def _contact_passage_field(contact: str)' in FLOW
    assert 'selector.BooleanSelector()' in FLOW
    assert 'Passage-door behaviour belongs to one concrete opening' in FLOW
    assert 'SelectSelectorConfig(options=options, multiple=True' not in FLOW


def test_passage_door_wording_keeps_required_meaning_and_hardware_warning():
    assert 'Durchgangstür, die von außen zugezogen wird' in FLOW
    assert 'echtem Drei-Zustands-Kontaktsensor im Türbeschlag' in FLOW
    assert 'Passage door that is pulled shut from outside' in FLOW
    assert 'genuine three-state contact sensor in the door hardware' in FLOW


def test_existing_persisted_contact_mapping_is_used_as_default_and_storage_contract_stays_same():
    assert 'default=bool(passage_doors.get(contact, False))' in FLOW
    assert 'room[CONF_CONTACT_PASSAGE_DOORS]' in FLOW
    assert 'compatibility fallback for in-flight/legacy forms' in FLOW
