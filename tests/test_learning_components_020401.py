from pathlib import Path

from custom_components.freshairiq.learning_components import build_learning_components_status

ROOT = Path(__file__).resolve().parents[1]


def test_all_adaptive_models_are_exposed_with_progress():
    rooms = {
        "room": {
            "calculation_enabled": True,
            "learning_samples": 4,
            "forecast_observation_samples": 3,
            "outcome_feedback_samples": 2,
            "routine_source_samples": 5,
            "routine_maturity": 25,
            "seasonal_samples": 6,
            "seasonal_maturity": 25,
            "strategy_samples": 3,
            "strategy_maturity": 10,
            "strategy_outcome_samples": 1,
            "behaviour_recommendation_opportunities": 5,
            "behaviour_recommendation_followed": 3,
            "behaviour_duration_samples": 2,
        }
    }
    result = build_learning_components_status(
        rooms,
        {"night_model_samples": 4, "house_strategy_samples": 5},
        forecast_backtest={"room_sample_count": 2},
        post_close_stabilization={"valid_observations": 1},
    )
    components = {row["key"]: row for row in result["components"]}
    expected = {
        "room_physics", "live_forecast", "forecast_feedback", "shadow_learning", "routines",
        "seasonality", "user_strategy", "personal_context", "night_model",
        "house_strategy", "forecast_validation", "post_close",
    }
    assert set(components) == expected
    assert result["component_count"] == len(expected)
    for row in components.values():
        assert 0 <= row["maturity_percent"] <= 100
        assert row["target_samples"] >= 1
        assert "status" in row and row["status"]
        assert "description" in row and row["description"]


def test_release_version_020401_is_consistent():
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    manifest = (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    frontend = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'VERSION = "0.25.0.73"' in const
    assert '"version": "0.25.0.73"' in manifest
    assert 'const FAIQ_VERSION = "0.25.0.73";' in frontend
