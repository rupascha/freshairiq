"""Notification routing and anti-spam logic for FreshAirIQ."""
from __future__ import annotations
from contextvars import ContextVar
from datetime import datetime, timedelta
import json
import re
import math
from typing import Any

from homeassistant.core import HomeAssistant

from .automation_events import ventilation_measures_active
from .const import NOTIFY_SCOPE_BOTH, NOTIFY_SCOPE_HOUSE, NOTIFY_SCOPE_ROOM
from .forecast import in_night_window, night_window_hours
from .intelligence import mark_recommendation_notified
from .language_confidence import room_notification_message
from .localize import Translator, is_german, protected_names

# Set while one notification pass runs for a non-German Home Assistant (0.26.4.5).
_OUTPUT_TRANSLATOR: ContextVar[Translator | None] = ContextVar("freshairiq_notification_translator", default=None)


def _localized(title: str, message: str) -> tuple[str, str]:
    translator = _OUTPUT_TRANSLATOR.get()
    if translator is None:
        return title, message
    return translator.text(str(title or "")), translator.text(str(message or ""))

def _finite_float(value: Any, default: float = 0.0) -> float:
    """Return a finite float; corrupted/runtime values degrade to a safe default."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)




def _available_notification_targets(hass: HomeAssistant, configured: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Discover legacy notify services and modern notify entities from HA backend state.

    Configured targets are retained even when temporarily unavailable so opening and
    saving settings never silently loses a valid target during startup/reload.
    """
    services = sorted(
        service for service in (hass.services.async_services().get("notify") or {}).keys()
        if service != "send_message"
    )
    entities: set[str] = set()
    states = getattr(hass, "states", None)
    if states is not None and hasattr(states, "async_all"):
        entities.update(
            str(state.entity_id) for state in states.async_all()
            if str(getattr(state, "entity_id", "")).startswith("notify.")
        )
    # The entity registry is authoritative even when an entity currently has no State
    # object (for example during a platform reload). Keep this optional for test/mocks.
    try:
        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(hass)
        registry_entities = getattr(registry, "entities", {})
        values = registry_entities.values() if hasattr(registry_entities, "values") else []
        entities.update(
            str(entry.entity_id) for entry in values
            if str(getattr(entry, "entity_id", "")).startswith("notify.")
        )
    except (ImportError, AttributeError, TypeError):
        pass
    for target in configured or []:
        value = str(target or "").strip()
        if value.startswith("entity:notify."):
            entities.add(value.split(":", 1)[1])
        elif value.startswith("notify."):
            service = value.split(".", 1)[1]
            if service and service not in services:
                services.append(service)
        elif value and not value.startswith("entity:") and value not in services:
            services.append(value)
    return sorted(set(services)), sorted(entities)

def _target_service(target: str) -> str:
    return target.split(".", 1)[1] if target.startswith("notify.") else target


def _target_entity(target: str) -> str | None:
    """Return a notify entity target encoded by the settings contract."""
    value = str(target or "").strip()
    if value.startswith("entity:notify."):
        return value.split(":", 1)[1]
    return None


def _target_available(hass: HomeAssistant, target: str) -> bool:
    entity_id = _target_entity(target)
    if entity_id is not None:
        return bool(hass.services.has_service("notify", "send_message") and hass.states.get(entity_id) is not None)
    return hass.services.has_service("notify", _target_service(str(target)))


async def _send_target(hass: HomeAssistant, target: str, title: str, message: str) -> bool:
    """Send through either a legacy notify service or a modern notify entity."""
    title, message = _localized(title, message)
    entity_id = _target_entity(target)
    if entity_id is not None:
        if not _target_available(hass, target):
            return False
        # ``target:`` is automation/script syntax. Direct ServiceRegistry calls
        # pass the resolved entity target as ``entity_id`` in service_data.
        data = {"message": message, "entity_id": entity_id}
        if title:
            data["title"] = title
        await hass.services.async_call("notify", "send_message", data, blocking=False)
        return True
    service = _target_service(str(target))
    if not hass.services.has_service("notify", service):
        return False
    await hass.services.async_call("notify", service, {"title": title, "message": message}, blocking=False)
    return True


def _allowed_room(room_key: str, options: dict[str, Any]) -> bool:
    selected = options.get("notification_room_keys") or []
    return not selected or room_key in selected


def _due(store, key: str, now: datetime, cooldown_min: float) -> bool:
    sent = store.data.setdefault("notifications", {}).get(key)
    if sent:
        try:
            if now - datetime.fromisoformat(sent) < timedelta(minutes=cooldown_min):
                return False
        except (TypeError, ValueError):
            pass
    return True


def _mark_sent(store, key: str, now: datetime) -> None:
    store.data.setdefault("notifications", {})[key] = now.isoformat()


# Slot labels the dashboard shows for residents without a name ("Erwachsener 1").
_PLACEHOLDER_NAME = re.compile(r"(?:erwachsene[rn]?|kind|adult|child|person)\s*\d+", re.IGNORECASE)


def _resident_profiles(options: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        raw = options.get("resident_room_profiles") or "{}"
        data = raw if isinstance(raw, dict) else json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    def _names(value: Any) -> list[str]:
        text = str(value or "").replace(";", ",").replace("\n", ",")
        return [part.strip() for part in text.split(",") if part.strip()]
    adult_names = _names(options.get("adult_resident_names"))
    child_names = _names(options.get("child_resident_names"))
    result: list[dict[str, Any]] = []
    for slot, raw_profile in data.items():
        if not isinstance(raw_profile, dict) or not raw_profile.get("notification_targets"):
            continue
        profile = dict(raw_profile)
        role, sep, index_text = str(slot).partition(":")
        names = adult_names if role == "adult" else child_names if role == "child" else []
        stored = " ".join(str(profile.get("name") or "").split())
        # 0.26.4.1 (community report): profiles saved before a name was entered kept
        # the placeholder "Erwachsener 1" and every message started with it. Only a
        # name that is configured for this household may address someone.
        if stored and stored in names:
            profile["name"] = stored
        elif sep and index_text.isdigit() and 0 <= int(index_text) < len(names):
            profile["name"] = names[int(index_text)]
        elif stored and not _PLACEHOLDER_NAME.fullmatch(stored):
            profile["name"] = stored
        else:
            profile["name"] = ""
        result.append(profile)
    return result


def _all_notification_targets(options: dict[str, Any]) -> list[str]:
    """Return global and resident targets once, preserving configured order."""
    result: list[str] = []
    seen: set[str] = set()
    for target in options.get("notification_targets") or []:
        value = str(target)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    for profile in _resident_profiles(options):
        for target in profile.get("notification_targets") or []:
            value = str(target)
            if value and value not in seen:
                seen.add(value)
                result.append(value)
    return result


def _has_notification_targets(options: dict[str, Any]) -> bool:
    return bool(_all_notification_targets(options))


_RECOMMENDATION_EVENTS = {"ventilate", "cool", "iq_ventilate", "iq_continue", "iq_wait", "iq_pollen_wait", "iq_prepare"}
# Repeated suppressions / undeliverable attempts are folded into one trace row.
_FOLDABLE_TRACE_STATUSES = {"suppressed", "not_sent"}
TRACE_FOLD_WINDOW_SECONDS = 30 * 60


def _record_notification_diagnostic(
    store, *, now: datetime, event: str, scope: str, status: str,
    target_count: int, available_service_count: int, reason: str | None = None,
    exception_type: str | None = None,
) -> bool:
    """Persist a bounded privacy-safe notification delivery trace.

    Never stores notify entity IDs, service names, titles, messages, resident names
    or other user content. The trace exists so a later manual diagnostic export can
    distinguish suppression/configuration problems from HA notify-service failures.

    0.26.4.7 (support exports): a suppressed or undeliverable message is retried
    every coordinator cycle. Repeats of the same row are folded into the previous
    row (``repeat_count``/``last_seen_at``) instead of appending a new row every
    10 seconds, which pushed real deliveries out of the 50-row window and forced
    an immediate storage write on every cycle. Returns ``True`` only when a new
    row was added (the caller then persists immediately).
    """
    trace = store.data.setdefault("notification_diagnostics", [])
    if not isinstance(trace, list):
        trace = []
        store.data["notification_diagnostics"] = trace
    if status in _FOLDABLE_TRACE_STATUSES and not exception_type:
        signature = (str(event)[:48], str(scope)[:16], str(status)[:24], str(reason)[:64] if reason else None)
        for previous in reversed(trace[-10:]):
            if not isinstance(previous, dict):
                continue
            if (previous.get("event"), previous.get("scope"), previous.get("status"), previous.get("reason")) != signature:
                continue
            try:
                last_seen = datetime.fromisoformat(str(previous.get("last_seen_at") or previous.get("timestamp")))
                age_s = (now - last_seen).total_seconds()
            except (TypeError, ValueError):
                break
            if 0 <= age_s <= TRACE_FOLD_WINDOW_SECONDS:
                previous["repeat_count"] = int(previous.get("repeat_count", 0) or 0) + 1
                previous["last_seen_at"] = now.isoformat()
                previous["target_count"] = max(int(target_count), 0)
                previous["available_service_count"] = max(int(available_service_count), 0)
                return False
            break
    row = {
        "timestamp": now.isoformat(),
        "event": str(event)[:48],
        "scope": str(scope)[:16],
        "status": str(status)[:24],
        "target_count": max(int(target_count), 0),
        "available_service_count": max(int(available_service_count), 0),
    }
    if reason:
        row["reason"] = str(reason)[:64]
    if exception_type:
        row["exception_type"] = str(exception_type)[:64]
    trace.append(row)
    store.data["notification_diagnostics"] = trace[-50:]
    # 0.26.4.3: link delivery to the active recommendation episode so the follow
    # rate can be split into "notified" and "only shown on the dashboard".
    if row["status"] == "sent" and row["event"] in _RECOMMENDATION_EVENTS:
        mark_recommendation_notified(store.data, now)
    return True


def _room_can_raise_sensor_alerts(room: dict[str, Any]) -> bool:
    """Only rooms FreshAirIQ actually calculates can have a sensor problem.

    0.26.4.7 (support case "Benachrichtigungen für Räume ohne Berechnung und
    Sensoren"): rooms kept only as building structure or as live-value displays
    report ``data_quality`` "not_configured"/"monitor_only". That is their
    intended state, not a fault, so they must never trigger "Sensoren prüfen".
    """
    if room.get("calculation_enabled") is False or room.get("monitor_only"):
        return False
    return str(room.get("action") or "") != "Monitor only"


def _notification_service_counts(hass: HomeAssistant, options: dict[str, Any]) -> tuple[int, int]:
    targets = _all_notification_targets(options)
    available = sum(1 for target in targets if _target_available(hass, str(target)))
    return len(targets), available


async def _send_targets(
    hass: HomeAssistant, targets: list[str], title: str, message: str
) -> bool:
    sent = False
    used: set[str] = set()
    for target in targets:
        value = str(target)
        if not value or value in used:
            continue
        used.add(value)
        if await _send_target(hass, value, title, message):
            sent = True
    return sent


async def _send(hass: HomeAssistant, options: dict[str, Any], title: str, message: str) -> bool:
    """Send a household message to all configured global/personal devices."""
    return await _send_targets(hass, _all_notification_targets(options), title, message)


async def _send_room_personalised(
    hass: HomeAssistant,
    options: dict[str, Any],
    title: str,
    message: str,
    room_key: str,
) -> bool:
    """Route a room event to global targets plus residents assigned to that room."""
    sent = False
    used: set[str] = set()

    for profile in _resident_profiles(options):
        assigned = {str(x) for x in (profile.get("room_keys") or [])}
        if room_key not in assigned:
            continue
        name = str(profile.get("name") or "").strip()
        personal_message = f"{name}, {message}" if name else message
        for target in profile.get("notification_targets") or []:
            value = str(target)
            if not value or value in used:
                continue
            used.add(value)
            if await _send_target(hass, value, title, personal_message):
                sent = True

    for target in options.get("notification_targets") or []:
        value = str(target)
        if not value or value in used:
            continue
        used.add(value)
        if await _send_target(hass, value, title, message):
            sent = True
    return sent


async def _send_personalised(hass: HomeAssistant, options: dict[str, Any], title: str, message: str, iq: dict[str, Any]) -> bool:
    """Send one resident-specific wording per assigned phone/notify service.

    The physical recommendation remains identical; only address, room context
    and comfort wording differ per resident. Unassigned global targets still
    receive the neutral household message.
    """
    sent = False
    used: set[str] = set()
    selected = set(str(x) for x in (iq.get("room_keys") or []))
    temp = _finite_float(iq.get("expected_temperature_change_c"), 0.0)
    for profile in _resident_profiles(options):
        name = str(profile.get("name") or "").strip()
        assigned = set(str(x) for x in (profile.get("room_keys") or []))
        thermal = str(profile.get("thermal_preference") or "inherit")
        prefix = f"{name}, " if name else ""
        context = ""
        if selected & assigned:
            context = "Diese Empfehlung betrifft einen deiner hinterlegten Räume. "
        if thermal == "warm" and temp < -0.2:
            context += "Dein eher warmes Komfortprofil ist beim Temperaturverlust berücksichtigt. "
        personal = prefix + context + message
        for target in profile.get("notification_targets") or []:
            value = str(target)
            if not value or value in used:
                continue
            used.add(value)
            if await _send_target(hass, value, title, personal):
                sent = True
    for target in options.get("notification_targets") or []:
        if str(target) in used:
            continue
        if await _send_target(hass, str(target), title, message):
            sent = True
    return sent


def _continuation(room: dict[str, Any]) -> str:
    """User-facing forecast using the configured horizon, never the internal 5-min gate."""
    horizon = max(int(round(_finite_float(room.get("forecast_horizon_min", 5), 5.0))), 1)
    effect = _finite_float(room.get("forecast_moisture_effect_ml", room.get("forecast_5_min_moisture_effect_ml", 0)), 0.0)
    dt = _finite_float(room.get("forecast_temperature_change_c", room.get("forecast_5_min_temperature_change_c", 0)), 0.0)
    cost = max(_finite_float(room.get("forecast_cost", room.get("next_5_min_cost", 0)), 0.0), 0.0)
    moisture = f"−{round(abs(effect))} ml" if effect > 0 else f"+{round(abs(effect))} ml" if effect < 0 else "±0 ml"
    sign = "+" if dt > 0 else "−" if dt < 0 else "±"
    temp = f"{sign}{abs(dt):.1f} °C" if dt else "±0.0 °C"
    return f"Weitere {horizon} Min: {moisture} · Temperatur {temp} · Energiekosten ca. {cost:.2f} €"


EVENT_NOTIFICATION = "freshairiq_notification"


def _fan_hint(room: dict[str, Any]) -> str:
    """0.26.4.9: rooms with an exhaust fan can also be aired by the fan."""
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    if not actuators.get("exhaust_fan") or actuators.get("mechanical_exhaust_active"):
        return ""
    return " Alternativ den Lüfter einschalten."


def _house_message(iq: dict[str, Any], rooms: dict[str, Any]) -> tuple[str, str]:
    """Title and text of a whole-house recommendation (push and event)."""
    title = f"FreshAirIQ · {iq.get('title', 'Empfehlung')}"
    message_parts = [str(iq.get("instruction") or "").strip(), str(iq.get("summary") or "").strip()]
    reasons = [str(x).strip() for x in (iq.get("reasons") or []) if str(x).strip()]
    if reasons:
        message_parts.append("Warum: " + " · ".join(reasons[:3]))
    if iq.get("secondary"):
        message_parts.append(str(iq.get("secondary")))
    if str(iq.get("kind") or "") == "ventilate":
        fan_rooms = [str(r.get("name") or k) for k, r in rooms.items() if isinstance(r, dict) and str(k) in {str(x) for x in (iq.get("room_keys") or [])} and _fan_hint(r)]
        if fan_rooms:
            message_parts.append(f"Alternativ den Lüfter einschalten ({', '.join(fan_rooms)}).")
    return title, " ".join(x for x in message_parts if x)


def _publish_event(
    hass: HomeAssistant, store, now: datetime, cooldown: float, event: str, title: str, message: str,
    room_key: str | None, rooms: dict[str, Any], night_quiet: bool, extra: dict[str, Any] | None = None,
) -> bool:
    """Fire ``freshairiq_notification`` once per message (same cooldown as push)."""
    key = f"event:{event}:{room_key or 'house'}"
    if not _due(store, key, now, cooldown):
        return False
    title_out, message_out = _localized(title, message)
    room = rooms.get(room_key) if room_key and isinstance(rooms.get(room_key), dict) else {}
    payload: dict[str, Any] = {
        "type": event,
        "room_key": room_key,
        "room_name": room.get("name") if room else None,
        "title": title_out,
        "message": message_out,
        # Speech-friendly text for Alexa & co.: without the "FreshAirIQ ·" prefix.
        "speech": message_out if not room else f"{room.get('name')}: {message_out}",
        "night_quiet_hours": bool(night_quiet),
        "created_at": now.isoformat(),
    }
    if extra:
        payload.update(extra)
    try:
        hass.bus.async_fire(EVENT_NOTIFICATION, payload)
    except Exception:  # noqa: BLE001 - an event listener must never break the coordinator
        return False
    _mark_sent(store, key, now)
    return True


def notification_translator(hass: HomeAssistant, data: dict[str, Any], options: dict[str, Any]) -> Translator | None:
    """English output for every Home Assistant language except German."""
    language = getattr(getattr(hass, "config", None), "language", None)
    if not isinstance(language, str) or is_german(language):
        return None
    rooms = data.get("rooms") if isinstance(data.get("rooms"), dict) else {}
    entry_like = {
        "rooms": [r for r in rooms.values() if isinstance(r, dict)],
        "levels": data.get("levels") if isinstance(data.get("levels"), list) else [],
    }
    return Translator(protected_names(entry_like, options))


async def process_notifications(hass: HomeAssistant, store, data: dict[str, Any], options: dict[str, Any], now: datetime, completed_sessions: list[dict[str, Any]]) -> bool:
    token = _OUTPUT_TRANSLATOR.set(notification_translator(hass, data, options))
    try:
        return await _process_notifications(hass, store, data, options, now, completed_sessions)
    finally:
        _OUTPUT_TRANSLATOR.reset(token)


async def _process_notifications(hass: HomeAssistant, store, data: dict[str, Any], options: dict[str, Any], now: datetime, completed_sessions: list[dict[str, Any]]) -> bool:
    # 0.26.4.9: every message is also published as Home Assistant event
    # ``freshairiq_notification`` (Node-RED, Alexa announcements, own
    # automations) – even when phone notifications are off or no notify
    # service is configured. Phone delivery itself is unchanged.
    push_enabled = bool(options.get("notifications_enabled")) and _has_notification_targets(options)
    changed = False
    cooldown = max(_finite_float(options.get("notification_cooldown_min", 90), 90.0), 0.0)
    scope = options.get("notification_scope", NOTIFY_SCOPE_HOUSE)
    rooms_raw = data.get("rooms", {})
    rooms = rooms_raw if isinstance(rooms_raw, dict) else {}
    suppress_at_night = bool(
        options.get("suppress_notifications_at_night")
        and options.get("night_forecast_enabled", True)
        and in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour"))
    )
    # A Home Assistant restart can restore FreshAirIQ before its source integrations.
    # The coordinator already protects decisions for 90 seconds while those sources
    # recover. Mirror that guard for sensor-error notifications: keep the safe
    # sensor_error state internally, but do not alarm the user about a condition
    # which the runtime is explicitly treating as transient.
    recovery = data.get("sensor_recovery") if isinstance(data.get("sensor_recovery"), dict) else {}
    sensor_recovery_active = bool(recovery.get("active"))

    # Per-room action transitions. The action state is persisted, so restart does not spam.
    room_events: dict[str, list[dict[str, Any]]] = {"Ventilate": [], "Ventilate for cooling": [], "Close": [], "sensor": [], "mould": []}
    for key, room in rooms.items():
        if not isinstance(room, dict):
            continue
        mem = store.room(key)
        action = room.get("action")
        previous = mem.get("last_action")
        if action != previous:
            mem["last_action"] = action
            changed = True
            if action in room_events:
                room_events[action].append(room)
        if room.get("data_quality") != "ok" and _room_can_raise_sensor_alerts(room):
            room_events["sensor"].append(room)
        # 0.26.4.6 (user feedback): no mould alarm while something already works
        # against the humidity (shower with running fan, open window, recovery).
        # The warning follows once windows are closed and the fan is off again.
        if room.get("mould_level") in {"High", "Very high"} and not ventilation_measures_active(room):
            room_events["mould"].append(room)

    def publish(event: str, title: str, message: str, room_key: str | None = None, extra: dict[str, Any] | None = None) -> None:
        nonlocal changed
        if _publish_event(hass, store, now, cooldown, event, title, message, room_key, rooms, suppress_at_night, extra):
            changed = True

    async def emit(event: str, title: str, message: str, room_key: str | None = None, *, push: bool = True) -> bool:
        nonlocal changed
        publish(event, title, message, room_key)
        if not push_enabled or not push:
            return True
        target_count, available_count = _notification_service_counts(hass, options)
        if suppress_at_night:
            if _record_notification_diagnostic(store, now=now, event=event, scope="room" if room_key else "house", status="suppressed", target_count=target_count, available_service_count=available_count, reason="night_suppression"):
                changed = True
            return True
        if room_key and not _allowed_room(room_key, options):
            if _record_notification_diagnostic(store, now=now, event=event, scope="room", status="suppressed", target_count=target_count, available_service_count=available_count, reason="room_not_selected"):
                changed = True
            return True
        key = f"{event}:{room_key or 'house'}"
        if not _due(store, key, now, cooldown):
            if _record_notification_diagnostic(store, now=now, event=event, scope="room" if room_key else "house", status="suppressed", target_count=target_count, available_service_count=available_count, reason="cooldown"):
                changed = True
            return True
        try:
            sender_ok = (
                await _send_room_personalised(hass, options, title, message, room_key)
                if room_key
                else await _send(hass, options, title, message)
            )
        except Exception as err:
            _record_notification_diagnostic(
                store, now=now, event=event, scope="room" if room_key else "house",
                status="failed", target_count=target_count, available_service_count=available_count,
                reason="notify_service_exception", exception_type=type(err).__name__,
            )
            changed = True
            return False
        if _record_notification_diagnostic(
            store, now=now, event=event, scope="room" if room_key else "house",
            status="sent" if sender_ok else "not_sent", target_count=target_count,
            available_service_count=available_count,
            reason=None if sender_ok else "no_available_notify_service",
        ):
            changed = True
        if sender_ok:
            _mark_sent(store, key, now)
            changed = True
            return True
        return False

    # Room-scope messages (events always; phone push per scope and toggle)
    room_push = scope in {NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_BOTH}
    for r in room_events["Ventilate"]:
        reasons = ' · '.join(r.get('recommendation_reasons') or [])
        await emit("ventilate", f"FreshAirIQ · {r['name']}", f"{room_notification_message('ventilate', r, store.data)}{_fan_hint(r)} {reasons}".strip(), r["key"], push=room_push and bool(options.get("notify_ventilate")))
    for r in room_events["Ventilate for cooling"]:
        await emit("cool", f"FreshAirIQ · {r['name']}", f"{room_notification_message('cool', r, store.data)} {_continuation(r)}", r["key"], push=room_push and bool(options.get("notify_cooling")))
    for r in room_events["Close"]:
        await emit("close", f"FreshAirIQ · {r['name']}", f"{room_notification_message('close', r, store.data)} {_continuation(r)}", r["key"], push=room_push and bool(options.get("notify_close")))
    for r in room_events["mould"]:
        await emit("mould", f"FreshAirIQ · {r['name']}", f"Schimmelrisiko {r['mould_level'].lower()} · geschätzte Oberflächenfeuchte {round(r['surface_rh'])} %.{_fan_hint(r)}", r["key"], push=room_push and bool(options.get("notify_mould")))
    if not sensor_recovery_active:
        for r in room_events["sensor"]:
            await emit("sensor", f"FreshAirIQ · {r['name']}", room_notification_message("sensor", r, store.data), r["key"], push=room_push and bool(options.get("notify_sensor")))

    # House-scope messages use Recommendation Engine v2. The user receives one
    # coherent action instead of a dump of competing room recommendations.
    house_iq = data.get("intelligent_recommendation") if isinstance(data.get("intelligent_recommendation"), dict) else {}
    house_kind = str(house_iq.get("kind") or "")
    # Language-neutral (German and English installations keep identical state).
    house_signature = f"{house_kind}:{','.join(str(k) for k in (house_iq.get('room_keys') or []))}:{house_iq.get('status') or ''}"
    # A sensor recommendation during the start-up recovery grace is not stored, so it
    # is still published if the recovery really fails.
    if house_kind and house_signature != store.data.get("last_house_event_signature") and not (house_kind == "sensor" and sensor_recovery_active):
        store.data["last_house_event_signature"] = house_signature
        changed = True
        title_text, message_text = _house_message(house_iq, rooms)
        publish(f"house_{house_kind}", title_text, message_text, None, {"kind": house_kind, "room_keys": [str(k) for k in (house_iq.get("room_keys") or [])]})
    if push_enabled and scope in {NOTIFY_SCOPE_HOUSE, NOTIFY_SCOPE_BOTH}:
        iq_raw = data.get("intelligent_recommendation") or {}
        iq = iq_raw if isinstance(iq_raw, dict) else {}
        kind = str(iq.get("kind") or "")
        signature = f"{kind}:{','.join(iq.get('room_keys') or [])}:{iq.get('instruction','')}"
        previous_signature = store.data.get("last_house_recommendation_signature")
        if signature != previous_signature:
            title, message = _house_message(iq, rooms)
            # 0.26.4.9 (user feedback): "Lüftung läuft · Lüftung weiter beobachten"
            # asks nothing of the user, so a running airing is no longer pushed.
            enabled = ((kind in {"ventilate", "pollen_wait"} and options.get("notify_ventilate")) or (kind == "close" and options.get("notify_close")) or (kind == "sensor" and options.get("notify_sensor")))
            handled = True
            event_key = f"iq_{kind}:house"
            target_count, available_count = _notification_service_counts(hass, options)
            if kind == "sensor" and sensor_recovery_active:
                # Do not persist this transient signature. If recovery really fails
                # beyond the coordinator grace period, the unchanged recommendation
                # is then still eligible for delivery on the next cycle.
                handled = False
                if _record_notification_diagnostic(store, now=now, event="iq_sensor", scope="house", status="suppressed", target_count=target_count, available_service_count=available_count, reason="sensor_recovery_grace"):
                    changed = True
            elif not enabled:
                if _record_notification_diagnostic(store, now=now, event=f"iq_{kind}", scope="house", status="suppressed", target_count=target_count, available_service_count=available_count, reason="event_type_disabled"):
                    changed = True
            elif suppress_at_night:
                if _record_notification_diagnostic(store, now=now, event=f"iq_{kind}", scope="house", status="suppressed", target_count=target_count, available_service_count=available_count, reason="night_suppression"):
                    changed = True
            elif not _due(store, event_key, now, cooldown):
                if _record_notification_diagnostic(store, now=now, event=f"iq_{kind}", scope="house", status="suppressed", target_count=target_count, available_service_count=available_count, reason="cooldown"):
                    changed = True
            if enabled and not suppress_at_night and not (kind == "sensor" and sensor_recovery_active) and _due(store, event_key, now, cooldown):
                try:
                    handled = await _send_personalised(hass, options, title, message, iq)
                except Exception as err:
                    handled = False
                    _record_notification_diagnostic(
                        store, now=now, event=f"iq_{kind}", scope="house", status="failed",
                        target_count=target_count, available_service_count=available_count,
                        reason="notify_service_exception", exception_type=type(err).__name__,
                    )
                    changed = True
                else:
                    if _record_notification_diagnostic(
                        store, now=now, event=f"iq_{kind}", scope="house",
                        status="sent" if handled else "not_sent", target_count=target_count,
                        available_service_count=available_count,
                        reason=None if handled else "no_available_notify_service",
                    ):
                        changed = True
                if handled:
                    _mark_sent(store, event_key, now)
            if handled:
                store.data["last_house_recommendation_signature"] = signature
                changed = True

    for event in completed_sessions:
        if not isinstance(event, dict) or not event.get("key"):
            continue
        if event.get("learning_valid"):
            await emit("learning", f"FreshAirIQ · {event['name']}", "Neue gültige Lernprobe übernommen. Das Raum-Modell wurde aktualisiert.", event["key"], push=bool(options.get("notify_learning")) and _allowed_room(str(event["key"]), options))

    for event in completed_sessions:
        if not isinstance(event, dict) or not event.get("key"):
            continue
        room_key = str(event["key"])
        moisture_valid = bool(
            event.get("moisture_measurement_valid", event.get("removed_ml") is not None)
            and event.get("removed_ml") is not None
        )
        name = str(event.get("name") or room_key)
        if not moisture_valid:
            message = (
                "Lüftung beendet. Die Feuchtemessung war für eine belastbare Abschlussauswertung nicht ausreichend; "
                "der Vorgang wird nicht für Feuchte-Lernen oder Prognosekalibrierung verwendet."
            )
        else:
            removed_ml = _finite_float(event.get("removed_ml"), 0.0)
            temp_delta = _finite_float(event.get("temp_delta_c"), 0.0)
            cost = max(_finite_float(event.get("cost"), 0.0), 0.0)
            message = (
                (f"Lüftung beendet: {round(removed_ml)} ml entfernt" if removed_ml >= 0 else f"Lüftung beendet: {round(abs(removed_ml))} ml eingetragen")
                + f" · Temperatur {temp_delta:+.1f} °C · geschätzte Energiekosten {cost:.2f} €."
            )
        await emit("complete", f"FreshAirIQ · {name}", message, room_key, push=bool(options.get("notify_complete")) and _allowed_room(room_key, options))

    # One optional evening forecast per date.
    start_raw = options.get("night_start_hour", "22:00")
    try:
        raw = str(start_raw)
        if ":" in raw:
            h_raw, m_raw = raw.split(":", 1)
            night_start_min = (int(h_raw) % 24) * 60 + min(max(int(m_raw[:2]), 0), 59)
        else:
            night_start_min = (int(raw) % 24) * 60
    except (TypeError, ValueError):
        night_start_min = 22 * 60
    current_min = now.hour * 60 + now.minute + now.second / 60.0
    hours_to_night = ((night_start_min - current_min) % 1440.0) / 60.0
    night_window_enabled = night_window_hours(
        options.get("night_start_hour", "22:00"), options.get("night_end_hour", "07:00")
    ) > 0.0
    if night_window_enabled and hours_to_night <= 3.0:
        today=now.date().isoformat()
        if store.data.get("last_night_notification_date") != today and (options.get("notify_night") or store.data.get("last_night_event_date") != today):
            ns = data.get("night_strategy") if isinstance(data.get("night_strategy"), dict) else {}
            detail = str(ns.get("summary") or "").strip()
            instruction = str(ns.get("instruction") or data.get("night_recommendation", "")).strip()
            without_action = ns.get("forecast_without_action_ml")
            with_strategy = ns.get("forecast_with_strategy_ml")
            if without_action is not None and with_strategy is not None and ns.get("action") == "open_selected":
                message = (
                    f"Ohne Nachtlüftung werden bis morgen früh etwa {_finite_float(without_action):+.0f} ml erwartet; "
                    f"mit der empfohlenen Strategie etwa {_finite_float(with_strategy):+.0f} ml. {instruction}"
                )
            elif without_action is not None:
                message = f"Bei geschlossenen Fenstern werden bis morgen früh etwa {_finite_float(without_action):+.0f} ml erwartet. {instruction}"
            else:
                message = f"Bis morgen früh werden voraussichtlich etwa {round(_finite_float(data.get('overnight_forecast_ml', 0), 0.0))} ml Feuchtigkeit hinzukommen. {instruction}"
            if detail and detail not in message:
                message += f" {detail}"
            if store.data.get("last_night_event_date") != today:
                store.data["last_night_event_date"] = today
                publish("night", "FreshAirIQ · Nachtstrategie", message, None, {"kind": str(ns.get("action") or "")})
                changed = True
            if push_enabled and options.get("notify_night") and not suppress_at_night and await _send(hass, options, "FreshAirIQ · Nachtstrategie", message):
                store.data["last_night_notification_date"] = today
                changed=True

    return changed
