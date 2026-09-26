from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_editor_has_own_safe_translation_bridge():
    editor = CARD.split("class FreshAirIQCardEditor extends HTMLElement", 1)[1].split("if (!customElements.get(\"freshairiq-card-editor\"))", 1)[0]
    assert "_uiLanguage()" in editor
    assert "_t(key, vars = {})" in editor
    assert "const entry = FAIQ_UI[key]" in editor
    assert 'this._t("editor.dashboard_design")' in editor
    assert 'this._t("editor.classic")' in editor

def test_dashboard_variant_change_contract_remains_intact():
    editor = CARD.split("class FreshAirIQCardEditor extends HTMLElement", 1)[1]
    assert 'getElementById("dashboard-variant")' in editor
    assert 'dashboard_variant: e.target.value === "classic" ? "classic" : "iq"' in editor
    assert 'new CustomEvent("config-changed"' in editor

def test_release_version_is_025018():
    assert 'const FAIQ_VERSION = "0.25.1.8";' in CARD
