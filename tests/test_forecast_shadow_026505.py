"""Passive shadow comparison of the moisture formula ``humidity-hybrid-2026-10-31-r1``.

Formula values and limits, fair pairing on the frozen start curve, exclusions, statistics,
the published summary, diagnostics transport and that nothing in the control path uses it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import re
from pathlib import Path

import pytest

from custom_components.freshairiq import forecast_shadow as fs
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.diagnostic_transport import _sanitize_tree
from custom_components.freshairiq.forecast_validation import (
    build_validation_record,
    evaluate_start_forecast_at_duration,
    freeze_start_forecast_context,
)
from custom_components.freshairiq.learning_effectiveness import learning_effectiveness_summary

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "freshairiq"

# Audit N02: the window is counted back from now – the tests pin "now" so they do not age.
SUMMARY_NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def _summary(records, **kwargs):
    return fs.shadow_comparison_summary(records, **{"now": SUMMARY_NOW, **kwargs})



def _hand(room, source, volume, horizon, cross, legacy):
    """The formula of the study, transcribed independently with its literal coefficients."""
    if horizon == 0:
        return 0.0
    ratio = min(max(volume / 40.0, 0.1), 4.0)
    k = math.exp(-5.24466443 + (0.93384866 if cross else 0.0) - 0.24775893 * math.log(ratio))
    length = min(horizon, 20.0) + 0.55 * max(horizon - 20.0, 0.0)
    physical = (room - source) * volume * (1.0 - math.exp(-k * horizon)) - 0.03705066 * length
    return 0.20102258 * legacy + 0.79897742 * physical + 1.17503054 * (1.0 - math.exp(-horizon))


def _shadow(**kw):
    args = dict(room_ah_start_g_m3=12.0, source_ah_start_g_m3=7.0, volume_m3=40.0, horizon_min=10.0,
                is_cross_ventilated=False, legacy_start_forecast_ml=50.0)
    args.update(kw)
    return fs.shadow_removed_ml(**args)


# --- formula ---------------------------------------------------------------------------------

@pytest.mark.parametrize("kw", [
    {}, {"horizon_min": 20.0}, {"horizon_min": 35.0}, {"horizon_min": 120.0}, {"is_cross_ventilated": True},
    {"volume_m3": 1.0}, {"volume_m3": 4.0}, {"volume_m3": 160.0}, {"volume_m3": 500.0},
    {"source_ah_start_g_m3": 12.0}, {"source_ah_start_g_m3": 14.5}, {"legacy_start_forecast_ml": -20.0},
])
def test_formula_matches_the_study(kw) -> None:
    args = dict(room=12.0, source=7.0, volume=40.0, horizon=10.0, cross=False, legacy=50.0)
    names = {"room_ah_start_g_m3": "room", "source_ah_start_g_m3": "source", "volume_m3": "volume",
             "horizon_min": "horizon", "is_cross_ventilated": "cross", "legacy_start_forecast_ml": "legacy"}
    args.update({names[k]: v for k, v in kw.items()})
    assert _shadow(**kw) == pytest.approx(_hand(**args), rel=1e-12, abs=1e-9)


def test_the_smoke_values_of_the_formula_study() -> None:
    """test_candidate_formula.py of the formula study 2026-10-31: same inputs, same values."""
    kw = dict(room_ah_start_g_m3=12.0, source_ah_start_g_m3=9.0, volume_m3=40.0, is_cross_ventilated=False)
    assert fs.shadow_removed_ml(horizon_min=0, legacy_start_forecast_ml=0.0, **kw) == 0
    p5 = fs.shadow_removed_ml(horizon_min=5.0, legacy_start_forecast_ml=15.0, **kw)
    p10 = fs.shadow_removed_ml(horizon_min=10.0, legacy_start_forecast_ml=22.0, **kw)
    neg = fs.shadow_removed_ml(room_ah_start_g_m3=8.0, source_ah_start_g_m3=11.0, volume_m3=40.0, horizon_min=10,
                               is_cross_ventilated=True, legacy_start_forecast_ml=-40.0)
    assert (round(p5, 2), round(p10, 2), round(neg, 2)) == (6.53, 10.23, -19.2)
    assert p10 > p5 >= 0 and neg < 0


def test_formula_pinned_values_and_shape() -> None:
    assert _shadow() == pytest.approx(19.141726, abs=1e-5)
    assert _shadow(horizon_min=0.0) == 0.0
    # beyond 20 min the length term grows with 0.55
    assert _shadow(horizon_min=30.0) - _shadow(horizon_min=20.0) != pytest.approx(0.0)
    assert _shadow(is_cross_ventilated=True) > _shadow()  # faster exchange
    assert _shadow(volume_m3=2.0) == pytest.approx(_hand(12.0, 7.0, 2.0, 10.0, False, 50.0))  # ratio clamped at 0.1
    assert _shadow(source_ah_start_g_m3=14.0) < 0.2 * 50.0  # wetter source: the physics part is negative


@pytest.mark.parametrize("kw", [
    {"room_ah_start_g_m3": float("nan")}, {"source_ah_start_g_m3": float("inf")}, {"legacy_start_forecast_ml": float("-inf")},
    {"horizon_min": float("nan")},
])
def test_formula_rejects_non_finite_input(kw) -> None:
    with pytest.raises(ValueError, match="Non-finite"):
        _shadow(**kw)


@pytest.mark.parametrize("kw", [{"volume_m3": 0.99}, {"volume_m3": 500.1}, {"horizon_min": -0.1}, {"horizon_min": 120.01}])
def test_formula_refuses_outside_the_calibrated_range(kw) -> None:
    with pytest.raises(ValueError, match="calibrated range"):
        _shadow(**kw)


def test_formula_ids_are_stable_and_the_production_id_follows_the_forecast_code() -> None:
    assert fs.CANDIDATE_FORMULA_ID == "humidity-hybrid-2026-10-31-r1"
    # Testvermerk 0.26.7.0 (#28): Startkontext v3 (physikalischer Replay) -> neue Produktions-ID
    # Testvermerk 0.26.7.0 final hotfix F11-C: forecast.py changed (max-duration end point removed) -> revision r2
    assert fs.PRODUCTION_FORMULA_ID == "start-curve-v3-horizon-forecast-r2"
    # Any change of forecast.py (the active calculation) must bump PRODUCTION_FORMULA_ID and this pin.
    digest = hashlib.sha256((PKG / "forecast.py").read_bytes()).hexdigest()
    assert digest == "f26d7a7f3746d5ec8dc4d91c2824d1e83947d20548fff0e75b8c5fd5e7213df8", digest


# --- pairing on the frozen start ---------------------------------------------------------------

def _args(**extra):
    args = dict(current_ah=12.0, source_ah=7.0, current_temp_c=21.0, source_temp_c=8.0, volume_m3=40.0,
                rate_per_min=0.03, airflow_bonus=1.0, prior_source_ml_min=0.0, learned_source_ml_min=None,
                learned_thermal_residual_c_min=None, observation_samples=0, model_maturity_pct=55.0,
                measurement_frame_quality="excellent", running=True, session_elapsed_min=4.0,
                session_fresh_measurements=3, recent_observed_removed_ml_min=2.0, future_source_boundaries=None)
    args.update(extra)
    return args


def _context(cross=False, **extra):
    context = freeze_start_forecast_context(_args(**extra), target_ah=10.0, options=DEFAULT_OPTIONS, start_ah=12.0, start_source_ah=7.0,
                                            start_temp_c=21.0, start_source_temp_c=8.0)
    context["shadow"] = fs.freeze_shadow_start(cross_ventilated=cross, integration_version="0.26.5.5")
    return context


def _pair(context, horizon=12.0, measured=40.0, **kw):
    production = evaluate_start_forecast_at_duration(context, horizon)
    values = dict(horizon_min=horizon, production_predicted_ml=production["predicted_removed_ml"] if production else None,
                  measured_removed_ml=measured, comparable=True, time_aligned=production is not None, cross_ratio=0.0)
    values.update(kw)
    return fs.shadow_forecast_record(context, **values), production


def test_a_valid_pair_uses_the_frozen_curve_at_the_measured_duration() -> None:
    context = _context()
    record, production = _pair(context)
    assert record["paired_valid"] is True and record["exclusion_reason"] is None
    assert record["production_predicted_removed_ml"] == round(production["predicted_removed_ml"], 1)
    expected = fs.shadow_removed_ml(room_ah_start_g_m3=12.0, source_ah_start_g_m3=7.0, volume_m3=40.0, horizon_min=12.0,
                                    is_cross_ventilated=False, legacy_start_forecast_ml=production["predicted_removed_ml"])
    assert record["candidate_predicted_removed_ml"] == round(expected, 1)
    assert record["production_abs_error_ml"] == round(abs(40.0 - production["predicted_removed_ml"]), 1)
    assert record["candidate_abs_error_ml"] == round(abs(40.0 - expected), 1)
    assert (record["freshairiq_version_at_start"], record["start_context_version"], record["comparison_schema_version"]) == ("0.26.5.5", 3, 1)  # Testvermerk 0.26.7.0 (#28): Startkontext v3
    assert record["null_abs_error_ml"] == 40.0 and record["opening_learning_quarantined"] is False
    assert record["candidate_formula_id"] == fs.CANDIDATE_FORMULA_ID and record["production_formula_id"] == fs.PRODUCTION_FORMULA_ID


def test_end_values_never_reach_the_start_prediction() -> None:
    """The freeze copies the start state; later live values (end AH, later reference, learned rates) change nothing."""
    live = _args()
    context = freeze_start_forecast_context(live, target_ah=10.0, options=DEFAULT_OPTIONS, start_ah=12.0, start_source_ah=7.0,
                                            start_temp_c=21.0, start_source_temp_c=8.0)
    context["shadow"] = fs.freeze_shadow_start(cross_ventilated=False, integration_version="0.26.5.5")
    before, _ = _pair(context)
    live.update(current_ah=9.0, source_ah=9.5, rate_per_min=0.2, airflow_bonus=1.25)  # end of the session
    after, _ = _pair(context)
    assert before == after
    assert context["forecast_args"]["running"] is False and context["forecast_args"]["recent_observed_removed_ml_min"] is None


def test_shadow_frozen_by_an_older_version_keeps_its_provenance() -> None:
    context = _context()
    context["shadow"]["integration_version"] = "0.26.5.4"
    assert _pair(context)[0]["freshairiq_version_at_start"] == "0.26.5.4"


@pytest.mark.parametrize(("kw", "reason"), [
    ({"time_aligned": False}, "production_unavailable"),
    ({"production_predicted_ml": None}, "production_unavailable"),
    ({"measured_removed_ml": None}, "no_measurement"),
    ({"contaminated": True}, "moisture_source"),
    ({"reference_reversal": True}, "reference_reversal"),
    ({"comparable": False}, "measurement_quality"),
    ({"cross_ratio": 0.3}, "cross_mode_changed"),
    ({"cross_ratio": None}, "cross_mode_changed"),
])
def test_exclusions_are_never_counted_as_pairs(kw, reason) -> None:
    record, _ = _pair(_context(), **kw)
    assert record["paired_valid"] is False and record["exclusion_reason"] == reason
    assert record["production_abs_error_ml"] is None and record["candidate_abs_error_ml"] is None


def test_cross_ventilation_known_at_the_start() -> None:
    context = _context(cross=True)
    assert _pair(context, cross_ratio=0.97)[0]["paired_valid"] is True
    assert _pair(context, cross_ratio=0.6)[0]["exclusion_reason"] == "cross_mode_changed"
    plain = _pair(_context(), cross_ratio=0.04)[0]
    crossed = _pair(context, cross_ratio=1.0)[0]
    assert plain["paired_valid"] and crossed["candidate_predicted_removed_ml"] != plain["candidate_predicted_removed_ml"]


def test_unavailable_unsupported_and_broken_starts() -> None:
    assert fs.shadow_forecast_record(None, horizon_min=10, production_predicted_ml=1, measured_removed_ml=1,
                                     comparable=True, time_aligned=True) is None
    legacy = _context()
    legacy.pop("shadow")
    assert _pair(legacy)[0] is None  # started before the shadow existed: unavailable, never invented
    old = _context()
    old["shadow"]["version"] = 99
    assert _pair(old)[0] is None
    wrong = _context()
    wrong["version"] = 1
    assert fs.shadow_forecast_record(wrong, horizon_min=10, production_predicted_ml=1, measured_removed_ml=1, comparable=True,
                                     time_aligned=True)["exclusion_reason"] == "start_context_unsupported"
    big = _context(volume_m3=600.0)
    big["forecast_args"]["volume_m3"] = 600.0
    assert fs.shadow_forecast_record(big, horizon_min=10, production_predicted_ml=5, measured_removed_ml=1, comparable=True,
                                     time_aligned=True)["exclusion_reason"] == "outside_calibrated_range"
    nan = _context()
    nan["forecast_args"]["current_ah"] = float("nan")
    assert fs.shadow_forecast_record(nan, horizon_min=10, production_predicted_ml=5, measured_removed_ml=1, comparable=True,
                                     time_aligned=True)["exclusion_reason"] == "invalid_input"
    missing = _context()
    del missing["forecast_args"]["source_ah"]
    assert fs.shadow_forecast_record(missing, horizon_min=10, production_predicted_ml=5, measured_removed_ml=1, comparable=True,
                                     time_aligned=True)["exclusion_reason"] == "start_context_incomplete"
    unmeasured = fs.shadow_forecast_record(_context(), horizon_min=None, production_predicted_ml=None, measured_removed_ml=None,
                                           comparable=False, time_aligned=False, no_measurement=True)
    assert unmeasured["exclusion_reason"] == "no_measurement" and unmeasured["paired_valid"] is False

    class Broken(dict):
        def get(self, *_args):
            raise RuntimeError("boom")

    assert fs.shadow_forecast_record(Broken(), horizon_min=10, production_predicted_ml=1, measured_removed_ml=1, comparable=True,
                                     time_aligned=True)["exclusion_reason"] == "shadow_error"


def test_a_measured_zero_is_a_value_not_missing() -> None:
    record, _ = _pair(_context(), measured=0.0)
    assert record["paired_valid"] is True and record["measured_removed_ml"] == 0.0 and record["null_abs_error_ml"] == 0.0


def test_quarantined_sessions_are_marked_not_excluded() -> None:
    record, _ = _pair(_context(), quarantined=True)
    assert record["paired_valid"] is True and record["opening_learning_quarantined"] is True
    excluded, _ = _pair(_context(), quarantined=True, contaminated=True)
    assert excluded["opening_learning_quarantined"] is True and excluded["null_abs_error_ml"] is None


# --- validation record and statistics ------------------------------------------------------------

def _room(session_id, production_err, candidate_err, *, valid=True, reason=None, shadow=True, null=50.0, quarantined=False):
    room = {"validation_session_id": session_id, "key": "bad", "comparable": True}
    if shadow:
        room["shadow_forecast"] = {"paired_valid": valid, "exclusion_reason": reason,
                                   "production_abs_error_ml": production_err if valid else None,
                                   "candidate_abs_error_ml": candidate_err if valid else None,
                                   "null_abs_error_ml": null if valid else None, "opening_learning_quarantined": quarantined,
                                   "production_formula_id": fs.PRODUCTION_FORMULA_ID, "candidate_formula_id": fs.CANDIDATE_FORMULA_ID}
    return room


def _records(pairs, days=1, per_record=1):
    records = []
    for index in range(0, len(pairs), per_record):
        day = 1 + (index // per_record) % days
        rooms = [_room(f"s{index + i}", *pairs[index + i]) for i in range(min(per_record, len(pairs) - index))]
        records.append({"valid": True, "ended_at": f"2026-10-{day:02d}T12:{index % 60:02d}:00+00:00",
                        "started_at": f"2026-10-{day:02d}T11:00:00+00:00", "model_version": "x", "room_results": rooms})
    return records


def test_the_validation_record_carries_the_pair() -> None:
    shadow = {"paired_valid": True, "candidate_formula_id": fs.CANDIDATE_FORMULA_ID}
    record = build_validation_record({}, [{"event_id": "e1", "key": "bad", "prediction_comparable": True, "shadow_forecast": shadow},
                                          {"event_id": "e2", "key": "bad"}], model_version="m")
    rows = {row["event_id"]: row for row in record["room_results"]}
    assert rows["e1"]["shadow_forecast"] == shadow and rows["e2"]["shadow_forecast"] is None


def test_summary_empty_and_historic_records() -> None:
    assert _summary([])["status"] == "no_data"
    historic = _records([(10, 5)])
    historic[0]["room_results"] = [_room("old", 0, 0, shadow=False)]
    out = _summary(historic)
    assert out["status"] == "no_data" and out["samples"] == 0 and out["production_mae_ml"] is None and out["excluded_total"] == 0


def test_summary_small_numbers_gain_and_loss() -> None:
    one = _summary(_records([(10.0, 6.0)]))
    assert (one["status"], one["samples"], one["production_mae_ml"], one["candidate_mae_ml"]) == ("collecting", 1, 10.0, 6.0)
    assert (one["mae_difference_ml"], one["improvement_percent"]) == (-4.0, 40.0)
    worse = _summary(_records([(10.0, 15.0), (20.0, 25.0)]))
    assert worse["mae_difference_ml"] == 5.0 and worse["improvement_percent"] == pytest.approx(-33.3)
    assert worse["production_wins"] == 2 and worse["candidate_wins"] == 0
    zero = _summary(_records([(0.0, 3.0)]))
    assert zero["improvement_percent"] is None  # no meaningful denominator
    tie = _summary(_records([(10.0, 10.5)]))
    assert tie["ties"] == 1


def test_summary_counts_exclusions_and_each_session_once() -> None:
    records = _records([(10.0, 5.0), (10.0, 5.0)])
    records[1]["room_results"][0]["validation_session_id"] = "s0"  # the same session reported twice
    records.append({"valid": True, "ended_at": "2026-10-01T13:00:00+00:00", "room_results": [
        _room("x1", 0, 0, valid=False, reason="cross_mode_changed"), _room("x2", 0, 0, valid=False, reason="moisture_source"),
        "broken", {"shadow_forecast": "broken"}]})
    out = _summary(records)
    assert out["samples"] == 1 and out["excluded"] == {"cross_mode_changed": 1, "moisture_source": 1} and out["excluded_total"] == 2


def test_evidence_rules_for_better_and_worse() -> None:
    better = _summary(_records([(20.0 + i % 3, 10.0) for i in range(16)], days=4), days=30)
    assert better["status"] == "candidate_better" and better["independent_sessions"] == 16 and better["distinct_days"] == 4
    assert better["ci95_low_ml"] > 0 and better["auto_activation"] is False
    worse = _summary(_records([(10.0, 20.0 + i % 3) for i in range(16)], days=4), days=30)
    assert worse["status"] == "candidate_worse"
    mixed = _summary(_records([(10.0, 5.0) if i % 2 else (10.0, 15.0) for i in range(16)], days=4), days=30)
    assert mixed["status"] == "inconclusive"
    few_days = _summary(_records([(20.0, 10.0)] * 16, days=2), days=30)
    assert few_days["status"] == "collecting"
    clustered = _summary(_records([(20.0, 10.0)] * 16, days=4, per_record=4), days=30)
    assert clustered["independent_sessions"] == 4 and clustered["status"] == "collecting"  # rooms of one airing are not independent


def test_null_model_is_reported_and_gates_better() -> None:
    pairs = [(20.0 + i % 3, 10.0) for i in range(16)]
    better = _summary(_records(pairs, days=4), days=30)
    assert better["null_mae_ml"] == 50.0 and better["candidate_beats_null"] is True and better["production_beats_null"] is True
    assert better["evidence_rules"]["requires_beating_null_model"] is True
    near_zero = _records(pairs, days=4)
    for record in near_zero:
        for room in record["room_results"]:
            room["shadow_forecast"]["null_abs_error_ml"] = 9.5  # "always 0 ml" about as good as the candidate
    held = _summary(near_zero, days=30)
    assert held["status"] == "inconclusive" and held["candidate_beats_null"] is False and held["production_beats_null"] is False
    # pairs from before the null field: derived from the measurement
    legacy = _records([(10.0, 6.0)])
    shadow = legacy[0]["room_results"][0]["shadow_forecast"]
    del shadow["null_abs_error_ml"]
    shadow["measured_removed_ml"] = -12.0
    assert _summary(legacy)["null_mae_ml"] == 12.0
    assert _summary([])["null_mae_ml"] is None


def test_quarantined_pairs_are_counted() -> None:
    records = _records([(10.0, 5.0), (10.0, 5.0)])
    records[1]["room_results"][0]["shadow_forecast"]["opening_learning_quarantined"] = True
    out = _summary(records)
    assert out["samples"] == 2 and out["quarantined_pairs"] == 1


def test_published_summary_survives_a_broken_history() -> None:
    assert fs.published_comparison(None)["status"] == "no_data"
    assert fs.published_comparison(42)["status"] == "unavailable"


def test_learning_kpis_ignore_the_shadow() -> None:
    sample = {"valid": True, "production_abs_error_ml": 5.0, "baseline_abs_error_ml": 8.0, "paired_error_gain_ml": 3.0,
              "winner": "learned", "ended_at": "2026-10-01T12:00:00+00:00"}
    plain = [{"valid": True, "ended_at": "2026-10-01T12:00:00+00:00", "room_results": [{"key": "bad", "comparable": True, "learning_effectiveness": sample}]}]
    with_shadow = [{**plain[0], "room_results": [{**plain[0]["room_results"][0], "shadow_forecast": {"paired_valid": True, "production_abs_error_ml": 1.0, "candidate_abs_error_ml": 99.0}}]}]
    assert learning_effectiveness_summary(plain) == learning_effectiveness_summary(with_shadow)


# --- diagnostics transport ---------------------------------------------------------------------

def test_formula_ids_and_version_survive_the_upload_sanitizer() -> None:
    record = {"shadow_forecast": {"candidate_formula_id": fs.CANDIDATE_FORMULA_ID, "production_formula_id": fs.PRODUCTION_FORMULA_ID,
                                  "freshairiq_version_at_start": "0.26.5.5", "name": "Bad"}}
    room_map = {"r1": "room-abc", "hybrid": "room-def", "curve": "room-ghi", "bad": "room-x"}
    clean = _sanitize_tree(record, room_map)["shadow_forecast"]
    assert clean["candidate_formula_id"] == fs.CANDIDATE_FORMULA_ID and clean["production_formula_id"] == fs.PRODUCTION_FORMULA_ID
    assert clean["freshairiq_version_at_start"] == "0.26.5.5" and "name" not in clean
    # an ID-shaped key never lets free text through unredacted
    assert _sanitize_tree({"candidate_formula_id": "Kontakt binary_sensor.bad"}, room_map)["candidate_formula_id"] != "Kontakt binary_sensor.bad"


# --- no control or learning influence -----------------------------------------------------------

ALLOWED_USERS = {"forecast_shadow.py", "coordinator_room_model.py", "coordinator_session_events.py", "coordinator_decision.py"}


def test_nothing_in_the_control_path_uses_the_shadow() -> None:
    users = {path.name for path in PKG.glob("*.py") if re.search(r"from \.forecast_shadow import|shadow_removed_ml", path.read_text(encoding="utf-8"))}
    assert users == ALLOWED_USERS
    room_model = (PKG / "coordinator_room_model.py").read_text(encoding="utf-8")
    assert "shadow_removed_ml" not in room_model and room_model.count("freeze_shadow_start") == 2  # import + the frozen start only
    for name in ("model.py", "forecast.py", "decision.py", "live_coach.py", "consolidation.py", "notifications.py",
                 "actuator_control.py", "actuator_controller.py", "learning_effectiveness.py", "recommendation.py", "house_strategy.py"):
        assert "shadow_forecast" not in (PKG / name).read_text(encoding="utf-8"), name
