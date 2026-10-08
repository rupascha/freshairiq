from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from custom_components.freshairiq.measurement_frame import build_measurement_frame
from custom_components.freshairiq.learning_components import build_learning_components_status


def st(now, age):
    return SimpleNamespace(last_reported=now-timedelta(seconds=age), last_updated=now-timedelta(days=1))

def test_last_reported_freshness_and_grade_are_separate():
    now=datetime.now(timezone.utc)
    f=build_measurement_frame(now, temperature_state=st(now,100), humidity_state=st(now,110), reference_temperature_state=st(now,100), reference_humidity_state=st(now,110))
    assert f["quality"] == "excellent"
    assert f["grade"] == "A"
    assert f["learning_weight"] == 1.0

def test_old_but_synchronised_room_pair_is_not_objective_validation():
    now=datetime.now(timezone.utc)
    f=build_measurement_frame(now, temperature_state=st(now,850), humidity_state=st(now,851), reference_temperature_state=st(now,100), reference_humidity_state=st(now,101))
    assert f["validation_eligible"] is False
    assert f["quality"] in {"uncertain", "held"}

def test_sparse_validation_caps_learning_claims():
    room={"calculation_enabled":True,"learning_samples":500,"forecast_observation_samples":500,"outcome_feedback_samples":500,"outcome_success_rate":95,"shadow_learning_total_samples":500,"routine_source_samples":500,"routine_maturity":100,"seasonal_samples":500,"seasonal_maturity":100,"strategy_samples":500,"strategy_maturity":100,"behaviour_recommendation_opportunities":500,"behaviour_duration_samples":500}
    out=build_learning_components_status({"r":room},{"night_model_samples":500,"house_strategy_samples":500},forecast_backtest={"room_sample_count":3,"reliability":{"score_percent":95}})
    assert out["overall_maturity_percent"] <= 27.9
    assert out["stage_key"] == "grundmodell"
    assert out["personal_optimization_ready"] is False
