from custom_components.freshairiq.forecast import horizon_forecast
from custom_components.freshairiq.recommendation import build_recommendation


def _forecast(quality):
    return horizon_forecast(current_ah=13, source_ah=10, current_temp_c=22, source_temp_c=15,
        volume_m3=50, rate_per_min=.03, airflow_bonus=1, horizon_min=15,
        observation_samples=6, model_maturity_pct=90, measurement_frame_quality=quality)


def test_stale_frame_cannot_claim_confidence():
    assert _forecast("stale")["confidence"] == 0
    assert _forecast("held")["confidence"] <= 35
    assert _forecast("uncertain")["confidence"] <= 40
    assert _forecast("acceptable")["confidence"] <= 75


def test_bad_room_does_not_block_valid_room():
    rooms = {
        "bad": {"key":"bad","name":"Bad sensor","calculation_enabled":True,"data_quality":"error"},
        "ok": {"key":"ok","name":"OK","calculation_enabled":True,"data_quality":"ok","active":False,
               "action":"Ventilate","humidity":70,"surface_rh":70,"realistic_potential_ml":150,
               "delta_g_m3":2.0,"airflow_factor":1.0,"forecast_confidence":60},
    }
    result = build_recommendation(rooms, {"high_rh":68,"start_rh":62}, threshold_ml=100,
        total_potential_ml=150, recommended_duration_min=10)
    assert result["kind"] != "sensor"


def test_all_bad_rooms_still_raise_sensor_error():
    rooms = {"bad": {"key":"bad","name":"Bad sensor","calculation_enabled":True,"data_quality":"error"}}
    result = build_recommendation(rooms, {}, threshold_ml=100,total_potential_ml=0,recommended_duration_min=10)
    assert result["kind"] == "sensor"
