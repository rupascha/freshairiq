"""Runtime regression tests for legacy/corrupt config-entry persistence."""
from __future__ import annotations

from custom_components.freshairiq.config_flow import _normalise_room, _safe_int
from custom_components.freshairiq.const import (
    CONF_CONTACT_DELAYS,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
)


def test_safe_int_rejects_non_finite_and_bad_values() -> None:
    assert _safe_int("nan", 14, minimum=1, maximum=365) == 14
    assert _safe_int(float("inf"), 14, minimum=1, maximum=365) == 14
    assert _safe_int("broken", 14, minimum=1, maximum=365) == 14
    assert _safe_int(-20, 14, minimum=1, maximum=365) == 1
    assert _safe_int(900, 14, minimum=1, maximum=365) == 365


def test_room_normalisation_repairs_corrupt_persisted_sort_and_delays() -> None:
    existing = [{
        "key": "wohnzimmer",
        CONF_ROOM_NAME: "Wohnzimmer",
        CONF_ROOM_SORT_ORDER: "nan",
        CONF_CONTACT_DELAYS: {"binary_sensor.window": "broken"},
    }]
    room, errors = _normalise_room(
        {
            CONF_ROOM_NAME: "Wohnzimmer",
            CONF_ROOM_TEMPERATURE: "sensor.temp",
            CONF_ROOM_HUMIDITY: "sensor.humidity",
            CONF_ROOM_CONTACTS: ["binary_sensor.window"],
            CONF_ROOM_VOLUME: 50,
            CONF_ROOM_INCLUDE_CALCULATIONS: True,
        },
        existing,
        keep_key="wohnzimmer",
    )
    assert not errors
    assert room is not None
    assert room[CONF_ROOM_SORT_ORDER] == 1
    assert room[CONF_CONTACT_DELAYS]["binary_sensor.window"] == 0
