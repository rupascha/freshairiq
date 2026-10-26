"""When further airing no longer lowers the humidity (pure, 0.26.5.3).

Community report (heinzel): the bathroom fan was switched on by a moisture
source; the target was 58 %, the room stuck at 59 % and FreshAirIQ showed
"noch 3 Minuten" for over half an hour. Two causes:

* The supply air (outdoors, neighbouring room, window reference) only allows
  the room to come down to a certain humidity – the *equilibrium*. When that
  is above the target, the target cannot be reached by airing at all.
* The time left was "distance ÷ current rate". Near the equilibrium both shrink
  in the same proportion, so the estimate never decreased.

This module gives the equilibrium, an honest time estimate along the
exponential approach, and a *sliding* plateau check (the user's idea): if the
humidity did not fall noticeably during the last 15 minutes, the airing has
done what it can.
"""
from __future__ import annotations

from math import exp, isfinite, log
from typing import Any

PLATEAU_WINDOW_MIN = 15.0
# many sensors report whole percent: one step is no progress
PLATEAU_MAX_DROP_RH = 1.0
PLATEAU_MAX_DROP_AH = 0.15
UNREACHABLE_MARGIN_RH = 0.5
_KEEP_MIN = 30.0
_MAX_ETA_MIN = 240.0


def _svp(temp_c: float) -> float:
    return 6.112 * exp((17.62 * temp_c) / (243.12 + temp_c))


def equilibrium_rh(room_temp_c: Any, reference_ah: Any) -> float | None:
    """Relative humidity the room approaches with the supply air (absolute humidity g/m³)."""
    try:
        t, ah = float(room_temp_c), float(reference_ah)
    except (TypeError, ValueError):
        return None
    if not (isfinite(t) and isfinite(ah)) or ah <= 0 or not -30 < t < 60:
        return None
    return min(100.0, ah * (273.15 + t) / (216.7 * _svp(t)) * 100.0)


def goal_unreachable(rh: float | None, target: float, floor: float | None) -> bool:
    """The humidity target lies at or below what the supply air allows."""
    return rh is not None and floor is not None and rh > target and floor > target - UNREACHABLE_MARGIN_RH


def humidity_eta(rh: float | None, target: float, rate_pct_min: float | None, floor: float | None) -> float | None:
    """Minutes until ``target`` along the exponential approach to ``floor``.

    ``rate`` is the current change in %/min. Without a floor (room closed) the
    linear estimate is kept; an unreachable target has no time at all.
    """
    if rh is None or rh <= target:
        return 0.0
    if rate_pct_min is None or rate_pct_min >= -0.001:
        return None
    if floor is None:
        return round(min((rh - target) / abs(rate_pct_min), _MAX_ETA_MIN), 1)
    if goal_unreachable(rh, target, floor) or rh <= floor:
        return None
    tau = (rh - floor) / abs(rate_pct_min)
    return round(min(tau * log((rh - floor) / (target - floor)), _MAX_ETA_MIN), 1)


def record_sample(window: Any, elapsed_min: float, rh: float, ah: float, reports: int | None = None) -> list[dict[str, float]]:
    """Add one sample per minute of the running airing; a new airing starts afresh.

    ``reports`` is the number of humidity reports of this airing so far (stored as ``n``).
    """
    samples = [s for s in (window if isinstance(window, list) else []) if isinstance(s, dict)]
    if samples and float(samples[-1].get("t", 0.0)) > elapsed_min:
        samples = []
    if not samples or elapsed_min - float(samples[-1].get("t", 0.0)) >= 1.0:
        sample = {"t": round(elapsed_min, 2), "rh": round(rh, 2), "ah": round(ah, 3)}
        samples.append(sample if reports is None else {**sample, "n": int(reports)})
    return [s for s in samples if elapsed_min - float(s["t"]) <= _KEEP_MIN]


def humidity_plateau(window: Any, elapsed_min: float, rh: float, ah: float, reports: int | None = None) -> bool:
    """The humidity hardly fell during the last ``PLATEAU_WINDOW_MIN`` minutes.

    Audit P1-07 (0.26.5.4): a value that was merely held – no new humidity report in
    that window (silent sensor) – is no evidence of a plateau.
    """
    samples = [s for s in (window if isinstance(window, list) else []) if isinstance(s, dict)]
    older = [s for s in samples if elapsed_min - float(s.get("t", 0.0)) >= PLATEAU_WINDOW_MIN]
    if not older:
        return False
    then = older[-1]
    if reports is not None and "n" in then and int(reports) <= int(then["n"]):
        return False
    return float(then["rh"]) - rh < PLATEAU_MAX_DROP_RH and float(then["ah"]) - ah < PLATEAU_MAX_DROP_AH


def track_session(mem: dict[str, Any], *, session_active: bool, elapsed_min: float, temp_c: Any, rh: Any,
                  reports: int | None = None) -> bool:
    """Keep the sliding window of the running airing in ``mem``; True on a plateau."""
    try:
        t, h = float(temp_c), float(rh)
    except (TypeError, ValueError):
        t = h = float("nan")
    if not session_active or not (isfinite(t) and isfinite(h)):
        mem.pop("session_humidity_window", None)
        return False
    ah = 216.7 * ((h / 100.0) * _svp(t)) / (273.15 + t)
    mem["session_humidity_window"] = record_sample(mem.get("session_humidity_window"), elapsed_min, h, ah, reports)
    return humidity_plateau(mem["session_humidity_window"], elapsed_min, h, ah, reports)
