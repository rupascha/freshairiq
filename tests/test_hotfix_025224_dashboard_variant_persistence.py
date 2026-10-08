from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
def test_dashboard_variant_pending_choice_survives_stale_ha_config_echo():
    editor = CARD.split("class FreshAirIQCardEditor extends HTMLElement", 1)[1]
    assert "this._pendingDashboardVariant = null" in editor
    assert "incoming.dashboard_variant !== this._pendingDashboardVariant" in editor
    assert "dashboard_variant: this._pendingDashboardVariant" in editor
    assert "queueMicrotask(() => this._emitConfigChanged(this._config))" in editor
    assert "this._pendingDashboardVariant = nextConfig.dashboard_variant" in editor
def test_dashboard_variant_uses_ha_documented_config_changed_contract():
    editor = CARD.split("class FreshAirIQCardEditor extends HTMLElement", 1)[1]
    assert 'new CustomEvent("config-changed"' in editor
    assert 'detail: {config: normalizeDashboardConfig(config)}' in editor
    assert "this._emitConfigChanged(this._config)" in editor
