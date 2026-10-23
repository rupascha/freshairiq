"""0.26.5.3 (community: recorder load): pure helpers that keep published states quiet."""
from __future__ import annotations

from custom_components.freshairiq.dashboard_transport import (
    SOURCE_DETAIL_KEYS, VOLATILE_ROOM_KEYS, hold_source_details, stable_room_payload,
)
from custom_components.freshairiq.publish_filter import quantized, with_deadband

STAMPS = {
    "frame_temp_reported_at": "2026-10-23T10:00:05+00:00", "frame_humidity_reported_at": "2026-10-23T10:01:10+00:00",
    "frame_reference_temp_reported_at": "2026-10-23T09:55:00+00:00", "frame_reference_humidity_reported_at": "2026-10-23T09:58:00+00:00",
}


def _room(**extra):
    room = {"key": "bad", "humidity": 60, "last_measurement_at": "2026-10-23T10:02:30+00:00", **dict.fromkeys(VOLATILE_ROOM_KEYS, 12.3), **STAMPS,
            "temperature_history_14d": [1, 2], "humidity_history_14d": [3]}
    room.update(extra)
    return room


def test_the_published_room_payload_has_report_times_instead_of_counters():
    payload = stable_room_payload(_room())
    assert not set(VOLATILE_ROOM_KEYS) & set(payload)
    assert payload["last_measurement_at"] == "2026-10-23T10:01:10+00:00"  # newest own reading, not the evaluation time
    assert payload["measurement_frame_oldest_at"] == "2026-10-23T09:55:00+00:00"
    assert payload["history_on_demand"] is True and "temperature_history_14d" not in payload
    # two cycles with the same readings publish the same payload, whatever the clock says
    assert stable_room_payload(_room(frame_age_temp_s=99.9, last_measurement_at="2026-10-23T10:03:00+00:00")) == payload


def test_missing_report_times():
    payload = stable_room_payload(_room(frame_temp_reported_at=None, frame_humidity_reported_at=None))
    assert payload["last_measurement_at"] is None and payload["measurement_frame_oldest_at"] is None
    partial = stable_room_payload(_room(frame_reference_humidity_reported_at=None))
    assert partial["measurement_frame_oldest_at"] is None and partial["last_measurement_at"] == "2026-10-23T10:01:10+00:00"
    no_measurement = stable_room_payload({"key": "x", "frame_age_temp_s": 3})
    assert no_measurement == {"key": "x", "measurement_frame_oldest_at": None}
    assert stable_room_payload(None) is None and stable_room_payload("x") == "x"


def test_detector_values_are_held_outside_an_active_source():
    quiet = {"key": "bad", "moisture_source_active": False, "moisture_source_rate_ml_min": 0.7, "moisture_source_ah_rise_g_m3": 0.1}
    payload, held = hold_source_details(quiet, None)
    assert held is None and all(payload[key] is None for key in SOURCE_DETAIL_KEYS)
    active = {**quiet, "moisture_source_active": True, "moisture_source_rate_ml_min": 22.0, "moisture_source_generated_ml_window": 90}
    payload, held = hold_source_details(active, held)
    assert payload is active and held["moisture_source_rate_ml_min"] == 22.0 and held["moisture_source_ah_rise_g_m3"] == 0.1
    payload, held_after = hold_source_details({**quiet, "moisture_source_rate_ml_min": 0.3}, held)
    assert held_after is held and payload["moisture_source_rate_ml_min"] == 22.0 and payload["moisture_source_generated_ml_window"] == 90
    recovery = {**quiet, "moisture_source_recovery": True, "moisture_source_rate_ml_min": 5.0}
    assert hold_source_details(recovery, held)[0]["moisture_source_rate_ml_min"] == 5.0
    assert hold_source_details(None, held) == (None, held)


def test_quantized_and_deadband():
    assert [quantized(v, 50) for v in (333, 324.9, -26, 0, "x", None, True)] == [350, 300, -50, 0, "x", None, True]
    assert quantized(12.34, 0.5) == 12.5 and quantized(float("nan"), 10) != quantized(float("nan"), 10)
    assert [with_deadband(-0.3, v, 0.2) for v in (-0.4, -0.2, -0.5, -0.1, 0, None, "x")] == [-0.3, -0.3, -0.5, -0.1, 0, None, "x"]
    assert with_deadband(None, -0.3, 0.2) == -0.3 and with_deadband(0, -0.1, 0.2) == -0.1
    assert with_deadband(-0.3, float("inf"), 0.2) == float("inf")
