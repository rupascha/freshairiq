"""Code audit 0.26.5.5 (9): F01 kept by owner decision, F02 ventilation log metadata, F03 pair selection.

F01  The owner decided twice (30.10.) that the minimum airing time stays 3 minutes and that the
     decisions themselves must keep a useful airing open. These tests pin that behaviour at
     2:00 / 3:30 / 4:59 / 5:00 so a silent change is noticed; protection (moisture coming in)
     still closes inside the minimum, a younger window keeps its own minimum time.
F02  The long-term ventilation log keeps the logging version, the start version and the formula ids
     of the passive test (errors only for a valid pair); older entries stay "unknown".
F03  One observation per session whatever the order: a valid pair beats an exclusion, then the
     latest report; exclusions are counted once per session.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import csv
import io

import pytest

from custom_components.freshairiq import forecast_shadow as fs
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.opening_strategy import synchronize_room_presentation_actions
from custom_components.freshairiq.ventilation_daily import ventilation_csv
from custom_components.freshairiq.ventilation_log import (
    append_ventilation_log,
    build_ventilation_pdf,
    compact_ventilation_event,
    filter_ventilation_log,
)

UTC = timezone.utc


# --- F01: owner decision, 3 minutes -----------------------------------------------------------

def _open(key, elapsed, **extra):
    room = {"key": key, "name": key, "active": True, "session_elapsed_min": elapsed, "delta_g_m3": 1.2,
            "close_recommended": False, "action": "Continue ventilating", "close_decision_ready": True,
            "data_quality": "ok", "calculation_enabled": True, "forecast_5_min_moisture_effect_ml": 5.0}
    room.update(extra)
    return room

# Audit N02: the window is counted back from now – the tests pin "now" so they do not age.
SUMMARY_NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _summary(records, **kwargs):
    return fs.shadow_comparison_summary(records, **{"now": SUMMARY_NOW, **kwargs})



def _presented(rooms, keys):
    synchronize_room_presentation_actions({"kind": "close", "room_keys": keys}, rooms, min_duration_min=DEFAULT_OPTIONS["min_duration_min"])
    return {key: room["action"] for key, room in rooms.items()}


def test_f01_the_minimum_stays_three_minutes() -> None:
    assert DEFAULT_OPTIONS["min_duration_min"] == 3.0


@pytest.mark.parametrize(("elapsed", "action"), [(2.0, "Continue ventilating"), (3.5, "Close"), (4.98, "Close"), (5.0, "Close")])
def test_f01_a_house_close_reaches_a_room_after_its_minimum(elapsed, action) -> None:
    assert _presented({"bad": _open("bad", elapsed)}, ["bad"]) == {"bad": action}


def test_f01_staggered_windows_keep_their_own_minimum() -> None:
    assert _presented({"bad": _open("bad", 2.0), "kueche": _open("kueche", 6.0)}, ["bad", "kueche"]) == {
        "bad": "Continue ventilating", "kueche": "Close"}


def test_f01_moisture_coming_in_closes_inside_the_minimum() -> None:
    assert _presented({"bad": _open("bad", 2.0, delta_g_m3=-0.8, forecast_5_min_moisture_effect_ml=-8.0)}, ["bad"]) == {"bad": "Close"}


def test_f01_a_closed_room_in_its_final_measurement_is_not_touched() -> None:
    rooms = {"bad": _open("bad", 2.0, active=False, session_finalization_pending=True, action="Okay"), "kueche": _open("kueche", 4.0)}
    assert _presented(rooms, ["kueche"]) == {"bad": "Okay", "kueche": "Close"}


# --- F02: ventilation log metadata ------------------------------------------------------------

SHADOW = {"production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": fs.CANDIDATE_FORMULA_ID,
          "freshairiq_version_at_start": "0.26.5.4", "paired_valid": True, "production_abs_error_ml": 12.0,
          "candidate_abs_error_ml": 7.5, "null_abs_error_ml": 30.0}


def _event(event_id="bad:1", shadow=None, start="2026-10-31T10:00:00+00:00", end="2026-10-31T10:10:00+00:00"):
    event = {"event_id": event_id, "key": "bad", "name": "Bad", "started_at": start, "ended_at": end, "duration_min": 10.0,
             "removed_ml": 80.0, "moisture_measurement_valid": True}
    if shadow is not None:
        event["shadow_forecast"] = shadow
    return event


def test_f02_the_log_keeps_version_and_formula_ids() -> None:
    row = compact_ventilation_event(_event(shadow=SHADOW), "0.26.5.5")
    assert (row["freshairiq_version"], row["freshairiq_version_at_start"]) == ("0.26.5.5", "0.26.5.4")
    assert (row["production_formula_id"], row["candidate_formula_id"]) == (fs.PRODUCTION_FORMULA_ID, fs.CANDIDATE_FORMULA_ID)
    assert (row["formula_pair_valid"], row["production_abs_error_ml"], row["candidate_abs_error_ml"]) == (True, 12.0, 7.5)


def test_f02_excluded_and_missing_shadow_are_unknown_not_invented() -> None:
    excluded = compact_ventilation_event(_event(shadow={**SHADOW, "paired_valid": False, "exclusion_reason": "moisture_source"}), "0.26.5.5")
    assert excluded["formula_pair_valid"] is False and excluded["production_abs_error_ml"] is None and excluded["candidate_abs_error_ml"] is None
    assert excluded["production_formula_id"] == fs.PRODUCTION_FORMULA_ID
    none = compact_ventilation_event(_event(), "0.26.5.5")
    assert none["freshairiq_version"] == "0.26.5.5" and none["production_formula_id"] is None and none["formula_pair_valid"] is None
    legacy = compact_ventilation_event(_event())  # direct callers without a version
    assert legacy["freshairiq_version"] is None


def test_f02_log_filter_csv_and_pdf() -> None:
    now = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    old = {"event_id": "old", "room_key": "bad", "room_name": "Bad", "started_at": "2026-10-30T10:00:00+00:00",
           "ended_at": "2026-10-30T10:05:00+00:00", "duration_min": 5.0, "removed_ml": 20.0, "measurement_valid": True}
    log = append_ventilation_log([old], [_event(shadow=SHADOW), _event(shadow=SHADOW)], now, "0.26.5.5")
    assert [row["event_id"] for row in log] == ["old", "bad:1"]  # appended once
    rows = filter_ventilation_log(log, now - timedelta(days=2), now)
    assert rows[1]["production_formula_id"] == fs.PRODUCTION_FORMULA_ID and "production_formula_id" not in rows[0]
    table = list(csv.reader(io.StringIO(ventilation_csv(rows, date(2026, 10, 30), date(2026, 10, 31), UTC, language="de", daily=False)[1:]), delimiter=";"))
    assert table[0][-6:] == ["FreshAirIQ-Version", "Prognoseformel", "Version bei Lüftungsbeginn", "Testformel",
                             "Fehler Prognoseformel (ml)", "Fehler Testformel (ml)"]
    assert table[1][-6:] == ["", "", "", "", "", ""]
    # audit G01: both formula ids and the valid error comparison of the airing
    assert table[2][-6:] == ["0.26.5.5", fs.PRODUCTION_FORMULA_ID, "0.26.5.4", fs.CANDIDATE_FORMULA_ID, "12,0", "7,5"]
    english = list(csv.reader(io.StringIO(ventilation_csv(rows, date(2026, 10, 30), date(2026, 10, 31), UTC, language="en", daily=False)[1:])))
    assert english[0][-6:] == ["FreshAirIQ version", "Forecast formula", "Version at airing start", "Test formula",
                               "Forecast formula error (mL)", "Test formula error (mL)"]
    assert english[2][-2:] == ["12.0", "7.5"]
    assert build_ventilation_pdf(rows, now - timedelta(days=2), now, "de").startswith(b"%PDF")


# --- F03: pair selection ----------------------------------------------------------------------

def _shadow(valid, production=10.0, candidate=5.0, reason="no_measurement"):
    return {"paired_valid": valid, "exclusion_reason": None if valid else reason,
            "production_abs_error_ml": production if valid else None, "candidate_abs_error_ml": candidate if valid else None,
            "null_abs_error_ml": 40.0 if valid else None,
            # real pairs always name their formulas (audit N04: only the current pair enters the headline)
            "production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": fs.CANDIDATE_FORMULA_ID}


def _record(rooms, ended="2026-10-31T12:00:00+00:00"):
    return {"valid": True, "ended_at": ended, "started_at": ended, "model_version": "m",
            "room_results": [{"validation_session_id": sid, "shadow_forecast": sh} for sid, sh in rooms]}


@pytest.mark.parametrize("order", [(False, True), (True, False)])
def test_f03_a_valid_pair_wins_over_an_exclusion_in_any_order(order) -> None:
    records = [_record([("same", _shadow(valid))], ended=f"2026-10-31T1{i}:00:00+00:00") for i, valid in enumerate(order)]
    out = _summary(records)
    assert (out["samples"], out["excluded_total"], out["production_mae_ml"], out["candidate_mae_ml"]) == (1, 0, 10.0, 5.0)


def test_f03_two_valid_reports_of_one_session_count_once_and_the_latest_wins() -> None:
    early = _record([("same", _shadow(True, 10.0, 5.0))], ended="2026-10-31T10:00:00+00:00")
    late = _record([("same", _shadow(True, 20.0, 8.0))], ended="2026-10-31T11:00:00+00:00")
    for records in ([early, late], [late, early]):
        out = _summary(records)
        assert (out["samples"], out["production_mae_ml"], out["candidate_mae_ml"], out["null_mae_ml"]) == (1, 20.0, 8.0, 40.0)


def test_f03_exclusions_count_once_per_session_and_distinct_sessions_all_count() -> None:
    records = [_record([("a", _shadow(False, reason="cross_mode_changed"))], "2026-10-30T10:00:00+00:00"),
               _record([("a", _shadow(False, reason="moisture_source"))], "2026-10-30T11:00:00+00:00"),
               _record([("b", _shadow(True, 10.0, 6.0)), ("c", _shadow(True, 12.0, 4.0))], "2026-10-31T10:00:00+00:00")]
    out = _summary(records)
    assert out["samples"] == 2 and out["excluded"] == {"moisture_source": 1}  # the latest reason of session a
    assert out["independent_sessions"] == 1 and out["distinct_days"] == 1  # two rooms of one house airing
    reverse = _summary(list(reversed(records)))
    for key in ("samples", "excluded", "production_mae_ml", "candidate_mae_ml", "null_mae_ml", "independent_sessions", "distinct_days"):
        assert reverse[key] == out[key], key


def test_f03_reports_without_a_session_id_are_kept_apart() -> None:
    record = {"valid": True, "ended_at": "2026-10-31T10:00:00+00:00",
              "room_results": [{"shadow_forecast": _shadow(True)}, {"shadow_forecast": _shadow(True, 20.0, 9.0)}]}
    assert _summary([record])["samples"] == 2
