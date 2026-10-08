"""Migration robustness against damaged legacy FreshAirIQ entries."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import custom_components.freshairiq as integration
from custom_components.freshairiq.const import (
    CONF_CONTACT_DELAYS,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_VOLUME_MODE,
)


async def test_migration_skips_non_mapping_rooms_and_repairs_bad_legacy_numbers() -> None:
    entry = SimpleNamespace(
        version=7,
        data={
            "rooms": [
                "broken-room",
                {
                    "key": "living",
                    CONF_ROOM_NAME: "Living room",
                    "contact": "binary_sensor.window",
                    "contact_delay": "nan",
                    "volume": 55.0,
                    CONF_ROOM_FLOOR: "Ground floor",
                },
            ]
        },
        options={
            "threshold_mode": "percent_total_water",
            "min_potential_percent_total_water": "not-a-number",
        },
    )
    update = Mock()
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update))

    assert await integration.async_migrate_entry(hass, entry) is True
    kwargs = update.call_args.kwargs
    assert kwargs["version"] == 8
    migrated_rooms = kwargs["data"][CONF_ROOMS]
    assert len(migrated_rooms) == 1
    room = migrated_rooms[0]
    assert room[CONF_ROOM_CONTACTS] == ["binary_sensor.window"]
    assert room[CONF_CONTACT_DELAYS]["binary_sensor.window"] == 0
    assert CONF_VOLUME_MODE in room
    assert kwargs["options"]["threshold_mode"] == "adaptive_home_size"


async def test_migration_tolerates_non_list_room_container() -> None:
    entry = SimpleNamespace(version=7, data={CONF_ROOMS: {"bad": "container"}}, options={})
    update = Mock()
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update))

    assert await integration.async_migrate_entry(hass, entry) is True
    assert update.call_args.kwargs["data"][CONF_ROOMS] == []
