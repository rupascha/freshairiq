from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CARD=ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js"

def card_text(): return CARD.read_text(encoding="utf-8")

def test_dashboard_defaults_to_full_view_and_can_be_compacted():
    text=card_text()
    for key in ("info_moisture", "info_temperature", "info_time", "info_forecast", "info_night", "info_mould", "info_energy", "info_pollen", "info_cross_ventilation", "show_branding", "show_profile_badge", "show_iq_process", "show_details_button", "show_guests_button", "show_rooms_button"):
        assert f'inherited("{key}"' in text
    assert 'bleibt das vollständige Dashboard sichtbar' in text
    assert 'bleibt eine kompakte Ansicht mit der zentralen FreshAirIQ-Empfehlung' in text

def test_all_action_buttons_are_optional():
    text=card_text()
    assert 'show_details_button !== false' in text
    assert 'show_guests_button !== false' in text
    assert 'show_rooms_button !== false' in text

def test_central_recommendation_and_reasons_remain_visible():
    text=card_text()
    assert '${why.length ? `<div class="decision-why">' in text
    assert 'dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms)' in text
