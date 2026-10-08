"""0.26.4.4: setup-dialog texts and navigation (user + community reports, 2026-10-08)."""
import ast
import json
import re
from pathlib import Path

COMP = Path(__file__).resolve().parents[1] / "custom_components/freshairiq"
FLOW_SRC = (COMP / "config_flow.py").read_text(encoding="utf-8")
FLOW = ast.parse(FLOW_SRC)
SECTIONS = {"FreshAirIQConfigFlow": ("config",), "FreshAirIQOptionsFlow": ("options",), "FreshAirIQRoomSubentryFlow": ("config_subentries", "room")}
KNOWN_HELPERS = {"_resident_placeholders": {"resident_slots", *(f"{r}_{i}" for r in ("adult", "child") for i in range(1, 5))}}


def _show_form_calls():
    """(class, step_id, provided placeholder keys or None if not statically known)."""
    for cls in FLOW.body:
        if not isinstance(cls, ast.ClassDef) or cls.name not in SECTIONS:
            continue
        for node in ast.walk(cls):
            if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "async_show_form"):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            step = kw.get("step_id")
            if not isinstance(step, ast.Constant):
                continue
            ph = kw.get("description_placeholders")
            if ph is None:
                provided = set()
            elif isinstance(ph, ast.Dict):
                provided = {k.value for k in ph.keys if isinstance(k, ast.Constant)}
            elif isinstance(ph, ast.Call) and getattr(ph.func, "attr", "") in KNOWN_HELPERS:
                provided = KNOWN_HELPERS[ph.func.attr]
            else:
                provided = None
            yield cls.name, step.value, provided


def _placeholders(obj):
    text = json.dumps(obj, ensure_ascii=False)
    return set(re.findall(r"(?<!\{)\{([a-z_0-9]+)\}(?!\})", text))


def test_every_text_placeholder_is_provided_by_every_form_of_that_step():
    # Community report: "Translation [formatjs Error: MISSING_VALUE] ... contact_name" on
    # "Raum hinzufügen" and "<Raum> bearbeiten" - the step texts used the per-opening
    # placeholders of a different page.
    problems = []
    for lang in ("de", "en"):
        data = json.loads((COMP / f"translations/{lang}.json").read_text(encoding="utf-8"))
        for cls, step, provided in _show_form_calls():
            if provided is None:
                continue
            node = data
            for key in SECTIONS[cls]:
                node = node[key]
            step_text = node["step"].get(step, {})
            missing = _placeholders(step_text) - provided
            if missing:
                problems.append(f"{lang}:{cls}:{step} missing {sorted(missing)}")
    assert problems == []


def test_room_wizard_has_back_navigation_and_no_separate_orientation_or_delay_pages():
    sub = FLOW_SRC[FLOW_SRC.index("class FreshAirIQRoomSubentryFlow"):FLOW_SRC.index("class FreshAirIQOptionsFlow")]
    assert "async def async_step_add_orientations" not in sub and "async def async_step_add_delays" not in sub
    assert 'data_schema=_goal_priority_schema(room, include_back=True)' in sub
    assert "data_schema=_schema_with_wizard_back(_single_contact_reference_schema(room, contact))" in sub
    assert "return await self._async_step_room_origin()" in sub
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    steps = de["config_subentries"]["room"]["step"]
    assert "add_orientations" not in steps and "add_delays" not in steps
    assert steps["add_goals"]["data"]["wizard_back"] == steps["add_references"]["data"]["wizard_back"] == "← Zurück zur vorherigen Seite"


def test_selection_pages_offer_a_way_back():
    for step in ("recommendation_priorities", "edit_room_select"):
        body = FLOW_SRC[FLOW_SRC.index(f"    async def async_step_{step}("):]
        body = body[:body.index("\n    async def ", 10)]
        assert 'vol.Optional("wizard_back", default=False)' in body and 'user_input.get("wizard_back")' in body, step


def test_resident_profile_fields_show_the_resident_names():
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    labels = de["options"]["step"]["residents"]["sections"]["resident_profiles"]["data"]
    assert labels["adult_1_rooms"] == "{adult_1} – Räume" and labels["child_2_thermal"] == "{child_2} – Temperaturvorliebe"
    start = FLOW_SRC.index("def _resident_slot_placeholders(")
    src = FLOW_SRC[FLOW_SRC.index("def _resident_name_list("):FLOW_SRC.index("\ndef ", FLOW_SRC.index("def _resident_name_list(") + 5)]
    src += FLOW_SRC[start:FLOW_SRC.index("\ndef ", start + 5)]
    ns = {}
    exec(compile("from typing import Any\n" + src, "slots", "exec"), ns)
    slots = ns["_resident_slot_placeholders"]({"adult_resident_names": "Anna, Ben", "child_resident_names": "Mia"})
    assert (slots["adult_1"], slots["adult_2"], slots["adult_3"], slots["child_1"], slots["child_4"]) == ("Anna", "Ben", "Erwachsener 3", "Mia", "Kind 4")
    assert ns["_resident_slot_placeholders"]({}, "en")["adult_1"] == "Adult 1"
