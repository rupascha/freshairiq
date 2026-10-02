from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/"custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
CARD=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def _walk(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            here=f"{path}.{key}" if path else key
            yield here, value
            yield from _walk(value, here)

def test_de_en_translation_surfaces_have_exact_key_parity_and_nonempty_labels():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text(encoding="utf-8"))
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text(encoding="utf-8"))
    de_flat={p:v for p,v in _walk(de) if not isinstance(v,dict)}
    en_flat={p:v for p,v in _walk(en) if not isinstance(v,dict)}
    assert set(de_flat)==set(en_flat)
    for lang,data in (("de",de),("en",en)):
        for path,obj in _walk(data):
            if path.endswith(".data") and isinstance(obj,dict):
                # Dynamic per-contact steps intentionally have an empty translation data map;
                # their labels are generated from the contact friendly name in config_flow.py.
                assert all(isinstance(v,str) and v.strip() for v in obj.values()), f"{lang}: missing label in {path}"

def test_field_labels_do_not_repeat_defaults():
    for lang, token in (("de","(Standard:"),("en","(Default:")):
        data=json.loads((ROOT/f"custom_components/freshairiq/translations/{lang}.json").read_text(encoding="utf-8"))
        for path,obj in _walk(data):
            if path.endswith(".data") and isinstance(obj,dict):
                assert all(token not in str(v) for v in obj.values()), f"{lang}: redundant default in {path}"

def test_english_settings_have_no_known_german_empty_residue():
    en=(ROOT/"custom_components/freshairiq/translations/en.json").read_text(encoding="utf-8")
    assert "Default: leer" not in en
    assert "Recipients (Default: leer)" not in en
    assert "Default: leer" not in CARD

def test_passage_door_is_owned_by_each_contact_not_room_multiselect():
    schema=FLOW[FLOW.index("def _contact_reference_schema"):FLOW.index("def _apply_contact_references")]
    assert '_contact_reference_field(str(contact), "passage")' in schema
    assert "selector.BooleanSelector()" in schema
    assert 'description=f"{label} · {passage_label}"' in schema
    assert "SelectSelectorConfig(options=options, multiple=True" not in schema

def test_passage_door_roundtrip_remains_contact_keyed_and_backwards_compatible():
    apply=FLOW[FLOW.index("def _apply_contact_references"):FLOW.index("def _normalise_room")]
    assert 'user_input.get(_contact_reference_field(contact, "passage"), False)' in apply
    assert "room[CONF_CONTACT_PASSAGE_DOORS] = passage_doors" in apply
    normalise=FLOW[FLOW.index("def _normalise_room"):FLOW.index("def _normalise_legacy_entry_data")]
    assert "CONF_CONTACT_PASSAGE_DOORS: deepcopy(previous.get(CONF_CONTACT_PASSAGE_DOORS, {}))" in normalise

def test_dynamic_contact_labels_follow_ha_language():
    schema=FLOW[FLOW.index("def _contact_reference_schema"):FLOW.index("def _apply_contact_references")]
    assert 'language", "") or "").lower().startswith("de")' in schema
    for de,en in (
        ("Referenztemperatur","Reference temperature"),
        ("Referenzfeuchte","Reference humidity"),
        ("Rollo/Jalousie","Blind/shutter"),
        ("Durchgangstür – wird von außen nur zugezogen","Passage door – may only be pulled shut from outside"),
    ):
        assert de in schema and en in schema

def test_dashboard_passage_setting_is_inside_each_contact_card():
    method=CARD[CARD.index("_settingsContactRows("):CARD.index("_settingsRoomEditor(",CARD.index("_settingsContactRows("))]
    assert 'data-contact="${esc(c)}"' in method
    assert 'class="room-contact-passage"' in method
    assert method.index('class="room-contact-passage"') > method.index('room-contact-covers')

def test_dashboard_generic_setting_row_does_not_render_default_every_time():
    field=CARD[CARD.index("_settingsField("):CARD.index("_settingsGroup(",CARD.index("_settingsField("))]
    assert "<small>Standard:" not in field
    assert "Beispiel:" in field
