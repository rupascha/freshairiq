from datetime import datetime

from custom_components.freshairiq.personal_context import personalise_recommendation


def base_rec(kind="ventilate"):
    return {
        "kind": kind,
        "room_keys": ["bed"],
        "summary": "Technische Zusammenfassung.",
        "reasons": ["Physikalischer Grund"],
        "duration_min": 8,
        "decision_brain": {
            "summary": "Technische Zusammenfassung.",
            "why": ["Physikalischer Grund"],
            "impact": {"temperature_c": -0.5, "cost": 0.04},
        },
    }


def room():
    return {"bed": {"name": "Schlafzimmer", "behaviour_recommendation_opportunities": 10, "behaviour_recommendation_followed": 8}}


def test_personal_context_never_changes_technical_decision():
    rec = base_rec()
    out = personalise_recommendation(rec, room(), {
        "personalisation_enabled": True, "thermal_preference": "warm",
        "personal_priority": "energy", "night_window_preference": "closed",
    }, now=datetime(2026, 9, 12, 7, 0), expected_occupants=2)
    for key in ("kind", "room_keys", "duration_min"):
        assert out[key] == rec[key]
    assert out["decision_brain"]["personalised"] is True
    assert out["personal_context"]["behaviour_follow_rate"] == 80.0


def test_personal_context_disabled_is_identity_for_user_facing_text():
    rec = base_rec()
    out = personalise_recommendation(rec, room(), {"personalisation_enabled": False}, now=datetime(2026, 9, 12, 7, 0))
    assert out["summary"] == rec["summary"]
    assert out["decision_brain"] == rec["decision_brain"]
    assert out["personal_context"]["enabled"] is False


def test_behaviour_requires_minimum_observations():
    rooms = {"bed": {"behaviour_recommendation_opportunities": 4, "behaviour_recommendation_followed": 4}}
    out = personalise_recommendation(base_rec(), rooms, {
        "personalisation_enabled": True, "thermal_preference": "balanced",
        "personal_priority": "balanced", "night_window_preference": "automatic",
    }, now=datetime(2026, 9, 12, 12, 0), expected_occupants=1)
    assert out["personal_context"]["behaviour_follow_rate"] is None
    assert not any("Lüftungsverhalten" in x for x in out["decision_brain"]["why"])
