"""Per-room result: repeat cooldown, goals and the published room payload."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_FLOOR,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_ICON,
    CONF_ROOM_MOISTURE_SOURCES,
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_TARGET_TEMPERATURE,
    CONF_ROOM_TARGET_TEMPERATURE_FALLBACK,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_THRESHOLD_ML,
    CONF_ROOM_THRESHOLD_MODE,
    CONF_ROOM_THRESHOLD_PERCENT,
    CONF_ROOM_VOLUME,
    CONF_ROOM_WINDOW_ORIENTATION,
    CONTACT_MODE_ANY,
    FLOOR_GROUND,
    ORIENTATION_UNKNOWN,
    ROOM_THRESHOLD_AUTOMATIC,
    ROOM_THRESHOLD_FIXED,
    ROOM_THRESHOLD_PERCENT,
)
from .coordinator_contacts import _contact_ids, _opening_assessments
from .goals import evaluate_goals, room_comfort_target
from .humidity_plateau import equilibrium_rh
from .measurement_frame import session_measurement_quality
from .outdoor_air import outdoor_pm25_blocked
from .repeat_cooldown import remember_close_surface_rh, repeat_cooldown_urgent
from .robustness import finite_float
from .routines import expected_source_rate, learn_source_pattern, response_pattern, routine_maturity
from .seasonality import learn_seasonal_source, seasonal_context
from .strategy import strategy_maturity


class RoomResultMixin:
    """Per-room result: repeat cooldown, goals and the published room payload."""

    hass: HomeAssistant  # provided by the coordinator

    def _room_cooldown_and_goals(
        self,
        *,
        cfg: Any, changed: Any, co2: Any, co2_available: Any, default_ref_rh: Any, default_ref_t: Any,
        default_reference_humidity_entity: Any, default_reference_temperature_entity: Any,
        disabled_goals: Any, include: Any, is_open: Any, mem: Any, moisture_source: Any, now: Any,
        options: Any, outdoor_pm25: Any, physical_contact_modes: Any, pollen: Any, reason_list: Any,
        ref_t: Any, result: Any, rh: Any, t: Any, wind_bearing: Any, wind_speed: Any,
    ) -> Any:
        """Repeat-ventilation cooldown, routines, opening assessments, comfort target and goals."""
        minutes_since_vent = None
        if mem.get("last_ventilation_ended_at"):
            try: minutes_since_vent = max(0.0, (now-datetime.fromisoformat(mem["last_ventilation_ended_at"])).total_seconds()/60.0)
            except (TypeError, ValueError): minutes_since_vent = None
        stabilization_min = float(options.get("post_ventilation_stabilization_min", 4.0))
        repeat_cooldown = float(options.get("repeat_recommendation_cooldown_min", 120.0))
        stabilization = minutes_since_vent is not None and minutes_since_vent < stabilization_min
        last_ref_ah = mem.get("last_ventilation_reference_ah")
        current_ref_ah = float(result.reference_humidity or 0.0)
        weather_improved = False
        if last_ref_ah is not None:
            # A tiny weather fluctuation must not immediately re-arm a room.
            # Require a materially drier reference than at the previous close.
            weather_improved = current_ref_ah <= float(last_ref_ah) - max(float(options.get("repeat_weather_improvement_g_m3", 1.0)), 1.5)
        # 0.26.5.3 (GitHub #15): a chronically humid room sits above the mould
        # warning all the time, so "surface RH >= warning" lifted the repeat
        # cooldown permanently and the room was asked to air every 20 minutes.
        # Only the critical level or a clear rise since the last close lift it now.
        changed |= remember_close_surface_rh(mem, float(result.surface_rh or 0.0))
        urgent_override = repeat_cooldown_urgent(
            surface_rh=float(result.surface_rh or 0.0), surface_rh_at_close=mem.get("repeat_surface_rh_at_close"),
            co2=co2, options=options,
        )
        repeat_min_benefit = float(options.get("repeat_min_benefit_ml", 80.0))
        last_end_rh = finite_float(mem.get("last_ventilation_end_humidity"))
        humidity_rebound = None if last_end_rh is None else float(rh) - float(last_end_rh)
        strong_new_source = bool(
            (moisture_source.get("active") or moisture_source.get("recovery"))
            and float(moisture_source.get("confidence", 0.0) or 0.0) >= 90.0
            and float(result.potential_ml or 0.0) >= max(repeat_min_benefit * 1.5, 150.0)
            and (humidity_rebound is None or humidity_rebound >= 3.0)
        )
        # Prevent a credibility-breaking recommendation reversal directly
        # after closing. A changed reference path (e.g. Wintergarten ->
        # outside) may look like better weather, but may only bypass the
        # normal repeat cooldown after this anti-flap floor. Real urgency or
        # a strong new moisture source can still override immediately.
        anti_flap_min = max(stabilization_min, min(15.0, repeat_cooldown))
        weather_override_allowed = bool(
            weather_improved and minutes_since_vent is not None and minutes_since_vent >= anti_flap_min
        )
        cooldown_override = bool(strong_new_source or weather_override_allowed or urgent_override)
        stabilizing = stabilization
        recently_ventilated = minutes_since_vent is not None and minutes_since_vent < repeat_cooldown and not cooldown_override
        cooldown_demoted = bool(recently_ventilated and result.action == "Ventilate" and not is_open and not mem["session_active"])
        if cooldown_demoted:
            # 0.26.4.7 (GitHub #15): the house recommendation already skipped
            # rooms inside the repeat cooldown, but the room's own action (sensor,
            # dashboard tile, push, automation event) still said "Ventilate" a
            # few minutes after "Close". The room now shows the same decision.
            # Urgent air quality, a strong new moisture source or clearly better
            # weather still re-arm the room immediately (cooldown_override).
            result.action = "Wait"
            reason_list.append(
                f"Vor {max(round(minutes_since_vent), 1)} min gelüftet: eine erneute Lüftungsempfehlung folgt erst nach "
                f"der Wiederholungssperre von {round(repeat_cooldown)} min, außer bei kritischer Luftqualität, einer starken neuen Feuchtequelle oder deutlich trockenerer Außenluft"
            )
            result.reason = "; ".join(reason_list)
        if (
            include and result.data_quality == "ok" and not is_open and not mem.get("session_active")
            and not moisture_source.get("active") and not moisture_source.get("recovery")
            and not stabilizing and mem.get("forecast_source_ml_min") is not None
        ):
            source_value = float(mem.get("forecast_source_ml_min") or 0.0)
            if learn_source_pattern(mem, now, source_value):
                learn_seasonal_source(mem, now, source_value)
                changed = True
        routine_rate, routine_samples = expected_source_rate(mem, now)
        routine_response = response_pattern(mem, now)
        season_ctx = seasonal_context(mem, now)
        seasonal_routine_rate = (
            float(routine_rate) * float(season_ctx.get("factor", 1.0))
            if routine_rate is not None else None
        )
        opening_assessments = _opening_assessments(
            self.hass, cfg,
            room_temperature=float(t), room_humidity=float(rh), volume_m3=float(cfg[CONF_ROOM_VOLUME]),
            default_temp_entity=default_reference_temperature_entity,
            default_humidity_entity=default_reference_humidity_entity,
            default_temp=default_ref_t, default_humidity=default_ref_rh,
            learning_rate=float(mem.get("learning_rate", .03)),
            learning_samples=int(mem.get("learning_samples", 0)), co2=co2, pollen=pollen,
            options=options, wind_bearing=wind_bearing, wind_speed=wind_speed, contact_modes=physical_contact_modes,
            cooling_allowed="temperature" not in disabled_goals,
        )
        room_threshold_mode = str(cfg.get(CONF_ROOM_THRESHOLD_MODE, ROOM_THRESHOLD_AUTOMATIC) or ROOM_THRESHOLD_AUTOMATIC)
        if room_threshold_mode == ROOM_THRESHOLD_PERCENT:
            room_threshold_effective_ml = max(float(result.water_in_air_ml or 0.0) * float(cfg.get(CONF_ROOM_THRESHOLD_PERCENT, 5.0) or 5.0) / 100.0, 0.0)
        elif room_threshold_mode == ROOM_THRESHOLD_FIXED:
            room_threshold_effective_ml = max(float(cfg.get(CONF_ROOM_THRESHOLD_ML, 100.0) or 100.0), 0.0)
        else:
            room_threshold_mode = ROOM_THRESHOLD_AUTOMATIC
            room_threshold_effective_ml = max(float(options.get("min_potential_room_ml", 100.0) or 100.0), 0.0)

        comfort_target, comfort_target_source = room_comfort_target(cfg, mem)
        trend_prev = mem.get("goal_trend_sample") if isinstance(mem.get("goal_trend_sample"), dict) else {}
        trend_dt = None
        try:
            trend_dt = max((now - datetime.fromisoformat(str(trend_prev.get("at")))).total_seconds()/60.0, 0.01)
        except (TypeError, ValueError):
            pass
        def _trend(cur: Any, name: str) -> float | None:
            old = finite_float(trend_prev.get(name))
            return ((float(cur)-old)/trend_dt) if cur is not None and old is not None and trend_dt else None
        goal_state = evaluate_goals(
            humidity=rh, target_rh=options.get("target_rh", 55.0), co2=co2, co2_warn=options.get("co2_warn", 1000.0),
            temperature=t, temperature_target=comfort_target, humidity_rate_pct_min=_trend(rh,"rh"),
            co2_rate_ppm_min=_trend(co2,"co2"), temperature_rate_c_min=_trend(t,"temp"),
            priorities=cfg.get(CONF_ROOM_GOAL_PRIORITIES, []),
            available_goals=[
                *(["humidity"] if cfg.get(CONF_ROOM_HUMIDITY) and cfg.get(CONF_ROOM_TEMPERATURE) else []),
                *(["co2"] if cfg.get(CONF_ROOM_CO2) else []),
                *(["temperature"] if (cfg.get(CONF_ROOM_CLIMATE) or cfg.get(CONF_ROOM_TARGET_TEMPERATURE) not in (None, "") or cfg.get(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK) not in (None, "")) else []),
            ],
            hard_close=bool(result.close_recommended),
            disabled_goals=disabled_goals,
            humidity_floor_rh=equilibrium_rh(t, result.reference_humidity) if (is_open or mem.get("session_active")) else None,
        )
        for goal in goal_state.get("goals", []):
            if goal.get("id") == "humidity":
                goal["achievable_now"] = bool(result.ventilation_candidate or result.active) and not goal.get("unreachable")
            elif goal.get("id") == "temperature":
                goal["achievable_now"] = bool(result.cooling_candidate or (result.active and ref_t < t))
            elif goal.get("id") == "co2":
                goal["achievable_now"] = bool(co2_available and co2 >= float(options.get("co2_warn", 1000.0)) and not (options.get("pollen_enabled", False) and options.get("pollen_strict_veto", True) and pollen > float(options.get("pollen_max", 4.0))) and not outdoor_pm25_blocked(options, outdoor_pm25))
        mem["goal_trend_sample"] = {"at": now.isoformat(), "rh": rh, "co2": co2, "temp": t}
        return (
            changed, comfort_target, comfort_target_source, cooldown_demoted, cooldown_override, goal_state,
            humidity_rebound, minutes_since_vent, opening_assessments, recently_ventilated,
            room_threshold_effective_ml, room_threshold_mode, routine_response, routine_samples, season_ctx,
            seasonal_routine_rate, stabilizing,
        )

    def _room_result_payload(
        self,
        *,
        airflow: Any, cfg: Any, co2_available: Any, co2_display: Any, co2_entity: Any, comfort_target: Any,
        comfort_target_source: Any, cooldown_demoted: Any, cooldown_override: Any, cost: Any,
        cover_learning_guard: Any, delivered: Any, dynamic: Any, dynamic5: Any, effective_learning_rate: Any,
        elapsed: Any, explicit_three_state: Any, fcost: Any, fdel: Any, ffuel: Any, forecast_horizon: Any,
        fpurchased: Any, fuel: Any, goal_state: Any, has_ventilation_contact: Any, high_duration: Any,
        humidity_rebound: Any, humidity_trend: Any, idx: Any, illuminance: Any,
        illuminance_configured_entity: Any, illuminance_sensor_enabled: Any, include: Any,
        indirect_candidate: Any, indirect_cooling_candidate: Any, key: Any, measurement_frame: Any, mem: Any,
        minutes_since_vent: Any, moisture_source: Any, opening_assessments: Any, opening_mode: Any,
        options: Any, passage_contacts: Any, pm25: Any, pm25_configured_entity: Any, pm25_sensor_enabled: Any,
        proven_three_state: Any, purchased: Any, reason_list: Any, recently_ventilated: Any,
        reference_humidity_entity: Any, reference_temperature_entity: Any, result: Any, results: Any,
        room_threshold_effective_ml: Any, room_threshold_mode: Any, routine_response: Any,
        routine_samples: Any, season_ctx: Any, seasonal_routine_rate: Any, stabilizing: Any, temp_change: Any,
        three_state_stale_contacts: Any, three_state_unknown_contacts: Any, transition_suppressed: Any,
        voc: Any, voc_configured_entity: Any, voc_sensor_enabled: Any,
    ) -> Any:
        """Publish the room result: model output plus forecast, learning, goal and diagnostic fields."""
        results[key] = result.as_dict() | {
            "learning_diagnosis": mem.get("diagnosis", ""), "learning_sample_credit": round(float(mem.get("learning_sample_credit", 0.0) or 0.0), 3), "co2": co2_display, "co2_available": co2_available, "co2_data_quality": ("ok" if co2_available else "goal_disabled" if co2_display is not None else "missing" if co2_entity else "not_configured"),
            "goal_state": goal_state, "goal_priorities": goal_state.get("priorities"),
            "comfort_target_c": comfort_target, "comfort_target_source": comfort_target_source,
            "voc": voc, "voc_available": voc is not None, "voc_enabled": voc_sensor_enabled, "voc_configured": bool(voc_configured_entity),
            "pm25": pm25, "pm25_available": pm25 is not None, "pm25_enabled": pm25_sensor_enabled, "pm25_configured": bool(pm25_configured_entity),
            "illuminance": illuminance, "illuminance_available": illuminance is not None, "illuminance_enabled": illuminance_sensor_enabled, "illuminance_configured": bool(illuminance_configured_entity),
            "learned_exchange_rate_per_min": round(effective_learning_rate, 3),
            "opening_state": opening_mode,
            "opening_state_explicit": bool(explicit_three_state),
            "three_state_contacts": sorted(proven_three_state),
            "three_state_transition_suppressed": bool(transition_suppressed),
            "three_state_transients_suppressed": int(mem.get("three_state_transients_suppressed", 0) or 0),
            "three_state_unknown_contacts": list(mem.get("three_state_unknown_contacts") or []),
            "three_state_stale_contacts": list(mem.get("three_state_stale_contacts") or []),
            "session_three_state_unknown_observed": bool(mem.get("session_three_state_unknown_observed")),
            "passage_door_configured": bool(any(bool(v) for v in passage_contacts.values())),
            "passage_behavior": mem.get("passage_behavior", {}),
            "passage_pattern_learned": bool(any(isinstance(v, dict) and v.get("learned") for v in (mem.get("passage_behavior") or {}).values())),
            "learning_quarantined": bool(mem.get("session_learning_quarantined")),
            "learning_quarantine_code": mem.get("session_learning_quarantine_code"),
            "opening_diagnostic_codes": (["FAIQ-OPENING-3STATE-001"] if explicit_three_state and opening_mode == "unknown" else []) + (["FAIQ-OPENING-3STATE-002"] if transition_suppressed else []) + (["FAIQ-OPENING-3STATE-005"] if three_state_unknown_contacts else []) + (["FAIQ-OPENING-3STATE-006"] if three_state_stale_contacts else []) + ([str(mem.get("session_learning_quarantine_code"))] if mem.get("session_learning_quarantine_code") else []),
            "opening_learning": mem.get("opening_learning", {}),
            "direct_learning_samples": int(mem.get("learning_samples", 0)),
            "passive_learning_samples": int(mem.get("passive_learning_samples", 0)),
            "passive_learned_exchange_rate_per_min": round(float(mem.get("passive_learning_rate", .03)), 3),
            "ventilation_path": ("assigned_opening" if has_ventilation_contact else "indirect_unassigned"),
            "indirect_ventilation_candidate": indirect_candidate,
            "indirect_cooling_candidate": indirect_cooling_candidate,
            "behaviour_recommendation_opportunities": int(mem.get("recommendation_opportunities", 0)), "behaviour_recommendation_followed": int(mem.get("recommendation_followed", 0)), "behaviour_recommendation_follow_rate": mem.get("recommendation_follow_rate"),
            "behaviour_preferred_duration_min": mem.get("preferred_duration_min"), "behaviour_duration_samples": int(mem.get("duration_samples", 0)), "behaviour_avg_follow_delay_min": mem.get("avg_follow_delay_min"), "behaviour_follow_delay_samples": int(mem.get("follow_delay_samples", 0)), "behaviour_avg_duration_deviation_min": mem.get("avg_duration_deviation_min"),
            "forecast_observation_samples": int(mem.get("forecast_observation_samples", 0)), "forecast_source_ml_min": mem.get("forecast_source_ml_min"), "forecast_thermal_residual_c_min": mem.get("forecast_thermal_residual_c_min"),
            "routine_maturity": routine_maturity(mem), "routine_source_samples": int(mem.get("routine_source_samples", 0)), "routine_response_samples": int(mem.get("routine_response_samples", 0)),
            "routine_expected_source_ml_min": round(seasonal_routine_rate, 3) if seasonal_routine_rate is not None else None, "routine_current_bucket_samples": int(routine_samples), "routine_response": routine_response,
            "season": season_ctx.get("season"), "seasonal_factor": season_ctx.get("factor"), "seasonal_maturity": season_ctx.get("maturity"),
            "seasonal_source_rate_ml_min": season_ctx.get("season_rate_ml_min"), "long_term_source_rate_ml_min": season_ctx.get("long_term_rate_ml_min"),
            "seasonal_samples": int(mem.get("seasonal_samples", 0)), "long_term_source_samples": int(mem.get("long_term_source_samples", 0)),
            "routine_source_buckets": mem.get("routine_source_buckets", {}),
            "strategy_maturity": strategy_maturity(mem), "strategy_samples": int(mem.get("strategy_samples", 0)),
            "strategy_follow_samples": int(mem.get("strategy_follow_samples", 0)), "strategy_outcome_samples": int(mem.get("strategy_outcome_samples", 0)),
            "outcome_feedback_samples": int(mem.get("outcome_feedback_samples", 0)), "outcome_removed_factor": float(mem.get("outcome_removed_factor", 1.0) or 1.0), "outcome_temperature_factor": float(mem.get("outcome_temperature_factor", 1.0) or 1.0),
            "shadow_learning_samples": int(mem.get("shadow_learning_samples", 0)), "shadow_learning_total_samples": int(mem.get("shadow_learning_total_samples", 0)), "shadow_learning_status": mem.get("shadow_learning_status"), "shadow_learning_last_action": mem.get("shadow_learning_last_action"), "shadow_learning_last_improvement_pct": mem.get("shadow_learning_last_improvement_pct"), "shadow_learning_promotions": int(mem.get("shadow_learning_promotions", 0)), "shadow_learning_rollbacks": int(mem.get("shadow_learning_rollbacks", 0)), "shadow_rollback_active": bool(mem.get("shadow_rollback_active")),
            "outcome_avg_removed_error_ml": mem.get("outcome_avg_removed_error_ml"), "outcome_avg_temperature_error_c": mem.get("outcome_avg_temperature_error_c"), "outcome_success_rate": mem.get("outcome_success_rate"),
            "session_recommended_duration_min": mem.get("session_recommended_duration_min"), "session_target_min": mem.get("session_target_min") if mem.get("session_active") else None, "session_predicted_removed_ml": mem.get("session_predicted_removed_ml"), "session_predicted_temperature_change_c": mem.get("session_predicted_temperature_change_c"), "session_prediction_confidence": mem.get("session_prediction_confidence"), "session_prediction_snapshot_at": mem.get("session_prediction_snapshot_at"), "session_prediction_horizon_min": mem.get("session_prediction_horizon_min"), "session_prediction_snapshot_elapsed_min": mem.get("session_prediction_snapshot_elapsed_min"), "session_prediction_snapshot_valid": bool(mem.get("session_prediction_snapshot_valid")), "session_prediction_reference": mem.get("session_prediction_reference"),
            "session_elapsed_min": round(elapsed, 1), "temperature_change_c": temp_change, "volume_m3": round(float(cfg[CONF_ROOM_VOLUME]), 1),
            "contact_mode": cfg.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY), "contact_count": len(_contact_ids(cfg)), "contact_entities": _contact_ids(cfg), "contact_delays": dict(cfg.get(CONF_CONTACT_DELAYS, {})), "contact_orientations": dict(cfg.get(CONF_CONTACT_ORIENTATIONS, {})), "contact_reference_temperatures": dict(cfg.get(CONF_CONTACT_REFERENCE_TEMPERATURES, {})), "contact_reference_humidities": dict(cfg.get(CONF_CONTACT_REFERENCE_HUMIDITIES, {})), "active_reference_temperature_entity": reference_temperature_entity, "active_reference_humidity_entity": reference_humidity_entity, "opening_assessments": opening_assessments,
            "next_5_min_heat_kwh": delivered, "next_5_min_purchased_kwh": purchased, "next_5_min_cost": cost, "next_5_min_energy_amount": fuel["amount"], "next_5_min_energy_unit": fuel["unit"],
            "forecast_horizon_min": forecast_horizon, "forecast_moisture_effect_ml": int(dynamic["moisture_effect_ml"]),
            "forecast_physical_moisture_effect_ml": int(dynamic["physical_moisture_effect_ml"]), "forecast_uncapped_moisture_effect_ml": int(dynamic.get("uncapped_physical_moisture_effect_ml", dynamic["physical_moisture_effect_ml"])), "forecast_target_limited": bool(dynamic.get("target_limited", False)), "forecast_target_cap_ml": dynamic.get("target_cap_ml"), "forecast_live_adapted": bool(dynamic.get("live_adapted", False)), "forecast_live_observation_weight": float(dynamic.get("live_observation_weight", 0.0) or 0.0), "forecast_observed_projection_ml": dynamic.get("observed_projection_ml"), "forecast_internal_moisture_effect_ml": int(dynamic["internal_moisture_effect_ml"]),
            "forecast_net_moisture_change_ml": int(dynamic.get("net_moisture_change_ml", dynamic["moisture_effect_ml"])),
            "forecast_5_min_moisture_effect_ml": int(dynamic5["moisture_effect_ml"]),
            "forecast_5_min_net_moisture_change_ml": int(dynamic5.get("net_moisture_change_ml", dynamic5["moisture_effect_ml"])),
            "forecast_5_min_temperature_change_c": round(float(dynamic5["temperature_change_c"]), 2),
            "forecast_5_min_confidence": int(dynamic5["confidence"]),
            "forecast_temperature_change_c": round(float(dynamic["temperature_change_c"]), 2), "forecast_confidence": int(dynamic["confidence"]),
            "forecast_source_rate_ml_min": float(dynamic["source_rate_ml_min"]), "forecast_method": dynamic["method"],
            "forecast_simulation_steps": int(dynamic.get("simulation_steps", 1)), "forecast_simulated_final_ah": dynamic.get("simulated_final_ah"),
            "forecast_future_weather_used": bool(dynamic.get("future_weather_used", False)), "forecast_future_weather_confidence": dynamic.get("future_weather_confidence"),
            "forecast_optimal_close_in_min": dynamic.get("optimal_close_in_min"), "forecast_optimal_close_reason": dynamic.get("optimal_close_reason"),
            "forecast_max_cumulative_temp_loss_c": dynamic.get("max_cumulative_temp_loss_c"), "forecast_min_end_temp_c": dynamic.get("min_forecast_end_temp_c"),
            "forecast_heat_kwh": fdel, "forecast_purchased_kwh": fpurchased, "forecast_cost": fcost,
            "forecast_energy_amount": ffuel["amount"], "forecast_energy_unit": ffuel["unit"],
            "free_cooling_kwh": delivered if result.action == "Ventilate for cooling" else 0.0,
            "calculation_enabled": include, "icon": cfg.get(CONF_ROOM_ICON), "floor": cfg.get(CONF_ROOM_FLOOR, FLOOR_GROUND), "sort_order": int(cfg.get(CONF_ROOM_SORT_ORDER, idx)),
            "ventilation_threshold_mode": room_threshold_mode, "ventilation_threshold_percent": float(cfg.get(CONF_ROOM_THRESHOLD_PERCENT, 5.0) or 5.0), "ventilation_threshold_configured_ml": float(cfg.get(CONF_ROOM_THRESHOLD_ML, 100.0) or 100.0), "ventilation_threshold_effective_ml": round(room_threshold_effective_ml, 1),
            "window_orientation": cfg.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN), "airflow_factor": airflow,
            "configured_moisture_sources": list(cfg.get(CONF_ROOM_MOISTURE_SOURCES, []) or []),
            "moisture_source_active": bool(moisture_source.get("active")), "moisture_source_recovery": bool(moisture_source.get("recovery")),
            "moisture_source_label": moisture_source.get("label"), "moisture_source_identified_source": moisture_source.get("identified_source"), "moisture_source_message": moisture_source.get("message"), "moisture_source_ambiguous": bool(moisture_source.get("ambiguous")), "moisture_source_confidence": int(moisture_source.get("confidence", 0)),
            "moisture_source_rate_ml_min": float(moisture_source.get("source_rate_ml_min", 0.0)), "moisture_source_generated_ml_window": float(moisture_source.get("generated_ml_window", 0.0)),
            "moisture_source_observed_change_ml_window": float(moisture_source.get("observed_change_ml_window", 0.0)), "moisture_source_ventilation_change_ml_window": float(moisture_source.get("ventilation_change_ml_window", 0.0)),
            "moisture_source_ah_rise_g_m3": float(moisture_source.get("absolute_humidity_rise_g_m3", 0.0)), "moisture_source_window_min": float(moisture_source.get("window_min", 0.0)),
            "moisture_source_started_at": moisture_source.get("started_at"), "moisture_source_last_ended_at": moisture_source.get("last_ended_at"),
            "cover_learning_blocked": bool(mem.get("session_cover_learning_blocked")), "cover_learning_guard": mem.get("session_cover_learning_guard") if isinstance(mem.get("session_cover_learning_guard"), dict) else cover_learning_guard,
            "recommendation_reasons": ([*reason_list, f"Rollladen/Jalousie stärker als {float(cover_learning_guard.get('threshold', 20.0)):.0f} % geschlossen: Lüftung wird bilanziert, aber nicht als Lernprobe verwendet"] if mem.get("session_active") and cover_learning_guard.get("blocked") else reason_list), "humidity_trend_pct_h": round(humidity_trend, 2), "humidity_high_duration_min": round(high_duration, 1),
            "last_measurement_at": mem.get("last_measurement_at"), "last_measurement_valid": mem.get("last_measurement_valid"),
            "measurement_frame_quality": measurement_frame.get("quality"), "measurement_frame_learning_eligible": bool(measurement_frame.get("learning_eligible")),
            "measurement_frame_skew_s": measurement_frame.get("skew_s"), "measurement_frame_full_skew_s": measurement_frame.get("full_skew_s"), "measurement_frame_reference_skew_s": measurement_frame.get("reference_skew_s"), "measurement_frame_max_age_s": measurement_frame.get("max_age_s"),
            "frame_age_temp_s": measurement_frame.get("age_temperature_s"), "frame_age_humidity_s": measurement_frame.get("age_humidity_s"),
            "frame_age_reference_temp_s": measurement_frame.get("age_reference_temperature_s"), "frame_age_reference_humidity_s": measurement_frame.get("age_reference_humidity_s"),
            # 0.26.5.3: the report times themselves (stable between reports; the ages above grow every cycle)
            "frame_temp_reported_at": measurement_frame.get("temperature_reported_at"), "frame_humidity_reported_at": measurement_frame.get("humidity_reported_at"),
            "frame_reference_temp_reported_at": measurement_frame.get("reference_temperature_reported_at"), "frame_reference_humidity_reported_at": measurement_frame.get("reference_humidity_reported_at"),
            "humidity_high_since": mem.get("humidity_high_since"),
            "measurement_frame_reason": measurement_frame.get("reason"),
            # Intelligence 2.0 time-evidence must travel with the room snapshot.
            # build_learning_components_status() consumes `results`, not the
            # raw persistence dict; omitting these fields flattened all
            # independent-day counters to zero despite valid stored evidence.
            "learning_observation_dates": list(mem.get("learning_observation_dates") or []),
            "routine_observation_dates": list(mem.get("routine_observation_dates") or []),
            "strategy_observation_dates": list(mem.get("strategy_observation_dates") or []),
            "personal_context_observation_dates": list(mem.get("personal_context_observation_dates") or []),
            "seasonal_observation_days": dict(mem.get("seasonal_observation_days") or {}),
            "post_close_stabilization_active": bool(mem.get("post_close_active")),
            "post_close_stabilization": mem.get("post_close_last_outcome"),
            "start_measurement_state": mem.get("start_measurement_state"),
            "start_measurement_in_session_gate_passed": bool(mem.get("start_measurement_in_session_gate_passed")),
            "session_fresh_measurements": int(mem.get("session_fresh_measurements", 0)),
            "session_temperature_reports": int(mem.get("session_temperature_reports", 0)),
            "session_humidity_reports": int(mem.get("session_humidity_reports", 0)),
            "session_finalization_pending": bool(mem.get("session_close_pending")),
            "session_finalization_deadline_at": mem.get("session_close_deadline_at"),
            "session_final_temperature_feedback": bool(mem.get("session_close_temperature_feedback")),
            "session_final_humidity_feedback": bool(mem.get("session_close_humidity_feedback")),
            "session_measurement_quality": session_measurement_quality(
                int(mem.get("session_fresh_measurements", 0)),
                temperature_reports=int(mem.get("session_temperature_reports", 0)),
                humidity_reports=int(mem.get("session_humidity_reports", 0)),
                final_temperature_feedback=bool(mem.get("session_close_temperature_feedback")),
                final_humidity_feedback=bool(mem.get("session_close_humidity_feedback")),
            ),
            "close_decision_ready": bool(result.close_decision_ready),
            "last_learning_at": mem.get("last_learning_at"), "last_learning_valid": mem.get("last_learning_valid"),
            "stabilizing": stabilizing, "recently_ventilated": recently_ventilated, "repeat_cooldown_demoted": cooldown_demoted, "repeat_cooldown_override": cooldown_override,
            "minutes_since_last_ventilation": round(minutes_since_vent,1) if minutes_since_vent is not None else None,
            "repeat_humidity_rebound_percent": round(humidity_rebound, 1) if humidity_rebound is not None else None,
            "history_14d": self.store.room_history_days(key, int(options.get("statistics_days", 14))), "temperature_history_14d": self.store.room_temperature_points(key, int(options.get("statistics_days", 14))), "humidity_history_14d": self.store.room_humidity_points(key, int(options.get("statistics_days", 14))),
        }
