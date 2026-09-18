"""Fault-injection and behavioural regression tests for v0.25.0.7.

These tests deliberately feed FreshAirIQ states that real Home Assistant
installations can produce during startup, restore, provider failures or corrupt
persistence. The intent is behavioural: bad inputs must degrade to an explicit
non-learning/non-actionable state instead of poisoning adaptive state.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import inf, nan
from pathlib import Path

from custom_components.freshairiq.measurement_frame import build_measurement_frame
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.robustness import finite_float, sanitize_runtime_session

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


class FakeState:
    def __init__(self, stamp):
        self.last_reported = stamp
        self.last_updated = stamp


def _state(stamp):
    return FakeState(stamp)


def _valid_room(**overrides):
    values = dict(
        key="living",
        name="Living",
        temperature=21.0,
        humidity=60.0,
        reference_temperature=10.0,
        reference_humidity=70.0,
        volume_m3=55.0,
        contact_open=False,
        contact_open_seconds=0.0,
    )
    values.update(overrides)
    return RoomInput(**values)


def _options():
    return {
        "surface_factor": 0.25,
        "mould_warn_surface_rh": 80,
        "mould_critical_surface_rh": 90,
        "operating_profile": "comfort",
        "start_rh": 62,
        "min_delta": 2.5,
        "min_delta_high_rh": 1.5,
        "high_rh": 68,
        "close_delta": 0.4,
        "pollen_enabled": False,
        "pollen_max": 4,
        "min_room_potential_ml": 100,
        "close_efficiency_ml_per_01c": 20,
        "mould_surface_rh": 80,
    }


def test_unavailable_unknown_and_nonfinite_sensor_values_fail_closed():
    for value in ("unavailable", "unknown", "none", "", nan, inf, -inf, object()):
        assert finite_float(value) is None


def test_model_rejects_nan_and_inf_without_running_physics():
    for bad_room in (
        _valid_room(temperature=nan),
        _valid_room(humidity=inf),
        _valid_room(reference_temperature=-inf),
        _valid_room(volume_m3=nan),
    ):
        result = evaluate_room(bad_room, _options(), False)
        assert result.data_quality == "error"
        assert result.action == "Check sensor"
        assert result.absolute_humidity is None
        assert result.potential_ml == 0


def test_future_sensor_timestamp_is_not_allowed_to_train_model():
    now = datetime(2026, 9, 13, 0, 0, tzinfo=timezone.utc)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now + timedelta(minutes=5)),
        humidity_state=_state(now + timedelta(minutes=5)),
        reference_temperature_state=_state(now),
        reference_humidity_state=_state(now),
    )
    assert frame["quality"] == "stale"
    assert frame["learning_eligible"] is False
    assert frame["validation_eligible"] is False
    assert frame["max_future_offset_s"] == 300.0


def test_small_clock_jitter_does_not_unnecessarily_block_learning():
    now = datetime(2026, 9, 13, 0, 0, tzinfo=timezone.utc)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now + timedelta(seconds=2)),
        humidity_state=_state(now + timedelta(seconds=1)),
        reference_temperature_state=_state(now - timedelta(seconds=5)),
        reference_humidity_state=_state(now - timedelta(seconds=4)),
    )
    assert frame["quality"] == "excellent"
    assert frame["learning_eligible"] is True
    assert frame["max_future_offset_s"] == 2.0


def test_restart_session_preserves_valid_runtime_state():
    room = {
        "session_active": True,
        "session_start_temp": 21.4,
        "session_start_ah": 10.2,
        "session_start_source_ah": 7.1,
        "session_learning_start_ah": 10.2,
        "session_learning_source_ah": 7.1,
        "session_result_base_ml": -125.5,
        "session_result_ml": -130.0,
        "session_cross_seconds": 84.0,
        "session_fresh_measurements": 2,
        "session_forecast_timeline": [{"checkpoint_min": 5}],
        "session_prediction_snapshot_valid": True,
        "session_prediction_snapshot_pending": False,
        "session_start_frame_learning_eligible": True,
        "session_moisture_source_detected": False,
        "session_cross_active": True,
    }
    before = dict(room)
    repaired = sanitize_runtime_session(room)
    assert repaired == []
    assert room == before


def test_corrupt_restart_session_repairs_only_unsafe_fields():
    room = {
        "session_active": True,
        "session_start_temp": "not-a-number",
        "session_start_ah": nan,
        "session_start_source_ah": inf,
        "session_learning_start_ah": "broken",
        "session_learning_source_ah": 7.2,
        "session_result_base_ml": nan,
        "session_result_ml": inf,
        "session_cross_seconds": -20,
        "session_fresh_measurements": 99,
        "session_forecast_timeline": "corrupt",
        "session_prediction_snapshot_valid": True,
        "session_prediction_snapshot_pending": False,
        "session_start_frame_learning_eligible": True,
        "session_moisture_source_detected": False,
        "session_cross_active": True,
    }
    repaired = sanitize_runtime_session(room)
    assert room["session_active"] is True
    assert room["session_start_temp"] is None
    assert room["session_start_ah"] is None
    assert room["session_start_source_ah"] is None
    assert room["session_learning_start_ah"] is None
    assert room["session_learning_source_ah"] == 7.2
    assert room["session_result_base_ml"] == 0.0
    assert room["session_result_ml"] == 0.0
    assert room["session_cross_seconds"] == 0.0
    assert room["session_fresh_measurements"] == 2
    assert room["session_forecast_timeline"] == []
    assert "session_start_temp" in repaired


def test_corrupt_truthy_string_cannot_create_phantom_active_session():
    room = {
        "session_active": "false",
        "session_prediction_snapshot_valid": "yes",
        "session_prediction_snapshot_pending": 1,
        "session_start_frame_learning_eligible": "true",
        "session_moisture_source_detected": None,
        "session_cross_active": "on",
        "session_result_base_ml": 0,
        "session_result_ml": 0,
        "session_cross_seconds": 0,
        "session_fresh_measurements": 0,
        "session_forecast_timeline": [],
    }
    sanitize_runtime_session(room)
    assert room["session_active"] is False
    assert room["session_prediction_snapshot_valid"] is False
    assert room["session_prediction_snapshot_pending"] is False
    assert room["session_start_frame_learning_eligible"] is False
    assert room["session_cross_active"] is False


def test_production_paths_use_finite_guards_before_weather_and_session_math():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    weather = (COMP / "weather_future.py").read_text(encoding="utf-8")
    storage = (COMP / "storage.py").read_text(encoding="utf-8")
    assert "return finite_float(state.state)" in coordinator
    assert 'temperature = finite_float(state.attributes.get("temperature"))' in coordinator
    assert "persisted_start_temp = finite_float" in coordinator
    assert "result_base_ml = finite_float" in coordinator
    assert "return finite_float(value)" in weather
    assert "valid_rows: list[dict[str, Any]] = []" in weather
    assert "sanitize_runtime_session(room)" in storage
