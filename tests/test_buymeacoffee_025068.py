from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"

def test_buy_me_a_coffee_funding_and_readme():
    funding = (ROOT / ".github" / "FUNDING.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "buy_me_a_coffee: freshairiq" in funding
    assert "https://buymeacoffee.com/freshairiq" in readme
    assert "support continued development voluntarily" in readme
