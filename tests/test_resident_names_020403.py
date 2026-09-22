from datetime import datetime
from types import SimpleNamespace

from custom_components.freshairiq.personal_context import build_resident_context, personalise_recommendation


def _rec(kind="ventilate"):
    return {
        "kind": kind,
        "room_keys": ["bed"],
        "summary": "Schlafzimmer etwa 8 Minuten lüften.",
        "reasons": ["Außenluft ist trockener."],
        "duration_min": 8,
        "decision_brain": {
            "summary": "Schlafzimmer etwa 8 Minuten lüften.",
            "why": ["Außenluft ist trockener."],
            "impact": {"temperature_c": -0.3, "cost": 0.02},
        },
    }


def test_named_resident_is_addressed_only_when_sole_adult_is_confirmed_home():
    options = {
        "adult_occupants": 2,
        "child_occupants": 2,
        "adult_resident_names": "Paul, Lydia",
        "child_resident_names": "Fiona, Maya",
        "adult_presence_entities": ["person.paul", "person.lydia"],
        "child_presence_entities": [],
        "personalisation_enabled": True,
        "thermal_preference": "balanced",
        "personal_priority": "balanced",
        "night_window_preference": "automatic",
    }
    states = {
        "person.paul": SimpleNamespace(state="home"),
        "person.lydia": SimpleNamespace(state="not_home"),
    }
    resident_context = build_resident_context(options, states, expected_occupants=1.0)
    assert resident_context["direct_address_name"] == "Paul"
    assert resident_context["configured_names"] == 4

    rooms = {"bed": {"behaviour_recommendation_opportunities": 10, "behaviour_recommendation_followed": 8}}
    out = personalise_recommendation(
        _rec(), rooms, options, now=datetime(2026, 9, 12, 7, 0),
        expected_occupants=1.0, resident_context=resident_context,
    )
    assert out["summary"].startswith("Paul,")
    assert out["personal_context"]["addressed_name"] == "Paul"
    assert out["kind"] == "ventilate"
    assert out["duration_min"] == 8


def test_no_direct_name_when_an_untracked_adult_could_also_be_home():
    options = {
        "adult_occupants": 2,
        "adult_resident_names": "Paul, Lydia",
        "adult_presence_entities": ["person.paul"],
    }
    states = {"person.paul": SimpleNamespace(state="home")}
    ctx = build_resident_context(options, states, expected_occupants=1.0)
    assert ctx["direct_address_name"] is None


def test_child_names_are_context_only_not_direct_action_addressees():
    options = {
        "adult_occupants": 0,
        "child_occupants": 1,
        "child_resident_names": "Fiona",
        "child_presence_entities": ["person.fiona"],
    }
    states = {"person.fiona": SimpleNamespace(state="home")}
    ctx = build_resident_context(options, states, expected_occupants=1.0)
    assert ctx["direct_address_name"] is None
    assert ctx["configured_names"] == 1


def test_names_are_local_presentation_options_and_available_in_both_settings_uis():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    card = (root / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    flow = (root / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    settings = (root / "custom_components/freshairiq/settings_contract.py").read_text(encoding="utf-8")
    diagnostics = (root / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert 'key:"adult_resident_names"' in card
    assert 'key:"child_resident_names"' in card
    assert '"adult_resident_names"' in flow and '"child_resident_names"' in flow
    assert '"adult_resident_names", "child_resident_names"' in settings
    # Names must not enter the diagnostics safe-option whitelist.
    safe_block = diagnostics.split("_SAFE_OPTION_KEYS", 1)[1].split("}", 1)[0]
    assert "adult_resident_names" not in safe_block
    assert "child_resident_names" not in safe_block
