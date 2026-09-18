from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_grouped_settings_route_to_group_menu():
    assert 'section.startsWith("group_") ? this._settingsGroupMenu(section) : this._settingsSection(section)' in JS
    assert '[data-settings-section]' in JS


def test_iq_time_zero_is_not_reported_as_over_target():
    assert 'remaining < 0 ? `+${Math.ceil(Math.abs(remaining))} min` : "0 min"' in JS
    assert 'remaining < 0 ? "über Ziel" : "Ziel erreicht"' in JS


def test_forecast_change_masks_stale_value_until_matching_payload_arrives():
    assert 'const forecastDataH = Math.max(1, Math.round(Number(st.forecast_horizon_min || 5)));' in JS
    assert 'const forecastPending = forecastH !== forecastDataH;' in JS
    assert 'Wird berechnet …' in JS
    assert 'FreshAirIQ aktualisiert Feuchte, Temperatur und Kosten für den neuen Zeitraum.' in JS


def test_forecast_quick_choices_are_single_row_without_20_min_and_have_or_separator():
    assert 'const presets = [5, 10, 15, 30, 60];' in JS
    assert 'flex-wrap:nowrap' in JS
    assert '>oder</span>' in JS
    assert 'Schnellwahl wird sofort übernommen.' in JS
