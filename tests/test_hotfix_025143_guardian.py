from custom_components.freshairiq.guardian import evaluate_guardian

def test_guardian_healthy_minimal_state():
    result=evaluate_guardian({"rooms":{},"sensor_recovery":{"active":False,"required_sources_unavailable":0}})
    assert result["status"]=="healthy" and result["finding_count"]==0

def test_guardian_detects_invalid_physical_measurement_without_identity():
    result=evaluate_guardian({"rooms":{"secret-room":{"temperature":21,"humidity":130,"absolute_humidity":9}}})
    finding=result["findings"][0]
    assert finding["code"]=="FAIQ-GUARDIAN-SENSOR-001"
    assert "secret-room" not in str(result)

def test_guardian_detects_recovery_state_and_offers_only_safe_repair():
    result=evaluate_guardian({"rooms":{},"sensor_recovery":{"active":True,"required_sources_unavailable":0,"valid_cycles":2,"required_valid_cycles":2}})
    assert result["auto_heal_candidate_count"]==1
    assert result["safe_repairs"]==[{"repair":"clear_completed_sensor_recovery","safe":True,"reversible":True}]

def test_guardian_detects_forecast_non_monotonicity():
    result=evaluate_guardian({"rooms":{},"forecast_timeline":[{"minutes":5,"moisture_effect_ml":100},{"minutes":15,"moisture_effect_ml":80}]})
    assert any(x["code"]=="FAIQ-GUARDIAN-FORECAST-001" for x in result["findings"])

def test_guardian_covers_invalid_rows_decision_recovery_session_and_fallback_timeline():
    result=evaluate_guardian({
        "rooms":{"a":"bad","b":{"temperature":"bad","humidity":50,"absolute_humidity":9,"canonical_action":"keep open","action":"Close"}},
        "forecast_validation":{"timeline":["bad",{"duration_min":-1,"predicted_removed_ml":5}]},
        "sensor_recovery":{"active":False,"required_sources_unavailable":2,"valid_cycles":0,"required_valid_cycles":2},
        "finalizing_measurements":{"pending_count":-1},
    })
    codes={x["code"] for x in result["findings"]}
    assert {"FAIQ-GUARDIAN-SENSOR-001","FAIQ-GUARDIAN-DECISION-001","FAIQ-GUARDIAN-SENSOR-002","FAIQ-GUARDIAN-SESSION-001"} <= codes

def test_guardian_num_rejects_nonfinite_values():
    result=evaluate_guardian({"rooms":{"a":{"temperature":float("nan"),"humidity":float("inf"),"absolute_humidity":None}}})
    assert result["status"] == "healthy"
