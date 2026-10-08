"""Every value the coordinator phases read must be bound on every path.

0.26.3.1 shipped a refactoring step that left ``status`` unbound when the
intelligent recommendation carried no status (``status = ... or status``). The
golden master could not see it because every scenario produced a status. This
static check sees all paths.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("definite_assignment_check", ROOT / "tools/definite_assignment_check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

COORD = str(ROOT / "custom_components/freshairiq/coordinator.py")
RULES = str(ROOT / "custom_components/freshairiq/house_decision.py")

# Path-insensitive analysis cannot correlate two identical guards. Each entry is
# reviewed: target_ah is written and read under the same `result.data_quality == "ok"`
# guard, and neither `result` nor its data_quality is reassigned in between.
REVIEWED = {"_async_evaluate_room": {"target_ah"}}


def test_coordinator_phases_never_read_possibly_unbound_values():
    for name in ("_async_update_data_impl", "_async_evaluate_room", "_apply_passive_ventilation",
                 "_house_recommendation_and_plan", "_async_finalize_cycle"):
        assert check.check(COORD, name) == REVIEWED.get(name, set()), name
    for name in ("ventilation_threshold_decision", "house_status_fallback",
                 "floor_ventilation_decision", "build_night_strategy"):
        assert check.check(RULES, name) == set(), name


def test_status_fallback_is_bound_before_the_recommendation_may_override_it():
    source = Path(COORD).read_text(encoding="utf-8")
    fallback = source.index("status = house_status_fallback(")
    override = source.index('status = str(intelligent_recommendation.get("status") or status)')
    assert fallback < override
