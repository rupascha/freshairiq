"""Regression contracts for 0.25.0.10 aggregate close-gate hotfix."""
from dataclasses import asdict
from pathlib import Path

from custom_components.freshairiq.consolidation import aggregate_close_allowed
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def _result(*, fresh: int, elapsed: float = 10.0):
    room = RoomInput(
        "living", "Living room", 20, 58, 15, 55, 80, True, int(elapsed * 60),
        session_active=True,
        session_elapsed_min=elapsed,
        session_start_temp=21,
        learning_rate=0.03,
        session_fresh_measurements=fresh,
    )
    return asdict(evaluate_room(room, {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 20}, False))


def test_aggregate_close_is_blocked_with_zero_fresh_measurements():
    room = _result(fresh=0)
    assert room["close_decision_ready"] is False
    assert aggregate_close_allowed([room], low_return=True, thermal_bad=False) is False


def test_aggregate_close_is_blocked_with_one_fresh_measurement():
    room = _result(fresh=1)
    assert room["close_decision_ready"] is False
    assert aggregate_close_allowed([room], low_return=True, thermal_bad=False) is False


def test_aggregate_close_is_allowed_after_two_fresh_measurements():
    room = _result(fresh=2)
    assert room["close_decision_ready"] is True
    assert aggregate_close_allowed([room], low_return=True, thermal_bad=False) is True


def test_aggregate_close_may_use_15_minute_model_fallback_without_two_reports():
    room = RoomInput(
        "living", "Living room", 23, 70, 8, 45, 80, True, 900,
        session_active=True,
        session_elapsed_min=15.0,
        session_start_temp=23,
        learning_rate=0.03,
        session_fresh_measurements=0,
    )
    result = asdict(evaluate_room(
        room,
        {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 20, "min_return_next_5_min_ml": 1},
        False,
    ))
    assert result["close_decision_ready"] is True
    assert result["close_decision_model_fallback"] is True
    assert aggregate_close_allowed([result], low_return=True, thermal_bad=False) is True


def test_house_and_floor_aggregate_paths_both_use_the_close_gate():
    assert "house_should_close = aggregate_close_allowed(" in COORD
    assert "floor_should_close = aggregate_close_allowed(" in COORD
    assert "house_close_gate_ready = aggregate_close_gate_ready(active)" in COORD
    assert "floor_close_gate_ready = aggregate_close_gate_ready(floor_active)" in COORD
