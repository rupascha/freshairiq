"""B1/B3 (0.26.7.1): the released temperature limit survives every overlay; a held close keeps its true origin.

B1 – two open paths (helpful outdoor window, unsuitable conservatory door): the room model released the close at the
explicit limit, but the reason chosen was "air no longer helps" (the delta of the moistest path) and the opening overlay
turned the house close into "keep the window open". The limit is now the close kind whenever it is reached (and no
critical CO₂ keeps the window open); the opening and presentation overlays keep it.
B3 – a close stored because of the temperature limit was later held as "goals were reached" although the humidity goal
was never reached. The stored close carries its cause (``close_notified_kind``); only a really reached goal holds.
All fixtures are synthetic (dummy entity IDs, no real HA session).
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.live_coach import align_live_coach_state
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.notification_policy import effective_room_action
from custom_components.freshairiq.opening_strategy import (
    close_rooms_released_on_their_own, enrich_opening_recommendation, house_aligned_room_actions,
    keep_moisture_sources_open, synchronize_room_presentation_actions,
)
from custom_components.freshairiq.room_close_strategy import room_close_options
from custom_components.freshairiq.room_recommendation import _close_reason, _recommendation

OPTIONS = {**DEFAULT_OPTIONS, "target_rh": 58.0, "min_duration_min": 5.0, "airing_min_room_temp_c": 16.0, "operating_profile": "comfort"}
GOOD = dict(reference_temperature=0.7, reference_humidity=92.0)     # outdoor window (relative humidity, %)
POOR = dict(reference_temperature=14.0, reference_humidity=75.0)    # conservatory door


def _bath(t=14.9, *, source=True, ref=POOR, co2=None, **extra):
    return RoomInput(key="bad", name="Bad", temperature=t, humidity=70.0, volume_m3=9.4, contact_open=True,
                     contact_open_seconds=1800, session_active=True, session_elapsed_min=30.0, session_fresh_measurements=6,
                     moisture_source_active=source, moisture_source_label="Dusche", co2=co2, **ref, **extra)


def _assessment(name, result):
    return {"entity_id": f"binary_sensor.fixture_{name}", "name": name, "available": True, "is_open": True,
            "delta_g_m3": result.delta_g_m3, "moisture_effect_next_5_min_ml": result.moisture_effect_next_5_min_ml,
            "temperature_effect_next_5_min_c": result.temp_next_5_min_c, "ventilation_candidate": result.ventilation_candidate}


def _pipeline(room_input, *, openings=("aussen", "wintergarten"), co2=None, options=OPTIONS):
    """Original model → room wording → every final overlay, as in the coordinator order."""
    used = evaluate_room(room_input, options, False)
    action, reason, reasons = _recommendation(used, options, pollen=0.0, co2=co2, airflow=1.0, wind_bearing=None, wind_speed=None)
    assessments = []
    for name in openings:
        ref = GOOD if name == "aussen" else POOR
        assessments.append(_assessment(name, evaluate_room(replace(room_input, **ref), options, False)))
    room = used.as_dict() | {"key": "bad", "name": "Bad", "action": action, "reason": reason, "recommendation_reasons": reasons,
                             "active": True, "open": True, "opening_state": "open", "session_elapsed_min": 30.0,
                             "opening_assessments": assessments}
    rooms = {"bad": room}
    kind = "close" if used.close_recommended else "continue"
    rec = {"kind": kind, "status": "close_windows" if kind == "close" else "ventilation_running", "room_keys": ["bad"],
           "title": "x", "instruction": "Bad schließen", "duration_min": 0.0, "reasons": [], "presentation_scope": "room"}
    rec = enrich_opening_recommendation(rec, rooms, options)
    close_rooms_released_on_their_own(rec, rooms)
    keep_moisture_sources_open(rec, rooms, options)
    align_live_coach_state(rec)
    synchronize_room_presentation_actions(rec, rooms, min_duration_min=5.0)
    house_aligned_room_actions(rec, rooms)
    return used, rec, room


@pytest.mark.parametrize("source", [True, False])
@pytest.mark.parametrize("openings", [("aussen", "wintergarten"), ("wintergarten",)])
def test_b1_limit_released_with_poor_model_path_closes_end_to_end(source, openings):
    used, rec, room = _pipeline(_bath(source=source), openings=openings)
    assert used.close_recommended and used.close_kind == "temperature_limit"
    assert rec["kind"] == "close" and rec["room_keys"] == ["bad"]
    assert "offen lassen" not in rec["instruction"]
    assert room["action"] == "Close" and room["house_aligned_action"] == "close"
    assert effective_room_action(room, rec, {"bad": room}) == "Close"          # notification layer
    assert any("Temperaturgrenze" in r for r in room["recommendation_reasons"])


@pytest.mark.parametrize("source", [True, False])
def test_b1_limit_released_with_helpful_model_path_closes(source):
    used, rec, room = _pipeline(_bath(source=source, ref=GOOD))
    assert used.close_kind == "temperature_limit" and rec["kind"] == "close" and room["house_aligned_action"] == "close"


@pytest.mark.parametrize("t,limited", [(15.9, True), (16.0, True), (16.1, False)])
def test_b1_limit_boundary(t, limited):
    used, rec, room = _pipeline(_bath(t, source=True, ref=GOOD))
    assert (used.close_kind == "temperature_limit") is limited
    if not limited:                                    # above the limit the shower keeps the helpful window open
        assert room["action"] == "Continue ventilating"


def test_b1_critical_co2_keeps_its_existing_priority():
    used, rec, room = _pipeline(_bath(source=True, ref=GOOD, co2=1600.0), co2=1600.0)
    assert used.close_kind != "temperature_limit" and room["action"] == "Continue ventilating"


def test_b1_two_paths_without_a_limit_still_route_the_air():
    # unchanged behaviour: no explicit limit → a mixed-path close is refined to "keep the good path, close the poor one"
    options = {**OPTIONS, "airing_min_room_temp_c": 0.0}
    used, rec, room = _pipeline(_bath(source=False), options=options)
    assert used.close_kind == "air_no_longer_helps"
    assert rec["kind"] == "continue" and "aussen offen lassen" in rec["instruction"]


# ------------------------------------------------------------------------------------------------ B3

GOALS = room_close_options({**DEFAULT_OPTIONS, "target_rh": 58.0, "min_duration_min": 5.0, "airing_min_room_temp_c": 16.0},
                           {"close_strategy": "goals_reached"})


def _trace(steps, *, kind_store=True):
    base = RoomInput(key="bad", name="Bad", temperature=14.9, humidity=59.0, volume_m3=9.4, contact_open=True,
                     contact_open_seconds=1800, session_active=True, session_elapsed_min=30.0, session_fresh_measurements=6, **GOOD)
    latched, kind, out = False, None, []
    for minute, (t, rh) in enumerate(steps, start=5):
        result = evaluate_room(replace(base, temperature=t, humidity=rh, session_elapsed_min=float(minute),
                                       contact_open_seconds=minute * 60, close_notified=latched,
                                       close_notified_kind=kind if kind_store else None), GOALS, False)
        out.append(result)
        latched = result.close_recommended          # the coordinator's update rule (coordinator_room_model)
        kind = ((result.close_kind if kind is None or result.close_kind == "goals_reached" else kind) if latched else None)
    return out


def test_b3_a_temperature_close_never_becomes_reached_goals():
    trace = _trace([(20.0, 65.0), (19.0, 63.0), (17.0, 61.0), (15.0, 59.0), (14.9, 59.0), (17.0, 59.0)])
    assert [r.close_kind for r in trace[3:5]] == ["temperature_limit", "temperature_limit"]
    final = trace[-1]
    assert final.close_kind != "goals_held"
    assert "Ziele dieses Raums wurden" not in _close_reason(final, GOALS)
    control = evaluate_room(replace(RoomInput(key="bad", name="Bad", temperature=17.0, humidity=59.0, volume_m3=9.4,
                                              contact_open=True, contact_open_seconds=600, session_active=True,
                                              session_elapsed_min=10.0, session_fresh_measurements=6, **GOOD)),
                            {**GOALS, "room_close_on_goals": False}, False)
    assert final.action == control.action == "Continue ventilating"   # re-decided like a fresh evaluation


def test_b3_old_stored_close_without_cause_claims_no_goal():
    # older stored data: close_notified=True but no cause → conservative, no "goals reached" claim
    result = evaluate_room(RoomInput(key="bad", name="Bad", temperature=20.0, humidity=59.0, volume_m3=9.4, contact_open=True,
                                     contact_open_seconds=600, session_active=True, session_elapsed_min=10.0,
                                     session_fresh_measurements=6, close_notified=True, **GOOD), GOALS, False)
    assert result.close_kind != "goals_held"


def test_b3_really_reached_goals_still_hold_inside_the_hysteresis():
    trace = _trace([(20.0, 60.0), (20.0, 58.0), (20.0, 59.0), (20.0, 60.0), (20.0, 61.0)])
    assert trace[1].close_kind == "goals_reached"
    assert [r.close_kind for r in trace[2:4]] == ["goals_held", "goals_held"]
    assert not trace[4].close_recommended                           # above target + hysteresis → open again


def test_b3_stored_data_of_an_older_build_gets_an_unknown_cause():
    # a 0.26.7.0/.7.2 store has no ``close_notified_kind``: the room defaults add it as None (unknown) – the model then
    # claims no reached goal (see test_b3_old_stored_close_without_cause_claims_no_goal)
    from custom_components.freshairiq.storage_defaults import _room_defaults
    from custom_components.freshairiq.const import STORAGE_VERSION
    defaults = _room_defaults()
    assert "close_notified_kind" in defaults and defaults["close_notified_kind"] is None
    assert STORAGE_VERSION == 1                                     # no schema step: a downgrade from a test build loads
