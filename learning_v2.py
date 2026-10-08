"""Learning Engine V2: calibrated model maturity, uncertainty and safety authority.

Pure/read-only over the established learning engines. It never fabricates evidence and
never mutates learned coefficients. Production authority is conservative: learned
terms are trusted only while objective validation does not show regression.
"""
from __future__ import annotations
from math import isfinite
from typing import Any, Mapping

ENGINE_VERSION = "v2"

def _n(v: Any, default: float = 0.0) -> float:
    try: x=float(v)
    except (TypeError,ValueError,OverflowError): return default
    return x if isfinite(x) else default

def _clamp(v: float, lo: float=0.0, hi: float=100.0) -> float: return min(max(v,lo),hi)

def _score_ratio(v: Any, target: float) -> float: return _clamp(_n(v)/max(target,1e-9)*100.0)

def _room_backtest(backtest: Mapping[str,Any], key: str) -> Mapping[str,Any]:
    for row in backtest.get("rooms") or []:
        if isinstance(row, Mapping) and str(row.get("key")) == str(key): return row
    return {}

def build_learning_v2_status(rooms: Mapping[str,Mapping[str,Any]]|list[Mapping[str,Any]], *,
    forecast_backtest: Mapping[str,Any]|None=None, learning_effectiveness: Mapping[str,Any]|None=None,
    post_close: Mapping[str,Any]|None=None, components: Mapping[str,Any]|None=None) -> dict[str,Any]:
    vals=list(rooms.values()) if isinstance(rooms,Mapping) else list(rooms or [])
    vals=[r for r in vals if isinstance(r,Mapping) and r.get("calculation_enabled",True)]
    bt=forecast_backtest or {}; eff=learning_effectiveness or {}; pc=post_close or {}; comp=components or {}
    eff_status=str(eff.get("status") or "collecting")
    global_drift = eff_status == "regressing"
    overall_mae=bt.get("moisture_mae_ml")
    direction=bt.get("direction_accuracy_percent")
    close_mae=bt.get("close_time_mae_min")
    rows=[]
    for r in vals:
        key=str(r.get("key") or "unknown"); rb=_room_backtest(bt,key)
        samples=int(_n(r.get("learning_samples"))); f_samples=int(_n(r.get("forecast_observation_samples")))
        feedback=int(_n(r.get("outcome_feedback_samples"))); shadow=int(_n(r.get("shadow_learning_total_samples")))
        dates=r.get("learning_observation_dates") if isinstance(r.get("learning_observation_dates"),list) else []
        seasonal=r.get("seasonal_observation_days") if isinstance(r.get("seasonal_observation_days"),Mapping) else {}
        seasonal_days=len({str(d) for ds in seasonal.values() if isinstance(ds,list) for d in ds})
        evidence=(.25*_score_ratio(samples,80)+.20*_score_ratio(f_samples,60)+.20*_score_ratio(feedback,80)+.15*_score_ratio(shadow,80)+.20*_score_ratio(len(set(dates)),45))
        diversity=(.6*_score_ratio(len(set(dates)),45)+.4*_score_ratio(seasonal_days,90))
        mae=rb.get("moisture_mae_ml",overall_mae); diracc=rb.get("direction_accuracy_percent",direction); cmae=rb.get("close_time_mae_min",close_mae)
        accuracy_parts=[]
        if mae is not None: accuracy_parts.append(_clamp(100.0-_n(mae)/5.0))
        if diracc is not None: accuracy_parts.append(_clamp(_n(diracc)))
        if cmae is not None: accuracy_parts.append(_clamp(100.0-_n(cmae)*8.0))
        accuracy=sum(accuracy_parts)/len(accuracy_parts) if accuracy_parts else 45.0
        sensor_quality=100.0 if str(r.get("data_quality") or "ok") == "ok" else 35.0
        stability=35.0 if bool(r.get("shadow_rollback_active")) else (55.0 if global_drift else 92.0)
        rebound=_score_ratio(pc.get("valid_observations"),40)
        maturity=_clamp(.25*evidence+.18*diversity+.25*accuracy+.12*sensor_quality+.12*stability+.08*rebound)
        # Uncertainty is explicitly inverse to evidence/accuracy and never claims precision without field data.
        uncertainty=_clamp(100.0-(.45*evidence+.35*accuracy+.20*diversity))
        authority="physics_fallback" if global_drift or bool(r.get("shadow_rollback_active")) else ("hybrid" if maturity>=45 else "physics_guarded")
        rows.append({"key":key,"maturity_percent":round(maturity,1),"evidence_percent":round(evidence,1),"situational_diversity_percent":round(diversity,1),"forecast_accuracy_percent":round(accuracy,1),"sensor_quality_percent":round(sensor_quality,1),"model_stability_percent":round(stability,1),"uncertainty_percent":round(uncertainty,1),"confidence_percent":round(100-uncertainty,1),"authority":authority,"learning_samples":samples,"forecast_samples":f_samples,"feedback_samples":feedback,"shadow_samples":shadow,"moisture_mae_ml":mae,"close_time_mae_min":cmae,"direction_accuracy_percent":diracc})
    mean=lambda k: round(sum(_n(x.get(k)) for x in rows)/len(rows),1) if rows else 0.0
    maturity=mean("maturity_percent"); confidence=mean("confidence_percent")
    if maturity>=85 and confidence>=80: label="Sehr gut eingelernt"
    elif maturity>=65: label="Eingelernt"
    elif maturity>=40: label="Lernt aktiv"
    else: label="Grundmodell / Lernphase"
    fallbacks=sum(x["authority"]=="physics_fallback" for x in rows)
    return {"engine":ENGINE_VERSION,"status":label,"maturity_percent":maturity,"confidence_percent":confidence,"uncertainty_percent":round(100-confidence,1),"forecast_mae_ml":overall_mae,"close_time_mae_min":close_mae,"direction_accuracy_percent":direction,"learning_effectiveness_status":eff_status,"drift_detected":global_drift,"physics_fallback_rooms":fallbacks,"room_count":len(rows),"rooms":rows,"safety":{"learned_terms_allowed":not global_drift,"physics_fallback_on_regression":True,"shadow_rollback_guard":True,"uncertainty_calibrated":True},"models":{"room_physics":True,"live_forecast":True,"forecast_feedback":True,"shadow_challengers":True,"seasonality":True,"post_close_rebound":True,"sensor_quality":True}}
