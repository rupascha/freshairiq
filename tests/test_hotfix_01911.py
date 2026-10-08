from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.consolidation import stabilise_recommendation
from custom_components.freshairiq.live_coach import refine_live_recommendation


def _room_result(**kw):
    base = {
        "key": "living", "name": "Living", "calculation_enabled": True,
        "data_quality": "ok", "active": True, "action": "Close",
        "close_recommended": True, "close_decision_ready": True,
        "session_elapsed_min": 10.0,
        "forecast_5_min_moisture_effect_ml": 20.0,
        "moisture_effect_next_5_min_ml": 20.0,
        "forecast_5_min_temperature_change_c": -0.2,
        "temp_next_5_min_c": -0.2,
        "efficiency_ml_per_01c": 10.0,
        "surface_rh": 60, "co2": None,
    }
    base.update(kw)
    return base


def _rec(kind="close"):
    return {
        "kind": kind, "status": "close_windows" if kind == "close" else "ventilation_running",
        "title": "Jetzt schließen" if kind == "close" else "Lüftung läuft",
        "instruction": "Living schließen", "summary": "test", "room_keys": ["living"],
        "duration_min": 0.0 if kind == "close" else 2.0,
    }


def test_target_rh_alone_does_not_close_while_five_minute_return_is_material():
    options = {
        **DEFAULT_OPTIONS,
        "operating_profile": "dehumidify",
        "min_duration_min": 3,
        "max_duration_min": 20,
        "min_return_next_5_min_ml": 25,
        "target_rh": 58,
    }
    # RH has reached the configured target, but very dry reference air still
    # gives a strong five-minute return. Before 0.19.1.1 this could close solely
    # because target_rh was reached.
    room = RoomInput(
        "living", "Living", 22, 58, 10, 40, 100, True, 600,
        session_active=True, session_elapsed_min=10,
        session_start_temp=22, learning_rate=0.03, session_fresh_measurements=2,
    )
    result = evaluate_room(room, options, False)
    assert result.moisture_effect_next_5_min_ml >= 15
    assert result.action == "Continue ventilating"
    assert not result.close_recommended


def test_aggregate_close_is_blocked_while_combined_short_term_return_is_material():
    options = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "min_return_next_5_min_ml": 25}
    rooms = {
        "a": _room_result(key="a", name="A", forecast_5_min_moisture_effect_ml=9, moisture_effect_next_5_min_ml=9),
        "b": _room_result(key="b", name="B", forecast_5_min_moisture_effect_ml=9, moisture_effect_next_5_min_ml=9),
    }
    rec = {**_rec(), "room_keys": ["a", "b"]}
    out = stabilise_recommendation(rec, rooms, options)
    assert out["kind"] == "continue"
    assert "premature_aggregate_close_blocked" in out["consolidation_checks"]


def test_aggregate_close_remains_allowed_after_marginal_return_falls_low():
    options = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "min_return_next_5_min_ml": 25}
    rooms = {
        "a": _room_result(key="a", name="A", forecast_5_min_moisture_effect_ml=5, moisture_effect_next_5_min_ml=5),
        "b": _room_result(key="b", name="B", forecast_5_min_moisture_effect_ml=4, moisture_effect_next_5_min_ml=4),
    }
    rec = {**_rec(), "room_keys": ["a", "b"]}
    out = stabilise_recommendation(rec, rooms, options)
    assert out["kind"] == "close"
    assert out["duration_min"] == 0.0


def test_hard_max_duration_still_allows_close_despite_high_return():
    options = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "max_duration_min": 20}
    rooms = {"living": _room_result(session_elapsed_min=20, forecast_5_min_moisture_effect_ml=80)}
    out = stabilise_recommendation(_rec(), rooms, options)
    assert out["kind"] == "close"


def test_close_live_coach_sets_remaining_time_to_zero():
    rooms = {"living": _room_result(forecast_5_min_confidence=90)}
    out = refine_live_recommendation(rooms, DEFAULT_OPTIONS, _rec())
    assert out["kind"] == "close"
    assert out["live_coach_remaining_min"] == 0.0
