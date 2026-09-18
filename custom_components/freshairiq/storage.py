"""Persistent learning, session, statistics and notification store."""
from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import LEGACY_DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .robustness import sanitize_runtime_session


def _safe_date(value: Any):
    """Return an ISO date or ``None`` for corrupt persisted keys."""
    try:
        return datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _finite_number(value: Any, default: float = 0.0) -> float:
    """Coerce persisted/runtime numeric input without allowing NaN/inf."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if isfinite(number) else default


AGGREGATE_HISTORY_DAYS = 730
RAW_TEMPERATURE_HISTORY_DAYS = 30


def _room_defaults() -> dict[str, Any]:
    return {
        "learning_rate": 0.03,
        "learning_samples": 0,
        "learning_sample_credit": 0.0,
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
        "session_result_base_ml": 0.0,
        "session_result_ml": 0.0,
        "close_notified": False,
        "session_fresh_measurements": 0,
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
        # Time-resolved cross-ventilation tracking.  A boolean sampled only at
        # session close is wrong because closing the contact itself ends the
        # cross-flow before the result is calculated.
        "session_cross_active": False,
        "session_cross_seconds": 0.0,
        "session_cross_last_update": None,
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


class LearningStore:
    """State that must survive Home Assistant restarts and integration reloads."""

    def __init__(self, hass: HomeAssistant, entry_id: str, legacy_entry_id: str | None = None) -> None:
        self._hass = hass
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        self._legacy_entry_id = legacy_entry_id
        self.data: dict[str, Any] = {
            "rooms": {},
            "last_diagnosis": "",
            "history": {},
            "temperature_points": [],
            "night_model_ml_h": None,
            "night_model_samples": 0,
            "night_last_snapshot": None,
            "night_last_water_ml": None,
            "night_observed_dates": [],
            "notifications": {},
            "last_house_status": None,
            "last_night_notification_date": None,
            "last_ventilation": None,
            "ventilation_group": None,
            "water_daily": {},
            "iq_active_advice": None,
            "house_strategy_buckets": {},
            "house_strategy_samples": 0,
            "house_strategy_successes": 0,
            "house_strategy_total_removed_ml": 0.0,
            "house_strategy_total_minutes": 0.0,
            "house_strategy_observation_dates": [],
            "forecast_validation_history": [],
            "post_close_stabilization_history": [],
        }

    async def async_load(self) -> None:
        saved = await self._store.async_load()
        if isinstance(saved, dict):
            self.data.update(saved)
            self._normalise()
            return
        if self._legacy_entry_id:
            legacy_store = Store(
                self._hass, 1, f"{LEGACY_DOMAIN}.learning.{self._legacy_entry_id}"
            )
            legacy_saved = await legacy_store.async_load()
            if isinstance(legacy_saved, dict):
                self.data.update(legacy_saved)
                self._normalise()
                await self.async_save()

    def _normalise(self) -> None:
        self.data.setdefault("rooms", {})
        self.data.setdefault("history", {})
        self.data.setdefault("temperature_points", [])
        self.data.setdefault("notifications", {})
        self.data.setdefault("night_model_ml_h", None)
        self.data.setdefault("night_model_samples", 0)
        self.data.setdefault("night_observed_dates", [])
        if not isinstance(self.data.get("night_observed_dates"), list):
            self.data["night_observed_dates"] = []
        self.data.setdefault("last_ventilation", None)
        self.data.setdefault("ventilation_group", None)
        if self.data.get("ventilation_group") is not None and not isinstance(self.data.get("ventilation_group"), dict):
            self.data["ventilation_group"] = None
        elif isinstance(self.data.get("ventilation_group"), dict) and not isinstance(self.data["ventilation_group"].get("sessions", []), list):
            self.data["ventilation_group"]["sessions"] = []
        self.data.setdefault("iq_active_advice", None)
        self.data.setdefault("water_daily", {})
        if not isinstance(self.data.get("rooms"), dict):
            self.data["rooms"] = {}
        if not isinstance(self.data.get("history"), dict):
            self.data["history"] = {}
        if not isinstance(self.data.get("notifications"), dict):
            self.data["notifications"] = {}
        if not isinstance(self.data.get("water_daily"), dict):
            self.data["water_daily"] = {}
        if not isinstance(self.data.get("house_strategy_buckets"), dict):
            self.data["house_strategy_buckets"] = {}
        self.data.setdefault("house_strategy_buckets", {})
        self.data.setdefault("house_strategy_samples", 0)
        self.data.setdefault("house_strategy_successes", 0)
        self.data.setdefault("house_strategy_total_removed_ml", 0.0)
        self.data.setdefault("house_strategy_total_minutes", 0.0)
        self.data.setdefault("house_strategy_observation_dates", [])
        if not isinstance(self.data.get("house_strategy_observation_dates"), list):
            self.data["house_strategy_observation_dates"] = []
        if not isinstance(self.data.get("forecast_validation_history"), list):
            self.data["forecast_validation_history"] = []
        self.data.setdefault("forecast_validation_history", [])
        if not isinstance(self.data.get("post_close_stabilization_history"), list):
            self.data["post_close_stabilization_history"] = []
        self.data.setdefault("post_close_stabilization_history", [])
        self._sanitize_global_learning()
        # Corrupt/hand-edited learning storage must degrade to defaults rather
        # than poisoning every future coordinator refresh with TypeError/NaN.
        for room_key, raw_room in list(self.data["rooms"].items()):
            if not isinstance(raw_room, dict):
                raw_room = _room_defaults()
                self.data["rooms"][room_key] = raw_room
            room = raw_room
            defaults = _room_defaults()
            for key, value in defaults.items():
                if isinstance(value, dict) and not isinstance(room.get(key), dict):
                    room[key] = {}
                elif isinstance(value, list) and not isinstance(room.get(key), list):
                    room[key] = []
                else:
                    room.setdefault(key, value)
            self._sanitize_room_learning(room)
            sanitize_runtime_session(room)

    def _sanitize_global_learning(self) -> None:
        """Repair impossible/non-finite house-level adaptive persistence."""
        def finite(value: Any) -> float | None:
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                return None
            return number if isfinite(number) else None

        night_rate = self.data.get("night_model_ml_h")
        if night_rate is not None and finite(night_rate) is None:
            self.data["night_model_ml_h"] = None
        for key in ("night_model_samples", "house_strategy_samples", "house_strategy_successes"):
            value = finite(self.data.get(key))
            self.data[key] = 0 if value is None else min(max(int(value), 0), 100000)
        for key in ("house_strategy_total_removed_ml", "house_strategy_total_minutes"):
            value = finite(self.data.get(key))
            self.data[key] = 0.0 if value is None else max(value, 0.0)

    @staticmethod
    def _sanitize_room_learning(room: dict[str, Any]) -> None:
        """Repair only impossible/non-finite adaptive values.

        Valid learned values are never reset. Bounds mirror existing model guards
        so corrupted persistence cannot bypass the same physical safety envelope.
        """
        def finite(value: Any) -> float | None:
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                return None
            return number if isfinite(number) else None

        rate = finite(room.get("learning_rate"))
        room["learning_rate"] = 0.03 if rate is None else min(max(rate, 0.002), 0.25)
        for key in ("learning_samples", "forecast_observation_samples", "thermal_rate_samples", "outcome_feedback_samples", "outcome_successes", "shadow_learning_samples", "shadow_learning_total_samples", "shadow_learning_promotions", "shadow_learning_rollbacks", "shadow_learning_cooldown", "shadow_rollback_samples", "shadow_rollback_previous_wins"):
            value = finite(room.get(key))
            room[key] = 0 if value is None else min(max(int(value), 0), 1000)
        sample_credit = finite(room.get("learning_sample_credit"))
        room["learning_sample_credit"] = 0.0 if sample_credit is None else min(max(sample_credit, 0.0), 0.999999)
        removed_factor = finite(room.get("outcome_removed_factor"))
        room["outcome_removed_factor"] = 1.0 if removed_factor is None else min(max(removed_factor, 0.40), 1.70)
        temp_factor = finite(room.get("outcome_temperature_factor"))
        room["outcome_temperature_factor"] = 1.0 if temp_factor is None else min(max(temp_factor, 0.40), 1.70)
        if not isinstance(room.get("shadow_learning_candidates"), dict):
            room["shadow_learning_candidates"] = {}
        for key in ("shadow_rollback_previous_factor", "shadow_rollback_promoted_factor"):
            value = room.get(key)
            if value is not None and finite(value) is None:
                room[key] = None
        for key in ("shadow_rollback_active_error", "shadow_rollback_previous_error"):
            value = finite(room.get(key))
            room[key] = 0.0 if value is None or value < 0 else value
        for key in ("forecast_source_ml_min", "forecast_thermal_residual_c_min", "long_term_source_ml_min"):
            value = room.get(key)
            if value is not None and finite(value) is None:
                room[key] = None

    def room(self, key: str) -> dict[str, Any]:
        rooms = self.data.setdefault("rooms", {})
        room = rooms.setdefault(key, _room_defaults())
        if not isinstance(room, dict):
            room = _room_defaults()
            rooms[key] = room
        defaults = _room_defaults()
        for k, v in defaults.items():
            room.setdefault(k, v)
        self._sanitize_room_learning(room)
        sanitize_runtime_session(room)
        return room

    async def async_save(self) -> None:
        await self._store.async_save(self.data)

    async def async_reset_learning(self) -> None:
        """Reset adaptive learning only; keep configuration and statistics."""
        for key in list(self.data.setdefault("rooms", {})):
            old = self.data["rooms"][key]
            active = bool(old.get("session_active"))
            fresh = _room_defaults()
            fresh["history"] = old.get("history", {})
            fresh["temperature_points"] = old.get("temperature_points", [])
            fresh["last_measurement_at"] = old.get("last_measurement_at")
            fresh["last_measurement_valid"] = old.get("last_measurement_valid")
            # Preserve a currently running session so a reset cannot corrupt it.
            if active:
                for field in (
                    "session_active", "session_started", "session_physical_started", "session_start_ah",
                    "session_start_source_ah", "session_learning_start_ah", "session_learning_source_ah",
                    "session_start_temp", "session_result_base_ml",
                    "session_result_ml", "close_notified",
                    "session_fresh_measurements", "session_temperature_reports", "session_humidity_reports",
                    "session_last_temperature_update", "session_last_humidity_update",
                    "session_open_temperature_reported_at", "session_open_humidity_reported_at",
                    "session_last_valid_temperature", "session_last_valid_humidity",
                    "session_last_valid_reference_temperature", "session_last_valid_reference_humidity",
                    "session_last_valid_at",
                    "session_close_pending", "session_close_detected_at", "session_close_wait_started_at",
                    "session_close_deadline_at", "session_close_temperature_baseline",
                    "session_close_humidity_baseline", "session_close_temperature_feedback",
                    "session_close_humidity_feedback", "session_close_refresh_requested_at",
                    "session_moisture_source_detected", "session_cross_active",
                    "session_cross_seconds", "session_cross_last_update",
                    "session_recommended_duration_min", "session_recommendation_followed",
                    "session_recommendation_issued_at", "session_predicted_removed_ml",
                    "session_predicted_temperature_change_c", "session_predicted_cost",
                    "session_prediction_confidence", "session_prediction_snapshot_at",
                    "session_prediction_horizon_min", "session_prediction_snapshot_elapsed_min", "session_prediction_snapshot_valid",
                    "session_prediction_snapshot_pending", "session_prediction_reference",
                    "session_validation_id", "session_prediction_start_context", "session_prediction_time_aligned",
                    "session_selected_option_id", "session_forecast_timeline",
                    "session_timeline_last_checkpoint_min",
                    "session_start_frame_quality", "session_start_frame_skew_s",
                    "session_start_frame_max_age_s", "session_start_frame_learning_eligible",
                    "session_prediction_snapshot_frame_quality", "session_prediction_snapshot_frame_skew_s",
                    "session_prediction_snapshot_frame_max_age_s",
                ):
                    fresh[field] = old.get(field)
            self.data["rooms"][key] = fresh
        self.data["last_diagnosis"] = "Learning data reset manually"
        self.data["night_model_ml_h"] = None
        self.data["night_model_samples"] = 0
        self.data["night_last_snapshot"] = None
        self.data["night_last_water_ml"] = None
        self.data["iq_active_advice"] = None
        self.data["house_strategy_buckets"] = {}
        self.data["house_strategy_samples"] = 0
        self.data["house_strategy_successes"] = 0
        self.data["house_strategy_total_removed_ml"] = 0.0
        self.data["house_strategy_total_minutes"] = 0.0
        await self.async_save()

    async def async_reset_statistics(self) -> None:
        """Reset all statistics while preserving adaptive learning and live sessions."""
        self.data["history"] = {}
        self.data["temperature_points"] = []
        self.data["water_daily"] = {}
        self.data["last_ventilation"] = None
        self.data["forecast_validation_history"] = []
        for room in self.data.setdefault("rooms", {}).values():
            room["history"] = {}
            room["temperature_points"] = []
        await self.async_save()


    def record_house_water(self, when: datetime, total_water_ml: float) -> bool:
        """Persist a representative daily mean without oversampling sensor bursts."""
        last_raw = self.data.get("water_last_sample_at")
        if last_raw:
            try:
                last = datetime.fromisoformat(str(last_raw))
                if (when - last).total_seconds() < 60:
                    return False
            except (TypeError, ValueError):
                pass
        self.data["water_last_sample_at"] = when.isoformat()
        day = when.date().isoformat()
        water_daily = self.data.get("water_daily")
        if not isinstance(water_daily, dict):
            water_daily = {}
            self.data["water_daily"] = water_daily
        row = water_daily.setdefault(day, {"sum_ml": 0.0, "samples": 0, "mean_ml": 0.0})
        if not isinstance(row, dict):
            row = {"sum_ml": 0.0, "samples": 0, "mean_ml": 0.0}
            water_daily[day] = row
        row["sum_ml"] = _finite_number(row.get("sum_ml")) + max(_finite_number(total_water_ml), 0.0)
        row["samples"] = max(int(_finite_number(row.get("samples"))), 0) + 1
        row["mean_ml"] = round(row["sum_ml"] / max(row["samples"], 1), 1)
        cutoff = when.date() - timedelta(days=AGGREGATE_HISTORY_DAYS - 1)
        self.data["water_daily"] = {
            day_key: row_data
            for day_key, row_data in self.data["water_daily"].items()
            if (parsed_day := _safe_date(day_key)) is not None and parsed_day >= cutoff
        }
        return True

    def water_history_days(self, days: int = 14) -> list[dict[str, Any]]:
        hist = self.data.get("water_daily")
        if not isinstance(hist, dict):
            hist = {}
            self.data["water_daily"] = hist
        today = dt_util.now().date(); out=[]
        for offset in range(days-1,-1,-1):
            day=(today-timedelta(days=offset)).isoformat(); row=hist.get(day,{})
            if not isinstance(row, dict): row = {}
            out.append({"date":day,"water_ml":round(_finite_number(row.get("mean_ml",0.0))),"samples":max(int(_finite_number(row.get("samples",0))),0)})
        for i,x in enumerate(out):
            x["trend"]="stable"
            prev=next((out[j]["water_ml"] for j in range(i-1,-1,-1) if out[j]["samples"]>0),None)
            if prev and x["samples"]>0:
                change=(x["water_ml"]-prev)/prev
                x["trend"]="wetter" if change>0.03 else "trockener" if change<-0.03 else "stabil"
        return out

    def record_session(self, when: datetime, removed_ml: float, duration_min: float, temp_delta_c: float, energy_kwh: float, cost: float, room_key: str | None = None, *, moisture_valid: bool = True) -> None:
        day = when.date().isoformat()
        row = self.data.setdefault("history", {}).setdefault(day, {
            "removed_ml": 0.0, "sessions": 0, "moisture_measured_sessions": 0, "moisture_unmeasured_sessions": 0, "ventilation_minutes": 0.0,
            "energy_kwh": 0.0, "cost": 0.0, "temp_loss_sum_c": 0.0,
        })
        removed = _finite_number(removed_ml) if moisture_valid else 0.0
        duration = max(_finite_number(duration_min), 0.0)
        energy = max(_finite_number(energy_kwh), 0.0)
        session_cost = max(_finite_number(cost), 0.0)
        temp_delta = _finite_number(temp_delta_c)
        row["removed_ml"] = round(_finite_number(row.get("removed_ml")) + removed, 1)
        row["sessions"] = max(int(_finite_number(row.get("sessions"))), 0) + 1
        row["moisture_measured_sessions"] = max(int(_finite_number(row.get("moisture_measured_sessions"))), 0) + int(bool(moisture_valid))
        row["moisture_unmeasured_sessions"] = max(int(_finite_number(row.get("moisture_unmeasured_sessions"))), 0) + int(not bool(moisture_valid))
        row["ventilation_minutes"] = round(_finite_number(row.get("ventilation_minutes")) + duration, 1)
        row["energy_kwh"] = round(_finite_number(row.get("energy_kwh")) + energy, 4)
        row["cost"] = round(_finite_number(row.get("cost")) + session_cost, 4)
        row["temp_loss_sum_c"] = round(_finite_number(row.get("temp_loss_sum_c")) + min(temp_delta, 0.0), 2)
        if room_key:
            room = self.room(room_key)
            rrow = room.setdefault("history", {}).setdefault(day, {
                "removed_ml": 0.0, "sessions": 0, "moisture_measured_sessions": 0, "moisture_unmeasured_sessions": 0, "ventilation_minutes": 0.0,
                "energy_kwh": 0.0, "cost": 0.0, "temp_loss_sum_c": 0.0,
            })
            rrow["removed_ml"] = round(_finite_number(rrow.get("removed_ml")) + removed, 1)
            rrow["sessions"] = max(int(_finite_number(rrow.get("sessions"))), 0) + 1
            rrow["moisture_measured_sessions"] = max(int(_finite_number(rrow.get("moisture_measured_sessions"))), 0) + int(bool(moisture_valid))
            rrow["moisture_unmeasured_sessions"] = max(int(_finite_number(rrow.get("moisture_unmeasured_sessions"))), 0) + int(not bool(moisture_valid))
            rrow["ventilation_minutes"] = round(_finite_number(rrow.get("ventilation_minutes")) + duration, 1)
            rrow["energy_kwh"] = round(_finite_number(rrow.get("energy_kwh")) + energy, 4)
            rrow["cost"] = round(_finite_number(rrow.get("cost")) + session_cost, 4)
            rrow["temp_loss_sum_c"] = round(_finite_number(rrow.get("temp_loss_sum_c")) + min(temp_delta, 0.0), 2)
        self.prune(AGGREGATE_HISTORY_DAYS)

    def record_room_temperature_point(self, room_key: str, when: datetime, temperature_c: float, days: int = 30) -> bool:
        points = self.room(room_key).setdefault("temperature_points", [])
        if not isinstance(points, list):
            points = []
            self.room(room_key)["temperature_points"] = points
        hour_key = when.strftime("%Y-%m-%dT%H:00")
        last_point = points[-1] if points and isinstance(points[-1], dict) else None
        if last_point and last_point.get("time") == hour_key:
            last_point["temperature_c"] = round(_finite_number(temperature_c), 2)
            return False
        points.append({"time": hour_key, "temperature_c": round(_finite_number(temperature_c), 2)})
        cutoff = when - timedelta(days=max(1, min(int(days), RAW_TEMPERATURE_HISTORY_DAYS)), hours=2)
        clean_points = []
        for point in points:
            try:
                if datetime.fromisoformat(str(point.get("time"))) >= cutoff.replace(tzinfo=None):
                    clean_points.append(point)
            except (AttributeError, TypeError, ValueError, OverflowError):
                continue
        self.room(room_key)["temperature_points"] = clean_points
        return True

    def room_history_days(self, room_key: str, days: int = 14) -> list[dict[str, Any]]:
        room = self.room(room_key)
        history = room.get("history")
        if not isinstance(history, dict):
            history = {}
            room["history"] = history
        try:
            days = max(1, min(int(days), AGGREGATE_HISTORY_DAYS))
        except (TypeError, ValueError, OverflowError):
            days = 14
        today = dt_util.now().date(); rows = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            row = {"date": day, "removed_ml": 0.0, "sessions": 0, "moisture_measured_sessions": 0, "moisture_unmeasured_sessions": 0, "ventilation_minutes": 0.0, "energy_kwh": 0.0, "cost": 0.0, "temp_loss_sum_c": 0.0}
            stored = history.get(day, {})
            if isinstance(stored, dict):
                row.update(stored)
            rows.append(row)
        return rows

    def room_temperature_points(self, room_key: str, days: int = 14) -> list[dict[str, Any]]:
        cutoff = dt_util.now().replace(tzinfo=None) - timedelta(days=max(1, min(int(days), RAW_TEMPERATURE_HISTORY_DAYS)), hours=1)
        rows=[]
        for point in self.room(room_key).setdefault("temperature_points", []):
            try:
                if datetime.fromisoformat(point["time"]) >= cutoff: rows.append(point)
            except (ValueError, TypeError, KeyError): pass
        return rows

    def record_temperature_point(self, when: datetime, temperature_c: float, days: int = 30) -> bool:
        points = self.data.setdefault("temperature_points", [])
        if not isinstance(points, list):
            points = []
            self.data["temperature_points"] = points
        hour_key = when.strftime("%Y-%m-%dT%H:00")
        last_point = points[-1] if points and isinstance(points[-1], dict) else None
        if last_point and last_point.get("time") == hour_key:
            last_point["temperature_c"] = round(_finite_number(temperature_c), 2)
            return False
        points.append({"time": hour_key, "temperature_c": round(_finite_number(temperature_c), 2)})
        cutoff = when - timedelta(days=max(1, min(int(days), RAW_TEMPERATURE_HISTORY_DAYS)), hours=2)
        clean_points = []
        for point in points:
            try:
                if datetime.fromisoformat(str(point.get("time"))) >= cutoff.replace(tzinfo=None):
                    clean_points.append(point)
            except (AttributeError, TypeError, ValueError, OverflowError):
                continue
        self.data["temperature_points"] = clean_points
        return True

    def temperature_points(self, days: int = 14) -> list[dict[str, Any]]:
        """Return stored hourly temperature points for the requested 1–30 day window."""
        days = max(1, min(int(days), RAW_TEMPERATURE_HISTORY_DAYS))
        cutoff = dt_util.now().replace(tzinfo=None) - timedelta(days=days, hours=1)
        rows = []
        for point in self.data.setdefault("temperature_points", []):
            try:
                if datetime.fromisoformat(point["time"]) >= cutoff:
                    rows.append(point)
            except (ValueError, TypeError, KeyError):
                continue
        return rows

    def history_days(self, days: int = 14) -> list[dict[str, Any]]:
        history = self.data.get("history")
        if not isinstance(history, dict):
            history = {}
            self.data["history"] = history
        try:
            days = max(1, min(int(days), AGGREGATE_HISTORY_DAYS))
        except (TypeError, ValueError, OverflowError):
            days = 14
        today = dt_util.now().date()
        rows = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            row = {
                "date": day, "removed_ml": 0.0, "sessions": 0,
                "moisture_measured_sessions": 0, "moisture_unmeasured_sessions": 0,
                "ventilation_minutes": 0.0, "energy_kwh": 0.0, "cost": 0.0,
                "temp_loss_sum_c": 0.0,
            }
            stored = history.get(day, {})
            if isinstance(stored, dict):
                row.update(stored)
            rows.append(row)
        return rows

    def prune(self, days: int = AGGREGATE_HISTORY_DAYS) -> None:
        """Prune aggregate history without letting corrupt persistence abort refreshes."""
        retention_days = max(1, min(int(days), AGGREGATE_HISTORY_DAYS))
        cutoff = dt_util.now().date() - timedelta(days=retention_days - 1)

        def _clean(history: Any) -> dict[str, Any]:
            if not isinstance(history, dict):
                return {}
            return {
                str(day): row
                for day, row in history.items()
                if (parsed_day := _safe_date(day)) is not None and parsed_day >= cutoff
                and isinstance(row, dict)
            }

        self.data["history"] = _clean(self.data.setdefault("history", {}))
        for room_key, room in list(self.data.setdefault("rooms", {}).items()):
            if not isinstance(room, dict):
                room = _room_defaults()
                self.data["rooms"][room_key] = room
            room["history"] = _clean(room.setdefault("history", {}))
