from custom_components.freshairiq.goals import effective_temperature_target,evaluate_goals,normalise_priorities

def test_priority_is_complete_and_stable():
    assert normalise_priorities(["co2","temperature"]) == ["co2","temperature","humidity"]

def test_frost_protection_is_not_comfort_target():
    assert effective_temperature_target(thermostat_target=5,fallback=20)==(20.0,"fallback")

def test_session_snapshot_survives_window_automation():
    assert effective_temperature_target(session_target=21,thermostat_target=5)==(21.0,"session")

def test_parallel_goal_tracker_and_eta():
    x=evaluate_goals(humidity=55,target_rh=60,co2=1300,co2_warn=1000,temperature=22,temperature_target=20,
        co2_rate_ppm_min=-50,temperature_rate_c_min=-.25,priorities=["co2","temperature","humidity"])
    assert x["goals"][0]["id"]=="co2" and x["goals"][0]["eta_min"]==6.0
    assert x["goals"][1]["eta_min"]==8.0
    assert x["goals"][2]["reached"] is True

def test_no_temperature_target_when_all_sources_invalid():
    assert effective_temperature_target(manual=None,session_target=None,thermostat_target=5,fallback=None)==(None,"none")

def test_live_coach_extends_for_achievable_priority_goal():
    from custom_components.freshairiq.live_coach import refine_live_recommendation
    room={"calculation_enabled":True,"data_quality":"ok","active":True,"session_elapsed_min":5,
          "session_recommended_duration_min":5,"result_ml":50,"forecast_5_min_moisture_effect_ml":0,
          "forecast_5_min_temperature_change_c":-.2,"volume_m3":40,"forecast_5_min_confidence":80,
          "close_decision_ready":True,"surface_rh":60,"co2_available":True,"co2":1200,
          "goal_state":{"goals":[{"id":"co2","active":True,"reached":False,"achievable_now":True,"eta_min":4}]}}
    out=refine_live_recommendation({"r":room},{"min_duration_min":3,"max_duration_min":20,"min_return_next_5_min_ml":25,
        "max_temp_loss_next_5_min_c":1.5,"mould_critical_surface_rh":90,"co2_critical":1400},{"kind":"continue","duration_min":1,"reasons":[]})
    assert out["live_coach_state"]=="goal_extended" and out["duration_min"]>0

def test_candidate_priority_goal_adds_soft_score_only():
    from custom_components.freshairiq.recommendation import _candidate
    base={"key":"r","name":"Room","humidity":55,"surface_rh":60,"co2_available":True,"co2":1200,
          "humidity_trend_pct_h":0,"humidity_high_duration_min":0,"realistic_potential_ml":20,"delta_g_m3":1,
          "airflow_factor":1,"next_5_min_cost":0,"temp_next_5_min_c":-.1,"action":"Wait","mould_level":"Low"}
    a=_candidate(dict(base),{"co2_warn":1000,"co2_critical":1400},500)
    b=_candidate(dict(base,goal_state={"goals":[{"id":"co2","active":True,"reached":False,"achievable_now":True}]}),{"co2_warn":1000,"co2_critical":1400},500)
    assert b.score>a.score
