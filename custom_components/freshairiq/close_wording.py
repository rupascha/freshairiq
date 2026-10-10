"""What "close" means for a room (0.26.4.10).

A room aired only by its exhaust fan has nothing to close – the action is to
switch the fan off, and only when that room itself is advised to stop (moisture
would come in). Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from typing import Any


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
    fans = [_name(r) for r in picked if fan_only(r) and _name(r)]
    parts = []
    if windows:
        parts.append(f"{joiner.join(windows)} schließen")
    if fans:
        parts.append(f"Lüfter in {joiner.join(fans)} ausschalten")
    return " · ".join(parts) or f"{fallback} schließen"


def area_close_instruction(area: str, rooms: list[Any]) -> str:
    """"Erdgeschoss schließen", plus fans that must stop; fans alone are named."""
    picked = [r for r in rooms if isinstance(r, dict)]
    if picked and all(fan_only(r) for r in picked):
        return close_instruction(picked)
    fans = [_name(r) for r in picked if fan_only(r) and r.get("close_recommended") and _name(r)]
    return f"{area} schließen" + (f" · Lüfter in {' + '.join(fans)} ausschalten" if fans else "")


def keep_instruction(rooms: list[Any], remaining_min: float | None) -> str:
    """"Bad offen lassen · Lüfter in Garage laufen lassen · noch ca. 4 min" (no time without a target)."""
    picked = [r for r in rooms if isinstance(r, dict)]
    windows = [_name(r) or "Raum" for r in picked if not fan_only(r)]
    fans = [_name(r) or "Raum" for r in picked if fan_only(r)]
    parts = []
    if windows:
        parts.append(f"{' + '.join(windows)} offen lassen")
    if fans:
        parts.append(f"Lüfter in {' + '.join(fans)} laufen lassen")
    text = " · ".join(parts) or "Weiterlüften"
    return text if remaining_min is None else f"{text} · noch ca. {max(round(remaining_min), 1)} min"


def fan_stop_message(room: Any) -> str:
    """Push text for a fan that should stop, worded by cause."""
    try:
        delta = float(room.get("delta_g_m3")) if isinstance(room, dict) else None
    except (TypeError, ValueError):
        delta = None
    if delta is not None and delta < 0:
        return "Die Außenluft ist gerade feuchter als die Raumluft. Lüfter ausschalten."
    return "Die Außenluft ist kaum noch trockener als die Raumluft. Lüfter ausschalten."
