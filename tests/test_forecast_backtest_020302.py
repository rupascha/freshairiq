from custom_components.freshairiq.forecast_backtest import backtest_summary


def _room(key, predicted, actual, *, horizon=15, confidence=80, timeline=None):
    error = actual - predicted
    return {
        "key": key,
        "name": key.title(),
        "comparable": True,
        "predicted_removed_ml": predicted,
        "actual_removed_ml": actual,
        "moisture_error_ml": error,
        "temperature_error_c": 0.1,
        "close_time_error_min": 1.0,
        "cost_error": 0.002,
        "direction_correct": (predicted >= 0) == (actual >= 0),
        "forecast_horizon_min": horizon,
        "forecast_confidence": confidence,
        "forecast_timeline": timeline or [],
    }


def _record(version, day, rooms):
    return {
        "valid": True,
        "model_version": version,
        "started_at": f"2026-09-{day:02d}T20:00:00+02:00",
        "ended_at": f"2026-09-{day:02d}T20:15:00+02:00",
        "room_results": rooms,
    }


def test_backtest_groups_real_historical_samples_by_horizon_and_confidence():
    records = [_record("0.20.3.4", 10, [
        _room("wohn", -100, -110, horizon=5, confidence=72),
        _room("bad", -200, -180, horizon=15, confidence=90),
    ])]
    result = backtest_summary(records, days=30)
    assert result["backtest_engine"] == "v2"
    assert result["mode"] == "historical_snapshot_replay"
    assert result["room_sample_count"] == 2
    assert [row["bucket"] for row in result["by_horizon"]] == ["0-5", "10-15"]
    assert [row["bucket"] for row in result["by_confidence"]] == ["60-74", "85-94"]
    assert result["overall"]["moisture_mae_ml"] == 15.0


def test_backtest_timeline_replay_shows_convergence():
    timeline = [
        {"kind": "start", "checkpoint_min": 0, "predicted_final_removed_ml": -100},
        {"kind": "live", "checkpoint_min": 5, "predicted_final_removed_ml": -118},
        {"kind": "live", "checkpoint_min": 10, "predicted_final_removed_ml": -121},
    ]
    result = backtest_summary([_record("0.20.3.4", 10, [_room("wohn", -100, -120, timeline=timeline)])])
    rows = {row["checkpoint"]: row for row in result["timeline_replay"]}
    assert rows["start"]["moisture_mae_ml"] == 20.0
    assert rows["+5"]["moisture_mae_ml"] == 2.0
    assert rows["+10"]["moisture_mae_ml"] == 1.0


def test_backtest_keeps_invalid_and_noncomparable_sessions_out_of_scores():
    records = [
        _record("0.20.3.4", 10, [_room("wohn", -100, -110)]),
        {
            "valid": False,
            "model_version": "0.20.3.4",
            "started_at": "2026-09-11T20:00:00+02:00",
            "ended_at": "2026-09-11T20:20:00+02:00",
            "room_results": [{"key": "bad", "comparable": False, "predicted_removed_ml": -500, "actual_removed_ml": 500}],
        },
    ]
    result = backtest_summary(records)
    assert result["record_count"] == 2
    assert result["valid_record_count"] == 1
    assert result["room_sample_count"] == 1
    assert result["overall"]["moisture_mae_ml"] == 10.0


def test_backtest_compares_versions_only_after_minimum_sample_count():
    records = []
    for day in (1, 2, 3):
        records.append(_record("0.20.3.1", day, [_room("wohn", -100, -130)]))
    for day in (4, 5, 6):
        records.append(_record("0.20.3.4", day, [_room("wohn", -100, -110)]))
    result = backtest_summary(records)
    comparison = result["version_comparison"]
    assert comparison is not None
    assert comparison["previous_version"] == "0.20.3.1"
    assert comparison["current_version"] == "0.20.3.4"
    assert comparison["delta_current_minus_previous"]["moisture_mae_ml"] == -20.0


def test_backtest_reports_largest_outliers_without_mutating_history():
    records = [_record("0.20.3.4", 10, [
        _room("a", -100, -105),
        _room("b", -100, -200),
    ])]
    before = repr(records)
    result = backtest_summary(records)
    assert result["largest_outliers"][0]["room_key"] == "b"
    assert result["largest_outliers"][0]["absolute_error_ml"] == 100.0
    assert repr(records) == before


def test_backtest_v2_reports_reliability_separately_from_evidence_depth():
    records = [_record("0.20.3.5", 10, [
        _room("wohn", -100, -110, confidence=90),
        _room("bad", -200, -180, confidence=80),
    ])]
    result = backtest_summary(records)
    reliability = result["reliability"]
    assert reliability["samples"] == 2
    assert reliability["magnitude_accuracy_percent"] is not None
    assert reliability["direction_accuracy_percent"] == 100.0
    assert reliability["evidence_maturity_percent"] == 10.0
    assert reliability["score_percent"] is not None
    assert "evidence-weighted" in reliability["score_formula"]
    assert result["rooms"][0]["reliability"]["samples"] >= 1
