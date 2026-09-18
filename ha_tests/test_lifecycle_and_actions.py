"""Home Assistant lifecycle and action behaviour for FreshAirIQ."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import ServiceValidationError

import custom_components.freshairiq as integration
from custom_components.freshairiq.const import DOMAIN, PLATFORMS


@pytest.mark.asyncio
async def test_unload_failure_keeps_runtime_listeners_alive(monkeypatch) -> None:
    """A rejected platform unload must not half-unload the coordinator."""
    coordinator = SimpleNamespace(async_stop_listeners=AsyncMock())
    entry = SimpleNamespace(entry_id="entry")
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=False))
    )
    clear = Mock()
    monkeypatch.setattr(integration, "get_runtime_coordinator", lambda _hass, _entry: coordinator)
    monkeypatch.setattr(integration, "clear_runtime_coordinator", clear)

    assert await integration.async_unload_entry(hass, entry) is False
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
    coordinator.async_stop_listeners.assert_not_awaited()
    clear.assert_not_called()


@pytest.mark.asyncio
async def test_successful_unload_stops_listeners_and_clears_runtime(monkeypatch) -> None:
    coordinator = SimpleNamespace(async_stop_listeners=AsyncMock())
    entry = SimpleNamespace(entry_id="entry")
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True))
    )
    clear = Mock()
    monkeypatch.setattr(integration, "get_runtime_coordinator", lambda _hass, _entry: coordinator)
    monkeypatch.setattr(integration, "clear_runtime_coordinator", clear)

    assert await integration.async_unload_entry(hass, entry) is True
    coordinator.async_stop_listeners.assert_awaited_once()
    clear.assert_called_once_with(hass, entry)


@pytest.mark.asyncio
async def test_intervention_action_uses_native_validation_error_when_room_key_missing() -> None:
    hass = SimpleNamespace()
    call = SimpleNamespace(data={})
    with pytest.raises(ServiceValidationError) as err:
        await integration._async_execute_intervention_service(hass, call)
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "room_key_required"


@pytest.mark.asyncio
async def test_intervention_action_uses_runtime_data_and_executes_service() -> None:
    intervention = {
        "key": "extract_moisture",
        "entity_id": "fan.bathroom",
        "service": "fan.turn_on",
        "service_data": {"percentage": 70},
    }
    coordinator = SimpleNamespace(
        data={"rooms": {"bathroom": {"interventions": [intervention]}}}
    )
    entry = SimpleNamespace(runtime_data=coordinator)
    states = SimpleNamespace(get=lambda entity_id: object() if entity_id == "fan.bathroom" else None)
    services = SimpleNamespace(async_call=AsyncMock())
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda domain: [entry]),
        data={},
        states=states,
        services=services,
    )
    call = SimpleNamespace(data={"room_key": "bathroom", "intervention_key": "extract_moisture"})

    await integration._async_execute_intervention_service(hass, call)
    services.async_call.assert_awaited_once_with(
        "fan", "turn_on", {"percentage": 70, "entity_id": "fan.bathroom"}, blocking=True
    )


@pytest.mark.asyncio
async def test_intervention_action_rejects_unavailable_entity() -> None:
    coordinator = SimpleNamespace(
        data={
            "rooms": {
                "bathroom": {
                    "interventions": [
                        {"key": "extract", "entity_id": "fan.missing", "service": "fan.turn_on"}
                    ]
                }
            }
        }
    )
    entry = SimpleNamespace(runtime_data=coordinator)
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda domain: [entry]),
        data={},
        states=SimpleNamespace(get=lambda entity_id: None),
    )
    call = SimpleNamespace(data={"room_key": "bathroom"})

    with pytest.raises(ServiceValidationError) as err:
        await integration._async_execute_intervention_service(hass, call)
    assert err.value.translation_key == "intervention_entity_unavailable"

@pytest.mark.asyncio
async def test_successful_unload_clears_repair_issue(monkeypatch) -> None:
    coordinator = SimpleNamespace(async_stop_listeners=AsyncMock())
    entry = SimpleNamespace(entry_id="entry")
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True))
    )
    clear_repair = Mock()
    monkeypatch.setattr(integration, "get_runtime_coordinator", lambda _hass, _entry: coordinator)
    monkeypatch.setattr(integration, "clear_runtime_coordinator", Mock())
    monkeypatch.setattr(integration, "async_clear_missing_entity_issue", clear_repair)

    assert await integration.async_unload_entry(hass, entry) is True
    clear_repair.assert_called_once_with(hass, entry)


@pytest.mark.asyncio
async def test_unload_failure_keeps_repair_issue(monkeypatch) -> None:
    coordinator = SimpleNamespace(async_stop_listeners=AsyncMock())
    entry = SimpleNamespace(entry_id="entry")
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=False))
    )
    clear_repair = Mock()
    monkeypatch.setattr(integration, "get_runtime_coordinator", lambda _hass, _entry: coordinator)
    monkeypatch.setattr(integration, "async_clear_missing_entity_issue", clear_repair)

    assert await integration.async_unload_entry(hass, entry) is False
    clear_repair.assert_not_called()


def test_required_source_availability_logs_only_transitions(caplog) -> None:
    from custom_components.freshairiq.coordinator import FreshAirIQCoordinator

    states = {
        "sensor.outdoor_temperature": SimpleNamespace(state="unavailable"),
        "sensor.outdoor_humidity": SimpleNamespace(state="55"),
    }
    fake = SimpleNamespace(
        hass=SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: states.get(entity_id))),
        _unavailable_required_sources=set(),
        _required_source_entities=lambda: {
            "sensor.outdoor_temperature", "sensor.outdoor_humidity"
        },
    )

    with caplog.at_level("INFO"):
        FreshAirIQCoordinator._log_required_source_availability(fake)
        FreshAirIQCoordinator._log_required_source_availability(fake)
        states["sensor.outdoor_temperature"] = SimpleNamespace(state="12.0")
        FreshAirIQCoordinator._log_required_source_availability(fake)
        FreshAirIQCoordinator._log_required_source_availability(fake)

    messages = [record.getMessage() for record in caplog.records]
    assert messages.count("Required FreshAirIQ source sensor.outdoor_temperature is unavailable") == 1
    assert messages.count("Required FreshAirIQ source sensor.outdoor_temperature is available again") == 1


@pytest.mark.asyncio
async def test_setup_entry_rolls_back_runtime_after_platform_failure(monkeypatch) -> None:
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(),
        async_start_listeners=AsyncMock(),
        async_stop_listeners=AsyncMock(),
    )
    store = SimpleNamespace(async_load=AsyncMock())
    entry = SimpleNamespace(
        entry_id="entry",
        data={"rooms": []},
        options={},
        subentries={},
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=Mock(),
            async_forward_entry_setups=AsyncMock(side_effect=RuntimeError("platform failed")),
        )
    )
    set_runtime = Mock()
    clear_runtime = Mock()
    clear_repair = Mock()

    monkeypatch.setattr(integration, "_async_sync_room_subentries", Mock())
    monkeypatch.setattr(integration, "_async_cleanup_removed_room_registry_entries", Mock())
    monkeypatch.setattr(integration, "LearningStore", lambda *_args: store)
    monkeypatch.setattr(integration, "FreshAirIQCoordinator", lambda *_args: coordinator)
    monkeypatch.setattr(integration, "set_runtime_coordinator", set_runtime)
    monkeypatch.setattr(integration, "clear_runtime_coordinator", clear_runtime)
    monkeypatch.setattr(integration, "async_sync_missing_entity_issue", Mock())
    monkeypatch.setattr(integration, "async_clear_missing_entity_issue", clear_repair)

    with pytest.raises(RuntimeError, match="platform failed"):
        await integration.async_setup_entry(hass, entry)

    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    coordinator.async_start_listeners.assert_awaited_once()
    set_runtime.assert_called_once_with(hass, entry, coordinator)
    coordinator.async_stop_listeners.assert_awaited_once()
    clear_runtime.assert_called_once_with(hass, entry)
    clear_repair.assert_called_once_with(hass, entry)


@pytest.mark.asyncio
async def test_setup_entry_repairs_failure_does_not_block_platform_setup(monkeypatch) -> None:
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(),
        async_start_listeners=AsyncMock(),
    )
    store = SimpleNamespace(async_load=AsyncMock())
    entry = SimpleNamespace(entry_id="entry", data={"rooms": []}, options={}, subentries={})
    forward = AsyncMock()
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_update_entry=Mock(), async_forward_entry_setups=forward)
    )

    monkeypatch.setattr(integration, "_async_sync_room_subentries", Mock())
    monkeypatch.setattr(integration, "_async_cleanup_removed_room_registry_entries", Mock())
    monkeypatch.setattr(integration, "LearningStore", lambda *_args: store)
    monkeypatch.setattr(integration, "FreshAirIQCoordinator", lambda *_args: coordinator)
    monkeypatch.setattr(integration, "set_runtime_coordinator", Mock())
    monkeypatch.setattr(
        integration, "async_sync_missing_entity_issue", Mock(side_effect=RuntimeError("repair backend failed"))
    )

    assert await integration.async_setup_entry(hass, entry) is True
    forward.assert_awaited_once_with(entry, PLATFORMS)
