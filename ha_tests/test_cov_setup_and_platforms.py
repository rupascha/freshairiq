"""Real Home Assistant runtime coverage for setup, lifecycle and entity platforms.

Every test drives FreshAirIQ through a real ``hass`` instance (config entries,
service registry, entity/device registries, Lovelace resources) and asserts the
observable result: entity states, stored options, registry contents, raised
service errors or recorded diagnostics.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant import config_entries
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

import custom_components.freshairiq as integration
from custom_components.freshairiq import repairs, room_creation_trace, weather_future
from custom_components.freshairiq.const import (
    CONF_CONTACT_DELAY,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_ROOM_CONTACT,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_SUBENTRY_KEYS,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
    CONTACT_MODE_ANY,
    DOMAIN,
    STORAGE_KEY,
)
from custom_components.freshairiq.entity import FreshAirIQEntity
from custom_components.freshairiq.storage import REMOVED_ROOM_MARKER


# ---------------------------------------------------------------------------
# helpers


def _room(key: str = "wohnzimmer", name: str = "Wohnzimmer") -> dict:
    return {
        "key": key,
        CONF_ROOM_NAME: name,
        CONF_ROOM_TEMPERATURE: f"sensor.{key}_temperature",
        CONF_ROOM_HUMIDITY: f"sensor.{key}_humidity",
        CONF_ROOM_CONTACTS: [f"binary_sensor.{key}_window"],
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
        CONF_ROOM_VOLUME: 55.0,
        CONF_ROOM_FLOOR: "EG",
        CONF_ROOM_INCLUDE_CALCULATIONS: True,
    }


def _set_sources(hass, *room_keys: str) -> None:
    hass.states.async_set("sensor.outdoor_temperature", "10", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.outdoor_humidity", "70", {"unit_of_measurement": "%"})
    for key in room_keys:
        hass.states.async_set(f"sensor.{key}_temperature", "21", {"unit_of_measurement": "°C"})
        hass.states.async_set(f"sensor.{key}_humidity", "60", {"unit_of_measurement": "%"})
        hass.states.async_set(f"binary_sensor.{key}_window", "off")


def _entry(*, rooms: list[dict] | None = None, options: dict | None = None, **kwargs) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        version=8,
        data={
            CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature",
            CONF_OUTDOOR_HUMIDITY: "sensor.outdoor_humidity",
            "rooms": list(rooms if rooms is not None else [_room()]),
            "levels": ["EG"],
        },
        options=dict(options or {}),
        **kwargs,
    )


async def _setup(hass, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def _unload(hass, entry: MockConfigEntry) -> None:
    if entry.state is ConfigEntryState.LOADED:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
async def loaded(hass):
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    yield entry
    await _unload(hass, entry)


# ---------------------------------------------------------------------------
# platforms: sensor / number / select / button


async def test_room_sensors_publish_mapped_states_and_room_payload(hass, loaded) -> None:
    registry = er.async_get(hass)
    action_id = registry.async_get_entity_id("sensor", DOMAIN, f"{loaded.entry_id}_wohnzimmer_action")
    mould_id = registry.async_get_entity_id("sensor", DOMAIN, f"{loaded.entry_id}_wohnzimmer_mould_level")
    learning_id = registry.async_get_entity_id("sensor", DOMAIN, f"{loaded.entry_id}_wohnzimmer_learning_status")
    aligned_id = registry.async_get_entity_id("sensor", DOMAIN, f"{loaded.entry_id}_wohnzimmer_house_aligned_action")
    action = hass.states.get(action_id)
    assert action is not None and action.state not in {"unavailable", "unknown", ""}
    assert action.attributes["freshairiq_room_key"] == "wohnzimmer"
    assert action.attributes["freshairiq_transport"] == "room_v2"
    assert action.attributes["freshairiq_entry_id"] == loaded.entry_id
    assert isinstance(action.attributes["freshairiq_room_payload"], dict)
    assert hass.states.get(mould_id).state not in {"unavailable", ""}
    assert hass.states.get(learning_id).state not in {"unavailable", ""}
    assert hass.states.get(aligned_id) is not None

    # A non-action room sensor exposes only the identity attributes (no payload).
    humidity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{loaded.entry_id}_wohnzimmer_delta_g_m3")
    attrs = hass.states.get(humidity_id).attributes
    assert "freshairiq_room_payload" not in attrs

    # Unknown raw values map to the documented fallbacks.
    coordinator = loaded.runtime_data
    room = coordinator.data["rooms"]["wohnzimmer"]
    room.update(action="nonsense", house_aligned_action="nonsense", mould_level="nonsense", learning_status="nonsense")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(action_id).state == "unknown"
    assert hass.states.get(aligned_id).state == "unknown"
    assert hass.states.get(mould_id).state == "unknown"
    assert hass.states.get(learning_id).state == "base_estimate"

    # The room disappearing from the payload removes the payload attribute.
    coordinator.data["rooms"].pop("wohnzimmer")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get(action_id)
    assert state.state == "unavailable"


async def test_number_entities_clamp_and_persist_options(hass, loaded) -> None:
    registry = er.async_get(hass)
    horizon = registry.async_get_entity_id("number", DOMAIN, f"{loaded.entry_id}_forecast_horizon")
    adults = registry.async_get_entity_id("number", DOMAIN, f"{loaded.entry_id}_guest_adults")
    children = registry.async_get_entity_id("number", DOMAIN, f"{loaded.entry_id}_guest_children")

    await hass.services.async_call("number", "set_value", {"entity_id": horizon, "value": 45.4}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": adults, "value": 3}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": children, "value": 2}, blocking=True)
    await hass.async_block_till_done()

    assert loaded.options["forecast_horizon_min"] == 45
    assert loaded.options["guest_adults"] == 3
    assert loaded.options["guest_children"] == 2
    assert float(hass.states.get(horizon).state) == 45.0
    assert float(hass.states.get(adults).state) == 3.0
    assert float(hass.states.get(children).state) == 2.0


async def test_select_entity_persists_operating_profile(hass, loaded) -> None:
    entity_id = er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{loaded.entry_id}_operating_profile")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": "dehumidify"}, blocking=True
    )
    await hass.async_block_till_done()
    assert loaded.options["operating_profile"] == "dehumidify"
    assert hass.states.get(entity_id).state == "dehumidify"


async def test_buttons_reset_store_and_propagate_native_errors(hass, loaded, monkeypatch) -> None:
    registry = er.async_get(hass)
    learning = registry.async_get_entity_id("button", DOMAIN, f"{loaded.entry_id}_reset_learning")
    statistics = registry.async_get_entity_id("button", DOMAIN, f"{loaded.entry_id}_reset_statistics")
    store = loaded.runtime_data.store
    reset_learning = AsyncMock()
    reset_statistics = AsyncMock()
    monkeypatch.setattr(store, "async_reset_learning", reset_learning)
    monkeypatch.setattr(store, "async_reset_statistics", reset_statistics)

    await hass.services.async_call("button", "press", {"entity_id": learning}, blocking=True)
    await hass.services.async_call("button", "press", {"entity_id": statistics}, blocking=True)
    reset_learning.assert_awaited_once()
    reset_statistics.assert_awaited_once()

    native = HomeAssistantError("already translated")
    monkeypatch.setattr(store, "async_reset_learning", AsyncMock(side_effect=native))
    monkeypatch.setattr(store, "async_reset_statistics", AsyncMock(side_effect=native))
    for entity_id in (learning, statistics):
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
        assert err.value is native


async def test_real_learning_reset_button_succeeds(hass, loaded) -> None:
    entity_id = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{loaded.entry_id}_reset_learning")
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state not in {"unknown", "unavailable"}


def test_base_entity_without_translation_key_uses_fallback_name() -> None:
    entity = FreshAirIQEntity(SimpleNamespace(), SimpleNamespace(entry_id="e1"), "plain", "Plain name")
    assert entity.name == "Plain name"
    assert entity.unique_id == "e1_plain"
    assert entity.extra_state_attributes["freshairiq_entity_key"] == "plain"


# ---------------------------------------------------------------------------
# execute_intervention action


async def test_intervention_action_without_loaded_entry(hass) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "execute_intervention", {"room_key": "x"}, blocking=True)
    assert err.value.translation_key == "integration_not_loaded"


async def test_intervention_action_validation_and_execution(hass, loaded) -> None:
    room = loaded.runtime_data.data["rooms"]["wohnzimmer"]

    async def _call(**data):
        await hass.services.async_call(DOMAIN, "execute_intervention", data, blocking=True)

    with pytest.raises(ServiceValidationError) as err:
        await _call(room_key="nope")
    assert err.value.translation_key == "unknown_room"

    room["interventions"] = []
    with pytest.raises(ServiceValidationError) as err:
        await _call(room_key="wohnzimmer")
    assert err.value.translation_key == "no_executable_intervention"

    room["interventions"] = [{"key": "bad", "entity_id": "fan", "service": "fan.turn_on"}]
    with pytest.raises(ServiceValidationError) as err:
        await _call(room_key="wohnzimmer")
    assert err.value.translation_key == "invalid_intervention_action"

    hass.states.async_set("fan.bath", "off")
    calls = async_mock_service(hass, "fan", "turn_on")
    room["interventions"] = [
        {"key": "run", "entity_id": "fan.bath", "service": "fan.turn_on", "service_data": {"percentage": 60}}
    ]
    await _call(room_key="wohnzimmer", intervention_key="run")
    assert len(calls) == 1
    assert calls[0].data == {"percentage": 60, "entity_id": "fan.bath"}

    native = HomeAssistantError("native")

    async def _native(call: ServiceCall) -> None:
        raise native

    async def _generic(call: ServiceCall) -> None:
        raise ValueError("boom")

    hass.services.async_register("fan", "native_fail", _native)
    hass.services.async_register("fan", "generic_fail", _generic)
    room["interventions"] = [{"key": "n", "entity_id": "fan.bath", "service": "fan.native_fail"}]
    with pytest.raises(HomeAssistantError) as err:
        await _call(room_key="wohnzimmer")
    assert err.value is native

    room["interventions"] = [{"key": "g", "entity_id": "fan.bath", "service": "fan.generic_fail"}]
    with pytest.raises(HomeAssistantError) as err:
        await _call(room_key="wohnzimmer")
    assert err.value.translation_key == "intervention_execution_failed"
    assert err.value.translation_placeholders == {"service": "fan.generic_fail"}
    assert isinstance(err.value.__cause__, ValueError)


# ---------------------------------------------------------------------------
# async_setup: frontend registration


async def test_lovelace_resource_registered_once_and_legacy_duplicates_migrated(hass, loaded) -> None:
    resources = hass.data[LOVELACE_DATA].resources
    ours = [item for item in resources.async_items() if integration._is_freshairiq_resource(item.get("url"))]
    assert len(ours) == 1
    assert ours[0]["url"] == integration._FRONTEND_MODULE

    # Simulate an older install: stale loader URL with wrong type plus a duplicate.
    await resources.async_update_item(ours[0]["id"], {"url": integration._FRONTEND_OLD_LOADER_BASE, "res_type": "js"})
    await resources.async_create_item({"res_type": "module", "url": f"{integration._FRONTEND_MODULE_BASE}?v=old"})
    await resources.async_create_item({"res_type": "module", "url": f"{integration._FRONTEND_MODULE_BASE}?v=older"})

    real_delete = resources.async_delete_item
    deleted: list[str] = []

    async def _delete(item_id):
        if deleted:
            raise RuntimeError("storage locked")
        deleted.append(item_id)
        await real_delete(item_id)

    resources.async_delete_item = _delete
    try:
        assert await integration._async_register_lovelace_resource(hass) is True
    finally:
        resources.async_delete_item = real_delete

    ours = [item for item in resources.async_items() if integration._is_freshairiq_resource(item.get("url"))]
    # first entry updated in place, one duplicate removed, the failing delete tolerated
    assert len(ours) == 2
    assert ours[0]["url"] == integration._FRONTEND_MODULE
    assert ours[0]["type"] == "module"
    assert len(deleted) == 1
    assert integration._is_freshairiq_resource(None) is False


async def test_lovelace_registration_fallbacks(hass, loaded, monkeypatch, caplog) -> None:
    lovelace = hass.data[LOVELACE_DATA]
    resources = lovelace.resources

    monkeypatch.setattr(resources, "async_get_info", AsyncMock(side_effect=RuntimeError("broken store")))
    with caplog.at_level("ERROR"):
        assert await integration._async_register_lovelace_resource(hass) is False
    assert "Could not register the FreshAirIQ Lovelace resource" in caplog.text

    monkeypatch.setitem(hass.data, LOVELACE_DATA, SimpleNamespace(resource_mode="yaml", resources=None))
    assert await integration._async_register_lovelace_resource(hass) is False

    hass.data.pop(LOVELACE_DATA)
    with caplog.at_level("WARNING"):
        assert await integration._async_register_lovelace_resource(hass) is False
    assert "Lovelace data is unavailable" in caplog.text
    hass.data[LOVELACE_DATA] = lovelace


async def test_async_setup_tolerates_compression_and_static_path_failures(hass, loaded, monkeypatch) -> None:
    added: list[str] = []
    monkeypatch.setattr(integration, "add_extra_js_url", lambda _hass, url: added.append(url))
    monkeypatch.setattr(integration, "_async_register_lovelace_resource", AsyncMock(return_value=False))
    monkeypatch.setattr(hass.http, "async_register_static_paths", AsyncMock(side_effect=RuntimeError("dup")))
    monkeypatch.setattr(integration, "_precompress_frontend", lambda: (_ for _ in ()).throw(OSError("ro fs")))

    assert await integration.async_setup(hass, {}) is True
    # Fallback loader added, already-registered views/services are not duplicated.
    assert added == [integration._FRONTEND_MODULE]
    assert hass.services.has_service(DOMAIN, "execute_intervention")

    monkeypatch.setattr(integration, "_precompress_frontend", lambda: {"errors": ["card.js"]})
    assert await integration.async_setup(hass, {}) is True


def test_precompress_uses_brotli_when_available(monkeypatch) -> None:
    fake = SimpleNamespace(compress=lambda data, quality: b"br:" + data + bytes([quality]))
    monkeypatch.setitem(sys.modules, "brotli", fake)
    seen = {}

    def _ensure(directory, compressor):
        seen["dir"] = directory
        seen["out"] = compressor(b"x")
        return {"written": [], "errors": []}

    monkeypatch.setattr(integration, "ensure_precompressed", _ensure)
    assert integration._precompress_frontend() == {"written": [], "errors": []}
    assert seen["dir"] == integration._FRONTEND_DIR
    assert seen["out"] == b"br:x\n"

    monkeypatch.setitem(sys.modules, "brotli", None)  # import now fails
    monkeypatch.setattr(integration, "ensure_precompressed", lambda directory, compressor: {"compressor": compressor})
    assert integration._precompress_frontend() == {"compressor": None}


# ---------------------------------------------------------------------------
# async_setup_entry housekeeping


async def test_setup_repairs_contradictory_options_and_drops_foreign_subentries(hass, hass_storage) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = _entry(
        options={"target_rh": 70.0, "start_rh": 60.0, "notification_cooldown_min": 30},
        subentries_data=[{
            "data": {"key": "ghost", "name": "Geist"},
            "subentry_type": "room",
            "title": "Geist",
            "unique_id": "room:ghost",
        }],
    )
    entry.add_to_hass(hass)
    hass_storage[f"{STORAGE_KEY}.{entry.entry_id}"] = {
        "version": 1,
        "key": f"{STORAGE_KEY}.{entry.entry_id}",
        "data": {"rooms": {"ghost": {"samples": 3}}},
    }
    await _setup(hass, entry)
    try:
        assert entry.options["target_rh"] == 60.0  # repaired to start_rh
        assert entry.options["notification_cooldown_min"] == 30  # untouched
        assert {sub.unique_id for sub in entry.subentries.values()} == {"room:wohnzimmer"}
        assert entry.data[CONF_ROOM_SUBENTRY_KEYS] == ["wohnzimmer"]
        ghost = entry.runtime_data.store.data["rooms"]["ghost"]
        assert REMOVED_ROOM_MARKER in ghost
    finally:
        await _unload(hass, entry)


async def test_setup_survives_prune_and_watch_failures(hass, monkeypatch) -> None:
    _set_sources(hass, "wohnzimmer")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(integration.LearningStore, "prune_removed_rooms", _boom)
    monkeypatch.setattr(integration, "_async_watch_room_subentry_deletion", _boom)
    entry = await _setup(hass, _entry())
    assert entry.runtime_data is not None
    await _unload(hass, entry)


async def test_platform_failure_rolls_back_even_if_repair_cleanup_fails(hass, monkeypatch) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = _entry()
    entry.add_to_hass(hass)
    monkeypatch.setattr(
        hass.config_entries, "async_forward_entry_setups", AsyncMock(side_effect=RuntimeError("platform"))
    )
    monkeypatch.setattr(
        integration, "async_clear_missing_entity_issue", lambda *_a: (_ for _ in ()).throw(RuntimeError("ir"))
    )
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert getattr(entry, "runtime_data", None) is None


async def test_unload_tolerates_repair_cleanup_failure(hass, loaded, monkeypatch) -> None:
    monkeypatch.setattr(
        integration, "async_clear_missing_entity_issue", lambda *_a: (_ for _ in ()).throw(RuntimeError("ir"))
    )
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert loaded.state is ConfigEntryState.NOT_LOADED
    assert getattr(loaded, "runtime_data", None) is None


async def test_reload_keeps_entities_available(hass, loaded) -> None:
    assert await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    assert loaded.state is ConfigEntryState.LOADED
    entity_id = er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{loaded.entry_id}_operating_profile")
    assert hass.states.get(entity_id).state == "comfort"


async def test_deleting_room_subentry_reloads_and_removes_room(hass) -> None:
    _set_sources(hass, "wohnzimmer", "bad")
    entry = await _setup(hass, _entry(rooms=[_room(), _room("bad", "Bad")]))
    try:
        assert sorted(entry.data[CONF_ROOM_SUBENTRY_KEYS]) == ["bad", "wohnzimmer"]
        devices = dr.async_get(hass)
        assert devices.async_get_device_by_identifier((DOMAIN, f"{entry.entry_id}:room:bad"), entry.entry_id) is not None

        # An unrelated entry change does not schedule a FreshAirIQ reload.
        other = MockConfigEntry(domain="other")
        other.add_to_hass(hass)
        async_dispatcher_send(hass, config_entries.SIGNAL_CONFIG_ENTRY_CHANGED, None, other)

        sub = next(s for s in entry.subentries.values() if s.unique_id == "room:bad")
        hass.config_entries.async_remove_subentry(entry, sub.subentry_id)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert [room["key"] for room in entry.data["rooms"]] == ["wohnzimmer"]
        assert entry.data[CONF_ROOM_SUBENTRY_KEYS] == ["wohnzimmer"]
        assert devices.async_get_device_by_identifier((DOMAIN, f"{entry.entry_id}:room:bad"), entry.entry_id) is None
    finally:
        await _unload(hass, entry)


async def test_subentry_watch_helpers_without_signal_or_known_keys(hass, monkeypatch) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert integration._rooms_pending_subentry_deletion(entry) == set()
    monkeypatch.delattr(config_entries, "SIGNAL_CONFIG_ENTRY_CHANGED")
    before = len(entry._on_unload or [])
    integration._async_watch_room_subentry_deletion(hass, entry)
    assert len(entry._on_unload or []) == before


async def test_registry_cleanup_skips_malformed_device_items(hass, monkeypatch) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    stale = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}:room:old")}
    )
    malformed = object()
    short_identifier = SimpleNamespace(id="short", identifiers={("only-domain",), 5})
    real_iter = integration._iter_device_entries
    monkeypatch.setattr(
        integration,
        "_iter_device_entries",
        lambda registry, entry_id: [malformed, short_identifier, *real_iter(registry, entry_id)],
    )
    integration._async_cleanup_removed_room_registry_entries(hass, entry)
    assert devices.async_get(stale.id) is None


# ---------------------------------------------------------------------------
# migration


async def test_migration_through_real_config_entries(hass) -> None:
    current = MockConfigEntry(domain=DOMAIN, version=8, data={"rooms": []})
    current.add_to_hass(hass)
    assert await integration.async_migrate_entry(hass, current) is True
    assert current.version == 8 and current.data == {"rooms": []}

    legacy = MockConfigEntry(
        domain="freshairiq_legacy_probe",
        version=7,
        data={
            "rooms": [
                {"key": "a", CONF_ROOM_NAME: "A", CONF_ROOM_CONTACT: "binary_sensor.a", CONF_CONTACT_DELAY: "abc",
                 CONF_ROOM_FLOOR: "OG"},
                {"key": "b", CONF_ROOM_NAME: "B", CONF_ROOM_CONTACTS: "binary_sensor.b", CONF_CONTACT_DELAY: 999,
                 "length": 4, "width": 3, "height": 2.5},
            ]
        },
        options={"min_potential_percent_total_water": 10.0},
    )
    legacy.add_to_hass(hass)
    assert await integration.async_migrate_entry(hass, legacy) is True
    assert legacy.version == 8
    a, b = legacy.data["rooms"]
    assert a[CONF_ROOM_CONTACTS] == ["binary_sensor.a"]
    assert a[CONF_CONTACT_DELAYS] == {"binary_sensor.a": 0}
    assert b[CONF_CONTACT_DELAYS] == {"binary_sensor.b": 300}
    assert b["contact_orientations"] == {"binary_sensor.b": "unknown"}
    assert legacy.data["levels"] == ["OG", "ground_floor"]
    assert b["volume_mode"] == "dimensions" and a["volume_mode"] == "direct"
    assert legacy.options["threshold_mode"] == "adaptive_home_size"


# ---------------------------------------------------------------------------
# repairs


async def test_repairs_handle_string_contacts_duplicates_and_bad_room_container(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_OUTDOOR_TEMPERATURE: "sensor.gone_outdoor",
            "rooms": [
                {"key": "a", "name": "A", CONF_ROOM_TEMPERATURE: "sensor.gone_outdoor",
                 CONF_ROOM_CONTACTS: "binary_sensor.gone_window"},
            ],
        },
    )
    entry.add_to_hass(hass)
    missing = repairs.missing_required_entities(hass, entry)
    ids = [entity_id for entity_id, _ in missing]
    assert ids == ["sensor.gone_outdoor", "binary_sensor.gone_window"]

    repairs.async_sync_missing_entity_issue(hass, entry)
    from homeassistant.helpers import issue_registry as ir

    issue = ir.async_get(hass).async_get_issue(DOMAIN, repairs.issue_id_for_entry(entry))
    assert issue is not None and "binary_sensor.gone_window" in issue.translation_placeholders["entities"]
    repairs.async_clear_missing_entity_issue(hass, entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, repairs.issue_id_for_entry(entry)) is None

    broken = SimpleNamespace(data={CONF_OUTDOOR_HUMIDITY: "sensor.h", "rooms": "corrupt"})
    assert repairs._required_entity_references(broken, "en") == [("sensor.h", "Outdoor humidity")]


# ---------------------------------------------------------------------------
# room creation trace


async def test_room_creation_trace_records_sparse_events(hass) -> None:
    events: list[dict] = []

    async def _record(event):
        events.append(event)

    recorder = SimpleNamespace(async_record_room_creation_trace=_record)
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(diagnostics=recorder),
        data={"rooms": [{"key": "a"}, {"key": ""}, "bad"]},
        subentries={"s": SimpleNamespace(subentry_type="room", unique_id="room:a")},
    )
    room_creation_trace.trace_room_creation(
        hass, entry, source="flow", stage="commit", room_key="a", outcome="ok",
        error_type="X" * 100, extra={"attempt": 2, "secret_name": "Küche"},
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    event = events[0]
    assert event["attempt"] == 2 and "secret_name" not in event
    assert event["parent_room_count"] == 3
    assert len(event["parent_room_fingerprints"]) == 1  # empty key yields no fingerprint
    assert len(event["error_type"]) == 80

    entry.data = {"rooms": "corrupt"}
    assert room_creation_trace.room_creation_snapshot(entry)["parent_room_count"] == 0

    # Without a recorder nothing is scheduled.
    room_creation_trace.trace_room_creation(hass, SimpleNamespace(data={}), source="x", stage="y")

    # Post-reload trace: unknown entry is ignored, a known one is recorded.
    room_creation_trace.trace_room_creation_after_reload(hass, "missing", source="flow", delay_seconds=0)
    await hass.async_block_till_done()
    assert len(events) == 1

    real = MockConfigEntry(domain=DOMAIN, data={"rooms": [{"key": "b"}]})
    real.add_to_hass(hass)
    real.runtime_data = SimpleNamespace(diagnostics=recorder)
    room_creation_trace.trace_room_creation_after_reload(hass, real.entry_id, source="flow", room_key="b", delay_seconds=0)
    await hass.async_block_till_done()
    assert events[-1]["stage"] == "post_reload_state"
    assert events[-1]["outcome"] == "observed"


# ---------------------------------------------------------------------------
# weather_future


def test_future_boundaries_skip_invalid_rows_and_out_of_range_horizons() -> None:
    now = dt_util.now()
    rows = [
        {"datetime": now + timedelta(hours=1), "temperature_c": 12.0, "humidity": 70.0},
        {"datetime": now + timedelta(hours=2), "temperature_c": "nan", "humidity": 70.0},
        {"datetime": now + timedelta(hours=14), "temperature_c": 8.0, "humidity": 80.0},
    ]
    result = weather_future.future_boundaries(rows, now, 10.0, 75.0, delays=(30, 800, 900))
    assert set(result) == {30}  # 800 min > 12 h guard, 900 min beyond the last row
    assert result[30]["source"] == "weather_hourly_interpolated"
    assert result[30]["confidence"] == 90


def test_forecast_datetime_parser_rejects_empty_and_unparseable_values() -> None:
    assert weather_future._dt(None) is None
    assert weather_future._dt("") is None
    assert weather_future._dt("not-a-date") is None
    parsed = weather_future._dt("2026-10-16T12:00:00+00:00")
    assert parsed is not None and parsed.utcoffset() is not None
