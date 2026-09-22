from custom_components.freshairiq.support_incident import build_support_incident, classify_support_code


def trace(kind="okay", status="ok", invariants=None):
    return {"final":{"kind":kind,"status":status,"scope":"rooms"},"invariants":invariants or {"selected_rooms_exist":True}}


def test_healthy_decision_has_no_incident_but_stable_trace_id():
    a=build_support_incident(trace()); b=build_support_incident(trace())
    assert a["incident"] is False and a["support_code"] is None
    assert a["fingerprint"] == b["fingerprint"] and a["decision_trace_id"] == b["decision_trace_id"]


def test_sensor_problem_gets_stable_support_code():
    assert classify_support_code(trace("sensor","sensor_error")) == "FAIQ-SENSOR-DATA-001"


def test_invariant_failure_has_priority_over_sensor_classification():
    t=trace("sensor","sensor_error",{"selected_rooms_exist":False})
    assert classify_support_code(t) == "FAIQ-DECISION-INVARIANT-001"


def test_diagnostic_io_error_has_stable_code():
    assert classify_support_code(trace(), diagnostics_error_type="OSError") == "FAIQ-DIAG-IO-001"


def test_runtime_config_issue_has_stable_code():
    assert classify_support_code(trace(), runtime_config_issues=["bad_threshold"]) == "FAIQ-CONFIG-RUNTIME-001"


def test_fingerprint_groups_equal_incidents_without_names_or_entities():
    a=build_support_incident(trace("sensor","sensor_error"), {"invalid_rooms":2})
    b=build_support_incident(trace("sensor","sensor_error"), {"invalid_rooms":2})
    assert a["fingerprint"] == b["fingerprint"]
    payload=str(a)
    assert "sensor.bedroom" not in payload and "Schlafzimmer" not in payload
    assert a["privacy"] == {"contains_entity_ids":False,"contains_room_names":False,"contains_free_text":False}


def test_list_shaped_sensor_issue_is_classified():
    incident=build_support_incident(trace(), {"stale_rooms":["room-token"]})
    assert incident["support_code"] == "FAIQ-SENSOR-DATA-001"
