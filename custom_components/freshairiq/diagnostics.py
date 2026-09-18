"""Privacy-conscious rolling diagnostics recorder for FreshAirIQ.

The recorder deliberately stores calculated FreshAirIQ state instead of raw
Home Assistant entity identifiers. Files are kept as daily JSONL chunks under
``.storage/freshairiq_diagnostics`` and are exported through an authenticated
Home Assistant API view.
"""
from __future__ import annotations

from copy import deepcopy

import hashlib
import json
import platform
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .runtime import iter_runtime_coordinators
from .const import DOMAIN
from .diagnostic_transport import normalise_resident_names

DIAGNOSTICS_SCHEMA_VERSION = 10
DIAGNOSTICS_IDENTITY_SCHEMA_VERSION = 1
DIAGNOSTICS_IDENTITY_FILENAME = "field_test_identity.json"
DIAGNOSTICS_CLIENTS_FILENAME = "field_test_clients.json"
DIAGNOSTICS_MAX_CLIENTS = 64
DIAGNOSTICS_RETENTION_DAYS = 30
DIAGNOSTICS_INTERVAL_SECONDS = 120
DIAGNOSTICS_IDLE_INTERVAL_SECONDS = 15 * 60
DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS = 120
DIAGNOSTICS_MAX_EXPORT_RECORDS = 120000
DIAGNOSTICS_MAX_EXPORT_BYTES = 24 * 1024 * 1024
DIAGNOSTICS_MAX_TOTAL_BYTES = 100 * 1024 * 1024

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
    "shade_min_illuminance_lx", "learning_enabled", "learning_max_duration_min",
    "cross_ventilation_pairs", "cross_zone_connections", "operating_profile",
    "personalisation_enabled", "thermal_preference", "personal_priority",
    "night_window_preference", "cooling_start_temp_c",
    "cooling_min_outdoor_delta_c", "cooling_max_indoor_rh",
    "cooling_max_moisture_gain_5min_ml", "property_type", "adult_occupants",
    "child_occupants", "untracked_follow_household", "pets_in_household",
    "guest_adults", "guest_children", "night_start_hour", "night_end_hour",
    "night_forecast_enabled", "adult_night_moisture_ml_h",
    "child_night_moisture_ml_h", "background_night_moisture_ml_h",
    "adult_day_moisture_ml", "child_day_moisture_ml",
    "household_day_moisture_ml", "pollen_enabled", "pollen_max",
    "pollen_strict_veto", "wind_orientation_enabled", "heating_system",
    "electricity_price_per_kwh", "heat_pump_cop", "gas_price_per_kwh",
    "gas_efficiency", "district_price_per_kwh", "district_efficiency",
    "oil_price_per_liter", "oil_kwh_per_liter", "oil_efficiency",
    "energy_price_per_kwh", "heating_efficiency", "notifications_enabled",
    "notification_scope", "notification_room_keys", "notify_ventilate",
    "notify_close", "notify_complete", "notify_mould", "notify_sensor",
    "notify_night", "notify_learning", "notify_cooling",
    "notification_cooldown_min", "statistics_days", "dashboard_show_temperature",
    "dashboard_show_time", "dashboard_show_next5", "dashboard_show_night",
    "dashboard_show_mould", "dashboard_show_history",
    "diagnostics_reporting_mode", "diagnostics_include_client_context",
)


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
    "moisture_balance_today_ml", "pollen_enabled", "pollen_index", "pollen_limit",
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
    "active", "open_seconds",
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
    "avg_follow_delay_min", "follow_delay_samples", "preferred_duration_min",
    "duration_samples", "avg_duration_deviation_min",
    "outcome_temperature_factor", "outcome_avg_removed_error_ml",
    "shadow_learning_samples", "shadow_learning_total_samples", "shadow_learning_status", "shadow_learning_last_action",
    "shadow_learning_last_improvement_pct", "shadow_learning_promotions", "shadow_learning_rollbacks", "shadow_rollback_active",
    "outcome_avg_temperature_error_c",
)

_LEARNING_ROOM_KEYS = (
    "learning_rate", "learning_samples", "learning_sample_credit", "learning_status", "diagnosis",
    "last_learning_at", "outcome_feedback_samples", "outcome_successes", "outcome_guarded_direction", "outcome_guarded_streak", "outcome_guarded_last_ratio", "last_outcome_feedback_applied",
    "outcome_removed_factor", "strategy_samples", "strategy_outcome_samples",
    "shadow_learning_samples", "shadow_learning_total_samples", "shadow_learning_status", "shadow_learning_last_action", "shadow_learning_promotions", "shadow_learning_rollbacks", "shadow_rollback_active",
    "session_active", "session_started", "session_physical_started", "session_result_ml", "session_start_ah",
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
    "pollen_index", "pollen_blocked", "wind_bearing", "wind_speed",
    "outdoor_temperature", "outdoor_humidity", "outdoor_absolute_humidity",
    "outdoor_data_quality",
)

_TREND_ROOM_KEYS = (
    "key", "temperature", "humidity", "absolute_humidity", "water_in_air_ml",
    "surface_rh", "co2",
    "voc", "voc_available", "voc_enabled", "voc_configured",
    "pm25", "pm25_available", "pm25_enabled", "pm25_configured",
    "illuminance", "illuminance_available", "illuminance_enabled", "illuminance_configured",
    "active", "open_seconds", "action",
    "potential_ml", "result_ml",
    "forecast_moisture_effect_ml", "forecast_temperature_change_c",
)


class FreshAirIQDiagnosticsRecorder:
    """Record a rolling, anonymised diagnostic trace."""

    def __init__(self, hass: HomeAssistant, entry_id: str, version: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.version = version
        self.directory = Path(hass.config.path(".storage", "freshairiq_diagnostics"))
        self._last_recorded_at: datetime | None = None
        self._last_signature: str | None = None
        self._last_cleanup_at: datetime | None = None
        self.last_error: str | None = None
        self.record_count_session = 0
        self._last_room_active: dict[str, bool] = {}
        self._last_room_opened_at: dict[str, str] = {}
        self._config_snapshot: dict[str, Any] = {}
        self._config_signature: str | None = None
        self._configuration_changed = False
        self._legacy_compaction_mtime_ns: dict[str, int] = {}
        self._last_export_client: dict[str, Any] = {}
        self._field_test_storage_lock = Lock()

    @property
    def _identity_path(self) -> Path:
        return self.directory / DIAGNOSTICS_IDENTITY_FILENAME

    @property
    def _clients_path(self) -> Path:
        return self.directory / DIAGNOSTICS_CLIENTS_FILENAME

    def _load_or_create_field_test_identity(self, now: datetime) -> dict[str, Any]:
        """Load or atomically create the stable anonymous installation identity."""
        with self._field_test_storage_lock:
            return self._load_or_create_field_test_identity_unlocked(now)

    def _load_or_create_field_test_identity_unlocked(self, now: datetime) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        identity: dict[str, Any] = {}
        identity_status = "existing"
        if self._identity_path.exists():
            try:
                raw = json.loads(self._identity_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    identity = raw
                else:
                    identity_status = "recreated_invalid_identity"
            except (OSError, json.JSONDecodeError):
                identity_status = "recreated_invalid_identity"

        installation_id = str(identity.get("installation_id") or "")
        if not installation_id.startswith("faiq-install-"):
            installation_id = f"faiq-install-{uuid4().hex}"
            identity_status = "created" if not identity else "recreated_invalid_identity"
        created_at = identity.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            created_at = now.isoformat()
        export_sequence = _safe_int(identity.get("export_sequence"), 0, low=0, high=10_000_000) + 1
        persisted = {
            "identity_schema_version": DIAGNOSTICS_IDENTITY_SCHEMA_VERSION,
            "installation_id": installation_id,
            "created_at": created_at,
            "export_sequence": export_sequence,
            "last_exported_at": now.isoformat(),
        }
        tmp = self._identity_path.with_suffix(self._identity_path.suffix + ".tmp")
        tmp.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self._identity_path)
        entry_fingerprint = hashlib.sha256(f"{installation_id}|{self.entry_id}".encode("utf-8")).hexdigest()[:24]
        return {**persisted, "identity_status": identity_status, "entry_fingerprint": entry_fingerprint}

    def _load_field_test_clients(self) -> list[dict[str, Any]]:
        if not self._clients_path.exists():
            return []
        raw = json.loads(self._clients_path.read_text(encoding="utf-8"))
        rows = raw.get("clients") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)][-DIAGNOSTICS_MAX_CLIENTS:]

    def _register_client_sync(self, context: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Persist one anonymous dashboard client without raw UA or device names."""
        with self._field_test_storage_lock:
            return self._register_client_sync_unlocked(context, now)

    def _register_client_sync_unlocked(self, context: dict[str, Any], now: datetime) -> dict[str, Any]:
        safe = _sanitise_client_context(context)
        if not safe:
            return {"registered": False, "reason": "invalid_client_context"}
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            clients = self._load_field_test_clients()
        except (OSError, json.JSONDecodeError):
            clients = []
        client_id = safe["client_id"]
        existing = next((row for row in clients if row.get("client_id") == client_id), None)
        if existing is None:
            existing = {"client_id": client_id, "first_seen_at": now.isoformat(), "seen_count": 0}
            clients.append(existing)
        existing["last_seen_at"] = now.isoformat()
        existing["seen_count"] = _safe_int(existing.get("seen_count"), 0, low=0, high=10_000_000) + 1
        existing["current"] = safe
        for field in (
            "platform_family", "os_version", "device_class", "device_family", "device_model",
            "companion_app_version", "browser_family", "browser_version", "webview_engine_version",
            "home_assistant_version_reported_by_frontend", "freshairiq_frontend_version",
        ):
            value = safe.get(field)
            if not value:
                continue
            history_key = f"{field}_history"
            history = existing.get(history_key)
            if not isinstance(history, list):
                history = []
            if value not in history:
                history.append(value)
            existing[history_key] = history[-12:]
        clients = clients[-DIAGNOSTICS_MAX_CLIENTS:]
        tmp = self._clients_path.with_suffix(self._clients_path.suffix + ".tmp")
        tmp.write_text(json.dumps({"clients": clients}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self._clients_path)
        self._last_export_client = safe
        return {"registered": True, "client_id": client_id}

    async def async_register_client(self, context: dict[str, Any]) -> dict[str, Any]:
        now = dt_util.now()
        try:
            return await self.hass.async_add_executor_job(self._register_client_sync, context, now)
        except OSError as err:
            return {"registered": False, "reason": f"{type(err).__name__}: {err}"}

    async def async_get_identity(self) -> dict[str, Any]:
        """Return the existing random field-test identity without exporting records."""
        now = dt_util.now()
        try:
            identity = await self.hass.async_add_executor_job(
                self._load_or_create_field_test_identity, now
            )
        except OSError as err:
            return {"installation_id": None, "identity_status": f"storage_error:{type(err).__name__}"}
        return {
            "installation_id": identity.get("installation_id"),
            "identity_status": identity.get("identity_status"),
            "created_at": identity.get("created_at"),
        }

    async def _async_runtime_environment(self) -> dict[str, Any]:
        """Collect HA-provided system metadata and whitelist field-test-safe facts."""
        fallback = _runtime_environment_snapshot()
        try:
            from homeassistant.helpers.system_info import async_get_system_info
            info = await async_get_system_info(self.hass)
        except Exception:
            return fallback
        if not isinstance(info, dict):
            return fallback
        safe = {
            "home_assistant_version": info.get("version") or fallback.get("home_assistant_version"),
            "installation_type": info.get("installation_type"),
            "channel": info.get("channel"),
            "dev": info.get("dev"),
            "hassio": info.get("hassio"),
            "docker": info.get("docker"),
            "virtualenv": info.get("virtualenv"),
            "python_version": info.get("python_version") or fallback.get("python_version"),
            "os_name": info.get("os_name") or fallback.get("os_name"),
            "os_version": info.get("os_version") or fallback.get("os_version"),
            "architecture": info.get("arch") or fallback.get("architecture"),
            "container_architecture": info.get("container_arch"),
            "timezone": info.get("timezone"),
        }
        return _json_safe(safe)

    @property
    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "retention_days": DIAGNOSTICS_RETENTION_DAYS,
            "interval_seconds": DIAGNOSTICS_IDLE_INTERVAL_SECONDS,
            "active_interval_seconds": DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS,
            "max_storage_mb": round(DIAGNOSTICS_MAX_TOTAL_BYTES / 1024 / 1024),
            "last_recorded_at": self._last_recorded_at.isoformat() if self._last_recorded_at else None,
            "records_this_runtime": self.record_count_session,
            "last_error": self.last_error,
        }

    def update_configuration_snapshot(
        self, entry_data: dict[str, Any], options: dict[str, Any], data: dict[str, Any], now: datetime
    ) -> None:
        """Keep an anonymised setup snapshot for portable beta-test exports."""
        room_rows: list[dict[str, Any]] = []
        raw_rooms = entry_data.get("rooms") or []
        if not isinstance(raw_rooms, list):
            raw_rooms = []
        live_rooms = data.get("rooms") or {}
        if not isinstance(live_rooms, dict):
            live_rooms = {}
        for raw in raw_rooms:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "")
            live = live_rooms.get(key) or {}
            orientations = raw.get("contact_orientations") or {}
            if isinstance(orientations, dict):
                direction_values = sorted({str(v) for v in orientations.values() if v})
            else:
                direction_values = []
            contacts = [x for x in (raw.get("contacts") or ([] if not raw.get("contact") else [raw.get("contact")])) if x]
            contact_delays = raw.get("contact_delays") if isinstance(raw.get("contact_delays"), dict) else {}
            contact_ref_t = raw.get("contact_reference_temperatures") if isinstance(raw.get("contact_reference_temperatures"), dict) else {}
            contact_ref_h = raw.get("contact_reference_humidities") if isinstance(raw.get("contact_reference_humidities"), dict) else {}
            contact_covers = raw.get("contact_covers") if isinstance(raw.get("contact_covers"), dict) else {}
            openings = []
            for index, contact in enumerate(contacts, 1):
                covers = contact_covers.get(contact) or []
                if not isinstance(covers, list):
                    covers = [covers] if covers else []
                openings.append({
                    "opening_index": index,
                    "orientation": _json_safe(orientations.get(contact) if isinstance(orientations, dict) else None),
                    "delay_seconds": _json_safe(contact_delays.get(contact)),
                    "reference_temperature_configured": bool(contact_ref_t.get(contact)),
                    "reference_humidity_configured": bool(contact_ref_h.get(contact)),
                    "cover_count": len([item for item in covers if item]),
                })
            room_rows.append({
                "key": key,
                "name": str(raw.get("name") or live.get("name") or key),
                "floor": _json_safe(raw.get("floor") or live.get("floor")),
                "sort_order": _json_safe(raw.get("sort_order")),
                "volume_m3": _json_safe(raw.get("volume") or live.get("volume_m3")),
                "dimensions_m": {
                    "length": _json_safe(raw.get("length")),
                    "width": _json_safe(raw.get("width")),
                    "height": _json_safe(raw.get("height")),
                },
                "calculation_enabled": bool(raw.get("include_in_calculations", True)),
                "moisture_sources": _json_safe(raw.get("moisture_sources") or []),
                "ventilation_threshold": {
                    "mode": _json_safe(raw.get("ventilation_threshold_mode") or "automatic"),
                    "percent": _json_safe(raw.get("ventilation_threshold_percent", 5.0)),
                    "fixed_ml": _json_safe(raw.get("ventilation_threshold_ml", 100.0)),
                    "effective_ml": _json_safe(live.get("ventilation_threshold_effective_ml")),
                },
                "window_orientation": _json_safe(raw.get("window_orientation") or live.get("window_orientation")),
                "contact_orientations": direction_values,
                "contact_count": len(contacts),
                "openings": openings,
                "temperature_sensor_configured": bool(raw.get("temperature")),
                "humidity_sensor_configured": bool(raw.get("humidity")),
                "has_co2": bool(raw.get("co2")),
                "has_voc": bool(raw.get("voc")),
                "has_pm25": bool(raw.get("pm25")),
                "has_illuminance": bool(raw.get("illuminance")),
                "reference_temperature_configured": bool(raw.get("reference_temperature")),
                "reference_humidity_configured": bool(raw.get("reference_humidity")),
                "has_reference_climate": bool(raw.get("reference_temperature") or raw.get("reference_humidity")),
                "actuators": {
                    "climate": bool(raw.get("climate")),
                    "exhaust_fan": bool(raw.get("exhaust_fan")),
                    "supply_fan": bool(raw.get("supply_fan")),
                    "ventilation_device": bool(raw.get("ventilation_device")),
                    "dehumidifier": bool(raw.get("dehumidifier")),
                    "humidifier": bool(raw.get("humidifier")),
                    "air_purifier": bool(raw.get("air_purifier")),
                },
            })

        snapshot = {
            "captured_at": now.isoformat(),
            "freshairiq_version": self.version,
            "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "model_options": {key: _json_safe(options.get(key)) for key in _SAFE_OPTION_KEYS if key in options},
            "capabilities": {
                "weather_entity_configured": bool(entry_data.get("outdoor_weather")),
                "outdoor_temperature_sensor_configured": bool(entry_data.get("outdoor_temperature")),
                "outdoor_humidity_sensor_configured": bool(entry_data.get("outdoor_humidity")),
                "pollen_sensor_configured": bool(entry_data.get("pollen_entity")),
                "adult_presence_tracker_count": len(options.get("adult_presence_entities") or []),
                "child_presence_tracker_count": len(options.get("child_presence_entities") or []),
                "soft_presence_sensor_count": len(options.get("presence_sensor_entities") or []),
                "pet_safe_presence_sensor_count": len(options.get("pet_safe_presence_entities") or []),
                "co2_room_count": sum(1 for room in raw_rooms if isinstance(room, dict) and room.get("co2")),
                "voc_room_count": sum(1 for room in raw_rooms if isinstance(room, dict) and room.get("voc")),
                "pm25_room_count": sum(1 for room in raw_rooms if isinstance(room, dict) and room.get("pm25")),
                "illuminance_room_count": sum(1 for room in raw_rooms if isinstance(room, dict) and room.get("illuminance")),
                "reference_climate_room_count": sum(1 for room in raw_rooms if isinstance(room, dict) and (room.get("reference_temperature") or room.get("reference_humidity"))),
                "contact_count": sum(int(row["contact_count"]) for row in room_rows),
                "physical_heating_state_sensor_configured": False,
                "resident_profile_count": len(normalise_resident_names(options.get("adult_resident_names"))) + len(normalise_resident_names(options.get("child_resident_names"))),
                "resident_room_profile_count": len(options.get("resident_room_profiles") or {}) if isinstance(options.get("resident_room_profiles"), dict) else 0,
                "notification_target_count": len(options.get("notification_targets") or []),
            },
            "privacy_omissions": [
                "entity_ids", "notification_targets", "resident_names", "presence_entity_names", "coordinates", "credentials"
            ],
            "levels": [str(level) for level in (entry_data.get("levels") or [])],
            "rooms": room_rows,
        }
        # ``captured_at`` changes every coordinator cycle and must not make a
        # stable configuration look different.  Compare the actual content
        # only, then keep the fresh timestamp for the export dossier.
        comparable = dict(snapshot)
        comparable.pop("captured_at", None)
        configuration_fingerprint = _sha256_json(comparable)
        snapshot["configuration_fingerprint_sha256"] = configuration_fingerprint
        self._configuration_changed = self._config_signature is not None and configuration_fingerprint != self._config_signature
        self._config_signature = configuration_fingerprint
        self._config_snapshot = snapshot

    def _window_events(self, data: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
        """Describe ventilation-state transitions without exposing entity IDs."""
        events: list[dict[str, Any]] = []
        current_keys: set[str] = set()
        room_map = data.get("rooms") or {}
        if not isinstance(room_map, dict):
            room_map = {}
        for key, raw in room_map.items():
            if not isinstance(raw, dict):
                continue
            room_key = str(key)
            current_keys.add(room_key)
            active = bool(raw.get("active"))
            previous = self._last_room_active.get(room_key)
            if previous is None:
                self._last_room_active[room_key] = active
                if active:
                    self._last_room_opened_at[room_key] = now.isoformat()
                continue
            if active == previous:
                continue
            event = {
                "room_key": room_key,
                "room_name": str(raw.get("name") or room_key),
                "event": "ventilation_opened" if active else "ventilation_closed",
                "timestamp": now.isoformat(),
                "open_seconds": _json_safe(raw.get("open_seconds")),
            }
            if active:
                self._last_room_opened_at[room_key] = now.isoformat()
            else:
                started = self._last_room_opened_at.pop(room_key, None)
                event["opened_at"] = started
                if started:
                    try:
                        event["duration_seconds"] = round((now - datetime.fromisoformat(started)).total_seconds(), 1)
                    except (TypeError, ValueError):
                        pass
            events.append(event)
            self._last_room_active[room_key] = active
        for key in list(self._last_room_active):
            if key not in current_keys:
                self._last_room_active.pop(key, None)
                self._last_room_opened_at.pop(key, None)
        return events

    @staticmethod
    def _sensor_quality_summary(data: dict[str, Any]) -> dict[str, Any]:
        room_map = data.get("rooms") or {}
        rooms = [room for room in room_map.values() if isinstance(room, dict)] if isinstance(room_map, dict) else []
        valid = [room for room in rooms if room.get("data_quality") == "ok"]
        issues = [
            {"room_key": str(room.get("key") or ""), "room_name": str(room.get("name") or ""),
             "data_quality": _json_safe(room.get("data_quality"))}
            for room in rooms if room.get("data_quality") != "ok"
        ]
        return {
            "rooms_total": len(rooms),
            "rooms_ok": len(valid),
            "rooms_with_issues": len(issues),
            "room_quality_percent": round(100.0 * len(valid) / max(len(rooms), 1), 1),
            "outdoor_data_quality": _json_safe(data.get("outdoor_data_quality")),
            "issues": issues,
        }

    def _signature(self, data: dict[str, Any]) -> str:
        recommendation = data.get("intelligent_recommendation") or {}
        rooms = data.get("rooms") or {}
        if not isinstance(rooms, dict):
            rooms = {}
        active = sorted(str(k) for k, value in rooms.items() if isinstance(value, dict) and value.get("active"))
        actions = sorted(
            (str(k), str(value.get("action") or ""))
            for k, value in rooms.items()
            if isinstance(value, dict) and value.get("action") in {"Ventilate", "Continue ventilating", "Close", "Ventilate for cooling", "Check sensor"}
        )
        payload = {
            "status": data.get("status"),
            "kind": recommendation.get("kind"),
            "room_keys": recommendation.get("room_keys") or [],
            "active": active,
            "actions": actions,
            "last_ventilation": (data.get("last_ventilation") or {}).get("ended_at"),
            "night_action": (data.get("night_strategy") or {}).get("action"),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def _build_record(
        self,
        data: dict[str, Any],
        store_data: dict[str, Any],
        now: datetime,
        reason: str,
        completed_sessions: list[dict[str, Any]],
        window_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        completed_sessions = [item for item in (completed_sessions or []) if isinstance(item, dict)]
        window_events = (
            [item for item in window_events if isinstance(item, dict)]
            if isinstance(window_events, list) else None
        )
        rooms = []
        room_map = data.get("rooms") or {}
        if not isinstance(room_map, dict):
            room_map = {}
        for key, raw in room_map.items():
            if not isinstance(raw, dict):
                continue
            room = _pick(raw, _ROOM_KEYS)
            room.setdefault("key", str(key))
            # Do not export entity-id keyed orientation maps. Direction values
            # are enough for model analysis and keep the trace anonymous.
            orientations = raw.get("contact_orientations") or {}
            if isinstance(orientations, dict):
                room["contact_orientations"] = sorted({str(v) for v in orientations.values() if v})
            rooms.append(room)

        learning_rooms = []
        learning_map = store_data.get("rooms") or {}
        if not isinstance(learning_map, dict):
            learning_map = {}
        for key, raw in learning_map.items():
            if not isinstance(raw, dict):
                continue
            compact = _pick(raw, _LEARNING_ROOM_KEYS)
            compact["key"] = str(key)
            learning_rooms.append(compact)

        if window_events is None:
            window_events = self._window_events(data, now)

        return {
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "freshairiq_version": self.version,
            "timestamp": now.isoformat(),
            "reason": reason,
            "record_type": "event",
            "configuration_snapshot": _json_safe(self._config_snapshot),
            "runtime_environment": _json_safe(_runtime_environment_snapshot()),
            "house": _pick(data, _TOP_LEVEL_KEYS),
            "rooms": rooms,
            "decision": _privacy_safe_decision(data.get("intelligent_recommendation") or {}),
            "decision_intelligence": _privacy_safe_iq_state(data.get("iq_state") or {}),
            "night_strategy": _json_safe(data.get("night_strategy") or {}),
            "day_night_plan": _json_safe(data.get("day_night_plan") or {}),
            "future_weather_boundaries": _json_safe(data.get("future_weather_boundaries") or {}),
            "completed_sessions": _json_safe(completed_sessions),
            "window_events": _json_safe(window_events),
            "sensor_quality": self._sensor_quality_summary(data),
            "recommendation_tracking": {
                "active_advice": _json_safe(store_data.get("iq_active_advice")),
                "followed_session_count": sum(1 for item in completed_sessions if item.get("recommendation_followed")),
                "completed_session_count": len(completed_sessions),
            },
            "heating_model": {
                "system": _json_safe(data.get("heating_system")),
                "energy_price_per_kwh": _json_safe(data.get("energy_price_per_kwh")),
                "forecast_heat_kwh": _json_safe(data.get("forecast_heat_kwh")),
                "forecast_reheat_cost": _json_safe(data.get("forecast_cost")),
                "physical_heating_state": None,
                "physical_heating_state_reason": "No dedicated heating-state entity is configured in FreshAirIQ.",
            },
            "forecast_validation": _json_safe(data.get("forecast_validation") or {}),
            "post_close_stabilization": _json_safe(data.get("post_close_stabilization") or {}),
            "post_close_stabilization_history": _json_safe(data.get("post_close_stabilization_history") or []),
            "forecast_backtest": _json_safe(data.get("forecast_backtest") or {}),
            "learning_components": _json_safe(data.get("learning_components") or {}),
            "learning": {
                "last_diagnosis": _json_safe(store_data.get("last_diagnosis")),
                "night_model_ml_h": _json_safe(store_data.get("night_model_ml_h")),
                "night_model_samples": _safe_int(store_data.get("night_model_samples")),
                "house_strategy_samples": _safe_int(store_data.get("house_strategy_samples")),
                "house_strategy_successes": _safe_int(store_data.get("house_strategy_successes")),
                "rooms": learning_rooms,
            },
        }

    def _build_trend_record(
        self,
        data: dict[str, Any],
        now: datetime,
        reason: str,
    ) -> dict[str, Any]:
        """Build a compact routine sample suitable for long 30-day traces."""
        rooms: list[dict[str, Any]] = []
        room_map = data.get("rooms") or {}
        if not isinstance(room_map, dict):
            room_map = {}
        for key, raw in room_map.items():
            if not isinstance(raw, dict):
                continue
            room = _pick(raw, _TREND_ROOM_KEYS)
            room.setdefault("key", str(key))
            rooms.append(room)
        recommendation = data.get("intelligent_recommendation") or {}
        runtime = _runtime_environment_snapshot()
        return {
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "freshairiq_version": self.version,
            "timestamp": now.isoformat(),
            "reason": reason,
            "record_type": "trend",
            # Keep only the HA version in routine samples. This makes software
            # upgrade history reconstructable without materially growing the
            # 30-day rolling trace. Full system metadata remains export-time data.
            "runtime_environment": {"home_assistant_version": _json_safe(runtime.get("home_assistant_version"))},
            "house": _pick(data, _TREND_TOP_LEVEL_KEYS),
            "rooms": rooms,
            "decision": {
                "kind": _json_safe(recommendation.get("kind")),
                "room_keys": _json_safe(recommendation.get("room_keys") or []),
                "confidence": _json_safe(recommendation.get("confidence")),
            },
            "sensor_quality": self._sensor_quality_summary(data),
        }

    @staticmethod
    def _is_active_ventilation(data: dict[str, Any]) -> bool:
        rooms = data.get("rooms") or {}
        if not isinstance(rooms, dict):
            return False
        return any(bool(room.get("active")) for room in rooms.values() if isinstance(room, dict))

    @staticmethod
    def _compact_legacy_record(record: dict[str, Any]) -> dict[str, Any]:
        """Compact routine records from older schemas during export.

        Historical session/window events remain untouched.  Only repetitive
        periodic/state-change records without such events are reduced so an
        existing large beta trace can still contribute its full 30-day time
        span after upgrading.
        """
        record_type = str(record.get("record_type") or "")
        if record_type == "event" or record_type.startswith("trend"):
            return record
        if record.get("completed_sessions") or record.get("window_events"):
            return record
        reason = str(record.get("reason") or "")
        if reason not in {"periodic", "state_change", "active_sample", "idle_sample"}:
            return record

        house = record.get("house") or {}
        rooms = []
        for raw in record.get("rooms") or []:
            room = _pick(raw, _TREND_ROOM_KEYS)
            if "key" not in room and raw.get("key") is not None:
                room["key"] = _json_safe(raw.get("key"))
            rooms.append(room)
        decision = record.get("decision") or {}
        compacted = {
            "schema_version": record.get("schema_version"),
            "freshairiq_version": record.get("freshairiq_version"),
            "timestamp": record.get("timestamp"),
            "reason": reason,
            "record_type": "trend_legacy_compacted",
            "house": _pick(house, _TREND_TOP_LEVEL_KEYS),
            "rooms": rooms,
            "decision": {
                "kind": _json_safe(decision.get("kind")),
                "room_keys": _json_safe(decision.get("room_keys") or []),
                "confidence": _json_safe(decision.get("confidence")),
            },
            "sensor_quality": _json_safe(record.get("sensor_quality") or {}),
        }
        # A legacy state-change row may be the only evidence of a historical
        # configuration change. Keep that snapshot there, but do not repeat it
        # in the much more numerous periodic rows.
        if reason == "state_change" and record.get("configuration_snapshot"):
            compacted["configuration_snapshot"] = _json_safe(record.get("configuration_snapshot"))
        return compacted

    async def async_record(
        self,
        data: dict[str, Any],
        store_data: dict[str, Any],
        now: datetime,
        completed_sessions: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Record compact trends and preserve meaningful events in full."""
        completed_sessions = completed_sessions or []
        signature = self._signature(data)
        window_events = self._window_events(data, now)
        active_ventilation = self._is_active_ventilation(data)
        elapsed = (
            (now - self._last_recorded_at).total_seconds()
            if self._last_recorded_at is not None
            else DIAGNOSTICS_IDLE_INTERVAL_SECONDS
        )
        changed = signature != self._last_signature
        event_reason: str | None = None
        if completed_sessions:
            event_reason = "session_completed"
        elif window_events:
            event_reason = "window_event"
        elif self._configuration_changed:
            event_reason = "configuration_changed"
        elif changed:
            event_reason = "state_change"

        interval = DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS if active_ventilation else DIAGNOSTICS_IDLE_INTERVAL_SECONDS
        if event_reason is None and elapsed < interval:
            return False

        if event_reason in {"session_completed", "window_event", "configuration_changed"}:
            record = self._build_record(
                data, store_data, now, event_reason, completed_sessions, window_events=window_events
            )
        elif event_reason == "state_change" and self._last_signature is not None:
            # v0.25.0.2: preserve decision transitions at compact fidelity.
            # Critical session/window/configuration evidence remains full fidelity.
            record = self._build_trend_record(data, now, "state_change")
            record["record_type"] = "decision_event"
        elif event_reason == "state_change":
            # Keep the first baseline snapshot complete so configuration and
            # environment evidence remain reconstructable after restart.
            record = self._build_record(data, store_data, now, event_reason, completed_sessions, window_events=window_events)
        else:
            reason = "active_sample" if active_ventilation else "idle_sample"
            record = self._build_trend_record(data, now, reason)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        path = self.directory / f"{now.date().isoformat()}.jsonl"
        try:
            await self.hass.async_add_executor_job(self._append_line, path, line)
            self._last_recorded_at = now
            self._last_signature = signature
            self._configuration_changed = False
            self.record_count_session += 1
            self.last_error = None
            if self._last_cleanup_at is None or (now - self._last_cleanup_at) >= timedelta(hours=1):
                await self.hass.async_add_executor_job(self._cleanup_files, now)
                self._last_cleanup_at = now
            return True
        except OSError as err:
            self.last_error = f"{type(err).__name__}: {err}"
            return False

    def _append_line(self, path: Path, line: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _compact_legacy_file(self, path: Path) -> None:
        """Atomically compact retained pre-v3 routine rows in-place."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        changed = False
        output: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                # Keep damaged rows untouched so the exporter can still report
                # their location instead of silently discarding evidence.
                output.append(line)
                continue
            compact = self._compact_legacy_record(raw)
            if compact != raw:
                changed = True
            output.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
        if not changed:
            return
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)

    def _cleanup_files(self, now: datetime) -> None:
        if not self.directory.exists():
            return
        cutoff = now.date() - timedelta(days=DIAGNOSTICS_RETENTION_DAYS - 1)
        for path in self.directory.glob("*.jsonl"):
            try:
                day = datetime.fromisoformat(path.stem).date()
            except ValueError:
                continue
            if day < cutoff:
                path.unlink(missing_ok=True)

        # Upgrade still-retained traces from older versions before applying
        # the storage cap.  This protects the 30-day window from being lost
        # simply because old routine rows were much larger than v3 rows.
        for path in sorted(self.directory.glob("*.jsonl")):
            try:
                mtime_ns = path.stat().st_mtime_ns
            except OSError:
                continue
            cache_key = str(path)
            if self._legacy_compaction_mtime_ns.get(cache_key) == mtime_ns:
                continue
            self._compact_legacy_file(path)
            try:
                self._legacy_compaction_mtime_ns[cache_key] = path.stat().st_mtime_ns
            except OSError:
                self._legacy_compaction_mtime_ns.pop(cache_key, None)

        # Secondary safety cap: if unusually frequent state changes produce more
        # data than expected, remove the oldest complete daily chunks first.
        files = sorted(self.directory.glob("*.jsonl"))
        total = 0
        for path in files:
            try:
                if path.exists():
                    total += path.stat().st_size
            except OSError:
                continue
        current_name = now.date().isoformat() + ".jsonl"
        for path in files:
            if total <= DIAGNOSTICS_MAX_TOTAL_BYTES:
                break
            if path.name == current_name:
                continue
            try:
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                total -= size
            except OSError:
                continue

    async def async_export(self) -> dict[str, Any]:
        """Return the retained trace as one portable field-test JSON document."""
        now = dt_util.now()
        environment = await self._async_runtime_environment()
        return await self.hass.async_add_executor_job(self._export_sync, now, environment)

    def _export_sync(self, now: datetime, runtime_environment: dict[str, Any] | None = None) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        errors: list[str] = []
        export_bytes = 0
        truncated_by_bytes = False
        if self.directory.exists():
            # Prefer the newest retained diagnostics if a very large beta trace
            # must be capped for browser memory safety. Read only one daily file
            # at a time, then restore chronological order before exporting.
            for path in sorted(self.directory.glob("*.jsonl"), reverse=True):
                try:
                    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
                    for reverse_index, line in enumerate(reversed(lines), 1):
                        if not line.strip():
                            continue
                        try:
                            raw_record = json.loads(line)
                            if not isinstance(raw_record, dict):
                                line_no = len(lines) - reverse_index + 1
                                errors.append(f"{path.name}:{line_no}:non_object")
                                continue
                            record = self._compact_legacy_record(raw_record)
                            compact_line = json.dumps(
                                record, ensure_ascii=False, separators=(",", ":")
                            ) + "\n"
                            line_bytes = len(compact_line.encode("utf-8"))
                            if export_bytes + line_bytes > DIAGNOSTICS_MAX_EXPORT_BYTES:
                                truncated_by_bytes = True
                                break
                            records.append(record)
                            export_bytes += line_bytes
                        except json.JSONDecodeError:
                            line_no = len(lines) - reverse_index + 1
                            errors.append(f"{path.name}:{line_no}")
                        if len(records) >= DIAGNOSTICS_MAX_EXPORT_RECORDS:
                            break
                except OSError:
                    errors.append(path.name)
                if len(records) >= DIAGNOSTICS_MAX_EXPORT_RECORDS or truncated_by_bytes:
                    break
            records.reverse()
        reason_counts: dict[str, int] = {}
        completed_session_count = 0
        followed_session_count = 0
        window_event_count = 0
        quality_values: list[float] = []
        for record in records:
            reason = str(record.get("reason") or "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            sessions = record.get("completed_sessions") or []
            if not isinstance(sessions, list):
                sessions = []
            completed_session_count += len(sessions)
            followed_session_count += sum(
                1 for item in sessions if isinstance(item, dict) and item.get("recommendation_followed")
            )
            window_events = record.get("window_events") or []
            if not isinstance(window_events, list):
                window_events = []
            window_event_count += len(window_events)
            sensor_quality = record.get("sensor_quality") or {}
            quality = sensor_quality.get("room_quality_percent") if isinstance(sensor_quality, dict) else None
            if isinstance(quality, (int, float)) and isfinite(float(quality)):
                quality_values.append(float(quality))
        first_timestamp = records[0].get("timestamp") if records else None
        last_timestamp = records[-1].get("timestamp") if records else None
        latest_validation: dict[str, Any] = {}
        latest_backtest: dict[str, Any] = {}
        for record in reversed(records):
            candidate = record.get("forecast_validation")
            if isinstance(candidate, dict) and candidate:
                latest_validation = candidate
            candidate_backtest = record.get("forecast_backtest")
            if isinstance(candidate_backtest, dict) and candidate_backtest:
                latest_backtest = candidate_backtest
            if latest_validation and latest_backtest:
                break
        parsed_timestamps: list[datetime] = []
        recorded_days: set[str] = set()
        version_history: dict[str, dict[str, Any]] = {}
        configuration_history: dict[str, dict[str, Any]] = {}
        ha_version_history: dict[str, dict[str, Any]] = {}
        for record in records:
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    # Historic files can contain both offset-aware and naive
                    # timestamps.  Interval math only needs one internally
                    # consistent representation; dropping the offset after
                    # parsing prevents mixed-datetime comparison failures.
                    if parsed.tzinfo is not None:
                        parsed = parsed.replace(tzinfo=None)
                    parsed_timestamps.append(parsed)
                    recorded_days.add(parsed.date().isoformat())
                except ValueError:
                    pass
            version = str(record.get("freshairiq_version") or "unknown")
            row = version_history.setdefault(version, {"version": version, "first_seen_at": timestamp, "last_seen_at": timestamp, "record_count": 0})
            row["record_count"] += 1
            row["last_seen_at"] = timestamp
            config = record.get("configuration_snapshot")
            if isinstance(config, dict) and config:
                fingerprint = str(config.get("configuration_fingerprint_sha256") or _sha256_json({k: v for k, v in config.items() if k != "captured_at"}))
                c_row = configuration_history.setdefault(fingerprint, {
                    "configuration_fingerprint_sha256": fingerprint,
                    "first_seen_at": timestamp,
                    "last_seen_at": timestamp,
                    "event_record_count": 0,
                    "freshairiq_version": config.get("freshairiq_version"),
                })
                c_row["event_record_count"] += 1
                c_row["last_seen_at"] = timestamp
            runtime = record.get("runtime_environment")
            if isinstance(runtime, dict):
                ha_version = runtime.get("home_assistant_version")
                if ha_version:
                    ha_key = str(ha_version)
                    h_row = ha_version_history.setdefault(ha_key, {"version": ha_key, "first_seen_at": timestamp, "last_seen_at": timestamp, "event_record_count": 0})
                    h_row["event_record_count"] += 1
                    h_row["last_seen_at"] = timestamp

        largest_gap_minutes = None
        gap_count_over_30_min = 0
        if len(parsed_timestamps) >= 2:
            parsed_timestamps.sort()
            gaps = [(right - left).total_seconds() / 60.0 for left, right in zip(parsed_timestamps, parsed_timestamps[1:])]
            largest_gap_minutes = round(max(gaps), 1) if gaps else None
            gap_count_over_30_min = sum(1 for gap in gaps if gap > 30.0)
        period_span_days = None
        if len(parsed_timestamps) >= 2:
            period_span_days = round((parsed_timestamps[-1] - parsed_timestamps[0]).total_seconds() / 86400.0, 3)

        try:
            identity = self._load_or_create_field_test_identity(now)
        except OSError as err:
            identity = {
                "identity_schema_version": DIAGNOSTICS_IDENTITY_SCHEMA_VERSION,
                "installation_id": None,
                "entry_fingerprint": None,
                "export_sequence": None,
                "created_at": None,
                "identity_status": f"storage_error:{type(err).__name__}",
            }
        try:
            clients = self._load_field_test_clients()
        except (OSError, json.JSONDecodeError):
            clients = []
        current_environment = _json_safe(runtime_environment or _runtime_environment_snapshot())
        export_id = f"faiq-export-{uuid4().hex}"
        record_hash = _sha256_json(records)
        observation = {
            "period_start": first_timestamp,
            "period_end": last_timestamp,
            "period_span_days": period_span_days,
            "calendar_days_with_records": len(recorded_days),
            "recorded_calendar_days": sorted(recorded_days),
            "longest_consecutive_calendar_day_streak": _longest_consecutive_day_streak(sorted(recorded_days)),
            "largest_sampling_gap_minutes": largest_gap_minutes,
            "sampling_gaps_over_30_minutes": gap_count_over_30_min,
            "record_count": len(records),
            "truncated": len(records) >= DIAGNOSTICS_MAX_EXPORT_RECORDS or truncated_by_bytes,
            "read_error_count": len(errors),
        }
        field_test = {
            "evidence_schema_version": 1,
            "anonymous_installation_id": identity.get("installation_id"),
            "config_entry_fingerprint": identity.get("entry_fingerprint"),
            "identity_created_at": identity.get("created_at"),
            "identity_status": identity.get("identity_status"),
            "export_id": export_id,
            "export_sequence": identity.get("export_sequence"),
            "runtime_environment": current_environment,
            "export_client": _json_safe(self._last_export_client),
            "known_clients": _json_safe(clients),
            "known_client_count": len(clients),
            "observation": observation,
            "freshairiq_version_history": list(version_history.values()),
            "home_assistant_version_history": list(ha_version_history.values()),
            "configuration_history": list(configuration_history.values()),
            "data_integrity": {
                "algorithm": "sha256",
                "records_sha256": record_hash,
                "note": "Detects accidental changes/duplicates; this is not a cryptographic authenticity signature.",
            },
            "privacy": {
                "stable_ids_are_random_pseudonyms": True,
                "raw_user_agent_exported": False,
                "entity_ids_exported": False,
                "device_names_or_serial_numbers_exported": False,
                "exact_device_model": "Only included when the browser/WebView exposes a model string; iOS normally exposes only iPhone/iPad family.",
            },
        }

        return {
            "format": "FreshAirIQ diagnostic export",
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "freshairiq_version": self.version,
            "exported_at": now.isoformat(),
            "retention_days": DIAGNOSTICS_RETENTION_DAYS,
            "privacy": "No Home Assistant entity IDs, coordinates, credentials, presence entity names, notification targets, raw User-Agent strings, device names or serial numbers are intentionally exported. Configured room labels are retained for analysis.",
            "field_test": field_test,
            "test_dossier": {
                "period_start": first_timestamp,
                "period_end": last_timestamp,
                "period_span_days": period_span_days,
                "calendar_days_with_records": len(recorded_days),
                "longest_consecutive_calendar_day_streak": _longest_consecutive_day_streak(sorted(recorded_days)),
                "largest_sampling_gap_minutes": largest_gap_minutes,
                "record_count": len(records),
                "reason_counts": reason_counts,
                "completed_session_count": completed_session_count,
                "recommendation_followed_session_count": followed_session_count,
                "window_event_count": window_event_count,
                "average_room_data_quality_percent": round(sum(quality_values) / len(quality_values), 1) if quality_values else None,
                "configuration": _json_safe(self._config_snapshot),
                "forecast_validation": _json_safe(latest_validation),
                "forecast_backtest": _json_safe(latest_backtest),
            },
            "record_count": len(records),
            "truncated": len(records) >= DIAGNOSTICS_MAX_EXPORT_RECORDS or truncated_by_bytes,
            "export_payload_limit_mb": round(DIAGNOSTICS_MAX_EXPORT_BYTES / 1024 / 1024),
            "export_payload_bytes": export_bytes,
            "sampling": {
                "idle_interval_minutes": round(DIAGNOSTICS_IDLE_INTERVAL_SECONDS / 60),
                "active_ventilation_interval_minutes": round(DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS / 60),
                "critical_event_records_full_fidelity": True,
                "decision_state_changes_compacted": True,
                "legacy_routine_records_compacted_on_export": True,
            },
            "read_errors": errors,
            "records": records,
        }


class FreshAirIQDiagnosticsView(HomeAssistantView):
    """Authenticated endpoint used by the FreshAirIQ dashboard export button."""

    url = "/api/freshairiq/diagnostics"
    name = "api:freshairiq:diagnostics"
    requires_auth = True

    @staticmethod
    def _recorder(hass: HomeAssistant):
        coordinators = iter_runtime_coordinators(hass)
        if not coordinators:
            return None
        return getattr(coordinators[0], "diagnostics", None)

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]
        recorder = self._recorder(hass)
        if recorder is None:
            return self.json({"error": "FreshAirIQ diagnostics are unavailable"}, status_code=503)
        return self.json(await recorder.async_export())

    async def post(self, request):
        """Register an anonymous dashboard/client observation before export."""
        hass: HomeAssistant = request.app["hass"]
        recorder = self._recorder(hass)
        if recorder is None:
            return self.json({"error": "FreshAirIQ diagnostics are unavailable"}, status_code=503)
        try:
            payload = await request.json()
        except Exception:
            return self.json({"registered": False, "reason": "invalid_json"}, status_code=400)
        if not isinstance(payload, dict):
            return self.json({"registered": False, "reason": "invalid_payload"}, status_code=400)
        return self.json(await recorder.async_register_client(payload))
