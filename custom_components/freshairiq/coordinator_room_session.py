"""Per-room ventilation session lifecycle: start, restore/repair, tracking and close."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ROOM_TARGET_TEMPERATURE,
    CONF_ROOM_TARGET_TEMPERATURE_FALLBACK,
    CONF_ROOM_TARGET_TEMPERATURE_MODE,
)
from . import cover_guard
from .climate_sources import advance_climate_report_activity, climate_report_snapshot
from .consolidation import session_target_min as _session_target_min
from .coordinator_contacts import _room_physical_opened_at
from .coordinator_sources import _state_report_timestamp
from .goals import effective_temperature_target
from .intelligence import mark_recommendation_followed
from .measurement_frame import last_valid_session_measurement
from .model import absolute_humidity
from .robustness import finite_float
from .ventilation_result import (
    include_ventilation_group_start,
    new_ventilation_group,
    update_session_cross_tracking,
)


class RoomSessionMixin:
    """Per-room ventilation session lifecycle: start, restore/repair, tracking and close."""

    hass: HomeAssistant  # provided by the coordinator

    async def _async_room_session_lifecycle(
        self,
        *,
        active_passage_contacts: Any, cfg: Any, changed: Any, completed_sessions: Any,
        confirmed_close_seconds: Any, contacts_known: Any, cover_learning_guard: Any, cross: Any,
        humidity_entity: Any, humidity_state: Any, include: Any, key: Any, measurement_frame: Any,
        mechanical_exhaust_active: Any, mem: Any, now: Any, opening_mode: Any, options: Any,
        passage_door_active: Any, raw_contact_open: Any, ref_rh: Any, ref_t: Any,
        reference_humidity_entity: Any, reference_temperature_entity: Any, rh: Any, session_should: Any,
        specialist_opening_mode: Any, specialist_opening_signature: Any, stable_session_modes: Any,
        stable_since: Any, t: Any, temperature_entity: Any, temperature_state: Any,
        three_state_stale_contacts: Any, three_state_unknown_contacts: Any, ventilation_group: Any,
    ) -> Any:
        """Session lifecycle of one room: start, restore/repair, tracking and close."""
        # Monitor-only rooms never start sessions and never alter the IQ model/statistics.
        measurements_valid = (-10 < t < 50 and 5 <= rh <= 100 and -30 < ref_t < 60 and 0 <= ref_rh <= 100)
        session_should = session_should and include
        # Never create a session from startup placeholders (999/-1). Each
        # ventilation session starts with a fresh zero baseline; completed
        # session values are never carried into the next live balance.
        if session_should and not mem["session_active"] and measurements_valid:
            (changed, ventilation_group) = self._open_room_session(
                cfg=cfg, changed=changed, humidity_entity=humidity_entity, humidity_state=humidity_state,
                mechanical_exhaust_active=mechanical_exhaust_active, mem=mem, now=now, options=options,
                raw_contact_open=raw_contact_open, ref_rh=ref_rh, ref_t=ref_t, rh=rh,
                stable_session_modes=stable_session_modes, stable_since=stable_since, t=t,
                temperature_entity=temperature_entity, temperature_state=temperature_state,
                three_state_unknown_contacts=three_state_unknown_contacts,
                ventilation_group=ventilation_group,
            )
            (changed,) = self._freeze_session_start_context(
                active_passage_contacts=active_passage_contacts, cfg=cfg,
                cover_learning_guard=cover_learning_guard, cross=cross, key=key,
                measurement_frame=measurement_frame, mechanical_exhaust_active=mechanical_exhaust_active,
                mem=mem, now=now, opening_mode=opening_mode, passage_door_active=passage_door_active,
                raw_contact_open=raw_contact_open, ref_t=ref_t,
                reference_humidity_entity=reference_humidity_entity,
                reference_temperature_entity=reference_temperature_entity,
                specialist_opening_mode=specialist_opening_mode,
                specialist_opening_signature=specialist_opening_signature, t=t,
                three_state_stale_contacts=three_state_stale_contacts,
            )

        (changed,) = self._repair_restored_session(
            active_passage_contacts=active_passage_contacts, cfg=cfg, changed=changed, cross=cross,
            humidity_entity=humidity_entity, humidity_state=humidity_state,
            measurement_frame=measurement_frame, measurements_valid=measurements_valid,
            mechanical_exhaust_active=mechanical_exhaust_active, mem=mem, now=now, opening_mode=opening_mode,
            passage_door_active=passage_door_active,
            raw_contact_open=raw_contact_open, ref_rh=ref_rh, ref_t=ref_t, rh=rh,
            specialist_opening_mode=specialist_opening_mode,
            specialist_opening_signature=specialist_opening_signature,
            stable_session_modes=stable_session_modes, stable_since=stable_since, t=t,
            temperature_entity=temperature_entity, temperature_state=temperature_state,
            three_state_stale_contacts=three_state_stale_contacts,
        )

        (changed,) = self._track_active_session(
            changed=changed, cover_learning_guard=cover_learning_guard, cross=cross,
            humidity_entity=humidity_entity, humidity_state=humidity_state,
            measurements_valid=measurements_valid, mechanical_exhaust_active=mechanical_exhaust_active,
            mem=mem, now=now, opening_mode=opening_mode, raw_contact_open=raw_contact_open, ref_rh=ref_rh,
            ref_t=ref_t, rh=rh, specialist_opening_mode=specialist_opening_mode,
            specialist_opening_signature=specialist_opening_signature, t=t,
            temperature_entity=temperature_entity, temperature_state=temperature_state,
            three_state_stale_contacts=three_state_stale_contacts,
        )

        (changed,) = await self._async_track_session_close(
            cfg=cfg, changed=changed, completed_sessions=completed_sessions,
            confirmed_close_seconds=confirmed_close_seconds, contacts_known=contacts_known, cross=cross,
            humidity_state=humidity_state, key=key, measurement_frame=measurement_frame,
            measurements_valid=measurements_valid, mem=mem, now=now, raw_contact_open=raw_contact_open,
            ref_rh=ref_rh, ref_t=ref_t, reference_humidity_entity=reference_humidity_entity,
            reference_temperature_entity=reference_temperature_entity, rh=rh, session_should=session_should,
            t=t, temperature_state=temperature_state,
        )
        return (changed, measurements_valid, ventilation_group)

    def _open_room_session(
        self,
        *,
        cfg: Any, changed: Any, humidity_entity: Any, humidity_state: Any, mechanical_exhaust_active: Any,
        mem: Any, now: Any, options: Any, raw_contact_open: Any, ref_rh: Any, ref_t: Any, rh: Any,
        stable_session_modes: Any, stable_since: Any, t: Any, temperature_entity: Any, temperature_state: Any,
        three_state_unknown_contacts: Any, ventilation_group: Any,
    ) -> Any:
        """Open a new room session: group membership, comfort target and start baseline."""
        physical_started = _room_physical_opened_at(self.hass, cfg, contact_modes=stable_session_modes, contact_since=stable_since) or now
        if not isinstance(ventilation_group, dict) or not ventilation_group.get("active"):
            ventilation_group = new_ventilation_group(physical_started)
            self.store.data["ventilation_group"] = ventilation_group
        elif include_ventilation_group_start(ventilation_group, physical_started):
            changed = True
        mem["session_active"] = True
        mem["session_co2_only"] = bool(mem.get("co2_airing_last"))  # 0.26.5.4 (review A07): asked for CO2 alone
        # 0.26.4.10: the airing duration FreshAirIQ showed when the window was
        # opened. Until it has passed, a close is only advised if moisture
        # would come in (see model.analyse_room).
        # A session started by the exhaust fan alone has no planned time;
        # a window opened later in it gets one then (see below).
        fan_start = bool(mechanical_exhaust_active and not raw_contact_open)
        mem["session_target_min"] = None if fan_start else _session_target_min(self.data, options)
        mem["session_target_fan_start"] = fan_start
        target_mode = str(cfg.get(CONF_ROOM_TARGET_TEMPERATURE_MODE, "automatic"))
        manual_target = cfg.get(CONF_ROOM_TARGET_TEMPERATURE) if target_mode == "manual" else None
        auto_target = mem.get("last_plausible_comfort_target_c") if target_mode == "automatic" else None
        resolved_target, resolved_source = effective_temperature_target(
            manual=manual_target, thermostat_target=auto_target, fallback=cfg.get(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK)
        )
        mem["session_comfort_target_c"] = resolved_target
        mem["session_comfort_target_source"] = resolved_source
        mem["session_three_state_unknown_observed"] = bool(three_state_unknown_contacts)
        # Keep both clocks deliberately: session_started marks the first
        # trustworthy climate baseline used for moisture/temperature
        # forecast comparison and learning, while session_physical_started
        # marks the real contact opening used for physical runtime and
        # recommendation timing.
        mem["session_started"] = now.isoformat()
        mem["session_physical_started"] = physical_started.isoformat()
        mem["session_start_ah"] = absolute_humidity(t, rh)
        mem["session_start_source_ah"] = absolute_humidity(ref_t, ref_rh)
        mem["session_start_source_temp"] = ref_t
        mem["session_learning_start_ah"] = mem["session_start_ah"]
        mem["session_learning_source_ah"] = mem["session_start_source_ah"]
        mem["session_start_temp"] = t
        mem["session_start_humidity"] = rh
        mem["session_result_base_ml"] = 0.0
        mem["session_result_ml"] = 0.0
        mem["close_notified"] = False
        # Use the same aggregated/proxy states as the room calculation;
        # list-valued multi-sensor configs are not valid hass.states keys.
        temp_reported = _state_report_timestamp(temperature_state)
        humidity_reported = _state_report_timestamp(humidity_state)
        mem["session_last_temperature_update"] = temp_reported
        mem["session_last_humidity_update"] = humidity_reported
        # Persist the exact report clocks seen at physical/session start.
        # They are diagnostic evidence for the strict learning gate: a
        # value whose report timestamp never advances after opening must
        # never be treated as a fresh learning observation.
        mem["session_open_temperature_reported_at"] = temp_reported
        mem["session_open_humidity_reported_at"] = humidity_reported
        mem["session_last_valid_temperature"] = t
        mem["session_last_valid_humidity"] = rh
        mem["session_last_valid_reference_temperature"] = ref_t
        mem["session_last_valid_reference_humidity"] = ref_rh
        mem["session_last_valid_at"] = now.isoformat()
        # Reports that arrived after the physical opening but before a
        # configured contact-delay gate already belong to this airing.
        def _after_physical_open(stamp: str | None) -> bool:
            if not stamp:
                return False
            try:
                return datetime.fromisoformat(stamp) > physical_started
            except (TypeError, ValueError):
                return False
        mem["session_temperature_reports"] = int(_after_physical_open(temp_reported))
        mem["session_humidity_reports"] = int(_after_physical_open(humidity_reported))
        # Track every logical climate sensor independently. Reports that
        # already arrived after physical opening count even when a contact
        # delay postponed creation of the FreshAirIQ session.
        sensor_snapshot = climate_report_snapshot(self.hass, temperature_entity, humidity_entity)
        sensor_counts: dict[str, int] = {}
        for sensor_key, sensor_row in sensor_snapshot.items():
            count = 0
            for stamp in dict(sensor_row.get("reports") or {}).values():
                if _after_physical_open(stamp):
                    count += 1
            sensor_counts[sensor_key] = min(count, 99)
        mem["session_climate_report_state"] = sensor_snapshot
        mem["session_climate_report_counts"] = sensor_counts
        available_counts = [sensor_counts.get(k, 0) for k, row in sensor_snapshot.items() if row.get("available")]
        mem["session_fresh_measurements"] = min(max(available_counts), 2) if available_counts else 0
        return (changed, ventilation_group)

    def _freeze_session_start_context(
        self,
        *,
        active_passage_contacts: Any, cfg: Any, cover_learning_guard: Any, cross: Any, key: Any,
        measurement_frame: Any, mechanical_exhaust_active: Any, mem: Any, now: Any, opening_mode: Any,
        passage_door_active: Any, raw_contact_open: Any, ref_t: Any, reference_humidity_entity: Any,
        reference_temperature_entity: Any, specialist_opening_mode: Any, specialist_opening_signature: Any,
        t: Any, three_state_stale_contacts: Any,
    ) -> Any:
        """Start evidence, prediction placeholders and validation baseline of a new session."""
        self._clear_final_measurement_wait(mem, key)
        mem["session_start_frame_quality"] = measurement_frame.get("quality")
        mem["session_start_frame_skew_s"] = measurement_frame.get("skew_s")
        mem["session_start_frame_max_age_s"] = measurement_frame.get("max_age_s")
        mem["session_start_frame_learning_eligible"] = bool(measurement_frame.get("learning_eligible"))
        # Explain start evidence separately from the strict in-session gate.
        # A held battery-sensor value can be plausible without being fresh;
        # it never bypasses the later timestamp activity requirement.
        _start_age = float(measurement_frame.get("max_age_s") or 0.0)
        if _start_age <= 300.0:
            mem["start_measurement_state"] = "fresh"
        elif _start_age <= 1200.0 and measurement_frame.get("quality") not in {"invalid", "missing"}:
            mem["start_measurement_state"] = "held_plausible"
        else:
            mem["start_measurement_state"] = "uncertain"
        mem["start_measurement_in_session_gate_passed"] = False
        mem["session_learning_started"] = now.isoformat() if measurement_frame.get("learning_eligible") else None
        mem["session_last_eligible_ah"] = mem["session_start_ah"] if measurement_frame.get("learning_eligible") else None
        mem["session_last_eligible_at"] = now.isoformat() if measurement_frame.get("learning_eligible") else None
        mem["forecast_recent_removed_ml_min"] = None
        mem["forecast_recent_observed_at"] = None
        mem["session_moisture_source_detected"] = False
        mem["session_reference_moisture_reversal"] = False
        mem["session_cross_active"] = bool(cross)
        mem["session_cross_seconds"] = 0.0
        mem["session_cross_last_update"] = now.isoformat()
        mem["session_opening_mode"] = ("mechanical_exhaust" if mechanical_exhaust_active and not raw_contact_open else "combined" if mechanical_exhaust_active and raw_contact_open else ("cross" if cross and opening_mode == "open" else opening_mode))
        mem["session_specialist_opening_mode"] = ("mechanical_exhaust" if mechanical_exhaust_active and not raw_contact_open else "combined" if mechanical_exhaust_active and raw_contact_open else ("cross" if cross and opening_mode == "open" else specialist_opening_mode))
        mem["session_specialist_opening_signature"] = list(specialist_opening_signature) if specialist_opening_mode else []
        mem["session_opening_mode_mixed"] = False
        mem["session_passage_door"] = bool(passage_door_active and opening_mode == "open")
        mem["session_passage_contacts"] = list(active_passage_contacts) if opening_mode == "open" else []
        mem["session_learning_quarantined"] = bool(three_state_stale_contacts)
        mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006" if three_state_stale_contacts else None
        mem["session_contact_unknown_expired"] = False
        # 0.26.4.9: judged over the whole airing, not by its first moment.
        cover_guard.reset(mem)
        cover_guard.tick(mem, cover_learning_guard, now)
        mem["session_cover_learning_blocked"] = False
        mem["session_cover_learning_guard"] = dict(cover_learning_guard, session=cover_guard.verdict(mem, float(cover_learning_guard.get("threshold", 20.0))))
        # Hotfix 0.20.2.6: a session prediction is frozen from the first
        # forecast calculated after the physical opening. Never carry a
        # previous recommendation/live forecast into a new session.
        mem["session_predicted_removed_ml"] = None
        mem["session_predicted_temperature_change_c"] = None
        mem["session_predicted_cost"] = None
        mem["session_prediction_confidence"] = None
        mem["session_prediction_snapshot_at"] = None
        mem["session_prediction_horizon_min"] = None
        mem["session_prediction_snapshot_elapsed_min"] = None
        mem["session_prediction_snapshot_valid"] = False
        mem["session_prediction_snapshot_pending"] = True
        mem["session_prediction_reference"] = None
        mem["session_prediction_start_context"] = None
        mem["session_validation_id"] = f"{key}:{now.isoformat()}"
        mem["session_prediction_time_aligned"] = False
        mem["session_prediction_snapshot_frame_quality"] = None
        mem["session_prediction_snapshot_frame_skew_s"] = None
        mem["session_prediction_snapshot_frame_max_age_s"] = None
        # Freeze the physical/logical start values immediately. Their
        # trustworthiness is decided later from actual sensor activity
        # during this session, not from an arbitrary age threshold alone.
        mem["session_validation_started"] = now.isoformat()
        mem["session_validation_start_ah"] = mem["session_start_ah"]
        mem["session_validation_start_source_ah"] = mem["session_start_source_ah"]
        mem["session_validation_start_temp"] = t
        mem["session_validation_start_source_temp"] = ref_t
        mem["session_last_validation_ah"] = mem["session_start_ah"]
        mem["session_last_validation_temp"] = t
        mem["session_last_validation_at"] = now.isoformat()
        mem["session_forecast_timeline"] = []
        mem["session_timeline_last_checkpoint_min"] = None
        if mark_recommendation_followed(self.store.data, mem, key, now):
            changed = True
        # Baseline is captured first; only then ask HA/integration for a
        # fresh report. No extra entity configuration is required.
        self.hass.async_create_task(self._async_request_room_sensor_refresh(
            cfg,
            active_reference_temperature=reference_temperature_entity,
            active_reference_humidity=reference_humidity_entity,
        ))
        changed = True
        return (changed,)

    def _repair_restored_session(
        self,
        *,
        active_passage_contacts: Any, cfg: Any, changed: Any, cross: Any, humidity_entity: Any,
        humidity_state: Any, measurement_frame: Any, measurements_valid: Any, mechanical_exhaust_active: Any,
        mem: Any, now: Any, opening_mode: Any, passage_door_active: Any,
        raw_contact_open: Any, ref_rh: Any, ref_t: Any, rh: Any, specialist_opening_mode: Any,
        specialist_opening_signature: Any, stable_session_modes: Any, stable_since: Any, t: Any,
        temperature_entity: Any, temperature_state: Any, three_state_stale_contacts: Any,
    ) -> Any:
        """Keep restored session baselines and repair malformed legacy sessions."""
        # Restart continuity: keep the ORIGINAL session baseline across a
        # Home Assistant restart. This is the only way to continue the live
        # moisture balance physically from the moment the window was opened.
        # The separately persisted session_result_ml is only a display/fallback
        # value while climate sensors are temporarily unavailable during startup.
        # Once valid measurements return, evaluate_room() again compares the
        # current absolute humidity with the original session_start_ah and the
        # displayed balance therefore continues without a visible reset to 0 ml.
        if self._first_update and mem["session_active"]:
            mem.setdefault("session_learning_start_ah", mem.get("session_start_ah"))
            mem.setdefault("session_learning_source_ah", mem.get("session_start_source_ah"))

        # Repair persisted sessions from older versions. Never reset a valid
        # active session merely because it is old: a window may legitimately
        # remain open for hours. Only malformed/future timestamps or invalid
        # physical baselines are repaired.
        if mem["session_active"] and measurements_valid:
            persisted_start_temp = finite_float(mem.get("session_start_temp"))
            persisted_start_ah = finite_float(mem.get("session_start_ah"))
            bad_start_temp = persisted_start_temp is None or not (-10 < persisted_start_temp < 50)
            bad_start_ah = persisted_start_ah is None or not (0 < persisted_start_ah < 40)
            bad_started = False
            try:
                started = datetime.fromisoformat(mem.get("session_started"))
                age_min = (now - started).total_seconds() / 60.0
                bad_started = age_min < -2.0
            except (TypeError, ValueError):
                bad_started = True
            if bad_start_temp or bad_start_ah or bad_started:
                mem["session_started"] = now.isoformat()
                # A repaired legacy/corrupt session has no trustworthy
                # historical baseline. Preserve a known physical opening
                # timestamp when available; otherwise use the repair time.
                physical_started = _room_physical_opened_at(self.hass, cfg, contact_modes=stable_session_modes, contact_since=stable_since) or now
                mem["session_physical_started"] = physical_started.isoformat()
                mem["session_start_temp"] = t
                mem["session_start_humidity"] = rh
                mem["session_start_ah"] = absolute_humidity(t, rh)
                mem["session_start_source_ah"] = absolute_humidity(ref_t, ref_rh)
                mem["session_start_source_temp"] = ref_t
                mem["session_learning_start_ah"] = mem["session_start_ah"]
                mem["session_learning_source_ah"] = mem["session_start_source_ah"]
                mem["session_result_base_ml"] = 0.0
                mem["session_result_ml"] = 0.0
                mem["close_notified"] = False
                # Keep the same aggregated/proxy states used for this calculation cycle.
                # For a legacy single sensor this is the original HA State object.
                mem["session_last_temperature_update"] = _state_report_timestamp(temperature_state)
                mem["session_last_humidity_update"] = _state_report_timestamp(humidity_state)
                mem["session_open_temperature_reported_at"] = mem["session_last_temperature_update"]
                mem["session_open_humidity_reported_at"] = mem["session_last_humidity_update"]
                mem["session_last_valid_temperature"] = t
                mem["session_last_valid_humidity"] = rh
                mem["session_last_valid_reference_temperature"] = ref_t
                mem["session_last_valid_reference_humidity"] = ref_rh
                mem["session_last_valid_at"] = now.isoformat()
                # A repaired/legacy session has no auditable report history.
                # Start counting only reports whose timestamp advances after
                # this repair instead of inferring activity from an old value.
                mem["session_temperature_reports"] = 0
                mem["session_humidity_reports"] = 0
                mem["session_start_frame_quality"] = measurement_frame.get("quality")
                mem["session_start_frame_skew_s"] = measurement_frame.get("skew_s")
                mem["session_start_frame_max_age_s"] = measurement_frame.get("max_age_s")
                mem["session_start_frame_learning_eligible"] = bool(measurement_frame.get("learning_eligible"))
                mem["session_fresh_measurements"] = 0
                mem["session_climate_report_state"] = climate_report_snapshot(self.hass, temperature_entity, humidity_entity)
                mem["session_climate_report_counts"] = {key: 0 for key in mem["session_climate_report_state"]}
                mem["session_moisture_source_detected"] = False
                mem["session_reference_moisture_reversal"] = False
                mem["session_cross_active"] = bool(cross)
                mem["session_cross_seconds"] = 0.0
                mem["session_cross_last_update"] = now.isoformat()
                mem["session_opening_mode"] = ("mechanical_exhaust" if mechanical_exhaust_active and not raw_contact_open else "combined" if mechanical_exhaust_active and raw_contact_open else ("cross" if cross and opening_mode == "open" else opening_mode))
                mem["session_specialist_opening_mode"] = ("mechanical_exhaust" if mechanical_exhaust_active and not raw_contact_open else "combined" if mechanical_exhaust_active and raw_contact_open else ("cross" if cross and opening_mode == "open" else specialist_opening_mode))
                mem["session_specialist_opening_signature"] = list(specialist_opening_signature) if specialist_opening_mode else []
                mem["session_opening_mode_mixed"] = False
                mem["session_passage_door"] = bool(passage_door_active and opening_mode == "open")
                mem["session_passage_contacts"] = list(active_passage_contacts) if opening_mode == "open" else []
                # A repaired/legacy session must inherit current three-state
                # confidence. Never clear an already-known stale-contact quarantine.
                mem["session_learning_quarantined"] = bool(three_state_stale_contacts)
                mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006" if three_state_stale_contacts else None
                if three_state_stale_contacts:
                    mem["session_three_state_unknown_observed"] = True
                changed = True
        return (changed,)

    def _track_active_session(
        self,
        *,
        changed: Any, cover_learning_guard: Any, cross: Any, humidity_entity: Any, humidity_state: Any,
        measurements_valid: Any, mechanical_exhaust_active: Any, mem: Any, now: Any, opening_mode: Any,
        raw_contact_open: Any, ref_rh: Any, ref_t: Any, rh: Any, specialist_opening_mode: Any,
        specialist_opening_signature: Any, t: Any, temperature_entity: Any, temperature_state: Any,
        three_state_stale_contacts: Any,
    ) -> Any:
        """Reference reversal, last valid snapshot, cover/opening-mode consistency and report counting."""
        if mem["session_active"] and measurements_valid:
            # A session may start with dry reference air and later encounter
            # a weather reversal. Once reference air is no longer drier than
            # the room by the configured close margin, keep that fact sticky
            # for the session: the measurements remain useful for the balance
            # but must not teach the adaptive ventilation coefficient.
            current_room_ah = absolute_humidity(t, rh)
            current_reference_ah = absolute_humidity(ref_t, ref_rh)
            if current_reference_ah >= current_room_ah - float(self.options.get("close_delta", 0.4)):
                if not mem.get("session_reference_moisture_reversal"):
                    mem["session_reference_moisture_reversal"] = True
                    changed = True

        if mem["session_active"] and measurements_valid:
            # Keep the latest numeric climate state seen while this session is
            # active. This is only an end-of-session availability fail-safe: it
            # does not increment report counters and cannot make a session learnable.
            snapshot = (t, rh, ref_t, ref_rh)
            previous_snapshot = (
                mem.get("session_last_valid_temperature"),
                mem.get("session_last_valid_humidity"),
                mem.get("session_last_valid_reference_temperature"),
                mem.get("session_last_valid_reference_humidity"),
            )
            if snapshot != previous_snapshot or not mem.get("session_last_valid_at"):
                mem["session_last_valid_temperature"] = t
                mem["session_last_valid_humidity"] = rh
                mem["session_last_valid_reference_temperature"] = ref_t
                mem["session_last_valid_reference_humidity"] = ref_rh
                mem["session_last_valid_at"] = now.isoformat()
                changed = True

        if mem["session_active"]:
            cover_guard.tick(mem, cover_learning_guard, now)
            cover_verdict = cover_guard.verdict(mem, float(cover_learning_guard.get("threshold", 20.0)))
            if bool(mem.get("session_cover_learning_blocked")) != cover_verdict["blocked"]:
                changed = True
            mem["session_cover_learning_blocked"] = cover_verdict["blocked"]
            if cover_learning_guard.get("blocked") or cover_verdict["blocked"]:
                mem["session_cover_learning_guard"] = dict(cover_learning_guard, session=cover_verdict)
            current_session_mode = "mechanical_exhaust" if mechanical_exhaust_active and not raw_contact_open else "combined" if mechanical_exhaust_active and raw_contact_open else ("cross" if cross and opening_mode == "open" else opening_mode)
            started_mode = str(mem.get("session_opening_mode") or current_session_mode)
            if current_session_mode not in {"unknown", "closed"} and started_mode != current_session_mode:
                if not mem.get("session_opening_mode_mixed"):
                    mem["session_opening_mode_mixed"] = True
                    changed = True
            # Specialist learning is provenance-strict: the same room-level
            # mode is not enough if a binary contact joins/leaves or another
            # proven contact becomes the physical source.
            current_specialist = "mechanical_exhaust" if mechanical_exhaust_active and not raw_contact_open else "combined" if mechanical_exhaust_active and raw_contact_open else ("cross" if cross and opening_mode == "open" else specialist_opening_mode)
            started_specialist = mem.get("session_specialist_opening_mode")
            started_signature = tuple(str(x) for x in (mem.get("session_specialist_opening_signature") or []))
            current_signature = tuple(specialist_opening_signature) if current_specialist not in {None, "cross"} else ()
            # A closed room (close confirmation / final measurement wait) is not
            # a source change; like the room-level check above it never mixes.
            if started_specialist and not three_state_stale_contacts and (current_session_mode not in {"unknown", "closed"}) and (current_specialist != started_specialist or (started_specialist != "cross" and current_signature != started_signature)):
                if not mem.get("session_opening_mode_mixed"):
                    mem["session_opening_mode_mixed"] = True
                    changed = True
        if mem["session_active"] and update_session_cross_tracking(mem, now, cross and opening_mode == "open"):
            changed = True

        # Count real room-climate reports after the physical opening.
        # Temperature and humidity both contribute; unchanged numeric values
        # still count when Home Assistant advances ``last_reported``. Reports
        # that arrive only after the physical close belong to the final grace
        # phase and do not retroactively prove in-session activity.
        if mem["session_active"]:
            try:
                report_window_start = datetime.fromisoformat(str(mem.get("session_physical_started") or mem.get("session_started")))
            except (TypeError, ValueError):
                report_window_start = now
            report_window_end = None
            if mem.get("session_close_detected_at"):
                try:
                    report_window_end = datetime.fromisoformat(str(mem.get("session_close_detected_at")))
                except (TypeError, ValueError):
                    report_window_end = None

            report_specs = (
                (temperature_state, "session_last_temperature_update", "session_temperature_reports"),
                (humidity_state, "session_last_humidity_update", "session_humidity_reports"),
            )
            for sensor_state, timestamp_key, counter_key in report_specs:
                current_report = _state_report_timestamp(sensor_state)
                previous_report = mem.get(timestamp_key)
                if not current_report:
                    continue
                if previous_report is None or self._first_update:
                    if previous_report != current_report:
                        mem[timestamp_key] = current_report
                        changed = True
                    continue
                if current_report == previous_report:
                    continue
                mem[timestamp_key] = current_report
                try:
                    report_at = datetime.fromisoformat(current_report)
                    inside_session = report_at > report_window_start and (report_window_end is None or report_at <= report_window_end)
                except (TypeError, ValueError):
                    inside_session = False
                if inside_session:
                    mem[counter_key] = min(int(mem.get(counter_key, 0)) + 1, 99)
                changed = True
            current_sensor_snapshot = climate_report_snapshot(self.hass, temperature_entity, humidity_entity)
            next_sensor_state, next_sensor_counts, new_fresh = advance_climate_report_activity(
                mem.get("session_climate_report_state"),
                mem.get("session_climate_report_counts"),
                current_sensor_snapshot,
                window_start=report_window_start,
                window_end=report_window_end,
            )
            if mem.get("session_climate_report_state") != next_sensor_state:
                mem["session_climate_report_state"] = next_sensor_state
                changed = True
            if mem.get("session_climate_report_counts") != next_sensor_counts:
                mem["session_climate_report_counts"] = next_sensor_counts
                changed = True
            if int(mem.get("session_fresh_measurements", 0)) != new_fresh:
                mem["session_fresh_measurements"] = new_fresh
                changed = True
        return (changed,)

    async def _async_track_session_close(
        self,
        *,
        cfg: Any, changed: Any, completed_sessions: Any, confirmed_close_seconds: Any, contacts_known: Any,
        cross: Any, humidity_state: Any, key: Any, measurement_frame: Any, measurements_valid: Any, mem: Any,
        now: Any, raw_contact_open: Any, ref_rh: Any, ref_t: Any, reference_humidity_entity: Any,
        reference_temperature_entity: Any, rh: Any, session_should: Any, t: Any, temperature_state: Any,
    ) -> Any:
        """Learning/validation clocks and the close handling (final measurement wait, finish)."""
        # Learning retains the existing measurement-frame side channel, but
        # held/stale age alone no longer decides whether the completed session
        # is usable. The final decision is made from actual session activity.
        if mem["session_active"] and measurements_valid and measurement_frame.get("learning_eligible"):
            current_ah = absolute_humidity(t, rh)
            if not mem.get("session_learning_started"):
                mem["session_learning_started"] = now.isoformat()
                mem["session_learning_start_ah"] = current_ah
                mem["session_learning_source_ah"] = absolute_humidity(ref_t, ref_rh)
                mem["session_start_frame_quality"] = measurement_frame.get("quality")
                mem["session_start_frame_skew_s"] = measurement_frame.get("skew_s")
                mem["session_start_frame_max_age_s"] = measurement_frame.get("max_age_s")
                mem["session_start_frame_learning_eligible"] = True
                changed = True
            mem["session_last_eligible_ah"] = current_ah
            # Store the sensor report clock, not the coordinator-refresh clock.
            # This prevents repeatedly refreshed held values from looking new.
            report_stamps = [
                getattr(temperature_state, "last_reported", None) or getattr(temperature_state, "last_updated", None),
                getattr(humidity_state, "last_reported", None) or getattr(humidity_state, "last_updated", None),
            ]
            valid_stamps = [stamp for stamp in report_stamps if stamp is not None]
            mem["session_last_eligible_at"] = max(valid_stamps).isoformat() if valid_stamps else now.isoformat()

        # A/B frames still update the strict validation observation clock, but
        # the opening baseline itself was already frozen at session start.
        if mem["session_active"] and measurements_valid and measurement_frame.get("validation_eligible"):
            validation_ah = absolute_humidity(t, rh)
            mem["session_last_validation_ah"] = validation_ah
            mem["session_last_validation_temp"] = t
            report_stamps = [
                getattr(temperature_state, "last_reported", None) or getattr(temperature_state, "last_updated", None),
                getattr(humidity_state, "last_reported", None) or getattr(humidity_state, "last_updated", None),
            ]
            valid_stamps = [stamp for stamp in report_stamps if stamp is not None]
            mem["session_last_validation_at"] = max(valid_stamps).isoformat() if valid_stamps else now.isoformat()
            changed = True

        if mem["session_active"]:
            if session_should:
                # A reopen during the 3 s close-confirmation window or the later
                # end-measurement grace phase resumes the same ventilation. Clear
                # the tentative physical-close boundary as well as pending timers.
                if contacts_known and raw_contact_open and (mem.get("session_close_pending") or mem.get("session_close_detected_at")):
                    self._clear_final_measurement_wait(mem, key)
                    changed = True
            else:
                # Preserve the actual contact-close time; the later sensor wait
                # must never inflate ventilation duration.
                physical_closed_at = now
                if confirmed_close_seconds is not None:
                    physical_closed_at = now - timedelta(seconds=max(confirmed_close_seconds, 0.0))
                if not mem.get("session_close_pending"):
                    self._begin_final_measurement_wait(
                        mem, cfg, now=now, physical_closed_at=physical_closed_at,
                        temperature_state=temperature_state, humidity_state=humidity_state,
                        active_reference_temperature=reference_temperature_entity,
                        active_reference_humidity=reference_humidity_entity,
                    )
                    changed = True

                feedback_count = self._update_final_measurement_feedback(mem, temperature_state, humidity_state)
                try:
                    deadline = datetime.fromisoformat(str(mem.get("session_close_deadline_at")))
                except (TypeError, ValueError):
                    deadline = now
                wait_expired = now >= deadline
                if not wait_expired:
                    self._schedule_final_measurement_timeout(key, max((deadline - now).total_seconds(), 0.05))

                # Two room-climate responses let us finish immediately. If a
                # sleeping battery device does not answer, the grace phase is
                # capped at 10 s and session activity decides measurement trust.
                ready_to_finish = feedback_count >= 2 or wait_expired
                if ready_to_finish:
                    try:
                        session_ended_at = datetime.fromisoformat(str(mem.get("session_close_detected_at")))
                    except (TypeError, ValueError):
                        session_ended_at = physical_closed_at

                    event = None
                    if mem.get("session_contact_unknown_expired"):
                        # 0.26.5.0: ended because a dead contact stopped holding it –
                        # duration is logged, nothing is learned from the outcome.
                        self._cancel_final_measurement_timer(key)
                        event = self._finish_session_without_measurement(mem, cfg, session_ended_at)
                    elif measurements_valid:
                        # Missing post-close refresh feedback is not a rejection.
                        # The last currently held numeric state remains usable; the
                        # session quality stays "good" (0.75) instead of "high".
                        self._cancel_final_measurement_timer(key)
                        event = await self._finish_session(
                            mem, cfg, t, rh, ref_t, ref_rh, session_ended_at, cross, measurement_frame,
                            final_measurement_source="state_at_finalization",
                            final_measurement_timeout=wait_expired,
                        )
                    elif wait_expired:
                        # If HA marks a climate entity unavailable exactly at the
                        # deadline, finish from the most recent numeric climate
                        # snapshot already observed during this same session. This
                        # never creates timestamp evidence and therefore cannot
                        # bypass the strict in-session T+RH learning gate.
                        fallback = last_valid_session_measurement(mem)
                        self._cancel_final_measurement_timer(key)
                        if fallback is not None:
                            event = await self._finish_session(
                                mem, cfg,
                                fallback["temperature"], fallback["humidity"],
                                fallback["reference_temperature"], fallback["reference_humidity"],
                                session_ended_at, cross, measurement_frame,
                                final_measurement_source="last_valid_session_state",
                                final_measurement_timeout=True,
                            )
                        else:
                            # Legacy/corrupt restored sessions may have no stored
                            # numeric snapshot. They still must close deterministically
                            # after the grace window, but no physical outcome is learned.
                            event = self._finish_session_without_measurement(mem, cfg, session_ended_at)

                    if event:
                        completed_sessions.append(event)
                        changed = True

        return (changed,)
