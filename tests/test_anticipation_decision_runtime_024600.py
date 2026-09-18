from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

import custom_components.freshairiq.anticipation as anticipation
import custom_components.freshairiq.decision as decision
from custom_components.freshairiq.runtime import (
    clear_runtime_coordinator,
    get_runtime_coordinator,
    set_runtime_coordinator,
)


def _room(**overrides):
    base = {
        "key": "living",
        "name": "Wohnzimmer",
        "data_quality": "ok",
        "calculation_enabled": True,
        "active": False,
        "humidity": 60.0,
        "absolute_humidity": 10.0,
        "volume_m3": 60.0,
        "routine_expected_source_ml_min": 0.3,
        "forecast_source_rate_ml_min": 0.3,
        "realistic_potential_ml": 120.0,
        "potential_ml": 140.0,
        "delta_g_m3": 2.0,
        "surface_rh": 70.0,
        "co2": 800,
        "co2_available": True,
        "humidity_trend_pct_h": 0.5,
        "learned_exchange_rate_per_min": 0.05,
        "airflow_factor": 1.0,
        "temperature": 22.0,
        "forecast_temperature_change_c": -0.5,
        "forecast_cost": 0.02,
        "forecast_confidence": 85,
        "forecast_horizon_min": 10,
        "outcome_feedback_samples": 8,
        "outcome_removed_factor": 1.1,
        "outcome_temperature_factor": 1.0,
    }
    base.update(overrides)
    return base


def _options(**overrides):
    base = {
        "start_rh": 62.0,
        "high_rh": 68.0,
        "min_potential_room_ml": 100.0,
        "min_duration_min": 3.0,
        "max_duration_min": 15.0,
        "mould_warn_surface_rh": 80.0,
        "mould_critical_surface_rh": 90.0,
        "co2_warn": 1000.0,
        "co2_critical": 1400.0,
    }
    base.update(overrides)
    return base


def test_anticipation_numeric_guards_and_future_rh():
    assert anticipation._f("nan", 7.0) == 7.0
    assert anticipation._f(float("inf"), 8.0) == 8.0
    assert anticipation._f("bad", 9.0) == 9.0
    assert anticipation._clamp(120, 0, 100) == 100
    assert anticipation._future_rh(_room(absolute_humidity=0), 100) == 60.0
    assert 60 < anticipation._future_rh(_room(), 120) <= 100


def test_predict_room_event_guards_and_event(monkeypatch):
    now = datetime(2026, 9, 14, 6, 0)
    assert anticipation.predict_room_event(_room(data_quality="bad"), _options(), now) is None
    assert anticipation.predict_room_event(_room(calculation_enabled=False), _options(), now) is None
    assert anticipation.predict_room_event(_room(active=True), _options(), now) is None

    values = iter([(20.0, 10.0), (150.0, 70.0)])
    monkeypatch.setattr(anticipation, "project_generation_ml", lambda *a, **k: next(values))
    event = anticipation.predict_room_event(_room(), _options(), now, horizons=(15, 30))
    assert event is not None
    assert event["horizon_min"] == 30
    assert event["confidence"] >= 55
    assert event["pre_vent_useful"] is True


def test_anticipation_state_and_refinement(monkeypatch):
    now = datetime(2026, 9, 14, 6, 0)
    monkeypatch.setattr(anticipation, "project_generation_ml", lambda *a, **k: (180.0, 80.0))
    rooms = {"living": _room()}
    state = anticipation.build_anticipation_state(rooms, _options(), now)
    assert state["active"] is True
    assert state["primary"]["room_key"] == "living"

    base = {"kind": "okay", "reasons": []}
    out = anticipation.refine_with_anticipation(base, rooms, _options(), now)
    assert out["kind"] == "prepare"
    assert out["anticipatory_action"] is True
    assert out["room_keys"] == ["living"]

    locked = anticipation.refine_with_anticipation({"kind": "close"}, rooms, _options(), now)
    assert locked["kind"] == "close"

    rooms_low = {"living": _room(realistic_potential_ml=10.0, potential_ml=10.0)}
    obs = anticipation.refine_with_anticipation(base, rooms_low, _options(), now)
    assert obs.get("anticipatory_observation") is True


def test_anticipation_no_event_summary(monkeypatch):
    monkeypatch.setattr(anticipation, "project_generation_ml", lambda *a, **k: (0.0, 0.0))
    state = anticipation.build_anticipation_state({"living": _room()}, _options(), datetime(2026, 9, 14, 6))
    assert state["active"] is False
    assert state["events"] == []


def test_decision_numeric_health_and_behaviour_guards():
    assert decision._f("nan", 4.0) == 4.0
    assert decision._f(float("inf"), 5.0) == 5.0
    assert 0 <= decision._exchange_fraction(0.05, 10, 1.0) <= 0.92
    assert decision._health_pressure(_room(humidity=75, surface_rh=92, co2=1600), _options()) >= 90
    duration, reason = decision._behaviour_duration(8, [_room(behaviour_duration_samples=10, behaviour_avg_duration_deviation_min=4)], _options())
    assert duration > 8
    assert reason and "Lernmodell" in reason
    duration2, reason2 = decision._behaviour_duration(8, [_room()], _options())
    assert duration2 == 8
    assert reason2 is None


def test_decision_simulation_and_duration_optimisation():
    room = _room()
    sim = decision._simulate_ventilation([room], 10)
    assert sim["removed_ml"] > 0
    assert sim["temperature_change_c"] < 0
    sim_future = decision._simulate_ventilation([room], 10, source_ah=6.0, source_temp_c=15.0)
    assert sim_future["removed_ml"] > 0
    assert sim_future["temperature_change_c"] < 0
    duration, opt_sim, meta = decision._optimise_duration([room], 8, _options(), 40)
    assert 3 <= duration <= 15
    assert opt_sim["removed_ml"] >= 0
    assert meta["duration_optimised_min"] == duration
    assert "extra_5_min_ml" in meta


def test_decision_builds_matrix_with_weather_routine_and_night(monkeypatch):
    now = datetime(2026, 9, 14, 6, 0)
    monkeypatch.setattr(decision, "project_generation_ml", lambda rooms, now, delay: (40.0 + delay, 50.0))
    monkeypatch.setattr(decision, "household_strategy_fit", lambda *a, **k: {"maturity": 50, "fit": 0.7, "follow": 0.8, "success": 0.75})
    rec = {"kind": "ventilate", "room_keys": ["living"], "duration_min": 8, "reasons": []}
    future = {15: {"absolute_humidity": 5.0, "temperature_c": 18.0, "humidity": 55, "confidence": 80}}
    out = decision.build_decision_simulation(
        {"living": _room(behaviour_duration_samples=10, behaviour_avg_duration_deviation_min=2)},
        _options(), rec, future_outdoor=future, night_forecast_ml=120, night_confidence=70, now=now,
    )
    assert out["decision_engine"] == "v6"
    assert len(out["simulated_options"]) == 5
    assert out["future_weather_used"] is True
    assert out["selected_option_id"] is not None


def test_decision_locked_or_missing_room_preserves_recommendation():
    rec = {"kind": "close", "room_keys": ["living"], "reasons": ["x"]}
    out = decision.build_decision_simulation({"living": _room()}, _options(), rec)
    assert out["kind"] == "close"
    assert out["decision_refined"] is False
    missing = decision.build_decision_simulation({}, _options(), {"kind": "ventilate", "room_keys": ["missing"]})
    assert missing["simulated_options"] == []
    assert missing["selected_option_id"] is None


class _Hass:
    def __init__(self):
        self.data = {}


class _Entry:
    def __init__(self, entry_id="abc"):
        self.entry_id = entry_id
        self.runtime_data = None


def test_runtime_coordinator_uses_config_entry_runtime_data_only():
    hass = _Hass()
    entry = _Entry()
    coordinator = object()
    set_runtime_coordinator(hass, entry, coordinator)
    assert entry.runtime_data is coordinator
    assert get_runtime_coordinator(hass, entry) is coordinator
    clear_runtime_coordinator(hass, entry)
    assert entry.runtime_data is None

    missing = SimpleNamespace(entry_id="missing")
    with pytest.raises(RuntimeError, match="no loaded runtime_data"):
        get_runtime_coordinator(hass, missing)

def test_iter_runtime_coordinators_reads_runtime_data_and_deduplicates():
    from custom_components.freshairiq.runtime import iter_runtime_coordinators

    coordinator = object()
    entry = SimpleNamespace(runtime_data=coordinator)
    config_entries = SimpleNamespace(async_entries=lambda domain: [entry])
    second = object()
    entry2 = SimpleNamespace(runtime_data=second)
    config_entries = SimpleNamespace(async_entries=lambda domain: [entry, entry, entry2])
    hass = SimpleNamespace(config_entries=config_entries)
    items = iter_runtime_coordinators(hass)
    assert items == [coordinator, second]


def test_iter_runtime_coordinators_tolerates_missing_config_entries_api():
    from custom_components.freshairiq.runtime import iter_runtime_coordinators

    assert iter_runtime_coordinators(SimpleNamespace()) == []

    empty = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda domain: []),
    )
    assert iter_runtime_coordinators(empty) == []
