"""Cross-module finite-number hardening for v0.25.0.7."""
from datetime import datetime, timedelta

from custom_components.freshairiq.personal_context import build_resident_context, personalise_recommendation
from custom_components.freshairiq.ventilation_result import (
    append_completed_sessions,
    finalise_ventilation_group,
    include_ventilation_group_start,
    new_ventilation_group,
    update_session_cross_tracking,
)
from custom_components.freshairiq.passive_ventilation import evaluate_passive_ventilation


class StateSource:
    def __init__(self, mapping=None, raises=False):
        self.mapping = mapping or {}
        self.raises = raises
    def get(self, entity_id):
        if self.raises:
            raise RuntimeError("boom")
        return self.mapping.get(entity_id)


def test_personal_context_nonfinite_behaviour_counters_cannot_crash():
    rec = {
        "kind": "ventilate", "room_keys": ["r"], "summary": "Lüften.",
        "decision_brain": {"summary": "Lüften.", "why": [], "impact": {"temperature_c": float("nan"), "cost": float("inf")}},
    }
    rooms = {"r": {"key": "r", "name": "Raum", "behaviour_recommendation_opportunities": float("nan"), "behaviour_recommendation_followed": float("inf")}}
    out = personalise_recommendation(rec, rooms, {"personalisation_enabled": True}, now=datetime(2026, 9, 14, 7, 0))
    assert out["personal_context"]["behaviour_opportunities"] == 0
    assert out["personal_context"]["behaviour_follow_rate"] is None


def test_build_resident_context_handles_bad_counts_bad_json_and_state_errors():
    options = {
        "adult_occupants": float("nan"),
        "child_occupants": "broken",
        "adult_resident_names": " Paul ; Lydia\n",
        "adult_presence_entities": ["person.paul", "person.lydia"],
        "resident_room_profiles": "{not-json",
    }
    ctx = build_resident_context(options, StateSource(raises=True), expected_occupants=1)
    assert ctx["configured_names"] == 2
    assert all(r["presence"] == "unknown" for r in ctx["residents"])
    assert ctx["direct_address_name"] is None


def test_resident_profile_follows_matching_name_after_reorder():
    options = {
        "adult_occupants": 2,
        "adult_resident_names": ["Lydia", "Paul"],
        "adult_presence_entities": ["person.lydia", "person.paul"],
        "resident_room_profiles": {
            "adult:0": {"name": "Paul", "room_keys": ["office"], "thermal_preference": "warm"},
            "adult:1": {"name": "Lydia", "room_keys": ["living"], "thermal_preference": "cool"},
        },
    }
    states = StateSource({"person.lydia": "home", "person.paul": "not_home"})
    ctx = build_resident_context(options, states)
    lydia = ctx["residents"][0]
    assert lydia["name"] == "Lydia"
    assert lydia["room_keys"] == ["living"]
    assert lydia["thermal_preference"] == "cool"
    assert ctx["direct_address_name"] == "Lydia"


def test_ventilation_result_ignores_nonfinite_numeric_payloads():
    start = datetime(2026, 9, 14, 6, 0)
    group = new_ventilation_group(start)
    assert append_completed_sessions(group, [{
        "event_id": "x", "key": "r", "name": "Raum", "volume_m3": float("nan"),
        "removed_ml": float("nan"), "duration_min": float("inf"), "cost": float("inf"),
        "energy_kwh": float("-inf"), "temp_delta_c": float("nan"),
        "predicted_removed_ml": float("inf"), "prediction_comparable": True,
        "predicted_temperature_change_c": float("nan"),
        "cross_ventilation_minutes": float("inf"),
    }])
    result = finalise_ventilation_group(group, start + timedelta(minutes=10))
    assert result is not None
    room = result["room_results"][0]
    assert room["removed_ml"] is None
    assert room["moisture_result_complete"] is False
    assert room["duration_min"] == 0.0
    assert room["cost"] == 0.0
    assert room["energy_kwh"] == 0.0
    assert room["temp_delta_c"] is None
    assert room["predicted_removed_ml"] is None


def test_ventilation_group_helpers_tolerate_invalid_and_duplicate_events():
    start = datetime(2026, 9, 14, 7, 0)
    group = new_ventilation_group(start)
    assert include_ventilation_group_start(group, "broken") is False
    assert include_ventilation_group_start(group, start - timedelta(minutes=2)) is True
    assert include_ventilation_group_start(group, start) is False
    group["sessions"] = "corrupt"
    assert append_completed_sessions(group, [{"event_id": "1", "key": "r"}]) is True
    assert append_completed_sessions(group, [{"event_id": "1", "key": "r"}]) is False
    assert append_completed_sessions(group, []) is False


def test_cross_tracking_handles_bad_timestamp_and_inactive_session():
    now = datetime(2026, 9, 14, 7, 0)
    assert update_session_cross_tracking({}, now, True) is False
    mem = {"session_active": True, "session_cross_last_update": "broken", "session_cross_active": True}
    assert update_session_cross_tracking(mem, now, False) is True
    assert mem["session_cross_active"] is False


def test_passive_ventilation_guard_reasons_are_deterministic():
    common = dict(start_ah=12, current_ah=11, reference_ah=8, volume_m3=50, elapsed_min=10, connected=True)
    assert evaluate_passive_ventilation(**common, connection_strength=0.2)["reason"] == "not_connected"
    assert evaluate_passive_ventilation(**{**common, "elapsed_min": 2})["reason"] == "warming_up"
    assert evaluate_passive_ventilation(**{**common, "reference_ah": 11.9})["reason"] == "reference_too_similar"
    assert evaluate_passive_ventilation(**{**common, "reference_ah": 13, "start_reference_ah": 8})["reason"] == "reference_changed_direction"
    assert evaluate_passive_ventilation(**{**common, "current_ah": 11.99})["reason"] == "below_noise_floor"
    assert evaluate_passive_ventilation(**{**common, "current_ah": 12.5})["reason"] == "wrong_direction"


def test_ventilation_result_falls_back_to_event_start_and_feedback_priority():
    ended = datetime(2026, 9, 14, 8, 0)
    group = {"active": True, "started_at": "broken", "sessions": [
        {"event_id": "1", "key": "r", "name": "Raum", "started_at": "broken", "duration_min": 3, "outcome_feedback_action": "applied"},
        {"event_id": "2", "key": "r", "name": "Raum", "started_at": (ended - timedelta(minutes=7)).isoformat(), "duration_min": 4, "outcome_feedback_action": "guarded_observation", "outcome_feedback_reason": "large"},
    ]}
    out = finalise_ventilation_group(group, ended)
    assert out["duration_min"] == 7.0
    assert out["learning_feedback_action"] == "guarded_observation"
    assert "Verdachtsprobe" in out["learning_feedback_text"]


def test_ventilation_feedback_texts_cover_all_public_actions():
    ended = datetime(2026, 9, 14, 8, 0)
    expected_fragments = {
        "cautious_confirmation": "zweite ähnliche",
        "confirmed_outlier": "wiederholt bestätigt",
        "guarded": "minimal angepasst",
        "cautious": "geringer Gewichtung",
        "applied": "Lernmodell übernommen",
        "skipped": "nicht zur Prognoseanpassung",
    }
    for action, fragment in expected_fragments.items():
        group = {"active": True, "started_at": ended.isoformat(), "sessions": [{"key": action, "name": action, "duration_min": 2, "outcome_feedback_action": action}]}
        out = finalise_ventilation_group(group, ended)
        assert out["learning_feedback_action"] == action
        assert fragment in out["learning_feedback_text"]


def test_personal_context_covers_energy_wait_close_night_and_child_wording():
    rooms = {
        "kids": {"key": "kids", "name": "Kinderzimmer", "behaviour_recommendation_opportunities": 10, "behaviour_recommendation_followed": 2},
    }
    resident_context = {
        "configured_names": 2,
        "direct_address_name": "Paul",
        "named_adults_home": ["Paul"],
        "residents": [
            {"role": "adult", "name": "Paul", "room_keys": ["kids"], "thermal_preference": "warm"},
            {"role": "child", "name": "Maya", "room_keys": ["kids"], "thermal_preference": "warm"},
        ],
    }
    rec = {
        "kind": "ventilate", "room_keys": ["kids"], "summary": "Basis",
        "expected_temperature_change_c": -0.5, "estimated_reheat_cost": 0.2,
        "decision_brain": {"summary": "Basis", "why": [], "impact": {"temperature_c": -0.5, "cost": 0.2}, "night_strategy": {"active": True, "action": "close"}},
    }
    out = personalise_recommendation(rec, rooms, {
        "personalisation_enabled": True, "thermal_preference": "warm", "personal_priority": "energy", "night_window_preference": "closed"
    }, now=datetime(2026, 9, 14, 19, 0), expected_occupants=2, resident_context=resident_context)
    text = " ".join(out["reasons"])
    assert out["summary"].startswith("Paul")
    assert "Wärmekomfort" in text or "warmes Komfortprofil" in text
    assert "Energie" in text
    assert "Maya" in text
    assert "nachts Fenster geschlossen" in text

    wait = personalise_recommendation({"kind": "wait", "room_keys": [], "summary": "Basis", "decision_brain": {"summary": "Basis", "why": []}}, rooms,
                                     {"personalisation_enabled": True, "personal_priority": "energy"}, now=datetime(2026, 9, 14, 12, 0), expected_occupants=0)
    assert wait["summary"].startswith("Warten vermeidet")
    assert any("keine unmittelbare Anwesenheit" in x for x in wait["reasons"])

    close = personalise_recommendation({"kind": "close", "room_keys": ["kids"], "summary": "Basis", "decision_brain": {"summary": "Basis", "why": []}}, rooms,
                                      {"personalisation_enabled": True, "thermal_preference": "warm"}, now=datetime(2026, 9, 14, 12, 0), resident_context=resident_context)
    assert any("Längeres Offenlassen" in x for x in close["reasons"])


def test_personal_context_allows_night_open_preference():
    rec = {"kind": "okay", "room_keys": [], "summary": "Basis", "decision_brain": {"summary": "Basis", "why": [], "night_strategy": {"active": True, "action": "open_selected"}}}
    out = personalise_recommendation(rec, {}, {"personalisation_enabled": True, "night_window_preference": "allowed"}, now=datetime(2026, 9, 14, 23, 0), expected_occupants=1)
    assert any("Nächtlich geöffnete Fenster" in x for x in out["reasons"])
