"""Long-run deterministic stability stress gate for FreshAirIQ pure logic."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
import tracemalloc
from dataclasses import asdict
from pathlib import Path
import types

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
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.recommendation import build_recommendation


def _inputs() -> list[RoomInput]:
    return [
        RoomInput(
            key=f"room_{i}", name=f"Room {i}",
            temperature=20.0 + (i % 5) * 0.7,
            humidity=54.0 + (i % 6) * 3.0,
            reference_temperature=8.0 + (i % 3),
            reference_humidity=56.0,
            volume_m3=28.0 + i * 4.0,
            contact_open=bool(i % 4 == 0),
            contact_open_seconds=420 if i % 4 == 0 else 0,
            session_active=bool(i % 4 == 0),
            session_elapsed_min=7.0 if i % 4 == 0 else 0.0,
            session_start_temp=21.2 if i % 4 == 0 else None,
            session_fresh_measurements=2 if i % 4 == 0 else 0,
        )
        for i in range(12)
    ]


def _recommendation_rooms(results: list[dict]) -> dict[str, dict]:
    return {str(r["key"]): r for r in results}


def run_stress(cycles: int) -> str:
    rooms = _inputs()
    options = dict(DEFAULT_OPTIONS)
    digest = hashlib.sha256()
    for cycle in range(cycles):
        results = [asdict(evaluate_room(room, options, bool(cycle & 1))) for room in rooms]
        recommendation = build_recommendation(
            _recommendation_rooms(results),
            options,
            threshold_ml=float(options.get("ventilation_threshold_ml", 500)),
            total_potential_ml=sum(max(0.0, float(r.get("potential_ml", 0.0) or 0.0)) for r in results),
            recommended_duration_min=8.0,
        )
        # Hash only deterministic decision fields to catch state leakage while
        # avoiding large retained collections in the stress loop itself.
        digest.update(str(recommendation.get("kind", "")).encode())
        digest.update(str(recommendation.get("room_keys", [])).encode())
        digest.update(str(results[cycle % len(results)].get("action", "")).encode())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="quality/quality_policy.json")
    parser.add_argument("--json-output", default=None)
    args = parser.parse_args()

    policy = json.loads((ROOT / args.policy).read_text(encoding="utf-8"))
    cfg = policy["stability"]
    cycles = int(cfg["stress_cycles"])
    max_retained = float(cfg["max_retained_memory_kib"])
    max_peak = float(cfg["max_peak_memory_kib"])
    max_runtime = float(cfg["max_runtime_seconds"])

    # Determinism check catches accidental module/global state contamination.
    first = run_stress(max(50, cycles // 20))
    second = run_stress(max(50, cycles // 20))
    deterministic = first == second

    gc.collect()
    tracemalloc.start()
    before_current, _ = tracemalloc.get_traced_memory()
    started = time.perf_counter()
    digest = run_stress(cycles)
    runtime = time.perf_counter() - started
    gc.collect()
    after_current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    retained_kib = max(0, after_current - before_current) / 1024.0
    peak_kib = peak / 1024.0
    failures: list[str] = []
    if not deterministic:
        failures.append("repeated stress runs produced different deterministic decisions")
    if retained_kib > max_retained:
        failures.append(f"retained memory {retained_kib:.1f} KiB > {max_retained:.1f} KiB")
    if peak_kib > max_peak:
        failures.append(f"peak memory {peak_kib:.1f} KiB > {max_peak:.1f} KiB")
    if runtime > max_runtime:
        failures.append(f"stress runtime {runtime:.2f}s > {max_runtime:.2f}s")

    payload = {
        "schema": 1,
        "version": policy["version"],
        "cycles": cycles,
        "deterministic": deterministic,
        "digest": digest,
        "runtime_seconds": runtime,
        "retained_memory_kib": retained_kib,
        "peak_memory_kib": peak_kib,
        "failures": failures,
    }
    print(
        f"Stability stress: cycles={cycles}, runtime={runtime:.2f}s, "
        f"retained={retained_kib:.1f} KiB, peak={peak_kib:.1f} KiB, "
        f"deterministic={'yes' if deterministic else 'NO'}"
    )
    if args.json_output:
        out = ROOT / args.json_output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if failures:
        print("Stability gate FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("Stability gate PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
