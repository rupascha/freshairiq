"""Hotfix 0.26.6.0 (1): the room status of a switch-off at the lock period that did not arrive.

A FreshAirIQ switch-off in the lock period that failed while the fan still runs is "failed" (please switch
off by hand, user action needed) – never "stopping". While it is on its way it stays "stopping"; once the
fan is off it is "blocked_time". The controller side is tested in ha_tests/test_fan_block_ownership_hotfix_026600.py.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.fan_automation import room_fan_automation


def _room(fan_on: bool) -> dict:
    return {"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": ["switch.fan"], "mechanical_exhaust_active": fan_on}}


@pytest.mark.parametrize(("fan_on", "command_state", "owned", "expected"), [
    (True, "failed", True, ("failed", "failed_off", True)),
    (True, "pending", False, ("stopping", "block_time", False)),
    (False, "confirmed", False, ("blocked_time", "block_time", False)),
    (False, "failed", True, ("blocked_time", "block_time", False)),   # the fan is off after all: nothing to do
])
def test_the_status_shows_a_missing_switch_off_in_the_lock_period(fan_on, command_state, owned, expected) -> None:
    snap = {"block_time": True, "command": "off", "command_state": command_state, "owned": owned, "reason": "block_time"}
    status = room_fan_automation(_room(fan_on), snap)
    assert (status["state"], status["label_key"], status["user_action_needed"]) == expected
