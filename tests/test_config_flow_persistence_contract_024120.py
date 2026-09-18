"""Static regression guards for config-flow persistence hardening."""
from __future__ import annotations

import ast
from pathlib import Path


def _config_flow_tree() -> ast.Module:
    path = Path(__file__).resolve().parents[1] / "custom_components/freshairiq/config_flow.py"
    return ast.parse(path.read_text(encoding="utf-8"))


def test_contact_delay_forms_do_not_cast_persisted_values_with_raw_int() -> None:
    """Corrupt historic delay strings must not crash a form before validation."""
    guarded = {"async_step_add_delays", "async_step_room_delays", "async_step_contact_delays"}
    tree = _config_flow_tree()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in guarded:
            continue
        found.add(node.name)
        source_calls = [
            call for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_safe_int"
        ]
        assert source_calls, f"{node.name} must sanitize delay values with _safe_int"

        for call in ast.walk(node):
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "int"
                and call.args
            ):
                continue
            rendered = ast.unparse(call.args[0])
            assert "current.get" not in rendered
            assert "user_input.get" not in rendered
    assert found == guarded
