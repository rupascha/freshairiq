from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")

def test_android_details_scroll_keeps_vertical_touch_chain():
    assert "overflow:hidden}.dialog{" in JS
    assert "box-shadow:0 30px 80px rgba(0,0,0,.55)}.dialog-head{" in JS
    assert ".dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto" in JS
    assert "-webkit-overflow-scrolling:touch" in JS

def test_delayed_learning_is_explained_to_user():
    text = "Die Lern-Auswertung kann deshalb verzögert erscheinen."
    assert text in JS
    assert text in COORD
