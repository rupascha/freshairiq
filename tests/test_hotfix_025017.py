from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()

def test_legacy_learning_status_removed():
    assert "LERNMODELL V14.2.1" not in CARD
    assert "FRESHAIRIQ INTELLIGENCE 2.0" in CARD

def test_runtime_version():
    assert 'const FAIQ_VERSION = "0.25.0.75"' in CARD
