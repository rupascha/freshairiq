"""Home Assistant bus events for user automations (Node-RED, Alexa, scripts).

FreshAirIQ never switches devices by itself. These events let users build their
own reactions on a stable, documented contract instead of parsing dashboard
text: a fan that starts when a room should be aired, an Alexa announcement
"Bitte Schlafzimmerfenster schließen", a Node-RED flow, …

Contract (schema 1, see docs/AUTOMATIONEN.md):

* ``freshairiq_room_action``         a room's recommended action changed
* ``freshairiq_house_recommendation`` the whole-home recommendation changed
* ``freshairiq_mould_risk``          a room's mould risk level changed

Events are fired only on *changes*. The first cycle after a (re)start records
the current state silently, so restarts never replay old announcements.
Payloads contain room names chosen by the user and FreshAirIQ's own texts in
the Home Assistant language; they stay inside the local Home Assistant event
bus and are not part of the diagnostics upload.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

EVENT_ROOM_ACTION = "freshairiq_room_action"
EVENT_HOUSE_RECOMMENDATION = "freshairiq_house_recommendation"
EVENT_MOULD_RISK = "freshairiq_mould_risk"
EVENT_SCHEMA_VERSION = 1

# Machine-readable action codes: identical to the states of the room "Aktion"
# sensor (sensor.<room>_aktion), so events and entity triggers use one vocabulary.
ACTION_CODES = {
    "Ventilate": "ventilate",
    "Continue ventilating": "continue_ventilating",
    "Close": "close",
    "Ventilate for cooling": "ventilate_for_cooling",
    "Do not ventilate": "do_not_ventilate",
    "Wait": "wait",
    "Okay": "okay",
    "Check sensor": "check_sensor",
    "Monitor only": "monitor_only",
    "Open fully": "open_fully",
}
_LABELS = {
    "de": {
        "ventilate": "Bitte lüften", "continue_ventilating": "Weiterlüften", "close": "Bitte Fenster schließen",
        "ventilate_for_cooling": "Zum Kühlen lüften", "do_not_ventilate": "Bitte nicht lüften", "wait": "Noch warten",
        "okay": "Alles in Ordnung", "check_sensor": "Sensor prüfen", "monitor_only": "Nur Beobachtung",
        "open_fully": "Fenster ganz öffnen",
    },
    "en": {
        "ventilate": "Please air the room", "continue_ventilating": "Keep airing", "close": "Please close the window",
        "ventilate_for_cooling": "Air for cooling", "do_not_ventilate": "Please do not air", "wait": "Wait for now",
        "okay": "All good", "check_sensor": "Check sensor", "monitor_only": "Monitoring only",
        "open_fully": "Open the window fully",
    },
}
_MOULD_ORDER = {"Low": 0, "Elevated": 1, "High": 2, "Very high": 3}


def mould_code(level: Any) -> str | None:
    """Mould level as the room "Schimmelrisiko" sensor state (e.g. "very_high")."""
    if level in (None, ""):
        return None
    return str(level).strip().lower().replace(" ", "_")


def action_code(action: Any) -> str:
    text = str(action or "")
    return ACTION_CODES.get(text, text.strip().lower().replace(" ", "_") or "unknown")


def ventilation_measures_active(room: dict[str, Any]) -> bool:
    """True while something already works against the humidity in this room.

    Window/door session, a running exhaust fan, a detected moisture source such
    as a shower (and its recovery phase) or the post-close buffer observation.
    Mould warnings during such phases tell the user nothing actionable.
    """
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    return bool(
        room.get("active")
        or actuators.get("mechanical_exhaust_active")
        or room.get("moisture_source_active")
        or room.get("moisture_source_recovery")
        or room.get("post_close_stabilization_active")
    )


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _language(data: dict[str, Any]) -> str:
    return "en" if str(data.get("output_language") or "").lower() == "en" else "de"


def room_payload(room: dict[str, Any], *, previous_action: Any, language: str, entry_id: str) -> dict[str, Any]:
    code = action_code(room.get("action"))
    label = _LABELS[language].get(code, str(room.get("action") or ""))
    name = str(room.get("name") or room.get("key") or "")
    reasons = [str(x) for x in (room.get("recommendation_reasons") or []) if str(x).strip()][:4]
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "entry_id": entry_id,
        "room_key": str(room.get("key") or ""),
        "room_name": name,
        "floor": room.get("floor"),
        "action": code,
        "previous_action": action_code(previous_action) if previous_action is not None else None,
        # 0.26.4.7: the room action considering the whole-house decision
        # ("ventilate_later" while the house deliberately waits).
        "house_aligned_action": room.get("house_aligned_action"),
        "action_label": label,
        # Ready-to-speak sentence, e.g. "Schlafzimmer: Bitte Fenster schließen."
        "message": f"{name}: {label}.",
        "reasons": reasons,
        "humidity": _number(room.get("humidity")),
        "temperature": _number(room.get("temperature")),
        "potential_ml": _number(room.get("potential_ml")),
        "recommended_duration_min": _number(room.get("recommended_duration_min")),
        "mould_level": mould_code(room.get("mould_level")),
        "surface_rh": _number(room.get("surface_rh")),
        "ventilation_active": bool(room.get("active")),
        "ventilation_measures_active": ventilation_measures_active(room),
        "data_quality": room.get("data_quality"),
    }


def house_payload(iq: dict[str, Any], *, previous_kind: Any, data: dict[str, Any], entry_id: str) -> dict[str, Any]:
    reasons = [str(x) for x in (iq.get("reasons") or []) if str(x).strip()][:4]
    title = str(iq.get("title") or "")
    instruction = str(iq.get("instruction") or "")
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "entry_id": entry_id,
        "kind": str(iq.get("kind") or ""),
        "previous_kind": previous_kind,
        "status": str(iq.get("status") or data.get("status") or ""),
        "severity": iq.get("severity"),
        "title": title,
        "instruction": instruction,
        "summary": str(iq.get("summary") or ""),
        "message": " ".join(x for x in (title.rstrip(".") + "." if title else "", instruction) if x).strip(),
        "reasons": reasons,
        "room_keys": [str(x) for x in (iq.get("room_keys") or [])],
        "room_names": [str(x) for x in (iq.get("room_names") or [])],
        "duration_min": _number(iq.get("duration_min")),
        "estimated_removed_ml": _number(iq.get("estimated_removed_ml")),
        "night_strategy": bool(iq.get("night_strategy_primary")),
    }


class AutomationEventEmitter:
    """Detects changes between coordinator cycles and fires bus events."""

    def __init__(self, fire: Callable[[str, dict[str, Any]], None], entry_id: str) -> None:
        self._fire = fire
        self._entry_id = entry_id
        self._initialised = False
        self._room_actions: dict[str, Any] = {}
        self._room_mould: dict[str, Any] = {}
        self._house_signature: str | None = None
        self._house_kind: Any = None
        self._seen_rooms: set[str] = set()
        self.fired = 0

    def process(self, data: dict[str, Any]) -> int:
        """Fire events for changes in ``data``; return how many were fired."""
        rooms_raw = data.get("rooms") if isinstance(data.get("rooms"), dict) else {}
        language = _language(data)
        fired = 0
        initial = not self._initialised
        for key, room in rooms_raw.items():
            if not isinstance(room, dict):
                continue
            key = str(key)
            action = room.get("action")
            previous = self._room_actions.get(key)
            self._room_actions[key] = action
            if not initial and key in self._seen_rooms and action != previous:
                self._fire(EVENT_ROOM_ACTION, room_payload(room, previous_action=previous, language=language, entry_id=self._entry_id))
                fired += 1
            level = room.get("mould_level")
            previous_level = self._room_mould.get(key)
            self._room_mould[key] = level
            if not initial and previous_level is not None and level != previous_level:
                payload = room_payload(room, previous_action=previous, language=language, entry_id=self._entry_id)
                payload.update({
                    "mould_level": mould_code(level),
                    "previous_mould_level": mould_code(previous_level),
                    "rising": _MOULD_ORDER.get(str(level), 0) > _MOULD_ORDER.get(str(previous_level), 0),
                })
                self._fire(EVENT_MOULD_RISK, payload)
                fired += 1
        self._seen_rooms = set(self._room_actions)

        iq = data.get("intelligent_recommendation") if isinstance(data.get("intelligent_recommendation"), dict) else {}
        signature = "|".join([str(iq.get("kind") or ""), ",".join(str(x) for x in (iq.get("room_keys") or [])), str(iq.get("instruction") or "")])
        if not initial and iq and signature != self._house_signature:
            self._fire(EVENT_HOUSE_RECOMMENDATION, house_payload(iq, previous_kind=self._house_kind, data=data, entry_id=self._entry_id))
            fired += 1
        self._house_signature = signature
        self._house_kind = iq.get("kind") if iq else None
        self._initialised = True
        self.fired += fired
        return fired
