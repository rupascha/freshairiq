"""0.26.5.5 (community diagnosis): no "switch the fan off" while another room or automation runs it."""
from __future__ import annotations

import pytest

from custom_components.freshairiq.close_wording import fan_stop_message
from custom_components.freshairiq.fan_automation import AUTO_START_STATES, AUTO_STOP_STATES, room_fan_automation
from custom_components.freshairiq.notification_policy import auto_room_event

ROOM = {"key": "flur", "name": "Flur", "house_aligned_action": "close", "delta_g_m3": 1.2,
        "configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": "switch.luefter", "mechanical_exhaust_active": True}}


@pytest.mark.parametrize(("snapshot", "state", "key"), [
    ({"shared_owner": True}, "shared", "shared_owner"),
    ({"owned": True, "shared_for": True}, "shared", "shared_for"),
    ({"external_lock": True}, "external", "external"),
    ({"external_lock": True, "owned": True}, "external", "external"),
])
def test_shared_and_external_fans_are_no_task_for_the_user(snapshot, state, key) -> None:
    automation = room_fan_automation(ROOM, snapshot)
    assert (automation["state"], automation["label_key"], automation["user_action_needed"]) == (state, key, False)
    room = {**ROOM, "fan_automation": automation}
    event, _title, text = auto_room_event("close", room, "Bitte Lüfter ausschalten")
    assert event == "fan_auto" and "ausschalten" not in text.lower()
    assert "ausschalten" not in fan_stop_message(room).lower()
    assert state in AUTO_STOP_STATES and state in AUTO_START_STATES


def test_an_own_running_room_and_a_hand_switched_fan_keep_their_states() -> None:
    assert room_fan_automation({**ROOM, "house_aligned_action": "continue_ventilating"}, {"owned": True, "shared_for": True})["state"] == "running"
    assert room_fan_automation(ROOM, {})["state"] == "manual"
    failed = room_fan_automation(ROOM, {"owned": True, "shared_for": True, "command": "off", "command_state": "failed"})
    assert failed["state"] == "failed"  # a failed switch-off is never hidden behind "shared"
    off = {**ROOM, "configured_actuators": {**ROOM["configured_actuators"], "mechanical_exhaust_active": False}}
    assert room_fan_automation(off, {"shared_owner": True})["state"] == "idle"
