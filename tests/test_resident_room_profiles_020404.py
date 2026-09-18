from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from custom_components.freshairiq.personal_context import build_resident_context, personalise_recommendation


def _recommendation(room_key="office"):
    return {
        "kind": "ventilate",
        "room_keys": [room_key],
        "summary": "Technische Empfehlung.",
        "reasons": ["Außenluft ist günstiger."],
        "duration_min": 8,
        "decision_brain": {
            "summary": "Technische Empfehlung.",
            "why": ["Außenluft ist günstiger."],
            "impact": {"temperature_c": -0.4, "cost": 0.02},
        },
    }


def test_room_assignment_and_individual_comfort_are_loaded_by_resident_slot():
    options = {
        "adult_occupants": 2,
        "child_occupants": 1,
        "adult_resident_names": "Paul, Lydia",
        "child_resident_names": "Fiona",
        "adult_presence_entities": ["person.paul", "person.lydia"],
        "resident_room_profiles": '{"adult:0":{"room_keys":["office","bed"],"thermal_preference":"warm"},"child:0":{"room_keys":["kids"],"thermal_preference":"balanced"}}',
    }
    states = {
        "person.paul": SimpleNamespace(state="home"),
        "person.lydia": SimpleNamespace(state="not_home"),
    }
    ctx = build_resident_context(options, states)
    paul = next(r for r in ctx["residents"] if r["name"] == "Paul")
    fiona = next(r for r in ctx["residents"] if r["name"] == "Fiona")
    assert paul["room_keys"] == ["office", "bed"]
    assert paul["thermal_preference"] == "warm"
    assert fiona["room_keys"] == ["kids"]
    assert ctx["direct_address_name"] == "Paul"


def test_assigned_room_personalises_wording_without_changing_technical_decision():
    options = {
        "adult_occupants": 2,
        "adult_resident_names": "Paul, Lydia",
        "adult_presence_entities": ["person.paul", "person.lydia"],
        "resident_room_profiles": '{"adult:0":{"room_keys":["office"],"thermal_preference":"warm"}}',
        "personalisation_enabled": True,
        "thermal_preference": "balanced",
        "personal_priority": "balanced",
        "night_window_preference": "automatic",
    }
    states = {
        "person.paul": SimpleNamespace(state="home"),
        "person.lydia": SimpleNamespace(state="not_home"),
    }
    ctx = build_resident_context(options, states)
    rooms = {"office": {"key": "office", "name": "Arbeitszimmer", "behaviour_recommendation_opportunities": 0}}
    rec = _recommendation()
    out = personalise_recommendation(rec, rooms, options, now=datetime(2026, 9, 12, 12, 0), resident_context=ctx, expected_occupants=1)
    assert out["summary"].startswith("Paul,")
    assert "Arbeitszimmer" in out["summary"]
    assert out["kind"] == rec["kind"]
    assert out["room_keys"] == rec["room_keys"]
    assert out["duration_min"] == rec["duration_min"]
    assert out["personal_context"]["assigned_residents"][0]["name"] == "Paul"
    assert any("warmes Komfortprofil" in reason for reason in out["reasons"])


def test_child_room_assignment_is_context_not_direct_instruction():
    options = {
        "adult_occupants": 1,
        "child_occupants": 1,
        "adult_resident_names": "Paul",
        "child_resident_names": "Fiona",
        "adult_presence_entities": ["person.paul"],
        "resident_room_profiles": '{"child:0":{"room_keys":["kids"],"thermal_preference":"balanced"}}',
        "personalisation_enabled": True,
    }
    states = {"person.paul": SimpleNamespace(state="not_home")}
    ctx = build_resident_context(options, states)
    rooms = {"kids": {"key": "kids", "name": "Kinderzimmer"}}
    out = personalise_recommendation(_recommendation("kids"), rooms, options, now=datetime(2026, 9, 12, 18, 0), resident_context=ctx)
    assert not out["summary"].startswith("Fiona,")
    assert any("Für Fiona" in reason and "Kinderzimmer" in reason for reason in out["reasons"])



def test_room_profile_follows_named_resident_when_name_order_changes():
    options = {
        "adult_occupants": 2,
        "adult_resident_names": "Lydia, Paul",
        "adult_presence_entities": ["person.lydia", "person.paul"],
        "resident_room_profiles": '{"adult:0":{"name":"Paul","room_keys":["office"],"thermal_preference":"warm"},"adult:1":{"name":"Lydia","room_keys":["living"],"thermal_preference":"balanced"}}',
    }
    states = {"person.lydia": SimpleNamespace(state="home"), "person.paul": SimpleNamespace(state="not_home")}
    ctx = build_resident_context(options, states)
    lydia = next(r for r in ctx["residents"] if r["name"] == "Lydia")
    paul = next(r for r in ctx["residents"] if r["name"] == "Paul")
    assert lydia["room_keys"] == ["living"]
    assert paul["room_keys"] == ["office"]

def test_dashboard_has_structured_resident_profile_editor_and_diagnostics_scrub_personal_text():
    root = Path(__file__).resolve().parents[1]
    card = (root / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    settings = (root / "custom_components/freshairiq/settings_api.py").read_text(encoding="utf-8")
    diagnostics = (root / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert "BEWOHNERPROFILE" in card
    assert "data-resident-profile" in card
    assert 'key:"resident_room_profiles"' in card
    assert '"resident_room_profiles"' in settings
    assert "_privacy_safe_decision" in diagnostics
    assert "_privacy_safe_iq_state" in diagnostics
    safe_block = diagnostics.split("_SAFE_OPTION_KEYS", 1)[1].split(")", 1)[0]
    assert "resident_room_profiles" not in safe_block
