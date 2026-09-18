"""Validate FreshAirIQ coverage from a real Home Assistant coverage.py JSON report.

The v1 release standard is intentionally stricter than Home Assistant's >95%
quality-scale rule: every Python integration module must be at least 98%, the
combined integration must be at least 99%, and config_flow.py must be 100%.
The project target remains 100% wherever the runtime makes the path testable.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

INTEGRATION_ROOT = Path("custom_components/freshairiq")
CONFIG_FLOW = INTEGRATION_ROOT / "config_flow.py"


def _percent(summary: dict) -> float:
    value = summary.get("percent_covered")
    if value is not None:
        return float(value)
    covered = float(summary.get("covered_lines", 0))
    total = float(summary.get("num_statements", 0))
    return 100.0 if total == 0 else covered / total * 100.0


def _source_modules() -> list[str]:
    return sorted(
        path.as_posix()
        for path in INTEGRATION_ROOT.glob("*.py")
        if path.name != "__pycache__"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="ha_tests/coverage-ha.json")
    parser.add_argument("--min-total", type=float, default=99.0)
    parser.add_argument("--min-module", type=float, default=98.0)
    parser.add_argument("--config-flow", type=float, default=100.0)
    args = parser.parse_args()

    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    files = payload.get("files", {})
    total = _percent(payload["totals"])

    module_rows: list[tuple[str, float]] = []
    missing_modules: list[str] = []
    for module in _source_modules():
        row = files.get(module)
        if row is None:
            # A release report must never look healthy by silently omitting a
            # module that coverage.py did not execute/measure.
            missing_modules.append(module)
            module_rows.append((module, 0.0))
        else:
            module_rows.append((module, _percent(row.get("summary", {}))))

    config_key = CONFIG_FLOW.as_posix()
    config_pct = dict(module_rows).get(config_key, 0.0)
    below_module_floor = [
        (name, pct) for name, pct in module_rows if pct + 1e-9 < args.min_module
    ]

    failures: list[str] = []
    if total + 1e-9 < args.min_total:
        failures.append(f"combined coverage {total:.2f}% < {args.min_total:.2f}%")
    if config_pct + 1e-9 < args.config_flow:
        failures.append(
            f"config_flow.py coverage {config_pct:.2f}% < {args.config_flow:.2f}%"
        )
    if below_module_floor:
        failures.append(
            f"{len(below_module_floor)} module(s) below {args.min_module:.2f}%"
        )
    if missing_modules:
        failures.append(f"{len(missing_modules)} integration module(s) missing from report")

    print(f"FreshAirIQ combined HA coverage: {total:.2f}%")
    print(f"config_flow.py coverage: {config_pct:.2f}%")
    print(f"Per-module release floor: {args.min_module:.2f}%")
    print(f"Project target: 100.00% where testable")
    if below_module_floor:
        print("Modules below release floor:")
        for name, pct in below_module_floor:
            print(f"  - {name}: {pct:.2f}%")
    if missing_modules:
        print("Missing modules:")
        for name in missing_modules:
            print(f"  - {name}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write("## FreshAirIQ canonical HA coverage gate\n\n")
            handle.write(f"- Combined integration: **{total:.2f}%** (required ≥ {args.min_total:.2f}%)\n")
            handle.write(f"- `config_flow.py`: **{config_pct:.2f}%** (required {args.config_flow:.2f}%)\n")
            handle.write(f"- Every Python integration module: **≥ {args.min_module:.2f}%**\n")
            handle.write("- FreshAirIQ target: **100% wherever the code path is testable**\n")
            if below_module_floor:
                handle.write("\n### Modules below the v1 floor\n")
                for name, pct in below_module_floor:
                    handle.write(f"- `{name}`: **{pct:.2f}%**\n")
            if missing_modules:
                handle.write("\n### Missing from coverage report\n")
                for name in missing_modules:
                    handle.write(f"- `{name}`\n")
            if failures:
                handle.write("\n**Release coverage gate: FAILED**\n")
            else:
                handle.write("\n**Release coverage gate: PASSED**\n")

    if failures:
        print("Coverage gate FAILED: " + "; ".join(failures))
        return 1
    print("Coverage gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
