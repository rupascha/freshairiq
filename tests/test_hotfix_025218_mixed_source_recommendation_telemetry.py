from pathlib import Path

from custom_components.freshairiq.opening_state import specialist_opening_provenance


def test_mixed_three_state_and_binary_never_selects_specialist_model():
    assert specialist_opening_provenance(
        {"sensor.door": "tilted", "binary_sensor.window": "open"},
        {"sensor.door"},
    ) == (None, ())
    assert specialist_opening_provenance(
        {"sensor.door": "open", "binary_sensor.window": "open"},
        {"sensor.door"},
    ) == (None, ())


def test_mixed_three_state_modes_never_select_specialist_model():
    assert specialist_opening_provenance(
        {"sensor.left": "tilted", "sensor.right": "open"},
        {"sensor.left", "sensor.right"},
    ) == (None, ())


def test_same_proven_mode_can_use_specialist_model():
    mode, signature = specialist_opening_provenance(
        {"sensor.left": "tilted", "sensor.right": "tilted"},
        {"sensor.left", "sensor.right"},
    )
    assert mode == "tilted"
    assert signature == ("sensor.left", "sensor.right")


def test_session_source_change_quarantines_specialist_learning_contract():
    text = Path("custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'mem["session_opening_mode_mixed"] = True' in text
    assert 'not mem.get("session_opening_mode_mixed")' in text
    assert 'current_signature != started_signature' in text


def test_nightly_diagnostics_exposes_mixed_source_without_entity_ids():
    text = Path("custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert '"mixed_source_session": bool(stored.get("session_opening_mode_mixed"))' in text
    assert '"proven_contact_count"' in text


def test_recommendation_counters_are_read_from_persistent_room_memory():
    text = Path("custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert 'if counter_key in stored_room:' in text
    assert 'room[counter_key] = _json_safe(stored_room.get(counter_key))' in text
    assert '"recommendation_opportunity_count": recommendation_opportunities' in text


def test_nightly_transport_carries_recommendation_count():
    text = Path("custom_components/freshairiq/diagnostic_transport.py").read_text(encoding="utf-8")
    assert '"recommendation_opportunity_count"' in text
