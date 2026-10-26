"""Start model: better starting exchange rates for rooms that have not learned yet (pure, 0.26.5.4).

The learning moves a room's exchange rate by at most 15 % per airing
(``model.update_learning``), so the starting value decides how many airings a
new room needs until its forecasts fit. The built-in starting values are
physical guesses (0.03/min for an open window, 0.015 tilted, 0.04 cross
ventilation, 0.02 exhaust fan).

The diagnostics hub derives a start model from the measured exchange rates of
real airings in other homes and checks it against installations it has not
seen (``freshairiq_hub.start_model``). Only values the hub recommends are
taken over into ``start_model_data.START_MODEL`` with a release
(``tools/apply_start_model.py``) – nothing is downloaded at runtime.

A start model only sets the starting value of a room (or of one way of airing)
that has no learning sample yet. As soon as the room learns, its own values
take over. Without a start model nothing changes.

This module also measures the exchange rate of every finished airing with the
same formula and validity rules as the learning, so the hub can build the
start model from it (``learning_observation`` in the session record).
"""
from __future__ import annotations

from typing import Any

FORMAT = "freshairiq-start-model"
FORMAT_VERSION = 1
# built-in starting values (storage_defaults / coordinator_sessions)
DEFAULT_RATES = {"open": 0.03, "tilted": 0.015, "cross": 0.04, "mechanical_exhaust": 0.02}
MIN_RATE, MAX_RATE = 0.002, 0.25
# room size buckets (m³), shared with the hub
SIZE_BUCKETS = ((15.0, "<15"), (30.0, "15-30"), (60.0, "30-60"), (float("inf"), ">=60"))
ALL_SIZES = "all"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def size_bucket(volume_m3: Any) -> str | None:
    volume = _number(volume_m3)
    if volume is None or volume <= 0:
        return None
    return next(label for limit, label in SIZE_BUCKETS if volume < limit)


def observed_exchange_rate(*, start_ah: Any, end_ah: Any, source_ah: Any, elapsed_min: Any, max_duration_min: Any = 120.0) -> float | None:
    """Measured exchange rate of one airing, with the validity rules of ``update_learning``."""
    start, end, source, elapsed = _number(start_ah), _number(end_ah), _number(source_ah), _number(elapsed_min)
    limit = _number(max_duration_min) or 120.0
    if None in (start, end, source, elapsed) or elapsed < 2 or elapsed > limit:
        return None
    start_delta, reduction = start - source, start - end
    if start_delta <= 0.5 or reduction <= 0.05:
        return None
    raw = reduction / start_delta / elapsed
    return round(raw, 5) if MIN_RATE <= raw <= MAX_RATE else None


def learning_observation(
    *, start_ah: Any, end_ah: Any, source_ah: Any, elapsed_min: Any, max_duration_min: Any, rate_before: Any, samples_before: Any, usable: bool,
) -> dict[str, Any]:
    """What one airing showed about the room's exchange rate (session record, no entity IDs)."""
    def rounded(value: Any, digits: int) -> float | None:
        number = _number(value)
        return None if number is None else round(number, digits)

    return {
        "observed_rate_per_min": observed_exchange_rate(start_ah=start_ah, end_ah=end_ah, source_ah=source_ah,
                                                         elapsed_min=elapsed_min, max_duration_min=max_duration_min) if usable else None,
        "usable": bool(usable),
        "start_ah": rounded(start_ah, 3), "end_ah": rounded(end_ah, 3), "source_ah": rounded(source_ah, 3),
        "elapsed_min": rounded(elapsed_min, 2), "rate_before": rounded(rate_before, 5),
        "samples_before": int(_number(samples_before) or 0),
    }


def validate(model: Any) -> dict[str, Any]:
    """A clean start model; anything malformed is dropped (an empty model changes nothing)."""
    if not isinstance(model, dict) or model.get("format") != FORMAT or model.get("format_version") != FORMAT_VERSION:
        return {"format": FORMAT, "format_version": FORMAT_VERSION, "version": None, "cells": []}
    cells = []
    for cell in model.get("cells") if isinstance(model.get("cells"), list) else []:
        rate = _number(cell.get("rate_per_min")) if isinstance(cell, dict) else None
        if rate is None or not MIN_RATE <= rate <= MAX_RATE:
            continue
        if cell.get("mode") not in DEFAULT_RATES or cell.get("size") not in {label for _l, label in SIZE_BUCKETS} | {ALL_SIZES}:
            continue
        cells.append({"mode": cell["mode"], "size": cell["size"], "rate_per_min": round(rate, 5)})
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "version": str(model.get("version") or "") or None, "cells": cells}


def start_rate(model: dict[str, Any], mode: str, volume_m3: Any) -> float | None:
    """The start model's rate for a way of airing and room size (size cell first, then all sizes)."""
    size = size_bucket(volume_m3)
    rates = {(c["mode"], c["size"]): c["rate_per_min"] for c in model.get("cells") or []}
    return rates.get((mode, size)) if (mode, size) in rates else rates.get((mode, ALL_SIZES))


def seed_room(mem: dict[str, Any], model: dict[str, Any], volume_m3: Any) -> bool:
    """Set the starting rates of a room that has not learned yet; returns whether ``mem`` changed.

    Only values still at their start (no learning sample) are touched, so a
    learned value is never overwritten. A start model that is removed again
    returns such values to the built-in defaults.
    """
    seeded = mem.get("start_model") if isinstance(mem.get("start_model"), dict) else {}
    applied: dict[str, float] = {}
    changed = False

    def apply(mode: str, current: Any, samples: Any) -> float | None:
        if int(_number(samples) or 0) > 0:
            return None
        rate = start_rate(model, mode, volume_m3)
        target = rate if rate is not None else DEFAULT_RATES[mode]
        untouched = _number(current) in (None, DEFAULT_RATES[mode], (seeded.get("rates") or {}).get(mode))
        if not untouched:
            return None  # set elsewhere (e.g. migrated): keep it
        if rate is not None:
            applied[mode] = rate
        return target

    general = apply("open", mem.get("learning_rate"), mem.get("learning_samples"))
    if general is not None and _number(mem.get("learning_rate")) != general:
        mem["learning_rate"] = general
        changed = True
    rows = mem.get("opening_learning") if isinstance(mem.get("opening_learning"), dict) else None
    for mode in ("open", "tilted", "cross", "mechanical_exhaust"):
        if rows is None:
            break
        row = rows.get(mode) if isinstance(rows.get(mode), dict) else None
        if row is None:
            if start_rate(model, mode, volume_m3) is None:
                continue
            # e.g. the exhaust-fan model exists only after its first airing
            row = rows[mode] = {"rate": DEFAULT_RATES[mode], "samples": 0, "credit": 0.0}
            changed = True
        target = apply(mode, row.get("rate"), row.get("samples"))
        if target is not None and _number(row.get("rate")) != target:
            row["rate"] = target
            changed = True
    record = {"version": model.get("version"), "rates": applied} if applied else None
    if record != (seeded or None):
        if record is None:
            mem.pop("start_model", None)
        else:
            mem["start_model"] = record
        changed = True
    return changed
