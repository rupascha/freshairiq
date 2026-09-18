"""Notification routing and anti-spam logic for FreshAirIQ."""
from __future__ import annotations
from datetime import datetime, timedelta
import json
import math
from typing import Any

from homeassistant.core import HomeAssistant

from .const import NOTIFY_SCOPE_BOTH, NOTIFY_SCOPE_HOUSE, NOTIFY_SCOPE_ROOM
from .forecast import night_window_hours

def _finite_float(value: Any, default: float = 0.0) -> float:
    """Return a finite float; corrupted/runtime values degrade to a safe default."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _target_service(target: str) -> str:
    return target.split(".", 1)[1] if target.startswith("notify.") else target


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


def _resident_profiles(options: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        raw = options.get("resident_room_profiles") or "{}"
        data = raw if isinstance(raw, dict) else json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    return [p for p in data.values() if isinstance(p, dict) and p.get("notification_targets")]


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
        service = _target_service(value)
        if not hass.services.has_service("notify", service):
            continue
        await hass.services.async_call(
            "notify", service, {"title": title, "message": message}, blocking=False
        )
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
            service = _target_service(value)
            if not hass.services.has_service("notify", service):
                continue
            await hass.services.async_call(
                "notify", service, {"title": title, "message": personal_message}, blocking=False
            )
            sent = True

    for target in options.get("notification_targets") or []:
        value = str(target)
        if not value or value in used:
            continue
        used.add(value)
        service = _target_service(value)
        if not hass.services.has_service("notify", service):
            continue
        await hass.services.async_call(
            "notify", service, {"title": title, "message": message}, blocking=False
        )
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
            service = _target_service(value)
            if hass.services.has_service("notify", service):
                await hass.services.async_call("notify", service, {"title": title, "message": personal}, blocking=False)
                sent = True
    for target in options.get("notification_targets") or []:
        if str(target) in used:
            continue
        service = _target_service(str(target))
        if hass.services.has_service("notify", service):
            await hass.services.async_call("notify", service, {"title": title, "message": message}, blocking=False)
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


async def process_notifications(hass: HomeAssistant, store, data: dict[str, Any], options: dict[str, Any], now: datetime, completed_sessions: list[dict[str, Any]]) -> bool:
    if not options.get("notifications_enabled") or not _has_notification_targets(options):
        return False
    changed = False
    cooldown = max(_finite_float(options.get("notification_cooldown_min", 90), 90.0), 0.0)
    scope = options.get("notification_scope", NOTIFY_SCOPE_HOUSE)
    rooms_raw = data.get("rooms", {})
    rooms = rooms_raw if isinstance(rooms_raw, dict) else {}

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
        if room.get("data_quality") != "ok":
            room_events["sensor"].append(room)
        if room.get("mould_level") in {"High", "Very high"}:
            room_events["mould"].append(room)

    async def emit(event: str, title: str, message: str, room_key: str | None = None) -> bool:
        nonlocal changed
        if room_key and not _allowed_room(room_key, options):
            return True
        key = f"{event}:{room_key or 'house'}"
        if not _due(store, key, now, cooldown):
            return True
        sender_ok = (
            await _send_room_personalised(hass, options, title, message, room_key)
            if room_key
            else await _send(hass, options, title, message)
        )
        if sender_ok:
            _mark_sent(store, key, now)
            changed = True
            return True
        return False

    # Room-scope messages
    if scope in {NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_BOTH}:
        if options.get("notify_ventilate"):
            for r in room_events["Ventilate"]:
                reasons = ' · '.join(r.get('recommendation_reasons') or [])
                await emit("ventilate", f"FreshAirIQ · {r['name']}", f"Jetzt lüften. {reasons}", r["key"])
        if options.get("notify_cooling"):
            for r in room_events["Ventilate for cooling"]:
                await emit("cool", f"FreshAirIQ · {r['name']}", f"Sommerkühlung sinnvoll. {_continuation(r)}", r["key"])
        if options.get("notify_close"):
            for r in room_events["Close"]:
                await emit("close", f"FreshAirIQ · {r['name']}", f"Optimales Lüftungsziel erreicht. {_continuation(r)} Empfehlung: jetzt schließen.", r["key"])
        if options.get("notify_mould"):
            for r in room_events["mould"]:
                await emit("mould", f"FreshAirIQ · {r['name']}", f"Schimmelrisiko {r['mould_level'].lower()} · geschätzte Oberflächenfeuchte {round(r['surface_rh'])} %.", r["key"])
        if options.get("notify_sensor"):
            for r in room_events["sensor"]:
                await emit("sensor", f"FreshAirIQ · {r['name']}", "Messwerte fehlen oder sind unplausibel. Sensoren prüfen.", r["key"])

    # House-scope messages use Recommendation Engine v2. The user receives one
    # coherent action instead of a dump of competing room recommendations.
    if scope in {NOTIFY_SCOPE_HOUSE, NOTIFY_SCOPE_BOTH}:
        iq_raw = data.get("intelligent_recommendation") or {}
        iq = iq_raw if isinstance(iq_raw, dict) else {}
        kind = str(iq.get("kind") or "")
        signature = f"{kind}:{','.join(iq.get('room_keys') or [])}:{iq.get('instruction','')}"
        previous_signature = store.data.get("last_house_recommendation_signature")
        if signature != previous_signature:
            title = f"FreshAirIQ · {iq.get('title', 'Empfehlung')}"
            message_parts = [str(iq.get("instruction") or "").strip(), str(iq.get("summary") or "").strip()]
            reasons = [str(x).strip() for x in (iq.get("reasons") or []) if str(x).strip()]
            if reasons:
                message_parts.append("Warum: " + " · ".join(reasons[:3]))
            if iq.get("secondary"):
                message_parts.append(str(iq.get("secondary")))
            message = " ".join(x for x in message_parts if x)
            enabled = ((kind in {"ventilate", "continue", "pollen_wait"} and options.get("notify_ventilate")) or (kind == "close" and options.get("notify_close")) or (kind == "sensor" and options.get("notify_sensor")))
            handled = True
            event_key = f"iq_{kind}:house"
            if enabled and _due(store, event_key, now, cooldown):
                handled = await _send_personalised(hass, options, title, message, iq)
                if handled:
                    _mark_sent(store, event_key, now)
            if handled:
                store.data["last_house_recommendation_signature"] = signature
                changed = True

    if options.get("notify_learning"):
        for event in completed_sessions:
            if not isinstance(event, dict) or not event.get("key"):
                continue
            if event.get("learning_valid") and _allowed_room(str(event["key"]), options):
                await emit("learning", f"FreshAirIQ · {event['name']}", "Neue gültige Lernprobe übernommen. Das Raum-Modell wurde aktualisiert.", event["key"])

    if options.get("notify_complete"):
        for event in completed_sessions:
            if not isinstance(event, dict) or not event.get("key"):
                continue
            room_key = str(event["key"])
            if not _allowed_room(room_key, options):
                continue
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
            await emit("complete", f"FreshAirIQ · {name}", message, room_key)

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
    if options.get("notify_night") and night_window_enabled and hours_to_night <= 3.0:
        today=now.date().isoformat()
        if store.data.get("last_night_notification_date") != today:
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
            if await _send(hass, options, "FreshAirIQ · Nachtstrategie", message):
                store.data["last_night_notification_date"] = today
                changed=True

    return changed
