"""FreshAirIQ Personal Context Engine.

Personalises the wording and timing context of an already-final technical
recommendation. It is intentionally forbidden from changing the physical
decision (kind, selected rooms, duration, forecast, safety thresholds).
"""
from __future__ import annotations

from datetime import datetime
import json
from math import isfinite
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _unique(items: list[str], limit: int = 6) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _split_names(value: Any) -> list[str]:
    """Parse optional resident display names from a compact local setting."""
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        text = str(value or "").replace(";", ",").replace("\n", ",")
        raw = text.split(",")
    out: list[str] = []
    for item in raw:
        name = " ".join(str(item or "").strip().split())
        if name:
            out.append(name[:48])
    return out[:20]



def _resident_profiles(value: Any) -> dict[str, dict[str, Any]]:
    """Parse resident room/comfort profiles stored as compact local JSON.

    Keys are stable resident slots (``adult:0``, ``child:1``). Invalid or
    hand-edited data is ignored rather than affecting a recommendation.
    """
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for slot, profile in raw.items():
        if not isinstance(profile, dict):
            continue
        slot_text = str(slot or "")
        if not (slot_text.startswith("adult:") or slot_text.startswith("child:")):
            continue
        room_keys = []
        for key in profile.get("room_keys") or []:
            text = str(key or "").strip()
            if text and text not in room_keys:
                room_keys.append(text[:80])
        thermal = str(profile.get("thermal_preference") or "inherit")
        if thermal not in {"inherit", "warm", "balanced", "cool"}:
            thermal = "inherit"
        out[slot_text] = {
            "name": " ".join(str(profile.get("name") or "").strip().split())[:48],
            "room_keys": room_keys[:50],
            "thermal_preference": thermal,
            "notification_targets": [str(x)[:120] for x in (profile.get("notification_targets") or []) if str(x).strip()][:10],
        }
    return out

def build_resident_context(
    options: dict[str, Any],
    state_source: Any,
    *,
    expected_occupants: float = 0.0,
) -> dict[str, Any]:
    """Build local presentation context for named residents.

    Names are aligned by index with the configured tracker lists. Additional
    names represent residents without their own tracker. This helper deliberately
    exposes no entity ids in its returned payload.
    """
    def _get_state(entity_id: str) -> str:
        if not entity_id:
            return "untracked"
        try:
            state = state_source.get(entity_id)
        except Exception:
            state = None
        if state is None:
            return "unknown"
        raw = getattr(state, "state", state)
        text = str(raw or "").lower()
        if text == "home":
            return "home"
        if text in {"not_home", "away"}:
            return "away"
        return "unknown"

    adults = max(0, int(_f(options.get("adult_occupants"), 0)))
    children = max(0, int(_f(options.get("child_occupants"), 0)))
    adult_names = _split_names(options.get("adult_resident_names"))
    child_names = _split_names(options.get("child_resident_names"))
    adult_entities = [str(x) for x in (options.get("adult_presence_entities") or [])]
    child_entities = [str(x) for x in (options.get("child_presence_entities") or [])]
    profiles = _resident_profiles(options.get("resident_room_profiles"))

    residents: list[dict[str, Any]] = []
    for role, count, names, entities in (
        ("adult", adults, adult_names, adult_entities),
        ("child", children, child_names, child_entities),
    ):
        total = max(count, len(names), len(entities))
        for idx in range(total):
            name = names[idx] if idx < len(names) else ""
            entity_id = entities[idx] if idx < len(entities) else ""
            profile = profiles.get(f"{role}:{idx}", {})
            # If names were reordered in the compact resident list, prefer the
            # profile carrying the same resident name over blindly following
            # the old slot index. This keeps room assignments attached to the
            # person whenever a unique local name is available.
            if name and profile.get("name") and profile.get("name") != name:
                profile = next((
                    p for slot, p in profiles.items()
                    if slot.startswith(f"{role}:") and p.get("name") == name
                ), profile)
            residents.append({
                "role": role,
                "index": idx,
                "name": name,
                "presence": _get_state(entity_id),
                "tracked": bool(entity_id),
                "room_keys": list(profile.get("room_keys") or []),
                "thermal_preference": str(profile.get("thermal_preference") or "inherit"),
            })

    named_adults_home = [r for r in residents if r["role"] == "adult" and r["name"] and r["presence"] == "home"]
    direct_name = None
    if len(named_adults_home) == 1:
        other_adults = [r for r in residents if r["role"] == "adult" and r is not named_adults_home[0]]
        others_confirmed_away = bool(other_adults) and all(r["tracked"] and r["presence"] == "away" for r in other_adults)
        no_other_adults = not other_adults
        # Directly address a person only when FreshAirIQ can identify the sole
        # adult at home without guessing about an untracked co-resident. The
        # aggregate occupancy estimate alone is intentionally not enough.
        if others_confirmed_away or no_other_adults:
            direct_name = named_adults_home[0]["name"]

    return {
        "configured_names": sum(1 for r in residents if r["name"]),
        "named_adults_home": [r["name"] for r in named_adults_home],
        "direct_address_name": direct_name,
        "residents": residents,
    }


def personalise_recommendation(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    *,
    now: datetime,
    expected_occupants: float = 0.0,
    resident_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a presentation-only personalised copy of a final recommendation."""
    out = dict(recommendation or {})
    if not bool(options.get("personalisation_enabled", True)):
        out["personal_context"] = {"enabled": False, "engine": "v1"}
        return out

    brain = dict(out.get("decision_brain") or {})
    kind = str(out.get("kind") or "okay")
    room_keys = [str(k) for k in (out.get("room_keys") or [])]
    selected = [rooms[k] for k in room_keys if k in rooms]
    selected_names = {str(r.get("key")): str(r.get("name") or r.get("key") or "Raum") for r in selected}
    resident_context = dict(resident_context or {})
    residents = list(resident_context.get("residents") or [])
    relevant_residents = [
        r for r in residents
        if set(str(k) for k in (r.get("room_keys") or [])) & set(room_keys)
    ]
    thermal = str(options.get("thermal_preference") or "balanced")
    priority = str(options.get("personal_priority") or "balanced")
    night_pref = str(options.get("night_window_preference") or "automatic")
    addressed_name = str(resident_context.get("direct_address_name") or "").strip()
    reasons = list(brain.get("why") or out.get("reasons") or [])
    context: list[str] = []

    # Existing behaviour learning becomes useful presentation context only after
    # enough opportunities exist. It never suppresses a health/safety decision.
    opportunities = sum(int(_f(r.get("behaviour_recommendation_opportunities"))) for r in selected)
    followed = sum(int(_f(r.get("behaviour_recommendation_followed"))) for r in selected)
    follow_rate = (100.0 * followed / opportunities) if opportunities >= 5 else None
    if follow_rate is not None and follow_rate >= 70 and kind in {"ventilate", "continue"}:
        context.append("Die Empfehlung passt zu deinem bisherigen Lüftungsverhalten in diesen Räumen")
    elif follow_rate is not None and follow_rate <= 30 and kind == "ventilate":
        context.append("FreshAirIQ berücksichtigt, dass Empfehlungen für diese Räume bisher nur selten direkt umgesetzt wurden")

    hour = now.hour
    daypart = "morning" if 5 <= hour < 10 else "day" if 10 <= hour < 18 else "evening" if 18 <= hour < 22 else "night"
    temp_change = _f((brain.get("impact") or {}).get("temperature_c", out.get("expected_temperature_change_c")))
    cost = _f((brain.get("impact") or {}).get("cost", out.get("estimated_reheat_cost")))

    # Resident-room assignments are context only. They may change wording, but
    # never the selected rooms, action, duration, forecast or safety logic.
    relevant_named = [r for r in relevant_residents if str(r.get("name") or "").strip()]
    direct_resident = next((r for r in residents if addressed_name and r.get("name") == addressed_name), None)
    direct_room_names = [selected_names[k] for k in (direct_resident or {}).get("room_keys", []) if k in selected_names]
    child_room_matches = [r for r in relevant_named if r.get("role") == "child"]
    local_thermal = {
        str(r.get("thermal_preference")) for r in relevant_residents
        if str(r.get("thermal_preference")) in {"warm", "balanced", "cool"}
    }

    summary = str(brain.get("summary") or out.get("summary") or "")
    if kind == "ventilate":
        if addressed_name:
            if len(direct_room_names) == 1:
                room_name = direct_room_names[0]
                if daypart == "morning" and follow_rate is not None and follow_rate >= 70:
                    summary = f"{addressed_name}, deine übliche Morgenlüftung für {room_name} passt heute gut. " + summary
                elif daypart == "evening":
                    summary = f"{addressed_name}, wenn es gerade passt: Für {room_name} ist jetzt vor der Nacht ein guter Lüftungszeitpunkt. " + summary
                else:
                    summary = f"{addressed_name}, wenn es gerade passt: Für {room_name} ist jetzt ein guter Zeitpunkt zum Lüften. " + summary
            elif daypart == "morning" and follow_rate is not None and follow_rate >= 70:
                summary = f"{addressed_name}, deine übliche Morgenlüftung passt heute gut. " + summary
            elif daypart == "evening":
                summary = f"{addressed_name}, wenn es gerade passt: Jetzt ist ein guter Zeitpunkt, die Lüftung noch vor der Nacht zu erledigen. " + summary
            else:
                summary = f"{addressed_name}, wenn es gerade passt: Jetzt ist ein guter Zeitpunkt zum Lüften. " + summary
        elif daypart == "morning":
            summary = "Der aktuelle Zeitpunkt eignet sich gut für eine kurze Lüftung. " + summary
        elif daypart == "evening":
            summary = "Wenn es für dich passt, ist jetzt ein guter Zeitpunkt, die Lüftung noch vor der Nacht zu erledigen. " + summary
        if thermal == "warm" and temp_change < -0.2:
            context.append("Deine Wärmekomfort-Präferenz wird berücksichtigt; FreshAirIQ hält die Lüftung deshalb so effizient wie möglich")
        if priority == "energy" and cost > 0:
            context.append("Energie hat in deinem Profil mehr Gewicht; die Empfehlung bleibt nur bestehen, weil der erwartete Nutzen den Wärmeverlust rechtfertigt")
        elif priority == "climate":
            context.append("Dein Profil priorisiert Raumklima; Komfort- und Energiekosten bleiben trotzdem Teil der Entscheidung")
    elif kind == "wait":
        if priority == "energy":
            summary = "Warten vermeidet aktuell unnötigen Wärmeverlust. " + summary
        elif thermal == "warm":
            summary = "Da du Wärmeverlust stärker gewichtest, ist Abwarten aktuell besonders passend. " + summary
    elif kind == "close" and thermal == "warm":
        context.append("Längeres Offenlassen würde zu deiner Wärmekomfort-Präferenz nicht mehr im Verhältnis zum Zusatznutzen stehen")

    ns = brain.get("night_strategy") if isinstance(brain.get("night_strategy"), dict) else {}
    if ns.get("active") and night_pref == "closed" and str(ns.get("action")) in {"close", "closed_monitor"}:
        context.append("Deine Präferenz, nachts Fenster geschlossen zu halten, passt heute zur berechneten Nachtstrategie")
    elif ns.get("active") and night_pref == "allowed" and str(ns.get("action")) == "open_selected":
        context.append("Nächtlich geöffnete Fenster sind in deinem Haushaltsprofil erlaubt und werden deshalb als Option berücksichtigt")

    if len(child_room_matches) == 1 and len(room_keys) == 1:
        child = child_room_matches[0]
        room_name = selected_names.get(room_keys[0], "dieser Raum")
        context.append(f"Für {child['name']} ist {room_name} als regelmäßig genutzter Raum hinterlegt")

    if temp_change < -0.2 and "warm" in local_thermal:
        warm_names = [str(r.get("name")) for r in relevant_named if r.get("thermal_preference") == "warm"]
        if len(warm_names) == 1:
            context.append(f"Für {warm_names[0]} ist ein eher warmes Komfortprofil hinterlegt; der erwartete Temperaturverlust wird deshalb besonders transparent ausgewiesen")
        else:
            context.append("Für mindestens einen Nutzer dieses Raums ist ein eher warmes Komfortprofil hinterlegt; der erwartete Temperaturverlust wird deshalb besonders transparent ausgewiesen")

    if expected_occupants <= 0 and kind in {"okay", "wait"}:
        context.append("Aktuell wird keine unmittelbare Anwesenheit berücksichtigt; FreshAirIQ kann deshalb stärker auf das nächste günstige Zeitfenster optimieren")

    reasons = _unique(reasons + context, 6)
    brain["summary"] = summary
    brain["why"] = reasons
    brain["personal_context"] = context
    brain["personalised"] = bool(context or summary != str(out.get("summary") or ""))
    out["summary"] = summary
    out["reasons"] = reasons
    out["decision_brain"] = brain
    out["personal_context"] = {
        "enabled": True,
        "engine": "v1",
        "thermal_preference": thermal,
        "priority": priority,
        "night_window_preference": night_pref,
        "expected_occupants": round(float(expected_occupants), 1),
        "behaviour_opportunities": opportunities,
        "behaviour_follow_rate": round(follow_rate, 1) if follow_rate is not None else None,
        "named_residents": int(resident_context.get("configured_names", 0) or 0),
        "addressed_name": addressed_name or None,
        "named_adults_home": list(resident_context.get("named_adults_home") or []),
        "assigned_residents": [
            {"name": str(r.get("name") or ""), "role": str(r.get("role") or ""),
             "room_keys": list(r.get("room_keys") or []),
             "thermal_preference": str(r.get("thermal_preference") or "inherit")}
            for r in relevant_residents if r.get("name")
        ],
    }
    return out
