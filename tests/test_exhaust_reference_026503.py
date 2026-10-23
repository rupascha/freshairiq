"""0.26.5.3 (community, heinzel): an exhaust fan draws its replacement air from the
neighbouring room, not from outside. The neighbouring room's sensors are the
reference while the fan airs the room."""
from __future__ import annotations

import pytest

from custom_components.freshairiq.exhaust_reference import exhaust_reference_applies, exhaust_reference_pair


def test_pair_is_atomic_and_trimmed():
    assert exhaust_reference_pair({"exhaust_fan_reference_temperature": " sensor.flur_t ", "exhaust_fan_reference_humidity": "sensor.flur_h"}) == ("sensor.flur_t", "sensor.flur_h")
    assert exhaust_reference_pair({"exhaust_fan_reference_temperature": "sensor.flur_t"}) is None
    assert exhaust_reference_pair({"exhaust_fan_reference_humidity": "sensor.flur_h"}) is None
    assert exhaust_reference_pair({}) is None


@pytest.mark.parametrize(("fan_configured", "fan_active", "window_open", "has_contacts", "expected"), [
    (True, True, False, True, True),     # fan runs, window closed: neighbouring room
    (True, True, True, True, False),     # an open window brings its own air
    (True, False, False, True, False),   # window room, fan off: opening the window is the option
    (True, False, False, False, True),   # windowless room: the fan is its only way to air
    (False, True, False, False, False),  # no fan configured
])
def test_when_the_neighbouring_room_is_the_reference(fan_configured, fan_active, window_open, has_contacts, expected):
    assert exhaust_reference_applies(fan_configured=fan_configured, fan_active=fan_active,
                                     window_open=window_open, has_contacts=has_contacts) is expected
