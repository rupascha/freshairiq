from custom_components.freshairiq.recommendation import build_recommendation
from custom_components.freshairiq.live_coach import refine_live_recommendation

OPTS={"start_rh":62,"high_rh":68,"co2_warn":1000,"co2_critical":1400,"min_potential_room_ml":100,"max_temp_loss_next_5_min_c":1.5}

def room(**kw):
    x={"key":"bed","name":"Schlafzimmer","data_quality":"ok","calculation_enabled":True,"active":False,"action":"Wait","humidity":55,"surface_rh":60,"co2":None,"co2_available":False,"delta_g_m3":-1.0,"realistic_potential_ml":0,"airflow_factor":1.0,"goal_state":{"priorities":[],"goals":[],"hard_close":False}}
    x.update(kw); return x

def rec(r,total=0):
    return build_recommendation({"bed":r},OPTS,threshold_ml=500,total_potential_ml=total,recommended_duration_min=10)

def test_co2_can_trigger_even_when_outdoor_air_is_wetter():
    r=room(co2=1200,co2_available=True,goal_state={"priorities":["co2","humidity"],"hard_close":False,"goals":[{"id":"co2","active":True,"reached":False,"achievable_now":True,"eta_min":6},{"id":"humidity","active":True,"reached":True,"achievable_now":False,"eta_min":0}]})
    out=rec(r,-100)
    assert out["kind"]=="ventilate"
    text=" ".join([out.get("summary","")]+out.get("reasons",[]))
    assert "CO₂" in text
    assert "würde das Problem nicht verbessern" not in text

def test_temperature_can_trigger_with_zero_moisture_potential():
    r=room(action="Ventilate for cooling",goal_state={"priorities":["temperature"],"hard_close":False,"goals":[{"id":"temperature","active":True,"reached":False,"achievable_now":True,"eta_min":15}]})
    out=rec(r,0)
    assert out["kind"]=="ventilate"
    assert "Temperaturkomfort" in " ".join(out.get("reasons",[]))

def test_hard_close_beats_open_goal_eta_in_live_coach():
    r=room(active=True,action="Continue ventilating",close_decision_ready=True,session_elapsed_min=6,session_recommended_duration_min=10,forecast_5_min_temperature_change_c=-0.2,forecast_5_min_moisture_effect_ml=80,volume_m3=40,goal_state={"priorities":["co2"],"hard_close":True,"goals":[{"id":"co2","active":True,"reached":False,"achievable_now":True,"eta_min":4}]})
    base={"kind":"continue","status":"ventilation_running","title":"Weiterlüften","instruction":"offen lassen","reasons":[]}
    out=refine_live_recommendation({"bed":r},OPTS,base)
    assert out["kind"]=="close"
    assert out["live_coach_state"]=="protection_close"
    assert out["live_coach_remaining_min"]==0
    assert "4 min" in out["live_coach_reason"]

def test_missing_co2_goal_cannot_influence_decision():
    r=room(co2=None,co2_available=False,goal_state={"priorities":["humidity"],"hard_close":False,"goals":[{"id":"humidity","active":True,"reached":True,"achievable_now":False,"eta_min":0}]})
    out=rec(r,0)
    assert out["kind"]=="okay"
    assert "CO₂" not in " ".join([out.get("summary","")]+out.get("reasons",[]))
