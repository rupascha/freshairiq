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

def test_passage_door_is_owned_by_one_real_contact_per_native_page():
    schema=FLOW[FLOW.index("def _single_contact_reference_schema"):FLOW.index("def _apply_single_contact_reference")]
    assert 'vol.Optional("passage_door"' in schema
    assert "selector.BooleanSelector()" in schema
    assert "SelectSelectorConfig(options=options, multiple=True" not in schema

def test_passage_door_roundtrip_remains_contact_keyed_and_backwards_compatible():
    apply=FLOW[FLOW.index("def _apply_single_contact_reference"):FLOW.index("def _normalise_room")]
    assert 'passage_doors[contact] = bool(user_input.get("passage_door", False))' in apply
    assert "room[CONF_CONTACT_PASSAGE_DOORS] = passage_doors" in apply
    normalise=FLOW[FLOW.index("def _normalise_room"):FLOW.index("def _normalise_legacy_entry_data")]
    assert "CONF_CONTACT_PASSAGE_DOORS: deepcopy(previous.get(CONF_CONTACT_PASSAGE_DOORS, {}))" in normalise

def test_native_contact_labels_use_static_translation_keys():
    schema=FLOW[FLOW.index("def _single_contact_reference_schema"):FLOW.index("def _apply_single_contact_reference")]
    assert '"passage_door"' in schema
    assert "opening_" not in schema

# test_dashboard_passage_setting_is_inside_each_contact_card: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).

# test_dashboard_generic_setting_row_does_not_render_default_every_time: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).
