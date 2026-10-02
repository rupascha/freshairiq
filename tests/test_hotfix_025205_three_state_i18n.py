from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"
COORD = ROOT / "custom_components/freshairiq/coordinator.py"


def test_three_state_runtime_copy_has_english_dashboard_parity():
    card = CARD.read_text(encoding="utf-8")
    pairs = {
        "Fenster ist gekippt; vollständig öffnen erhöht den Luftwechsel für die aktuelle Empfehlung":
            "Window is tilted; opening it fully increases airflow for the current recommendation",
        "Drei-Zustands-Sensor meldet Kipplüftung; FreshAirIQ empfiehlt für den aktuellen Bedarf vollständiges Öffnen":
            "Three-state sensor reports a tilted window; FreshAirIQ recommends opening it fully for the current ventilation demand",
        "Drei-Zustands-Sensor meldet Kipplüftung; der reduzierte Luftwechsel wird separat gelernt":
            "Three-state sensor reports a tilted window; the reduced airflow is learned separately",
        "Vollständig öffnen": "Open fully",
    }
    for de, en in pairs.items():
        assert f'["{de}", "{en}"]' in card


def test_open_fully_action_uses_existing_language_adapter():
    card = CARD.read_text(encoding="utf-8")
    assert '"Open fully": "Vollständig öffnen"' in card
    assert 'faiqEnglishText(actionDE(r.action))' in card
    assert "_localizeLegacyFragment" in card


def test_all_new_three_state_user_visible_backend_copy_is_covered():
    coordinator = COORD.read_text(encoding="utf-8")
    card = CARD.read_text(encoding="utf-8")
    expected = [
        "Drei-Zustands-Sensor meldet Kipplüftung; die gewählte Lüftungsart wird mit dem separaten Kippmodell bewertet",
    ]
    for text in expected:
        assert text in coordinator
        assert f'["{text}",' in card
