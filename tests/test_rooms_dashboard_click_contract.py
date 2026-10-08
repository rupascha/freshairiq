from pathlib import Path
CARD=(Path(__file__).resolve().parents[1]/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
def test_rooms_button_and_tile_use_current_navigation_paths():
    assert 'id="rooms"' in CARD
    assert '<div class="ai-all-good clickable" data-info="rooms">' in CARD
    assert 'querySelectorAll("[data-info]")' in CARD
    assert '_o.addEventListener("click"' in CARD
    assert 'if (this._info === "rooms")' in CARD
