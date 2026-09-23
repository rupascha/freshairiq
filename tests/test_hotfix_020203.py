from pathlib import Path

from custom_components.freshairiq.forecast import horizon_forecast

ROOT = Path(__file__).resolve().parents[1]


def _base(**overrides):
    args = dict(
        current_ah=12.0,
        source_ah=6.0,
        current_temp_c=21.0,
        source_temp_c=16.0,
        volume_m3=100.0,
        rate_per_min=0.03,
        airflow_bonus=1.0,
        observation_samples=6,
        running=True,
        session_elapsed_min=20.0,
        session_fresh_measurements=2,
        recent_observed_removed_ml_min=2.0,
    )
    args.update(overrides)
    return args


def test_young_model_confidence_is_capped_below_95():
    result = horizon_forecast(horizon_min=5, model_maturity_pct=61, **_base())
    assert result["confidence"] == 61


def test_mature_model_can_still_reach_high_confidence():
    result = horizon_forecast(horizon_min=5, model_maturity_pct=95, **_base())
    assert result["confidence"] == 95


def test_optimal_close_respects_exact_remaining_max_duration():
    result = horizon_forecast(
        horizon_min=60,
        target_ah=4.0,
        cap_positive_to_target=True,
        min_return_next_5_min_ml=0.0,
        max_temp_loss_next_5_min_c=99.0,
        min_efficiency_ml_per_01c=0.0,
        min_duration_min=3.0,
        max_duration_min=20.0,
        operating_profile="comfort",
        **_base(session_elapsed_min=19.0, model_maturity_pct=80),
    )
    assert result["optimal_close_reason"] == "max_duration"
    assert result["optimal_close_in_min"] == 1.0


def test_forecast_help_separates_energy_cost_model():
    js = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert "Heizsystem und Energiepreis beeinflussen nicht die physikalische Feuchteprognose" in js


def test_release_version_020203():
    assert 'VERSION = "0.25.0.54"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.54"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.54"' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
