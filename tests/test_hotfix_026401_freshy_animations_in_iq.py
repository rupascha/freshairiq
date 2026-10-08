"""0.26.4.1: the 0.26.4 Freshy dashboard was withdrawn at the user's request; the
IQ view is back exactly as in 0.26.3.2, but Freshy in its hero is the new animated
character with eleven moods.

Replaces the 0.25.1.17/0.25.1.18 tests that pinned the old CSS-drawn mascot
(three-quarter angle layer, leaf wings, moon, airflow spans).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
MOODS = ["ok", "act", "run", "done", "night", "rain", "cool", "mould", "sensor", "pollen", "learn"]


def _panel():
    start = CARD.index("    _compactAIPanel(st, rooms = []) {")
    return CARD[start:CARD.index("\n    _", start + 10)]


def test_iq_view_and_classic_view_are_both_back():
    assert 'dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms)' in CARD
    assert "_freshyDashboard" not in CARD and "fd-nav" not in CARD


def test_iq_hero_uses_the_animated_freshy():
    panel = _panel()
    assert '<div class="ai-mascot-wrap fr-wrap">${freshySvg(freshyMood, 112, this._uiLanguage(), freshyProgress)}</div>' in panel
    assert 'class="ai-freshy-angle"' not in panel


def test_eleven_moods_each_have_their_own_face_or_motion():
    assert f'const FRESHY_MOODS = {str(MOODS).replace(chr(39), chr(34))};' in CARD
    for mood in MOODS:
        assert re.search(rf"\.fr-{mood} [^{{]*\{{[^}}]*(display:inline|animation|stroke)", CARD), mood
    assert "@media (prefers-reduced-motion: reduce){.fr *{animation:none!important}}" in CARD
    assert "FAIQ_DESIGN_CSS + FAIQ_FRESHY_CSS" in CARD


def test_mood_follows_the_situation_logic():
    panel = _panel()
    assert 'const freshyMood = kind === "live" && close.some(r => r.active) ? "done"' in panel
    assert ': kind === "continuous" || kind === "live" ? "run"' in panel
    assert 'kind === "night" ? (nightRecommendation && freshyNightAction ? "act" : freshyRainClose ? "rain" : "night")' in panel


def test_freshy_is_not_small():
    assert ".ai-mascot-wrap.fr-wrap .fr{width:112px;height:98px}" in CARD
    assert ".ai-mascot-wrap.fr-wrap,.ai-mascot-wrap.fr-wrap .fr{width:96px;height:84px}" in CARD
    assert "https://" not in CARD[CARD.index("const FAIQ_FRESHY_CSS"):CARD.index("class FreshAirIQCard extends")]
