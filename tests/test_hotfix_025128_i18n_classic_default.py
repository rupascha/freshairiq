from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
LOADER = (ROOT / "custom_components/freshairiq/frontend/freshairiq-loader.js").read_text()
PANEL = (ROOT / "custom_components/freshairiq/frontend/freshairiq-panel.js").read_text()

def test_new_cards_default_to_classic_without_overriding_saved_choice():
    assert 'raw.dashboard_variant || "classic"' in CARD
    assert 'static getStubConfig() { return { dashboard_variant: "classic" }; }' in CARD
    assert 'static getStubConfig() { return {dashboard_variant:"classic"}; }' in LOADER
    assert 'this._config.dashboard_variant === "classic" ? "classic" : "iq"' in CARD

def test_native_support_dialogs_use_i18n_keys():
    for key in ("support.prompt", "support.message_too_long", "support.confirm", "support.success", "support.failure_alert", "settings.confirm_delete_room", "settings.confirm_reset_learning", "settings.confirm_reset_options"):
        assert f'"{key}"' in CARD
    assert 'window.prompt(this._t("support.prompt")' in CARD
    assert 'window.confirm(this._t("support.confirm"))' in CARD
    assert 'window.alert(this._t("support.failure_alert"))' in CARD

def test_loader_and_safe_panel_have_english_fallback_copy():
    assert 'FreshAirIQ is loading' in LOADER
    assert 'Intelligent ventilation, humidity, energy and learning overview.' in LOADER
    assert 'FreshAirIQ is loading …' in PANEL
    assert 'FreshAirIQ could not be loaded' in PANEL
