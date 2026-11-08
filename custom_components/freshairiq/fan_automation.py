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
# 0.26.5.5: "shared" – the fan runs for another room's control (FreshAirIQ switches it, not the user);
# "external" – another automation (Alexa, washing machine …) controls it: no request to the user either.
# 0.26.5.5: "blocked_time" – the room's lock period: FreshAirIQ keeps the fan off on purpose, no request either way.
AUTO_STOP_STATES = frozenset({"stopping", "follow_up", "source", "completed", "shared", "external", "blocked_time"})
AUTO_START_STATES = frozenset({"recommended", "requested", "running", "waiting", "partial", "shared", "external", "blocked_time"})

_LABELS = {
    "recommended": "Automatische Lüftung empfohlen – Ablüfter wird automatisch eingeschaltet",
    "requested": "Ablüfter wird automatisch eingeschaltet",
    "running": "Automatische Lüftung läuft",
    "waiting": "Automatische Lüftung startet nach der Pause",
    "stopping": "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung",
    # hotfix F3: the goal is reached, the switch-off is not sent yet (confirmation time)
    "stop_check": "Lüftungsziel erreicht – FreshAirIQ prüft kurz und schaltet die Lüftung dann aus",
    "source": "Ablüfter läuft wegen erkannter Feuchtequelle",
    "follow_up": "Feuchtequelle beendet – automatische Nachlaufzeit aktiv",
    "failed_on": "Ablüfter konnte nicht automatisch eingeschaltet werden – bitte von Hand einschalten",
    "partial": "Nicht alle Ablüfter sind angesprungen – bitte die übrigen prüfen",
    "failed_off": "Ablüfter konnte nicht automatisch ausgeschaltet werden – bitte von Hand ausschalten",
    "completed": "Automatische Lüftung abgeschlossen",
    "shared_for": "Gemeinsamer Ablüfter läuft für einen anderen Raum weiter – FreshAirIQ schaltet ihn danach aus",
    "shared_owner": "Gemeinsamer Ablüfter läuft – FreshAirIQ steuert ihn über einen anderen Raum",
    "external": "Ablüfter wird gerade von einer anderen Automation gesteuert – FreshAirIQ schaltet ihn nicht aus",
    "block_time": "Ablüfter wegen eingestellter Sperrzeit ausgeschaltet",
    # 0.26.7.0: the global automation lock (e.g. holidays)
    "automation_lock": "Automationssperre aktiv – FreshAirIQ schaltet den Ablüfter nicht automatisch",
    "automation_lock_off": "Automationssperre aktiv – FreshAirIQ beendet nur noch die eigene Lüftung",
}
COMPLETED_LABEL = _LABELS["completed"]
_LABELS_EN = {
    "recommended": "Automatic airing recommended – the exhaust fan is switched on automatically",
    "requested": "The exhaust fan is being switched on automatically",
    "running": "Automatic airing is running",
    "waiting": "Automatic airing starts after the pause",
    "stopping": "Airing goal reached – FreshAirIQ ends the airing",
    "stop_check": "Airing goal reached – FreshAirIQ checks briefly and then ends the airing",
    "source": "Exhaust fan runs because of a detected moisture source",
    "follow_up": "Moisture source ended – automatic follow-up time running",
    "failed_on": "The exhaust fan could not be switched on automatically – please switch it on by hand",
    "partial": "Not every exhaust fan came on – please check the others",
    "failed_off": "The exhaust fan could not be switched off automatically – please switch it off by hand",
    "completed": "Automatic airing finished",
    "shared_for": "Shared exhaust fan keeps running for another room – FreshAirIQ switches it off afterwards",
    "shared_owner": "Shared exhaust fan running – FreshAirIQ controls it through another room",
    "external": "The exhaust fan is controlled by another automation right now – FreshAirIQ does not switch it off",
    "block_time": "Exhaust fan switched off because of the set lock period",
    "automation_lock": "Automation lock active – FreshAirIQ does not switch the exhaust fan automatically",
    "automation_lock_off": "Automation lock active – FreshAirIQ only ends its own airing",
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
        # 0.26.5.5: fixed points in time for a real countdown – only while the follow-up runs
        "follow_up_until": snap.get("follow_up_until") if fan_on and state in {"follow_up", "shared"} else None,
        "runtime_limit_at": snap.get("runtime_limit_at") if fan_on else None,
        **_group(snap),
    }


def _group(snap: dict[str, Any]) -> dict[str, Any]:
    """Audit P1-05/P1-06: several fans, only some on – never shown as if all ran."""
    if "fans_total" not in snap:
        return {}
    total, on = int(snap["fans_total"]), int(snap.get("fans_on") or 0)
    return {"fans_total": total, "fans_on": on, "group_incomplete": 0 < on < total, "fans_unknown": int(snap.get("fans_unknown") or 0)}


def _state(mode, fan_on, owned, aligned, room, snap, command, command_state) -> tuple[str, str | None]:
    if snap.get("external_lock"):
        return "external", "external"
    if snap.get("automation_lock"):
        # 0.26.7.0: nothing automatic – the user decides; only FreshAirIQ's own switch-off may still be on its way
        if command == "off" and fan_on and command_state == "failed":
            return "failed", "failed_off"
        if command == "off" and fan_on and command_state == "pending":
            return "stopping", "automation_lock_off"
        return "locked", "automation_lock"
    # 0.26.5.5: lock period – off (or FreshAirIQ's own switch-off on its way); a fan switched on by hand stays the user's
    if snap.get("block_time") and fan_on and command == "off" and command_state == "failed":
        return "failed", "failed_off"  # hotfix 0.26.6.0: the switch-off at the lock period did not arrive – never "stopping"
    if snap.get("block_time") and (not fan_on or command == "off"):
        return ("blocked_time" if not fan_on else "stopping"), "block_time"
    failed = snap.get("own_off") == "failed" or (command_state == "failed" and ((command == "on" and not fan_on) or (command == "off" and fan_on)))
    shared = None if failed else _shared_state(fan_on, owned, aligned, room, snap)
    return shared if shared is not None else _own_state(mode, fan_on, owned, aligned, room, snap, command, command_state)


def _shared_state(fan_on, owned, aligned, room, snap) -> tuple[str, str] | None:
    """0.26.5.5 (community diagnosis): a fan several rooms share has one owner – the other rooms
    show it as FreshAirIQ's, never as switched on by hand ("manual" asked the user to act)."""
    if not fan_on:
        return None
    if not owned and snap.get("shared_owner"):
        return "shared", "shared_owner"
    if owned and snap.get("shared_for") and aligned not in FAN_ON_RECOMMENDATIONS and not room.get("moisture_source_active"):
        return "shared", "shared_for"
    return None


def _own_state(mode, fan_on, owned, aligned, room, snap, command, command_state) -> tuple[str, str | None]:
    if snap.get("own_off") == "failed":
        return "failed", "failed_off"  # audit N01: the room's own fan did not go off (a shared one runs on)
    if command_state == "failed" and ((command == "on" and not fan_on) or (command == "off" and fan_on)):
        return "failed", f"failed_{command}"
    if command == "on" and command_state == "pending" and owned:
        return "requested", "requested"
    if command == "off" and not fan_on and command_state != "confirmed" and int(snap.get("fans_unknown") or 0):
        # hotfix F3: the others are off, but a fan without a state is not – never "completed"
        return ("failed", "failed_off") if command_state == "failed" else ("stopping", "stopping")
    if command == "off" and command_state == "pending" and fan_on:
        # 0.26.5.4 (review A02): FreshAirIQ's own switch-off, not yet reported by the device – not "manual"
        return "stopping", "stopping"
    if fan_on and owned:
        if mode == "moisture_source":
            running = ("source", "source") if room.get("moisture_source_active") else ("follow_up", "follow_up")
        else:
            # hotfix F3: no switch-off sent yet (it waits for its confirmation) – "stop_check", not "stopping"
            running = ("running", "running") if aligned in FAN_ON_RECOMMENDATIONS else ("stopping", "stop_check")
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
