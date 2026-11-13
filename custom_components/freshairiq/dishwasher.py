"""Dishwasher as a moisture source (0.26.7.0, GitHub #18). Pure logic: no Home Assistant imports.

A dishwasher releases most of its water vapour into the room in two moments: while it dries with the door opened a
gap (Siemens/Bosch "eco dry", Miele "AutoOpen") and when the door is opened after the end of the programme; then the
warm load keeps evaporating for a while (after-evaporation). While it washes and rinses with the door shut, little
escapes. A room may name an optional device signal – a binary sensor ("drying" or the door), or a programme/phase
sensor or select of the appliance integration. Its phase is read here; without a signal the room climate alone is
used (``moisture_source._source_signatures``).

0.26.7.0 (F10, release blocker): states are matched exactly after normalisation – no substring search. Earlier
"drying_complete" and "not_drying" were read as drying because they contain "dry". An unknown state says nothing.
"""
from __future__ import annotations

import re
from typing import Any

WASHING, DRYING, FINISHED, IDLE = "washing", "drying", "finished", "idle"
DOOR_OPEN, AFTER_EVAPORATION = "door_open", "after_evaporation"
PHASES = (WASHING, DRYING, DOOR_OPEN, FINISHED, AFTER_EVAPORATION, IDLE)
RELEASE_PHASES = frozenset({DRYING, DOOR_OPEN})            # vapour escapes now: a source at once (announced, not guessed)
ATTRIBUTION_PHASES = frozenset({FINISHED, AFTER_EVAPORATION})  # a measured humidity rise now is named "dishwasher"
AFTER_EVAPORATION_MIN = 20.0                               # warm load keeps evaporating after drying / the door opening

_EXACT: dict[str, str] = {}
for _phase, _words in (
    (DRYING, ("drying", "dry", "dries", "drying_phase", "drying_active", "drying_running", "eco_dry", "ecodry",
              "extra_dry", "extradry", "auto_open", "autoopen", "auto_open_drying", "autoopen_drying", "zeolith_drying",
              "zeolite_drying", "trocknen", "trocknung", "trocknet", "trockenphase", "trocknungsphase", "nachtrocknen")),
    (DOOR_OPEN, ("door_open", "door_opened", "door_ajar", "open", "opened", "offen", "geoeffnet", "geöffnet",
                 "tuer_offen", "tür_offen", "tuer_geoeffnet", "tür_geöffnet")),
    (FINISHED, ("finished", "finish", "end", "ended", "program_end", "program_ended", "programme_end", "programme_ended",
                "program_finished", "programme_finished", "done", "complete", "completed", "drying_complete",
                "drying_completed", "drying_finished", "drying_done", "drying_ended", "fertig", "beendet", "ende",
                "programmende", "programm_beendet", "programm_fertig", "abgeschlossen", "trocknen_beendet",
                "trocknung_beendet", "trocknung_abgeschlossen")),
    (WASHING, ("wash", "washing", "main_wash", "mainwash", "main_dishwash", "pre_wash", "prewash", "pre_dishwash",
               "rinse", "rinsing", "pre_rinse", "interim_rinse", "final_rinse", "clear_rinse", "hot_rinse", "heating",
               "pre_drain", "drain", "run", "running", "in_progress", "program_running", "programme_running",
               "spuelen", "spülen", "hauptspuelen", "hauptspülen", "vorspuelen", "vorspülen", "klarspuelen",
               "klarspülen", "zwischenspuelen", "zwischenspülen", "reinigen", "aufheizen", "laeuft", "läuft")),
    (IDLE, ("off", "idle", "ready", "standby", "inactive", "aus", "bereit", "inaktiv", "none", "not_running",
            "not_drying", "no_drying", "drying_off", "drying_inactive", "nicht_trocknen", "keine_trocknung",
            "program_idle", "waiting", "waiting_to_start", "delayed_start", "delayedstart", "programmed", "pause",
            "paused", "pausiert", "cancelled", "canceled", "aborted", "abgebrochen", "closed", "geschlossen")),
):
    for _word in _words:
        _EXACT[_word] = _phase

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def normalize_state(value: Any) -> str:
    """Lower-case token of a device state: "Drying complete" / "drying-complete" / "dryingComplete" →
    "drying_complete"; an enum path "BSH.Common.EnumType.OperationState.Finished" → its last part "finished"."""
    text = str(getattr(value, "state", value) or "").strip()
    if "." in text and " " not in text:
        text = text.rsplit(".", 1)[-1]
    text = _CAMEL.sub("_", text).lower()
    text = re.sub(r"[\s\-/]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def dishwasher_phase(entity_id: Any, state: Any) -> str | None:
    """Phase of the device signal (``PHASES``), or None when it says nothing.

    A binary sensor (or switch) is a "drying" signal – on = drying – or, with device class door/opening, the door:
    on = door open. Text states are matched exactly against known words in English and German; anything else is
    unknown and changes nothing (never "drying" by default).
    """
    domain = str(entity_id or "").partition(".")[0].lower()
    value = normalize_state(state)
    if value in {"", "unknown", "unavailable"}:
        return None
    if domain in {"binary_sensor", "switch", "input_boolean"}:
        attributes = getattr(state, "attributes", None)
        device_class = str(attributes.get("device_class") or "") if isinstance(attributes, dict) else ""
        on_phase = DOOR_OPEN if device_class in {"door", "opening", "window"} else DRYING
        return on_phase if value == "on" else IDLE if value == "off" else None
    return _EXACT.get(value)


def effective_phase(memory: dict[str, Any], phase: str | None, now: Any) -> str | None:
    """Phase including the after-evaporation: for ``AFTER_EVAPORATION_MIN`` after the last drying / door opening the
    warm load still releases vapour, while the device itself already reports idle, finished or nothing.
    A new washing phase ends it. ``now`` is a datetime; the memory keeps the time as ISO text."""
    from datetime import datetime  # noqa: PLC0415 – keeps the module import-light

    if phase in RELEASE_PHASES:
        memory["dishwasher_release_at"] = now.isoformat()
        return phase
    if phase == WASHING:
        memory.pop("dishwasher_release_at", None)
        return phase
    try:
        released = datetime.fromisoformat(str(memory.get("dishwasher_release_at")))
    except (TypeError, ValueError):
        return phase
    if 0.0 <= (now - released).total_seconds() / 60.0 <= AFTER_EVAPORATION_MIN:
        return AFTER_EVAPORATION
    memory.pop("dishwasher_release_at", None)
    return phase
