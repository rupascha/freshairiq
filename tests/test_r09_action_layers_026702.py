"""R09 (0.26.7.2): physical vs. effective action – no presentation or aggregate layer loses a released protective close.

``canonical_action`` keeps the room engine's action, ``house_aligned_action`` is the presentation. A room whose own
temperature limit released the close (``close_kind == "temperature_limit"``) stays "close" through the final house
consolidation (aggregate return, long-opening tolerance, running moisture source) and through presentation alignment.
Other closes keep their existing behaviour (no generalisation of every ``close_recommended``).
"""
from __future__ import annotations

from custom_components.freshairiq.consolidation import stabilise_recommendation
from custom_components.freshairiq.model import min_return_volume_factor
from custom_components.freshairiq.notification_policy import effective_room_action
from custom_components.freshairiq.opening_strategy import house_aligned_room_actions, synchronize_room_presentation_actions

OPTIONS = {"min_return_next_5_min_ml": 25.0, "max_duration_min": 20.0, "close_delta": 0.4, "min_duration_min": 3.0}


def _room(key, *, kind="temperature_limit", next5=200.0, elapsed=12.0, **extra):
    room = dict(key=key, name=key, data_quality="ok", active=True, action="Close", close_recommended=True, close_kind=kind,
                session_elapsed_min=elapsed, temperature_change_c=-0.3, delta_g_m3=2.9, forecast_5_min_temperature_change_c=-0.1,
                volume_m3=30.0, efficiency_ml_per_01c=50.0, forecast_5_min_moisture_effect_ml=next5, close_decision_ready=True)
    room.update(extra)
    return room


def _final(rooms, kind="close"):
    rec = stabilise_recommendation({"kind": kind, "room_keys": list(rooms)}, rooms, OPTIONS)
    synchronize_room_presentation_actions(rec, rooms, min_duration_min=OPTIONS["min_duration_min"])
    house_aligned_room_actions(rec, rooms)
    return rec


def test_large_aggregate_return_does_not_turn_a_released_temperature_close_into_continue():
    rooms = {"bad": _room("bad")}
    rec = _final(rooms)
    assert rec["kind"] == "close" and rec["room_keys"] == ["bad"]
    assert rooms["bad"]["action"] == "Close" and rooms["bad"]["house_aligned_action"] == "close"


def test_other_closes_keep_the_existing_aggregate_hold():
    # the physical "air no longer helps" close with a large combined return stays held as before (no generalisation)
    thr = 25.0 * min_return_volume_factor(30.0)
    rooms = {"bad": _room("bad", kind="air_no_longer_helps", next5=thr * 2)}
    assert _final(rooms)["kind"] == "continue"


def test_a_long_opening_with_a_released_limit_is_not_tolerated_as_monitor_open():
    rooms = {"bad": _room("bad", next5=0.0, elapsed=45.0, temperature_change_c=-0.4)}
    rec = _final(rooms)
    assert rec.get("status") != "passive_open_monitor" and rec["kind"] == "close"
    assert rooms["bad"]["house_aligned_action"] == "close"
    # the tolerance itself is unchanged for other closes
    other = {"bad": _room("bad", kind="air_no_longer_helps", next5=0.0, elapsed=45.0, temperature_change_c=-0.4)}
    assert _final(other).get("status") == "passive_open_monitor"


def test_source_room_with_a_released_limit_is_closed_and_not_kept_open_beside_it():
    rooms = {"bad": _room("bad", moisture_source_active=True, moisture_source_label="Dusche"),
             "gast": _room("gast", kind=None, action="Continue ventilating", close_recommended=False, moisture_source_active=True,
                           moisture_source_label="Dusche")}
    rec = _final(rooms)
    assert rec["kind"] == "close" and rec["room_keys"] == ["bad"]
    assert "bad" not in (rec.get("moisture_source_kept_open") or [])
    assert rooms["bad"]["house_aligned_action"] == "close"
    assert rooms["gast"]["action"] == "Continue ventilating"


def test_canonical_and_effective_layers_reach_their_receivers():
    rooms = {"bad": _room("bad", kind="air_no_longer_helps", next5=0.0, elapsed=4.0, action="Continue ventilating", close_recommended=False),
             "flur": _room("flur", next5=0.0)}
    rec = _final(rooms)
    # presentation alignment keeps the engine's action as canonical_action where it rewrote it
    for room in rooms.values():
        if "presentation_action_override" in room:
            assert room["canonical_action"] != room["action"]
    # the notification policy reads the effective (house-aligned) layer; the protective close survives there
    assert rooms["flur"]["house_aligned_action"] == "close"
    assert effective_room_action(rooms["flur"], rec, rooms) == "Close"


def test_anchor_a_room_still_needing_co2_is_not_presented_as_close_by_another_rooms_close():
    # synthetic anchor: one room released its close, a second room is not released and still needs CO₂ (≈1057 ppm).
    # The observed .7.0 payload showed action="Close" with close_recommended=false for the second room.
    rooms = {"schlaf": _room("schlaf", kind="air_no_longer_helps", next5=0.0),
             "wohnen": _room("wohnen", kind=None, action="Continue ventilating", close_recommended=False, co2=1057.0,
                             goal_state={"hard_close": False, "goals": [{"id": "co2", "active": True, "reached": False}]},
                             next5=0.0, delta_g_m3=0.3)}
    rec = stabilise_recommendation({"kind": "close", "room_keys": ["schlaf", "wohnen"]}, rooms, OPTIONS)
    synchronize_room_presentation_actions(rec, rooms, min_duration_min=OPTIONS["min_duration_min"])
    house_aligned_room_actions(rec, rooms)
    assert "wohnen" not in rec["room_keys"]
    assert not (rooms["wohnen"]["action"] == "Close" and rooms["wohnen"]["close_recommended"] is False)
