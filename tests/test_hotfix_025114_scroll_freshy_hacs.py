from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_root_overlays_capture_and_restore_dashboard_viewport():
    assert CARD.count("this._captureOverlayViewport()") >= 5
    assert "else { if (!this._dialogOpen) this._captureOverlayViewport(); this._resetInfoNavigation(); }" in CARD
    assert "if (!this._dialogOpen) this._restoreOverlayViewport();" in CARD
    assert "this._render(); this._restoreOverlayViewport();" in CARD

def test_live_freshy_has_no_external_wind_stripes():
    assert ".ai-compact.live .ai-wind{display:none}" in CARD
    assert "repeating-linear-gradient(to bottom" not in CARD
    assert "@keyframes faiqWindTrail" not in CARD

def test_hacs_readme_is_english_with_german_link_and_freshy_screenshot():
    readme=(ROOT / "README.md").read_text(encoding="utf-8")
    german=(ROOT / "README_DE.md").read_text(encoding="utf-8")
    assert "[Deutsch](README_DE.md) · **English**" in readme
    assert "Your home can tell you" in readme
    assert "Dein Zuhause kann dir sagen" in german
    assert "docs/screenshots/00-freshy-dashboard.jpeg" in readme
    assert (ROOT / "docs/screenshots/00-freshy-dashboard.jpeg").is_file()
