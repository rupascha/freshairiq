"""Occupancy/presence model for FreshAirIQ.

The model deliberately separates *configured household size* from *currently
expected occupancy*.  Tracked Home Assistant ``person``/``device_tracker``
entities can remove absent residents from short-term and night moisture priors,
while residents without a tracker remain supported.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

_UNKNOWN_STATES = {"", "unknown", "unavailable", "none", "null"}


def _unique_entities(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []
    result: list[str] = []
    for value in values:
        entity_id = str(value or "").strip()
        if entity_id and entity_id not in result:
            result.append(entity_id)
    return result


def _state_kind(value: Any) -> str:
    """Map HA presence state to ``home`` / ``away`` / ``unknown``."""
    if value is None:
        return "unknown"
    state = str(getattr(value, "state", value) or "").strip().lower()
    if state in _UNKNOWN_STATES:
        return "unknown"
    if state == "home":
        return "home"
    # person/device_tracker states other than home represent a zone or away.
    return "away"


def resolve_occupancy(
    options: dict[str, Any],
    state_getter: Callable[[str], Any],
) -> dict[str, Any]:
    """Return configured, detected and forecast occupancy.

    Residents with no assigned presence entity are intentionally allowed.  By
    default they follow the household when at least one reliable tracked
    resident exists: if every known tracker is away, untracked residents are
    also treated as away.  This is useful for children without phones.  The
    behaviour can be disabled with ``untracked_follow_household``.

    Unknown/unavailable trackers contribute 0.5 person to the probabilistic
    forecast and reduce the reported presence confidence instead of causing a
    hard and potentially wrong home/away flip.
    """
    configured_adults = max(int(options.get("adult_occupants", 0) or 0), 0)
    configured_children = max(int(options.get("child_occupants", 0) or 0), 0)
    adult_entities = _unique_entities(options.get("adult_presence_entities", []))[:configured_adults]
    child_entities = _unique_entities(options.get("child_presence_entities", []))[:configured_children]

    def counts(entities: list[str]) -> tuple[int, int, int]:
        kinds = [_state_kind(state_getter(entity_id)) for entity_id in entities]
        return kinds.count("home"), kinds.count("away"), kinds.count("unknown")

    ah, aa, au = counts(adult_entities)
    ch, ca, cu = counts(child_entities)
    untracked_adults = max(configured_adults - len(adult_entities), 0)
    untracked_children = max(configured_children - len(child_entities), 0)

    known_home = ah + ch
    known_away = aa + ca
    known_tracked = known_home + known_away
    follow = bool(options.get("untracked_follow_household", True))
    guests_adults = max(int(round(float(options.get("guest_adults", 0) or 0))), 0)
    guests_children = max(int(round(float(options.get("guest_children", 0) or 0))), 0)

    # Guests explicitly entered by the user prove that somebody is present.
    household_home_signal = known_home > 0 or (guests_adults + guests_children) > 0
    household_away_signal = known_tracked > 0 and known_home == 0 and not household_home_signal
    untracked_factor = 0.0 if follow and household_away_signal else 1.0

    expected_adults = ah + au * 0.5 + untracked_adults * untracked_factor + guests_adults
    expected_children = ch + cu * 0.5 + untracked_children * untracked_factor + guests_children

    tracked_total = len(adult_entities) + len(child_entities)
    untracked_total = untracked_adults + untracked_children
    configured_total = configured_adults + configured_children
    if configured_total <= 0:
        confidence = 100
    else:
        # Known trackers are strongest evidence; untracked residents are useful
        # but explicitly less certain, and unknown trackers are weakest.
        evidence = known_tracked * 1.0 + (au + cu) * 0.35 + untracked_total * (0.60 if follow else 0.45)
        confidence = int(round(min(max(evidence / configured_total * 100.0, 20.0), 100.0)))

    # Soft sensor fusion. A single motion event never becomes a hard person.
    # Pet-safe sensors are a specialized subset in the UI, but they are also
    # valid soft presence inputs on their own. Merge both lists so selecting a
    # sensor only as "pet-safe" can never make it silently ineffective.
    pet_safe_entities = _unique_entities(options.get("pet_safe_presence_entities", []))
    soft_entities = _unique_entities([
        *(options.get("presence_sensor_entities", []) or []),
        *pet_safe_entities,
    ])
    pet_safe = set(pet_safe_entities)
    pets = bool(options.get("pets_in_household", False))
    active_soft = []
    for entity_id in soft_entities:
        state = state_getter(entity_id)
        raw = str(getattr(state, "state", state) or "").lower()
        if raw in {"on", "home", "occupied", "detected", "true"}:
            active_soft.append(entity_id)
    soft_score = 0.0
    for entity_id in active_soft:
        if entity_id in pet_safe:
            soft_score += 0.45
        else:
            soft_score += 0.12 if pets else 0.25
    soft_score = min(soft_score, 0.85)
    if household_away_signal and soft_score > 0:
        # Evidence may restore probability for untracked residents, but cannot
        # manufacture more people than are configured.
        expected_untracked = min(untracked_adults + untracked_children, soft_score)
        if untracked_adults + untracked_children > 0:
            share_a = untracked_adults / (untracked_adults + untracked_children)
            expected_adults += expected_untracked * share_a
            expected_children += expected_untracked * (1.0-share_a)
        confidence = max(20, confidence - 10)

    return {
        "configured_adults": configured_adults,
        "configured_children": configured_children,
        "configured_total": configured_total,
        "tracked_adults": len(adult_entities),
        "tracked_children": len(child_entities),
        "tracked_total": tracked_total,
        "home_adults": ah,
        "home_children": ch,
        "away_adults": aa,
        "away_children": ca,
        "unknown_adults": au,
        "unknown_children": cu,
        "untracked_adults": untracked_adults,
        "untracked_children": untracked_children,
        "guest_adults": guests_adults,
        "guest_children": guests_children,
        "expected_adults": round(expected_adults, 2),
        "expected_children": round(expected_children, 2),
        "expected_total": round(expected_adults + expected_children, 2),
        "presence_confidence": confidence,
        "untracked_follow_household": follow,
        "all_known_trackers_away": household_away_signal,
        "presence_sensor_count": len(soft_entities),
        "active_presence_sensors": active_soft,
        "soft_presence_score": round(soft_score, 2),
        "pets_in_household": pets,
        "presence_explanation": (
            "Mindestens ein primärer Tracker ist zuhause; Bewohner ohne Tracker werden als zuhause angenommen." if known_home > 0 else
            "Alle verlässlichen primären Tracker sind außer Haus; Bewohner ohne Tracker werden grundsätzlich als abwesend angenommen, weiche Präsenzsignale können die Wahrscheinlichkeit vorsichtig erhöhen." if household_away_signal else
            "Trackerzustände sind unvollständig; FreshAirIQ rechnet vorsichtig mit Wahrscheinlichkeiten statt einer harten An-/Abwesenheit."
        ),
    }
