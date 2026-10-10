from pathlib import Path
from custom_components.freshairiq.opening_state import stabilise_explicit_mode
from tests.frontend_source import card_text

def test_open_to_tilt_transient_is_suppressed():
    assert stabilise_explicit_mode("tilted", "open", 0.4) == ("open", True)
    assert stabilise_explicit_mode("tilted", "open", 3.1) == ("tilted", False)

def test_tilt_to_open_transient_is_suppressed():
    assert stabilise_explicit_mode("open", "tilted", 1.0) == ("tilted", True)

def test_binary_and_closed_are_not_reinterpreted():
    assert stabilise_explicit_mode("open", None, 0.1) == ("open", False)
    assert stabilise_explicit_mode("closed", "open", 0.1) == ("open", True)

def test_passage_door_is_available_in_both_configuration_surfaces_and_diagnostics():
    root=Path(__file__).parents[1]
    cfg=(root/'custom_components/freshairiq/config_flow.py').read_text()
    ui=card_text()
    diag=(root/'custom_components/freshairiq/diagnostics.py').read_text()
    coord=(root/'custom_components/freshairiq/coordinator.py').read_text()
    assert 'CONF_CONTACT_PASSAGE_DOORS' in cfg
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert 'passage_door' in diag
    assert 'FAIQ-OPENING-3STATE-003' in coord

def test_new_dashboard_copy_has_english_parity():
    text=card_text()
    assert 'This door is regularly used as a passage and may only be pulled shut from outside' in text
