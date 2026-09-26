from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_ai_first_dashboard_contract():
    assert 'const FAIQ_VERSION = "0.25.1.8";' in JS
    assert '_compactAIPanel(st, rooms = [])' in JS
    assert 'FreshAirIQ übernimmt' in JS
    assert 'class="ai-mascot"' in JS
    assert '@media(prefers-reduced-motion:reduce)' in JS
    assert 'data-info="night"' in JS
    assert 'data-info="pollen"' in JS
    assert 'data-info="learning:quality"' in JS

def test_landing_uses_compact_panel_without_removing_detail_engine():
    assert 'dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms)' in JS
    assert '_intelligentPanel(st, rooms = [])' in JS
    assert '_details(st, rooms)' in JS
