"""R08 (0.26.7.2): forecast/learning quality – stratified, no invalid session as a zero-error success.

* The backtest keeps records of the earlier, target-capped replay (explicit ``validation_version`` < 3) out of today's
  room reliability, as ``validation_summary`` does (#28); a missing version is unknown and is kept (compacted records).
* Invalid records and non-comparable sessions never enter the error metrics, and a missing error stays ``None``.
* One session never changes the moisture forecast factor (shadow competition needs repeated superiority).
"""
from __future__ import annotations

from custom_components.freshairiq.forecast_backtest import backtest_summary
from custom_components.freshairiq.forecast_validation import VALIDATION_RECORD_VERSION, build_validation_record, validation_summary


def _room(key, predicted, actual, *, comparable=True):
    return {"key": key, "name": key, "comparable": comparable, "predicted_removed_ml": predicted, "actual_removed_ml": actual,
            "moisture_error_ml": (actual - predicted) if comparable else None, "temperature_error_c": None,
            "close_time_error_min": None, "cost_error": None, "direction_correct": True if comparable else None,
            "forecast_horizon_min": 15, "forecast_confidence": 80, "forecast_timeline": []}


def _record(day, rooms, **extra):
    return {"valid": True, "model_version": "0.26.7.2", "started_at": f"2026-11-{day:02d}T20:00:00+01:00",
            "ended_at": f"2026-11-{day:02d}T20:15:00+01:00", "room_results": rooms, **extra}


def test_backtest_keeps_the_previous_basis_apart_and_a_missing_version_is_unknown():
    records = [_record(1, [_room("bad", 100, 300)], validation_version=2),            # older, target-capped basis
               _record(2, [_room("bad", 100, 110)], validation_version=VALIDATION_RECORD_VERSION),
               _record(3, [_room("bad", 100, 90)])]                                     # compacted: version unknown
    out = backtest_summary(records, days=30)
    assert out["previous_basis_record_count"] == 1 and out["room_sample_count"] == 2
    room = out["rooms"][0]
    assert room["samples"] == 2 and room["moisture_mae_ml"] == 10.0                     # the 200 ml miss is not mixed in


def test_invalid_and_noncomparable_sessions_are_never_zero_error_successes():
    records = [_record(1, [_room("bad", 100, 0, comparable=False)]), {**_record(2, [_room("bad", 100, 100)]), "valid": False}]
    out = backtest_summary(records, days=30)
    assert out["room_sample_count"] == 0 and out["rooms"] == []
    summary = validation_summary([{**r, "validation_version": VALIDATION_RECORD_VERSION} for r in records], days=30)
    assert summary["moisture_mae_ml"] is None and summary["close_time_mae_min"] is None


def test_a_session_without_a_frozen_start_forecast_is_invalid_not_perfect():
    record = build_validation_record({"started_at": "2026-11-01T20:00:00", "ended_at": "2026-11-01T20:10:00"},
                                     [{"key": "bad", "prediction_comparable": False, "removed_ml": 0.0, "duration_min": 10.0}],
                                     model_version="0.26.7.2")
    assert record["valid"] is False and record["invalid_code"] == "no_frozen_start_forecast"
    assert record["moisture_abs_error_ml"] is None and record["close_time_mae_min"] is None
    assert record["room_results"][0]["moisture_abs_error_ml"] is None


def test_one_session_does_not_change_the_moisture_forecast_factor():
    from custom_components.freshairiq.intelligence import ensure_behaviour_defaults, learn_outcome_feedback
    room: dict = {}
    ensure_behaviour_defaults(room)
    room.update({"session_prediction_snapshot_valid": True, "session_predicted_removed_ml": 200.0})
    before = room.get("outcome_removed_factor", 1.0)
    assert learn_outcome_feedback(room, 400.0, -0.5) is True                            # processed as evidence …
    assert room.get("outcome_removed_factor", 1.0) == before                              # … but no universal correction from n=1
