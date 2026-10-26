"""Reference air of a room aired by its exhaust fan (0.26.5.3).

An exhaust fan pushes room air outside; the replacement air flows in from the
neighbouring room (door gap, transfer grille), not from outside. When the user
configured the temperature/humidity of that neighbouring room, it is the
reference air while the fan airs the room: the fan runs and no window is open,
or the room has no window contact at all (then the fan is its only way to air).
An open window always uses its own (outdoor or opening-specific) reference.
"""
from __future__ import annotations

from typing import Any

# 0.26.5.4: tells which air "Außen-/Referenzluft" means in the room's reasons
NEIGHBOUR_REFERENCE_REASON = "Vergleichsluft ist die Zuluft aus dem Nebenraum (Ablüfter), nicht die Außenluft"


def exhaust_reference_pair(room: dict[str, Any]) -> tuple[str, str] | None:
    """The configured neighbouring-room sensor pair, or None when incomplete."""
    temperature = str(room.get("exhaust_fan_reference_temperature") or "").strip()
    humidity = str(room.get("exhaust_fan_reference_humidity") or "").strip()
    return (temperature, humidity) if temperature and humidity else None


def exhaust_reference_applies(
    *, fan_configured: bool, fan_active: bool, window_open: bool, has_contacts: bool, auto_start: bool = False,
) -> bool:
    """True when the neighbouring-room air replaces the outdoor/opening reference.

    0.26.5.4: with the fan switched automatically by the recommendation
    (``auto_start``), the fan is the way FreshAirIQ airs the room while no
    window is open – its start is decided on the neighbouring-room air it will
    draw in, not on the outdoor air, so the basis does not switch once it runs.
    """
    if not fan_configured or window_open:
        return False
    return fan_active or not has_contacts or auto_start
