from custom_components.freshairiq.learning_components import build_learning_components_status


def _room(n: int, *, success: float = 88.0):
    return {
        "calculation_enabled": True,
        "learning_samples": n,
        "forecast_observation_samples": n,
        "outcome_feedback_samples": n,
        "outcome_success_rate": success,
        "routine_source_samples": n,
        "routine_maturity": min(100, n * 2),
        "seasonal_samples": n,
        "seasonal_maturity": min(100, n * 2),
        "strategy_samples": n,
        "strategy_maturity": min(100, n * 2),
        "strategy_outcome_samples": n,
        "behaviour_recommendation_opportunities": n,
        "behaviour_recommendation_followed": int(n * .8),
        "behaviour_duration_samples": n,
    }


def test_intelligence_2_does_not_finish_after_a_handful_of_events():
    status = build_learning_components_status({"room": _room(6)}, {"night_model_samples": 6, "house_strategy_samples": 6}, forecast_backtest={"room_sample_count": 6, "reliability": {"score_percent": 90, "evidence_maturity_percent": 12}})
    assert status["version"] == "v5"
    assert status["overall_maturity_percent"] < 30
    assert status["stage_key"] in {"grundmodell", "beobachtet"}
    assert status["personal_optimization_ready"] is False


def test_top_stage_requires_personal_evidence_and_validated_quality():
    rooms = {"room": _room(80)}
    common = {"night_model_samples": 80, "house_strategy_samples": 100}
    weak = build_learning_components_status(rooms, common, forecast_backtest={"room_sample_count": 80, "reliability": {"score_percent": 70, "evidence_maturity_percent": 100}})
    strong = build_learning_components_status(rooms, common, forecast_backtest={"room_sample_count": 120, "reliability": {"score_percent": 90, "evidence_maturity_percent": 100}})
    assert weak["stage_key"] != "auf_beduerfnisse_optimiert"
    assert strong["stage_key"] != "auf_beduerfnisse_optimiert"
    assert strong["personal_optimization_ready"] is False
    # Large raw counters alone are no longer allowed to impersonate calendar experience.
