"""#28 (0.26.7.0): the validation replay of the frozen start forecast is physical, not humidity-target capped.

The recommendation layer may stop at the humidity target, but the measured removal is absolute. Validation,
learning effectiveness and the shadow comparison therefore replay the start curve without the cap; the live
coach keeps the target-limited expectation; records of the earlier capped basis are counted, never mixed in.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import custom_components.freshairiq.learning_effectiveness as le
from custom_components.freshairiq import live_coach
from custom_components.freshairiq.forecast_validation import (
    PREDICTION_BASIS,
    START_FORECAST_CONTEXT_VERSION,
    VALIDATION_RECORD_VERSION,
    evaluate_start_forecast_at_duration,
    freeze_start_forecast_context,
    validation_summary,
)

OPTIONS = {
    "min_return_next_5_min_ml": 25.0, "max_temp_loss_next_5_min_c": 0.6, "min_efficiency_ml_per_01c": 8.0,
    "min_duration_min": 3.0, "max_duration_min": 20.0, "operating_profile": "comfort", "heating_system": "gas",
    "gas_price_per_kwh": 0.11, "gas_efficiency": 0.92,
}


def _context(*, current_ah: float, target_ah: float) -> dict:
    args = {
        "current_ah": current_ah, "source_ah": 6.0, "current_temp_c": 21.0, "source_temp_c": 8.0,
        "volume_m3": 40.0, "rate_per_min": 0.05, "airflow_bonus": 1.0, "prior_source_ml_min": 0.0,
        "learned_source_ml_min": 0.0, "learned_thermal_residual_c_min": 0.0, "observation_samples": 6,
        "model_maturity_pct": 80.0,
    }
    return freeze_start_forecast_context(
        args, target_ah=target_ah, options=OPTIONS,
        start_ah=current_ah, start_source_ah=6.0, start_temp_c=21.0, start_source_temp_c=8.0,
    )


def test_room_close_to_target_is_replayed_physically_and_marked_target_limited():
    # 0.4 g/m³ above the target in 40 m³ = 16 ml target gap; airing 15 min against 6 g/m³ removes far more
    context = _context(current_ah=10.4, target_ah=10.0)
    assert context["version"] == START_FORECAST_CONTEXT_VERSION == 3
    physical = evaluate_start_forecast_at_duration(context, 15.0)
    capped = evaluate_start_forecast_at_duration(context, 15.0, limit_to_target=True)
    assert physical is not None and capped is not None
    assert physical["prediction_basis"] == PREDICTION_BASIS == "physical_start_replay"
    assert capped["prediction_basis"] == "target_limited_start_replay"
    assert physical["target_gap_ml"] == 16.0
    assert physical["target_limited"] is True
    # the old capped replay stayed near the gap; the physical replay follows the real air exchange
    assert capped["predicted_removed_ml"] <= 16.5
    assert physical["predicted_removed_ml"] > 3 * capped["predicted_removed_ml"]


def test_room_already_below_target_is_no_longer_predicted_as_zero():
    context = _context(current_ah=9.5, target_ah=10.0)
    physical = evaluate_start_forecast_at_duration(context, 12.0)
    capped = evaluate_start_forecast_at_duration(context, 12.0, limit_to_target=True)
    assert physical["target_gap_ml"] == 0.0 and physical["target_limited"] is True
    assert abs(capped["predicted_removed_ml"]) < 1.0
    assert physical["predicted_removed_ml"] > 50.0


def test_short_or_target_free_horizons_are_not_marked():
    context = _context(current_ah=14.0, target_ah=10.0)  # 160 ml gap
    short = evaluate_start_forecast_at_duration(context, 5.0)
    assert short["target_limited"] is False
    assert evaluate_start_forecast_at_duration(context, 5.0, limit_to_target=True)["predicted_removed_ml"] == short["predicted_removed_ml"]


def _validation_record(day: int, *, version: int | None, error: float) -> dict:
    ended = datetime(2026, 11, 1, 18, 0) + timedelta(days=day)
    record = {
        "valid": True, "ended_at": ended.isoformat(), "started_at": (ended - timedelta(minutes=10)).isoformat(),
        "moisture_abs_error_ml": error, "moisture_error_ml": error, "direction_correct": True,
        "room_results": [{"key": "bad", "name": "Bad", "comparable": True, "moisture_abs_error_ml": error}],
    }
    if version is not None:
        record["validation_version"] = version
    return record


def test_validation_summary_keeps_capped_records_out_and_counts_them():
    history = [_validation_record(0, version=2, error=500.0), _validation_record(1, version=None, error=400.0),
               _validation_record(2, version=VALIDATION_RECORD_VERSION, error=20.0)]
    summary = validation_summary(history, days=3650)
    assert summary["previous_basis_record_count"] == 2
    assert summary["prediction_basis"] == "physical_start_replay"
    assert summary["moisture_mae_ml"] == 20.0
    # the stored history itself is not rewritten
    assert history[0]["moisture_abs_error_ml"] == 500.0 and history[0]["validation_version"] == 2


def test_learning_effectiveness_counts_but_does_not_score_capped_samples():
    def record(day: int, basis: str | None) -> dict:
        sample = {"valid": True, "ended_at": f"2026-11-{day + 1:02d}T18:00:00", "production_abs_error_ml": 10.0,
                  "baseline_abs_error_ml": 30.0, "paired_error_gain_ml": 20.0, "winner": "learned"}
        if basis:
            sample["prediction_basis"] = basis
        return {"valid": True, "ended_at": sample["ended_at"], "room_results": [{"key": "r", "comparable": True, "learning_effectiveness": sample}]}
    records = [record(0, None), record(1, "physical_start_replay")]
    assert len(le._extract_samples(records)) == 1
    summary = le.learning_effectiveness_summary(records, days=3650)
    assert summary["previous_basis_sample_count"] == 1


def test_live_coach_compares_progress_with_the_target_limited_expectation():
    def room(**extra):
        base = {"calculation_enabled": True, "data_quality": "ok", "active": True, "opening_state": "open",
                "session_elapsed_min": 6.0, "session_recommended_duration_min": 12.0, "result_ml": 30.0,
                "close_decision_ready": False, "forecast_5_min_confidence": 80, "forecast_5_min_moisture_effect_ml": 40.0}
        base.update(extra)
        return base
    recommendation = {"kind": "continue", "duration_min": 6.0}
    limited = live_coach.refine_live_recommendation(
        {"bad": room(session_predicted_removed_ml=200.0, session_target_limited_removed_ml=60.0)}, OPTIONS, recommendation)
    legacy = live_coach.refine_live_recommendation(
        {"bad": room(session_predicted_removed_ml=60.0)}, OPTIONS, recommendation)
    # physical 200 ml would mark the session as far behind; the coach keeps the 60 ml expectation of the recommendation
    assert limited.get("live_coach_expected_now_ml") == legacy.get("live_coach_expected_now_ml") == 30.0


def test_shadow_candidate_keeps_its_calibrated_target_limited_input():
    """The candidate humidity-hybrid-2026-10-31-r1 was calibrated on the target-limited start replay; it keeps that
    input (same versioned formula), while the production side of the pair is the physical replay."""
    import custom_components.freshairiq.forecast_shadow as fs
    context = _context(current_ah=10.4, target_ah=10.0)
    context["shadow"] = fs.freeze_shadow_start(cross_ventilated=False, integration_version="0.26.7.0")
    physical = evaluate_start_forecast_at_duration(context, 15.0)["predicted_removed_ml"]
    limited = evaluate_start_forecast_at_duration(context, 15.0, limit_to_target=True)["predicted_removed_ml"]
    record = fs.shadow_forecast_record(context, horizon_min=15.0, production_predicted_ml=physical, measured_removed_ml=60.0,
                                       comparable=True, time_aligned=True)
    assert record["candidate_input_basis"] == "target_limited_start_replay"
    expected = fs.shadow_removed_ml(room_ah_start_g_m3=10.4, source_ah_start_g_m3=6.0, volume_m3=40.0, horizon_min=15.0,
                                    is_cross_ventilated=False, legacy_start_forecast_ml=limited)
    assert record["candidate_predicted_removed_ml"] == round(expected, 1)
    assert record["production_predicted_removed_ml"] == round(physical, 1)
    assert record["production_formula_id"] == "start-curve-v3-horizon-forecast-r2"  # Testvermerk final hotfix F11-C
