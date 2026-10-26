"""Final house recommendation, presentation layers and the published coordinator payload."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_LEVELS, PROPERTY_HOUSE, SESSION_END_MEASUREMENT_WAIT_SECONDS
from .anticipation import refine_with_anticipation
from .consolidation import stabilise_recommendation
from .decision import build_decision_simulation
from .decision_brain import build_unified_decision
from .decision_trace import build_decision_trace, build_recommendation_quality
from .energy import energy_price_per_kwh_equivalent
from .forecast import effective_night_rate_ml_h
from .forecast_backtest import backtest_summary
from .close_wording import airing_running, fan_only, no_opening_wording
from .fan_automation import room_fan_automation
from .forecast_validation import validation_summary
from .house_decision import floor_ventilation_decision
from .house_strategy import house_maturity, house_strategy_fit, learn_house_outcome
from .intelligence import build_intelligence_state, sync_active_recommendation
from .language_confidence import adapt_language_confidence
from .learning_components import build_learning_components_status
from .learning_v2 import build_learning_v2_status
from .live_coach import refine_live_recommendation
from .model import absolute_humidity
from .open_connections import connection_map
from .opening_strategy import (
    enrich_opening_recommendation,
    house_aligned_room_actions,
    keep_moisture_sources_open,
    synchronize_room_presentation_actions,
)
from .outdoor_air import outdoor_pm25_limit
from .personal_context import build_resident_context, personalise_recommendation
from .planner import build_multi_hour_plan, refine_with_plan
from .post_stabilization import stabilization_summary
from .presence import presence_diagnostics
from .recommendation import build_recommendation


class HouseDecisionMixin:
    """Final house recommendation, presentation layers and the published coordinator payload."""

    hass: HomeAssistant  # provided by the coordinator

    def _finalise_house_recommendation(
        self,
        *,
        active: Any, changed: Any, cross: Any, forecast_confidence: Any, forecast_cost: Any,
        forecast_effect: Any, forecast_horizon: Any, intelligent_recommendation: Any, max_elapsed: Any,
        next5_effect: Any, night_confidence: Any, night_samples: Any, night_strategy: Any, now: Any,
        occupancy: Any, options: Any, recommended: Any, remaining: Any, results: Any, status: Any, valid: Any,
    ) -> Any:
        """Presentation layers of the final house recommendation (house/floor mode, personal context, trace)."""
        # Adaptive presentation mode: when most of the monitored house is being
        # aired, communicate one house action instead of noisy per-room closing.
        monitored_count = max(len(valid), 1)
        # 0.26.5.4 (support case): a running exhaust fan alone is no opened
        # window – it is judged by its own room model. Counted here, its start
        # held the whole floor on "continue" and its floor close told the user
        # to switch off a fan that still dried the room.
        # A room in its final measurement after closing is no longer aired either.
        active = [r for r in active if airing_running(r) and not fan_only(r)]
        active_ratio = len(active) / monitored_count
        previous_house_mode = bool(self.store.data.get("house_ventilation_mode", False))
        enter_ratio = float(options.get("house_ventilation_enter_ratio", 0.75))
        exit_ratio = float(options.get("house_ventilation_exit_ratio", 0.50))
        house_ventilation_mode = active_ratio >= (exit_ratio if previous_house_mode else enter_ratio)
        if house_ventilation_mode != previous_house_mode:
            self.store.data["house_ventilation_mode"] = house_ventilation_mode
            changed = True
        (floor_display_name, floor_ventilation_mode) = floor_ventilation_decision(
            active=active,
            cross=cross,
            forecast_confidence=forecast_confidence,
            forecast_cost=forecast_cost,
            house_ventilation_mode=house_ventilation_mode,
            intelligent_recommendation=intelligent_recommendation,
            night_strategy=night_strategy,
            options=options,
            valid=valid,
        )

        # Personal Context Engine v1 is the final presentation layer. Running it
        # here also covers the aggregate house-ventilation presentation above.
        # It is presentation-only and cannot alter the canonical physical action.
        resident_context = build_resident_context(
            options, self.hass.states,
            expected_occupants=float(occupancy.get("expected_total", 0.0)),
        )
        intelligent_recommendation = personalise_recommendation(
            intelligent_recommendation, results, options, now=now,
            expected_occupants=float(occupancy.get("expected_total", 0.0)),
            resident_context=resident_context,
        )
        # Language Confidence Layer v1 changes only how the final decision is
        # expressed. Model maturity and current-situation confidence are kept
        # separate so a mature room can still be described cautiously when the
        # present measurement/weather situation is uncertain.
        intelligent_recommendation = adapt_language_confidence(
            intelligent_recommendation, results, self.store.data
        )
        # Opening Strategy v1: the existing engines decide WHETHER and WHERE to
        # ventilate. Only after that decision is final do we choose WHICH
        # configured opening(s) best match the current source air. This keeps
        # every canonical physics/forecast/learning value unchanged.
        intelligent_recommendation = enrich_opening_recommendation(
            intelligent_recommendation, results, options
        )
        # 0.26.5.2: after the house/floor aggregate and the opening overlay, a
        # room with a running moisture source (sauna, shower ...) is never closed.
        keep_moisture_sources_open(intelligent_recommendation, results, options)
        # Three-state mode selection is the last action-specific presentation
        # layer so generic wording/personalisation cannot erase the explicit
        # tilt-vs-shock recommendation or a running user's selected mode.

        # Decision Intelligence & Validation v1: attach an observational trace
        # only after every layer has finished. It cannot alter the canonical
        # action and therefore cannot destabilise the proven ventilation logic.
        _decision_validation = validation_summary(
            self.store.data.get("forecast_validation_history") or [], days=30
        )
        intelligent_recommendation["decision_trace"] = build_decision_trace(
            intelligent_recommendation, results, validation=_decision_validation
        )
        intelligent_recommendation["recommendation_quality"] = build_recommendation_quality(
            _decision_validation
        )

        if sync_active_recommendation(self.store.data, intelligent_recommendation, now):
            changed = True
        iq_state = build_intelligence_state(
            results, intelligent_recommendation,
            forecast_confidence=forecast_confidence, overnight_confidence=night_confidence,
            presence_confidence=float(occupancy.get("presence_confidence", 50)), night_samples=night_samples, now=now,
        )
        status = str(intelligent_recommendation.get("status") or status)
        status_text = f"{intelligent_recommendation.get('title', '')} · {intelligent_recommendation.get('instruction', '')}".strip(" ·")
        displayed_recommended = recommended
        if str(intelligent_recommendation.get("kind") or "") == "ventilate" and intelligent_recommendation.get("duration_min") is not None:
            displayed_recommended = float(intelligent_recommendation["duration_min"])
        elif active and intelligent_recommendation.get("live_coach_target_min") is not None:
            displayed_recommended = float(intelligent_recommendation["live_coach_target_min"])
            remaining = float(intelligent_recommendation.get("live_coach_remaining_min", remaining))
        if str(intelligent_recommendation.get("kind") or "") == "close":
            # A close action is immediate, but the dashboard's IQ-ZEIT tile should
            # still show how far the real session has already passed its target.
            # Negative remaining time is rendered as "+X min über Ziel".
            remaining = min(0.0, round(float(displayed_recommended) - max_elapsed, 1))

        # Routine bucket tables are an internal model. Keep only compact
        # Hotfix 0.20.2.6: when house mode is active, the short-term tile and
        # the explanation consume the exact same signed aggregate value.
        if house_ventilation_mode and active:
            _house_short = intelligent_recommendation.get("house_next_5_min_moisture_effect_ml")
            if _house_short is not None:
                next5_effect = float(_house_short)
                if forecast_horizon == 5:
                    forecast_effect = float(_house_short)

        # Keep every dashboard surface semantically aligned with the final
        # recommendation. Canonical room actions are preserved as metadata and
        # this happens only after all physics/learning decisions are complete.
        synchronize_room_presentation_actions(intelligent_recommendation, results)
        house_aligned_room_actions(intelligent_recommendation, results)
        for _key, _room in results.items():
            if isinstance(_room, dict) and _room.get("fan_automation") is not None:
                _room["fan_automation"] = room_fan_automation(_room, self._fan_snapshot(_key))
        no_opening_wording(results, connection_map(options, results))

        # summaries in coordinator data so the dashboard payload stays small.
        for _room in results.values():
            _room.pop("routine_source_buckets", None)
        return (
            _decision_validation, active_ratio, changed, displayed_recommended, floor_display_name,
            floor_ventilation_mode, forecast_effect, house_ventilation_mode, intelligent_recommendation,
            iq_state, next5_effect, remaining, status, status_text,
        )

    def _house_status_extras(
        self,
        *,
        _decision_validation: Any, _learning_effectiveness_pre: Any, current_daily_generation: Any,
        future_outdoor: Any, night_samples: Any, now: Any, options: Any, outdoor_rh: Any, outdoor_t: Any,
        results: Any, routine_night_maturity: Any, stats_days: Any, valid: Any,
    ) -> Any:
        """History, system check, learning summaries and pending end-of-session measurements."""
        history = self.store.history_days(stats_days)
        history_summary = {"removed_ml": round(sum(float(x.get("removed_ml", 0)) for x in history)), "sessions": sum(int(x.get("sessions", 0)) for x in history), "moisture_measured_sessions": sum(int(x.get("moisture_measured_sessions", 0)) for x in history), "moisture_unmeasured_sessions": sum(int(x.get("moisture_unmeasured_sessions", 0)) for x in history), "ventilation_minutes": round(sum(float(x.get("ventilation_minutes", 0)) for x in history), 1), "energy_kwh": round(sum(float(x.get("energy_kwh", 0)) for x in history), 3), "cost": round(sum(float(x.get("cost", 0)) for x in history), 2)}
        today_row = history[-1] if history else {}; elapsed_day_fraction = (now.hour * 60 + now.minute) / 1440.0
        expected_generated_so_far = round(current_daily_generation * elapsed_day_fraction); moisture_balance_today = round(expected_generated_so_far - float(today_row.get("removed_ml", 0)))
        adults = int(options.get("adult_occupants", 0)); children = int(options.get("child_occupants", 0))

        stale_rooms = [r for r in results.values() if r.get("calculation_enabled", True) and r.get("data_quality") != "ok"]
        co2_rooms = sum(1 for r in valid if r.get("co2_available"))
        frame_quality_counts = {
            quality: sum(1 for r in results.values() if r.get("calculation_enabled", True) and r.get("measurement_frame_quality") == quality)
            for quality in ("excellent", "acceptable", "uncertain", "stale")
        }
        system_check = {
            "configured_rooms": len([r for r in results.values() if r.get("calculation_enabled", True)]),
            "valid_rooms": len(valid),
            "stale_or_invalid_rooms": len(stale_rooms),
            "weather_available": bool(outdoor_t is not None and outdoor_rh is not None),
            "future_weather_available": bool(future_outdoor),
            "co2_rooms": co2_rooms,
            "co2_optional": True,
            "measurement_frame_quality_counts": frame_quality_counts,
            "measurement_frame_learning_eligible_rooms": sum(1 for r in results.values() if r.get("calculation_enabled", True) and r.get("measurement_frame_learning_eligible")),
            "night_model_samples": night_samples,
            "night_model_maturity_percent": min(100, round(night_samples / 20 * 100)),
            "routine_maturity_percent": round(routine_night_maturity),
            "runtime_config_issues": list(self.robustness.runtime_config_issues),
            "repaired_option_keys": list(self.robustness.repaired_option_keys),
            "overall": "Gut – Lernen läuft" if valid and not stale_rooms and not self.robustness.runtime_config_issues else ("Eingeschränkt – Konfiguration/Sensordaten prüfen" if valid else "Nicht bereit"),
        }
        forecast_validation_status = _decision_validation
        forecast_backtest_status = backtest_summary(self.store.data.get("forecast_validation_history") or [], days=30)
        learning_effectiveness_status = _learning_effectiveness_pre
        post_close_status = stabilization_summary(self.store.data.get("post_close_stabilization_history") or [])
        learning_components_status = build_learning_components_status(
            results,
            self.store.data,
            forecast_backtest=forecast_backtest_status,
            post_close_stabilization=post_close_status,
        )
        learning_v2_status = build_learning_v2_status(
            results, forecast_backtest=forecast_backtest_status,
            learning_effectiveness=learning_effectiveness_status,
            post_close=post_close_status, components=learning_components_status,
        )

        pending_final_rooms = [r for r in results.values() if r.get("session_finalization_pending")]
        pending_deadlines = []
        for room in pending_final_rooms:
            try:
                pending_deadlines.append(datetime.fromisoformat(str(room.get("session_finalization_deadline_at"))))
            except (TypeError, ValueError):
                pass
        final_wait_remaining_s = max(
            [max((deadline - now).total_seconds(), 0.0) for deadline in pending_deadlines] or [0.0]
        )
        finalizing_measurements = {
            "active": bool(pending_final_rooms),
            "room_count": len(pending_final_rooms),
            "room_names": [str(room.get("name") or room.get("key")) for room in pending_final_rooms],
            "wait_remaining_s": round(final_wait_remaining_s, 1),
            "max_wait_s": SESSION_END_MEASUREMENT_WAIT_SECONDS,
            "temperature_feedback_count": sum(bool(room.get("session_final_temperature_feedback")) for room in pending_final_rooms),
            "humidity_feedback_count": sum(bool(room.get("session_final_humidity_feedback")) for room in pending_final_rooms),
            "message": "Fenster geschlossen · FreshAirIQ wartet kurz auf aktuelle Rückmeldungen der Klimasensoren und wertet danach die Lüftung aus.",
        }
        return (
            adults, children, expected_generated_so_far, finalizing_measurements, forecast_backtest_status,
            forecast_validation_status, history, history_summary, learning_components_status,
            learning_effectiveness_status, learning_v2_status, moisture_balance_today, post_close_status,
            system_check,
        )

    async def _async_publish_house_data(
        self,
        *,
        _phase_started: Any, actionable_potential: Any, active_ratio: Any, adults: Any, changed: Any,
        children: Any, completed_sessions: Any, confidence: Any, cooling: Any, cross: Any,
        current_daily_generation: Any, day_night_plan: Any, displayed_recommended: Any, effective_adults: Any,
        effective_children: Any, expected_daily_generation: Any, expected_generated_so_far: Any,
        finalizing_measurements: Any, floor_display_name: Any, floor_ventilation_mode: Any,
        forecast_backtest_status: Any, forecast_confidence: Any, forecast_cost: Any, forecast_effect: Any,
        forecast_heat: Any, forecast_horizon: Any, forecast_live_adapted: Any,
        forecast_live_observation_weight: Any, forecast_optimal_close_in_min: Any,
        forecast_target_limited: Any, forecast_temp: Any, forecast_uncapped_effect: Any,
        forecast_validation_status: Any, future_outdoor: Any, history: Any, history_summary: Any,
        house_ventilation_mode: Any, intelligent_recommendation: Any, iq_state: Any,
        learning_components_status: Any, learning_effectiveness_status: Any, learning_v2_status: Any,
        live: Any, max_surface: Any, moisture_balance_today: Any, moisture_gain_next5: Any, next5_effect: Any,
        night_confidence: Any, night_forecast: Any, night_forecast_base: Any, night_hours: Any,
        night_recommendation: Any, night_samples: Any, night_strategy: Any, now: Any, occupancy: Any,
        options: Any, outdoor_air_cause: Any, outdoor_pm25: Any, outdoor_rh: Any, outdoor_t: Any, pollen: Any,
        pollen_only_blocked: Any, post_close_status: Any, potential: Any, realistic_actionable_potential: Any,
        realistic_house_effect: Any, remaining: Any, results: Any, rooms_cfg: Any,
        routine_night_adjustment: Any, routine_night_maturity: Any, routine_night_projection: Any,
        sensor_recovery_grace: Any, stats_days: Any, status: Any, status_text: Any, system_check: Any,
        temp_live: Any, threshold_mode: Any, threshold_reason: Any, total_water: Any, trend_effect: Any,
        ventilation_threshold: Any, weather_effect: Any, weather_situation: Any, wind_bearing: Any,
        wind_speed: Any,
    ) -> Any:
        """Assemble the published house payload and finish the update cycle."""
        data = {
            "status": status, "status_text": status_text, "rooms": results, "levels": list(self.entry.data.get(CONF_LEVELS, [])), "potential_total_ml": round(realistic_house_effect), "actionable_potential_ml": round(realistic_actionable_potential), "theoretical_potential_total_ml": round(potential), "theoretical_actionable_potential_ml": round(actionable_potential), "live_balance_ml": round(live), "next_5_min_ml": round(max(next5_effect, 0)), "next_5_min_effect_ml": round(next5_effect), "moisture_gain_next_5_min_ml": round(moisture_gain_next5),
            "forecast_horizon_min": forecast_horizon, "forecast_moisture_effect_ml": round(forecast_effect), "forecast_uncapped_moisture_effect_ml": round(forecast_uncapped_effect), "forecast_target_limited": forecast_target_limited, "forecast_live_adapted": forecast_live_adapted, "forecast_live_observation_weight": round(forecast_live_observation_weight, 3),
            "forecast_temperature_change_c": round(forecast_temp, 2), "forecast_cost": round(forecast_cost, 4),
            "forecast_heat_kwh": round(forecast_heat, 4), "forecast_confidence": forecast_confidence,
            "forecast_optimal_close_in_min": forecast_optimal_close_in_min,
            "max_surface_rh": max_surface, "total_water_ml": round(total_water), "ventilation_threshold_ml": round(ventilation_threshold), "ventilation_threshold_percent": float(options.get("min_potential_percent_total_water", 10)), "ventilation_threshold_mode": threshold_mode, "ventilation_threshold_reason": threshold_reason,
            "prognosis_confidence": confidence, "cross_ventilation": cross, "recommended_duration_min": displayed_recommended, "remaining_duration_min": remaining, "temperature_change_live_c": temp_live,
            "last_learning_diagnosis": self.store.data.get("last_diagnosis", ""), "operating_profile": options.get("operating_profile", "comfort"), "cooling_rooms": len(cooling),
            "overnight_forecast_ml": night_forecast, "overnight_forecast_base_ml": night_forecast_base,
            "overnight_weather_effect_ml": round(weather_effect), "overnight_trend_effect_ml": round(trend_effect),
            "overnight_routine_projection_ml": round(routine_night_projection), "overnight_routine_adjustment_ml": round(routine_night_adjustment), "routine_night_maturity": round(routine_night_maturity),
            "overnight_hours_remaining": round(night_hours, 2), "overnight_confidence": night_confidence,
            "night_model_ml_h": round(effective_night_rate_ml_h(options, self.store.data.get("night_model_ml_h"), int(self.store.data.get("night_model_samples", 0)), effective_adults, effective_children), 1),
            "night_model_samples": night_samples, "night_recommendation": night_recommendation,
            "night_start_hour": options.get("night_start_hour", "22:00"), "night_end_hour": options.get("night_end_hour", "07:00"),
            "night_strategy": night_strategy,
            "history_14d": history, "water_history_14d": self.store.water_history_days(stats_days), "history_summary": history_summary, "statistics_days": stats_days,
            "occupants": adults + children, "adult_occupants": adults, "child_occupants": children,
            "effective_occupants": occupancy["expected_total"], "effective_adults": occupancy["expected_adults"], "effective_children": occupancy["expected_children"],
            "tracked_occupants": occupancy["tracked_total"], "home_tracked_occupants": occupancy["home_adults"] + occupancy["home_children"],
            "away_tracked_occupants": occupancy["away_adults"] + occupancy["away_children"], "unknown_tracked_occupants": occupancy["unknown_adults"] + occupancy["unknown_children"],
            "untracked_adults": occupancy["untracked_adults"], "untracked_children": occupancy["untracked_children"],
            "guest_adults": occupancy["guest_adults"], "guest_children": occupancy["guest_children"], "presence_confidence": occupancy["presence_confidence"],
            "presence_explanation": occupancy.get("presence_explanation"), "presence_diagnostics": presence_diagnostics(options, self.hass.states.get), "pets_in_household": occupancy.get("pets_in_household", False),
            "soft_presence_score": occupancy.get("soft_presence_score", 0.0), "active_presence_sensors": occupancy.get("active_presence_sensors", []),
            "property_type": options.get("property_type", PROPERTY_HOUSE), "heating_system": options.get("heating_system"),
            "energy_price_per_kwh": energy_price_per_kwh_equivalent(options), "notifications_enabled": bool(options.get("notifications_enabled")), "estimated_moisture_generation_day_ml": current_daily_generation, "configured_moisture_generation_day_ml": expected_daily_generation, "estimated_generated_so_far_ml": expected_generated_so_far, "moisture_balance_today_ml": moisture_balance_today,
            "pollen_enabled": bool(options.get("pollen_enabled")), "pollen_index": pollen, "pollen_limit": float(options.get("pollen_max", 4)), "pollen_blocked": pollen_only_blocked,
            "outdoor_pm25": outdoor_pm25, "outdoor_pm25_limit": outdoor_pm25_limit(options), "outdoor_pm25_blocked": bool(self._outdoor_pm25_blocked), "outdoor_air_veto_cause": outdoor_air_cause,
            "weather_now": weather_situation,
            "wind_bearing": wind_bearing, "wind_speed": wind_speed, "last_ventilation": self.store.data.get("last_ventilation"),
            "finalizing_measurements": finalizing_measurements,
            "forecast_validation": forecast_validation_status,
            "recommendation_quality": intelligent_recommendation.get("recommendation_quality", {}),
            "decision_trace": intelligent_recommendation.get("decision_trace", {}),
            "forecast_backtest": forecast_backtest_status,
            "learning_effectiveness": learning_effectiveness_status,
            "post_close_stabilization": post_close_status,
            "learning_components": learning_components_status, "learning_v2": learning_v2_status,
            "post_close_stabilization_history": list(self.store.data.get("post_close_stabilization_history") or [])[-100:],
            "intelligent_recommendation": intelligent_recommendation, "recommendation_engine": "v3", "house_ventilation_mode": house_ventilation_mode, "house_ventilation_active_ratio": round(active_ratio, 3), "floor_ventilation_mode": floor_ventilation_mode, "floor_ventilation_floor": floor_display_name if floor_ventilation_mode else None, "room_sort_order": [str(r.get("key")) for r in rooms_cfg], "system_check": system_check,
            "iq_state": iq_state, "intelligence_engine": "v13", "decision_engine": "v6", "live_coach_engine": "v1", "anticipation_engine": "v1", "planner_engine": "v1", "seasonal_engine": "v1", "house_strategy_engine": "v1", "consolidation_engine": "v1", "decision_brain_engine": "v1", "decision_trace_engine": "v1",
            "future_weather_available": bool(future_outdoor), "future_weather_boundaries": future_outdoor, "day_night_plan": day_night_plan,
            "house_strategy_maturity": house_maturity(self.store.data), "house_strategy_samples": int(self.store.data.get("house_strategy_samples", 0)),
            "sign_convention": "display: moisture_removed=-, moisture_added=+",
            "outdoor_temperature": round(outdoor_t, 2) if outdoor_t is not None else None,
            "outdoor_humidity": round(outdoor_rh, 2) if outdoor_rh is not None else None,
            "outdoor_absolute_humidity": round(absolute_humidity(outdoor_t, outdoor_rh), 3) if outdoor_t is not None and outdoor_rh is not None and -30 < outdoor_t < 60 and 0 <= outdoor_rh <= 100 else None,
            "outdoor_data_quality": "ok" if outdoor_t is not None and outdoor_rh is not None and -30 < outdoor_t < 60 and 0 <= outdoor_rh <= 100 else "missing_or_invalid",
            "sensor_recovery": {
                "active": sensor_recovery_grace,
                "required_sources_unavailable": len(self._unavailable_required_sources),
                "valid_cycles": self._sensor_recovery_valid_cycles,
                "required_valid_cycles": self._sensor_recovery_required_valid_cycles,
                "grace_seconds": self._sensor_recovery_grace_seconds,
                # 0.26.4.2: lets the Guardian tell a guard that never engaged from a
                # persistent outage that intentionally left grace (now a sensor error).
                "unavailable_for_seconds": round((now - self._sensor_recovery_started_at).total_seconds(), 1) if self._unavailable_required_sources and self._sensor_recovery_started_at is not None else 0.0,
            },
        }
        return await self._async_finalize_cycle(
            data, options=options, now=now, completed_sessions=completed_sessions,
            changed=changed, phase_started=_phase_started,
        )

    def _house_recommendation_and_plan(
        self,
        *,
        changed: Any,
        completed_house_sessions: Any,
        cross: Any,
        future_outdoor: Any,
        night_buffer: Any,
        night_confidence: Any,
        night_forecast: Any,
        night_strategy: Any,
        now: Any,
        occupancy: Any,
        options: Any,
        planning_outdoor: Any,
        pollen: Any,
        pollen_blocked: Any,
        realistic_actionable_potential: Any,
        recommended: Any,
        results: Any,
        ventilation_threshold: Any,
    ) -> Any:
        """Phase 3: night recommendation text, day/night plan and the intelligent house recommendation."""
        if night_strategy.get("action") == "close":
            night_recommendation = str(night_strategy.get("instruction"))
        elif night_strategy.get("action") in {"open_selected", "pre_ventilate"}:
            night_recommendation = str(night_strategy.get("instruction"))
        elif night_buffer >= 100:
            night_recommendation = f"Vorlüften kann etwa {night_buffer} ml Puffer schaffen."
        elif night_forecast >= 150:
            night_recommendation = "Nachtfeuchte wird erhöht erwartet; FreshAirIQ beobachtet die Entwicklung weiter."
        else:
            night_recommendation = "Vorlüften ist aktuell nicht zwingend nötig."

        room_meta_for_house = {
            str(k): {"floor": r.get("floor"), "name": r.get("name", k)}
            for k, r in results.items()
        }
        # Learn the house strategy exactly once per completed house ventilation,
        # using every room session in that batch. Learning each room-close cycle
        # separately would fragment staggered multi-room ventilation into several
        # false "house" outcomes.
        if completed_house_sessions:
            completed_cross = any(bool(event.get("cross_ventilation")) for event in completed_house_sessions)
            if learn_house_outcome(
                self.store.data, completed_house_sessions, room_meta_for_house,
                cross=completed_cross, expected_occupants=float(occupancy.get("expected_total", 0.0)), observed_at=now,
            ):
                changed = True

        # Recommendation Engine v2: collapse all room diagnostics into one
        # prioritised house action. Room diagnostics remain available in the
        # room view, but the main dashboard no longer presents competing calls
        # to action.
        intelligent_recommendation = build_recommendation(
            results,
            options,
            threshold_ml=ventilation_threshold,
            total_potential_ml=realistic_actionable_potential,
            recommended_duration_min=recommended,
            pollen_index=pollen,
            pollen_blocked=bool(getattr(self, "_pollen_only_blocked", pollen_blocked)),
            outdoor_pm25=getattr(self, "_outdoor_pm25", None),
            outdoor_pm25_blocked=bool(getattr(self, "_outdoor_pm25_blocked", False)),
            night_forecast_ml=night_forecast,
        )
        intelligent_recommendation = refine_with_anticipation(
            intelligent_recommendation, results, options, now
        )
        intelligent_recommendation = build_decision_simulation(
            results, options, intelligent_recommendation,
            night_forecast_ml=night_forecast, night_confidence=night_confidence,
            future_outdoor=future_outdoor, now=now,
        )
        intelligent_recommendation = refine_live_recommendation(
            results, options, intelligent_recommendation
        )
        day_night_plan = build_multi_hour_plan(
            results, options, now,
            future_outdoor=planning_outdoor,
            night_forecast_ml=night_forecast,
            night_confidence=night_confidence,
            horizon_hours=8.0,
        )
        intelligent_recommendation = refine_with_plan(
            intelligent_recommendation, day_night_plan
        )
        house_fit = house_strategy_fit(
            self.store.data,
            [str(x) for x in (intelligent_recommendation.get("room_keys") or [])],
            room_meta_for_house,
            cross=cross,
            expected_occupants=float(occupancy.get("expected_total", 0.0)),
        )
        intelligent_recommendation["house_strategy"] = house_fit
        if float(house_fit.get("maturity", 0.0) or 0.0) >= 20.0:
            reasons = list(intelligent_recommendation.get("reasons") or [])
            if float(house_fit.get("efficiency_factor", 1.0) or 1.0) >= 1.10:
                reasons.append("Hauslernen: diese Raum-/Etagenstrategie war bisher überdurchschnittlich effizient")
            elif float(house_fit.get("efficiency_factor", 1.0) or 1.0) <= 0.90:
                reasons.append("Hauslernen: diese Raum-/Etagenstrategie war bisher eher unterdurchschnittlich effizient")
            intelligent_recommendation["reasons"] = reasons[:6]

        # Hotfix 0.17.0.8: first make the technical recommendation final, then
        # render the user-facing Decision Brain from that canonical result.
        # No later layer may change kind/rooms/duration after Decision Brain.
        intelligent_recommendation = stabilise_recommendation(
            intelligent_recommendation, results, options,
            previous=getattr(self, "_last_final_recommendation", None),
        )
        self._last_final_recommendation = {
            "kind": intelligent_recommendation.get("kind"),
            "room_keys": list(intelligent_recommendation.get("room_keys") or []),
        }
        intelligent_recommendation = build_unified_decision(
            intelligent_recommendation, results, options, cross_active=cross,
            night_strategy=night_strategy,
        )
        return changed, day_night_plan, intelligent_recommendation, night_recommendation
