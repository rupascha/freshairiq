from datetime import datetime, timedelta, timezone
from pathlib import Path

from custom_components.freshairiq.measurement_frame import report_timestamp_after_boundary
from custom_components.freshairiq.ventilation_result import finalise_ventilation_group, new_ventilation_group
from custom_components.freshairiq.house_strategy import learn_house_outcome

ROOT = Path(__file__).resolve().parents[1]
COORDINATOR = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
STORAGE = (ROOT / "custom_components/freshairiq/storage.py").read_text(encoding="utf-8")


def _event(start, end, *, key="living", removed=100.0, valid=True):
    return {
        "event_id": f"{key}:{start.isoformat()}:{end.isoformat()}",
        "key": key,
        "name": key,
        "floor": "ground_floor",
        "sort_order": 0,
        "volume_m3": 50.0,
        "started_at": start.isoformat(),
        "ended_at": end.isoformat(),
        "removed_ml": removed if valid else None,
        "raw_removed_ml": removed,
        "moisture_measurement_valid": valid,
        "duration_min": 10.0,
        "temp_delta_c": -0.5,
        "energy_kwh": 0.2,
        "cost": 0.1,
        "cross_ventilation": False,
        "learning_valid": valid,
        "prediction_comparable": valid,
        "prediction_time_aligned": valid,
        "predicted_removed_ml": 90.0,
    }


def test_report_after_physical_close_detects_feedback_inside_debounce_window():
    close = datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc)
    assert report_timestamp_after_boundary(close + timedelta(seconds=1), close) is True
    assert report_timestamp_after_boundary((close + timedelta(seconds=2)).isoformat(), close.isoformat()) is True
    assert report_timestamp_after_boundary(close, close) is False
    assert report_timestamp_after_boundary(close - timedelta(seconds=1), close) is False
    assert report_timestamp_after_boundary("bad", close) is False
    assert report_timestamp_after_boundary(None, close) is False
    assert report_timestamp_after_boundary(close.replace(tzinfo=None), close) is False


def test_untrusted_moisture_is_unknown_not_zero_in_result():
    start = datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    group = new_ventilation_group(start)
    group["sessions"] = [_event(start, end, valid=False)]
    result = finalise_ventilation_group(group, end)
    assert result is not None
    assert result["removed_ml"] is None
    assert result["measured_removed_ml_partial"] is None
    assert result["moisture_result_complete"] is False
    assert result["moisture_measured_sessions"] == 0
    assert result["moisture_unmeasured_sessions"] == 1
    assert result["room_results"][0]["removed_ml"] is None


def test_partial_house_measurement_is_not_presented_as_complete_total():
    start = datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    group = new_ventilation_group(start)
    group["sessions"] = [
        _event(start, end, key="living", removed=120.0, valid=True),
        _event(start, end, key="bath", removed=80.0, valid=False),
    ]
    result = finalise_ventilation_group(group, end)
    assert result is not None
    assert result["removed_ml"] is None
    assert result["measured_removed_ml_partial"] == 120
    assert result["moisture_result_complete"] is False
    assert result["moisture_measured_sessions"] == 1
    assert result["moisture_unmeasured_sessions"] == 1


def test_frontend_prioritises_finalisation_when_only_pending_rooms_remain():
    assert "const activelyVentilating = active.filter(r => !r.session_finalization_pending);" in CARD
    assert "if (finalizing.active && !activelyVentilating.length)" in CARD
    assert "if (!active.length && finalizing.active)" not in CARD


def test_learning_now_indicator_uses_strict_timestamp_gate():
    assert "r.session_measurement_quality?.timestamp_gate_passed === true" in CARD
    assert "active.filter(r => r.measurement_frame_learning_eligible)" not in CARD


def test_physical_close_boundary_is_frozen_before_three_second_confirmation():
    assert "physical_close_candidate = now - timedelta(seconds=max(closed_for, 0.0))" in COORDINATOR
    assert 'if not mem.get("session_close_detected_at"):' in COORDINATOR
    assert "raw_contact_open = bool(is_open)" in COORDINATOR
    assert "contacts_known and raw_contact_open" in COORDINATOR
    assert "report_timestamp_after_boundary(current_temp, close_boundary)" in COORDINATOR
    assert "report_timestamp_after_boundary(current_humidity, close_boundary)" in COORDINATOR


def test_fractional_learning_evidence_is_accumulated_instead_of_full_sample():
    assert 'mem.get("learning_sample_credit", 0.0)' in COORDINATOR
    assert "sample_increment = int(evidence_total)" in COORDINATOR
    assert 'mem["learning_sample_credit"] = 0.0 if samples >= 1000 else round(evidence_total - sample_increment, 6)' in COORDINATOR
    assert '"learning_sample_credit": 0.0' in STORAGE
    assert 'room["learning_sample_credit"] = 0.0 if sample_credit is None else min(max(sample_credit, 0.0), 0.999999)' in STORAGE


def test_reset_preserves_opening_report_timestamps_for_active_session():
    assert '"session_open_temperature_reported_at", "session_open_humidity_reported_at"' in STORAGE


def test_untrusted_session_does_not_seed_post_close_learning_or_statistics_moisture():
    assert "moisture_valid=session_activity_eligible" in COORDINATOR
    assert "if session_activity_eligible:\n            start_post_close_observation(" in COORDINATOR
    assert '"removed_ml": session_removed if session_activity_eligible else None' in COORDINATOR
    assert '"raw_removed_ml": round(session_removed, 1)' in COORDINATOR


def test_house_strategy_does_not_learn_a_synthetic_zero_from_untrusted_moisture():
    start = datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    store = {}
    event = _event(start, end, valid=False)
    changed = learn_house_outcome(
        store, [event], {"living": {"floor": "ground_floor", "name": "Wohnzimmer"}},
        cross=False, expected_occupants=2, observed_at=end,
    )
    assert changed is False
    assert store["house_strategy_samples"] == 0
