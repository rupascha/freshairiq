"""House stage of the coordinator: outdoor forecast, ventilation group, aggregates and passive ventilation."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .open_connections import connected_pairs
from .const import (
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    POST_VENTILATION_RESULT_MINUTES,
    VERSION,
)
from .coordinator_contacts import _contact_ids, _room_physical_opened_at
from .energy import exchanged_air_fraction
from .forecast import estimated_daily_moisture_ml
from .forecast_validation import append_validation_record, build_validation_record
from .house_decision import house_status_fallback, ventilation_threshold_decision
from .outdoor_air import veto_cause as outdoor_veto_cause
from .passive_ventilation import evaluate_passive_ventilation, learn_passive_exchange
from .ventilation_log import append_ventilation_log
from .ventilation_result import append_completed_sessions, finalise_ventilation_group, new_ventilation_group
from .weather_future import (
    FORECAST_REFRESH_SECONDS,
    async_hourly_forecast,
    forecast_retry_delay_seconds,
    future_boundaries,
)
from .weather_now import weather_now


class HouseStageMixin:
    """House stage of the coordinator: outdoor forecast, ventilation group, aggregates and passive ventilation."""

    hass: HomeAssistant  # provided by the coordinator

    async def _async_outdoor_forecast(
        self,
        *,
        now: Any, outdoor_rh: Any, outdoor_t: Any, outdoor_weather_state: Any,
    ) -> Any:
        """Hourly forecast refresh, future outdoor boundaries and the current weather situation."""
        weather_entity = self.entry.data.get(CONF_OUTDOOR_WEATHER)
        if weather_entity and (
            self._hourly_forecast_fetched_at is None
            or (now - self._hourly_forecast_fetched_at).total_seconds() >= FORECAST_REFRESH_SECONDS
        ):
            forecast_status: dict[str, Any] = {}
            fetched_forecast = await async_hourly_forecast(self.hass, weather_entity, forecast_status)
            if fetched_forecast:
                # Replace only with a valid provider response. A transient weather
                # integration failure must not discard the last useful forecast.
                self._hourly_forecast_cache = fetched_forecast
                self._hourly_forecast_fetched_at = now
                self._hourly_forecast_failures = 0
            else:
                # Keep any previous forecast. Retry after 1, 2, 5, 10, 30, then
                # 60 minutes instead of every minute forever (0.26.4.7).
                self.robustness.weather_failure(forecast_status.get("reason"))
                self._hourly_forecast_failures += 1
                delay = forecast_retry_delay_seconds(self._hourly_forecast_failures)
                self._hourly_forecast_fetched_at = now - timedelta(seconds=FORECAST_REFRESH_SECONDS - delay)
        future_outdoor = future_boundaries(
            self._hourly_forecast_cache, now, outdoor_t, outdoor_rh
        ) if weather_entity else {}
        # Hotfix 0.20.2.1: the user-facing 15–120 minute forecast advances
        # through real 5-minute future weather boundaries. Keep this separate
        # from the compact public/diagnostic boundary set above.
        forecast_outdoor_steps = future_boundaries(
            self._hourly_forecast_cache, now, outdoor_t, outdoor_rh,
            delays=tuple(range(5, 121, 5)),
        ) if weather_entity else {}
        planning_delays = (60, 120, 180, 240, 360, 480)
        planning_outdoor = future_boundaries(
            self._hourly_forecast_cache, now, outdoor_t, outdoor_rh, delays=planning_delays
        ) if weather_entity else {}
        cross = self._cross_ventilation_active()
        # 0.26.4.8: current weather for the dashboard mascot (rain now / soon,
        # snow, thunder, frost, heat) instead of "rain somewhere tonight".
        weather_situation = weather_now(
            outdoor_weather_state.state if outdoor_weather_state is not None else None,
            self._hourly_forecast_cache if weather_entity else [], now, outdoor_t,
        )
        return (cross, forecast_outdoor_steps, future_outdoor, planning_outdoor, weather_situation)

    def _restore_ventilation_group(
        self,
        *,
        changed: Any, rooms_cfg: Any, ventilation_group: Any,
    ) -> Any:
        """Recreate the house ventilation group from persisted active sessions."""
        if not isinstance(ventilation_group, dict) or not ventilation_group.get("active"):
            persisted_starts = []
            for _cfg in rooms_cfg:
                _mem = self.store.room(_cfg["key"])
                if _mem.get("session_active") and _mem.get("session_started"):
                    _contacts = _contact_ids(_cfg)
                    _proven = set(str(x) for x in (_mem.get("three_state_contacts") or [])) & set(_contacts)
                    _stable_raw = _mem.get("stable_opening_modes") if isinstance(_mem.get("stable_opening_modes"), dict) else {}
                    _stable_modes = {c: str(_stable_raw.get(c, "unknown")) for c in _proven}
                    _since_raw = _mem.get("stable_opening_since") if isinstance(_mem.get("stable_opening_since"), dict) else {}
                    _stable_since: dict[str, datetime] = {}
                    for _contact in _proven:
                        try:
                            _stable_since[_contact] = datetime.fromisoformat(str(_since_raw.get(_contact)))
                        except (TypeError, ValueError):
                            pass
                    physical_start = _room_physical_opened_at(
                        self.hass, _cfg, contact_modes=_stable_modes, contact_since=_stable_since
                    )
                    if physical_start is not None:
                        persisted_starts.append(physical_start)
                    try:
                        persisted_starts.append(datetime.fromisoformat(str(_mem["session_started"])))
                    except (TypeError, ValueError):
                        pass
            if persisted_starts:
                ventilation_group = new_ventilation_group(min(persisted_starts))
                self.store.data["ventilation_group"] = ventilation_group
                changed = True
            else:
                ventilation_group = None
        return (changed, ventilation_group)

    def _close_ventilation_group(
        self,
        *,
        changed: Any, completed_house_sessions: Any, completed_sessions: Any, now: Any, rooms_cfg: Any,
        ventilation_group: Any,
    ) -> Any:
        """Log completed sessions and finalise the house ventilation group once every room closed."""
        if completed_sessions:
            self.store.data["ventilation_log"] = append_ventilation_log(
                self.store.data.get("ventilation_log", []), completed_sessions, now
            )
            changed = True
            if not isinstance(ventilation_group, dict) or not ventilation_group.get("active"):
                starts = []
                for event in completed_sessions:
                    raw = event.get("started_at")
                    if raw:
                        starts.append(datetime.fromisoformat(str(raw)))
                ventilation_group = new_ventilation_group(min(starts) if starts else now)
                self.store.data["ventilation_group"] = ventilation_group
            if append_completed_sessions(ventilation_group, completed_sessions):
                changed = True

        any_house_session_active = any(
            bool(self.store.room(cfg["key"]).get("session_active"))
            for cfg in rooms_cfg if cfg.get(CONF_ROOM_INCLUDE_CALCULATIONS, True)
        )
        if isinstance(ventilation_group, dict) and ventilation_group.get("active") and not any_house_session_active:
            group_ended_at = now
            event_ends: list[datetime] = []
            for event in ventilation_group.get("sessions", []):
                try:
                    event_ends.append(datetime.fromisoformat(str(event.get("ended_at"))))
                except (TypeError, ValueError):
                    pass
            if event_ends:
                group_ended_at = max(event_ends)
            completed_house_sessions = [
                dict(event) for event in ventilation_group.get("sessions", [])
                if isinstance(event, dict)
            ]
            result = finalise_ventilation_group(
                ventilation_group, group_ended_at, display_minutes=POST_VENTILATION_RESULT_MINUTES
            )
            if result is not None:
                self.store.data["last_ventilation"] = result
                validation_record = build_validation_record(
                    result, completed_house_sessions, model_version=VERSION
                )
                self.store.data["forecast_validation_history"] = append_validation_record(
                    self.store.data.get("forecast_validation_history") or [],
                    validation_record,
                    group_ended_at,
                )
                changed = True
            self.store.data["ventilation_group"] = None
            ventilation_group = None
            changed = True
        return (changed, completed_house_sessions)

    def _house_aggregates(
        self,
        *,
        active: Any, bad: Any, changed: Any, close: Any, cross: Any, effective_adults: Any,
        effective_children: Any, now: Any, options: Any, outdoor_t: Any, pollen: Any,
        sensor_recovery_grace: Any, valid: Any,
    ) -> Any:
        """House-wide sums of the room results, threshold, status fallback and recommended duration."""
        candidates = [r for r in valid if r.get("ventilation_candidate", False)]; cooling = [r for r in valid if r["action"] == "Ventilate for cooling"]
        # Keep the displayed "removable" value semantically identical to the
        # room breakdown: theoretical current potential across every valid room.
        # Decision logic remains based only on actionable ventilation candidates.
        potential = sum(max(float(r.get("potential_ml", 0)), 0.0) for r in valid)
        actionable_potential = sum(max(float(r.get("potential_ml", 0)), 0.0) for r in candidates)
        # House live balance is strictly the currently running sessions.
        # Completed room results may remain available for diagnostics but must
        # never be summed into a new/restarted live session.
        live = sum(r["result_ml"] for r in active)
        # Signed physical effect: + means removable/removed internally, - means moisture would be/was added.
        next5_effect = sum(r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml", 0)) for r in active)
        # When no ventilation is running, expose the aggregate 5-minute moisture
        # gain of rooms for which outside/reference air is currently wetter.
        # This is deliberately separate from removable potential so a negative
        # physical effect can never invalidate the dashboard state.
        moisture_gain_next5 = sum(
            max(0, -int(r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml", 0))))
            for r in valid if r.get("action") == "Do not ventilate"
        )
        forecast_effect = sum(float(r.get("forecast_moisture_effect_ml", 0)) for r in active)
        forecast_uncapped_effect = sum(float(r.get("forecast_uncapped_moisture_effect_ml", r.get("forecast_moisture_effect_ml", 0))) for r in active)
        forecast_target_limited = bool(active) and any(bool(r.get("forecast_target_limited")) for r in active)
        forecast_live_adapted = bool(active) and any(bool(r.get("forecast_live_adapted")) for r in active)
        forecast_live_observation_weight = max((float(r.get("forecast_live_observation_weight", 0.0) or 0.0) for r in active), default=0.0)
        forecast_cost = sum(float(r.get("forecast_cost", 0)) for r in active)
        forecast_heat = sum(float(r.get("forecast_heat_kwh", 0)) for r in active)
        active_forecast_volume = sum(float(r.get("volume_m3", 0)) for r in active)
        forecast_temp = (
            sum(float(r.get("forecast_temperature_change_c", 0)) * float(r.get("volume_m3", 0)) for r in active) / active_forecast_volume
            if active_forecast_volume > 0 else 0.0
        )
        forecast_confidence = round(
            sum(float(r.get("forecast_confidence", 0)) * float(r.get("volume_m3", 0)) for r in active) / active_forecast_volume
            if active_forecast_volume > 0 else 0.0
        )
        active_close_times = [
            float(r.get("forecast_optimal_close_in_min")) for r in active
            if r.get("forecast_optimal_close_in_min") is not None
        ]
        # A house-wide close time exists only when every active room reaches an
        # efficient end point inside the chosen horizon. Otherwise at least one
        # room is still predicted to benefit beyond the horizon.
        forecast_optimal_close_in_min = (
            round(max(active_close_times), 1)
            if active and len(active_close_times) == len(active) else None
        )
        max_surface = max((r["surface_rh"] for r in valid), default=0)
        total_water = sum(r["water_in_air_ml"] for r in valid)
        if valid and self.store.record_house_water(now.replace(tzinfo=None), total_water): changed = True
        threshold_mode = str(options.get("threshold_mode", "adaptive_home_size"))
        expected_daily_generation = estimated_daily_moisture_ml(options)
        current_daily_generation = estimated_daily_moisture_ml(options, effective_adults, effective_children)
        (pollen_blocked, threshold_reason, ventilation_threshold) = ventilation_threshold_decision(
            expected_daily_generation=expected_daily_generation,
            now=now,
            options=options,
            outdoor_t=outdoor_t,
            pollen=pollen,
            threshold_mode=threshold_mode,
            total_water=total_water,
            valid=valid,
        )
        pollen_only_blocked = pollen_blocked
        outdoor_air_cause = outdoor_veto_cause(pollen_only_blocked, self._outdoor_pm25_blocked)
        # One outdoor-air veto for house status and recommendation (pollen and/or PM2.5).
        pollen_blocked = bool(pollen_only_blocked or self._outdoor_pm25_blocked)
        self._pollen_only_blocked = pollen_only_blocked
        status = house_status_fallback(
            actionable_potential=actionable_potential,
            active=active,
            bad=bad,
            close=close,
            cooling=cooling,
            options=options,
            pollen_blocked=pollen_blocked,
            sensor_recovery_grace=sensor_recovery_grace,
            valid=valid,
            ventilation_threshold=ventilation_threshold,
        )

        confidence = round(sum(min(r["learning_samples"], 10) for r in valid) / max(len(valid) * 10, 1) * 100)
        reference_temp = outdoor_t if outdoor_t is not None else 10.0; max_delta = max((r["delta_g_m3"] for r in valid), default=0.0)
        base = 4 if reference_temp <= 0 else 5 if reference_temp <= 5 else 7 if reference_temp <= 10 else 10 if reference_temp <= 15 else 12 if reference_temp <= 20 else 15
        adj = -2 if max_delta >= 5 else -1 if max_delta >= 3 else 3 if max_delta < 2 else 0
        recommended = int(min(max(base + adj, float(options["min_duration_min"])), float(options["max_duration_min"])))

        # Hotfix 0.9.4.7: the user-facing moisture potential is the amount that
        # FreshAirIQ expects to exchange during the recommended airing time, not
        # the theoretical 100% replacement of all room air.  The physical basis
        # remains the absolute-humidity gradient (inside - reference/outside);
        # the learned per-room exchange rate then determines how much of that
        # gradient is realistically reached.  Keep the sign: positive means
        # removable moisture, negative means outside/reference air would add it.
        realistic_house_effect = 0.0
        realistic_actionable_potential = 0.0
        for r in valid:
            fraction = exchanged_air_fraction(
                float(r.get("learned_exchange_rate_per_min", .03)),
                recommended,
                (1.25 if cross else 1.0) * float(r.get("airflow_factor", 1.0)),
            )
            realistic = (
                float(r.get("delta_g_m3", 0.0))
                * float(r.get("volume_m3", 0.0))
                * fraction
            )
            r["realistic_potential_ml"] = round(realistic)
            r["theoretical_potential_ml"] = int(r.get("potential_ml", 0) or 0)
            r["potential_horizon_min"] = recommended
            realistic_house_effect += realistic
            if r.get("ventilation_candidate", False):
                realistic_actionable_potential += max(realistic, 0.0)

        max_elapsed = max((float(r.get("session_elapsed_min", 0)) for r in active), default=0.0); remaining = round(recommended - max_elapsed, 1) if active else float(recommended)
        active_volume = sum(float(r.get("volume_m3", 0)) for r in active)
        temp_live = round(sum(float(r.get("temperature_change_c", 0)) * float(r.get("volume_m3", 0)) for r in active) / active_volume, 1) if active_volume > 0 else 0.0
        avg_temp = round(sum(float(r["temperature"]) * float(r["volume_m3"]) for r in valid) / sum(float(r["volume_m3"]) for r in valid), 2) if valid and sum(float(r["volume_m3"]) for r in valid) > 0 else 0.0
        stats_days = int(options.get("statistics_days", 14))
        if valid and self.store.record_temperature_point(now.replace(tzinfo=None), avg_temp, days=30): changed = True
        return (
            actionable_potential, changed, confidence, cooling, current_daily_generation,
            expected_daily_generation, forecast_confidence, forecast_cost, forecast_effect, forecast_heat,
            forecast_live_adapted, forecast_live_observation_weight, forecast_optimal_close_in_min,
            forecast_target_limited, forecast_temp, forecast_uncapped_effect, live, max_elapsed, max_surface,
            moisture_gain_next5, next5_effect, outdoor_air_cause, pollen_blocked, pollen_only_blocked,
            potential, realistic_actionable_potential, realistic_house_effect, recommended, remaining,
            stats_days, status, temp_live, threshold_mode, threshold_reason, total_water,
            ventilation_threshold,
        )

    def _apply_passive_ventilation(
        self,
        *,
        active: Any,
        changed: Any,
        now: Any,
        options: Any,
        results: Any,
        rooms_cfg: Any,
        ventilation_group: Any,
    ) -> Any:
        """Phase 3: estimate indirect (passive) ventilation of closed rooms connected to aired rooms."""
        # Hotfix 0.20.2.4: detect closed rooms that are measurably participating
        # in the current house ventilation.  This is deliberately conservative:
        # a same-floor/explicit connection makes a room only a *candidate*; the
        # room's own absolute-humidity sensor must then move toward its current
        # ventilation reference.  The estimate is display-only and is NOT added
        # to live_balance_ml, because that could double-count moisture transported
        # through an actively ventilated neighbouring room.
        active_keys = {str(r.get("key")) for r in active}
        active_floors = {str(r.get("floor", "")) for r in active}
        cross_zone_pairs: set[frozenset[str]] = set()
        for _pair in str(options.get("cross_zone_connections", "") or "").split(","):
            _keys = [x.strip() for x in _pair.split("+") if x.strip()]
            if len(_keys) == 2:
                cross_zone_pairs.add(frozenset(_keys))
        # 0.26.5.3: an open connection without a door is an explicit link too
        cross_zone_pairs |= connected_pairs(options)
        passive_group_id = (
            str(ventilation_group.get("started_at"))
            if isinstance(ventilation_group, dict) and ventilation_group.get("active")
            else None
        )
        for _key, _room in results.items():
            _mem = self.store.room(_key)
            _room["passive_ventilation_active"] = False
            _room["passive_ventilation_estimated_ml"] = 0.0
            _room["passive_ventilation_confidence"] = 0
            _room["passive_ventilation_reason"] = None
            _room["passive_ventilation_estimated"] = True

            _is_active = bool(_room.get("active"))
            _valid = (
                _room.get("data_quality") == "ok"
                and _room.get("calculation_enabled", True)
                and not _room.get("moisture_source_active")
                and not _room.get("moisture_source_recovery")
            )
            _same_floor = str(_room.get("floor", "")) in active_floors if active_floors else False
            _explicit_link = any(frozenset((_key, akey)) in cross_zone_pairs for akey in active_keys)
            _active_same_floor_count = sum(1 for a in active if str(a.get("floor", "")) == str(_room.get("floor", "")))
            # Same-floor proximity alone is weak evidence. Require at least two
            # active openings on that floor, while an explicit configured link
            # remains strong evidence on its own.
            _connection_strength = 1.0 if _explicit_link else (0.65 if _same_floor and _active_same_floor_count >= 2 else 0.0)
            _connected = bool(active and _connection_strength >= 0.45)

            if _is_active or not _valid or not _connected or passive_group_id is None:
                for _field in (
                    "passive_group_id", "passive_observation_started_at",
                    "passive_start_ah", "passive_start_reference_ah", "passive_samples",
                ):
                    if _mem.get(_field) is not None:
                        _mem[_field] = None
                        changed = True
                continue

            _current_ah = float(_room.get("absolute_humidity") or 0.0)
            _reference_ah = float(_room.get("reference_humidity") or 0.0)
            _volume = float(_room.get("volume_m3") or 0.0)
            if _mem.get("passive_group_id") != passive_group_id or _mem.get("passive_start_ah") is None:
                _mem["passive_group_id"] = passive_group_id
                _mem["passive_observation_started_at"] = now.isoformat()
                _mem["passive_start_ah"] = _current_ah
                _mem["passive_start_reference_ah"] = _reference_ah
                _mem["passive_samples"] = [{"elapsed_min": 0.0, "ah": _current_ah, "reference_ah": _reference_ah}]
                changed = True
                continue

            try:
                _passive_started = datetime.fromisoformat(str(_mem.get("passive_observation_started_at")))
                _elapsed_passive = max(0.0, (now - _passive_started).total_seconds() / 60.0)
            except (TypeError, ValueError):
                _mem["passive_observation_started_at"] = now.isoformat()
                _mem["passive_start_ah"] = _current_ah
                _mem["passive_start_reference_ah"] = _reference_ah
                _mem["passive_samples"] = [{"elapsed_min": 0.0, "ah": _current_ah, "reference_ah": _reference_ah}]
                changed = True
                continue

            _samples = list(_mem.get("passive_samples") or [])
            if not _samples or abs(float(_samples[-1].get("ah", _current_ah)) - _current_ah) >= 0.015 or _elapsed_passive - float(_samples[-1].get("elapsed_min", 0.0)) >= 1.5:
                _samples.append({"elapsed_min": round(_elapsed_passive, 3), "ah": _current_ah, "reference_ah": _reference_ah})
                _samples = _samples[-8:]
                _mem["passive_samples"] = _samples
                changed = True

            _passive = evaluate_passive_ventilation(
                start_ah=float(_mem.get("passive_start_ah") or _current_ah),
                current_ah=_current_ah,
                reference_ah=_reference_ah,
                volume_m3=_volume,
                elapsed_min=_elapsed_passive,
                connected=True,
                start_reference_ah=float(_mem.get("passive_start_reference_ah") or _reference_ah),
                samples=_samples,
                connection_strength=_connection_strength,
            )
            _room["passive_ventilation_active"] = bool(_passive.get("active"))
            _room["passive_ventilation_estimated_ml"] = float(_passive.get("estimated_ml", 0.0) or 0.0)
            _room["passive_ventilation_confidence"] = int(_passive.get("confidence", 0) or 0)
            _room["passive_ventilation_reason"] = _passive.get("reason")
            _room["passive_ventilation_elapsed_min"] = round(_elapsed_passive, 1)

            # Learn indirect exchange once per house ventilation group. Keep this
            # coefficient separate from direct-window learning: it describes how
            # strongly this room participates through the building air path.
            if (
                bool(_passive.get("active"))
                and int(_passive.get("confidence", 0) or 0) >= 60
                and not _contact_ids(next((cfg for cfg in rooms_cfg if cfg.get("key") == _key), {}))
                and _mem.get("passive_learning_last_group_id") != passive_group_id
                and _elapsed_passive >= 5.0
            ):
                _learned_passive = learn_passive_exchange(
                    old_rate=float(_mem.get("passive_learning_rate", 0.03) or 0.03),
                    old_samples=int(_mem.get("passive_learning_samples", 0) or 0),
                    start_ah=float(_mem.get("passive_start_ah") or _current_ah),
                    current_ah=_current_ah,
                    start_reference_ah=float(_mem.get("passive_start_reference_ah") or _reference_ah),
                    elapsed_min=_elapsed_passive,
                )
                if _learned_passive["valid"]:
                    _mem["passive_learning_rate"] = float(_learned_passive["rate"])
                    _mem["passive_learning_samples"] = int(_learned_passive["samples"])
                    _mem["passive_learning_last_group_id"] = passive_group_id
                    _mem["passive_learning_last_at"] = now.isoformat()
                    _room["passive_learning_samples"] = int(_mem["passive_learning_samples"])
                    _room["passive_learned_exchange_rate_per_min"] = float(_mem["passive_learning_rate"])
                    changed = True
        return (changed,)
