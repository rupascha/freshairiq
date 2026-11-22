"""Pure calculation model ported from the V14.2.1 YAML package."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, isfinite
from typing import Any

from .iq2 import SATURATION_LIMIT
from .outdoor_air import outdoor_pm25_blocked as _outdoor_pm25_blocked


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
    # B3 (0.26.7.1): why the stored close of this session was given (the room model's close kind); None = unknown
    # (older stored data) – then no reached goal is claimed for it
    close_notified_kind: str | None = None
    # IQ2 (0.26.7.1): the goals of this airing were reliably reached at some point (kept beside another close cause)
    session_goals_reached: bool = False
    # IQ2: part of the outdoor temperature difference the room air follows (thermal mass keeps the rest); 1 = plain mixing
    thermal_air_share: float = 1.0
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
    # 0.26.5.5 (audit F02): minutes since the moisture source ended; None = unknown
    # (the follow-up then counts from the start of the airing, as before).
    moisture_source_ended_min: float | None = None
    # 0.26.4.7 (GitHub #15): the room recommended airing in the previous cycle.
    ventilation_latched: bool = False
    # 0.26.4.7 (user feedback): outdoor fine dust (PM2.5, µg/m³); None = no sensor.
    outdoor_pm25: float | None = None
    # 0.26.4.10: planned airing duration known when the window was opened.
    session_target_min: float | None = None
    # 0.26.4.10: only an exhaust fan runs, no window/door is open.
    mechanical_only: bool = False
    # 0.26.5.1: False when the room's temperature goal is switched off – no
    # airing for cooling is started or prolonged.
    cooling_allowed: bool = True
    # 0.26.5.3 (community: "Fenster schließen" although temperature has
    # priority 1): the room's comfort target when it has a temperature goal.
    comfort_target_c: float | None = None
    # 0.26.5.4 (review A04): temperature the simplified wall model compares with – the
    # room's default reference (outdoor air), never the supply air of an exhaust fan
    # or of a single window. ``None``: the reference air (previous behaviour).
    surface_reference_temperature: float | None = None
    # v0.26.6.1 (#21): surface RH from the room's Home Assistant Mold Indicator helper (checked: finite, 0–100 %);
    # None = the internal estimate below (unchanged formula, global surface_factor and limits)
    surface_rh_helper: float | None = None
    co2_lead_latched: bool = False  # 0.26.5.4 (review A07): CO2 airing started, ends 50 ppm below the warning threshold
    session_co2_only: bool = False  # the running airing was asked for CO2 alone (a short, thorough airing)
    co2_sensor_missing: bool = False  # audit P1-04: CO2 goal on, sensor configured, but no readable value
    # 0.26.5.3 (community: fan stuck at 59 % for half an hour): the humidity did
    # not fall noticeably during the last 15 minutes of this airing.
    humidity_plateau: bool = False
    # 0.26.5.5 (community diagnosis): the measurement frame is too old or out of step to trust
    # ("stale") – a stored close is then not lifted for comfort cooling.
    measurements_stale: bool = False


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
    co2_airing: bool = False  # 0.26.5.4 (review A07): the airing is asked for CO2 alone
    co2_sensor_missing: bool = False  # the CO2 sensor has no value: a CO2 airing runs on its plan
    fresh_measurements: int = 0
    close_decision_ready: bool = False
    close_decision_model_fallback: bool = False
    future_moisture_risk_15: bool = False
    moisture_source_active: bool = False
    moisture_source_recovery: bool = False
    moisture_source_label: str = "Feuchtequelle"
    moisture_source_confidence: int = 0
    moisture_source_rate_ml_min: float = 0.0
    # 0.26.5.3: the open window still cools the room towards its comfort target
    comfort_cooling_active: bool = False
    # R01/R02 (0.26.7.2): why a running airing closes – "temperature_limit", "goals_reached", "goals_held",
    # "summer_warming", "air_no_longer_helps", "benefit_exhausted", "model_fallback"; None when there is no close.
    # Later layers (room text, moisture-source and house presentation) use it so a protective close is never
    # rewritten without notice.
    close_kind: str | None = None
    # IQ2 (0.26.7.1, C1): the goals of the airing are reliably reached in this evaluation / still inside the humidity
    # hysteresis – independent of which close cause has priority (kept as the session's goal history by the coordinator)
    goals_reached_now: bool = False
    goals_in_band: bool = False
    # nothing but the remaining moisture benefit keeps this running airing open (no source, CO2, cooling, protection,
    # minimum duration); the coordinator may then close it on confirmed IQ2 forecasts (room_close_strategy)
    benefit_close_ready: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# 0.26.4.7 (GitHub #15 "Ventilate/Close flapping in small rooms"):
# * Hysteresis: once a room recommends airing, the start condition is released
#   only after humidity/drying gradient fall clearly below the start values.
# * The close criterion "additional benefit in the next 5 min" is an absolute
#   amount of water (default 25 ml). A 9.4 m³ bathroom can physically never
#   reach it, so every session was closed at the minimum duration and the room
#   re-armed shortly after. The threshold now scales with room volume below a
#   typical 30 m³ room (never below a quarter of the configured value).
VENTILATION_HYSTERESIS_RH = 2.0
VENTILATION_HYSTERESIS_DELTA_G_M3 = 0.4
MIN_RETURN_REFERENCE_VOLUME_M3 = 30.0
MIN_RETURN_MIN_VOLUME_FACTOR = 0.25
# 0.26.5.1 (Node-RED feedback: "Weiterlüften"/"Bitte Fenster schließen" every
# minute): once a close was recommended in a running session it is kept until
# the next five minutes would clearly beat the close threshold again.
CLOSE_RELEASE_FACTOR = 1.25
TEMPERATURE_LIMIT_CLOSE_REASON = "Configured temperature limit for airing reached; close because of the temperature, not because enough moisture was removed"
AIR_NO_LONGER_HELPS_CLOSE_REASON = "Reference air no longer removes moisture"
# K02 (0.26.7.1): the room chose to close once its goals are reliably reached (room_close_strategy.py)
GOALS_REACHED_CLOSE_REASON = "Room goals reached; the room is set to close once its goals are reached"
# R02 (0.26.7.2): the goal close of this airing is kept inside the existing humidity hysteresis
GOAL_CLOSE_KINDS = frozenset({"goals_reached", "goals_held"})
GOALS_HELD_CLOSE_REASON = "Room goals were reached; the close is kept while humidity stays inside the hysteresis band"
# the humidity target is still open, but confirmed IQ2 forecasts show that further airing hardly removes moisture
BENEFIT_CLOSE_KIND = "benefit_exhausted"
BENEFIT_EXHAUSTED_CLOSE_REASON = "Further airing hardly removes moisture any more; the humidity target is not reached"
ROOM_TOO_DRY_CLOSE_REASON = "Room air is already dry; further airing would dry it out too much"
# 0.26.7.0 (F11): a close stored because the air no longer helped is lifted once it is clearly drier again
CLOSE_RELEASE_DELTA_G_M3 = 0.3
# 0.26.5.1 (summer night cooling): in the "summer cooling" profile an airing
# that still cools is not ended by the maximum duration; it is ended once the
# outdoor air is no longer at least this much cooler than a warm room.
SUMMER_WARMING_MARGIN_C = 0.5
# 0.26.5.4: a CO2-led recommendation ends only this far below the warning threshold
CO2_HYSTERESIS_PPM = 50.0
# 0.26.5.3: cooling towards the comfort target counts until 0.5 K above it.
COMFORT_COOLING_MARGIN_C = 0.5
SUMMER_WARMING_CLOSE_REASON = "Outdoor air is no longer cooler than the room; closing keeps the coolness inside"


def min_return_volume_factor(volume_m3: Any) -> float:
    """Share of the configured 5-minute close threshold that applies to a room volume."""
    try:
        volume = float(volume_m3)
    except (TypeError, ValueError):
        return 1.0
    if not isfinite(volume) or volume <= 0:
        return 1.0
    return min(max(volume / MIN_RETURN_REFERENCE_VOLUME_M3, MIN_RETURN_MIN_VOLUME_FACTOR), 1.0)


def scaled_min_return(min_return_ml: Any, volume_m3: Any) -> float:
    """Configured close threshold (ml per 5 min) scaled to the room volume."""
    try:
        base = float(min_return_ml)
    except (TypeError, ValueError):
        base = 25.0
    return max(base, 0.0) * min_return_volume_factor(volume_m3)


def _mould_level(surface_rh: float, warn: float, critical: float, slight: float = 60.0, elevated: float = 70.0) -> str:
    """Mould risk level of the estimated surface humidity (four settable limits, checked from the top)."""
    if surface_rh >= critical:
        return "Very high"
    if surface_rh >= warn:
        return "High"
    if surface_rh >= elevated:
        return "Elevated"
    if surface_rh >= slight:
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


def _comfort_cooling(room: RoomInput, options: dict[str, Any], cooling_delta: float, moisture_effect_next5: float,
                     drying_delta: float = 0.0) -> bool:
    """0.26.5.3: an open window still cools the room towards its comfort target.

    Only for rooms with a temperature goal: above the target, clearly cooler
    reference air, not too humid inside – and, outside the summer profile,
    without bringing in any noteworthy moisture. The house-wide 24 °C summer
    threshold knows nothing about a 19 °C bedroom, so it is not used here.
    0.26.5.4 (community report): reference air at most ``close_delta`` wetter than the
    room counts as equal – the same significance limit the close rule uses.
    """
    return (
        room.cooling_allowed
        and room.comfort_target_c is not None
        and room.temperature >= float(room.comfort_target_c) + COMFORT_COOLING_MARGIN_C
        and cooling_delta >= float(options.get("cooling_min_outdoor_delta_c", 2.0))
        and room.humidity <= float(options.get("cooling_max_indoor_rh", 70.0))
        and (moisture_effect_next5 >= 0.0 or drying_delta >= -float(options.get("close_delta", 0.4)))
    )


def _cooling_start_c(room: RoomInput, options: dict[str, Any], profile: str) -> float:
    """Room temperature from which a new cooling airing is recommended.

    In the comfort profile a room with a temperature goal follows its own
    comfort target: a new cooling airing starts only once the room is above
    that target by the same margin that keeps a running one open
    (``_comfort_cooling``). The house-wide start temperature stays the lower
    bound, so no room is asked to cool earlier than before. Without a valid
    target, and in the summer profile, the house-wide value applies unchanged.
    """
    start = float(options.get("cooling_start_temp_c", 24.0))
    if profile == "comfort" and room.comfort_target_c is not None:
        return max(start, float(room.comfort_target_c) + COMFORT_COOLING_MARGIN_C)
    return start


def _close_released(large_return: bool, proven_cooling: bool, *, still_closing: bool, within_duration: bool) -> bool:
    """Whether a stored close ("close_notified") is lifted again.

    Only when its reason is gone (0.26.5.5, community diagnosis: 85 flips in 15 minutes). A
    measured plateau, a finished CO2 airing (it never closed for low drying), poor thermal
    efficiency or summer warming still close – a large forecast alone would otherwise lift the
    close and the next cycle would close again. Comfort cooling lifts it when proven: temperature
    goal on, clearly cooler air without noteworthy moisture (``_comfort_cooling``), confirmed and
    trustworthy readings. 0.26.7.0 (F11): no maximum duration any more (``within_duration`` is always True); the
    close is lifted once the reference air is clearly drier again (``CLOSE_RELEASE_DELTA_G_M3`` hysteresis).
    """
    return (large_return or proven_cooling) and not still_closing and within_duration


# 0.26.7.0 (F11): the former plateau close (``_plateau_close``) was removed – a humidity plateau with drier air is an
# internal load in balance with the airing, not a reason to close.


def _source_postrun(room: RoomInput, options: dict[str, Any], *, running: bool, delta: float, mins: float) -> bool:
    """Keep airing after a moisture source while the reference air is still drier.

    0.26.5.5 (audit F02): the follow-up counts from the end of the source
    (``moisture_source_ended_min``), not from the start of the airing; unknown end = airing time.
    """
    since_end = mins if room.moisture_source_ended_min is None else max(float(room.moisture_source_ended_min), 0.0)
    return (
        bool(room.moisture_source_recovery)
        and running
        and delta >= max(float(options.get("close_delta", 0.4)), 0.4)
        and since_end < max(float(options.get("moisture_source_postrun_min", 8.0)), float(options.get("min_duration_min", 3.0)))
    )

def temperature_limit_reached(room: RoomInput, options: dict[str, Any]) -> bool:
    """0.26.7.0 (F11, case D): the user's own temperature limit for airing is reached.

    Only an explicitly set limit (``airing_min_room_temp_c`` > 0) counts – there is no hidden default. It applies
    while the airing cools the room (reference air colder); then FreshAirIQ may close although drier air could still
    remove moisture, and says that it closes because of the temperature, not because enough moisture left.
    """
    try:
        limit = float(options.get("airing_min_room_temp_c") or 0.0)
    except (TypeError, ValueError):
        return False
    return limit > 0.0 and room.reference_temperature < room.temperature and room.temperature <= limit


def _goals_reached_close(room: RoomInput, options: dict[str, Any], *, co2_held: bool, cooling_still_useful: bool,
                         urgent: bool, hold: bool) -> bool:
    """K02: the room's goals are reached (``hold``: still within the existing humidity hysteresis, for the latch).

    Humidity at or below ``target_rh`` (the raw reading – rounding never fakes a reached goal), no CO2 hold, no useful
    cooling left, no urgent protection. Only for rooms that chose ``goals_reached``; never on missing readings.
    """
    if not options.get("room_close_on_goals") or urgent or co2_held or cooling_still_useful or room.co2_sensor_missing:
        return False
    target = float(options.get("target_rh", 55.0))
    return room.humidity <= target + (VENTILATION_HYSTERESIS_RH if hold else 0.0)


def _running_close(
    room: RoomInput, options: dict[str, Any], *, delta: float, mins: float, profile: str, candidate: bool, urgent: bool,
    co2_held: bool, source_drying_useful: bool, outdoor_blocked: bool, low_return: bool, cooling_still_useful: bool,
    comfort_cooling: bool, thermal_bad: bool, moisture_effect_next5: float, next5: float, min_return: float,
    sensor_confirmed: bool, close_decision_ready: bool,
) -> tuple[bool, bool, bool, str | None, tuple[bool, bool]]:
    """(source keeps the window open, summer warming, close signal, goal close kind, goal facts) of a running airing.

    Goal facts (C1): (goals reliably reached now, goals still inside the hysteresis band) – true facts of this
    evaluation, also when another close cause (temperature limit) has priority.

    The goal close kind is "reached" (goals reliably reached now), "held" (a stored goal close kept inside the
    existing humidity hysteresis, R02) or None.

    0.26.7.0 (F11, owner decision): an airing is not ended because of a time, a reached humidity target, a small
    predicted return, a forecast plateau or a hidden thermal rule while drier reference air still takes moisture
    out (case A/B). It closes when that air no longer helps – moisture would come in or it is at most
    ``close_delta`` drier (case C) – at the user's own temperature limit (case D), or, in the summer cooling profile,
    when the outside air warms the room. ``low_return``, ``thermal_bad``, ``next5`` and ``min_return`` stay inputs of
    the forecast and the live coach's wording; they no longer close an airing.
    """
    running = True
    source_postrun = _source_postrun(room, options, running=running, delta=delta, mins=mins)
    source_keep_open = running and (source_drying_useful or source_postrun) and not outdoor_blocked
    close_delta = float(options.get("close_delta", 0.4))
    moisture_ingress, drying_exhausted = moisture_effect_next5 <= 0.0, delta <= close_delta  # 0.26.5.4 (review A01)
    # case C: the physical situation, never a clock. Final hotfix F11-B: the lower humidity setting
    # (``humidify_below_rh``) is no reason to close on its own – it keeps its other uses.
    air_no_longer_helps = moisture_ingress or drying_exhausted
    temperature_limit = temperature_limit_reached(room, options) and not urgent
    summer_warming = (
        profile == "summer_cooling"
        and running
        and room.cooling_allowed
        and not room.mechanical_only
        and not urgent
        and room.temperature >= float(options.get("cooling_start_temp_c", 24.0)) - 1.0
        and room.reference_temperature >= room.temperature - SUMMER_WARMING_MARGIN_C
        # final hotfix F11-A: warmer outdoor air closes a summer airing only when it no longer takes moisture out –
        # the cooling start temperature is no explicit close limit (that is ``airing_min_room_temp_c`` alone)
        and air_no_longer_helps
    )
    ready = running and close_decision_ready
    # K02: an explicitly chosen goal close needs fresh, confirmed readings and the room's own minimum duration; a
    # running or following-up moisture source keeps the window open (``source_keep_open`` below)
    goal_close = (_goals_reached_close(room, options, co2_held=co2_held, cooling_still_useful=cooling_still_useful, urgent=urgent, hold=False)
                  and sensor_confirmed and not room.measurements_stale and mins >= float(options["min_duration_min"]))
    if room.mechanical_only:
        # audit N04: CO2 keeps a fan running; a fan may run for hours – only air that no longer helps stops it
        should_close = ready and not source_keep_open and (not room.close_notified or co2_held) and (air_no_longer_helps or goal_close) and not co2_held
    else:
        should_close = ready and not source_keep_open and (not room.close_notified or co2_held) and (
            summer_warming
            or (
                (mins >= float(options["min_duration_min"]) or (delta < 0 and moisture_ingress))  # audit F01: ingress is protection
                and air_no_longer_helps
                and not cooling_still_useful
                and not co2_held
            )
            or goal_close
        )
    # a stored close is lifted once the air clearly helps again (hysteresis against flapping) or proven cooling runs
    # – proven by confirmed, fresh readings only (stale or unconfirmed values never lift a close)
    drying_again = (delta >= close_delta + CLOSE_RELEASE_DELTA_G_M3 and moisture_effect_next5 > 0.0
                    and sensor_confirmed and not room.measurements_stale)
    # K02: a close stored because the goals were reached is not lifted only because the air is still drier – only when a
    # goal opens again (humidity above the existing hysteresis, CO2 hold, useful cooling)
    # B3 (0.26.7.1): only a close that was stored because the goals were really reached in this session holds inside
    # the humidity hysteresis – a stored temperature/physical close never turns into "goals reached"
    # C1 (IQ2): … or the goals were really reached earlier in this airing while another cause had priority
    goals_latched = room.close_notified_kind in GOAL_CLOSE_KINDS or room.session_goals_reached
    goal_band = _goals_reached_close(room, options, co2_held=co2_held, cooling_still_useful=cooling_still_useful, urgent=urgent, hold=True)
    goal_hold = goals_latched and goal_band
    # a benefit close is lifted by the coordinator on confirmed IQ2 forecasts, not by the drier air alone
    benefit_latched = room.close_notified_kind == BENEFIT_CLOSE_KIND
    close_released = _close_released(drying_again and not goal_hold and not benefit_latched, comfort_cooling and sensor_confirmed and not room.measurements_stale,
                                     still_closing=air_no_longer_helps or summer_warming or goal_close, within_duration=True)
    # audit S01: CO2 needing the air again lifts an earlier close – the close is decided anew (protection limits still apply)
    close_latched = room.close_notified and not close_released and not co2_held
    close_signal = ready and ((not source_keep_open and (close_latched or should_close)) or temperature_limit)
    goal_kind = None if source_keep_open else "reached" if goal_close else "held" if close_latched and goal_hold else None
    return source_keep_open, summer_warming, close_signal, goal_kind, (bool(goal_close and not source_keep_open), bool(goal_band))


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
    wall_reference = room.surface_reference_temperature if room.surface_reference_temperature is not None else room.reference_temperature
    surf_rh = room.surface_rh_helper if room.surface_rh_helper is not None else surface_relative_humidity(room.temperature, room.humidity, wall_reference, float(options["surface_factor"]))
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
    high_rh = float(options["high_rh"])
    if room.ventilation_latched and not room.session_active:
        start_rh -= VENTILATION_HYSTERESIS_RH
        high_rh -= VENTILATION_HYSTERESIS_RH
        min_delta = max(0.1, min_delta - VENTILATION_HYSTERESIS_DELTA_G_M3)
        min_delta_high = max(0.1, min_delta_high - VENTILATION_HYSTERESIS_DELTA_G_M3)
    candidate = (
        (room.humidity >= start_rh and delta >= min_delta)
        or (room.humidity >= high_rh and delta >= min_delta_high)
    )
    # An active internal moisture source changes the decision context. Even a
    # modest positive drying gradient is useful because ventilation is then
    # offsetting newly generated water rather than only reducing stored room air.
    source_drying_useful = bool(room.moisture_source_active) and delta >= max(float(options.get("close_delta", 0.4)), 0.4)
    candidate = candidate or source_drying_useful
    running = room.session_active and room.contact_open
    bonus = 1.25 if cross_ventilation else 1.0
    # IQ2: the 5-minute decision value uses the same exponential replacement as the forecast and the learning
    airflow_bonus_5 = bonus * min(max(room.airflow_factor, 0.5), 1.5)
    # iq2.net_fraction / iq2.relax for 5 minutes, written out: this runs for every room in every cycle (performance
    # gate); tests/test_iq2_model_02671 pins that both give the same values
    rate_5 = room.learning_rate
    effective_5 = (0.0 if rate_5 < 0.0 else 0.95 if rate_5 > 0.95 else rate_5) * airflow_bonus_5
    effective_5 = effective_5 if effective_5 < 0.95 else 0.95
    exchange_fraction_5 = min(1.0 - (1.0 - effective_5) ** 5.0, 0.85)
    # Positive = moisture removed, negative = moisture added.
    moisture_effect_next5 = delta * room.volume_m3 * exchange_fraction_5
    next5 = max(moisture_effect_next5, 0.0)

    cooling_delta = room.temperature - room.reference_temperature
    cooling_candidate = (
        room.cooling_allowed
        and profile in {"summer_cooling", "comfort"}
        and room.temperature >= _cooling_start_c(room, options, profile)
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
        share = room.thermal_air_share
        share = 1e-3 if share < 1e-3 else 1.0 if share > 1.0 else share
        kept = (1.0 - effective_5) ** (5.0 / share)
        dt = share * (room.reference_temperature - room.temperature) * (1.0 - (0.05 if share >= 1.0 and kept < 0.05 else kept))
    physical_limit = room.reference_temperature - room.temperature
    dt = max(dt, physical_limit) if physical_limit < 0 else min(dt, physical_limit)
    efficiency = 999.0 if dt >= -0.05 else next5 / (abs(dt) * 10)

    # Critical CO2 is a health override (even with slightly wetter air); from the warning threshold CO2 is a goal of
    # its own (0.26.5.4, review A07) as long as the airing brings hardly any moisture in – see ``_co2_state``.
    co2_held, co2_urgent, co2_airing = _co2_state(room, options, candidate, delta)
    candidate = candidate or co2_urgent or co2_airing
    urgent = surf_rh >= critical or co2_urgent
    pollen_blocked = (
        bool(options.get("pollen_enabled", False))
        and bool(options.get("pollen_strict_veto", True))
        and room.pollen_index > float(options.get("pollen_max", 4.0))
        and not urgent
    )
    pm25_blocked = room.outdoor_pm25 is not None and _outdoor_pm25_blocked(options, room.outdoor_pm25) and not urgent  # P01: no reading, no check
    outdoor_blocked = pollen_blocked or pm25_blocked
    min_return = scaled_min_return(options["min_return_next_5_min_ml"], room.volume_m3)
    max_temp_loss, min_efficiency = float(options["max_temp_loss_next_5_min_c"]), float(options["min_efficiency_ml_per_01c"])
    if profile == "dehumidify":
        min_return *= 0.60
        max_temp_loss *= 1.50
        min_efficiency *= 0.60
    elif profile == "summer_cooling":
        # Cooling is the desired thermal effect; do not close merely because
        # temperature falls. Moisture safety still applies.
        min_return *= 0.50
    comfort_cooling = running and _comfort_cooling(room, options, cooling_delta, moisture_effect_next5, delta)
    cooling_still_useful = comfort_cooling or (
        room.cooling_allowed and profile == "summer_cooling"
        and room.temperature >= float(options.get("cooling_start_temp_c", 24.0))
        and cooling_delta >= float(options.get("cooling_min_outdoor_delta_c", 2.0))
        and moisture_effect_next5 >= -float(options.get("cooling_max_moisture_gain_5min_ml", 60.0))
    )
    low_return = (
        next5 < min_return
        and surf_rh < warn
        and not co2_held
        and not cooling_still_useful
    )
    thermal_bad = (
        profile != "summer_cooling" and not comfort_cooling
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
    # Close decision of a running airing (P01, 0.26.5.5: only evaluated while the airing runs; for any
    # other room all three are False by definition, as before).
    source_keep_open, summer_warming, close_signal, goal_kind, goal_facts = _running_close(
        room, options, delta=delta, mins=mins, profile=profile, candidate=candidate, urgent=urgent, co2_held=co2_held,
        source_drying_useful=source_drying_useful, outdoor_blocked=outdoor_blocked, low_return=low_return,
        cooling_still_useful=cooling_still_useful, comfort_cooling=comfort_cooling, thermal_bad=thermal_bad,
        moisture_effect_next5=moisture_effect_next5, next5=next5, min_return=min_return, sensor_confirmed=sensor_confirmed,
        close_decision_ready=close_decision_ready,
    ) if running else (False, False, False, None, (False, False))

    benefit_close_ready = bool(
        running and options.get("room_close_on_goals") and not room.mechanical_only and not source_keep_open
        and not room.moisture_source_active and not room.moisture_source_recovery and not co2_held and not urgent
        and not cooling_still_useful and not comfort_cooling and mins >= float(options["min_duration_min"])
        and delta > float(options.get("close_delta", 0.4)) and moisture_effect_next5 > 0
        and not temperature_limit_reached(room, options) and not goal_facts[0]
    )
    close_kind = None
    if close_signal:
        # B1 (0.26.7.1): the user's explicit temperature limit is the protective cause whenever it is reached (and no
        # critical CO2 keeps the window open) – independent of the delta of the opening the room model happened to use
        if temperature_limit_reached(room, options) and not urgent:
            action, reason, close_kind = "Close", TEMPERATURE_LIMIT_CLOSE_REASON, "temperature_limit"
        elif model_fallback and future_moisture_risk_15:
            action, reason, close_kind = "Close", "Sensor updates are missing; forecast indicates the drying advantage will soon be lost", "model_fallback"
        elif model_fallback:
            action, reason, close_kind = "Close", "Sensor updates are missing; model indicates additional ventilation benefit is too low", "model_fallback"
        elif summer_warming:
            action, reason, close_kind = "Close", SUMMER_WARMING_CLOSE_REASON, "summer_warming"
        elif goal_kind == "reached" and delta > float(options.get("close_delta", 0.4)):
            action, reason, close_kind = "Close", GOALS_REACHED_CLOSE_REASON, "goals_reached"
        elif goal_kind == "held" and delta > float(options.get("close_delta", 0.4)):
            action, reason, close_kind = "Close", GOALS_HELD_CLOSE_REASON, "goals_held"
        elif room.close_notified_kind == BENEFIT_CLOSE_KIND and delta > float(options.get("close_delta", 0.4)) and next5 > 0:
            action, reason, close_kind = "Close", BENEFIT_EXHAUSTED_CLOSE_REASON, BENEFIT_CLOSE_KIND
        else:
            action, reason, close_kind = "Close", AIR_NO_LONGER_HELPS_CLOSE_REASON, "air_no_longer_helps"
    elif running:
        if source_keep_open:
            action, reason = "Continue ventilating", f"Active internal moisture source ({room.moisture_source_label}); ventilation is offsetting ongoing moisture generation"
        elif (profile == "summer_cooling" or comfort_cooling) and cooling_still_useful and not candidate:
            action, reason = "Continue ventilating", f"Cooling remains useful; outdoor air is {cooling_delta:.1f} °C cooler"
        else:
            action, reason = "Continue ventilating", f"Short-term 5-minute close check expects {round(next5)} ml moisture removal"
    elif outdoor_blocked and (candidate or cooling_candidate):
        action, reason = "Do not ventilate", (
            f"Pollen load {room.pollen_index:.1f} exceeds configured limit" if pollen_blocked
            else f"Outdoor fine dust {float(room.outdoor_pm25 or 0.0):.0f} µg/m³ exceeds configured limit"
        )
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
        mould_level=_mould_level(surf_rh, warn, critical, float(options.get("mould_slight_surface_rh", 60.0)), float(options.get("mould_elevated_surface_rh", 70.0))),
        learning_status=_learning_status(room.learning_samples),
        learning_samples=room.learning_samples,
        active=room.session_active,
        open=room.contact_open,
        close_recommended=bool(close_signal),
        result_ml=round(result_ml),
        water_in_air_ml=round(ah * room.volume_m3),
        cooling_candidate=cooling_candidate, comfort_cooling_active=bool(comfort_cooling and action == "Continue ventilating"), close_kind=close_kind,
        goals_reached_now=goal_facts[0], goals_in_band=goal_facts[1], benefit_close_ready=benefit_close_ready,
        moisture_effect_next_5_min_ml=round(moisture_effect_next5),
        ventilation_candidate=candidate, co2_airing=co2_airing, co2_sensor_missing=room.co2_sensor_missing,
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


def co2_release_ppm(options: dict[str, Any]) -> float:
    """#29 (0.26.7.0): absolute CO2 level down to which a started CO2 airing keeps going.

    ``co2_release`` 0/missing = automatic, i.e. the previous 50 ppm below the warning threshold.
    A configured value is never at or above the warning threshold (then it would not release).
    """
    warn = float(options.get("co2_warn", 1000.0))
    try:
        configured = float(options.get("co2_release") or 0.0)
    except (TypeError, ValueError):
        configured = 0.0
    if configured <= 0.0 or configured != configured:  # 0 / NaN = automatic
        return warn - CO2_HYSTERESIS_PPM
    return min(max(configured, 0.0), warn - 1.0)


def co2_release_configured(options: dict[str, Any]) -> bool:
    """#29: True when the user set an own absolute release level (texts name it then)."""
    try:
        return float(options.get("co2_release") or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def co2_lead(co2: float | None, options: dict[str, Any], latched: bool) -> bool:
    """CO2 at or above the warning threshold (once reached, kept down to the release level ``co2_release_ppm``)."""
    if co2 is None:
        return False
    warn = float(options.get("co2_warn", 1000.0))
    return co2 >= warn or (latched and co2 >= co2_release_ppm(options))


def _co2_state(room: "RoomInput", options: dict[str, Any], moisture_candidate: bool, delta: float) -> tuple[bool, bool, bool]:
    """(CO2 still needs the air, critical, airing for CO2 alone).

    "Still needs the air" is ``co2_lead``: from the warning threshold, and once an
    airing for it started down to 50 ppm below (audit P1-03: the small-return and
    the humidity-plateau close ignored this band and closed at 975 ppm).

    0.26.5.4 (review A07): elevated CO2 asks for an airing of its own – no longer
    hidden only because the drying difference is too small. Not when the CO2 goal
    is switched off (``co2`` is then None), and not when the reference air is
    clearly wetter (more than ``close_delta``): then it stays "wait" with the CO2
    reason. Pollen and fine dust still veto it like every other airing.
    """
    # audit P1-04: a CO2 airing whose sensor lost its value runs on the plan made when it was opened
    blind = room.session_co2_only and room.session_active and room.co2_sensor_missing and room.session_elapsed_min < float(room.session_target_min or 0.0)
    co2_held = co2_lead(room.co2, options, room.co2_lead_latched) or blind
    co2_urgent = room.co2 is not None and room.co2 >= float(options.get("co2_critical", 1400.0))
    co2_airing = (not moisture_candidate and not co2_urgent and co2_lead(room.co2, options, room.co2_lead_latched)
                  and delta >= -float(options.get("close_delta", 0.4)))
    return co2_held, co2_urgent, co2_airing


def update_learning(
    *, old_rate: float, old_samples: int, elapsed_min: float,
    start_ah: float, end_ah: float, source_ah: float, learning_enabled: bool,
    max_duration_min: float = 120.0,
) -> tuple[float, int, str, bool]:
    """Port the V14.2.1 learning validation and smoothing rules."""
    start_delta = start_ah - source_ah
    reduction = start_ah - end_ah
    # IQ2: exact inverse of the exponential forward model (was the linear short-time approximation
    # reduction / start_delta / minutes, which made the same real rate look smaller the longer an airing lasted)
    removed = reduction / start_delta if start_delta != 0 else 0.0
    saturated = removed >= SATURATION_LIMIT
    raw = 1.0 - (1.0 - removed) ** (1.0 / elapsed_min) if elapsed_min > 0 and 0.0 < removed < 1.0 else 0.0

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
    if saturated:
        return old_rate, old_samples, f"Rejected: room reached {removed * 100:.0f} % of the reference difference; the exchange rate is not identifiable", False
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
