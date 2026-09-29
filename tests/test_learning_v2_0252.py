import importlib.util
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    p=ROOT/'custom_components/freshairiq'/f'{name}.py'; spec=importlib.util.spec_from_file_location(f'lv2_{name}',p); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m

def test_learning_v2_never_claims_high_maturity_without_evidence():
    fn=load('learning_v2').build_learning_v2_status
    out=fn({"r":{"key":"r","learning_samples":1,"forecast_observation_samples":0,"outcome_feedback_samples":0,"shadow_learning_total_samples":0,"learning_observation_dates":["2026-01-01"],"data_quality":"ok"}})
    assert out["maturity_percent"] < 50 and out["rooms"][0]["authority"] == "physics_guarded"

def test_learning_v2_regression_forces_physics_fallback():
    fn=load('learning_v2').build_learning_v2_status
    room={"key":"r","learning_samples":100,"forecast_observation_samples":100,"outcome_feedback_samples":100,"shadow_learning_total_samples":100,"learning_observation_dates":[f"2026-01-{i:02d}" for i in range(1,29)],"data_quality":"ok"}
    out=fn({"r":room}, learning_effectiveness={"status":"regressing"})
    assert out["drift_detected"] is True and out["safety"]["learned_terms_allowed"] is False and out["rooms"][0]["authority"] == "physics_fallback"

def test_learning_v2_exposes_objective_accuracy_and_uncertainty():
    fn=load('learning_v2').build_learning_v2_status
    room={"key":"r","learning_samples":80,"forecast_observation_samples":60,"outcome_feedback_samples":80,"shadow_learning_total_samples":80,"learning_observation_dates":[f"2026-01-{i:02d}" for i in range(1,29)],"data_quality":"ok"}
    out=fn({"r":room},forecast_backtest={"moisture_mae_ml":25,"direction_accuracy_percent":95,"close_time_mae_min":1.0,"rooms":[]})
    assert out["forecast_mae_ml"] == 25 and 0 <= out["uncertainty_percent"] <= 100

def test_guardian_detects_learning_drift_without_identifiers():
    g=load('guardian').evaluate_guardian({"learning_v2":{"drift_detected":True,"physics_fallback_rooms":2}})
    f=next(x for x in g["findings"] if x["code"]=="FAIQ-GUARDIAN-LEARNING-001")
    assert f["evidence"] == {"physics_fallback_rooms":2}

def test_coordinator_wires_objective_regression_to_physics_fallback():
    text=(ROOT/'custom_components/freshairiq/coordinator.py').read_text()
    assert '_learning_v2_force_physics' in text and 'rate_per_min=(0.03 if _learning_v2_force_physics' in text and 'learned_source_ml_min=(None if _learning_v2_force_physics' in text

def test_learning_v2_uses_room_specific_backtest_when_available():
    fn=load('learning_v2').build_learning_v2_status
    out=fn({"r":{"key":"r","data_quality":"ok"}}, forecast_backtest={"moisture_mae_ml":90,"rooms":[{"key":"r","moisture_mae_ml":10,"direction_accuracy_percent":100,"close_time_mae_min":0.5}]})
    assert out["rooms"][0]["moisture_mae_ml"] == 10

def test_guardian_rejects_high_maturity_with_uncalibrated_confidence():
    g=load('guardian').evaluate_guardian({"learning_v2":{"maturity_percent":90,"confidence_percent":20}})
    assert any(x["code"]=="FAIQ-GUARDIAN-LEARNING-002" for x in g["findings"])
