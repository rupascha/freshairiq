"""Pure transport policy and privacy helpers for FreshAirIQ diagnostics sharing.

This module deliberately has no Home Assistant imports.  It owns the parts that
must stay deterministic and testable: reporting cadence, problem fingerprints,
room pseudonymisation and the cloud-upload data minimiser.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import re
from typing import Any, Mapping

UPLOAD_SCHEMA_VERSION = 2
CURSOR_SCHEMA_VERSION = 1
REPORTING_MODES = ("off", "errors", "daily", "weekly")
# Compatibility surface: Diagnostics HA / Diagnostics Hub tooling and older exports may
# still import the public single-payload helper/constants. Keep these public names stable
# even though the active client uses transport v2 chunking.
DEFAULT_MAX_UPLOAD_RECORDS = 240  # Legacy single-payload helper only; the v2 client does not trim history.

_ENTITY_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[a-z_][a-z0-9_]*\.[a-z0-9_]+)(?![A-Za-z0-9_])")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL_RE = re.compile(r"https?://[^\s]+", re.I)
_VERSION_LITERAL_KEYS = {"freshairiq_version", "freshairiq_frontend_version", "model_version"}


def normalise_resident_names(value: Any) -> list[str]:
    """Return bounded resident names from list or compact comma-separated settings."""
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").replace(";", ",").replace("\n", ",").split(",")
    out: list[str] = []
    for item in raw:
        name = " ".join(str(item or "").strip().split())[:48]
        if name and name not in out:
            out.append(name)
        if len(out) >= 20:
            break
    return out


def _version_literal_path(path: tuple[str, ...]) -> bool:
    """Return whether an IPv4-shaped string is a known software-version field."""
    if not path:
        return False
    if path[-1] in _VERSION_LITERAL_KEYS:
        return True
    return len(path) >= 2 and path[-2] == "freshairiq_version_history" and path[-1] == "version"
_DROP_KEYS = {
    "name", "room_name", "levels", "known_clients", "export_client",
    "config_entry_fingerprint", "identity_created_at", "adult_resident_names",
    "child_resident_names", "resident_room_profiles", "notification_targets",
    "notification_room_keys", "active_presence_sensors", "device_model", "device_family", "device_name",
    "serial_number", "serial", "mac_address", "mac", "ssid", "bssid",
    "user_id", "person_id", "username", "latitude", "longitude",
    "location_name", "internal_url", "external_url", "timezone",
    "configuration_fingerprint_sha256", "records_sha256",
}
_REMOTE_SAFE_MODEL_OPTIONS = {
    "start_rh", "high_rh", "target_rh", "min_delta", "min_delta_high_rh",
    "close_delta", "threshold_mode", "min_potential_percent_total_water",
    "min_potential_total_ml", "min_potential_room_ml", "min_duration_min",
    "max_duration_min", "min_return_next_5_min_ml",
    "post_ventilation_stabilization_min", "repeat_recommendation_cooldown_min",
    "repeat_min_benefit_ml", "repeat_weather_improvement_g_m3",
    "moisture_source_postrun_min", "house_ventilation_enter_ratio",
    "house_ventilation_exit_ratio", "forecast_horizon_min",
    "max_temp_loss_next_5_min_c", "min_efficiency_ml_per_01c", "surface_factor",
    "mould_warn_surface_rh", "mould_critical_surface_rh", "co2_warn",
    "co2_critical", "voc_sensor_enabled", "pm25_sensor_enabled",
    "illuminance_sensor_enabled", "voc_warn", "voc_critical", "pm25_warn",
    "pm25_critical", "humidify_below_rh", "shade_above_temp_c",
    "shade_min_illuminance_lx", "learning_enabled", "learning_max_duration_min",
    "operating_profile", "personalisation_enabled", "thermal_preference",
    "personal_priority", "night_window_preference", "cooling_start_temp_c",
    "cooling_min_outdoor_delta_c", "cooling_max_indoor_rh",
    "cooling_max_moisture_gain_5min_ml", "property_type", "night_start_hour",
    "night_end_hour", "night_forecast_enabled", "pollen_enabled", "pollen_max",
    "pollen_strict_veto", "wind_orientation_enabled", "heating_system",
    "statistics_days",
}


def normalise_reporting_mode(value: Any) -> str:
    """Return a supported reporting mode; unknown input fails closed."""
    text = str(value or "off").strip().lower()
    return text if text in REPORTING_MODES else "off"


def deterministic_upload_slot(installation_id: str) -> tuple[int, int]:
    """Return a stable local upload slot between 02:00 and 03:59.

    The two-hour spread prevents every FreshAirIQ installation from contacting
    the hub at the same minute while remaining deterministic for each install.
    """
    digest = hashlib.sha256(str(installation_id or "anonymous").encode("utf-8")).digest()
    minute_of_window = int.from_bytes(digest[:2], "big") % 120
    return 2 + minute_of_window // 60, minute_of_window % 60


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None


def _same_time_basis(value: datetime | None, now: datetime) -> datetime | None:
    """Align a persisted timestamp with ``now`` for safe comparisons."""
    if value is None:
        return None
    if now.tzinfo is None:
        return value.replace(tzinfo=None)
    if value.tzinfo is None:
        return value.replace(tzinfo=now.tzinfo)
    return value.astimezone(now.tzinfo)


def upload_due(
    mode: Any,
    now: datetime,
    installation_id: str,
    *,
    last_success_at: Any = None,
    problem_fingerprint: str | None = None,
    last_problem_fingerprint: str | None = None,
) -> bool:
    """Return whether the configured cadence should upload now."""
    mode = normalise_reporting_mode(mode)
    if mode == "off":
        return False
    last = _same_time_basis(_parse_dt(last_success_at), now)
    if mode == "errors":
        if not problem_fingerprint:
            return False
        if problem_fingerprint != last_problem_fingerprint:
            return True
        return last is None or now - last >= timedelta(hours=24)

    hour, minute = deterministic_upload_slot(installation_id)
    if mode == "daily":
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now < target:
            return False
        return last is None or last.date() < now.date()

    # Weekly mode uses a second stable digest byte for the weekday.
    digest = hashlib.sha256(str(installation_id or "anonymous").encode("utf-8")).digest()
    weekday = digest[2] % 7
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    target = week_start + timedelta(days=weekday, hours=hour, minutes=minute)
    if now < target:
        return False
    return last is None or last < target


def retry_delay_seconds(consecutive_failures: Any) -> int:
    """Return bounded exponential retry delay (5 min .. 6 h)."""
    try:
        failures = max(int(consecutive_failures), 1)
    except (TypeError, ValueError, OverflowError):
        failures = 1
    return min(300 * (2 ** min(failures - 1, 8)), 6 * 60 * 60)


def problem_fingerprint(health: Mapping[str, Any] | None) -> str | None:
    """Build a privacy-safe fingerprint from runtime health signals."""
    health = health if isinstance(health, Mapping) else {}
    robust = health.get("robustness") if isinstance(health.get("robustness"), Mapping) else {}
    diagnostics = health.get("diagnostics") if isinstance(health.get("diagnostics"), Mapping) else {}
    try:
        consecutive = max(int(robust.get("consecutive_failures") or 0), 0)
    except (TypeError, ValueError, OverflowError):
        consecutive = 0
    issues = robust.get("runtime_config_issues")
    issues = sorted(str(item)[:80] for item in issues) if isinstance(issues, list) else []
    last_error = diagnostics.get("last_error")
    error_type = None
    if last_error:
        error_type = str(last_error).split(":", 1)[0][:80]
    if consecutive <= 0 and not issues and not error_type:
        return None
    payload = {
        "consecutive_failures": min(consecutive, 1000),
        "last_failure_type": str(robust.get("last_failure_type") or "")[:80],
        "runtime_config_issues": issues,
        "diagnostics_error_type": error_type,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def room_token(room_key: Any, installation_id: str) -> str:
    """Return a stable per-installation pseudonym for one room key."""
    raw = f"{installation_id}|room|{room_key}".encode("utf-8")
    return "room-" + hashlib.sha256(raw).hexdigest()[:12]


def _collect_room_keys(value: Any, found: set[str] | None = None) -> set[str]:
    found = found if found is not None else set()
    if isinstance(value, Mapping):
        room_key = value.get("room_key")
        if isinstance(room_key, str) and room_key:
            found.add(room_key)
        for key in ("room_keys", "followed_room_keys"):
            rows = value.get(key)
            if isinstance(rows, list):
                found.update(str(item) for item in rows if isinstance(item, str) and item)
        rooms = value.get("rooms")
        if isinstance(rooms, Mapping):
            found.update(str(key) for key in rooms if str(key))
        elif isinstance(rooms, list):
            for row in rooms:
                if isinstance(row, Mapping) and isinstance(row.get("key"), str) and row.get("key"):
                    found.add(str(row["key"]))
        for child in value.values():
            _collect_room_keys(child, found)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_room_keys(child, found)
    return found


def _redact_text(
    text: str, room_map: Mapping[str, str], *, preserve_ipv4_shaped_version: bool = False
) -> str:
    result = text
    for raw in sorted(room_map, key=len, reverse=True):
        if raw:
            result = result.replace(raw, room_map[raw])
    # Redact compound identifiers before entity-id shaped substrings inside
    # them (for example ``example.com`` in an e-mail or URL).
    result = _EMAIL_RE.sub("<redacted_email>", result)
    result = _URL_RE.sub("<redacted_url>", result)
    if not preserve_ipv4_shaped_version:
        result = _IPV4_RE.sub("<redacted_ip>", result)
    result = _ENTITY_RE.sub("<redacted_entity>", result)
    return result


def _sanitize_tree(
    value: Any, room_map: Mapping[str, str], path: tuple[str, ...] = ()
) -> Any:
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text in _DROP_KEYS:
                continue
            safe_key = room_map.get(key_text, key_text)
            clean[safe_key] = _sanitize_tree(child, room_map, path + (key_text,))
        return clean
    if isinstance(value, list):
        return [_sanitize_tree(item, room_map, path) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_tree(item, room_map, path) for item in value]
    if isinstance(value, str):
        return _redact_text(value, room_map, preserve_ipv4_shaped_version=_version_literal_path(path))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), room_map, preserve_ipv4_shaped_version=_version_literal_path(path))


def _safe_configuration(configuration: Any, room_map: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(configuration, Mapping):
        return {}
    rooms = configuration.get("rooms") if isinstance(configuration.get("rooms"), list) else []
    safe_rooms: list[dict[str, Any]] = []
    canonical_floors = {"basement", "ground_floor", "upper_floor", "attic", "other"}
    for raw_room in rooms:
        if not isinstance(raw_room, Mapping):
            continue
        row = deepcopy(dict(raw_room))
        if row.get("floor") not in canonical_floors:
            row["floor"] = "custom" if row.get("floor") else None
        safe_rooms.append(row)
    model_options = configuration.get("model_options") if isinstance(configuration.get("model_options"), Mapping) else {}
    safe = {
        "freshairiq_version": configuration.get("freshairiq_version"),
        "diagnostics_schema_version": configuration.get("diagnostics_schema_version"),
        "model_options": {key: model_options.get(key) for key in sorted(_REMOTE_SAFE_MODEL_OPTIONS) if key in model_options},
        "capabilities": deepcopy(configuration.get("capabilities")) if isinstance(configuration.get("capabilities"), Mapping) else {},
        "rooms": safe_rooms,
    }
    return _sanitize_tree(safe, room_map)


def _safe_client_context(field_test: Mapping[str, Any]) -> list[dict[str, Any]]:
    clients = field_test.get("known_clients")
    if not isinstance(clients, list):
        return []
    rows: list[dict[str, Any]] = []
    for client in clients[-8:]:
        if not isinstance(client, Mapping):
            continue
        current = client.get("current") if isinstance(client.get("current"), Mapping) else {}
        rows.append({
            "platform_family": current.get("platform_family"),
            "device_class": current.get("device_class"),
            "companion_app": bool(current.get("companion_app")),
            "companion_app_version": current.get("companion_app_version"),
            "browser_family": current.get("browser_family"),
            "browser_version": current.get("browser_version"),
            "webview_engine_version": current.get("webview_engine_version"),
            "viewport_css_px": deepcopy(current.get("viewport_css_px")),
            "device_pixel_ratio": current.get("device_pixel_ratio"),
        })
    return rows


def build_cloud_payload(
    exported: Mapping[str, Any],
    *,
    include_client_context: bool = False,
    max_records: int = DEFAULT_MAX_UPLOAD_RECORDS,
) -> dict[str, Any]:
    """Minimise and locally pseudonymise a diagnostics export for the hub.

    Raw room labels, room keys, HA entity IDs, notification targets, resident
    names, exact device models, IP addresses, e-mail addresses and URLs are not
    included in the resulting document.
    """
    exported = exported if isinstance(exported, Mapping) else {}
    field = exported.get("field_test") if isinstance(exported.get("field_test"), Mapping) else {}
    dossier = exported.get("test_dossier") if isinstance(exported.get("test_dossier"), Mapping) else {}
    installation_id = str(field.get("anonymous_installation_id") or "")
    if not installation_id:
        raise ValueError("diagnostics export has no anonymous installation id")
    try:
        limit = max(0, min(int(max_records), 2000))
    except (TypeError, ValueError, OverflowError):
        limit = DEFAULT_MAX_UPLOAD_RECORDS
    records = exported.get("records") if isinstance(exported.get("records"), list) else []
    selected_records = deepcopy(records[-limit:]) if limit else []
    configuration = dossier.get("configuration")
    source_for_keys = [configuration, selected_records, dossier.get("forecast_validation"), dossier.get("forecast_backtest")]
    room_keys: set[str] = set()
    for value in source_for_keys:
        _collect_room_keys(value, room_keys)
    room_map = {key: room_token(key, installation_id) for key in room_keys}
    # Room labels can surface in old completed-session text. Map labels to the
    # same pseudonym as their room key so they cannot leak through free text.
    if isinstance(configuration, Mapping):
        configured_rooms = configuration.get("rooms")
        if isinstance(configured_rooms, list):
            for room in configured_rooms:
                if not isinstance(room, Mapping):
                    continue
                raw_key = str(room.get("key") or "")
                raw_name = str(room.get("name") or "")
                if raw_key and raw_name and raw_key in room_map:
                    room_map[raw_name] = room_map[raw_key]

    environment = field.get("runtime_environment") if isinstance(field.get("runtime_environment"), Mapping) else {}
    safe_environment_keys = (
        "home_assistant_version", "installation_type", "channel", "dev", "hassio",
        "docker", "virtualenv", "python_version", "os_name", "os_version",
        "architecture", "container_architecture",
    )
    observation = field.get("observation") if isinstance(field.get("observation"), Mapping) else {}
    safe_observation_keys = (
        "period_start", "period_end", "period_span_days", "calendar_days_with_records",
        "longest_consecutive_calendar_day_streak", "largest_sampling_gap_minutes",
        "sampling_gaps_over_30_minutes", "record_count", "truncated", "read_error_count",
    )
    payload: dict[str, Any] = {
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "diagnostics_schema_version": exported.get("schema_version"),
        "freshairiq_version": exported.get("freshairiq_version"),
        "generated_at": exported.get("exported_at"),
        "anonymous_installation_id": installation_id,
        "runtime_environment": {key: environment.get(key) for key in safe_environment_keys if key in environment},
        "observation": {key: observation.get(key) for key in safe_observation_keys if key in observation},
        "freshairiq_version_history": deepcopy(field.get("freshairiq_version_history")) if isinstance(field.get("freshairiq_version_history"), list) else [],
        "home_assistant_version_history": deepcopy(field.get("home_assistant_version_history")) if isinstance(field.get("home_assistant_version_history"), list) else [],
        "configuration": _safe_configuration(configuration, room_map),
        "summary": {
            key: dossier.get(key)
            for key in (
                "period_start", "period_end", "period_span_days", "calendar_days_with_records",
                "longest_consecutive_calendar_day_streak", "largest_sampling_gap_minutes",
                "record_count", "reason_counts", "completed_session_count",
                "recommendation_followed_session_count", "window_event_count",
                "average_room_data_quality_percent",
            ) if key in dossier
        },
        "latest_forecast_validation": _sanitize_tree(deepcopy(dossier.get("forecast_validation") or {}), room_map),
        "latest_forecast_backtest": _sanitize_tree(deepcopy(dossier.get("forecast_backtest") or {}), room_map),
        "records": _sanitize_tree(selected_records, room_map),
        "privacy": {
            "room_labels_removed": True,
            "room_keys_pseudonymised": True,
            "entity_ids_redacted": True,
            "resident_names_removed": True,
            "notification_targets_removed": True,
            "exact_device_models_removed": True,
            "client_context_included": bool(include_client_context),
        },
    }
    if include_client_context:
        payload["client_context"] = _sanitize_tree(_safe_client_context(field), room_map)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


_CANONICAL_FLOORS = {"basement", "ground_floor", "upper_floor", "attic", "other", "custom"}


def _canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for transport fingerprints."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _extend_room_label_map(value: Any, room_map: dict[str, str]) -> None:
    """Map room labels found beside a room key to the same stable pseudonym."""
    if isinstance(value, Mapping):
        raw_key = value.get("room_key") if isinstance(value.get("room_key"), str) else value.get("key")
        raw_name = value.get("room_name") if isinstance(value.get("room_name"), str) else value.get("name")
        if isinstance(raw_key, str) and raw_key in room_map and isinstance(raw_name, str) and raw_name:
            room_map[raw_name] = room_map[raw_key]
        for child in value.values():
            _extend_room_label_map(child, room_map)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _extend_room_label_map(child, room_map)


def _extend_private_label_map(
    value: Any, replacements: dict[str, str], installation_id: str
) -> None:
    """Collect private labels that can reappear inside diagnostic free text."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in {"adult_resident_names", "child_resident_names"}:
                for name in normalise_resident_names(child):
                    replacements[name] = "<redacted_resident>"
            elif key_text == "levels" and isinstance(child, list):
                for level in child:
                    if isinstance(level, str) and level and level not in _CANONICAL_FLOORS:
                        token = hashlib.sha256(f"{installation_id}|level|{level}".encode("utf-8")).hexdigest()[:10]
                        replacements[level] = f"level-{token}"
            elif key_text in {"floor", "level", "floor_name", "level_name"} and isinstance(child, str):
                if child and child not in _CANONICAL_FLOORS:
                    token = hashlib.sha256(f"{installation_id}|level|{child}".encode("utf-8")).hexdigest()[:10]
                    replacements[child] = f"level-{token}"
            _extend_private_label_map(child, replacements, installation_id)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _extend_private_label_map(child, replacements, installation_id)


def _sanitize_analysis_tree(
    value: Any, room_map: Mapping[str, str], path: tuple[str, ...] = ()
) -> Any:
    """Sanitise an analysis tree while retaining non-identifying technical detail.

    This differs from the legacy minimiser: numeric model settings and diagnostic
    evidence are retained because the Hub needs analysis-equivalent information.
    Direct identifiers, raw room labels, entity IDs and custom floor labels are
    still removed locally before any network transfer.
    """
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text in _DROP_KEYS:
                continue
            safe_key = room_map.get(key_text, key_text)
            if key_text in {"floor", "level", "floor_name", "level_name"} and isinstance(child, str):
                child = child if child in _CANONICAL_FLOORS else "custom"
            clean[safe_key] = _sanitize_analysis_tree(child, room_map, path + (key_text,))
        return clean
    if isinstance(value, list):
        return [_sanitize_analysis_tree(item, room_map, path) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_analysis_tree(item, room_map, path) for item in value]
    if isinstance(value, str):
        return _redact_text(value, room_map, preserve_ipv4_shaped_version=_version_literal_path(path))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), room_map, preserve_ipv4_shaped_version=_version_literal_path(path))


def _record_transport_id(record: Mapping[str, Any]) -> str:
    """Return a stable content ID for one already-sanitised diagnostic record."""
    return hashlib.sha256(_canonical_json_bytes(record)).hexdigest()


def record_cursor(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the resumable cursor stored after a Hub acknowledges one record."""
    return {
        "schema_version": CURSOR_SCHEMA_VERSION,
        "timestamp": record.get("timestamp"),
        "record_id": _record_transport_id(record),
    }


def _timestamp_at_or_after(value: Any, boundary: Any) -> bool:
    """Conservatively compare timestamps; unknown values are resent, never lost."""
    current = _parse_dt(value)
    reference = _parse_dt(boundary)
    if current is None or reference is None:
        return True
    reference = _same_time_basis(reference, current)
    return reference is None or current >= reference


def select_records_after_cursor(
    records: list[dict[str, Any]], cursor: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    """Return only records not known to be acknowledged by the Hub.

    Exact cursor matches are lossless. If the local 30-day retention window has
    already pruned the acknowledged record, timestamp fallback may resend the
    boundary timestamp; per-record IDs let the Hub deduplicate that safely.
    """
    if not isinstance(cursor, Mapping) or not cursor.get("record_id"):
        return list(records)
    cursor_id = str(cursor.get("record_id"))
    cursor_timestamp = cursor.get("timestamp")
    for index, record in enumerate(records):
        if _record_transport_id(record) == cursor_id and record.get("timestamp") == cursor_timestamp:
            return list(records[index + 1 :])
    return [
        record for record in records
        if _timestamp_at_or_after(record.get("timestamp"), cursor_timestamp)
    ]


def build_analysis_export(
    exported: Mapping[str, Any], *, include_client_context: bool = False
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Create a locally anonymised, analysis-equivalent export.

    The manual Home Assistant export is not modified. This function creates a
    separate transport representation from it, retaining the full technical
    dossier and all retained records while removing direct identifiers.
    """
    exported = exported if isinstance(exported, Mapping) else {}
    field = exported.get("field_test") if isinstance(exported.get("field_test"), Mapping) else {}
    installation_id = str(field.get("anonymous_installation_id") or "")
    if not installation_id:
        raise ValueError("diagnostics export has no anonymous installation id")

    records = exported.get("records") if isinstance(exported.get("records"), list) else []
    room_keys = _collect_room_keys(exported)
    room_map = {key: room_token(key, installation_id) for key in room_keys}
    _extend_room_label_map(exported, room_map)
    _extend_private_label_map(exported, room_map, installation_id)

    # The sanitiser is functional: it builds new dict/list containers and never
    # mutates the diagnostics export. Avoiding a redundant deepcopy here cuts
    # both CPU time and peak memory for large 30-day field-test exports.
    sanitized_records = [
        _sanitize_analysis_tree(record, room_map)
        for record in records
        if isinstance(record, Mapping)
    ]
    metadata_source = {key: value for key, value in exported.items() if key != "records"}
    metadata = _sanitize_analysis_tree(metadata_source, room_map)
    metadata["anonymous_installation_id"] = installation_id
    metadata["privacy"] = (
        "FreshAirIQ Hub transport is locally redacted before upload; direct identifiers, "
        "raw room labels, entity IDs, network identifiers and exact device models are removed."
    )
    metadata["transport"] = {
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "cursor_schema_version": CURSOR_SCHEMA_VERSION,
        "analysis_equivalent": True,
        "full_retained_history": True,
        "incremental_after_first_ack": True,
    }
    metadata["transport_privacy"] = {
        "local_redaction_before_upload": True,
        "room_labels_removed": True,
        "room_keys_pseudonymised": True,
        "entity_ids_redacted": True,
        "resident_names_removed": True,
        "notification_targets_removed": True,
        "network_identifiers_removed": True,
        "exact_device_models_removed": True,
        "client_context_included": bool(include_client_context),
    }
    if include_client_context:
        metadata["client_context"] = _sanitize_analysis_tree(_safe_client_context(field), room_map)
    return metadata, sanitized_records


def _chunk_payload_size(payload: Mapping[str, Any]) -> int:
    """Return uncompressed canonical payload size used for the safety limit."""
    return len(_canonical_json_bytes(payload))


def _build_chunk_document(
    *,
    metadata: Mapping[str, Any],
    installation_id: str,
    batch_id: str,
    records: list[dict[str, Any]],
    record_ids: list[str],
    cursor_before: Mapping[str, Any] | None,
    chunk_index: int,
    chunk_count: int,
    initial_snapshot: bool,
) -> dict[str, Any]:
    cursor_after = (
        {
            "schema_version": CURSOR_SCHEMA_VERSION,
            "timestamp": records[-1].get("timestamp"),
            "record_id": record_ids[-1],
        }
        if records and record_ids
        else (dict(cursor_before) if isinstance(cursor_before, Mapping) else None)
    )
    document: dict[str, Any] = {
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "diagnostics_schema_version": metadata.get("schema_version"),
        "freshairiq_version": metadata.get("freshairiq_version"),
        "anonymous_installation_id": installation_id,
        "batch_id": batch_id,
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "initial_snapshot": bool(initial_snapshot),
        "incremental": not bool(initial_snapshot),
        "cursor_before": dict(cursor_before) if isinstance(cursor_before, Mapping) else None,
        "cursor_after": cursor_after,
        "record_ids": list(record_ids),
        "records": list(records),
        "metadata": dict(metadata),
    }
    digest_basis = dict(document)
    canonical = _canonical_json_bytes(digest_basis)
    document["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    document["chunk_id"] = "chunk-" + hashlib.sha256(
        _canonical_json_bytes({
            "batch_id": batch_id,
            "chunk_index": chunk_index,
            "record_ids": record_ids,
            "content_sha256": document["content_sha256"],
        })
    ).hexdigest()[:24]
    return document


def build_upload_chunks(
    exported: Mapping[str, Any],
    *,
    include_client_context: bool = False,
    after_cursor: Mapping[str, Any] | None = None,
    max_chunk_bytes: int = 2 * 1024 * 1024,
) -> list[dict[str, Any]]:
    """Build deterministic, resumable chunks without discarding retained history.

    The first successful transfer contains every record present in the normal
    30-day diagnostics export. Subsequent transfers select only records after
    the last acknowledged cursor. Each record also receives a stable content ID
    so the Hub can deduplicate a boundary resend after uncertain network errors.
    """
    try:
        byte_limit = int(max_chunk_bytes)
    except (TypeError, ValueError, OverflowError):
        byte_limit = 2 * 1024 * 1024
    if byte_limit < 4096:
        raise ValueError("diagnostics chunk limit is too small")

    metadata, all_records = build_analysis_export(
        exported, include_client_context=include_client_context
    )
    installation_id = str(metadata.get("anonymous_installation_id") or "")
    selected = select_records_after_cursor(all_records, after_cursor)
    selected_ids = [_record_transport_id(record) for record in selected]
    initial_snapshot = not (isinstance(after_cursor, Mapping) and after_cursor.get("record_id"))
    batch_basis = {
        "installation_id": installation_id,
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "generated_at": metadata.get("exported_at"),
        "cursor_before": dict(after_cursor) if isinstance(after_cursor, Mapping) else None,
        "record_ids": selected_ids,
    }
    batch_id = "batch-" + hashlib.sha256(_canonical_json_bytes(batch_basis)).hexdigest()[:24]

    # Partition in linear time. v0.25.0.24 rebuilt and canonicalised the whole
    # growing candidate chunk once per record, which made a large 30-day export
    # effectively quadratic. Here the fixed metadata cost is measured once and
    # each already-sanitised record contributes only its own canonical byte
    # weight. Final chunks are still measured exactly before they can leave HA.
    empty_probe = _build_chunk_document(
        metadata=metadata,
        installation_id=installation_id,
        batch_id=batch_id,
        records=[],
        record_ids=[],
        cursor_before=after_cursor,
        chunk_index=0,
        chunk_count=1,
        initial_snapshot=initial_snapshot,
    )
    empty_size = _chunk_payload_size(empty_probe)
    if empty_size > byte_limit:
        raise ValueError("diagnostics metadata exceeds chunk upload limit")

    if not selected:
        return [empty_probe]

    # Keep generous headroom for cursor changes, counters and hashes. The final
    # exact-size guard below remains authoritative, so estimation can never
    # allow an oversized payload to be uploaded.
    partition_limit = max(empty_size + 1, byte_limit - 4 * 1024)
    groups: list[tuple[list[dict[str, Any]], list[str]]] = []
    current_records: list[dict[str, Any]] = []
    current_ids: list[str] = []
    current_size = empty_size
    for record, record_id in zip(selected, selected_ids):
        record_weight = len(_canonical_json_bytes(record)) + len(_canonical_json_bytes(record_id)) + 2
        if current_records and current_size + record_weight > partition_limit:
            groups.append((current_records, current_ids))
            current_records = []
            current_ids = []
            current_size = empty_size
        current_records.append(record)
        current_ids.append(record_id)
        current_size += record_weight
    if current_records:
        groups.append((current_records, current_ids))

    chunks: list[dict[str, Any]] = []
    cursor_before_chunk = dict(after_cursor) if isinstance(after_cursor, Mapping) else None
    total = len(groups)
    for index, (group_records, group_ids) in enumerate(groups):
        chunk = _build_chunk_document(
            metadata=metadata,
            installation_id=installation_id,
            batch_id=batch_id,
            records=group_records,
            record_ids=group_ids,
            cursor_before=cursor_before_chunk,
            chunk_index=index,
            chunk_count=total,
            initial_snapshot=initial_snapshot,
        )
        if _chunk_payload_size(chunk) > byte_limit:
            raise ValueError("one diagnostics record exceeds chunk upload limit")
        chunks.append(chunk)
        cursor_before_chunk = chunk.get("cursor_after")
    return chunks
