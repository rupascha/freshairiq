from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types

import pytest


def _load_settings_api():
    # Minimal HA HTTP/runtime stubs; the tests exercise FreshAirIQ's own API logic.
    sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    components = sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
    http = types.ModuleType("homeassistant.components.http")

    class HomeAssistantView:
        def json(self, payload, status_code=200):
            return {"status": status_code, "payload": payload}

    http.HomeAssistantView = HomeAssistantView
    sys.modules["homeassistant.components.http"] = http
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    sys.modules["homeassistant.core"] = core

    flow = types.ModuleType("custom_components.freshairiq.config_flow")

    def _normalise_legacy_entry_data(data):
        return dict(data)

    def _normalise_room(raw, rooms, keep_key=None):
        room = dict(raw)
        room.setdefault("key", keep_key or "generated")
        return room, {}

    flow._normalise_legacy_entry_data = _normalise_legacy_entry_data
    flow._normalise_room = _normalise_room
    sys.modules["custom_components.freshairiq.config_flow"] = flow
    sys.modules.pop("custom_components.freshairiq.settings_api", None)
    return importlib.import_module("custom_components.freshairiq.settings_api")


def test_option_coercion_and_server_side_bounds():
    api = _load_settings_api()
    assert api._coerce_option("statistics_days", 365) == 365
    assert api._coerce_option("learning_enabled", "on") is True
    assert api._coerce_option("learning_enabled", "false") is False
    assert api._coerce_option("adult_presence_entities", ["person.a", "", "person.b"]) == ["person.a", "person.b"]
    assert api._coerce_option("operating_profile", "comfort") == "comfort"
    assert api._coerce_option("night_start_hour", "23:05") == "23:05"
    assert api._coerce_option("cross_ventilation_pairs", None) == ""

    with pytest.raises(ValueError):
        api._coerce_option("statistics_days", 366)
    with pytest.raises(ValueError):
        api._coerce_option("operating_profile", "invalid")
    with pytest.raises(ValueError):
        api._coerce_option("learning_enabled", "maybe")
    with pytest.raises(ValueError):
        api._coerce_option("night_start_hour", "29:90")
    with pytest.raises(ValueError):
        api._coerce_option("not_editable", 1)


def test_resident_profile_coercion_sanitises_payload():
    api = _load_settings_api()
    raw = {
        "adult:0": {
            "name": "  Paul   Test  ",
            "room_keys": ["living", "living", "bedroom"],
            "thermal_preference": "hotter-than-sun",
            "notification_targets": ["notify.phone", "notify.phone"],
        },
        "attacker": {"name": "ignored"},
    }
    clean = json.loads(api._coerce_option("resident_room_profiles", json.dumps(raw)))
    assert set(clean) == {"adult:0"}
    assert clean["adult:0"]["name"] == "Paul Test"
    assert clean["adult:0"]["room_keys"] == ["living", "bedroom"]
    assert clean["adult:0"]["thermal_preference"] == "inherit"
    assert clean["adult:0"]["notification_targets"] == ["notify.phone"]

    with pytest.raises(ValueError):
        api._coerce_option("resident_room_profiles", "[]")
    with pytest.raises(ValueError):
        api._coerce_option("resident_room_profiles", "{")


def test_dashboard_room_requires_reference_sensor_pairs_and_preserves_contact_metadata():
    api = _load_settings_api()
    c = importlib.import_module("custom_components.freshairiq.const")
    base = {
        c.CONF_ROOM_NAME: "Wohnküche",
        c.CONF_ROOM_TEMPERATURE: "sensor.temp",
        c.CONF_ROOM_HUMIDITY: "sensor.rh",
        c.CONF_ROOM_CONTACTS: ["binary_sensor.window", "binary_sensor.door"],
        c.CONF_CONTACT_DELAYS: {"binary_sensor.window": 999, "binary_sensor.door": -3},
        c.CONF_CONTACT_ORIENTATIONS: {"binary_sensor.window": "east", "binary_sensor.door": "invalid"},
        c.CONF_CONTACT_REFERENCE_TEMPERATURES: {"binary_sensor.door": "sensor.wg_temp"},
        c.CONF_CONTACT_REFERENCE_HUMIDITIES: {"binary_sensor.door": "sensor.wg_rh"},
        "moisture_sources": ["shower", "invalid"],
    }
    room = api._normalise_dashboard_room(base, [])
    assert room[c.CONF_CONTACT_DELAYS]["binary_sensor.window"] == 600
    assert room[c.CONF_CONTACT_DELAYS]["binary_sensor.door"] == 0
    assert room[c.CONF_CONTACT_ORIENTATIONS]["binary_sensor.door"] == "unknown"
    assert room[c.CONF_CONTACT_REFERENCE_TEMPERATURES]["binary_sensor.door"] == "sensor.wg_temp"
    assert room[c.CONF_CONTACT_REFERENCE_HUMIDITIES]["binary_sensor.door"] == "sensor.wg_rh"
    assert "invalid" not in room["moisture_sources"]

    bad = dict(base)
    bad[c.CONF_CONTACT_REFERENCE_HUMIDITIES] = {}
    with pytest.raises(ValueError, match="benötigt immer Temperatur und Luftfeuchtigkeit"):
        api._normalise_dashboard_room(bad, [])


def test_dashboard_room_sensor_requirement_is_enforced_without_name_error():
    api = _load_settings_api()
    c = importlib.import_module("custom_components.freshairiq.const")
    # This path used to raise NameError because CONF_ROOM_INCLUDE_CALCULATIONS
    # was referenced but not imported by settings_api.py.
    with pytest.raises(ValueError, match="Temperatursensor fehlt"):
        api._normalise_dashboard_room({c.CONF_ROOM_NAME: "Bad", c.CONF_ROOM_HUMIDITY: "sensor.rh"}, [])

    room = api._normalise_dashboard_room({c.CONF_ROOM_NAME: "Optional", c.CONF_ROOM_INCLUDE_CALCULATIONS: False}, [])
    assert room[c.CONF_ROOM_INCLUDE_CALCULATIONS] is False


def test_room_sorting_and_time_validation():
    api = _load_settings_api()
    c = importlib.import_module("custom_components.freshairiq.const")
    rooms = [
        {"key": "b", c.CONF_ROOM_NAME: "B", c.CONF_ROOM_SORT_ORDER: 5},
        {"key": "a", c.CONF_ROOM_NAME: "A", c.CONF_ROOM_SORT_ORDER: 0},
        {"key": "c", c.CONF_ROOM_NAME: "C", c.CONF_ROOM_SORT_ORDER: 5},
    ]
    assert [r["key"] for r in api._sorted_rooms(rooms)] == ["a", "b", "c"]
    assert api.re_time("00:00") and api.re_time("23:59")
    assert not api.re_time("24:00") and not api.re_time("x") and not api.re_time("12:00:00")


@pytest.mark.asyncio
async def test_runtime_update_is_nonblocking_and_rebuilds_listeners_when_requested():
    api = _load_settings_api()

    class Coordinator:
        def __init__(self):
            self.calls = []
        async def async_rebuild_listeners(self, *, invalidate_weather_cache=False):
            self.calls.append(("rebuild", invalidate_weather_cache))
        async def async_request_refresh(self):
            self.calls.append(("refresh",))

    class Hass:
        def __init__(self, coordinator):
            self.data = {api.DOMAIN: {"entry": coordinator}}
            self.tasks = []
        def async_create_task(self, coro):
            task = asyncio.create_task(coro)
            self.tasks.append(task)
            return task

    coordinator = Coordinator()
    entry = types.SimpleNamespace(entry_id="entry", runtime_data=coordinator)
    hass = Hass(coordinator)
    await api._apply_runtime_update(hass, entry, rebuild_listeners=True, invalidate_weather_cache=True)
    await asyncio.gather(*hass.tasks)
    assert coordinator.calls == [("rebuild", True), ("refresh",)]

    empty = Hass(coordinator)
    unloaded_entry = types.SimpleNamespace(entry_id="entry", runtime_data=None)
    await api._apply_runtime_update(empty, unloaded_entry)
    assert not empty.tasks


def test_entry_payload_exposes_only_supported_options_and_notify_services():
    api = _load_settings_api()
    c = importlib.import_module("custom_components.freshairiq.const")

    class Services:
        def async_services(self):
            return {"notify": {"mobile_app_b": object(), "mobile_app_a": object()}}

    hass = types.SimpleNamespace(services=Services())
    entry = types.SimpleNamespace(
        entry_id="id1", title="FreshAirIQ", data={c.CONF_ROOMS: []},
        options={"statistics_days": 90, "internal_secret": "no"},
    )
    payload = api._entry_payload(hass, entry)
    assert payload["options"]["statistics_days"] == 90
    assert "internal_secret" not in payload["options"]
    assert payload["notify_services"] == ["mobile_app_a", "mobile_app_b"]
