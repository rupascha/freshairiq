from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sensorless_shell_is_marked_and_complete_edit_reactivates_calculations():
    text = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    assert '"_auto_passive_no_sensors": bool(auto_passive)' in text
    assert "if not include and auto_passive and complete_active_setup:" in text
    assert "include = True" in text


def test_explicitly_disabled_configured_room_is_not_auto_reactivated():
    text = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    assert "and not previous.get(CONF_ROOM_TEMPERATURE)" in text
    assert "and not previous.get(CONF_ROOM_HUMIDITY)" in text
    assert "and not (previous.get(CONF_ROOM_CONTACTS) or [])" in text


def test_loader_dashboard_strategy_has_editor_and_propagates_variant():
    text = (ROOT / "custom_components/freshairiq/frontend/freshairiq-loader.js").read_text(encoding="utf-8")
    assert "FreshAirIQLoaderStrategyEditor" in text
    assert "static getConfigElement()" in text
    assert 'dashboard_variant:dashboardVariant' in text
    assert 'type:"custom:freshairiq-card"' in text


def test_heavy_strategy_propagates_variant_too():
    text = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'config.dashboard_variant === "iq" ? "iq" : "classic"' in text
    assert 'dashboard_variant: dashboardVariant' in text
