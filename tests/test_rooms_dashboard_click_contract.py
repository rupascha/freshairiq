from pathlib import Path


def test_rooms_button_matches_direct_action_button_pattern():
    card = (Path(__file__).parents[1] / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'id="rooms"' in card
    assert 'id="rooms" data-info="rooms"' not in card
    assert 'getElementById("rooms")' in card
    assert 'getElementById("guests")' in card
    assert 'getElementById("support")' in card
    assert 'this._info = "rooms"; this._render();' in card
