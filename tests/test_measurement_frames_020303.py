from datetime import datetime, timedelta, timezone
from pathlib import Path

from custom_components.freshairiq.measurement_frame import build_measurement_frame


class FakeState:
    def __init__(self, stamp):
        self.last_reported = stamp
        self.last_updated = stamp


def _state(now, age_s):
    return FakeState(now - timedelta(seconds=age_s))


def test_measurement_frame_excellent_and_learning_eligible():
    now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now, 10),
        humidity_state=_state(now, 20),
        reference_temperature_state=_state(now, 5),
        reference_humidity_state=_state(now, 12),
    )
    assert frame["quality"] == "excellent"
    assert frame["skew_s"] == 10.0
    assert frame["full_skew_s"] == 15.0
    assert frame["learning_eligible"] is True
    assert frame["validation_eligible"] is True


def test_measurement_frame_acceptable_up_to_90_seconds_skew():
    now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now, 15),
        humidity_state=_state(now, 80),
        reference_temperature_state=_state(now, 10),
        reference_humidity_state=_state(now, 35),
    )
    assert frame["quality"] == "acceptable"
    assert frame["skew_s"] == 65.0
    assert frame["full_skew_s"] == 70.0
    assert frame["learning_eligible"] is True


def test_measurement_frame_uncertain_is_not_used_for_learning_or_validation():
    now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now, 10),
        humidity_state=_state(now, 130),
        reference_temperature_state=_state(now, 20),
        reference_humidity_state=_state(now, 40),
    )
    assert frame["quality"] == "uncertain"
    assert frame["learning_eligible"] is False
    assert frame["validation_eligible"] is False


def test_measurement_frame_held_is_learning_only_and_truly_stale_is_rejected():
    now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now, 10),
        humidity_state=_state(now, 350),
        reference_temperature_state=_state(now, 20),
        reference_humidity_state=_state(now, 40),
    )
    assert frame["quality"] == "held"
    assert frame["learning_eligible"] is True
    assert frame["validation_eligible"] is False

    stale = build_measurement_frame(
        now,
        temperature_state=_state(now, 10),
        humidity_state=_state(now, 2600),
        reference_temperature_state=_state(now, 20),
        reference_humidity_state=_state(now, 40),
    )
    assert stale["quality"] == "stale"
    assert stale["learning_eligible"] is False

    root = Path(__file__).resolve().parents[1]
    coordinator = (root / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    diagnostics = (root / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert 'frame_learning_eligible = session_activity_eligible' in coordinator
    # 0.25.0.43: legacy frame classes remain diagnostic context; actual
    # in-session report timestamps are now the mandatory learning/validation gate.
    assert 'snapshot_frame_valid = bool(session_activity_eligible)' in coordinator
    assert 'start_learning_valid = session_activity_eligible' in coordinator
    assert 'DIAGNOSTICS_SCHEMA_VERSION = 10' in diagnostics


def test_slow_weather_reference_cadence_does_not_poison_room_learning():
    now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
    weather = _state(now, 600)
    frame = build_measurement_frame(
        now,
        temperature_state=_state(now, 12),
        humidity_state=_state(now, 20),
        reference_temperature_state=weather,
        reference_humidity_state=weather,
    )
    assert frame["quality"] == "excellent"
    assert frame["learning_eligible"] is True
    assert frame["full_skew_s"] == 588.0
    assert frame["reference_skew_s"] == 0.0
