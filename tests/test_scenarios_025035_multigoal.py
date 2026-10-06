from custom_components.freshairiq.goals import effective_temperature_target,evaluate_goals

def G(**kw):
    base=dict(humidity=55,target_rh=60,co2=800,co2_warn=1000,temperature=21,temperature_target=20,
              humidity_rate_pct_min=-.2,co2_rate_ppm_min=-50,temperature_rate_c_min=-.2,priorities=['humidity','co2','temperature'])
    base.update(kw); return evaluate_goals(**base)

def row(x,k): return next(r for r in x['goals'] if r['id']==k)

def test_scenario_all_targets_reached():
    x=G(temperature=20.2); assert x['all_active_goals_reached']

def test_scenario_co2_keeps_goal_open_after_humidity_target():
    x=G(co2=1300,priorities=['co2','humidity','temperature']); assert x['highest_open_goal']=='co2' and row(x,'co2')['eta_min']==6

def test_scenario_temperature_goal_open_after_air_quality_is_good():
    x=G(temperature=24,temperature_target=20); assert row(x,'temperature')['eta_min']==20

def test_scenario_safety_close_flag_does_not_falsify_goal_completion():
    x=G(co2=1300,hard_close=True); assert x['hard_close'] and not row(x,'co2')['reached']

def test_scenario_frost_protection_does_not_replace_session_snapshot():
    assert effective_temperature_target(session_target=21,thermostat_target=5,fallback=20)==(21.0,'session')

def test_scenario_summer_off_uses_manual_fallback():
    assert effective_temperature_target(thermostat_target=None,fallback=20)==(20.0,'fallback')

def test_scenario_no_summer_target_is_invented():
    assert effective_temperature_target(thermostat_target=None,fallback=None)==(None,'none')

def test_scenario_priority_changes_conflict_order_not_goal_truth():
    a=G(co2=1300,temperature=23,priorities=['co2','temperature','humidity'])
    b=G(co2=1300,temperature=23,priorities=['temperature','co2','humidity'])
    assert a['highest_open_goal']=='co2' and b['highest_open_goal']=='temperature'
