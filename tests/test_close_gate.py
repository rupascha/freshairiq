from custom_components.freshairiq.live_coach import refine_live_recommendation
from custom_components.freshairiq.consolidation import stabilise_recommendation


def _room(**kw):
    room = {
        "key": "living", "name": "Living room", "calculation_enabled": True,
        "data_quality": "ok", "active": True, "action": "Continue ventilating",
        "close_recommended": False, "close_decision_ready": False,
        "session_elapsed_min": 10, "session_recommended_duration_min": 3,
        "session_predicted_removed_ml": 100, "result_ml": 80,
        "forecast_5_min_moisture_effect_ml": 5, "forecast_5_min_temperature_change_c": -0.1,
        "forecast_5_min_confidence": 80, "volume_m3": 80, "surface_rh": 65, "co2": 500,
    }
    room.update(kw)
    return room


def _options():
    return {
        "min_duration_min": 3, "max_duration_min": 20,
        "min_return_next_5_min_ml": 25, "mould_critical_surface_rh": 90,
        "co2_warn": 1000,
    }


def _recommendation(kind="continue"):
    return {
        "kind": kind, "status": "ventilation_running", "title": "Lüftung läuft",
        "instruction": "Living room offen lassen", "summary": "running",
        "room_keys": ["living"], "duration_min": 1, "reasons": [],
    }


def test_live_coach_cannot_close_before_room_gate_is_ready():
    rooms = {"living": _room(close_decision_ready=False)}
    out = refine_live_recommendation(rooms, _options(), _recommendation())
    assert out["kind"] == "continue"


def test_live_coach_may_close_after_room_gate_is_ready():
    rooms = {"living": _room(close_decision_ready=True)}
    out = refine_live_recommendation(rooms, _options(), _recommendation())
    assert out["kind"] == "close"


def test_final_consolidation_blocks_unreleased_downstream_close():
    rooms = {"living": _room(close_decision_ready=False)}
    out = stabilise_recommendation(_recommendation("close"), rooms, _options())
    assert out["kind"] == "continue"
    assert "unreleased_close_blocked" in out["consolidation_checks"]


def test_final_consolidation_preserves_physical_room_close():
    rooms = {"living": _room(close_decision_ready=True, close_recommended=True, action="Close")}
    out = stabilise_recommendation(_recommendation("continue"), rooms, _options())
    assert out["kind"] == "close"
    assert "close_state_authoritative" in out["consolidation_checks"]


def test_final_consolidation_allows_released_downstream_close():
    rooms = {"living": _room(close_decision_ready=True, close_recommended=False, action="Continue ventilating")}
    out = stabilise_recommendation(_recommendation("close"), rooms, _options())
    assert out["kind"] == "close"
    assert "released_downstream_close_allowed" in out["consolidation_checks"]


def test_final_close_duration_is_immediate_zero_even_with_minimum_duration():
    rooms = {"living": _room(close_decision_ready=True, close_recommended=True, action="Close")}
    rec = _recommendation("close")
    rec["duration_min"] = 3
    out = stabilise_recommendation(rec, rooms, _options())
    assert out["kind"] == "close"
    assert out["duration_min"] == 0.0
    assert "close_duration_forced_zero" in out["consolidation_checks"]


def test_released_downstream_close_duration_is_immediate_zero():
    rooms = {"living": _room(close_decision_ready=True, close_recommended=False, action="Continue ventilating")}
    rec = _recommendation("close")
    rec["duration_min"] = 0
    out = stabilise_recommendation(rec, rooms, _options())
    assert out["kind"] == "close"
    assert out["duration_min"] == 0.0


def test_active_continue_remaining_duration_may_fall_below_minimum():
    rooms = {"living": _room(close_decision_ready=True)}
    rec = _recommendation("continue")
    rec["duration_min"] = 0.5
    out = stabilise_recommendation(rec, rooms, _options())
    assert out["kind"] == "continue"
    assert out["duration_min"] == 0.5
    assert "active_remaining_duration_preserved" in out["consolidation_checks"]


def test_active_continue_zero_remaining_duration_is_not_raised_to_minimum():
    rooms = {"living": _room(close_decision_ready=True)}
    rec = _recommendation("continue")
    rec["duration_min"] = 0
    out = stabilise_recommendation(rec, rooms, _options())
    assert out["kind"] == "continue"
    assert out["duration_min"] == 0.0


def test_new_ventilation_still_obeys_configured_minimum_duration():
    rooms = {"living": _room(active=False, close_decision_ready=False)}
    rec = _recommendation("ventilate")
    rec["duration_min"] = 0.5
    out = stabilise_recommendation(rec, rooms, _options())
    assert out["kind"] == "ventilate"
    assert out["duration_min"] == 3.0
