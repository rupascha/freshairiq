"""Opening-level recommendation overlay for FreshAirIQ.

This module is a recommendation overlay. It never changes canonical room/house
physics, learning state or stored room actions. It normally only explains which
configured opening(s) are best. For one narrowly defined mixed-source case it
may refine a room-level close presentation into "keep the good path open, close
the harmful path" while preserving the original canonical action as metadata.
"""
from __future__ import annotations

from typing import Any

from .close_wording import airing_running


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("entity_id") or "Öffnung")


def _opening_score(item: dict[str, Any], profile: str) -> float:
    """Rank openings using already-computed physical effects.

    Moisture removal remains the dominant term. In comfort mode, avoid picking
    a marginally drier opening when it causes materially more heat loss. Summer
    cooling intentionally values cooling rather than penalising it.
    """
    effect = _f(item.get("moisture_effect_next_5_min_ml"))
    # ``moisture_effect_next_5_min_ml`` already comes from ``evaluate_room``
    # with this opening's airflow factor applied. Multiplying by airflow here a
    # second time would square the wind/orientation influence and distort ranks.
    dt = _f(item.get("temperature_effect_next_5_min_c"))
    if profile == "summer_cooling":
        cooling_bonus = max(-dt, 0.0) * 6.0
        return effect + cooling_bonus
    heat_penalty = max(-dt, 0.0) * (4.0 if profile == "dehumidify" else 8.0)
    return effect - heat_penalty


def _usable(item: dict[str, Any]) -> bool:
    return bool(item.get("available")) and (
        bool(item.get("ventilation_candidate"))
        or bool(item.get("cooling_candidate"))
        or _f(item.get("moisture_effect_next_5_min_ml")) > 0.5
    )


def _poor(item: dict[str, Any]) -> bool:
    return bool(item.get("available")) and (
        _f(item.get("delta_g_m3")) <= 0.0
        or _f(item.get("moisture_effect_next_5_min_ml")) <= 0.0
    )


def _append_unique(items: list[str], text: str, limit: int = 6) -> list[str]:
    text = str(text or "").strip()
    if text and text not in items and len(items) < limit:
        items.append(text)
    return items


def _room_opening_plan(
    room: dict[str, Any], profile: str, *, running: bool, close_delta: float = 0.0
) -> dict[str, Any] | None:
    assessments = [x for x in (room.get("opening_assessments") or []) if isinstance(x, dict)]
    if not assessments:
        return None

    available = [x for x in assessments if x.get("available")]
    if not available:
        return None

    scored = sorted(
        ((x, _opening_score(x, profile)) for x in available),
        key=lambda row: row[1], reverse=True,
    )
    useful = [(x, score) for x, score in scored if _usable(x)]
    if not useful:
        return None

    best_score = useful[0][1]
    # Keep near-equivalent openings together. This allows two outside windows
    # with the same source to be recommended together without pretending that
    # we have simulated a precise multi-opening CFD flow field.
    tolerance = max(abs(best_score) * 0.18, 3.0)
    preferred = [x for x, score in useful if score >= best_score - tolerance]

    if running:
        preferred_open = [x for x in preferred if x.get("is_open")]
        useful_open = [x for x, _ in useful if x.get("is_open")]
        bad_open = [
            x for x in available
            if x.get("is_open") and (
                _poor(x) or _f(x.get("delta_g_m3")) <= float(close_delta)
            )
        ]
        # A cooling-only path can be usable even while its moisture gradient is
        # harmful. With a single opening this previously put the exact same
        # contact into both keep and close, producing a contradictory command.
        # Preserve the established close_delta behaviour for weak-but-positive
        # ventilation paths; only remove true keep/close self-conflicts.
        # 0.26.5.2 (community: "Fenster Schlafzimmer offen lassen · Fenster
        # Schlafzimmer schließen", alternating with "Schließen" every few
        # minutes): an opening that is kept open is never also told to close.
        # With a single weak opening there is nothing to re-route, so the
        # canonical close stays instead of flipping to "keep ventilating".
        keep_ids = {id(x) for x in (preferred_open or useful_open)}
        keep_names = {_name(x) for x in (preferred_open or useful_open)}
        bad_open = [x for x in bad_open if id(x) not in keep_ids and _name(x) not in keep_names]
        # Do not invent a route change during an active session unless there is
        # already at least one useful open path that can keep ventilating.
        if bad_open and useful_open:
            keep = preferred_open or useful_open
            return {
                "preferred": keep,
                "avoid": bad_open,
                "mode": "adjust_running",
            }
        return None

    avoid = [x for x in available if x not in preferred and (
        _poor(x)
        or (_f(x.get("delta_g_m3")) + 0.8 < _f(preferred[0].get("delta_g_m3")))
    )]
    return {"preferred": preferred, "avoid": avoid, "mode": "before_opening"}


def enrich_opening_recommendation(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    """Add contact-specific opening guidance on top of canonical room physics.

    Physical room results, room selection, forecasts and learning values remain
    untouched. In the mixed-source recovery case only the user-facing aggregate
    action is refined from blanket ``close`` to selective ``continue``; the
    original canonical action is retained in metadata for diagnostics.
    """
    if not isinstance(recommendation, dict):
        return recommendation
    kind = str(recommendation.get("kind") or "")
    if kind not in {"ventilate", "continue", "close"}:
        return recommendation

    room_keys = [str(x) for x in (recommendation.get("room_keys") or [])]
    if not room_keys:
        return recommendation

    profile = str(options.get("operating_profile", "comfort"))
    plans: list[dict[str, Any]] = []
    for key in room_keys:
        room = rooms.get(key)
        if not isinstance(room, dict):
            continue
        close_delta = _f(options.get("close_delta"), 0.4)
        plan = _room_opening_plan(
            room, profile,
            running=(kind in {"continue", "close"} or bool(room.get("active"))),
            close_delta=close_delta,
        )
        if not plan:
            continue
        # A canonical room-level close may be caused by the deliberately
        # conservative "moistest open source" rule. Only recover from that close
        # when the room-level gradient itself has fallen to the close threshold
        # AND opening-level evidence shows a useful open path plus a harmful one.
        # This intentionally does not override thermal/max-duration/target closes
        # while the canonical room gradient is still clearly useful.
        if kind == "close":
            if plan.get("mode") != "adjust_running" or _f(room.get("delta_g_m3"), 999.0) > close_delta:
                continue
        plan = dict(plan)
        plan["room_key"] = key
        plan["room_name"] = str(room.get("name") or key)
        plans.append(plan)

    if not plans:
        return recommendation

    # If *every* room in a close recommendation has a mixed-source recovery
    # plan, the user-facing action must keep the good path open and close only
    # the harmful one. The canonical per-room model remains untouched in
    # ``rooms``; we record the original recommendation for diagnostics.
    if kind == "close":
        planned_keys = {str(p.get("room_key")) for p in plans}
        if planned_keys != set(room_keys):
            return recommendation
        recommendation["canonical_kind"] = "close"
        recommendation["canonical_status"] = str(recommendation.get("status") or "close_windows")
        recommendation["kind"] = "continue"
        recommendation["status"] = "ventilation_running"
        recommendation["title"] = "Gezielt weiterlüften"
        recommendation["summary"] = "Eine ungünstige Öffnung bremst die Lüftung. Die günstigere Luftquelle kann weiter genutzt werden."
        brain = recommendation.get("decision_brain")
        if isinstance(brain, dict):
            brain["headline"] = recommendation["title"]
            brain["summary"] = recommendation["summary"]
            brain["decision_label"] = "LIVE-OPTIMIERUNG"
            brain["canonical_kind"] = "close"
        kind = "continue"

    instruction_parts: list[str] = []
    reasons = [str(x) for x in (recommendation.get("reasons") or []) if str(x).strip()]
    metadata: list[dict[str, Any]] = []

    for plan in plans:
        preferred = list(plan.get("preferred") or [])
        avoid = list(plan.get("avoid") or [])
        preferred_names = [_name(x) for x in preferred]
        avoid_names = [_name(x) for x in avoid]
        room_name = str(plan.get("room_name") or "Raum")
        if plan.get("mode") == "adjust_running":
            part = f"{room_name}: {', '.join(preferred_names)} offen lassen"
            if avoid_names:
                part += f" · {', '.join(avoid_names)} schließen"
        else:
            part = f"{room_name}: {', '.join(preferred_names)} öffnen"
            if avoid_names:
                part += f" · {', '.join(avoid_names)} geschlossen lassen"
        instruction_parts.append(part)

        best = preferred[0]
        source_label = str(best.get("source_label") or "Referenzluft")
        _append_unique(
            reasons,
            f"{preferred_names[0]}: {source_label} ist {_f(best.get('delta_g_m3')):.1f} g/m³ trockener; erwarteter 5-Minuten-Effekt etwa {round(_f(best.get('moisture_effect_next_5_min_ml')))} ml",
        )
        if avoid:
            worst = min(avoid, key=lambda x: _f(x.get("delta_g_m3")))
            delta = _f(worst.get("delta_g_m3"))
            if delta <= 0:
                why = "gleich feucht oder feuchter als die Raumluft"
            else:
                why = f"nur {delta:.1f} g/m³ trockener"
            _append_unique(reasons, f"{_name(worst)} derzeit nicht bevorzugt: Referenzluft ist {why}")

        metadata.append({
            "room_key": plan.get("room_key"),
            "room_name": room_name,
            "mode": plan.get("mode"),
            "preferred": [str(x.get("entity_id")) for x in preferred],
            "avoid": [str(x.get("entity_id")) for x in avoid],
        })

    if instruction_parts:
        recommendation["instruction"] = " · ".join(instruction_parts)
        recommendation["reasons"] = reasons[:6]
        recommendation["opening_guidance"] = metadata
        brain = recommendation.get("decision_brain")
        if isinstance(brain, dict):
            brain["action_line"] = recommendation["instruction"]
            why = [str(x) for x in (brain.get("why") or []) if str(x).strip()]
            for reason in reasons:
                _append_unique(why, reason)
            brain["why"] = why[:6]
            brain["opening_guidance"] = metadata
    return recommendation


def keep_moisture_sources_open(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
) -> None:
    """Final invariant: never tell a room with a running moisture source to close.

    0.26.5.2 (owner: "Schließen" while the sauna runs is a no-go). The room
    engine keeps such a room open while the reference air is drier, but the
    house/floor aggregate that runs later closed every open room together.
    Rooms whose own decision is "Continue ventilating" because of an active
    source are taken out of a close; when no other room is left, the close
    becomes "keep ventilating".
    """
    if not isinstance(recommendation, dict) or not isinstance(rooms, dict):
        return
    if str(recommendation.get("kind") or "") != "close":
        return
    close_delta = _f(options.get("close_delta"), 0.4) if isinstance(options, dict) else 0.4
    selected = [str(key) for key in (recommendation.get("room_keys") or [])]
    sources = [
        key for key in selected
        if isinstance(rooms.get(key), dict)
        and rooms[key].get("active")
        and rooms[key].get("moisture_source_active")
        and str(rooms[key].get("action") or "") == "Continue ventilating"
        and _f(rooms[key].get("delta_g_m3")) > close_delta
    ]
    if not sources:
        return
    names = " + ".join(str(rooms[key].get("name") or key) for key in sources)
    labels = "/".join(dict.fromkeys(str(rooms[key].get("moisture_source_label") or "Feuchtequelle") for key in sources))
    keep = f"{names} offen lassen ({labels} aktiv)"
    remaining = [key for key in selected if key not in sources]
    reason = f"{names}: {labels} läuft; die trocknere Außen-/Referenzluft führt die entstehende Feuchte weiter ab"
    reasons = [str(x) for x in (recommendation.get("reasons") or []) if str(x).strip()]
    recommendation["moisture_source_kept_open"] = sources
    if remaining:
        recommendation["room_keys"] = remaining
        recommendation["instruction"] = f"{recommendation.get('instruction') or 'Jetzt schließen'} · {keep}"
    else:
        recommendation.update({
            "kind": "continue", "status": "moisture_source_active", "room_keys": sources,
            "title": f"{labels} erkannt", "instruction": keep,
            "summary": "Während die interne Feuchte- und Wärmequelle aktiv ist, hat die trocknere Außen-/Referenzluft Vorrang vor einer Schließempfehlung.",
            "duration_min": None,
        })
    recommendation["reasons"] = [reason, *[x for x in reasons if x != reason]][:6]
    brain = recommendation.get("decision_brain")
    if isinstance(brain, dict):
        brain["headline"] = recommendation.get("title")
        brain["action_line"] = recommendation["instruction"]
        brain["summary"] = recommendation.get("summary")
        brain["why"] = list(recommendation["reasons"])


def synchronize_room_presentation_actions(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
) -> None:
    """Align exported room actions with the final user-facing recommendation.

    The room engine's original action is retained as ``canonical_action`` for
    diagnostics. This runs only after physics, forecasting, learning and the
    final recommendation are complete, so it cannot feed presentation choices
    back into canonical calculations.
    """
    if not isinstance(recommendation, dict) or not isinstance(rooms, dict):
        return
    kind = str(recommendation.get("kind") or "")
    if kind not in {"ventilate", "continue", "close"}:
        return
    selected = {str(key) for key in (recommendation.get("room_keys") or [])}
    if not selected:
        return
    guidance = {
        str(item.get("room_key")): item
        for item in (recommendation.get("opening_guidance") or [])
        if isinstance(item, dict) and item.get("room_key") is not None
    }
    for key in selected:
        room = rooms.get(key)
        if not isinstance(room, dict):
            continue
        current = str(room.get("action") or "")
        final_action: str | None = None
        if kind == "close":
            final_action = "Close"
        elif kind == "continue" and airing_running(room):
            final_action = "Continue ventilating"
        elif kind == "ventilate" and not airing_running(room):
            final_action = "Ventilate"
        if key in guidance and str(guidance[key].get("mode") or "") == "adjust_running":
            final_action = "Continue ventilating"
        if final_action and current != final_action:
            room["canonical_action"] = current
            room["action"] = final_action
            room["presentation_action_override"] = {
                "action": final_action,
                "recommendation_kind": kind,
                "reason": "final_recommendation_alignment",
            }


# 0.26.4.7 (open item "Raumanzeige folgt Hausentscheidung"): the room "Aktion"
# sensor keeps its physical, room-local meaning (automations rely on it). An
# additional value tells what the room should do *given the house decision*:
# while the house deliberately waits (better window later, pollen/fine dust,
# night hold) a room that could physically be aired reads "ventilate_later".
HOUSE_HOLD_KINDS = frozenset({"wait", "pollen_wait"})
HOUSE_ALIGNED_STATES = frozenset({
    "ventilate", "continue_ventilating", "close", "ventilate_for_cooling", "do_not_ventilate",
    "wait", "okay", "check_sensor", "monitor_only", "ventilate_later", "ventilate_indirectly", "open_fully",
    "monitor_open",
})
PASSIVE_OPEN_MONITOR_STATUS = "passive_open_monitor"


def _action_code(action: Any) -> str:
    text = str(action or "").strip()
    return text.lower().replace(" ", "_") if text else "unknown"


def house_aligned_room_actions(recommendation: dict[str, Any], rooms: dict[str, dict[str, Any]]) -> None:
    """Add ``house_aligned_action`` to every room payload (presentation only)."""
    if not isinstance(rooms, dict):
        return
    kind = str((recommendation or {}).get("kind") or "") if isinstance(recommendation, dict) else ""
    house_holds = kind in HOUSE_HOLD_KINDS
    # F02 (2026-10-16): the final house decision tolerates a long, thermally
    # stable opening ("Daueröffnung wird beobachtet"). The physical room action
    # may still read "close"; the effective recommendation for exactly these
    # rooms is "monitor_open", so no surface tells the user to close while the
    # house says the window may stay open. Hard closes never reach this mode.
    monitored: set[str] = set()
    if isinstance(recommendation, dict) and kind == "okay" and str(recommendation.get("status") or "") == PASSIVE_OPEN_MONITOR_STATUS:
        monitored = {str(k) for k in (recommendation.get("room_keys") or [])}
    for room_key, room in rooms.items():
        if not isinstance(room, dict):
            continue
        code = _action_code(room.get("action"))
        if house_holds and code in {"ventilate", "ventilate_for_cooling"} and not room.get("active"):
            code = "ventilate_later"
        elif code == "close" and room.get("active") and str(room.get("key") or room_key) in monitored:
            code = "monitor_open"
        room["house_aligned_action"] = code if code in HOUSE_ALIGNED_STATES else "unknown"
