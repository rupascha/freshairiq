"""#31: give up a CO2 airing whose CO2 levels off above the release level (pure logic)."""
from __future__ import annotations

from statistics import linear_regression
from typing import Any

from .model import co2_release_ppm

CO2_SLOPE_WINDOW_S = 120.0  # the fall is measured over the last two minutes of CO2 samples
CO2_GIVE_UP_MIN = 2.0  # an airing that needs longer than this to reach the release level no longer pays off
CO2_CLEAR_FALL_PPM_MIN = 20.0  # falling faster than this: keep airing
CO2_RISE_PPM_MIN = 10.0  # rising faster than this: keep airing
# give up only once the fall is at most a quarter of the steepest fall of this airing – a plateau flattens, a slow steady fall does not
CO2_FLATTENED_SHARE = 0.25
CO2_GIVE_UP_HOLD_S = 120.0  # the give-up condition must hold this long without interruption, so one noisy slope cannot end an airing


def co2_slope_ppm_min(samples: list[tuple[float, float]]) -> float | None:
    """Least-squares CO2 slope (ppm/min) over the last two minutes of ``(seconds, ppm)`` samples; None when unknown.

    shortcut: a sensor reporting less often than every 2 min gives no slope, so its airing just keeps going; a wider
    window would mix in the slow start of the airing (support_134), upgrade only with a better start-up rule.
    The steepest fall of an airing is runtime-only: after an HA restart during an airing only the steepest fall since the restart counts, so the give-up comes later (safe side).
    """
    if not samples:
        return None
    recent = [s for s in samples if s[0] >= samples[-1][0] - CO2_SLOPE_WINDOW_S]
    if recent[-1][0] - recent[0][0] < 60.0:  # the span also guarantees two points
        return None
    return linear_regression([s[0] / 60.0 for s in recent], [s[1] for s in recent]).slope


def co2_airing_given_up(co2: float, options: dict[str, Any], slope: float | None, elapsed_min: float, steepest: float) -> bool:
    """A running CO2 airing inside the hold band (release level <= CO2 < warning threshold) no longer pays off.

    Unknown or clear movement keeps airing; a slow fall keeps airing only when the release level is within
    ``CO2_GIVE_UP_MIN`` minutes at that pace, and only once the fall flattened against ``steepest`` (the most negative
    slope of this airing). Not before ``min_duration_min``; above the warning threshold the rule
    does not apply (closing there would re-trigger "Ventilate" at once).
    """
    release = co2_release_ppm(options)
    if elapsed_min < float(options["min_duration_min"]) or not release <= co2 < float(options.get("co2_warn", 1000.0)) or slope is None:
        return False
    if slope > CO2_RISE_PPM_MIN or slope < -CO2_CLEAR_FALL_PPM_MIN:
        return False
    if steepest < 0.0 and slope < CO2_FLATTENED_SHARE * steepest:
        return False
    return slope >= 0.0 or (co2 - release) / -slope > CO2_GIVE_UP_MIN


def co2_give_up_confirmed(since: float | None, at: float, holds: bool, hold_s: float = CO2_GIVE_UP_HOLD_S) -> tuple[float | None, bool]:
    """(new ``since``, confirmed): ``since`` is the sample time (s) from which the give-up condition has held without a break."""
    since = (at if since is None else since) if holds else None
    return since, since is not None and at - since >= hold_s
