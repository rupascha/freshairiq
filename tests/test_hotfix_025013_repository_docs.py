from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]

def test_release_notes_are_not_in_repository_root():
    assert not list(ROOT.glob("RELEASE_NOTES_*.md"))

def test_current_release_notes_live_in_docs_folder():
    version = json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text())["version"]
    assert (ROOT / "docs" / "releases" / f"RELEASE_NOTES_{version}.md").is_file()

def test_readme_has_english_counterpart_and_language_switch():
    de = (ROOT / "README.md").read_text(encoding="utf-8")
    en = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    assert "[English](README_EN.md)" in de
    assert "[Deutsch](README.md)" in en
    assert "Installation via HACS" in en
    assert "Diagnostics & privacy" in en
    assert "Technical principles" in en

def test_release_tooling_uses_docs_release_folder():
    for rel in ("tools/github_release_gate.py", "tools/reliability_foundation_gate.py", "tools/bump_release_version.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "docs" in text and "releases" in text
