from pathlib import Path

from custom_components.freshairiq.opening_state import specialist_opening_provenance


def test_three_state_open_alone_is_specialist_open():
    mode, signature = specialist_opening_provenance(
        {"sensor.handle": "open"}, {"sensor.handle"}
    )
    assert mode == "open"
    assert signature == ("sensor.handle",)


def test_three_state_tilt_alone_is_specialist_tilt():
    mode, signature = specialist_opening_provenance(
        {"sensor.handle": "tilted"}, {"sensor.handle"}
    )
    assert mode == "tilted"
    assert signature == ("sensor.handle",)


def test_binary_open_alone_never_selects_specialist():
    assert specialist_opening_provenance(
        {"binary_sensor.window": "open"}, set()
    ) == (None, ())


def test_closed_three_state_plus_open_binary_is_general_only():
    assert specialist_opening_provenance(
        {"sensor.handle": "closed", "binary_sensor.window": "open"},
        {"sensor.handle"},
    ) == (None, ())


def test_tilted_three_state_plus_open_binary_is_ambiguous():
    assert specialist_opening_provenance(
        {"sensor.handle": "tilted", "binary_sensor.window": "open"},
        {"sensor.handle"},
    ) == (None, ())


def test_open_three_state_plus_open_binary_is_general_only():
    assert specialist_opening_provenance(
        {"sensor.handle": "open", "binary_sensor.window": "open"},
        {"sensor.handle"},
    ) == (None, ())


def test_multiple_proven_contacts_same_mode_have_auditable_signature():
    mode, signature = specialist_opening_provenance(
        {"sensor.b": "open", "sensor.a": "open"}, {"sensor.a", "sensor.b"}
    )
    assert mode == "open"
    assert signature == ("sensor.a", "sensor.b")


def test_multiple_proven_contacts_different_modes_are_ambiguous():
    assert specialist_opening_provenance(
        {"sensor.a": "open", "sensor.b": "tilted"}, {"sensor.a", "sensor.b"}
    ) == (None, ())


def test_coordinator_pins_specialist_learning_and_prediction_to_provenance():
    text = Path("custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "specialist_opening_provenance(contact_modes, proven_three_state)" in text
    assert 'mem["session_specialist_opening_mode"]' in text
    assert 'mem["session_specialist_opening_signature"]' in text
    assert 'session_mode = str(mem.get("session_specialist_opening_mode") or "")' in text
    assert 'opening_model_key = "cross" if cross and opening_mode == "open" else specialist_opening_mode' in text
    assert "current_signature != started_signature" in text


def test_all_closed_contacts_have_no_specialist_provenance():
    assert specialist_opening_provenance(
        {"sensor.handle": "closed"}, {"sensor.handle"}
    ) == (None, ())
