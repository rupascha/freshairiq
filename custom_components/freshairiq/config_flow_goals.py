"""Room goal priorities in the config flows: available goals, ranking form and validation."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

from .const import (
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_DISABLED_GOALS,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_TARGET_TEMPERATURE,
    CONF_ROOM_TARGET_TEMPERATURE_FALLBACK,
    CONF_ROOM_TEMPERATURE,
)
from .goals import SWITCHABLE_GOALS, normalise_disabled_goals


def _available_room_goals(room: dict[str, Any]) -> list[str]:
    """Goals available from this room's configured data sources."""
    goals: list[str] = []
    if room.get(CONF_ROOM_HUMIDITY) and room.get(CONF_ROOM_TEMPERATURE):
        goals.append("humidity")
    if room.get(CONF_ROOM_CO2):
        goals.append("co2")
    if room.get(CONF_ROOM_CLIMATE) or room.get(CONF_ROOM_TARGET_TEMPERATURE) not in (None, "") or room.get(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK) not in (None, ""):
        goals.append("temperature")
    return goals


def _filter_room_priorities(value: Any, room: dict[str, Any]) -> list[str]:
    available = _available_room_goals(room)
    vals = value if isinstance(value, list) else []
    ordered = list(dict.fromkeys(str(x) for x in vals if str(x) in available))
    return ordered + [x for x in available if x not in ordered]


GOAL_OFF = "off"


def _shown_goal_priorities(room: dict[str, Any]) -> list[str]:
    """Goal per form position: active goals in order, then ``off`` (0.26.5.1)."""
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    disabled = set(normalise_disabled_goals(room.get(CONF_ROOM_DISABLED_GOALS)))
    active = [goal for goal in current if goal not in disabled] or current[:1]
    return active + [GOAL_OFF] * (len(current) - len(active))


def _goal_priority_schema(room: dict[str, Any], *, include_back: bool = False) -> vol.Schema:
    """Show every available ventilation goal at once in its current priority order.

    From the second position on a goal can be switched off (0.26.5.1, user
    request: a room that should only dehumidify).
    """
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    if not current:
        return vol.Schema({})
    shown = _shown_goal_priorities(room)
    fields: dict[Any, Any] = {}
    if include_back:
        fields[vol.Optional("wizard_back", default=False)] = bool
    for idx, goal in enumerate(shown, start=1):
        options = list(current) if idx == 1 else [*current, GOAL_OFF]
        fields[vol.Required(f"goal_priority_{idx}", default=goal)] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="ventilation_goal",
            )
        )
    return vol.Schema(fields)


def _resolve_move_ranking(ranked: list[str], current: list[str]) -> list[str]:
    """Turn the submitted dropdown values into a complete, duplicate-free order.

    0.26.4.6 (user report "Lüftungsziele priorisieren: Reihenfolge lässt sich
    nicht bestätigen"): reordering with one dropdown per position used to need
    two coordinated changes; changing only one dropdown produced a duplicate
    and the form refused to save. A changed position now means "move this goal
    here": explicitly changed positions win, unchanged positions keep their
    goal when it is still free, and the remaining goals fill the gaps in their
    previous order.
    """
    size = len(current)
    result: list[str | None] = [None] * size
    used: set[str] = set()
    changed = [idx for idx in range(size) if idx < len(ranked) and ranked[idx] != current[idx]]
    for idx in changed:
        goal = ranked[idx]
        if goal in current and goal not in used:
            result[idx] = goal
            used.add(goal)
    for idx in range(size):
        goal = ranked[idx] if idx < len(ranked) else ""
        if result[idx] is None and goal in current and goal not in used:
            result[idx] = goal
            used.add(goal)
    rest = [goal for goal in current if goal not in used]
    return [goal if goal is not None else rest.pop(0) for goal in result]


def _resolve_goal_selection(user_input: dict[str, Any], room: dict[str, Any]) -> tuple[list[str], list[str]] | None:
    """Return ``(active order, switched-off goals)`` or ``None`` for invalid input.

    Same "move" semantics as :func:`_resolve_move_ranking`; a position set to
    ``off`` stays off and every goal no longer placed is switched off.
    """
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    shown = _shown_goal_priorities(room)
    ranked = [
        str(user_input.get(f"goal_priority_{idx}") or "")
        for idx in range(1, len(current) + 1)
    ]
    if any(goal not in current and goal != GOAL_OFF for goal in ranked) or ranked[:1] == [GOAL_OFF]:
        return None
    result: list[str | None] = [None] * len(current)
    used: set[str] = set()
    for idx, goal in enumerate(ranked):
        if goal == GOAL_OFF:
            result[idx] = GOAL_OFF
        elif goal != shown[idx] and goal not in used:
            result[idx] = goal
            used.add(goal)
    for idx, goal in enumerate(ranked):
        if result[idx] is None and goal not in used:
            result[idx] = goal
            used.add(goal)
    rest = [goal for goal in shown if goal != GOAL_OFF and goal not in used]
    filled = [goal if goal is not None else (rest.pop(0) if rest else GOAL_OFF) for goal in result]
    active = [goal for goal in filled if goal != GOAL_OFF]
    return active, [goal for goal in current if goal not in active]


def _switched_off_goals(user_input: dict[str, Any], room: dict[str, Any]) -> list[str]:
    """Return the goals the submitted form switches off (``off`` positions)."""
    selection = _resolve_goal_selection(user_input, room)
    if selection is None:
        return normalise_disabled_goals(room.get(CONF_ROOM_DISABLED_GOALS))
    return selection[1]


def _ranked_goal_priorities(user_input: dict[str, Any], room: dict[str, Any]) -> list[str]:
    """Return the complete, duplicate-free ranking submitted by the user."""
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    ranked = [
        str(user_input.get(f"goal_priority_{idx}") or "")
        for idx in range(1, len(current) + 1)
    ]
    if not any(ranked):
        return current
    if all(goal in current for goal in ranked) and _shown_goal_priorities(room) == current:
        return _resolve_move_ranking(ranked, current)
    # 0.26.5.1: positions set to "off" – active goals first, switched-off goals last.
    selection = _resolve_goal_selection(user_input, room)
    return current if selection is None else selection[0] + selection[1]


def _goal_priority_errors(user_input: dict[str, Any], room: dict[str, Any]) -> dict[str, str]:
    """Reject unknown goals; duplicates are resolved as "move" (0.26.4.6).

    ``duplicate_goal_order`` is kept as a translation key for older flows but is
    no longer raised: a goal chosen twice moves to the explicitly changed slot.
    """
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    ranked = [
        str(user_input.get(f"goal_priority_{idx}") or "")
        for idx in range(1, len(current) + 1)
    ]
    if not current or bool(user_input.get("wizard_back")):
        return {}
    selection = _resolve_goal_selection(user_input, room)
    if len(ranked) != len(current) or selection is None:
        return {"base": "invalid_goal_order"}
    if any(goal not in SWITCHABLE_GOALS for goal in selection[1]):
        return {"base": "humidity_goal_required"}
    return {}
