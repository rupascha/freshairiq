"""Send cooldowns for explicit user submissions (0.26.4.10).

Feedback may be sent once every 15 minutes (spam protection); the dashboard
shows the remaining time. Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

FEEDBACK_COOLDOWN_SECONDS = 15 * 60


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None


def remaining_seconds(until: Any, now: datetime) -> int:
    """Whole seconds left until ``until`` (0 when over, unknown or unparsable)."""
    end = _parse(until)
    if end is None:
        return 0
    if now.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=now.tzinfo)
    elif now.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    left = (end - now).total_seconds()
    return max(1, int(left + 0.999)) if left > 0 else 0


def cooldown_result(seconds: int, now: datetime) -> dict[str, Any]:
    """Uniform "not now" answer for the dashboard."""
    seconds = max(int(seconds), 1)
    return {"accepted": False, "reason": "cooldown", "retry_after_seconds": seconds,
            "cooldown_until": (now + timedelta(seconds=seconds)).isoformat(),
            "cooldown_seconds": FEEDBACK_COOLDOWN_SECONDS}


def started_cooldown(now: datetime, seconds: int = FEEDBACK_COOLDOWN_SECONDS) -> str:
    return (now + timedelta(seconds=seconds)).isoformat()


def hub_retry_after(body: Any) -> int | None:
    """``retry_after_seconds`` of a Hub 429 answer (``{"detail": {...}}`` or flat)."""
    if not isinstance(body, dict):
        return None
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    try:
        value = int(detail.get("retry_after_seconds"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
