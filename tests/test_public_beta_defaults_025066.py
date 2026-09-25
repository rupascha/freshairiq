"""Regression contracts for v0.25.0.76 public-beta defaults and README assets."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_public_beta_diagnostics_defaults():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert '"diagnostics_reporting_mode": "daily"' in const
    assert '"diagnostics_include_client_context": True' in const
    assert 'current.get("diagnostics_reporting_mode", "daily")' in flow
    assert 'current.get("diagnostics_include_client_context", True)' in flow


def test_public_beta_readme_and_screenshots_are_packaged():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "FreshAirIQ · Public Beta" in readme
    assert "Täglich nachts" in readme
    assert "Geräte-/Browser-Kontext" in readme
    screenshots = ROOT / "docs" / "screenshots"
    expected = {
        "01-house-ventilation.jpeg", "02-room-overview.jpeg",
        "03-intelligence-overview.jpeg", "04-model-quality.jpeg",
        "05-learning-home.jpeg", "06-learning-forecast.jpeg",
        "07-water-balance.jpeg", "08-mould-iq.jpeg",
    }
    assert expected <= {p.name for p in screenshots.iterdir() if p.is_file()}


def test_release_versions_are_aligned():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "quality" / "quality_policy.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == policy["version"] == package["version"] == "0.25.0.76"
    assert 'VERSION = "0.25.0.76"' in (COMP / "const.py").read_text(encoding="utf-8")
