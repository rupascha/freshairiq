"""Regression tests for final room/presentation action consistency."""
from custom_components.freshairiq.opening_strategy import synchronize_room_presentation_actions


def test_final_continue_replaces_conflicting_room_close_only_for_presentation():
    rooms = {"bed": {"key": "bed", "active": True, "action": "Close"}}
    rec = {"kind": "continue", "room_keys": ["bed"]}
    synchronize_room_presentation_actions(rec, rooms)
    assert rooms["bed"]["action"] == "Continue ventilating"
    assert rooms["bed"]["canonical_action"] == "Close"


def test_final_close_replaces_conflicting_running_room_action():
    rooms = {"bed": {"key": "bed", "active": True, "action": "Continue ventilating"}}
    rec = {"kind": "close", "room_keys": ["bed"]}
    synchronize_room_presentation_actions(rec, rooms)
    assert rooms["bed"]["action"] == "Close"
    assert rooms["bed"]["canonical_action"] == "Continue ventilating"


def test_unselected_room_is_untouched():
    rooms = {
        "bed": {"key": "bed", "active": True, "action": "Close"},
        "bath": {"key": "bath", "active": True, "action": "Close"},
    }
    rec = {"kind": "continue", "room_keys": ["bed"]}
    synchronize_room_presentation_actions(rec, rooms)
    assert rooms["bath"] == {"key": "bath", "active": True, "action": "Close"}


def test_invalid_or_non_actionable_inputs_are_noops():
    rooms = {"r": {"key": "r", "active": False, "action": "Wait"}}
    synchronize_room_presentation_actions(None, rooms)
    synchronize_room_presentation_actions({"kind": "okay", "room_keys": ["r"]}, rooms)
    synchronize_room_presentation_actions({"kind": "ventilate", "room_keys": []}, rooms)
    assert rooms["r"]["action"] == "Wait"


def test_missing_selected_room_is_ignored_and_idle_ventilate_is_aligned():
    rooms = {"r": {"key": "r", "active": False, "action": "Wait"}}
    synchronize_room_presentation_actions({"kind": "ventilate", "room_keys": ["missing", "r"]}, rooms)
    assert rooms["r"]["action"] == "Ventilate"
    assert rooms["r"]["canonical_action"] == "Wait"


def test_opening_guidance_adjust_running_forces_continue_presentation():
    rooms = {"r": {"key": "r", "active": True, "action": "Close"}}
    rec = {
        "kind": "continue",
        "room_keys": ["r"],
        "opening_guidance": [None, {"room_key": "r", "mode": "adjust_running"}],
    }
    synchronize_room_presentation_actions(rec, rooms)
    assert rooms["r"]["action"] == "Continue ventilating"


def test_no_canonical_metadata_is_added_when_action_already_matches():
    rooms = {"r": {"key": "r", "active": True, "action": "Continue ventilating"}}
    synchronize_room_presentation_actions({"kind": "continue", "room_keys": ["r"]}, rooms)
    assert rooms["r"] == {"key": "r", "active": True, "action": "Continue ventilating"}
