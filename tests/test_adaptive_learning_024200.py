"""Robustness and behavioural coverage for adaptive learning components."""
from __future__ import annotations

from datetime import datetime, timedelta
import math

from custom_components.freshairiq.routines import (
    expected_source_rate,
    learn_response_pattern,
    learn_source_pattern,
    project_generation_ml,
    response_pattern,
    routine_bucket_key,
    routine_maturity,
)
from custom_components.freshairiq.seasonality import (
    learn_seasonal_source,
    season_key,
    seasonal_adjust_rate,
    seasonal_context,
    seasonal_house_maturity,
)
from custom_components.freshairiq.strategy import (
    household_strategy_fit,
    learn_strategy_opportunity,
    learn_strategy_outcome,
    strategy_fit,
    strategy_key,
    strategy_maturity,
)


def test_routine_learning_throttles_and_clamps():
    room = {}
    when = datetime(2026, 9, 14, 8, 0)
    assert routine_bucket_key(when) == "weekday_08"
    assert learn_source_pattern(room, when, 100.0) is True
    assert expected_source_rate(room, when) == (35.0, 1)
    assert learn_source_pattern(room, when + timedelta(minutes=5), 1.0) is False
    assert learn_source_pattern(room, when + timedelta(minutes=20), -99.0) is True
    value, samples = expected_source_rate(room, when)
    assert samples == 2
    assert -5.0 <= value <= 35.0


def test_routine_corrupt_persistence_is_repaired_or_ignored():
    when = datetime(2026, 9, 14, 9, 0)
    room = {"routine_source_buckets": [], "routine_response_buckets": "broken"}
    assert routine_maturity(room) == 0.0
    assert expected_source_rate(room, when) == (None, 0)
    assert response_pattern(room, when) is None
    assert learn_source_pattern(room, when, 2.0)
    learn_response_pattern(room, when, True, 250)
    assert isinstance(room["routine_source_buckets"], dict)
    assert isinstance(room["routine_response_buckets"], dict)
    assert response_pattern(room, when)["avg_delay_min"] == 180.0


def test_project_generation_uses_fallback_and_bounds_horizon():
    start = datetime(2026, 9, 14, 12, 0)
    room = {"key": "living", "forecast_source_rate_ml_min": 2.0}
    total, maturity = project_generation_ml([room], start, 30)
    assert total == 60.0
    assert maturity == 0.0
    assert project_generation_ml([], start, 30) == (0.0, 0.0)
    capped, _ = project_generation_ml([room], start, 9999)
    assert capped == 1440.0


def test_seasonality_handles_stale_and_corrupt_values():
    now = datetime(2026, 7, 15, 12, 0)
    room = {"seasonal_source_profiles": []}
    learn_seasonal_source(room, now, 100.0)
    assert season_key(now) == "summer"
    assert room["seasonal_source_profiles"]["summer"]["rate_ml_min"] == 35.0
    context = seasonal_context(room, now)
    assert context["season"] == "summer"
    assert 0.70 <= context["factor"] <= 1.45

    room["long_term_source_ml_min"] = float("nan")
    context = seasonal_context(room, now)
    assert math.isfinite(context["factor"])
    assert math.isfinite(context["long_term_rate_ml_min"])

    stale = now - timedelta(days=365)
    room["seasonal_source_profiles"]["summer"]["last_seen"] = stale.isoformat()
    assert seasonal_context(room, now)["maturity"] < context["maturity"]


def test_seasonal_adjust_and_house_maturity_are_bounded():
    now = datetime(2026, 1, 10, 10, 0)
    room = {}
    for i in range(30):
        learn_seasonal_source(room, now + timedelta(minutes=i), 4.0)
    adjusted, context = seasonal_adjust_rate(room, now, 3.0)
    assert adjusted >= 0
    assert 0 <= context["maturity"] <= 100
    assert 0 <= seasonal_house_maturity([room, {}], now) <= 100
    assert seasonal_house_maturity([], now) == 0.0


def test_strategy_learning_and_corrupt_bucket_recovery():
    room = {"strategy_buckets": []}
    assert strategy_key("wait_30", 5) == "wait_30|short"
    assert strategy_key("night", 10) == "night|medium"
    assert strategy_key("ventilate", 20) == "now|long"
    assert strategy_key(None, None) == "now|none"

    learn_strategy_opportunity(room, "ventilate", 10, True, 999)
    learn_strategy_outcome(room, "ventilate", 10, successful=True)
    fit = strategy_fit(room, "ventilate", 10)
    assert 0.15 <= fit["fit"] <= 0.90
    assert 0 <= fit["maturity"] <= 100
    row = room["strategy_buckets"]["now|medium"]
    assert row["avg_follow_delay_min"] == 180.0
    assert row["success_rate"] == 100.0


def test_strategy_maturity_and_household_weighting():
    room_a, room_b = {}, {}
    for _ in range(20):
        learn_strategy_opportunity(room_a, "ventilate", 10, True, 2)
        learn_strategy_outcome(room_a, "ventilate", 10, successful=True)
    for _ in range(8):
        learn_strategy_opportunity(room_b, "ventilate", 10, False)
        learn_strategy_outcome(room_b, "ventilate", 10, successful=False)
    assert strategy_maturity(room_a) > 0
    combined = household_strategy_fit([room_a, room_b], "ventilate", 10)
    assert 0.15 <= combined["fit"] <= 0.90
    assert combined["maturity"] > 0
    assert household_strategy_fit([{}], "ventilate", 10)["fit"] == 0.5
