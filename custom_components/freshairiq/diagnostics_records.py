"""Diagnostics records: configuration snapshot, per-cycle and trend records, legacy compaction."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .exhaust_reference import exhaust_reference_pair
from .const import DIAGNOSTICS_SCHEMA_VERSION
from .diagnostic_transport import normalise_resident_names
from .diagnostics_privacy import (
    _LEARNING_ROOM_KEYS,
    _ROOM_KEYS,
    _SAFE_OPTION_KEYS,
    _TOP_LEVEL_KEYS,
    _TREND_ROOM_KEYS,
    _TREND_TOP_LEVEL_KEYS,
    _collection_size,
    _compact_learning_components,
    _json_safe,
    _latest_evidence,
    _pick,
    _privacy_safe_decision,
    _privacy_safe_iq_state,
    _runtime_environment_snapshot,
    _safe_int,
    _sha256_json,
    _three_state_learning_diagnostic,
)
from .support_incident import build_support_incident


class DiagnosticsRecordsMixin:
    """Diagnostics records: configuration snapshot, per-cycle and trend records, legacy compaction."""

    hass: HomeAssistant  # provided by the recorder

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
            passage_doors = raw.get("contact_passage_doors") if isinstance(raw.get("contact_passage_doors"), dict) else {}
            openings = []
            three_state = {str(x) for x in (live.get("three_state_contacts") or [])} if isinstance(live, dict) else set()
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
                    "passage_door": bool(passage_doors.get(contact, False)),
                    **self._contact_profile(str(contact), three_state),
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
                "contacts_sharing_a_name": self._duplicate_contact_names(contacts),
                "exhaust_reference_configured": exhaust_reference_pair(raw) is not None,
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
                "outdoor_pm25_sensor_configured": bool(entry_data.get("outdoor_pm25_entity")),
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
                "passage_door_count": sum(sum(1 for opening in row.get("openings", []) if opening.get("passage_door")) for row in room_rows),
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
        """Summarise quality only for rooms that participate in calculations.

        Monitor-only / structure-only rooms intentionally remain visible in the
        diagnostic record, but they are not decision inputs.  Treating their
        explicit ``monitor_only`` state as an error polluted the house quality
        score and made the Diagnostics Hub reopen FAIQ-DATA-002 even though the
        room was configured correctly (for example a conservatory used only as
        a local climate reference).
        """
        room_map = data.get("rooms") or {}
        all_rooms = (
            [room for room in room_map.values() if isinstance(room, dict)]
            if isinstance(room_map, dict)
            else []
        )

        def _is_monitor_only(room: dict[str, Any]) -> bool:
            # The explicit flags are authoritative for current records.  The
            # data_quality fallback keeps older diagnostic records compatible.
            return (
                room.get("calculation_enabled") is False
                or room.get("monitor_only") is True
                or room.get("data_quality") == "monitor_only"
            )

        rooms = [room for room in all_rooms if not _is_monitor_only(room)]
        monitor_only = [room for room in all_rooms if _is_monitor_only(room)]
        valid = [room for room in rooms if room.get("data_quality") == "ok"]
        issues = [
            {"room_key": str(room.get("key") or ""), "room_name": str(room.get("name") or ""),
             "data_quality": _json_safe(room.get("data_quality"))}
            for room in rooms if room.get("data_quality") != "ok"
        ]
        # Aggregate quality classes are deliberately identity-free. They are
        # sufficient to replay the sensor-safety branch without exporting a
        # room key, room label or Home Assistant entity ID.
        issue_quality_counts: dict[str, int] = {}
        issue_reason_counts: dict[str, int] = {}
        issue_age_buckets: dict[str, int] = {}
        for room in rooms:
            if room.get("data_quality") == "ok":
                continue
            quality = str(room.get("data_quality") or "unknown").strip().lower()[:32]
            issue_quality_counts[quality] = issue_quality_counts.get(quality, 0) + 1
            reason = str(room.get("measurement_frame_reason") or "unspecified").strip().lower()[:64]
            # Keep only a bounded technical class; never export room/entity identity here.
            reason = "_".join(part for part in reason.replace("-", "_").split() if part) or "unspecified"
            issue_reason_counts[reason] = issue_reason_counts.get(reason, 0) + 1
            ages = [room.get("frame_age_temp_s"), room.get("frame_age_humidity_s")]
            numeric_ages = []
            for value in ages:
                try:
                    if value is not None:
                        numeric_ages.append(max(float(value), 0.0))
                except (TypeError, ValueError, OverflowError):
                    pass
            if not numeric_ages:
                bucket = "unknown"
            else:
                age = max(numeric_ages)
                bucket = "lt_60s" if age < 60 else "60_300s" if age < 300 else "gt_300s"
            issue_age_buckets[bucket] = issue_age_buckets.get(bucket, 0) + 1
        return {
            "rooms_total": len(rooms),
            "rooms_ok": len(valid),
            "rooms_with_issues": len(issues),
            "room_quality_percent": round(100.0 * len(valid) / max(len(rooms), 1), 1),
            "rooms_all_total": len(all_rooms),
            "rooms_monitor_only": len(monitor_only),
            "issue_quality_counts": dict(sorted(issue_quality_counts.items())),
            "issue_reason_counts": dict(sorted(issue_reason_counts.items())),
            "issue_age_buckets": dict(sorted(issue_age_buckets.items())),
            "sensor_recovery_active": bool((data.get("sensor_recovery") or {}).get("active")) if isinstance(data.get("sensor_recovery"), dict) else False,
            "sensor_recovery_unavailable_sources": int((data.get("sensor_recovery") or {}).get("required_sources_unavailable") or 0) if isinstance(data.get("sensor_recovery"), dict) else 0,
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
            stored_room = (store_data.get("rooms") or {}).get(str(key), {}) if isinstance(store_data.get("rooms"), dict) else {}
            # Recommendation behaviour counters live in persistent room memory,
            # not in the coordinator's public room payload. Export them from the
            # canonical store so the nightly beta funnel can observe real advice.
            for counter_key in (
                "recommendation_opportunities", "recommendation_followed",
                "recommendation_missed", "recommendation_follow_rate",
                "recommendation_notified", "recommendation_followed_notified",
                "avg_follow_delay_min", "follow_delay_samples",
            ):
                if counter_key in stored_room:
                    room[counter_key] = _json_safe(stored_room.get(counter_key))
            room["three_state_learning"] = _three_state_learning_diagnostic(raw, stored_room)
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
            compact["three_state_learning"] = _three_state_learning_diagnostic(room_map.get(str(key), {}), raw)
            learning_rooms.append(compact)

        if window_events is None:
            window_events = self._window_events(data, now)

        decision_trace = (data.get("intelligent_recommendation") or {}).get("decision_trace") or {}
        sensor_quality = self._sensor_quality_summary(data)
        support_incident = build_support_incident(
            decision_trace, sensor_quality, diagnostics_error_type=(self.last_error or "").split(":", 1)[0] or None
        )

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
            "sensor_quality": sensor_quality,
            "support_incident": _json_safe(support_incident),
            "runtime_health": _json_safe(data.get("runtime_health") or {}),
            "presence_tracking": _json_safe(data.get("presence_diagnostics") or {}),
            "guardian": _json_safe(data.get("guardian") or {}),
            "recommendation_tracking": {
                "active_advice": _json_safe(store_data.get("iq_active_advice")),
                "followed_session_count": sum(1 for item in completed_sessions if item.get("recommendation_followed")),
                "completed_session_count": len(completed_sessions),
            },
            # 0.26.5.4: which fan command FreshAirIQ sent, why, and whether Home Assistant confirmed it
            "fan_automation_trace": _json_safe(data.get("fan_automation_trace") or []),
            "notification_delivery": {
                "trace_schema_version": 1,
                "recent_attempts": _json_safe((store_data.get("notification_diagnostics") or [])[-50:])
                if isinstance(store_data.get("notification_diagnostics"), list) else [],
                "privacy": "No notify entity IDs, service names, titles, messages or resident names are exported.",
            },
            "heating_model": {
                "system": _json_safe(data.get("heating_system")),
                "energy_price_per_kwh": _json_safe(data.get("energy_price_per_kwh")),
                "forecast_heat_kwh": _json_safe(data.get("forecast_heat_kwh")),
                "forecast_reheat_cost": _json_safe(data.get("forecast_cost")),
                "physical_heating_state": None,
                "physical_heating_state_reason": "No dedicated heating-state entity is configured in FreshAirIQ.",
            },
            "forecast_validation": _json_safe(_latest_evidence(data.get("forecast_validation"))),
            "post_close_stabilization": _json_safe(data.get("post_close_stabilization") or {}),
            "diagnostic_history_summary": {
                "post_close_stabilization_samples": _collection_size(data.get("post_close_stabilization_history")),
                "forecast_backtest_samples": _collection_size(data.get("forecast_backtest")),
            },
            "learning_effectiveness": _json_safe(data.get("learning_effectiveness") or {}),
            "learning_v2": _json_safe(data.get("learning_v2") or {}),
            "learning_components": _json_safe(_compact_learning_components(data.get("learning_components"))),
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
            "runtime_health": _json_safe(data.get("runtime_health") or {}),
            "presence_tracking": _json_safe(data.get("presence_diagnostics") or {}),
            "guardian": _json_safe(data.get("guardian") or {}),
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
