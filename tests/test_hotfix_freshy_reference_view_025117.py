from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

# test_freshy_uses_three_quarter_angle_layer_and_permanent_wing: retired in 0.26.4.1, the CSS-drawn mascot was replaced by the animated
# Freshy SVG (see test_hotfix_026401_freshy_animations_in_iq.py).

def test_freshy_animation_stage_remains_clipped():
    assert '.ai-mascot-wrap{position:relative;width:62px;height:62px;overflow:hidden' in CARD
    assert 'contain:paint' in CARD

def test_freshy_wing_loops_are_closed():
    assert '@keyframes faiqWingFlight{0%,100%' in CARD
    assert '@keyframes faiqWingGentle{0%,100%' in CARD
