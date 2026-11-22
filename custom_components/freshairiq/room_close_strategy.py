"""Per-room close strategy and temperature limit (K02, default changed with IQ2 in 0.26.7.1). Pure logic.

Default (nothing chosen): ``goals_reached`` – a running airing closes once the room's active goals are reliably reached
(humidity at or below ``target_rh`` on fresh, confirmed readings, no CO2 hold, no useful cooling left), after the
room's own minimum duration and never while a moisture source runs or follows up (``model._running_close``). The
close is kept inside the existing humidity hysteresis. A drier outdoor air alone no longer keeps a window open
against the only goal that is already met.

A room may choose
* ``keep_drying`` – the earlier behaviour (F11): the airing continues while drier air still takes moisture out and
  closes when the air no longer helps;
* its own temperature limit while airing; empty = the global value is inherited, 0 = no limit for this room.
No new thresholds or durations: the existing ``target_rh``, ``min_duration_min`` and humidity hysteresis are used.

With the default a running airing whose humidity target is still open also closes once its remaining benefit is
exhausted (``apply_benefit_close``): the uncapped IQ2 benefit of the next five minutes stays below the room's own
threshold on two new reports in a row. That close has its own cause and never counts as reached goals.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from .model import (
    BENEFIT_CLOSE_KIND, CLOSE_RELEASE_FACTOR, MIN_RETURN_MIN_VOLUME_FACTOR,
    MIN_RETURN_REFERENCE_VOLUME_M3,
)
from .measurement_frame import (
    FRAME_ACCEPTABLE_SKEW_S, FRAME_HELD_SKEW_S, MAX_FUTURE_TIMESTAMP_S, REFERENCE_HELD_MAX_AGE_S, REFERENCE_HELD_SKEW_S,
    ROOM_HELD_MAX_AGE_S,
)
from .room_recommendation import benefit_close_text, running_check_text

CONF_ROOM_CLOSE_STRATEGY = "close_strategy"
CONF_ROOM_AIRING_MIN_TEMP = "room_airing_min_temp_c"
STRATEGY_GOALS = "goals_reached"
STRATEGY_KEEP_DRYING = "keep_drying"
# Earlier name of the earlier default. Test builds wrote it into every saved room (the form stored its default), so a
# stored "continue_while_drying" is no deliberate choice: it is read as "nothing chosen" = the default below.
STRATEGY_CONTINUE = "continue_while_drying"
CLOSE_STRATEGIES = (STRATEGY_GOALS, STRATEGY_KEEP_DRYING)
ROOM_TEMP_LIMIT_MIN_C, ROOM_TEMP_LIMIT_MAX_C = 0.0, 30.0   # the bounds of the global option


def close_strategy(cfg: dict[str, Any]) -> str:
    """IQ2 (0.26.7.1): default = close once the goals are reached; "keep_drying" only when chosen explicitly."""
    return STRATEGY_KEEP_DRYING if str(cfg.get(CONF_ROOM_CLOSE_STRATEGY) or "") == STRATEGY_KEEP_DRYING else STRATEGY_GOALS


def room_temperature_limit(cfg: dict[str, Any]) -> float | None:
    """The room's own limit (°C) or None = inherit the global one. Invalid values are ignored (inherit)."""
    raw = cfg.get(CONF_ROOM_AIRING_MIN_TEMP)
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) and ROOM_TEMP_LIMIT_MIN_C <= value <= ROOM_TEMP_LIMIT_MAX_C else None


def room_close_options(options: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Options as one room sees them (close on reached goals unless the room chose to keep drying)."""
    strategy, limit = close_strategy(cfg), room_temperature_limit(cfg)
    out = dict(options)
    out["room_close_on_goals"] = strategy == STRATEGY_GOALS
    if limit is not None:
        out["airing_min_room_temp_c"] = limit
    return out


BENEFIT_CHECK_KEY = "session_benefit_check"
# state of the check of a running airing (a fixed code) and, per room channel, the report seen last and whether its value was new
CLOSE_CHECK_KEY = "session_close_check"
BENEFIT_CONFIRMATIONS = 2
# the forecast must already follow the measured course of this airing, from frames that are neither held nor uncertain
BENEFIT_MIN_LIVE_WEIGHT = 0.5
BENEFIT_FRAME_QUALITIES = frozenset({"excellent", "acceptable"})
# the staggered path takes both grades between them and stale: a pair closer together than "held" is no worse evidence
BENEFIT_STAGGERED_QUALITIES = frozenset({"uncertain", "held"})
BASIS_REGULAR, BASIS_STAGGERED = "regular", "staggered"
_BENEFIT_PROFILE_FACTOR = {"dehumidify": 0.6, "summer_cooling": 0.5}
# beginnings of the close-check lines of room_recommendation that the benefit check replaces
_REASON_PREFIXES = {"Kurzfristiger Schließcheck (5 min)", "Weiteres Lüften entfernt kaum noch Feuchtigkeit"}


# Issue #30: a staggered pair – a new value of one room channel next to an older value of the other (an uncertain or held
# frame) – may confirm an exhausted benefit as well (never lift it, never any other close). The new value is a real report of
# this airing, received at most this long ago …
HELD_REPORT_MAX_AGE_S = 300.0
# … while the older channel may have moved since its report: a reporting step plus a rate times its age. A temperature moves
# by the larger of the forecast's own change and a floor; the absolute humidity moves by about this share per kelvin at
# fixed RH, and by its relative share when the relative humidity moves
HELD_TEMP_STEP_C = 0.3
HELD_TEMP_RATE_C_MIN = 0.02
HELD_REFERENCE_TEMP_RATE_C_MIN = 0.03
HELD_AH_PER_K = 0.075
HELD_RH_STEP_PCT = 1.0
HELD_RH_RATE_PCT_MIN = 0.05
# a coherent reference pair (temperature and humidity reported together) may be older: outdoor absolute humidity drifts slowly
HELD_REFERENCE_AH_DRIFT_G_M3_H = 0.6
# the readings must stay usable for the five minutes the benefit refers to – a close is never confirmed on a frame that is
# about to turn stale (and would be withdrawn again at once)
HELD_USABLE_AHEAD_S = 300.0
# an older channel of a sensor that has just reported its other channel is held by a working device: its time stamp alone no
# longer blocks the close, its possible drift is counted up to the age a held pair may reach anyway
HELD_ALIVE_AGE_CAP_S = FRAME_HELD_SKEW_S - HELD_USABLE_AHEAD_S
_CHANNELS = (("humidity", "humidity_reported_at", "age_humidity_s", "frame"),
             ("temperature", "temperature_reported_at", "age_temperature_s", "frame_t"))


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def benefit_threshold_ml(min_return_ml: Any, volume_m3: Any, profile: Any) -> float:
    """5-minute benefit (ml) below which further airing of this room is not worth it.

    The configured value refers to a 30 m³ room and follows the volume both ways – a large room moves more water for the
    same air change, a small one keeps at least a quarter – with the profile factors of the room model.
    """
    base = _finite(min_return_ml)
    volume = _finite(volume_m3)
    factor = max(volume / MIN_RETURN_REFERENCE_VOLUME_M3, MIN_RETURN_MIN_VOLUME_FACTOR) if volume and volume > 0 else 1.0
    return max(25.0 if base is None else base, 0.0) * factor * _BENEFIT_PROFILE_FACTOR.get(str(profile or ""), 1.0)


def _threshold(options: dict[str, Any], volume_m3: Any) -> float:
    return benefit_threshold_ml(options.get("min_return_next_5_min_ml", 25.0), volume_m3, options.get("operating_profile"))


def benefit_next5_ml(forecast: Any) -> float | None:
    """Uncapped IQ2 benefit of the next five minutes: the larger of the airing effect and the outdoor removal.

    Internal moisture production and the net change of the room are not part of it – a room that still gets wetter
    against a running source is not proof that the air no longer helps.
    """
    if not isinstance(forecast, dict) or forecast.get("method") == "unavailable":
        return None
    values = [v for v in (_finite(forecast.get(k)) for k in ("moisture_effect_ml", "outdoor_transport_ml")) if v is not None]
    return max(values) if values else None


def benefit_close_state(mem: dict[str, Any], forecast: Any, options: dict[str, Any], volume_m3: Any,
                        result: Any = None) -> dict[str, Any]:
    """Room fields of the benefit check: the value the close compares, the room's threshold and the confirmations.

    A running airing also names the state of its check (``close_check``, a fixed code) and the path a confirmed close
    came from (``close_benefit_basis``); both are left out for every other room.
    """
    benefit = benefit_next5_ml(forecast)
    check = mem.get(BENEFIT_CHECK_KEY) if isinstance(mem.get(BENEFIT_CHECK_KEY), dict) else {}
    trace = mem.get(CLOSE_CHECK_KEY) if isinstance(mem.get(CLOSE_CHECK_KEY), dict) else {}
    on = bool(options.get("room_close_on_goals"))
    state = trace.get("state") if mem.get("session_active") else None
    if state and getattr(result, "data_quality", "ok") != "ok":
        state = "sensor_unavailable"
    return {
        "forecast_5_min_benefit_ml": None if benefit is None else round(benefit),
        "close_benefit_threshold_ml": round(_threshold(options, volume_m3), 1) if on else None,
        "close_benefit_confirmations": int(check.get("low") or 0) if not check.get("latched") else BENEFIT_CONFIRMATIONS,
        **({"close_check": state} if state else {}),
        **({"close_benefit_basis": check.get("basis")} if state and check.get("latched") else {}),
    }


def _stamp(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def held_benefit_margin_ml(frame: dict[str, Any], result: Any, forecast: dict[str, Any], volume_m3: Any, *,
                          new: str = "humidity", alive: bool = False) -> float | None:
    """How far the 5-minute benefit of a staggered frame may be off (ml), or None when its readings are not usable for a close.

    ``new`` is the room channel that has just reported; the other one is older. Room and reference are checked separately. The
    older room channel may have moved by its reporting step plus a drift rate over its age (temperature: ``HELD_TEMP_STEP_C``,
    humidity: ``HELD_RH_STEP_PCT``). With ``alive`` – the same sensor reported the new channel – the older channel's age alone
    does not block, its drift is counted up to ``HELD_ALIVE_AGE_CAP_S``. A reference pair reported together only ages (the
    outdoor absolute humidity drifts slowly); a reference pair reported apart is treated like the room. Both errors move the
    benefit by the exchanged air volume of the next five minutes times the absolute-humidity error.
    """
    ages = {k: _finite(frame.get(k)) for k in ("age_humidity_s", "age_temperature_s", "age_reference_temperature_s", "age_reference_humidity_s")}
    room_t, room_rh, room_ah, ref_ah = (_finite(getattr(result, k, None)) for k in ("temperature", "humidity", "absolute_humidity", "reference_humidity"))
    volume, fraction = _finite(volume_m3), _finite(forecast.get("exchange_fraction"))
    if any(v is None or v < 0 for v in ages.values()) or room_t is None or not room_rh or not room_ah or not ref_ah or room_ah < 0 or ref_ah < 0:
        return None
    if not volume or volume <= 0 or fraction is None or not 0 < fraction <= 1:
        return None
    if (_finite(frame.get("max_future_offset_s")) or 0.0) > MAX_FUTURE_TIMESTAMP_S:
        return None
    old = "temperature" if new == "humidity" else "humidity"
    new_age, old_age = ages[f"age_{new}_s"], ages[f"age_{old}_s"]
    if new_age > HELD_REPORT_MAX_AGE_S:
        return None
    if alive:
        old_age = min(old_age, HELD_ALIVE_AGE_CAP_S)
    else:
        room_skew = _finite(frame.get("skew_s"))
        if room_skew is None or room_skew + HELD_USABLE_AHEAD_S > FRAME_HELD_SKEW_S or old_age + HELD_USABLE_AHEAD_S > ROOM_HELD_MAX_AGE_S:
            return None
    if max(ages["age_reference_temperature_s"], ages["age_reference_humidity_s"]) + HELD_USABLE_AHEAD_S > REFERENCE_HELD_MAX_AGE_S:
        return None
    if old == "temperature":
        rate = max(abs(_finite(forecast.get("temperature_change_c")) or 0.0) / 5.0, HELD_TEMP_RATE_C_MIN)
        room_error = room_ah * HELD_AH_PER_K * (HELD_TEMP_STEP_C + rate * old_age / 60.0)
    else:
        room_error = room_ah * (HELD_RH_STEP_PCT + HELD_RH_RATE_PCT_MIN * old_age / 60.0) / room_rh
    ref_skew = _finite(frame.get("reference_skew_s"))
    if ref_skew is None or ref_skew > REFERENCE_HELD_SKEW_S:
        return None
    ref_age_h = max(ages["age_reference_temperature_s"], ages["age_reference_humidity_s"]) / 3600.0
    ref_error = HELD_REFERENCE_AH_DRIFT_G_M3_H * ref_age_h
    if ref_skew > FRAME_ACCEPTABLE_SKEW_S:
        ref_error += ref_ah * HELD_AH_PER_K * (HELD_TEMP_STEP_C + HELD_REFERENCE_TEMP_RATE_C_MIN * ref_skew / 60.0)
    return volume * fraction * (room_error + ref_error)


def _paired_rows(mem: dict[str, Any]) -> list[dict[str, Any]]:
    """Available logical room sensors of this airing that report both temperature and humidity."""
    state = mem.get("session_climate_report_state")
    rows = state.values() if isinstance(state, dict) else []
    return [r for r in rows if isinstance(r, dict) and r.get("available", True) and isinstance(r.get("reports"), dict)
            and {"temperature", "humidity"} <= set(r["reports"])]


def _alive(mem: dict[str, Any], frame: dict[str, Any], kind: str) -> bool:
    """The sensor that holds the older channel has just reported ``kind``: one working device, not a silent one."""
    stamp = frame.get(f"{kind}_reported_at")
    return bool(stamp) and any(r["reports"].get(kind) == stamp for r in _paired_rows(mem))


def _staggered_report(mem: dict[str, Any], frame: dict[str, Any], check: dict[str, Any], seen: dict[str, Any]) -> str | None:
    """The room channel whose new report a staggered frame may count, or None.

    Only a new value of this airing counts, reported after the last counted report of that channel. A repeated report of the
    same value (a restart, a substituted time stamp), a coordinator refresh and a report from before the opening are no new
    evidence. Time stamps without their zone are never compared with zoned ones.
    """
    if str(frame.get("quality") or "") in BENEFIT_FRAME_QUALITIES or not frame.get("quality"):
        return None
    started, best = _stamp(mem.get("session_started")), None
    for kind, key, _, counted in _CHANNELS:
        stamp, row = frame.get(key), seen.get(kind) or {}
        if not stamp or row.get("at") != stamp or not row.get("new"):
            continue
        new, last = _stamp(stamp), _stamp(check.get(counted))
        try:
            if new is not None and started is not None and new >= started and (last is None or new > last) and (best is None or new > best[1]):
                best = (kind, new)
        except TypeError:
            continue
    return best[0] if best else None


def _holdable(mem: dict[str, Any], frame: dict[str, Any]) -> bool:
    """The readings a staggered close rests on are still usable: not stale, or stale only by the age of a working room sensor."""
    quality = str(frame.get("quality") or "")
    if quality in BENEFIT_FRAME_QUALITIES | BENEFIT_STAGGERED_QUALITIES:
        return True
    ages = [_finite(frame.get(k)) for k in ("age_humidity_s", "age_temperature_s", "age_reference_temperature_s", "age_reference_humidity_s")]
    ref_skew = _finite(frame.get("reference_skew_s"))
    if quality != "stale" or any(a is None for a in ages) or ref_skew is None or not _paired_rows(mem):
        return False
    return ((_finite(frame.get("max_future_offset_s")) or 0.0) <= MAX_FUTURE_TIMESTAMP_S and min(ages[:2]) <= ROOM_HELD_MAX_AGE_S
            and max(ages[2:]) <= REFERENCE_HELD_MAX_AGE_S and ref_skew <= REFERENCE_HELD_SKEW_S)


def _replace_reason(result: Any, reasons: list[Any], text: str, *, insert: bool) -> None:
    """Swap the room's close-check line for ``text`` in the reason list and the room reason (``insert``: or add it)."""
    reason = str(result.reason or "")
    for index, item in enumerate(reasons):
        if isinstance(item, str) and any(item.startswith(prefix) for prefix in _REASON_PREFIXES):
            reasons[index] = text
            result.reason = reason.replace(item, text, 1) if item in reason else f"{text}; {reason}" if reason else text
            return
    if insert:
        reasons.insert(0, text)
        result.reason = f"{text}; {reason}" if reason else text


def apply_benefit_close(mem: dict[str, Any], result: Any, forecast: Any, frame: Any, options: dict[str, Any],
                        volume_m3: Any, reasons: list[Any], *, running: bool) -> bool:
    """Close a running airing whose remaining benefit is confirmed exhausted; returns whether ``mem`` changed.

    Only where the room model reports that nothing else keeps the window open (``benefit_close_ready``: goal strategy,
    no source, CO2, cooling or protection, own minimum duration passed). A frame counts once – by the time of its
    humidity report – and only with an excellent or acceptable frame and a live-adapted forecast; two in a row below
    the threshold close, two at ``CLOSE_RELEASE_FACTOR`` times the threshold open the window again. Stale or repeated
    readings neither confirm nor lift the close.

    Issue #30: a new value of one room channel next to an older value of the other (uncertain, held, or stale only by the
    age of a sensor that has just reported) may count as well, once, when the benefit stays below the threshold also with
    the possible error of the older readings (``held_benefit_margin_ml``) – or, clearly above it, as a counter-measurement
    that ends the series. Such a report that decides nothing is not used up: a later report may make it a regular frame. It
    never lifts a close. A close that needed such a report (basis "staggered") is released again with its confirmation
    when the readings turn stale or unavailable.
    """
    stored = mem.get(BENEFIT_CHECK_KEY)
    check = dict(stored) if isinstance(stored, dict) else {}
    if getattr(result, "data_quality", "ok") != "ok":
        if not (running and check.get("latched") and check.get("basis") == BASIS_STAGGERED):
            return False
        mem[BENEFIT_CHECK_KEY] = _release_staggered(check)
        return True
    benefit = benefit_next5_ml(forecast)
    frame = frame if isinstance(frame, dict) else {}
    stamp = frame.get("humidity_reported_at")
    # per room channel: the report seen last and whether its value differed from the report before it
    traced = mem.get(CLOSE_CHECK_KEY)
    seen = {kind: dict((traced or {}).get(kind) or {}) for kind, *_ in _CHANNELS} if isinstance(traced, dict) and running else {}
    for kind, key, _, _ in _CHANNELS if running else ():
        if frame.get(key) and frame.get(key) != seen.get(kind, {}).get("at"):
            value, before = _finite(getattr(result, kind, None)), _finite(seen.get(kind, {}).get("value"))
            seen[kind] = {"at": frame.get(key), "value": value, "new": value is not None and before is not None and value != before}
    state = None
    if not running:
        check = {}
    elif not getattr(result, "benefit_close_ready", False):
        state = ("keep_drying" if not options.get("room_close_on_goals") else
                 "other_close" if result.close_recommended and result.close_kind != BENEFIT_CLOSE_KIND else
                 "moisture_source" if getattr(result, "moisture_source_active", False) or getattr(result, "moisture_source_recovery", False) else
                 "not_ready")
        check = {}
    elif benefit is None:
        state = "no_forecast"
    else:
        threshold = _threshold(options, volume_m3)
        weight = _finite(forecast.get("live_observation_weight")) or 0.0
        live = bool(forecast.get("live_adapted")) and weight >= BENEFIT_MIN_LIVE_WEIGHT
        quality = str(frame.get("quality") or "")
        if check.get("latched") and check.get("basis") == BASIS_STAGGERED and not _holdable(mem, frame):
            check = _release_staggered(check)
            state = "released_stale"
        if stamp and stamp != check.get("frame") and quality in BENEFIT_FRAME_QUALITIES and live:
            low, high = int(check.get("low") or 0), int(check.get("high") or 0)
            staggered = int(check.get("staggered") or 0)
            if benefit < threshold:
                low, high = low + 1, 0
            else:
                low, high, staggered = 0, (high + 1 if benefit >= threshold * CLOSE_RELEASE_FACTOR else 0), 0
            latched = bool(check.get("latched"))
            if not latched and low >= BENEFIT_CONFIRMATIONS:
                latched, high = True, 0
            elif latched and high >= BENEFIT_CONFIRMATIONS:
                latched, low, staggered = False, 0, 0
            check = {"frame": stamp, "low": low, "high": high, "latched": latched,
                     "benefit_ml": round(benefit, 1), "threshold_ml": round(threshold, 1)}
            if staggered:
                check["staggered"] = staggered
            if frame.get("temperature_reported_at"):
                check["frame_t"] = frame["temperature_reported_at"]
        elif live and not check.get("latched") and isinstance(forecast, dict) and (channel := _staggered_report(mem, frame, check, seen)):
            alive = _alive(mem, frame, channel)
            margin = held_benefit_margin_ml(frame, result, forecast, volume_m3, new=channel, alive=alive) if alive or quality != "stale" else None
            # a staggered report counts as a confirmation or – clearly above the threshold – as a counter-measurement that
            # ends the series; a report whose possible error reaches across the threshold is unclear and decides nothing
            if margin is not None and (benefit + margin < threshold or benefit - margin >= threshold):
                low = int(check.get("low") or 0) + 1 if benefit + margin < threshold else 0
                staggered = int(check.get("staggered") or 0) + 1 if low else 0
                check = {"frame": frame.get("humidity_reported_at"), "frame_t": frame.get("temperature_reported_at"), "low": low, "high": 0,
                         "latched": low >= BENEFIT_CONFIRMATIONS, "benefit_ml": round(benefit, 1), "threshold_ml": round(threshold, 1),
                         "margin_ml": round(margin, 1), "channel": channel}
                if staggered:
                    check["staggered"] = staggered
        if check.get("latched"):
            check["basis"] = BASIS_REGULAR if int(check.get("low") or 0) - int(check.get("staggered") or 0) >= BENEFIT_CONFIRMATIONS else BASIS_STAGGERED
        else:
            check.pop("basis", None)
        latched = bool(check.get("latched"))
        if state is None:
            state = (("confirmed" if check.get("basis") == BASIS_REGULAR else "confirmed_staggered") if latched else
                     "forecast_not_live" if not live else "above_threshold" if benefit >= threshold else
                     "confirming" if int(check.get("low") or 0) else "waiting_for_report")
        if latched and result.action == "Continue ventilating" and not result.close_recommended:
            result.action, result.close_kind, result.close_recommended = "Close", BENEFIT_CLOSE_KIND, True
        if result.close_kind == BENEFIT_CLOSE_KIND and result.close_recommended:
            if latched:
                text = benefit_close_text(float(check.get("benefit_ml", benefit)), threshold, result.humidity, options)
                _replace_reason(result, reasons, text, insert=True)
        elif result.action == "Continue ventilating":
            _replace_reason(result, reasons, running_check_text(benefit), insert=False)
    if (running and not check.get("latched") and benefit is not None and result.action == "Close"
            and result.close_kind == BENEFIT_CLOSE_KIND and result.close_recommended):
        # the stored close of the room model is lifted here: the benefit is back or something else keeps the window open
        result.action, result.close_kind, result.close_recommended = "Continue ventilating", None, False
        _replace_reason(result, reasons, running_check_text(benefit), insert=True)
    changed = (check or None) != stored
    if changed:
        mem[BENEFIT_CHECK_KEY] = check or None
    trace = {**seen, "state": state} if running else None
    if trace != traced:
        mem[CLOSE_CHECK_KEY] = trace; changed = True
    if mem.get("session_active") and running:
        close = bool(result.close_recommended)
        if bool(mem.get("close_notified", False)) != close:
            mem["close_notified"] = close; changed = True
        kind = mem.get("close_notified_kind")
        benefit_kind = kind is None and result.close_kind == BENEFIT_CLOSE_KIND
        new_kind = (BENEFIT_CLOSE_KIND if benefit_kind else kind) if close else None
        if new_kind != kind:
            mem["close_notified_kind"] = new_kind; changed = True
    return changed


def _release_staggered(check: dict[str, Any]) -> dict[str, Any]:
    """Withdraw a close that needed a staggered report together with the confirmations of that path."""
    low = max(int(check.get("low") or 0) - int(check.get("staggered") or 0), 0)
    out = {k: v for k, v in check.items() if k not in {"latched", "basis", "staggered", "margin_ml"}}
    out.update({"low": low, "high": 0, "latched": False})
    return out
