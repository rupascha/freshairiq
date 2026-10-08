from custom_components.freshairiq.learning_components import build_learning_components_status


def test_learning_components_expose_each_adaptive_subsystem_independently():
    rooms = {
        "wohn": {
            "calculation_enabled": True,
            "learning_samples": 10,
            "outcome_feedback_samples": 6,
            "outcome_success_rate": 80,
            "routine_source_samples": 12,
            "routine_maturity": 60,
            "seasonal_samples": 24,
            "seasonal_maturity": 80,
            "strategy_samples": 9,
            "strategy_maturity": 30,
            "strategy_outcome_samples": 4,
            "forecast_observation_samples": 6,
            "behaviour_recommendation_opportunities": 10,
            "behaviour_recommendation_followed": 8,
            "behaviour_duration_samples": 6,
        },
        "bad": {
            "calculation_enabled": True,
            "learning_samples": 5,
            "outcome_feedback_samples": 2,
            "outcome_success_rate": 50,
            "routine_source_samples": 4,
            "routine_maturity": 20,
            "seasonal_samples": 6,
            "seasonal_maturity": 20,
            "strategy_samples": 0,
            "strategy_maturity": 0,
            "strategy_outcome_samples": 0,
            "forecast_observation_samples": 3,
            "behaviour_recommendation_opportunities": 5,
            "behaviour_recommendation_followed": 1,
            "behaviour_duration_samples": 2,
        },
    }
    result = build_learning_components_status(
        rooms,
        {"night_model_samples": 10, "house_strategy_samples": 18},
        forecast_backtest={
            "room_sample_count": 8,
            "overall": {"moisture_mae_ml": 22},
            "reliability": {"score_percent": 81, "evidence_maturity_percent": 40},
        },
        post_close_stabilization={"valid_observations": 5, "average_buffer_fraction_percent": 18},
    )
    keys = {item["key"] for item in result["components"]}
    assert keys == {
        "room_physics", "live_forecast", "forecast_feedback", "shadow_learning", "routines", "seasonality", "user_strategy",
        "personal_context", "night_model", "house_strategy", "forecast_validation", "post_close",
    }
    by_key = {item["key"]: item for item in result["components"]}
    assert by_key["room_physics"]["samples"] == 15
    assert by_key["live_forecast"]["samples"] == 9
    assert by_key["live_forecast"]["maturity_percent"] == 0.0
    assert by_key["personal_context"]["samples"] == 8
    assert by_key["personal_context"]["maturity_percent"] == 0.0
    assert "60 % umgesetzt" in by_key["personal_context"]["detail"]
    assert "8 Lüftungsdauern" in by_key["personal_context"]["detail"]
    assert by_key["night_model"]["maturity_percent"] == 0.0
    assert by_key["night_model"]["samples"] == 0
    assert "0 unterschiedliche Nächte" in by_key["night_model"]["evidence_text"]
    assert by_key["forecast_validation"]["quality_percent"] == 81.0
    assert by_key["post_close"]["observation_only"] is True
    assert 0 <= result["overall_maturity_percent"] <= 100


def test_learning_components_do_not_confuse_zero_samples_with_accuracy():
    result = build_learning_components_status([], {}, forecast_backtest={}, post_close_stabilization={})
    assert result["component_count"] == 12
    assert all(item["maturity_percent"] == 0 for item in result["components"])
    assert result["components"][0]["status"] == "Grundschätzung"
