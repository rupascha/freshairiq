"""Adaptive internal moisture-source detection for FreshAirIQ.

The detector separates measured room-water change from the moisture change that
ventilation alone should have caused.  This prevents showers, baths and sauna
use from being misread as failed ventilation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .const import (
    MOISTURE_SOURCE_BATH,
    MOISTURE_SOURCE_SAUNA,
    MOISTURE_SOURCE_SHOWER,
    MOISTURE_SOURCE_COOKING,
    MOISTURE_SOURCE_WASHING_MACHINE,
    MOISTURE_SOURCE_DRYER,
    MOISTURE_SOURCE_IRONING_STATION,
    MOISTURE_SOURCE_LAUNDRY_DRYING,
)
from .energy import exchanged_air_fraction

_LABELS = {
    MOISTURE_SOURCE_SHOWER: "Dusche",
    MOISTURE_SOURCE_BATH: "Bad",
    MOISTURE_SOURCE_SAUNA: "Sauna",
    MOISTURE_SOURCE_COOKING: "Kochen",
    MOISTURE_SOURCE_WASHING_MACHINE: "Waschmaschine",
    MOISTURE_SOURCE_DRYER: "Trockner",
    MOISTURE_SOURCE_IRONING_STATION: "Bügelstation",
    MOISTURE_SOURCE_LAUNDRY_DRYING: "Wäsche trocknen",
}


def source_label(configured: list[str] | tuple[str, ...] | None) -> str:
    """Return a truthful label. Multiple configured sources are not asserted as one source."""
    values = [x for x in (configured or []) if x in _LABELS]
    if len(values) == 1:
        return _LABELS[values[0]]
    return "Feuchtequelle"


def _pattern_features(points: list[dict[str, Any]], *, now: datetime) -> dict[str, float]:
    """Summarise the recent shape without pretending one sample identifies an activity."""
    rows: list[tuple[datetime, float, float]] = []
    for point in points:
        at = _dt(point.get("at"))
        if at is None or not 0 <= (now - at).total_seconds() <= 12 * 60:
            continue
        try:
            rows.append((at, float(point.get("ah")), float(point.get("temp"))))
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda row: row[0])
    if len(rows) < 2:
        return {"samples": float(len(rows)), "ah_monotonic": 0.0, "temp_monotonic": 0.0, "peak_ah_rate": 0.0}
    ah_positive = temp_positive = intervals = 0
    peak_ah_rate = 0.0
    for left, right in zip(rows, rows[1:]):
        dt_min = max((right[0] - left[0]).total_seconds() / 60.0, 1 / 60)
        ah_delta = right[1] - left[1]
        temp_delta = right[2] - left[2]
        intervals += 1
        ah_positive += ah_delta >= -0.015
        temp_positive += temp_delta >= -0.08
        peak_ah_rate = max(peak_ah_rate, ah_delta / dt_min)
    return {
        "samples": float(len(rows)),
        "ah_monotonic": ah_positive / max(intervals, 1),
        "temp_monotonic": temp_positive / max(intervals, 1),
        "peak_ah_rate": peak_ah_rate,
    }


def _source_signatures(
    configured: set[str], *, ah_rise: float, temp_rise: float, source_rate: float,
    generated_ml: float, pattern: dict[str, float],
) -> list[str]:
    """Return only source types whose physical/time signature is sufficiently specific.

    Configuration is context, never proof. Thresholds are deliberately conservative:
    ordinary occupancy can raise indoor humidity and must not be labelled as cooking,
    showering or sauna use merely because that is the only configured source.
    """
    samples = int(pattern.get("samples", 0))
    monotonic = pattern.get("ah_monotonic", 0.0) >= 0.66 if samples >= 3 else True
    strong_monotonic = pattern.get("ah_monotonic", 0.0) >= 0.80 if samples >= 3 else True
    matches: list[str] = []
    if MOISTURE_SOURCE_SHOWER in configured and monotonic and ah_rise >= 0.45 and source_rate >= 6.0 and generated_ml >= 30.0:
        matches.append(MOISTURE_SOURCE_SHOWER)
    if MOISTURE_SOURCE_BATH in configured and monotonic and ah_rise >= 0.32 and source_rate >= 4.5 and generated_ml >= 25.0 and temp_rise >= -0.15:
        matches.append(MOISTURE_SOURCE_BATH)
    if MOISTURE_SOURCE_SAUNA in configured and monotonic and temp_rise >= 0.80 and ah_rise >= 0.10 and source_rate >= 2.2 and generated_ml >= 12.0:
        matches.append(MOISTURE_SOURCE_SAUNA)
    if MOISTURE_SOURCE_COOKING in configured and strong_monotonic and temp_rise >= 0.40 and ah_rise >= 0.22 and source_rate >= 4.5 and generated_ml >= 24.0:
        matches.append(MOISTURE_SOURCE_COOKING)
    # A dryer has a useful combined heat+moisture signature. A washing machine
    # alone is intentionally not named from room climate: that is not reliably
    # distinguishable from people or another weak source without appliance data.
    if MOISTURE_SOURCE_DRYER in configured and monotonic and temp_rise >= 0.50 and ah_rise >= 0.12 and source_rate >= 2.8 and generated_ml >= 16.0:
        matches.append(MOISTURE_SOURCE_DRYER)
    # Washing machines usually produce a weaker, pulsed room-climate signature than
    # dryers. Only classify it when the rise is sustained but clearly below the
    # strong heat signatures of cooking/dryer/sauna.
    if MOISTURE_SOURCE_WASHING_MACHINE in configured and samples >= 3 and monotonic and 0.08 <= temp_rise < 0.50 and 0.12 <= ah_rise < 0.45 and 1.8 <= source_rate < 4.5 and generated_ml >= 14.0:
        matches.append(MOISTURE_SOURCE_WASHING_MACHINE)
    # Hung laundry is deliberately recognised only as a slow, sustained humidity
    # source without a meaningful heat rise; this prevents showers/cooking from
    # being mislabeled as drying laundry.
    if MOISTURE_SOURCE_LAUNDRY_DRYING in configured and samples >= 4 and strong_monotonic and -0.20 <= temp_rise <= 0.25 and 0.18 <= ah_rise < 0.55 and 1.2 <= source_rate <= 4.0 and generated_ml >= 18.0:
        matches.append(MOISTURE_SOURCE_LAUNDRY_DRYING)
    if MOISTURE_SOURCE_IRONING_STATION in configured and monotonic and temp_rise >= 0.15 and ah_rise >= 0.30 and source_rate >= 4.0 and generated_ml >= 22.0:
        matches.append(MOISTURE_SOURCE_IRONING_STATION)
    return matches


def _identify_source(matches: list[str]) -> tuple[str, str | None, str]:
    """Name an activity only when exactly one source-specific signature matches."""
    if len(matches) != 1:
        return "Feuchtequelle", None, "Zusätzliche interne Feuchtigkeit erkannt. Die genaue Quelle ist nicht eindeutig; FreshAirIQ berücksichtigt nur die gemessene Feuchtelast."
    key = matches[0]
    label = _LABELS[key]
    text = {
        MOISTURE_SOURCE_COOKING: "Kochen erkannt. Das Wärme- und Feuchtemuster passt zur konfigurierten Quelle; FreshAirIQ berücksichtigt die zusätzliche Feuchtelast.",
        MOISTURE_SOURCE_SHOWER: "Dusche erkannt. Der schnelle Feuchteanstieg passt zur konfigurierten Quelle; FreshAirIQ plant die Nachlüftung entsprechend.",
        MOISTURE_SOURCE_BATH: "Bad erkannt. Das Feuchtemuster passt zur konfigurierten Quelle; FreshAirIQ berücksichtigt die zusätzliche Feuchtelast.",
        MOISTURE_SOURCE_SAUNA: "Sauna erkannt. Der kombinierte Wärme- und Feuchteanstieg passt zur konfigurierten Quelle.",
        MOISTURE_SOURCE_DRYER: "Trockner erkannt. Der kombinierte Wärme- und Feuchteanstieg passt zur konfigurierten Quelle.",
        MOISTURE_SOURCE_WASHING_MACHINE: "Waschmaschine erkannt. Das moderate, anhaltende Feuchte- und Wärmemuster passt zur konfigurierten Quelle.",
        MOISTURE_SOURCE_IRONING_STATION: "Bügelstation erkannt. Das Wärme- und Feuchtemuster passt zur konfigurierten Quelle.",
        MOISTURE_SOURCE_LAUNDRY_DRYING: "Wäsche aufhängen erkannt. Der langsame, anhaltende Feuchteanstieg ohne deutliche Wärmequelle passt zur konfigurierten Quelle.",
    }.get(key, "Zusätzliche interne Feuchtigkeit erkannt.")
    return label, key, text


def _dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _bounded(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def update_moisture_source(
    memory: dict[str, Any],
    *,
    now: datetime,
    absolute_humidity_g_m3: float,
    reference_ah_g_m3: float,
    temperature_c: float,
    volume_m3: float,
    window_open: bool,
    learning_rate_per_min: float,
    airflow_factor: float,
    cross_ventilation: bool,
    configured_sources: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    """Update and return moisture-source state for one room.

    Positive ``source_rate_ml_min`` means water is being generated inside the
    room after subtracting the modelled ventilation effect.  Detection uses a
    short rolling history plus hysteresis; one noisy humidity sample cannot
    switch the state on or off.
    """
    points = list(memory.get("moisture_source_points") or [])
    current = {
        "at": now.isoformat(),
        "ah": round(float(absolute_humidity_g_m3), 4),
        "ref_ah": round(float(reference_ah_g_m3), 4),
        "temp": round(float(temperature_c), 3),
        "open": bool(window_open),
    }

    # Do not fill persistent storage with coordinator refresh duplicates. A new
    # climate value or one minute of elapsed time is enough to add a point.
    add = True
    if points:
        last = points[-1]
        last_at = _dt(last.get("at"))
        age_s = (now - last_at).total_seconds() if last_at else 999.0
        add = (
            age_s >= 60.0
            or abs(float(last.get("ah", 0.0)) - current["ah"]) >= 0.015
            or abs(float(last.get("temp", 0.0)) - current["temp"]) >= 0.08
        )
    if add:
        points.append(current)

    cutoff = now - timedelta(minutes=20)
    points = [x for x in points if (_dt(x.get("at")) or now) >= cutoff][-36:]
    memory["moisture_source_points"] = points

    # Prefer a 3–8 minute baseline. This is fast enough for shower detection but
    # long enough to suppress normal sensor quantisation. If sensor reporting is
    # slower, accept any baseline between 1.5 and 12 minutes.
    candidates: list[tuple[float, dict[str, Any]]] = []
    for point in points[:-1]:
        at = _dt(point.get("at"))
        if at is None:
            continue
        age_min = (now - at).total_seconds() / 60.0
        if 1.5 <= age_min <= 12.0:
            candidates.append((age_min, point))
    preferred = [x for x in candidates if 3.0 <= x[0] <= 8.0]
    baseline_row = min(preferred or candidates, key=lambda x: abs(x[0] - 5.0)) if (preferred or candidates) else None

    active_before = bool(memory.get("moisture_source_active", False))
    previous_confidence = int(memory.get("moisture_source_confidence", 0) or 0)
    previous_rate = float(memory.get("moisture_source_rate_ml_min", 0.0) or 0.0)
    previous_generated = float(memory.get("moisture_source_generated_ml", 0.0) or 0.0)
    previous_label = str(memory.get("moisture_source_label", "Feuchtequelle"))
    previous_ended = memory.get("moisture_source_last_ended_at")
    label = source_label(configured_sources)
    identified_source = None
    source_message = ""
    detected = False
    confidence = previous_confidence
    source_rate = previous_rate
    generated_ml = previous_generated
    observed_change_ml = 0.0
    ventilation_change_ml = 0.0
    ah_rise = 0.0
    temp_rise = 0.0
    interval_min = 0.0

    if baseline_row is not None:
        interval_min, base = baseline_row
        old_ah = float(base.get("ah", absolute_humidity_g_m3))
        old_ref = float(base.get("ref_ah", reference_ah_g_m3))
        old_temp = float(base.get("temp", temperature_c))
        ah_rise = float(absolute_humidity_g_m3) - old_ah
        temp_rise = float(temperature_c) - old_temp
        observed_change_ml = ah_rise * max(float(volume_m3), 0.0)

        # Signed room-water change caused by ventilation alone. Negative means
        # ventilation removes moisture. Only model the interval as ventilated if
        # the opening was already open at the baseline and remains open now.
        if bool(base.get("open")) and window_open:
            avg_room_ah = (old_ah + float(absolute_humidity_g_m3)) / 2.0
            avg_ref_ah = (old_ref + float(reference_ah_g_m3)) / 2.0
            fraction = exchanged_air_fraction(
                max(float(learning_rate_per_min), 0.001),
                interval_min,
                (1.25 if cross_ventilation else 1.0) * _bounded(airflow_factor, 0.5, 1.5),
            )
            ventilation_change_ml = (avg_ref_ah - avg_room_ah) * max(float(volume_m3), 0.0) * fraction

        generated_ml = observed_change_ml - ventilation_change_ml
        source_rate = generated_ml / max(interval_min, 1.0)

        configured = {x for x in (configured_sources or []) if x in _LABELS}
        pattern = _pattern_features(points, now=now)
        matches = _source_signatures(
            configured,
            ah_rise=ah_rise,
            temp_rise=temp_rise,
            source_rate=source_rate,
            generated_ml=generated_ml,
            pattern=pattern,
        )

        # Strong unconfigured loads may still be recognised as an unspecified
        # internal moisture load. Configured activities, however, are activated
        # only by their own signature: configuration is never evidence by itself.
        generic_strong = (
            not configured
            and source_rate >= 7.0
            and generated_ml >= 40.0
            and ah_rise >= 0.45
            and (pattern.get("ah_monotonic", 0.0) >= 0.66 or pattern.get("samples", 0.0) < 3)
        )
        detected = bool(matches) or generic_strong

        if detected:
            label, identified_source, source_message = _identify_source(matches)
            reference_change = abs(float(reference_ah_g_m3) - old_ref)
            # Confidence describes evidence for an internal load. Naming an
            # activity additionally requires exactly one source signature above.
            min_rate = 4.0 if matches else 7.0
            min_ah_rise = 0.10 if matches == [MOISTURE_SOURCE_SAUNA] else (0.22 if matches else 0.45)
            confidence = 52
            confidence += min(int(max(source_rate - min_rate, 0.0) * 3.0), 20)
            confidence += min(int(max(ah_rise - min_ah_rise, 0.0) * 16.0), 14)
            confidence += 8 if len(matches) == 1 else 0
            confidence += 4 if pattern.get("ah_monotonic", 0.0) >= 0.66 else 0
            confidence += 5 if reference_change <= max(0.15, abs(ah_rise) * 0.35) else 0
            confidence = int(_bounded(confidence, 55, 98))
            memory["moisture_source_last_positive_at"] = now.isoformat()
            if not active_before:
                memory["moisture_source_started_at"] = now.isoformat()
            memory["moisture_source_active"] = True
            memory["moisture_source_last_ended_at"] = None
        elif active_before:
            last_positive = _dt(memory.get("moisture_source_last_positive_at"))
            # Six quiet minutes prevents a brief pause in a shower or sauna
            # infusion from constantly toggling the recommendation.
            quiet_min = (now - last_positive).total_seconds() / 60.0 if last_positive else 999.0
            if quiet_min >= 6.0 and source_rate < 1.5:
                memory["moisture_source_active"] = False
                memory["moisture_source_last_ended_at"] = now.isoformat()
            else:
                memory["moisture_source_active"] = True
                confidence = max(int(memory.get("moisture_source_confidence", 0) or 0) - 3, 55)

    active = bool(memory.get("moisture_source_active", False))
    if active and not identified_source:
        identified_source = memory.get("moisture_source_identified_source")
        source_message = str(memory.get("moisture_source_message") or source_message)
        label = str(memory.get("moisture_source_label") or label)
    memory["moisture_source_identified_source"] = identified_source
    memory["moisture_source_message"] = source_message
    memory["moisture_source_confidence"] = int(confidence if active else 0)
    memory["moisture_source_rate_ml_min"] = round(max(source_rate, 0.0), 2)
    memory["moisture_source_generated_ml"] = round(max(generated_ml, 0.0), 1)
    memory["moisture_source_label"] = label
    memory["moisture_source_last_evaluated_at"] = now.isoformat()

    ended_at = _dt(memory.get("moisture_source_last_ended_at"))
    recovery = bool(ended_at and 0 <= (now - ended_at).total_seconds() / 60.0 <= 15.0)
    return {
        "active": active,
        "recovery": recovery,
        "label": label,
        "identified_source": identified_source,
        "message": source_message,
        "ambiguous": bool(active and configured_sources and len([x for x in configured_sources if x in _LABELS]) > 1 and not identified_source),
        "configured_sources": list(configured_sources or []),
        "confidence": int(memory.get("moisture_source_confidence", 0) or 0),
        "source_rate_ml_min": round(max(source_rate, 0.0), 2),
        "generated_ml_window": round(max(generated_ml, 0.0), 1),
        "observed_change_ml_window": round(observed_change_ml, 1),
        "ventilation_change_ml_window": round(ventilation_change_ml, 1),
        "absolute_humidity_rise_g_m3": round(ah_rise, 3),
        "temperature_rise_c": round(temp_rise, 2),
        "window_min": round(interval_min, 1),
        "started_at": memory.get("moisture_source_started_at"),
        "last_ended_at": memory.get("moisture_source_last_ended_at"),
        "changed": bool(
            add
            or active_before != active
            or previous_confidence != int(memory.get("moisture_source_confidence", 0) or 0)
            or abs(previous_rate - float(memory.get("moisture_source_rate_ml_min", 0.0) or 0.0)) >= 0.25
            or abs(previous_generated - float(memory.get("moisture_source_generated_ml", 0.0) or 0.0)) >= 2.0
            or previous_label != str(memory.get("moisture_source_label", "Feuchtequelle"))
            or previous_ended != memory.get("moisture_source_last_ended_at")
        ),
    }
