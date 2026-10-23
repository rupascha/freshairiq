"""Night stage of the coordinator: night learning, overnight forecast and night strategy."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .energy import exchanged_air_fraction, ventilation_cost
from .forecast import (
    effective_night_rate_ml_h,
    in_night_window,
    night_interval_bounds,
    night_window_hours,
    overnight_forecast_ml,
    update_night_learning,
)
from .house_decision import build_night_strategy
from .model import absolute_humidity
from .routines import project_generation_ml


class NightStageMixin:
    """Night stage of the coordinator: night learning, overnight forecast and night strategy."""

    hass: HomeAssistant  # provided by the coordinator

    def _night_outlook(
        self,
        *,
        actionable_potential: Any, active: Any, calc_volume_total: Any, changed: Any, cross: Any,
        daily_generation_prior: Any, effective_adults: Any, effective_children: Any, now: Any, occupancy: Any,
        options: Any, outdoor_rh: Any, outdoor_t: Any, recommended: Any, total_water: Any, valid: Any,
    ) -> Any:
        """Night stage: learn the night rate, forecast the night and derive the night strategy."""
        (changed,) = self._learn_night_rate(
            active=active, changed=changed, effective_adults=effective_adults,
            effective_children=effective_children, now=now, options=options, total_water=total_water,
            valid=valid,
        )

        (
            night_buffer, night_confidence, night_forecast, night_forecast_base, night_hours, night_rows,
            night_samples, night_strategy_relevant, routine_night_adjustment, routine_night_maturity,
            routine_night_projection, trend_effect, weather_effect,
        ) = self._night_forecast(
            actionable_potential=actionable_potential, calc_volume_total=calc_volume_total, cross=cross,
            daily_generation_prior=daily_generation_prior, effective_adults=effective_adults,
            effective_children=effective_children, now=now, occupancy=occupancy, options=options,
            outdoor_rh=outdoor_rh, outdoor_t=outdoor_t, valid=valid,
        )

        (
            avg_indoor_ah, current_outdoor_ah, first_rain_dt, minutes_until_rain, night_ah_delta,
            night_avg_ah, night_max_rh, night_min_temp, night_rain_expected, night_rain_mm, night_rain_prob,
            night_weather_available, open_rooms, pre_rain_avg_ah, rain_start_label,
        ) = self._night_weather(
            night_rows=night_rows, now=now, outdoor_rh=outdoor_rh, outdoor_t=outdoor_t, valid=valid,
        )

        (night_strategy,) = self._night_strategy(
            avg_indoor_ah=avg_indoor_ah, current_outdoor_ah=current_outdoor_ah, first_rain_dt=first_rain_dt,
            minutes_until_rain=minutes_until_rain, night_ah_delta=night_ah_delta, night_avg_ah=night_avg_ah,
            night_confidence=night_confidence, night_forecast=night_forecast,
            night_forecast_base=night_forecast_base, night_hours=night_hours, night_max_rh=night_max_rh,
            night_min_temp=night_min_temp, night_rain_expected=night_rain_expected,
            night_rain_mm=night_rain_mm, night_rain_prob=night_rain_prob, night_rows=night_rows,
            night_strategy_relevant=night_strategy_relevant, night_weather_available=night_weather_available,
            now=now, open_rooms=open_rooms, options=options, pre_rain_avg_ah=pre_rain_avg_ah,
            rain_start_label=rain_start_label, recommended=recommended,
            routine_night_adjustment=routine_night_adjustment, trend_effect=trend_effect, valid=valid,
        )
        return (
            changed, night_buffer, night_confidence, night_forecast, night_forecast_base, night_hours,
            night_samples, night_strategy, routine_night_adjustment, routine_night_maturity,
            routine_night_projection, trend_effect, weather_effect,
        )

    def _learn_night_rate(
        self,
        *,
        active: Any, changed: Any, effective_adults: Any, effective_children: Any, now: Any, options: Any,
        total_water: Any, valid: Any,
    ) -> Any:
        """Learn the household night moisture rate while the house sleeps with closed windows."""
        if options.get("night_forecast_enabled") and valid and not active and in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour")):
            last_raw = self.store.data.get("night_last_snapshot"); last_water = self.store.data.get("night_last_water_ml")
            if not last_raw or last_water is None:
                self.store.data["night_last_snapshot"] = now.isoformat(); self.store.data["night_last_water_ml"] = round(total_water); changed = True
            else:
                try:
                    last_dt = datetime.fromisoformat(last_raw); hours = (now - last_dt).total_seconds() / 3600.0
                    if hours >= .25:
                        if hours <= 1.5:
                            observed_rate = (total_water - float(last_water)) / hours
                            # Store a household-normalised rate so a night with
                            # one resident home does not permanently teach the
                            # model that a four-person household only emits one
                            # person's moisture. The live forecast scales it back
                            # to the currently detected occupancy.
                            current_prior = max(effective_night_rate_ml_h(options, None, 0, effective_adults, effective_children), 1.0)
                            configured_prior = max(effective_night_rate_ml_h(options, None, 0), 1.0)
                            normalised_rate = observed_rate * (configured_prior / current_prior)
                            rate, samples = update_night_learning(self.store.data.get("night_model_ml_h"), int(self.store.data.get("night_model_samples", 0)), normalised_rate)
                            if samples != self.store.data.get("night_model_samples"):
                                self.store.data["night_model_ml_h"] = rate; self.store.data["night_model_samples"] = samples
                                nights = self.store.data.get("night_observed_dates")
                                if not isinstance(nights, list):
                                    nights = []
                                # Attribute after-midnight samples to the night
                                # that started on the previous calendar day.
                                night_day = (now.date() if now.hour >= 12 else (now - timedelta(days=1)).date()).isoformat()
                                if night_day not in nights:
                                    nights.append(night_day)
                                    nights = nights[-500:]
                                self.store.data["night_observed_dates"] = nights
                        self.store.data["night_last_snapshot"] = now.isoformat(); self.store.data["night_last_water_ml"] = round(total_water); changed = True
                except (ValueError, TypeError): self.store.data["night_last_snapshot"] = now.isoformat(); self.store.data["night_last_water_ml"] = round(total_water); changed = True
        elif not in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour")) and self.store.data.get("night_last_snapshot") is not None:
            self.store.data["night_last_snapshot"] = None; self.store.data["night_last_water_ml"] = None; changed = True
        return (changed,)

    def _night_forecast(
        self,
        *,
        actionable_potential: Any, calc_volume_total: Any, cross: Any, daily_generation_prior: Any,
        effective_adults: Any, effective_children: Any, now: Any, occupancy: Any, options: Any,
        outdoor_rh: Any, outdoor_t: Any, valid: Any,
    ) -> Any:
        """Night window and the overnight moisture forecast (occupancy, weather, trend, routines)."""
        # v0.18.0.3: establish one exact night window before any night-facing
        # calculation. Forecast value, strategy text and notifications therefore
        # describe the same hours and the same hourly weather rows.
        def _time_value(value: Any, default_hour: int) -> tuple[int, int]:
            try:
                raw = str(value)
                if ":" in raw:
                    hour_raw, minute_raw = raw.split(":", 1)
                    return int(hour_raw) % 24, min(max(int(minute_raw[:2]), 0), 59)
                return int(raw) % 24, 0
            except (TypeError, ValueError):
                return default_hour, 0

        night_start_h, night_start_m = _time_value(options.get("night_start_hour", "22:00"), 22)
        current_minutes = now.hour * 60 + now.minute + now.second / 60.0
        start_minutes = night_start_h * 60 + night_start_m
        configured_night_hours = night_window_hours(options.get("night_start_hour"), options.get("night_end_hour"))
        hours_to_start = ((start_minutes - current_minutes) % 1440.0) / 60.0 if configured_night_hours > 0 else 24.0
        night_strategy_relevant = bool(options.get("night_forecast_enabled")) and configured_night_hours > 0 and (
            in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour"))
            or hours_to_start <= 3.0
        )
        night_start_dt, night_end_dt = night_interval_bounds(
            now, options.get("night_start_hour", "22:00"), options.get("night_end_hour", "07:00")
        )

        night_rows = [
            x for x in self._hourly_forecast_cache
            if night_start_dt <= x.get("datetime", night_start_dt - timedelta(days=1)) <= night_end_dt
        ]
        night_hours = max((night_end_dt - night_start_dt).total_seconds() / 3600.0, 0.0)
        night_forecast_base = overnight_forecast_ml(
            options, self.store.data.get("night_model_ml_h"), int(self.store.data.get("night_model_samples", 0)),
            adults=effective_adults, children=effective_children, hours=night_hours,
        ) if options.get("night_forecast_enabled") else 0

        # Intelligent night model: occupancy + learned baseline + current room
        # residuals + real outdoor conditions through windows that are actually
        # open. Weather and trend terms use the same learned room air-exchange
        # model as the configurable short-term forecast.
        weather_effect = 0.0
        trend_effect = 0.0
        if options.get("night_forecast_enabled"):
            minutes_remaining = max(night_hours * 60.0, 0.0)
            trend_minutes = min(minutes_remaining, 60.0)
            # Use the same hourly night weather that the strategy will explain.
            # Current outdoor air is only a fallback when the provider has no
            # usable night forecast. This prevents text and ml values describing
            # different physical nights.
            forecast_night_ah = (
                sum(float(x.get("absolute_humidity", 0)) for x in night_rows) / len(night_rows)
                if night_rows else None
            )
            out_ah = forecast_night_ah
            if out_ah is None and outdoor_t is not None and outdoor_rh is not None:
                out_ah = absolute_humidity(outdoor_t, outdoor_rh)
            for r in valid:
                room_volume = float(r.get("volume_m3", 0) or 0)
                room_share = room_volume / calc_volume_total if calc_volume_total > 0 else 0.0
                room_prior = (daily_generation_prior / 1440.0) * room_share
                observed_source = float(r.get("forecast_source_rate_ml_min", room_prior) or room_prior)
                obs_samples = int(r.get("forecast_confidence", 0) or 0)
                trend_weight = min(max(obs_samples / 80.0, 0.0), 1.0)
                # Current shower/cooking/desorption behaviour only influences the
                # early part of a long night; it is deliberately not projected
                # linearly until morning.
                trend_effect += (observed_source - room_prior) * trend_minutes * trend_weight
                if out_ah is not None and r.get("open"):
                    fraction = exchanged_air_fraction(
                        float(r.get("learned_exchange_rate_per_min", .03)),
                        minutes_remaining,
                        float(r.get("airflow_factor", 1.0)) * (1.25 if cross else 1.0),
                    )
                    weather_effect += (out_ah - float(r.get("absolute_humidity", out_ah))) * room_volume * fraction

        routine_night_projection = 0.0
        routine_night_maturity = 0.0
        routine_night_adjustment = 0.0
        if options.get("night_forecast_enabled") and valid and night_hours > 0:
            routine_night_projection, routine_night_maturity = project_generation_ml(valid, now, night_hours * 60.0)
            if routine_night_maturity >= 15.0:
                # Blend cautiously with the established occupancy/night model.
                # The routine layer may refine timing, but cannot replace the
                # biological prior after only a few observations.
                weight = min(routine_night_maturity / 100.0, 0.55)
                routine_night_adjustment = (routine_night_projection - night_forecast_base) * weight
        # Plausibility guard: immature trend/routine layers may refine but must not
        # swamp the biology/occupancy prior. This also keeps guest influence visible.
        trend_cap = max(float(night_forecast_base) * 0.35, 150.0)
        routine_cap = max(float(night_forecast_base) * 0.45, 200.0)
        trend_effect = min(max(trend_effect, -trend_cap), trend_cap)
        routine_night_adjustment = min(max(routine_night_adjustment, -routine_cap), routine_cap)
        night_forecast = max(0, round(night_forecast_base + weather_effect + trend_effect + routine_night_adjustment))
        night_samples = int(self.store.data.get("night_model_samples", 0))
        raw_night_confidence = (
            28.0 + min(night_samples, 20) * 2.0
            + float(occupancy.get("presence_confidence", 50)) * 0.22
            + min(float(routine_night_maturity), 100.0) * 0.18
            - max(night_hours - 8.0, 0.0) * 1.5
        )
        maturity_cap = 50.0 + min(night_samples, 20) * 1.5 + min(float(routine_night_maturity), 100.0) * 0.20
        night_confidence = int(round(min(max(raw_night_confidence, 20.0), min(maturity_cap, 95.0))))
        night_buffer = min(round(actionable_potential * .40), round(night_forecast * .40)) if night_forecast > 0 else 0
        return (
            night_buffer, night_confidence, night_forecast, night_forecast_base, night_hours, night_rows,
            night_samples, night_strategy_relevant, routine_night_adjustment, routine_night_maturity,
            routine_night_projection, trend_effect, weather_effect,
        )

    def _night_weather(
        self,
        *,
        night_rows: Any, now: Any, outdoor_rh: Any, outdoor_t: Any, valid: Any,
    ) -> Any:
        """Night weather rows summarised for the night strategy (moisture, rain, temperature)."""
        # v0.18.0.3: explainable night strategy consumes the exact same night
        # window and hourly forecast rows as the ml projection above. Urgent
        # safety/live states retain priority in the unified decision layer.
        avg_indoor_ah = (
            sum(float(r.get("absolute_humidity", 0)) * float(r.get("volume_m3", 0)) for r in valid)
            / max(sum(float(r.get("volume_m3", 0)) for r in valid), 1.0)
        ) if valid else 0.0
        night_weather_available = len(night_rows) >= 2
        night_avg_ah = sum(float(x.get("absolute_humidity", 0)) for x in night_rows) / len(night_rows) if night_rows else None
        night_min_temp = min((float(x.get("temperature_c", 0)) for x in night_rows), default=None)
        night_max_rh = max((float(x.get("humidity", 0)) for x in night_rows), default=None)
        night_rain_prob = max((float(x.get("precipitation_probability", 0)) for x in night_rows), default=0.0)
        night_rain_mm = sum(float(x.get("precipitation_mm", 0)) for x in night_rows)
        rainy_conditions = {"rainy", "pouring", "lightning-rainy", "hail", "snowy-rainy"}

        def _rain_row(row: dict[str, Any]) -> bool:
            return (
                float(row.get("precipitation_probability", 0) or 0) >= 55.0
                or float(row.get("precipitation_mm", 0) or 0) >= 0.2
                or str(row.get("condition", "")) in rainy_conditions
            )

        night_rain_expected = night_rain_prob >= 55.0 or night_rain_mm >= 0.5 or any(_rain_row(x) for x in night_rows)
        first_rain_row = next((x for x in night_rows if _rain_row(x)), None)
        first_rain_dt = first_rain_row.get("datetime") if first_rain_row else None
        minutes_until_rain = (
            max((first_rain_dt - now).total_seconds() / 60.0, 0.0)
            if isinstance(first_rain_dt, datetime) else None
        )
        rain_start_label = first_rain_dt.strftime("%H:%M") if isinstance(first_rain_dt, datetime) else None
        pre_rain_rows = [
            x for x in night_rows
            if isinstance(first_rain_dt, datetime) and x.get("datetime") < first_rain_dt
        ]
        pre_rain_avg_ah = (
            sum(float(x.get("absolute_humidity", 0)) for x in pre_rain_rows) / len(pre_rain_rows)
            if pre_rain_rows else None
        )
        current_outdoor_ah = (
            absolute_humidity(outdoor_t, outdoor_rh)
            if outdoor_t is not None and outdoor_rh is not None else None
        )
        night_ah_delta = (night_avg_ah - avg_indoor_ah) if night_avg_ah is not None else None
        open_rooms = [r.get("name") for r in valid if r.get("open")]
        return (
            avg_indoor_ah, current_outdoor_ah, first_rain_dt, minutes_until_rain, night_ah_delta,
            night_avg_ah, night_max_rh, night_min_temp, night_rain_expected, night_rain_mm, night_rain_prob,
            night_weather_available, open_rooms, pre_rain_avg_ah, rain_start_label,
        )

    def _night_strategy(
        self,
        *,
        avg_indoor_ah: Any, current_outdoor_ah: Any, first_rain_dt: Any, minutes_until_rain: Any,
        night_ah_delta: Any, night_avg_ah: Any, night_confidence: Any, night_forecast: Any,
        night_forecast_base: Any, night_hours: Any, night_max_rh: Any, night_min_temp: Any,
        night_rain_expected: Any, night_rain_mm: Any, night_rain_prob: Any, night_rows: Any,
        night_strategy_relevant: Any, night_weather_available: Any, now: Any, open_rooms: Any, options: Any,
        pre_rain_avg_ah: Any, rain_start_label: Any, recommended: Any, routine_night_adjustment: Any,
        trend_effect: Any, valid: Any,
    ) -> Any:
        """Controlled night ventilation: room selection, thermal impact, pre-ventilation and strategy."""
        # v0.18.0.4: select concrete rooms for controlled night ventilation
        # before calculating thermal/moisture impact. The displayed room choice
        # and the simulated choice are therefore identical. Only rooms with a
        # configured ventilation contact can be selected.
        night_avg_temp = (
            sum(float(x.get("temperature_c", 0)) for x in night_rows) / len(night_rows)
            if night_rows else None
        )
        controlled_open_factor = 0.30
        thermal_retention_factor = 0.35
        night_room_candidates: list[dict[str, Any]] = []
        if night_avg_ah is not None and night_avg_temp is not None and night_hours > 0:
            for r in valid:
                if int(r.get("contact_count", 0) or 0) <= 0:
                    continue
                volume = max(float(r.get("volume_m3", 0) or 0), 0.0)
                room_ah = float(r.get("absolute_humidity", night_avg_ah) or night_avg_ah)
                if volume <= 0 or room_ah - night_avg_ah < 0.6:
                    continue
                rate = max(float(r.get("learned_exchange_rate_per_min", .03) or .03), 0.0)
                airflow = max(float(r.get("airflow_factor", 1.0) or 1.0), 0.0) * controlled_open_factor
                fraction = exchanged_air_fraction(rate, night_hours * 60.0, airflow)
                samples = int(r.get("outcome_feedback_samples", 0) or 0)
                outcome_weight = min(samples / 8.0, 1.0)
                temp_factor = 1.0 + (
                    min(max(float(r.get("outcome_temperature_factor", 1.0) or 1.0), 0.60), 1.50) - 1.0
                ) * outcome_weight
                room_temp = float(r.get("temperature", night_avg_temp) or night_avg_temp)
                raw_drop = min((night_avg_temp - room_temp) * fraction, 0.0)
                projected_drop = raw_drop * thermal_retention_factor * temp_factor
                moisture_effect = (night_avg_ah - room_ah) * volume * fraction
                delivered, _purchased, cost = ventilation_cost(
                    volume, room_temp, night_avg_temp,
                    min(fraction * thermal_retention_factor, 1.0), options,
                )
                if night_avg_temp >= room_temp:
                    # Warmer outside air does not create a reheating loss.
                    delivered = 0.0
                    cost = 0.0
                # Rank by useful moisture removal, with a mild thermal penalty.
                score = max(-moisture_effect, 0.0) - abs(projected_drop) * volume * 0.10
                night_room_candidates.append({
                    "room": r, "name": str(r.get("name") or r.get("key") or "Raum"),
                    "volume": volume, "fraction": fraction,
                    "moisture_effect_ml": moisture_effect,
                    "temperature_change_c": projected_drop,
                    "energy_kwh": delivered, "cost": cost, "score": score,
                })

        night_room_candidates.sort(key=lambda x: (float(x.get("score", 0)), -float(x.get("temperature_change_c", 0))), reverse=True)
        selected_night = night_room_candidates[:1]
        if len(night_room_candidates) > 1 and (
            -float(night_room_candidates[1].get("moisture_effect_ml", 0)) >= 50.0
            or -float(night_room_candidates[1].get("moisture_effect_ml", 0)) >= 0.45 * max(-float(night_room_candidates[0].get("moisture_effect_ml", 0)), 1.0)
        ):
            selected_night.append(night_room_candidates[1])

        selected_night_names = [str(x["name"]) for x in selected_night]
        thermal_volume = sum(float(x.get("volume", 0)) for x in selected_night)
        thermal_weighted_drop = sum(float(x.get("temperature_change_c", 0)) * float(x.get("volume", 0)) for x in selected_night)
        night_energy_kwh = sum(float(x.get("energy_kwh", 0)) for x in selected_night)
        night_energy_cost = sum(float(x.get("cost", 0)) for x in selected_night)
        selected_weather_effect = sum(float(x.get("moisture_effect_ml", 0)) for x in selected_night)
        night_temperature_change_c = thermal_weighted_drop / thermal_volume if thermal_volume > 0 else None
        max_night_temp_loss_c = max(float(options.get("max_temp_loss_next_5_min_c", 0.6) or 0.6) * 2.5, 1.0)
        thermal_ok = (
            bool(selected_night)
            and night_temperature_change_c is not None
            and night_temperature_change_c >= -max_night_temp_loss_c
        )

        # Separate the passive closed-window night from the current state and
        # from the selected strategy. This prevents one number being presented
        # as if it represented all three scenarios.
        night_forecast_closed = round(
            night_forecast_base + trend_effect + routine_night_adjustment
        )
        night_forecast_with_selected = round(night_forecast_closed + selected_weather_effect) if selected_night else None

        prebed_minutes = min(max(round(recommended), 10), 30)
        pre_vent_source_ah = pre_rain_avg_ah
        if current_outdoor_ah is not None and not in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour")):
            pre_vent_source_ah = current_outdoor_ah
        pre_vent_effect = 0.0
        if selected_night and pre_vent_source_ah is not None:
            for item in selected_night:
                r = item["room"]
                room_ah = float(r.get("absolute_humidity", pre_vent_source_ah) or pre_vent_source_ah)
                if room_ah <= pre_vent_source_ah:
                    continue
                rate = max(float(r.get("learned_exchange_rate_per_min", .03) or .03), 0.0)
                airflow = max(float(r.get("airflow_factor", 1.0) or 1.0), 0.0)
                fraction = exchanged_air_fraction(rate, prebed_minutes, airflow)
                pre_vent_effect += (pre_vent_source_ah - room_ah) * float(item.get("volume", 0)) * fraction
        night_strategy = build_night_strategy(
            avg_indoor_ah=avg_indoor_ah,
            first_rain_dt=first_rain_dt,
            max_night_temp_loss_c=max_night_temp_loss_c,
            minutes_until_rain=minutes_until_rain,
            night_ah_delta=night_ah_delta,
            night_avg_ah=night_avg_ah,
            night_avg_temp=night_avg_temp,
            night_confidence=night_confidence,
            night_energy_cost=night_energy_cost,
            night_energy_kwh=night_energy_kwh,
            night_forecast=night_forecast,
            night_forecast_closed=night_forecast_closed,
            night_forecast_with_selected=night_forecast_with_selected,
            night_hours=night_hours,
            night_max_rh=night_max_rh,
            night_min_temp=night_min_temp,
            night_rain_expected=night_rain_expected,
            night_rain_mm=night_rain_mm,
            night_rain_prob=night_rain_prob,
            night_strategy_relevant=night_strategy_relevant,
            night_temperature_change_c=night_temperature_change_c,
            night_weather_available=night_weather_available,
            open_rooms=open_rooms,
            pre_vent_effect=pre_vent_effect,
            pre_vent_source_ah=pre_vent_source_ah,
            prebed_minutes=prebed_minutes,
            rain_start_label=rain_start_label,
            selected_night=selected_night,
            selected_night_names=selected_night_names,
            selected_weather_effect=selected_weather_effect,
            thermal_ok=thermal_ok,
        )
        return (night_strategy,)
