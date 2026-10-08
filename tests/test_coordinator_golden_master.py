"""0.26.3.1: the coordinator must reproduce its recorded behaviour exactly.

The golden master runs the real update cycle over six scripted households
(117 cycles: airing, night, sensor drop-outs, tilt windows, summer cooling,
structure-only and empty homes) with a frozen clock and no network. Any change of
an output value or of the persisted learning state fails this test. Intentional
behaviour changes re-record the reference with
``python tools/coordinator_golden.py --record`` and say so in the changelog.
It also asserts that no installation contacts the diagnostics hub without consent.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_coordinator_matches_golden_master_and_stays_offline_without_consent():
    result = subprocess.run(
        [sys.executable, "tools/coordinator_golden.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "golden master OK" in result.stdout


def test_update_cycle_is_split_into_named_phases():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    for phase in ("_async_evaluate_room", "_apply_passive_ventilation", "_house_recommendation_and_plan",
                  "_async_finalize_cycle"):
        assert f"def {phase}(" in coordinator
    # Pure decision rules live in house_decision.py and are boundary-tested there.
    rules = (ROOT / "custom_components/freshairiq/house_decision.py").read_text(encoding="utf-8")
    for rule in ("ventilation_threshold_decision", "floor_ventilation_decision", "build_night_strategy"):
        assert f"def {rule}(" in rules and f"{rule}(" in coordinator
    assert "homeassistant" not in rules
    import ast
    tree = ast.parse(coordinator)
    impl = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "_async_update_data_impl")
    # Was 3,004 lines in 0.26.3.0. Keep it from silently growing back.
    assert impl.end_lineno - impl.lineno + 1 < 1000
