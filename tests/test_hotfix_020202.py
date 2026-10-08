from custom_components.freshairiq.forecast import horizon_forecast


def _common(**overrides):
    data = dict(
        current_ah=12.0,
        source_ah=6.0,
        current_temp_c=21.0,
        source_temp_c=16.0,
        volume_m3=100.0,
        rate_per_min=0.03,
        airflow_bonus=1.0,
        prior_source_ml_min=0.0,
        observation_samples=6,
        running=True,
        session_elapsed_min=5.0,
        session_fresh_measurements=2,
        target_ah=9.5,
        cap_positive_to_target=True,
        min_return_next_5_min_ml=25.0,
        max_temp_loss_next_5_min_c=0.6,
        min_efficiency_ml_per_01c=8.0,
        min_duration_min=3.0,
        max_duration_min=120.0,
        operating_profile="comfort",
    )
    data.update(overrides)
    return data


def test_long_horizon_exposes_predicted_end_point_when_marginal_return_falls():
    result = horizon_forecast(horizon_min=60, **_common())
    assert result["simulation_steps"] == 12
    assert result["optimal_close_in_min"] is not None
    assert 5 <= result["optimal_close_in_min"] <= 60
    assert result["optimal_close_reason"] in {"target_reached", "marginal_return", "thermal_efficiency", "cumulative_temperature_loss", "projected_end_temperature", "max_duration"}


def test_no_end_point_inside_horizon_when_drying_stays_strong_and_limits_are_relaxed():
    result = horizon_forecast(
        horizon_min=30,
        **_common(
            source_ah=1.0,
            target_ah=1.0,
            min_return_next_5_min_ml=0.0,
            max_temp_loss_next_5_min_c=5.0,
            min_efficiency_ml_per_01c=0.0,
            max_duration_min=120.0,
        ),
    )
    assert result["optimal_close_in_min"] is None
    assert result["optimal_close_reason"] is None


def test_five_minute_control_path_does_not_gain_forecast_close_signal():
    result = horizon_forecast(horizon_min=5, **_common())
    assert result["optimal_close_in_min"] is None
    assert result["optimal_close_reason"] is None
