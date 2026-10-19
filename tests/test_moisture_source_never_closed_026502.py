"""0.26.5.2 (owner, Wellnessraum): "Schließen" while the sauna runs is a no-go.

The room engine kept the room open ("Sauna wahrscheinlich aktiv … die steigende
Raumfeuchte stammt aus der aktiven Feuchtequelle"), but the house/floor
aggregate that runs later closed every open room together, and the presentation
layer then turned the room action into "Close".
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.house_decision import floor_ventilation_decision
from custom_components.freshairiq.opening_strategy import keep_moisture_sources_open, synchronize_room_presentation_actions

OPTIONS = {"close_delta": 0.4}


def _room(key, **extra):
    room = {"key": key, "name": key.title(), "floor": "ground_floor", "volume_m3": 30.0, "active": True,
            "forecast_5_min_net_moisture_change_ml": 1.0, "forecast_5_min_temperature_change_c": -0.1,
            "close_decision_ready": True, "action": "Close", "close_recommended": True,
            "delta_g_m3": 1.2, "session_elapsed_min": 30.0}
    room.update(extra)
    return room


def _sauna(**extra):
    fields = {"name": "Wellnessraum", "action": "Continue ventilating", "close_recommended": False,
              "moisture_source_active": True, "moisture_source_label": "Sauna"}
    return _room("wellnessraum", **{**fields, **extra})


def _house_close(rooms, house_mode):
    rec: dict = {}
    floor_ventilation_decision(active=rooms, cross=False, forecast_confidence=70, forecast_cost=0.1,
                               house_ventilation_mode=house_mode, intelligent_recommendation=rec,
                               night_strategy={}, options=OPTIONS, valid=rooms)
    return rec


@pytest.mark.parametrize("house_mode", [True, False])
def test_the_house_close_never_closes_the_sauna_room(house_mode):
    rooms = [_sauna(), _room("bad")]
    rec = _house_close(rooms, house_mode)
    assert rec["kind"] == "close" and "wellnessraum" in rec["room_keys"]  # the bug: aggregate closes both
    by_key = {r["key"]: r for r in rooms}
    keep_moisture_sources_open(rec, by_key, OPTIONS)
    synchronize_room_presentation_actions(rec, by_key)
    assert by_key["wellnessraum"]["action"] == "Continue ventilating"
    assert by_key["bad"]["action"] == "Close"
    assert rec["kind"] == "close" and rec["room_keys"] == ["bad"]
    assert rec["instruction"].endswith("Wellnessraum offen lassen (Sauna aktiv)")
    assert rec["reasons"][0].startswith("Wellnessraum: Sauna läuft")
    assert rec["decision_brain"]["action_line"] == rec["instruction"]
    assert rec["moisture_source_kept_open"] == ["wellnessraum"]


def test_only_the_sauna_room_open_turns_the_close_into_keep_ventilating():
    rooms = {"wellnessraum": _sauna()}
    rec = {"kind": "close", "status": "close_windows", "room_keys": ["wellnessraum"], "title": "Jetzt schließen",
           "instruction": "Wellnessraum schließen", "reasons": ["Zusatznutzen klein"]}
    keep_moisture_sources_open(rec, rooms, OPTIONS)
    synchronize_room_presentation_actions(rec, rooms)
    assert rec["kind"] == "continue" and rec["status"] == "moisture_source_active"
    assert rec["title"] == "Sauna erkannt" and rec["instruction"] == "Wellnessraum offen lassen (Sauna aktiv)"
    assert rec["room_keys"] == ["wellnessraum"] and rec["duration_min"] is None
    assert rooms["wellnessraum"]["action"] == "Continue ventilating"
    assert rec["reasons"] == ["Wellnessraum: Sauna läuft; die trocknere Außen-/Referenzluft führt die entstehende Feuchte weiter ab", "Zusatznutzen klein"]


@pytest.mark.parametrize("change", [
    {"moisture_source_active": False},          # no source
    {"action": "Close"},                        # the room itself says close (e.g. outdoor air too humid)
    {"delta_g_m3": 0.4},                        # reference air no longer drier than the close threshold
    {"active": False},                          # window already closed
])
def test_a_close_stays_when_the_room_does_not_keep_the_source_open(change):
    rooms = {"wellnessraum": _sauna(**change)}
    rec = {"kind": "close", "room_keys": ["wellnessraum"], "instruction": "Wellnessraum schließen"}
    keep_moisture_sources_open(rec, rooms, OPTIONS)
    assert rec == {"kind": "close", "room_keys": ["wellnessraum"], "instruction": "Wellnessraum schließen"}


def test_other_kinds_and_malformed_input_are_left_alone():
    rooms = {"wellnessraum": _sauna()}
    for rec in ({"kind": "continue", "room_keys": ["wellnessraum"]}, {"kind": "close", "room_keys": ["missing"]}):
        before = dict(rec)
        keep_moisture_sources_open(rec, rooms, OPTIONS)
        assert rec == before
    keep_moisture_sources_open(None, rooms, OPTIONS)  # type: ignore[arg-type]
    keep_moisture_sources_open({"kind": "close"}, None, OPTIONS)  # type: ignore[arg-type]
    rec = {"kind": "close", "room_keys": ["wellnessraum"]}
    keep_moisture_sources_open(rec, {"wellnessraum": _sauna(moisture_source_label=None)}, None)  # type: ignore[arg-type]
    assert rec["instruction"] == "Wellnessraum offen lassen (Feuchtequelle aktiv)" and rec["kind"] == "continue"
    rec = {"kind": "close", "room_keys": ["wellnessraum", "bad"]}
    keep_moisture_sources_open(rec, {"wellnessraum": _sauna(), "bad": _room("bad")}, OPTIONS)
    assert rec["instruction"] == "Jetzt schließen · Wellnessraum offen lassen (Sauna aktiv)"
