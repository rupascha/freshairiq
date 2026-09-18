"""Night moisture forecast and adaptive whole-house learning."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any


def _minute_of_day(value: Any, default_hour: int) -> int:
    """Parse HA time-selector values with minute precision; numeric values remain hour-compatible."""
    if isinstance(value, str) and ":" in value:
        try:
            hour_raw, minute_raw = value.split(":", 1)
            hour = int(hour_raw) % 24
            minute = min(max(int(minute_raw[:2]), 0), 59)
            return hour * 60 + minute
        except (TypeError, ValueError):
            return default_hour * 60
    try:
        return (int(value) % 24) * 60
    except (TypeError, ValueError):
        return default_hour * 60


def night_window_hours(start_hour: Any, end_hour: Any) -> float:
    start = _minute_of_day(start_hour, 22)
    end = _minute_of_day(end_hour, 7)
    # Equal start/end is treated as a disabled night window. Interpreting the
    # same timestamp as 24 hours caused contradictory all-day night forecasts.
    if start == end:
        return 0.0
    return float(((end - start) % 1440) / 60.0)


def night_interval_bounds(now: datetime, start_hour: Any, end_hour: Any) -> tuple[datetime, datetime]:
    """Return the remaining current night or the next complete night interval."""
    start = _minute_of_day(start_hour, 22)
    end = _minute_of_day(end_hour, 7)
    if start == end:
        return now, now

    current = now.hour * 60 + now.minute + now.second / 60.0
    if in_night_window(now, start_hour, end_hour):
        end_dt = now.replace(hour=end // 60, minute=end % 60, second=0, microsecond=0)
        if current >= end:
            end_dt += timedelta(days=1)
        return now, end_dt

    start_dt = now.replace(hour=start // 60, minute=start % 60, second=0, microsecond=0)
    if start_dt <= now:
        start_dt += timedelta(days=1)
    duration_min = (end - start) % 1440
    return start_dt, start_dt + timedelta(minutes=duration_min)


def _property_background_factor(options: dict[str, Any]) -> float:
    return {
        "house": 1.0,
        "apartment": 0.85,
        "maisonette": 0.92,
        "other": 1.0,
    }.get(str(options.get("property_type", "house")), 1.0)


def baseline_night_rate_ml_h(options: dict[str, Any], adults: float | None = None, children: float | None = None) -> float:
    """Biology-based prior; the user no longer tunes moisture-per-person values."""
    # Backward compatibility with v0.5 custom values, but new entries use fixed priors.
    if "moisture_g_per_person_hour_night" in options and "adult_occupants" not in options:
        people = max(int(options.get("occupants", 0)), 0)
        return people * max(float(options.get("moisture_g_per_person_hour_night", 45.0)), 0.0) + max(float(options.get("background_moisture_g_per_hour", 10.0)), 0.0)
    adults = max(float(options.get("adult_occupants", 0) if adults is None else adults), 0.0)
    children = max(float(options.get("child_occupants", 0) if children is None else children), 0.0)
    adult_rate = float(options.get("adult_night_moisture_ml_h", 45.0))
    child_rate = float(options.get("child_night_moisture_ml_h", 30.0))
    background = float(options.get("background_night_moisture_ml_h", 10.0)) * _property_background_factor(options)
    return adults * adult_rate + children * child_rate + background


def effective_night_rate_ml_h(
    options: dict[str, Any], learned_rate: float | None, samples: int,
    adults: float | None = None, children: float | None = None,
) -> float:
    """Blend biological prior and learned night behaviour, occupancy-aware."""
    base = baseline_night_rate_ml_h(options, adults, children)
    if learned_rate is None or samples <= 0:
        return base
    # A learned whole-house rate from nights with a different occupancy must not
    # dominate today's forecast. Scale it by the current/configured prior ratio.
    configured_base = max(baseline_night_rate_ml_h(options), 1.0)
    occupancy_scaled_learned = max(float(learned_rate), 0.0) * (base / configured_base)
    weight = min(samples / 12.0, 0.85)
    return (base * (1.0 - weight)) + (occupancy_scaled_learned * weight)


def remaining_night_hours(now: datetime, start_hour: Any, end_hour: Any) -> float:
    """Hours until the relevant night end; during daytime, next full night."""
    start = _minute_of_day(start_hour, 22)
    end = _minute_of_day(end_hour, 7)
    if start == end:
        return 0.0
    full_min = float((end - start) % 1440)
    if in_night_window(now, start_hour, end_hour):
        current = now.hour * 60 + now.minute + now.second / 60.0
        end_abs = float(end)
        if start > end and current >= start:
            end_abs += 1440.0
        if start > end and current < end:
            current += 1440.0
            end_abs += 1440.0
        return max((end_abs - current) / 60.0, 0.0)
    return full_min / 60.0


def overnight_forecast_ml(
    options: dict[str, Any], learned_rate: float | None, samples: int,
    *, adults: float | None = None, children: float | None = None,
    hours: float | None = None,
) -> int:
    if hours is None:
        hours = night_window_hours(options.get("night_start_hour", "22:00"), options.get("night_end_hour", "07:00"))
    return round(effective_night_rate_ml_h(options, learned_rate, samples, adults, children) * max(float(hours), 0.0))


def estimated_daily_moisture_ml(
    options: dict[str, Any], adults: float | None = None, children: float | None = None,
) -> int:
    configured_adults = max(float(options.get("adult_occupants", options.get("occupants", 0)) or 0), 0.0)
    configured_children = max(float(options.get("child_occupants", 0) or 0), 0.0)
    adults = configured_adults if adults is None else max(float(adults), 0.0)
    children = configured_children if children is None else max(float(children), 0.0)
    configured_total = configured_adults + configured_children
    present_total = adults + children
    occupancy_ratio = 1.0 if configured_total <= 0 else min(max(present_total / configured_total, 0.0), 1.5)
    # Household activity (cooking, showers, etc.) drops strongly when nobody is
    # home, but a small passive building/background component remains.
    activity_factor = 0.15 + 0.85 * occupancy_ratio
    return round(
        adults * float(options.get("adult_day_moisture_ml", 1000.0))
        + children * float(options.get("child_day_moisture_ml", 700.0))
        + float(options.get("household_day_moisture_ml", 1000.0)) * _property_background_factor(options) * activity_factor
    )


def update_night_learning(old_rate: float | None, old_samples: int, observed_rate: float) -> tuple[float | None, int]:
    if observed_rate < 0 or observed_rate > 1000:
        return old_rate, old_samples
    if old_rate is None or old_samples <= 0:
        return round(observed_rate, 1), 1
    alpha = 0.18 if old_samples < 10 else 0.10
    bounded = min(max(observed_rate, old_rate * 0.5), max(old_rate * 1.5, 20.0))
    return round(old_rate * (1-alpha) + bounded * alpha, 1), min(old_samples + 1, 1000)


def in_night_window(now: datetime, start_hour: Any, end_hour: Any) -> bool:
    start = _minute_of_day(start_hour, 22)
    end = _minute_of_day(end_hour, 7)
    current = now.hour * 60 + now.minute + now.second / 60.0
    if start > end:
        return current >= start or current < end
    return start <= current < end


def horizon_forecast(
    *,
    current_ah: float,
    source_ah: float,
    current_temp_c: float,
    source_temp_c: float,
    volume_m3: float,
    rate_per_min: float,
    airflow_bonus: float,
    horizon_min: float,
    prior_source_ml_min: float = 0.0,
    learned_source_ml_min: float | None = None,
    learned_thermal_residual_c_min: float | None = None,
    observation_samples: int = 0,
    running: bool = False,
    session_elapsed_min: float = 0.0,
    session_fresh_measurements: int = 0,
    recent_observed_removed_ml_min: float | None = None,
    target_ah: float | None = None,
    cap_positive_to_target: bool = False,
    future_source_boundaries: dict[int, dict[str, Any]] | None = None,
    min_return_next_5_min_ml: float = 25.0,
    max_temp_loss_next_5_min_c: float = 0.6,
    min_efficiency_ml_per_01c: float = 8.0,
    min_duration_min: float = 3.0,
    max_duration_min: float = 20.0,
    operating_profile: str = "comfort",
    model_maturity_pct: float | None = None,
    measurement_frame_quality: str | None = None,
) -> dict[str, Any]:
    """Hybrid short-term forecast for moisture and room-air temperature.

    It combines the learned air-exchange model with a learned residual from
    recent measurements.  The residual captures internal moisture generation,
    sorption/desorption and heating/thermal-mass effects that a pure outdoor-
    air mixing model cannot explain.

    Moisture result uses FreshAirIQ's established sign convention:
    positive = moisture removed, negative = moisture added.
    """
    from .energy import exchanged_air_fraction

    horizon = min(max(float(horizon_min), 1.0), 120.0)
    bonus = min(max(float(airflow_bonus), 0.25), 2.5)
    volume = max(float(volume_m3), 0.0)

    samples = max(int(observation_samples), 0)
    learned_weight = min(samples / 6.0, 1.0)
    if running:
        learned_weight *= min(max(float(session_elapsed_min), 0.0) / 12.0, 1.0)
    source_rate = max(float(prior_source_ml_min), -20.0)
    if learned_source_ml_min is not None:
        learned = min(max(float(learned_source_ml_min), -25.0), 25.0)
        source_rate = source_rate * (1.0 - learned_weight) + learned * learned_weight

    # During an active ventilation session, recent sensor observations may
    # correct the model.  The correction is deliberately established exactly
    # as before; for horizons >5 min it is then applied step-by-step instead of
    # projecting one measured rate linearly across the complete horizon.
    live_observation_weight = 0.0
    live_adapted = False
    if running and recent_observed_removed_ml_min is not None and session_elapsed_min >= 5.0:
        fresh_weight = min(max(float(session_fresh_measurements) / 2.0, 0.0), 1.0)
        elapsed_weight = min(max((float(session_elapsed_min) - 5.0) / 20.0, 0.0), 1.0)
        live_observation_weight = 0.94 * fresh_weight * elapsed_weight
        live_adapted = live_observation_weight > 0.0

    def _effective_residual_minutes(minutes: float) -> float:
        """Damped extrapolation of internal/thermal residuals."""
        minutes = max(float(minutes), 0.0)
        return minutes if minutes <= 20.0 else 20.0 + (minutes - 20.0) * 0.55

    def _future_boundary(minute: float) -> tuple[float, float, int | None]:
        """Return the future reference boundary nearest to this step end.

        The coordinator supplies 5-minute weather-interpolated points when the
        room uses the outdoor weather entity as its reference. Rooms with a
        custom reference sensor intentionally keep the current reference state.
        """
        if not future_source_boundaries:
            return float(source_ah), float(source_temp_c), None
        key = int(round(minute))
        point = future_source_boundaries.get(key)
        if not isinstance(point, dict):
            return float(source_ah), float(source_temp_c), None
        try:
            ah = float(point.get("absolute_humidity", source_ah))
            temp = float(point.get("temperature_c", source_temp_c))
        except (TypeError, ValueError):
            return float(source_ah), float(source_temp_c), None
        if not (0.0 <= ah <= 40.0 and -40.0 <= temp <= 60.0):
            return float(source_ah), float(source_temp_c), None
        try:
            confidence = int(point.get("confidence")) if point.get("confidence") is not None else None
        except (TypeError, ValueError):
            confidence = None
        return ah, temp, confidence

    # Keep the established 5-minute control path bit-for-bit in spirit. This
    # hotfix only changes user-selected horizons above five minutes, so the
    # close/continue gate cannot regress because of the new simulation.
    optimal_close_in_min: float | None = None
    optimal_close_reason: str | None = None
    temperature_path: list[dict[str, float]] = []

    # Forecast-side end-point thresholds mirror the existing 5-minute close
    # criteria, but are advisory only. The real-time room model remains the
    # authority for an actual "close now" decision.
    profile = str(operating_profile or "comfort")
    forecast_min_return = max(float(min_return_next_5_min_ml), 0.0)
    forecast_max_temp_loss = max(float(max_temp_loss_next_5_min_c), 0.05)
    forecast_min_efficiency = max(float(min_efficiency_ml_per_01c), 0.0)
    if profile == "dehumidify":
        forecast_min_return *= 0.60
        forecast_max_temp_loss *= 1.50
        forecast_min_efficiency *= 0.60
    elif profile == "summer_cooling":
        forecast_min_return *= 0.50

    # Hotfix 0.20.2.5: long-horizon close timing must also respect cumulative
    # cooling, not only the loss of the latest 5-minute slice. Derive the
    # cumulative guard from the already profile-adjusted thermal tolerance.
    max_cumulative_temp_loss = max(forecast_max_temp_loss * 2.0, 1.0)
    min_forecast_end_temp = 17.0

    if horizon <= 5.0:
        fraction = exchanged_air_fraction(rate_per_min, horizon, bonus)
        physical_removed_ml = (float(current_ah) - float(source_ah)) * volume * fraction
        uncapped_physical_removed_ml = physical_removed_ml

        target_cap_ml: float | None = None
        if cap_positive_to_target and target_ah is not None and physical_removed_ml > 0:
            target_cap_ml = max((float(current_ah) - float(target_ah)) * volume, 0.0)
            physical_removed_ml = min(physical_removed_ml, target_cap_ml)

        residual_minutes = _effective_residual_minutes(horizon)
        internal_change_ml = source_rate * residual_minutes
        net_removed_ml = physical_removed_ml - internal_change_ml
        ventilation_effect_ml = physical_removed_ml
        observed_projection_ml = None
        if live_adapted:
            observed_projection_ml = float(recent_observed_removed_ml_min) * horizon
            scale = max(abs(float(uncapped_physical_removed_ml)), 20.0)
            observed_projection_ml = min(max(observed_projection_ml, -scale), scale * 1.5)
            blended = (float(uncapped_physical_removed_ml) * (1.0 - live_observation_weight)
                       + observed_projection_ml * live_observation_weight)
            if target_cap_ml is not None and blended > 0:
                blended = min(blended, target_cap_ml)
            ventilation_effect_ml = blended

        physical_dt = (float(source_temp_c) - float(current_temp_c)) * fraction
        thermal_residual = 0.0
        if learned_thermal_residual_c_min is not None:
            thermal_residual = min(max(float(learned_thermal_residual_c_min), -0.20), 0.20) * learned_weight * residual_minutes
        temp_delta = physical_dt + thermal_residual
        future_temp = min(max(float(current_temp_c) + temp_delta, -10.0), 50.0)
        temp_delta = future_temp - float(current_temp_c)
        temperature_path.append({
            "start_min": 0.0, "end_min": float(horizon), "duration_min": float(horizon),
            "room_start_c": float(current_temp_c), "source_c": float(source_temp_c),
            "room_end_c": float(future_temp),
        })
        weather_confidence = None
        simulation_steps = 1
        simulated_final_ah = float(current_ah) - (net_removed_ml / volume if volume > 0 else 0.0)
    else:
        # Hotfix 0.20.2.1: true rolling horizon simulation.  Every step starts
        # from the room state predicted by the previous step. This means the
        # moisture/temperature gradient, internal source contribution and live
        # measurement correction all evolve across a 15/30/60/120-minute view.
        # With weather forecast data, the outdoor reference boundary also moves
        # in five-minute increments instead of being frozen at "now".
        step_size = 5.0
        state_ah = float(current_ah)
        state_temp = float(current_temp_c)
        initial_gradient = abs(float(current_ah) - float(source_ah))
        cumulative_min = 0.0
        uncapped_physical_removed_ml = 0.0
        ventilation_effect_uncapped_ml = 0.0
        internal_change_ml = 0.0
        exchange_remaining = 1.0
        observed_projection_ml = 0.0 if live_adapted else None
        weather_confidences: list[int] = []
        simulation_steps = 0
        total_min_duration = max(float(min_duration_min), 0.0)
        total_max_duration = max(float(max_duration_min), total_min_duration)
        elapsed_before_forecast = float(session_elapsed_min) if running else 0.0
        hard_max_in = max(total_max_duration - elapsed_before_forecast, 0.0)

        while cumulative_min < horizon - 1e-9:
            step = min(step_size, horizon - cumulative_min)
            step_end = cumulative_min + step
            step_source_ah, step_source_temp, boundary_conf = _future_boundary(step_end)
            if boundary_conf is not None:
                weather_confidences.append(boundary_conf)

            step_fraction = exchanged_air_fraction(rate_per_min, step, bonus)
            exchange_remaining *= (1.0 - step_fraction)
            model_removed = (state_ah - step_source_ah) * volume * step_fraction
            uncapped_physical_removed_ml += model_removed

            prev_effective = _effective_residual_minutes(cumulative_min)
            next_effective = _effective_residual_minutes(step_end)
            effective_step_min = max(next_effective - prev_effective, 0.0)
            step_internal = source_rate * effective_step_min
            internal_change_ml += step_internal

            # Recent measured net drying is most trustworthy near "now".
            # As the simulation advances, its influence fades and is also scaled
            # by the remaining moisture gradient, preventing a measured 5-minute
            # rate from being copied unchanged over a full hour.
            step_effect = model_removed
            if live_adapted:
                gradient = abs(state_ah - step_source_ah)
                gradient_ratio = min(max(gradient / max(initial_gradient, 0.15), 0.0), 1.5)
                observed_step = float(recent_observed_removed_ml_min) * step * gradient_ratio
                distance_decay = max(0.97, 1.0 - 0.03 * (cumulative_min / max(horizon, 1.0)))
                step_weight = live_observation_weight * distance_decay
                scale = max(abs(model_removed), 5.0)
                observed_step = min(max(observed_step, -scale), scale * 1.5)
                step_effect = model_removed * (1.0 - step_weight) + observed_step * step_weight
                observed_projection_ml += observed_step

            ventilation_effect_uncapped_ml += step_effect

            if volume > 0.0:
                # The next step sees the predicted result of this step. Internal
                # moisture is added after exchange, then may be removed by later
                # steps, unlike the former one-shot extrapolation.
                state_ah -= step_effect / volume
                state_ah += step_internal / volume
                state_ah = min(max(state_ah, 0.0), 40.0)

            step_room_start_temp = state_temp
            physical_dt = (step_source_temp - state_temp) * step_fraction
            state_temp += physical_dt
            thermal_step = 0.0
            if learned_thermal_residual_c_min is not None:
                thermal_step = min(max(float(learned_thermal_residual_c_min), -0.20), 0.20) * learned_weight * effective_step_min
                state_temp += thermal_step
            state_temp = min(max(state_temp, -10.0), 50.0)
            temperature_path.append({
                "start_min": float(cumulative_min), "end_min": float(step_end), "duration_min": float(step),
                "room_start_c": float(step_room_start_temp), "source_c": float(step_source_temp),
                "room_end_c": float(state_temp),
            })

            # Hotfix 0.20.2.2: derive the first efficient end point inside the
            # selected horizon from the same rolling future state. This does not
            # issue a close command; it only tells the UI when the simulation
            # expects the marginal benefit to stop justifying more ventilation.
            if optimal_close_in_min is None:
                total_elapsed_at_step = elapsed_before_forecast + step_end
                step_temp_delta = physical_dt + thermal_step
                positive_step_effect = max(step_effect, 0.0)
                step_efficiency = 999.0 if step_temp_delta >= -0.05 else positive_step_effect / (abs(step_temp_delta) * 10.0)
                reached_target = bool(target_ah is not None and state_ah <= float(target_ah) + 0.02)
                low_return = positive_step_effect < forecast_min_return
                thermal_bad = (
                    profile != "summer_cooling"
                    and step_temp_delta <= -forecast_max_temp_loss
                    and step_efficiency < forecast_min_efficiency
                )
                cumulative_temp_loss = max(float(current_temp_c) - state_temp, 0.0)
                cumulative_thermal_bad = (
                    profile != "summer_cooling"
                    and cumulative_temp_loss >= max_cumulative_temp_loss
                )
                projected_end_too_cold = (
                    profile != "summer_cooling"
                    and state_temp <= min_forecast_end_temp
                )
                hard_max = hard_max_in <= horizon and step_end >= hard_max_in - 1e-9
                decision_ready_by_time = total_elapsed_at_step >= total_min_duration
                if hard_max:
                    # A hard configured maximum is not rounded to the next
                    # 5-minute simulation point. Example: after 19 min of a
                    # 20-min maximum the advisory end point is exactly 1 min.
                    optimal_close_in_min = hard_max_in
                    optimal_close_reason = "max_duration"
                elif decision_ready_by_time and (
                    reached_target or low_return or thermal_bad
                    or cumulative_thermal_bad or projected_end_too_cold
                ):
                    optimal_close_in_min = step_end
                    optimal_close_reason = (
                        "target_reached" if reached_target else
                        "projected_end_temperature" if projected_end_too_cold else
                        "cumulative_temperature_loss" if cumulative_thermal_bad else
                        "thermal_efficiency" if thermal_bad else
                        "marginal_return"
                    )

            cumulative_min = step_end
            simulation_steps += 1

        target_cap_ml = None
        physical_removed_ml = uncapped_physical_removed_ml
        ventilation_effect_ml = ventilation_effect_uncapped_ml
        if cap_positive_to_target and target_ah is not None and physical_removed_ml > 0:
            target_cap_ml = max((float(current_ah) - float(target_ah)) * volume, 0.0)
            physical_removed_ml = min(physical_removed_ml, target_cap_ml)
            if ventilation_effect_ml > 0:
                ventilation_effect_ml = min(ventilation_effect_ml, target_cap_ml)

        net_removed_ml = ventilation_effect_ml - internal_change_ml
        fraction = 1.0 - exchange_remaining
        temp_delta = state_temp - float(current_temp_c)
        weather_confidence = min(weather_confidences) if weather_confidences else None
        simulated_final_ah = state_ah

    base_confidence = 35.0 + min(samples, 6) * 8.0
    if running:
        base_confidence += min(max(float(session_elapsed_min), 0.0), 20.0) * 1.0
    horizon_penalty = max(0.0, horizon - 15.0) * 0.35
    confidence = int(round(min(max(base_confidence - horizon_penalty, 20.0), 95.0)))

    # Hotfix 0.20.2.3: short-term confidence is a model-confidence indicator,
    # not a probability of hitting the exact predicted mL value. Mature live
    # observations can raise it, but the room's persisted learning/outcome
    # maturity is now a hard upper bound so a young model cannot jump to 95 %.
    if model_maturity_pct is not None:
        maturity_cap = min(max(float(model_maturity_pct), 35.0), 95.0)
        confidence = min(confidence, int(round(maturity_cap)))
    if weather_confidence is not None:
        confidence = min(confidence, max(min(int(weather_confidence), 95), 20))

    # v0.25.0.2: confidence must describe the quality of the *current input
    # frame* as well as model maturity. A mathematically valid forecast based
    # on held/stale sensor values must never be presented as high-confidence.
    # The physical result is retained for internal continuity/diagnostics; the
    # UI and recommendation layer can now see that the evidence is weak.
    frame_quality = str(measurement_frame_quality or "legacy").lower()
    frame_confidence_caps = {
        "excellent": 95,
        "acceptable": 75,
        "uncertain": 40,
        "held": 35,
        "stale": 0,
    }
    if frame_quality in frame_confidence_caps:
        confidence = min(confidence, frame_confidence_caps[frame_quality])

    return {
        "horizon_min": int(round(horizon)),
        "moisture_effect_ml": round(ventilation_effect_ml),
        "physical_moisture_effect_ml": round(physical_removed_ml),
        "uncapped_physical_moisture_effect_ml": round(uncapped_physical_removed_ml),
        "internal_moisture_effect_ml": round(internal_change_ml),
        "net_moisture_change_ml": round(net_removed_ml),
        "temperature_change_c": round(temp_delta, 2),
        "exchange_fraction": round(fraction, 4),
        "confidence": confidence,
        "source_rate_ml_min": round(source_rate, 3),
        "observed_projection_ml": round(observed_projection_ml) if observed_projection_ml is not None else None,
        "live_observation_weight": round(live_observation_weight, 3),
        "live_adapted": live_adapted,
        "target_cap_ml": round(target_cap_ml) if target_cap_ml is not None else None,
        "target_limited": bool(target_cap_ml is not None and ventilation_effect_ml >= target_cap_ml - 0.5),
        "simulation_steps": simulation_steps,
        "simulated_final_ah": round(simulated_final_ah, 3),
        "future_weather_used": bool(weather_confidence is not None),
        "future_weather_confidence": weather_confidence,
        "optimal_close_in_min": round(optimal_close_in_min, 1) if optimal_close_in_min is not None else None,
        "optimal_close_reason": optimal_close_reason,
        "temperature_path": temperature_path,
        "max_cumulative_temp_loss_c": round(max_cumulative_temp_loss, 2),
        "min_forecast_end_temp_c": round(min_forecast_end_temp, 1),
        "method": (
            ("rolling_live_measured_target_limited" if target_cap_ml is not None else "rolling_live_measured")
            if horizon > 5.0 and live_adapted else
            ("rolling_model_target_limited" if target_cap_ml is not None else "rolling_model")
            if horizon > 5.0 else
            ("hybrid_live_measured_target_limited" if target_cap_ml is not None else "hybrid_live_measured")
            if live_adapted else
            ("hybrid_live_model_target_limited" if target_cap_ml is not None else "hybrid_live_model")
        ),
    }
