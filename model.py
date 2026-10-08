"""Pure calculation model ported from the V14.2.1 YAML package."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, isfinite
from typing import Any


def absolute_humidity(temp_c: float, rh: float) -> float:
    """Return absolute humidity in g/m³ using the V14.2.1 Magnus formula."""
    svp = 6.112 * exp((17.62 * temp_c) / (243.12 + temp_c))
    return 216.7 * ((rh / 100.0) * svp) / (273.15 + temp_c)


def surface_relative_humidity(
    temp_c: float, rh: float, outside_temp_c: float, surface_factor: float
) -> float:
    """Estimate surface RH using the same simplified wall model as V14.2.1."""
    surface_temp = temp_c - ((temp_c - outside_temp_c) * surface_factor)
    esi = 6.112 * exp((17.62 * temp_c) / (243.12 + temp_c))
    ess = 6.112 * exp((17.62 * surface_temp) / (243.12 + surface_temp))
    return min(100.0, 100.0 * ((rh / 100.0) * esi) / ess)


@dataclass(slots=True)
class RoomInput:
    key: str
    name: str
    temperature: float
    humidity: float
    reference_temperature: float
    reference_humidity: float
    volume_m3: float
    contact_open: bool
    contact_open_seconds: float
    learning_rate: float = 0.03
    learning_samples: int = 0
    co2: float | None = None
    session_active: bool = False
    session_elapsed_min: float = 0.0
    session_start_ah: float | None = None
    session_start_temp: float | None = None
    session_result_base_ml: float = 0.0
    session_result_ml: float = 0.0
    close_notified: bool = False
    airflow_factor: float = 1.0
    pollen_index: float = 0.0
    session_fresh_measurements: int = 0
    future_reference_temperature_15: float | None = None
    future_reference_humidity_15: float | None = None
    moisture_source_active: bool = False
    moisture_source_recovery: bool = False
    moisture_source_label: str = "Feuchtequelle"
    moisture_source_confidence: int = 0
    moisture_source_rate_ml_min: float = 0.0


@dataclass(slots=True)
class RoomResult:
    key: str
    name: str
    data_quality: str
    action: str
    reason: str
    temperature: float | None
    humidity: float | None
    absolute_humidity: float | None
    reference_humidity: float | None
    delta_g_m3: float
    potential_ml: int
    next_5_min_ml: int
    temp_next_5_min_c: float
    efficiency_ml_per_01c: float
    surface_rh: int
    mould_level: str
    learning_status: str
    learning_samples: int
    active: bool
    open: bool
    close_recommended: bool
    result_ml: int
    water_in_air_ml: int
    cooling_candidate: bool = False
    moisture_effect_next_5_min_ml: int = 0
    ventilation_candidate: bool = False
    fresh_measurements: int = 0
    close_decision_ready: bool = False
    close_decision_model_fallback: bool = False
    future_moisture_risk_15: bool = False
    moisture_source_active: bool = False
    moisture_source_recovery: bool = False
    moisture_source_label: str = "Feuchtequelle"
    moisture_source_confidence: int = 0
    moisture_source_rate_ml_min: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mould_level(surface_rh: float, warn: float, critical: float) -> str:
    if surface_rh >= critical:
        return "Very high"
    if surface_rh >= warn:
        return "High"
    if surface_rh >= 70:
        return "Elevated"
    if surface_rh >= 60:
        return "Slightly elevated"
    return "Low"


def _learning_status(samples: int) -> str:
    if samples >= 10:
        return "Very stable"
    if samples >= 5:
        return "Stable"
    if samples >= 3:
        return "Usable"
    if samples > 0:
        return "Learning"
    return "Base estimate"


def evaluate_room(room: RoomInput, options: dict[str, Any], cross_ventilation: bool) -> RoomResult:
    """Evaluate one room using the V14.2.1 room decision logic."""
    numeric_inputs = (
        room.temperature, room.humidity, room.reference_temperature,
        room.reference_humidity, room.volume_m3,
    )
    valid = (
        all(isfinite(value) for value in numeric_inputs)
        and -10 < room.temperature < 50
        and 5 <= room.humidity <= 100
        and -30 < room.reference_temperature < 60
        and 0 <= room.reference_humidity <= 100
        and room.volume_m3 >= 2
    )
    if not valid:
        return RoomResult(
            room.key, room.name, "error", "Check sensor", "Missing or implausible measurements",
            None, None, None, None, 0.0, 0, 0, 0.0, 0.0, 0, "Unknown",
            _learning_status(room.learning_samples), room.learning_samples, room.session_active,
            room.contact_open, False, round(room.session_result_ml), 0,
        )

    ah = absolute_humidity(room.temperature, room.humidity)
    ref_ah = absolute_humidity(room.reference_temperature, room.reference_humidity)
    delta = ah - ref_ah
    potential = delta * room.volume_m3
    surf_rh = surface_relative_humidity(
        room.temperature, room.humidity, room.reference_temperature, float(options["surface_factor"])
    )
    warn = float(options["mould_warn_surface_rh"])
    critical = float(options["mould_critical_surface_rh"])

    profile = str(options.get("operating_profile", "comfort"))
    # Profiles intentionally adjust priorities, not the underlying physics.
    # Dehumidify starts a little earlier and tolerates more heat loss; summer
    # cooling requires a useful temperature gradient while retaining a moisture veto.
    start_rh = float(options["start_rh"])
    min_delta = float(options["min_delta"])
    min_delta_high = float(options["min_delta_high_rh"])
    if profile == "dehumidify":
        start_rh = max(40.0, start_rh - 2.0)
        min_delta = max(0.1, min_delta * 0.85)
        min_delta_high = max(0.1, min_delta_high * 0.85)
    candidate = (
        (room.humidity >= start_rh and delta >= min_delta)
        or (room.humidity >= float(options["high_rh"]) and delta >= min_delta_high)
    )
    # An active internal moisture source changes the decision context. Even a
    # modest positive drying gradient is useful because ventilation is then
    # offsetting newly generated water rather than only reducing stored room air.
    source_drying_useful = bool(room.moisture_source_active) and delta >= max(float(options.get("close_delta", 0.4)), 0.4)
    candidate = candidate or source_drying_useful
    running = room.session_active and room.contact_open
    bonus = 1.25 if cross_ventilation else 1.0
    exchange_fraction_5 = min(room.learning_rate * 5 * bonus * min(max(room.airflow_factor, 0.5), 1.5), 0.85)
    # Positive = moisture removed, negative = moisture added.
    moisture_effect_next5 = delta * room.volume_m3 * exchange_fraction_5
    next5 = max(moisture_effect_next5, 0.0)

    cooling_delta = room.temperature - room.reference_temperature
    cooling_candidate = (
        profile in {"summer_cooling", "comfort"}
        and room.temperature >= float(options.get("cooling_start_temp_c", 24.0))
        and cooling_delta >= float(options.get("cooling_min_outdoor_delta_c", 2.0))
        and room.humidity <= float(options.get("cooling_max_indoor_rh", 70.0))
        and moisture_effect_next5 >= -float(options.get("cooling_max_moisture_gain_5min_ml", 60.0))
    )

    start_temp = room.session_start_temp if room.session_start_temp is not None else room.temperature
    mins = room.session_elapsed_min
    if running:
        if mins >= 2:
            dt = ((room.temperature - start_temp) / mins) * 5
        else:
            dt = (room.reference_temperature - room.temperature) * 0.10
    else:
        # Before a window is opened, estimate the 5-minute temperature effect
        # from the same learned exchanged-air fraction used for moisture.
        dt = (room.reference_temperature - room.temperature) * exchange_fraction_5
    physical_limit = room.reference_temperature - room.temperature
    dt = max(dt, physical_limit) if physical_limit < 0 else min(dt, physical_limit)
    efficiency = 999.0 if dt >= -0.05 else next5 / (abs(dt) * 10)

    co2_warn = float(options.get("co2_warn", 1000.0))
    co2_critical = float(options.get("co2_critical", 1400.0))
    co2_high = room.co2 is not None and room.co2 >= co2_warn
    co2_urgent = room.co2 is not None and room.co2 >= co2_critical
    # CO2 above the warning threshold raises attention and can prolong an active
    # airing session. Only the separately configured critical threshold is a
    # health-urgent override. A critical CO2 level must itself create an airing
    # candidate even when outside/reference air is slightly wetter.
    candidate = candidate or co2_urgent
    urgent = surf_rh >= critical or co2_urgent
    pollen_blocked = (
        bool(options.get("pollen_enabled", False))
        and bool(options.get("pollen_strict_veto", True))
        and room.pollen_index > float(options.get("pollen_max", 4.0))
        and not urgent
    )
    min_return = float(options["min_return_next_5_min_ml"])
    max_temp_loss = float(options["max_temp_loss_next_5_min_c"])
    min_efficiency = float(options["min_efficiency_ml_per_01c"])
    if profile == "dehumidify":
        min_return *= 0.60
        max_temp_loss *= 1.50
        min_efficiency *= 0.60
    elif profile == "summer_cooling":
        # Cooling is the desired thermal effect; do not close merely because
        # temperature falls. Moisture safety still applies.
        min_return *= 0.50
    cooling_still_useful = (
        profile == "summer_cooling"
        and room.temperature >= float(options.get("cooling_start_temp_c", 24.0))
        and cooling_delta >= float(options.get("cooling_min_outdoor_delta_c", 2.0))
        and moisture_effect_next5 >= -float(options.get("cooling_max_moisture_gain_5min_ml", 60.0))
    )
    low_return = (
        next5 < min_return
        and surf_rh < warn
        and not co2_high
        and not cooling_still_useful
    )
    thermal_bad = (
        profile != "summer_cooling"
        and dt <= -max_temp_loss
        and efficiency < min_efficiency
        and not urgent
    )
    # Hotfix 0.17.0.4: retain the two-fresh-measurement guard from 0.17.0.3,
    # but do not let a silent/slow humidity sensor block a decision forever.
    # After 15 minutes, FreshAirIQ may fall back to the physical/learned model.
    # If a 15-minute outdoor forecast is available, a near-term loss of the
    # drying gradient is an additional conservative reason to close.
    fresh_measurements = max(int(room.session_fresh_measurements), 0)
    sensor_confirmed = fresh_measurements >= 2
    model_fallback = running and not sensor_confirmed and mins >= 15.0

    future_moisture_risk_15 = False
    if model_fallback and room.future_reference_temperature_15 is not None and room.future_reference_humidity_15 is not None:
        try:
            future_ref_ah = absolute_humidity(
                float(room.future_reference_temperature_15),
                float(room.future_reference_humidity_15),
            )
            future_delta_15 = ah - future_ref_ah
            future_moisture_risk_15 = future_delta_15 <= float(options["close_delta"])
        except (TypeError, ValueError):
            future_moisture_risk_15 = False

    close_decision_ready = sensor_confirmed or model_fallback
    source_postrun = (
        bool(room.moisture_source_recovery)
        and running
        and delta >= max(float(options.get("close_delta", 0.4)), 0.4)
        and mins < max(float(options.get("moisture_source_postrun_min", 8.0)), float(options.get("min_duration_min", 3.0)))
    )
    source_keep_open = running and (source_drying_useful or source_postrun) and not pollen_blocked
    # Hotfix 0.19.1.1: reaching target RH or the close-delta is no longer
    # sufficient on its own to stop an active airing session.  In a dry-air
    # situation a room can still remove a meaningful amount of water even after
    # crossing the nominal target.  Moisture-driven closing therefore requires
    # the *marginal* 5-minute return to have fallen below the configured
    # threshold.  The configured hard maximum duration and a genuinely poor
    # thermal efficiency remain independent close reasons.
    moisture_close = low_return and not cooling_still_useful
    should_close = running and close_decision_ready and not source_keep_open and not room.close_notified and (
        mins >= float(options["max_duration_min"])
        or (
            mins >= float(options["min_duration_min"])
            and (
                moisture_close
                or thermal_bad
            )
        )
    )
    close_signal = running and close_decision_ready and not source_keep_open and (room.close_notified or should_close)

    if close_signal:
        if model_fallback and future_moisture_risk_15:
            action, reason = "Close", "Sensor updates are missing; forecast indicates the drying advantage will soon be lost"
        elif model_fallback:
            action, reason = "Close", "Sensor updates are missing; model indicates additional ventilation benefit is too low"
        else:
            action, reason = "Close", "Target reached or additional ventilation benefit is too low"
    elif running:
        if source_keep_open:
            action, reason = "Continue ventilating", f"Active internal moisture source ({room.moisture_source_label}); ventilation is offsetting ongoing moisture generation"
        elif profile == "summer_cooling" and cooling_still_useful and not candidate:
            action, reason = "Continue ventilating", f"Cooling remains useful; outdoor air is {cooling_delta:.1f} °C cooler"
        else:
            action, reason = "Continue ventilating", f"Short-term 5-minute close check expects {round(next5)} ml moisture removal"
    elif pollen_blocked and (candidate or cooling_candidate):
        action, reason = "Do not ventilate", f"Pollen load {room.pollen_index:.1f} exceeds configured limit"
    elif candidate:
        action, reason = "Ventilate", f"About {max(round(potential), 0)} ml moisture can be removed"
    elif cooling_candidate:
        action, reason = "Ventilate for cooling", f"Outdoor air is {cooling_delta:.1f} °C cooler"
    elif delta < -0.4:
        action, reason = "Do not ventilate", "Reference air would add moisture"
    elif potential > 0:
        action, reason = "Wait", "Potential exists, but ventilation threshold is not reached"
    else:
        action, reason = "Okay", "No meaningful ventilation demand"

    result_ml = room.session_result_ml
    if running and room.session_start_ah is not None:
        result_ml = room.session_result_base_ml + ((room.session_start_ah - ah) * room.volume_m3)

    return RoomResult(
        key=room.key,
        name=room.name,
        data_quality="ok",
        action=action,
        reason=reason,
        temperature=round(room.temperature, 1),
        humidity=round(room.humidity),
        absolute_humidity=round(ah, 2),
        reference_humidity=round(ref_ah, 2),
        delta_g_m3=round(delta, 2),
        potential_ml=max(round(potential), 0),
        next_5_min_ml=round(next5),
        temp_next_5_min_c=round(dt, 1),
        efficiency_ml_per_01c=round(efficiency, 1),
        surface_rh=round(surf_rh),
        mould_level=_mould_level(surf_rh, warn, critical),
        learning_status=_learning_status(room.learning_samples),
        learning_samples=room.learning_samples,
        active=room.session_active,
        open=room.contact_open,
        close_recommended=bool(close_signal),
        result_ml=round(result_ml),
        water_in_air_ml=round(ah * room.volume_m3),
        cooling_candidate=cooling_candidate,
        moisture_effect_next_5_min_ml=round(moisture_effect_next5),
        ventilation_candidate=candidate,
        fresh_measurements=fresh_measurements,
        close_decision_ready=close_decision_ready,
        close_decision_model_fallback=model_fallback,
        future_moisture_risk_15=future_moisture_risk_15,
        moisture_source_active=bool(room.moisture_source_active),
        moisture_source_recovery=bool(room.moisture_source_recovery),
        moisture_source_label=str(room.moisture_source_label),
        moisture_source_confidence=int(room.moisture_source_confidence),
        moisture_source_rate_ml_min=round(max(float(room.moisture_source_rate_ml_min), 0.0), 2),
    )


def update_learning(
    *, old_rate: float, old_samples: int, elapsed_min: float,
    start_ah: float, end_ah: float, source_ah: float, learning_enabled: bool,
    max_duration_min: float = 120.0,
) -> tuple[float, int, str, bool]:
    """Port the V14.2.1 learning validation and smoothing rules."""
    start_delta = start_ah - source_ah
    reduction = start_ah - end_ah
    raw = reduction / start_delta / elapsed_min if elapsed_min > 0 and start_delta != 0 else 0.0

    if not learning_enabled:
        return old_rate, old_samples, f"Paused: learning disabled · {elapsed_min:.1f} min", False
    if elapsed_min < 2:
        return old_rate, old_samples, f"Rejected: duration {elapsed_min:.1f} min < 2 min", False
    if elapsed_min > max_duration_min:
        return old_rate, old_samples, f"Rejected: duration {elapsed_min:.1f} min > {max_duration_min:.0f} min learning limit", False
    if start_delta <= 0.5:
        return old_rate, old_samples, f"Rejected: start delta {start_delta:.2f} g/m³ ≤ 0.50", False
    if reduction <= 0.05:
        return old_rate, old_samples, f"Rejected: humidity reduction {reduction:.2f} g/m³ ≤ 0.05", False
    if raw < 0.002:
        return old_rate, old_samples, f"Rejected: learning rate {raw:.4f}/min < 0.002", False
    if raw > 0.25:
        return old_rate, old_samples, f"Rejected: learning rate {raw:.3f}/min > 0.25", False

    observed = min(max(raw, max(old_rate * 0.75, 0.002)), min(old_rate * 1.25, 0.25))
    alpha = 0.20 if old_samples < 5 else (0.12 if old_samples < 20 else 0.08)
    candidate = (old_rate * (1 - alpha)) + (observed * alpha)
    new_rate = round(min(max(candidate, max(old_rate * 0.85, 0.002)), min(old_rate * 1.15, 0.25)), 3)
    new_samples = min(old_samples + 1, 1000)
    diagnosis = (
        f"Learned: sample {new_samples} · {elapsed_min:.1f} min · start Δ {start_delta:.2f} g/m³ · "
        f"reduction {reduction:.2f} g/m³ · rate {old_rate:.3f}→{new_rate:.3f}"
    )
    return new_rate, new_samples, diagnosis, True
