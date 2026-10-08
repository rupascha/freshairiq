"""Post-close moisture stabilization tracking for FreshAirIQ.

This layer observes the room after a ventilation session has ended.  It is
strictly diagnostic in v1: it quantifies moisture rebound / continued drying
without changing the production forecast or adaptive learning coefficients.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any

TARGET_MINUTES = 10.0
MAX_MINUTES = 15.0
MIN_SAMPLE_SPACING_SECONDS = 45.0
MAX_SAMPLES = 24

def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _elapsed_minutes(started: datetime, now: datetime) -> float:
    """Calculate elapsed minutes across legacy naive/aware timestamp mixes."""
    if started.tzinfo is None and now.tzinfo is not None:
        started = started.replace(tzinfo=now.tzinfo)
    elif started.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=started.tzinfo)
    return max(0.0, (now - started).total_seconds() / 60.0)


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def start_post_close_observation(
    room: dict[str, Any], *, event_id: str, room_key: str, room_name: str, now: datetime, close_ah: float,
    close_temp_c: float, removed_ml: float, volume_m3: float,
    frame_quality: str | None,
) -> None:
    """Start a bounded post-close observation linked to one finished session."""
    room["post_close_active"] = True
    room["post_close_event_id"] = event_id
    room["post_close_room_key"] = str(room_key)
    room["post_close_room_name"] = str(room_name)
    room["post_close_started_at"] = now.isoformat()
    room["post_close_ah"] = round(float(close_ah), 6)
    room["post_close_temp_c"] = round(float(close_temp_c), 4)
    room["post_close_removed_ml"] = round(float(removed_ml), 4)
    room["post_close_volume_m3"] = round(max(float(volume_m3), 0.0), 4)
    room["post_close_start_frame_quality"] = frame_quality
    room["post_close_contaminated"] = False
    room["post_close_samples"] = []
    room["post_close_last_sample_at"] = None
    room["post_close_last_outcome"] = None


def _outcome(
    room: dict[str, Any], *, now: datetime, current_ah: float | None,
    current_temp_c: float | None, status: str, reason: str,
    frame_quality: str | None,
) -> dict[str, Any]:
    started = _dt(room.get("post_close_started_at")) or now
    elapsed = _elapsed_minutes(started, now)
    close_ah = _num(room.get("post_close_ah"), 0.0)
    close_temp = _num(room.get("post_close_temp_c"), 0.0)
    volume = max(_num(room.get("post_close_volume_m3"), 0.0), 0.0)
    close_removed = _num(room.get("post_close_removed_ml"), 0.0)
    delta_ml = None
    rebound_ml = None
    continued_drying_ml = None
    retained_removed_ml = None
    temp_recovery_c = None
    if current_ah is not None and volume > 0:
        delta_ml = (_num(current_ah, close_ah) - close_ah) * volume
        rebound_ml = max(delta_ml, 0.0)
        continued_drying_ml = max(-delta_ml, 0.0)
        retained_removed_ml = close_removed - delta_ml
    if current_temp_c is not None:
        temp_recovery_c = _num(current_temp_c, close_temp) - close_temp

    threshold_ml = max(10.0, abs(close_removed) * 0.05)
    if delta_ml is None:
        interpretation = "unknown"
    elif rebound_ml is not None and rebound_ml >= threshold_ml:
        interpretation = "moisture_rebound"
    elif continued_drying_ml is not None and continued_drying_ml >= threshold_ml:
        interpretation = "continued_drying"
    else:
        interpretation = "stable"

    clean = (
        status == "complete"
        and not bool(room.get("post_close_contaminated"))
        and room.get("post_close_start_frame_quality") in {"legacy", "excellent", "acceptable"}
        and frame_quality in {"legacy", "excellent", "acceptable"}
        and len(room.get("post_close_samples") or []) >= 2
    )
    buffer_fraction = None
    if rebound_ml is not None and abs(close_removed) >= 1.0:
        buffer_fraction = rebound_ml / abs(close_removed) * 100.0

    return {
        "event_id": room.get("post_close_event_id"),
        "key": room.get("post_close_room_key"),
        "name": room.get("post_close_room_name"),
        "started_at": room.get("post_close_started_at"),
        "completed_at": now.isoformat(),
        "elapsed_min": round(elapsed, 2),
        "status": status,
        "reason": reason,
        "valid_for_analysis": bool(clean),
        "interpretation": interpretation,
        "close_removed_ml": round(close_removed, 1),
        "post_close_delta_ml": round(delta_ml, 1) if delta_ml is not None else None,
        "moisture_rebound_ml": round(rebound_ml, 1) if rebound_ml is not None else None,
        "continued_drying_ml": round(continued_drying_ml, 1) if continued_drying_ml is not None else None,
        "retained_removed_ml": round(retained_removed_ml, 1) if retained_removed_ml is not None else None,
        "buffer_fraction_percent": round(buffer_fraction, 1) if buffer_fraction is not None else None,
        "temperature_recovery_c": round(temp_recovery_c, 2) if temp_recovery_c is not None else None,
        "start_frame_quality": room.get("post_close_start_frame_quality"),
        "end_frame_quality": frame_quality,
        "contaminated": bool(room.get("post_close_contaminated")),
        "sample_count": len(room.get("post_close_samples") or []),
        "samples": list(room.get("post_close_samples") or []),
    }


def update_post_close_observation(
    room: dict[str, Any], *, now: datetime, absolute_humidity_g_m3: float | None,
    temperature_c: float | None, frame_quality: str | None,
    frame_valid: bool, window_open: bool, moisture_source_active: bool,
) -> tuple[dict[str, Any] | None, bool]:
    """Update a pending post-close observation.

    Returns (completed_outcome, changed). Reopening the room ends the observation
    as interrupted rather than accidentally treating a new ventilation session
    as hygroscopic rebound.
    """
    if not bool(room.get("post_close_active")):
        return None, False
    started = _dt(room.get("post_close_started_at"))
    if started is None:
        room["post_close_active"] = False
        return _outcome(room, now=now, current_ah=absolute_humidity_g_m3, current_temp_c=temperature_c,
                        status="invalid", reason="missing_start_timestamp", frame_quality=frame_quality), True
    elapsed = _elapsed_minutes(started, now)
    if moisture_source_active:
        room["post_close_contaminated"] = True
    if window_open:
        outcome = _outcome(room, now=now, current_ah=absolute_humidity_g_m3, current_temp_c=temperature_c,
                           status="interrupted", reason="window_reopened", frame_quality=frame_quality)
        room["post_close_active"] = False
        room["post_close_last_outcome"] = outcome
        return outcome, True

    changed = False
    if frame_valid and absolute_humidity_g_m3 is not None and temperature_c is not None:
        last_at = _dt(room.get("post_close_last_sample_at"))
        if last_at is None or (now - last_at).total_seconds() >= MIN_SAMPLE_SPACING_SECONDS:
            close_ah = _num(room.get("post_close_ah"), 0.0)
            volume = max(_num(room.get("post_close_volume_m3"), 0.0), 0.0)
            current_ah = _num(absolute_humidity_g_m3, close_ah)
            current_temp = _num(temperature_c, _num(room.get("post_close_temp_c"), 0.0))
            delta_ml = (current_ah - close_ah) * volume
            sample = {
                "elapsed_min": round(elapsed, 2),
                "captured_at": now.isoformat(),
                "absolute_humidity_g_m3": round(current_ah, 4),
                "temperature_c": round(current_temp, 3),
                "post_close_delta_ml": round(delta_ml, 1),
                "frame_quality": frame_quality,
            }
            samples = list(room.get("post_close_samples") or [])
            samples.append(sample)
            room["post_close_samples"] = samples[-MAX_SAMPLES:]
            room["post_close_last_sample_at"] = now.isoformat()
            changed = True

    if elapsed >= TARGET_MINUTES and len(room.get("post_close_samples") or []) >= 2:
        outcome = _outcome(room, now=now, current_ah=absolute_humidity_g_m3, current_temp_c=temperature_c,
                           status="complete", reason="target_window_reached", frame_quality=frame_quality)
        room["post_close_active"] = False
        room["post_close_last_outcome"] = outcome
        return outcome, True
    if elapsed >= MAX_MINUTES:
        outcome = _outcome(room, now=now, current_ah=absolute_humidity_g_m3, current_temp_c=temperature_c,
                           status="invalid", reason="insufficient_clean_samples", frame_quality=frame_quality)
        room["post_close_active"] = False
        room["post_close_last_outcome"] = outcome
        return outcome, True
    return None, changed


def prune_history(history: list[dict[str, Any]], now: datetime, days: int = 30) -> list[dict[str, Any]]:
    cutoff = now.timestamp() - max(days, 1) * 86400
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in history:
        if not isinstance(item, dict):
            continue
        event_id = str(item.get("event_id") or "")
        if not event_id or event_id in seen:
            continue
        completed = _dt(item.get("completed_at"))
        if completed is not None and completed.timestamp() < cutoff:
            continue
        seen.add(event_id)
        out.append(dict(item))
    return out[-500:]


def stabilization_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact 30-day summary for diagnostics/dashboard transport."""
    rows = [dict(x) for x in history if isinstance(x, dict)]
    valid = [x for x in rows if x.get("valid_for_analysis")]
    rebound = [_num(x.get("moisture_rebound_ml"), 0.0) for x in valid]
    fractions = [_num(x.get("buffer_fraction_percent"), 0.0) for x in valid if x.get("buffer_fraction_percent") is not None]
    rebound_cases = [x for x in valid if x.get("interpretation") == "moisture_rebound"]
    distinct_days = {str(x.get("completed_at") or x.get("started_at"))[:10] for x in valid if (x.get("completed_at") or x.get("started_at"))}
    return {
        "engine": "post_close_v1",
        "observations": len(rows),
        "valid_observations": len(valid),
        "distinct_observation_days": len(distinct_days),
        "invalid_or_interrupted": len(rows) - len(valid),
        "rebound_cases": len(rebound_cases),
        "average_rebound_ml": round(sum(rebound) / len(rebound), 1) if rebound else None,
        "average_buffer_fraction_percent": round(sum(fractions) / len(fractions), 1) if fractions else None,
        "rooms_with_valid_observations": len({str(x.get("key")) for x in valid if x.get("key")}),
    }
