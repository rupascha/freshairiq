"""Regression and evidence contracts for Learning Effectiveness Validation v1."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import custom_components.freshairiq.learning_effectiveness as le
from custom_components.freshairiq.forecast_validation import (
    build_validation_record,
    evaluate_start_forecast_at_duration,
    freeze_start_forecast_context,
)

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _start_context(*, rate: float = 0.047, source_residual: float | None = 0.25, thermal: float | None = 0.01, samples: int = 6):
    args = {
        "current_ah": 13.0,
        "source_ah": 8.0,
        "current_temp_c": 22.0,
        "source_temp_c": 12.0,
        "volume_m3": 50.0,
        "rate_per_min": rate,
        "airflow_bonus": 1.0,
        "prior_source_ml_min": 0.5,
        "learned_source_ml_min": source_residual,
        "learned_thermal_residual_c_min": thermal,
        "observation_samples": samples,
        "model_maturity_pct": 80.0,
        "future_source_boundaries": {
            5: {"absolute_humidity": 8.0, "temperature_c": 12.0, "confidence": 90},
            10: {"absolute_humidity": 8.2, "temperature_c": 12.4, "confidence": 88},
        },
    }
    options = {
        "min_return_next_5_min_ml": 25.0,
        "max_temp_loss_next_5_min_c": 0.6,
        "min_efficiency_ml_per_01c": 8.0,
        "min_duration_min": 3.0,
        "max_duration_min": 20.0,
        "operating_profile": "comfort",
        "heating_system": "gas",
        "electricity_price_per_kwh": 0.30,
        "heat_pump_cop": 3.5,
        "gas_price_per_kwh": 0.11,
        "gas_efficiency": 0.92,
        "district_price_per_kwh": 0.15,
        "district_efficiency": 0.98,
        "oil_price_per_liter": 1.0,
        "oil_kwh_per_liter": 10.0,
        "oil_efficiency": 0.88,
    }
    return freeze_start_forecast_context(
        args,
        target_ah=10.5,
        options=options,
        start_ah=13.0,
        start_source_ah=8.0,
        start_temp_c=22.0,
        start_source_temp_c=12.0,
    )


def _frozen_start(**kwargs):
    context = _start_context(**kwargs)
    room = {
        "learning_samples": 17,
        "outcome_feedback_samples": 11,
        "shadow_learning_promotions": 1,
    }
    context["learning_effectiveness"] = le.freeze_learning_effectiveness_context(context, room)
    return context


def _sample(*, gain: float, ended_at: str, record_id: str, room: str = "bad") -> dict:
    baseline_error = 100.0
    production_error = baseline_error - gain
    winner = "learned" if gain > 1 else "baseline" if gain < -1 else "tie"
    return {
        "valid": True,
        "ended_at": ended_at,
        "production_abs_error_ml": production_error,
        "baseline_abs_error_ml": baseline_error,
        "paired_error_gain_ml": gain,
        "winner": winner,
        "production_direction_correct": gain >= 0,
        "baseline_direction_correct": True,
        "validation_record_id": record_id,
        "room_key": room,
        "room_name": room,
        "horizon_bucket": "5-10",
        "season": "autumn",
        "source_temperature_bucket": "10-20",
        "ah_gradient_bucket": "2-4",
        "learning_stage_id": "physics:10-19|forecast:6-9",
    }


def _record(day: int, gains: list[float], *, model_version: str = "0.25.0.65") -> dict:
    ended = datetime(2026, 9, 1, 18, 0) + timedelta(days=day)
    rooms = []
    for index, gain in enumerate(gains):
        baseline_error = 100.0
        production_error = baseline_error - gain
        rooms.append({
            "key": f"r{index}",
            "name": f"Raum {index}",
            "comparable": True,
            "learning_effectiveness": {
                "valid": True,
                "ended_at": ended.isoformat(),
                "production_abs_error_ml": production_error,
                "baseline_abs_error_ml": baseline_error,
                "paired_error_gain_ml": gain,
                "winner": "learned" if gain > 1 else "baseline" if gain < -1 else "tie",
                "production_direction_correct": True,
                "baseline_direction_correct": True,
                "horizon_bucket": "0-5" if index % 2 == 0 else "15-30",
                "season": "autumn",
                "source_temperature_bucket": "10-20",
                "ah_gradient_bucket": "2-4",
                "learning_stage_id": "physics:10-19|forecast:6-9",
            },
        })
    return {
        "valid": True,
        "started_at": (ended - timedelta(minutes=10)).isoformat(),
        "ended_at": ended.isoformat(),
        "model_version": model_version,
        "room_results": rooms,
    }


def test_numeric_and_bucket_helpers_cover_defensive_edges():
    assert le._number(None) is None
    assert le._number("x") is None
    assert le._number(float("inf")) is None
    assert le._number("2.5") == 2.5
    assert le._safe_int("x", 7) == 7
    assert le._safe_int(-4) == 0
    assert [le._bucket_count(v) for v in (0, 1, 3, 6, 10, 20, 40)] == ["0", "1-2", "3-5", "6-9", "10-19", "20-39", "40+"]
    assert [le._horizon_bucket(v) for v in (None, 5, 10, 15, 30, 31)] == ["unknown", "0-5", "5-10", "10-15", "15-30", "30+"]
    assert [le._source_temperature_bucket(v) for v in (None, -1, 0, 10, 20, 30)] == ["unknown", "<0", "0-10", "10-20", "20-30", "30+"]
    assert le._gradient_bucket(None, 1) == "unknown"
    assert [le._gradient_bucket(v, 10) for v in (10, 10.5, 11.5, 13, 15)] == ["<=0", "0-1", "1-2", "2-4", "4+"]
    assert le._season("bad") == "unknown"
    assert [le._season(f"2026-{month:02d}-15T12:00:00+02:00") for month in (3, 6, 9, 12)] == ["spring", "summer", "autumn", "winter"]
    assert le._same_direction(1, 1)
    assert not le._same_direction(0, 10)
    assert not le._same_direction(-10, 10)
    assert le._same_direction(-10, -20)
    assert len(le._snapshot_id({"x": 1})) == 16


def test_model_snapshot_only_hashes_forecast_relevant_learning_state():
    args = _start_context()["forecast_args"]
    room = {"learning_samples": 17, "outcome_feedback_samples": 12, "shadow_learning_promotions": 2}
    snapshot = le.build_model_snapshot(room, args)
    assert snapshot["learning_stage_id"] == "physics:10-19|forecast:6-9"
    assert "feedback:10-19" in snapshot["context_learning_stage_id"]
    assert snapshot["shadow_promotions"] == 2
    first_id = snapshot["model_snapshot_id"]

    # Shadow/outcome counters currently do not affect horizon_forecast and must
    # therefore not create a fake forecast-model generation.
    changed_context = le.build_model_snapshot({**room, "outcome_feedback_samples": 99, "shadow_learning_promotions": 8}, args)
    assert changed_context["model_snapshot_id"] == first_id
    changed_forecast = le.build_model_snapshot(room, {**args, "rate_per_min": 0.051})
    assert changed_forecast["model_snapshot_id"] != first_id

    defaults = le.build_model_snapshot({}, {"rate_per_min": "bad", "learned_source_ml_min": "bad", "learned_thermal_residual_c_min": None, "observation_samples": 99})
    assert defaults["rate_per_min"] == 0.03
    assert defaults["learned_source_ml_min"] is None
    assert defaults["observation_samples"] == 6


def test_freeze_baseline_changes_only_adaptive_forecast_terms_and_is_immutable():
    original = _start_context()
    original_copy = deepcopy(original)
    assert le.freeze_learning_effectiveness_context("bad", {}) is None
    assert le.freeze_learning_effectiveness_context({}, {}) is None

    frozen = le.freeze_learning_effectiveness_context(original, {"learning_samples": 8})
    assert frozen is not None
    baseline = frozen["baseline_context"]
    assert original == original_copy
    assert baseline is not original
    assert baseline["forecast_args"]["rate_per_min"] == 0.03
    assert baseline["forecast_args"]["learned_source_ml_min"] is None
    assert baseline["forecast_args"]["learned_thermal_residual_c_min"] is None
    assert baseline["forecast_args"]["observation_samples"] == 0
    assert baseline["forecast_args"]["current_ah"] == original["forecast_args"]["current_ah"]
    assert baseline["forecast_args"]["future_source_boundaries"] == original["forecast_args"]["future_source_boundaries"]
    assert baseline["controls"] == original["controls"]

    # Defensive branch: an exotic Mapping-like payload can expose production
    # args but deepcopy into a context without forecast args.
    class OddDict(dict):
        def __deepcopy__(self, memo):
            return {}
    odd = OddDict(forecast_args={"rate_per_min": 0.04})
    assert le.freeze_learning_effectiveness_context(odd, {}) is None


def test_baseline_context_lookup_defends_schema_and_returns_copy():
    assert le.baseline_context_from_start(None) is None
    assert le.baseline_context_from_start({}) is None
    assert le.baseline_context_from_start({"learning_effectiveness": {"schema_version": "bad"}}) is None
    assert le.baseline_context_from_start({"learning_effectiveness": {"schema_version": 99}}) is None
    assert le.baseline_context_from_start({"learning_effectiveness": {"schema_version": 1, "baseline_context": "bad"}}) is None
    context = _frozen_start()
    baseline = le.baseline_context_from_start(context)
    assert baseline is not None
    baseline["forecast_args"]["current_ah"] = 99
    assert context["learning_effectiveness"]["baseline_context"]["forecast_args"]["current_ah"] == 13.0


def test_same_session_baseline_replays_same_physical_event_and_differs_from_learned_model():
    context = _frozen_start()
    production = evaluate_start_forecast_at_duration(context, 10)
    baseline = evaluate_start_forecast_at_duration(le.baseline_context_from_start(context), 10)
    assert production and baseline
    assert production["duration_min"] == baseline["duration_min"] == 10.0
    assert production["predicted_removed_ml"] != baseline["predicted_removed_ml"]
    assert context["forecast_args"]["rate_per_min"] == 0.047


def test_build_effectiveness_sample_validates_input_and_scores_all_winners():
    context = _frozen_start()
    prod = {"predicted_removed_ml": 90}
    base = {"predicted_removed_ml": 70}
    assert le.build_effectiveness_sample(None, duration_min=10, production_prediction=prod, baseline_prediction=base, actual_removed_ml=100, ended_at="x") is None
    assert le.build_effectiveness_sample({}, duration_min=10, production_prediction=prod, baseline_prediction=base, actual_removed_ml=100, ended_at="x") is None
    bad_schema = deepcopy(context)
    bad_schema["learning_effectiveness"]["schema_version"] = 2
    assert le.build_effectiveness_sample(bad_schema, duration_min=10, production_prediction=prod, baseline_prediction=base, actual_removed_ml=100, ended_at="x") is None
    assert le.build_effectiveness_sample(context, duration_min=10, production_prediction=None, baseline_prediction=base, actual_removed_ml=100, ended_at="x") is None
    assert le.build_effectiveness_sample(context, duration_min="bad", production_prediction=prod, baseline_prediction=base, actual_removed_ml=100, ended_at="x") is None

    learned = le.build_effectiveness_sample(context, duration_min=10, production_prediction=prod, baseline_prediction=base, actual_removed_ml=100, ended_at="2026-09-23T12:00:00+02:00")
    assert learned["winner"] == "learned"
    assert learned["paired_error_gain_ml"] == 20.0
    assert learned["horizon_bucket"] == "5-10"
    assert learned["season"] == "autumn"
    assert learned["source_temperature_bucket"] == "10-20"
    assert learned["ah_gradient_bucket"] == "4+"
    assert learned["uses_future_weather"] is True
    assert learned["model_snapshot_id"]

    baseline_wins = le.build_effectiveness_sample(context, duration_min=8, production_prediction={"predicted_removed_ml": 60}, baseline_prediction={"predicted_removed_ml": 95}, actual_removed_ml=100, ended_at="bad")
    assert baseline_wins["winner"] == "baseline"
    tied = le.build_effectiveness_sample(context, duration_min=8, production_prediction={"predicted_removed_ml": 90}, baseline_prediction={"predicted_removed_ml": 89.5}, actual_removed_ml=100, ended_at="2026-01-01")
    assert tied["winner"] == "tie"


def test_paired_summary_collecting_improving_regressing_and_inconclusive():
    collecting = le._paired_summary([])
    assert collecting["status"] == "collecting"
    assert collecting["production_mae_ml"] is None
    assert collecting["independent_sessions"] == 0

    improving = []
    regressing = []
    inconclusive = []
    for i in range(12):
        date = f"2026-09-{1 + i:02d}T12:00:00+02:00"
        improving.append(_sample(gain=20 + (i % 2), ended_at=date, record_id=f"e{i}"))
        regressing.append(_sample(gain=-20 - (i % 2), ended_at=date, record_id=f"r{i}"))
        inconclusive.append(_sample(gain=10 if i % 2 == 0 else -10, ended_at=date, record_id=f"i{i}"))
    assert le._paired_summary(improving)["status"] == "improving"
    assert le._paired_summary(improving)["improvement_claim_supported"] is True
    assert le._paired_summary(regressing)["status"] == "regressing"
    assert le._paired_summary(inconclusive)["status"] == "inconclusive"

    # Two rooms in one ventilation count as two paired room samples but only
    # one independent session for confidence/evidence.
    clustered = [
        _sample(gain=20, ended_at="2026-09-01T12:00:00", record_id="same", room="a"),
        _sample(gain=30, ended_at="2026-09-01T12:00:00", record_id="same", room="b"),
    ]
    summary = le._paired_summary(clustered)
    assert summary["samples"] == 2
    assert summary["independent_sessions"] == 1
    assert summary["paired_gain_ci95_low_ml"] is None


def test_scope_extract_grouping_and_record_identity_are_defensive():
    records = [
        "bad",
        {"valid": True, "ended_at": "bad", "room_results": []},
        {"valid": False, "ended_at": "2026-09-01", "room_results": []},
        _record(0, [20]),
        _record(40, [20]),
    ]
    scoped = le._scope_records(records, 30)
    assert len(scoped) == 1
    assert scoped[0]["ended_at"].startswith("2026-10")
    assert le._scope_records(["bad", {"ended_at": "bad"}], 0) == []

    malformed = {
        "valid": True,
        "started_at": "2026-09-01",
        "ended_at": "2026-09-01T12:00:00",
        "room_results": [
            "bad",
            {"key": "a", "comparable": False},
            {"key": "b", "comparable": True, "learning_effectiveness": "bad"},
            {"key": "c", "comparable": True, "learning_effectiveness": {"valid": False}},
            {"key": "d", "comparable": True, "learning_effectiveness": {"valid": True, "production_abs_error_ml": "bad", "baseline_abs_error_ml": 1}},
        ],
    }
    assert le._extract_samples(["bad", {"valid": False}, malformed]) == []
    extracted = le._extract_samples([_record(0, [20, -5])])
    assert len(extracted) == 2
    assert extracted[0]["validation_record_id"] == extracted[1]["validation_record_id"]
    assert extracted[0]["model_version"] == "0.25.0.65"
    assert le._record_id({"started_at": "x", "ended_at": "y"}, 1) != le._record_id({"started_at": "x", "ended_at": "y"}, 2)
    grouped = le._grouped(extracted, lambda x: x["horizon_bucket"])
    assert {row["bucket"] for row in grouped} == {"0-5", "15-30"}


def test_effectiveness_summary_reports_breakdowns_clustered_evidence_and_progression():
    # 14 independent ventilation records, two rooms each. Learned model is
    # consistently better and should satisfy the conservative evidence gate.
    records = [_record(i, [20 + (i % 3), 15 + (i % 2)]) for i in range(14)]
    summary = le.learning_effectiveness_summary(records, days=30)
    assert summary["effectiveness_engine"] == "v1"
    assert summary["mode"] == "paired_same_session_baseline"
    assert summary["observational_only"] is True
    assert summary["samples"] == 28
    assert summary["independent_sessions"] == 14
    assert summary["distinct_days"] == 14
    assert summary["status"] == "improving"
    assert summary["improvement_claim_supported"] is True
    assert summary["tracking_started_at"]
    assert summary["latest_sample_at"]
    assert len(summary["by_room"]) == 2
    assert [x["bucket"] for x in summary["by_horizon"]] == ["0-5", "15-30"]
    assert summary["by_season"][0]["bucket"] == "autumn"
    assert summary["by_source_temperature"][0]["bucket"] == "10-20"
    assert summary["by_ah_gradient"][0]["bucket"] == "2-4"
    assert summary["by_learning_stage"][0]["learning_stage_id"].startswith("physics:")
    assert summary["progression"] is not None
    assert summary["progression"]["observational_only"] is True
    assert summary["evidence_rules"]["minimum_independent_sessions"] == 8
    assert any("Shadow" in text for text in summary["limitations"])

    empty = le.learning_effectiveness_summary([], days=0)
    assert empty["samples"] == 0
    assert empty["tracking_started_at"] is None
    assert empty["progression"] is None


def test_progression_waits_for_twelve_independent_sessions():
    samples = [_sample(gain=10, ended_at=f"2026-09-{i+1:02d}", record_id=f"x{i}") for i in range(11)]
    assert le._progression(samples) is None
    samples.append(_sample(gain=10, ended_at="2026-09-12", record_id="x11"))
    assert le._progression(samples) is not None


def test_validation_record_persists_effectiveness_only_as_observational_evidence():
    effectiveness = {
        "valid": True,
        "production_abs_error_ml": 10.0,
        "baseline_abs_error_ml": 30.0,
        "paired_error_gain_ml": 20.0,
    }
    session = {
        "event_id": "evt",
        "key": "bad",
        "name": "Bad",
        "prediction_comparable": True,
        "predicted_removed_ml": 90.0,
        "removed_ml": 100.0,
        "validation_removed_ml": 100.0,
        "predicted_temperature_change_c": -0.4,
        "temp_delta_c": -0.3,
        "prediction_horizon_min": 10,
        "duration_min": 10,
        "prediction_confidence": 80,
        "learning_effectiveness": effectiveness,
    }
    record = build_validation_record(
        {"started_at": "2026-09-23T10:00:00+02:00", "ended_at": "2026-09-23T10:10:00+02:00", "removed_ml": 100, "duration_min": 10},
        [session],
        model_version="0.25.0.65",
    )
    assert record["room_results"][0]["learning_effectiveness"] == effectiveness
    effectiveness["paired_error_gain_ml"] = -999
    assert record["room_results"][0]["learning_effectiveness"]["paired_error_gain_ml"] == 20.0


def test_feature_is_observational_and_wired_to_diagnostics_sensor_and_ui():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    diagnostics = (COMP / "diagnostics.py").read_text(encoding="utf-8")
    sensor = (COMP / "sensor.py").read_text(encoding="utf-8")
    frontend = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    module = (COMP / "learning_effectiveness.py").read_text(encoding="utf-8")
    assert "freeze_learning_effectiveness_context(" in coordinator
    assert 'history=self.store.data.get("forecast_validation_history") or []' in coordinator
    assert "previous_model_context_from_start(start_context)" in coordinator
    assert "learning_effectiveness_summary(" in coordinator
    assert '"learning_effectiveness": learning_effectiveness_sample' in coordinator
    assert '"learning_effectiveness": _json_safe(data.get("learning_effectiveness") or {})' in diagnostics
    assert '"learning_effectiveness": self.coordinator.data.get("learning_effectiveness", {})' in sensor
    assert "Lernwirkung vs. Grundmodell" in frontend
    assert "Aktuell vs. vorherige Generation" in frontend
    assert "process_shadow_feedback" not in module
    assert 'room["outcome_removed_factor"] =' not in module


def _generation_sample(*, gain: float, ended_at: str, record_id: str, room: str = "bad") -> dict:
    sample = _sample(gain=5.0, ended_at=ended_at, record_id=record_id, room=room)
    previous_error = 100.0
    current_error = previous_error - gain
    sample.update({
        "generation_valid": True,
        "production_abs_error_ml": current_error,
        "previous_model_abs_error_ml": previous_error,
        "generation_error_gain_ml": gain,
        "generation_winner": "current" if gain > 1 else "previous" if gain < -1 else "tie",
        "previous_model_direction_correct": True,
        "model_snapshot_id": f"current-{record_id}",
        "previous_model_snapshot_id": f"previous-{record_id}",
    })
    return sample


def test_previous_generation_snapshot_lookup_and_replay_context_are_defensive():
    current = le.build_model_snapshot(
        {"learning_samples": 8, "outcome_feedback_samples": 4, "shadow_learning_promotions": 0},
        _start_context(rate=0.047)["forecast_args"],
    )
    previous = {
        "rate_per_min": 0.041,
        "learned_source_ml_min": None,
        "learned_thermal_residual_c_min": 0.005,
        "observation_samples": 4,
        "learning_samples": 7,
        "outcome_feedback_samples": 3,
        "shadow_promotions": 0,
        "model_snapshot_id": "previous-model",
        "learning_stage_id": "physics:6-9|forecast:3-5",
        "context_learning_stage_id": "physics:6-9|forecast:3-5|feedback:3-5|shadow:0",
    }
    history = [
        "bad",
        {"room_results": ["bad", {"key": "other"}, {"key": "bad", "learning_effectiveness": "bad"}]},
        {"room_results": [{"key": "bad", "learning_effectiveness": {"valid": False}}]},
        {"room_results": [{"key": "bad", "learning_effectiveness": {"valid": True, "model_snapshot": "bad"}}]},
        {"room_results": [{"key": "bad", "learning_effectiveness": {"valid": True, "model_snapshot": previous}}]},
        {"room_results": [{"key": "bad", "learning_effectiveness": {"valid": True, "model_snapshot": current}}]},
    ]
    assert le.previous_model_snapshot_from_history(None, "bad", current["model_snapshot_id"]) is None
    assert le.previous_model_snapshot_from_history(history, None, current["model_snapshot_id"]) is None
    assert le.previous_model_snapshot_from_history(history, "bad", None) is None
    assert le.previous_model_snapshot_from_history(["bad"], "bad", current["model_snapshot_id"]) is None
    assert le.previous_model_snapshot_from_history([{"room_results": ["bad", {"key": "other"}]}], "bad", current["model_snapshot_id"]) is None
    assert le.previous_model_snapshot_from_history([{"room_results": [{"key": "bad", "learning_effectiveness": "bad"}]}], "bad", current["model_snapshot_id"]) is None
    assert le.previous_model_snapshot_from_history([{"room_results": [{"key": "bad", "learning_effectiveness": {"valid": True, "model_snapshot": "bad"}}]}], "bad", current["model_snapshot_id"]) is None
    assert le.previous_model_snapshot_from_history([{"room_results": [{"key": "bad", "learning_effectiveness": {"valid": True, "model_snapshot": current}}]}], "bad", current["model_snapshot_id"]) is None
    found = le.previous_model_snapshot_from_history(history, "bad", current["model_snapshot_id"])
    assert found == previous and found is not previous

    start = _start_context(rate=0.047)
    assert le._context_with_model_snapshot(None, previous) is None
    assert le._context_with_model_snapshot(start, None) is None
    assert le._context_with_model_snapshot({}, previous) is None
    assert le._context_with_model_snapshot(start, {"rate_per_min": 0.04}) is None
    assert le._context_with_model_snapshot(start, {"rate_per_min": "bad", "observation_samples": 2}) is None
    replay = le._context_with_model_snapshot(start, previous)
    assert replay["forecast_args"]["rate_per_min"] == 0.041
    assert replay["forecast_args"]["learned_source_ml_min"] is None
    assert replay["forecast_args"]["learned_thermal_residual_c_min"] == 0.005
    assert replay["forecast_args"]["observation_samples"] == 4
    assert start["forecast_args"]["rate_per_min"] == 0.047

    room = {"learning_samples": 8, "outcome_feedback_samples": 4, "shadow_learning_promotions": 0}
    frozen = le.freeze_learning_effectiveness_context(start, room, history=history, room_key="bad")
    assert frozen["previous_model_snapshot"]["model_snapshot_id"] == "previous-model"
    assert frozen["previous_model_context"]["forecast_args"]["rate_per_min"] == 0.041


def test_previous_model_context_accessor_is_backward_compatible():
    assert le.previous_model_context_from_start(None) is None
    assert le.previous_model_context_from_start({}) is None
    assert le.previous_model_context_from_start({"learning_effectiveness": {"schema_version": "bad"}}) is None
    assert le.previous_model_context_from_start({"learning_effectiveness": {"schema_version": 99}}) is None
    assert le.previous_model_context_from_start({"learning_effectiveness": {"schema_version": 1}}) is None
    context = _frozen_start()
    context["learning_effectiveness"]["previous_model_context"] = _start_context(rate=0.04)
    previous = le.previous_model_context_from_start(context)
    assert previous["forecast_args"]["rate_per_min"] == 0.04
    previous["forecast_args"]["rate_per_min"] = 0.09
    assert context["learning_effectiveness"]["previous_model_context"]["forecast_args"]["rate_per_min"] == 0.04


def test_effectiveness_sample_scores_previous_generation_without_affecting_baseline():
    context = _frozen_start()
    previous_snapshot = {
        "rate_per_min": 0.04,
        "learned_source_ml_min": 0.1,
        "learned_thermal_residual_c_min": 0.0,
        "observation_samples": 4,
        "model_snapshot_id": "previous-model",
    }
    context["learning_effectiveness"]["previous_model_snapshot"] = previous_snapshot
    context["learning_effectiveness"]["generation_definition"] = "test generation"

    current = le.build_effectiveness_sample(
        context,
        duration_min=10,
        production_prediction={"predicted_removed_ml": 90},
        baseline_prediction={"predicted_removed_ml": 70},
        previous_model_prediction={"predicted_removed_ml": 80},
        actual_removed_ml=100,
        ended_at="2026-09-23T12:00:00+02:00",
    )
    assert current["generation_valid"] is True
    assert current["generation_winner"] == "current"
    assert current["previous_model_abs_error_ml"] == 20.0
    assert current["generation_error_gain_ml"] == 10.0
    assert current["previous_model_snapshot_id"] == "previous-model"

    previous = le.build_effectiveness_sample(
        context,
        duration_min=10,
        production_prediction={"predicted_removed_ml": 70},
        baseline_prediction={"predicted_removed_ml": 60},
        previous_model_prediction={"predicted_removed_ml": 95},
        actual_removed_ml=100,
        ended_at="2026-09-23T12:00:00+02:00",
    )
    assert previous["generation_winner"] == "previous"
    tied = le.build_effectiveness_sample(
        context,
        duration_min=10,
        production_prediction={"predicted_removed_ml": 90},
        baseline_prediction={"predicted_removed_ml": 80},
        previous_model_prediction={"predicted_removed_ml": 89.5},
        actual_removed_ml=100,
        ended_at="2026-09-23T12:00:00+02:00",
    )
    assert tied["generation_winner"] == "tie"
    no_previous = le.build_effectiveness_sample(
        context,
        duration_min=10,
        production_prediction={"predicted_removed_ml": 90},
        baseline_prediction={"predicted_removed_ml": 80},
        previous_model_prediction=None,
        actual_removed_ml=100,
        ended_at="2026-09-23T12:00:00+02:00",
    )
    assert no_previous["generation_valid"] is False


def test_generation_summary_uses_same_conservative_independent_session_evidence():
    malformed = _sample(gain=10, ended_at="2026-09-01", record_id="bad")
    malformed["generation_valid"] = True
    assert le._generation_summary([malformed])["samples"] == 0

    improving = [_generation_sample(gain=20 + (i % 2), ended_at=f"2026-09-{i+1:02d}", record_id=f"g{i}") for i in range(12)]
    regressing = [_generation_sample(gain=-20 - (i % 2), ended_at=f"2026-09-{i+1:02d}", record_id=f"r{i}") for i in range(12)]
    inconclusive = [_generation_sample(gain=10 if i % 2 == 0 else -10, ended_at=f"2026-09-{i+1:02d}", record_id=f"i{i}") for i in range(12)]
    collecting = le._generation_summary(improving[:2])
    assert collecting["status"] == "collecting"
    assert collecting["status_label"] == "Sammelt Generationenvergleiche"
    better = le._generation_summary(improving)
    assert better["status"] == "improving"
    assert better["status_label"] == "Aktuelle Modellgeneration besser belegt"
    assert better["current_model_mae_ml"] < better["previous_model_mae_ml"]
    assert better["transition_count"] == 12
    worse = le._generation_summary(regressing)
    assert worse["status"] == "regressing"
    assert worse["status_label"] == "Aktuelle Modellgeneration schlechter belegt"
    unclear = le._generation_summary(inconclusive)
    assert unclear["status"] == "inconclusive"
    assert unclear["status_label"] == "Noch kein eindeutiger Generationseffekt"


def test_learning_effectiveness_summary_exposes_generation_effectiveness():
    records = []
    for i in range(12):
        record = _record(i, [20])
        sample = record["room_results"][0]["learning_effectiveness"]
        sample.update({
            "generation_valid": True,
            "previous_model_abs_error_ml": 100.0,
            "generation_error_gain_ml": 20.0,
            "generation_winner": "current",
            "previous_model_direction_correct": True,
            "model_snapshot_id": f"current-{i}",
            "previous_model_snapshot_id": f"previous-{i}",
        })
        records.append(record)
    summary = le.learning_effectiveness_summary(records)
    generation = summary["generation_effectiveness"]
    assert generation["mode"] == "current_vs_previous_observed_generation"
    assert generation["status"] == "improving"
    assert generation["samples"] == 12
    assert generation["independent_sessions"] == 12
    assert generation["improvement_claim_supported"] is True
