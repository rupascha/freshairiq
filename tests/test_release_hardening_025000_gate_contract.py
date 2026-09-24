"""Release-gate contracts for the FreshAirIQ 0.25.0.7 hardening milestone."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_release_version_is_consistent_across_runtime_and_frontend():
    version = "0.25.0.61"
    assert f'VERSION = "{version}"' in (COMP / "const.py").read_text(encoding="utf-8")
    assert json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"] == version
    for filename in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert f'const FAIQ_VERSION = "{version}";' in (COMP / "frontend" / filename).read_text(encoding="utf-8")
    assert f"Current release: {version}" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert (ROOT / f"RELEASE_NOTES_{version}.md").is_file()


def test_v1_coverage_policy_is_a_hard_gate_not_a_reporting_hint():
    coverage_cfg = (ROOT / ".coveragerc-pure").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    reporter = (ROOT / "tools" / "report_ha_coverage.py").read_text(encoding="utf-8")

    assert "fail_under = 100" in coverage_cfg
    assert "--cov-fail-under=100" in workflow
    assert "--cov-append" in workflow
    assert "--min-total 99" in workflow
    assert "--min-module 98" in workflow
    assert "--config-flow 100" in workflow
    assert 'default=99.0' in reporter
    assert 'default=98.0' in reporter
    assert 'default=100.0' in reporter
    assert "missing_modules.append(module)" in reporter
    assert "return 1" in reporter


def test_v1_quality_gate_document_keeps_unverified_real_ha_work_open():
    quality = (ROOT / "QUALITY_GATES_1.0.md").read_text(encoding="utf-8")
    notes = (ROOT / "RELEASE_NOTES_0.25.0.7.md").read_text(encoding="utf-8")

    assert "Pure Logic: 100 %" in quality
    assert "mindestens **99 %**" in quality
    assert "mindestens **98 %**" in quality
    assert "`config_flow.py` **100 %**" in quality
    assert "Reale HA-Runtime-Coverage bleibt offen" in quality
    assert "Noch offene v1-Gates" in notes
    assert "kein** 1.0-Release" in notes
