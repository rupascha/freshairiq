"""Coverage and persistence hardening for house-wide strategy learning."""
from __future__ import annotations

from custom_components.freshairiq.house_strategy import (
    house_maturity,
    house_strategy_fit,
    learn_house_outcome,
    occupancy_bucket,
    strategy_signature,
)

ROOMS = {
    "a": {"floor": "EG"},
    "b": {"floor": "EG"},
    "c": {"floor": "KG"},
}


def test_signature_covers_scope_cross_and_occupancy():
    assert occupancy_bucket(0) == "away"
    assert occupancy_bucket(2) == "normal"
    assert occupancy_bucket(3) == "busy"
    assert strategy_signature(["a"], ROOMS, cross=False, expected_occupants=0) == "single|normal|away"
    assert strategy_signature(["a", "b"], ROOMS, cross=True, expected_occupants=2) == "same_floor|cross|normal"
    assert strategy_signature(["a", "c"], ROOMS, cross=False, expected_occupants=4) == "multi_floor|normal|busy"


def test_house_learning_preserves_bad_signed_outcome_and_recovers_corrupt_bucket_store():
    store = {"house_strategy_buckets": []}
    events = [{"key": "a", "duration_min": 10, "removed_ml": -120, "predicted_removed_ml": 100, "cost": 0.2}]
    assert learn_house_outcome(store, events, ROOMS, cross=False, expected_occupants=2)
    assert store["house_strategy_total_removed_ml"] == -120.0
    assert isinstance(store["house_strategy_buckets"], dict)
    row = next(iter(store["house_strategy_buckets"].values()))
    assert row["success_rate"] == 0.0
    assert row["avg_removed_ml"] == -120.0


def test_house_learning_rejects_too_short_batches_and_nonfinite_values_safely():
    store = {}
    assert not learn_house_outcome(store, [{"key": "a", "duration_min": 0.5}], ROOMS, cross=False, expected_occupants=1)
    events = [{"key": "a", "duration_min": 5, "removed_ml": float("nan"), "predicted_removed_ml": float("inf"), "cost": float("nan")}]
    assert learn_house_outcome(store, events, ROOMS, cross=False, expected_occupants=1)
    row = next(iter(store["house_strategy_buckets"].values()))
    assert row["avg_removed_ml"] == 0.0
    assert row["avg_cost_per_100ml"] == 0.0


def test_house_fit_moves_with_repeated_success_and_maturity():
    store = {}
    event = {"key": "a", "duration_min": 10, "removed_ml": 120, "predicted_removed_ml": 100, "cost": 0.01}
    for _ in range(20):
        assert learn_house_outcome(store, [event], ROOMS, cross=True, expected_occupants=2)
    fit = house_strategy_fit(store, ["a"], ROOMS, cross=True, expected_occupants=2)
    assert fit["maturity"] == 100.0
    assert fit["success_probability"] > 0.8
    assert 0.2 <= fit["fit"] <= 0.9
    assert house_maturity(store) > 0


def test_house_fit_and_maturity_ignore_corrupt_persistence():
    store = {"house_strategy_buckets": "broken"}
    fit = house_strategy_fit(store, ["a"], ROOMS, cross=False, expected_occupants=1)
    assert fit["fit"] == 0.5
    assert fit["samples"] == 0
    assert house_maturity(store) == 0.0
