"""Title and plain text of room and house messages (pure, 0.26.5.5 notification hotfix).

F1  The title names the effective action ("FreshAirIQ · Wohnzimmer · Jetzt lüften"); a reminder is
    marked as one. A status (FreshAirIQ switches the fan itself) names no task, and a close aired by
    the fan alone asks to switch the fan off, never to close a window.
F2  The body is plain text in a fixed order: the recommendation, then "Warum:" with at most three
    reasons, then details where there are any. A room's own reasons are only used while its own
    action is the action of the message: a house-aligned action never borrows the reasons of a
    contradicting room action.
"""
from __future__ import annotations

import math
from typing import Any

from .close_wording import fan_only
from .fan_automation import auto_start, fan_automation, handled_label
from .language_confidence import room_notification_message

ACTION_TITLES = {"ventilate": "Jetzt lüften", "close": "Jetzt schließen", "cool": "Kühlen"}
FAN_OFF_TITLE = "Lüfter ausschalten"
# the fan control asks for a hand (audit S08): the title names that task
_FAN_TASK_TITLES = {"failed_on": "Lüfter einschalten", "partial": "Lüfter prüfen", "failed_off": FAN_OFF_TITLE}
AUTO_HOUSE_TITLE = "Automatische Lüftung"
REASONS_HEADING = "Warum:"
BULLET = "• "
MAX_REASONS = 3
_RAW_ACTION = {"ventilate": "Ventilate", "cool": "Ventilate for cooling", "close": "Close"}
_EVENT_OF_ACTION = {"Ventilate": "ventilate", "Ventilate for cooling": "cool", "Close": "close"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def room_title(event: str, room: dict[str, Any], *, reminder: bool = False) -> str:
    """``FreshAirIQ · <Raum> · <Aktion>`` for a task, ``FreshAirIQ · <Raum>`` for anything else."""
    name = room.get("name") or room.get("key")
    action = ACTION_TITLES.get(event)
    if event in {"ventilate", "close"} and handled_label(room, event) and fan_automation(room).get("user_action_needed"):
        action = _FAN_TASK_TITLES.get(str(fan_automation(room).get("label_key")), action)
    elif event == "close" and fan_only(room):
        action = FAN_OFF_TITLE
    if not action:
        return f"FreshAirIQ · {name}"
    return f"FreshAirIQ · {name} · Erinnerung: {action}" if reminder else f"FreshAirIQ · {name} · {action}"


def message_body(recommendation: str, reasons: Any = (), details: Any = ()) -> str:
    """Recommendation, then "Warum:" with at most three reasons, then the details (one per line)."""
    lines = [str(recommendation or "").strip()]
    picked = [str(r).strip() for r in (reasons or []) if str(r or "").strip()][:MAX_REASONS]
    if picked:
        lines += [REASONS_HEADING, *(BULLET + reason for reason in picked)]
    lines += [str(detail or "").strip() for detail in details]
    return "\n".join(line for line in lines if line)


def room_reasons(event: str, room: dict[str, Any]) -> list[Any]:
    """The room's reasons – only while the room's own action is the action of the message."""
    return list(room.get("recommendation_reasons") or []) if room.get("action") == _RAW_ACTION.get(event) else []


def speech_text(message: str) -> str:
    """One readable line for voice output: bullets become sentences."""
    sentences = []
    for raw in str(message or "").split("\n"):
        line = raw.strip().removeprefix(BULLET.strip()).strip()
        if line:
            sentences.append(line if line[-1] in ".!?:" else f"{line}.")
    return " ".join(sentences)


def continuation(room: dict[str, Any]) -> str:
    """User-facing forecast using the configured horizon, never the internal 5-min gate."""
    horizon = max(int(round(_number(room.get("forecast_horizon_min", 5), 5.0))), 1)
    effect = _number(room.get("forecast_moisture_effect_ml", room.get("forecast_5_min_moisture_effect_ml", 0)))
    dt = _number(room.get("forecast_temperature_change_c", room.get("forecast_5_min_temperature_change_c", 0)))
    cost = max(_number(room.get("forecast_cost", room.get("next_5_min_cost", 0))), 0.0)
    moisture = f"−{round(abs(effect))} ml" if effect > 0 else f"+{round(abs(effect))} ml" if effect < 0 else "±0 ml"
    sign = "+" if dt > 0 else "−" if dt < 0 else "±"
    temp = f"{sign}{abs(dt):.1f} °C" if dt else "±0.0 °C"
    return f"Weitere {horizon} Min: {moisture} · Temperatur {temp} · Energiekosten ca. {cost:.2f} €"


def fan_hint(room: dict[str, Any]) -> str:
    """0.26.4.9: rooms with an exhaust fan can also be aired by the fan."""
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    if not actuators.get("exhaust_fan") or actuators.get("mechanical_exhaust_active") or auto_start(room):
        return ""  # 0.26.5.4: not while FreshAirIQ switches the fan itself
    return " Alternativ den Lüfter einschalten."


def auto_room_event(event: str, room: dict[str, Any], message: str) -> tuple[str, str, str]:
    """0.26.5.4: event, title and text of a room message.

    When FreshAirIQ switches the room's fan itself, the message is a status
    ("fan_auto") with the automation's wording instead of a task for the user.
    """
    label = handled_label(room, "close" if event == "close" else "ventilate")
    if label and fan_automation(room).get("user_action_needed"):
        return event, room_title(event, room), f"{label}."  # audit S08: e.g. not every fan came on – a task, not a status
    return ("fan_auto", room_title("fan_auto", room), f"{label}.") if label else (event, room_title(event, room), message)


def action_message(action: Any, room: dict[str, Any], store_data: dict[str, Any]) -> tuple[str, str, str]:
    """Event, title and body of the first message of a room action (also used to retry its push)."""
    event = _EVENT_OF_ACTION[action]
    text = room_notification_message(event, room, store_data)
    if event == "ventilate":
        return auto_room_event(event, room, message_body(f"{text}{fan_hint(room)}", room_reasons(event, room)))
    body = message_body(text, room_reasons(event, room), [continuation(room)])
    return (event, room_title(event, room), body) if event == "cool" else auto_room_event(event, room, body)


def room_messages(events: dict[str, list[dict[str, Any]]], store: Any, options: dict[str, Any], room_push: bool, *, sensor_recovery: bool) -> list[dict[str, Any]]:
    """Every room message of this cycle in send order (events are published, pushes per option)."""
    data = store.data
    wanted = {"ventilate": "notify_ventilate", "cool": "notify_cooling", "close": "notify_close", "fan_auto": "notify_close"}
    out: list[dict[str, Any]] = []

    def add(event: str, title: str, message: str, room: dict[str, Any], option: str, **extra: Any) -> None:
        out.append({"event": event, "title": title, "message": message, "room_key": room["key"],
                    "push": room_push and bool(options.get(option)), "reminder": False, "retry": False, "action": None, **extra})

    for action in ("Ventilate", "Ventilate for cooling", "Close"):
        for room in events[action]:
            event, title, message = action_message(action, room, data)
            add(event, title, message, room, wanted[_EVENT_OF_ACTION[action]], action=action)
    for room in events["mould"]:
        add("mould", f"FreshAirIQ · {room['name']}", f"Schimmelrisiko {room['mould_level'].lower()} · geschätzte Oberflächenfeuchte {round(room['surface_rh'])} %.{fan_hint(room)}", room, "notify_mould")
    for room in events["reminder"]:
        event = _EVENT_OF_ACTION.get(store.room(room["key"]).get("last_action"), "close")
        add(event, room_title(event, room, reminder=True), f"Erinnerung: {room_notification_message(event, room, data)}", room,
            wanted[event], reminder=True)
    for room in [] if sensor_recovery else events["sensor"]:
        add("sensor", f"FreshAirIQ · {room['name']}", room_notification_message("sensor", room, data), room, "notify_sensor")
    for room in events.get("retry", []):
        # F4: the push of an action that was attempted but not accepted (the event was published already)
        action = store.room(room["key"]).get("last_action")
        event, title, message = action_message(action, room, data)
        add(event, title, message, room, wanted[_EVENT_OF_ACTION[action]], action=action, retry=True)
    return out


def house_message(iq: dict[str, Any], rooms: dict[str, Any], automatic: bool) -> tuple[str, str]:
    """Title and text of a whole-house recommendation (push and event)."""
    keys = [str(x) for x in (iq.get("room_keys") or [])]
    picked = [(k, rooms[k]) for k in keys if isinstance(rooms.get(k), dict)]
    if automatic:
        # F1: FreshAirIQ switches every fan itself – a status, not "Jetzt schließen"
        code = "close" if str(iq.get("kind") or "") == "close" else "ventilate"
        lines = [f"{room.get('name') or key}: {handled_label(room, code)}." for key, room in picked if handled_label(room, code)]
        return f"FreshAirIQ · {AUTO_HOUSE_TITLE}", "\n".join(lines)
    first = str(iq.get("instruction") or "").strip()
    if str(iq.get("kind") or "") == "ventilate":
        fan_rooms = [str(room.get("name") or key) for key, room in picked if fan_hint(room)]
        if fan_rooms:
            first = f"{first} Alternativ den Lüfter einschalten ({', '.join(fan_rooms)}).".strip()
    summary = str(iq.get("summary") or "").strip()
    head = "\n".join(x for x in (first, summary) if x)
    return f"FreshAirIQ · {iq.get('title', 'Empfehlung')}", message_body(head, iq.get("reasons"), [iq.get("secondary") or ""])
