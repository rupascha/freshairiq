"""Contracts for the real-HA coverage measurement pipeline."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "freshairiq"


def _complete_report(percent: float = 100.0) -> dict:
    files = {}
    for module in INTEGRATION.glob("*.py"):
        files[module.relative_to(ROOT).as_posix()] = {
            "summary": {
                "covered_lines": 100,
                "num_statements": 100,
                "percent_covered": percent,
            }
        }
    return {
        "totals": {
            "covered_lines": 100,
            "num_statements": 100,
            "percent_covered": percent,
        },
        "files": files,
    }


def test_ha_runtime_ci_persists_machine_readable_coverage() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert "--cov-report=json:ha_tests/coverage-ha.json" in workflow
    assert "python tools/report_ha_coverage.py ha_tests/coverage-ha.json" in workflow
    assert "--min-total 99" in workflow
    assert "--min-module 98" in workflow
    assert "--config-flow 100" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "freshairiq-ha-runtime-coverage" in workflow


def test_coverage_reporter_accepts_complete_100_percent_report(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(_complete_report()), encoding="utf-8")
    completed = subprocess.run(
        ["python", str(ROOT / "tools/report_ha_coverage.py"), str(report)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "FreshAirIQ combined HA coverage: 100.00%" in completed.stdout
    assert "config_flow.py coverage: 100.00%" in completed.stdout
    assert "Coverage gate PASSED" in completed.stdout


def test_coverage_reporter_rejects_omitted_integration_module(tmp_path: Path) -> None:
    payload = _complete_report()
    payload["files"].pop("custom_components/freshairiq/coordinator.py")
    report = tmp_path / "coverage-missing.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    completed = subprocess.run(
        ["python", str(ROOT / "tools/report_ha_coverage.py"), str(report)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "coordinator.py" in completed.stdout
    assert "Coverage gate FAILED" in completed.stdout
