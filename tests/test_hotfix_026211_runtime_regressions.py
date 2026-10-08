from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components/freshairiq"
FLOW=(COMP/"config_flow.py").read_text(encoding="utf-8")
CARD=(COMP/"frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_contact_reference_schema_has_no_undefined_include_back():
    block=FLOW[FLOW.index("def _single_contact_reference_schema"):FLOW.index("def _schema_with_wizard_back")]
    assert "include_back" not in block
    assert "return vol.Schema(fields)" in block

def test_back_is_added_by_outer_wrapper_only():
    block=FLOW[FLOW.index("def _schema_with_wizard_back"):FLOW.index("def _apply_single_contact_reference")]
    assert 'vol.Optional("wizard_back", default=False)' in block
    assert "selector.BooleanSelector()" in block

def test_rooms_uses_proven_generic_navigation_path():
    assert '<div class="ai-all-good clickable" data-info="rooms">' in CARD
    assert 'querySelectorAll("[data-info]")' in CARD
    assert ':not([data-info="rooms"])' not in CARD
    assert 'if (this._info === "rooms")' in CARD

def test_back_translation_has_no_duplicate_description():
    for language in ("de","en"):
        data=json.loads((COMP/"translations"/f"{language}.json").read_text(encoding="utf-8"))
        for step in ("sort_rooms","recommendation_priority_order","room_goals"):
            entry=data["options"]["step"][step]
            assert "wizard_back" in entry["data"]
            assert "wizard_back" not in entry.get("data_description",{})
