from custom_components.freshairiq.decision_trace import build_decision_trace, build_recommendation_quality


def test_trace_is_observational_and_records_final_decision():
    rooms = {"bath": {"name": "Bad"}}
    rec = {
        "kind": "continue", "status": "ventilation_running", "presentation_scope": "floor",
        "room_keys": ["bath"], "duration_min": 12,
        "title": "Etagenlüftung läuft", "instruction": "Weiterlüften",
        "decision_brain": {"headline": "Etagenlüftung läuft", "action_line": "Weiterlüften", "decision_label": "ETAGENLÜFTUNG", "impact": {"confidence": 82}},
    }
    before = dict(rec)
    trace = build_decision_trace(rec, rooms, validation={"valid_record_count": 14, "direction_accuracy_percent": 90, "moisture_mae_ml": 18})
    assert rec == before
    assert trace["observational_only"] is True
    assert trace["final"]["kind"] == "continue"
    assert trace["final"]["scope"] == "floor"
    assert trace["invariants"]["final_action_matches_brain"] is True
    assert trace["evidence"]["overrides"][0]["strategy"] == "floor_aggregation"


def test_quality_requires_real_validation_evidence():
    assert build_recommendation_quality({"valid_record_count": 4})["evidence_level"] == "insufficient"
    q = build_recommendation_quality({"valid_record_count": 12, "direction_accuracy_percent": 85, "moisture_mae_ml": 20})
    assert q["evidence_level"] == "established"
    assert q["calibrated"] is True


def test_trace_exposes_night_strategy_as_winner_or_suppressed():
    rooms = {}
    rec = {"kind": "okay", "status": "ok", "decision_brain": {"night_strategy": {"active": True, "action": "close"}, "night_strategy_primary": False}}
    trace = build_decision_trace(rec, rooms)
    assert trace["evidence"]["overrides"][0] == {"strategy": "night_strategy", "active": True, "won": False, "action": "close"}


def test_quality_evidence_levels_and_optional_metrics():
    developing = build_recommendation_quality({"valid_record_count": 5, "close_time_mae_min": 1.25, "timeline_improvement_percent": 7.5})
    assert developing["evidence_level"] == "developing"
    assert developing["close_time_mae_min"] == 1.25
    assert developing["timeline_improvement_percent"] == 7.5
    strong = build_recommendation_quality({"valid_record_count": 30})
    assert strong["evidence_level"] == "strong"


def test_trace_candidates_fallback_confidence_and_safety_overrides():
    rooms = {"r": {"name": "R"}}
    rec = {
        "kind": "pollen_wait", "status": "passive_open_monitor", "room_keys": ["r"],
        "forecast_confidence": 73, "selected_option_id": "now",
        "simulated_options": [None, {"id": "now", "score": 4.2, "removed_ml": 22, "confidence": 70}],
        "day_night_plan": {"selected_option_id": "later", "confidence": 66, "options": [None, {"id": "later", "score": 5, "projected_potential_ml": 31}]},
    }
    trace = build_decision_trace(rec, rooms)
    assert trace["final"]["confidence"] == 73
    assert len(trace["evidence"]["candidates"]) == 2
    strategies = {x["strategy"] for x in trace["evidence"]["overrides"]}
    assert {"passive_open_monitor", "pollen_veto"} <= strategies


def test_trace_sensor_override_and_invalid_input_are_safe():
    trace = build_decision_trace({"kind": "sensor", "room_keys": ["missing"]}, {})
    assert trace["evidence"]["overrides"][0]["strategy"] == "sensor_safety"
    assert trace["invariants"]["selected_rooms_exist"] is False
    empty = build_decision_trace(None, {})
    assert empty["final"]["kind"] == "okay"
