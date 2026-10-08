"""FreshAirIQ Language Confidence Layer.

Adapts only the wording of an already-final recommendation to the evidence
maturity and confidence of the current situation.  It must never change the
physical action, rooms, duration, forecast values or safety thresholds.
"""
from __future__ import annotations

from typing import Any
from math import isfinite


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _band(maturity: float) -> tuple[str, str]:
    if maturity < 12:
        return "grundmodell", "Grundmodell"
    if maturity < 28:
        return "beobachtet", "Beobachtet"
    if maturity < 45:
        return "muster_erkannt", "Muster erkannt"
    if maturity < 62:
        return "bestaetigt", "Bestätigt"
    if maturity < 78:
        return "eingelernt", "Eingelernt"
    if maturity < 92:
        return "sehr_gut_eingelernt", "Sehr gut eingelernt"
    return "auf_beduerfnisse_optimiert", "Auf deine Bedürfnisse optimiert"


def _relevant_maturity(kind: str, selected: list[dict[str, Any]]) -> tuple[float, int]:
    """Evidence maturity for the models that actually support this wording."""
    if not selected:
        return 0.0, 0
    scores: list[float] = []
    samples = 0
    for room in selected:
        physics_n = int(_f(room.get("learning_samples")))
        live_n = int(_f(room.get("forecast_observation_samples")))
        feedback_n = int(_f(room.get("outcome_feedback_samples")))
        strategy_n = int(_f(room.get("strategy_samples")))
        behaviour_n = int(_f(room.get("behaviour_recommendation_opportunities"))) + int(_f(room.get("behaviour_duration_samples")))
        if kind in {"continue", "close"}:
            score = 100.0 * _avg([min(physics_n / 80.0, 1.0), min(live_n / 60.0, 1.0), min(feedback_n / 80.0, 1.0)])
            samples += physics_n + live_n + feedback_n
        elif kind == "ventilate":
            score = 100.0 * _avg([min(physics_n / 80.0, 1.0), min(feedback_n / 80.0, 1.0), min(strategy_n / 100.0, 1.0), min(behaviour_n / 100.0, 1.0)])
            samples += physics_n + feedback_n + strategy_n + behaviour_n
        else:
            score = 100.0 * _avg([min(physics_n / 80.0, 1.0), min(feedback_n / 80.0, 1.0)])
            samples += physics_n + feedback_n
        scores.append(score)
    return _clamp(_avg(scores)), samples


def _situation_confidence(recommendation: dict[str, Any], selected: list[dict[str, Any]]) -> float:
    brain = recommendation.get("decision_brain") if isinstance(recommendation.get("decision_brain"), dict) else {}
    impact = brain.get("impact") if isinstance(brain.get("impact"), dict) else {}
    base = _f(impact.get("confidence"), _f(recommendation.get("confidence"), 50.0))
    room_conf = [_f(r.get("forecast_confidence")) for r in selected if r.get("forecast_confidence") is not None]
    if room_conf:
        base = 0.6 * base + 0.4 * _avg(room_conf)
    # Measurement coherence is a real-time property and therefore belongs to
    # situation confidence, not model maturity.
    quality_factor = {"excellent": 1.0, "acceptable": 0.92, "held": 0.60, "uncertain": 0.72, "stale": 0.45, "invalid": 0.35}
    factors = []
    for room in selected:
        q = str(room.get("measurement_frame_quality") or "").lower()
        if q:
            factors.append(quality_factor.get(q, 0.85))
    if factors:
        base *= _avg(factors)
    return _clamp(base)


def _variant_index(store: dict[str, Any], key: str, signature: str, count: int) -> int:
    """Keep wording stable while a decision is unchanged and rotate on a later episode.

    This is presentation state only. It never feeds the decision engine.
    """
    if count <= 1:
        return 0
    state = store.setdefault("narrative_variants", {})
    if not isinstance(state, dict):
        state = {}
        store["narrative_variants"] = state
    channel = "decision" if key.startswith(("lead:", "headline:")) else key
    active_key = f"_active_signature:{channel}"
    episode_key = f"_episode:{channel}"
    active_signature = str(state.get(active_key) or "")
    if active_signature != signature:
        state[active_key] = signature
        state[episode_key] = int(_f(state.get(episode_key))) + 1
    episode = int(_f(state.get(episode_key)))
    current = state.get(key) if isinstance(state.get(key), dict) else {}
    if current.get("signature") == signature and int(_f(current.get("episode"))) == episode:
        return int(_f(current.get("index"))) % count
    previous = int(_f(current.get("index"), -1))
    index = (previous + 1) % count
    state[key] = {"signature": signature, "episode": episode, "index": index}
    # Bounded persistent presentation metadata.
    if len(state) > 40:
        for old_key in list(state)[:-40]:
            state.pop(old_key, None)
    return index


def _choose(store: dict[str, Any], key: str, signature: str, variants: list[str]) -> str:
    clean = [str(v).strip() for v in variants if str(v).strip()]
    return clean[_variant_index(store, key, signature, len(clean))] if clean else ""


def _headline_variants(kind: str, band: str, fallback: str) -> list[str]:
    cautious = band in {"grundmodell", "beobachtet"}
    mapping = {
        "ventilate": [
            "Jetzt ist ein guter Zeitpunkt zum Lüften",
            "Die aktuellen Bedingungen sprechen fürs Lüften" if cautious else "Das Lüftungsfenster passt jetzt gut",
            "Jetzt lohnt sich der Luftaustausch",
            "FreshAirIQ sieht jetzt einen sinnvollen Lüftungsmoment",
        ],
        "wait": [
            "Noch etwas warten",
            "Im Moment lohnt sich Lüften noch nicht",
            "Ein günstigerer Zeitpunkt ist noch nicht erreicht",
            "FreshAirIQ beobachtet die Bedingungen noch",
        ],
        "continue": [
            "Die Lüftung wirkt – noch weiterlüften",
            "Der Luftaustausch bringt noch Nutzen",
            "Noch nicht schließen",
            "FreshAirIQ verfolgt die laufende Lüftung",
        ],
        "close": [
            "Jetzt ist ein guter Zeitpunkt zum Schließen",
            "Der zusätzliche Lüftungsnutzen ist erreicht",
            "Die Lüftung kann jetzt beendet werden",
            "Jetzt schließen – der Zusatznutzen wird klein",
        ],
        "okay": [
            "Aktuell ist keine Lüftungsaktion nötig",
            "Das Raumklima braucht im Moment keinen Eingriff",
            "FreshAirIQ sieht derzeit keinen Lüftungsbedarf",
            "Im Moment reicht Beobachten aus",
        ],
        "prepare": ["Jetzt Feuchtepuffer schaffen", "Kurzes Vorlüften passt jetzt gut", "Jetzt für den erwarteten Feuchteanstieg vorlüften"],
        "pollen_wait": ["Lüften wäre sinnvoll – Pollen sprechen dagegen", "Der Lüftungsnutzen ist da, die Pollenlage bremst", "Heute besser auf ein pollenärmeres Fenster warten"],
        "sensor": ["FreshAirIQ kann aktuell nicht zuverlässig entscheiden", "Für eine sichere Empfehlung fehlen verlässliche Messwerte", "Messdaten zuerst prüfen"],
    }
    return mapping.get(kind, [fallback])


def _lead_variants(band: str) -> list[str]:
    return {
        "grundmodell": [
            "FreshAirIQ arbeitet hier noch überwiegend mit Gebäudephysik und aktuellen Messdaten.",
            "Für diesen Bereich lernt FreshAirIQ noch; die Einschätzung basiert deshalb vor allem auf den aktuellen Messwerten.",
            "Das persönliche Modell ist hier noch jung, deshalb bleibt die Bewertung bewusst nah an den Messdaten.",
        ],
        "beobachtet": [
            "FreshAirIQ sammelt erste Erfahrungen und bleibt mit persönlichen Aussagen noch vorsichtig.",
            "Erste Muster sind sichtbar, für belastbare persönliche Aussagen sammelt FreshAirIQ aber noch Daten.",
            "Das Modell kennt bereits erste Verläufe, gewichtet die aktuelle Physik aber weiterhin stärker.",
        ],
        "muster_erkannt": [
            "FreshAirIQ erkennt wiederkehrende Muster und prüft sie noch gegen weitere Lüftungen.",
            "Das persönliche Raumverhalten zeichnet sich ab, wird aber noch weiter bestätigt.",
            "Mehrere Verläufe ähneln sich bereits; FreshAirIQ bleibt bis zu weiteren Bestätigungen etwas vorsichtig.",
        ],
        "bestaetigt": [
            "Mehrere unabhängige Beobachtungen bestätigen das erkannte Lüftungsverhalten dieser Räume.",
            "Das bisher erkannte Raumverhalten hat sich mehrfach bestätigt und fließt jetzt stärker in die Formulierung ein.",
            "FreshAirIQ kann sich hier bereits auf mehrfach bestätigte Erfahrungen stützen.",
        ],
        "eingelernt": [
            "FreshAirIQ hat für diese Räume eine belastbare eigene Datenbasis und personalisiert die Einschätzung vorsichtig.",
            "Das Raumverhalten ist inzwischen gut eingelernt; die Empfehlung berücksichtigt die bestätigten Erfahrungen.",
            "Für diese Räume liegen genug eigene Erfahrungen vor, um die aktuelle Situation persönlicher einzuordnen.",
        ],
        "sehr_gut_eingelernt": [
            "FreshAirIQ kennt das Lüftungsverhalten dieser Räume inzwischen sehr gut und prüft seine Anpassungen fortlaufend.",
            "Die Reaktion dieser Räume ist sehr gut eingelernt; aktuelle Abweichungen werden gezielt gegen das bekannte Muster geprüft.",
            "Hier kann FreshAirIQ auf eine sehr stabile persönliche Datenbasis zurückgreifen.",
        ],
        "auf_beduerfnisse_optimiert": [
            "FreshAirIQ kennt Raumverhalten sowie bestätigte Nutzungs- und Komfortmuster sehr gut.",
            "Die Empfehlung kann hier auf ein ausgereiftes persönliches Modell aus Raum-, Nutzungs- und Komfortdaten zurückgreifen.",
            "Das Modell ist hier weit ausgereift und kann die Situation anhand deiner bestätigten Muster einordnen.",
        ],
    }.get(band, ["FreshAirIQ bewertet die aktuelle Situation anhand der verfügbaren Messwerte."])


def room_notification_message(event: str, room: dict[str, Any], store_data: dict[str, Any] | None = None) -> str:
    """Presentation-only varied copy for room-scoped notifications."""
    store = store_data if isinstance(store_data, dict) else {}
    name = str(room.get("name") or room.get("key") or "Raum")
    samples = int(_f(room.get("learning_samples")))
    band, _ = _band(min(samples / 80.0, 1.0) * 100.0)
    signature = f"room-notify|{event}|{room.get('key') or name}|{band}"
    variants = {
        "ventilate": [
            "Jetzt lüften.",
            "Jetzt passt der Zeitpunkt zum Lüften.",
            "Für diesen Raum lohnt sich der Luftaustausch jetzt.",
        ],
        "cool": [
            "Sommerkühlung sinnvoll.",
            "Jetzt lässt sich der Raum sinnvoll abkühlen.",
            "Die Außenbedingungen passen jetzt zur Sommerkühlung.",
        ],
        "close": [
            "Optimales Lüftungsziel erreicht. Empfehlung: jetzt schließen.",
            "Die zusätzliche Lüftungswirkung wird klein. Jetzt schließen.",
            "Für diesen Raum ist der passende Schließzeitpunkt erreicht.",
        ],
        "sensor": [
            "Messwerte fehlen oder sind unplausibel. Sensoren prüfen.",
            "Für eine verlässliche Empfehlung fehlen gültige Messwerte. Sensoren prüfen.",
        ],
    }.get(event, [""])
    return _choose(store, f"room_notification:{event}:{room.get('key') or name}", signature, variants)


def adapt_language_confidence(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    store_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a presentation-only copy whose wording reflects evidence depth."""
    out = dict(recommendation or {})
    brain = dict(out.get("decision_brain") or {})
    kind = str(out.get("kind") or "okay")
    room_keys = [str(k) for k in (out.get("room_keys") or [])]
    selected = [rooms[k] for k in room_keys if k in rooms]
    # House presentation may intentionally have no room chips. In that case the
    # canonical recommendation still carries room_keys; if not, use active rooms.
    if not selected and str(out.get("presentation_scope")) == "house":
        selected = [r for r in rooms.values() if isinstance(r, dict) and r.get("active")]

    maturity, evidence_samples = _relevant_maturity(kind, selected)
    store = store_data if isinstance(store_data, dict) else {}
    # If the final recommendation is explicitly driven by a night or house
    # strategy, include that model's own evidence depth instead of pretending
    # the room model alone supports the wording.
    ns = brain.get("night_strategy") if isinstance(brain.get("night_strategy"), dict) else {}
    if brain.get("night_strategy_primary") or (ns.get("active") and kind in {"okay", "wait"}):
        night_n = int(_f(store.get("night_model_samples")))
        maturity = _avg([maturity, min(night_n / 120.0, 1.0) * 100.0]) if selected else min(night_n / 120.0, 1.0) * 100.0
        evidence_samples += night_n
    if str(out.get("presentation_scope")) == "house":
        house_n = int(_f(store.get("house_strategy_samples")))
        maturity = _avg([maturity, min(house_n / 150.0, 1.0) * 100.0])
        evidence_samples += house_n
    situation = _situation_confidence(out, selected)
    band_key, band_label = _band(maturity)
    original_summary = str(brain.get("summary") or out.get("summary") or "").strip()

    # Evidence-calibrated voice with stable, non-random variation. A wording
    # remains stable for the same decision episode and rotates only after the
    # canonical situation changes and later returns.
    signature = "|".join([kind, str(out.get("status") or ""), ",".join(room_keys), band_key, str(out.get("presentation_scope") or "rooms")])
    lead = _choose(store, f"lead:{kind}", signature, _lead_variants(band_key))
    current_headline = str(brain.get("headline") or out.get("title") or "").strip()
    # Preserve specialised primary stories (night strategy, passive-open monitor)
    # instead of flattening them into a generic action phrase.
    if not brain.get("night_strategy_primary") and str(out.get("status") or "") != "passive_open_monitor":
        headline = _choose(store, f"headline:{kind}", signature, _headline_variants(kind, band_key, current_headline))
        if headline:
            brain["headline"] = headline
            out["title"] = headline
    if situation < 45:
        qualifier = " Die aktuelle Situation ist jedoch ungewöhnlich oder messtechnisch unsicher, deshalb bleibt die Einschätzung bewusst vorsichtig."
    elif situation < 65:
        qualifier = " Für die aktuelle Situation ist die Sicherheit noch begrenzt, deshalb ist die Formulierung bewusst zurückhaltend."
    elif situation >= 85 and maturity >= 60:
        qualifier = " Auch die aktuelle Situation lässt sich mit hoher Sicherheit bewerten."
    else:
        qualifier = ""

    # Do not drown out urgent live/close instructions. Put learning context after
    # the action summary there; for idle/start recommendations it can lead.
    confidence_text = (lead + qualifier).strip()
    if kind in {"continue", "close"}:
        summary = (original_summary + " " + confidence_text).strip()
    else:
        summary = (confidence_text + " " + original_summary).strip()

    reasons = list(brain.get("why") or out.get("reasons") or [])
    # Surface the strongest already-learned personal signal. This changes only
    # wording/reason priority, never the selected action or physical thresholds.
    personal_traces: list[tuple[float, str]] = []
    for room in selected:
        name = str(room.get("name") or "Dieser Raum")
        routine_maturity = _f(room.get("routine_maturity"))
        routine_samples = int(_f(room.get("routine_source_samples")))
        routine_rate = room.get("routine_expected_source_ml_min")
        if routine_samples >= 8 and routine_maturity >= 25 and routine_rate is not None:
            hourly = _f(routine_rate) * 60.0
            if abs(hourly) >= 10:
                direction = "Feuchtezunahme" if hourly > 0 else "Feuchteabnahme"
                personal_traces.append((routine_maturity, f"Persönliches Muster: {name} zeigt um diese Zeit häufig eine {direction} von etwa {abs(hourly):.0f} ml/h"))
        strategy_samples = int(_f(room.get("strategy_samples")))
        success = _f(room.get("outcome_success_rate"))
        feedback = int(_f(room.get("outcome_feedback_samples")))
        if strategy_samples >= 10 and feedback >= 5 and success > 0:
            personal_traces.append((min(100.0, strategy_samples / 2.0), f"Gelernte Erfahrung: {name} · {feedback} überprüfte Ergebnisse · Prognosetreffer {success:.0f} %"))
    if personal_traces:
        personal_traces.sort(key=lambda item: item[0], reverse=True)
        trace_text = personal_traces[0][1]
        if trace_text not in reasons:
            reasons.insert(0, trace_text)
    # One compact, factual trace makes the change visible without turning the
    # recommendation into a diagnostics panel.
    trace = f"Lernstand: {band_label} ({maturity:.0f} %) · Situationssicherheit {situation:.0f} %"
    if trace not in reasons:
        reasons.append(trace)
    reasons = reasons[:7]

    brain["summary"] = summary
    brain["why"] = reasons
    brain["language_confidence"] = {
        "version": "v1",
        "maturity_percent": round(maturity, 1),
        "maturity_band": band_key,
        "maturity_label": band_label,
        "evidence_samples": evidence_samples,
        "situation_confidence_percent": round(situation, 1),
        "calibrated_wording": True,
        "narrative_variation": True,
        "narrative_signature": signature,
    }
    out["summary"] = summary
    out["reasons"] = reasons
    out["decision_brain"] = brain
    out["language_confidence"] = dict(brain["language_confidence"])
    return out
