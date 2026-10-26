"""Privacy-safe diagnostics helpers: allow-listed keys, sanitising and compact summaries."""
from __future__ import annotations

import hashlib
import json
import platform
from copy import deepcopy
from datetime import datetime
from math import isfinite
from typing import Any


# Only analysis-relevant, non-entity options are exported.  Entity lists,
# notification targets and other potentially identifying configuration values
# are intentionally excluded.
_SAFE_OPTION_KEYS = (
    "start_rh", "high_rh", "target_rh", "min_delta", "min_delta_high_rh",
    "close_delta", "threshold_mode", "min_potential_percent_total_water",
    "min_potential_total_ml", "min_potential_room_ml", "min_duration_min",
    "max_duration_min", "min_return_next_5_min_ml",
    "post_ventilation_stabilization_min", "repeat_recommendation_cooldown_min",
    "repeat_min_benefit_ml", "repeat_weather_improvement_g_m3",
    "moisture_source_postrun_min", "house_ventilation_enter_ratio",
    "house_ventilation_exit_ratio", "forecast_horizon_min",
    "max_temp_loss_next_5_min_c", "min_efficiency_ml_per_01c",
    "surface_factor", "mould_warn_surface_rh", "mould_critical_surface_rh",
    "co2_warn", "co2_critical", "voc_sensor_enabled", "pm25_sensor_enabled",
    "illuminance_sensor_enabled", "voc_warn", "voc_critical", "pm25_warn",
    "pm25_critical", "humidify_below_rh", "shade_above_temp_c",
    "shade_min_illuminance_lx", "shade_lead_min", "shade_forecast_max_c", "shade_max_cloud_coverage", "learning_enabled", "learning_max_duration_min",
    "cover_position_zero_means", "cover_learning_max_closed_percent",
    "cross_ventilation_pairs", "cross_zone_connections", "operating_profile",
    "personalisation_enabled", "thermal_preference", "personal_priority",
    "night_window_preference", "cooling_start_temp_c",
    "cooling_min_outdoor_delta_c", "cooling_max_indoor_rh",
    "cooling_max_moisture_gain_5min_ml", "property_type", "adult_occupants",
    "child_occupants", "untracked_follow_household", "presence_night_hold", "pets_in_household",
    "guest_adults", "guest_children", "night_start_hour", "night_end_hour",
    "night_forecast_enabled", "adult_night_moisture_ml_h",
    "child_night_moisture_ml_h", "background_night_moisture_ml_h",
    "adult_day_moisture_ml", "child_day_moisture_ml",
    "household_day_moisture_ml", "pollen_enabled", "pollen_max", "outdoor_pm25_enabled", "outdoor_pm25_max",
    "pollen_strict_veto", "wind_orientation_enabled", "heating_system",
    "electricity_price_per_kwh", "heat_pump_cop", "gas_price_per_kwh",
    "gas_efficiency", "district_price_per_kwh", "district_efficiency",
    "oil_price_per_liter", "oil_kwh_per_liter", "oil_efficiency",
    "energy_price_per_kwh", "heating_efficiency", "notifications_enabled",
    "notification_scope", "notification_room_keys", "notify_ventilate",
    "notify_close", "notify_complete", "notify_mould", "notify_sensor",
    "notify_night", "notify_learning", "notify_cooling",
    "notification_cooldown_min", "notify_status_messages", "action_reminder_min",
    "suppress_notifications_at_night", "notify_only_when_home",
    "notify_important_when_away", "statistics_days", "dashboard_show_temperature",
    "dashboard_show_time", "dashboard_show_next5", "dashboard_show_night",
    "dashboard_show_mould", "dashboard_show_history",
    "diagnostics_reporting_mode", "diagnostics_consent", "diagnostics_include_client_context",
)


def _collection_size(value: Any) -> int:
    if isinstance(value, (list, tuple, dict)):
        return min(len(value), 1_000_000)
    return 0


def _latest_evidence(value: Any) -> Any:
    if isinstance(value, list):
        return value[-1] if value else {}
    if not isinstance(value, dict):
        return {}
    compact = dict(value)
    for key in ("history", "records", "samples", "validations", "entries", "observations"):
        raw = compact.get(key)
        if isinstance(raw, list):
            compact[f"{key}_count"] = len(raw)
            compact[f"latest_{key[:-1] if key.endswith('s') else key}"] = raw[-1] if raw else None
            compact.pop(key, None)
    return compact


def _compact_learning_components(value: Any) -> Any:
    if not isinstance(value, (dict, list)):
        return {}
    if isinstance(value, list):
        return [_latest_evidence(item) if isinstance(item, dict) else item for item in value[:64]]
    return {str(key): _latest_evidence(item) if isinstance(item, dict) else item for key, item in value.items()}


def _safe_int(value: Any, default: int = 0, *, low: int = 0, high: int = 1_000_000) -> int:
    """Return a bounded integer for persisted/runtime diagnostic counters."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(number):
        return default
    return min(max(int(number), low), high)


def _json_safe(value: Any) -> Any:
    """Return JSON-safe values without leaking HA objects."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _sha256_json(value: Any) -> str:
    """Return a deterministic fingerprint for privacy-safe JSON data."""
    payload = json.dumps(_json_safe(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _bounded_text(value: Any, max_length: int = 96) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:max_length] if text else None


def _sanitise_client_context(value: Any) -> dict[str, Any]:
    """Whitelist anonymous client facts; never retain the raw User-Agent."""
    if not isinstance(value, dict):
        return {}
    client_id = _bounded_text(value.get("client_id"), 96)
    if not client_id:
        return {}
    client_prefix = "faiq-client-session-" if client_id.startswith("faiq-client-session-") else "faiq-client-"
    if not client_id.startswith(client_prefix):
        return {}
    client_token = client_id[len(client_prefix):]
    if not (12 <= len(client_token) <= 64 and client_token.isalnum()):
        return {}
    platform_family = _bounded_text(value.get("platform_family"), 24)
    if platform_family not in {"iOS", "iPadOS", "Android", "Windows", "macOS", "Linux", "Other"}:
        platform_family = "Other"
    device_class = _bounded_text(value.get("device_class"), 16)
    if device_class not in {"phone", "tablet", "desktop", "other"}:
        device_class = "other"

    def _num(key: str, low: float, high: float, integer: bool = False):
        try:
            number = float(value.get(key))
        except (TypeError, ValueError, OverflowError):
            return None
        if not isfinite(number) or not low <= number <= high:
            return None
        return int(round(number)) if integer else round(number, 3)

    def _dims(key: str):
        raw = value.get(key)
        if not isinstance(raw, dict):
            return None
        try:
            width = int(round(float(raw.get("width", 0))))
            height = int(round(float(raw.get("height", 0))))
        except (TypeError, ValueError, OverflowError):
            return None
        if not (0 <= width <= 20000 and 0 <= height <= 20000):
            return None
        return {"width": width, "height": height}

    return {
        "client_id": client_id,
        "client_id_persistence": _bounded_text(value.get("client_id_persistence"), 24),
        "platform_family": platform_family,
        "os_version": _bounded_text(value.get("os_version"), 48),
        "device_class": device_class,
        "device_family": _bounded_text(value.get("device_family"), 48),
        "device_model": _bounded_text(value.get("device_model"), 80),
        "companion_app": bool(value.get("companion_app")),
        "companion_app_version": _bounded_text(value.get("companion_app_version"), 48),
        "browser_family": _bounded_text(value.get("browser_family"), 32),
        "browser_version": _bounded_text(value.get("browser_version"), 48),
        "webview_engine_version": _bounded_text(value.get("webview_engine_version"), 48),
        "home_assistant_version_reported_by_frontend": _bounded_text(value.get("home_assistant_version_reported_by_frontend"), 48),
        "freshairiq_frontend_version": _bounded_text(value.get("freshairiq_frontend_version"), 48),
        "viewport_css_px": _dims("viewport_css_px"),
        "screen_css_px": _dims("screen_css_px"),
        "device_pixel_ratio": _num("device_pixel_ratio", 0.1, 20.0),
        "touch_points": _num("touch_points", 0, 100, True),
        "standalone_display_mode": bool(value.get("standalone_display_mode")),
    }


def _runtime_environment_snapshot() -> dict[str, Any]:
    """Return a small local fallback when HA system_info is unavailable."""
    try:
        from homeassistant.const import __version__ as ha_version
    except (ImportError, AttributeError):
        ha_version = None
    return {
        "home_assistant_version": _json_safe(ha_version),
        "python_version": platform.python_version(),
        "os_name": platform.system() or None,
        "os_version": platform.release() or None,
        "architecture": platform.machine() or None,
        "python_implementation": platform.python_implementation() or None,
    }


def _longest_consecutive_day_streak(days: list[str]) -> int:
    parsed = []
    for value in days:
        try:
            parsed.append(datetime.fromisoformat(value).date())
        except (TypeError, ValueError):
            continue
    if not parsed:
        return 0
    parsed = sorted(set(parsed))
    longest = current = 1
    for previous, current_day in zip(parsed, parsed[1:]):
        if (current_day - previous).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _privacy_safe_decision(value: Any) -> dict[str, Any]:
    """Return decision diagnostics without resident names or personalised text."""
    if not isinstance(value, dict):
        return {}
    out = deepcopy(value)
    for key in ("personal_context", "summary", "title", "instruction", "reasons"):
        out.pop(key, None)
    brain = out.get("decision_brain")
    if isinstance(brain, dict):
        brain = dict(brain)
        for key in ("personal_context", "summary", "headline", "action_line", "why"):
            brain.pop(key, None)
        out["decision_brain"] = brain
    return _json_safe(out)


def _privacy_safe_iq_state(value: Any) -> dict[str, Any]:
    """Return IQ diagnostics without personalised free text."""
    if not isinstance(value, dict):
        return {}
    out = deepcopy(value)
    out.pop("summary", None)
    out.pop("explanation", None)
    decision = out.get("decision")
    if isinstance(decision, dict):
        decision = dict(decision)
        decision.pop("title", None)
        decision.pop("instruction", None)
        out["decision"] = decision
    return _json_safe(out)


def _pick(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: _json_safe(source.get(key)) for key in keys if key in source}


def _three_state_learning_diagnostic(runtime: Any, stored: Any) -> dict[str, Any]:
    """Return privacy-safe three-state learning evidence without entity IDs.

    The nightly diagnostics need enough evidence to compare tilt/open/cross model
    maturity and forecast behaviour over time, but contact entity IDs and the
    entity-keyed passage behaviour map must never leave the installation.
    """
    runtime = runtime if isinstance(runtime, dict) else {}
    stored = stored if isinstance(stored, dict) else {}
    contacts = stored.get("three_state_contacts") or runtime.get("three_state_contacts") or []
    models = stored.get("opening_learning") or runtime.get("opening_learning") or {}
    if not isinstance(models, dict):
        models = {}

    def model(mode: str) -> dict[str, Any]:
        row = models.get(mode) if isinstance(models.get(mode), dict) else {}
        return {
            "rate_per_min": _json_safe(row.get("rate")),
            "samples": _safe_int(row.get("samples")),
            "credit": _json_safe(row.get("credit")),
        }

    passage = stored.get("passage_behavior") or runtime.get("passage_behavior") or {}
    passage_rows = list(passage.values()) if isinstance(passage, dict) else []
    passage_rows = [row for row in passage_rows if isinstance(row, dict)]
    return {
        "available": bool(contacts),
        "proven_contact_count": len(contacts) if isinstance(contacts, (list, tuple, set)) else 0,
        "current_opening_state": _json_safe(runtime.get("opening_state")),
        "opening_state_explicit": bool(runtime.get("opening_state_explicit")),
        "active_specialist_model": _json_safe(
            stored.get("session_specialist_opening_mode") or runtime.get("opening_learning_mode")
        ),
        "models": {"tilted": model("tilted"), "open": model("open"), "cross": model("cross")},
        "session_active": bool(stored.get("session_active")),
        "mixed_source_session": bool(stored.get("session_opening_mode_mixed")),
        "session_learning_quarantined": bool(stored.get("session_learning_quarantined")),
        "session_learning_quarantine_code": _json_safe(stored.get("session_learning_quarantine_code")),
        "session_predicted_removed_ml": _json_safe(stored.get("session_predicted_removed_ml")),
        "session_predicted_temperature_change_c": _json_safe(stored.get("session_predicted_temperature_change_c")),
        "session_prediction_confidence": _json_safe(stored.get("session_prediction_confidence")),
        "three_state_transients_suppressed": _safe_int(stored.get("three_state_transients_suppressed")),
        "passage_door_configured": bool(runtime.get("passage_door_configured")),
        "passage_pattern_count": len(passage_rows),
        "passage_patterns_learned": sum(1 for row in passage_rows if row.get("learned")),
    }


_TOP_LEVEL_KEYS = (
    "status", "status_text", "potential_total_ml", "actionable_potential_ml",
    "theoretical_potential_total_ml", "theoretical_actionable_potential_ml",
    "live_balance_ml", "next_5_min_effect_ml", "moisture_gain_next_5_min_ml",
    "forecast_horizon_min", "forecast_moisture_effect_ml",
    "forecast_temperature_change_c", "forecast_cost", "forecast_heat_kwh",
    "forecast_confidence", "prognosis_confidence", "max_surface_rh",
    "total_water_ml", "ventilation_threshold_ml", "ventilation_threshold_mode",
    "ventilation_threshold_reason", "cross_ventilation",
    "recommended_duration_min", "remaining_duration_min",
    "temperature_change_live_c", "operating_profile", "cooling_rooms",
    "overnight_forecast_ml", "overnight_forecast_base_ml",
    "overnight_weather_effect_ml", "overnight_trend_effect_ml",
    "overnight_routine_projection_ml", "overnight_routine_adjustment_ml",
    "routine_night_maturity", "overnight_hours_remaining", "overnight_confidence",
    "night_model_ml_h", "night_model_samples", "night_recommendation",
    "effective_occupants", "effective_adults", "effective_children",
    "tracked_occupants", "home_tracked_occupants", "away_tracked_occupants",
    "unknown_tracked_occupants", "untracked_adults", "untracked_children",
    "guest_adults", "guest_children", "presence_confidence", "presence_explanation",
    "pets_in_household", "soft_presence_score", "property_type", "heating_system",
    "energy_price_per_kwh", "estimated_moisture_generation_day_ml",
    "configured_moisture_generation_day_ml", "estimated_generated_so_far_ml",
    "moisture_balance_today_ml", "pollen_enabled", "pollen_index", "pollen_limit", "outdoor_pm25", "outdoor_pm25_limit", "outdoor_pm25_blocked", "outdoor_air_veto_cause",
    "pollen_blocked", "wind_bearing", "wind_speed", "future_weather_available",
    "house_strategy_maturity", "house_strategy_samples", "sign_convention",
    "outdoor_temperature", "outdoor_humidity", "outdoor_absolute_humidity",
    "outdoor_data_quality",
)


_ROOM_KEYS = (
    "key", "name", "floor", "volume_m3", "calculation_enabled", "data_quality",
    "temperature", "humidity", "absolute_humidity", "water_in_air_ml",
    "reference_temperature", "reference_humidity", "reference_absolute_humidity",
    "surface_rh", "mould_level", "co2", "co2_available", "co2_data_quality",
    "voc", "voc_available", "voc_enabled", "voc_configured",
    "pm25", "pm25_available", "pm25_enabled", "pm25_configured",
    "illuminance", "illuminance_available", "illuminance_enabled", "illuminance_configured",
    "active", "open_seconds", "opening_state", "opening_state_explicit", "three_state_transition_suppressed", "three_state_transients_suppressed", "passage_door_configured", "learning_quarantined", "learning_quarantine_code", "opening_diagnostic_codes",
    "airflow_factor", "window_orientation", "action", "reason",
    "recommendation_reasons", "potential_ml", "realistic_potential_ml", "result_ml",
    "forecast_horizon_min", "forecast_moisture_effect_ml",
    "forecast_temperature_change_c", "forecast_cost", "forecast_heat_kwh",
    "moisture_effect_next_5_min_ml", "temp_next_5_min_c", "learning_status",
    "learning_samples", "learning_sample_credit", "learned_exchange_rate_per_min", "learning_diagnosis",
    "last_learning_at", "last_learning_valid", "last_measurement_at",
    "last_measurement_valid", "measurement_frame_quality", "measurement_frame_learning_eligible",
    "measurement_frame_skew_s", "measurement_frame_full_skew_s", "measurement_frame_reference_skew_s", "measurement_frame_max_age_s", "frame_age_temp_s",
    "frame_age_humidity_s", "frame_age_reference_temp_s", "frame_age_reference_humidity_s",
    "measurement_frame_reason", "post_close_stabilization_active", "post_close_stabilization", "outcome_feedback_samples", "outcome_success_rate",
    "outcome_removed_factor", "routine_source_samples", "routine_maturity",
    "routine_expected_source_ml_min", "strategy_samples", "strategy_maturity",
    "strategy_outcome_samples",
    "recommendation_opportunities", "recommendation_followed",
    "recommendation_missed", "recommendation_follow_rate",
    "recommendation_notified", "recommendation_followed_notified",
    "avg_follow_delay_min", "follow_delay_samples", "preferred_duration_min",
    "duration_samples", "avg_duration_deviation_min",
    "outcome_temperature_factor", "outcome_avg_removed_error_ml",
    "shadow_learning_samples", "shadow_learning_total_samples", "shadow_learning_status", "shadow_learning_last_action",
    "shadow_learning_last_improvement_pct", "shadow_learning_promotions", "shadow_learning_rollbacks", "shadow_rollback_active",
    "outcome_avg_temperature_error_c",
    "fan_automation", "reference_path", "air_exchange",
    # 0.26.5.4 (support case): temperature target and the action at each decision step
    "comfort_target_c", "comfort_target_source", "canonical_action", "house_aligned_action",
    "close_recommended", "close_decision_ready", "contact_count", "action_hint",
)


_LEARNING_ROOM_KEYS = (
    "learning_rate", "learning_samples", "learning_sample_credit", "learning_status", "diagnosis", "start_model",
    "last_learning_at", "outcome_feedback_samples", "outcome_successes", "outcome_guarded_direction", "outcome_guarded_streak", "outcome_guarded_last_ratio", "last_outcome_feedback_applied",
    "outcome_removed_factor", "strategy_samples", "strategy_outcome_samples",
    "shadow_learning_samples", "shadow_learning_total_samples", "shadow_learning_status", "shadow_learning_last_action", "shadow_learning_promotions", "shadow_learning_rollbacks", "shadow_rollback_active",
    "session_active", "session_started", "three_state_transients_suppressed", "session_passage_door", "session_learning_quarantined", "session_learning_quarantine_code", "session_physical_started", "session_result_ml", "session_start_ah",
    "session_start_source_ah", "session_start_temp", "session_fresh_measurements", "session_temperature_reports", "session_humidity_reports", "session_open_temperature_reported_at", "session_open_humidity_reported_at",
    "session_last_valid_temperature", "session_last_valid_humidity", "session_last_valid_reference_temperature", "session_last_valid_reference_humidity", "session_last_valid_at",
    "session_predicted_removed_ml", "session_predicted_temperature_change_c",
    "session_predicted_cost", "session_prediction_confidence",
    "session_prediction_snapshot_at", "session_prediction_horizon_min",
    "session_prediction_snapshot_valid", "session_prediction_reference",
    "session_start_frame_quality", "session_start_frame_skew_s", "session_start_frame_max_age_s",
    "session_start_frame_learning_eligible", "session_prediction_snapshot_frame_quality",
    "session_prediction_snapshot_frame_skew_s", "session_prediction_snapshot_frame_max_age_s",
    "last_measurement_frame_quality", "last_measurement_frame_skew_s", "last_measurement_frame_max_age_s",
    "last_measurement_frame_learning_eligible",
    "post_close_active", "post_close_event_id", "post_close_room_key", "post_close_room_name", "post_close_started_at", "post_close_last_outcome",
)


# Compact time-series fields used for routine sampling.  The full diagnostic
# record remains available for meaningful events (window transitions,
# completed sessions, configuration changes, etc.), while these fields are
# sufficient to reconstruct 30-day climate/forecast trends without repeating
# the large decision and learning payload every few minutes.
_TREND_TOP_LEVEL_KEYS = (
    "status", "potential_total_ml", "actionable_potential_ml",
    "live_balance_ml", "forecast_horizon_min", "forecast_moisture_effect_ml",
    "forecast_temperature_change_c", "forecast_cost", "forecast_confidence",
    "max_surface_rh", "total_water_ml", "cross_ventilation",
    "recommended_duration_min", "remaining_duration_min",
    "temperature_change_live_c", "operating_profile", "cooling_rooms",
    "overnight_forecast_ml", "overnight_confidence", "presence_confidence",
    "pollen_index", "pollen_blocked", "outdoor_pm25", "outdoor_pm25_blocked", "wind_bearing", "wind_speed",
    "outdoor_temperature", "outdoor_humidity", "outdoor_absolute_humidity",
    "outdoor_data_quality",
)


_TREND_ROOM_KEYS = (
    "key", "temperature", "humidity", "absolute_humidity", "water_in_air_ml",
    "surface_rh", "co2",
    "voc", "voc_available", "voc_enabled", "voc_configured",
    "pm25", "pm25_available", "pm25_enabled", "pm25_configured",
    "illuminance", "illuminance_available", "illuminance_enabled", "illuminance_configured",
    "active", "open_seconds", "opening_state", "opening_state_explicit", "three_state_transition_suppressed", "three_state_transients_suppressed", "passage_door_configured", "learning_quarantined", "learning_quarantine_code", "opening_diagnostic_codes", "action",
    "potential_ml", "result_ml",
    "forecast_moisture_effect_ml", "forecast_temperature_change_c",
)
