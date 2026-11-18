from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Testvermerk 0.26.7.2 (R07): the IQ time tile moved into freshairiq-card-data.js (card size gate); the source contract
# reads both modules, the checked expressions are unchanged
JS = "\n".join((ROOT / f"custom_components/freshairiq/frontend/{name}").read_text(encoding="utf-8")
                for name in ("freshairiq-card.js", "freshairiq-card-data.js"))


# test_grouped_settings_route_to_group_menu: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); covered by ha_tests/test_config_flow_matrix.py::test_options_main_sections_are_reachable


def test_iq_time_zero_is_not_reported_as_over_target():
    assert 'remaining < 0 ? `+${Math.ceil(Math.abs(remaining))} min` : "0 min"' in JS
    # Testvermerk 0.26.7.1 (N1): a zero remaining time is "target reached" only where it really means that – a running
    # airing with 0 or unknown time is "being reassessed"; "0 min" stays for a real close ("jetzt schließen")
    assert 'remaining < 0 ? "über Ziel" : "jetzt schließen"' in JS
    assert '(remaining === 0 && st.remaining_duration_state !== "close")) return "<b>wird neu bewertet</b>' in JS


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
