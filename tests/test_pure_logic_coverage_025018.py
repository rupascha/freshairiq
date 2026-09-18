from datetime import datetime
import custom_components.freshairiq.learning_components as lc
import custom_components.freshairiq.language_confidence as lang
from custom_components.freshairiq.house_strategy import learn_house_outcome
from custom_components.freshairiq.routines import learn_source_pattern
from custom_components.freshairiq.seasonality import learn_seasonal_source


def test_new_time_evidence_defensive_storage_paths():
    room={"routine_source_buckets":{}, "routine_observation_dates":"bad"}
    assert learn_source_pattern(room, datetime(2026,9,16,12), 2.0)
    assert room["routine_observation_dates"] == ["2026-09-16"]
    seasonal={"seasonal_source_profiles":{}, "seasonal_observation_days":"bad"}
    learn_seasonal_source(seasonal, datetime(2026,1,10,12), 2.0)
    assert seasonal["seasonal_observation_days"]["2025:winter"] == ["2026-01-10"]
    store={"house_strategy_observation_dates":"bad"}
    events=[{"key":"a","duration_min":10,"removed_ml":100,"predicted_removed_ml":80,"cost":.1}]
    assert learn_house_outcome(store, events, {"a":{"floor":"EG"}}, cross=False, expected_occupants=2, observed_at=datetime(2026,9,16,12))
    assert store["house_strategy_observation_dates"] == ["2026-09-16"]


def test_language_confidence_remaining_voice_paths(monkeypatch):
    rec={"kind":"okay","room_keys":["r"],"summary":"Basis","confidence":90}
    room={"active":True,"learning_samples":80,"outcome_feedback_samples":80,"forecast_confidence":90,"measurement_frame_quality":"excellent"}
    for band in ("bestaetigt","eingelernt","sehr_gut_eingelernt","auf_beduerfnisse_optimiert"):
        monkeypatch.setattr(lang, "_band", lambda maturity, b=band: (b,b))
        monkeypatch.setattr(lang, "_situation_confidence", lambda out, selected: 90)
        out=lang.adapt_language_confidence(rec,{"r":room},{})
        assert out["summary"]
    monkeypatch.setattr(lang, "_band", lambda maturity:("grundmodell","Grundmodell"))
    monkeypatch.setattr(lang, "_situation_confidence", lambda out, selected: 90)
    out=lang.adapt_language_confidence(rec,{"r":room},{})
    assert "hoher Sicherheit" in out["summary"]


def test_learning_component_helpers_and_malformed_calendar_evidence():
    assert lc._status(50, 1, 1) == "Bestätigt"
    assert lc._status(30, 1, 1) == "Muster erkannt"
    row=lc._component("x","X",1,100,1,"d",description="d",extra={"x":1})
    assert row["x"] == 1
    room={"calculation_enabled":True,"seasonal_observation_days":{"badperiod":["bad-date"],"x:spring":["bad-date"]}}
    store={"night_observed_dates":["bad-date"]}
    out=lc.build_learning_components_status({"r":room},store)
    assert out["stage_key"] == "grundmodell"


def _fake_component_factory(maturity=100.0, quality=95.0):
    def fake(key,label,samples,component_maturity,target_samples,detail,**kwargs):
        return {"key":key,"label":label,"samples":samples,"target_samples":target_samples,"maturity_percent":maturity,
                "status":"X","description":kwargs.get("description",""),"detail":detail,
                "observation_only":kwargs.get("observation_only",False),"quality_percent": quality if key=="forecast_validation" else kwargs.get("quality_percent")}
    return fake


def test_overall_validation_caps_and_high_stage_paths(monkeypatch):
    monkeypatch.setattr(lc,"_component",_fake_component_factory())
    # Exercise all validation-depth ceilings and the high-maturity fallback.
    for n in (15,30,75,100):
        out=lc.build_learning_components_status([],{},forecast_backtest={"room_sample_count":n,"reliability":{"score_percent":95}})
        assert out["overall_maturity_percent"] <= 100
    # With all component maturities forced high and strong validation, optimized path is reachable.
    out=lc.build_learning_components_status([],{},forecast_backtest={"room_sample_count":120,"reliability":{"score_percent":95}})
    assert out["stage_key"] == "auf_beduerfnisse_optimiert"


def test_overall_stage_ladder(monkeypatch):
    # Force component evidence to fixed values to execute presentation stage ladder.
    for m, expected in ((20,"beobachtet"),(35,"muster_erkannt"),(50,"bestaetigt"),(70,"eingelernt"),(85,"sehr_gut_eingelernt")):
        monkeypatch.setattr(lc,"_component",_fake_component_factory(maturity=m, quality=95))
        out=lc.build_learning_components_status([],{},forecast_backtest={"room_sample_count":120,"reliability":{"score_percent":95}})
        assert out["stage_key"] == expected

def test_remaining_learning_component_defensive_and_high_fallback(monkeypatch):
    room={"calculation_enabled":True,"seasonal_observation_days":{"2026:spring":["bad-date"]}}
    lc.build_learning_components_status({"r":room},{})
    monkeypatch.setattr(lc,"_component",_fake_component_factory(maturity=100, quality=60))
    lowq=lc.build_learning_components_status([],{},forecast_backtest={"room_sample_count":120,"reliability":{"score_percent":60}})
    assert lowq["overall_maturity_percent"] <= 77.9
    def fake(key,label,samples,component_maturity,target_samples,detail,**kwargs):
        m=80.0 if key=="personal_context" else 100.0
        return {"key":key,"label":label,"samples":samples,"target_samples":target_samples,"maturity_percent":m,
                "status":"X","description":kwargs.get("description",""),"detail":detail,
                "observation_only":kwargs.get("observation_only",False),"quality_percent":95.0 if key=="forecast_validation" else kwargs.get("quality_percent")}
    monkeypatch.setattr(lc,"_component",fake)
    out=lc.build_learning_components_status([],{},forecast_backtest={"room_sample_count":120,"reliability":{"score_percent":95}})
    assert out["stage_key"] == "sehr_gut_eingelernt"
