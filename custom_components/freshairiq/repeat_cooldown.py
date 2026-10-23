"""When a just-aired room may be asked to air again (pure, 0.26.5.3, GitHub #15).

After a close, a room is not recommended again for ``repeat_recommendation_cooldown_min``
(120 min) unless something really changed. The mould exception used the
*warning* level (80 %): a small, chronically humid bathroom stays above it all
the time, so the cooldown never applied and the room flapped between "close"
and "air again" all morning. Now only these lift the cooldown:

* the surface humidity reaches the critical level,
* it rose clearly (``SURFACE_RISE_PCT``) since the first evaluation after the close,
* CO₂ reaches its critical level
  (a strong new moisture source and clearly drier weather stay separate reasons).
"""
from __future__ import annotations

from typing import Any

SURFACE_RISE_PCT = 3.0


def remember_close_surface_rh(mem: dict[str, Any], surface_rh: float) -> bool:
    """Store the surface humidity of the first evaluation after each close; True if stored."""
    ended = mem.get("last_ventilation_ended_at")
    if not ended or mem.get("repeat_surface_rh_close_id") == ended:
        return False
    mem["repeat_surface_rh_close_id"] = ended
    mem["repeat_surface_rh_at_close"] = round(float(surface_rh), 1)
    return True


def repeat_cooldown_urgent(*, surface_rh: float, surface_rh_at_close: Any, co2: Any, options: dict[str, Any]) -> bool:
    if surface_rh >= float(options.get("mould_critical_surface_rh", 90.0)):
        return True
    if co2 is not None and co2 >= float(options.get("co2_critical", 1400.0)):
        return True
    try:
        baseline = float(surface_rh_at_close)
    except (TypeError, ValueError):
        return False
    return surface_rh >= float(options.get("mould_warn_surface_rh", 80.0)) and surface_rh - baseline >= SURFACE_RISE_PCT
