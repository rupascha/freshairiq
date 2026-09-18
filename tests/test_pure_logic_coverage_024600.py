from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import custom_components.freshairiq.decision as decision
import custom_components.freshairiq.language_confidence as lc
import custom_components.freshairiq.live_coach as live
import custom_components.freshairiq.model as model
import custom_components.freshairiq.validation as validation
import custom_components.freshairiq.routines as routines
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.runtime import set_runtime_coordinator, clear_runtime_coordinator


def _room(**kw):
    r={
        'key':'r','name':'Raum','data_quality':'ok','active':True,'calculation_enabled':True,
        'humidity':65.0,'surface_rh':75.0,'co2':900,'co2_available':True,'humidity_trend_pct_h':0.0,
        'absolute_humidity':11.0,'volume_m3':50.0,'potential_ml':140.0,
        'learned_exchange_rate_per_min':0.05,'airflow_factor':1.0,'temperature':22.0,
        'forecast_temperature_change_c':-0.4,'forecast_cost':0.01,'forecast_confidence':85,
        'forecast_horizon_min':10,'outcome_feedback_samples':4,'outcome_removed_factor':1.0,
        'outcome_temperature_factor':1.0,
    }
    r.update(kw); return r


def test_language_confidence_all_bands_and_house_night_paths():
    assert lc._f('nan', 7)==7 and lc._f(float('inf'),8)==8
    assert lc._avg([])==0
    expected=['grundmodell','beobachtet','muster_erkannt','bestaetigt','eingelernt','sehr_gut_eingelernt','auf_beduerfnisse_optimiert']
    vals=[0,15,30,50,65,80,95]
    assert [lc._band(v)[0] for v in vals]==expected
    base={'kind':'okay','presentation_scope':'house','room_keys':[], 'summary':'Alles gut',
          'decision_brain':{'impact':{'confidence':90},'night_strategy_primary':True,'night_strategy':{'active':True}}}
    rooms={'r':{'active':True,'learning_samples':40,'outcome_feedback_samples':40,'forecast_confidence':90,'measurement_frame_quality':'excellent'}}
    out=lc.adapt_language_confidence(base, rooms, {'night_model_samples':50,'house_strategy_samples':80})
    assert out['language_confidence']['evidence_samples']>=130
    assert out['language_confidence']['maturity_percent']>=45
    assert 'unabhängige Beobachtungen bestätigen' in out['summary']


def test_language_confidence_mid_bands_and_quality_fallbacks():
    rec={'kind':'ventilate','room_keys':['r'],'summary':'Lüften','confidence':70}
    for samples,band in [(5,'grundmodell'),(12,'beobachtet'),(20,'beobachtet'),(28,'muster_erkannt')]:
        room={'learning_samples':samples,'outcome_feedback_samples':samples,'strategy_samples':samples,
              'behaviour_recommendation_opportunities':samples,'behaviour_duration_samples':samples,
              'forecast_confidence':70,'measurement_frame_quality':'mystery'}
        out=lc.adapt_language_confidence(rec, {'r':room})
        assert out['language_confidence']['maturity_band']==band
    close=lc.adapt_language_confidence({'kind':'close','room_keys':['r'],'summary':'Schließen'}, {'r':{'learning_samples':20,'forecast_observation_samples':20,'outcome_feedback_samples':20,'forecast_confidence':30,'measurement_frame_quality':'stale'}})
    assert close['summary'].startswith('Schließen')


def test_live_coach_finite_guard_close_extend_and_shortened():
    assert live._f('nan',3)==3 and live._f(float('inf'),4)==4
    options={**DEFAULT_OPTIONS,'min_duration_min':3,'max_duration_min':20,'min_return_next_5_min_ml':25}
    active=_room(session_elapsed_min=6,session_recommended_duration_min=10,session_predicted_removed_ml=200,
                 result_ml=20,forecast_5_min_moisture_effect_ml=50,forecast_5_min_temperature_change_c=-0.2,
                 forecast_5_min_confidence=80,close_decision_ready=False,outcome_feedback_samples=12)
    rec={'kind':'continue','duration_min':4,'reasons':[]}
    out=live.refine_live_recommendation({'r':active},options,rec)
    assert out['live_coach_state'] in {'extended','on_track','shortened'}
    fast={**active,'result_ml':180,'session_elapsed_min':6,'forecast_5_min_moisture_effect_ml':20}
    out2=live.refine_live_recommendation({'r':fast},options,rec)
    assert out2['live_coach_state']=='shortened'
    ready={**fast,'close_decision_ready':True,'session_elapsed_min':12,'session_recommended_duration_min':10}
    out3=live.refine_live_recommendation({'r':ready},options,rec)
    assert out3['kind']=='close'
    already=live.refine_live_recommendation({'r':active},options,{'kind':'close'})
    assert already['live_coach_remaining_min']==0
    assert live.refine_live_recommendation({},options,rec) is rec


def test_decision_wait_override_now_and_strategy_branches(monkeypatch):
    room=_room(active=False, behaviour_duration_samples=8, behaviour_preferred_duration_min=8.1)
    opts={'min_duration_min':3,'max_duration_min':15,'min_potential_room_ml':100,'high_rh':68,'mould_warn_surface_rh':80,'mould_critical_surface_rh':90,'co2_warn':1000,'co2_critical':1400}
    # low maturity disables strategy bonus
    monkeypatch.setattr(decision,'household_strategy_fit',lambda *a,**k:{'maturity':5,'fit':0.9,'follow':0.9,'success':0.9})
    adj=decision._strategy_adjustment([room],'now',8,20)
    assert adj['strategy_bonus']==0
    d,reason=decision._behaviour_duration(8,[room],opts)
    assert reason and 'bestätigt' in reason
    # zero-current forecast temperature branch
    sim=decision._simulate_ventilation([{**room,'forecast_temperature_change_c':0.0,'forecast_cost':1.0}],5,source_ah=10.0,source_temp_c=22.0)
    assert sim['cost']==0
    # force wait to overrule now and cover forecast/routine explanations
    calls={'n':0}
    def fake_opt(selected, seed, options, pressure, **kwargs):
        calls['n']+=1
        if kwargs.get('source_ah') is not None:
            return 6.0,{'removed_ml':500,'temperature_change_c':-0.1,'cost':0.0,'confidence':90},{'duration_seed_min':8,'duration_optimised_min':6,'extra_5_min_ml':5,'outcome_feedback_samples':4}
        return 8.0,{'removed_ml':20,'temperature_change_c':-1.0,'cost':0.2,'confidence':80},{'duration_seed_min':8,'duration_optimised_min':8,'extra_5_min_ml':5,'outcome_feedback_samples':4}
    monkeypatch.setattr(decision,'_optimise_duration',fake_opt)
    monkeypatch.setattr(decision,'project_generation_ml',lambda *a,**k:(100.0,60.0))
    monkeypatch.setattr(decision,'household_strategy_fit',lambda *a,**k:{'maturity':50,'fit':0.2,'follow':0.8,'success':0.7})
    rec={'kind':'ventilate','room_keys':['r'],'duration_min':8,'reasons':[]}
    out=decision.build_decision_simulation({'r':room},opts,rec,future_outdoor={15:{'absolute_humidity':5,'temperature_c':18,'humidity':50,'confidence':90}},now=datetime(2026,9,14,6))
    assert out['kind']=='wait'
    assert out['decision_refined'] is True
    assert any('Tagesmuster' in x for x in out['reasons'])


def test_model_status_mould_fallback_and_learning_rejections():
    assert model._mould_level(95,80,90)=='Very high'
    assert model._mould_level(85,80,90)=='High'
    assert model._mould_level(75,80,90)=='Elevated'
    assert model._mould_level(65,80,90)=='Slightly elevated'
    assert model._mould_level(50,80,90)=='Low'
    assert [model._learning_status(x) for x in (10,5,3,1,0)]==['Very stable','Stable','Usable','Learning','Base estimate']
    base=dict(key='r',name='R',temperature=20,humidity=58,reference_temperature=15,reference_humidity=55,volume_m3=80,contact_open=True,contact_open_seconds=900,session_active=True,session_elapsed_min=15,session_start_temp=21,learning_rate=0.03,session_fresh_measurements=0)
    bad_future=model.RoomInput(**base,future_reference_temperature_15='bad',future_reference_humidity_15=50)
    res=model.evaluate_room(bad_future,DEFAULT_OPTIONS,False)
    assert res.close_decision_model_fallback
    for kwargs in [
        dict(learning_enabled=False,elapsed_min=5,start_ah=12,end_ah=10,source_ah=8),
        dict(learning_enabled=True,elapsed_min=5,start_ah=8.4,end_ah=8.2,source_ah=8),
        dict(learning_enabled=True,elapsed_min=5,start_ah=12,end_ah=11.98,source_ah=8),
        dict(learning_enabled=True,elapsed_min=100,start_ah=12,end_ah=11.8,source_ah=8),
        dict(learning_enabled=True,elapsed_min=2,start_ah=12,end_ah=6,source_ah=8),
    ]:
        _,_,_,valid=model.update_learning(old_rate=0.03,old_samples=5,max_duration_min=120,**kwargs)
        assert valid is False


class BadRuntimeEntry:
    entry_id='x'
    @property
    def runtime_data(self):
        return None
    @runtime_data.setter
    def runtime_data(self, value):
        raise AttributeError('legacy')


def test_runtime_set_and_clear_use_runtime_data_only():
    hass = SimpleNamespace(data={})
    entry = SimpleNamespace(entry_id="modern", runtime_data=None)
    coordinator = object()
    set_runtime_coordinator(hass, entry, coordinator)
    assert entry.runtime_data is coordinator
    clear_runtime_coordinator(hass, entry)
    assert entry.runtime_data is None

def test_validation_invalid_inputs_and_extreme_repairs():
    assert validation._number({'x':'bad'},'x',3.5)==3.5
    repaired=validation.repair_option_relationships({
        'target_rh':70,'start_rh':60,'high_rh':50,
        'close_delta':3,'min_delta_high_rh':2,'min_delta':1,
        'min_duration_min':20,'max_duration_min':5,
        'mould_warn_surface_rh':100,'mould_critical_surface_rh':90,
        'co2_warn':4000,'co2_critical':3000,
    })
    assert repaired['target_rh']<=repaired['start_rh']<=repaired['high_rh']
    assert repaired['mould_warn_surface_rh']<repaired['mould_critical_surface_rh']
    assert repaired['co2_warn']<repaired['co2_critical']


def test_routines_corrupt_timestamp_maturity_and_zero_projection():
    room={'routine_observation_at':'not-a-date','routine_source_buckets':'bad','routine_response_buckets':'bad'}
    now=datetime(2026,9,14,7)
    assert routines.learn_source_pattern(room,now,2.0)
    routines.learn_response_pattern(room,now,True,12)
    assert routines.response_pattern(room,now)['followed']==1
    assert routines.project_generation_ml([],now,60)==(0.0,0.0)
    assert routines.project_generation_ml([room],now,0)==(0.0,0.0)
    mature={'routine_source_buckets':{'weekday_07':{'rate_ml_min':1,'samples':12}}}
    assert routines.routine_maturity(mature)>0


def test_decision_now_branch_and_prepare_bonus(monkeypatch):
    room=_room(active=False)
    opts={'min_duration_min':3,'max_duration_min':15,'min_potential_room_ml':100,'high_rh':68,'mould_warn_surface_rh':80,'mould_critical_surface_rh':90,'co2_warn':1000,'co2_critical':1400}
    monkeypatch.setattr(decision,'_strategy_adjustment',lambda selected, option_id, duration, pressure:{'strategy_fit':0.5,'strategy_follow_probability':50.0,'strategy_success_probability':50.0,'strategy_maturity':50.0,'strategy_bonus':20.0 if option_id=='now' else -20.0})
    monkeypatch.setattr(decision,'_optimise_duration',lambda *a,**k:(6.0,{'removed_ml':500,'temperature_change_c':-0.1,'cost':0.0,'confidence':90},{'duration_seed_min':15,'duration_optimised_min':6,'extra_5_min_ml':5,'outcome_feedback_samples':4}))
    out=decision.build_decision_simulation({'r':room},opts,{'kind':'ventilate','room_keys':['r'],'duration_min':15,'reasons':[]})
    assert out['selected_option_id']=='now'
    assert out['estimated_removed_ml']>=0
    assert out['decision_refined'] in {True,False}
    prep=decision.build_decision_simulation({'r':room},opts,{'kind':'prepare','room_keys':['r'],'duration_min':8,'reasons':[]})
    assert prep['simulated_options']


def test_runtime_clear_when_domain_storage_absent():
    class Entry:
        entry_id='none'
        runtime_data=None
    hass=SimpleNamespace(data={})
    clear_runtime_coordinator(hass, Entry())
    assert hass.data=={}

def test_routines_mature_bucket_blends_learned_rate():
    now=datetime(2026,9,14,7,0)
    room={'key':'r','forecast_source_rate_ml_min':0.2,
          'routine_source_buckets':{'weekday_07':{'rate_ml_min':1.0,'samples':12}},
          'seasonal_month_buckets':{}}
    generated,maturity=routines.project_generation_ml([room],now,15)
    assert generated>3
    assert maturity>0

def test_runtime_get_missing_runtime_data_raises_clear_error():
    from custom_components.freshairiq.runtime import get_runtime_coordinator
    hass = SimpleNamespace()
    entry = SimpleNamespace(entry_id="missing")
    import pytest
    with pytest.raises(RuntimeError, match="no loaded runtime_data"):
        get_runtime_coordinator(hass, entry)

def test_decision_feedback_confirmation_reason(monkeypatch):
    room=_room(active=False)
    opts={'min_duration_min':3,'max_duration_min':15,'min_potential_room_ml':100,'high_rh':68,'mould_warn_surface_rh':80,'mould_critical_surface_rh':90,'co2_warn':1000,'co2_critical':1400}
    monkeypatch.setattr(decision,'_strategy_adjustment',lambda selected, option_id, duration, pressure:{'strategy_fit':0.5,'strategy_follow_probability':50.0,'strategy_success_probability':50.0,'strategy_maturity':0.0,'strategy_bonus':20.0 if option_id=='now' else -20.0})
    monkeypatch.setattr(decision,'_optimise_duration',lambda *a,**k:(6.0,{'removed_ml':300,'temperature_change_c':-0.1,'cost':0.0,'confidence':90},{'duration_seed_min':6,'duration_optimised_min':6,'extra_5_min_ml':4,'outcome_feedback_samples':4}))
    out=decision.build_decision_simulation({'r':room},opts,{'kind':'ventilate','room_keys':['r'],'duration_min':6,'reasons':[]})
    assert out['selected_option_id']=='now'
