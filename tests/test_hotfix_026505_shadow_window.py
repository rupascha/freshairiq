"""Hotfix 0.26.5.5 (31.10.): formula-test summary – F02 nothing from the future, F03 null-model evidence.

F02  The 30-day window is bounded on both sides: from 30 × 24 h before now up to now (plus 10 minutes for a
     device clock running slightly ahead). A record far in the future never enters.
F03  Whether a formula beats "always 0 ml" is only stated when every headline pair has a known null error;
     the null MAE of the known ones stays visible with its count. Nothing is filled in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq import forecast_shadow as fs

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
IDS = {"production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": fs.CANDIDATE_FORMULA_ID}


def _record(session, ended, production=20.0, candidate=10.0, *, null=50.0, measured=None):
    shadow = {"paired_valid": True, "production_abs_error_ml": production, "candidate_abs_error_ml": candidate, **IDS}
    if null is not None:
        shadow["null_abs_error_ml"] = null
    if measured is not None:
        shadow["measured_removed_ml"] = measured
    return {"valid": True, "ended_at": ended, "room_results": [{"validation_session_id": session, "shadow_forecast": shadow}]}


@pytest.mark.parametrize(("ended", "kept"), [
    (NOW.isoformat(), True),                                            # today
    ((NOW - timedelta(days=1)).isoformat(), True),                      # yesterday
    ((NOW - timedelta(days=30) + timedelta(minutes=1)).isoformat(), True),
    ((NOW - timedelta(days=30, minutes=1)).isoformat(), False),
    ((NOW + timedelta(minutes=9)).isoformat(), True),                   # clock a few minutes ahead
    ((NOW + timedelta(minutes=11)).isoformat(), False),
    ("2027-12-05T12:00:00+00:00", False),                               # far in the future
    ("2026-10-31T12:30:00", False),                                     # naive, read as UTC: 30 min ahead
    ("2026-10-31T13:05:00+01:00", True),                                # = 12:05 UTC
    ("2026-10-25T02:30:00+02:00", True), ("2026-10-25T02:30:00+01:00", True),  # both sides of the DST change
])
def test_f02_the_window_is_bounded_on_both_sides(ended, kept) -> None:
    assert fs.shadow_comparison_summary([_record("a", ended)], now=NOW)["samples"] == (1 if kept else 0)


def _sixteen(known_nulls, *, null=1000.0):
    days = [NOW - timedelta(days=d) for d in range(4)]
    return [_record(f"s{i}", days[i % 4].isoformat(), 20.0 + i % 3, 10.0, null=null if i < known_nulls else None) for i in range(16)]


@pytest.mark.parametrize(("known", "beats", "status"), [(1, None, "inconclusive"), (15, None, "inconclusive"), (16, True, "candidate_better")])
def test_f03_the_null_model_needs_every_headline_pair(known, beats, status) -> None:
    out = fs.shadow_comparison_summary(_sixteen(known), now=NOW)
    assert (out["samples"], out["null_samples"], out["candidate_beats_null"], out["status"]) == (16, known, beats, status)
    assert out["production_beats_null"] is beats
    assert out["null_mae_ml"] == 1000.0  # the known ones stay visible


def test_f03_a_measured_zero_is_known_and_unknown_stays_unknown() -> None:
    zero = fs.shadow_comparison_summary([_record("a", NOW.isoformat(), null=None, measured=0.0)], now=NOW)
    assert (zero["null_samples"], zero["null_mae_ml"], zero["candidate_beats_null"]) == (1, 0.0, False)
    unknown = fs.shadow_comparison_summary([_record("a", NOW.isoformat(), null=None)], now=NOW)
    assert (unknown["null_samples"], unknown["null_mae_ml"], unknown["candidate_beats_null"]) == (0, None, None)
