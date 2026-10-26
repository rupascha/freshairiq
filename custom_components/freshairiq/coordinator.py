"""Coordinator for FreshAirIQ."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from time import perf_counter
from math import cos, pi
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .live_settings import room_structure
from .const import *
from .climate_sources import aggregate_states, entity_ids, climate_report_snapshot, advance_climate_report_activity, participating_climate_entities
from .energy import energy_price_per_kwh_equivalent, exchanged_air_fraction, heating_cost_context, ventilation_cost, ventilation_cost_for_temperature_path
from .forecast import effective_night_rate_ml_h, estimated_daily_moisture_ml, horizon_forecast, in_night_window, night_interval_bounds, night_window_hours, overnight_forecast_ml, update_night_learning
from .weather_now import weather_now
from . import cover_guard
from .outdoor_air import outdoor_pm25_blocked, outdoor_pm25_limit, plausible_pm25, pm25_reason, veto_cause as outdoor_veto_cause
from .model import (
    VENTILATION_HYSTERESIS_DELTA_G_M3,
    VENTILATION_HYSTERESIS_RH,
    SUMMER_WARMING_CLOSE_REASON,
    RoomInput,
    absolute_humidity,
    evaluate_room,
    scaled_min_return,
    update_learning,
)
from .moisture_source import update_moisture_source
from .notifications import process_notifications
from .presence import presence_diagnostics, resolve_occupancy
from .recommendation import build_recommendation
from .opening_strategy import enrich_opening_recommendation, house_aligned_room_actions, keep_moisture_sources_open, synchronize_room_presentation_actions
from .opening_state import normalize_opening_state, opening_contact_profile, aggregate_opening_mode, specialist_opening_provenance, stabilise_explicit_mode, update_passage_pattern, stable_state_seconds
from .personal_context import build_resident_context, personalise_recommendation
from .language_confidence import adapt_language_confidence
from .automation_events import AutomationEventEmitter
from .live_coach import refine_live_recommendation
from .anticipation import refine_with_anticipation
from .planner import build_multi_hour_plan, refine_with_plan
from .passive_ventilation import evaluate_passive_ventilation, learn_passive_exchange
from .intelligence import (
    build_intelligence_state, clear_session_behaviour, ensure_behaviour_defaults,
    learn_completed_session, learn_outcome_feedback, mark_recommendation_followed, sync_active_recommendation,
)
from .storage import LearningStore
from .decision import build_decision_simulation
from .weather_future import (
    FORECAST_REFRESH_SECONDS,
    async_hourly_forecast,
    forecast_retry_delay_seconds,
    future_boundaries,
)
from .routines import expected_source_rate, learn_source_pattern, project_generation_ml, response_pattern, routine_maturity
from .strategy import strategy_maturity
from .seasonality import learn_seasonal_source, seasonal_context
from .house_strategy import learn_house_outcome, house_strategy_fit, house_maturity
from .consolidation import session_target_min as _session_target_min, stabilise_recommendation
from .decision_brain import build_unified_decision
from .decision_trace import build_decision_trace, build_recommendation_quality
from .diagnostics import FreshAirIQDiagnosticsRecorder
from .telemetry import FreshAirIQDiagnosticsClient
from .runtime_health import RuntimeHealthMonitor
from .guardian import evaluate_guardian
from .ventilation_result import append_completed_sessions, finalise_ventilation_group, include_ventilation_group_start, new_ventilation_group, update_session_cross_tracking
from .ventilation_log import append_ventilation_log
from .forecast_validation import (
    append_validation_record,
    build_validation_record,
    evaluate_start_forecast_at_duration,
    freeze_start_forecast_context,
    prediction_duration_comparable,
    validation_summary,
)
from .forecast_backtest import backtest_summary
from .learning_effectiveness import (
    baseline_context_from_start,
    build_effectiveness_sample,
    freeze_learning_effectiveness_context,
    learning_effectiveness_summary,
    previous_model_context_from_start,
)
from .measurement_frame import build_measurement_frame, last_valid_session_measurement, report_timestamp_after_boundary, session_measurement_quality, trusted_session_end_baseline
from .post_stabilization import start_post_close_observation, update_post_close_observation, prune_history as prune_stabilization_history, stabilization_summary
from .learning_components import build_learning_components_status
from .learning_v2 import build_learning_v2_status
from .robustness import RobustnessMonitor, finite_float, prepare_runtime_rooms, safe_options
from .intervention import build_interventions, voc_scale
from .sun_exposure import (
    DEFAULT_SHADE_FORECAST_MAX_C,
    DEFAULT_SHADE_LEAD_MIN,
    DEFAULT_SHADE_MAX_CLOUD_COVERAGE,
    forecast_max_today,
    shading_plan,
    solar_position,
    sun_position,
)
from .goals import effective_temperature_target, evaluate_goals, normalise_disabled_goals
from .house_decision import build_night_strategy, floor_ventilation_decision, house_status_fallback, ventilation_threshold_decision
from .repairs import async_sync_missing_entity_issue
from .localize import Translator, is_german, protected_names
from .sensor_recovery import advance_sensor_recovery
# The coordinator is split into the coordinator_* modules (mixins and helpers); every name that
# used to live here stays importable from this module.
from .coordinator_sources import _entity_active, _exhaust_stopped_for_seconds, _float_state, _pollen_level, _outdoor_pm25_level, _cover_learning_guard, _aggregate_state_proxy, _state_report_timestamp, _weather_values, _weather_wind  # noqa: F401 - re-exported
from .coordinator_contacts import _contact_ids, _contact_specific_reference, _opening_assessments, _open_seconds, _room_contacts_known, _room_physical_opened_at, _contact_unknown_for, _room_closed_for_seconds, _room_ventilation_state, _cover_openings, _ORIENTATION_DEG, _orientation_factor, _room_orientation_factor  # noqa: F401 - re-exported
from .room_recommendation import _recommendation  # noqa: F401 - re-exported
from .coordinator_listeners import CoordinatorListenersMixin
from .coordinator_session_events import SessionEventsMixin
from .coordinator_sessions import SessionFinishMixin
from .coordinator_session_validation import SessionValidationMixin
from .coordinator_house import HouseStageMixin
from .coordinator_night import NightStageMixin
from .coordinator_decision import HouseDecisionMixin
from .coordinator_room import RoomEvaluationMixin
from .coordinator_room_contacts import RoomContactsMixin
from .coordinator_room_session import RoomSessionMixin
from .coordinator_room_model import RoomModelMixin
from .coordinator_room_result import RoomResultMixin

if TYPE_CHECKING:
    from .typing import FreshAirIQConfigEntry

_LOGGER = logging.getLogger(__name__)


class FreshAirIQCoordinator(
    RoomResultMixin,
    RoomModelMixin,
    RoomSessionMixin,
    RoomContactsMixin,
    RoomEvaluationMixin,
    HouseDecisionMixin,
    NightStageMixin,
    HouseStageMixin,
    SessionValidationMixin,
    SessionFinishMixin,
    SessionEventsMixin,
    CoordinatorListenersMixin,
    DataUpdateCoordinator[dict[str, Any]],
):
    """FreshAirIQ update coordinator; the phases live in the coordinator_* mixin modules."""
    def __init__(self, hass: HomeAssistant, entry: "FreshAirIQConfigEntry", store: LearningStore) -> None:
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN,
                         update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL), config_entry=entry)
        self.entry = entry; self.store = store; self._unsub_state = None; self._first_update = True
        self._contact_entities: set[str] = set()
        self._listened_sources: frozenset[str] = frozenset()
        # 0.26.5.3: what the running integration was set up with (live_settings)
        self._room_structure = room_structure(entry.data)
        self._applied_options = dict(entry.options)
        self._contact_confirm_unsubs: dict[str, Any] = {}
        self._final_measurement_unsubs: dict[str, Any] = {}
        # 0.26.5.1: last shading plan per room (runtime only, not persisted)
        self._shading_memory: dict[str, dict[str, Any]] = {}
        self._refresh_coalesce_unsub = None
        self._hourly_forecast_cache: list[dict[str, Any]] = []
        self._hourly_forecast_fetched_at: datetime | None = None
        self._hourly_forecast_failures = 0
        self._outdoor_pm25: float | None = None
        self._outdoor_pm25_blocked = False
        self._pollen_only_blocked = False
        self.diagnostics = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, VERSION)
        self.robustness = RobustnessMonitor()
        self.runtime_health = RuntimeHealthMonitor()
        self.telemetry = FreshAirIQDiagnosticsClient(
            hass,
            entry,
            self.diagnostics,
            health_provider=lambda: {
                "robustness": self.robustness.snapshot(),
                "diagnostics": self.diagnostics.status,
                "runtime_health": self.runtime_health.snapshot,
            },
            health_snapshot_provider=lambda now: {
                "captured_at": now.isoformat(),
                "robustness": self.robustness.snapshot(),
                "diagnostics": self.diagnostics.status,
                "runtime_health": self.runtime_health.health_snapshot(now),
            },
        )
        self._unavailable_required_sources: set[str] = set()
        self.automation_events = AutomationEventEmitter(
            lambda event_type, payload: self.hass.bus.async_fire(event_type, payload), entry.entry_id
        )
        self._unsub_automation_events = None
        # F01: last final house decision (kind + rooms) for the close hysteresis.
        self._last_final_recommendation: dict[str, Any] | None = None
        # Short source outages are common while HA integrations (for example MQTT/Zigbee)
        # restore after startup. Keep them separate from persistent sensor failures.
        self._sensor_recovery_started_at: datetime | None = None
        self._sensor_recovery_valid_cycles = 0
        self._sensor_recovery_grace_seconds = 90
        self._sensor_recovery_required_valid_cycles = 2


    @property
    def options(self) -> dict[str, Any]:
        options, repaired = safe_options(DEFAULT_OPTIONS, dict(self.entry.options))
        self.robustness.repaired_option_keys = repaired
        return options


    async def _async_update_data(self) -> dict[str, Any]:
        """Run one update transaction and degrade cleanly on unexpected failures."""
        started = dt_util.now()
        try:
            data = await self._async_update_data_impl()
        except UpdateFailed as exc:
            self.robustness.failure(started, exc)
            raise
        except Exception as exc:  # noqa: BLE001 - coordinator must fail closed, not crash HA
            self.robustness.failure(started, exc)
            self.runtime_health.record_exception("coordinator", "update", exc, started)
            raise UpdateFailed(
                f"FreshAirIQ update failed safely ({type(exc).__name__}); previous coordinator data is retained"
            ) from exc
        self.robustness.success(started)
        finished = dt_util.now()
        try:
            duration_ms = max((finished - started).total_seconds() * 1000.0, 0.0)
            self.runtime_health.observe_metric("coordinator_update_ms", duration_ms, finished, unit="ms")
        except (TypeError, ValueError, OverflowError):
            pass
        # Repair issues represent configuration that requires user action, not
        # transient sensor unavailability. The helper checks both HA state and
        # entity registry before creating an issue.
        try:
            async_sync_missing_entity_issue(self.hass, self.entry)
        except Exception:  # noqa: BLE001 - Repairs must never break the control loop
            _LOGGER.debug("Could not synchronize FreshAirIQ repair issues", exc_info=True)
        data["runtime_robustness"] = self.robustness.snapshot()
        return self._localize_output(data)

    def _localize_output(self, data: dict[str, Any]) -> dict[str, Any]:
        """Publish English texts for every Home Assistant language except German.

        The decision logic always runs in German; only the published copy is
        translated, so learning state and decisions stay identical (0.26.4.5).
        """
        language = getattr(getattr(self.hass, "config", None), "language", None)
        if not isinstance(language, str) or is_german(language):
            # 0.26.5.0: the dashboard follows the language of these texts, so a
            # German profile on an English server never mixes both languages.
            data["output_language"] = "de"
            return data
        try:
            protected = frozenset(protected_names(self.entry.data, self.options))
            translator = getattr(self, "_output_translator", None)
            if translator is None or getattr(self, "_output_protected", None) != protected:
                translator = Translator(protected)
                self._output_translator = translator
                self._output_protected = protected
            localized = translator.payload(data)
        except Exception:  # noqa: BLE001 - translation must never break the update cycle
            _LOGGER.debug("FreshAirIQ output translation failed; publishing German texts", exc_info=True)
            return data
        localized["output_language"] = "en"
        return localized

    async def _async_update_data_impl(self) -> dict[str, Any]:
        _phase_started = perf_counter()
        self._log_required_source_availability()
        options = self.options
        occupancy = resolve_occupancy(options, self.hass.states.get, dt_util.now())
        effective_adults = float(occupancy["expected_adults"])
        effective_children = float(occupancy["expected_children"])
        outdoor_weather_entity = self.entry.data.get(CONF_OUTDOOR_WEATHER)
        outdoor_weather_state = self.hass.states.get(outdoor_weather_entity) if outdoor_weather_entity else None
        outdoor_t, outdoor_rh = _weather_values(self.hass, outdoor_weather_entity)
        outdoor_temp_entity = self.entry.data.get(CONF_OUTDOOR_TEMPERATURE)
        outdoor_humidity_entity = self.entry.data.get(CONF_OUTDOOR_HUMIDITY)
        outdoor_temp_state = self.hass.states.get(outdoor_temp_entity) if outdoor_temp_entity else outdoor_weather_state
        outdoor_humidity_state = self.hass.states.get(outdoor_humidity_entity) if outdoor_humidity_entity else outdoor_weather_state
        sensor_t = _float_state(self.hass, outdoor_temp_entity); sensor_rh = _float_state(self.hass, outdoor_humidity_entity)
        if sensor_t is not None: outdoor_t = sensor_t
        if sensor_rh is not None: outdoor_rh = sensor_rh
        wind_bearing, wind_speed = _weather_wind(self.hass, self.entry.data.get(CONF_OUTDOOR_WEATHER))
        pollen = _pollen_level(self.hass, self.entry.data.get(CONF_POLLEN_ENTITY))
        # 0.26.4.7 (user feedback): outdoor fine dust protection.
        outdoor_pm25 = _outdoor_pm25_level(self.hass, self.entry.data.get(CONF_OUTDOOR_PM25_ENTITY))
        self._outdoor_pm25 = outdoor_pm25
        self._outdoor_pm25_blocked = outdoor_pm25_blocked(options, outdoor_pm25)
        now = dt_util.now(); results: dict[str, Any] = {}; changed = False; completed_sessions = []
        # Sensor recovery guard: integrations can restore after FreshAirIQ during a HA
        # restart. A brief all-source unavailable phase must not become a support
        # incident or a false sensor_error. Persistent failures still surface after
        # the grace period. After recovery, require two valid coordinator cycles
        # before normal recommendations resume.
        required_unavailable = bool(self._unavailable_required_sources)
        (
            self._sensor_recovery_started_at,
            self._sensor_recovery_valid_cycles,
            sensor_recovery_grace,
        ) = advance_sensor_recovery(
            self._sensor_recovery_started_at,
            self._sensor_recovery_valid_cycles,
            required_unavailable=required_unavailable, now=now,
            grace_seconds=self._sensor_recovery_grace_seconds,
            required_valid_cycles=self._sensor_recovery_required_valid_cycles,
        )
        completed_house_sessions: list[dict[str, Any]] = []
        (
            cross, forecast_outdoor_steps, future_outdoor, planning_outdoor, weather_situation,
        ) = await self._async_outdoor_forecast(
            now=now, outdoor_rh=outdoor_rh, outdoor_t=outdoor_t, outdoor_weather_state=outdoor_weather_state,
        )

        (
            _learning_effectiveness_pre, calc_volume_total, changed, daily_generation_prior, forecast_horizon,
            rooms_cfg, ventilation_group,
        ) = await self._async_evaluate_rooms(
            changed=changed, completed_sessions=completed_sessions, cross=cross,
            effective_adults=effective_adults, effective_children=effective_children,
            forecast_outdoor_steps=forecast_outdoor_steps, future_outdoor=future_outdoor, now=now,
            options=options, outdoor_humidity_entity=outdoor_humidity_entity,
            outdoor_humidity_state=outdoor_humidity_state, outdoor_rh=outdoor_rh, outdoor_t=outdoor_t,
            outdoor_temp_entity=outdoor_temp_entity, outdoor_temp_state=outdoor_temp_state, pollen=pollen,
            results=results, wind_bearing=wind_bearing, wind_speed=wind_speed,
        )

        valid_all = [r for r in results.values() if r["data_quality"] == "ok"]
        valid = [r for r in valid_all if r.get("calculation_enabled", True)]
        bad = [r for r in results.values() if r["data_quality"] != "ok" and r.get("calculation_enabled", True)]
        active = [r for r in valid if r["active"]]; close = [r for r in valid if r["action"] == "Close"]

        (changed,) = self._apply_passive_ventilation(
            active=active, changed=changed, now=now, options=options, results=results, rooms_cfg=rooms_cfg,
            ventilation_group=ventilation_group,
        )
        (changed, completed_house_sessions) = self._close_ventilation_group(
            changed=changed, completed_house_sessions=completed_house_sessions,
            completed_sessions=completed_sessions, now=now, rooms_cfg=rooms_cfg,
            ventilation_group=ventilation_group,
        )

        (
            actionable_potential, changed, confidence, cooling, current_daily_generation,
            expected_daily_generation, forecast_confidence, forecast_cost, forecast_effect, forecast_heat,
            forecast_live_adapted, forecast_live_observation_weight, forecast_optimal_close_in_min,
            forecast_target_limited, forecast_temp, forecast_uncapped_effect, live, max_elapsed, max_surface,
            moisture_gain_next5, next5_effect, outdoor_air_cause, pollen_blocked, pollen_only_blocked,
            potential, realistic_actionable_potential, realistic_house_effect, recommended, remaining,
            stats_days, status, temp_live, threshold_mode, threshold_reason, total_water,
            ventilation_threshold,
        ) = self._house_aggregates(
            active=active, bad=bad, changed=changed, close=close, cross=cross,
            effective_adults=effective_adults, effective_children=effective_children, now=now,
            options=options, outdoor_t=outdoor_t, pollen=pollen, sensor_recovery_grace=sensor_recovery_grace,
            valid=valid,
        )

        (
            changed, night_buffer, night_confidence, night_forecast, night_forecast_base, night_hours,
            night_samples, night_strategy, routine_night_adjustment, routine_night_maturity,
            routine_night_projection, trend_effect, weather_effect,
        ) = self._night_outlook(
            actionable_potential=actionable_potential, active=active, calc_volume_total=calc_volume_total,
            changed=changed, cross=cross, daily_generation_prior=daily_generation_prior,
            effective_adults=effective_adults, effective_children=effective_children, now=now,
            occupancy=occupancy, options=options, outdoor_rh=outdoor_rh, outdoor_t=outdoor_t,
            recommended=recommended, total_water=total_water, valid=valid,
        )

        return await self._async_decide_and_publish(
            _learning_effectiveness_pre=_learning_effectiveness_pre, _phase_started=_phase_started,
            actionable_potential=actionable_potential, active=active, changed=changed,
            completed_house_sessions=completed_house_sessions, completed_sessions=completed_sessions,
            confidence=confidence, cooling=cooling, cross=cross,
            current_daily_generation=current_daily_generation, effective_adults=effective_adults,
            effective_children=effective_children, expected_daily_generation=expected_daily_generation,
            forecast_confidence=forecast_confidence, forecast_cost=forecast_cost,
            forecast_effect=forecast_effect, forecast_heat=forecast_heat, forecast_horizon=forecast_horizon,
            forecast_live_adapted=forecast_live_adapted,
            forecast_live_observation_weight=forecast_live_observation_weight,
            forecast_optimal_close_in_min=forecast_optimal_close_in_min,
            forecast_target_limited=forecast_target_limited, forecast_temp=forecast_temp,
            forecast_uncapped_effect=forecast_uncapped_effect, future_outdoor=future_outdoor, live=live,
            max_elapsed=max_elapsed, max_surface=max_surface, moisture_gain_next5=moisture_gain_next5,
            next5_effect=next5_effect, night_buffer=night_buffer, night_confidence=night_confidence,
            night_forecast=night_forecast, night_forecast_base=night_forecast_base, night_hours=night_hours,
            night_samples=night_samples, night_strategy=night_strategy, now=now, occupancy=occupancy,
            options=options, outdoor_air_cause=outdoor_air_cause, outdoor_pm25=outdoor_pm25,
            outdoor_rh=outdoor_rh, outdoor_t=outdoor_t, planning_outdoor=planning_outdoor, pollen=pollen,
            pollen_blocked=pollen_blocked, pollen_only_blocked=pollen_only_blocked, potential=potential,
            realistic_actionable_potential=realistic_actionable_potential,
            realistic_house_effect=realistic_house_effect, recommended=recommended, remaining=remaining,
            results=results, rooms_cfg=rooms_cfg, routine_night_adjustment=routine_night_adjustment,
            routine_night_maturity=routine_night_maturity, routine_night_projection=routine_night_projection,
            sensor_recovery_grace=sensor_recovery_grace, stats_days=stats_days, status=status,
            temp_live=temp_live, threshold_mode=threshold_mode, threshold_reason=threshold_reason,
            total_water=total_water, trend_effect=trend_effect, valid=valid,
            ventilation_threshold=ventilation_threshold, weather_effect=weather_effect,
            weather_situation=weather_situation, wind_bearing=wind_bearing, wind_speed=wind_speed,
        )

    async def _async_evaluate_rooms(
        self,
        *,
        changed: Any, completed_sessions: Any, cross: Any, effective_adults: Any, effective_children: Any,
        forecast_outdoor_steps: Any, future_outdoor: Any, now: Any, options: Any,
        outdoor_humidity_entity: Any, outdoor_humidity_state: Any, outdoor_rh: Any, outdoor_t: Any,
        outdoor_temp_entity: Any, outdoor_temp_state: Any, pollen: Any, results: Any, wind_bearing: Any,
        wind_speed: Any,
    ) -> Any:
        """Room stage: prepare the room configuration, restore the house group and evaluate every room."""
        rooms_cfg, runtime_room_issues = prepare_runtime_rooms(self.entry.data.get(CONF_ROOMS, []))
        self.robustness.runtime_config_issues = runtime_room_issues
        rooms_cfg = sorted(rooms_cfg, key=lambda r: (int(r.get(CONF_ROOM_SORT_ORDER, 9999)), r.get("name", "")))
        ventilation_group = self.store.data.get("ventilation_group")
        (changed, ventilation_group) = self._restore_ventilation_group(
            changed=changed, rooms_cfg=rooms_cfg, ventilation_group=ventilation_group,
        )
        calc_volume_total = sum(
            max(float(r.get(CONF_ROOM_VOLUME, 0.0) or 0.0), 0.0)
            for r in rooms_cfg if r.get(CONF_ROOM_INCLUDE_CALCULATIONS, True)
        )
        daily_generation_prior = float(estimated_daily_moisture_ml(options, effective_adults, effective_children))
        forecast_horizon = int(round(min(max(float(options.get("forecast_horizon_min", 5)), 1.0), 120.0)))
        # Learning Engine V2 safety authority: objective paired field evidence
        # may temporarily revoke learned forecast terms. Physics remains the
        # deterministic fallback until evidence stops showing regression.
        _learning_effectiveness_pre = learning_effectiveness_summary(
            self.store.data.get("forecast_validation_history") or [], days=30
        )
        _learning_v2_force_physics = str(_learning_effectiveness_pre.get("status") or "") == "regressing"
        voc_sensor_enabled = bool(options.get("voc_sensor_enabled", True))
        pm25_sensor_enabled = bool(options.get("pm25_sensor_enabled", True))
        illuminance_sensor_enabled = bool(options.get("illuminance_sensor_enabled", True))
        for idx, cfg in enumerate(rooms_cfg):
            changed, ventilation_group = await self._async_evaluate_room(
                idx, cfg, changed=changed, ventilation_group=ventilation_group,
                _learning_v2_force_physics=_learning_v2_force_physics, calc_volume_total=calc_volume_total,
                completed_sessions=completed_sessions, cross=cross,
                daily_generation_prior=daily_generation_prior, forecast_horizon=forecast_horizon,
                forecast_outdoor_steps=forecast_outdoor_steps, future_outdoor=future_outdoor,
                illuminance_sensor_enabled=illuminance_sensor_enabled, now=now, options=options,
                outdoor_humidity_entity=outdoor_humidity_entity,
                outdoor_humidity_state=outdoor_humidity_state, outdoor_rh=outdoor_rh, outdoor_t=outdoor_t,
                outdoor_temp_entity=outdoor_temp_entity, outdoor_temp_state=outdoor_temp_state,
                pm25_sensor_enabled=pm25_sensor_enabled, pollen=pollen, results=results,
                voc_sensor_enabled=voc_sensor_enabled, wind_bearing=wind_bearing, wind_speed=wind_speed,
            )
        return (
            _learning_effectiveness_pre, calc_volume_total, changed, daily_generation_prior, forecast_horizon,
            rooms_cfg, ventilation_group,
        )

    async def _async_decide_and_publish(
        self,
        *,
        _learning_effectiveness_pre: Any, _phase_started: Any, actionable_potential: Any, active: Any,
        changed: Any, completed_house_sessions: Any, completed_sessions: Any, confidence: Any, cooling: Any,
        cross: Any, current_daily_generation: Any, effective_adults: Any, effective_children: Any,
        expected_daily_generation: Any, forecast_confidence: Any, forecast_cost: Any, forecast_effect: Any,
        forecast_heat: Any, forecast_horizon: Any, forecast_live_adapted: Any,
        forecast_live_observation_weight: Any, forecast_optimal_close_in_min: Any,
        forecast_target_limited: Any, forecast_temp: Any, forecast_uncapped_effect: Any, future_outdoor: Any,
        live: Any, max_elapsed: Any, max_surface: Any, moisture_gain_next5: Any, next5_effect: Any,
        night_buffer: Any, night_confidence: Any, night_forecast: Any, night_forecast_base: Any,
        night_hours: Any, night_samples: Any, night_strategy: Any, now: Any, occupancy: Any, options: Any,
        outdoor_air_cause: Any, outdoor_pm25: Any, outdoor_rh: Any, outdoor_t: Any, planning_outdoor: Any,
        pollen: Any, pollen_blocked: Any, pollen_only_blocked: Any, potential: Any,
        realistic_actionable_potential: Any, realistic_house_effect: Any, recommended: Any, remaining: Any,
        results: Any, rooms_cfg: Any, routine_night_adjustment: Any, routine_night_maturity: Any,
        routine_night_projection: Any, sensor_recovery_grace: Any, stats_days: Any, status: Any,
        temp_live: Any, threshold_mode: Any, threshold_reason: Any, total_water: Any, trend_effect: Any,
        valid: Any, ventilation_threshold: Any, weather_effect: Any, weather_situation: Any,
        wind_bearing: Any, wind_speed: Any,
    ) -> Any:
        """House stage: final recommendation, presentation, status extras and the published payload."""
        (changed, day_night_plan, intelligent_recommendation, night_recommendation) = self._house_recommendation_and_plan(
            changed=changed, completed_house_sessions=completed_house_sessions, cross=cross,
            future_outdoor=future_outdoor, night_buffer=night_buffer, night_confidence=night_confidence,
            night_forecast=night_forecast, night_strategy=night_strategy, now=now, occupancy=occupancy,
            options=options, planning_outdoor=planning_outdoor, pollen=pollen, pollen_blocked=pollen_blocked,
            realistic_actionable_potential=realistic_actionable_potential, recommended=recommended,
            results=results, ventilation_threshold=ventilation_threshold,
        )
        (
            _decision_validation, active_ratio, changed, displayed_recommended, floor_display_name,
            floor_ventilation_mode, forecast_effect, house_ventilation_mode, intelligent_recommendation,
            iq_state, next5_effect, remaining, status, status_text,
        ) = self._finalise_house_recommendation(
            active=active, changed=changed, cross=cross, forecast_confidence=forecast_confidence,
            forecast_cost=forecast_cost, forecast_effect=forecast_effect, forecast_horizon=forecast_horizon,
            intelligent_recommendation=intelligent_recommendation, max_elapsed=max_elapsed,
            next5_effect=next5_effect, night_confidence=night_confidence, night_samples=night_samples,
            night_strategy=night_strategy, now=now, occupancy=occupancy, options=options,
            recommended=recommended, remaining=remaining, results=results, status=status, valid=valid,
        )

        (
            adults, children, expected_generated_so_far, finalizing_measurements, forecast_backtest_status,
            forecast_validation_status, history, history_summary, learning_components_status,
            learning_effectiveness_status, learning_v2_status, moisture_balance_today, post_close_status,
            system_check,
        ) = self._house_status_extras(
            _decision_validation=_decision_validation,
            _learning_effectiveness_pre=_learning_effectiveness_pre,
            current_daily_generation=current_daily_generation, future_outdoor=future_outdoor,
            night_samples=night_samples, now=now, options=options, outdoor_rh=outdoor_rh, outdoor_t=outdoor_t,
            results=results, routine_night_maturity=routine_night_maturity, stats_days=stats_days,
            valid=valid,
        )

        return await self._async_publish_house_data(
            _phase_started=_phase_started, actionable_potential=actionable_potential,
            active_ratio=active_ratio, adults=adults, changed=changed, children=children,
            completed_sessions=completed_sessions, confidence=confidence, cooling=cooling, cross=cross,
            current_daily_generation=current_daily_generation, day_night_plan=day_night_plan,
            displayed_recommended=displayed_recommended, effective_adults=effective_adults,
            effective_children=effective_children, expected_daily_generation=expected_daily_generation,
            expected_generated_so_far=expected_generated_so_far,
            finalizing_measurements=finalizing_measurements, floor_display_name=floor_display_name,
            floor_ventilation_mode=floor_ventilation_mode, forecast_backtest_status=forecast_backtest_status,
            forecast_confidence=forecast_confidence, forecast_cost=forecast_cost,
            forecast_effect=forecast_effect, forecast_heat=forecast_heat, forecast_horizon=forecast_horizon,
            forecast_live_adapted=forecast_live_adapted,
            forecast_live_observation_weight=forecast_live_observation_weight,
            forecast_optimal_close_in_min=forecast_optimal_close_in_min,
            forecast_target_limited=forecast_target_limited, forecast_temp=forecast_temp,
            forecast_uncapped_effect=forecast_uncapped_effect,
            forecast_validation_status=forecast_validation_status, future_outdoor=future_outdoor,
            history=history, history_summary=history_summary, house_ventilation_mode=house_ventilation_mode,
            intelligent_recommendation=intelligent_recommendation, iq_state=iq_state,
            learning_components_status=learning_components_status,
            learning_effectiveness_status=learning_effectiveness_status,
            learning_v2_status=learning_v2_status, live=live, max_surface=max_surface,
            moisture_balance_today=moisture_balance_today, moisture_gain_next5=moisture_gain_next5,
            next5_effect=next5_effect, night_confidence=night_confidence, night_forecast=night_forecast,
            night_forecast_base=night_forecast_base, night_hours=night_hours,
            night_recommendation=night_recommendation, night_samples=night_samples,
            night_strategy=night_strategy, now=now, occupancy=occupancy, options=options,
            outdoor_air_cause=outdoor_air_cause, outdoor_pm25=outdoor_pm25, outdoor_rh=outdoor_rh,
            outdoor_t=outdoor_t, pollen=pollen, pollen_only_blocked=pollen_only_blocked,
            post_close_status=post_close_status, potential=potential,
            realistic_actionable_potential=realistic_actionable_potential,
            realistic_house_effect=realistic_house_effect, remaining=remaining, results=results,
            rooms_cfg=rooms_cfg, routine_night_adjustment=routine_night_adjustment,
            routine_night_maturity=routine_night_maturity, routine_night_projection=routine_night_projection,
            sensor_recovery_grace=sensor_recovery_grace, stats_days=stats_days, status=status,
            status_text=status_text, system_check=system_check, temp_live=temp_live,
            threshold_mode=threshold_mode, threshold_reason=threshold_reason, total_water=total_water,
            trend_effect=trend_effect, ventilation_threshold=ventilation_threshold,
            weather_effect=weather_effect, weather_situation=weather_situation, wind_bearing=wind_bearing,
            wind_speed=wind_speed,
        )


    async def _async_finalize_cycle(
        self,
        data: dict[str, Any],
        *,
        options: dict[str, Any],
        now: datetime,
        completed_sessions: list[dict[str, Any]],
        changed: bool,
        phase_started: float,
    ) -> dict[str, Any]:
        """Phase 4: guardian, notifications, persistence and diagnostics for one cycle."""
        _phase_started = phase_started
        _core_finished = perf_counter()
        self.runtime_health.observe_metric("coordinator_phase_core_ms", (_core_finished - _phase_started) * 1000.0, now, unit="ms")
        _guardian_started = perf_counter()
        guardian = evaluate_guardian(data)
        self.runtime_health.observe_metric("coordinator_phase_guardian_ms", (perf_counter() - _guardian_started) * 1000.0, now, unit="ms")
        # Guardian is observation-first. Only explicitly allow-listed, reversible
        # runtime repairs may mutate coordinator state. Never touch user config,
        # entity assignments or learned preferences here.
        self.runtime_health.reconcile_guardian_findings(
            guardian.get("findings") if isinstance(guardian.get("findings"), list) else [], now
        )
        if any(item.get("repair") == "clear_completed_sensor_recovery" for item in guardian.get("safe_repairs", []) if isinstance(item, dict)):
            self._sensor_recovery_started_at = None
            self._sensor_recovery_valid_cycles = 0
            guardian["auto_healed"] = ["clear_completed_sensor_recovery"]
            guardian["recovery_events"] = [{
                "repair": "clear_completed_sensor_recovery",
                "status": "success",
                "postcondition": "sensor_recovery_runtime_cleared",
                "postcondition_passed": self._sensor_recovery_started_at is None and self._sensor_recovery_valid_cycles == 0,
            }]
        else:
            guardian["auto_healed"] = []
            guardian["recovery_events"] = []
        data["guardian"] = guardian
        _notification_started = perf_counter()
        notification_changed = await process_notifications(self.hass, self.store, data, options, now, completed_sessions)
        self.runtime_health.observe_metric("coordinator_phase_notifications_ms", (perf_counter() - _notification_started) * 1000.0, now, unit="ms")
        changed = changed or notification_changed
        _persistence_started = perf_counter()
        if changed:
            # Completed sessions and notification bookkeeping are persisted at
            # once; routine learning/runtime updates are coalesced (0.26.4.6).
            if completed_sessions or notification_changed:
                await self.store.async_save()
            else:
                await self.store.async_save_deferred()
        self.runtime_health.observe_metric("coordinator_phase_persistence_ms", (perf_counter() - _persistence_started) * 1000.0, now, unit="ms")
        data["runtime_health"] = self.runtime_health.snapshot
        controller = getattr(self, "actuator_controller", None)
        data["fan_automation_trace"] = controller.fan_trace() if controller is not None else []  # 0.26.5.4
        _diagnostics_started = perf_counter()
        self.diagnostics.update_configuration_snapshot(self.entry.data, options, data, now)
        await self.diagnostics.async_record(data, self.store.data, now, completed_sessions)
        self.runtime_health.observe_metric("coordinator_phase_diagnostics_ms", (perf_counter() - _diagnostics_started) * 1000.0, now, unit="ms")
        data["diagnostics"] = self.diagnostics.status
        data["diagnostics_upload"] = self.telemetry.status
        self._first_update = False
        return data


