"""Runtime hardening helpers for FreshAirIQ.

This module deliberately contains no ventilation physics.  Its job is to keep
bad/corrupt configuration, state storms, persisted non-finite values and a
single failed coordinator update from turning into a cascade failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Iterable

from .const import (
    CONF_ROOM_NAME,
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_VOLUME,
)


def finite_float(value: Any, default: float | None = None) -> float | None:
    """Convert a value to a finite float, otherwise return the fallback."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if isfinite(number) else default


def finite_int(value: Any, default: int = 0) -> int:
    """Convert a value to an int without allowing non-finite numbers through."""
    number = finite_float(value)
    if number is None:
        return default
    # finite_float() guarantees a real finite float here, so int() cannot hit
    # TypeError/ValueError/OverflowError. Keep the conversion explicit and avoid
    # an unreachable exception branch in release-critical code.
    return int(number)


def safe_options(defaults: dict[str, Any], configured: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Merge options while repairing only clearly invalid numeric persistence.

    Home Assistant UI validation protects normal writes.  This second line of
    defence is for hand-edited/corrupt storage and migrations from old builds.
    It never changes valid values and intentionally leaves enums/lists/strings
    untouched so product behaviour cannot silently drift.
    """
    merged = {**defaults, **configured}
    repaired: list[str] = []
    for key, default in defaults.items():
        if isinstance(default, bool) or not isinstance(default, (int, float)):
            continue
        value = merged.get(key)
        numeric = finite_float(value)
        if numeric is None:
            merged[key] = default
            repaired.append(key)
            continue
        merged[key] = int(numeric) if isinstance(default, int) else numeric
    return merged, repaired


def prepare_runtime_rooms(raw_rooms: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Return runtime-safe room dictionaries plus non-fatal configuration issues.

    A malformed room must never prevent healthy rooms from updating.  Rooms
    without a stable key cannot safely be represented and are skipped.  Invalid
    volume/sort values are degraded to non-actionable defaults so the existing
    model reports bad configuration instead of raising an exception.
    """
    if not isinstance(raw_rooms, list):
        return [], ["rooms_not_a_list"] if raw_rooms not in (None, []) else []

    prepared: list[dict[str, Any]] = []
    issues: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_rooms):
        if not isinstance(raw, dict):
            issues.append(f"room_{index}:not_a_mapping")
            continue
        room = dict(raw)
        key = room.get("key")
        if not isinstance(key, str) or not key.strip():
            issues.append(f"room_{index}:missing_key")
            continue
        key = key.strip()
        if key in seen:
            issues.append(f"room_{index}:duplicate_key:{key}")
            continue
        seen.add(key)
        room["key"] = key
        name = room.get(CONF_ROOM_NAME)
        if not isinstance(name, str) or not name.strip():
            room[CONF_ROOM_NAME] = key
            issues.append(f"room:{key}:missing_name")

        volume = finite_float(room.get(CONF_ROOM_VOLUME))
        if volume is None or volume < 0:
            room[CONF_ROOM_VOLUME] = 0.0
            issues.append(f"room:{key}:invalid_volume")
        else:
            room[CONF_ROOM_VOLUME] = volume

        room[CONF_ROOM_SORT_ORDER] = finite_int(room.get(CONF_ROOM_SORT_ORDER), 9999)
        prepared.append(room)
    return prepared, issues


def sanitize_runtime_session(room: dict[str, Any]) -> list[str]:
    """Repair corrupt/non-finite transient session persistence in-place.

    A running ventilation session survives Home Assistant restarts. That makes
    these fields more safety-critical than ordinary cached UI values: one hand-
    edited or partially written value must not trap the coordinator in a repeat
    failure loop. Valid values are preserved; invalid values are degraded to a
    neutral fallback so the coordinator can re-base from the next trustworthy
    measurement frame.
    """
    repaired: list[str] = []

    def _set(key: str, value: Any) -> None:
        if room.get(key) != value:
            room[key] = value
            repaired.append(key)

    # JSON storage should contain real booleans. Strings such as "false" are
    # truthy in Python and could otherwise resurrect a phantom ventilation.
    # Legacy runtime dictionaries are also accepted. Newly introduced optional
    # close/finalisation fields are only sanitised when they are already present;
    # ``FreshAirIQStore.room()`` merges their defaults for normal persisted rooms.
    for key in (
        "session_active",
        "session_prediction_snapshot_valid",
        "session_prediction_snapshot_pending",
        "session_start_frame_learning_eligible",
        "session_moisture_source_detected",
        "session_cross_active",
    ):
        value = room.get(key)
        if not isinstance(value, bool):
            _set(key, False)

    for key in (
        "session_close_pending",
        "session_close_temperature_feedback",
        "session_close_humidity_feedback",
    ):
        if key not in room:
            continue
        value = room.get(key)
        if not isinstance(value, bool):
            _set(key, False)

    nullable_ranges: dict[str, tuple[float, float]] = {
        "session_start_temp": (-30.0, 60.0),
        "session_start_ah": (0.0, 50.0),
        "session_start_source_ah": (0.0, 50.0),
        "session_learning_start_ah": (0.0, 50.0),
        "session_learning_source_ah": (0.0, 50.0),
        "session_last_valid_temperature": (-30.0, 60.0),
        "session_last_valid_humidity": (0.0, 100.0),
        "session_last_valid_reference_temperature": (-40.0, 70.0),
        "session_last_valid_reference_humidity": (0.0, 100.0),
        "session_predicted_removed_ml": (-1_000_000.0, 1_000_000.0),
        "session_predicted_temperature_change_c": (-50.0, 50.0),
        "session_predicted_cost": (0.0, 1_000_000.0),
        "session_prediction_confidence": (0.0, 100.0),
        "session_prediction_horizon_min": (0.0, 1_440.0),
        "session_prediction_snapshot_elapsed_min": (0.0, 1_440.0),
        "forecast_recent_removed_ml_min": (-100_000.0, 100_000.0),
    }
    for key, (low, high) in nullable_ranges.items():
        value = room.get(key)
        if value is None:
            continue
        numeric = finite_float(value)
        if numeric is None or not (low <= numeric <= high):
            _set(key, None)
        elif numeric != value:
            _set(key, numeric)

    for key in ("session_result_base_ml", "session_result_ml"):
        numeric = finite_float(room.get(key), 0.0)
        if numeric is None or not (-1_000_000.0 <= numeric <= 1_000_000.0):
            numeric = 0.0
        _set(key, numeric)

    cross_seconds = finite_float(room.get("session_cross_seconds"), 0.0)
    _set("session_cross_seconds", max(cross_seconds or 0.0, 0.0))

    has_report_counters = "session_temperature_reports" in room or "session_humidity_reports" in room
    if has_report_counters:
        temp_reports = min(max(finite_int(room.get("session_temperature_reports"), 0), 0), 99)
        humidity_reports = min(max(finite_int(room.get("session_humidity_reports"), 0), 0), 99)
        _set("session_temperature_reports", temp_reports)
        _set("session_humidity_reports", humidity_reports)
        fresh = min(max(finite_int(room.get("session_fresh_measurements"), temp_reports + humidity_reports), 0), 2)
        # Keep the compatibility field equal to the combined room-climate activity.
        fresh = min(max(temp_reports + humidity_reports, fresh), 2)
        _set("session_fresh_measurements", fresh)
    elif "session_fresh_measurements" in room:
        # Preserve the pre-v0.25.0.29 compatibility field when restoring a
        # legacy session that does not yet have split temperature/humidity counts.
        fresh = min(max(finite_int(room.get("session_fresh_measurements"), 0), 0), 2)
        _set("session_fresh_measurements", fresh)

    if not isinstance(room.get("session_forecast_timeline"), list):
        _set("session_forecast_timeline", [])

    return repaired


@dataclass(slots=True)
class RobustnessMonitor:
    """Small in-memory health ledger; never contains personal/sensor values."""

    refresh_successes: int = 0
    refresh_failures: int = 0
    consecutive_failures: int = 0
    source_events: int = 0
    coalesced_refreshes: int = 0
    weather_fetch_failures: int = 0
    listener_sources: int = 0
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_failure_type: str | None = None
    last_update_duration_ms: float | None = None
    repaired_option_keys: list[str] = field(default_factory=list)
    runtime_config_issues: list[str] = field(default_factory=list)

    def source_event(self) -> None:
        self.source_events += 1

    def coalesced_refresh(self) -> None:
        self.coalesced_refreshes += 1

    def weather_failure(self) -> None:
        self.weather_fetch_failures += 1

    def success(self, started: datetime) -> None:
        now = datetime.now().astimezone()
        self.refresh_successes += 1
        self.consecutive_failures = 0
        self.last_success_at = now.isoformat()
        self.last_update_duration_ms = round(max((now - started).total_seconds(), 0.0) * 1000.0, 1)

    def failure(self, started: datetime, exc: BaseException) -> None:
        now = datetime.now().astimezone()
        self.refresh_failures += 1
        self.consecutive_failures += 1
        self.last_failure_at = now.isoformat()
        self.last_failure_type = type(exc).__name__
        self.last_update_duration_ms = round(max((now - started).total_seconds(), 0.0) * 1000.0, 1)

    def snapshot(self) -> dict[str, Any]:
        return {
            "refresh_successes": self.refresh_successes,
            "refresh_failures": self.refresh_failures,
            "consecutive_failures": self.consecutive_failures,
            "source_events": self.source_events,
            "coalesced_refreshes": self.coalesced_refreshes,
            "weather_fetch_failures": self.weather_fetch_failures,
            "listener_sources": self.listener_sources,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "last_failure_type": self.last_failure_type,
            "last_update_duration_ms": self.last_update_duration_ms,
            "repaired_option_keys": list(self.repaired_option_keys),
            "runtime_config_issues": list(self.runtime_config_issues),
        }
