"""How much of a room's air an airing has exchanged so far (pure, 0.26.5.4).

Community question (HarryP): a bedroom without CO₂ sensor is aired in the
morning, and the user wants to see how far the air has been replaced. This is
display only – no goal, no priority, no influence on any recommendation.

The room's learned exchange rate (share of the room air replaced per minute,
per opening mode or fan) times the same airflow and cross-ventilation factors
the model uses gives the rate under the current conditions. The share of old
air still in the room shrinks exponentially; it is carried from cycle to cycle,
so an opened second window or a change of wind shortens the remaining time at
once. 100 % is never reached physically – the display counts down to 95 %
(about three air changes).
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any

DISPLAY_TARGET = 0.95
_MAX_RATE = 0.95


def _rate(rate_per_min: Any, factor: Any) -> float:
    try:
        value = float(rate_per_min) * float(factor)
    except (TypeError, ValueError):
        return 0.0
    if value != value:
        return 0.0
    return min(max(value, 0.0), _MAX_RATE)


def advance_air_exchange(
    mem: dict[str, Any], *, active: bool, elapsed_min: Any, now: datetime, rate_per_min: Any, factor: Any, learned: bool,
) -> dict[str, Any] | None:
    """Exchanged share and minutes to 95 % for a running airing (``None`` otherwise); ``mem`` is updated."""
    if not active:
        mem.pop("air_exchange", None)
        return None
    rate = _rate(rate_per_min, factor)
    state = mem.get("air_exchange") if isinstance(mem.get("air_exchange"), dict) else {}
    session = mem.get("session_started")
    try:
        last = datetime.fromisoformat(str(state.get("at")))
        share = float(state["share"])
        minutes = max((now - last).total_seconds() / 60.0, 0.0) if state.get("session") == session else None
    except (KeyError, TypeError, ValueError):
        minutes = None
    if minutes is None:
        # new airing, or nothing remembered (e.g. after a restart): start from the elapsed time
        try:
            elapsed = max(float(elapsed_min or 0.0), 0.0)
        except (TypeError, ValueError):
            elapsed = 0.0
        share, minutes = 1.0, elapsed
    share = min(max(share * (1.0 - rate) ** minutes, 0.0), 1.0)
    mem["air_exchange"] = {"session": session, "share": round(share, 6), "at": now.isoformat()}
    remaining_share = 1.0 - DISPLAY_TARGET
    if share <= remaining_share:
        to_target: float | None = 0.0
    elif rate <= 0.0:
        to_target = None
    else:
        to_target = round(math.log(remaining_share / share) / math.log(1.0 - rate), 1)
    return {
        # 0.26.5.4 (review A09): the display stops at 95 % ("practically complete"), never 100 %
        "exchanged_percent": min(int(math.floor((1.0 - share) * 100.0)), int(DISPLAY_TARGET * 100)),
        "minutes_to_95": to_target,
        "rate_per_min": round(rate, 4),
        "estimate": not learned,
    }
