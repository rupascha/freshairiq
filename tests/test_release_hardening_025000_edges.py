from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import custom_components.freshairiq.anticipation as anticipation
import custom_components.freshairiq.consolidation as consolidation
import custom_components.freshairiq.decision as decision
import custom_components.freshairiq.decision_brain as decision_brain
import custom_components.freshairiq.forecast as forecast
import custom_components.freshairiq.forecast_backtest as backtest
import custom_components.freshairiq.house_strategy as house_strategy
import custom_components.freshairiq.intervention as intervention
import custom_components.freshairiq.measurement_frame as measurement_frame
import custom_components.freshairiq.presence as presence
import custom_components.freshairiq.robustness as robustness
import custom_components.freshairiq.seasonality as seasonality
import custom_components.freshairiq.shadow_learning as shadow_learning
import custom_components.freshairiq.strategy as strategy
import custom_components.freshairiq.ventilation_result as ventilation_result


def _room(**overrides):
    room = {
        "key": "r",
        "name": "Raum",
        "data_quality": "ok",
        "calculation_enabled": True,
        "active": False,
        "humidity": 60.0,
        "temperature": 21.0,
        "absolute_humidity": 10.0,
        "reference_absolute_humidity": 7.0,
        "delta_g_m3": 3.0,
        "volume_m3": 50.0,
        "potential_ml": 150.0,
        "realistic_potential_ml": 150.0,
        "surface_rh": 70.0,
        "co2": 700.0,
        "co2_available": True,
        "learned_exchange_rate_per_min": 0.03,
        "airflow_factor": 1.0,
        "forecast_confidence": 80,
        "forecast_5_min_moisture_effect_ml": 50.0,
        "forecast_5_min_temperature_change_c": -0.2,
        "temperature_change_c": -0.1,
        "result_ml": 20.0,
    }
    room.update(overrides)
    return room


def test_numeric_defensive_edges_and_simple_helpers(monkeypatch):
    # Exception/fallback paths are part of the release contract: persisted and
    # sensor-originating data are not trusted just because the UI validated it.
    class BadFloat:
        def __float__(self):
            raise OverflowError

    assert house_strategy._f(BadFloat(), 9.0) == 9.0
    assert intervention._f(BadFloat(), 8.0) == 8.0
    assert seasonality._f(BadFloat(), 7.0) == 7.0
    assert robustness.finite_int(BadFloat(), 6) == 6

    assert seasonality.season_key(datetime(2026, 4, 1)) == "spring"
    assert seasonality._age_weight(None, datetime(2026, 9, 1)) == 0.0
    assert seasonality._age_weight("broken", datetime(2026, 9, 1)) == 0.0

    assert backtest._percentile([], 0.9) is None
    assert backtest._horizon_bucket(20) == "15-30"
    assert backtest._horizon_bucket(31) == "30+"
    assert backtest._confidence_bucket(50) == "0-59"
    assert backtest._confidence_bucket(99) == "95-100"
    assert backtest._checkpoint_bucket(None) == "unknown"
    assert backtest._record_stamp({"ended_at": "broken"}) is None
    scoped = backtest._scope_records(["bad", {"ended_at": "2026-09-14T12:00:00"}], 30)
    assert len(scoped) == 1
    assert backtest._room_samples([
        {"valid": True, "room_results": ["bad", {"comparable": False}]}
    ]) == []


def test_backtest_reliability_all_status_bands_and_timeline_guard():
    assert backtest._reliability_summary([])["status"] == "Keine Vergleichsdaten"
    one = [{"magnitude_accuracy_percent": 90, "direction_correct": True, "forecast_confidence": 90}]
    assert backtest._reliability_summary(one)["status"] == "Erste Daten"

    learning = one * 5
    assert backtest._reliability_summary(learning)["status"] == "Lernt"

    # 10+ samples remove the evidence<50 branch. Vary empirical quality to hit
    # every final label without touching production code.
    very_good = [{"magnitude_accuracy_percent": 100, "direction_correct": True, "forecast_confidence": 100}] * 20
    good = [{"magnitude_accuracy_percent": 85, "direction_correct": True, "forecast_confidence": 85}] * 20
    observe = [{"magnitude_accuracy_percent": 70, "direction_correct": True, "forecast_confidence": 70}] * 20
    unstable = [{"magnitude_accuracy_percent": 20, "direction_correct": False, "forecast_confidence": 90}] * 20
    assert backtest._reliability_summary(very_good)["status"] == "Sehr zuverlässig"
    assert backtest._reliability_summary(good)["status"] in {"Zuverlässig", "Sehr zuverlässig"}
    assert backtest._reliability_summary(observe)["status"] in {"Beobachten", "Zuverlässig"}
    assert backtest._reliability_summary(unstable)["status"] == "Noch instabil"

    samples = [{"actual_removed_ml": 100, "timeline": ["bad", {"checkpoint_min": 5, "predicted_final_removed_ml": 90}]}]
    rows = backtest._timeline_replay(samples)
    assert rows and rows[0]["checkpoint"] == "+5"


def test_robustness_repairs_and_health_counters(monkeypatch):
    assert robustness.prepare_runtime_rooms("bad") == ([], ["rooms_not_a_list"])
    rooms, issues = robustness.prepare_runtime_rooms([{"key": "office", "volume": 20}])
    assert rooms[0]["name"] == "office"
    assert "room:office:missing_name" in issues

    room = {
        "session_predicted_removed_ml": "12.5",
        "session_result_base_ml": float("inf"),
        "session_result_ml": -float("inf"),
    }
    repaired = robustness.sanitize_runtime_session(room)
    assert room["session_predicted_removed_ml"] == 12.5
    assert room["session_result_base_ml"] == 0.0
    assert room["session_result_ml"] == 0.0
    assert "session_predicted_removed_ml" in repaired

    monitor = robustness.RobustnessMonitor()
    monitor.source_event()
    monitor.coalesced_refresh()
    monitor.weather_failure()
    assert (monitor.source_events, monitor.coalesced_refreshes, monitor.weather_fetch_failures) == (1, 1, 1)


def test_house_strategy_neutral_efficiency_branch():
    store = {
        "house_strategy_buckets": {
            "single|normal|normal": {
                "samples": 5,
                "successes": 3,
                "avg_removed_ml_min": 0,
                "avg_cost_per_100ml": 0,
            }
        },
        "house_strategy_samples": 5,
        "house_strategy_total_removed_ml": 0,
        "house_strategy_total_minutes": 100,
    }
    rooms = {"r": {"floor": "ground_floor"}}
    out = house_strategy.house_strategy_fit(store, ["r"], rooms, cross=False, expected_occupants=1)
    assert out["efficiency_factor"] == 1.0


def test_strategy_recovers_non_mapping_outcome_bucket():
    room = {"strategy_buckets": []}
    strategy.learn_strategy_outcome(room, "now", 5, successful=True)
    assert isinstance(room["strategy_buckets"], dict)
    assert room["strategy_buckets"]["now|short"]["outcomes"] == 1


def test_ventilation_group_invalid_existing_start_and_empty_finish():
    group = {"started_at": "broken", "sessions": []}
    candidate = datetime(2026, 9, 15, 8, 0)
    assert ventilation_result.include_ventilation_group_start(group, candidate)
    assert group["started_at"] == candidate.isoformat()
    assert ventilation_result.finalise_ventilation_group({"sessions": []}, candidate) is None


def test_forecast_night_future_boundary_profiles_and_live_cap():
    now = datetime(2026, 9, 15, 8, 0)
    # Non-wrap interval, already past start: next day's interval.
    start, end = forecast.night_interval_bounds(now, 9, 17)
    assert start.date() == now.date()
    assert end > start

    # Cross-midnight branch while currently after the start.
    assert forecast.remaining_night_hours(datetime(2026, 9, 15, 23, 0), 22, 7) > 0

    common = dict(
        current_ah=12.0,
        source_ah=7.0,
        current_temp_c=22.0,
        source_temp_c=10.0,
        volume_m3=50.0,
        rate_per_min=0.05,
        airflow_bonus=1.0,
        horizon_min=5,
        running=True,
        session_elapsed_min=20,
        session_fresh_measurements=2,
        recent_observed_removed_ml_min=50.0,
        target_ah=11.5,
        cap_positive_to_target=True,
    )
    capped = forecast.horizon_forecast(**common)
    assert capped["moisture_effect_ml"] <= 25.0 + 1e-6

    for profile in ("dehumidify", "summer_cooling"):
        out = forecast.horizon_forecast(**{**common, "horizon_min": 15, "running": False, "operating_profile": profile})
        assert out["horizon_min"] == 15.0

    bad_points = {
        5: {"absolute_humidity": "bad", "temperature_c": 5},
        10: {"absolute_humidity": 99, "temperature_c": 5},
        15: {"absolute_humidity": 8, "temperature_c": 5, "confidence": "bad"},
    }
    out = forecast.horizon_forecast(**{**common, "horizon_min": 20, "running": False, "future_source_boundaries": bad_points})
    assert out["simulation_steps"] >= 4


def test_anticipation_no_event_and_refinement_early_exits(monkeypatch):
    room = _room(humidity=50, routine_expected_source_ml_min=0.1)
    monkeypatch.setattr(anticipation, "project_generation_ml", lambda *args, **kwargs: (1.0, 50.0))
    assert anticipation.predict_room_event(room, {"start_rh": 62, "high_rh": 68}, datetime(2026, 9, 15, 8), horizons=(15, 30)) is None

    monkeypatch.setattr(anticipation, "build_anticipation_state", lambda *a, **k: {"active": False})
    assert anticipation.refine_with_anticipation({"kind": "okay"}, {"r": room}, {}, datetime.now())["kind"] == "okay"

    monkeypatch.setattr(anticipation, "build_anticipation_state", lambda *a, **k: {"active": True, "primary": {"confidence": 40, "room_key": "r"}})
    assert anticipation.refine_with_anticipation({"kind": "okay"}, {"r": room}, {}, datetime.now())["kind"] == "okay"

    monkeypatch.setattr(anticipation, "build_anticipation_state", lambda *a, **k: {"active": True, "primary": {"confidence": 80, "room_key": "missing"}})
    assert anticipation.refine_with_anticipation({"kind": "okay"}, {"r": room}, {}, datetime.now())["kind"] == "okay"


def test_decision_duration_at_max_and_pollen_penalty(monkeypatch):
    selected = [_room(active=False, outcome_feedback_samples=0)]
    opts = {"min_duration_min": 3, "max_duration_min": 3, "min_potential_room_ml": 100, "high_rh": 68, "mould_warn_surface_rh": 80, "mould_critical_surface_rh": 90, "co2_warn": 1000, "co2_critical": 1400}
    duration, _, meta = decision._optimise_duration(selected, 3, opts, 10)
    assert duration == 3
    assert meta["extra_5_min_ml"] == 0

    # Force the pollen-wait scoring path while preserving a valid simulated option set.
    monkeypatch.setattr(decision, "_optimise_duration", lambda *a, **k: (3.0, {"removed_ml": 100.0, "temperature_change_c": -0.1, "cost": 0.0, "confidence": 80.0}, {"extra_5_min_ml": 0, "outcome_feedback_samples": 0}))
    out = decision.build_decision_simulation({"r": selected[0]}, opts, {"kind": "pollen_wait", "room_keys": ["r"], "duration_min": 3, "reasons": []})
    assert out["simulated_options"]


def test_decision_brain_exposes_next_window_for_non_now_plan():
    rec = {
        "kind": "okay",
        "room_keys": [],
        "summary": "Alles ruhig",
        "day_night_plan": {"active": True, "selected_option_id": "wait_30", "selected_label": "30 min warten"},
    }
    out = decision_brain.build_unified_decision(rec, {}, {})
    assert out["decision_brain"]["alternative"] == "Nächstes interessantes Fenster: 30 min warten"


def test_consolidation_limit_profile_active_authority_and_scopes():
    assert consolidation._unique_text(["a", "b", "c"], limit=2) == ["a", "b"]

    options = {"max_duration_min": 20, "min_return_next_5_min_ml": 25, "max_temp_loss_next_5_min_c": 0.6, "min_efficiency_ml_per_01c": 8, "operating_profile": "summer_cooling"}
    active = _room(active=True, action="Continue", session_elapsed_min=5, key="r")
    out = consolidation.stabilise_recommendation({"kind": "wait", "room_keys": ["r"]}, {"r": active}, options)
    assert out["kind"] == "continue"
    assert "active_session_authoritative" in out["consolidation_checks"]

    # Action without a referenced room is retained only as a consistency warning.
    inactive = _room(active=False, key="r")
    out2 = consolidation.stabilise_recommendation({"kind": "ventilate", "room_keys": []}, {"r": inactive}, options)
    assert "action_without_room_reference" in out2["consolidation_checks"]

    rooms = {
        "a": _room(key="a", floor="ground_floor"),
        "b": _room(key="b", floor="basement"),
    }
    out3 = consolidation.stabilise_recommendation({"kind": "ventilate", "room_keys": ["a", "b"]}, rooms, options)
    assert out3["recommendation_scope"] == "house"


def test_measurement_frame_timestamp_guards():
    class State:
        last_reported = "broken"
        last_updated = "broken"
        last_changed = "broken"

    assert measurement_frame.state_reported_at(None) is None
    assert measurement_frame.state_reported_at(State()) == "broken"
    assert measurement_frame._age_seconds(datetime(2026, 9, 15, 8, 0), State()) is None

    class FutureState:
        last_reported = datetime(2026, 9, 15, 9, 0)
        last_updated = None
        last_changed = None

    now = datetime(2026, 9, 15, 8, 0)
    assert measurement_frame._age_seconds(now, FutureState()) is not None


def test_presence_weird_state_and_deduplication():
    assert presence._unique_entities("bad") == ["bad"]
    assert presence._unique_entities(123) == []
    assert presence._unique_entities(["person.a", "person.a", "", None]) == ["person.a"]
    assert presence._state_kind(None) == "unknown"
    assert presence._state_kind(object()) == "away"

