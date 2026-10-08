"""0.26.4.1: verified user reports (dashboard feedback, GitHub #10/#12, community forum)."""
import ast
import builtins
import json
import re
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
CARD = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")


def _undefined_names(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    top = symtable.symtable(src, str(path), "exec")
    defined = {s.get_name() for s in top.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    defined |= set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__path__", "__spec__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            defined.update(node.names)
        # `from .const import *`: take the names the star module defines.
        if isinstance(node, ast.ImportFrom) and node.module and any(a.name == "*" for a in node.names):
            module = path.parent / (node.module.replace(".", "/") + ".py")
            if module.exists():
                mtree = ast.parse(module.read_text(encoding="utf-8"))
                defined |= {n.id for n in ast.walk(mtree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                defined |= {n.name for n in mtree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    found = []

    def walk(table):
        for sym in table.get_symbols():
            name = sym.get_name()
            is_global = sym.is_global() if table is not top else not (sym.is_assigned() or sym.is_imported() or sym.is_namespace())
            if sym.is_referenced() and is_global and name not in defined:
                found.append(f"{path.name}:{table.get_lineno()} {table.get_name()} uses undefined {name!r}")
        for child in table.get_children():
            walk(child)

    walk(top)
    return found


def test_no_module_reads_an_undefined_name():
    # GitHub #12: `include_back` was read in _single_contact_reference_schema without
    # being defined, so adding a room crashed with NameError. Guard every module.
    problems = []
    for path in sorted(COMP.rglob("*.py")):
        problems += _undefined_names(path)
    assert problems == []


def test_single_contact_reference_schema_has_no_wizard_back_flag():
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    start = flow.index("def _single_contact_reference_schema(")
    body = flow[start:flow.index("\ndef ", start + 10)]
    assert "include_back" not in body


def test_heartbeat_needs_consent_and_reporting_not_off():
    # GitHub #10.
    text = (COMP / "telemetry.py").read_text(encoding="utf-8")
    start = text.index("async def async_activity_heartbeat")
    body = text[start:text.index("    def _health(", start)]
    assert body.index('== "off"') < body.index("/v1/activity")


def test_rooms_overview_has_no_goal_impact_tiles():
    # Dashboard feedback: "-6 ml entfernbar", "-2,0 °C kühler" and the CO2 tile are gone
    # from the room overview tiles; the room detail keeps its goal information.
    start = CARD.index("    _roomCardImpl(")
    body = CARD[start:CARD.index("    _infoBackButton()", start)]
    assert "_goalTracker" not in body


def test_people_are_counted_without_decimals():
    assert "fmt(st.effective_occupants || 0, 1)" not in CARD
    assert 'const fmtPeople = v =>' in CARD
    assert '${fmtPeople(st.effective_occupants || 0)} ${Number(st.effective_occupants) === 1 ? "Person" : "Personen"} aktuell' in CARD


def test_diagnostics_buttons_have_a_clean_two_line_layout():
    assert ".settings-room-actions #diagnostics-export,.settings-room-actions #diagnostics-send{flex:1 1 0" in CARD
    assert "grid-row:1 / 3" in CARD


def test_resident_placeholders_are_never_stored_or_used_as_names():
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert 'data-resident-name="${esc(r.name)}"' not in CARD
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert '"name": names[idx] if idx < len(names) else "",' in flow
    assert '"resident_slots": _resident_slot_overview(self._working_options, language),' in flow
    assert "description_placeholders=self._resident_placeholders()" in flow
    for lang in ("de", "en"):
        text = json.loads((COMP / f"translations/{lang}.json").read_text(encoding="utf-8"))
        assert "{resident_slots}" in text["options"]["step"]["residents"]["description"]


def test_slot_overview_names_each_numbered_profile():
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    src = flow[flow.index("def _resident_name_list("):flow.index("\ndef ", flow.index("def _resident_name_list(") + 5)]
    src += flow[flow.index("def _resident_slot_overview("):flow.index("\ndef ", flow.index("def _resident_slot_overview(") + 5)]
    ns = {"Any": object}
    exec(compile("from typing import Any\n" + src, "slot", "exec"), ns)
    overview = ns["_resident_slot_overview"]
    assert overview({"adult_occupants": 2, "adult_resident_names": "Anna", "child_occupants": 1, "child_resident_names": "Mia"}) == \
        "Erwachsener 1 = Anna · Erwachsener 2 = noch ohne Namen · Kind 1 = Mia"
    assert overview({"adult_occupants": 1, "adult_resident_names": "Anna"}, "en") == "Adult 1 = Anna"
    assert re.search("keine Bewohner", overview({}))
