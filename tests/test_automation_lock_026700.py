"""0.26.7.0 (owner request): the global automation lock – pure parts (no Home Assistant)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.actuator_control import AUTOMATION_LOCK_REASON, automation_lock_state, settle_removed_off
from custom_components.freshairiq.fan_automation import automation_text, auto_start, auto_stop, room_fan_automation

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
ROOM = {"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": ["switch.fan"], "mechanical_exhaust_active": True},
        "house_aligned_action": "close"}


def test_lock_state_from_the_chosen_entity() -> None:
    assert automation_lock_state(None, None) == {"configured": False, "entity_id": None, "active": False, "source_state": None}
    assert automation_lock_state(" input_boolean.urlaub ", "on")["active"] is True
    for state in ("on", "ON", "active", "paused"):
        assert automation_lock_state("timer.x", state)["active"] is True
    for state in ("off", "idle", "unavailable", "unknown"):
        lock = automation_lock_state("input_boolean.urlaub", state)
        assert lock["active"] is False and lock["source_state"] == state.lower()
    assert automation_lock_state("input_boolean.weg", None) == {"configured": True, "entity_id": "input_boolean.weg", "active": False, "source_state": "missing"}


def test_the_lock_switch_off_is_settled_like_a_removed_control() -> None:
    mem = {"reason": AUTOMATION_LOCK_REASON, "command_state": "pending", "command_at": NOW.isoformat(), "off_entities": ["switch.fan"]}
    assert settle_removed_off(dict(mem), False, NOW) is False   # another reason: not this one's to settle
    done = dict(mem)
    assert settle_removed_off(done, False, NOW, all_off=True, reason=AUTOMATION_LOCK_REASON) is True
    assert done["command_state"] == "confirmed" and "off_entities" not in done
    late = dict(mem)
    assert settle_removed_off(late, True, NOW + timedelta(minutes=5), reason=AUTOMATION_LOCK_REASON) is True and late["command_state"] == "failed"


def test_fan_states_under_the_lock_nothing_automatic_is_promised() -> None:
    locked = room_fan_automation(ROOM, {"automation_lock": True})
    assert locked["state"] == "locked" and locked["label_key"] == "automation_lock"
    assert "Automationssperre" in locked["label"] and not locked["user_action_needed"]
    assert not auto_stop({"fan_automation": locked}) and not auto_start({"fan_automation": locked})   # the user decides
    stopping = room_fan_automation(ROOM, {"automation_lock": True, "command": "off", "command_state": "pending"})
    assert stopping["state"] == "stopping" and stopping["label_key"] == "automation_lock_off" and auto_stop({"fan_automation": stopping})
    failed = room_fan_automation(ROOM, {"automation_lock": True, "command": "off", "command_state": "failed"})
    assert failed["state"] == "failed" and failed["user_action_needed"]
    assert automation_text(locked, "en") == "Automation lock active – FreshAirIQ does not switch the exhaust fan automatically"
    assert automation_text(stopping, "en") == "Automation lock active – FreshAirIQ only ends its own airing"
    # the device lock of another automation still comes first
    assert room_fan_automation(ROOM, {"automation_lock": True, "external_lock": True})["state"] == "external"
