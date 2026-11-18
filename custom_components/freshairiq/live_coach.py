"""FreshAirIQ self-learning live ventilation coach.

Re-evaluates an already running ventilation session. It never starts a session
and never overrides sensor errors. Health/safety and the existing physical
close rules remain authoritative.
"""
from __future__ import annotations
from typing import Any
from math import isfinite

from .close_wording import airing_running, close_cause, close_instruction, fan_only, keep_instruction
from .consolidation import moisture_coming_in, opening_phase_protected, planned_target_min
from .model import co2_release_ppm, min_return_volume_factor


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _aired_now(room: dict[str, Any]) -> bool:
    """F06 (0.26.5.5, GitHub #24): the room is really aired right now.

    A room whose windows are closed again stays ``active`` until its final measurement – it must
    neither time a window opened later nor count in the coach's forecast. A running exhaust fan
    airs the room although every window is closed.
    """
    if not airing_running(room):
        return False
    actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
    return bool(actuators.get("mechanical_exhaust_active")) or str(room.get("opening_state") or "") != "closed"


def refine_live_recommendation(
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    """Adapt remaining time from actual session progress and marginal benefit."""
    active = [r for r in rooms.values()
              if r.get("calculation_enabled", True)
              and r.get("data_quality") == "ok"
              and _aired_now(r)]
    if not active or str(recommendation.get("kind") or "") not in {"continue", "close"}:
        return recommendation

    # Existing close decision is authoritative; we only enrich its explanation.
    if str(recommendation.get("kind") or "") == "close":
        out = dict(recommendation)
        out["live_coach"] = True
        out["live_coach_state"] = "close"
        out["live_coach_reason"] = close_cause(active)[1] or "Physikalisches Schließkriterium erreicht"  # R07: the real cause
        # Hotfix 0.19.1.1: a close recommendation is an immediate action.  Do
        # not leave a stale positive remaining time from the previous house
        # target in the dashboard (e.g. "Jetzt schließen" and "1 min bis Ziel"
        # at the same time).
        out["live_coach_remaining_min"] = 0.0
        out["live_coach_confidence"] = min(
            [int(r.get("forecast_5_min_confidence", r.get("forecast_confidence", 0)) or 0) for r in active] or [0]
        )
        return out

    # 0.26.4.10: a long-running exhaust fan does not time the windows opened later.
    timed = [r for r in active if not fan_only(r)] or active
    elapsed = max((_f(r.get("session_elapsed_min")) for r in timed), default=0.0)
    youngest = min((_f(r.get("session_elapsed_min")) for r in timed), default=0.0)  # F06: every window has its own minimum
    min_duration = max(_f(options.get("min_duration_min"), 3.0), 2.0)
    max_duration = max(_f(options.get("max_duration_min"), 20.0), min_duration)

    # Original learned target attached when the recommendation was followed.
    linked_targets = [
        _f(r.get("session_recommended_duration_min"))
        for r in active if r.get("session_recommended_duration_min") is not None
    ]
    baseline_target = (
        sum(linked_targets) / len(linked_targets)
        if linked_targets else elapsed + max(_f(recommendation.get("duration_min"), 1.0), 1.0)
    )
    baseline_target = _clamp(baseline_target, min_duration, max_duration)

    # #28: session_predicted_removed_ml is the physical start replay (validation/learning); the coach compares
    # progress with the target-limited expectation the recommendation was based on (fallback: older sessions).
    def _coach_expected(r: dict[str, Any]) -> float:
        limited = r.get("session_target_limited_removed_ml")
        return _f(limited if limited is not None else r.get("session_predicted_removed_ml"))

    predicted_totals = [_coach_expected(r) for r in active if _coach_expected(r) > 20]
    predicted_total = sum(predicted_totals)
    actual_removed = sum(max(_f(r.get("result_ml")), 0.0) for r in active)
    next5 = sum(max(_f(r.get("forecast_5_min_moisture_effect_ml",
                             r.get("moisture_effect_next_5_min_ml"))), 0.0) for r in active)
    next5_temp = (
        sum(_f(r.get("forecast_5_min_temperature_change_c")) * max(_f(r.get("volume_m3")), 1.0) for r in active)
        / max(sum(max(_f(r.get("volume_m3")), 1.0) for r in active), 1.0)
    )
    confidence = min(
        [int(r.get("forecast_5_min_confidence", r.get("forecast_confidence", 0)) or 0) for r in active] or [0]
    )

    # Hotfix 0.17.0.5: the live coach may adapt duration, but it must never
    # manufacture a close recommendation for rooms whose room model has not
    # yet released the two-report / 15-minute close-decision gate. Because a
    # live-coach close instruction targets all active rooms, all of them must be
    # decision-ready before the coach may turn ``continue`` into ``close``.
    all_close_decisions_ready = all(bool(r.get("close_decision_ready", False)) for r in active)

    # Progress ratio compares real removal with what should have been achieved
    # by this point on the originally recommended trajectory.
    expected_now = 0.0
    progress_ratio = 1.0
    if predicted_total > 20 and baseline_target > 0:
        expected_now = predicted_total * min(elapsed / baseline_target, 1.0)
        if expected_now > 15:
            progress_ratio = _clamp(actual_removed / expected_now, 0.35, 1.80)

    # Project the remaining time from measured progress. Confidence and outcome
    # samples determine how strongly the coach may move away from the baseline.
    feedback_samples = sum(int(r.get("outcome_feedback_samples", 0) or 0) for r in active)
    learning_weight = min(feedback_samples / 12.0, 1.0) * min(max(confidence / 100.0, 0.25), 0.95)

    if predicted_total > 20 and actual_removed > 10 and elapsed >= 2:
        observed_rate = actual_removed / elapsed
        remaining_moisture = max(predicted_total - actual_removed, 0.0)
        projected_remaining = remaining_moisture / max(observed_rate, 1.0)
        adaptive_target = elapsed + projected_remaining
    else:
        adaptive_target = baseline_target

    target = baseline_target * (1.0 - learning_weight) + adaptive_target * learning_weight
    target = _clamp(target, min_duration, max_duration)
    return _coach_close_or_extend(
        active=active, actual_removed=actual_removed, all_close_decisions_ready=all_close_decisions_ready,
        baseline_target=baseline_target, confidence=confidence, elapsed=elapsed, expected_now=expected_now,
        feedback_samples=feedback_samples, learning_weight=learning_weight, max_duration=max_duration,
        min_duration=min_duration, next5=next5, next5_temp=next5_temp, options=options,
        progress_ratio=progress_ratio, recommendation=recommendation, target=target, youngest=youngest,
    )


def _coach_close_or_extend(
    *,
    active: Any, actual_removed: Any, all_close_decisions_ready: Any, baseline_target: Any, confidence: Any,
    elapsed: Any, expected_now: Any, feedback_samples: Any, learning_weight: Any, max_duration: Any,
    min_duration: Any, next5: Any, next5_temp: Any, options: Any, progress_ratio: Any, recommendation: Any,
    target: Any, youngest: Any = None,
) -> Any:
    """Close/hold/extend decision from the marginal benefit, health and goal priorities."""

    # Marginal benefit can shorten a session even when the initial target was
    # longer; conversely a useful next 5 min can justify a limited extension.
    # 0.26.4.7 (GitHub #15): absolute ml thresholds scale with the aired volume.
    volume_factor = min_return_volume_factor(sum(max(_f(r.get("volume_m3")), 0.0) for r in active))
    min_return = _f(options.get("min_return_next_5_min_ml"), 25.0) * volume_factor
    health_urgent = any(
        _f(r.get("surface_rh")) >= _f(options.get("mould_critical_surface_rh"), 90.0)
        or (bool(r.get("co2_available", r.get("co2") is not None)) and _f(r.get("co2")) >= _f(options.get("co2_critical"), 1400.0))
        for r in active
    )

    state = "on_track"
    reason = "Ist-Verlauf entspricht dem gelernten Lüftungsmodell"

    # 0.26.4.10: inside the airing time shown when the window was opened – and for
    # rooms aired only by their exhaust fan – the coach never shortens or closes;
    # only moisture coming in may end the airing (support case 472cf5b9, garage).
    signed_next5 = sum(_f(r.get("forecast_5_min_net_moisture_change_ml", r.get("forecast_5_min_moisture_effect_ml",
                                r.get("moisture_effect_next_5_min_ml")))) for r in active)
    ingress = moisture_coming_in(active, signed_next5, _f(options.get("close_delta"), 0.4))
    planned_target = planned_target_min(active)
    planned_hold = not ingress and opening_phase_protected(active, planned_target)
    fans_only = all(fan_only(r) for r in active)
    hold = planned_hold or (fans_only and not ingress)

    if hold:
        pass
    elif elapsed >= min_duration and next5 < min_return and not health_urgent:
        target = min(target, elapsed)
        state = "shortened"
        reason = f"Zusatznutzen fällt ab: interner 5-Minuten-Schließcheck nur noch etwa {round(next5)} ml"
    elif progress_ratio >= 1.18 and elapsed >= min_duration:
        target = min(target, max(elapsed, baseline_target - min(3.0, baseline_target * 0.22)))
        state = "shortened"
        reason = f"Lüftung wirkt schneller als erwartet ({round((progress_ratio-1)*100)} % voraus)"
    elif progress_ratio <= 0.78 and next5 >= min_return and elapsed < max_duration:
        extension = min(4.0, max_duration - baseline_target)
        target = max(target, baseline_target + extension * learning_weight)
        state = "extended"
        reason = f"Lüftung wirkt langsamer als erwartet; weitere Luftwechsel sind noch sinnvoll"

    target = _clamp(target, min_duration, max_duration)
    if planned_hold:
        # The shown time is never shorter than the time shown at opening.
        target = max(target, min(float(planned_target), max_duration))
    remaining = max(target - elapsed, 0.0)

    # Canonical protection gate: no goal priority or ETA may extend a session
    # once any room reports a hard close condition.
    hard_close_rooms = [r for r in active if isinstance(r.get("goal_state"), dict) and r["goal_state"].get("hard_close")]
    if hard_close_rooms:
        out = dict(recommendation)
        open_goals=[]
        for room in hard_close_rooms:
            for goal in room.get("goal_state", {}).get("goals", []):
                if goal.get("active") and not goal.get("reached"):
                    open_goals.append(goal)
        eta_values=[float(g["eta_min"]) for g in open_goals if g.get("eta_min") is not None and float(g.get("eta_min") or 0)>0]
        suffix = f" Das nächste offene Ziel bräuchte voraussichtlich noch etwa {max(round(min(eta_values)),1)} min." if eta_values else ""
        reason = "Schutzgrenze erreicht; offene Komfortziele dürfen die Lüftung nicht weiter verlängern." + suffix
        out.update({
            "kind":"close", "status":"close_windows", "title":"Jetzt schließen",
            "instruction":close_instruction(active),
            "summary":"Eine Schutzgrenze ist erreicht. Noch offene Ziele bleiben sichtbar, rechtfertigen aber kein weiteres Lüften.",
            "duration_min":0.0, "live_coach":True, "live_coach_state":"protection_close",
            "live_coach_reason":reason, "live_coach_remaining_min":0.0,
            "live_coach_confidence":confidence,
        })
        reasons=list(out.get("reasons") or []); reasons.insert(0,reason); out["reasons"]=reasons[:6]
        return out

    # Multi-goal extension: a still-open, user-prioritised goal may justify a
    # limited continuation, but never across the configured thermal protection
    # boundary. This is deliberately conservative: unknown ETA never invents a
    # duration and the established safety/close gates remain authoritative.
    priority_open = []
    for room in active:
        gs = room.get("goal_state") if isinstance(room.get("goal_state"), dict) else {}
        for goal in gs.get("goals", []):
            if goal.get("active") and not goal.get("reached") and goal.get("achievable_now"):
                priority_open.append(goal)
                break
    thermal_protection = next5_temp <= -abs(_f(options.get("max_temp_loss_next_5_min_c"), 1.5))
    priority_eta = [float(g["eta_min"]) for g in priority_open if g.get("eta_min") is not None and float(g.get("eta_min") or 0) > 0]
    if priority_open and not thermal_protection and priority_eta:
        target = max(target, min(elapsed + min(priority_eta), max_duration))
        remaining = max(target - elapsed, 0.0)
        state = "goal_extended"
        reason = f"Höher priorisiertes Lüftungsziel noch offen; voraussichtlich etwa {max(round(min(priority_eta)),1)} min bis zum nächsten Ziel"

    # Target reached + weak return closes only when the reference air no longer helps (F11: ingress or no room > close_delta drier)
    air_no_longer_helps = ingress or all(_f(r.get("delta_g_m3"), 99.0) <= _f(options.get("close_delta"), 0.4) for r in active)
    if (
        not hold
        and air_no_longer_helps
        and all_close_decisions_ready
        # F06: never before the youngest window's minimum time; 0.26.5.5 (audit F01): moisture really
        # coming in (net 5-minute change below zero) is protection and closes before the minimum.
        and ((ingress and signed_next5 < 0) or (elapsed >= min_duration and (youngest is None or youngest >= min_duration) and remaining <= 0.35))
        and next5 < max(min_return * 1.25, 35.0 * volume_factor)
        and not health_urgent
    ):
        out = dict(recommendation)
        out.update({
            "kind": "close", "status": "close_windows", "title": "Jetzt schließen",
            "instruction": close_instruction(active),
            "summary": "FreshAirIQ hat die laufende Lüftung neu bewertet; der effiziente Endpunkt ist erreicht.",
            "duration_min": 0.0, "estimated_removed_ml": round(actual_removed),
            "live_coach": True, "live_coach_state": "close",
            "live_coach_reason": reason, "live_coach_target_min": round(target, 1),
            "live_coach_remaining_min": 0.0, "live_coach_progress_ratio": round(progress_ratio, 2),
            "live_coach_next_5_min_ml": round(next5),
            "live_coach_next_5_min_temperature_c": round(next5_temp, 2),
            "live_coach_confidence": confidence,
        })
        reasons = list(out.get("reasons") or [])
        reasons.insert(0, reason)
        out["reasons"] = reasons[:6]
        return out

    reassessing = remaining <= 0.35 and not fans_only  # R07: target passed, air helps – no "0 min"; N1: the real reason
    out, reason = dict(recommendation), (_reassess_reason(active, next5, options) if reassessing else reason)
    out.update({
        "instruction": keep_instruction(active, None if fans_only or remaining <= 0.35 else remaining),  # F11: no time-limit countdown
        "duration_min": None if reassessing else round(remaining, 1),
        "estimated_removed_ml": round(next5),
        "live_coach": True, "live_coach_state": state,
        "live_coach_reason": reason, "live_coach_target_min": round(target, 1),
        "live_coach_baseline_target_min": round(baseline_target, 1),
        "live_coach_remaining_min": None if reassessing else round(remaining, 1), "live_coach_time_state": "reassessing" if reassessing else "countdown",
        "live_coach_time_reason": _open_time_reason(active, options) if reassessing else None,
        "live_coach_progress_ratio": round(progress_ratio, 2),
        "live_coach_actual_removed_ml": round(actual_removed),
        "live_coach_expected_now_ml": round(expected_now),
        "live_coach_next_5_min_ml": round(next5),
        "live_coach_next_5_min_temperature_c": round(next5_temp, 2),
        "live_coach_confidence": confidence,
        "live_coach_feedback_samples": feedback_samples,
    })
    out["reasons"] = [reason, *(out.get("reasons") or [])][:6]
    return out


def _co2_reason(active: list[dict[str, Any]], options: dict[str, Any]) -> str | None:
    """The CO2 clause when CO2 is what keeps a window open (critical, or the CO2 goal of a room is still open)."""
    critical = _f(options.get("co2_critical"), 1400.0)
    for room in active:
        if not bool(room.get("co2_available", room.get("co2") is not None)):
            continue
        ppm = _f(room.get("co2"))
        goals = (room.get("goal_state") or {}).get("goals") if isinstance(room.get("goal_state"), dict) else []
        open_goal = any(isinstance(g, dict) and g.get("id") == "co2" and g.get("active") and not g.get("reached") for g in goals or [])
        if ppm >= critical:
            return f"weitergelüftet wird wegen CO₂ ({round(ppm)} ppm, kritisch ab {round(critical)} ppm)"
        if open_goal:
            return f"weitergelüftet wird wegen CO₂ ({round(ppm)} ppm, Freigabe unter {round(co2_release_ppm(options))} ppm)"
    return None


def _reassess_reason(active: list[dict[str, Any]], next5: float, options: dict[str, Any]) -> str:
    """Why an airing past its planned time goes on – the goal that really keeps it open and the measured facts.

    N1: no standing positive phrase. C2 (IQ2): CO2, cooling or a running moisture source is named as the reason; air
    that is not drier is never described as "still drier".
    """
    delta = max((_f(r.get("delta_g_m3")) for r in active), default=0.0)
    changes = [_f(r.get("temperature_change_c")) for r in active if r.get("temperature_change_c") is not None]
    parts = ["Geplante Zeit erreicht"]
    cause = _co2_reason(active, options)
    if cause is None and any(r.get("comfort_cooling_active") for r in active):
        cause = "weitergelüftet wird zum Kühlen"
    if cause is None and any(r.get("moisture_source_active") for r in active):
        cause = "eine Feuchtequelle ist noch aktiv"
    if cause is not None:
        parts.append(cause)
    if delta > 0:
        parts.append(f"die Außenluft ist noch {delta:.1f} g/m³ trockener (nächste 5 min etwa {max(round(next5), 0)} ml)")
    else:
        parts.append(f"die Außenluft ist {abs(delta):.1f} g/m³ feuchter als die Raumluft und entfeuchtet gerade nicht")
    if changes:
        parts.append(f"Raum {min(changes):+.1f} °C seit Start")
    return " – ".join(("; ".join(parts), "FreshAirIQ bewertet jeden Zyklus neu"))


def _open_time_reason(active: list[dict[str, Any]], options: dict[str, Any]) -> str:
    """Why no remaining time can be given: what keeps the airing open and what ends it (no time is invented)."""
    cause = _co2_reason(active, options)
    if cause is None and any(r.get("comfort_cooling_active") for r in active):
        cause = "weitergelüftet wird zum Kühlen"
    if cause is None and any(r.get("moisture_source_active") for r in active):
        cause = "eine Feuchtequelle ist noch aktiv"
    if cause is None:
        checked = [r for r in active if r.get("close_benefit_threshold_ml") is not None and r.get("forecast_5_min_benefit_ml") is not None]
        if checked:
            room = min(checked, key=lambda r: _f(r.get("forecast_5_min_benefit_ml")) - _f(r.get("close_benefit_threshold_ml")))
            cause = (f"geschlossen wird, sobald zwei neue Messungen unter {round(_f(room.get('close_benefit_threshold_ml')))} ml "
                     f"in 5 min liegen (jetzt etwa {max(round(_f(room.get('forecast_5_min_benefit_ml'))), 0)} ml)")
        else:
            cause = "geschlossen wird, sobald die Außenluft nicht mehr trocknet"
    return f"Restzeit nicht bestimmbar – {cause}"


_CLOSE_STATES = frozenset({"close", "protection_close"})


def align_live_coach_state(recommendation: dict[str, Any]) -> None:
    """Hotfix S2 (01.11.): the live-coach fields describe the final decision, not an earlier one.

    The coach runs before the floor/house aggregate. When that aggregate turns a close into
    "keep ventilating" (or a running airing into a close), the earlier ``live_coach_state`` and
    remaining time stayed and reached the IQ time and the explanation. Same values as the
    consolidation uses for a blocked close: ``awaiting_measurements`` without a remaining time,
    and ``close`` with 0 min for a close.
    """
    if not isinstance(recommendation, dict) or not recommendation.get("live_coach"):
        return
    kind = str(recommendation.get("kind") or "")
    state = str(recommendation.get("live_coach_state") or "")
    if kind == "continue" and state in _CLOSE_STATES:
        recommendation["live_coach_state"] = "awaiting_measurements"
        recommendation["live_coach_reason"] = str(recommendation.get("summary") or recommendation.get("live_coach_reason") or "")
        recommendation["live_coach_remaining_min"] = None
        if recommendation.get("duration_min") in (0, 0.0):
            recommendation["duration_min"] = None
    elif kind == "close" and state not in _CLOSE_STATES:
        recommendation["live_coach_state"] = "close"
        recommendation["live_coach_remaining_min"] = 0.0


def r07_time_fields(recommendation: dict[str, Any], results: Any, *, active: bool, remaining: float | None,
                    displayed_recommended: Any, max_elapsed: float) -> dict[str, Any]:
    """R07 (0.26.7.2): initial estimate, remaining time, total session and close reason as separate, additive values.

    ``remaining_duration_state``: ``plan`` (no airing runs), ``countdown`` (an honest remaining time), ``reassessing``
    (target time passed, the air still helps – reassessed every cycle, no countdown), ``close`` / ``overrun`` (close
    now; a negative remaining time is the intended overrun beyond the target, never a reason to close by itself).
    """
    kind = str(recommendation.get("kind") or "")
    if not active:
        state = "plan"
    elif kind == "close":
        state = "overrun" if remaining is not None and remaining < 0 else "close"
    else:
        state = "reassessing" if remaining is None else "countdown"
    rooms = [results.get(k) for k in (recommendation.get("room_keys") or [])] if isinstance(results, dict) else []
    return {
        "remaining_duration_state": state,
        "initial_duration_estimate_min": recommendation.get("live_coach_baseline_target_min") if active else displayed_recommended,
        "session_total_min": round(float(max_elapsed), 1) if active else None,
        "close_reason_kind": close_cause(rooms)[0] if kind == "close" else None,
        "remaining_duration_reason": recommendation.get("live_coach_time_reason") if state == "reassessing" else None,
    }


def room_time_fields(rooms: Any, house_time: Any, min_duration_min: float) -> None:
    """IQ2 (0.26.7.1): one time meaning per aired room, written by the integration and read by both cards.

    ``time_state``: ``close`` (close now), ``countdown`` (``time_remaining_min`` minutes of the house plan are left),
    ``minimum`` (the room's own minimum duration still runs – rooms opened later keep their own clock),
    ``reassessing`` (the plan is over, the airing is reassessed every cycle; no remaining time). Rooms that are not
    aired have no time state. A card never derives a remaining time from an old plan again.
    """
    house = house_time if isinstance(house_time, dict) else {}
    countdown = _f(house.get("remaining_duration_min"), -1.0) if house.get("remaining_duration_state") == "countdown" else -1.0
    for room in (rooms.values() if isinstance(rooms, dict) else []):
        if not isinstance(room, dict):
            continue
        if not airing_running(room) or room.get("data_quality") != "ok":
            room["time_state"], room["time_remaining_min"] = None, None
            continue
        own_left = max(float(min_duration_min) - _f(room.get("session_elapsed_min")), 0.0)
        if str(room.get("action") or "") == "Close":
            room["time_state"], room["time_remaining_min"] = "close", 0.0
        elif countdown > 0.35:
            room["time_state"], room["time_remaining_min"] = "countdown", round(max(countdown, own_left), 1)
        elif own_left > 0.35:
            room["time_state"], room["time_remaining_min"] = "minimum", round(own_left, 1)
        else:
            room["time_state"], room["time_remaining_min"] = "reassessing", None

