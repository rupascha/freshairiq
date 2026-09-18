"""FreshAirIQ deterministic micro-performance gate.

The benchmark normalizes each workload against an in-process control loop so the
result is much less sensitive to runner speed. CI compares normalized ratios to
an accepted baseline and fails only on meaningful regressions.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
import types
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load pure FreshAirIQ modules without executing integration __init__.py, which
# requires a full Home Assistant runtime. This mirrors tests/conftest.py.
CUSTOM = ROOT / "custom_components"
PKG = CUSTOM / "freshairiq"
if "custom_components" not in sys.modules:
    custom = types.ModuleType("custom_components")
    custom.__path__ = [str(CUSTOM)]
    sys.modules["custom_components"] = custom
if "custom_components.freshairiq" not in sys.modules:
    freshairiq = types.ModuleType("custom_components.freshairiq")
    freshairiq.__path__ = [str(PKG)]
    sys.modules["custom_components.freshairiq"] = freshairiq

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.decision import _simulate_ventilation
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.recommendation import build_recommendation


def _control(iterations: int) -> int:
    value = 0
    for i in range(iterations):
        value = (value + ((i * 17) ^ (i >> 2))) & 0xFFFFFFFF
    return value


def _room_input(index: int = 0) -> RoomInput:
    return RoomInput(
        key=f"room_{index}",
        name=f"Room {index}",
        temperature=21.5 + (index % 3) * 0.3,
        humidity=63.0 + (index % 4),
        reference_temperature=12.0,
        reference_humidity=58.0,
        volume_m3=45.0 + index * 2.0,
        contact_open=False,
        contact_open_seconds=0,
    )


def _room_payload(index: int = 0) -> dict:
    return {
        "key": f"room_{index}",
        "name": f"Room {index}",
        "calculation_enabled": True,
        "data_quality": "ok",
        "active": False,
        "action": "Ventilate",
        "humidity": 64 + (index % 4),
        "surface_rh": 70,
        "mould_level": "Low",
        "co2": 700,
        "potential_ml": 140 + index * 5,
        "delta_g_m3": 2.6,
        "airflow_factor": 1.0,
        "temperature": 21.5,
        "reference_temperature": 12.0,
        "reference_humidity": 58.0,
        "absolute_humidity": 11.7,
        "reference_absolute_humidity": 6.2,
        "volume_m3": 50.0,
        "temp_next_5_min_c": -0.2,
        "next_5_min_cost": 0.01,
        "moisture_effect_next_5_min_ml": 45,
        "forecast_horizon_min": 15,
        "forecast_moisture_effect_ml": 120,
        "forecast_temperature_change_c": -0.5,
        "forecast_cost": 0.02,
        "humidity_trend_pct_h": 0.0,
        "humidity_high_duration_min": 20,
    }


def _benchmark_evaluate(iterations: int) -> None:
    rooms = [_room_input(i) for i in range(12)]
    options = dict(DEFAULT_OPTIONS)
    for i in range(iterations):
        evaluate_room(rooms[i % len(rooms)], options, bool(i & 1))


def _benchmark_recommendation(iterations: int) -> None:
    rooms = {f"room_{i}": _room_payload(i) for i in range(12)}
    options = {
        "start_rh": 62.0,
        "high_rh": 68.0,
        "mould_warn_surface_rh": 80.0,
        "mould_critical_surface_rh": 90.0,
        "co2_warn": 1000.0,
        "co2_critical": 1400.0,
        "cross_ventilation_pairs": "room_0+room_1",
    }
    for _ in range(iterations):
        build_recommendation(
            rooms,
            options,
            threshold_ml=500,
            total_potential_ml=1800,
            recommended_duration_min=8,
        )


def _benchmark_simulation(iterations: int) -> None:
    selected = [_room_payload(i) for i in range(6)]
    for _ in range(iterations):
        _simulate_ventilation(selected, 10.0, source_ah=6.2, source_temp_c=12.0)


BENCHMARKS: dict[str, tuple[int, Callable[[int], None]]] = {
    "evaluate_room": (1800, _benchmark_evaluate),
    "recommendation_12_rooms": (650, _benchmark_recommendation),
    "simulate_6_rooms": (1400, _benchmark_simulation),
}


def _median_ns(fn: Callable[[int], None], iterations: int, rounds: int) -> float:
    samples: list[int] = []
    fn(max(1, iterations // 10))
    for _ in range(rounds):
        started = time.perf_counter_ns()
        fn(iterations)
        samples.append(time.perf_counter_ns() - started)
    return float(statistics.median(samples))


def _control_median_ns(iterations: int, rounds: int) -> float:
    samples: list[int] = []
    _control(max(1, iterations // 10))
    for _ in range(rounds):
        started = time.perf_counter_ns()
        _control(iterations)
        samples.append(time.perf_counter_ns() - started)
    return float(statistics.median(samples))


def measure(rounds: int) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    for name, (iterations, fn) in BENCHMARKS.items():
        workload_ns = _median_ns(fn, iterations, rounds)
        # The control loop intentionally uses more iterations so its duration is
        # large enough to be stable at timer resolution.
        control_iterations = iterations * 12
        control_ns = _control_median_ns(control_iterations, rounds)
        ratio = workload_ns / control_ns if control_ns > 0 else float("inf")
        results[name] = {
            "ratio": ratio,
            "us_per_call": workload_ns / iterations / 1000.0,
            "workload_ms": workload_ns / 1_000_000.0,
            "control_ms": control_ns / 1_000_000.0,
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="quality/quality_policy.json")
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--json-output", default=None)
    args = parser.parse_args()

    policy = json.loads((ROOT / args.policy).read_text(encoding="utf-8"))
    perf = policy["performance"]
    baseline_path = ROOT / (args.baseline or perf["baseline_file"])
    rounds = int(perf.get("rounds", 7))
    warning_pct = float(perf["warning_regression_percent"])
    failure_pct = float(perf["failure_regression_percent"])

    measured = measure(rounds)
    payload = {
        "schema": 1,
        "version": policy["version"],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "benchmarks": measured,
    }

    if args.write_baseline:
        baseline = {
            "schema": 1,
            "version": policy["version"],
            "python": payload["python"],
            "description": "Normalized ratios captured by tools/performance_gate.py.",
            "benchmarks": {name: {"ratio": row["ratio"]} for name, row in measured.items()},
        }
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote performance baseline: {baseline_path}")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_rows = baseline.get("benchmarks", {})
    failures: list[str] = []
    warnings: list[str] = []
    for name, row in measured.items():
        base_ratio = float(baseline_rows.get(name, {}).get("ratio", 0.0))
        if base_ratio <= 0:
            failures.append(f"{name}: missing/invalid baseline")
            continue
        regression_pct = (row["ratio"] / base_ratio - 1.0) * 100.0
        row["baseline_ratio"] = base_ratio
        row["regression_percent"] = regression_pct
        state = "PASS"
        if regression_pct > failure_pct:
            state = "FAIL"
            failures.append(f"{name}: {regression_pct:+.1f}% > {failure_pct:.1f}%")
        elif regression_pct > warning_pct:
            state = "WARN"
            warnings.append(f"{name}: {regression_pct:+.1f}% > {warning_pct:.1f}%")
        row["status"] = state
        print(
            f"{name:24s} {state:4s}  {row['us_per_call']:8.2f} us/call  "
            f"normalized={row['ratio']:.4f}  regression={regression_pct:+.1f}%"
        )

    payload["warnings"] = warnings
    payload["failures"] = failures
    if args.json_output:
        out = ROOT / args.json_output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if warnings:
        print("Performance warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if failures:
        print("Performance gate FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("Performance gate PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
