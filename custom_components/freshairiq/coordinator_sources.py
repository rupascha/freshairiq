"""Home Assistant state readers used by the coordinator (sensors, weather, fans, covers)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_CONTACT_COVERS
from .climate_sources import entity_ids
from .outdoor_air import plausible_pm25
from .robustness import finite_float


def _entity_active(hass: HomeAssistant, entity_id: str | list[str] | tuple[str, ...] | None) -> bool:
    """Return whether any configured mechanical ventilation entity is active.

    Legacy scalar values remain supported; new configurations may contain
    multiple fans or fan-stage entities for one room.
    """
    entity_ids = [entity_id] if isinstance(entity_id, str) else list(entity_id or [])
    for current in entity_ids:
        state = hass.states.get(current)
        if state is not None and str(state.state).lower() in {"on", "open", "running", "fan_only", "ventilation"}:
            return True
    return False


def _exhaust_stopped_for_seconds(hass: HomeAssistant, entity_id: str | list[str] | tuple[str, ...] | None, session_started: Any, now: datetime) -> float | None:
    """Return how long ago the exhaust fan stopped, if it stopped during the session.

    A fan-only airing in a room with window contacts ends when the fan stops,
    not when the (long closed) windows were closed. Only called while the room
    is logically closed, i.e. no configured fan is running.
    """
    entity_ids = [entity_id] if isinstance(entity_id, str) else list(entity_id or [])
    changed = [state.last_changed for current in entity_ids if (state := hass.states.get(current)) is not None]
    if not changed:
        return None
    try:
        started = datetime.fromisoformat(str(session_started))
    except (TypeError, ValueError):
        return None
    stopped = max(changed)
    if stopped < started:
        return None
    return max((now - stopped).total_seconds(), 0.0)


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id: return None
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable", "none", ""}: return None
    return finite_float(state.state)


def _pollen_level(hass: HomeAssistant, configured: Any) -> float:
    """Highest valid value of all configured pollen sensors (0.26.4.6).

    A single legacy entity behaves exactly as before; unavailable sensors are
    ignored so one offline sensor cannot hide the others.
    """
    values = [value for value in (_float_state(hass, entity_id) for entity_id in entity_ids(configured)) if value is not None]
    return max(values) if values else 0.0


def _outdoor_pm25_level(hass: HomeAssistant, configured: Any) -> float | None:
    """Highest plausible outdoor PM2.5 value of the configured sensors; None without one."""
    values = [
        value for value in (plausible_pm25(_float_state(hass, entity_id)) for entity_id in entity_ids(configured))
        if value is not None
    ]
    return max(values) if values else None


def _cover_learning_guard(hass: HomeAssistant, room: dict[str, Any], contact_modes: dict[str, str], options: dict[str, Any]) -> dict[str, Any]:
    """Return normalized cover closure and whether current ventilation is clean enough to learn.

    Home Assistant normally reports ``current_position`` as 0=closed/100=open.
    Some installations expose the inverse convention, so the user-selected
    interpretation is normalized here once. Only covers assigned to an opening
    that is physically open/tilted can invalidate that ventilation sample.
    """
    mapping = room.get(CONF_CONTACT_COVERS) if isinstance(room.get(CONF_CONTACT_COVERS), dict) else {}
    zero_means = str(room.get("cover_position_zero_means", options.get("cover_position_zero_means", "closed")) or "closed")
    threshold = min(max(float(options.get("cover_learning_max_closed_percent", 20.0) or 0.0), 0.0), 100.0)
    affected: list[dict[str, Any]] = []
    unknown: list[str] = []
    moving = False
    for contact, mode in contact_modes.items():
        if mode not in {"open", "tilted"}:
            continue
        for entity_id in list(mapping.get(contact) or []):
            state = hass.states.get(str(entity_id))
            if state is not None and str(getattr(state, "state", "")) in {"opening", "closing"}:
                moving = True
                continue  # 0.26.4.9: a shutter on its way is not judged
            raw = finite_float((state.attributes or {}).get("current_position")) if state is not None else None
            if raw is None:
                unknown.append(str(entity_id)); continue
            raw = min(max(float(raw), 0.0), 100.0)
            closed_pct = raw if zero_means == "open" else 100.0 - raw
            if closed_pct > threshold:
                affected.append({"contact": str(contact), "cover": str(entity_id), "position": round(raw, 1), "closed_percent": round(closed_pct, 1)})
    return {"blocked": bool(affected), "threshold": threshold, "zero_means": zero_means, "affected": affected, "unknown": sorted(set(unknown)), "moving": moving}


def _aggregate_state_proxy(hass: HomeAssistant, configured: Any, source: Any) -> Any:
    """Return the original State for one sensor, or a conservative multi-source proxy."""
    ids = entity_ids(configured)
    if len(ids) == 1:
        return hass.states.get(ids[0])
    if source.value is None:
        return None
    from types import SimpleNamespace
    stamp = source.oldest_reported
    return SimpleNamespace(state=str(source.value), last_reported=stamp, last_updated=stamp, last_changed=stamp)


def _state_report_timestamp(state: Any) -> str | None:
    """Return the newest sensor report timestamp with HA-version fallback.

    Home Assistant's ``last_reported`` advances for every state report, even
    when the value is unchanged. Older HA versions may not expose it, so
    ``last_updated`` remains the compatibility fallback.
    """
    if state is None:
        return None
    stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    return stamp.isoformat() if stamp is not None else None


def _weather_values(hass: HomeAssistant, entity_id: str | None) -> tuple[float | None, float | None]:
    if not entity_id: return None, None
    state = hass.states.get(entity_id)
    if state is None: return None, None
    temperature = finite_float(state.attributes.get("temperature"))
    humidity = finite_float(state.attributes.get("humidity"))
    return temperature, humidity


def _weather_wind(hass: HomeAssistant, entity_id: str | None) -> tuple[float | None, float | None]:
    if not entity_id: return None, None
    state = hass.states.get(entity_id)
    if state is None: return None, None
    bearing = state.attributes.get("wind_bearing")
    speed = state.attributes.get("wind_speed")
    bearing = finite_float(bearing)
    speed = finite_float(speed)
    return bearing, speed
