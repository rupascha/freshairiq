"""Repair lifecycle and entity metadata checks against a real HA runtime."""
from __future__ import annotations

from types import MappingProxyType, SimpleNamespace
from unittest.mock import Mock

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import EntityCategory

from custom_components.freshairiq import repairs
from custom_components.freshairiq.const import (
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOMS,
    DOMAIN,
)
from custom_components.freshairiq.button import ResetLearningButton, ResetStatisticsButton
from custom_components.freshairiq.number import (
    FreshAirIQForecastHorizonNumber,
    FreshAirIQGuestAdultsNumber,
    FreshAirIQGuestChildrenNumber,
)
from custom_components.freshairiq.select import FreshAirIQOperatingProfileSelect


def _entry() -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry-1",
        title="Mein Haus",
        data={
            CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature",
            CONF_OUTDOOR_HUMIDITY: "sensor.outdoor_humidity",
            CONF_ROOMS: [
                {
                    "key": "bathroom",
                    "name": "Badezimmer",
                    CONF_ROOM_INCLUDE_CALCULATIONS: True,
                    CONF_ROOM_TEMPERATURE: "sensor.bathroom_temperature",
                    CONF_ROOM_HUMIDITY: "sensor.bathroom_humidity",
                    CONF_ROOM_CONTACTS: ["binary_sensor.bathroom_window"],
                },
                {
                    "key": "storage",
                    "name": "Lager",
                    CONF_ROOM_INCLUDE_CALCULATIONS: False,
                    CONF_ROOM_TEMPERATURE: "sensor.deleted_but_unused",
                    CONF_ROOM_HUMIDITY: "sensor.deleted_but_unused_humidity",
                    CONF_ROOM_CONTACTS: ["binary_sensor.deleted_but_unused_window"],
                },
            ],
        },
    )



def test_required_entity_references_accept_home_assistant_readonly_mappings() -> None:
    entry = _entry()
    entry.data = MappingProxyType({
        CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature",
        CONF_OUTDOOR_HUMIDITY: "sensor.outdoor_humidity",
        CONF_ROOMS: [MappingProxyType({
            "key": "office",
            "name": "Arbeitszimmer",
            CONF_ROOM_INCLUDE_CALCULATIONS: True,
            CONF_ROOM_TEMPERATURE: "sensor.office_temperature",
            CONF_ROOM_HUMIDITY: "sensor.office_humidity",
            CONF_ROOM_CONTACTS: ["binary_sensor.office_window"],
        })],
    })
    refs = repairs._required_entity_references(entry)
    assert {entity_id for entity_id, _context in refs} == {
        "sensor.outdoor_temperature",
        "sensor.outdoor_humidity",
        "sensor.office_temperature",
        "sensor.office_humidity",
        "binary_sensor.office_window",
    }

def test_required_entity_references_skip_non_calculated_rooms() -> None:
    refs = repairs._required_entity_references(_entry())
    entity_ids = {entity_id for entity_id, _context in refs}
    assert entity_ids == {
        "sensor.outdoor_temperature",
        "sensor.outdoor_humidity",
        "sensor.bathroom_temperature",
        "sensor.bathroom_humidity",
        "binary_sensor.bathroom_window",
    }


def test_transient_unavailable_state_is_not_a_repair(monkeypatch) -> None:
    entry = _entry()
    configured = {entity_id for entity_id, _context in repairs._required_entity_references(entry)}
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: object() if entity_id in configured else None))
    registry = SimpleNamespace(async_get=lambda entity_id: None)
    monkeypatch.setattr(repairs.er, "async_get", lambda _hass: registry)
    assert repairs.missing_required_entities(hass, entry) == []


def test_registry_entry_prevents_false_missing_repair(monkeypatch) -> None:
    entry = _entry()
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _entity_id: None))
    registry = SimpleNamespace(async_get=lambda entity_id: object())
    monkeypatch.setattr(repairs.er, "async_get", lambda _hass: registry)
    assert repairs.missing_required_entities(hass, entry) == []


def test_removed_required_entity_creates_actionable_issue(monkeypatch) -> None:
    entry = _entry()
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _entity_id: None))
    registry = SimpleNamespace(
        async_get=lambda entity_id: None if entity_id == "sensor.bathroom_humidity" else object()
    )
    create = Mock()
    delete = Mock()
    monkeypatch.setattr(repairs.er, "async_get", lambda _hass: registry)
    monkeypatch.setattr(repairs.ir, "async_create_issue", create)
    monkeypatch.setattr(repairs.ir, "async_delete_issue", delete)

    repairs.async_sync_missing_entity_issue(hass, entry)

    delete.assert_not_called()
    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[:3] == (hass, DOMAIN, repairs.issue_id_for_entry(entry))
    assert kwargs["severity"] == ir.IssueSeverity.ERROR
    assert kwargs["translation_key"] == "missing_required_entities"
    assert "sensor.bathroom_humidity" in kwargs["translation_placeholders"]["entities"]
    assert kwargs["data"]["entry_id"] == entry.entry_id


def test_repair_is_deleted_after_configuration_recovers(monkeypatch) -> None:
    entry = _entry()
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _entity_id: object()))
    registry = SimpleNamespace(async_get=lambda _entity_id: None)
    create = Mock()
    delete = Mock()
    monkeypatch.setattr(repairs.er, "async_get", lambda _hass: registry)
    monkeypatch.setattr(repairs.ir, "async_create_issue", create)
    monkeypatch.setattr(repairs.ir, "async_delete_issue", delete)

    repairs.async_sync_missing_entity_issue(hass, entry)

    create.assert_not_called()
    delete.assert_called_once_with(hass, DOMAIN, repairs.issue_id_for_entry(entry))


def test_config_entities_use_native_category_and_translation_keys() -> None:
    coordinator = SimpleNamespace(options={}, store=SimpleNamespace())
    entry = SimpleNamespace(entry_id="entry", options={})
    entities = [
        FreshAirIQForecastHorizonNumber(coordinator, entry),
        FreshAirIQGuestAdultsNumber(coordinator, entry),
        FreshAirIQGuestChildrenNumber(coordinator, entry),
        FreshAirIQOperatingProfileSelect(coordinator, entry),
        ResetLearningButton(coordinator, entry),
        ResetStatisticsButton(coordinator, entry),
    ]
    assert all(entity.entity_category == EntityCategory.CONFIG for entity in entities)
    assert all(entity.translation_key for entity in entities)


def test_room_sensor_availability_includes_coordinator_health() -> None:
    from custom_components.freshairiq.sensor import RoomSensor

    coordinator = SimpleNamespace(
        last_update_success=False,
        data={"rooms": {"office": {"data_quality": "ok", "action": "Okay"}}},
    )
    entry = SimpleNamespace(entry_id="entry")
    sensor = RoomSensor(
        coordinator, entry, "office", "Arbeitszimmer", "action", "Action", None,
        "mdi:weather-windy",
    )
    assert sensor.available is False

    coordinator.last_update_success = True
    assert sensor.available is True
    coordinator.data["rooms"]["office"]["data_quality"] = "missing"
    assert sensor.available is False


def test_sensor_device_classes_and_diagnostic_defaults() -> None:
    from homeassistant.components.sensor import SensorDeviceClass
    from custom_components.freshairiq.sensor import HOUSE, ROOM_FIELDS

    house = {item.key: item for item in HOUSE}
    room = {item[0]: item for item in ROOM_FIELDS}

    assert house["max_surface_rh"].device_class == SensorDeviceClass.HUMIDITY
    assert house["recommended_duration_min"].device_class == SensorDeviceClass.DURATION
    assert house["forecast_temperature_change_c"].device_class == SensorDeviceClass.TEMPERATURE_DELTA
    assert house["last_learning_diagnosis"].enabled_default is False

    # tuple: field, label, unit, icon, device_class, enabled_default
    assert room["absolute_humidity"][4] == SensorDeviceClass.ABSOLUTE_HUMIDITY
    assert room["temp_next_5_min_c"][4] == SensorDeviceClass.TEMPERATURE
    assert room["temperature_change_c"][4] == SensorDeviceClass.TEMPERATURE_DELTA
    assert room["session_elapsed_min"][4] == SensorDeviceClass.DURATION
    assert room["learning_samples"][5] is False
    assert room["learning_diagnosis"][5] is False
