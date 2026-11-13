"""Which room messages are due in a notification cycle (pure, 0.26.5.3).

Community feedback (HarryP): contradicting messages ("Schlafzimmer: Bitte
Fenster schließen" while the house says "Wohnung gemeinsam weiterlüften"),
status messages drowning the actions, and no way to be reminded of an action
that is still open. This module decides per room:

* the *effective* action – the room action as aligned with the house decision
  (``house_aligned_action``), so a room never asks for something the house
  recommendation contradicts;
* reminders of a still-open action after the user's interval (5–60 min, off by
  default);
* whether a message category is wanted at all ("Statusmeldungen ausgeben").
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .automation_events import CATEGORY_STATUS, action_code, notification_category, ventilation_measures_active
from .close_wording import fan_only, house_handled_by_automation
from .fan_automation import fan_automation, handled_label
from .notification_adaptation import notification_adaptation
from .notification_text import auto_room_event  # noqa: F401 - imported from here by older callers
from .open_connections import connection_map

ROOM_EVENT_ACTIONS = ("Ventilate", "Ventilate for cooling", "Close")
_ALIGNED_TO_ACTION = {"ventilate": "Ventilate", "ventilate_for_cooling": "Ventilate for cooling", "close": "Close"}
REMINDER_OPTION = "action_reminder_min"
# F4 (notification hotfix): a room push that was attempted but not accepted is tried again – at most
# once a minute and only within this window, while the action is unchanged and still open.
PUSH_PENDING = "push_pending"
PUSH_RETRY_WINDOW_MIN = 30.0
PUSH_RETRY_STEP_MIN = 1.0
STATUS_OPTION = "notify_status_messages"
REMINDERS_SENT = "action_reminders_sent"


def status_messages_wanted(options: dict[str, Any], event_type: str) -> bool:
    """False for a status message while the user switched status messages off."""
    return bool(options.get(STATUS_OPTION, True)) or notification_category(event_type) != CATEGORY_STATUS


def reminder_interval_min(options: dict[str, Any]) -> float | None:
    """The reminder interval in minutes (5–60) or ``None`` when reminders are off."""
    try:
        value = float(options.get(REMINDER_OPTION) or 0)
    except (TypeError, ValueError):
        return None
    if value != value or value <= 0:
        return None
    return min(max(value, 5.0), 60.0)


def _aligned_action(room: dict[str, Any]) -> Any:
    aligned = str(room.get("house_aligned_action") or "")
    raw = room.get("action")
    return raw if aligned in {"", "unknown", action_code(raw)} else _ALIGNED_TO_ACTION.get(aligned, aligned)


def _fans(room: dict[str, Any]) -> set[str]:
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    raw = actuators.get("exhaust_fan")
    return {raw} if isinstance(raw, str) and raw else {str(x) for x in (raw or []) if x} if isinstance(raw, list) else set()


def effective_room_action(
    room: dict[str, Any], house: dict[str, Any] | None = None, rooms: dict[str, Any] | None = None,
    connections: dict[str, set[str]] | None = None,
) -> Any:
    """Room action as the user should act on it.

    The house-aligned recommendation wins over the raw room action (a room the
    house deliberately holds is "ventilate later", a long opening the house
    tolerates is "monitored"). A room is not asked to close while the running
    house airing keeps it open together with others, while an openly connected
    room keeps airing, or – aired by a fan alone – while another room still
    needs the same fan. A room whose openly connected neighbour is being aired
    is aired through that connection ("Ventilate indirectly"). Hard protection
    closes always stay.
    """
    action = _aligned_action(room)
    key = str(room.get("key") or "")
    house = house if isinstance(house, dict) else {}
    others = [r for k, r in (rooms or {}).items() if str(k) != key and isinstance(r, dict)]
    linked = [r for r in others if str(r.get("key") or "") in (connections or {}).get(key, set())]
    if action == "Close" and not (room.get("goal_state") or {}).get("hard_close"):
        keep = {"Continue ventilating", "Ventilate", "Ventilate for cooling"}
        if str(house.get("kind") or "") == "continue" and key in {str(k) for k in (house.get("room_keys") or [])}:
            return "Continue ventilating"
        if any(r.get("active") and _aligned_action(r) in keep for r in linked):
            return "Continue ventilating"
        if fan_only(room) and any(_fans(room) & _fans(r) and _aligned_action(r) in keep for r in others):
            return "Continue ventilating"
    if action == "Ventilate" and not room.get("active") and any(r.get("active") for r in linked):
        return "Ventilate indirectly"
    return action


def _automatic(action: Any, room: dict[str, Any]) -> bool:
    """0.26.5.4: FreshAirIQ carries the action out itself - nothing to remind of."""
    return handled_label(room, action_code(action)) is not None and not fan_automation(room).get("user_action_needed")


def _still_open(action: Any, room: dict[str, Any]) -> bool:
    """The asked action has not been done yet."""
    return bool(room.get("active")) if action == "Close" else not room.get("active")


def room_notification_events(
    rooms: dict[str, Any], store: Any, now: datetime, options: dict[str, Any], house: dict[str, Any] | None,
    *, sensor_alerts: Any, quiet: bool = False,
) -> tuple[dict[str, list[dict[str, Any]]], bool]:
    """Room messages due in this cycle and whether the persisted state changed.

    ``reminder`` lists rooms whose action is unchanged and still open after the
    reminder interval. The action state is persisted, so a restart does not spam.
    """
    events: dict[str, list[dict[str, Any]]] = {**{name: [] for name in ROOM_EVENT_ACTIONS}, "sensor": [], "mould": [], "reminder": [], "retry": []}
    changed = False
    interval = reminder_interval_min(options)
    connections = connection_map(options, rooms)
    for key, room in rooms.items():
        if not isinstance(room, dict):
            continue
        mem = store.room(key)
        action = effective_room_action(room, house, rooms, connections)
        # 0.26.7.0 (behaviour learning): how this room's reminders are adapted – visible for diagnostics
        adaptation = room["notification_adaptation"] = notification_adaptation(room, options, interval)
        if action != mem.get("last_action") and _reopen_held(action, room, mem, now, options):
            pass  # announced once the repeat cooldown is over (the last action stays)
        elif action != mem.get("last_action"):
            mem["last_action"] = action
            mem["action_notified_at"] = now.isoformat()
            mem[REMINDERS_SENT] = 0
            mem.pop(PUSH_PENDING, None)  # F4: a push of the previous action is no longer valid
            changed = True
            if action in events:
                events[action].append(room)
        elif PUSH_PENDING in mem:
            due, dropped = _push_retry(action, room, mem, now)
            changed = changed or dropped
            if due:
                events["retry"].append(room)
        elif interval is not None and action in ROOM_EVENT_ACTIONS and _still_open(action, room) and not _automatic(action, room):
            due, touched = _reminder_due(room, mem, now, adaptation, quiet=quiet)
            changed = changed or touched
            if due:
                events["reminder"].append(room)
        if room.get("data_quality") != "ok" and sensor_alerts(room):
            events["sensor"].append(room)
        # 0.26.4.6 (user feedback): no mould alarm while something already works
        # against the humidity (shower with running fan, open window, recovery).
        if room.get("mould_level") in {"High", "Very high"} and not ventilation_measures_active(room):
            events["mould"].append(room)
    return events, changed


def _reminder_due(room: dict[str, Any], mem: dict[str, Any], now: datetime, adaptation: dict[str, Any], *, quiet: bool = False) -> tuple[bool, bool]:
    """(reminder due now, persisted state changed) – after the (adapted) interval, at most ``max_reminders`` times.
    A reminder in the quiet night window (push held back) does not use up the limit."""
    notified = _parse(mem.get("action_notified_at"))
    if notified is None:
        # state from before 0.26.5.3 or a damaged value: count from now
        mem["action_notified_at"] = now.isoformat()
        return False, True
    if now - notified < timedelta(minutes=float(adaptation["reminder_interval_min"])):
        return False, False
    limit = adaptation.get("max_reminders")
    sent = int(mem.get(REMINDERS_SENT) or 0) if str(mem.get(REMINDERS_SENT) or "0").isdigit() else 0
    if limit is not None and sent >= int(limit):
        return False, False  # no reminder loop: the action stays visible on the dashboard
    mem["action_notified_at"] = now.isoformat()
    mem[REMINDERS_SENT] = sent if quiet else sent + 1
    room["reminder_summarize"] = bool(adaptation.get("summarize"))
    return True, True


def _push_retry(action: Any, room: dict[str, Any], mem: dict[str, Any], now: datetime) -> tuple[bool, bool]:
    """F4: (push due again, pending state dropped) for a room push that was not accepted."""
    pending = mem.get(PUSH_PENDING) if isinstance(mem.get(PUSH_PENDING), dict) else {}
    first, attempt = _parse(pending.get("first_at")), _parse(pending.get("attempt_at"))
    if (pending.get("action") != action or first is None or attempt is None or now - first > timedelta(minutes=PUSH_RETRY_WINDOW_MIN)
            or not _still_open(action, room) or _automatic(action, room)):
        mem.pop(PUSH_PENDING, None)
        return False, True
    return now - attempt >= timedelta(minutes=PUSH_RETRY_STEP_MIN), False


def record_room_push(mem: dict[str, Any], message: dict[str, Any], accepted: bool, now: datetime) -> bool:
    """F4: after a room message of an action – whether the persisted state changed.

    ``accepted`` is False only when a push was attempted and no notify service accepted it (a push the
    user's options, the night window, the room selection, presence or the cooldown hold back is not a
    failure). Only then the push is kept for a bounded retry. "Close was said" (GitHub #15 hold) is
    stored once the close message is out, never before.
    """
    action = message.get("action")
    if action not in ROOM_EVENT_ACTIONS or mem.get("last_action") != action:
        return False
    if not accepted:
        pending = mem.get(PUSH_PENDING) if isinstance(mem.get(PUSH_PENDING), dict) else {}
        first = pending.get("first_at") if pending.get("action") == action else None
        mem[PUSH_PENDING] = {"action": action, "first_at": first or now.isoformat(), "attempt_at": now.isoformat()}
        return True
    mem.pop(PUSH_PENDING, None)
    if action == "Close":
        mem["last_close_message_at"] = now.isoformat()
    return True


def _reopen_held(action: Any, room: dict[str, Any], mem: dict[str, Any], now: datetime, options: dict[str, Any]) -> bool:
    """0.26.5.3 (GitHub #15): no "ventilate" right after "close" for the same room.

    Within the repeat cooldown after a close message, a new ventilate message
    waits – unless the room needs protection (critical mould risk or CO2).
    """
    if action not in {"Ventilate", "Ventilate for cooling"}:
        return False
    closed = _parse(mem.get("last_close_message_at"))
    try:
        cooldown = float(options.get("repeat_recommendation_cooldown_min", 120.0))
    except (TypeError, ValueError):
        cooldown = 120.0
    if closed is None or now - closed >= timedelta(minutes=cooldown):
        return False
    return not _protection_needed(room, options)


def house_reopen_held(kind: str, last_close_at: Any, now: datetime, options: dict[str, Any], iq: dict[str, Any], rooms: dict[str, Any]) -> bool:
    """Community hotfix (GitHub #15): the house "ventilate" push waits after a house "close" push.

    The two pushes have separate cooldowns, so "open" could follow "close" within minutes. Same rule
    as ``_reopen_held`` for room messages: within the repeat cooldown, unless a named room needs
    protection (critical mould risk or CO2). Not stored as sent – it follows once the time is over.
    """
    if kind != "ventilate":
        return False
    held = _reopen_held("Ventilate", {}, {"last_close_message_at": last_close_at}, now, options)  # the time rule only
    keys = [str(k) for k in (iq.get("room_keys") or [])]
    return held and not any(_protection_needed(rooms[k], options) for k in keys if isinstance(rooms.get(k), dict))


def _protection_needed(room: dict[str, Any], options: dict[str, Any]) -> bool:
    try:
        surface = float(room.get("surface_rh") or 0.0)
        co2 = float(room.get("co2") or 0.0) if room.get("co2_available", True) else 0.0
        return surface >= float(options.get("mould_critical_surface_rh", 90.0)) or co2 >= float(options.get("co2_critical", 1400.0))
    except (TypeError, ValueError):
        return True


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def auto_house(iq: dict[str, Any], rooms: dict[str, Any]) -> bool:
    """A house close/ventilate that only concerns fans FreshAirIQ switches itself."""
    return house_handled_by_automation(iq.get("kind"), iq.get("room_keys"), rooms)
