"""Diagnostics export: retained records, adoption funnel, histories and the export document."""
from __future__ import annotations

import json
from datetime import datetime
from math import isfinite
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DIAGNOSTICS_SCHEMA_VERSION
from .diagnostics_limits import (
    DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS,
    DIAGNOSTICS_IDENTITY_SCHEMA_VERSION,
    DIAGNOSTICS_IDLE_INTERVAL_SECONDS,
    DIAGNOSTICS_MAX_EXPORT_BYTES,
    DIAGNOSTICS_MAX_EXPORT_RECORDS,
    DIAGNOSTICS_RETENTION_DAYS,
)
from .diagnostics_privacy import (
    _json_safe,
    _longest_consecutive_day_streak,
    _runtime_environment_snapshot,
    _safe_int,
    _sha256_json,
)


class DiagnosticsExportMixin:
    """Diagnostics export: retained records, adoption funnel, histories and the export document."""

    hass: HomeAssistant  # provided by the recorder

    async def async_export(self) -> dict[str, Any]:
        """Return the retained trace as one portable field-test JSON document."""
        now = dt_util.now()
        environment = await self._async_runtime_environment()
        return await self.hass.async_add_executor_job(self._export_sync, now, environment)

    def _export_sync(self, now: datetime, runtime_environment: dict[str, Any] | None = None) -> dict[str, Any]:
        (errors, export_bytes, records, truncated_by_bytes) = self._read_export_records()
        (
            beta_funnel, completed_session_count, first_timestamp, followed_session_count, last_timestamp,
            quality_values, reason_counts, recommendation_followed, recommendation_missed,
            recommendation_opportunities, window_event_count,
        ) = self._export_adoption_funnel(
            records=records,
        )
        (
            clients, configuration_history, gap_count_over_30_min, ha_version_history, identity,
            largest_gap_minutes, latest_backtest, latest_effectiveness, latest_validation, period_span_days,
            recorded_days, version_history,
        ) = self._export_histories(
            now=now, records=records,
        )
        return self._export_document(
            beta_funnel=beta_funnel, clients=clients, completed_session_count=completed_session_count,
            configuration_history=configuration_history, errors=errors, export_bytes=export_bytes,
            first_timestamp=first_timestamp, followed_session_count=followed_session_count,
            gap_count_over_30_min=gap_count_over_30_min, ha_version_history=ha_version_history,
            identity=identity, largest_gap_minutes=largest_gap_minutes, last_timestamp=last_timestamp,
            latest_backtest=latest_backtest, latest_effectiveness=latest_effectiveness,
            latest_validation=latest_validation, now=now, period_span_days=period_span_days,
            quality_values=quality_values, reason_counts=reason_counts,
            recommendation_followed=recommendation_followed, recommendation_missed=recommendation_missed,
            recommendation_opportunities=recommendation_opportunities, recorded_days=recorded_days,
            records=records, runtime_environment=runtime_environment, truncated_by_bytes=truncated_by_bytes,
            version_history=version_history, window_event_count=window_event_count,
        )

    def _read_export_records(
        self,
    ) -> Any:
        """Read the retained JSONL records within the export record and byte limits."""
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
        return (errors, export_bytes, records, truncated_by_bytes)

    def _export_adoption_funnel(
        self,
        *,
        records: Any,
    ) -> Any:
        """Session and recommendation counts and the privacy-preserving adoption funnel."""
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

        # v0.25.0.66: privacy-preserving beta/adoption funnel.  Every stage is
        # derived from diagnostics evidence FreshAirIQ already records; no new
        # personal identifiers or raw interaction stream is collected.
        active_days = sorted({
            str(record.get("timestamp"))[:10]
            for record in records
            if isinstance(record.get("timestamp"), str) and len(str(record.get("timestamp"))) >= 10
        })
        first_valid_analysis_at = None
        first_recommendation_at = None
        first_followed_recommendation_at = None
        first_completed_session_at = None
        recommendation_opportunities = 0
        recommendation_followed = 0
        recommendation_missed = 0
        recommendation_notified = 0
        recommendation_followed_notified = 0
        for record in records:
            stamp = record.get("timestamp") if isinstance(record.get("timestamp"), str) else None
            quality = record.get("sensor_quality") if isinstance(record.get("sensor_quality"), dict) else {}
            if first_valid_analysis_at is None and isinstance(quality.get("room_quality_percent"), (int, float)) and float(quality.get("room_quality_percent") or 0) > 0:
                first_valid_analysis_at = stamp
            rooms = record.get("rooms") if isinstance(record.get("rooms"), list) else []
            record_opportunities = sum(
                _safe_int(room.get("recommendation_opportunities"))
                for room in rooms if isinstance(room, dict)
            )
            recommendation_opportunities = max(recommendation_opportunities, record_opportunities)
            record_followed = sum(_safe_int(room.get("recommendation_followed")) for room in rooms if isinstance(room, dict))
            record_missed = sum(_safe_int(room.get("recommendation_missed")) for room in rooms if isinstance(room, dict))
            recommendation_followed = max(recommendation_followed, record_followed)
            recommendation_missed = max(recommendation_missed, record_missed)
            recommendation_notified = max(recommendation_notified, sum(_safe_int(room.get("recommendation_notified")) for room in rooms if isinstance(room, dict)))
            recommendation_followed_notified = max(recommendation_followed_notified, sum(_safe_int(room.get("recommendation_followed_notified")) for room in rooms if isinstance(room, dict)))
            if first_recommendation_at is None and record_opportunities > 0:
                first_recommendation_at = stamp
            sessions = record.get("completed_sessions") if isinstance(record.get("completed_sessions"), list) else []
            if first_completed_session_at is None and sessions:
                first_completed_session_at = stamp
            if first_followed_recommendation_at is None and any(
                isinstance(item, dict) and item.get("recommendation_followed") for item in sessions
            ):
                first_followed_recommendation_at = stamp

        configured_rooms = 0
        if isinstance(self._config_snapshot, dict):
            rooms_cfg = self._config_snapshot.get("rooms")
            configured_rooms = len(rooms_cfg) if isinstance(rooms_cfg, (list, dict)) else 0
        setup_completed = configured_rooms > 0
        beta_funnel = {
            "schema_version": 1,
            "setup_completed": setup_completed,
            "configured_rooms": configured_rooms,
            "first_valid_analysis_at": first_valid_analysis_at,
            "first_recommendation_at": first_recommendation_at,
            "first_followed_recommendation_at": first_followed_recommendation_at,
            "first_completed_session_at": first_completed_session_at,
            "active_days_30d": len(active_days),
            "returning_user": len(active_days) >= 2,
            "retained_7d_signal": len(active_days) >= 2 and bool(active_days and first_timestamp and active_days[-1] > str(first_timestamp)[:10]),
            "recommendation_opportunities": recommendation_opportunities,
            "recommendation_followed": recommendation_followed,
            "recommendation_missed": recommendation_missed,
            "recommendation_pending": max(recommendation_opportunities - recommendation_followed - recommendation_missed, 0),
            # 0.26.4.3: was the resident told at all? Splits "ignored" from "never reached".
            "recommendation_notified": recommendation_notified,
            "recommendation_followed_notified": recommendation_followed_notified,
            "recommendation_counting_version": 2,
            "notifications_configured": bool(self._notifications_configured()),
            "completed_sessions": completed_session_count,
            "followed_sessions": followed_session_count,
            "follow_rate_percent": round(100.0 * followed_session_count / completed_session_count, 1) if completed_session_count else None,
            "measurement_window_days": 30,
        }
        return (
            beta_funnel, completed_session_count, first_timestamp, followed_session_count, last_timestamp,
            quality_values, reason_counts, recommendation_followed, recommendation_missed,
            recommendation_opportunities, window_event_count,
        )

    def _export_histories(
        self,
        *,
        now: Any, records: Any,
    ) -> Any:
        """Latest summaries, observed days, version/configuration history, gaps and clients."""
        latest_validation: dict[str, Any] = {}
        latest_backtest: dict[str, Any] = {}
        latest_effectiveness: dict[str, Any] = {}
        for record in reversed(records):
            candidate = record.get("forecast_validation")
            if isinstance(candidate, dict) and candidate:
                latest_validation = candidate
            candidate_backtest = record.get("forecast_backtest")
            if isinstance(candidate_backtest, dict) and candidate_backtest:
                latest_backtest = candidate_backtest
            candidate_effectiveness = record.get("learning_effectiveness")
            if isinstance(candidate_effectiveness, dict) and candidate_effectiveness:
                latest_effectiveness = candidate_effectiveness
            if latest_validation and latest_backtest and latest_effectiveness:
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
        return (
            clients, configuration_history, gap_count_over_30_min, ha_version_history, identity,
            largest_gap_minutes, latest_backtest, latest_effectiveness, latest_validation, period_span_days,
            recorded_days, version_history,
        )

    def _export_document(
        self,
        *,
        beta_funnel: Any, clients: Any, completed_session_count: Any, configuration_history: Any, errors: Any,
        export_bytes: Any, first_timestamp: Any, followed_session_count: Any, gap_count_over_30_min: Any,
        ha_version_history: Any, identity: Any, largest_gap_minutes: Any, last_timestamp: Any,
        latest_backtest: Any, latest_effectiveness: Any, latest_validation: Any, now: Any,
        period_span_days: Any, quality_values: Any, reason_counts: Any, recommendation_followed: Any,
        recommendation_missed: Any, recommendation_opportunities: Any, recorded_days: Any, records: Any,
        runtime_environment: Any, truncated_by_bytes: Any, version_history: Any, window_event_count: Any,
    ) -> Any:
        """Assemble the export document: observation, field-test summary and records."""
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
                "recommendation_opportunity_count": recommendation_opportunities,
                "recommendation_followed_count": recommendation_followed,
                "recommendation_missed_count": recommendation_missed,
                "recommendation_pending_count": max(recommendation_opportunities - recommendation_followed - recommendation_missed, 0),
                "recommendation_followed_session_count": followed_session_count,
                "beta_funnel": beta_funnel,
                "window_event_count": window_event_count,
                "average_room_data_quality_percent": round(sum(quality_values) / len(quality_values), 1) if quality_values else None,
                "configuration": _json_safe(self._config_snapshot),
                "forecast_validation": _json_safe(latest_validation),
                "forecast_backtest": _json_safe(latest_backtest),
                "learning_effectiveness": _json_safe(latest_effectiveness),
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
            "notification_delivery": {
                "trace_schema_version": 1,
                "recent_attempts": _json_safe(self._notification_delivery_snapshot),
                "privacy": "No notify entity IDs, service names, titles, messages or resident names are exported.",
            },
            "read_errors": errors,
            "records": records,
        }
