from pathlib import Path

CARD = Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_dark_card_isolates_home_assistant_theme_foreground_variables():
    assert "color:#e9f0f4;--primary-text-color:#e9f0f4;--secondary-text-color:#84939e;" in CARD

def test_dark_dialog_isolates_home_assistant_theme_foreground_variables():
    assert ".dialog{color:#e9f0f4;--primary-text-color:#e9f0f4;--secondary-text-color:#84939e}" in CARD

def test_semantic_accent_colors_are_preserved():
    assert ".iq{color:#56d5ff}" in CARD
    assert "color:var(--decision)" in CARD
