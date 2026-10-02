from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/"custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")

def test_native_contact_form_uses_only_static_translatable_field_names():
    schema=FLOW[FLOW.index("def _single_contact_reference_schema"):FLOW.index("def _apply_single_contact_reference")]
    for key in ("reference_temperature","reference_humidity","covers","passage_door"):
        assert f'"{key}"' in schema
    assert "opening_" not in schema
    assert "__freshairiq_reference_" not in schema

def test_passage_field_has_de_and_en_label_and_explanation_in_all_native_flows():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text())
    targets=lambda d: (
        d["config"]["step"]["room_references"],
        d["options"]["step"]["contact_references"],
        d["config_subentries"]["room"]["step"]["room_references"],
    )
    for dd,ee in zip(targets(de),targets(en)):
        assert dd["data"]["passage_door"]=="Durchgangstür – nach dem Durchgehen wird sie von außen zugezogen"
        assert ee["data"]["passage_door"]=="Passage door – pulled shut from outside after passing through"
        assert "zum Rauchen auf die Terrasse oder den Balkon" in dd["data_description"]["passage_door"]
        assert "echten Drei-Zustands-Kontaktsensor im Türbeschlag" in dd["data_description"]["passage_door"]
        assert "smoke on the terrace or balcony" in ee["data_description"]["passage_door"]
        assert "genuine three-state contact sensor installed in the door hardware" in ee["data_description"]["passage_door"]

def test_every_static_field_has_de_and_en_label_and_description():
    for lang in ("de","en"):
        d=json.loads((ROOT/f"custom_components/freshairiq/translations/{lang}.json").read_text())
        for obj in (
            d["config"]["step"]["room_references"],
            d["options"]["step"]["contact_references"],
            d["config_subentries"]["room"]["step"]["room_references"],
        ):
            for key in ("reference_temperature","reference_humidity","covers","passage_door"):
                assert obj["data"].get(key)
                assert obj["data_description"].get(key)
            assert "opening_" not in " ".join(obj["data"])

def test_apply_changes_only_selected_real_contact():
    apply=FLOW[FLOW.index("def _apply_single_contact_reference"):FLOW.index("def _normalise_room")]
    assert "temperatures = dict(room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {})" in apply
    assert "temperatures[contact] = temp" in apply
    assert "contact_covers[contact]" in apply
    assert 'passage_doors[contact] = bool(user_input.get("passage_door", False))' in apply

def test_contact_name_prefers_home_assistant_friendly_name_with_readable_fallback():
    helper=FLOW[FLOW.index("def _contact_display_name"):FLOW.index("def _single_contact_reference_schema")]
    assert 'get("friendly_name")' in helper
    assert 're.sub(r"[_-]+", " ", object_id)' in helper
