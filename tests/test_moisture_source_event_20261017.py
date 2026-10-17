"""0.26.5.1 (community: run the bathroom fan only after showering): the bus event
``freshairiq_moisture_source`` reports when an internal moisture source starts
and ends in a room."""
from __future__ import annotations

from custom_components.freshairiq.automation_events import (
    EVENT_MOISTURE_SOURCE,
    AutomationEventEmitter,
    moisture_source_payload,
)


def _bad(active=False, source=None, **extra):
    return {"key": "bad", "name": "Badezimmer", "floor": "EG", "action": "Okay", "humidity": 78, "mould_level": "Low",
            "moisture_source_active": active, "moisture_source_identified_source": source,
            "moisture_source_confidence": 84 if active else 0, "moisture_source_rate_ml_min": 9.5,
            "moisture_source_generated_ml_window": 48.0, "moisture_source_started_at": "2026-10-17T07:02:00+02:00",
            "moisture_source_last_ended_at": None if active else "2026-10-17T07:21:00+02:00", **extra}


def _data(room, language=None):
    data = {"rooms": {room["key"]: room}, "intelligent_recommendation": {"kind": "okay", "instruction": ""}}
    if language:
        data["output_language"] = language
    return data


def _source_events(fired):
    return [p for t, p in fired if t == EVENT_MOISTURE_SOURCE]


def test_shower_start_and_end_fire_once_each():
    fired = []
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1")
    emitter.process(_data(_bad()))  # first cycle stays silent
    emitter.process(_data(_bad()))
    assert _source_events(fired) == []
    emitter.process(_data(_bad(True, "shower")))
    emitter.process(_data(_bad(True, "shower")))  # still active: no repeat
    emitter.process(_data(_bad(False, None)))  # the detector forgets the source when it ends
    started, ended = _source_events(fired)
    assert started["phase"] == "started" and started["source"] == "shower" and started["source_label"] == "Dusche"
    assert started["message"] == "Badezimmer: Dusche erkannt."
    assert started["confidence"] == 84 and started["rate_ml_min"] == 9.5 and started["generated_ml"] == 48.0
    assert started["ended_at"] is None and started["room_key"] == "bad" and started["entry_id"] == "entry1"
    assert ended["phase"] == "ended" and ended["source"] == "shower"  # still named at the end
    assert ended["message"] == "Badezimmer: Dusche beendet." and ended["ended_at"] == "2026-10-17T07:21:00+02:00"


def test_unidentified_source_and_english_labels():
    fired = []
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1")
    emitter.process(_data(_bad(), "en"))
    emitter.process(_data(_bad(True, None), "en"))
    emitter.process(_data(_bad(False, None), "en"))
    started, ended = _source_events(fired)
    assert started["source"] is None and started["source_label"] == "Moisture source"
    assert started["message"] == "Badezimmer: Moisture source detected."
    assert ended["message"] == "Badezimmer: Moisture source ended."


def test_room_seen_for_the_first_time_does_not_fire():
    fired = []
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1")
    emitter.process(_data(_bad()))
    data = _data(_bad())
    data["rooms"]["kueche"] = {**_bad(True, "cooking"), "key": "kueche", "name": "Küche"}
    emitter.process(data)
    assert _source_events(fired) == []


def test_payload_ignores_unknown_source_codes_and_bad_numbers():
    payload = moisture_source_payload(_bad(True, "teapot", moisture_source_confidence=None, moisture_source_rate_ml_min="x"),
                                      phase="started", source="teapot", language="de", entry_id="e")
    assert payload["source"] is None and payload["source_label"] == "Feuchtequelle"
    assert payload["confidence"] == 0 and payload["rate_ml_min"] is None
