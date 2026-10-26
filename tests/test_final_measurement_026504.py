"""0.26.5.4: a closed window in its final measurement is not aired any more.

After the contact closes, the session lives on for a short final measurement
(``session_finalization_pending``). Room recommendation, house recommendation,
its consolidation, the floor/house mode and the room presentation all read the
session flag as "still aired" and told the user to keep ventilating (or to
close) an already closed window for one more cycle.
"""
from __future__ import annotations

from custom_components.freshairiq.close_wording import airing_running
from custom_components.freshairiq.consolidation import session_target_min, stabilise_recommendation
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.opening_strategy import synchronize_room_presentation_actions
from custom_components.freshairiq.recommendation import build_recommendation
from custom_components.freshairiq.room_recommendation import _recommendation

OPTIONS = dict(DEFAULT_OPTIONS)


def _room(**extra) -> dict:
    room = {"key": "kueche", "name": "Küche", "active": True, "open": False, "session_finalization_pending": True,
            "calculation_enabled": True, "data_quality": "ok", "action": "Wait", "delta_g_m3": 3.0,
            "humidity": 66.0, "close_decision_ready": True, "floor": "EG"}
    room.update(extra)
    return room


def test_airing_running() -> None:
    assert airing_running(_room(session_finalization_pending=False)) is True
    assert airing_running(_room()) is False
    assert airing_running(_room(active=False, session_finalization_pending=False)) is False
    assert airing_running(None) is False


def test_closed_room_is_not_told_to_keep_ventilating() -> None:
    room = RoomInput(key="kueche", name="Küche", temperature=21.0, humidity=66.0, reference_temperature=8.0, reference_humidity=70.0,
                     volume_m3=40.0, contact_open=False, contact_open_seconds=None, learning_rate=0.03,
                     session_active=True, session_elapsed_min=8.0, session_fresh_measurements=2)
    result = evaluate_room(room, OPTIONS, False)
    assert result.active is True and result.open is False
    action, _reason, _reasons = _recommendation(result, OPTIONS, pollen=0.0, co2=None, airflow=1.0, wind_bearing=None, wind_speed=None)
    assert action not in {"Continue ventilating", "Close"}
    result.open = True  # the same session with the window still open keeps its running action
    action, _reason, _reasons = _recommendation(result, OPTIONS, pollen=0.0, co2=None, airflow=1.0, wind_bearing=None, wind_speed=None)
    assert action in {"Continue ventilating", "Close"}


def test_consolidation_does_not_turn_the_house_back_to_continue() -> None:
    out = stabilise_recommendation({"kind": "wait", "status": "wait", "room_keys": []}, {"kueche": _room()}, OPTIONS)
    assert out["kind"] == "wait" and "kueche" not in out["room_keys"]
    running = stabilise_recommendation({"kind": "wait", "status": "wait", "room_keys": []},
                                       {"kueche": _room(open=True, session_finalization_pending=False)}, OPTIONS)
    assert running["kind"] == "continue"


def test_presentation_keeps_the_closed_room_out_of_continue() -> None:
    rooms = {"kueche": _room()}
    synchronize_room_presentation_actions({"kind": "continue", "room_keys": ["kueche"]}, rooms)
    assert rooms["kueche"]["action"] == "Wait" and "presentation_action_override" not in rooms["kueche"]


def test_house_recommendation_does_not_continue_a_closed_room() -> None:
    rooms = {"kueche": _room(forecast_5_min_moisture_effect_ml=20.0, moisture_effect_next_5_min_ml=20.0)}
    out = build_recommendation(rooms, OPTIONS, threshold_ml=200.0, total_potential_ml=0.0, recommended_duration_min=10.0)
    assert not (out["kind"] in {"continue", "close"} and "kueche" in out["room_keys"]), out["kind"]
    assert rooms["kueche"]["active"] is True  # the caller's room data is left as it is


def test_a_new_window_does_not_join_a_finished_airing() -> None:
    previous = {"remaining_duration_min": 4.0, "recommended_duration_min": 12.0}
    assert session_target_min({**previous, "rooms": {"kueche": _room()}}, OPTIONS) == 12.0
    assert session_target_min({**previous, "rooms": {"kueche": _room(open=True, session_finalization_pending=False)}}, OPTIONS) == 4.0
