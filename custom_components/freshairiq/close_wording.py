"""What "close" means for a room (0.26.4.10).

A room aired only by its exhaust fan has nothing to close – the action is to
switch the fan off, and only when that room itself is advised to stop (moisture
would come in). Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from typing import Any

from .fan_automation import auto_start, auto_stop, fan_automation


def airing_running(room: Any) -> bool:
    """True while the room is really being aired.

    After the window is closed the session lives on for its final measurement
    (``session_finalization_pending``); the room is no longer aired then and must
    not be told to keep ventilating or to close.
    """
    return isinstance(room, dict) and bool(room.get("active")) and not bool(room.get("session_finalization_pending"))


def fan_only(room: Any) -> bool:
    """True when the room's running airing is the exhaust fan alone."""
    if not isinstance(room, dict):
        return False
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    if not actuators.get("mechanical_exhaust_active"):
        return actuators.get("ventilation_type") == "mechanical_exhaust" and not actuators.get("window_open")
    return not bool(actuators.get("window_open"))


def _name(room: dict[str, Any]) -> str:
    return str(room.get("name") or room.get("key") or "")


def close_instruction(rooms: list[Any], fallback: str = "Geöffnete Fenster", *, joiner: str = " + ", all_rooms: bool = False) -> str:
    """German instruction, e.g. "Bad schließen · Lüfter in Garage ausschalten".

    A fan-only room is named only if it is itself advised to stop
    (``close_recommended``), unless ``all_rooms`` asks for every room.
    """
    picked = [r for r in rooms if isinstance(r, dict)]
    if not all_rooms:
        picked = [r for r in picked if not fan_only(r) or r.get("close_recommended")] or picked
    windows = [_name(r) for r in picked if not fan_only(r) and _name(r)]
    fans = [_name(r) for r in picked if fan_only(r) and not auto_stop(r) and _name(r)]
    # 0.26.5.4: a fan FreshAirIQ switched on is switched off by FreshAirIQ
    automatic = [_name(r) for r in picked if fan_only(r) and auto_stop(r) and _name(r)]
    parts = []
    if windows:
        parts.append(f"{joiner.join(windows)} schließen")
    if fans:
        parts.append(f"Lüfter in {joiner.join(fans)} ausschalten")
    if automatic:
        parts.append(f"FreshAirIQ beendet die automatische Lüftung in {joiner.join(automatic)}")
    return " · ".join(parts) or f"{fallback} schließen"


def area_close_instruction(area: str, rooms: list[Any]) -> str:
    """"Erdgeschoss schließen", plus fans that must stop; fans alone are named."""
    picked = [r for r in rooms if isinstance(r, dict)]
    if picked and all(fan_only(r) for r in picked):
        return close_instruction(picked)
    fans = [_name(r) for r in picked if fan_only(r) and r.get("close_recommended") and not auto_stop(r) and _name(r)]
    return f"{area} schließen" + (f" · Lüfter in {' + '.join(fans)} ausschalten" if fans else "")


def keep_instruction(rooms: list[Any], remaining_min: float | None) -> str:
    """"Bad offen lassen · Lüfter in Garage laufen lassen · noch ca. 4 min" (no time without a target)."""
    picked = [r for r in rooms if isinstance(r, dict)]
    windows = [_name(r) or "Raum" for r in picked if not fan_only(r)]
    fans = [_name(r) or "Raum" for r in picked if fan_only(r) and not auto_start(r)]
    automatic = [_name(r) or "Raum" for r in picked if fan_only(r) and auto_start(r)]
    parts = []
    if windows:
        parts.append(f"{' + '.join(windows)} offen lassen")
    if fans:
        parts.append(f"Lüfter in {' + '.join(fans)} laufen lassen")
    if automatic:
        parts.append(f"Automatische Lüftung in {' + '.join(automatic)} läuft")
    text = " · ".join(parts) or "Weiterlüften"
    return text if remaining_min is None else f"{text} · noch ca. {max(round(remaining_min), 1)} min"


def fan_stop_message(room: Any) -> str:
    """Push text for a fan that should stop, worded by cause."""
    try:
        delta = float(room.get("delta_g_m3")) if isinstance(room, dict) else None
    except (TypeError, ValueError):
        delta = None
    if auto_stop(room):
        return "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung."
    # 0.26.5.4: the fan draws its air from the neighbouring room when one is configured
    neighbour = isinstance(room, dict) and room.get("reference_path") == "neighbour_room"
    failed = fan_automation(room).get("state") == "failed"
    return _FAN_STOP_TEXT[(neighbour, delta is not None and delta < 0, failed)]


_FAN_STOP_TEXT = {
    (False, True, False): "Die Außenluft ist gerade feuchter als die Raumluft. Lüfter ausschalten.",
    (False, False, False): "Die Außenluft ist kaum noch trockener als die Raumluft. Lüfter ausschalten.",
    (True, True, False): "Die Zuluft aus dem Nebenraum ist gerade feuchter als die Raumluft. Lüfter ausschalten.",
    (True, False, False): "Die Zuluft aus dem Nebenraum ist kaum noch trockener als die Raumluft. Lüfter ausschalten.",
    (False, True, True): "Die Außenluft ist gerade feuchter als die Raumluft. Automatisches Ausschalten hat nicht geklappt. Lüfter ausschalten.",
    (False, False, True): "Die Außenluft ist kaum noch trockener als die Raumluft. Automatisches Ausschalten hat nicht geklappt. Lüfter ausschalten.",
    (True, True, True): "Die Zuluft aus dem Nebenraum ist gerade feuchter als die Raumluft. Automatisches Ausschalten hat nicht geklappt. Lüfter ausschalten.",
    (True, False, True): "Die Zuluft aus dem Nebenraum ist kaum noch trockener als die Raumluft. Automatisches Ausschalten hat nicht geklappt. Lüfter ausschalten.",
}


def house_handled_by_automation(kind: Any, room_keys: Any, rooms: Any) -> bool:
    """0.26.5.4: every room of a house close/ventilate is a fan FreshAirIQ switches itself."""
    kind = str(kind or "")
    keys = [str(k) for k in (room_keys or [])]
    picked = [rooms.get(k) for k in keys] if isinstance(rooms, dict) else []
    if not picked or not all(isinstance(r, dict) for r in picked):
        return False
    if kind == "close":
        return all(fan_only(r) and auto_stop(r) for r in picked)
    if kind in {"ventilate", "start"}:
        return all(auto_start(r) and not (r.get("configured_actuators") or {}).get("window_open") for r in picked)
    return False


FAN_ON_HINT = "Ablüfter einschalten"
_NO_OPENING_REASON = "No opening is assigned to this room; ventilate it via a connected room"


def no_opening_wording(rooms: dict[str, Any], connections: dict[str, set[str]]) -> None:
    """0.26.5.4 (support case): how a room without a window contact is aired.

    The room action stays "Ventilate indirectly" (nothing to open, nothing
    directly actionable for the house). Only the wording says the real air
    path: the room's own exhaust fan, the configured open connection, or –
    when neither is known – no invented connection.
    """
    for key, room in rooms.items():
        if not isinstance(room, dict) or room.get("action") != "Ventilate indirectly" or int(room.get("contact_count") or 0):
            continue
        actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
        linked = sorted(_name(rooms[k]) for k in connections.get(str(key), set()) if isinstance(rooms.get(k), dict))
        if actuators.get("exhaust_fan"):
            reason = "No window is assigned to this room; switch on its exhaust fan"
            if not actuators.get("mechanical_exhaust_active"):
                room["action_hint"] = FAN_ON_HINT
        elif linked:
            reason = f"No window is assigned to this room; it is aired through the open connection to {' + '.join(linked)}"
        else:
            reason = "No window or open connection is assigned to this room; air it through a neighbouring room if possible"
        if room.get("reason") == _NO_OPENING_REASON:
            room["reason"] = reason
