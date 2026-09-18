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
)
from .energy import exchanged_air_fraction

_LABELS = {
    MOISTURE_SOURCE_SHOWER: "Dusche",
    MOISTURE_SOURCE_BATH: "Bad",
    MOISTURE_SOURCE_SAUNA: "Sauna",
    MOISTURE_SOURCE_COOKING: "Kochen",
}


def source_label(configured: list[str] | tuple[str, ...] | None) -> str:
    """Return a truthful label. Multiple configured sources are not asserted as one source."""
    values = [x for x in (configured or []) if x in _LABELS]
    if len(values) == 1:
        return _LABELS[values[0]]
    return "Feuchtequelle"


def _identify_source(configured: set[str], *, temp_rise: float, source_rate: float, generated_ml: float) -> tuple[str, str | None, str]:
    """Return label, source key and user-facing text without overclaiming causality."""
    if not configured:
        return "Feuchtequelle", None, "Zusätzliche Feuchtigkeit erkannt. FreshAirIQ berücksichtigt den Anstieg bei der Lüftungsstrategie."
    if len(configured) == 1:
        key = next(iter(configured)); label = _LABELS[key]
    elif MOISTURE_SOURCE_SAUNA in configured and temp_rise >= 0.8 and source_rate >= 2.2:
        key, label = MOISTURE_SOURCE_SAUNA, _LABELS[MOISTURE_SOURCE_SAUNA]
    elif MOISTURE_SOURCE_COOKING in configured and temp_rise >= 0.35 and source_rate >= 3.0 and generated_ml >= 18.0:
        key, label = MOISTURE_SOURCE_COOKING, _LABELS[MOISTURE_SOURCE_COOKING]
    else:
        return "Feuchtequelle", None, "Zusätzliche Feuchtigkeit erkannt. Die genaue Quelle ist nicht eindeutig; FreshAirIQ berücksichtigt den Anstieg bei der Lüftungsstrategie."
    text = {
        MOISTURE_SOURCE_COOKING: "Kochen erkannt. FreshAirIQ berücksichtigt zusätzliche Wärme und Feuchte. Guten Appetit! 🍽️",
        MOISTURE_SOURCE_SHOWER: "Dusche erkannt. Genieß die warme Dusche – um die frische Luft kümmert sich FreshAirIQ danach. 🚿",
        MOISTURE_SOURCE_BATH: "Bad erkannt. Zeit zum Entspannen – FreshAirIQ behält die Feuchteentwicklung im Blick. 🛁",
        MOISTURE_SOURCE_SAUNA: "Sauna erkannt. FreshAirIQ berücksichtigt Wärme und Feuchte und plant die passende Nachlüftung.",
    }.get(key, "Zusätzliche Feuchtigkeit erkannt.")
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
        wet_source_configured = bool(configured)
        # Room context lowers the threshold, but never replaces physical evidence.
        min_rate = 3.2 if wet_source_configured else 5.0
        min_generated = 18.0 if wet_source_configured else 30.0
        min_ah_rise = 0.20 if wet_source_configured else 0.32

        # Sauna use can include a moderate moisture rise plus a simultaneous
        # temperature rise (e.g. humid sauna / infusion). Dry heat alone is not
        # called a moisture source because it adds no water to the air.
        sauna_signature = (
            MOISTURE_SOURCE_SAUNA in configured
            and temp_rise >= 0.8
            and source_rate >= 2.2
            and generated_ml >= 12.0
            and ah_rise >= 0.10
        )
        cooking_signature = (
            MOISTURE_SOURCE_COOKING in configured
            and temp_rise >= 0.25
            and source_rate >= 3.0
            and generated_ml >= 18.0
            and ah_rise >= 0.16
        )
        wet_signature = source_rate >= min_rate and generated_ml >= min_generated and ah_rise >= min_ah_rise
        detected = wet_signature or sauna_signature or cooking_signature

        if detected:
            label, identified_source, source_message = _identify_source(
                configured, temp_rise=temp_rise, source_rate=source_rate, generated_ml=generated_ml
            )
            reference_change = abs(float(reference_ah_g_m3) - old_ref)
            confidence = 48
            confidence += min(int(max(source_rate - min_rate, 0.0) * 3.0), 22)
            confidence += min(int(max(ah_rise - min_ah_rise, 0.0) * 18.0), 15)
            confidence += 8 if wet_source_configured else 0
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
