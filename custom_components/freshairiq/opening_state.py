"""Opening-state normalization for binary and explicit three-state contacts."""
from __future__ import annotations
from typing import Any

TILT_STATES = {"tilted", "tilt", "kip", "kipp", "gekippt", "vent", "ventilation"}
OPEN_STATES = {"on", "open", "opening", "opened", "auf", "offen"}
CLOSED_STATES = {"off", "closed", "closing", "shut", "zu", "geschlossen"}
UNKNOWN_STATES = {"unknown", "unavailable", "none", "", "null"}


def normalize_opening_state(raw: Any) -> str:
    value = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in TILT_STATES or "tilt" in value or "kipp" in value:
        return "tilted"
    if value in OPEN_STATES:
        return "open"
    if value in CLOSED_STATES:
        return "closed"
    return "unknown"


def advertises_three_states(entity_id: str, state: Any) -> bool:
    """Detect explicit three-state capability without guessing from duration.

    Binary sensors are deliberately binary. Enum/template helpers are detected
    from their advertised options. A currently observed tilt state is also
    conclusive and can be persisted by the caller for sensors that do not expose
    an options list.
    """
    if str(entity_id).startswith("binary_sensor."):
        return False
    current = normalize_opening_state(getattr(state, "state", None))
    if current == "tilted":
        return True
    attrs = getattr(state, "attributes", {}) or {}
    options = attrs.get("options") or attrs.get("states") or []
    if not isinstance(options, (list, tuple, set)):
        return False
    normalized = {normalize_opening_state(x) for x in options}
    return {"closed", "open", "tilted"}.issubset(normalized)



def opening_contact_profile(hass: Any, entity_ids: list[str], remembered_three_state: set[str] | None = None) -> tuple[dict[str, str], set[str]]:
    """Return normalized state per contact and explicitly proven three-state contacts."""
    remembered = set(remembered_three_state or set())
    proven = set(remembered)
    modes: dict[str, str] = {}
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            modes[entity_id] = "unknown"
            continue
        if advertises_three_states(entity_id, state):
            proven.add(entity_id)
        modes[entity_id] = normalize_opening_state(state.state)
    return modes, proven


def aggregate_opening_mode(modes: dict[str, str]) -> str:
    """Aggregate only for room-level ventilation; preserve mixed open/tilted explicitly."""
    values = list(modes.values())
    active = {v for v in values if v in {"open", "tilted"}}
    if active == {"open", "tilted"}:
        return "mixed"
    if "open" in active:
        return "open"
    if "tilted" in active:
        return "tilted"
    if values and all(v == "closed" for v in values):
        return "closed"
    return "unknown"

def specialist_opening_provenance(modes: dict[str, str], proven_three_state: set[str]) -> tuple[str | None, tuple[str, ...]]:
    """Return a specialist mode only when every active opening is proven three-state.

    A room merely *containing* a three-state contact is not sufficient. Binary or
    otherwise unproven active contacts make the opening geometry ambiguous and
    therefore force the established general learning model.  The returned
    signature pins a specialist session to the exact active proven contacts so a
    later source change cannot silently contaminate the same sub-model.
    """
    active = {entity_id: mode for entity_id, mode in modes.items() if mode in {"open", "tilted"}}
    if not active:
        return None, ()
    if any(entity_id not in proven_three_state for entity_id in active):
        return None, ()
    active_modes = set(active.values())
    if len(active_modes) != 1:
        return None, ()
    mode = next(iter(active_modes))
    signature = tuple(sorted(active))
    return mode, signature


def room_opening_mode(hass: Any, entity_ids: list[str], remembered_three_state: set[str] | None = None) -> tuple[str, set[str]]:
    """Return closed/open/tilted/unknown and newly proven three-state entities."""
    modes, proven = opening_contact_profile(hass, entity_ids, remembered_three_state)
    aggregate = aggregate_opening_mode(modes)
    # Compatibility API historically returned one of four values. Mixed remains
    # physically open here; richer callers should use opening_contact_profile.
    return ("open" if aggregate == "mixed" else aggregate), proven


def stabilise_explicit_mode(current: str, previous: str | None, state_age_seconds: float | None, *, threshold_seconds: float = 3.0) -> tuple[str, bool]:
    """Confirm every explicit three-state transition after a short stable window.

    The timer is based only on Home Assistant's already received state timestamp;
    FreshAirIQ never polls or waits for a battery contact to answer again.  This
    deliberately includes closed -> open/tilted so a handle moving through an
    intermediate state cannot start and misclassify a learning session.
    """
    current = current if current in {"closed", "open", "tilted", "unknown"} else "unknown"
    previous = previous if previous in {"closed", "open", "tilted", "unknown"} else None
    if (
        previous in {"closed", "open", "tilted"}
        and current in {"closed", "open", "tilted"}
        and current != previous
        and state_age_seconds is not None
        and 0 <= state_age_seconds < threshold_seconds
    ):
        return previous, True
    return current, False


def update_passage_pattern(stats: dict[str, Any] | None, *, pulled_shut_evidence: bool) -> dict[str, Any]:
    """Update conservative passage-door behaviour evidence.

    This learns only whether a configured passage opening repeatedly produces
    the characteristic sensor-open/physically-weak pattern. It never rewrites
    the physical contact state. At least three matching observations and >=75%
    matching evidence are required before the pattern is considered learned.
    """
    current = dict(stats or {})
    pulled = max(int(current.get("pulled_shut_events", 0) or 0), 0)
    genuine = max(int(current.get("genuine_open_events", 0) or 0), 0)
    if pulled_shut_evidence:
        pulled = min(pulled + 1, 1000)
    else:
        genuine = min(genuine + 1, 1000)
    total = pulled + genuine
    confidence = pulled / total if total else 0.0
    learned = pulled >= 3 and total >= 3 and confidence >= 0.75
    return {
        "pulled_shut_events": pulled,
        "genuine_open_events": genuine,
        "observations": total,
        "confidence": round(confidence, 3),
        "learned": learned,
    }


def stable_state_seconds(now, stable_since) -> float:
    """Return non-negative age for a confirmed opening state."""
    if stable_since is None:
        return 0.0
    try:
        return max(0.0, (now - stable_since).total_seconds())
    except (TypeError, ValueError, AttributeError):
        return 0.0
