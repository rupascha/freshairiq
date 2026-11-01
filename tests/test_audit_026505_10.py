"""Re-check 0.26.5.5 (10): formula-test summary robustness (N01–N05).

N01  Mixed naive/aware time stamps no longer switch the whole comparison off (naive is read as UTC,
     unreadable stamps leave out only their record).
N02  "Last 30 days" counts back from now, not from the newest record.
N03  An unknown null-model error stays unknown – no 0 ml stand-in; only known values are compared.
N04  Only pairs of the current formula pair enter the headline; other revisions are listed apart.
N05  Equal reports of one airing are chosen by a fixed rule (current formula pair, then ids), never
     by the order of the reports.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq import forecast_shadow as fs

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
CURRENT = {"production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": fs.CANDIDATE_FORMULA_ID}


def _record(session, ended, production=20.0, candidate=10.0, *, null=50.0, measured=50.0, ids=None):
    shadow = {"paired_valid": True, "production_abs_error_ml": production, "candidate_abs_error_ml": candidate, **(ids or CURRENT)}
    if null is not None:
        shadow["null_abs_error_ml"] = null
    if measured is not None:
        shadow["measured_removed_ml"] = measured
    return {"valid": True, "ended_at": ended, "room_results": [{"validation_session_id": session, "shadow_forecast": shadow}]}


def _summary(records, **kwargs):
    return fs.shadow_comparison_summary(records, **{"now": NOW, **kwargs})


# --- N01 --------------------------------------------------------------------------------------

def test_n01_mixed_naive_and_aware_stamps_keep_every_pair() -> None:
    records = [_record("a", "2026-10-30T10:00:00"), _record("b", "2026-10-31T10:00:00+01:00")]
    assert _summary(records)["samples"] == 2
    published = fs.published_comparison(records, now=NOW)
    assert published["status"] != "unavailable" and published["samples"] == 2


def test_n01_utc_dst_and_broken_stamps() -> None:
    records = [_record("z", "2026-10-30T10:00:00Z"),
               _record("summer", "2026-10-24T23:30:00+02:00"),  # before the change to winter time (Berlin)
               _record("winter", "2026-10-25T03:30:00+01:00"),
               _record("broken", "30.10.2026 10:00"), _record("none", None)]
    out = _summary(records)
    assert out["samples"] == 3 and out["status"] == "collecting"
    assert _summary([])["status"] == "no_data" and fs.published_comparison([], now=NOW)["status"] == "no_data"


# --- N02 --------------------------------------------------------------------------------------

@pytest.mark.parametrize(("age", "kept"), [(timedelta(days=29), True), (timedelta(days=30) - timedelta(minutes=1), True),
                                           (timedelta(days=30, minutes=1), False), (timedelta(days=31), False)])
def test_n02_the_window_counts_back_from_now(age, kept) -> None:
    assert _summary([_record("a", (NOW - age).isoformat())])["samples"] == (1 if kept else 0)


def test_n02_an_old_history_only_is_no_data() -> None:
    out = _summary([_record("a", "2020-01-01T10:00:00+00:00")])
    assert (out["samples"], out["status"], out["first_day"], out["period_days"]) == (0, "no_data", None, 30)
    # a local "now" in another time zone gives the same window
    local_now = NOW.astimezone(timezone(timedelta(hours=-5)))
    assert _summary([_record("a", (NOW - timedelta(days=29)).isoformat())], now=local_now)["samples"] == 1
    naive_now = NOW.replace(tzinfo=None)
    assert _summary([_record("a", (NOW - timedelta(days=29)).isoformat())], now=naive_now)["samples"] == 1


# --- N03 --------------------------------------------------------------------------------------

def test_n03_an_unknown_null_error_is_not_zero() -> None:
    out = _summary([_record("a", NOW.isoformat(), null=None, measured=None)])
    assert out["samples"] == 1 and out["null_samples"] == 0
    assert (out["null_mae_ml"], out["candidate_beats_null"], out["production_beats_null"]) == (None, None, None)


def test_n03_a_measured_zero_is_a_real_value_and_partial_fields_only_count_where_known() -> None:
    zero = _summary([_record("a", NOW.isoformat(), null=None, measured=0.0)])
    assert (zero["null_samples"], zero["null_mae_ml"], zero["candidate_beats_null"]) == (1, 0.0, False)
    partial = _summary([_record("a", NOW.isoformat(), 20.0, 10.0, null=100.0), _record("b", NOW.isoformat(), 30.0, 30.0, null=None, measured=None)])
    assert (partial["samples"], partial["null_samples"], partial["null_mae_ml"]) == (2, 1, 100.0)
    # Hotfix F03 (31.10.): the earlier expectation True judged the null model on one of two headline pairs;
    # with partly unknown null errors no "beats" statement is made any more (the known null MAE stays visible)
    assert partial["candidate_beats_null"] is None and partial["candidate_mae_ml"] == 20.0  # headline MAE over both pairs


def test_n03_better_needs_known_null_errors() -> None:
    days = [NOW - timedelta(days=d) for d in range(4)]
    known = [_record(f"s{i}", days[i % 4].isoformat(), 20.0 + i % 3, 10.0) for i in range(16)]
    assert _summary(known)["status"] == "candidate_better"
    unknown = [_record(f"s{i}", days[i % 4].isoformat(), 20.0 + i % 3, 10.0, null=None, measured=None) for i in range(16)]
    out = _summary(unknown)
    assert out["status"] == "inconclusive" and out["candidate_beats_null"] is None


# --- N04 --------------------------------------------------------------------------------------

def test_n04_other_formula_revisions_are_never_mixed_into_the_headline() -> None:
    v2 = {"production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": "humidity-hybrid-2026-12-01-r2"}
    records = [_record("a", NOW.isoformat(), 20.0, 10.0), _record("b", NOW.isoformat(), 10.0, 20.0, ids=v2)]
    out = _summary(records)
    assert (out["samples"], out["production_mae_ml"], out["candidate_mae_ml"]) == (1, 20.0, 10.0)
    assert out["candidate_formula_ids"] == [fs.CANDIDATE_FORMULA_ID] and out["other_formula_samples"] == 1
    assert out["other_formula_pairs"] == [{"production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": v2["candidate_formula_id"],
                                           "samples": 1, "production_mae_ml": 10.0, "candidate_mae_ml": 20.0}]


def test_n04_a_changed_production_formula_and_only_old_pairs() -> None:
    old_prod = {"production_formula_id": "start-curve-v2-horizon-forecast-r0", "candidate_formula_id": fs.CANDIDATE_FORMULA_ID}
    out = _summary([_record("a", NOW.isoformat(), 20.0, 10.0, ids=old_prod)])
    assert out["status"] == "no_data" and out["samples"] == 0 and out["production_formula_ids"] == []
    assert out["other_formula_pairs"][0]["production_formula_id"] == "start-curve-v2-horizon-forecast-r0"
    missing = _summary([_record("b", NOW.isoformat(), ids={"production_formula_id": None, "candidate_formula_id": None})])
    assert missing["samples"] == 0 and missing["other_formula_pairs"][0]["candidate_formula_id"] is None


# --- N05 --------------------------------------------------------------------------------------

def test_n05_equal_reports_are_chosen_by_rule_not_by_order() -> None:
    v2 = {**CURRENT, "candidate_formula_id": "candidate-v2"}
    v3 = {**CURRENT, "candidate_formula_id": "candidate-v3"}
    current, other, third = (_record("s", NOW.isoformat()), _record("s", NOW.isoformat(), ids=v2), _record("s", NOW.isoformat(), ids=v3))
    for records in ([current, other], [other, current]):
        out = _summary(records)
        assert out["samples"] == 1 and out["other_formula_samples"] == 0  # the current pair wins
    for records in ([other, third], [third, other]):
        out = _summary(records)
        assert out["other_formula_pairs"][0]["candidate_formula_id"] == "candidate-v3"  # then by id, deterministically
