"""Post-close persistence hardening and summary contracts."""
from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.post_stabilization import (
    prune_history, stabilization_summary, start_post_close_observation, update_post_close_observation,
)


def test_inactive_missing_timestamp_and_max_timeout_paths():
    now = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
    assert update_post_close_observation({}, now=now, absolute_humidity_g_m3=8, temperature_c=20, frame_quality="excellent", frame_valid=True, window_open=False, moisture_source_active=False) == (None, False)
    room = {"post_close_active": True, "post_close_started_at": "broken"}
    outcome, changed = update_post_close_observation(room, now=now, absolute_humidity_g_m3=8, temperature_c=20, frame_quality="excellent", frame_valid=True, window_open=False, moisture_source_active=False)
    assert changed and outcome["reason"] == "missing_start_timestamp"

    room = {}
    start_post_close_observation(room, event_id="e", room_key="r", room_name="Raum", now=now-timedelta(minutes=16), close_ah=8, close_temp_c=20, removed_ml=100, volume_m3=50, frame_quality="excellent")
    outcome, changed = update_post_close_observation(room, now=now, absolute_humidity_g_m3=None, temperature_c=None, frame_quality="poor", frame_valid=False, window_open=False, moisture_source_active=False)
    assert changed and outcome["reason"] == "insufficient_clean_samples"


def test_legacy_naive_timestamp_and_corrupt_numeric_persistence_do_not_crash():
    now = datetime(2026, 9, 14, 12, 10, tzinfo=timezone.utc)
    room = {
        "post_close_active": True,
        "post_close_started_at": "2026-09-14T12:00:00",  # legacy naive
        "post_close_ah": "broken", "post_close_temp_c": float("nan"),
        "post_close_volume_m3": float("inf"), "post_close_removed_ml": "bad",
        "post_close_start_frame_quality": "excellent", "post_close_samples": [{}, {}],
    }
    outcome, changed = update_post_close_observation(room, now=now, absolute_humidity_g_m3=float("nan"), temperature_c=float("inf"), frame_quality="excellent", frame_valid=True, window_open=False, moisture_source_active=False)
    assert changed and outcome is not None
    assert outcome["status"] == "complete"
    assert outcome["close_removed_ml"] == 0.0


def test_prune_history_deduplicates_old_and_invalid_rows():
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    history = [
        None,
        {"event_id":""},
        {"event_id":"old","completed_at":"2026-07-01T00:00:00+00:00"},
        {"event_id":"a","completed_at":"2026-09-13T00:00:00+00:00"},
        {"event_id":"a","completed_at":"2026-09-14T00:00:00+00:00"},
        {"event_id":"bad-date","completed_at":"broken"},
    ]
    result = prune_history(history, now, days=30)
    assert [x["event_id"] for x in result] == ["a", "bad-date"]


def test_stabilization_summary_tolerates_corrupt_values():
    summary = stabilization_summary([
        None,
        {"event_id":"a","key":"living","valid_for_analysis":True,"moisture_rebound_ml":float("nan"),"buffer_fraction_percent":"bad","interpretation":"moisture_rebound"},
        {"event_id":"b","key":"living","valid_for_analysis":False},
    ])
    assert summary["observations"] == 2
    assert summary["valid_observations"] == 1
    assert summary["average_rebound_ml"] == 0.0
    assert summary["average_buffer_fraction_percent"] == 0.0
    assert summary["rooms_with_valid_observations"] == 1
