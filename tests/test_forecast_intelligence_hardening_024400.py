"""Additional edge coverage for forecast and intelligence state."""
from datetime import datetime

from custom_components.freshairiq.forecast import (
    baseline_night_rate_ml_h,
    effective_night_rate_ml_h,
    estimated_daily_moisture_ml,
    night_interval_bounds,
    night_window_hours,
    overnight_forecast_ml,
    remaining_night_hours,
    update_night_learning,
)
from custom_components.freshairiq.intelligence import build_intelligence_state


def test_forecast_time_parsing_and_legacy_prior_edges():
    assert night_window_hours("broken:xx", "07:00") == 9.0
    assert night_window_hours(None, None) == 9.0
    now = datetime(2026, 9, 14, 23, 30)
    start, end = night_interval_bounds(now, "22:00", "07:00")
    assert start == now
    assert end.date().day == 15
    assert remaining_night_hours(datetime(2026, 9, 15, 2, 0), "22:00", "07:00") == 5.0

    legacy = {"occupants": 2, "moisture_g_per_person_hour_night": 50, "background_moisture_g_per_hour": 12}
    assert baseline_night_rate_ml_h(legacy) == 112


def test_forecast_learning_and_daily_moisture_edges():
    opts = {
        "adult_occupants": 2, "child_occupants": 1,
        "adult_night_moisture_ml_h": 45, "child_night_moisture_ml_h": 30,
        "background_night_moisture_ml_h": 10, "property_type": "apartment",
        "adult_day_moisture_ml": 1000, "child_day_moisture_ml": 700, "household_day_moisture_ml": 1000,
        "night_start_hour": "22:00", "night_end_hour": "07:00",
    }
    base = baseline_night_rate_ml_h(opts, adults=1, children=0)
    assert base > 0
    assert effective_night_rate_ml_h(opts, None, 0, adults=1, children=0) == base
    learned = effective_night_rate_ml_h(opts, 300, 50, adults=1, children=0)
    assert learned > base
    assert overnight_forecast_ml(opts, None, 0, adults=1, children=0, hours=2) == round(base * 2)
    assert estimated_daily_moisture_ml(opts, adults=0, children=0) < estimated_daily_moisture_ml(opts, adults=2, children=1)
    assert update_night_learning(None, 0, 120) == (120.0, 1)
    updated, samples = update_night_learning(100, 20, 500)
    assert samples == 21
    assert 100 < updated <= 105


def _room(samples, behaviour, *, quality="ok", routine=0, strategy=0, seasonal=0, outcome=0):
    return {
        "calculation_enabled": True,
        "data_quality": quality,
        "learning_samples": samples,
        "behaviour_duration_samples": behaviour,
        "routine_source_buckets": {"x": {"samples": routine}} if routine else {},
        "routine_response_buckets": {},
        "strategy_buckets": {"x": {"samples": strategy, "successes": strategy}} if strategy else {},
        "seasonal_source_profiles": {"summer": {"samples": seasonal}} if seasonal else {},
        "outcome_feedback_samples": outcome,
    }


def test_intelligence_state_confidence_labels_and_unknown_kind():
    invalid = _room(0, 0, quality="bad")
    state = build_intelligence_state({"x": invalid}, {"kind": "mystery"}, forecast_confidence=0, overnight_confidence=0, presence_confidence=0, night_samples=0, now=datetime(2026,9,14))
    assert state["confidence"] == 0
    assert state["confidence_label"] == "Noch geringe Sicherheit"
    assert state["mode"] == "analyzing"
    assert state["learning_label"] == "Grundmodell"


def test_intelligence_state_exposes_anticipation_and_plan_activity():
    room = _room(20, 20, outcome=2)
    rec = {
        "kind": "okay",
        "forecast_confidence": 90,
        "future_weather_used": True,
        "anticipation": {"active": True},
        "anticipatory_action": True,
        "day_night_plan": {"active": True},
        "house_strategy": {"maturity": 50},
        "consolidation_checks": ["x"],
    }
    state = build_intelligence_state({"r": room}, rec, forecast_confidence=80, overnight_confidence=80, presence_confidence=80, night_samples=12, now=datetime(2026,9,14))
    assert state["mode"] == "predicting"
    assert state["headline"] == "Bevorstehende Entwicklung erkannt"
    assert len(state["activities"]) <= 4
    assert "Entscheidung konsolidiert" in state["activities"]


def test_intelligence_learning_label_ladder():
    # Learning maturity alone drives the lower labels, with behaviour gating the top stage.
    expected = [
        (2, 0, "Grundmodell"),
        (4, 0, "Beobachtet"),
        (6, 0, "Muster erkannt"),
        (9, 0, "Bestätigt"),
        (13, 0, "Eingelernt"),
        (16, 12, "Sehr gut eingelernt"),
    ]
    for samples, behaviour, label in expected:
        state = build_intelligence_state({"r": _room(samples, behaviour)}, {"kind": "okay", "forecast_confidence": 80}, forecast_confidence=80, overnight_confidence=0, presence_confidence=100, night_samples=0, now=datetime(2026,9,14))
        assert state["learning_label"] == label
