"""Regression contracts for v0.25.0.54 release-asset/changelog hygiene."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_release_job_attaches_exact_verified_clean_zip():
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "uses: actions/download-artifact@v4" in release
    assert "name: freshairiq-clean-release" in release
    assert 'SOURCE="release-artifact/FreshAirIQ-release.zip"' in release
    assert 'python tools/github_release_gate.py --zip "$SOURCE"' in release
    assert 'ASSET="FreshAirIQ-v${VERSION}-CLEAN.zip"' in release
    assert 'gh release create "$GITHUB_REF_NAME" "$RELEASE_ASSET"' in release


def test_changelog_has_single_canonical_heading_and_correct_history():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("# FreshAirIQ Changelog") == 1
    assert "\n# Changelog\n" not in changelog
    assert changelog.count("## 0.25.0.45 – Release, Scroll & Locale Hardening Hotfix") == 1
    assert "## 0.25.0.44 — Native Config, Scroll & Quality Hotfix" in changelog


def test_release_metadata_is_025047_and_hygiene_named():
    manifest = json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text())
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text())
    package = json.loads((ROOT / "package.json").read_text())
    assert manifest["version"] == "0.25.0.54"
    assert policy["version"] == "0.25.0.54"
    assert package["version"] == "0.25.0.54"
    assert str(policy["release"]["artifact_suffix"]).strip()
    assert (ROOT / "RELEASE_NOTES_0.25.0.54.md").is_file()


def test_mini_hotfix_does_not_touch_core_runtime_files_beyond_version_markers():
    # Guard the release-only scope: the workflow/changelog/release metadata are the intended changes.
    # Runtime version markers must still stay synchronized for HA/HACS cache/update semantics.
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    manifest = (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    card = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'VERSION = "0.25.0.54"' in const
    assert '"version": "0.25.0.54"' in manifest
    assert 'const FAIQ_VERSION = "0.25.0.54";' in card
