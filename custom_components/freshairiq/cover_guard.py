"""Shutter/blind learning guard over the whole airing (0.26.4.9).

User feedback (FAIQ-FB-CA969D3722D2): "nach dem Lernvorgang die Meldung, dass
im Schlafzimmer der Rollo zu 96 % geschlossen war … tatsächlich war er zu 90 %
geöffnet". Until 0.26.4.8 a single moment with the shutter closed more than the
learning limit blocked the learning sample of the whole session – typically the
seconds right after opening the window while the shutter was still on its way
up – and the message reported that moment's value.

Now the guard measures *how long* the shutter was closed more than the limit
during the airing. A sample is skipped only when that was the case for a
relevant part of the session (at least two minutes and at least a quarter of
the time). Covers that are moving (opening/closing) are not judged.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

MIN_BLOCKED_SECONDS = 120.0
MIN_BLOCKED_SHARE = 0.25
MAX_TICK_SECONDS = 180.0

MEMORY_DEFAULTS: dict[str, Any] = {
    "session_cover_observed_s": 0.0,
    "session_cover_closed_s": 0.0,
    "session_cover_max_closed": 0.0,
    "session_cover_last_tick": None,
    "session_cover_last_blocked": False,
}


def reset(mem: dict[str, Any]) -> None:
    """Start a new session's cover bookkeeping."""
    mem.update(MEMORY_DEFAULTS)


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def tick(mem: dict[str, Any], guard: dict[str, Any], now: datetime) -> None:
    """Account the time since the last cycle to the previous cover state."""
    last = _parse(mem.get("session_cover_last_tick"))
    if last is not None:
        try:
            delta = (now - last).total_seconds()
        except TypeError:  # naive/aware mix from an old store
            delta = 0.0
        delta = min(max(delta, 0.0), MAX_TICK_SECONDS)
        mem["session_cover_observed_s"] = float(mem.get("session_cover_observed_s") or 0.0) + delta
        if mem.get("session_cover_last_blocked"):
            mem["session_cover_closed_s"] = float(mem.get("session_cover_closed_s") or 0.0) + delta
    # Moving covers are already left out of ``affected``; any other cover still counts.
    blocked_now = bool(guard.get("blocked"))
    mem["session_cover_last_blocked"] = blocked_now
    mem["session_cover_last_tick"] = now.isoformat()
    if blocked_now:
        worst = max((float(row.get("closed_percent", 0.0) or 0.0) for row in guard.get("affected") or [] if isinstance(row, dict)), default=0.0)
        mem["session_cover_max_closed"] = max(float(mem.get("session_cover_max_closed") or 0.0), worst)


def verdict(mem: dict[str, Any], threshold: float) -> dict[str, Any]:
    """Whether the session must not be used as a learning sample."""
    observed = float(mem.get("session_cover_observed_s") or 0.0)
    closed = float(mem.get("session_cover_closed_s") or 0.0)
    share = closed / observed if observed > 0 else 0.0
    blocked = closed >= MIN_BLOCKED_SECONDS and share >= MIN_BLOCKED_SHARE
    return {
        "blocked": blocked,
        "threshold": float(threshold),
        "closed_minutes": round(closed / 60.0, 1),
        "observed_minutes": round(observed / 60.0, 1),
        "closed_share_percent": round(share * 100.0, 1),
        "max_closed_percent": round(float(mem.get("session_cover_max_closed") or 0.0), 1),
    }


def diagnosis(result: dict[str, Any]) -> str:
    """User-facing reason for a skipped sample (German; English via text_en)."""
    return (
        f"Lernmessung übersprungen: Rollladen/Jalousie war {result['closed_minutes']:.0f} von {result['observed_minutes']:.0f} Minuten "
        f"stärker als die Lern-Grenze von {result['threshold']:.0f} % geschlossen (bis zu {result['max_closed_percent']:.0f} %). "
        "Die Lüftung wurde weiterhin erkannt und bilanziert."
    )
