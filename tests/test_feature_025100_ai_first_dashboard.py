from tests.release_version import CURRENT_RELEASE_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_ai_first_dashboard_contract():
    assert f'const FAIQ_VERSION = "{CURRENT_RELEASE_VERSION}";' in JS
    assert '_compactAIPanel(st, rooms = [])' in JS
    assert 'FreshAirIQ übernimmt' in JS
    assert '<div class="ai-mascot-wrap fr-wrap">${freshySvg(freshyMood, 112, this._uiLanguage(), freshyProgress, this._freshyMotion(freshyMood, freshyTimeKind))}</div>' in JS
    assert '@media(prefers-reduced-motion:reduce)' in JS
    assert 'data-info="night"' in JS
    assert 'data-info="pollen"' in JS
    assert 'data-info="learning:quality"' in JS

def test_landing_uses_compact_panel_without_removing_detail_engine():
    assert 'dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms)' in JS
    assert '_intelligentPanel(st, rooms = [])' in JS
    assert '_details(st, rooms)' in JS
