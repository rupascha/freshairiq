from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_github_hacs_source_gate_passes_current_release():
    result = subprocess.run(
        [sys.executable, "tools/github_release_gate.py", "--source", "."],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "GitHub/HACS release gate: PASS" in result.stdout


def test_release_builder_invokes_source_and_zip_gates():
    source = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
    assert '"tools/github_release_gate.py"), "--source"' in source
    assert '"tools/github_release_gate.py"), "--zip"' in source


def test_github_workflows_enforce_release_gate():
    for rel in (".github/workflows/validate.yml", ".github/workflows/release.yml", ".github/workflows/quality.yml"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "tools/github_release_gate.py" in text


def test_github_hacs_gate_requires_complete_local_brand_set():
    source = (ROOT / "tools/github_release_gate.py").read_text(encoding="utf-8")
    for name in (
        "icon.png", "icon@2x.png", "dark_icon.png", "dark_icon@2x.png",
        "logo.png", "logo@2x.png", "dark_logo.png", "dark_logo@2x.png",
    ):
        assert name in source
    assert "missing required local brand asset" in source
