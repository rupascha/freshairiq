from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_english_dashboard_locale_bridge_exists():
    assert 'const FAIQ_VERSION = "0.25.1.6";' in CARD
    assert '_uiLanguage()' in CARD
    assert 'raw.startsWith("de") ? "de" : "en"' in CARD
    assert '_localizeLegacyFragment(template.content);' in CARD
    assert 'NodeFilter.SHOW_TEXT' in CARD
    assert 'const FAIQ_UI = Object.freeze({' in CARD

def test_core_english_dashboard_copy_is_covered():
    for english in (
        '"Ventilate"', '"Rooms"', '"Guests"', '"Whole-home ventilation"',
        '"Humidity & water balance"', '"Forecasts & learning"',
        '"FreshAirIQ is currently learning"', '"Why this decision?"',
    ):
        assert english in CARD

def test_german_rendering_source_is_preserved():
    # German legacy rendering remains compatible while new UI uses keyed i18n.
    # The legacy bridge is one-way and runs before the fragment is mounted.
    assert '"Lüften"' in CARD
    assert '"Räume"' in CARD
    assert 'if (!root || this._uiLanguage() === "de") return;' in CARD
