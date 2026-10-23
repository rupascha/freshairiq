"""Opening contacts: open/closed state, reference air per opening and wind orientation."""
from __future__ import annotations

from datetime import datetime
from math import cos, pi
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTACT_COVERS,
    CONF_CONTACT_DELAY,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_ROOM_CONTACT,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_COVERS,
    CONF_ROOM_NAME,
    CONF_ROOM_WINDOW_ORIENTATION,
    CONTACT_MODE_ALL,
    CONTACT_MODE_ANY,
    ORIENTATION_UNKNOWN,
)
from .climate_sources import entity_ids
from .coordinator_sources import _float_state
from .model import RoomInput, absolute_humidity, evaluate_room
from .opening_state import normalize_opening_state, stable_state_seconds


def _contact_ids(room: dict[str, Any]) -> list[str]:
    contacts = room.get(CONF_ROOM_CONTACTS)
    if isinstance(contacts, str): return [contacts]
    if isinstance(contacts, list): return [str(x) for x in contacts if x]
    legacy = room.get(CONF_ROOM_CONTACT)
    return [legacy] if legacy else []


def _contact_specific_reference(
    hass: HomeAssistant, room: dict[str, Any], *,
    default_temp_entity: str | None, default_humidity_entity: str | None,
    default_temp: float | None, default_humidity: float | None,
    contact_modes: dict[str, str] | None = None,
) -> tuple[str | None, str | None, float | None, float | None]:
    """Return the conservative reference-air pair for the currently open contacts.

    A room may have openings into different air zones (for example outside and
    a winter garden). Each open contact contributes its own configured pair; an
    unconfigured contact inherits the room/global reference. If several openings
    are open at once, the moistest valid source is used. This is deliberately
    conservative: FreshAirIQ must not promise more dehumidification than the
    least favourable incoming air stream supports.
    """
    temp_map = room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    humidity_map = room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    open_ids = [
        cid for cid in _contact_ids(room)
        if ((contact_modes or {}).get(cid) in {"open", "tilted"})
        if cid in (contact_modes or {})
    ] if contact_modes is not None else [
        cid for cid in _contact_ids(room) if _open_seconds(hass, cid, dt_util.utcnow()) is not None
    ]
    if not open_ids:
        return default_temp_entity, default_humidity_entity, default_temp, default_humidity
    candidates = []
    for cid in open_ids:
        contact_te = str(temp_map.get(cid) or "").strip() or None
        contact_he = str(humidity_map.get(cid) or "").strip() or None
        local_configured = bool(contact_te or contact_he)
        # A local reference is atomic: never mix e.g. Wintergarten temperature
        # with outdoor humidity. More importantly, an explicitly configured
        # local source that is unavailable must NEVER silently turn into outside
        # air. With several simultaneously open paths, one unknown source makes
        # the combined incoming air unknown as well, so fail closed for the room.
        if contact_te and contact_he:
            te, he = contact_te, contact_he
            tv, hv = _float_state(hass, te), _float_state(hass, he)
        elif local_configured:
            return contact_te, contact_he, None, None
        else:
            te, he = default_temp_entity, default_humidity_entity
            tv, hv = default_temp, default_humidity
        if tv is None or hv is None or not (-30 < tv < 60 and 0 <= hv <= 100):
            return te, he, None, None
        candidates.append((absolute_humidity(tv, hv), te, he, tv, hv))
    _ah, te, he, tv, hv = max(candidates, key=lambda item: item[0])
    return te, he, tv, hv


def _opening_assessments(
    hass: HomeAssistant, room: dict[str, Any], *,
    room_temperature: float, room_humidity: float, volume_m3: float,
    default_temp_entity: str | None, default_humidity_entity: str | None,
    default_temp: float | None, default_humidity: float | None,
    learning_rate: float, learning_samples: int, co2: float | None, pollen: float,
    options: dict[str, Any], wind_bearing: float | None, wind_speed: float | None,
    contact_modes: dict[str, str] | None = None,
    cooling_allowed: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate every configured opening against its own incoming air.

    This is a side-channel decision aid only: it does not alter the canonical
    room result, forecast, learning state or session physics. Each opening is
    run through the same pure ``evaluate_room`` model with the same learned
    exchange rate, but with that opening's source-air pair and orientation.
    """
    temp_map = room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    humidity_map = room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    orientation_map = room.get(CONF_CONTACT_ORIENTATIONS) or {}
    fallback_orientation = str(room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN))
    wind_enabled = bool(options.get("wind_orientation_enabled", True))
    out: list[dict[str, Any]] = []

    for contact in _contact_ids(room):
        local_te = str(temp_map.get(contact) or "").strip() or None
        local_he = str(humidity_map.get(contact) or "").strip() or None
        local_configured = bool(local_te or local_he)
        pair_complete = bool(local_te and local_he)
        if pair_complete:
            te, he = local_te, local_he
            source_t, source_rh = _float_state(hass, te), _float_state(hass, he)
            source_label = "lokale Referenz"
        elif local_configured:
            # Existing malformed legacy data must never be mixed with outdoor
            # values. Mark the opening unavailable until the pair is completed.
            te, he = local_te, local_he
            source_t, source_rh = None, None
            source_label = "unvollständige lokale Referenz"
        else:
            te, he = default_temp_entity, default_humidity_entity
            source_t, source_rh = default_temp, default_humidity
            source_label = "Außen-/Raumreferenz"

        state = hass.states.get(contact)
        friendly = str((state.attributes.get("friendly_name") if state else None) or contact)
        orientation = str(orientation_map.get(contact, fallback_orientation))
        airflow = _orientation_factor(orientation, wind_bearing, wind_speed, wind_enabled)
        available = (
            source_t is not None and source_rh is not None
            and -30 < float(source_t) < 60 and 0 <= float(source_rh) <= 100
        )
        row: dict[str, Any] = {
            "entity_id": contact,
            "name": friendly,
            "is_open": ((contact_modes or {}).get(contact) in {"open", "tilted"}) if contact_modes is not None else (_open_seconds(hass, contact, dt_util.utcnow()) is not None),
            "orientation": orientation,
            "airflow_factor": airflow,
            "source_kind": "local_reference" if pair_complete else "default_reference",
            "source_label": source_label,
            "reference_temperature_entity": te,
            "reference_humidity_entity": he,
            "available": bool(available),
        }
        if not available:
            row["reason"] = "Referenzsensoren fehlen oder liefern keine gültigen Werte"
            out.append(row)
            continue

        simulated = evaluate_room(
            RoomInput(
                key=str(room.get("key") or "opening"),
                name=str(room.get(CONF_ROOM_NAME) or room.get("name") or "Raum"),
                temperature=float(room_temperature), humidity=float(room_humidity),
                reference_temperature=float(source_t), reference_humidity=float(source_rh),
                volume_m3=float(volume_m3), contact_open=False, contact_open_seconds=0.0,
                learning_rate=float(learning_rate), learning_samples=int(learning_samples),
                co2=co2, session_active=False, airflow_factor=airflow, pollen_index=float(pollen),
                cooling_allowed=cooling_allowed,
            ),
            options,
            False,
        )
        row.update({
            "reference_temperature_c": round(float(source_t), 2),
            "reference_humidity_percent": round(float(source_rh), 2),
            "reference_absolute_humidity_g_m3": round(absolute_humidity(float(source_t), float(source_rh)), 3),
            "delta_g_m3": round(float(simulated.delta_g_m3), 3),
            "potential_ml": int(simulated.potential_ml),
            "moisture_effect_next_5_min_ml": int(simulated.moisture_effect_next_5_min_ml),
            "temperature_effect_next_5_min_c": round(float(simulated.temp_next_5_min_c), 3),
            "ventilation_candidate": bool(simulated.ventilation_candidate),
            "cooling_candidate": bool(simulated.cooling_candidate),
            "model_action": str(simulated.action),
        })
        out.append(row)
    return out


def _open_seconds(hass: HomeAssistant, entity_id: str, now: datetime) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or normalize_opening_state(state.state) not in {"open", "tilted"}: return None
    return max(0.0, (now - state.last_changed).total_seconds())


def _room_contacts_known(hass: HomeAssistant, room: dict[str, Any]) -> bool:
    """Return False while HA is still restoring a configured contact after startup."""
    ids = _contact_ids(room)
    if not ids:
        return True
    return all(
        (state := hass.states.get(entity_id)) is not None
        and normalize_opening_state(state.state) != "unknown"
        for entity_id in ids
    )


def _room_physical_opened_at(
    hass: HomeAssistant,
    room: dict[str, Any],
    *,
    contact_modes: dict[str, str] | None = None,
    contact_since: dict[str, datetime] | None = None,
) -> datetime | None:
    """Return the earliest *confirmed* physical opening timestamp for a room.

    Proven three-state contacts must use the same debounced mode/timestamp pair
    as the session lifecycle.  Binary contacts retain their HA raw timestamp.
    """
    opened: list[datetime] = []
    for entity_id in _contact_ids(room):
        state = hass.states.get(entity_id)
        override = (contact_modes or {}).get(entity_id)
        mode = override if override is not None else (normalize_opening_state(state.state) if state is not None else "unknown")
        if mode not in {"open", "tilted"}:
            continue
        changed = (contact_since or {}).get(entity_id) if override is not None else getattr(state, "last_changed", None)
        if isinstance(changed, datetime):
            opened.append(changed)
    return min(opened) if opened else None


def _contact_unknown_for(state: Any, missing_since: datetime, now: datetime) -> float:
    """Seconds a configured contact has been unknown/unavailable (or missing)."""
    since = getattr(state, "last_changed", None) if state is not None else missing_since
    try:
        return max((now - since).total_seconds(), 0.0) if isinstance(since, datetime) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _room_closed_for_seconds(hass: HomeAssistant, room: dict[str, Any], now: datetime, *, contact_modes: dict[str, str] | None = None) -> float | None:
    """Return how long the room has continuously been in its logical closed state.

    The contact mode matters: with ``any`` ventilation ends only when *all*
    contacts are closed, so the newest close transition defines the start of the
    closed state. With ``all`` ventilation ends when *any* required contact is
    closed, so the oldest currently closed contact defines that state. ``None``
    means the room is still logically open (or a contact state is unknown).
    """
    ids = _contact_ids(room)
    if not ids:
        return None
    closed_seconds: list[float] = []
    open_count = 0
    for entity_id in ids:
        state = hass.states.get(entity_id)
        if state is None:
            return None
        normalized = normalize_opening_state(state.state)
        normalized = (contact_modes or {}).get(entity_id, normalized)
        if normalized == "unknown":
            return None
        if normalized in {"open", "tilted"}:
            open_count += 1
            continue
        if normalized != "closed":
            return None
        closed_seconds.append(max(0.0, (now - state.last_changed).total_seconds()))

    mode = room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)
    if mode == CONTACT_MODE_ALL:
        if open_count == len(ids):
            return None
        return max(closed_seconds) if closed_seconds else 0.0
    if open_count:
        return None
    return min(closed_seconds) if closed_seconds else 0.0


def _room_ventilation_state(hass: HomeAssistant, room: dict[str, Any], now: datetime, *, honour_delays: bool = False, contact_modes: dict[str, str] | None = None, contact_since: dict[str, datetime] | None = None) -> tuple[bool, float]:
    ids = _contact_ids(room)
    if not ids: return False, 0.0
    delays = room.get(CONF_CONTACT_DELAYS) or {}
    fallback = int(room.get(CONF_CONTACT_DELAY, 0))
    opened: list[tuple[str, float]] = []
    for entity_id in ids:
        # Explicit three-state contacts are allowed to drive the session only
        # through their debounced/stable mode. Binary contacts have no override
        # and therefore retain the historical immediate start behaviour.
        mode_override = (contact_modes or {}).get(entity_id)
        if mode_override is not None:
            if mode_override not in {"open", "tilted"}:
                continue
            state = hass.states.get(entity_id)
            if state is None:
                continue
            # A debounced mode and its age must come from the same stable
            # transition. During raw open<->tilted movement, HA last_changed
            # already belongs to the candidate state and must not reset the
            # age of the still-active stable state.
            stable_since = (contact_since or {}).get(entity_id)
            if not isinstance(stable_since, datetime):
                stable_since = state.last_changed
            sec = stable_state_seconds(now, stable_since)
        else:
            sec = _open_seconds(hass, entity_id, now)
        if sec is not None:
            opened.append((entity_id, sec))
    mode = room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)

    def ready(item: tuple[str, float]) -> tuple[bool, float]:
        entity_id, sec = item
        delay = float(delays.get(entity_id, fallback)) if honour_delays else 0.0
        return sec >= delay, max(sec - delay, 0.0)

    if mode == CONTACT_MODE_ALL:
        if len(opened) != len(ids): return False, 0.0
        checked = [ready(x) for x in opened]
        if not all(x[0] for x in checked): return False, 0.0
        return True, min(x[1] for x in checked)
    checked = [ready(x) for x in opened]
    elapsed = [x[1] for x in checked if x[0]]
    return (True, max(elapsed)) if elapsed else (False, 0.0)


def _cover_openings(room: dict[str, Any]) -> list[tuple[str, str]]:
    """Every configured cover with the orientation of its opening (room fallback)."""
    fallback = str(room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN))
    orientations = room.get(CONF_CONTACT_ORIENTATIONS) or {}
    mapping = room.get(CONF_CONTACT_COVERS) or {}
    pairs = [
        (cover, str(orientations.get(contact, fallback)))
        for contact, covers in (mapping.items() if isinstance(mapping, dict) else [])
        for cover in entity_ids(covers)
    ]
    return pairs or [(cover, fallback) for cover in entity_ids(room.get(CONF_ROOM_COVERS))]


_ORIENTATION_DEG = {"n": 0, "ne": 45, "e": 90, "se": 135, "s": 180, "sw": 225, "w": 270, "nw": 315}


def _orientation_factor(orientation: str, wind_bearing: float | None, wind_speed: float | None, enabled: bool) -> float:
    """Conservative pressure-side airflow modifier from local wind direction."""
    if not enabled or orientation not in _ORIENTATION_DEG or wind_bearing is None: return 1.0
    speed_weight = min(max((wind_speed or 0.0) / 5.0, 0.0), 1.0)
    delta = abs((_ORIENTATION_DEG[orientation] - wind_bearing + 180) % 360 - 180)
    alignment = cos(delta * pi / 180.0)
    return round(min(max(1.0 + 0.30 * alignment * speed_weight, 0.70), 1.30), 3)


def _room_orientation_factor(hass: HomeAssistant, room: dict[str, Any], now: datetime, wind_bearing: float | None, wind_speed: float | None, enabled: bool, *, contact_modes: dict[str, str] | None = None) -> float:
    """Combine per-contact orientations; while ventilating, only open contacts count."""
    contacts = _contact_ids(room)
    mapping = room.get(CONF_CONTACT_ORIENTATIONS) or {}
    fallback = str(room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN))
    open_contacts = [
        c for c in contacts
        if ((contact_modes or {}).get(c) in {"open", "tilted"})
        if c in (contact_modes or {})
    ] if contact_modes is not None else [c for c in contacts if _open_seconds(hass, c, now) is not None]
    relevant = open_contacts or contacts
    if not relevant:
        return _orientation_factor(fallback, wind_bearing, wind_speed, enabled)
    factors = [_orientation_factor(str(mapping.get(c, fallback)), wind_bearing, wind_speed, enabled) for c in relevant]
    # Multiple openings on different façades should not create an unrealistic
    # wind bonus. Their mean is deliberately conservative; cross ventilation
    # is handled separately by the learned/cross-ventilation model.
    return round(sum(factors) / len(factors), 3)
