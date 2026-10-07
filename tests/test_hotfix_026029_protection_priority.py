from custom_components.freshairiq.recommendation import build_recommendation

OPTS={"start_rh":62,"high_rh":68,"mould_warn_surface_rh":80,"mould_critical_surface_rh":90,"co2_warn":1000,"co2_critical":1400,"close_delta":0.4,"min_potential_room_ml":100}

def room(**kw):
    r={"key":"r","name":"Raum","calculation_enabled":True,"data_quality":"ok","active":False,"action":"Do not ventilate","humidity":55,"surface_rh":60,"mould_level":"Low","co2":500,"co2_available":True,"delta_g_m3":-0.5,"realistic_potential_ml":-40,"potential_ml":0,"forecast_temperature_change_c":-0.2,"forecast_cost":0,"forecast_confidence":80,"goal_state":{"goals":[],"hard_close":False}}
    r.update(kw); return r

def build(r, **kw):
    return build_recommendation({"r":r}, OPTS, threshold_ml=500,total_potential_ml=kw.pop("total",0),recommended_duration_min=kw.pop("duration",10),**kw)

def test_critical_co2_cannot_disappear_behind_do_not_ventilate():
    out=build(room(co2=1800, delta_g_m3=-1.2, realistic_potential_ml=-80))
    assert out["kind"]=="ventilate" and out["status"]=="critical_co2"
    assert out["duration_min"]==5.0
    assert "CO₂ 1800" in " ".join(out["reasons"])
    assert "feuchter" in " ".join(out["reasons"])

def test_critical_co2_overrides_pollen_but_discloses_conflict():
    out=build(room(co2=1700, delta_g_m3=1.0, realistic_potential_ml=80), pollen_blocked=True,pollen_index=7)
    assert out["kind"]=="ventilate" and out["duration_min"]==5.0
    assert "Pollenindex 7.0" in " ".join(out["reasons"])

def test_critical_co2_uses_normal_duration_without_conflict():
    out=build(room(co2=1600, action="Ventilate",delta_g_m3=2.0,realistic_potential_ml=120,forecast_temperature_change_c=-0.3),duration=8)
    assert out["kind"]=="ventilate" and out["duration_min"]==8.0

def test_critical_mould_with_wetter_outside_warns_but_does_not_ventilate():
    out=build(room(surface_rh=93,humidity=78,delta_g_m3=-0.8,realistic_potential_ml=-100))
    assert out["kind"]=="wait" and out["status"]=="critical_mould_wait"
    assert out["severity"]=="danger"
    assert "kritisch" in out["title"].lower()

def test_critical_mould_with_real_drying_effect_ventilates_even_if_legacy_action_waits():
    out=build(room(surface_rh=93,humidity=78,delta_g_m3=2.2,realistic_potential_ml=160))
    assert out["kind"]=="ventilate" and out["status"]=="critical_mould"
    assert out["estimated_removed_ml"]==160

def test_critical_mould_hard_close_is_not_overridden():
    out=build(room(surface_rh=94,delta_g_m3=2.0,realistic_potential_ml=150,goal_state={"goals":[],"hard_close":True}))
    assert out["kind"]=="wait" and out["status"]=="critical_mould_wait"
    assert "Schutzgrenze" in " ".join(out["reasons"])

def test_co2_wins_when_co2_and_mould_are_both_critical_and_outside_is_wetter():
    out=build(room(co2=1900,surface_rh=94,humidity=80,delta_g_m3=-1.0,realistic_potential_ml=-90))
    assert out["status"]=="critical_co2" and out["kind"]=="ventilate"
    assert out["duration_min"]==5.0

def test_running_critical_co2_does_not_get_closed_by_legacy_close_signal():
    out=build(room(co2=1850,active=True,action="Close",close_recommended=True,delta_g_m3=-0.6,realistic_potential_ml=-40))
    assert out["kind"]=="continue" and out["status"]=="critical_co2"
    assert "offen lassen" in out["instruction"]

def test_running_critical_mould_with_wetter_outside_closes():
    out=build(room(surface_rh=94,humidity=80,active=True,action="Continue ventilating",delta_g_m3=-0.7,realistic_potential_ml=-80))
    assert out["kind"]=="close" and out["status"]=="critical_mould_wait"
    assert "schließen" in out["instruction"]

def test_running_critical_mould_with_drier_outside_continues():
    out=build(room(surface_rh=94,humidity=80,active=True,action="Close",close_recommended=True,delta_g_m3=2.0,realistic_potential_ml=140))
    assert out["kind"]=="continue" and out["status"]=="critical_mould"

def test_critical_co2_shortens_for_thermal_conflict_and_explains_it():
    out=build(room(co2=1750,delta_g_m3=1.0,realistic_potential_ml=50,forecast_temperature_change_c=-2.0),duration=12)
    assert out["duration_min"]==5.0
    assert "Temperaturprognose -2.0" in " ".join(out["reasons"])

def test_critical_mould_drying_override_discloses_pollen_conflict():
    out=build(room(surface_rh=93,delta_g_m3=2.0,realistic_potential_ml=120),pollen_blocked=True,pollen_index=6)
    assert out["status"]=="critical_mould" and out["kind"]=="ventilate"
    assert "Pollenindex 6.0" in " ".join(out["reasons"])

def test_critical_mould_positive_gradient_but_no_positive_forecast_waits():
    out=build(room(surface_rh=93,delta_g_m3=1.0,realistic_potential_ml=0))
    assert out["status"]=="critical_mould_wait"
    assert "keinen positiven Feuchteabbau" in " ".join(out["reasons"])

def test_critical_co2_respects_authoritative_session_close_for_reassessment():
    out=build(room(active=True,co2=1800,co2_available=True,goal_state={"goals":[],"hard_close":True}))
    assert out["kind"] == "close"
    assert out["status"] == "critical_co2_reassess"
    assert "neu bewerten" in out["instruction"].lower()


def test_multiroom_critical_co2_can_close_expired_room_and_open_other_room():
    a=room(key="a",name="A",active=True,co2=1900,co2_available=True,goal_state={"goals":[],"hard_close":True})
    b=room(key="b",name="B",active=False,co2=1700,co2_available=True,goal_state={"goals":[],"hard_close":False})
    out=build_recommendation({"a":a,"b":b}, OPTS, threshold_ml=500, total_potential_ml=0, recommended_duration_min=8)
    assert out["kind"] == "ventilate"
    assert "A schließen" in out["instruction"]
    assert "B öffnen" in out["instruction"]


def test_multiroom_all_critical_co2_at_session_endpoint_closes_for_reassessment():
    a=room(key="a",name="A",active=True,co2=1900,co2_available=True,goal_state={"goals":[],"hard_close":True})
    b=room(key="b",name="B",active=True,co2=1700,co2_available=True,goal_state={"goals":[],"hard_close":True})
    out=build_recommendation({"a":a,"b":b}, OPTS, threshold_ml=500, total_potential_ml=0, recommended_duration_min=8)
    assert out["kind"] == "close"
    assert out["status"] == "critical_co2_reassess"
