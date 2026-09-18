from pathlib import Path
from custom_components.freshairiq.recommendation import build_recommendation

ROOT = Path(__file__).resolve().parents[1]


def _options():
    return {"start_rh":62.0,"high_rh":68.0,"mould_warn_surface_rh":80.0,"mould_critical_surface_rh":90.0,"co2_warn":1000.0,"co2_critical":1400.0,"min_potential_room_ml":100.0,"cross_ventilation_pairs":""}


def _room(threshold):
    return {"key":"bath","name":"Badezimmer","calculation_enabled":True,"data_quality":"ok","active":False,"action":"Ventilate","humidity":70,"surface_rh":60,"mould_level":"Low","co2":500,"potential_ml":80,"realistic_potential_ml":80,"delta_g_m3":2.0,"airflow_factor":1.0,"temp_next_5_min_c":-0.2,"next_5_min_cost":0.0,"humidity_trend_pct_h":0,"humidity_high_duration_min":30,"ventilation_threshold_effective_ml":threshold}


def test_per_room_threshold_changes_nonurgent_targeting():
    blocked = build_recommendation({"bath":_room(120)}, _options(), threshold_ml=500, total_potential_ml=80, recommended_duration_min=8)
    allowed = build_recommendation({"bath":_room(50)}, _options(), threshold_ml=500, total_potential_ml=80, recommended_duration_min=8)
    assert blocked["kind"] == "wait"
    assert allowed["kind"] == "ventilate"


def test_health_override_is_not_blocked_by_high_room_threshold():
    r=_room(1000); r["surface_rh"]=95; r["mould_level"]="Critical"
    out=build_recommendation({"bath":r}, _options(), threshold_ml=500, total_potential_ml=80, recommended_duration_min=8)
    assert out["kind"] == "ventilate"


def test_floor_localisation_and_threshold_ui_are_present():
    coordinator=(ROOT/'custom_components/freshairiq/coordinator.py').read_text(encoding='utf-8')
    card=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')
    assert '"ground_floor": "Erdgeschoss"' in coordinator
    assert 'threshold-mode-direct' in card
    assert 'room-threshold-mode' in card
