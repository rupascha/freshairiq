"""Central FreshAirIQ intelligence layer and behavioural learning helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .routines import learn_response_pattern, routine_maturity
from .strategy import ensure_strategy_defaults, learn_strategy_opportunity, learn_strategy_outcome, strategy_maturity
from .seasonality import ensure_seasonal_defaults, seasonal_house_maturity
from .shadow_learning import ensure_shadow_defaults, process_shadow_feedback


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _mean(values: list[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default


def _iso_age_minutes(value: Any, now: datetime) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, (now - datetime.fromisoformat(str(value))).total_seconds() / 60.0)
    except (TypeError, ValueError):
        return None


def ensure_behaviour_defaults(room: dict[str, Any]) -> None:
    """Add behavioural-learning fields without invalidating older storage."""
    defaults = {
        "recommendation_opportunities": 0,
        "recommendation_followed": 0,
        "recommendation_missed": 0,
        "recommendation_follow_rate": None,
        "avg_follow_delay_min": None,
        "follow_delay_samples": 0,
        "preferred_duration_min": None,
        "duration_samples": 0,
        "avg_duration_deviation_min": None,
        "session_recommended_duration_min": None,
        "session_recommendation_followed": False,
        "session_recommendation_issued_at": None,
        "session_predicted_removed_ml": None,
        "session_predicted_temperature_change_c": None,
        "session_predicted_cost": None,
        "session_prediction_confidence": None,
        "session_prediction_snapshot_at": None,
        "session_prediction_horizon_min": None,
        "session_prediction_snapshot_valid": False,
        "session_prediction_snapshot_pending": False,
        "session_prediction_reference": None,
        "session_validation_id": None,
        "session_prediction_start_context": None,
        "session_prediction_time_aligned": False,
        "session_prediction_snapshot_frame_quality": None,
        "session_prediction_snapshot_frame_skew_s": None,
        "session_prediction_snapshot_frame_max_age_s": None,
        "session_selected_option_id": None,
        "outcome_feedback_samples": 0,
        "outcome_removed_factor": 1.0,
        "outcome_temperature_factor": 1.0,
        "outcome_avg_removed_error_ml": None,
        "outcome_avg_temperature_error_c": None,
        "outcome_success_rate": None,
        "outcome_successes": 0,
        "outcome_guarded_direction": None,
        "outcome_guarded_streak": 0,
        "outcome_guarded_last_ratio": None,
        "last_outcome_feedback_applied": False,
        "routine_source_buckets": {},
        "routine_response_buckets": {},
        "routine_observation_at": None,
        "routine_source_samples": 0,
        "routine_response_samples": 0,
        "seasonal_source_profiles": {},
        "seasonal_samples": 0,
        "long_term_source_ml_min": None,
        "long_term_source_samples": 0,
        "long_term_updated_at": None,
        "post_close_active": False,
        "post_close_event_id": None,
        "post_close_room_key": None,
        "post_close_room_name": None,
        "post_close_started_at": None,
        "post_close_ah": None,
        "post_close_temp_c": None,
        "post_close_removed_ml": None,
        "post_close_volume_m3": None,
        "post_close_start_frame_quality": None,
        "post_close_contaminated": False,
        "post_close_samples": [],
        "post_close_last_sample_at": None,
        "post_close_last_outcome": None,
    }
    for key, value in defaults.items():
        room.setdefault(key, value)
    ensure_strategy_defaults(room)
    ensure_seasonal_defaults(room)
    ensure_shadow_defaults(room)


def mark_recommendation_followed(store_data: dict[str, Any], room: dict[str, Any], room_key: str, now: datetime) -> bool:
    """Attach a currently active IQ recommendation to a newly started session."""
    ensure_behaviour_defaults(room)
    advice = store_data.get("iq_active_advice")
    if not isinstance(advice, dict) or room_key not in list(advice.get("room_keys") or []):
        return False
    age = _iso_age_minutes(advice.get("issued_at"), now)
    if age is None or age > 120.0:
        return False

    advice["followed"] = True
    advice["followed_at"] = now.isoformat()
    followed_keys = set(advice.get("followed_room_keys") or [])
    followed_keys.add(room_key)
    advice["followed_room_keys"] = sorted(followed_keys)
    follow_delays = advice.setdefault("follow_delay_by_room", {})
    follow_delays[room_key] = round(float(age), 1)

    room["session_recommendation_followed"] = True
    room["session_recommendation_issued_at"] = advice.get("issued_at")
    room["session_recommended_duration_min"] = advice.get("duration_min")
    room["session_predicted_removed_ml"] = advice.get("estimated_removed_ml")
    room["session_predicted_temperature_change_c"] = advice.get("expected_temperature_change_c")
    room["session_predicted_cost"] = advice.get("estimated_reheat_cost")
    room["session_prediction_confidence"] = advice.get("forecast_confidence")
    room["session_selected_option_id"] = advice.get("selected_option_id")

    old_samples = int(room.get("follow_delay_samples", 0))
    old_avg = room.get("avg_follow_delay_min")
    delay = float(age)
    alpha = 1.0 if old_avg is None or old_samples <= 0 else (0.25 if old_samples < 8 else 0.12)
    room["avg_follow_delay_min"] = round(delay if old_avg is None else float(old_avg) * (1 - alpha) + delay * alpha, 1)
    room["follow_delay_samples"] = min(old_samples + 1, 1000)
    return True


def _finalize_advice(store_data: dict[str, Any]) -> None:
    advice = store_data.get("iq_active_advice")
    if not isinstance(advice, dict):
        return
    followed_keys = set(advice.get("followed_room_keys") or [])
    for key in list(advice.get("room_keys") or []):
        room = store_data.setdefault("rooms", {}).get(key)
        if not isinstance(room, dict):
            continue
        ensure_behaviour_defaults(room)
        room["recommendation_opportunities"] = min(int(room.get("recommendation_opportunities", 0)) + 1, 100000)
        if key in followed_keys:
            room["recommendation_followed"] = min(int(room.get("recommendation_followed", 0)) + 1, 100000)
        else:
            room["recommendation_missed"] = min(int(room.get("recommendation_missed", 0)) + 1, 100000)
        opportunities = max(int(room.get("recommendation_opportunities", 0)), 1)
        room["recommendation_follow_rate"] = round(100.0 * int(room.get("recommendation_followed", 0)) / opportunities, 1)
        try:
            issued = datetime.fromisoformat(str(advice.get("issued_at")))
        except (TypeError, ValueError):
            issued = None
        if issued is not None:
            delays = advice.get("follow_delay_by_room") if isinstance(advice.get("follow_delay_by_room"), dict) else {}
            delay = delays.get(key) if key in followed_keys else None
            learn_response_pattern(room, issued, key in followed_keys, delay)
            learn_strategy_opportunity(
                room, advice.get("selected_option_id"), advice.get("duration_min"),
                key in followed_keys, delay,
            )


def sync_active_recommendation(store_data: dict[str, Any], recommendation: dict[str, Any], now: datetime) -> bool:
    """Track one recommendation episode instead of counting every coordinator refresh."""
    kind = str(recommendation.get("kind") or "")
    room_keys = sorted(str(x) for x in (recommendation.get("room_keys") or []))
    trackable = kind in {"ventilate", "pollen_wait", "wait", "prepare"} and bool(room_keys)
    signature = f"{kind}|{','.join(room_keys)}" if trackable else ""
    previous = store_data.get("iq_active_advice")
    previous_signature = str(previous.get("signature") or "") if isinstance(previous, dict) else ""

    if previous_signature and previous_signature != signature:
        _finalize_advice(store_data)
        store_data["iq_active_advice"] = None

    if not trackable:
        return bool(previous_signature)

    if signature != previous_signature:
        store_data["iq_active_advice"] = {
            "signature": signature,
            "kind": kind,
            "issued_at": now.isoformat(),
            "room_keys": room_keys,
            "duration_min": recommendation.get("duration_min"),
            "estimated_removed_ml": recommendation.get("estimated_removed_ml"),
            "expected_temperature_change_c": recommendation.get("expected_temperature_change_c"),
            "estimated_reheat_cost": recommendation.get("estimated_reheat_cost"),
            "forecast_confidence": recommendation.get("forecast_confidence"),
            "selected_option_id": recommendation.get("selected_option_id"),
            "followed": False,
            "followed_room_keys": [],
            "follow_delay_by_room": {},
        }
        return True

    # Keep the original issue time, but let the recommended duration evolve.
    if isinstance(previous, dict):
        previous["duration_min"] = recommendation.get("duration_min")
        previous["estimated_removed_ml"] = recommendation.get("estimated_removed_ml")
        previous["expected_temperature_change_c"] = recommendation.get("expected_temperature_change_c")
        previous["estimated_reheat_cost"] = recommendation.get("estimated_reheat_cost")
        previous["forecast_confidence"] = recommendation.get("forecast_confidence")
        previous["selected_option_id"] = recommendation.get("selected_option_id")
    return False


def learn_completed_session(room: dict[str, Any], duration_min: float) -> None:
    """Learn the resident's actual ventilation duration and recommendation deviation."""
    ensure_behaviour_defaults(room)
    duration = _clamp(duration_min, 0.0, 240.0)
    old_samples = int(room.get("duration_samples", 0))
    old_duration = room.get("preferred_duration_min")
    alpha = 1.0 if old_duration is None or old_samples <= 0 else (0.22 if old_samples < 8 else 0.10)
    room["preferred_duration_min"] = round(duration if old_duration is None else float(old_duration) * (1 - alpha) + duration * alpha, 1)
    room["duration_samples"] = min(old_samples + 1, 1000)

    rec_duration = room.get("session_recommended_duration_min")
    if rec_duration is not None:
        deviation = duration - float(rec_duration)
        old_dev = room.get("avg_duration_deviation_min")
        beta = 1.0 if old_dev is None else (0.22 if old_samples < 8 else 0.10)
        room["avg_duration_deviation_min"] = round(deviation if old_dev is None else float(old_dev) * (1 - beta) + deviation * beta, 1)



def learn_outcome_feedback(room: dict[str, Any], actual_removed_ml: float, actual_temperature_change_c: float) -> bool:
    """Process forecast outcome feedback and calibrate only trustworthy patterns.

    Returns True when the feedback sample was processed. Whether coefficients
    were actually changed is exposed separately via
    ``last_outcome_feedback_applied`` so a first extreme outlier can be retained
    as evidence without silently changing the model.
    """
    ensure_behaviour_defaults(room)
    room["last_outcome_feedback_applied"] = False
    # Physical forecast calibration is independent of whether the user
    # explicitly followed a FreshAirIQ recommendation. Every trustworthy
    # measured ventilation may teach the physical model; recommendation
    # following remains a separate behavioural signal.
    if not bool(room.get("session_prediction_snapshot_valid")):
        return False
    predicted_removed = room.get("session_predicted_removed_ml")
    if predicted_removed is None or float(predicted_removed) < 20.0:
        return False

    actual_removed = float(actual_removed_ml)
    predicted_removed = max(float(predicted_removed), 1.0)
    raw_ratio = actual_removed / predicted_removed
    removed_error = actual_removed - predicted_removed
    denominator = max(abs(predicted_removed), abs(actual_removed), 1.0)
    accuracy = max(0.0, min(100.0, 100.0 - abs(removed_error) / denominator * 100.0))
    samples = int(room.get("outcome_feedback_samples", 0))
    base_alpha = 0.24 if samples < 6 else 0.12
    try:
        learning_weight = _clamp(float(room.get("session_prediction_learning_weight", 1.0)), 0.10, 1.0)
    except (TypeError, ValueError, OverflowError):
        learning_weight = 1.0
    base_alpha *= learning_weight
    abs_error = abs(removed_error)

    guarded_sample = accuracy < 40.0 and abs_error > 80.0
    if guarded_sample:
        direction = "actual_lower" if raw_ratio < 1.0 else "actual_higher"
        previous_direction = room.get("outcome_guarded_direction")
        try:
            previous_ratio = float(room.get("outcome_guarded_last_ratio"))
        except (TypeError, ValueError):
            previous_ratio = None
        previous_streak = int(room.get("outcome_guarded_streak", 0) or 0)
        similar = (
            previous_direction == direction
            and previous_ratio is not None
            and abs(raw_ratio - previous_ratio) <= max(0.20, abs(previous_ratio) * 0.35)
        )
        streak = min(previous_streak + 1, 3) if similar else 1
        room["outcome_guarded_direction"] = direction
        room["outcome_guarded_streak"] = streak
        room["outcome_guarded_last_ratio"] = round(raw_ratio, 4)

        if streak == 1:
            alpha = 0.0
            feedback_action = "guarded_observation"
            feedback_reason = "Sehr große Prognoseabweichung erkannt. FreshAirIQ speichert sie zunächst nur als Verdachtsprobe; das Prognosemodell bleibt unverändert, bis eine ähnliche Abweichung bestätigt wird."
        elif streak == 2:
            alpha = min(base_alpha, 0.04)
            feedback_action = "cautious_confirmation"
            feedback_reason = "Eine zweite ähnliche große Abweichung bestätigt das Muster. FreshAirIQ passt das Modell erstmals mit sehr geringer Gewichtung an."
        else:
            alpha = min(base_alpha, 0.08)
            feedback_action = "confirmed_outlier"
            feedback_reason = "Die große Abweichung wurde wiederholt bestätigt. FreshAirIQ übernimmt das stabile Muster nun kontrolliert in das Prognosemodell."
    else:
        room["outcome_guarded_direction"] = None
        room["outcome_guarded_streak"] = 0
        room["outcome_guarded_last_ratio"] = None
        if abs_error <= 15.0:
            alpha = min(base_alpha, 0.08)
            feedback_action = "applied"
            feedback_reason = "Kleine Prognoseabweichung im normalen Mess- und Modellrauschen; die Messdaten werden behutsam übernommen."
        elif accuracy >= 70.0 or abs_error <= 35.0:
            alpha = base_alpha
            feedback_action = "applied"
            feedback_reason = "Messdaten wurden regulär in das Lernmodell übernommen und verfeinern künftige Prognosen."
        else:
            alpha = min(base_alpha, 0.06)
            feedback_action = "cautious"
            feedback_reason = "Deutliche Abweichung erkannt; FreshAirIQ führt das Modell nur vorsichtig nach."

    # Residual statistics are diagnostic evidence, not forecast coefficients.
    # Preserve them even for an unapplied first outlier so later confirmation
    # and diagnostics can explain what happened without contaminating the model.
    stats_alpha = 1.0 if room.get("outcome_avg_removed_error_ml") is None else min(base_alpha, 0.08)
    old_err = room.get("outcome_avg_removed_error_ml")
    room["outcome_avg_removed_error_ml"] = round(removed_error if old_err is None else float(old_err) * (1.0-stats_alpha) + removed_error * stats_alpha, 1)

    predicted_temp = room.get("session_predicted_temperature_change_c")
    if predicted_temp is not None and abs(float(predicted_temp)) >= 0.10:
        temp_error = float(actual_temperature_change_c) - float(predicted_temp)
        old_temp_err = room.get("outcome_avg_temperature_error_c")
        room["outcome_avg_temperature_error_c"] = round(temp_error if old_temp_err is None else float(old_temp_err) * (1.0-stats_alpha) + temp_error * stats_alpha, 2)

    # Learning 3.0: moisture calibration no longer changes after every single
    # session. Competing shadow multipliers are scored against real outcomes and
    # may only replace the production factor after repeated superiority.
    # Slowly reporting held frames are legitimate evidence, but one such frame
    # must not count like a fully synchronized sample in Learning 3.0. Accumulate
    # their fractional weight and only advance the shadow competition after
    # enough cautious evidence has accumulated to one full sample.
    if learning_weight < 0.999:
        accumulator = _clamp(float(room.get("shadow_learning_weight_accumulator", 0.0) or 0.0) + learning_weight, 0.0, 2.0)
        if accumulator >= 1.0:
            room["shadow_learning_weight_accumulator"] = round(accumulator - 1.0, 4)
            shadow_result = process_shadow_feedback(
                room, predicted_removed_ml=predicted_removed, actual_removed_ml=actual_removed
            )
        else:
            room["shadow_learning_weight_accumulator"] = round(accumulator, 4)
            shadow_result = {"action": "observing", "reason": "weighted_held_sample"}
    else:
        shadow_result = process_shadow_feedback(
            room, predicted_removed_ml=predicted_removed, actual_removed_ml=actual_removed
        )
    shadow_action = str(shadow_result.get("action") or "observing")

    if alpha > 0.0 and predicted_temp is not None and abs(float(predicted_temp)) >= 0.10:
        temp_ratio = _clamp(abs(float(actual_temperature_change_c)) / max(abs(float(predicted_temp)), 0.10), 0.40, 1.70)
        old_temp_factor = float(room.get("outcome_temperature_factor", 1.0) or 1.0)
        room["outcome_temperature_factor"] = round(old_temp_factor * (1.0-alpha) + temp_ratio * alpha, 3)
        room["last_outcome_feedback_applied"] = True
    if shadow_action in {"promoted", "rollback"}:
        room["last_outcome_feedback_applied"] = True
    if shadow_action == "promoted":
        feedback_action = "shadow_promoted"
        feedback_reason = (
            "Learning 3.0 hat ein alternatives Prognosemodell erst nach wiederholtem Realvergleich übernommen. "
            "Die Anpassung läuft nun in einem automatischen Rollback-Schutzfenster."
        )
    elif shadow_action == "rollback":
        feedback_action = "shadow_rollback"
        feedback_reason = (
            "Die letzte Learning-3.0-Anpassung hat sich in den Folgemessungen nicht bestätigt und wurde automatisch zurückgenommen."
        )
    elif shadow_action in {"observing", "guarding_promotion", "no_promotion"}:
        feedback_reason += " · Learning 3.0 bewertet parallel unverbindliche Shadow-Modelle; das produktive Feuchtemodell bleibt bis zu belastbarer Evidenz unverändert."

    room["last_outcome_feedback_action"] = feedback_action
    room["last_outcome_feedback_reason"] = feedback_reason
    room["last_outcome_feedback_accuracy"] = round(accuracy, 1)
    room["outcome_feedback_samples"] = min(samples + 1, 1000)
    successful = actual_removed >= predicted_removed * 0.70
    if successful:
        room["outcome_successes"] = min(int(room.get("outcome_successes", 0)) + 1, 1000)
    room["outcome_success_rate"] = round(100.0 * int(room.get("outcome_successes", 0)) / max(int(room["outcome_feedback_samples"]), 1), 1)
    learn_strategy_outcome(
        room, room.get("session_selected_option_id"), room.get("session_recommended_duration_min"),
        successful=successful, observed_at=datetime.now().astimezone(),
    )
    return True


def clear_session_behaviour(room: dict[str, Any]) -> None:
    ensure_behaviour_defaults(room)
    room["session_recommended_duration_min"] = None
    room["session_recommendation_followed"] = False
    room["session_recommendation_issued_at"] = None
    room["session_predicted_removed_ml"] = None
    room["session_predicted_temperature_change_c"] = None
    room["session_predicted_cost"] = None
    room["session_prediction_confidence"] = None
    room["session_prediction_snapshot_at"] = None
    room["session_prediction_horizon_min"] = None
    room["session_prediction_snapshot_valid"] = False
    room["session_prediction_snapshot_pending"] = False
    room["session_prediction_reference"] = None
    room["session_validation_id"] = None
    room["session_prediction_start_context"] = None
    room["session_prediction_time_aligned"] = False
    room["session_prediction_snapshot_frame_quality"] = None
    room["session_prediction_snapshot_frame_skew_s"] = None
    room["session_prediction_snapshot_frame_max_age_s"] = None
    room["session_selected_option_id"] = None


def build_intelligence_state(
    rooms: dict[str, dict[str, Any]], recommendation: dict[str, Any], *,
    forecast_confidence: float, overnight_confidence: float, presence_confidence: float,
    night_samples: int, now: datetime | None = None,
) -> dict[str, Any]:
    """Build the compact, explainable state presented as the FreshAirIQ brain."""
    calculated = [r for r in rooms.values() if r.get("calculation_enabled", True)]
    valid = [r for r in calculated if r.get("data_quality") == "ok"]
    learning_samples = [max(int(r.get("learning_samples", 0)), 0) for r in valid]
    behaviour_samples = [max(int(r.get("behaviour_duration_samples", 0)), 0) for r in valid]
    learning_maturity = _mean([min(x / 20.0, 1.0) for x in learning_samples], 0.0) * 100.0
    behaviour_maturity = _mean([min(x / 20.0, 1.0) for x in behaviour_samples], 0.0) * 100.0
    routine_maturities = [routine_maturity(r) for r in valid]
    routine_learning_maturity = _mean(routine_maturities, 0.0)
    strategy_maturities = [strategy_maturity(r) for r in valid]
    strategy_learning_maturity = _mean(strategy_maturities, 0.0)
    seasonal_learning_maturity = seasonal_house_maturity(valid, now or datetime.now())
    house_strategy_learning_maturity = float(
        (recommendation.get("house_strategy") or {}).get("maturity", 0.0)
        if isinstance(recommendation.get("house_strategy"), dict) else 0.0
    )
    data_quality = 100.0 * len(valid) / max(len(calculated), 1)

    selected_conf = float(recommendation.get("forecast_confidence") or forecast_confidence or 0.0)
    if selected_conf <= 0:
        selected_conf = float(forecast_confidence or 0.0)
    confidence = (
        selected_conf * 0.38
        + data_quality * 0.22
        + learning_maturity * 0.195
        + _clamp(presence_confidence, 0, 100) * 0.10
        + _clamp(overnight_confidence, 0, 100) * 0.05
        + min(max(int(night_samples), 0) / 12.0, 1.0) * 100.0 * 0.03
        + routine_learning_maturity * 0.015
        + strategy_learning_maturity * 0.005
        + seasonal_learning_maturity * 0.003
        + house_strategy_learning_maturity * 0.002
    )
    confidence = int(round(_clamp(confidence, 15.0 if valid else 0.0, 98.0)))

    if confidence >= 85:
        confidence_label = "Sehr hohe Sicherheit"
    elif confidence >= 70:
        confidence_label = "Hohe Sicherheit"
    elif confidence >= 50:
        confidence_label = "Mittlere Sicherheit"
    else:
        confidence_label = "Noch geringe Sicherheit"

    kind = str(recommendation.get("kind") or "okay")
    status_map = {
        "close": ("acting", "Lüftung beenden"),
        "continue": ("coaching", "Lüftung überwachen"),
        "ventilate": ("recommending", "Beste Aktion berechnet"),
        "pollen_wait": ("protecting", "Pollenrisiko abwägen"),
        "wait": ("observing", "Entwicklung beobachten"),
        "prepare": ("predicting", "Nachtentwicklung vorausberechnen"),
        "sensor": ("limited", "Datenqualität prüfen"),
        "okay": ("monitoring", "Hausklima überwachen"),
    }
    mode, headline = status_map.get(kind, ("analyzing", "Hausdaten analysieren"))
    anticipation = recommendation.get("anticipation") if isinstance(recommendation.get("anticipation"), dict) else {}
    if anticipation.get("active"):
        if recommendation.get("anticipatory_action"):
            mode, headline = "predicting", "Bevorstehende Entwicklung erkannt"
        elif kind == "okay":
            mode, headline = "predicting", "Routineentwicklung vorausberechnen"

    activities = ["Raumklima bewertet", "Außenluft verglichen"]
    if kind in {"ventilate", "continue", "close", "wait", "prepare"}:
        activities.append("Lüftungsoptionen bewertet")
    if int(night_samples) > 0:
        activities.append("Nachtmodell berücksichtigt")
    if learning_samples and max(learning_samples) > 0:
        activities.append("Raumlernen berücksichtigt")
    if any(int(r.get("behaviour_duration_samples", 0)) > 0 for r in valid):
        activities.append("Bewohnerverhalten berücksichtigt")
    if recommendation.get("future_weather_used"):
        activities.append("Wetterentwicklung simuliert")
    if any(int(r.get("outcome_feedback_samples", 0)) > 0 for r in valid):
        activities.append("Prognosefeedback berücksichtigt")
    if routine_learning_maturity >= 10:
        activities.append("Tagesroutinen berücksichtigt")
    if strategy_learning_maturity >= 10:
        activities.append("Nutzerstrategie optimiert")
    if seasonal_learning_maturity >= 10:
        activities.append("Saisonverhalten berücksichtigt")
    if house_strategy_learning_maturity >= 10:
        activities.append("Hausstrategie berücksichtigt")
    if anticipation.get("active"):
        activities.append("Bevorstehendes Feuchtemuster erkannt")
    plan = recommendation.get("day_night_plan") if isinstance(recommendation.get("day_night_plan"), dict) else {}
    if plan.get("active"):
        activities.append("Tages- & Nachtfenster geplant")
    if recommendation.get("consolidation_checks"):
        activities.append("Entscheidung konsolidiert")
    activities = activities[-4:]

    # Intelligence 2.0: the top stage requires both a mature house model and
    # mature personal behaviour evidence. It is intentionally hard to reach.
    if learning_maturity >= 92 and behaviour_maturity >= 85 and strategy_learning_maturity >= 80:
        learning_label = "Auf deine Bedürfnisse optimiert"
    elif learning_maturity >= 78 and behaviour_maturity >= 60:
        learning_label = "Sehr gut eingelernt"
    elif learning_maturity >= 62:
        learning_label = "Eingelernt"
    elif learning_maturity >= 45:
        learning_label = "Bestätigt"
    elif learning_maturity >= 28:
        learning_label = "Muster erkannt"
    elif learning_maturity >= 12:
        learning_label = "Beobachtet"
    else:
        learning_label = "Grundmodell"

    return {
        "mode": mode,
        "headline": headline,
        "summary": str(recommendation.get("summary") or "FreshAirIQ überwacht das Hausklima."),
        "confidence": confidence,
        "confidence_label": confidence_label,
        "learning_label": learning_label,
        "learning_maturity": round(learning_maturity),
        "behaviour_maturity": round(behaviour_maturity),
        "routine_maturity": round(routine_learning_maturity),
        "strategy_maturity": round(strategy_learning_maturity),
        "seasonal_maturity": round(seasonal_learning_maturity),
        "house_strategy_maturity": round(house_strategy_learning_maturity),
        "data_quality": round(data_quality),
        "activities": activities,
        "explanation": list(recommendation.get("reasons") or []),
        "decision": {
            "title": recommendation.get("title"),
            "instruction": recommendation.get("instruction"),
            "room_keys": list(recommendation.get("room_keys") or []),
            "duration_min": recommendation.get("duration_min"),
            "estimated_removed_ml": recommendation.get("estimated_removed_ml"),
            "expected_temperature_change_c": recommendation.get("expected_temperature_change_c"),
            "estimated_reheat_cost": recommendation.get("estimated_reheat_cost"),
            "selected_option_id": recommendation.get("selected_option_id"),
            "selected_option_label": recommendation.get("selected_option_label"),
            "decision_engine": recommendation.get("decision_engine"),
            "simulated_options": list(recommendation.get("simulated_options") or []),
        },
    }
