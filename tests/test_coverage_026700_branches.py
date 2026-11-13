"""0.26.7.0: the defensive branches of the new code paths (#28, #29, behaviour learning) are exercised explicitly."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import custom_components.freshairiq.forecast_shadow as fs
import custom_components.freshairiq.learning_effectiveness as le
from custom_components.freshairiq.forecast_validation import VALIDATION_RECORD_VERSION, validation_summary
from custom_components.freshairiq.intelligence import ensure_behaviour_defaults, sync_active_recommendation
from custom_components.freshairiq.model import co2_release_configured
from tests.test_issue28_target_cap_026700 import _context


def test_candidate_formula_failing_on_its_inputs_is_named_not_raised(monkeypatch):
    context = _context(current_ah=12.0, target_ah=10.0)
    context["shadow"] = fs.freeze_shadow_start(cross_ventilated=False, integration_version="0.26.7.0")

    def broken(**_kwargs):
        raise TypeError("unexpected input")

    monkeypatch.setattr(fs, "shadow_removed_ml", broken)
    record = fs.shadow_forecast_record(context, horizon_min=10.0, production_predicted_ml=50.0, measured_removed_ml=40.0,
                                       comparable=True, time_aligned=True)
    assert record["exclusion_reason"] == "start_context_incomplete" and record["paired_valid"] is False


def test_replay_raising_on_a_non_finite_start_is_invalid_input(monkeypatch):
    context = _context(current_ah=12.0, target_ah=10.0)
    context["shadow"] = fs.freeze_shadow_start(cross_ventilated=False, integration_version="0.26.7.0")

    def broken(*_args, **_kwargs):
        raise OverflowError("math range")

    monkeypatch.setattr(fs, "evaluate_start_forecast_at_duration", broken)
    record = fs.shadow_forecast_record(context, horizon_min=10.0, production_predicted_ml=50.0, measured_removed_ml=40.0,
                                       comparable=True, time_aligned=True)
    assert record["exclusion_reason"] == "invalid_input"


def test_validation_summary_skips_non_comparable_rooms_of_current_records():
    ended = datetime(2026, 11, 12, 18, 0)
    record = {"valid": True, "validation_version": VALIDATION_RECORD_VERSION, "ended_at": ended.isoformat(),
              "moisture_abs_error_ml": 10.0, "room_results": [{"key": "a", "comparable": False, "moisture_abs_error_ml": 99.0},
                                                                {"key": "b", "comparable": True, "moisture_abs_error_ml": 10.0}]}
    summary = validation_summary([record], days=3650)
    assert [r["key"] for r in summary["rooms"]] == ["b"]


def test_learning_effectiveness_basis_count_and_extract_skip_incomplete_rows():
    rows = [{"valid": False}, "bad", {"valid": True, "room_results": [
        {"key": "r", "comparable": True, "learning_effectiveness": {"valid": True, "prediction_basis": "physical_start_replay",
                                                                     "production_abs_error_ml": None, "baseline_abs_error_ml": 3}}]}]
    assert le._previous_basis_count(rows) == 0
    assert le._extract_samples(rows) == []


def test_unchanged_episode_reports_only_a_change_of_actionability():
    store: dict = {"rooms": {"bad": {}}}
    ensure_behaviour_defaults(store["rooms"]["bad"])
    now = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)
    rec = {"kind": "ventilate", "room_keys": ["bad"]}
    assert sync_active_recommendation(store, rec, now, {"away": True}) is True
    assert sync_active_recommendation(store, rec, now + timedelta(minutes=1), {"away": True}) is False
    assert sync_active_recommendation(store, rec, now + timedelta(minutes=2), {}) is True        # somebody came home
    assert sync_active_recommendation(store, rec, now + timedelta(minutes=3), {}) is False


def test_co2_release_configured_tolerates_bad_values():
    assert co2_release_configured({"co2_release": "bad"}) is False
    assert co2_release_configured({"co2_release": 750}) is True
