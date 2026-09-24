"""Contracts for the 0.25.0.65 Continuous Quality System."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quality_policy_covers_all_five_quality_axes():
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    assert policy["version"] == "0.25.0.65"
    for key in ("correctness", "robustness", "stability", "performance", "compatibility", "release"):
        assert key in policy
    assert policy["correctness"]["pure_logic_coverage_percent"] == 100.0
    assert policy["performance"]["failure_regression_percent"] > policy["performance"]["warning_regression_percent"]
    assert policy["stability"]["stress_cycles"] >= 1000


def test_performance_baseline_tracks_all_representative_core_workloads():
    baseline = json.loads((ROOT / "quality/performance_baseline.json").read_text(encoding="utf-8"))
    assert baseline["version"] == "0.25.0.65"
    assert set(baseline["benchmarks"]) == {
        "evaluate_room",
        "recommendation_12_rooms",
        "simulate_6_rooms",
    }
    assert all(float(row["ratio"]) > 0 for row in baseline["benchmarks"].values())


def test_quality_orchestrator_and_clean_release_builder_exist():
    gate = (ROOT / "tools/quality_gate.py").read_text(encoding="utf-8")
    builder = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
    assert "correctness + pure-logic 100% coverage" in gate
    assert "robustness fault-injection suite" in gate
    assert "stability stress" in gate
    assert "performance regression" in gate
    assert "release-hygiene" in gate
    assert "Release build aborted: quality gate failed." in builder
    assert "zipfile.ZIP_DEFLATED" in builder


def test_ci_enforces_ha_python_frontend_hacs_and_clean_release_matrix():
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    for job in (
        "core-quality:",
        "python-compatibility:",
        "ha-compatibility:",
        "ha-runtime:",
        "frontend-compatibility:",
        "hacs:",
        "release-dry-run:",
        "ha-edge-watch:",
    ):
        assert job in workflow
    assert '["3.13", "3.14"]' in workflow
    assert '>=2026.8,<2026.9' in workflow
    assert '>=2026.9,<2026.10' in workflow
    assert "chromium webkit firefox" in workflow
    assert "tools/build_release.py --skip-quality" in workflow


def test_frontend_browser_smoke_covers_phone_tablet_android_and_desktop():
    spec = (ROOT / "frontend_tests/freshairiq.spec.mjs").read_text(encoding="utf-8")
    for label in ("iPhone", "iPad", "Android", "Desktop"):
        assert label in spec
    for drilldown in (
        "learning:home",
        "learning:forecast",
        "learning:habits",
        "learning:longterm",
        "learning:quality",
    ):
        assert drilldown in spec
    assert "50-room dashboard smoke render remains responsive" in spec


def test_release_policy_forbids_cache_and_development_artifacts():
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))["release"]
    assert "__pycache__" in policy["forbidden_path_parts"]
    assert ".pytest_cache" in policy["forbidden_path_parts"]
    assert "node_modules" in policy["forbidden_path_parts"]
    assert ".pyc" in policy["forbidden_suffixes"]
    assert ".coverage" in policy["forbidden_file_names"]
