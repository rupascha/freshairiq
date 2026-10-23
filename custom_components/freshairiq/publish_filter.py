"""How finely a sensor state is published (pure, 0.26.5.3).

Community (recorder load): every published state change is a recorder row.
Some values move with the clock or flicker between neighbouring values without
anything happening in the room (the overnight forecast counts down the night,
today's moisture balance grows minute by minute, the forecast temperature change
jumps between two tenths). Their sensors publish in meaningful steps instead;
calculations, the dashboard and the events keep the full precision.
"""
from __future__ import annotations

from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def quantized(value: Any, step: float) -> Any:
    """``value`` rounded to ``step`` (e.g. 10 mL); non-numbers pass unchanged."""
    number = _number(value)
    if number is None:
        return value
    out = round(number / step) * step
    return int(out) if float(step).is_integer() else round(out, 6)


def with_deadband(previous: Any, value: Any, band: float) -> Any:
    """Keep ``previous`` while ``value`` stays within ``band`` of it.

    A change to or from zero is always published (a forecast starts or ends),
    as is anything that is not a number.
    """
    new, old = _number(value), _number(previous)
    if new is None or old is None or new == 0 or old == 0:
        return value
    return previous if round(abs(new - old), 6) < band else value
