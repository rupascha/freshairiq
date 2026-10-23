"""Finished-session bookkeeping: statistics record and validation of the frozen start forecast."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_ROOM_VOLUME, PROFILE_SUMMER_COOLING
from .energy import exchanged_air_fraction, ventilation_cost
from .forecast_validation import evaluate_start_forecast_at_duration, prediction_duration_comparable
from .intelligence import learn_completed_session, learn_outcome_feedback
from .learning_effectiveness import (
    baseline_context_from_start,
    build_effectiveness_sample,
    previous_model_context_from_start,
)
from .robustness import finite_float


class SessionValidationMixin:
    """Finished-session bookkeeping: statistics record and validation of the frozen start forecast."""

    hass: HomeAssistant  # provided by the coordinator

    def _record_completed_session(
        self,
        *,
        cfg: Any,
        elapsed: Any,
        mem: Any,
        now: Any,
        rate: Any,
        ref_t: Any,
        session_activity_eligible: Any,
        session_removed: Any,
        t: Any,
    ) -> Any:
        """Record the finished session in the statistics and the behaviour model."""
        temp_start = finite_float(mem.get("session_start_temp"))
        if temp_start is None:
            temp_start = t
        temp_delta = t - temp_start
        elapsed_seconds = max(elapsed * 60.0, 0.0)
        cross_seconds = min(max(finite_float(mem.get("session_cross_seconds"), 0.0) or 0.0, 0.0), elapsed_seconds)
        # A session may be cross-ventilated only for part of its runtime.  Use
        # the time-weighted airflow bonus instead of sampling the contact state
        # after it has already been closed.
        cross_ratio = cross_seconds / elapsed_seconds if elapsed_seconds > 0 else 0.0
        cross_multiplier = 1.0 + 0.25 * cross_ratio
        fraction = exchanged_air_fraction(float(rate), elapsed, cross_multiplier); _delivered, purchased, cost = ventilation_cost(float(cfg[CONF_ROOM_VOLUME]), temp_start, ref_t, fraction, self.options)
        if temp_delta >= 0 or (self.options.get("operating_profile") == PROFILE_SUMMER_COOLING and ref_t < temp_start):
            purchased = 0.0; cost = 0.0
        self.store.record_session(now.replace(tzinfo=None), session_removed, elapsed, temp_delta, purchased, cost, cfg["key"], moisture_valid=session_activity_eligible)
        learn_completed_session(mem, elapsed)
        pc_dates = mem.get("personal_context_observation_dates")
        if not isinstance(pc_dates, list):
            pc_dates = []
        pc_day = now.date().isoformat()
        if pc_day not in pc_dates:
            pc_dates.append(pc_day)
        mem["personal_context_observation_dates"] = pc_dates[-730:]
        return (cost, cross_ratio, cross_seconds, purchased, temp_delta)

    def _validate_session_forecast(
        self,
        *,
        cfg: Any,
        elapsed: Any,
        learning_contaminated: Any,
        mem: Any,
        now: Any,
        reference_moisture_reversal: Any,
        session_activity_eligible: Any,
        session_quality: Any,
        session_removed: Any,
        temp_delta: Any,
        validation_end_ah: Any,
        validation_end_temp: Any,
    ) -> Any:
        """Compare the frozen start forecast with the measured session and learn outcome feedback."""
        # Hotfix 0.24.14.1: compare the immutable START model with the duration
        # that was actually measured.  The end measurement only selects the
        # point on the frozen start-time forecast curve; it is never fed back as
        # a prediction input.  This removes the previous systematic mismatch in
        # which (for example) a 15-minute start forecast was rejected when the
        # user happened to close the window after 9 or 25 minutes.
        validation_started = None
        try:
            validation_started = datetime.fromisoformat(str(mem.get("session_validation_started"))) if mem.get("session_validation_started") else None
        except (TypeError, ValueError):
            validation_started = None
        validation_elapsed = max(0.0, (now - validation_started).total_seconds() / 60.0) if validation_started else 0.0
        validation_start_ah = finite_float(mem.get("session_validation_start_ah"))
        validation_start_temp = finite_float(mem.get("session_validation_start_temp"))
        validation_removed = (
            (validation_start_ah - validation_end_ah) * float(cfg[CONF_ROOM_VOLUME])
            if validation_start_ah is not None and validation_end_ah is not None
            else None
        )
        validation_temp_delta = (
            validation_end_temp - validation_start_temp
            if validation_start_temp is not None and validation_end_temp is not None
            else None
        )

        start_context = mem.get("session_prediction_start_context")
        aligned_prediction = evaluate_start_forecast_at_duration(start_context, validation_elapsed)
        baseline_prediction = evaluate_start_forecast_at_duration(
            baseline_context_from_start(start_context), validation_elapsed
        )
        previous_model_prediction = evaluate_start_forecast_at_duration(
            previous_model_context_from_start(start_context), validation_elapsed
        )
        learning_effectiveness_sample = build_effectiveness_sample(
            start_context,
            duration_min=validation_elapsed,
            production_prediction=aligned_prediction,
            baseline_prediction=baseline_prediction,
            previous_model_prediction=previous_model_prediction,
            actual_removed_ml=validation_removed,
            ended_at=now.isoformat(),
        )
        prediction_time_aligned = aligned_prediction is not None
        if aligned_prediction is not None:
            mem["session_predicted_removed_ml"] = aligned_prediction["predicted_removed_ml"]
            mem["session_predicted_temperature_change_c"] = aligned_prediction["predicted_temperature_change_c"]
            mem["session_predicted_cost"] = aligned_prediction["predicted_cost"]
            mem["session_prediction_confidence"] = aligned_prediction["confidence"]
            mem["session_prediction_horizon_min"] = aligned_prediction["duration_min"]
            mem["session_prediction_reference"] = "session_start_curve_v2"
            mem["session_prediction_time_aligned"] = True
            # A valid frozen start context is enough for an informational
            # same-duration comparison. Objective validation/learning remains
            # deliberately stricter and is gated below by measurement quality.
            original_snapshot_valid = True
            prediction_comparable = True
        else:
            # Backward compatibility for a session restored from a pre-hotfix
            # store: keep the previous fixed-horizon test when no v2 start
            # context exists.
            snapshot_horizon = mem.get("session_prediction_horizon_min")
            original_snapshot_valid = bool(mem.get("session_prediction_snapshot_valid"))
            snapshot_valid = original_snapshot_valid and snapshot_horizon is not None
            if snapshot_valid:
                snapshot_horizon_f = max(float(snapshot_horizon), 1.0)
                prediction_comparable = prediction_duration_comparable(elapsed, snapshot_horizon_f)
            else:
                prediction_comparable = False
            mem["session_prediction_time_aligned"] = False

        snapshot_frame_valid = bool(session_activity_eligible)
        end_frame_valid = bool(
            session_activity_eligible
            and validation_end_ah is not None
            and validation_end_temp is not None
        )
        if learning_contaminated or not snapshot_frame_valid or not end_frame_valid:
            prediction_comparable = False

        # Objective validation and adaptive forecast learning share the same
        # mandatory timestamp-activity gate. Legacy frame classes remain
        # diagnostic metadata only; neither ``held`` nor ``excellent`` may
        # bypass a missing in-session report from temperature or humidity.
        start_learning_valid = session_activity_eligible
        end_learning_valid = session_activity_eligible
        prediction_learning_eligible = bool(
            session_activity_eligible
            and original_snapshot_valid
            and prediction_time_aligned
            and start_learning_valid
            and end_learning_valid
        )
        mem["session_prediction_snapshot_valid"] = bool(prediction_learning_eligible)
        activity_weight = float(session_quality.get("learning_weight", 0.0) or 0.0)
        mem["session_prediction_learning_weight"] = activity_weight if session_activity_eligible else 0.0
        feedback_processed = False if learning_contaminated else learn_outcome_feedback(mem, session_removed, temp_delta)
        feedback_learned = bool(feedback_processed and mem.get("last_outcome_feedback_applied", False))
        mem["session_prediction_snapshot_valid"] = bool(original_snapshot_valid)
        if learning_contaminated:
            feedback_action = "skipped"
            feedback_reason = ("Lernanpassung übersprungen, weil die Referenzluft während der Lüftung feuchter wurde." if reference_moisture_reversal else "Lernanpassung übersprungen, weil während der Lüftung eine interne Feuchtequelle erkannt wurde.")
            feedback_accuracy = None
        elif feedback_processed:
            feedback_action = mem.get("last_outcome_feedback_action")
            feedback_reason = mem.get("last_outcome_feedback_reason")
            feedback_accuracy = mem.get("last_outcome_feedback_accuracy")
        else:
            feedback_action = "skipped"
            if prediction_time_aligned and (not snapshot_frame_valid or not end_frame_valid):
                feedback_reason = "Die Startprognose wurde auf exakt dieselbe Messdauer abgeglichen, aber Temperatur und Luftfeuchtigkeit haben während dieser Lüftung nicht beide mindestens einen neueren Sensor-Zeitstempel geliefert. Deshalb werden weder Prognosegenauigkeit noch Lernmodell aus diesem Vergleich angepasst. Die Lern-Auswertung kann deshalb verzögert erscheinen."
            elif prediction_time_aligned:
                feedback_reason = "Startprognose wurde mit exakt derselben Messdauer verglichen. Für diese Lüftung wurde daraus keine Modellanpassung abgeleitet."
            elif original_snapshot_valid and mem.get("session_prediction_horizon_min") is not None and not prediction_comparable:
                feedback_reason = "Ältere Startprognose ohne eingefrorene Startkurve konnte nicht zuverlässig auf die tatsächliche Messdauer abgeglichen werden. Sie verändert das Prognosemodell nicht."
            else:
                feedback_reason = "Beim bestätigten Lüftungsstart konnte keine Startprognose eingefroren werden; diese Lüftung wird deshalb nicht zur Prognoseanpassung verwendet."
            feedback_accuracy = None
        return (feedback_accuracy, feedback_action, feedback_learned, feedback_reason, learning_effectiveness_sample, prediction_comparable, prediction_time_aligned, validation_elapsed, validation_removed, validation_started, validation_temp_delta)
