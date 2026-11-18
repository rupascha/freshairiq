"""Night moisture forecast and adaptive whole-house learning."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from functools import partial
from math import log1p
from typing import Any

from .iq2 import effective_rate, relax


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


def elapsed_minutes(start: datetime, end: datetime) -> float:
    """F12: real minutes between two times – through UTC, so a clock change and its repeated hour count as they last.

    Datetimes of one zone subtract as wall clock times in Python; naive values (no zone) keep that plain difference.
    """
    if start.tzinfo is None or end.tzinfo is None:
        return (end - start).total_seconds() / 60.0
    return (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 60.0


def night_interval_bounds(now: datetime, start_hour: Any, end_hour: Any) -> tuple[datetime, datetime]:
    """Return the remaining current night or the next complete night interval.

    The bounds are local wall-clock times (the night is configured by the clock); its length is
    ``elapsed_minutes`` between them, never the wall-clock difference (F12).
    """
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
        "attic_apartment": 0.85,
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


def _boundary_at(boundaries: dict[int, dict[str, Any]] | None, source_ah: float, source_temp_c: float, minute: float) -> tuple[float, float, int | None]:
    """Future reference boundary nearest to a step end (absolute humidity, temperature, weather confidence).

    The coordinator supplies 5-minute weather-interpolated points when the room uses the outdoor weather entity as
    its reference. Rooms with a custom reference sensor keep the current reference state.
    """
    point = (boundaries or {}).get(int(round(minute)))
    if not isinstance(point, dict):
        return source_ah, source_temp_c, None
    try:
        ah = float(point.get("absolute_humidity", source_ah))
        temp = float(point.get("temperature_c", source_temp_c))
    except (TypeError, ValueError):
        return source_ah, source_temp_c, None
    if not (0.0 <= ah <= 40.0 and -40.0 <= temp <= 60.0):
        return source_ah, source_temp_c, None
    try:
        confidence = int(point.get("confidence")) if point.get("confidence") is not None else None
    except (TypeError, ValueError):
        confidence = None
    return ah, temp, confidence


def _observed_equilibrium_shift(
    *, live_adapted: bool, recent_observed_removed_ml_min: Any, current_ah: Any, source_ah: Any, anchor_ah: float,
    rate_per_min: Any, bonus: float, moisture_share: float, volume: float,
) -> float | None:
    """Equilibrium offset (g/m³) that makes the buffered model reproduce the measured net drying rate right now.

    The model removes ``k/share * (A - A_eq) * V`` per minute at the current state. A measured rate that differs
    states that the equilibrium the room is heading to differs; every horizon then relaxes from the same start state
    towards that equilibrium instead of projecting the measured rate linearly. None = no usable live observation.
    """
    if not live_adapted or volume <= 0.0:
        return None
    decay = -log1p(-effective_rate(rate_per_min, bonus)) / moisture_share
    if decay <= 0.0:
        return None
    model_gradient = float(current_ah) - (moisture_share * float(source_ah) + (1.0 - moisture_share) * anchor_ah)
    bound = max(abs(model_gradient), abs(float(current_ah) - float(source_ah)))
    observed_gradient = min(max(float(recent_observed_removed_ml_min) / (decay * volume), -bound), bound)
    return model_gradient - observed_gradient


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
    moisture_air_share: float = 1.0,
    thermal_air_share: float = 1.0,
    anchor_ah: float | None = None,
    anchor_temp_c: float | None = None,
) -> dict[str, Any]:
    """Hybrid short-term forecast for moisture and room-air temperature.

    IQ2 (0.26.7.1): the room state advances with ``iq2.relax`` towards the equilibrium of reference air and moisture
    buffer / thermal mass (``anchor_*``: room state when the airing started; shares of 1 = the earlier plain model).
    Result quantities: ``net_room_change_ml`` (vapour change of the room air, not target-limited),
    ``outdoor_transport_ml`` (modelled, not measured), ``to_target_ml`` and the target-limited ``moisture_effect_ml``.

    It combines the learned air-exchange model with a learned residual from recent measurements (internal moisture
    generation, sorption/desorption, heating) that the mixing model cannot explain.

    Sign convention: positive = moisture removed, negative = moisture added.
    """
    from .energy import exchanged_air_fraction

    moisture_share, thermal_share = min(max(float(moisture_air_share), 0.05), 1.0), min(max(float(thermal_air_share), 0.01), 1.0)
    anchor_ah, anchor_temp_c = float(current_ah if anchor_ah is None else anchor_ah), float(current_temp_c if anchor_temp_c is None else anchor_temp_c)
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
    observed_shift_ah = _observed_equilibrium_shift(
        live_adapted=live_adapted, recent_observed_removed_ml_min=recent_observed_removed_ml_min, current_ah=current_ah,
        source_ah=source_ah, anchor_ah=anchor_ah, rate_per_min=rate_per_min, bonus=bonus, moisture_share=moisture_share,
        volume=volume,
    )

    def _effective_residual_minutes(minutes: float) -> float:
        """Damped extrapolation of internal/thermal residuals."""
        minutes = max(float(minutes), 0.0)
        return minutes if minutes <= 20.0 else 20.0 + (minutes - 20.0) * 0.55

    _future_boundary = partial(_boundary_at, future_source_boundaries, float(source_ah), float(source_temp_c))

    # Keep the established 5-minute control path bit-for-bit in spirit. This
    # hotfix only changes user-selected horizons above five minutes, so the
    # close/continue gate cannot regress because of the new simulation.
    optimal_close_in_min: float | None = None
    optimal_close_reason: str | None = None
    temperature_path: list[dict[str, float]] = []

    (
        forecast_max_temp_loss, forecast_min_efficiency, forecast_min_return, max_cumulative_temp_loss,
        min_forecast_end_temp, profile,
    ) = _forecast_end_thresholds(
        max_temp_loss_next_5_min_c=max_temp_loss_next_5_min_c,
        min_efficiency_ml_per_01c=min_efficiency_ml_per_01c,
        min_return_next_5_min_ml=min_return_next_5_min_ml, operating_profile=operating_profile,
    )

    (
        fraction, internal_change_ml, net_removed_ml, observed_projection_ml, optimal_close_in_min,
        optimal_close_reason, physical_removed_ml, simulated_final_ah, simulation_steps, target_cap_ml,
        temp_delta, uncapped_physical_removed_ml, ventilation_effect_ml, weather_confidence,
        net_uncapped_ml, outdoor_transport_ml,
    ) = _forecast_path(
        _effective_residual_minutes=_effective_residual_minutes, _future_boundary=_future_boundary,
        bonus=bonus, cap_positive_to_target=cap_positive_to_target, current_ah=current_ah,
        current_temp_c=current_temp_c, exchanged_air_fraction=exchanged_air_fraction,
        forecast_max_temp_loss=forecast_max_temp_loss, forecast_min_efficiency=forecast_min_efficiency,
        forecast_min_return=forecast_min_return, horizon=horizon,
        learned_thermal_residual_c_min=learned_thermal_residual_c_min, learned_weight=learned_weight,
        live_adapted=live_adapted, live_observation_weight=live_observation_weight,
        max_cumulative_temp_loss=max_cumulative_temp_loss, max_duration_min=max_duration_min,
        min_duration_min=min_duration_min, min_forecast_end_temp=min_forecast_end_temp,
        optimal_close_in_min=optimal_close_in_min, optimal_close_reason=optimal_close_reason, profile=profile,
        rate_per_min=rate_per_min, observed_shift_ah=observed_shift_ah,
        running=running, session_elapsed_min=session_elapsed_min, source_ah=source_ah,
        source_rate=source_rate, source_temp_c=source_temp_c, target_ah=target_ah,
        temperature_path=temperature_path, volume=volume,
        anchor_ah=anchor_ah, anchor_temp_c=anchor_temp_c, moisture_share=moisture_share, thermal_share=thermal_share,
    )

    return _forecast_result(
        to_target_ml=(max((float(current_ah) - float(target_ah)) * volume, 0.0) if target_ah is not None else None),
        net_room_change_ml=net_uncapped_ml, outdoor_transport_ml=outdoor_transport_ml,
        fraction=fraction, horizon=horizon, internal_change_ml=internal_change_ml, live_adapted=live_adapted,
        live_observation_weight=live_observation_weight, max_cumulative_temp_loss=max_cumulative_temp_loss,
        measurement_frame_quality=measurement_frame_quality, min_forecast_end_temp=min_forecast_end_temp,
        model_maturity_pct=model_maturity_pct, net_removed_ml=net_removed_ml,
        observed_projection_ml=observed_projection_ml, optimal_close_in_min=optimal_close_in_min,
        optimal_close_reason=optimal_close_reason, physical_removed_ml=physical_removed_ml, running=running,
        samples=samples, session_elapsed_min=session_elapsed_min, simulated_final_ah=simulated_final_ah,
        simulation_steps=simulation_steps, source_rate=source_rate, target_cap_ml=target_cap_ml,
        temp_delta=temp_delta, temperature_path=temperature_path,
        uncapped_physical_removed_ml=uncapped_physical_removed_ml,
        ventilation_effect_ml=ventilation_effect_ml, weather_confidence=weather_confidence,
    )


def _forecast_end_thresholds(
    *,
    max_temp_loss_next_5_min_c: Any, min_efficiency_ml_per_01c: Any, min_return_next_5_min_ml: Any,
    operating_profile: Any,
) -> Any:
    """Advisory forecast end-point thresholds adjusted to the operating profile."""
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
    return (
        forecast_max_temp_loss, forecast_min_efficiency, forecast_min_return, max_cumulative_temp_loss,
        min_forecast_end_temp, profile,
    )


def _forecast_path(
    *,
    _effective_residual_minutes: Any, _future_boundary: Any, bonus: Any, cap_positive_to_target: Any,
    current_ah: Any, current_temp_c: Any, exchanged_air_fraction: Any, forecast_max_temp_loss: Any,
    forecast_min_efficiency: Any, forecast_min_return: Any, horizon: Any, learned_thermal_residual_c_min: Any,
    learned_weight: Any, live_adapted: Any, live_observation_weight: Any, max_cumulative_temp_loss: Any,
    max_duration_min: Any, min_duration_min: Any, min_forecast_end_temp: Any, optimal_close_in_min: Any,
    optimal_close_reason: Any, profile: Any, rate_per_min: Any, observed_shift_ah: Any,
    running: Any, session_elapsed_min: Any, source_ah: Any, source_rate: Any, source_temp_c: Any,
    target_ah: Any, temperature_path: Any, volume: Any,
    anchor_ah: Any = None, anchor_temp_c: Any = None, moisture_share: Any = 1.0, thermal_share: Any = 1.0,
) -> Any:
    """Moisture and temperature path over the horizon (single slice or stepped simulation)."""
    if horizon <= 5.0:
        fraction = exchanged_air_fraction(rate_per_min, horizon, bonus)
        # IQ2: net change of the room air (buffered) and, separately, the modelled transport through the opening
        physical_removed_ml = (float(current_ah) - relax(float(current_ah), float(source_ah), anchor_ah, rate_per_min, horizon, bonus, moisture_share)) * volume
        uncapped_physical_removed_ml = physical_removed_ml
        outdoor_transport_ml = (float(current_ah) - float(source_ah)) * volume * fraction

        target_cap_ml: float | None = None
        if cap_positive_to_target and target_ah is not None and physical_removed_ml > 0:
            target_cap_ml = max((float(current_ah) - float(target_ah)) * volume, 0.0)
            physical_removed_ml = min(physical_removed_ml, target_cap_ml)

        residual_minutes = _effective_residual_minutes(horizon)
        internal_change_ml = source_rate * residual_minutes
        net_removed_ml = physical_removed_ml - internal_change_ml
        net_uncapped_ml = uncapped_physical_removed_ml - internal_change_ml
        ventilation_effect_ml = physical_removed_ml
        observed_projection_ml = None
        if observed_shift_ah is not None:
            # same relaxation as the stepped path, towards the equilibrium the measured rate implies
            observed_projection_ml = (float(current_ah) - relax(float(current_ah), float(source_ah) + observed_shift_ah / moisture_share, anchor_ah, rate_per_min, horizon, bonus, moisture_share)) * volume
            blended = (float(current_ah) - relax(float(current_ah), float(source_ah) + live_observation_weight * observed_shift_ah / moisture_share, anchor_ah, rate_per_min, horizon, bonus, moisture_share)) * volume
            net_uncapped_ml = blended - internal_change_ml
            if cap_positive_to_target and target_ah is not None and blended > 0:
                # the cap belongs to the positive effect, also when only the live correction makes it positive
                target_cap_ml = max((float(current_ah) - float(target_ah)) * volume, 0.0)
                blended = min(blended, target_cap_ml)
            ventilation_effect_ml = blended

        physical_dt = relax(float(current_temp_c), float(source_temp_c), anchor_temp_c, rate_per_min, horizon, bonus, thermal_share) - float(current_temp_c)
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
        cumulative_min = 0.0
        uncapped_physical_removed_ml = 0.0
        ventilation_effect_uncapped_ml = 0.0
        internal_change_ml = 0.0
        exchange_remaining = 1.0
        observed_projection_ml = 0.0 if observed_shift_ah is not None else None
        weather_confidences: list[int] = []
        simulation_steps = 0
        total_min_duration = max(float(min_duration_min), 0.0)
        total_max_duration = max(float(max_duration_min), total_min_duration)
        elapsed_before_forecast = float(session_elapsed_min) if running else 0.0
        hard_max_in = max(total_max_duration - elapsed_before_forecast, 0.0)

        (
            exchange_remaining, internal_change_ml, observed_projection_ml, optimal_close_in_min,
            optimal_close_reason, simulation_steps, state_ah, state_temp, uncapped_physical_removed_ml,
            ventilation_effect_uncapped_ml, outdoor_transport_ml,
        ) = _simulate_forecast_steps(
            _effective_residual_minutes=_effective_residual_minutes, _future_boundary=_future_boundary,
            bonus=bonus, cumulative_min=cumulative_min, current_temp_c=current_temp_c,
            elapsed_before_forecast=elapsed_before_forecast, exchange_remaining=exchange_remaining,
            exchanged_air_fraction=exchanged_air_fraction, forecast_max_temp_loss=forecast_max_temp_loss,
            forecast_min_efficiency=forecast_min_efficiency, forecast_min_return=forecast_min_return,
            hard_max_in=hard_max_in, horizon=horizon,
            internal_change_ml=internal_change_ml,
            learned_thermal_residual_c_min=learned_thermal_residual_c_min, learned_weight=learned_weight,
            live_adapted=live_adapted, live_observation_weight=live_observation_weight,
            max_cumulative_temp_loss=max_cumulative_temp_loss, min_forecast_end_temp=min_forecast_end_temp,
            observed_projection_ml=observed_projection_ml, optimal_close_in_min=optimal_close_in_min,
            optimal_close_reason=optimal_close_reason, profile=profile, rate_per_min=rate_per_min,
            observed_shift_ah=observed_shift_ah, simulation_steps=simulation_steps,
            source_rate=source_rate, state_ah=state_ah, state_temp=state_temp, step_size=step_size,
            target_ah=target_ah, temperature_path=temperature_path, total_min_duration=total_min_duration,
            uncapped_physical_removed_ml=uncapped_physical_removed_ml,
            ventilation_effect_uncapped_ml=ventilation_effect_uncapped_ml, volume=volume,
            weather_confidences=weather_confidences,
            anchor_ah=anchor_ah, anchor_temp_c=anchor_temp_c, moisture_share=moisture_share, thermal_share=thermal_share,
        )

        target_cap_ml = None
        physical_removed_ml = uncapped_physical_removed_ml
        ventilation_effect_ml = ventilation_effect_uncapped_ml
        if cap_positive_to_target and target_ah is not None and (physical_removed_ml > 0 or ventilation_effect_ml > 0):
            target_cap_ml = max((float(current_ah) - float(target_ah)) * volume, 0.0)
            physical_removed_ml = min(physical_removed_ml, target_cap_ml)
            if ventilation_effect_ml > 0:
                ventilation_effect_ml = min(ventilation_effect_ml, target_cap_ml)

        net_removed_ml = ventilation_effect_ml - internal_change_ml
        net_uncapped_ml = ventilation_effect_uncapped_ml - internal_change_ml
        fraction = 1.0 - exchange_remaining
        temp_delta = state_temp - float(current_temp_c)
        weather_confidence = min(weather_confidences) if weather_confidences else None
        simulated_final_ah = state_ah
    return (
        fraction, internal_change_ml, net_removed_ml, observed_projection_ml, optimal_close_in_min,
        optimal_close_reason, physical_removed_ml, simulated_final_ah, simulation_steps, target_cap_ml,
        temp_delta, uncapped_physical_removed_ml, ventilation_effect_ml, weather_confidence,
        net_uncapped_ml, outdoor_transport_ml,
    )


def _forecast_result(
    *,
    fraction: Any, horizon: Any, internal_change_ml: Any, live_adapted: Any, live_observation_weight: Any,
    max_cumulative_temp_loss: Any, measurement_frame_quality: Any, min_forecast_end_temp: Any,
    model_maturity_pct: Any, net_removed_ml: Any, observed_projection_ml: Any, optimal_close_in_min: Any,
    optimal_close_reason: Any, physical_removed_ml: Any, running: Any, samples: Any, session_elapsed_min: Any,
    simulated_final_ah: Any, simulation_steps: Any, source_rate: Any, target_cap_ml: Any, temp_delta: Any,
    temperature_path: Any, uncapped_physical_removed_ml: Any, ventilation_effect_ml: Any,
    weather_confidence: Any, net_room_change_ml: Any = None, to_target_ml: Any = None, outdoor_transport_ml: Any = None,
) -> Any:
    """Confidence (model maturity and measurement frame caps) and the forecast payload."""
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
        # IQ2: separate, clearly named quantities (see horizon_forecast)
        "net_room_change_ml": round(net_room_change_ml) if net_room_change_ml is not None else round(net_removed_ml),
        "outdoor_transport_ml": round(outdoor_transport_ml) if outdoor_transport_ml is not None else round(uncapped_physical_removed_ml),
        "to_target_ml": round(to_target_ml) if to_target_ml is not None else None,
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


def _simulate_forecast_steps(
    *,
    _effective_residual_minutes: Any, _future_boundary: Any, bonus: Any, cumulative_min: Any,
    current_temp_c: Any, elapsed_before_forecast: Any, exchange_remaining: Any, exchanged_air_fraction: Any,
    forecast_max_temp_loss: Any, forecast_min_efficiency: Any, forecast_min_return: Any, hard_max_in: Any,
    horizon: Any, internal_change_ml: Any, learned_thermal_residual_c_min: Any,
    learned_weight: Any, live_adapted: Any, live_observation_weight: Any, max_cumulative_temp_loss: Any,
    min_forecast_end_temp: Any, observed_projection_ml: Any, optimal_close_in_min: Any,
    optimal_close_reason: Any, profile: Any, rate_per_min: Any, observed_shift_ah: Any,
    simulation_steps: Any, source_rate: Any, state_ah: Any, state_temp: Any, step_size: Any, target_ah: Any,
    temperature_path: Any, total_min_duration: Any, uncapped_physical_removed_ml: Any,
    ventilation_effect_uncapped_ml: Any, volume: Any, weather_confidences: Any,
    anchor_ah: Any = None, anchor_temp_c: Any = None, moisture_share: Any = 1.0, thermal_share: Any = 1.0,
) -> Any:
    """Advance the moisture/temperature state in 5-minute steps through the future weather boundaries."""
    outdoor_transport_ml = 0.0
    while cumulative_min < horizon - 1e-9:
        step = min(step_size, horizon - cumulative_min)
        step_end = cumulative_min + step
        step_source_ah, step_source_temp, boundary_conf = _future_boundary(step_end)
        if boundary_conf is not None:
            weather_confidences.append(boundary_conf)

        step_fraction = exchanged_air_fraction(rate_per_min, step, bonus)
        exchange_remaining *= (1.0 - step_fraction)
        # IQ2: buffered net change of the room air in this step (equals the plain replacement for share 1)
        model_removed = (state_ah - relax(state_ah, step_source_ah, anchor_ah, rate_per_min, step, bonus, moisture_share)) * volume
        uncapped_physical_removed_ml += model_removed
        outdoor_transport_ml += (state_ah - step_source_ah) * volume * step_fraction

        prev_effective = _effective_residual_minutes(cumulative_min)
        next_effective = _effective_residual_minutes(step_end)
        effective_step_min = max(next_effective - prev_effective, 0.0)
        step_internal = source_rate * effective_step_min
        internal_change_ml += step_internal

        # Live correction: the same relaxation from the predicted state of this step, towards the equilibrium shifted
        # by the measured net drying (it fades with the remaining gradient instead of copying one measured rate).
        step_effect = model_removed
        if observed_shift_ah is not None:
            observed_step = (state_ah - relax(state_ah, step_source_ah + observed_shift_ah / moisture_share, anchor_ah, rate_per_min, step, bonus, moisture_share)) * volume
            step_effect = (state_ah - relax(state_ah, step_source_ah + live_observation_weight * observed_shift_ah / moisture_share, anchor_ah, rate_per_min, step, bonus, moisture_share)) * volume
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
        physical_dt = relax(state_temp, step_source_temp, anchor_temp_c, rate_per_min, step, bonus, thermal_share) - state_temp
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
            decision_ready_by_time = total_elapsed_at_step >= total_min_duration
            # final hotfix F11-C: the stored ``max_duration_min`` is no end point of the forecast any more (it was
            # shown as "optimal close ... max_duration"); the forecast horizon itself stays bounded.
            if decision_ready_by_time and (
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
    return (
        exchange_remaining, internal_change_ml, observed_projection_ml, optimal_close_in_min,
        optimal_close_reason, simulation_steps, state_ah, state_temp, uncapped_physical_removed_ml,
        ventilation_effect_uncapped_ml, outdoor_transport_ml,
    )
