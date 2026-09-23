from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


def test_idle_card_does_not_offer_timed_ventilation_forecast():
    js = CARD.read_text(encoding="utf-8")
    assert "BEI LÜFTUNG · ${forecastH} MIN" not in js
    assert "JETZT ENTFERNBAR" in js
    assert "NACHTPROGNOSE" in js
    assert "SCHIMMEL" in js


def test_live_forecast_remains_available_during_active_ventilation():
    js = CARD.read_text(encoding="utf-8")
    assert "if (active.length)" in js
    assert "WEITERE ${forecastH} MIN" in js
    assert "seit Lüftungsbeginn" in js


def test_iq_header_shows_forecast_horizon_only_when_ventilation_is_active():
    js = CARD.read_text(encoding="utf-8")
    assert 'active.length && showForecast ? `Prognose ${forecastH} min · ` : ""' in js


def test_release_version_020308_is_consistent():
    assert 'const FAIQ_VERSION = "0.25.0.58";' in CARD.read_text(encoding="utf-8")
    assert 'VERSION = "0.25.0.58"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.58"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
