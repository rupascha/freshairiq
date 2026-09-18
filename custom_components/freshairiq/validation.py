"""Cross-field validation for FreshAirIQ configuration options."""
from __future__ import annotations

from typing import Any


RELATION_MESSAGES_DE = {
    "invalid_humidity_order": "Die Feuchtewerte müssen logisch aufeinander folgen: Zielwert ≤ Lüftungsstartwert ≤ hohe Luftfeuchte.",
    "invalid_delta_order": "Die Feuchtedifferenzen sind widersprüchlich: Schließ-Differenz ≤ Mindestdifferenz bei hoher Feuchte ≤ normale Mindestdifferenz.",
    "invalid_duration_order": "Die Mindestdauer darf nicht größer als die Maximaldauer sein.",
    "invalid_mould_order": "Die Schimmelwarnschwelle muss niedriger als die kritische Schimmelschwelle sein.",
    "invalid_co2_order": "Die CO₂-Warnschwelle muss niedriger als die kritische CO₂-Schwelle sein.",
}


def _number(options: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(options.get(key, default))
    except (TypeError, ValueError):
        return default


def option_relationship_error(options: dict[str, Any]) -> str | None:
    """Return the first violated cross-field invariant, if any."""
    target = _number(options, "target_rh", 58.0)
    start = _number(options, "start_rh", 62.0)
    high = _number(options, "high_rh", 68.0)
    if not target <= start <= high:
        return "invalid_humidity_order"

    close_delta = _number(options, "close_delta", 0.4)
    high_delta = _number(options, "min_delta_high_rh", 1.5)
    normal_delta = _number(options, "min_delta", 2.5)
    if not close_delta <= high_delta <= normal_delta:
        return "invalid_delta_order"

    minimum = _number(options, "min_duration_min", 3.0)
    maximum = _number(options, "max_duration_min", 20.0)
    if minimum > maximum:
        return "invalid_duration_order"

    mould_warn = _number(options, "mould_warn_surface_rh", 80.0)
    mould_critical = _number(options, "mould_critical_surface_rh", 90.0)
    if mould_warn >= mould_critical:
        return "invalid_mould_order"

    co2_warn = _number(options, "co2_warn", 1000.0)
    co2_critical = _number(options, "co2_critical", 1400.0)
    if co2_warn >= co2_critical:
        return "invalid_co2_order"

    return None


def option_relationship_message_de(options: dict[str, Any]) -> str | None:
    """Return a German user-facing explanation for a violated invariant."""
    code = option_relationship_error(options)
    return RELATION_MESSAGES_DE.get(code) if code else None

RELATION_OPTION_KEYS = {
    "target_rh", "start_rh", "high_rh",
    "close_delta", "min_delta_high_rh", "min_delta",
    "min_duration_min", "max_duration_min",
    "mould_warn_surface_rh", "mould_critical_surface_rh",
    "co2_warn", "co2_critical",
}


def repair_option_relationships(options: dict[str, Any]) -> dict[str, Any]:
    """Return a minimally repaired copy for legacy contradictory configurations.

    New writes are rejected instead of silently changed.  This repair exists only
    so configurations saved by older releases cannot start the runtime with
    impossible threshold ordering after an upgrade.
    """
    out = dict(options)

    target = _number(out, "target_rh", 58.0)
    start = _number(out, "start_rh", 62.0)
    high = _number(out, "high_rh", 68.0)
    if target > start:
        out["target_rh"] = start
        target = start
    if start > high:
        out["high_rh"] = start

    close_delta = _number(out, "close_delta", 0.4)
    high_delta = _number(out, "min_delta_high_rh", 1.5)
    normal_delta = _number(out, "min_delta", 2.5)
    if high_delta > normal_delta:
        out["min_delta_high_rh"] = normal_delta
        high_delta = normal_delta
    if close_delta > high_delta:
        out["close_delta"] = high_delta

    minimum = _number(out, "min_duration_min", 3.0)
    maximum = _number(out, "max_duration_min", 20.0)
    if minimum > maximum:
        out["max_duration_min"] = minimum

    mould_warn = _number(out, "mould_warn_surface_rh", 80.0)
    mould_critical = _number(out, "mould_critical_surface_rh", 90.0)
    if mould_warn >= mould_critical:
        out["mould_critical_surface_rh"] = min(100.0, mould_warn + 1.0)
        if _number(out, "mould_critical_surface_rh", 100.0) <= mould_warn:
            out["mould_warn_surface_rh"] = max(60.0, mould_critical - 1.0)

    co2_warn = _number(out, "co2_warn", 1000.0)
    co2_critical = _number(out, "co2_critical", 1400.0)
    if co2_warn >= co2_critical:
        out["co2_critical"] = min(4000.0, co2_warn + 50.0)
        if _number(out, "co2_critical", 4000.0) <= co2_warn:
            out["co2_warn"] = max(600.0, co2_critical - 50.0)

    return out
