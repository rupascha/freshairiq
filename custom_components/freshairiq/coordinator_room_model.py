"""Per-room physics: room model, recommendation, forecast and the frozen session prediction."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .air_exchange import advance_air_exchange
from .const import (
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_ROOM_CO2,
    CONF_ROOM_MOISTURE_SOURCES,
    CONF_ROOM_NAME,
    CONF_ROOM_REFERENCE_HUMIDITY,
    CONF_ROOM_REFERENCE_TEMPERATURE,
    CONF_ROOM_VOLUME,
)
from .consolidation import session_target_min as _session_target_min
from .coordinator_contacts import _contact_ids, _room_orientation_factor
from .energy import (
    exchanged_air_fraction,
    heating_cost_context,
    ventilation_cost,
    ventilation_cost_for_temperature_path,
)
from .forecast import horizon_forecast
from .goals import room_comfort_target
from .humidity_plateau import track_session
from .forecast_validation import evaluate_start_forecast_at_duration, freeze_start_forecast_context
from .learning_effectiveness import freeze_learning_effectiveness_context
from .model import RoomInput, absolute_humidity, evaluate_room, scaled_min_return
from .moisture_source import update_moisture_source
from .post_stabilization import prune_history as prune_stabilization_history, update_post_close_observation
from .room_recommendation import _recommendation, co2_lead
from .start_model import seed_room, validate as _validate_start_model
from .start_model_data import START_MODEL as _SHIPPED_START_MODEL

START_MODEL = _validate_start_model(_SHIPPED_START_MODEL)


def _remember_airing_kind(mem: dict[str, Any], result: Any, has_ventilation_contact: bool, is_open: Any) -> bool:
    """Hysteresis memory of a closed room; returns whether ``mem`` changed.

    0.26.4.7 (GitHub #15): only a closed room that recommended airing keeps the
    relaxed release thresholds – for humidity only, CO2 has its own hysteresis.
    0.26.5.4 (review A07): whether an airing opened now is asked for CO2 alone.
    """
    changed = False
    latched = bool(result.data_quality == "ok" and result.ventilation_candidate and not result.co2_airing and has_ventilation_contact and not mem["session_active"] and not is_open)
    if bool(mem.get("ventilation_candidate_latched", False)) != latched:
        mem["ventilation_candidate_latched"] = latched
        changed = True
    if not mem["session_active"] and bool(mem.get("co2_airing_last")) != bool(result.co2_airing):
        mem["co2_airing_last"] = bool(result.co2_airing)
        changed = True
    return changed


class RoomModelMixin:
    """Per-room physics: room model, recommendation, forecast and the frozen session prediction."""

    hass: HomeAssistant  # provided by the coordinator

    def _evaluate_room_model(
        self,
        *,
        cfg: Any, changed: Any, co2: Any, cross: Any, disabled_goals: Any, elapsed: Any, future_outdoor: Any,
        is_open: Any, key: Any, measurement_frame: Any, measurements_valid: Any,
        mechanical_exhaust_active: Any, mem: Any, now: Any, opening_mode: Any, options: Any,
        outdoor_pm25: Any, physical_contact_modes: Any, pollen: Any, raw_contact_open: Any,
        raw_open_seconds: Any, ref_rh: Any, ref_t: Any, reference_humidity_entity: Any,
        reference_temperature_entity: Any, rh: Any, specialist_opening_mode: Any, t: Any, wind_bearing: Any,
        wind_speed: Any,
    ) -> Any:
        """Elapsed time, moisture source, post-close observation and the physical room model."""
        if mem["session_active"] and (mem.get("session_physical_started") or mem.get("session_started")):
            try:
                elapsed_start = mem.get("session_physical_started") or mem.get("session_started")
                elapsed_end = now
                if mem.get("session_close_pending") and mem.get("session_close_detected_at"):
                    try:
                        elapsed_end = min(now, datetime.fromisoformat(str(mem.get("session_close_detected_at"))))
                    except (TypeError, ValueError):
                        elapsed_end = now
                elapsed = max(0.0, (elapsed_end - datetime.fromisoformat(str(elapsed_start))).total_seconds() / 60.0)
            except (ValueError, TypeError):
                elapsed = 0.0

        airflow = _room_orientation_factor(self.hass, cfg, now, wind_bearing, wind_speed, bool(options.get("wind_orientation_enabled", True)), contact_modes=physical_contact_modes)
        moisture_source = {"active": False, "recovery": False, "label": "Feuchtequelle", "configured_sources": [], "confidence": 0, "source_rate_ml_min": 0.0, "generated_ml_window": 0.0, "observed_change_ml_window": 0.0, "ventilation_change_ml_window": 0.0, "absolute_humidity_rise_g_m3": 0.0, "temperature_rise_c": 0.0, "window_min": 0.0, "started_at": None, "last_ended_at": None, "changed": False}
        if measurements_valid:
            moisture_source = update_moisture_source(
                mem, now=now,
                absolute_humidity_g_m3=absolute_humidity(t, rh),
                reference_ah_g_m3=absolute_humidity(ref_t, ref_rh),
                temperature_c=t, volume_m3=float(cfg[CONF_ROOM_VOLUME]),
                window_open=bool(is_open),
                learning_rate_per_min=float(mem.get("learning_rate", .03)),
                airflow_factor=airflow, cross_ventilation=cross,
                configured_sources=list(cfg.get(CONF_ROOM_MOISTURE_SOURCES, []) or []),
            )
            changed = changed or bool(moisture_source.get("changed"))
            if moisture_source.get("active") and mem.get("session_active"):
                if not mem.get("session_moisture_source_detected"):
                    mem["session_moisture_source_detected"] = True
                    changed = True

        # v0.20.3.4: observe the first ten minutes after closing to quantify
        # hygroscopic moisture rebound. This remains diagnostic-only: the
        # production forecast and adaptive coefficients are intentionally
        # untouched until enough real observations exist.
        stabilization_outcome, stabilization_changed = update_post_close_observation(
            mem, now=now,
            absolute_humidity_g_m3=(absolute_humidity(t, rh) if measurements_valid else None),
            temperature_c=(t if measurements_valid else None),
            frame_quality=measurement_frame.get("quality"),
            frame_valid=bool(measurement_frame.get("validation_eligible")) and measurements_valid,
            window_open=bool(is_open or mem.get("session_active")),
            moisture_source_active=bool(moisture_source.get("active") or moisture_source.get("recovery")),
        )
        if stabilization_changed:
            changed = True
        if stabilization_outcome is not None:
            history = list(self.store.data.get("post_close_stabilization_history") or [])
            history.append(stabilization_outcome)
            self.store.data["post_close_stabilization_history"] = prune_stabilization_history(history, now, days=30)
            changed = True
        _contact_ref_t = cfg.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
        _contact_ref_h = cfg.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
        active_contact_reference = any(
            physical_contact_modes.get(_cid) in {"open", "tilted"}
            and str(_contact_ref_t.get(_cid) or "").strip()
            and str(_contact_ref_h.get(_cid) or "").strip()
            and str(_contact_ref_t.get(_cid)) == str(reference_temperature_entity)
            and str(_contact_ref_h.get(_cid)) == str(reference_humidity_entity)
            for _cid in _contact_ids(cfg)
        )
        # Rooms without an assigned opening remain full calculated indoor rooms. Their exchange model
        # is learned from conservative passive observations instead of pretending they own another room's contact.
        has_ventilation_contact = bool(_contact_ids(cfg))
        # 0.26.5.4: a room that has not learned yet starts from the shipped start model (empty: built-in values)
        changed = bool(has_ventilation_contact and seed_room(mem, START_MODEL, cfg[CONF_ROOM_VOLUME])) or changed
        effective_learning_rate = float(mem["learning_rate"] if has_ventilation_contact else mem.get("passive_learning_rate", 0.03))
        effective_learning_samples = int(mem["learning_samples"] if has_ventilation_contact else mem.get("passive_learning_samples", 0))
        opening_learning = mem.get("opening_learning") if isinstance(mem.get("opening_learning"), dict) else {}
        opening_model_key = "cross" if cross and opening_mode == "open" else specialist_opening_mode
        opening_model = opening_learning.get(opening_model_key) if opening_model_key and isinstance(opening_learning.get(opening_model_key), dict) else None
        # Open/tilt specialist models require provenance from the currently
        # active proven three-state contacts. Binary/mixed-source ventilation
        # always falls back to the established general model. Cross keeps its
        # independent room-level model.
        if opening_model and int(opening_model.get("samples", 0) or 0) > 0:
            effective_learning_rate = float(opening_model.get("rate", effective_learning_rate))
            effective_learning_samples = int(opening_model.get("samples", effective_learning_samples))
        elif has_ventilation_contact and opening_model_key in ((mem.get("start_model") or {}).get("rates") or {}):  # not learned yet: start model
            effective_learning_rate = float(mem["start_model"]["rates"][opening_model_key])
        if mem.get("session_active") and mem.get("session_target_fan_start") and raw_contact_open:
            joined = _session_target_min(self.data, options)
            mem["session_target_min"] = round(elapsed + joined, 1) if joined is not None else None
            mem["session_target_fan_start"] = False
        room_input = RoomInput(
            key=key, name=cfg[CONF_ROOM_NAME], temperature=t, humidity=rh, reference_temperature=ref_t, reference_humidity=ref_rh,
            volume_m3=float(cfg[CONF_ROOM_VOLUME]), contact_open=is_open, contact_open_seconds=raw_open_seconds,
            learning_rate=effective_learning_rate, learning_samples=effective_learning_samples, co2=co2,
            cooling_allowed="temperature" not in disabled_goals, comfort_target_c=room_comfort_target(cfg, mem)[0] if "temperature" not in disabled_goals else None,
            surface_reference_temperature=self.__dict__.get("_wall_reference_t", {}).get(str(key)), co2_lead_latched=bool(mem.get("co2_lead_latched")), session_co2_only=bool(mem["session_active"] and mem.get("session_co2_only")),
            co2_sensor_missing=bool(cfg.get(CONF_ROOM_CO2)) and co2 is None and "co2" not in disabled_goals,
            humidity_plateau=track_session(mem, session_active=bool(mem["session_active"]), elapsed_min=elapsed, temp_c=t, rh=rh, reports=int(mem.get("session_humidity_reports", 0))),
            session_active=bool(mem["session_active"]), session_elapsed_min=elapsed, session_start_ah=mem.get("session_start_ah"),
            session_start_temp=mem.get("session_start_temp"), session_result_base_ml=float(mem.get("session_result_base_ml", 0.0)),
            session_result_ml=float(mem.get("session_result_ml", 0.0)), close_notified=bool(mem.get("close_notified", False)),
            airflow_factor=airflow, pollen_index=pollen,
            session_fresh_measurements=int(mem.get("session_fresh_measurements", 0)),
            session_target_min=mem.get("session_target_min") if mem.get("session_active") else None,
            mechanical_only=bool(mechanical_exhaust_active and not raw_contact_open),
            future_reference_temperature_15=(
                float(future_outdoor[15]["temperature_c"])
                if 15 in future_outdoor
                and not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
                and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
                and not active_contact_reference
                else None
            ),
            future_reference_humidity_15=(
                float(future_outdoor[15]["humidity"])
                if 15 in future_outdoor
                and not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
                and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
                and not active_contact_reference
                else None
            ),
            moisture_source_active=bool(moisture_source.get("active")),
            moisture_source_recovery=bool(moisture_source.get("recovery")),
            moisture_source_label=str(moisture_source.get("label") or "Feuchtequelle"),
            moisture_source_confidence=int(moisture_source.get("confidence") or 0),
            moisture_source_rate_ml_min=float(moisture_source.get("source_rate_ml_min") or 0.0),
            ventilation_latched=bool(mem.get("ventilation_candidate_latched", False)),
            outdoor_pm25=outdoor_pm25,
        )
        result = evaluate_room(room_input, options, cross)
        self.__dict__.setdefault("_air_exchange", {})[key] = advance_air_exchange(  # 0.26.5.4: display only
            mem, active=bool(mem["session_active"] and is_open), elapsed_min=elapsed, now=now, rate_per_min=room_input.learning_rate,
            factor=(1.25 if cross else 1.0) * min(max(float(airflow), 0.5), 1.5), learned=room_input.learning_samples >= 3)
        changed = _remember_airing_kind(mem, result, has_ventilation_contact, is_open) or changed

        return (
            active_contact_reference, airflow, changed, effective_learning_rate, elapsed,
            has_ventilation_contact, moisture_source, result, room_input,
        )

    def _room_recommendation_state(
        self,
        *,
        airflow: Any, cfg: Any, changed: Any, co2: Any, cross: Any, explicit_tilted: Any,
        has_ventilation_contact: Any, is_open: Any, mem: Any, now: Any, options: Any, outdoor_pm25: Any,
        pollen: Any, ref_t: Any, result: Any, room_input: Any, t: Any, wind_bearing: Any, wind_speed: Any,
    ) -> Any:
        """Humidity trend, room recommendation and the close-notification latch."""
        # Recommendation Engine v2 and the live forecast both use
        # persistence and trend. Forecast learning is based on absolute
        # humidity (g/m³), not RH alone, so temperature-driven RH changes
        # are not mistaken for water entering/leaving the room.
        humidity_trend = float(mem.get("humidity_trend_pct_h", 0.0) or 0.0)
        high_since = mem.get("humidity_high_since")
        if result.data_quality == "ok":
            start_rh = float(options.get("start_rh", 62.0))
            if float(result.humidity or 0.0) >= start_rh:
                if not high_since:
                    mem["humidity_high_since"] = now.isoformat(); high_since = mem["humidity_high_since"]; changed = True
            elif high_since:
                mem["humidity_high_since"] = None; high_since = None; changed = True

            prev_at = mem.get("forecast_observation_at")
            prev_ah = mem.get("forecast_observation_ah")
            prev_temp = mem.get("forecast_observation_temp")
            prev_ref_ah = mem.get("forecast_observation_ref_ah")
            prev_open = bool(mem.get("forecast_observation_open"))
            update_observation = prev_at is None or prev_ah is None
            if prev_at is not None and prev_ah is not None:
                try:
                    age_min = (now - datetime.fromisoformat(prev_at)).total_seconds() / 60.0
                    if 5.0 <= age_min <= 30.0:
                        curr_ah = float(result.absolute_humidity or 0.0)
                        legacy_prev_rh = mem.get("humidity_observation_rh")
                        if legacy_prev_rh is not None:
                            raw_trend = (float(result.humidity) - float(legacy_prev_rh)) / max(age_min / 60.0, 1/60)
                            humidity_trend = max(min(raw_trend, 20.0), -20.0)
                            mem["humidity_trend_pct_h"] = round(humidity_trend, 2)

                        volume = max(float(cfg[CONF_ROOM_VOLUME]), 0.0)
                        observed_ml_min = (curr_ah - float(prev_ah)) * volume / max(age_min, 1.0)
                        observed_temp_min = 0.0 if prev_temp is None else (t - float(prev_temp)) / max(age_min, 1.0)
                        residual_ml_min = observed_ml_min
                        residual_temp_min = observed_temp_min
                        if prev_open and mem.get("session_active"):
                            # Recent *measured* net removal rate. Positive = moisture
                            # actually left the room.  The running forecast blends this
                            # cautiously with the physical model so a stalled 60-minute
                            # session cannot keep promising the same theoretical removal.
                            mem["forecast_recent_removed_ml_min"] = round(-observed_ml_min, 4)
                            mem["forecast_recent_observed_at"] = now.isoformat()
                            curr_ref_ah = float(result.reference_humidity or 0.0)
                            avg_ref_ah = (float(prev_ref_ah) + curr_ref_ah) / 2.0 if prev_ref_ah is not None else curr_ref_ah
                            avg_room_ah = (float(prev_ah) + curr_ah) / 2.0
                            interval_fraction = exchanged_air_fraction(
                                float(mem.get("learning_rate", .03)), age_min,
                                (1.25 if cross else 1.0) * airflow,
                            )
                            physical_removed = (avg_room_ah - avg_ref_ah) * volume * interval_fraction
                            residual_ml_min = observed_ml_min + physical_removed / max(age_min, 1.0)
                            if prev_temp is not None:
                                avg_room_temp = (float(prev_temp) + t) / 2.0
                                physical_dt = (ref_t - avg_room_temp) * interval_fraction
                                residual_temp_min = observed_temp_min - physical_dt / max(age_min, 1.0)

                        residual_bound = max(8.0, volume * 0.25)
                        residual_ml_min = min(max(residual_ml_min, -residual_bound), residual_bound)
                        old_source = mem.get("forecast_source_ml_min")
                        alpha = 0.35 if mem.get("session_active") else 0.22
                        mem["forecast_source_ml_min"] = round(
                            residual_ml_min if old_source is None else float(old_source) * (1-alpha) + residual_ml_min * alpha, 4
                        )
                        residual_temp_min = min(max(residual_temp_min, -0.20), 0.20)
                        old_thermal = mem.get("forecast_thermal_residual_c_min")
                        mem["forecast_thermal_residual_c_min"] = round(
                            residual_temp_min if old_thermal is None else float(old_thermal) * (1-alpha) + residual_temp_min * alpha, 5
                        )
                        mem["forecast_observation_samples"] = min(int(mem.get("forecast_observation_samples", 0)) + 1, 1000)
                        update_observation = True
                    elif age_min > 30.0:
                        update_observation = True
                except (TypeError, ValueError):
                    update_observation = True
            if update_observation:
                mem["forecast_observation_at"] = now.isoformat()
                mem["forecast_observation_ah"] = float(result.absolute_humidity or 0.0)
                mem["forecast_observation_temp"] = float(t)
                mem["forecast_observation_ref_ah"] = float(result.reference_humidity or 0.0)
                mem["forecast_observation_open"] = bool(is_open)
                mem["humidity_observation_at"] = now.isoformat()
                mem["humidity_observation_rh"] = float(result.humidity)
                changed = True

        high_duration = 0.0
        if high_since:
            try:
                high_duration = max(0.0, (now - datetime.fromisoformat(high_since)).total_seconds() / 60.0)
            except (TypeError, ValueError):
                high_duration = 0.0

        mem["last_measurement_at"] = now.isoformat()
        mem["last_measurement_valid"] = result.data_quality == "ok"
        # audit S04: a sensor without a value keeps the hold band – only a valid reading below it ends it
        co2_latched = bool(mem.get("co2_lead_latched")) if room_input.co2_sensor_missing else co2_lead(co2, options, bool(mem.get("co2_lead_latched")))
        if bool(mem.get("co2_lead_latched")) != co2_latched:
            mem["co2_lead_latched"] = co2_latched; changed = True
        action, reason, reason_list = _recommendation(result, options, pollen=pollen, co2=co2, airflow=airflow, wind_bearing=wind_bearing, wind_speed=wind_speed, outdoor_pm25=outdoor_pm25, ventilation_latched=bool(room_input.ventilation_latched), co2_latched=co2_latched)
        if explicit_tilted and action not in {"Close", "Check sensor"}:
            # A tilted three-state session is a valid, separately learned
            # ventilation mode. Do not silently upgrade a user's deliberate
            # tilt choice to fully-open after the session has started.
            reason_list.append("Drei-Zustands-Sensor meldet Kipplüftung; die gewählte Lüftungsart wird mit dem separaten Kippmodell bewertet")
        indirect_candidate = bool(not has_ventilation_contact and result.ventilation_candidate)
        indirect_cooling_candidate = bool(not has_ventilation_contact and result.cooling_candidate)
        if not has_ventilation_contact and action in {"Ventilate", "Ventilate for cooling"}:
            # Keep the climate warning/potential, but do not invent an opening
            # or make this room directly actionable at house level.
            action = "Ventilate indirectly"
            reason = "No opening is assigned to this room; ventilate it via a connected room"
            reason_list.append("No opening is assigned; FreshAirIQ continues monitoring this room and can learn measurable passive ventilation")
            result.ventilation_candidate = False
            result.cooling_candidate = False
        result.action = action; result.reason = reason
        if action == "Continue ventilating" and result.moisture_source_active:
            # 0.26.5.2: a room kept open for its running moisture source sends
            # no room-level close either (also with a close threshold below 0.4)
            result.close_recommended = False
        if mem["session_active"] and result.data_quality == "ok":
            if abs(float(mem.get("session_result_ml", 0.0)) - float(result.result_ml)) >= 0.01:
                mem["session_result_ml"] = float(result.result_ml); changed = True
        if mem["session_active"] and bool(mem.get("close_notified", False)) != bool(result.close_recommended):
            # 0.26.5.1: remember a published close for the rest of the session
            # (released again by the model only with a clear margin).
            mem["close_notified"] = bool(result.close_recommended); changed = True
        return (
            changed, high_duration, humidity_trend, indirect_candidate, indirect_cooling_candidate,
            reason_list,
        )

    def _room_forecast(
        self,
        *,
        _learning_v2_force_physics: Any, active_contact_reference: Any, airflow: Any, calc_volume_total: Any,
        cfg: Any, cross: Any, daily_generation_prior: Any, effective_learning_rate: Any, elapsed: Any,
        forecast_horizon: Any, forecast_outdoor_steps: Any, is_open: Any, measurement_frame: Any, mem: Any,
        moisture_source: Any, now: Any, opening_mode: Any, options: Any, ref_t: Any, result: Any, t: Any,
    ) -> Any:
        """Cost of the next five minutes and the dynamic room forecast."""
        # Bound for the caller; it is only read under the same data-quality guard that sets it.
        target_ah = None
        fraction = exchanged_air_fraction(float(effective_learning_rate), 5, (1.25 if cross and opening_mode == "open" else 1.0) * airflow)
        delivered, purchased, cost = ventilation_cost(float(cfg[CONF_ROOM_VOLUME]), t, ref_t, fraction, options) if -30 < ref_t < 60 and -10 < t < 50 else (0, 0, 0)
        # Reheating cost is only meaningful when the next ventilation step
        # is expected to cool the room. Warming by outdoor air is not billed
        # as a reheating loss.
        if result.temp_next_5_min_c >= 0 or result.action == "Ventilate for cooling":
            purchased = 0.0; cost = 0.0
        start_temp = mem.get("session_start_temp")
        temp_change = round(t - float(start_temp), 1) if mem["session_active"] and start_temp is not None else 0.0
        fuel = heating_cost_context(delivered, options)

        room_prior_ml_min = 0.0
        if calc_volume_total > 0:
            room_prior_ml_min = (daily_generation_prior / 1440.0) * (float(cfg[CONF_ROOM_VOLUME]) / calc_volume_total)
        learned_source_for_forecast = mem.get("forecast_source_ml_min")
        if moisture_source.get("active"):
            detected_rate = max(float(moisture_source.get("source_rate_ml_min") or 0.0), 0.0)
            learned_source_for_forecast = max(float(learned_source_for_forecast or 0.0), detected_rate)
        recent_removed_rate = mem.get("forecast_recent_removed_ml_min")
        recent_removed_at = mem.get("forecast_recent_observed_at")
        if recent_removed_rate is not None and recent_removed_at:
            try:
                if (now - datetime.fromisoformat(str(recent_removed_at))).total_seconds() > 30 * 60:
                    recent_removed_rate = None
            except (TypeError, ValueError):
                recent_removed_rate = None
        forecast_model_maturity = min(
            95.0,
            55.0
            + min(int(mem.get("learning_samples", 0)), 10) * 2.0
            + min(int(mem.get("outcome_feedback_samples", 0)), 10) * 2.0
            + min(int(mem.get("forecast_observation_samples", 0)), 6) * 1.0,
        )
        forecast_args = dict(
            current_ah=float(result.absolute_humidity or 0.0),
            source_ah=float(result.reference_humidity or 0.0),
            current_temp_c=t, source_temp_c=ref_t,
            volume_m3=float(cfg[CONF_ROOM_VOLUME]),
            rate_per_min=(0.03 if _learning_v2_force_physics else float(mem.get("learning_rate", .03))),
            airflow_bonus=(1.25 if cross else 1.0) * airflow,
            prior_source_ml_min=room_prior_ml_min,
            learned_source_ml_min=(None if _learning_v2_force_physics else learned_source_for_forecast),
            learned_thermal_residual_c_min=(None if _learning_v2_force_physics else mem.get("forecast_thermal_residual_c_min")),
            observation_samples=(0 if _learning_v2_force_physics else int(mem.get("forecast_observation_samples", 0))),
            model_maturity_pct=forecast_model_maturity,
            measurement_frame_quality=str(measurement_frame.get("quality") or "stale"),
            running=bool(mem.get("session_active") and is_open),
            session_elapsed_min=elapsed,
            session_fresh_measurements=int(mem.get("session_fresh_measurements", 0)),
            recent_observed_removed_ml_min=recent_removed_rate,
            future_source_boundaries=(
                forecast_outdoor_steps
                if not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
                and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
                and not active_contact_reference
                else None
            ),
        )
        if result.data_quality == "ok":
            # Hotfix 0.17.0.2: the freely selectable long-horizon card is a
            # decision forecast, not a promise to keep drying indefinitely.
            # Cap only horizons >5 min at the configured room humidity target.
            # The internal 5-minute control forecast remains uncapped by the
            # comfort target, but during a mature running session it may be
            # corrected by the recent measured removal rate.  That prevents
            # the live coach from extending a session after real drying stalls.
            target_ah = absolute_humidity(t, float(options.get("target_rh", 58.0)))
            dynamic = horizon_forecast(
                horizon_min=forecast_horizon,
                target_ah=target_ah,
                cap_positive_to_target=forecast_horizon > 5,
                min_return_next_5_min_ml=scaled_min_return(options.get("min_return_next_5_min_ml", 25.0), cfg[CONF_ROOM_VOLUME]),
                max_temp_loss_next_5_min_c=float(options.get("max_temp_loss_next_5_min_c", 0.6)),
                min_efficiency_ml_per_01c=float(options.get("min_efficiency_ml_per_01c", 8.0)),
                min_duration_min=float(options.get("min_duration_min", 3.0)),
                max_duration_min=float(options.get("max_duration_min", 20.0)),
                operating_profile=str(options.get("operating_profile", "comfort")),
                **forecast_args,
            )
            dynamic5 = horizon_forecast(horizon_min=5, **forecast_args)
        else:
            dynamic = {
                "horizon_min": forecast_horizon, "moisture_effect_ml": 0,
                "physical_moisture_effect_ml": 0, "internal_moisture_effect_ml": 0,
                "net_moisture_change_ml": 0, "temperature_change_c": 0.0,
                "exchange_fraction": 0.0, "confidence": 0,
                "source_rate_ml_min": 0.0, "method": "unavailable",
            }
            dynamic5 = dict(dynamic, horizon_min=5)
        if result.data_quality == "ok":
            # horizon_forecast always returns at least one temperature step.
            fdel, fpurchased, fcost = ventilation_cost_for_temperature_path(
                float(cfg[CONF_ROOM_VOLUME]), float(mem.get("learning_rate", .03)),
                (1.25 if cross else 1.0) * airflow, dynamic["temperature_path"], options,
            )
        else:
            fdel, fpurchased, fcost = (0.0, 0.0, 0.0)
        if float(dynamic.get("temperature_change_c", 0.0)) >= 0 or result.action == "Ventilate for cooling":
            fdel = 0.0; fpurchased = 0.0; fcost = 0.0
        ffuel = heating_cost_context(fdel, options)

        return (
            cost, delivered, dynamic, dynamic5, fcost, fdel, ffuel, forecast_args, fpurchased, fuel,
            purchased, target_ah, temp_change,
        )

    def _freeze_session_prediction(
        self,
        *,
        cfg: Any, changed: Any, dynamic: Any, elapsed: Any, forecast_args: Any, forecast_horizon: Any,
        measurement_frame: Any, mem: Any, now: Any, options: Any, ref_rh: Any, ref_t: Any, result: Any,
        rh: Any, t: Any,
    ) -> Any:
        """Freeze the first forecast after the physical opening as the session prediction."""
        if (
            mem.get("session_active")
            and mem.get("session_prediction_snapshot_pending")
            and mem.get("session_validation_started")
            and result.data_quality == "ok"
        ):
            # Hotfix 0.24.14.1: freeze the complete START model immediately
            # from the numeric opening baseline. Whether that baseline is
            # allowed into objective scoring is decided only after the session
            # from real post-open sensor activity, so sleeping battery sensors
            # no longer lose their start forecast merely because last_reported
            # was old at the exact opening instant.
            try:
                measurement_started = datetime.fromisoformat(str(mem.get("session_validation_started")))
                measurement_elapsed_now = max(0.0, (now - measurement_started).total_seconds() / 60.0)
            except (TypeError, ValueError):
                measurement_elapsed_now = 0.0

            if measurement_elapsed_now <= 2.5:
                recommended_total_horizon = mem.get("session_recommended_duration_min")
                if recommended_total_horizon is not None:
                    # Recommendation duration is counted from physical opening.
                    # The frozen model starts at the confirmed measurement
                    # baseline, so predict only the still remaining part.
                    initial_horizon = max(float(recommended_total_horizon) - elapsed, 1.0)
                elif dynamic.get("optimal_close_in_min") is not None:
                    initial_horizon = max(float(dynamic.get("optimal_close_in_min")), 1.0)
                else:
                    initial_horizon = max(float(forecast_horizon), 1.0)
                initial_horizon = min(initial_horizon, 120.0)

                start_ah = float(mem.get("session_validation_start_ah") or absolute_humidity(t, rh))
                start_source_ah = float(mem.get("session_validation_start_source_ah") or absolute_humidity(ref_t, ref_rh))
                start_temp = float(mem.get("session_validation_start_temp") if mem.get("session_validation_start_temp") is not None else t)
                start_source_temp = float(mem.get("session_validation_start_source_temp") if mem.get("session_validation_start_source_temp") is not None else ref_t)
                start_target_ah = absolute_humidity(start_temp, float(options.get("target_rh", 58.0)))
                start_context = freeze_start_forecast_context(
                    forecast_args,
                    target_ah=start_target_ah,
                    options=options,
                    start_ah=start_ah,
                    start_source_ah=start_source_ah,
                    start_temp_c=start_temp,
                    start_source_temp_c=start_source_temp,
                )
                effectiveness_context = freeze_learning_effectiveness_context(
                    start_context,
                    mem,
                    history=self.store.data.get("forecast_validation_history") or [],
                    room_key=cfg.get("key"),
                )
                if effectiveness_context is not None:
                    start_context["learning_effectiveness"] = effectiveness_context
                start_prediction = evaluate_start_forecast_at_duration(start_context, initial_horizon)
                if start_prediction is not None:
                    mem["session_prediction_start_context"] = start_context
                    mem["session_predicted_removed_ml"] = start_prediction["predicted_removed_ml"]
                    mem["session_predicted_temperature_change_c"] = start_prediction["predicted_temperature_change_c"]
                    mem["session_predicted_cost"] = start_prediction["predicted_cost"]
                    mem["session_prediction_confidence"] = start_prediction["confidence"]
                    mem["session_prediction_snapshot_at"] = now.isoformat()
                    mem["session_prediction_horizon_min"] = initial_horizon
                    mem["session_prediction_snapshot_elapsed_min"] = round(measurement_elapsed_now, 3)
                    mem["session_prediction_snapshot_valid"] = True
                    mem["session_prediction_time_aligned"] = False
                    mem["session_prediction_reference"] = "session_start_curve_v2"
                    mem["session_prediction_snapshot_frame_quality"] = measurement_frame.get("quality")
                    mem["session_prediction_snapshot_frame_skew_s"] = measurement_frame.get("skew_s")
                    mem["session_prediction_snapshot_frame_max_age_s"] = measurement_frame.get("max_age_s")
                else:
                    mem["session_prediction_snapshot_valid"] = False
                    mem["session_prediction_reference"] = "start_snapshot_invalid"
            else:
                # This mainly covers restored/reloaded sessions for which the
                # integration was not running at the real logical start.
                mem["session_prediction_snapshot_valid"] = False
                mem["session_prediction_reference"] = "start_snapshot_missed"
            mem["session_prediction_snapshot_pending"] = False
            changed = True
        return (changed,)

    def _room_session_forecast_timeline(
        self,
        *,
        cfg: Any, changed: Any, dynamic: Any, dynamic5: Any, elapsed: Any, forecast_args: Any, key: Any,
        measurement_frame: Any, mem: Any, now: Any, options: Any, result: Any, rh: Any, t: Any,
        target_ah: Any,
    ) -> Any:
        """Session forecast timeline checkpoints and room history points."""
        # Validation Engine v2: keep a time-resolved forecast trajectory for
        # the active session. Every point predicts the FINAL state at the
        # original frozen start horizon, using only information available at
        # that checkpoint. This is intentionally diagnostic-only.
        if (
            mem.get("session_active")
            and result.data_quality == "ok"
            and mem.get("session_prediction_snapshot_valid")
            and mem.get("session_prediction_horizon_min") is not None
        ):
            timeline = list(mem.get("session_forecast_timeline") or [])
            start_ah = float(mem.get("session_start_ah") or 0.0)
            current_ah = absolute_humidity(t, rh)
            actual_so_far = float(mem.get("session_result_base_ml", 0.0)) + (start_ah - current_ah) * float(cfg[CONF_ROOM_VOLUME])
            temp_start = float(mem.get("session_start_temp") if mem.get("session_start_temp") is not None else t)
            actual_temp_delta = t - temp_start
            target_horizon = max(float(mem.get("session_prediction_horizon_min") or 0.0), 1.0)

            # Ensure the immutable start point exists exactly once.
            if not any(str(point.get("kind")) == "start" for point in timeline if isinstance(point, dict)):
                timeline.append({
                    "kind": "start",
                    "checkpoint_min": 0.0,
                    "captured_at": mem.get("session_prediction_snapshot_at") or now.isoformat(),
                    "elapsed_min": round(elapsed, 3),
                    "timing_error_min": round(elapsed, 3),
                    "actual_removed_ml": round(actual_so_far, 1),
                    "actual_temperature_change_c": round(actual_temp_delta, 2),
                    "predicted_final_removed_ml": round(float(mem.get("session_predicted_removed_ml") or 0.0), 1),
                    "predicted_final_temperature_change_c": round(float(mem.get("session_predicted_temperature_change_c") or 0.0), 2),
                    "remaining_horizon_min": round(max(target_horizon - elapsed, 0.0), 2),
                    "next_5_min_net_moisture_change_ml": round(float(dynamic5.get("net_moisture_change_ml", dynamic5.get("moisture_effect_ml", 0.0)) or 0.0), 1),
                    "next_5_min_temperature_change_c": round(float(dynamic5.get("temperature_change_c", 0.0) or 0.0), 2),
                    "confidence": int(mem.get("session_prediction_confidence") or 0),
                    "method": str(dynamic.get("method") or "unknown"),
                    "measurement_frame_quality": mem.get("session_prediction_snapshot_frame_quality"),
                    "measurement_frame_skew_s": mem.get("session_prediction_snapshot_frame_skew_s"),
                    "measurement_frame_max_age_s": mem.get("session_prediction_snapshot_frame_max_age_s"),
                })
                mem["session_timeline_last_checkpoint_min"] = 0.0
                changed = True

            checkpoint = int(elapsed // 5.0) * 5
            last_checkpoint = float(mem.get("session_timeline_last_checkpoint_min") or 0.0)
            if checkpoint >= 5 and checkpoint > last_checkpoint and elapsed <= target_horizon + 3.0:
                remaining = max(target_horizon - elapsed, 0.0)
                if remaining > 0.25:
                    live_to_end = horizon_forecast(
                        horizon_min=remaining,
                        target_ah=target_ah,
                        cap_positive_to_target=remaining > 5,
                        min_return_next_5_min_ml=scaled_min_return(options.get("min_return_next_5_min_ml", 25.0), cfg[CONF_ROOM_VOLUME]),
                        max_temp_loss_next_5_min_c=float(options.get("max_temp_loss_next_5_min_c", 0.6)),
                        min_efficiency_ml_per_01c=float(options.get("min_efficiency_ml_per_01c", 8.0)),
                        min_duration_min=float(options.get("min_duration_min", 3.0)),
                        max_duration_min=float(options.get("max_duration_min", 20.0)),
                        operating_profile=str(options.get("operating_profile", "comfort")),
                        **forecast_args,
                    )
                    predicted_final_removed = actual_so_far + float(live_to_end.get("net_moisture_change_ml", 0.0) or 0.0)
                    predicted_final_temp = actual_temp_delta + float(live_to_end.get("temperature_change_c", 0.0) or 0.0)
                else:
                    predicted_final_removed = actual_so_far
                    predicted_final_temp = actual_temp_delta
                    live_to_end = {"confidence": dynamic.get("confidence", 0), "method": "horizon_reached"}
                timeline.append({
                    "kind": "live",
                    "checkpoint_min": float(checkpoint),
                    "captured_at": now.isoformat(),
                    "elapsed_min": round(elapsed, 3),
                    "timing_error_min": round(elapsed - float(checkpoint), 3),
                    "actual_removed_ml": round(actual_so_far, 1),
                    "actual_temperature_change_c": round(actual_temp_delta, 2),
                    "predicted_final_removed_ml": round(predicted_final_removed, 1),
                    "predicted_final_temperature_change_c": round(predicted_final_temp, 2),
                    "remaining_horizon_min": round(remaining, 2),
                    "next_5_min_net_moisture_change_ml": round(float(dynamic5.get("net_moisture_change_ml", dynamic5.get("moisture_effect_ml", 0.0)) or 0.0), 1),
                    "next_5_min_temperature_change_c": round(float(dynamic5.get("temperature_change_c", 0.0) or 0.0), 2),
                    "confidence": int(live_to_end.get("confidence", 0) or 0),
                    "method": str(live_to_end.get("method") or "unknown"),
                    "measurement_frame_quality": measurement_frame.get("quality"),
                    "measurement_frame_skew_s": measurement_frame.get("skew_s"),
                    "measurement_frame_max_age_s": measurement_frame.get("max_age_s"),
                })
                mem["session_forecast_timeline"] = timeline[-32:]
                mem["session_timeline_last_checkpoint_min"] = float(checkpoint)
                changed = True
            elif timeline != list(mem.get("session_forecast_timeline") or []):
                mem["session_forecast_timeline"] = timeline[-32:]

        if result.data_quality == "ok":
            if self.store.record_room_temperature_point(key, now.replace(tzinfo=None), t, days=30): changed = True
            if self.store.record_room_humidity_point(key, now.replace(tzinfo=None), rh, days=30): changed = True
        return (changed,)
