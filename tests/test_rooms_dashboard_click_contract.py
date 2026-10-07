from pathlib import Path


def test_rooms_button_uses_central_info_handler():
    card = (Path(__file__).parents[1] / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'id="rooms" data-info="rooms"' in card
    assert 'getElementById("rooms")' not in card
    assert 'querySelectorAll("[data-info]")' in card
