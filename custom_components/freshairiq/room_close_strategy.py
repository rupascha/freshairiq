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
threshold on two new humidity reports in a row. That close has its own cause and never counts as reached goals.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

from .model import (
    BENEFIT_CLOSE_KIND, CLOSE_RELEASE_FACTOR, MIN_RETURN_MIN_VOLUME_FACTOR,
    MIN_RETURN_REFERENCE_VOLUME_M3,
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
BENEFIT_CONFIRMATIONS = 2
# the forecast must already follow the measured course of this airing, from frames that are neither held nor uncertain
BENEFIT_MIN_LIVE_WEIGHT = 0.5
BENEFIT_FRAME_QUALITIES = frozenset({"excellent", "acceptable"})
_BENEFIT_PROFILE_FACTOR = {"dehumidify": 0.6, "summer_cooling": 0.5}
# beginnings of the close-check lines of room_recommendation that the benefit check replaces
_REASON_PREFIXES = {"Kurzfristiger Schließcheck (5 min)", "Weiteres Lüften entfernt kaum noch Feuchtigkeit"}


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


def benefit_close_state(mem: dict[str, Any], forecast: Any, options: dict[str, Any], volume_m3: Any) -> dict[str, Any]:
    """Room fields of the benefit check: the value the close compares, the room's threshold and the confirmations."""
    benefit = benefit_next5_ml(forecast)
    check = mem.get(BENEFIT_CHECK_KEY) if isinstance(mem.get(BENEFIT_CHECK_KEY), dict) else {}
    on = bool(options.get("room_close_on_goals"))
    return {
        "forecast_5_min_benefit_ml": None if benefit is None else round(benefit),
        "close_benefit_threshold_ml": round(_threshold(options, volume_m3), 1) if on else None,
        "close_benefit_confirmations": int(check.get("low") or 0) if not check.get("latched") else BENEFIT_CONFIRMATIONS,
    }


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
    the threshold close, two at ``CLOSE_RELEASE_FACTOR`` times the threshold open the window again. Held, stale or
    repeated readings neither confirm nor lift the close.
    """
    if getattr(result, "data_quality", "ok") != "ok":
        return False
    stored = mem.get(BENEFIT_CHECK_KEY)
    check = dict(stored) if isinstance(stored, dict) else {}
    benefit = benefit_next5_ml(forecast)
    if not running or not getattr(result, "benefit_close_ready", False):
        check = {}
    elif benefit is not None:
        threshold = _threshold(options, volume_m3)
        frame = frame if isinstance(frame, dict) else {}
        stamp = frame.get("humidity_reported_at")
        weight = _finite(forecast.get("live_observation_weight")) or 0.0
        live = bool(forecast.get("live_adapted")) and weight >= BENEFIT_MIN_LIVE_WEIGHT
        if stamp and stamp != check.get("frame") and str(frame.get("quality") or "") in BENEFIT_FRAME_QUALITIES and live:
            low, high = int(check.get("low") or 0), int(check.get("high") or 0)
            if benefit < threshold:
                low, high = low + 1, 0
            else:
                low, high = 0, (high + 1 if benefit >= threshold * CLOSE_RELEASE_FACTOR else 0)
            latched = bool(check.get("latched"))
            if not latched and low >= BENEFIT_CONFIRMATIONS:
                latched, high = True, 0
            elif latched and high >= BENEFIT_CONFIRMATIONS:
                latched, low = False, 0
            check = {"frame": stamp, "low": low, "high": high, "latched": latched,
                     "benefit_ml": round(benefit, 1), "threshold_ml": round(threshold, 1)}
        latched = bool(check.get("latched"))
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
