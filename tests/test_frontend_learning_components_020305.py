from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_details_contains_hierarchical_learning_overview_and_quality_metrics():
    assert "_learningComponentsCard(st, rooms)" in JS
    assert "Lernfortschritt nach Bereichen" in JS
    assert "Dein Zuhause" in JS
    assert "Prognosen & Lernen" in JS
    assert "Deine Gewohnheiten" in JS
    assert "Langzeitlernen" in JS
    assert "MODELLQUALITÄT & DIAGNOSE" in JS
    assert "Betragsgenauigkeit" in JS
    assert "Richtung" in JS
    assert "Prognosequalität" in JS
    assert 'live_forecast:"mdi:chart-bell-curve-cumulative"' in JS
    assert 'personal_context:"mdi:account-heart-outline"' in JS


def test_longterm_drilldown_uses_independent_time_evidence():
    assert 'this._info === "learning:longterm"' in JS
    assert "Jahreszeiten optimiert" in JS
    assert "Nächte gelernt" in JS
    assert "Hohe Pollingraten beschleunigen die Reife nicht" in JS


def test_release_version_020305_is_consistent():
    assert 'const FAIQ_VERSION = "0.25.1.8";' in JS
    assert 'VERSION = "0.25.1.8"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.1.8"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
