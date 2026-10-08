from pathlib import Path
CARD=(Path(__file__).resolve().parents[1]/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
def test_rooms_tile_is_native_button_on_same_path_as_other_context_tiles():
    assert '<div class="ai-all-good clickable" data-info="rooms">' in CARD
    assert 'querySelectorAll("[data-info]")' in CARD
    assert "_boundShadowClick" not in CARD
    assert "_openRoomsOverview" not in CARD
