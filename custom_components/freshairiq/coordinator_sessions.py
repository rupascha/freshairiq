"""Finishing a room ventilation session: end measurement, learning, statistics and validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ROOMS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_HUMIDITY_AGGREGATION,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_TEMPERATURE_AGGREGATION,
    CONF_ROOM_VOLUME,
)
from . import cover_guard
from .climate_sources import aggregate_states, climate_report_snapshot, participating_climate_entities
from .coordinator_contacts import _contact_ids, _room_ventilation_state
from .intelligence import clear_session_behaviour, learn_completed_session
from .measurement_frame import session_measurement_quality, trusted_session_end_baseline
from .model import absolute_humidity, update_learning
from .opening_state import update_passage_pattern
from .post_stabilization import start_post_close_observation
from .robustness import finite_float


class SessionFinishMixin:
    """Finishing a room ventilation session: end measurement, learning, statistics and validation."""

    hass: HomeAssistant  # provided by the coordinator

    def _reset_completed_session_runtime(self, mem: dict[str, Any], room_key: str) -> None:
        """Clear only per-session runtime state after a definitive room close."""
        clear_session_behaviour(mem)
        self._cancel_final_measurement_timer(room_key)
        mem.update({
            "session_active": False,
            "session_started": None,
            "session_physical_started": None,
            "session_start_ah": None,
            "session_start_source_ah": None,
            "session_learning_start_ah": None,
            "session_learning_source_ah": None,
            "session_learning_started": None,
            "session_last_eligible_ah": None,
            "session_last_eligible_at": None,
            "session_start_temp": None,
            "session_start_humidity": None,
            "session_result_base_ml": 0.0,
            "close_notified": False,
            "session_fresh_measurements": 0,
            "session_target_min": None,
            "session_target_fan_start": False,
            "session_contact_unknown_expired": False,
            "session_temperature_reports": 0,
            "session_humidity_reports": 0,
            "session_last_temperature_update": None,
            "session_last_humidity_update": None,
            "session_open_temperature_reported_at": None,
            "session_open_humidity_reported_at": None,
            "session_last_valid_temperature": None,
            "session_last_valid_humidity": None,
            "session_last_valid_reference_temperature": None,
            "session_last_valid_reference_humidity": None,
            "session_last_valid_at": None,
            "session_close_pending": False,
            "session_close_detected_at": None,
            "session_close_wait_started_at": None,
            "session_close_deadline_at": None,
            "session_close_temperature_baseline": None,
            "session_close_humidity_baseline": None,
            "session_close_temperature_feedback": False,
            "session_close_humidity_feedback": False,
            "session_close_refresh_requested_at": None,
            "forecast_recent_removed_ml_min": None,
            "forecast_recent_observed_at": None,
            "session_moisture_source_detected": False,
            "session_reference_moisture_reversal": False,
            "session_cover_learning_blocked": False,
            "session_cover_learning_guard": {},
            **cover_guard.MEMORY_DEFAULTS,
            "session_cross_active": False,
            "session_three_state_unknown_observed": False,
            "session_cross_seconds": 0.0,
            "session_cross_last_update": None,
            "session_forecast_timeline": [],
            "session_timeline_last_checkpoint_min": None,
            "session_start_frame_quality": None,
            "session_start_frame_skew_s": None,
            "session_start_frame_max_age_s": None,
            "session_start_frame_learning_eligible": False,
            "session_prediction_snapshot_frame_quality": None,
            "session_prediction_snapshot_frame_skew_s": None,
            "session_prediction_snapshot_frame_max_age_s": None,
            "session_validation_id": None,
            "session_prediction_start_context": None,
            "session_prediction_time_aligned": False,
            "session_validation_started": None,
            "session_validation_start_ah": None,
            "session_validation_start_source_ah": None,
            "session_validation_start_temp": None,
            "session_validation_start_source_temp": None,
            "session_last_validation_ah": None,
            "session_last_validation_temp": None,
            "session_last_validation_at": None,
        })

    def _finish_session_without_measurement(
        self, mem: dict[str, Any], cfg: dict[str, Any], now: datetime
    ) -> dict[str, Any]:
        """Close a room session when no numeric end climate value is recoverable.

        This is a hard availability fail-safe, not a new learning path. The real
        ventilation duration is retained, but moisture/temperature outcome,
        physical learning, forecast calibration and repeat baselines are all
        explicitly unavailable.
        """
        started_raw = mem.get("session_physical_started") or mem.get("session_started")
        try:
            started = datetime.fromisoformat(str(started_raw)) if started_raw else now
        except (TypeError, ValueError):
            started = now
        if now < started:
            now = started
        elapsed = max(0.0, (now - started).total_seconds() / 60.0)
        elapsed_seconds = elapsed * 60.0
        cross_seconds = min(
            max(finite_float(mem.get("session_cross_seconds"), 0.0) or 0.0, 0.0),
            elapsed_seconds,
        )
        session_quality = session_measurement_quality(
            int(mem.get("session_fresh_measurements", 0)),
            temperature_reports=int(mem.get("session_temperature_reports", 0)),
            humidity_reports=int(mem.get("session_humidity_reports", 0)),
            final_temperature_feedback=bool(mem.get("session_close_temperature_feedback")),
            final_humidity_feedback=bool(mem.get("session_close_humidity_feedback")),
        )
        diagnosis = (
            "Lernmessung übersprungen: Nach dem Schließen war innerhalb der "
            "Abschlusswartezeit kein verwendbarer Temperatur-/Feuchte-Endwert verfügbar."
        )
        mem["diagnosis"] = diagnosis
        mem["last_learning_at"] = dt_util.now().isoformat()
        mem["last_learning_valid"] = False
        self.store.data["last_diagnosis"] = f"{cfg['name']}: {diagnosis}"
        self.store.record_session(
            now.replace(tzinfo=None), 0.0, elapsed, 0.0, 0.0, 0.0, cfg["key"], moisture_valid=False
        )
        learn_completed_session(mem, elapsed)
        pc_dates = mem.get("personal_context_observation_dates")
        if not isinstance(pc_dates, list):
            pc_dates = []
        pc_day = now.date().isoformat()
        if pc_day not in pc_dates:
            pc_dates.append(pc_day)
        mem["personal_context_observation_dates"] = pc_dates[-730:]

        (event, event_id) = self._unmeasured_session_event(
            cfg=cfg,
            cross_seconds=cross_seconds,
            elapsed=elapsed,
            elapsed_seconds=elapsed_seconds,
            mem=mem,
            now=now,
            session_quality=session_quality,
            started=started,
        )
        mem["session_result_ml"] = 0.0
        mem["last_ventilation_ended_at"] = now.isoformat()
        mem["last_ventilation_removed_ml"] = None
        mem["last_ventilation_end_humidity"] = None
        mem["last_ventilation_end_absolute_humidity"] = None
        mem["last_ventilation_reference_ah"] = None
        mem["post_close_active"] = False
        mem["post_close_last_outcome"] = {
            "event_id": event_id,
            "quality": "insufficient",
            "eligible": False,
            "reason": "Post-close learning skipped: no usable end climate measurement was available.",
        }
        self._reset_completed_session_runtime(mem, cfg["key"])
        return event

    async def _finish_session(
        self,
        mem: dict[str, Any],
        cfg: dict[str, Any],
        t: float,
        rh: float,
        ref_t: float,
        ref_rh: float,
        now: datetime,
        cross: bool,
        measurement_frame: dict[str, Any] | None = None,
        *,
        final_measurement_source: str = "state_at_finalization",
        final_measurement_timeout: bool = False,
    ) -> dict[str, Any]:
        (cover_learning_blocked, cover_session, elapsed, end_ah, frame_learning_eligible, learning_contaminated, learning_start_ah, measurement_elapsed, measurement_frame, measurement_started, now, reference_moisture_reversal, rh, session_activity_eligible, session_quality, session_removed, source_ah, source_contaminated, started, t, validation_end_ah, validation_end_max_age_s, validation_end_quality, validation_end_skew_s, validation_end_temp) = self._session_end_measurement(
            cfg=cfg,
            measurement_frame=measurement_frame,
            mem=mem,
            now=now,
            ref_rh=ref_rh,
            ref_t=ref_t,
            rh=rh,
            t=t,
        )
        (rate, valid) = self._learn_session_exchange(
            cfg=cfg,
            cover_learning_blocked=cover_learning_blocked,
            cover_session=cover_session,
            end_ah=end_ah,
            frame_learning_eligible=frame_learning_eligible,
            learning_contaminated=learning_contaminated,
            learning_start_ah=learning_start_ah,
            measurement_elapsed=measurement_elapsed,
            mem=mem,
            now=now,
            reference_moisture_reversal=reference_moisture_reversal,
            session_quality=session_quality,
            source_ah=source_ah,
        )
        (cost, cross_ratio, cross_seconds, purchased, temp_delta) = self._record_completed_session(
            cfg=cfg,
            elapsed=elapsed,
            mem=mem,
            now=now,
            rate=rate,
            ref_t=ref_t,
            session_activity_eligible=session_activity_eligible,
            session_removed=session_removed,
            t=t,
        )
        (feedback_accuracy, feedback_action, feedback_learned, feedback_reason, learning_effectiveness_sample, prediction_comparable, prediction_time_aligned, validation_elapsed, validation_removed, validation_started, validation_temp_delta) = self._validate_session_forecast(
            cfg=cfg,
            elapsed=elapsed,
            learning_contaminated=learning_contaminated,
            mem=mem,
            now=now,
            reference_moisture_reversal=reference_moisture_reversal,
            session_activity_eligible=session_activity_eligible,
            session_quality=session_quality,
            session_removed=session_removed,
            temp_delta=temp_delta,
            validation_end_ah=validation_end_ah,
            validation_end_temp=validation_end_temp,
        )
        (event, event_id) = self._session_completed_event(
            cfg=cfg,
            cost=cost,
            cover_learning_blocked=cover_learning_blocked,
            cross_ratio=cross_ratio,
            cross_seconds=cross_seconds,
            elapsed=elapsed,
            end_ah=end_ah,
            feedback_accuracy=feedback_accuracy,
            feedback_action=feedback_action,
            feedback_learned=feedback_learned,
            feedback_reason=feedback_reason,
            final_measurement_source=final_measurement_source,
            final_measurement_timeout=final_measurement_timeout,
            frame_learning_eligible=frame_learning_eligible,
            learning_effectiveness_sample=learning_effectiveness_sample,
            measurement_elapsed=measurement_elapsed,
            measurement_frame=measurement_frame,
            measurement_started=measurement_started,
            mem=mem,
            now=now,
            prediction_comparable=prediction_comparable,
            prediction_time_aligned=prediction_time_aligned,
            purchased=purchased,
            reference_moisture_reversal=reference_moisture_reversal,
            rh=rh,
            session_activity_eligible=session_activity_eligible,
            session_quality=session_quality,
            session_removed=session_removed,
            source_contaminated=source_contaminated,
            started=started,
            t=t,
            temp_delta=temp_delta,
            valid=valid,
            validation_elapsed=validation_elapsed,
            validation_end_max_age_s=validation_end_max_age_s,
            validation_end_quality=validation_end_quality,
            validation_end_skew_s=validation_end_skew_s,
            validation_removed=validation_removed,
            validation_started=validation_started,
            validation_temp_delta=validation_temp_delta,
        )
        mem["last_ventilation_ended_at"] = now.isoformat()
        mem["last_ventilation_removed_ml"] = round(session_removed, 1) if session_activity_eligible else None
        repeat_reference_ah = (
            absolute_humidity(ref_t, ref_rh)
            if -30 < ref_t < 60 and 0 <= ref_rh <= 100
            else None
        )
        repeat_baseline = trusted_session_end_baseline(
            timestamp_gate_passed=session_activity_eligible,
            end_humidity=rh,
            end_absolute_humidity=end_ah,
            reference_absolute_humidity=repeat_reference_ah,
        )
        mem["last_ventilation_end_humidity"] = (
            round(repeat_baseline["end_humidity"], 1)
            if repeat_baseline["end_humidity"] is not None else None
        )
        mem["last_ventilation_end_absolute_humidity"] = (
            round(repeat_baseline["end_absolute_humidity"], 3)
            if repeat_baseline["end_absolute_humidity"] is not None else None
        )
        mem["last_ventilation_reference_ah"] = (
            round(repeat_baseline["reference_absolute_humidity"], 3)
            if repeat_baseline["reference_absolute_humidity"] is not None else None
        )
        if session_activity_eligible:
            start_post_close_observation(
                mem, event_id=event_id, room_key=cfg["key"], room_name=cfg["name"], now=now, close_ah=end_ah, close_temp_c=t,
                removed_ml=session_removed, volume_m3=float(cfg[CONF_ROOM_VOLUME]),
                frame_quality=measurement_frame.get("quality"),
            )
        else:
            # Without proven in-session T+RH activity the end baseline is not
            # strong enough to seed post-close rebound learning either.
            mem["post_close_active"] = False
            mem["post_close_last_outcome"] = {
                "event_id": event_id,
                "quality": "insufficient",
                "eligible": False,
                "reason": "Post-close learning skipped: no complete in-session temperature/humidity timestamp evidence.",
            }
        self._reset_completed_session_runtime(mem, cfg["key"])
        return event

    def _session_end_measurement(
        self,
        *,
        cfg: Any,
        measurement_frame: Any,
        mem: Any,
        now: Any,
        ref_rh: Any,
        ref_t: Any,
        rh: Any,
        t: Any,
    ) -> Any:
        """Session duration, end measurement quality and the moisture balance of a finished session."""
        # Compatibility for direct/internal callers that predate Measurement
        # Frames. Production coordinator paths always provide the current frame.
        if not isinstance(measurement_frame, dict):
            measurement_frame = {"quality": "legacy", "learning_eligible": True, "validation_eligible": True, "skew_s": None, "max_age_s": None}
        measurement_started_raw = mem.get("session_learning_started") or mem.get("session_started")
        physical_started_raw = mem.get("session_physical_started") or measurement_started_raw
        try: measurement_started = datetime.fromisoformat(measurement_started_raw) if measurement_started_raw else now
        except (ValueError, TypeError): measurement_started = now
        try: started = datetime.fromisoformat(physical_started_raw) if physical_started_raw else measurement_started
        except (ValueError, TypeError): started = measurement_started
        if now < started:
            now = started
        if measurement_started < started:
            measurement_started = started
        if now < measurement_started:
            measurement_started = now
        elapsed = max(0.0, (now - started).total_seconds() / 60.0)
        measurement_elapsed = max(0.0, (now - measurement_started).total_seconds() / 60.0)

        # Keep live room climate independent from the session evidence gate. For
        # learning/finalisation, however, only logical sensors that produced at
        # least one fresh in-session report may influence the end measurement.
        # One sensor with >=2 reports is sufficient to open the room learning gate.
        _temperature_cfg = cfg.get(CONF_ROOM_TEMPERATURE)
        _humidity_cfg = cfg.get(CONF_ROOM_HUMIDITY)
        _snapshot = climate_report_snapshot(self.hass, _temperature_cfg, _humidity_cfg)
        _qualified_t, _qualified_h = participating_climate_entities(
            _temperature_cfg, _humidity_cfg, _snapshot, mem.get("session_climate_report_counts") or {}, min_reports=1
        )
        if _qualified_t:
            _session_t = aggregate_states(self.hass, _qualified_t, finite=finite_float, strategy=str(cfg.get(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean"))).value
            if _session_t is not None:
                t = _session_t
        if _qualified_h:
            _session_rh = aggregate_states(self.hass, _qualified_h, finite=finite_float, strategy=str(cfg.get(CONF_ROOM_HUMIDITY_AGGREGATION, "mean"))).value
            if _session_rh is not None:
                rh = _session_rh
        end_ah = absolute_humidity(t, rh) if -10 < t < 50 and 5 <= rh <= 100 else 0.0
        session_quality = session_measurement_quality(
            int(mem.get("session_fresh_measurements", 0)),
            temperature_reports=int(mem.get("session_temperature_reports", 0)),
            humidity_reports=int(mem.get("session_humidity_reports", 0)),
            final_temperature_feedback=bool(mem.get("session_close_temperature_feedback")),
            final_humidity_feedback=bool(mem.get("session_close_humidity_feedback")),
        )
        # In-session timestamp activity remains a hard gate. Historical
        # measurement-frame age classes may describe confidence, but they can no
        # longer make a session learnable when either room-climate channel never
        # produced a newer report after the physical opening.
        session_activity_eligible = bool(session_quality.get("timestamp_gate_passed"))
        mem["start_measurement_in_session_gate_passed"] = session_activity_eligible
        # Objective validation now uses the same strict in-session timestamp
        # activity gate. Frame age/skew remains visible for diagnostics, but it
        # can neither bypass nor independently invalidate proven sensor activity.
        validation_end_ah = end_ah if session_activity_eligible else None
        validation_end_temp = t if session_activity_eligible else None
        validation_end_quality = measurement_frame.get("quality")
        validation_end_skew_s = measurement_frame.get("skew_s")
        validation_end_max_age_s = measurement_frame.get("max_age_s")
        # Deliberately no fallback to an older pre-close validation frame here.
        # Without the strict in-session timestamp gate, such a fallback could make
        # a held value look like fresh evidence and contaminate learning/validation.

        source_ah = finite_float(mem.get("session_learning_source_ah"))
        if source_ah is None:
            source_ah = finite_float(mem.get("session_start_source_ah"), 0.0) or 0.0
        if source_ah <= 0 and -30 < ref_t < 60 and 0 <= ref_rh <= 100: source_ah = absolute_humidity(ref_t, ref_rh)
        learning_start_ah = finite_float(mem.get("session_learning_start_ah"))
        if learning_start_ah is None:
            learning_start_ah = finite_float(mem.get("session_start_ah"), 0.0) or 0.0
        live_start_ah = finite_float(mem.get("session_start_ah"), 0.0) or 0.0
        result_base_ml = finite_float(mem.get("session_result_base_ml"), 0.0) or 0.0
        session_removed = result_base_ml + (live_start_ah - end_ah) * float(cfg[CONF_ROOM_VOLUME])
        mem["session_result_ml"] = session_removed
        source_contaminated = bool(mem.get("session_moisture_source_detected"))
        reference_moisture_reversal = bool(mem.get("session_reference_moisture_reversal"))
        cover_session = cover_guard.verdict(mem, float(self.options.get("cover_learning_max_closed_percent", 20.0) or 20.0))
        cover_learning_blocked = bool(cover_session["blocked"])
        mem["session_cover_learning_blocked"] = cover_learning_blocked
        learning_contaminated = source_contaminated or reference_moisture_reversal
        frame_learning_eligible = session_activity_eligible
        return (cover_learning_blocked, cover_session, elapsed, end_ah, frame_learning_eligible, learning_contaminated, learning_start_ah, measurement_elapsed, measurement_frame, measurement_started, now, reference_moisture_reversal, rh, session_activity_eligible, session_quality, session_removed, source_ah, source_contaminated, started, t, validation_end_ah, validation_end_max_age_s, validation_end_quality, validation_end_skew_s, validation_end_temp)

    def _learn_session_exchange(
        self,
        *,
        cfg: Any,
        cover_learning_blocked: Any,
        cover_session: Any,
        end_ah: Any,
        frame_learning_eligible: Any,
        learning_contaminated: Any,
        learning_start_ah: Any,
        measurement_elapsed: Any,
        mem: Any,
        now: Any,
        reference_moisture_reversal: Any,
        session_quality: Any,
        source_ah: Any,
    ) -> Any:
        """Learn the room air-exchange rate (and opening sub-model) from a trustworthy session."""
        if cover_learning_blocked:
            rate = float(mem["learning_rate"]); samples = int(mem["learning_samples"])
            diagnosis = cover_guard.diagnosis(cover_session)
            valid = False
        elif learning_contaminated:
            rate = float(mem["learning_rate"]); samples = int(mem["learning_samples"])
            diagnosis = (
                "Lernmessung übersprungen: Referenzluft wurde während der Lüftung zu feucht"
                if reference_moisture_reversal
                else "Lernmessung übersprungen: aktive interne Feuchtequelle während der Lüftung erkannt"
            )
            valid = False
        elif not frame_learning_eligible:
            rate = float(mem["learning_rate"]); samples = int(mem["learning_samples"])
            diagnosis = f"Lernmessung übersprungen: {session_quality.get('reason') or 'Temperatur und Luftfeuchtigkeit haben während der Lüftung keine ausreichend neuen Zeitstempel geliefert.'}"
            valid = False
        else:
            old_rate = float(mem["learning_rate"])
            rate, samples, diagnosis, valid = update_learning(old_rate=old_rate, old_samples=int(mem["learning_samples"]), elapsed_min=measurement_elapsed, start_ah=learning_start_ah, end_ah=end_ah, source_ah=source_ah, learning_enabled=bool(self.options["learning_enabled"]), max_duration_min=float(self.options.get("learning_max_duration_min", 120)))
            if valid:
                # The session timestamp gate is now the authority for adaptive
                # influence. Legacy frame classes remain diagnostic context only
                # and may never upgrade a 0.75 "good" session to full weight.
                activity_weight = float(session_quality.get("learning_weight", 0.0) or 0.0)
                frame_weight = activity_weight
                rate = old_rate + (float(rate) - old_rate) * frame_weight

                # Maturity uses the same evidence weight as the coefficient update.
                # Keep ``learning_samples`` integer-compatible for the established UI
                # and models, but accumulate fractional evidence until one full sample
                # has genuinely been earned. Four 0.75 sessions therefore count as
                # three maturity samples instead of four.
                old_samples = int(mem.get("learning_samples", 0))
                try:
                    prior_credit = min(max(float(mem.get("learning_sample_credit", 0.0) or 0.0), 0.0), 0.999999)
                except (TypeError, ValueError, OverflowError):
                    prior_credit = 0.0
                evidence_total = prior_credit + max(min(frame_weight, 1.0), 0.0)
                sample_increment = int(evidence_total)
                samples = min(old_samples + sample_increment, 1000)
                mem["learning_sample_credit"] = 0.0 if samples >= 1000 else round(evidence_total - sample_increment, 6)
                # ``update_learning`` reports the unweighted candidate sample
                # number. Rewrite that label so diagnostics cannot claim a full
                # maturity sample when only fractional evidence was credited.
                diagnosis = diagnosis.replace(
                    f"Learned: sample {old_samples + 1}",
                    f"Learned: evidence {samples}+{mem['learning_sample_credit']:.2f}",
                    1,
                )
                if frame_weight < 1.0:
                    diagnosis = f"{diagnosis} · qualitätsgewichtet ({frame_weight:.2f})"
                diagnosis = f"{diagnosis} · Lernreife-Evidenz +{frame_weight:.2f} (Proben {samples}, Rest {mem['learning_sample_credit']:.2f})"
                dates = mem.get("learning_observation_dates")
                if not isinstance(dates, list):
                    dates = []
                day = now.date().isoformat()
                if day not in dates:
                    dates.append(day)
                mem["learning_observation_dates"] = dates[-730:]
        # Legacy contract: session_mode in {"open", "tilted", "cross"} remains supported.
        # Legacy defaults = {"open": 0.03, "tilted": 0.015, "cross": 0.04} remain unchanged.
        # Learn explicit opening strategies independently while preserving the
        # established general coefficient as the compatibility/fallback model.
        session_mode = str(mem.get("session_specialist_opening_mode") or "")
        if valid and not mem.get("session_opening_mode_mixed") and not mem.get("session_learning_quarantined") and session_mode in {"open", "tilted", "cross", "mechanical_exhaust"}:
            opening_learning = mem.get("opening_learning") if isinstance(mem.get("opening_learning"), dict) else {}
            defaults = {"open": 0.03, "tilted": 0.015, "cross": 0.04, "mechanical_exhaust": 0.02}
            row = opening_learning.get(session_mode) if isinstance(opening_learning.get(session_mode), dict) else {}
            old_mode_rate = float(row.get("rate", defaults[session_mode]) or defaults[session_mode])
            old_mode_samples = int(row.get("samples", 0) or 0)
            candidate_rate, _candidate_samples, _mode_diag, mode_valid = update_learning(
                old_rate=old_mode_rate, old_samples=old_mode_samples, elapsed_min=measurement_elapsed,
                start_ah=learning_start_ah, end_ah=end_ah, source_ah=source_ah,
                learning_enabled=bool(self.options["learning_enabled"]),
                max_duration_min=float(self.options.get("learning_max_duration_min", 120)),
            )
            passage_candidate = bool(mode_valid and session_mode == "open" and mem.get("session_passage_door"))
            learned_passage = any(isinstance((mem.get("passage_behavior") or {}).get(c), dict) and (mem.get("passage_behavior") or {}).get(c, {}).get("learned") for c in (mem.get("session_passage_contacts") or []))
            passage_threshold = max(defaults["open"] * (0.40 if learned_passage else 0.25), 0.006)
            passage_weak = bool(passage_candidate and float(candidate_rate) < passage_threshold)
            if passage_candidate:
                behaviour = mem.get("passage_behavior") if isinstance(mem.get("passage_behavior"), dict) else {}
                for contact_id in (mem.get("session_passage_contacts") or []):
                    row_stats = behaviour.get(contact_id) if isinstance(behaviour.get(contact_id), dict) else {}
                    behaviour[contact_id] = update_passage_pattern(row_stats, pulled_shut_evidence=passage_weak)
                mem["passage_behavior"] = behaviour
                learned_rows = [r for r in behaviour.values() if isinstance(r, dict) and r.get("learned")]
                if learned_rows:
                    diagnosis = f"{diagnosis} · wiederkehrendes Durchgangstür-Muster gelernt; Sensorzustand wird nicht überschrieben"
            if passage_weak:
                mem["session_learning_quarantined"] = True
                mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-003"
                diagnosis = f"{diagnosis} · Durchgangstür: Open-Speziallernen wegen unplausibel geringer Lüftungswirkung verworfen"
                mode_valid = False
            if mode_valid:
                weight = max(min(float(session_quality.get("learning_weight", 0.0) or 0.0), 1.0), 0.0)
                new_mode_rate = old_mode_rate + (float(candidate_rate) - old_mode_rate) * weight
                credit = max(min(float(row.get("credit", 0.0) or 0.0), 0.999999), 0.0) + weight
                increment = int(credit)
                opening_learning[session_mode] = {
                    "rate": round(min(max(new_mode_rate, 0.002), 0.25), 6),
                    "samples": min(old_mode_samples + increment, 1000),
                    "credit": 0.0 if old_mode_samples + increment >= 1000 else round(credit - increment, 6),
                }
                mem["opening_learning"] = opening_learning
                diagnosis = f"{diagnosis} · {session_mode}-Modell separat gelernt"
        mem["learning_rate"] = rate; mem["learning_samples"] = samples; mem["diagnosis"] = diagnosis; mem["last_learning_at"] = now.isoformat(); mem["last_learning_valid"] = bool(valid); self.store.data["last_diagnosis"] = f"{cfg['name']}: {diagnosis}"
        return (rate, valid)


    def _cross_ventilation_active(self) -> bool:
        pairs_raw = str(self.options.get("cross_ventilation_pairs", "")).strip()
        if not pairs_raw: return False
        room_by_key = {r["key"]: r for r in self.entry.data.get(CONF_ROOMS, []) if r.get(CONF_ROOM_INCLUDE_CALCULATIONS, True)}
        now = dt_util.now()
        for pair in pairs_raw.split(","):
            keys = [x.strip() for x in pair.split("+") if x.strip()]
            if len(keys) == 2 and all(k in room_by_key for k in keys):
                a,b=(room_by_key[k] for k in keys)
                same_zone = str(a.get(CONF_ROOM_FLOOR,"")) == str(b.get(CONF_ROOM_FLOOR,""))
                links = str(self.options.get("cross_zone_connections", ""))
                explicit = f"{keys[0]}+{keys[1]}" in links or f"{keys[1]}+{keys[0]}" in links
                if same_zone or explicit:
                    # Contact delays gate only the *start* of a room session. If a
                    # running session is reopened after a brief close, cross-flow
                    # must resume immediately as well instead of waiting through
                    # the opening delay a second time.
                    pair_open = True
                    for key in keys:
                        active_session = bool((self.store.data.get("rooms", {}).get(key) or {}).get("session_active"))
                        room_mem = self.store.data.get("rooms", {}).get(key) or {}
                        room_contacts = _contact_ids(room_by_key[key])
                        proven = set(str(x) for x in (room_mem.get("three_state_contacts") or [])) & set(room_contacts)
                        stable = room_mem.get("stable_opening_modes") if isinstance(room_mem.get("stable_opening_modes"), dict) else {}
                        stable_modes = {c: str(stable.get(c, "unknown")) for c in proven}
                        stable_since_raw = room_mem.get("stable_opening_since") if isinstance(room_mem.get("stable_opening_since"), dict) else {}
                        stable_since = {}
                        for c in proven:
                            try:
                                stable_since[c] = datetime.fromisoformat(str(stable_since_raw.get(c)))
                            except (TypeError, ValueError):
                                pass
                        room_open = _room_ventilation_state(
                            self.hass, room_by_key[key], now,
                            honour_delays=not active_session, contact_modes=stable_modes, contact_since=stable_since,
                        )[0]
                        if not room_open:
                            pair_open = False
                            break
                    if pair_open:
                        return True
        return False
