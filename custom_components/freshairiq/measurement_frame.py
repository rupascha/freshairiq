"""Time-coherent sensor measurement frames for FreshAirIQ.

A room forecast combines temperature, relative humidity and a reference-air
measurement.  Those values can arrive at different times in Home Assistant.
This module quantifies that temporal mismatch without changing the measured
values themselves.  Forecasts may continue to use valid values, while adaptive
learning and objective validation can reject frames that are too asynchronous.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

FRAME_EXCELLENT_SKEW_S = 30.0
FRAME_ACCEPTABLE_SKEW_S = 90.0
FRAME_UNCERTAIN_SKEW_S = 180.0
# Battery climate sensors often report temperature and humidity only when the
# value changes. A held frame is therefore allowed for *adaptive room learning*
# only, never for objective forecast validation. This prevents throwing away
# virtually every real-world session without pretending stale data is precise.
FRAME_HELD_SKEW_S = 1800.0
ROOM_HELD_MAX_AGE_S = 2400.0
REFERENCE_HELD_SKEW_S = 1800.0
REFERENCE_HELD_MAX_AGE_S = 3600.0
ROOM_EXCELLENT_MAX_AGE_S = 300.0
ROOM_ACCEPTABLE_MAX_AGE_S = 600.0
ROOM_USABLE_MAX_AGE_S = 1200.0
# Outdoor/weather reference entities commonly publish slower than room climate
# sensors. Treat their own pair coherence strictly, but allow a slower cadence
# before declaring the complete frame unusable.
REFERENCE_EXCELLENT_MAX_AGE_S = 900.0
REFERENCE_ACCEPTABLE_MAX_AGE_S = 1800.0
REFERENCE_USABLE_MAX_AGE_S = 3600.0
MAX_FUTURE_TIMESTAMP_S = 60.0


SESSION_ACTIVITY_REQUIRED_REPORTS = 2


def session_measurement_quality(
    fresh_reports: int,
    *,
    temperature_reports: int | None = None,
    humidity_reports: int | None = None,
    final_temperature_feedback: bool = False,
    final_humidity_feedback: bool = False,
) -> dict[str, Any]:
    """Return session-specific measurement quality for low-cadence sensors.

    The hard learning gate is based on sensor-report timestamps, not on the age
    of the currently held numeric value. Production callers provide split
    temperature/humidity counters that are incremented only when Home Assistant
    advances ``last_reported`` (or ``last_updated`` on older HA versions) *after*
    the physical opening and no later than the detected physical close.

    A learning/validation sample is therefore trustworthy only when both climate
    channels have proved activity during this exact ventilation and the combined
    activity contains at least two reports. A post-close refresh may improve the
    end boundary to ``high`` quality, but it can never satisfy the in-session
    timestamp gate retroactively.

    ``temperature_reports`` / ``humidity_reports`` remain optional only for
    compatibility with isolated pure-logic callers. Coordinator production paths
    always provide both counters and therefore use the strict per-channel gate.
    """
    try:
        reports = max(int(fresh_reports), 0)
    except (TypeError, ValueError, OverflowError):
        reports = 0

    split_activity_available = temperature_reports is not None or humidity_reports is not None
    try:
        temp_reports = max(int(temperature_reports or 0), 0)
    except (TypeError, ValueError, OverflowError):
        temp_reports = 0
    try:
        rh_reports = max(int(humidity_reports or 0), 0)
    except (TypeError, ValueError, OverflowError):
        rh_reports = 0

    if split_activity_available:
        reports = max(reports, temp_reports + rh_reports)
        timestamp_gate_passed = (
            reports >= SESSION_ACTIVITY_REQUIRED_REPORTS
            and temp_reports >= 1
            and rh_reports >= 1
        )
    else:
        # Compatibility only. Production learning never reaches this branch.
        timestamp_gate_passed = reports >= SESSION_ACTIVITY_REQUIRED_REPORTS

    end_feedback_count = int(bool(final_temperature_feedback)) + int(bool(final_humidity_feedback))
    if timestamp_gate_passed:
        quality = "high" if end_feedback_count >= 2 else "good"
        eligible = True
        weight = 1.0 if quality == "high" else 0.75
        reason = (
            "Temperatur und Luftfeuchtigkeit haben während dieser Lüftung jeweils mindestens eine neue Meldung geliefert; zusätzlich kamen nach dem Schließen frische Temperatur- und Feuchtewerte zurück."
            if quality == "high" else
            "Temperatur und Luftfeuchtigkeit haben während dieser Lüftung jeweils mindestens eine neue Meldung geliefert; die Session ist lernfähig, auch wenn der Abschluss-Refresh nicht beide Kanäle erneut erreicht hat."
        )
    elif reports >= SESSION_ACTIVITY_REQUIRED_REPORTS and split_activity_available:
        quality = "limited"
        eligible = False
        weight = 0.0
        missing = []
        if temp_reports < 1:
            missing.append("Temperatur")
        if rh_reports < 1:
            missing.append("Luftfeuchtigkeit")
        missing_text = " und ".join(missing) or "ein Klimakanal"
        reason = (
            f"Mehrere Meldungen wurden empfangen, aber {missing_text} hat seit dem Öffnen keinen neuen Zeitstempel geliefert. "
            "Diese Werte dürfen nicht in physikalisches Lernen oder Prognosekalibrierung einfließen."
        )
    elif reports == 1:
        quality = "limited"
        eligible = False
        weight = 0.0
        reason = "Nur eine neue Klimameldung seit dem Öffnen; der Zeitstempelverlauf reicht nicht für Lernen oder Prognosebewertung."
    else:
        quality = "insufficient"
        eligible = False
        weight = 0.0
        reason = "Seit dem Öffnen wurde keine neue Raumklimameldung mit neuerem Zeitstempel beobachtet; vor der Lüftung gehaltene Werte dürfen nicht zum Lernen verwendet werden."
    return {
        "quality": quality,
        "eligible": eligible,
        "timestamp_gate_passed": bool(timestamp_gate_passed),
        "learning_weight": weight,
        "fresh_reports": reports,
        "temperature_reports": temp_reports if split_activity_available else None,
        "humidity_reports": rh_reports if split_activity_available else None,
        "final_feedback_count": end_feedback_count,
        "reason": reason,
    }


def trusted_session_end_baseline(
    *,
    timestamp_gate_passed: bool,
    end_humidity: Any,
    end_absolute_humidity: Any,
    reference_absolute_humidity: Any,
) -> dict[str, float | None]:
    """Return end baselines only when this session has trustworthy evidence.

    Repeat-recommendation and anti-flap logic must never compare current values
    against a room-climate value that predates the just-finished ventilation.
    Therefore an in-session timestamp-gate failure clears all measurement-based
    baselines for that session. The ventilation end time may still be recorded
    separately so temporal cooldowns continue to reflect that a ventilation
    actually occurred.
    """
    if not timestamp_gate_passed:
        return {
            "end_humidity": None,
            "end_absolute_humidity": None,
            "reference_absolute_humidity": None,
        }

    def _finite(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number

    return {
        "end_humidity": _finite(end_humidity),
        "end_absolute_humidity": _finite(end_absolute_humidity),
        "reference_absolute_humidity": _finite(reference_absolute_humidity),
    }


def last_valid_session_measurement(room: Any) -> dict[str, float] | None:
    """Return the last persisted valid climate snapshot for session finalisation.

    The end-refresh is deliberately best-effort. If a sensor is temporarily
    ``unavailable`` when the grace window expires, FreshAirIQ may finish with
    the most recent numeric climate values it already observed during this
    session. This does *not* create timestamp evidence: learning eligibility is
    still decided exclusively by :func:`session_measurement_quality`.
    """
    if not isinstance(room, dict):
        return None

    def _finite(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number

    temperature = _finite(room.get("session_last_valid_temperature"))
    humidity = _finite(room.get("session_last_valid_humidity"))
    reference_temperature = _finite(room.get("session_last_valid_reference_temperature"))
    reference_humidity = _finite(room.get("session_last_valid_reference_humidity"))
    if (
        temperature is None or humidity is None
        or reference_temperature is None or reference_humidity is None
        or not (-10 < temperature < 50)
        or not (5 <= humidity <= 100)
        or not (-30 < reference_temperature < 60)
        or not (0 <= reference_humidity <= 100)
    ):
        return None
    return {
        "temperature": temperature,
        "humidity": humidity,
        "reference_temperature": reference_temperature,
        "reference_humidity": reference_humidity,
    }


def state_reported_at(state: Any) -> datetime | None:
    """Return the best timestamp representing the latest sensor report."""
    if state is None:
        return None
    return getattr(state, "last_reported", None) or getattr(state, "last_updated", None)


def report_timestamp_after_boundary(report_timestamp: Any, boundary: Any) -> bool:
    """Return whether a sensor report happened strictly after a physical boundary.

    ``report_timestamp`` and ``boundary`` may be aware ``datetime`` objects or
    ISO strings persisted by the coordinator.  A timezone mismatch is rejected
    instead of guessed so a clock/restore anomaly can never manufacture fresh
    evidence.
    """
    def _coerce(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if value in (None, ""):
            return None
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError, OverflowError):
            return None

    report = _coerce(report_timestamp)
    limit = _coerce(boundary)
    if report is None or limit is None:
        return False
    if (report.tzinfo is None) != (limit.tzinfo is None):
        return False
    return report > limit


def _age_seconds(now: datetime, state: Any) -> float | None:
    stamp = state_reported_at(state)
    if stamp is None:
        return None
    try:
        age = (now - stamp).total_seconds()
    except (TypeError, ValueError):
        return None
    # Clock corrections or mocked timestamps must never create negative ages.
    return round(max(age, 0.0), 1)


def build_measurement_frame(
    now: datetime,
    *,
    temperature_state: Any,
    humidity_state: Any,
    reference_temperature_state: Any,
    reference_humidity_state: Any,
) -> dict[str, Any]:
    """Describe temporal coherence of one complete room measurement frame.

    Quality thresholds intentionally err on the conservative side:
      * excellent: room/reference-pair skew <= 30 s with fresh-enough inputs
      * acceptable: pair skew <= 90 s
      * uncertain: pair skew <= 180 s
      * held: low-cadence battery pair, adaptive learning only
      * stale: excessive age/skew or a missing timestamp

    Absolute-age limits are deliberately wider than the skew thresholds: many
    battery climate sensors report only on change, while temporal mismatch
    between temperature and humidity is the main source of AH pairing error.

    Excellent/acceptable frames may influence adaptive learning and objective
    validation. A held frame may influence adaptive room learning conservatively,
    but is deliberately excluded from objective forecast validation.
    Uncertain/stale frames remain display/forecast-only.
    """
    states = {
        "temperature": temperature_state,
        "humidity": humidity_state,
        "reference_temperature": reference_temperature_state,
        "reference_humidity": reference_humidity_state,
    }
    stamps = {name: state_reported_at(state) for name, state in states.items()}
    ages = {name: _age_seconds(now, state) for name, state in states.items()}
    future_offsets = {
        name: (max((stamp - now).total_seconds(), 0.0) if stamp is not None else None)
        for name, stamp in stamps.items()
    }
    max_future_offset_s = max(
        (value for value in future_offsets.values() if value is not None),
        default=0.0,
    )

    available_stamps = [stamp for stamp in stamps.values() if stamp is not None]
    complete = len(available_stamps) == len(states)
    full_skew_s = None
    if complete:
        newest = max(available_stamps)
        oldest = min(available_stamps)
        full_skew_s = round(max((newest - oldest).total_seconds(), 0.0), 1)

    room_stamps = [stamps["temperature"], stamps["humidity"]]
    reference_stamps = [stamps["reference_temperature"], stamps["reference_humidity"]]
    room_skew_s = None if any(stamp is None for stamp in room_stamps) else round(abs((room_stamps[0] - room_stamps[1]).total_seconds()), 1)
    reference_skew_s = None if any(stamp is None for stamp in reference_stamps) else round(abs((reference_stamps[0] - reference_stamps[1]).total_seconds()), 1)

    room_ages = [ages["temperature"], ages["humidity"]]
    reference_ages = [ages["reference_temperature"], ages["reference_humidity"]]
    room_max_age_s = None if any(age is None for age in room_ages) else round(max(room_ages), 1)
    reference_max_age_s = None if any(age is None for age in reference_ages) else round(max(reference_ages), 1)
    max_age_s = None if room_max_age_s is None or reference_max_age_s is None else round(max(room_max_age_s, reference_max_age_s), 1)

    # The decisive skew is the room T/RH pair. The reference-air pair is also
    # checked, but its absolute age receives a wider allowance because weather
    # integrations often report at a slower cadence by design. Full cross-source
    # skew is retained for diagnostics instead of silently discarded.
    if not complete or room_skew_s is None or reference_skew_s is None or room_max_age_s is None or reference_max_age_s is None:
        quality = "stale"
        reason = "Mindestens ein Sensordatum besitzt keinen belastbaren Zeitstempel."
    elif max_future_offset_s > MAX_FUTURE_TIMESTAMP_S:
        quality = "stale"
        reason = "Mindestens ein Sensorzeitstempel liegt unplausibel in der Zukunft und wird nicht zum Lernen verwendet."
    elif (
        room_skew_s <= FRAME_EXCELLENT_SKEW_S
        and room_max_age_s <= ROOM_EXCELLENT_MAX_AGE_S
        and reference_skew_s <= FRAME_EXCELLENT_SKEW_S
        and reference_max_age_s <= REFERENCE_EXCELLENT_MAX_AGE_S
    ):
        quality = "excellent"
        reason = "Temperatur, Feuchte und Referenzluft sind zeitlich sehr gut synchronisiert."
    elif (
        room_skew_s <= FRAME_ACCEPTABLE_SKEW_S
        and room_max_age_s <= ROOM_ACCEPTABLE_MAX_AGE_S
        and reference_skew_s <= FRAME_ACCEPTABLE_SKEW_S
        and reference_max_age_s <= REFERENCE_ACCEPTABLE_MAX_AGE_S
    ):
        quality = "acceptable"
        reason = "Messwerte sind zeitlich ausreichend synchronisiert."
    elif (
        room_skew_s <= FRAME_UNCERTAIN_SKEW_S
        and room_max_age_s <= ROOM_USABLE_MAX_AGE_S
        and reference_skew_s <= FRAME_UNCERTAIN_SKEW_S
        and reference_max_age_s <= REFERENCE_USABLE_MAX_AGE_S
    ):
        quality = "uncertain"
        reason = "Raummesswerte liegen zeitlich zu weit auseinander und werden nicht zum Lernen verwendet."
    elif (
        room_skew_s <= FRAME_HELD_SKEW_S
        and room_max_age_s <= ROOM_HELD_MAX_AGE_S
        and reference_skew_s <= REFERENCE_HELD_SKEW_S
        and reference_max_age_s <= REFERENCE_HELD_MAX_AGE_S
    ):
        quality = "held"
        reason = "Langsam meldende Batterie-Sensoren: Das zeitlich gehaltene Messpaar darf vorsichtig ins Raumlernen einfließen, aber nicht in die objektive Prognosevalidierung."
    else:
        quality = "stale"
        reason = "Messwerte sind zu alt oder zeitlich zu stark versetzt und werden nicht zum Lernen verwendet."

    learning_eligible = quality in {"excellent", "acceptable", "held"}
    validation_eligible = quality in {"excellent", "acceptable"}
    # Keep measurement freshness, temporal alignment and learning influence
    # separate. A frame may be useful for a cautious adaptive update without
    # being precise enough for objective forecast scoring.
    grade = {"excellent": "A", "acceptable": "B", "held": "C", "uncertain": "C", "stale": "D"}.get(quality, "D")
    learning_weight = {"excellent": 1.0, "acceptable": 0.75, "held": 0.35}.get(quality, 0.0)
    return {
        "quality": quality,
        "learning_eligible": learning_eligible,
        "validation_eligible": validation_eligible,
        "grade": grade,
        "learning_weight": learning_weight,
        "skew_s": room_skew_s,
        "full_skew_s": full_skew_s,
        "reference_skew_s": reference_skew_s,
        "max_age_s": max_age_s,
        "room_max_age_s": room_max_age_s,
        "reference_max_age_s": reference_max_age_s,
        "age_temperature_s": ages["temperature"],
        "age_humidity_s": ages["humidity"],
        "age_reference_temperature_s": ages["reference_temperature"],
        "age_reference_humidity_s": ages["reference_humidity"],
        "max_future_offset_s": round(max_future_offset_s, 1),
        "temperature_reported_at": stamps["temperature"].isoformat() if stamps["temperature"] else None,
        "humidity_reported_at": stamps["humidity"].isoformat() if stamps["humidity"] else None,
        "reference_temperature_reported_at": stamps["reference_temperature"].isoformat() if stamps["reference_temperature"] else None,
        "reference_humidity_reported_at": stamps["reference_humidity"].isoformat() if stamps["reference_humidity"] else None,
        "reason": reason,
    }
