from __future__ import annotations

from datetime import datetime, timedelta

import custom_components.freshairiq.forecast_validation as fv
import custom_components.freshairiq.intelligence as intelligence
import custom_components.freshairiq.shadow_learning as shadow


class BadFloat:
    def __float__(self):
        raise OverflowError


def _frozen_context(**args_overrides):
    args = {
        "current_ah": 12.0,
        "source_ah": 7.0,
        "current_temp_c": 21.0,
        "source_temp_c": 10.0,
        "volume_m3": 50.0,
        "rate_per_min": 0.03,
        "airflow_bonus": 1.0,
    }
    args.update(args_overrides)
    return {
        "version": fv.START_FORECAST_CONTEXT_VERSION,
        "forecast_args": args,
        "target_ah": 10.0,
        "controls": {
            "min_return_next_5_min_ml": 25.0,
            "max_temp_loss_next_5_min_c": 0.6,
            "min_efficiency_ml_per_01c": 8.0,
            "min_duration_min": 3.0,
            "max_duration_min": 20.0,
            "operating_profile": "comfort",
        },
        "energy_options": {},
    }


def test_validation_start_replay_guards_boundaries_and_duration_cost(monkeypatch):
    assert fv.evaluate_start_forecast_at_duration(None, 5) is None
    assert fv.evaluate_start_forecast_at_duration({"version": 999}, 5) is None
    assert fv.evaluate_start_forecast_at_duration(_frozen_context(), BadFloat()) is None
    assert fv.evaluate_start_forecast_at_duration(_frozen_context(), 0) is None
    assert fv.evaluate_start_forecast_at_duration({"version": 2, "forecast_args": {}}, 5) is None

    ctx = _frozen_context(future_source_boundaries={"bad": {}, "5": {"absolute_humidity": 6.0}})
    monkeypatch.setattr(
        fv,
        "horizon_forecast",
        lambda **kwargs: {
            "net_moisture_change_ml": 42.0,
            "temperature_change_c": 0.2,
            "confidence": 77,
            "method": "test",
            "temperature_path": [],
        },
    )
    called = {}

    def fake_cost(*args, **kwargs):
        called["duration"] = args[4]
        return (1.0, 1.0, 9.99)

    monkeypatch.setattr(fv, "ventilation_cost_for_duration", fake_cost)
    out = fv.evaluate_start_forecast_at_duration(ctx, 7)
    assert out is not None
    assert out["predicted_cost"] == 0.0  # positive temperature change has no reheat cost
    assert called["duration"] == 7.0


def test_validation_comparability_direction_timeline_and_empty_records():
    assert fv.prediction_duration_comparable("bad", 15) is False
    assert fv._same_direction(2.0, -2.0) is True
    assert fv._same_direction(2.0, 20.0) is False
    assert fv._timeline_rows({"forecast_timeline": ["bad"]}, 10.0, 1.0) == []

    empty = fv.build_validation_record(
        {"started_at": "2026-09-15T08:00:00", "ended_at": "2026-09-15T08:10:00"},
        ["bad"],
        model_version="x",
    )
    assert empty["valid"] is False
    assert "Keine Startprognose" in empty["invalid_reason"]
    no_sessions = fv.build_validation_record({}, [], model_version="x")
    assert "Keine abgeschlossenen" in no_sessions["invalid_reason"]


def test_validation_history_and_summary_reject_corrupt_rows(monkeypatch):
    now = datetime(2026, 9, 15, 9, 0)
    records = [
        "bad",
        {"ended_at": "broken"},
        {"ended_at": now.isoformat(), "valid": False},
    ]
    kept = fv.prune_validation_history(records, now)
    assert len(kept) == 1

    # A valid row with corrupt timestamp exercises the defensive anchor fallback,
    # while corrupt rows/rooms are ignored instead of poisoning diagnostics.
    summary = fv.validation_summary([
        "bad",
        {"valid": True, "ended_at": "broken", "room_results": ["bad"]},
        {"valid": False, "ended_at": "also-broken"},
    ])
    assert summary["valid_record_count"] == 0
    assert summary["rooms"] == []

    summary2 = fv.validation_summary(["bad", {"valid": False, "ended_at": now.isoformat()}])
    assert summary2["valid_record_count"] == 0


def _feedback_room(**overrides):
    room = {
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": 100.0,
        "session_predicted_temperature_change_c": -1.0,
        "session_selected_option_id": "now",
        "session_recommended_duration_min": 10,
    }
    room.update(overrides)
    return room


def test_intelligence_finalize_and_invalid_age_paths():
    now = datetime(2026, 9, 15, 8, 0)
    assert intelligence._iso_age_minutes(None, now) is None
    store = {"iq_active_advice": "bad"}
    intelligence._finalize_advice(store)

    store = {
        "rooms": {"bad": "not-a-room", "missed": {}},
        "iq_active_advice": {
            "room_keys": ["bad", "missed"],
            "followed_room_keys": [],
            "issued_at": "broken",
        },
    }
    intelligence._finalize_advice(store)
    assert store["rooms"]["missed"]["recommendation_missed"] == 1


def test_intelligence_feedback_all_weight_and_shadow_action_paths(monkeypatch):
    # Corrupt learning weight must fall back to full weight.
    room = _feedback_room(session_prediction_learning_weight=BadFloat())
    monkeypatch.setattr(intelligence, "process_shadow_feedback", lambda *a, **k: {"action": "observing"})
    assert intelligence.learn_outcome_feedback(room, 75.0, -0.7)
    assert room["last_outcome_feedback_action"] == "applied"

    # Moderate but clearly inaccurate sample enters cautious direct temperature update.
    room2 = _feedback_room(session_predicted_removed_ml=100.0)
    assert intelligence.learn_outcome_feedback(room2, 50.0, -0.6)
    assert room2["last_outcome_feedback_action"] == "cautious"

    # Fractionally weighted held frames first accumulate, then advance shadow evidence.
    called = {"n": 0}
    def fake_shadow(*a, **k):
        called["n"] += 1
        return {"action": "observing"}
    monkeypatch.setattr(intelligence, "process_shadow_feedback", fake_shadow)
    held = _feedback_room(session_prediction_learning_weight=0.35)
    assert intelligence.learn_outcome_feedback(held, 95.0, -0.8)
    assert called["n"] == 0
    held["shadow_learning_weight_accumulator"] = 0.8
    assert intelligence.learn_outcome_feedback(held, 95.0, -0.8)
    assert called["n"] == 1

    # Shadow promotion and rollback are authoritative learning actions.
    for action, expected in (("promoted", "shadow_promoted"), ("rollback", "shadow_rollback")):
        monkeypatch.setattr(intelligence, "process_shadow_feedback", lambda *a, _action=action, **k: {"action": _action})
        candidate = _feedback_room()
        assert intelligence.learn_outcome_feedback(candidate, 95.0, -0.8)
        assert candidate["last_outcome_feedback_action"] == expected
        assert candidate["last_outcome_feedback_applied"] is True


def test_intelligence_state_top_maturity_and_anticipation_activity(monkeypatch):
    # Force component maturities so presentation-only high maturity branches are covered.
    monkeypatch.setattr(intelligence, "routine_maturity", lambda r: 90.0)
    monkeypatch.setattr(intelligence, "strategy_maturity", lambda r: 90.0)
    monkeypatch.setattr(intelligence, "seasonal_house_maturity", lambda r, now: 90.0)
    room = {
        "calculation_enabled": True,
        "data_quality": "ok",
        "learning_samples": 20,
        "behaviour_duration_samples": 20,
        "outcome_feedback_samples": 5,
    }
    rec = {
        "kind": "okay",
        "forecast_confidence": 95,
        "house_strategy": {"maturity": 90},
        "anticipation": {"active": True},
        "anticipatory_action": True,
        "day_night_plan": {"active": True},
        "consolidation_checks": ["ok"],
    }
    state = intelligence.build_intelligence_state(
        {"r": room}, rec,
        forecast_confidence=95, overnight_confidence=95, presence_confidence=95,
        night_samples=12, now=datetime(2026, 9, 15),
    )
    assert state["learning_label"] == "Auf deine Bedürfnisse optimiert"
    assert state["mode"] == "predicting"
    assert "Tagesroutinen berücksichtigt" in state["activities"] or "Hausstrategie berücksichtigt" in state["activities"]

    rec2 = dict(rec)
    rec2.pop("anticipatory_action")
    state2 = intelligence.build_intelligence_state(
        {"r": room}, rec2, forecast_confidence=95, overnight_confidence=95,
        presence_confidence=95, night_samples=12, now=datetime(2026, 9, 15),
    )
    assert state2["headline"] == "Routineentwicklung vorausberechnen"


def test_shadow_invalid_confirmation_no_promotion_and_clamped_no_change():
    room = {"outcome_removed_factor": 1.0, "outcome_feedback_samples": 20}
    shadow.ensure_shadow_defaults(room)
    assert shadow.process_shadow_feedback(room, predicted_removed_ml="bad", actual_removed_ml=1)["action"] == "skipped"

    # Finish a rollback guard where the promoted model remains at least as good.
    guarded = {
        "outcome_removed_factor": 1.1,
        "outcome_feedback_samples": 20,
        "shadow_rollback_active": True,
        "shadow_rollback_previous_factor": 1.0,
        "shadow_rollback_promoted_factor": 1.1,
        "shadow_rollback_samples": 4,
        "shadow_rollback_active_error": 0.0,
        "shadow_rollback_previous_error": 40.0,
        "shadow_rollback_previous_wins": 0,
    }
    shadow.ensure_shadow_defaults(guarded)
    result = shadow.process_shadow_feedback(guarded, predicted_removed_ml=110, actual_removed_ml=110)
    assert result["action"] == "promotion_confirmed"

    # Force a mature competition where baseline is still the winner -> no promotion.
    no_promotion = {"outcome_removed_factor": 1.0, "outcome_feedback_samples": 20, "shadow_learning_samples": 15}
    shadow.ensure_shadow_defaults(no_promotion)
    no_promotion["shadow_learning_candidates"] = {
        f"{m:.3f}": {"samples": 15, "abs_error": (100.0 if m == 1.0 else 1000.0), "sq_error": 0.0, "wins": 0}
        for m in shadow._SHADOW_MULTIPLIERS
    }
    result = shadow.process_shadow_feedback(no_promotion, predicted_removed_ml=100, actual_removed_ml=110)
    assert result["action"] == "no_promotion"

    # A winning >1 multiplier cannot move a production factor beyond its hard 1.55 cap.
    no_change = {"outcome_removed_factor": 1.55, "outcome_feedback_samples": 20, "shadow_learning_samples": 7}
    shadow.ensure_shadow_defaults(no_change)
    no_change["shadow_learning_candidates"] = {
        "0.850": {"samples": 7, "abs_error": 1000, "sq_error": 0, "wins": 0},
        "0.925": {"samples": 7, "abs_error": 1000, "sq_error": 0, "wins": 0},
        "1.000": {"samples": 7, "abs_error": 800, "sq_error": 0, "wins": 0},
        "1.075": {"samples": 7, "abs_error": 10, "sq_error": 0, "wins": 7},
        "1.150": {"samples": 7, "abs_error": 1000, "sq_error": 0, "wins": 0},
    }
    result = shadow.process_shadow_feedback(no_change, predicted_removed_ml=100, actual_removed_ml=107.5)
    assert result["action"] == "no_change"
