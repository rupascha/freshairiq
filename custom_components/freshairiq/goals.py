"""Multi-goal ventilation evaluation for FreshAirIQ.

Pure logic: humidity, CO2 and thermal comfort are evaluated in parallel. User
priority resolves soft conflicts; hard protection can always recommend closing.
"""
from __future__ import annotations
from math import isfinite
from typing import Any

GOALS = ("humidity", "co2", "temperature")

def _f(v: Any, default: float | None = None) -> float | None:
    try:
        x=float(v)
        return x if isfinite(x) else default
    except (TypeError,ValueError): return default

def normalise_priorities(value: Any, available: Any = None) -> list[str]:
    """Return only goals that actually exist for this room.

    Missing optional sensors/features never create phantom priorities. Stored
    legacy priorities are harmless because unavailable goals are filtered here.
    """
    allowed = [x for x in (available if isinstance(available, (list, tuple, set)) else GOALS) if x in GOALS]
    vals = value if isinstance(value, list) else []
    out = [str(x) for x in vals if str(x) in allowed]
    return out + [x for x in allowed if x not in out]

def effective_temperature_target(*, manual: Any=None, session_target: Any=None, thermostat_target: Any=None, fallback: Any=None) -> tuple[float|None,str]:
    """Resolve a plausible comfort target without accepting frost-protection values."""
    for value, source in ((manual,"manual"),(session_target,"session"),(thermostat_target,"thermostat"),(fallback,"fallback")):
        x=_f(value)
        if x is not None and 12.0 <= x <= 30.0:
            return round(x,1),source
    return None,"none"

def evaluate_goals(*, humidity: Any, target_rh: Any, co2: Any, co2_warn: Any,
                   temperature: Any, temperature_target: Any, temperature_rate_c_min: Any=None,
                   co2_rate_ppm_min: Any=None, humidity_rate_pct_min: Any=None,
                   priorities: Any=None, available_goals: Any=None, hard_close: bool=False) -> dict[str,Any]:
    rh=_f(humidity); rh_target=_f(target_rh,55.0) or 55.0
    c=_f(co2); c_target=_f(co2_warn,1000.0) or 1000.0
    t=_f(temperature); tt=_f(temperature_target)
    rows=[]
    def eta(delta: float|None, rate: float|None) -> float|None:
        if delta is None or delta <= 0: return 0.0
        r=_f(rate)
        if r is None or r >= -0.001: return None
        return round(min(max(delta/abs(r),0.0),240.0),1)
    rows.append({"id":"humidity","active":rh is not None,"reached":rh is not None and rh <= rh_target,
                 "value":rh,"target":rh_target,"eta_min":eta(None if rh is None else rh-rh_target, humidity_rate_pct_min)})
    rows.append({"id":"co2","active":c is not None,"reached":c is not None and c <= c_target,
                 "value":c,"target":c_target,"eta_min":eta(None if c is None else c-c_target, co2_rate_ppm_min)})
    rows.append({"id":"temperature","active":t is not None and tt is not None,"reached":t is not None and tt is not None and t <= tt+0.3,
                 "value":t,"target":tt,"eta_min":eta(None if t is None or tt is None else t-tt, temperature_rate_c_min)})
    active_ids = [r["id"] for r in rows if r["active"]]
    allowed = [g for g in (available_goals if isinstance(available_goals, (list, tuple, set)) else active_ids) if g in active_ids]
    order=normalise_priorities(priorities, allowed); rank={g:i for i,g in enumerate(order)}
    rows.sort(key=lambda r: rank.get(r["id"], 99))
    open_goals=[r for r in rows if r["active"] and not r["reached"]]
    return {"priorities":order,"goals":rows,"all_active_goals_reached":not open_goals,
            "highest_open_goal":open_goals[0]["id"] if open_goals else None,
            "hard_close":bool(hard_close)}
