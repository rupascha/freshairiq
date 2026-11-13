"""Behaviour learning that adapts reminders (0.26.7.0, owner order point 4). Pure logic.

FreshAirIQ counts, per room, the recommendation episodes somebody could have acted on (not everybody away, not carried
out by its own automation) and how many were followed, plus the usual reaction delay (``intelligence.py``). With
enough evidence the *reminders* of a still-open action are adapted – conservatively:

* timing: the first reminder is not sent before the household usually reacts anyway (average reaction delay);
* frequency / repetition: where reminders are mostly not acted on, the interval doubles (at most 60 min) and an
  action is reminded at most twice – no reminder loop;
* summarising: reminders due for several such rooms in the same cycle are sent as one message.

Never adapted: the first message of an action (the physical recommendation), protection closes (``hard_close``),
critical CO₂, critical surface humidity / mould messages – and the dashboard shows every action unchanged. Below the
minimum evidence, with inconsistent counters, with reminders switched off or with personalisation switched off,
nothing changes. Every room carries the decision and its reason for diagnostics (traceable).
"""
from __future__ import annotations

import math
from typing import Any

ADAPTATION_VERSION = 1
MIN_ACTIONABLE_SAMPLES = 12
MIN_DELAY_SAMPLES = 6
LOW_FOLLOW_RATE_PCT = 30.0
IGNORED_STREAK = 6
MAX_INTERVAL_MIN = 60.0
MAX_ADAPTED_REMINDERS = 2

REASON_DISABLED = "Personalisierung ausgeschaltet"
REASON_NO_REMINDERS = "Erinnerungen ausgeschaltet"
REASON_PROTECTED = "Schutzmeldung – nie angepasst"
REASON_NO_CONTACT = "Ohne Fenster-/Türkontakt ist das Umsetzen nicht messbar – unverändert"
REASON_INCONSISTENT = "Verhaltenszähler unplausibel – nicht verwendet"
REASON_FEW_SAMPLES = "Noch zu wenige Empfehlungen mit Handlungsmöglichkeit"
REASON_UNCHANGED = "Verhalten passt zu den Erinnerungen – unverändert"
REASON_LATER = "Erinnerung später: der Haushalt reagiert meist erst nach dieser Zeit"
REASON_FEWER = "Erinnerungen seltener und höchstens zweimal: sie werden meist nicht umgesetzt"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _count(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number == int(number) else None


def protected(room: dict[str, Any], options: dict[str, Any]) -> bool:
    """A reminder of this room is protection and is never adapted."""
    if bool((room.get("goal_state") or {}).get("hard_close")) if isinstance(room.get("goal_state"), dict) else False:
        return True
    co2 = _number(room.get("co2"))
    critical = _number(options.get("co2_critical")) or 1400.0
    if co2 is not None and co2 >= critical and room.get("co2_available", True):
        return True
    surface = _number(room.get("surface_rh"))
    if surface is not None and surface >= (_number(options.get("mould_critical_surface_rh")) or 90.0):
        return True
    return str(room.get("mould_level") or "") in {"High", "Very high"}


def notification_adaptation(room: dict[str, Any], options: dict[str, Any], base_interval_min: float | None) -> dict[str, Any]:
    """How the reminders of this room are adapted, with the evidence and the reason."""
    actionable = _count(room.get("behaviour_actionable"))
    followed = _count(room.get("behaviour_actionable_followed"))
    streak = _count(room.get("behaviour_ignored_streak")) or 0
    delay = _number(room.get("behaviour_avg_follow_delay_min"))
    delay_samples = _count(room.get("behaviour_follow_delay_samples")) or 0
    out: dict[str, Any] = {
        "version": ADAPTATION_VERSION, "active": False, "reason": REASON_UNCHANGED,
        "samples": actionable or 0, "min_samples": MIN_ACTIONABLE_SAMPLES,
        "follow_rate_pct": None, "ignored_streak": streak,
        "base_reminder_interval_min": base_interval_min, "reminder_interval_min": base_interval_min,
        "max_reminders": None, "summarize": False,
    }
    if not bool(options.get("personalisation_enabled", True)):
        out["reason"] = REASON_DISABLED
        return out
    if base_interval_min is None:
        out["reason"] = REASON_NO_REMINDERS
        return out
    if protected(room, options):
        out["reason"] = REASON_PROTECTED
        return out
    if "contact_count" in room and (_count(room.get("contact_count")) or 0) == 0:
        out["reason"] = REASON_NO_CONTACT   # nothing could be seen as "followed": no evidence of ignoring either
        return out
    if actionable is None or followed is None or followed > actionable:
        out["reason"] = REASON_INCONSISTENT
        return out
    if actionable < MIN_ACTIONABLE_SAMPLES:
        out["reason"] = REASON_FEW_SAMPLES
        return out
    rate = round(100.0 * followed / actionable, 1)
    out["follow_rate_pct"] = rate
    interval = float(base_interval_min)
    reasons = []
    if delay is not None and delay > 0 and delay_samples >= MIN_DELAY_SAMPLES and delay * 1.25 > interval:
        interval = min(delay * 1.25, MAX_INTERVAL_MIN)
        reasons.append(REASON_LATER)
    if rate < LOW_FOLLOW_RATE_PCT or streak >= IGNORED_STREAK:
        interval = min(max(interval, float(base_interval_min) * 2.0), MAX_INTERVAL_MIN)
        out["max_reminders"] = MAX_ADAPTED_REMINDERS
        out["summarize"] = True
        reasons.append(REASON_FEWER)
    out["reminder_interval_min"] = round(interval, 1)
    out["active"] = bool(reasons) and (interval != float(base_interval_min) or out["max_reminders"] is not None)
    out["reason"] = " · ".join(reasons) if out["active"] else REASON_UNCHANGED
    return out
