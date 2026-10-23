"""0.26.5.3 (community, HarryP): open connections without a door, shared fans.

"Mein Flur endet ohne Tür am Wohnzimmer" – and one room asked to switch the
fans off while another room still needed the same fans.
"""
from __future__ import annotations

from tests.test_user_feedback_026409 import _room  # installs the HA stubs

from custom_components.freshairiq.notification_policy import effective_room_action
from custom_components.freshairiq.open_connections import OPTION, connected_pairs, connection_map, with_connections


def test_connections_are_symmetric_and_ignore_unknown_rooms() -> None:
    options = {OPTION: {"flur": ["wohnzimmer", "flur", "weg"], "kueche": "x"}}
    assert connection_map(options, ["flur", "wohnzimmer"]) == {"flur": {"wohnzimmer"}, "wohnzimmer": {"flur"}}
    assert connection_map(options) == {"flur": {"wohnzimmer", "weg"}, "wohnzimmer": {"flur"}, "weg": {"flur"}}
    assert connection_map({}) == {} and connection_map({OPTION: "garbage"}) == {}
    assert connected_pairs(options) == {frozenset({"flur", "wohnzimmer"}), frozenset({"flur", "weg"})}


def test_setting_the_connections_of_one_room_keeps_the_others() -> None:
    options = {OPTION: {"flur": ["wohnzimmer"], "kueche": ["essen"]}}
    assert with_connections(options, "flur", ["wohnzimmer", "bad", "flur"]) == {
        "bad": ["flur"], "essen": ["kueche"], "flur": ["bad", "wohnzimmer"], "kueche": ["essen"], "wohnzimmer": ["flur"]}
    assert with_connections(options, "wohnzimmer", []) == {"essen": ["kueche"], "kueche": ["essen"]}


def _open(key: str, action: str, **extra) -> dict:
    return _room(key=key, name=key.title(), action=action, active=True, **extra)


def test_no_close_while_an_openly_connected_room_keeps_airing() -> None:
    rooms = {"flur": _open("flur", "Close"), "wohnzimmer": _open("wohnzimmer", "Continue ventilating")}
    links = connection_map({OPTION: {"flur": ["wohnzimmer"]}})
    assert effective_room_action(rooms["flur"], None, rooms, links) == "Continue ventilating"
    assert effective_room_action(rooms["flur"], None, rooms, {}) == "Close"  # not connected: unchanged
    rooms["wohnzimmer"]["action"] = "Close"
    assert effective_room_action(rooms["flur"], None, rooms, links) == "Close"  # both done
    rooms["wohnzimmer"]["action"] = "Continue ventilating"
    rooms["flur"]["goal_state"] = {"hard_close": True}
    assert effective_room_action(rooms["flur"], None, rooms, links) == "Close"  # protection wins


def test_a_room_aired_through_its_connection_is_not_asked_to_air_separately() -> None:
    rooms = {"flur": _room(key="flur", action="Ventilate", active=False), "wohnzimmer": _open("wohnzimmer", "Continue ventilating")}
    links = connection_map({OPTION: {"flur": ["wohnzimmer"]}})
    assert effective_room_action(rooms["flur"], None, rooms, links) == "Ventilate indirectly"
    rooms["wohnzimmer"]["active"] = False
    assert effective_room_action(rooms["flur"], None, rooms, links) == "Ventilate"


def test_a_shared_fan_is_not_switched_off_for_one_room_while_another_needs_it() -> None:
    fan = {"exhaust_fan": ["fan.luefter_1", "fan.luefter_2"], "mechanical_exhaust_active": True, "window_open": False}
    rooms = {
        "buero": _room(key="buero", action="Close", active=True, configured_actuators=dict(fan)),
        "wohnkueche": _room(key="wohnkueche", action="Continue ventilating", active=True, configured_actuators=dict(fan)),
    }
    assert effective_room_action(rooms["buero"], None, rooms, {}) == "Continue ventilating"
    rooms["wohnkueche"]["action"] = "Close"
    assert effective_room_action(rooms["buero"], None, rooms, {}) == "Close"
    # a window to close is still a window to close
    rooms["wohnkueche"]["action"] = "Continue ventilating"
    rooms["buero"]["configured_actuators"] = {**fan, "window_open": True}
    assert effective_room_action(rooms["buero"], None, rooms, {}) == "Close"
    # different fans: no link
    rooms["buero"]["configured_actuators"] = {**fan, "exhaust_fan": "fan.buero"}
    rooms["buero"]["configured_actuators"]["window_open"] = False
    assert effective_room_action(rooms["buero"], None, rooms, {}) == "Close"
