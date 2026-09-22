"""FreshAirIQ Reliability Foundation v1 gate.

Fast, deterministic pre-release checks for contracts that must remain stable as
FreshAirIQ grows. This gate deliberately checks behavior/release invariants,
not implementation line numbers.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
POLICY = ROOT / "quality/quality_policy.json"


def _version() -> str:
    return json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"]


def _check_version_contract(version: str) -> list[str]:
    failures: list[str] = []
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy.get("version") != version:
        failures.append("quality policy version differs from manifest")
    const = (COMP / "const.py").read_text(encoding="utf-8")
    if not re.search(rf'^VERSION\s*=\s*[\"\']{re.escape(version)}[\"\']', const, re.M):
        failures.append("const.py VERSION differs from manifest")
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        text = (COMP / "frontend" / name).read_text(encoding="utf-8")
        if f'const FAIQ_VERSION = "{version}";' not in text:
            failures.append(f"frontend version differs: {name}")
    package = ROOT / "package.json"
    if package.exists() and json.loads(package.read_text(encoding="utf-8")).get("version") != version:
        failures.append("package.json version differs from manifest")
    if not (ROOT / f"RELEASE_NOTES_{version}.md").exists():
        failures.append(f"release notes missing for {version}")
    return failures


def _run_golden_scenarios() -> int:
    return subprocess.run(
        [sys.executable, "tools/golden_scenario_replay.py"],
        cwd=ROOT,
    ).returncode


def _run_migration_contracts() -> int:
    return subprocess.run(
        [sys.executable, "tools/migration_contract_replay.py"],
        cwd=ROOT,
    ).returncode


def _run_pytest() -> int:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=ROOT,
    ).returncode


def main() -> int:
    version = _version()
    failures = _check_version_contract(version)
    if failures:
        print("Reliability Foundation: FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    if _run_golden_scenarios():
        print("Reliability Foundation: FAIL - golden scenario replay")
        return 1
    if _run_migration_contracts():
        print("Reliability Foundation: FAIL - migration contract replay")
        return 1
    if _run_pytest():
        print("Reliability Foundation: FAIL - behavioral regression suite")
        return 1
    print(f"Reliability Foundation: PASS - {version}")
    print("Golden scenario replay: PASS")
    print("Migration contract replay: PASS")
    print("Behavioral regression suite: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
