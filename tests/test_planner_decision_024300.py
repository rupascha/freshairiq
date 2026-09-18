"""Coverage and behavioural contracts for planner + unified decision brain."""
from __future__ import annotations
from datetime import datetime, timezone

from custom_components.freshairiq.planner import build_multi_hour_plan, refine_with_plan
from custom_components.freshairiq.decision_brain import build_unified_decision


def room(name="Wohnzimmer", **kw):
    base = {
        "name": name, "calculation_enabled": True, "data_quality": "ok", "active": False,
        "humidity": 72, "surface_rh": 82, "co2": 1300, "co2_available": True,
        "realistic_potential_ml": 280, "potential_ml": 500, "delta_g_m3": 2.5,
        "absolute_humidity": 11.0, "temperature": 22.0, "volume_m3": 60,
    }
    base.update(kw)
    return base


def opts(**kw):
    base = {"high_rh": 68, "mould_warn_surface_rh": 80, "co2_warn": 1000, "min_potential_total_ml": 500}
    base.update(kw)
    return base


def test_planner_inactive_when_no_closed_rooms():
    now = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
    plan = build_multi_hour_plan({"a": room(active=True)}, opts(), now)
    assert plan["active"] is False


def test_planner_builds_future_matrix_and_hysteresis():
    now = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
    future = {
        30: {"absolute_humidity": 10.5, "temperature_c": 21, "confidence": 80, "source":"weather"},
        60: {"absolute_humidity": 8.0, "temperature_c": 20, "confidence": 90, "source":"weather"},
        120: {"absolute_humidity": 6.0, "temperature_c": 19, "confidence": 90, "source":"weather"},
        130: {"absolute_humidity": 6.0, "temperature_c": 19, "confidence": 90, "source":"weather"}, # filtered: not hourly
    }
    plan = build_multi_hour_plan({"a": room(humidity=62, surface_rh=60, co2=700)}, opts(), now, future_outdoor=future, horizon_hours=4)
    assert plan["active"]
    assert any(o["id"] == "in_60" for o in plan["options"])
    assert all(o["id"] != "in_130" for o in plan["options"])
    assert 2 <= plan["horizon_hours"] <= 12


def test_planner_after_night_candidate_and_low_theoretical_fallback():
    now = datetime(2026, 9, 14, 20, tzinfo=timezone.utc)
    r = room(potential_ml=0, realistic_potential_ml=20, humidity=55, surface_rh=60, co2=None, co2_available=False)
    plan = build_multi_hour_plan({"a": r}, opts(), now, night_forecast_ml=800, night_confidence=75)
    candidate = next(o for o in plan["options"] if o["id"] == "after_night")
    assert candidate["ventilation_capture_fraction"] == 0.12
    assert candidate["confidence"] == 75


def test_refine_with_plan_respects_realtime_authority_and_future_wait():
    active_future = {"active":True,"selected_option_id":"in_60","selected_delay_min":60,"confidence":80,"selected_label":"In 1 h","summary":"Später besser"}
    out = refine_with_plan({"kind":"okay","reasons":[]}, active_future)
    assert out["kind"] == "wait" and out["planner_action"] is True
    assert "1 h" in out["instruction"]
    protected = refine_with_plan({"kind":"close"}, active_future)
    assert protected["kind"] == "close" and "planner_action" not in protected
    after = refine_with_plan({"kind":"prepare"}, {"active":True,"selected_option_id":"after_night","confidence":80,"summary":"Nacht besser"})
    assert after["kind"] == "wait" and "Nacht" in after["title"]
    inactive = refine_with_plan({"kind":"okay"}, {"active":False})
    assert inactive["kind"] == "okay"


def _base_rec(kind, **kw):
    rec = {
        "kind": kind, "room_keys":["a"], "title":"Alt", "instruction":"Alt", "summary":"Alt",
        "duration_min":10, "estimated_removed_ml":150, "expected_temperature_change_c":-0.5,
        "estimated_reheat_cost":0.05, "forecast_confidence":70, "reasons":["bestehender Grund"],
    }
    rec.update(kw)
    return rec


def test_decision_brain_covers_immediate_kinds_and_cross_ventilation():
    rooms = {"a": room("Bad"), "b": room("Küche")}
    vent = build_unified_decision(_base_rec("ventilate", room_keys=["a","b"]), rooms, opts(), cross_active=True)
    assert vent["decision_brain"]["decision_label"] == "JETZT QUERLÜFTEN"
    assert vent["decision_brain"]["cross_ventilation"] is True
    for kind, label in [
        ("continue","WEITERLÜFTEN"), ("close","JETZT SCHLIESSEN"),
        ("pollen_wait","VERSCHIEBEN"), ("sensor","SENSORDATEN PRÜFEN"),
        ("prepare","VORLÜFTEN"), ("okay","WEITER BEOBACHTEN"),
    ]:
        rec = _base_rec(kind)
        if kind == "continue": rec.update(live_coach_target_min=12, live_coach_remaining_min=4, live_coach_reason="Live gut")
        out = build_unified_decision(rec, {"a":rooms["a"]}, opts())
        assert out["decision_brain"]["decision_label"] == label
        assert out["decision_brain_engine"] == "v1"


def test_decision_brain_wait_comparison_house_learning_and_night_primary():
    rooms={"a":room("Schlafzimmer", humidity=60, surface_rh=65, co2=700)}
    rec=_base_rec("wait", simulated_options=[
        {"id":"now","score":20,"removed_ml":50,"confidence":70},
        {"id":"wait_30","score":40,"removed_ml":140,"delay_min":30,"label":"In 30 min","confidence":80},
    ], selected_option_id="wait_30", day_night_plan={"active":True,"selected_option_id":"wait_30","selected_delay_min":30,"confidence":80,"options":[{"id":"wait_30","delay_min":30,"removed_ml":140,"label":"In 30 min"}]}, house_strategy={"maturity":40,"efficiency_factor":1.15})
    out=build_unified_decision(rec, rooms, opts())
    assert out["decision_brain"]["decision_label"] == "NOCH WARTEN"
    assert out["decision_brain"]["comparison"]["future_ml"] == 140

    night={"active":True,"action":"open_selected","label":"NACHTLÜFTUNG","headline":"Nachtfenster","instruction":"Fenster öffnen","summary":"Jetzt nachts gut","reasons":["Außen kühl"],"confidence":91,"selected_rooms":["Schlafzimmer"]}
    nout=build_unified_decision(_base_rec("okay"), rooms, opts(), night_strategy=night)
    assert nout["decision_brain"]["night_strategy_primary"] is True
    assert nout["title"] == "Nachtfenster"

def test_decision_brain_additional_comparison_and_wait_branches():
    rooms={"a":room("Keller", humidity=60, surface_rh=65, co2=1500, co2_available=True)}
    rec=_base_rec("ventilate", simulated_options=[
        {"id":"now","score":45,"removed_ml":180},
        {"id":"wait_15","score":30,"removed_ml":120,"label":"In 15 min"},
        {"id":"wait_30","score":35,"removed_ml":150,"label":"In 30 min"},
    ], selected_option_id="now", house_strategy={"maturity":50,"efficiency_factor":0.8})
    out=build_unified_decision(rec, rooms, opts())
    assert out["decision_brain"]["comparison"]["alternative_label"] == "In 30 min"
    assert any("weniger effizient" in reason for reason in out["reasons"])
    assert any("CO₂" in reason for reason in out["reasons"])

    gain=build_unified_decision(_base_rec("wait", status="moisture_gain", summary="Außen feuchter"), rooms, opts())
    assert gain["decision_brain"]["decision_label"] == "FENSTER GESCHLOSSEN LASSEN"
    generic=build_unified_decision(_base_rec("wait"), rooms, opts())
    assert generic["decision_brain"]["decision_label"] == "NOCH WARTEN"
