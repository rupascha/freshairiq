"""0.26.7.0 N9: test runner output and caches never reach a CLEAN release.

Finding: the previous CLEAN zip carried ``test-results/.last-run.json`` (Playwright). The build now skips such
paths and both the release-tree hygiene stage and the artifact gate reject them.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
RESIDUE = ["test-results/.last-run.json", "playwright-report/index.html", "blob-report/report.zip", ".hypothesis/x",
           "htmlcov/index.html", ".cache/x", "custom_components/freshairiq/x.tmp", "docs/a.swp", "a.rej",
           "frontend_tests/__pycache__/x.pyc"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "tools"))
    spec.loader.exec_module(module)
    return module


def _tree(tmp_path: Path) -> Path:
    for rel in [*RESIDUE, "custom_components/freshairiq/manifest.json", "tests/test_x.py"]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    return tmp_path


def test_hygiene_stage_rejects_every_residue(tmp_path):
    result, failures = _load("quality_gate").hygiene_gate(_tree(tmp_path), POLICY)
    assert result["status"] == "FAIL"
    hits = set(result["forbidden_hits"])
    for rel in RESIDUE:
        assert rel in hits or any(rel.startswith(hit + "/") for hit in hits), rel
    assert "custom_components/freshairiq/manifest.json" not in hits and "tests/test_x.py" not in hits


def test_build_skips_the_residue():
    build = _load("build_release")
    for rel in RESIDUE:
        if Path(rel).suffix in {".tmp", ".swp", ".rej"}:
            continue  # suffix rules apply to existing files only (checked by the hygiene stage above)
        assert build._excluded(build.ROOT / rel, POLICY), rel
    assert not build._excluded(build.ROOT / "custom_components/freshairiq/manifest.json", POLICY)


def test_artifact_gate_lists_the_same_paths():
    gate = _load("github_release_gate")
    assert {"test-results", "playwright-report", "blob-report", ".hypothesis", "htmlcov"} <= gate.FORBIDDEN_PARTS
    assert ".last-run.json" in gate.FORBIDDEN_NAMES and {".tmp", ".swp", ".rej"} <= gate.FORBIDDEN_SUFFIXES
