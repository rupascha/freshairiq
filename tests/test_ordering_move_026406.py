"""0.26.4.6: one dropdown change is enough to reorder goals or rooms."""
from __future__ import annotations

import ast
from pathlib import Path

FLOW = Path(__file__).resolve().parents[1] / "custom_components/freshairiq/config_flow.py"


def _resolve():
    tree = ast.parse(FLOW.read_text(encoding="utf-8"))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_resolve_move_ranking")
    namespace: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(FLOW), "exec"), namespace)
    return namespace["_resolve_move_ranking"]


def test_single_change_moves_the_goal_and_shifts_the_others():
    resolve = _resolve()
    current = ["humidity", "co2", "temperature"]
    # The reported case: CO2 newly available, user picks it as priority 1 only.
    assert resolve(["co2", "co2", "temperature"], current) == ["co2", "humidity", "temperature"]
    assert resolve(["humidity", "co2", "humidity"], current) == ["temperature", "co2", "humidity"]
    assert resolve(["temperature", "co2", "temperature"], current) == ["temperature", "co2", "humidity"]


def test_complete_valid_orders_are_kept_unchanged():
    resolve = _resolve()
    current = ["humidity", "co2", "temperature"]
    assert resolve(current, current) == current
    assert resolve(["co2", "temperature", "humidity"], current) == ["co2", "temperature", "humidity"]


def test_result_is_always_a_permutation():
    import itertools

    resolve = _resolve()
    current = ["a", "b", "c", "d"]
    for ranked in itertools.product(current, repeat=4):
        result = resolve(list(ranked), current)
        assert sorted(result) == sorted(current)


def test_room_sorting_uses_the_same_move_semantics():
    source = FLOW.read_text(encoding="utf-8")
    block = source[source.index("async def async_step_sort_rooms"):source.index("def _room_order_schema")]
    assert "ranked_keys = _resolve_move_ranking(ranked_keys, current_keys)" in block
    assert "len(set(ranked_keys)) != len(ranked_keys)" not in block
