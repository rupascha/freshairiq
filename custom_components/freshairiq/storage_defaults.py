"""Persisted per-room learning defaults of the learning store."""
from __future__ import annotations

from typing import Any


def _room_defaults() -> dict[str, Any]:
    # Three literal parts keep the established key order of the stored room data.
    return {**_room_session_defaults(), **_room_model_defaults(), **_room_behaviour_defaults()}


def _room_session_defaults() -> dict[str, Any]:
    """Learned exchange rate, opening/contact state and the running session."""
    return {
        "learning_rate": 0.03,
        "learning_samples": 0,
        "learning_sample_credit": 0.0,
        # Explicit three-state openings learn independently. The established
        # binary/general model remains the fallback and is never reset.
        "opening_learning": {
            "open": {"rate": 0.03, "samples": 0, "credit": 0.0},
            "tilted": {"rate": 0.015, "samples": 0, "credit": 0.0},
            "cross": {"rate": 0.04, "samples": 0, "credit": 0.0},
        },
        "three_state_contacts": [],
        "three_state_unknown_contacts": [],
        "three_state_stale_contacts": [],
        "session_three_state_unknown_observed": False,
        "session_opening_mode": None,
        "session_opening_mode_mixed": False,
        "stable_opening_mode": None,
        "three_state_transients_suppressed": 0,
        "session_passage_door": False,
        "session_learning_quarantined": False,
        "session_learning_quarantine_code": None,
        "passage_behavior": {},
        "session_passage_contacts": [],
        # Indirect/passive airing is learned separately so evidence from a room
        # without its own opening can never contaminate the direct opening model.
        "passive_learning_rate": 0.03,
        "passive_learning_samples": 0,
        "passive_learning_last_group_id": None,
        "passive_learning_last_at": None,
        "diagnosis": "No learning session evaluated yet",
        "session_active": False,
        "session_started": None,
        "session_physical_started": None,
        "session_start_ah": None,
        "session_start_source_ah": None,
        # Original values are kept for learning validation even when the live
        # balance is re-based after a Home Assistant restart.
        "session_learning_start_ah": None,
        "session_learning_source_ah": None,
        "session_start_temp": None,
        "session_start_humidity": None,
        "session_result_base_ml": 0.0,
        "session_result_ml": 0.0,
        "close_notified": False,
        "session_fresh_measurements": 0,
        "session_target_min": None,
        "session_target_fan_start": False,
        "session_contact_unknown_expired": False,
        "session_temperature_reports": 0,
        "session_humidity_reports": 0,
        "session_last_temperature_update": None,
        "session_last_humidity_update": None,
        "session_open_temperature_reported_at": None,
        "session_open_humidity_reported_at": None,
        # Last valid numeric climate snapshot observed while this session was
        # active. It is a fail-safe end-value source only; it never creates
        # timestamp evidence or bypasses the strict T+RH learning gate.
        "session_last_valid_temperature": None,
        "session_last_valid_humidity": None,
        "session_last_valid_reference_temperature": None,
        "session_last_valid_reference_humidity": None,
        "session_last_valid_at": None,
        # End-measurement grace phase. The physical close time is preserved
        # separately from the later evaluation time so the measured duration is
        # never inflated by the short sensor-response wait.
        "session_close_pending": False,
        "session_close_detected_at": None,
        "session_close_wait_started_at": None,
        "session_close_deadline_at": None,
        "session_close_temperature_baseline": None,
        "session_close_humidity_baseline": None,
        "session_close_temperature_feedback": False,
        "session_close_humidity_feedback": False,
        "session_close_refresh_requested_at": None,
        "session_moisture_source_detected": False,
        # 0.26.4.9: shutter learning guard measured over the whole airing.
        "session_cover_observed_s": 0.0,
        "session_cover_closed_s": 0.0,
        "session_cover_max_closed": 0.0,
        "session_cover_last_tick": None,
        "session_cover_last_blocked": False,
        # Time-resolved cross-ventilation tracking.  A boolean sampled only at
        # session close is wrong because closing the contact itself ends the
        # cross-flow before the result is calculated.
        "session_cross_active": False,
        "session_cross_seconds": 0.0,
        "session_cross_last_update": None,
    }


def _room_model_defaults() -> dict[str, Any]:
    """Forecast observations, moisture source, measurements, post-close, history and prediction."""
    return {
        "thermal_rate_samples": 0,
        # Short-term forecast learning. These values deliberately persist so a
        # restart does not throw away the recent room behaviour.
        "forecast_observation_at": None,
        "forecast_observation_ah": None,
        "forecast_observation_temp": None,
        "forecast_observation_ref_ah": None,
        "forecast_observation_open": None,
        "forecast_source_ml_min": None,
        "forecast_thermal_residual_c_min": None,
        "forecast_observation_samples": 0,
        "forecast_recent_removed_ml_min": None,
        "forecast_recent_observed_at": None,
        # Internal moisture-source detector (shower/bath/sauna). Short rolling
        # samples and hysteresis survive reloads so an active event is not lost.
        "moisture_source_points": [],
        "moisture_source_active": False,
        "moisture_source_started_at": None,
        "moisture_source_last_positive_at": None,
        "moisture_source_last_ended_at": None,
        "moisture_source_confidence": 0,
        "moisture_source_rate_ml_min": 0.0,
        "moisture_source_generated_ml": 0.0,
        "moisture_source_label": "Feuchtequelle",
        "moisture_source_last_evaluated_at": None,
        # 0.26.4.7: post-close rebound guard (last open sample, pending candidate).
        "moisture_source_last_open_at": None,
        "moisture_source_rebound_candidate": None,
        # 0.26.4.7 (GitHub #15): ventilation start hysteresis.
        "ventilation_candidate_latched": False,
        "last_action": None,
        "last_measurement_at": None,
        "last_measurement_valid": None,
        "last_measurement_frame_quality": None,
        "last_measurement_frame_skew_s": None,
        "last_measurement_frame_max_age_s": None,
        "last_measurement_frame_learning_eligible": None,
        "last_learning_at": None,
        "last_learning_valid": None,
        "last_ventilation_ended_at": None,
        "last_ventilation_removed_ml": 0.0,
        # Post-close stabilization v1: diagnostic observation of moisture rebound
        # after a ventilation session. It does not modify forecast/learning yet.
        "post_close_active": False,
        "post_close_event_id": None,
        "post_close_room_key": None,
        "post_close_room_name": None,
        "post_close_started_at": None,
        "post_close_ah": None,
        "post_close_temp_c": None,
        "post_close_removed_ml": None,
        "post_close_volume_m3": None,
        "post_close_start_frame_quality": None,
        "post_close_contaminated": False,
        "post_close_samples": [],
        "post_close_last_sample_at": None,
        "post_close_last_outcome": None,
        "history": {},
        "temperature_points": [],
        "humidity_points": [],
        "recommendation_opportunities": 0,
        "recommendation_followed": 0,
        "recommendation_missed": 0,
        "recommendation_follow_rate": None,
        "avg_follow_delay_min": None,
        "follow_delay_samples": 0,
        "preferred_duration_min": None,
        "duration_samples": 0,
        "avg_duration_deviation_min": None,
        "session_recommended_duration_min": None,
        "session_recommendation_followed": False,
        "session_recommendation_issued_at": None,
        "session_predicted_removed_ml": None,
        "session_predicted_temperature_change_c": None,
        "session_predicted_cost": None,
        "session_prediction_confidence": None,
        "session_prediction_snapshot_at": None,
        "session_prediction_horizon_min": None,
        "session_prediction_snapshot_elapsed_min": None,
        "session_prediction_snapshot_valid": False,
        "session_prediction_snapshot_pending": False,
        "session_prediction_reference": None,
        "session_validation_id": None,
        "session_prediction_start_context": None,
        "session_prediction_time_aligned": False,
        # Measurement Frames v1: preserve the temporal quality of the session
        # baseline and the frozen prediction snapshot independently.
        "session_start_frame_quality": None,
        "session_start_frame_skew_s": None,
        "session_start_frame_max_age_s": None,
        "session_start_frame_learning_eligible": False,
        "session_prediction_snapshot_frame_quality": None,
        "session_prediction_snapshot_frame_skew_s": None,
        "session_prediction_snapshot_frame_max_age_s": None,
        # Measurement & Validation Hardening v0.25.0.28: objective forecast
        # validation owns an independent A/B-grade measurement clock. Adaptive
        # room learning may still use held battery frames, but they can no longer
        # silently become the baseline of an objective forecast score.
        "session_validation_started": None,
        "session_validation_start_ah": None,
        "session_validation_start_source_ah": None,
        "session_validation_start_temp": None,
        "session_validation_start_source_temp": None,
        "session_last_validation_ah": None,
        "session_last_validation_temp": None,
        "session_last_validation_at": None,
        # Validation Engine v2: immutable start snapshot plus time-resolved
        # live forecast checkpoints. This is diagnostic-only and never feeds
        # learning coefficients directly.
        "session_forecast_timeline": [],
        "session_timeline_last_checkpoint_min": None,
        "session_selected_option_id": None,
    }


def _room_behaviour_defaults() -> dict[str, Any]:
    """Outcome feedback, shadow learning, routines, seasons and strategies."""
    return {
        "outcome_feedback_samples": 0,
        "outcome_removed_factor": 1.0,
        "outcome_temperature_factor": 1.0,
        "outcome_avg_removed_error_ml": None,
        "outcome_avg_temperature_error_c": None,
        "outcome_success_rate": None,
        "outcome_successes": 0,
        "outcome_guarded_direction": None,
        "outcome_guarded_streak": 0,
        "outcome_guarded_last_ratio": None,
        # Learning 3.0 shadow-model competition + automatic rollback guard.
        "shadow_learning_generation": 1,
        "shadow_learning_samples": 0,
        "shadow_learning_total_samples": 0,
        "shadow_learning_candidates": {},
        "shadow_learning_status": "Beobachtet Produktionsmodell",
        "shadow_learning_last_action": "observing",
        "shadow_learning_last_improvement_pct": None,
        "shadow_learning_last_multiplier": None,
        "shadow_learning_promotions": 0,
        "shadow_learning_rollbacks": 0,
        "shadow_learning_cooldown": 0,
        "shadow_rollback_active": False,
        "shadow_rollback_previous_factor": None,
        "shadow_rollback_promoted_factor": None,
        "shadow_rollback_samples": 0,
        "shadow_rollback_active_error": 0.0,
        "shadow_rollback_previous_error": 0.0,
        "shadow_rollback_previous_wins": 0,
        "last_outcome_feedback_applied": False,
        "last_outcome_feedback_action": None,
        "last_outcome_feedback_reason": None,
        "last_outcome_feedback_accuracy": None,
        "routine_source_buckets": {},
        "routine_response_buckets": {},
        "routine_observation_at": None,
        "routine_source_samples": 0,
        "routine_response_samples": 0,
        "routine_observation_dates": [],
        "seasonal_source_profiles": {},
        "seasonal_samples": 0,
        "long_term_source_ml_min": None,
        "long_term_source_samples": 0,
        "long_term_updated_at": None,
        "seasonal_observation_days": {},
        "strategy_buckets": {},
        "strategy_samples": 0,
        "strategy_follow_samples": 0,
        "strategy_outcome_samples": 0,
        "learning_observation_dates": [],
        "strategy_observation_dates": [],
        "personal_context_observation_dates": [],
    }
