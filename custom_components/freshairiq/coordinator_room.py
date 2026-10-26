"""Per-room evaluation of the coordinator: sensor readings, stage order and room overlays."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTACT_COVERS,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_AIR_PURIFIER,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_COVERS,
    CONF_ROOM_DEHUMIDIFIER,
    CONF_ROOM_DISABLED_GOALS,
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_EXHAUST_FAN_CONTROL,
    CONF_ROOM_FLOOR,
    CONF_ROOM_HUMIDIFIER,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_HUMIDITY_AGGREGATION,
    CONF_ROOM_ICON,
    CONF_ROOM_ILLUMINANCE,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_MOISTURE_SOURCES,
    CONF_ROOM_NAME,
    CONF_ROOM_PM25,
    CONF_ROOM_REFERENCE_HUMIDITY,
    CONF_ROOM_REFERENCE_TEMPERATURE,
    CONF_ROOM_SUPPLY_FAN,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_TEMPERATURE_AGGREGATION,
    CONF_ROOM_VENTILATION_DEVICE,
    CONF_ROOM_VOC,
    CONF_ROOM_VOLUME,
    CONF_ROOM_WINDOW_ORIENTATION,
    CONTACT_MODE_ANY,
    ORIENTATION_UNKNOWN,
    PROFILE_SUMMER_COOLING,
)
from .automation_events import action_code
from .climate_sources import aggregate_states
from .coordinator_contacts import _contact_ids, _contact_specific_reference, _cover_openings
from .coordinator_sources import _aggregate_state_proxy, _float_state
from .goals import normalise_disabled_goals
from .intelligence import ensure_behaviour_defaults
from .exhaust_reference import NEIGHBOUR_REFERENCE_REASON
from .fan_automation import room_fan_automation
from .intervention import build_interventions, voc_scale
from .measurement_frame import build_measurement_frame
from .model import absolute_humidity
from .outdoor_air import outdoor_pm25_blocked
from .robustness import finite_float
from .sun_exposure import (
    DEFAULT_SHADE_FORECAST_MAX_C,
    DEFAULT_SHADE_LEAD_MIN,
    DEFAULT_SHADE_MAX_CLOUD_COVERAGE,
    forecast_max_today,
    shading_plan,
    solar_position,
    sun_position,
)


class RoomEvaluationMixin:
    """Per-room evaluation of the coordinator: sensor readings, stage order and room overlays."""

    hass: HomeAssistant  # provided by the coordinator

    def _fan_snapshot(self, key: str) -> dict[str, Any] | None:
        controller = getattr(self, "actuator_controller", None)
        return controller.fan_snapshot(key) if controller is not None else None

    def _shading_context(self, now: datetime, options: dict[str, Any], temperature: Any, comfort_target: Any) -> dict[str, Any]:
        """Sun now / after the lead time, expected heat and clouds for the shading plan (0.26.5.1)."""
        latitude = getattr(getattr(self.hass, "config", None), "latitude", None)
        longitude = getattr(getattr(self.hass, "config", None), "longitude", None)
        lead = timedelta(minutes=float(options.get("shade_lead_min", DEFAULT_SHADE_LEAD_MIN)))
        if isinstance(now, datetime) and now.tzinfo is not None and latitude is not None and longitude is not None:
            sun, sun_soon = solar_position(now, latitude, longitude), solar_position(now + lead, latitude, longitude)
        else:
            sun_state = self.hass.states.get("sun.sun")
            sun, sun_soon = sun_position(dict(sun_state.attributes) if sun_state else None), None
        weather_entity = self.entry.data.get(CONF_OUTDOOR_WEATHER)
        weather = self.hass.states.get(weather_entity) if weather_entity else None
        cloud = finite_float((weather.attributes or {}).get("cloud_coverage")) if weather is not None else None
        hottest = forecast_max_today(self._hourly_forecast_cache, now) if isinstance(now, datetime) and now.tzinfo is not None else None
        temperature = finite_float(temperature)
        target = finite_float(comfort_target)
        return {
            "sun": sun,
            "sun_soon": sun_soon,
            "heat_expected": bool(
                (hottest is not None and hottest >= float(options.get("shade_forecast_max_c", DEFAULT_SHADE_FORECAST_MAX_C)))
                or (temperature is not None and target is not None and temperature >= target)
            ),
            "cloudy": cloud is not None and cloud >= float(options.get("shade_max_cloud_coverage", DEFAULT_SHADE_MAX_CLOUD_COVERAGE)),
        }

    async def _async_evaluate_room(
        self, idx: int, cfg: dict[str, Any], *,
        changed: bool, ventilation_group: Any, _learning_v2_force_physics: Any, calc_volume_total: Any,
        completed_sessions: Any, cross: Any, daily_generation_prior: Any, forecast_horizon: Any,
        forecast_outdoor_steps: Any, future_outdoor: Any, illuminance_sensor_enabled: Any, now: Any,
        options: Any, outdoor_humidity_entity: Any, outdoor_humidity_state: Any, outdoor_rh: Any,
        outdoor_t: Any, outdoor_temp_entity: Any, outdoor_temp_state: Any, pm25_sensor_enabled: Any,
        pollen: Any, results: Any, voc_sensor_enabled: Any, wind_bearing: Any, wind_speed: Any,
    ) -> tuple[bool, Any]:
        """Phase 2: evaluate one room (measurement, session lifecycle, learning, recommendation).

        Writes the room result into ``results`` and finished sessions into
        ``completed_sessions`` (both shared with the caller). Returns the updated
        ``changed`` flag and the house-wide ``ventilation_group`` accumulator.
        """
        key = cfg["key"]; mem = self.store.room(key); ensure_behaviour_defaults(mem); include = bool(cfg.get(CONF_ROOM_INCLUDE_CALCULATIONS, True))
        outdoor_pm25 = getattr(self, "_outdoor_pm25", None)
        # v0.21.0.2: structure-only rooms are valid building metadata and may
        # intentionally have no climate/contact entities. Never dereference
        # mandatory climate keys before the calculation flag has been checked.
        if not include:
            return self._monitor_only_room_result(
                cfg=cfg, changed=changed, illuminance_sensor_enabled=illuminance_sensor_enabled, key=key,
                pm25_sensor_enabled=pm25_sensor_enabled, results=results, ventilation_group=ventilation_group,
                voc_sensor_enabled=voc_sensor_enabled,
            )
        (
            co2, co2_available, co2_display, co2_entity, default_ref_rh, default_ref_t,
            default_reference_humidity_entity, default_reference_temperature_entity, disabled_goals,
            humidity_entity, humidity_state, illuminance, illuminance_configured_entity, measurement_frame,
            pm25, pm25_configured_entity, ref_rh, ref_t, reference_humidity_entity,
            reference_temperature_entity, rh, t, temperature_entity, temperature_state, voc,
            voc_configured_entity, voc_unit_scale,
        ) = self._read_room_sensors(
            cfg=cfg, illuminance_sensor_enabled=illuminance_sensor_enabled, now=now,
            outdoor_humidity_entity=outdoor_humidity_entity, outdoor_humidity_state=outdoor_humidity_state,
            outdoor_rh=outdoor_rh, outdoor_t=outdoor_t, outdoor_temp_entity=outdoor_temp_entity,
            outdoor_temp_state=outdoor_temp_state, pm25_sensor_enabled=pm25_sensor_enabled,
            voc_sensor_enabled=voc_sensor_enabled,
        )
        (
            active_passage_contacts, changed, configured_contact_ids, contact_modes, contacts_known,
            explicit_three_state, explicit_tilted, opening_mode, passage_contacts, passage_door_active,
            proven_three_state, specialist_opening_mode, specialist_opening_signature, stable_since,
            three_state_stale_contacts, three_state_unknown_contacts, transition_suppressed,
        ) = self._stabilise_room_contacts(
            cfg=cfg, changed=changed, mem=mem, now=now,
        )
        (
            changed, confirmed_close_seconds, cover_learning_guard, is_open, measurement_frame,
            mechanical_exhaust_active, physical_contact_modes, raw_contact_open, raw_open_seconds, ref_rh,
            ref_t, reference_humidity_entity, reference_temperature_entity, rh, session_should,
            stable_session_modes, t,
        ) = self._room_session_contact_state(
            cfg=cfg, changed=changed, configured_contact_ids=configured_contact_ids,
            contact_modes=contact_modes, default_ref_rh=default_ref_rh, default_ref_t=default_ref_t,
            default_reference_humidity_entity=default_reference_humidity_entity,
            default_reference_temperature_entity=default_reference_temperature_entity,
            humidity_state=humidity_state, mem=mem, now=now, outdoor_humidity_state=outdoor_humidity_state,
            outdoor_temp_state=outdoor_temp_state, proven_three_state=proven_three_state, rh=rh,
            stable_since=stable_since, t=t, temperature_state=temperature_state,
        )
        # 0.26.5.4 (review A04): the wall (mould) model keeps the default reference, whatever air is drawn in
        self.__dict__.setdefault("_wall_reference_t", {})[str(cfg.get("key") or "")] = default_ref_t

        (changed, measurements_valid, ventilation_group) = await self._async_room_session_lifecycle(
            active_passage_contacts=active_passage_contacts, cfg=cfg, changed=changed,
            completed_sessions=completed_sessions, confirmed_close_seconds=confirmed_close_seconds,
            contacts_known=contacts_known, cover_learning_guard=cover_learning_guard, cross=cross,
            humidity_entity=humidity_entity, humidity_state=humidity_state, include=include, key=key,
            measurement_frame=measurement_frame, mechanical_exhaust_active=mechanical_exhaust_active, mem=mem,
            now=now, opening_mode=opening_mode, options=options, passage_door_active=passage_door_active,
            raw_contact_open=raw_contact_open, ref_rh=ref_rh, ref_t=ref_t,
            reference_humidity_entity=reference_humidity_entity,
            reference_temperature_entity=reference_temperature_entity, rh=rh, session_should=session_should,
            specialist_opening_mode=specialist_opening_mode,
            specialist_opening_signature=specialist_opening_signature,
            stable_session_modes=stable_session_modes, stable_since=stable_since, t=t,
            temperature_entity=temperature_entity, temperature_state=temperature_state,
            three_state_stale_contacts=three_state_stale_contacts,
            three_state_unknown_contacts=three_state_unknown_contacts, ventilation_group=ventilation_group,
        )
        return self._evaluate_room_outputs(
            _learning_v2_force_physics=_learning_v2_force_physics, calc_volume_total=calc_volume_total,
            cfg=cfg, changed=changed, co2=co2, co2_available=co2_available, co2_display=co2_display,
            co2_entity=co2_entity, cover_learning_guard=cover_learning_guard, cross=cross,
            daily_generation_prior=daily_generation_prior, default_ref_rh=default_ref_rh,
            default_ref_t=default_ref_t, default_reference_humidity_entity=default_reference_humidity_entity,
            default_reference_temperature_entity=default_reference_temperature_entity,
            disabled_goals=disabled_goals, explicit_three_state=explicit_three_state,
            explicit_tilted=explicit_tilted, forecast_horizon=forecast_horizon,
            forecast_outdoor_steps=forecast_outdoor_steps, future_outdoor=future_outdoor, idx=idx,
            illuminance=illuminance, illuminance_configured_entity=illuminance_configured_entity,
            illuminance_sensor_enabled=illuminance_sensor_enabled, include=include, is_open=is_open, key=key,
            measurement_frame=measurement_frame, measurements_valid=measurements_valid,
            mechanical_exhaust_active=mechanical_exhaust_active, mem=mem, now=now, opening_mode=opening_mode,
            options=options, outdoor_pm25=outdoor_pm25, passage_contacts=passage_contacts,
            physical_contact_modes=physical_contact_modes, pm25=pm25,
            pm25_configured_entity=pm25_configured_entity, pm25_sensor_enabled=pm25_sensor_enabled,
            pollen=pollen, proven_three_state=proven_three_state, raw_contact_open=raw_contact_open,
            raw_open_seconds=raw_open_seconds, ref_rh=ref_rh, ref_t=ref_t,
            reference_humidity_entity=reference_humidity_entity,
            reference_temperature_entity=reference_temperature_entity, results=results, rh=rh,
            specialist_opening_mode=specialist_opening_mode, t=t,
            three_state_stale_contacts=three_state_stale_contacts,
            three_state_unknown_contacts=three_state_unknown_contacts,
            transition_suppressed=transition_suppressed, ventilation_group=ventilation_group, voc=voc,
            voc_configured_entity=voc_configured_entity, voc_sensor_enabled=voc_sensor_enabled,
            voc_unit_scale=voc_unit_scale, wind_bearing=wind_bearing, wind_speed=wind_speed,
        )

    def _evaluate_room_outputs(
        self,
        *,
        _learning_v2_force_physics: Any, calc_volume_total: Any, cfg: Any, changed: Any, co2: Any,
        co2_available: Any, co2_display: Any, co2_entity: Any, cover_learning_guard: Any, cross: Any,
        daily_generation_prior: Any, default_ref_rh: Any, default_ref_t: Any,
        default_reference_humidity_entity: Any, default_reference_temperature_entity: Any,
        disabled_goals: Any, explicit_three_state: Any, explicit_tilted: Any, forecast_horizon: Any,
        forecast_outdoor_steps: Any, future_outdoor: Any, idx: Any, illuminance: Any,
        illuminance_configured_entity: Any, illuminance_sensor_enabled: Any, include: Any, is_open: Any,
        key: Any, measurement_frame: Any, measurements_valid: Any, mechanical_exhaust_active: Any, mem: Any,
        now: Any, opening_mode: Any, options: Any, outdoor_pm25: Any, passage_contacts: Any,
        physical_contact_modes: Any, pm25: Any, pm25_configured_entity: Any, pm25_sensor_enabled: Any,
        pollen: Any, proven_three_state: Any, raw_contact_open: Any, raw_open_seconds: Any, ref_rh: Any,
        ref_t: Any, reference_humidity_entity: Any, reference_temperature_entity: Any, results: Any, rh: Any,
        specialist_opening_mode: Any, t: Any, three_state_stale_contacts: Any,
        three_state_unknown_contacts: Any, transition_suppressed: Any, ventilation_group: Any, voc: Any,
        voc_configured_entity: Any, voc_sensor_enabled: Any, voc_unit_scale: Any, wind_bearing: Any,
        wind_speed: Any,
    ) -> Any:
        """Room model, recommendation, forecast, goals and the published room result."""
        elapsed = 0.0
        (
            active_contact_reference, airflow, changed, effective_learning_rate, elapsed,
            has_ventilation_contact, moisture_source, result, room_input,
        ) = self._evaluate_room_model(
            cfg=cfg, changed=changed, co2=co2, cross=cross, disabled_goals=disabled_goals, elapsed=elapsed,
            future_outdoor=future_outdoor, is_open=is_open, key=key, measurement_frame=measurement_frame,
            measurements_valid=measurements_valid, mechanical_exhaust_active=mechanical_exhaust_active,
            mem=mem, now=now, opening_mode=opening_mode, options=options, outdoor_pm25=outdoor_pm25,
            physical_contact_modes=physical_contact_modes, pollen=pollen, raw_contact_open=raw_contact_open,
            raw_open_seconds=raw_open_seconds, ref_rh=ref_rh, ref_t=ref_t,
            reference_humidity_entity=reference_humidity_entity,
            reference_temperature_entity=reference_temperature_entity, rh=rh,
            specialist_opening_mode=specialist_opening_mode, t=t, wind_bearing=wind_bearing,
            wind_speed=wind_speed,
        )
        (
            changed, high_duration, humidity_trend, indirect_candidate, indirect_cooling_candidate,
            reason_list,
        ) = self._room_recommendation_state(
            airflow=airflow, cfg=cfg, changed=changed, co2=co2, cross=cross, explicit_tilted=explicit_tilted,
            has_ventilation_contact=has_ventilation_contact, is_open=is_open, mem=mem, now=now,
            options=options, outdoor_pm25=outdoor_pm25, pollen=pollen, ref_t=ref_t, result=result,
            room_input=room_input, t=t, wind_bearing=wind_bearing, wind_speed=wind_speed,
        )
        (
            cost, delivered, dynamic, dynamic5, fcost, fdel, ffuel, forecast_args, fpurchased, fuel,
            purchased, target_ah, temp_change,
        ) = self._room_forecast(
            _learning_v2_force_physics=_learning_v2_force_physics,
            active_contact_reference=active_contact_reference, airflow=airflow,
            calc_volume_total=calc_volume_total, cfg=cfg, cross=cross,
            daily_generation_prior=daily_generation_prior, effective_learning_rate=effective_learning_rate,
            elapsed=elapsed, forecast_horizon=forecast_horizon, forecast_outdoor_steps=forecast_outdoor_steps,
            is_open=is_open, measurement_frame=measurement_frame, mem=mem, moisture_source=moisture_source,
            now=now, opening_mode=opening_mode, options=options, ref_t=ref_t, result=result, t=t,
        )
        (changed,) = self._freeze_session_prediction(
            cfg=cfg, changed=changed, dynamic=dynamic, elapsed=elapsed, forecast_args=forecast_args,
            forecast_horizon=forecast_horizon, measurement_frame=measurement_frame, mem=mem, now=now,
            options=options, ref_rh=ref_rh, ref_t=ref_t, result=result, rh=rh, t=t,
        )

        (changed,) = self._room_session_forecast_timeline(
            cfg=cfg, changed=changed, dynamic=dynamic, dynamic5=dynamic5, elapsed=elapsed,
            forecast_args=forecast_args, key=key, measurement_frame=measurement_frame, mem=mem, now=now,
            options=options, result=result, rh=rh, t=t, target_ah=target_ah,
        )
        (
            changed, comfort_target, comfort_target_source, cooldown_demoted, cooldown_override, goal_state,
            humidity_rebound, minutes_since_vent, opening_assessments, recently_ventilated,
            room_threshold_effective_ml, room_threshold_mode, routine_response, routine_samples, season_ctx,
            seasonal_routine_rate, stabilizing,
        ) = self._room_cooldown_and_goals(
            cfg=cfg, changed=changed, co2=co2, co2_available=co2_available, default_ref_rh=default_ref_rh,
            default_ref_t=default_ref_t, default_reference_humidity_entity=default_reference_humidity_entity,
            default_reference_temperature_entity=default_reference_temperature_entity,
            disabled_goals=disabled_goals, include=include, is_open=is_open, mem=mem,
            moisture_source=moisture_source, now=now, options=options, outdoor_pm25=outdoor_pm25,
            physical_contact_modes=physical_contact_modes, pollen=pollen, reason_list=reason_list,
            ref_t=ref_t, result=result, rh=rh, t=t, wind_bearing=wind_bearing, wind_speed=wind_speed,
        )

        self._room_result_payload(
            airflow=airflow, cfg=cfg, co2_available=co2_available, co2_display=co2_display,
            co2_entity=co2_entity, comfort_target=comfort_target, comfort_target_source=comfort_target_source,
            cooldown_demoted=cooldown_demoted, cooldown_override=cooldown_override, cost=cost,
            cover_learning_guard=cover_learning_guard, delivered=delivered, dynamic=dynamic,
            dynamic5=dynamic5, effective_learning_rate=effective_learning_rate, elapsed=elapsed,
            explicit_three_state=explicit_three_state, fcost=fcost, fdel=fdel, ffuel=ffuel,
            forecast_horizon=forecast_horizon, fpurchased=fpurchased, fuel=fuel, goal_state=goal_state,
            has_ventilation_contact=has_ventilation_contact, high_duration=high_duration,
            humidity_rebound=humidity_rebound, humidity_trend=humidity_trend, idx=idx,
            illuminance=illuminance, illuminance_configured_entity=illuminance_configured_entity,
            illuminance_sensor_enabled=illuminance_sensor_enabled, include=include,
            indirect_candidate=indirect_candidate, indirect_cooling_candidate=indirect_cooling_candidate,
            key=key, measurement_frame=measurement_frame, mem=mem, minutes_since_vent=minutes_since_vent,
            moisture_source=moisture_source, opening_assessments=opening_assessments,
            opening_mode=opening_mode, options=options, passage_contacts=passage_contacts, pm25=pm25,
            pm25_configured_entity=pm25_configured_entity, pm25_sensor_enabled=pm25_sensor_enabled,
            proven_three_state=proven_three_state, purchased=purchased, reason_list=reason_list,
            recently_ventilated=recently_ventilated, reference_humidity_entity=reference_humidity_entity,
            reference_temperature_entity=reference_temperature_entity, result=result, results=results,
            room_threshold_effective_ml=room_threshold_effective_ml, room_threshold_mode=room_threshold_mode,
            routine_response=routine_response, routine_samples=routine_samples, season_ctx=season_ctx,
            seasonal_routine_rate=seasonal_routine_rate, stabilizing=stabilizing, temp_change=temp_change,
            three_state_stale_contacts=three_state_stale_contacts,
            three_state_unknown_contacts=three_state_unknown_contacts,
            transition_suppressed=transition_suppressed, voc=voc, voc_configured_entity=voc_configured_entity,
            voc_sensor_enabled=voc_sensor_enabled,
        )
        self._room_result_overlays(
            cfg=cfg, comfort_target=comfort_target, key=key,
            mechanical_exhaust_active=mechanical_exhaust_active, mem=mem, now=now, options=options,
            outdoor_pm25=outdoor_pm25, pollen=pollen, raw_contact_open=raw_contact_open, results=results,
            voc_unit_scale=voc_unit_scale,
        )
        return changed, ventilation_group

    def _room_result_overlays(
        self,
        *,
        cfg: Any, comfort_target: Any, key: Any, mechanical_exhaust_active: Any, mem: Any, now: Any,
        options: Any, outdoor_pm25: Any, pollen: Any, raw_contact_open: Any, results: Any,
        voc_unit_scale: Any,
    ) -> Any:
        """Air-quality veto flags, shading plan, interventions and configured actuators of a room."""
        if voc_unit_scale is not None:
            results[key]["voc_scale"] = voc_unit_scale
        results[key]["pollen_blocked"] = bool(
            options.get("pollen_enabled", False)
            and options.get("pollen_strict_veto", True)
            and pollen > float(options.get("pollen_max", 4.0))
        )
        results[key]["outdoor_pm25_blocked"] = outdoor_pm25_blocked(options, outdoor_pm25)
        shading = shading_plan(
            cover_openings=_cover_openings(cfg),
            temperature=results[key].get("temperature"),
            illuminance=results[key].get("illuminance"),
            options=options,
            summer_cooling=str(options.get("operating_profile")) == PROFILE_SUMMER_COOLING,
            previous=self._shading_memory.get(key, {}).get("covers_to_close"),
            previous_sunlit=self._shading_memory.get(key, {}).get("sunlit_covers"),
            **self._shading_context(now, options, results[key].get("temperature"), comfort_target),
        )
        self._shading_memory[key] = shading
        results[key]["shading"] = shading
        interventions = build_interventions(
            room=results[key],
            config=cfg,
            options=options,
            entity_state=lambda entity_id: (self.hass.states.get(entity_id).state if self.hass.states.get(entity_id) else None),
        )
        results[key]["interventions"] = interventions
        results[key]["primary_intervention"] = interventions[0] if interventions else None
        results[key]["configured_actuators"] = {
            "contact_covers": {str(k): list(v or []) for k, v in (cfg.get(CONF_CONTACT_COVERS, {}) or {}).items()},
            "covers": list(cfg.get(CONF_ROOM_COVERS, []) or []),  # legacy fallback only
            "climate": cfg.get(CONF_ROOM_CLIMATE),
            "exhaust_fan": cfg.get(CONF_ROOM_EXHAUST_FAN),
            "exhaust_fan_control": str(cfg.get(CONF_ROOM_EXHAUST_FAN_CONTROL) or "off"),
            "mechanical_exhaust_active": mechanical_exhaust_active,
            "window_open": raw_contact_open,
            "ventilation_type": mem.get("session_specialist_opening_mode") if mem.get("session_active") else None,
            "supply_fan": cfg.get(CONF_ROOM_SUPPLY_FAN),
            "ventilation_device": cfg.get(CONF_ROOM_VENTILATION_DEVICE),
            "dehumidifier": cfg.get(CONF_ROOM_DEHUMIDIFIER),
            "humidifier": cfg.get(CONF_ROOM_HUMIDIFIER),
            "air_purifier": cfg.get(CONF_ROOM_AIR_PURIFIER),
        }
        results[key]["reference_path"] = self.__dict__.get("_reference_paths", {}).get(str(key), "default")
        results[key]["air_exchange"] = self.__dict__.get("_air_exchange", {}).get(key)  # 0.26.5.4: display only
        if results[key]["reference_path"] == "neighbour_room" and isinstance(results[key].get("recommendation_reasons"), list):
            results[key]["recommendation_reasons"].append(NEIGHBOUR_REFERENCE_REASON)
        # 0.26.5.4: what the automatic fan control does (final value after the house decision)
        results[key]["fan_automation"] = room_fan_automation(
            {**results[key], "house_aligned_action": action_code(results[key].get("action"))}, self._fan_snapshot(key)
        )

    def _monitor_only_room_result(
        self,
        *,
        cfg: Any, changed: Any, illuminance_sensor_enabled: Any, key: Any, pm25_sensor_enabled: Any,
        results: Any, ventilation_group: Any, voc_sensor_enabled: Any,
    ) -> Any:
        """Display-only result for a room excluded from calculations."""
        # v0.21.0.2: A monitor-only/structure room may still have real
        # climate sensors (for example a winter garden used as an outside
        # reference).  Keep those readings visible without allowing the
        # room to influence recommendations, learning, statistics or the
        # house balance.  This is intentionally display-only: no values
        # are estimated when a configured sensor is missing.
        temperature_entity = cfg.get(CONF_ROOM_TEMPERATURE)
        humidity_entity = cfg.get(CONF_ROOM_HUMIDITY)
        monitor_temp_source = aggregate_states(self.hass, temperature_entity, finite=finite_float, strategy=str(cfg.get(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean")))
        monitor_humidity_source = aggregate_states(self.hass, humidity_entity, finite=finite_float, strategy=str(cfg.get(CONF_ROOM_HUMIDITY_AGGREGATION, "mean")))
        temperature_state = _aggregate_state_proxy(self.hass, temperature_entity, monitor_temp_source)
        humidity_state = _aggregate_state_proxy(self.hass, humidity_entity, monitor_humidity_source)
        monitor_t = monitor_temp_source.value
        monitor_rh = monitor_humidity_source.value
        monitor_valid = bool(
            monitor_t is not None and monitor_rh is not None
            and -10 < monitor_t < 50 and 5 <= monitor_rh <= 100
        )
        monitor_ah = absolute_humidity(monitor_t, monitor_rh) if monitor_valid else None
        monitor_voc = _float_state(self.hass, cfg.get(CONF_ROOM_VOC)) if voc_sensor_enabled and cfg.get(CONF_ROOM_VOC) else None
        monitor_pm25 = _float_state(self.hass, cfg.get(CONF_ROOM_PM25)) if pm25_sensor_enabled and cfg.get(CONF_ROOM_PM25) else None
        monitor_illuminance = _float_state(self.hass, cfg.get(CONF_ROOM_ILLUMINANCE)) if illuminance_sensor_enabled and cfg.get(CONF_ROOM_ILLUMINANCE) else None
        monitor_volume = max(float(cfg.get(CONF_ROOM_VOLUME, 0.0) or 0.0), 0.0)
        monitor_last = None
        for monitor_state in (temperature_state, humidity_state):
            changed_at = getattr(monitor_state, "last_updated", None) if monitor_state is not None else None
            if changed_at is not None and (monitor_last is None or changed_at > monitor_last):
                monitor_last = changed_at
        sensor_configured = bool(temperature_entity and humidity_entity)
        results[key] = {
            "key": key,
            "name": cfg.get(CONF_ROOM_NAME, key),
            "icon": cfg.get(CONF_ROOM_ICON),
            "floor": cfg.get(CONF_ROOM_FLOOR, "Unzugeordnet"),
            "volume_m3": round(monitor_volume, 1),
            "calculation_enabled": False,
            "monitor_only": True,
            "sensor_data_configured": sensor_configured,
            "sensor_data_available": monitor_valid,
            "data_quality": "monitor_only" if monitor_valid else ("missing" if sensor_configured else "not_configured"),
            "action": "Monitor only",
            "reason": (
                "Live sensor values are shown; climate calculations are disabled"
                if monitor_valid else
                "Configured climate sensors are currently unavailable"
                if sensor_configured else
                "Room is stored as building structure without climate calculations"
            ),
            "temperature": round(float(monitor_t), 2) if monitor_valid else None,
            "humidity": round(float(monitor_rh), 2) if monitor_valid else None,
            "absolute_humidity": round(float(monitor_ah), 2) if monitor_ah is not None else None,
            "water_in_air_ml": int(round(float(monitor_ah) * monitor_volume)) if monitor_ah is not None else None,
            "voc": monitor_voc, "voc_available": monitor_voc is not None, "voc_enabled": voc_sensor_enabled, "voc_configured": bool(cfg.get(CONF_ROOM_VOC)),
            "pm25": monitor_pm25, "pm25_available": monitor_pm25 is not None, "pm25_enabled": pm25_sensor_enabled, "pm25_configured": bool(cfg.get(CONF_ROOM_PM25)),
            "illuminance": monitor_illuminance, "illuminance_available": monitor_illuminance is not None, "illuminance_enabled": illuminance_sensor_enabled, "illuminance_configured": bool(cfg.get(CONF_ROOM_ILLUMINANCE)),
            "last_measurement_at": monitor_last.isoformat() if monitor_last is not None else None,
            "last_measurement_valid": monitor_valid if sensor_configured else None,
            "active": False,
            "open": False,
            "close_recommended": False,
            "contact_mode": cfg.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY),
            "contact_count": len(_contact_ids(cfg)),
            "contact_entities": _contact_ids(cfg),
            "contact_delays": dict(cfg.get(CONF_CONTACT_DELAYS, {})),
            "contact_orientations": dict(cfg.get(CONF_CONTACT_ORIENTATIONS, {})),
            "contact_reference_temperatures": dict(cfg.get(CONF_CONTACT_REFERENCE_TEMPERATURES, {})),
            "contact_reference_humidities": dict(cfg.get(CONF_CONTACT_REFERENCE_HUMIDITIES, {})),
            "moisture_sources": list(cfg.get(CONF_ROOM_MOISTURE_SOURCES, [])),
            "window_orientation": cfg.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN),
        }
        return changed, ventilation_group  # was: continue (next room)

    def _read_room_sensors(
        self,
        *,
        cfg: Any, illuminance_sensor_enabled: Any, now: Any, outdoor_humidity_entity: Any,
        outdoor_humidity_state: Any, outdoor_rh: Any, outdoor_t: Any, outdoor_temp_entity: Any,
        outdoor_temp_state: Any, pm25_sensor_enabled: Any, voc_sensor_enabled: Any,
    ) -> Any:
        """Room climate, reference air and optional air-quality sensor readings."""
        temperature_entity = cfg.get(CONF_ROOM_TEMPERATURE)
        humidity_entity = cfg.get(CONF_ROOM_HUMIDITY)
        temperature_source = aggregate_states(self.hass, temperature_entity, finite=finite_float, strategy=str(cfg.get(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean")))
        humidity_source = aggregate_states(self.hass, humidity_entity, finite=finite_float, strategy=str(cfg.get(CONF_ROOM_HUMIDITY_AGGREGATION, "mean")))
        temperature_state = _aggregate_state_proxy(self.hass, temperature_entity, temperature_source)
        humidity_state = _aggregate_state_proxy(self.hass, humidity_entity, humidity_source)
        room_reference_temperature_entity = cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
        room_reference_humidity_entity = cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
        default_reference_temperature_entity = room_reference_temperature_entity or outdoor_temp_entity
        default_reference_humidity_entity = room_reference_humidity_entity or outdoor_humidity_entity
        default_ref_t = _float_state(self.hass, room_reference_temperature_entity) if room_reference_temperature_entity else outdoor_t
        default_ref_rh = _float_state(self.hass, room_reference_humidity_entity) if room_reference_humidity_entity else outdoor_rh
        reference_temperature_entity, reference_humidity_entity, ref_t, ref_rh = _contact_specific_reference(
            self.hass, cfg,
            default_temp_entity=default_reference_temperature_entity,
            default_humidity_entity=default_reference_humidity_entity,
            default_temp=default_ref_t, default_humidity=default_ref_rh,
        )
        reference_temperature_state = self.hass.states.get(reference_temperature_entity) if reference_temperature_entity else outdoor_temp_state
        reference_humidity_state = self.hass.states.get(reference_humidity_entity) if reference_humidity_entity else outdoor_humidity_state
        t = temperature_source.value; rh = humidity_source.value
        measurement_frame = build_measurement_frame(
            now,
            temperature_state=temperature_state,
            humidity_state=humidity_state,
            reference_temperature_state=reference_temperature_state,
            reference_humidity_state=reference_humidity_state,
        )
        co2_entity = cfg.get(CONF_ROOM_CO2)
        co2 = _float_state(self.hass, co2_entity) if co2_entity else None
        disabled_goals = normalise_disabled_goals(cfg.get(CONF_ROOM_DISABLED_GOALS))
        # A switched-off CO2 goal keeps the reading visible but removes it
        # from every decision (no CO2 airing, no critical-CO2 override).
        co2_display = co2
        if "co2" in disabled_goals:
            co2 = None
        co2_available = co2 is not None
        voc_configured_entity = cfg.get(CONF_ROOM_VOC)
        voc_entity = voc_configured_entity if voc_sensor_enabled else None
        voc = _float_state(self.hass, voc_entity) if voc_entity else None
        voc_state = self.hass.states.get(voc_entity) if voc_entity else None
        voc_unit_scale = voc_scale(
            voc_state.attributes.get("device_class") if voc_state else None,
            voc_state.attributes.get("unit_of_measurement") if voc_state else None,
        ) if voc_state else None
        pm25_configured_entity = cfg.get(CONF_ROOM_PM25)
        pm25_entity = pm25_configured_entity if pm25_sensor_enabled else None
        pm25 = _float_state(self.hass, pm25_entity) if pm25_entity else None
        illuminance_configured_entity = cfg.get(CONF_ROOM_ILLUMINANCE)
        illuminance_entity = illuminance_configured_entity if illuminance_sensor_enabled else None
        illuminance = _float_state(self.hass, illuminance_entity) if illuminance_entity else None
        return (
            co2, co2_available, co2_display, co2_entity, default_ref_rh, default_ref_t,
            default_reference_humidity_entity, default_reference_temperature_entity, disabled_goals,
            humidity_entity, humidity_state, illuminance, illuminance_configured_entity, measurement_frame,
            pm25, pm25_configured_entity, ref_rh, ref_t, reference_humidity_entity,
            reference_temperature_entity, rh, t, temperature_entity, temperature_state, voc,
            voc_configured_entity, voc_unit_scale,
        )
