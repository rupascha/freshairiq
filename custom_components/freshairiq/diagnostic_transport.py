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
# F39 (2026-10-16): technical codes and release versions are never personal
# data. Protect them from label pseudonymisation and entity redaction, so a
# floor called e.g. "DATA" cannot turn FAIQ-SENSOR-DATA-001 into garbage and
# "v0.26.5.0" stays readable. Four-part dotted numbers other than FreshAirIQ's
# 0.x versions keep being treated as IP addresses.
_TECHNICAL_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:(?:FAIQ|HUB)-[A-Z0-9]+(?:-[A-Z0-9]+)*"
    r"|v?0\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?(?![\d.])"
    r"|20\d\d\.\d{1,2}\.\d{1,2}(?![\d.]))"
)
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
    "shade_min_illuminance_lx", "shade_lead_min", "shade_forecast_max_c", "shade_max_cloud_coverage", "learning_enabled", "learning_max_duration_min",
    "operating_profile", "personalisation_enabled", "thermal_preference",
    "personal_priority", "night_window_preference", "cooling_start_temp_c",
    "cooling_min_outdoor_delta_c", "cooling_max_indoor_rh",
    "cooling_max_moisture_gain_5min_ml", "property_type", "night_start_hour",
    "night_end_hour", "night_forecast_enabled", "pollen_enabled", "pollen_max", "outdoor_pm25_enabled", "outdoor_pm25_max",
    "pollen_strict_veto", "wind_orientation_enabled", "heating_system",
    "statistics_days",
}


def normalise_reporting_mode(value: Any) -> str:
    """Return a supported reporting mode; unknown input fails closed."""
    text = str(value or "off").strip().lower()
    return text if text in REPORTING_MODES else "off"


# E09 (2026-10-16): automatic daily/weekly uploads are spread over the whole
# night window 00:30-06:00 (330 min) in the *local Home Assistant time zone*,
# with one-second resolution. The offset is derived from the existing anonymous
# installation id, so it is stable across restarts and needs no new identifier.
NIGHT_WINDOW_START_SECONDS = 30 * 60
NIGHT_WINDOW_END_SECONDS = 6 * 60 * 60
NIGHT_WINDOW_SECONDS = NIGHT_WINDOW_END_SECONDS - NIGHT_WINDOW_START_SECONDS


def deterministic_upload_offset_seconds(installation_id: str) -> int:
    """Stable second of this installation's slot inside the night window."""
    digest = hashlib.sha256(str(installation_id or "anonymous").encode("utf-8")).digest()
    return NIGHT_WINDOW_START_SECONDS + int.from_bytes(digest[4:8], "big") % NIGHT_WINDOW_SECONDS


def deterministic_upload_slot(installation_id: str) -> tuple[int, int]:
    """Return the stable local (hour, minute) of the upload slot (00:30-05:59)."""
    offset = deterministic_upload_offset_seconds(installation_id)
    return offset // 3600, (offset % 3600) // 60


def _local_midnight(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def nightly_upload_time(now: datetime, installation_id: str) -> datetime:
    """This installation's slot in the night window of ``now``'s local date.

    Wall-clock arithmetic keeps the slot at the same local time across DST
    changes; on the spring-forward night a slot inside the missing hour is
    simply reached one hour of real time earlier/later, never twice.
    """
    return _local_midnight(now) + timedelta(seconds=deterministic_upload_offset_seconds(installation_id))


def night_window_end(now: datetime) -> datetime:
    return _local_midnight(now) + timedelta(seconds=NIGHT_WINDOW_END_SECONDS)


def in_upload_window(now: datetime, installation_id: str) -> bool:
    """True between this installation's slot and 06:00 local time."""
    return nightly_upload_time(now, installation_id) <= now < night_window_end(now)


def next_nightly_upload_time(now: datetime, installation_id: str) -> datetime:
    """Next slot at or after ``now`` (today's if still ahead, otherwise tomorrow's)."""
    today = nightly_upload_time(now, installation_id)
    if now <= today:
        return today
    tomorrow = _local_midnight(now) + timedelta(days=1)
    return nightly_upload_time(tomorrow, installation_id)


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


DIAGNOSTICS_CONSENT_VALUES = ("unset", "granted", "declined")


def normalise_consent(value: Any) -> str:
    """Return the stored consent decision; anything unknown counts as undecided."""
    value = str(value or "").strip().lower()
    return value if value in DIAGNOSTICS_CONSENT_VALUES else "unset"


def effective_reporting_mode(options: Any) -> str:
    """Return the cadence that may actually run for scheduled uploads.

    Automatic uploads need an explicit ``granted`` decision. Undecided and
    declined installations never upload on a schedule; an explicit manual
    support send remains a separate, per-action consent.
    """
    options = options if isinstance(options, dict) else {}
    if normalise_consent(options.get("diagnostics_consent")) != "granted":
        return "off"
    return normalise_reporting_mode(options.get("diagnostics_reporting_mode", "daily"))


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

    # Regular uploads only run inside this installation's part of the night
    # window. A missed slot (Home Assistant offline, hub error until 06:00) is
    # taken up in the next night at the same individual slot - never as an
    # immediate catch-up wave after a restart during the day.
    if not in_upload_window(now, installation_id):
        return False
    if mode == "daily":
        return last is None or last.date() < now.date()

    # Weekly mode uses a second stable digest byte for the weekday; a missed
    # weekly slot is taken up in one of the following nights.
    digest = hashlib.sha256(str(installation_id or "anonymous").encode("utf-8")).digest()
    weekday = digest[2] % 7
    week_start = _local_midnight(now - timedelta(days=now.weekday()))
    target = nightly_upload_time(week_start + timedelta(days=weekday), installation_id)
    if now < target:
        target = nightly_upload_time(week_start - timedelta(days=7 - weekday), installation_id)
    return last is None or last < target


def retry_delay_seconds(consecutive_failures: Any, installation_id: str | None = None, retry_after: Any = None) -> int:
    """Return bounded exponential retry delay (5 min .. 6 h).

    E09: with an ``installation_id`` an individual, stable offset of up to 25 %
    is added, so installations that failed together (hub restart) do not
    retry together. A server ``Retry-After`` is honoured as a lower bound.
    """
    try:
        failures = max(int(consecutive_failures), 1)
    except (TypeError, ValueError, OverflowError):
        failures = 1
    delay = min(300 * (2 ** min(failures - 1, 8)), 6 * 60 * 60)
    if installation_id:
        digest = hashlib.sha256(f"{installation_id}:retry:{failures}".encode("utf-8")).digest()
        delay += int(delay * 0.25 * (int.from_bytes(digest[:2], "big") / 65535.0))
    try:
        server = int(float(retry_after))
    except (TypeError, ValueError, OverflowError):
        server = 0
    if 0 < server <= 24 * 60 * 60:
        delay = max(delay, server)
    return delay


def problem_fingerprint(health: Mapping[str, Any] | None) -> str | None:
    """Build a privacy-safe fingerprint from runtime health signals."""
    health = health if isinstance(health, Mapping) else {}
    robust = health.get("robustness") if isinstance(health.get("robustness"), Mapping) else {}
    diagnostics = health.get("diagnostics") if isinstance(health.get("diagnostics"), Mapping) else {}
    runtime_health = health.get("runtime_health") if isinstance(health.get("runtime_health"), Mapping) else {}
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
    runtime_incidents = runtime_health.get("incidents") if isinstance(runtime_health.get("incidents"), list) else []
    runtime_fingerprints = sorted(
        str(item.get("fingerprint"))[:80]
        for item in runtime_incidents
        if isinstance(item, Mapping) and item.get("fingerprint") and str(item.get("status") or "active") != "resolved"
    )[:32]
    if consecutive <= 0 and not issues and not error_type and not runtime_fingerprints:
        return None
    payload = {
        "consecutive_failures": min(consecutive, 1000),
        "last_failure_type": str(robust.get("last_failure_type") or "")[:80],
        "runtime_config_issues": issues,
        "diagnostics_error_type": error_type,
        "runtime_incident_fingerprints": runtime_fingerprints,
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
    protected: list[str] = []

    def _protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    result = _TECHNICAL_TOKEN_RE.sub(_protect, text) if text not in room_map else text
    for raw in sorted(room_map, key=len, reverse=True):
        if not raw:
            continue
        if result == raw:
            result = room_map[raw]
            continue
        # 0.26.4.2: hub data showed a floor named "1" being replaced inside every
        # number ("FAIQ-SENSOR-DATA-001" -> "...-00level-<hash>", timestamps too).
        # Labels now only match as whole tokens; purely numeric labels only when
        # they are the entire value.
        if raw.isdigit():
            continue
        result = re.sub(rf"(?<![\w]){re.escape(raw)}(?![\w])", lambda _m, _r=room_map[raw]: _r, result)
    # Redact compound identifiers before entity-id shaped substrings inside
    # them (for example ``example.com`` in an e-mail or URL).
    result = _EMAIL_RE.sub("<redacted_email>", result)
    result = _URL_RE.sub("<redacted_url>", result)
    if not preserve_ipv4_shaped_version:
        result = _IPV4_RE.sub("<redacted_ip>", result)
    result = _ENTITY_RE.sub("<redacted_entity>", result)
    if protected:
        result = re.sub("\x00(\\d+)\x00", lambda m: protected[int(m.group(1))], result)
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
                "recommendation_opportunity_count", "recommendation_followed_count", "recommendation_missed_count", "recommendation_pending_count", "recommendation_followed_session_count", "window_event_count",
                "average_room_data_quality_percent",
            ) if key in dossier
        },
        "latest_forecast_validation": _sanitize_tree(deepcopy(dossier.get("forecast_validation") or {}), room_map),
        "latest_forecast_backtest": _sanitize_tree(deepcopy(dossier.get("forecast_backtest") or {}), room_map),
        "learning_v2": _sanitize_tree(deepcopy(dossier.get("learning_v2") or {}), room_map),
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


def _canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for transport fingerprints."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


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


def _chunk_payload_size(payload: Mapping[str, Any]) -> int:
    """Return uncompressed canonical payload size used for the safety limit."""
    return len(_canonical_json_bytes(payload))


# The analysis export and upload chunking live in diagnostic_chunks, which builds on
# this module; their names stay importable from here without a circular import.
_CHUNK_NAMES = frozenset({
    "_CANONICAL_FLOORS",
    "_extend_room_label_map",
    "_extend_private_label_map",
    "_sanitize_analysis_tree",
    "select_records_after_cursor",
    "build_analysis_export",
    "_build_chunk_document",
    "build_upload_chunks",
})


def __getattr__(name: str) -> Any:
    if name in _CHUNK_NAMES:
        from . import diagnostic_chunks

        return getattr(diagnostic_chunks, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
