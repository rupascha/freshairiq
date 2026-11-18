"""IQ2 runtime helpers over the room memory (pure: no Home Assistant; see ``iq2`` for the model itself)."""
from __future__ import annotations

from typing import Any

from . import iq2

PHYSICS_FALLBACK_RATE = 0.03
_IQ2_DEFAULT_RATES = {iq2.GENERAL: 0.03, "open": 0.03, "tilted": 0.015, "cross": 0.04}
EXHAUST_MODE = "mechanical_exhaust"


def iq2_base_rate(mem: dict[str, Any], mode: str) -> float:
    """Start value of a way of airing: the shipped start model when it seeded this room, else the built-in value."""
    seeded = (mem.get("start_model") or {}).get("rates") if isinstance(mem.get("start_model"), dict) else None
    lookup = "open" if mode == iq2.GENERAL else mode
    try:
        return float((seeded or {}).get(lookup) or _IQ2_DEFAULT_RATES.get(mode, 0.03))
    except (TypeError, ValueError):
        return _IQ2_DEFAULT_RATES.get(mode, 0.03)


def iq2_room_parameters(mem: dict[str, Any], house: Any, *, mode: Any, legacy_rate: float, has_contact: bool,
                        force_physics: bool) -> tuple[dict[str, Any], bool]:
    """(parameters in force, room memory changed).

    Rooms without an opening keep their passive model. An airing by the exhaust fan alone (window closed) keeps the
    exhaust model its own sessions learned: the replaced air is not the outdoor reference air of the window model.
    """
    if not has_contact or mode == EXHAUST_MODE:
        return {"rate": legacy_rate, "moisture_share": 1.0, "thermal_share": 1.0, "level": "passive" if not has_contact else "exhaust_model",
                "mode": None, "active": False}, False
    key = str(mode) if mode in iq2.MODES else iq2.GENERAL
    seeded = False
    if not (isinstance(mem.get("iq2"), dict) and mem["iq2"].get("schema") == iq2.SCHEMA):
        rows = mem.get("opening_learning") if isinstance(mem.get("opening_learning"), dict) else {}
        legacy = {iq2.GENERAL: (mem.get("learning_rate"), mem.get("learning_samples"), iq2_base_rate(mem, iq2.GENERAL))}
        legacy.update({m: (row.get("rate"), row.get("samples"), iq2_base_rate(mem, m)) for m, row in rows.items() if isinstance(row, dict)})
        mem["iq2"] = iq2.room_state(mem.get("iq2"), legacy=legacy)
        seeded = True
    params = dict(iq2.parameters(mem["iq2"], house, key, iq2_base_rate(mem, key)), active=True)
    if force_physics:
        # objective validation shows a regression: the conservative global model, no learned terms
        params.update(rate=PHYSICS_FALLBACK_RATE, moisture_share=iq2.MOISTURE_SHARE_PRIOR, thermal_share=iq2.THERMAL_SHARE_PRIOR, level="fallback")
    elif (mem["iq2"].get("score") or {}).get("rollback"):
        # the room's own scored forecasts were worse than the reference model: back to the reference until it recovers
        params.update(rate=legacy_rate, moisture_share=1.0, level="rollback")
    return params, seeded


def update_goal_history(mem: dict[str, Any], result: Any) -> bool:
    """C1 (IQ2): the airing's goal history – reached once, kept while the goals stay inside their hysteresis."""
    reached = bool(result.goals_reached_now or (mem.get("session_goals_reached") and result.goals_in_band))
    if reached == bool(mem.get("session_goals_reached")):
        return False
    mem["session_goals_reached"] = reached
    return True


def iq2_interval_physics(params: Any, mem: dict[str, Any], *, prev_ah: float, prev_temp: Any, ref_ah: float, ref_t: float,
                         rate: float, minutes: float, bonus: float, volume: float) -> tuple[float, float | None]:
    """(modelled moisture leaving the room air, modelled temperature change) between two observations of an airing."""
    p = params if isinstance(params, dict) else {}
    removed = (prev_ah - iq2.relax(prev_ah, ref_ah, mem.get("session_start_ah"), rate, minutes, bonus, p.get("moisture_share", 1.0))) * volume
    if prev_temp is None:
        return removed, None
    return removed, iq2.relax(float(prev_temp), ref_t, mem.get("session_start_temp"), rate, minutes, bonus, p.get("thermal_share", 1.0)) - float(prev_temp)


def iq2_start_context(params: Any, mem: dict[str, Any], house: Any, validation_id: Any) -> dict[str, Any] | None:
    """I03: the IQ2 model of a start forecast, frozen with it – the parameters really in force (learned, physics
    fallback or rollback) together with the learned ones and the reference model."""
    p = params if isinstance(params, dict) else {}
    if not p.get("active") or not isinstance(mem.get("iq2"), dict):
        return None
    mode = p.get("mode") if p.get("mode") in iq2.MODES else iq2.GENERAL
    return dict(iq2.start_model(mem["iq2"], house, mode, iq2_base_rate(mem, mode), mem.get("learning_rate"), effective=p),
                validation_id=validation_id)


def iq2_forecast_arguments(params: Any, mem: dict[str, Any], *, running: bool, current_ah: float) -> dict[str, Any]:
    """Shares and buffer anchors of the forecast (the anchor is the room state when the airing started)."""
    p = params if isinstance(params, dict) else {}
    share = float(p.get("moisture_share", 1.0))
    if not running:
        return {"moisture_air_share": share, "thermal_air_share": float(p.get("thermal_share", 1.0))}
    start_ah, start_temp = mem.get("session_start_ah"), mem.get("session_start_temp")
    return {
        "moisture_air_share": iq2.session_share(share, start=start_ah, now=current_ah, source=mem.get("session_start_source_ah")),
        "thermal_air_share": float(p.get("thermal_share", 1.0)),
        "anchor_ah": float(start_ah) if start_ah is not None else None,
        "anchor_temp_c": float(start_temp) if start_temp is not None else None,
    }
