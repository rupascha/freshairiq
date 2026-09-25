from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"

def test_buy_me_a_coffee_funding_and_readme():
    funding = (ROOT / ".github" / "FUNDING.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "buy_me_a_coffee: freshairiq" in funding
    assert "https://buymeacoffee.com/freshairiq" in readme
    assert "freiwillig unterstützen" in readme

def test_025068_versions_aligned():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "quality" / "quality_policy.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == policy["version"] == package["version"] == "0.25.0.70"
    assert 'VERSION = "0.25.0.70"' in (COMP / "const.py").read_text(encoding="utf-8")
