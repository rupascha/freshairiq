from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/"custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")

def test_native_contact_form_never_uses_entity_id_as_visible_field_key():
    schema=FLOW[FLOW.index("def _contact_reference_schema"):FLOW.index("def _apply_contact_references")]
    assert "_contact_reference_slot(index" in schema
    assert "_contact_reference_field(str(contact)" not in schema
    assert "description=" not in schema

def test_passage_slot_has_de_and_en_label_and_explanation():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text())
    for section,step in (("options","contact_references"),("config","room_references")):
        dd=de[section]["step"][step]; ee=en[section]["step"][step]
        assert dd["data"]["opening_1_passage"]=="Öffnung 1 · Durchgangstür – wird von außen nur zugezogen"
        assert ee["data"]["opening_1_passage"]=="Opening 1 · Passage door – only pulled shut from outside"
        assert "echter Drei-Zustands-Kontaktsensor im Türbeschlag" in dd["data_description"]["opening_1_passage"]
        assert "genuine three-state contact sensor installed in the door hardware" in ee["data_description"]["opening_1_passage"]

def test_all_per_opening_fields_are_translated_for_de_and_en():
    for lang in ("de","en"):
        d=json.loads((ROOT/f"custom_components/freshairiq/translations/{lang}.json").read_text())
        for section,step in (("options","contact_references"),("config","room_references")):
            data=d[section]["step"][step]["data"]
            for n in range(1,17):
                for kind in ("temperature","humidity","covers","passage"):
                    assert data.get(f"opening_{n}_{kind}")

def test_apply_maps_slots_back_to_actual_contact_and_accepts_legacy_keys():
    apply=FLOW[FLOW.index("def _apply_contact_references"):FLOW.index("def _normalise_room")]
    assert "_contact_reference_slot(index, kind)" in apply
    assert "_contact_reference_field(contact, kind)" in apply
    assert 'passage_doors[contact] = bool(_value("passage", False))' in apply
