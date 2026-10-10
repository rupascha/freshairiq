from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_primary_night_recommendation_precedes_generic_ventilate_animation():
    assert 'const nightRecommendation = !active.length' in CARD
    assert 'Boolean(nightStrategy.primary || st.night_strategy_primary)' in CARD
    # 0.26.4.6 (GitHub #14) inserts the canonical "wait" between night and recommend;
    # night must still win over the generic ventilate animation.
    night = CARD.index(': nightRecommendation ? "night"')
    assert night < CARD.index(': houseWaits ? "wait"') < CARD.index(': vent.length || status === "ventilate" ? "recommend"')


def test_running_ventilation_keeps_live_animation_priority():
    assert 'const kind = active.length && passiveOpenMonitor ? "continuous"\n            : active.length ? "live"' in CARD
    assert 'const nightRecommendation = !active.length' in CARD


def test_night_visual_is_distinct_and_has_no_normal_airflow():
    assert '.ai-compact.night .ai-moon{display:block}' in CARD
    assert '.ai-compact.night .ai-airflow,.ai-compact.night .ai-air-leaf{display:none!important}' in CARD
    assert 'animation:faiqSleep 4.2s ease-in-out infinite' in CARD
