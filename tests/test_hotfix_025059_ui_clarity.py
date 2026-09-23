from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"

def test_decision_simulation_is_not_rendered():
    s = (COMP / "frontend/freshairiq-card.js").read_text()
    assert "IQ ENTSCHEIDUNGSSIMULATION" not in s
    assert "simulated_options) || []).slice(0, 5)" not in s

def test_night_comparison_is_one_user_facing_comparison():
    s = (COMP / "frontend/freshairiq-card.js").read_text()
    assert "WAS BRINGT LÜFTEN VOR DEM SCHLAFEN?" in s
    assert "night-comparison-grid" in s
    assert "Mit der Empfehlung erwartet FreshAirIQ morgen rund" in s
    assert "kein messbarer Feuchtevorteil" in s

def test_floor_selector_keeps_ids_but_uses_native_translation():
    s = (COMP / "config_flow.py").read_text()
    assert 'options=levels, mode=selector.SelectSelectorMode.DROPDOWN, custom_value=True, translation_key="floor"' in s
    de = (COMP / "translations/de.json").read_text()
    assert '"ground_floor": "Erdgeschoss"' in de
    assert '"basement": "Kellergeschoss"' in de
