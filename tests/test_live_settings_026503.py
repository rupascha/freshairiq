"""0.26.5.3: helpers deciding what a saved change needs to take effect at once."""
from __future__ import annotations

from custom_components.freshairiq.live_settings import (
    DIAGNOSTICS_OPTION_KEYS,
    changed_option_keys,
    optional_room_sensors,
    room_structure,
)


def test_room_structure_is_keys_and_names() -> None:
    data = {"rooms": [{"key": "b", "name": "Bad"}, {"key": "a"}, {"name": "ohne Schlüssel"}, "kaputt"]}
    assert room_structure(data) == (("a", "a"), ("b", "Bad"))
    assert room_structure({}) == () and room_structure({"rooms": "x"}) == ()


def test_changed_option_keys() -> None:
    assert changed_option_keys({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4}) == {"b", "c"}
    assert "diagnostics_consent" in DIAGNOSTICS_OPTION_KEYS


def test_optional_room_sensors_follow_the_room_setup() -> None:
    data = {"rooms": [
        {"key": "wz", "contact_covers": {"binary_sensor.f": ["cover.r"]}, "moisture_sources": []},
        {"key": "bad", "covers": [], "moisture_sources": ["shower"]},
        {"name": "ohne Schlüssel"},
    ]}
    assert optional_room_sensors(data) == {
        "wz_shading": True, "wz_moisture_source": False, "bad_shading": False, "bad_moisture_source": True}
    assert optional_room_sensors({"rooms": None}) == {}
