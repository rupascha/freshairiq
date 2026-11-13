"""0.26.7.0 point 7: a prepared, versioned successor of the shadow candidate – pure shadow mode.

Same formula and coefficients as ``humidity-hybrid-2026-10-31-r1`` (not recalibrated, no new data), fed with the
physical start replay instead of the target-limited one. It is recorded per session next to the candidate and never
used by any decision. No result is claimed: its error is only measured on real sessions.
"""
from __future__ import annotations

import custom_components.freshairiq.forecast_shadow as fs
from custom_components.freshairiq.forecast_validation import evaluate_start_forecast_at_duration, freeze_start_forecast_context
from tests._source import COMP

OPTIONS = {"min_return_next_5_min_ml": 25.0, "max_temp_loss_next_5_min_c": 0.6, "min_efficiency_ml_per_01c": 8.0,
           "min_duration_min": 3.0, "max_duration_min": 20.0, "operating_profile": "comfort", "heating_system": "gas",
           "gas_price_per_kwh": 0.11, "gas_efficiency": 0.92}


def _context():
    args = {"current_ah": 10.4, "source_ah": 6.0, "current_temp_c": 21.0, "source_temp_c": 8.0, "volume_m3": 40.0,
            "rate_per_min": 0.05, "airflow_bonus": 1.0, "prior_source_ml_min": 0.0, "learned_source_ml_min": 0.0,
            "learned_thermal_residual_c_min": 0.0, "observation_samples": 6, "model_maturity_pct": 80.0}
    context = freeze_start_forecast_context(args, target_ah=10.0, options=OPTIONS, start_ah=10.4, start_source_ah=6.0,
                                            start_temp_c=21.0, start_source_temp_c=8.0)
    context["shadow"] = fs.freeze_shadow_start(cross_ventilated=False, integration_version="0.26.7.0")
    return context


def test_successor_is_recorded_beside_the_candidate():
    context = _context()
    physical = evaluate_start_forecast_at_duration(context, 15.0)["predicted_removed_ml"]
    record = fs.shadow_forecast_record(context, horizon_min=15.0, production_predicted_ml=physical, measured_removed_ml=60.0,
                                       comparable=True, time_aligned=True, cross_ratio=0.0)
    assert record["successor_formula_id"] == fs.SUCCESSOR_FORMULA_ID != fs.CANDIDATE_FORMULA_ID
    assert record["successor_status"] == "shadow_only_uncalibrated" and record["successor_input_basis"] == "physical_start_replay"
    expected = fs.shadow_removed_ml(room_ah_start_g_m3=10.4, source_ah_start_g_m3=6.0, volume_m3=40.0, horizon_min=15.0,
                                    is_cross_ventilated=False, legacy_start_forecast_ml=physical)
    assert record["successor_predicted_removed_ml"] == round(expected, 1)
    assert record["successor_abs_error_ml"] == round(abs(60.0 - expected), 1)
    assert record["candidate_formula_id"] == "humidity-hybrid-2026-10-31-r1"     # the candidate is unchanged


def test_successor_outside_the_calibrated_range_is_excluded_not_guessed():
    context = _context()
    record = fs.shadow_forecast_record(context, horizon_min=150.0, production_predicted_ml=300.0, measured_removed_ml=200.0,
                                       comparable=True, time_aligned=True)
    assert "successor_predicted_removed_ml" not in record and "successor_abs_error_ml" not in record


def test_successor_is_never_used_by_a_decision():
    for module in ("model.py", "consolidation.py", "live_coach.py", "house_decision.py", "recommendation.py",
                   "notifications.py", "forecast.py", "coordinator_room_model.py"):
        assert "SUCCESSOR_FORMULA_ID" not in (COMP / module).read_text(encoding="utf-8") and "_successor(" not in (COMP / module).read_text(encoding="utf-8")


def test_successor_failure_is_recorded_not_raised():
    out: dict = {}
    assert fs._successor({"current_ah": 10.4, "source_ah": 6.0, "volume_m3": 40.0}, {}, 15.0, float("nan"), out) is None
    assert out["successor_exclusion_reason"] == "invalid_input"
    out = {}
    assert fs._successor({"current_ah": 10.4, "source_ah": 6.0, "volume_m3": 900.0}, {}, 15.0, 50.0, out) is None
    assert out["successor_exclusion_reason"] == "outside_calibrated_range"
    out = {}
    assert fs._successor({}, {}, 15.0, 50.0, out) is None and out["successor_exclusion_reason"] == "invalid_input"
