from datetime import date, timedelta
from custom_components.freshairiq.learning_components import build_learning_components_status


def dates(n):
    start=date(2026,1,1)
    return [(start+timedelta(days=i)).isoformat() for i in range(n)]


def test_house_strategy_many_sessions_one_day_cannot_look_mature():
    out=build_learning_components_status([], {"house_strategy_samples":500,"house_strategy_observation_dates":["2026-09-16"]})
    row={x["key"]:x for x in out["components"]}["house_strategy"]
    assert row["maturity_percent"] <= 2.3
    assert "1 unterschiedliche Tage" in row["evidence_text"]


def test_room_and_personal_models_require_time_breadth():
    room={"calculation_enabled":True,"learning_samples":1000,"forecast_observation_samples":1000,"behaviour_recommendation_opportunities":1000,"behaviour_duration_samples":1000,"learning_observation_dates":dates(5),"personal_context_observation_dates":dates(5)}
    out=build_learning_components_status({"r":room},{})
    rows={x["key"]:x for x in out["components"]}
    assert rows["room_physics"]["maturity_percent"] <= 11.2
    assert rows["live_forecast"]["maturity_percent"] <= 16.7
    assert rows["personal_context"]["maturity_percent"] <= 8.4


def test_validation_requires_independent_days_as_well_as_comparisons():
    out=build_learning_components_status([],{},forecast_backtest={"room_sample_count":500,"distinct_validation_days":2,"reliability":{"score_percent":95},"overall":{"moisture_mae_ml":5}})
    row={x["key"]:x for x in out["components"]}["forecast_validation"]
    assert row["maturity_percent"] <= 6.7
    assert "2 unterschiedliche Tage" in row["evidence_text"]


def test_post_close_requires_day_breadth():
    out=build_learning_components_status([],{},post_close_stabilization={"valid_observations":500,"distinct_observation_days":2,"average_buffer_fraction_percent":20})
    row={x["key"]:x for x in out["components"]}["post_close"]
    assert row["maturity_percent"] == 10.0
