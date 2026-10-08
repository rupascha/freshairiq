from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_freshy_is_large_and_clipped_by_hero_not_shrunk():
    assert ".ai-assistant{grid-template-columns:94px" in CARD
    assert ".ai-mascot-wrap{width:88px;height:88px" in CARD
    assert "overflow:hidden;contain:paint" in CARD


# test_leaf_wings_are_compact_horizontal_and_permanent: retired in 0.26.4.1, the CSS-drawn mascot was replaced by the animated
# Freshy SVG (see test_hotfix_026401_freshy_animations_in_iq.py).

def test_continuous_ventilation_is_visually_quiet():
    assert ".ai-compact.continuous .ai-airflow,.ai-compact.continuous .ai-air-leaf{display:none!important}" in CARD
    assert ".ai-compact.continuous .ai-airflow.b{display:block!important" in CARD
    assert "faiqGentleFlow18 7.2s" in CARD


def test_wait_has_no_airflow_or_particles():
    assert ".ai-compact.wait .ai-airflow,.ai-compact.wait .ai-air-leaf" in CARD
    assert "display:none!important" in CARD


# test_pre_night_is_tired_not_asleep_and_night_has_moon: retired in 0.26.4.1, the CSS-drawn mascot was replaced by the animated
# Freshy SVG (see test_hotfix_026401_freshy_animations_in_iq.py).

def test_new_animation_loops_are_closed():
    for name in ("faiqWingFlight18", "faiqWingFlightRight18", "faiqGentleFlow18", "faiqWingGentle18", "faiqWingGentleRight18"):
        assert f"@keyframes {name}{{0%,100%" in CARD


def test_mobile_freshy_grid_is_not_overridden_by_legacy_52px_rule():
    mobile_84 = ".ai-assistant{grid-template-columns:84px minmax(0,1fr) 22px"
    legacy_52 = ".ai-assistant{grid-template-columns:52px minmax(0,1fr) 22px"
    assert CARD.count(mobile_84) >= 2
    assert legacy_52 not in CARD
