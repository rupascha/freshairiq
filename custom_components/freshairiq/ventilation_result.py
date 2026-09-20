"""House-level ventilation result aggregation for FreshAirIQ."""
from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from typing import Any


def new_ventilation_group(started_at: datetime | str) -> dict[str, Any]:
    """Create a persistent house-level ventilation group."""
    stamp = started_at.isoformat() if isinstance(started_at, datetime) else str(started_at)
    return {"active": True, "started_at": stamp, "sessions": []}


def include_ventilation_group_start(group: dict[str, Any], started_at: datetime | str) -> bool:
    """Move a house-group start backwards when an earlier physical opening is discovered."""
    candidate_raw = started_at.isoformat() if isinstance(started_at, datetime) else str(started_at)
    try:
        candidate = datetime.fromisoformat(candidate_raw)
    except (TypeError, ValueError):
        return False
    current_raw = group.get("started_at")
    try:
        current = datetime.fromisoformat(str(current_raw)) if current_raw else None
    except (TypeError, ValueError):
        current = None
    if current is None or candidate < current:
        group["started_at"] = candidate.isoformat()
        return True
    return False




def update_session_cross_tracking(mem: dict[str, Any], now: datetime, cross_active: bool) -> bool:
    """Accumulate time during which an active room session experienced cross ventilation."""
    if not mem.get("session_active"):
        return False
    changed = False
    last_raw = mem.get("session_cross_last_update")
    previous_active = bool(mem.get("session_cross_active", False))
    if last_raw:
        try:
            last = datetime.fromisoformat(str(last_raw))
        except (TypeError, ValueError):
            last = None
        if last is not None and now >= last and previous_active:
            delta = max(0.0, (now - last).total_seconds())
            if delta:
                mem["session_cross_seconds"] = max(float(mem.get("session_cross_seconds", 0.0) or 0.0), 0.0) + delta
                changed = True
    stamp = now.isoformat()
    if mem.get("session_cross_last_update") != stamp:
        mem["session_cross_last_update"] = stamp
        changed = True
    if previous_active != bool(cross_active):
        mem["session_cross_active"] = bool(cross_active)
        changed = True
    return changed

def append_completed_sessions(group: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    """Append completed room sessions exactly once to an active house group."""
    if not events:
        return False
    sessions = group.setdefault("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
        group["sessions"] = sessions
    changed = False
    existing_ids = {str(item.get("event_id")) for item in sessions if item.get("event_id")}
    for event in events:
        item = dict(event)
        event_id = str(item.get("event_id") or "")
        if event_id and event_id in existing_ids:
            continue
        sessions.append(item)
        if event_id:
            existing_ids.add(event_id)
        changed = True
    return changed


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _weighted_average(pairs: list[tuple[float, float]]) -> float | None:
    valid = [(value, max(weight, 0.0)) for value, weight in pairs if weight > 0]
    weight_sum = sum(weight for _, weight in valid)
    if weight_sum <= 0:
        return None
    return sum(value * weight for value, weight in valid) / weight_sum


def finalise_ventilation_group(
    group: dict[str, Any],
    ended_at: datetime,
    *,
    display_minutes: float = 5.0,
) -> dict[str, Any] | None:
    """Build one complete result from all room sessions in a house ventilation."""
    sessions = [dict(item) for item in (group.get("sessions") or []) if isinstance(item, dict)]
    if not sessions:
        return None

    room_map: dict[str, dict[str, Any]] = {}
    for event in sessions:
        key = str(event.get("key") or event.get("name") or "unknown")
        room = room_map.setdefault(
            key,
            {
                "key": key,
                "name": str(event.get("name") or key),
                "floor": event.get("floor"),
                "sort_order": int(event.get("sort_order", 9999) or 9999),
                "removed_ml": 0.0,
                "moisture_measured_sessions": 0,
                "moisture_unmeasured_sessions": 0,
                "duration_min": 0.0,
                "cost": 0.0,
                "energy_kwh": 0.0,
                "temp_pairs": [],
                "predicted_removed_ml": 0.0,
                "predicted_removed_samples": 0,
                "prediction_actual_removed_ml": 0.0,
                "prediction_comparable_sessions": 0,
                "aligned_predicted_removed_ml": 0.0,
                "aligned_predicted_removed_samples": 0,
                "aligned_prediction_actual_removed_ml": 0.0,
                "prediction_time_aligned_sessions": 0,
                "predicted_temp_pairs": [],
                "recommendation_followed": False,
                "learning_valid_sessions": 0,
                "session_count": 0,
                "moisture_source_contaminated": False,
                "cross_ventilation_minutes": 0.0,
                "outcome_feedback_actions": [],
                "outcome_feedback_reasons": [],
            },
        )
        volume = max(_number(event.get("volume_m3")) or 0.0, 0.0)
        weight = volume if volume > 0 else 1.0
        measured_removed = _number(event.get("removed_ml")) if bool(event.get("moisture_measurement_valid", event.get("removed_ml") is not None)) else None
        if measured_removed is None:
            room["moisture_unmeasured_sessions"] += 1
        else:
            room["removed_ml"] += measured_removed
            room["moisture_measured_sessions"] += 1
        room["duration_min"] += max(_number(event.get("duration_min")) or 0.0, 0.0)
        room["cost"] += max(_number(event.get("cost")) or 0.0, 0.0)
        room["energy_kwh"] += max(_number(event.get("energy_kwh")) or 0.0, 0.0)
        temp_delta = _number(event.get("temp_delta_c"))
        if temp_delta is not None:
            room["temp_pairs"].append((temp_delta, weight))
        predicted_removed = _number(event.get("predicted_removed_ml"))
        actual_removed = measured_removed
        if predicted_removed is not None and actual_removed is not None and bool(event.get("prediction_time_aligned")):
            room["aligned_predicted_removed_ml"] += predicted_removed
            room["aligned_predicted_removed_samples"] += 1
            room["aligned_prediction_actual_removed_ml"] += actual_removed
            room["prediction_time_aligned_sessions"] += 1
        if predicted_removed is not None and actual_removed is not None and bool(event.get("prediction_comparable")):
            room["predicted_removed_ml"] += predicted_removed
            room["predicted_removed_samples"] += 1
            room["prediction_actual_removed_ml"] += actual_removed
            room["prediction_comparable_sessions"] += 1
        predicted_temp = _number(event.get("predicted_temperature_change_c"))
        if predicted_temp is not None:
            room["predicted_temp_pairs"].append((predicted_temp, weight))
        room["recommendation_followed"] = bool(room["recommendation_followed"] or event.get("recommendation_followed"))
        room["learning_valid_sessions"] += 1 if event.get("learning_valid") else 0
        room["session_count"] += 1
        room["moisture_source_contaminated"] = bool(room["moisture_source_contaminated"] or event.get("moisture_source_contaminated"))
        room["cross_ventilation_minutes"] += max(_number(event.get("cross_ventilation_minutes")) or 0.0, 0.0)
        if event.get("outcome_feedback_action"):
            room["outcome_feedback_actions"].append(str(event.get("outcome_feedback_action")))
        if event.get("outcome_feedback_reason"):
            room["outcome_feedback_reasons"].append(str(event.get("outcome_feedback_reason")))

    room_results: list[dict[str, Any]] = []
    for room in room_map.values():
        temp_delta = _weighted_average(room.pop("temp_pairs"))
        predicted_temp = _weighted_average(room.pop("predicted_temp_pairs"))
        predicted_samples = int(room.pop("predicted_removed_samples"))
        aligned_predicted_samples = int(room.pop("aligned_predicted_removed_samples"))
        measured_sessions = int(room.get("moisture_measured_sessions", 0))
        unmeasured_sessions = int(room.get("moisture_unmeasured_sessions", 0))
        room["removed_ml"] = round(float(room["removed_ml"]), 1) if measured_sessions > 0 else None
        room["moisture_result_complete"] = bool(measured_sessions > 0 and unmeasured_sessions == 0)
        room["duration_min"] = round(float(room["duration_min"]), 1)
        room["cost"] = round(float(room["cost"]), 3)
        room["energy_kwh"] = round(float(room["energy_kwh"]), 4)
        room["cross_ventilation_minutes"] = round(float(room["cross_ventilation_minutes"]), 1)
        room["temp_delta_c"] = round(temp_delta, 2) if temp_delta is not None else None
        room["predicted_removed_ml"] = round(float(room["predicted_removed_ml"]), 1) if predicted_samples else None
        room["prediction_actual_removed_ml"] = round(float(room["prediction_actual_removed_ml"]), 1) if predicted_samples else None
        room["prediction_comparable_sessions"] = int(room.get("prediction_comparable_sessions", 0))
        room["aligned_predicted_removed_ml"] = round(float(room["aligned_predicted_removed_ml"]), 1) if aligned_predicted_samples else None
        room["aligned_prediction_actual_removed_ml"] = round(float(room["aligned_prediction_actual_removed_ml"]), 1) if aligned_predicted_samples else None
        room["prediction_time_aligned_sessions"] = int(room.get("prediction_time_aligned_sessions", 0))
        # v0.25.0.36: classify forecast evidence per room. A room with strict
        # comparable sessions remains useful even when another room in the same
        # house ventilation reported asynchronously.
        aligned_count = room["prediction_time_aligned_sessions"]
        comparable_count = room["prediction_comparable_sessions"]
        if aligned_count <= 0:
            room["prediction_validation_status"] = "unavailable"
        elif comparable_count == aligned_count:
            room["prediction_validation_status"] = "valid"
        elif comparable_count > 0:
            room["prediction_validation_status"] = "restricted"
        else:
            room["prediction_validation_status"] = "not_comparable"
        room["predicted_temperature_change_c"] = round(predicted_temp, 2) if predicted_temp is not None else None
        actions = room.pop("outcome_feedback_actions", [])
        reasons = room.pop("outcome_feedback_reasons", [])
        priority = {"guarded_observation": 6, "cautious_confirmation": 5, "confirmed_outlier": 4, "guarded": 4, "cautious": 3, "applied": 2, "skipped": 1}
        room["outcome_feedback_action"] = max(actions, key=lambda x: priority.get(x, 0)) if actions else None
        room["outcome_feedback_reason"] = reasons[-1] if reasons else None
        room_results.append(room)
    room_results.sort(key=lambda item: (int(item.get("sort_order", 9999)), str(item.get("name", ""))))

    measured_room_values = [float(item["removed_ml"]) for item in room_results if item.get("removed_ml") is not None]
    measured_removed_partial = sum(measured_room_values) if measured_room_values else None
    moisture_measured_sessions = sum(int(item.get("moisture_measured_sessions", 0)) for item in room_results)
    moisture_unmeasured_sessions = sum(int(item.get("moisture_unmeasured_sessions", 0)) for item in room_results)
    moisture_result_complete = bool(moisture_measured_sessions > 0 and moisture_unmeasured_sessions == 0)
    total_removed = measured_removed_partial if moisture_result_complete else None
    total_cost = sum(float(item.get("cost", 0.0)) for item in room_results)
    total_energy = sum(float(item.get("energy_kwh", 0.0)) for item in room_results)
    total_room_minutes = sum(float(item.get("duration_min", 0.0)) for item in room_results)
    temp_pairs = [
        (float(item["temp_delta_c"]), max(float(next((e.get("volume_m3", 0.0) for e in sessions if str(e.get("key") or e.get("name")) == item["key"]), 0.0) or 0.0), 1.0))
        for item in room_results if item.get("temp_delta_c") is not None
    ]
    avg_temp = _weighted_average(temp_pairs)

    predicted_values = [float(item["predicted_removed_ml"]) for item in room_results if item.get("predicted_removed_ml") is not None]
    predicted_removed = sum(predicted_values) if predicted_values else None
    prediction_actual_values = [float(item["prediction_actual_removed_ml"]) for item in room_results if item.get("prediction_actual_removed_ml") is not None]
    prediction_actual_removed = sum(prediction_actual_values) if prediction_actual_values else None
    prediction_comparable_sessions = sum(int(item.get("prediction_comparable_sessions", 0)) for item in room_results)
    prediction_comparable_rooms = sum(1 for item in room_results if int(item.get("prediction_comparable_sessions", 0)) > 0)
    aligned_predicted_values = [float(item["aligned_predicted_removed_ml"]) for item in room_results if item.get("aligned_predicted_removed_ml") is not None]
    aligned_predicted_removed = sum(aligned_predicted_values) if aligned_predicted_values else None
    aligned_actual_values = [float(item["aligned_prediction_actual_removed_ml"]) for item in room_results if item.get("aligned_prediction_actual_removed_ml") is not None]
    aligned_prediction_actual_removed = sum(aligned_actual_values) if aligned_actual_values else None
    prediction_time_aligned_sessions = sum(int(item.get("prediction_time_aligned_sessions", 0)) for item in room_results)
    prediction_time_aligned_rooms = sum(1 for item in room_results if int(item.get("prediction_time_aligned_sessions", 0)) > 0)
    aligned_prediction_error = (aligned_prediction_actual_removed - aligned_predicted_removed) if aligned_predicted_removed is not None and aligned_prediction_actual_removed is not None else None
    # Same-duration replay remains diagnostic evidence only. The aligned score
    # is still published exclusively when *all* aligned sessions are strict.
    # Partial house validation uses the already strict prediction_* subset below
    # instead of weakening any timestamp or measurement-frame gate.
    aligned_score_eligible = bool(
        prediction_time_aligned_sessions > 0
        and prediction_comparable_sessions == prediction_time_aligned_sessions
    )
    prediction_excluded_sessions = max(0, prediction_time_aligned_sessions - prediction_comparable_sessions)
    prediction_excluded_rooms = sum(
        1
        for item in room_results
        if int(item.get("prediction_time_aligned_sessions", 0)) > 0
        and int(item.get("prediction_comparable_sessions", 0)) == 0
    )
    aligned_prediction_accuracy = None
    if aligned_score_eligible and aligned_predicted_removed is not None and aligned_prediction_actual_removed is not None:
        aligned_denominator = max(abs(aligned_predicted_removed), abs(aligned_prediction_actual_removed), 1.0)
        aligned_prediction_accuracy = max(0.0, min(100.0, 100.0 - abs(aligned_prediction_error) / aligned_denominator * 100.0))
    prediction_error = (prediction_actual_removed - predicted_removed) if predicted_removed is not None and prediction_actual_removed is not None else None
    prediction_accuracy = None
    if predicted_removed is not None and prediction_actual_removed is not None:
        denominator = max(abs(predicted_removed), abs(prediction_actual_removed), 1.0)
        prediction_accuracy = max(0.0, min(100.0, 100.0 - abs(prediction_error) / denominator * 100.0))

    started_raw = group.get("started_at")
    started = None
    if started_raw:
        try:
            started = datetime.fromisoformat(str(started_raw))
        except (TypeError, ValueError):
            started = None
    if started is None:
        starts = []
        for event in sessions:
            raw = event.get("started_at")
            if raw:
                try:
                    starts.append(datetime.fromisoformat(str(raw)))
                except (TypeError, ValueError):
                    pass
        started = min(starts) if starts else ended_at
    duration_min = max(0.0, (ended_at - started).total_seconds() / 60.0)
    if duration_min <= 0:
        duration_min = max((float(item.get("duration_min", 0.0)) for item in room_results), default=0.0)

    followed = sum(1 for item in room_results if item.get("recommendation_followed"))
    learning_valid = sum(int(item.get("learning_valid_sessions", 0)) for item in room_results)
    contaminated = sum(1 for item in room_results if item.get("moisture_source_contaminated"))
    feedback_actions = [str(item.get("outcome_feedback_action")) for item in room_results if item.get("outcome_feedback_action")]
    feedback_priority = {"guarded_observation": 6, "cautious_confirmation": 5, "confirmed_outlier": 4, "guarded": 4, "cautious": 3, "applied": 2, "skipped": 1}
    feedback_action = max(feedback_actions, key=lambda x: feedback_priority.get(x, 0)) if feedback_actions else None
    if feedback_action == "guarded_observation":
        feedback_text = "Sehr große Prognoseabweichung erkannt. FreshAirIQ hat sie als Verdachtsprobe gespeichert, das Modell aber noch nicht verändert."
    elif feedback_action == "cautious_confirmation":
        feedback_text = "Eine zweite ähnliche große Abweichung bestätigt das Muster. FreshAirIQ passt das Modell erstmals sehr vorsichtig an."
    elif feedback_action == "confirmed_outlier":
        feedback_text = "Die große Abweichung wurde wiederholt bestätigt. FreshAirIQ übernimmt das Muster nun kontrolliert in zukünftige Prognosen."
    elif feedback_action == "guarded":
        feedback_text = "Sehr große Prognoseabweichung erkannt. FreshAirIQ hat das Modell nur minimal angepasst und wartet auf weitere bestätigende Lüftungen."
    elif feedback_action == "cautious":
        feedback_text = "Die Abweichung wurde erkannt. Die Messdaten fließen mit geringer Gewichtung in zukünftige Prognosen ein."
    elif feedback_action == "applied":
        feedback_text = "Die aktuellen Messdaten wurden in das Lernmodell übernommen und werden für zukünftige Prognosen verwendet."
    elif feedback_action == "skipped":
        feedback_text = "Diese Lüftung wurde nicht zur Prognoseanpassung verwendet, weil die Messung nicht eindeutig genug war."
    else:
        feedback_text = None

    if prediction_time_aligned_sessions > 0:
        if prediction_comparable_sessions == prediction_time_aligned_sessions:
            prediction_status_text = "Startprognose mit exakt derselben Messdauer verglichen"
            prediction_alignment_quality = "validated"
        elif prediction_comparable_sessions > 0:
            prediction_status_text = (
                f"Teilvalidierung: {prediction_comparable_rooms} von {prediction_time_aligned_rooms} "
                "Raum/Räumen für die Genauigkeitswertung verwertbar"
            )
            prediction_alignment_quality = "partial_validated"
        else:
            prediction_status_text = "Startprognose auf die tatsächliche Messdauer abgeglichen · Sensordaten nicht ausreichend synchron – keine Genauigkeitswertung"
            prediction_alignment_quality = "informational"
    elif prediction_comparable_rooms > 0:
        prediction_status_text = "Startprognose mit vergleichbarer Zeitbasis ausgewertet"
        prediction_alignment_quality = "legacy_validated"
    else:
        prediction_status_text = "Für diese Lüftung konnte beim Start keine auswertbare Prognose eingefroren werden"
        prediction_alignment_quality = "unavailable"

    return {
        "result_version": 2,
        "started_at": started.isoformat(),
        "ended_at": ended_at.isoformat(),
        "display_until": (ended_at + timedelta(minutes=max(display_minutes, 0.0))).isoformat(),
        "removed_ml": round(total_removed) if total_removed is not None else None,
        "measured_removed_ml_partial": round(measured_removed_partial) if measured_removed_partial is not None else None,
        "moisture_result_complete": moisture_result_complete,
        "moisture_measured_sessions": moisture_measured_sessions,
        "moisture_unmeasured_sessions": moisture_unmeasured_sessions,
        "duration_min": round(duration_min, 1),
        "room_minutes_total": round(total_room_minutes, 1),
        "temp_delta_c": round(avg_temp, 2) if avg_temp is not None else None,
        "energy_kwh": round(total_energy, 4),
        "cost": round(total_cost, 2),
        "rooms": [item["name"] for item in room_results],
        "room_results": room_results,
        "room_count": len(room_results),
        "session_count": len(sessions),
        "cross_ventilation": any(bool(item.get("cross_ventilation")) for item in sessions),
        "cross_ventilation_room_minutes_total": round(sum(max(_number(item.get("cross_ventilation_minutes")) or 0.0, 0.0) for item in sessions), 1),
        "recommendation_followed_count": followed,
        "learning_valid_count": learning_valid,
        "moisture_source_contaminated_rooms": contaminated,
        "predicted_removed_ml": round(predicted_removed) if predicted_removed is not None else None,
        "prediction_actual_removed_ml": round(prediction_actual_removed) if prediction_actual_removed is not None else None,
        "prediction_comparable_sessions": prediction_comparable_sessions,
        "prediction_comparable_rooms": prediction_comparable_rooms,
        "prediction_error_ml": round(prediction_error) if prediction_error is not None else None,
        "prediction_accuracy_percent": round(prediction_accuracy) if prediction_accuracy is not None else None,
        "aligned_predicted_removed_ml": round(aligned_predicted_removed) if aligned_predicted_removed is not None else None,
        "aligned_prediction_actual_removed_ml": round(aligned_prediction_actual_removed) if aligned_prediction_actual_removed is not None else None,
        "aligned_prediction_error_ml": round(aligned_prediction_error) if aligned_prediction_error is not None else None,
        "aligned_prediction_accuracy_percent": round(aligned_prediction_accuracy) if aligned_prediction_accuracy is not None else None,
        "prediction_time_aligned_sessions": prediction_time_aligned_sessions,
        "prediction_time_aligned_rooms": prediction_time_aligned_rooms,
        "prediction_excluded_sessions": prediction_excluded_sessions,
        "prediction_excluded_rooms": prediction_excluded_rooms,
        "prediction_status_text": prediction_status_text,
        "prediction_alignment_quality": prediction_alignment_quality,
        "learning_feedback_action": feedback_action,
        "learning_feedback_text": feedback_text,
    }
