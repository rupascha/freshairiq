from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


def test_quick_setup_assumption_is_not_inferred_from_numeric_240_value():
    """2.40 m may be the user's exact measured height; provenance must be explicit."""
    card = CARD.read_text(encoding="utf-8")
    assert 'data-height-assumed="${r.height_assumed ? "true" : "false"}"' in card
    assert 'roomAreaHeight.dataset.userConfirmed = "true"' in card
    assert 'get("room-area-height").dataset.heightAssumed === "true"' in card
    assert 'get("room-area-height").dataset.userConfirmed !== "true"' in card
    assert 'Math.abs(Number(get("room-area-height").value) - 2.40) < 0.001' not in card


def test_estimate_banner_requires_assumed_height_not_just_area():
    """An exact area/height edit must remove the provisional-size warning."""
    card = CARD.read_text(encoding="utf-8")
    assert '${r.estimated_area_m2 && r.height_assumed ? `<div class="settings-group">' in card


def test_new_settings_strings_have_english_fallbacks():
    """All strings introduced by the settings/quick-setup UX must translate outside German HA."""
    card = CARD.read_text(encoding="utf-8")
    pairs = {
        "Raumgröße derzeit geschätzt": "Room size currently estimated",
        "Raumhöhe für Fläche": "Room height for area",
        "Direktes Raumvolumen": "Direct room volume",
        "Raum speichern": "Save room",
        "Raum löschen": "Delete room",
        "Diagnosedaten": "Diagnostic data",
        "Diagnose senden": "Send diagnostics",
    }
    for de, en in pairs.items():
        assert f'["{de}", "{en}"]' in card
