"""GitHub #27 (0.26.7.0): living room with a balcony door and a window, set up correctly, drawn differently in the
floor plan proposal. A contact of one room was drawn as a door only when its kind was stated as "door"; a balcony
door sensor whose Home Assistant device class says door (kind "not stated") became a window, while everything else
(``contact_role``) already read the device class. Now both agree; a kind stated in the setup still wins."""
from __future__ import annotations

from custom_components.freshairiq.house_autolayout import _openings, propose

SQUARE = {"wohnzimmer": [[0, 0], [5, 0], [5, 4], [0, 4]]}
DOOR, WINDOW = "binary_sensor.balkontuer", "binary_sensor.wz_fenster"


def _kinds(openings):
    return {o["contacts"][0]: (o["kind"], o["mechanics"]) for o in openings}


def test_balcony_door_sensor_is_drawn_as_a_door_without_a_stated_kind():
    rooms = [{"key": "wohnzimmer", "contacts": [DOOR, WINDOW]}]
    classes = {DOOR: "door", WINDOW: "window"}
    assert _kinds(_openings(rooms, SQUARE, {}, None, classes)) == {DOOR: ("door", "door"), WINDOW: ("window", "unknown")}
    # through the whole proposal as Home Assistant reports the classes
    layout = propose([{**rooms[0], "floor": "EG", "length": 5, "width": 4}], ["EG"], None, classes)
    assert _kinds(layout["layout"]["openings"]) == {DOOR: ("door", "door"), WINDOW: ("window", "unknown")}


def test_the_stated_kind_wins_over_the_device_class():
    rooms = [{"key": "wohnzimmer", "contacts": [DOOR], "contact_kinds": {DOOR: "window"}}]
    assert _kinds(_openings(rooms, SQUARE, {}, None, {DOOR: "door"})) == {DOOR: ("window", "unknown")}


def test_without_classes_the_previous_behaviour_stays():
    rooms = [{"key": "wohnzimmer", "contacts": [DOOR, WINDOW]}]
    assert _kinds(_openings(rooms, SQUARE, {})) == {DOOR: ("window", "unknown"), WINDOW: ("window", "unknown")}
