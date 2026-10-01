from pathlib import Path
from custom_components.freshairiq.opening_state import stabilise_explicit_mode


def test_closed_to_open_is_held_for_three_seconds():
    assert stabilise_explicit_mode("open", "closed", 0.2) == ("closed", True)
    assert stabilise_explicit_mode("open", "closed", 2.99) == ("closed", True)
    assert stabilise_explicit_mode("open", "closed", 3.0) == ("open", False)


def test_closed_open_tilt_handle_path_never_confirms_transient_open():
    # First open telegram is still inside the confirmation window.
    stable, suppressed = stabilise_explicit_mode("open", "closed", 0.6)
    assert (stable, suppressed) == ("closed", True)
    # The handle reaches tilt; its own three-second window starts from that event.
    stable, suppressed = stabilise_explicit_mode("tilted", "closed", 0.1)
    assert (stable, suppressed) == ("closed", True)
    assert stabilise_explicit_mode("tilted", "closed", 3.01) == ("tilted", False)


def test_direct_closed_to_tilt_is_also_confirmed():
    assert stabilise_explicit_mode("tilted", "closed", 1.0) == ("closed", True)
    assert stabilise_explicit_mode("tilted", "closed", 3.1) == ("tilted", False)


def test_open_tilt_and_tilt_open_remain_debounced():
    assert stabilise_explicit_mode("tilted", "open", 1.0) == ("open", True)
    assert stabilise_explicit_mode("open", "tilted", 1.0) == ("tilted", True)


def test_close_is_debounced_for_explicit_three_state_contact():
    assert stabilise_explicit_mode("closed", "open", 1.0) == ("open", True)
    assert stabilise_explicit_mode("closed", "open", 3.1) == ("closed", False)


def test_first_observation_without_previous_state_is_not_blocked():
    # Startup must not invent a prior state; persisted stable state is used when available.
    assert stabilise_explicit_mode("open", None, 0.1) == ("open", False)


def test_event_listener_schedules_confirmation_for_all_known_contact_states():
    source = Path("custom_components/freshairiq/coordinator.py").read_text()
    assert 'in {"closed", "open", "tilted"}' in source
    assert 'SESSION_CLOSE_CONFIRM_SECONDS, _confirm_contact_state' in source
    assert 'newer state' in source.lower()


def test_binary_compatibility_guard_remains_in_capability_detection():
    source = Path("custom_components/freshairiq/opening_state.py").read_text()
    assert 'startswith("binary_sensor.")' in source
    assert 'return False' in source
