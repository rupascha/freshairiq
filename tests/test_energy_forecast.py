import pytest

from custom_components.freshairiq.energy import exchanged_air_fraction, ventilation_heat_energy_kwh, ventilation_cost
from custom_components.freshairiq.forecast import baseline_night_rate_ml_h, overnight_forecast_ml, update_night_learning, horizon_forecast


def test_air_exchange_fraction_uses_exponential_replacement_model():
    assert exchanged_air_fraction(0.03, 5) == pytest.approx(1 - 0.97**5)
    assert exchanged_air_fraction(1, 5) == 0.95


def test_heat_loss_physics():
    q = ventilation_heat_energy_kwh(100, 20, 0, 0.2)
    assert 0.12 < q < 0.15


def test_heat_pump_cost_lower_than_direct_electric():
    hp = {"heating_system": "heat_pump", "heat_pump_cop": 4, "electricity_price_per_kwh": 0.30}
    el = {"heating_system": "electric", "electricity_price_per_kwh": 0.30}
    assert ventilation_cost(100, 20, 0, 0.2, hp)[2] < ventilation_cost(100, 20, 0, 0.2, el)[2]


def test_gas_and_oil_use_system_specific_prices():
    gas = {"heating_system": "gas", "gas_price_per_kwh": 0.11, "gas_efficiency": 0.92}
    oil = {"heating_system": "oil", "oil_price_per_liter": 1.0, "oil_kwh_per_liter": 10.0, "oil_efficiency": 0.88}
    assert ventilation_cost(100, 20, 0, 0.2, gas)[2] > 0
    assert ventilation_cost(100, 20, 0, 0.2, oil)[2] > 0


def test_night_forecast_uses_adults_children_and_fixed_biology_prior():
    o = {
        "property_type": "house",
        "adult_occupants": 1,
        "child_occupants": 1,
        "night_start_hour": "23:00",
        "night_end_hour": "07:00",
        "adult_night_moisture_ml_h": 45,
        "child_night_moisture_ml_h": 30,
        "background_night_moisture_ml_h": 10,
    }
    assert baseline_night_rate_ml_h(o) == 85
    assert overnight_forecast_ml(o, None, 0) == 680


def test_night_learning_rejects_negative():
    assert update_night_learning(100, 3, -10) == (100, 3)


def test_night_rate_scales_learned_model_to_current_occupancy():
    from custom_components.freshairiq.forecast import effective_night_rate_ml_h
    opts = {
        "adult_occupants": 2,
        "child_occupants": 2,
        "adult_night_moisture_ml_h": 45.0,
        "child_night_moisture_ml_h": 30.0,
        "background_night_moisture_ml_h": 10.0,
        "property_type": "house",
    }
    full = effective_night_rate_ml_h(opts, 160.0, 20, 2, 2)
    one = effective_night_rate_ml_h(opts, 160.0, 20, 1, 0)
    assert one < full
    assert one > 0


def test_remaining_night_hours_uses_remaining_window_not_full_night():
    from datetime import datetime
    from custom_components.freshairiq.forecast import remaining_night_hours
    assert 4.9 < remaining_night_hours(datetime(2026, 9, 8, 2, 0), "22:00", "07:00") < 5.1
    assert 8.9 < remaining_night_hours(datetime(2026, 9, 8, 20, 0), "22:00", "07:00") < 9.1


def test_user_facing_forecast_is_monotonic_for_drying_air():
    common = dict(
        current_ah=12.0, source_ah=7.0, current_temp_c=21.0, source_temp_c=15.0,
        volume_m3=50.0, rate_per_min=0.03, airflow_bonus=1.0,
        prior_source_ml_min=2.0, learned_source_ml_min=8.0,
        observation_samples=24, running=True, session_elapsed_min=18.0,
    )
    f5 = horizon_forecast(horizon_min=5, **common)
    f60 = horizon_forecast(horizon_min=60, **common)
    assert f5["moisture_effect_ml"] > 0
    assert f60["moisture_effect_ml"] >= f5["moisture_effect_ml"]
    assert f60["net_moisture_change_ml"] != f60["moisture_effect_ml"]


def test_user_facing_forecast_keeps_sign_for_wetter_source_air():
    common = dict(
        current_ah=8.0, source_ah=11.0, current_temp_c=21.0, source_temp_c=20.0,
        volume_m3=40.0, rate_per_min=0.03, airflow_bonus=1.0, horizon_min=10,
    )
    forecast = horizon_forecast(**common)
    assert forecast["moisture_effect_ml"] < 0


def test_long_user_forecast_can_be_limited_to_humidity_target():
    common = dict(
        current_ah=12.0, source_ah=6.0, current_temp_c=21.0, source_temp_c=10.0,
        volume_m3=100.0, rate_per_min=0.05, airflow_bonus=1.0,
        target_ah=11.0, cap_positive_to_target=True,
    )
    forecast = horizon_forecast(horizon_min=60, **common)
    assert forecast["moisture_effect_ml"] == 100
    assert forecast["target_cap_ml"] == 100
    assert forecast["target_limited"]


def test_live_five_minute_forecast_remains_uncapped_without_flag():
    common = dict(
        current_ah=12.0, source_ah=6.0, current_temp_c=21.0, source_temp_c=10.0,
        volume_m3=100.0, rate_per_min=0.05, airflow_bonus=1.0,
        target_ah=11.0,
    )
    forecast = horizon_forecast(horizon_min=5, **common)
    assert forecast["target_cap_ml"] is None
    assert not forecast["target_limited"]


def test_multi_hour_plan_converts_generation_to_ventilation_effective_potential():
    from datetime import datetime
    from custom_components.freshairiq.planner import build_multi_hour_plan

    rooms = {
        "room": {
            "key": "room", "name": "Room", "calculation_enabled": True,
            "data_quality": "ok", "active": False, "humidity": 65,
            "surface_rh": 70, "co2": 500, "delta_g_m3": 3.0,
            "absolute_humidity": 12.0, "temperature": 21.0, "volume_m3": 100.0,
            "potential_ml": 300, "realistic_potential_ml": 60,
            "forecast_source_rate_ml_min": 5.0,
            "routine_source_buckets": {}, "routine_source_samples": 0,
        }
    }
    plan = build_multi_hour_plan(
        rooms,
        {"high_rh": 68, "mould_warn_surface_rh": 80, "co2_warn": 1000,
         "min_potential_total_ml": 500},
        datetime(2026, 9, 10, 7, 0),
        future_outdoor={360: {"absolute_humidity": 6.0, "temperature_c": 10.0, "confidence": 80}},
        horizon_hours=8.0,
    )
    future = next(x for x in plan["options"] if x["id"] == "in_360")
    # 5 ml/min * 360 min = 1800 ml generated, but only the current 20 %
    # ventilation capture fraction may be added to removable potential.
    assert future["projected_generation_ml"] == 1800
    assert future["ventilation_capture_fraction"] == 0.2
    assert future["projected_potential_ml"] == 420


def test_night_window_respects_minute_precision():
    from custom_components.freshairiq.forecast import night_window_hours, in_night_window, remaining_night_hours
    from datetime import datetime

    assert abs(night_window_hours("22:30", "06:45") - 8.25) < 1e-9
    assert in_night_window(datetime(2026, 9, 10, 22, 20), "22:30", "06:45") is False
    assert in_night_window(datetime(2026, 9, 10, 22, 30), "22:30", "06:45") is True
    assert in_night_window(datetime(2026, 9, 11, 6, 44), "22:30", "06:45") is True
    assert in_night_window(datetime(2026, 9, 11, 6, 45), "22:30", "06:45") is False
    assert abs(remaining_night_hours(datetime(2026, 9, 11, 1, 15), "22:30", "06:45") - 5.5) < 1e-9
