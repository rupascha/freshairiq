from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.recommendation import build_recommendation

def r(k,co2=800,surf=60,delta=2,pot=200,active=False): return {"key":k,"name":k.upper(),"calculation_enabled":True,"data_quality":"ok","active":active,"action":"Wait","humidity":55,"surface_rh":surf,"mould_level":"Low","co2":co2,"co2_available":True,"potential_ml":pot,"realistic_potential_ml":pot,"delta_g_m3":delta,"airflow_factor":1,"forecast_temperature_change_c":-.2,"temp_next_5_min_c":-.2,"next_5_min_cost":0,"forecast_cost":0,"forecast_confidence":80,"humidity_trend_pct_h":0,"humidity_high_duration_min":0}
def build(rooms,**kw): return build_recommendation(rooms,dict(DEFAULT_OPTIONS),threshold_ml=500,total_potential_ml=kw.pop('total',400),recommended_duration_min=kw.pop('duration',8),**kw)
def test_two_critical_co2_bundled():
 o=build({"a":r("a",co2=1800),"b":r("b",co2=1600)}); assert o["kind"]=="ventilate" and set(o["room_keys"])=={"a","b"}
def test_blocked_worst_mould_does_not_hide_actionable_room():
 o=build({"blocked":r("blocked",surf=96,delta=-1,pot=-40),"helped":r("helped",surf=92,delta=2.5,pot=250)}); assert o["room_keys"]==["helped"] and "BLOCKED geschlossen lassen" in o["instruction"]
def test_co2_and_mould_combine_and_conflict_shortens():
 o=build({"air":r("air",co2=1900,delta=-.2,pot=-20),"bath":r("bath",surf=93,delta=2.8,pot=300)},duration=9); assert set(o["room_keys"])=={"air","bath"} and o["duration_min"]==5
def test_mixed_active_and_pollen_are_explicit():
 o=build({"air":r("air",co2=1900,active=True),"bath":r("bath",surf=93,delta=2.8,pot=300)},duration=9,pollen_blocked=True,pollen_index=9); assert o["kind"]=="ventilate" and o["duration_min"]==5 and "offen lassen" in o["instruction"] and "Pollenindex" in " ".join(o["reasons"])
def test_all_actionable_open_continues():
 o=build({"a":r("a",co2=1800,active=True),"b":r("b",co2=1700,active=True)}); assert o["kind"]=="continue"
def test_multiple_blocked_mould_wait_then_close_open_one():
 rooms={"a":r("a",surf=96,delta=-1,pot=-50),"b":r("b",surf=94,delta=-.5,pot=-20)}; assert build(rooms,total=-70)["kind"]=="wait"; rooms["b"]["active"]=True; assert build(rooms,total=-70)["kind"]=="close"
def test_text_scale_contract_moved_to_per_card_editor():
 from custom_components.freshairiq.settings_contract import NATIVE_OPTION_KEYS
 assert "dashboard_text_scale" not in DEFAULT_OPTIONS and "dashboard_text_scale" not in NATIVE_OPTION_KEYS
 card=open('custom_components/freshairiq/frontend/freshairiq-card.js',encoding='utf-8').read()
 assert "dashboard_text_scale" not in card
 for key in ("font_scale_recommendation","font_scale_goals","font_scale_rooms","font_scale_metrics","font_scale_details","font_scale_meta"):
  assert key in card
 assert "SCHRIFTGRÖSSEN DIESER KARTE" in card and "TEXT SIZES FOR THIS CARD" in card
