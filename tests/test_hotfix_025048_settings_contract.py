"""v0.25.4.8 regression: passive geometry, legacy references and priorities."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def _function(name: str) -> ast.FunctionDef:
    tree = ast.parse(FLOW)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def test_passive_rooms_do_not_require_geometry_but_active_rooms_still_do():
    src = ast.get_source_segment(FLOW, _function("_normalise_room")) or ""
    assert "if include:" in src
    assert 'errors["base"] = "room_volume_required"' in src
    assert "Passive/imported planning shell" in src
    assert "room.pop(CONF_ROOM_VOLUME, None)" in src


def test_current_editors_never_write_legacy_room_wide_reference_air():
    src = ast.get_source_segment(FLOW, _function("_normalise_room")) or ""
    assert "room.pop(CONF_ROOM_REFERENCE_TEMPERATURE, None)" in src
    assert "room.pop(CONF_ROOM_REFERENCE_HUMIDITY, None)" in src
    # Dashboard must not copy legacy values back into a current room save.
    save = CARD[CARD.index('const room = {'):CARD.index('const ok = await this._settingsPost({ action: "upsert_room", room });')]
    assert "reference_temperature:" not in save
    assert "reference_humidity:" not in save


def test_duplicate_priorities_are_rejected_in_native_and_dashboard_editors():
    assert 'target = idx - 1 if direction == "up" else idx + 1' in FLOW
    assert "_goal_priority_errors(user_input, room)" in FLOW
    assert "new Set(room.goal_priorities).size !== room.goal_priorities.length" in CARD
    assert "Jede Lüftungspriorität darf nur einmal ausgewählt werden." in CARD
