"""0.26.4.6: stable Home Assistant events for user automations (Node-RED, Alexa, scripts)."""
from __future__ import annotations

import copy
from pathlib import Path

from custom_components.freshairiq.automation_events import (
    EVENT_HOUSE_RECOMMENDATION,
    EVENT_MOULD_RISK,
    EVENT_ROOM_ACTION,
    AutomationEventEmitter,
    action_code,
    ventilation_measures_active,
)

ROOT = Path(__file__).resolve().parents[1]


def _room(key="schlaf", name="Schlafzimmer", action="Okay", **extra):
    return {"key": key, "name": name, "action": action, "humidity": 58, "temperature": "21.4", "potential_ml": 40,
            "mould_level": "Low", "surface_rh": 64, "active": False, "data_quality": "ok",
            "recommendation_reasons": ["Raumluftfeuchte 58 %"], **extra}


def _data(rooms, iq=None, language=None):
    data = {"rooms": {r["key"]: r for r in rooms}, "intelligent_recommendation": iq or {"kind": "okay", "title": "Alles gut", "instruction": ""}}
    if language:
        data["output_language"] = language
    return data


def _emitter():
    fired: list[tuple[str, dict]] = []
    return AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1"), fired


def test_first_cycle_is_silent_and_changes_fire_once():
    emitter, fired = _emitter()
    assert emitter.process(_data([_room()])) == 0
    assert emitter.process(_data([_room()])) == 0
    assert fired == []

    emitter.process(_data([_room(action="Close")]))
    assert [t for t, _ in fired] == [EVENT_ROOM_ACTION]
    payload = fired[0][1]
    assert payload["action"] == "close" and payload["previous_action"] == "okay"
    assert payload["message"] == "Schlafzimmer: Bitte Fenster schließen."
    assert payload["temperature"] == 21.4 and payload["entry_id"] == "entry1" and payload["schema_version"] == 1
    emitter.process(_data([_room(action="Close")]))
    assert len(fired) == 1  # unchanged state does not repeat


def test_new_rooms_do_not_fire_on_first_appearance_and_bad_values_are_tolerated():
    emitter, fired = _emitter()
    emitter.process(_data([_room()]))
    emitter.process(_data([_room(), _room(key="bad", name="Bad", action="Ventilate", humidity="nan", potential_ml=None)]))
    assert fired == []
    emitter.process(_data([_room(), _room(key="bad", name="Bad", action="Close", humidity="x")]))
    assert fired[0][1]["humidity"] is None
    data = _data([_room()])
    data["rooms"]["broken"] = "not-a-room"
    emitter.process(data)
    emitter.process({"rooms": "broken", "intelligent_recommendation": "broken"})


def test_house_recommendation_and_english_labels():
    emitter, fired = _emitter()
    iq = {"kind": "wait", "status": "wait", "title": "Noch etwas warten", "instruction": "Noch nicht lüften", "room_keys": ["schlaf"],
          "room_names": ["Schlafzimmer"], "reasons": ["a", "b"], "duration_min": None, "night_strategy_primary": True}
    emitter.process(_data([_room()], iq))
    changed = dict(iq, kind="ventilate", title="Jetzt lüften", instruction="Schlafzimmer öffnen", duration_min=9)
    emitter.process(_data([_room(action="Ventilate")], changed, language="en"))
    types = [t for t, _ in fired]
    assert types == [EVENT_ROOM_ACTION, EVENT_HOUSE_RECOMMENDATION]
    room = fired[0][1]
    assert room["message"] == "Schlafzimmer: Please air the room."
    house = fired[1][1]
    assert house["kind"] == "ventilate" and house["previous_kind"] == "wait"
    assert house["message"] == "Jetzt lüften. Schlafzimmer öffnen"
    assert house["duration_min"] == 9.0 and house["night_strategy"] is True
    emitter.process(_data([_room(action="Ventilate")], dict(changed, title="")))
    assert len(fired) == 2  # same kind/rooms/instruction: no new house event


def test_mould_risk_changes_report_direction_and_active_measures():
    emitter, fired = _emitter()
    emitter.process(_data([_room()]))
    emitter.process(_data([_room(mould_level="High", configured_actuators={"mechanical_exhaust_active": True})]))
    assert [t for t, _ in fired] == [EVENT_MOULD_RISK]
    assert fired[0][1]["rising"] is True and fired[0][1]["previous_mould_level"] == "low"
    assert fired[0][1]["mould_level"] == "high"
    assert fired[0][1]["ventilation_measures_active"] is True
    emitter.process(_data([_room(mould_level="Elevated")]))
    assert fired[-1][1]["rising"] is False
    assert emitter.fired == 2


def test_mould_codes_match_sensor_states():
    from custom_components.freshairiq.automation_events import mould_code

    assert mould_code("Very high") == "very_high" and mould_code(None) is None and mould_code("") is None


def test_action_codes_are_stable():
    assert action_code("Ventilate") == "ventilate"
    assert action_code("Ventilate for cooling") == "ventilate_for_cooling"
    assert action_code("Continue ventilating") == "continue_ventilating"
    assert action_code("Something new") == "something_new"
    assert action_code(None) == "unknown"


def test_ventilation_measures_cover_window_fan_shower_and_buffer():
    assert not ventilation_measures_active(_room())
    assert ventilation_measures_active(_room(active=True))
    assert ventilation_measures_active(_room(configured_actuators={"mechanical_exhaust_active": True}))
    assert ventilation_measures_active(_room(moisture_source_active=True))
    assert ventilation_measures_active(_room(moisture_source_recovery=True))
    assert ventilation_measures_active(_room(post_close_stabilization_active=True))
    assert not ventilation_measures_active(_room(configured_actuators="broken"))


def test_an_evening_produces_a_sparse_well_formed_event_stream():
    emitter, fired = _emitter()
    rooms = [_room(key=f"r{i}", name=f"Raum {i}") for i in range(4)]
    sequence = ["Okay", "Ventilate", "Ventilate", "Continue ventilating", "Close", "Okay"]
    for step, action in enumerate(sequence):
        current = copy.deepcopy(rooms)
        current[step % 4]["action"] = action
        emitter.process(_data(current))
    assert all(t == EVENT_ROOM_ACTION for t, _ in fired)
    assert len(fired) <= 2 * len(sequence)
    assert all(p["message"].endswith(".") for _, p in fired)


def test_coordinator_registers_and_releases_the_event_listener():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "self.automation_events = AutomationEventEmitter(" in source
    assert "add_listener(self._async_fire_automation_events)" in source
    stop = source[source.index("async def async_stop_listeners"):]
    assert "self._unsub_automation_events()" in stop[:600]


def test_mould_notifications_wait_until_ventilation_measures_end():
    source = (ROOT / "custom_components/freshairiq/notifications.py").read_text(encoding="utf-8")
    assert 'room.get("mould_level") in {"High", "Very high"} and not ventilation_measures_active(room)' in source


def test_documentation_and_blueprints_match_the_event_contract():
    from custom_components.freshairiq import automation_events as ev

    guide = (ROOT / "docs/AUTOMATIONEN.md").read_text(encoding="utf-8")
    english = (ROOT / "docs/AUTOMATIONS.md").read_text(encoding="utf-8")
    for name in (ev.EVENT_ROOM_ACTION, ev.EVENT_HOUSE_RECOMMENDATION, ev.EVENT_MOULD_RISK):
        assert name in guide and name in english
    for code in ev.ACTION_CODES.values():
        if code != "open_fully":
            assert f"`{code}`" in guide, code
    for blueprint in ("announce_room_action.yaml", "device_follows_room_action.yaml"):
        text = (ROOT / "blueprints/automation/freshairiq" / blueprint).read_text(encoding="utf-8")
        assert "event_type: freshairiq_room_action" in text
        assert "trigger.event.data" in text
        # Rooms are picked from a list; nobody has to know internal room keys.
        assert "integration: freshairiq" in text
        assert "state_attr" in text and "freshairiq_room_key" in text
