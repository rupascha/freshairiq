"""What the automatic exhaust-fan control is doing in a room (pure, 0.26.5.4).

With the automatic fan control on, FreshAirIQ switches the fan itself – a
message "Lüfter ausschalten" then asks the user for something FreshAirIQ is
already doing. This module keeps apart

* the recommendation (``house_aligned_action``),
* the configured mode (``exhaust_fan_control``),
* the device state Home Assistant reports (``mechanical_exhaust_active``),
* whether FreshAirIQ switched the fan on and still controls it (``owned``),
* the last command and whether Home Assistant confirmed it (pending /
  confirmed / failed),

and derives one ``state`` plus whether the user has to act. A fan someone
switched on by hand is never treated as FreshAirIQ's (``manual``); a command
that was not carried out leaves the action to the user (``failed``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

FAN_ON_RECOMMENDATIONS = frozenset({"ventilate", "continue_ventilating", "ventilate_indirectly"})
# FreshAirIQ carries out the action itself: no manual instruction for these.
# "completed": FreshAirIQ switched the fan off itself (e.g. maximum runtime) -
# the close is already carried out, no "switch off the fan" for the user.
AUTO_STOP_STATES = frozenset({"stopping", "follow_up", "source", "completed"})
AUTO_START_STATES = frozenset({"recommended", "requested", "running", "waiting", "partial"})

_LABELS = {
    "recommended": "Automatische Lüftung empfohlen – Ablüfter wird automatisch eingeschaltet",
    "requested": "Ablüfter wird automatisch eingeschaltet",
    "running": "Automatische Lüftung läuft",
    "waiting": "Automatische Lüftung startet nach der Pause",
    "stopping": "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung",
    "source": "Ablüfter läuft wegen erkannter Feuchtequelle",
    "follow_up": "Feuchtequelle beendet – automatische Nachlaufzeit aktiv",
    "failed_on": "Ablüfter konnte nicht automatisch eingeschaltet werden – bitte von Hand einschalten",
    "partial": "Nicht alle Ablüfter sind angesprungen – bitte die übrigen prüfen",
    "failed_off": "Ablüfter konnte nicht automatisch ausgeschaltet werden – bitte von Hand ausschalten",
    "completed": "Automatische Lüftung abgeschlossen",
}
COMPLETED_LABEL = _LABELS["completed"]
_LABELS_EN = {
    "recommended": "Automatic airing recommended – the exhaust fan is switched on automatically",
    "requested": "The exhaust fan is being switched on automatically",
    "running": "Automatic airing is running",
    "waiting": "Automatic airing starts after the pause",
    "stopping": "Airing goal reached – FreshAirIQ ends the airing",
    "source": "Exhaust fan runs because of a detected moisture source",
    "follow_up": "Moisture source ended – automatic follow-up time running",
    "failed_on": "The exhaust fan could not be switched on automatically – please switch it on by hand",
    "partial": "Not every exhaust fan came on – please check the others",
    "failed_off": "The exhaust fan could not be switched off automatically – please switch it off by hand",
    "completed": "Automatic airing finished",
}


def fan_restart_lock_min(options: dict[str, Any]) -> float:
    """No automatic restart this soon after a finished automatic airing.

    The same anti-flap floor that keeps a room from being re-armed by a
    changed reference path right after closing (``coordinator_room_result``).
    """
    try:
        stabilization = float(options.get("post_ventilation_stabilization_min", 4.0))
        cooldown = float(options.get("repeat_recommendation_cooldown_min", 120.0))
    except (TypeError, ValueError):
        return 15.0
    return max(stabilization, min(15.0, cooldown))


def fan_trace_row(room_key: str, mode: str, mem: dict[str, Any], now: datetime) -> dict[str, Any]:
    """One privacy-safe row of the fan command trace (no entity IDs)."""
    return {
        "at": now.isoformat(), "room_key": room_key, "mode": mode, "command": mem.get("command"),
        "reason": mem.get("reason"), "result": mem.get("command_state"),
    }


def room_fan_automation(room: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """The room's ``fan_automation`` field, or None without an automatic fan control."""
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    mode = str(actuators.get("exhaust_fan_control") or "off")
    if mode == "off" or not actuators.get("exhaust_fan"):
        return None
    snap = snapshot if isinstance(snapshot, dict) else {}
    fan_on = bool(actuators.get("mechanical_exhaust_active"))
    aligned = str(room.get("house_aligned_action") or "")
    command, command_state = snap.get("command"), snap.get("command_state")
    owned = bool(snap.get("owned"))
    state, label_key = _state(mode, fan_on, owned, aligned, room, snap, command, command_state)
    return {
        "mode": mode,
        "state": state,
        "owned": owned,
        "blocked": bool(snap.get("blocked")),
        "command": command,
        "command_state": command_state,
        "command_at": snap.get("command_at"),
        "reason": snap.get("reason"),
        "off_pending_since": snap.get("off_pending_since"),
        "user_action_needed": state in {"failed", "manual", "manual_off", "partial"},
        "label": _LABELS.get(label_key) if label_key else None,
        "label_key": label_key,
        **_group(snap),
    }


def _group(snap: dict[str, Any]) -> dict[str, Any]:
    """Audit P1-05/P1-06: several fans, only some on – never shown as if all ran."""
    if "fans_total" not in snap:
        return {}
    total, on = int(snap["fans_total"]), int(snap.get("fans_on") or 0)
    return {"fans_total": total, "fans_on": on, "group_incomplete": 0 < on < total}


def _state(mode, fan_on, owned, aligned, room, snap, command, command_state) -> tuple[str, str | None]:
    if snap.get("own_off") == "failed":
        return "failed", "failed_off"  # audit N01: the room's own fan did not go off (a shared one runs on)
    if command_state == "failed" and ((command == "on" and not fan_on) or (command == "off" and fan_on)):
        return "failed", f"failed_{command}"
    if command == "on" and command_state == "pending" and owned:
        return "requested", "requested"
    if command == "off" and command_state == "pending" and fan_on:
        # 0.26.5.4 (review A02): FreshAirIQ's own switch-off, not yet reported by the device – not "manual"
        return "stopping", "stopping"
    if fan_on and owned:
        if mode == "moisture_source":
            running = ("source", "source") if room.get("moisture_source_active") else ("follow_up", "follow_up")
        else:
            running = ("running", "running") if aligned in FAN_ON_RECOMMENDATIONS else ("stopping", "stopping")
        if running[0] != "stopping" and command_state == "partial" and _group(snap).get("group_incomplete"):
            return "partial", "partial"  # audit S08: not every fan came on – never shown as "running"
        return running
    if fan_on:
        return "manual", None  # switched on by someone else: the user decides
    if mode != "recommendation" or aligned not in FAN_ON_RECOMMENDATIONS:
        # the fan is reported off after FreshAirIQ's own switch-off
        return ("completed" if command == "off" and command_state != "failed" else "idle"), None
    if bool((room.get("configured_actuators") or {}).get("window_open")):
        return "idle", None
    if snap.get("blocked"):
        return "manual_off", None  # switched off by hand: no automatic restart until the demand ends
    if snap.get("restart_locked") and not room.get("moisture_source_active"):
        return "waiting", "waiting"
    return "recommended", "recommended"


def fan_automation(room: Any) -> dict[str, Any]:
    value = room.get("fan_automation") if isinstance(room, dict) else None
    return value if isinstance(value, dict) else {}


def auto_stop(room: Any) -> bool:
    """FreshAirIQ stops this fan itself – no "switch off the fan" for the user."""
    return fan_automation(room).get("state") in AUTO_STOP_STATES


def auto_start(room: Any) -> bool:
    """FreshAirIQ starts (or runs) this fan itself – no "switch on the fan" for the user."""
    return fan_automation(room).get("state") in AUTO_START_STATES


def automation_label(room: Any) -> str | None:
    label = fan_automation(room).get("label")
    return str(label) if label else None


def handled_label(room: Any, code: str, language: str = "de") -> str | None:
    """The automation's own wording when it carries out ``code`` itself (else None)."""
    handled = (code == "close" and auto_stop(room)) or (code in FAN_ON_RECOMMENDATIONS and auto_start(room))
    value = fan_automation(room)
    # the room field keeps no label after the switch-off; only the close wording names it
    key = (value.get("label_key") or ("completed" if value.get("state") == "completed" else None)) if handled else None
    if not key:
        return None
    return (_LABELS_EN if language == "en" else _LABELS).get(str(key))


def automation_text(value: dict[str, Any], language: str = "de") -> str | None:
    """The fan control's own sentence for its current state (None without one)."""
    key = value.get("label_key") or ("completed" if value.get("state") == "completed" else None)
    return (_LABELS_EN if language == "en" else _LABELS).get(str(key)) if key else None


def event_fields(room: Any) -> dict[str, Any] | None:
    """Compact automation status for event payloads (additive, no entity IDs)."""
    value = fan_automation(room)
    if not value:
        return None
    return {key: value.get(key) for key in ("mode", "state", "owned", "command", "command_state", "user_action_needed")}
