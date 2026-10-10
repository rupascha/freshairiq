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


# test_current_editors_never_write_legacy_room_wide_reference_air: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).


def test_duplicate_priorities_are_rejected_in_native_and_dashboard_editors():
    # 0.26.4.6: duplicates are no longer rejected but resolved as a move
    # (user report: the order could not be confirmed after adding CO2 sensors).
    # Behaviour: tests/test_ordering_move_026406.py
    assert "duplicate_goal_order" in FLOW
    assert "_resolve_move_ranking(ranked, current)" in FLOW
    assert "_goal_priority_errors(user_input, room)" in FLOW
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
