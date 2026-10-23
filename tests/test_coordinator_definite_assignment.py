"""Every value the coordinator phases read must be bound on every path.

0.26.3.1 shipped a refactoring step that left ``status`` unbound when the
intelligent recommendation carried no status (``status = ... or status``). The
golden master could not see it because every scenario produced a status. This
static check sees all paths.
"""
import ast
import importlib.util
from pathlib import Path

from tests._source import module_files, module_source

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("definite_assignment_check", ROOT / "tools/definite_assignment_check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

COORD = str(ROOT / "custom_components/freshairiq/coordinator.py")
RULES = str(ROOT / "custom_components/freshairiq/house_decision.py")

# Path-insensitive analysis cannot correlate an exception handler that always
# leaves the function. Each entry is reviewed: every handler of the try that binds
# the name raises or returns, so the name is bound wherever it is read.
REVIEWED = {"_async_update_data": {"data"}, "_localize_output": {"localized"}, "_exhaust_stopped_for_seconds": {"started"}}

# 0.26.5.2 maintenance: the coordinator phases are split into named phase helpers in
# the coordinator_* modules. Every function of every coordinator module is checked.
PHASES = ("_async_update_data_impl", "_async_evaluate_room", "_apply_passive_ventilation",
          "_house_recommendation_and_plan", "_async_finalize_cycle")


def _coordinator_functions() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in module_files("coordinator"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault(node.name, str(path))
    return found


def test_coordinator_phases_never_read_possibly_unbound_values():
    functions = _coordinator_functions()
    assert set(PHASES) <= set(functions)
    for name, path in sorted(functions.items()):
        assert check.check(path, name) == REVIEWED.get(name, set()), name
    for name in ("ventilation_threshold_decision", "house_status_fallback",
                 "floor_ventilation_decision", "build_night_strategy"):
        assert check.check(RULES, name) == set(), name


def test_status_fallback_is_bound_before_the_recommendation_may_override_it():
    source = module_source("coordinator")
    fallback = source.index("status = house_status_fallback(")
    override = source.index('status = str(intelligent_recommendation.get("status") or status)')
    assert fallback < override
