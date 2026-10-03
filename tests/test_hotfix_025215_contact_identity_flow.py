from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/"custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")

def test_no_failed_multi_opening_schema_is_used_anymore():
    assert "def _contact_reference_schema" not in FLOW
    assert "_contact_reference_slot(" not in FLOW

def test_all_four_native_flows_show_one_contact_at_a_time_with_real_identity():
    # Initial config + subentry reconfigure use room_references; Options uses contact_references.
    assert FLOW.count("_single_contact_reference_schema(room, contact)") == 4
    assert FLOW.count('"contact_name": _contact_display_name(self.hass, contact)') == 4
    assert FLOW.count('"contact_entity": contact') == 4
    assert FLOW.count('"contact_position": str(index + 1)') == 4
    assert FLOW.count('"contact_count": str(len(contacts))') == 4

def test_each_submission_advances_to_next_actual_contact():
    assert "self._room_reference_contact_index = index + 1" in FLOW
    assert "self._contact_reference_index = index + 1" in FLOW
    assert "contact = str(contacts[index])" in FLOW

def test_translation_titles_identify_actual_contact_not_opening_number():
    for lang in ("de","en"):
        d=json.loads((ROOT/f"custom_components/freshairiq/translations/{lang}.json").read_text())
        for obj in (
            d["config"]["step"]["room_references"],
            d["options"]["step"]["contact_references"],
            d["config_subentries"]["room"]["step"]["room_references"],
            d["config_subentries"]["room"]["step"]["add_references"],
        ):
            assert "{contact_name}" in obj["title"]
            assert "{contact_entity}" in obj["description"]
            assert "opening_" not in json.dumps(obj).lower()

def test_passage_help_contains_requested_real_world_example_and_sensor_constraint():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    help_text=de["options"]["step"]["contact_references"]["data_description"]["passage_door"]
    assert "Rauchen" in help_text
    assert "Terrasse" in help_text and "Balkon" in help_text
    assert "echten Drei-Zustands-Kontaktsensor" in help_text
    assert "Türbeschlag" in help_text
    assert "Drei-Zustands-Helfer" in help_text
