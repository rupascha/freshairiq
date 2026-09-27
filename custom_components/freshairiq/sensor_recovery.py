"""Pure sensor-recovery state machine for transient source outages."""
from __future__ import annotations

from datetime import datetime


def advance_sensor_recovery(
    started_at: datetime | None,
    valid_cycles: int,
    *,
    required_unavailable: bool,
    now: datetime,
    grace_seconds: int = 90,
    required_valid_cycles: int = 2,
) -> tuple[datetime | None, int, bool]:
    """Advance recovery state and return (started_at, valid_cycles, grace_active).

    A missing required climate source starts a grace window. Persistent loss
    leaves grace after ``grace_seconds`` so the caller can surface a real
    sensor error. Once all required sources return, normal decisions resume
    only after the configured number of consecutive valid cycles.
    """
    if required_unavailable:
        if started_at is None:
            started_at = now
        valid_cycles = 0
    elif started_at is not None:
        valid_cycles += 1

    recovery_age = (now - started_at).total_seconds() if started_at is not None else 0.0
    grace_active = bool(
        started_at is not None
        and (
            (required_unavailable and recovery_age < grace_seconds)
            or (not required_unavailable and valid_cycles < required_valid_cycles)
        )
    )

    if (
        started_at is not None
        and not required_unavailable
        and valid_cycles >= required_valid_cycles
    ):
        started_at = None
        valid_cycles = 0
        grace_active = False

    return started_at, valid_cycles, grace_active
