from custom_components.freshairiq.consolidation import stabilise_recommendation
from custom_components.freshairiq.decision_brain import build_unified_decision


def _options():
    return {"min_duration_min": 3, "max_duration_min": 30}


def _room(*, ready=False, close=False):
    return {
        "key": "room", "name": "Raum", "data_quality": "ok",
        "calculation_enabled": True, "active": True,
        "close_decision_ready": ready, "close_recommended": close,
        "action": "Close" if close else "Ventilating",
        "delta_g_m3": 2.0, "realistic_potential_ml": 50,
    }


def _finalise(rec, rooms):
    rec = stabilise_recommendation(rec, rooms, _options())
    return build_unified_decision(rec, rooms, _options(), cross_active=False)


def test_unreleased_close_is_consistent_everywhere():
    out = _finalise({
        "kind": "close", "room_keys": ["room"], "duration_min": 0,
        "title": "Jetzt schließen", "instruction": "Schließen",
        "severity": "warning", "live_coach_state": "close",
        "live_coach_reason": "Endpunkt", "live_coach_remaining_min": 0,
    }, {"room": _room(ready=False)})
    assert out["kind"] == "continue"
    assert out["decision_brain"]["decision_label"] == "WEITERLÜFTEN"
    assert "SCHLIESSEN" not in out["decision_brain"]["decision_label"]
    assert out["decision_brain"]["selected_rooms"] == ["Raum"]
    assert out["severity"] == "good"
    assert out["live_coach_state"] == "awaiting_measurements"
    assert out["duration_min"] is None
    assert out["decision_brain"]["impact"]["duration_min"] is None


def test_released_close_is_consistent_everywhere():
    out = _finalise({
        "kind": "close", "room_keys": ["room"], "duration_min": 4,
    }, {"room": _room(ready=True)})
    assert out["kind"] == "close"
    assert out["duration_min"] == 0.0
    assert out["decision_brain"]["decision_label"] == "JETZT SCHLIESSEN"
    assert out["decision_brain"]["impact"]["duration_min"] == 0.0


def test_authoritative_room_close_rebuilds_brain_after_consolidation():
    out = _finalise({
        "kind": "continue", "room_keys": ["room"], "duration_min": 1.0,
    }, {"room": _room(ready=True, close=True)})
    assert out["kind"] == "close"
    assert out["decision_brain"]["decision_label"] == "JETZT SCHLIESSEN"
    assert out["decision_brain"]["impact"]["duration_min"] == 0.0


def test_active_remaining_time_is_not_raised_to_minimum():
    out = _finalise({
        "kind": "continue", "room_keys": ["room"], "duration_min": 0.5,
        "live_coach_remaining_min": 0.5, "live_coach_target_min": 8.0,
    }, {"room": _room(ready=True)})
    assert out["kind"] == "continue"
    assert out["duration_min"] == 0.5
    assert out["decision_brain"]["decision_label"] == "WEITERLÜFTEN"
    assert out["decision_brain"]["impact"]["duration_min"] == 0.5


def test_preventilate_night_strategy_can_be_primary_only_when_no_urgent_action():
    ns = {
        "active": True, "action": "pre_ventilate", "label": "NACHT · VORHER LÜFTEN",
        "headline": "Trockene Nachtluft nutzen, aber nicht dauerhaft",
        "instruction": "Vor dem Schlafengehen 15 Minuten stoßlüften und danach schließen",
        "summary": "Dauerlüftung würde zu stark auskühlen.",
        "reasons": ["Nachtluft ist trockener", "Dauerlüftung kühlt zu stark aus"],
        "selected_rooms": ["Schlafzimmer"],
        "confidence": 82,
    }
    out = build_unified_decision({"kind": "okay", "room_keys": []}, {}, _options(), night_strategy=ns)
    assert out["decision_brain"]["night_strategy_primary"] is True
    assert out["decision_brain"]["decision_label"] == "NACHT · VORHER LÜFTEN"
    assert "15 Minuten" in out["decision_brain"]["action_line"]
    assert out["decision_brain"]["selected_rooms"] == ["Schlafzimmer"]


def test_night_strategy_never_overrides_immediate_close():
    ns = {
        "active": True, "action": "pre_ventilate", "label": "NACHT · VORHER LÜFTEN",
        "instruction": "Vor dem Schlafengehen lüften", "confidence": 95,
    }
    out = build_unified_decision({"kind": "close", "room_keys": ["room"], "duration_min": 0}, {"room": _room(ready=True)}, _options(), night_strategy=ns)
    assert out["decision_brain"]["night_strategy_primary"] is False
    assert out["decision_brain"]["decision_label"] == "JETZT SCHLIESSEN"
