"""FreshAirIQ Continuous Quality System orchestrator.

This is the single local/CI entry point for correctness, robustness, stability,
compatibility prerequisites, performance and release hygiene.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]


def _run(name: str, command: list[str], *, env: dict[str, str] | None = None) -> dict:
    print(f"\n=== {name} ===")
    print("$", " ".join(command))
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, env=env or os.environ.copy(), text=True)
    elapsed = time.perf_counter() - started
    status = "PASS" if proc.returncode == 0 else "FAIL"
    print(f"[{status}] {name} ({elapsed:.2f}s)")
    return {"name": name, "status": status, "returncode": proc.returncode, "seconds": elapsed}


def _iter_python_files(base: Path) -> Iterable[Path]:
    for path in base.rglob("*.py"):
        if any(part in {"__pycache__", ".venv", "node_modules"} for part in path.parts):
            continue
        yield path


def static_gate(policy: dict) -> tuple[dict, list[str]]:
    failures: list[str] = []
    version = str(policy["version"])
    manifest_path = ROOT / "custom_components/freshairiq/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != version:
        failures.append(f"manifest version {manifest.get('version')!r} != policy {version!r}")

    const_text = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*[\"\']([^\"\']+)[\"\']', const_text, re.M)
    if not match or match.group(1) != version:
        failures.append("const.py VERSION is not consistent with quality policy")

    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        text = (ROOT / "custom_components/freshairiq/frontend" / name).read_text(encoding="utf-8")
        match = re.search(r'const FAIQ_VERSION\s*=\s*"([^"]+)"', text)
        if not match or match.group(1) != version:
            failures.append(f"{name} FAIQ_VERSION is not {version}")

    json_count = 0
    for path in (ROOT / "custom_components/freshairiq").rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            json_count += 1
        except Exception as exc:  # pragma: no cover - release guard
            failures.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")

    py_count = 0
    for base in (ROOT / "custom_components/freshairiq", ROOT / "tools"):
        for path in _iter_python_files(base):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                py_count += 1
            except SyntaxError as exc:  # pragma: no cover - release guard
                failures.append(f"Python syntax {path.relative_to(ROOT)}: {exc}")

    node_checks: list[dict] = []
    node = shutil.which("node")
    if node:
        for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
            row = _run(f"frontend syntax: {name}", [node, "--check", f"custom_components/freshairiq/frontend/{name}"])
            node_checks.append(row)
            if row["returncode"] != 0:
                failures.append(f"JavaScript syntax failed: {name}")
    else:
        failures.append("node executable missing; frontend syntax gate cannot run")

    result = {
        "name": "static-and-version",
        "status": "PASS" if not failures else "FAIL",
        "python_files": py_count,
        "json_files": json_count,
        "node_checks": node_checks,
    }
    return result, failures


def hygiene_gate(tree: Path, policy: dict) -> tuple[dict, list[str]]:
    release = policy["release"]
    forbidden_parts = set(release["forbidden_path_parts"])
    forbidden_suffixes = tuple(release["forbidden_suffixes"])
    forbidden_names = set(release["forbidden_file_names"])
    hits: list[str] = []
    for path in tree.rglob("*"):
        rel = path.relative_to(tree)
        if any(part in forbidden_parts for part in rel.parts):
            hits.append(rel.as_posix())
            continue
        if path.is_file() and (path.name in forbidden_names or path.suffix in forbidden_suffixes):
            hits.append(rel.as_posix())
    hits = sorted(set(hits))
    return {
        "name": "release-hygiene",
        "status": "PASS" if not hits else "FAIL",
        "forbidden_hits": hits,
    }, [f"forbidden release artifact: {hit}" for hit in hits]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="quality/quality_policy.json")
    parser.add_argument("--profile", choices=("local", "ci", "hygiene"), default="local")
    parser.add_argument("--release-tree", default=None)
    parser.add_argument("--report", default="quality_reports/quality-report.json")
    args = parser.parse_args()

    policy = json.loads((ROOT / args.policy).read_text(encoding="utf-8"))
    results: list[dict] = []
    failures: list[str] = []

    tree = Path(args.release_tree).resolve() if args.release_tree else ROOT
    if args.profile == "hygiene":
        hygiene, hygiene_failures = hygiene_gate(tree, policy)
        results.append(hygiene)
        failures.extend(hygiene_failures)
        print(f"Release hygiene: {hygiene['status']} ({len(hygiene['forbidden_hits'])} forbidden artifacts)")
    else:
        # Working trees naturally accumulate pytest/coverage/bytecode artifacts.
        # The strict hygiene gate belongs to the staged release produced by
        # build_release.py, which excludes these files and then scans the exact
        # bytes that will be zipped.
        static, static_failures = static_gate(policy)
        results.append(static)
        failures.extend(static_failures)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        report_dir = ROOT / "quality_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        env["COVERAGE_FILE"] = str(report_dir / ".coverage")

        correctness = _run(
            "correctness + pure-logic 100% coverage",
            [
                sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests",
                "--cov=custom_components.freshairiq", "--cov-config=.coveragerc-pure",
                "--cov-report=term-missing", f"--cov-fail-under={policy['correctness']['pure_logic_coverage_percent']}",
            ],
            env=env,
        )
        results.append(correctness)
        if correctness["returncode"]:
            failures.append("correctness / pure-logic coverage gate failed")

        robustness_files = list(policy["robustness"]["required_test_files"])
        robustness = _run(
            "robustness fault-injection suite",
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *robustness_files],
            env=env,
        )
        results.append(robustness)
        if robustness["returncode"]:
            failures.append("robustness gate failed")

        stability = _run(
            "stability stress",
            [sys.executable, "tools/stability_gate.py", "--json-output", "quality_reports/stability.json"],
            env=env,
        )
        results.append(stability)
        if stability["returncode"]:
            failures.append("stability gate failed")

        performance = _run(
            "performance regression",
            [sys.executable, "tools/performance_gate.py", "--json-output", "quality_reports/performance.json"],
            env=env,
        )
        results.append(performance)
        if performance["returncode"]:
            failures.append("performance gate failed")

        # Full Home Assistant lifecycle tests are mandatory in CI. The local
        # profile intentionally does not pretend to validate HA if the runtime
        # is not installed; GitHub Actions provides the canonical environment.
        if args.profile == "ci":
            try:
                import homeassistant  # noqa: F401
            except Exception:
                failures.append("CI profile requires an installed Home Assistant runtime")
                results.append({"name": "home-assistant-runtime", "status": "FAIL", "reason": "homeassistant import missing"})
            else:
                ha = _run(
                    "Home Assistant lifecycle/config-flow",
                    [sys.executable, "-m", "pytest", "-c", "ha_tests/pytest.ini", "-q", "-p", "no:cacheprovider", "ha_tests"],
                    env=env,
                )
                results.append(ha)
                if ha["returncode"]:
                    failures.append("Home Assistant runtime gate failed")

    payload = {
        "schema": 1,
        "name": policy["name"],
        "version": policy["version"],
        "profile": args.profile,
        "status": "PASS" if not failures else "FAIL",
        "results": results,
        "failures": failures,
    }
    report = ROOT / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("\n========================================")
    print(f"FreshAirIQ Continuous Quality: {payload['status']}")
    for row in results:
        print(f"  {row['status']:4s}  {row['name']}")
    if failures:
        print("Failures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
