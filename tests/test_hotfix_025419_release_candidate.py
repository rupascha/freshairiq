from custom_components.freshairiq.recommendation import build_recommendation

def room(key,potential,rh=63,surface=70,co2=None,urgent=False):
    return {"key":key,"name":key,"calculation_enabled":True,"data_quality":"ok","active":False,"action":"Ventilate","realistic_potential_ml":potential,"potential_ml":potential,"delta_g_m3":2.5,"airflow_factor":1.0,"humidity":rh,"surface_rh":95 if urgent else surface,"humidity_high_duration_min":30,"co2_available":co2 is not None,"co2":co2,"goal_state":{"goals":[{"id":"humidity","active":True,"reached":False,"achievable_now":True}]},"ventilation_threshold_effective_ml":100}

def opts(): return {"high_rh":68,"start_rh":62,"mould_warn_surface_rh":80,"mould_critical_surface_rh":90,"co2_warn":1000,"co2_critical":1400,"min_potential_room_ml":100}

def test_house_ready_aggregates_meaningful_rooms_instead_of_single_problem_room():
    rooms={"lager":room("lager",230,69),"wohn":room("wohn",180),"bad":room("bad",160),"schlaf":room("schlaf",150)}
    rec=build_recommendation(rooms,opts(),threshold_ml=500,total_potential_ml=720,recommended_duration_min=10)
    assert rec["kind"]=="ventilate"
    assert len(rec["room_keys"]) >= 2
    assert sum(rooms[k]["potential_ml"] for k in rec["room_keys"]) >= 500
    assert rec["recommendation_scope"] in {"house","floor"}

def test_urgent_room_still_overrides_house_aggregation():
    rooms={"kritisch":room("kritisch",120,75,urgent=True),"wohn":room("wohn",250),"bad":room("bad",220)}
    rec=build_recommendation(rooms,opts(),threshold_ml=400,total_potential_ml=590,recommended_duration_min=10)
    assert rec["room_keys"]==["kritisch"]

def test_learning_modes_are_explicitly_separate_in_coordinator_source():
    src=open('custom_components/freshairiq/coordinator.py').read() + open('custom_components/freshairiq/recommendation.py').read()
    assert 'session_mode in {"open", "tilted", "cross", "mechanical_exhaust"}' in src
    assert 'opening_learning[session_mode]' in src
    assert 'session_opening_mode_mixed' in src

def test_cover_boundary_and_user_hint_contract():
    src=open('custom_components/freshairiq/coordinator.py').read() + open('custom_components/freshairiq/recommendation.py').read()
    assert 'if closed_pct > threshold:' in src
    assert 'für bessere Lüftungswirkung weiter öffnen' in src
    assert 'session_cover_learning_blocked' in src

def test_all_rendered_room_sensor_fields_have_de_en_title_and_description():
    import json
    from pathlib import Path
    de=json.loads(Path('custom_components/freshairiq/translations/de.json').read_text())
    en=json.loads(Path('custom_components/freshairiq/translations/en.json').read_text())
    keys=['co2','exhaust_fan','climate','target_temperature_mode','target_temperature','target_temperature_fallback']
    # Search recursively: each key must occur as a non-empty label and description in both locales.
    def values(obj, key, parent=None):
        out=[]
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k==key and isinstance(v,str) and v.strip(): out.append((parent,v))
                out += values(v,key,k)
        elif isinstance(obj,list):
            for v in obj: out += values(v,key,parent)
        return out
    for key in keys:
        assert values(de,key), ('de',key)
        assert values(en,key), ('en',key)


def test_running_session_surfaces_restricted_cover_guidance():
    r=room("wohn",180)
    r.update({"active":True,"action":"Continue ventilating","forecast_moisture_effect_ml":80,"forecast_horizon_min":5,"session_elapsed_min":2,"cover_learning_blocked":True,"cover_learning_guard":{"affected":[{"closed_percent":35}]}})
    rec=build_recommendation({"wohn":r},opts(),threshold_ml=100,total_potential_ml=180,recommended_duration_min=10)
    assert rec["kind"]=="continue"
    assert any("Rollo/Jalousie teilweise geschlossen (35 %)" in x for x in rec["reasons"])
    assert any("nicht als normale Lernprobe" in x for x in rec["reasons"])
