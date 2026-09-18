"""Dashboard Settings API runtime behaviour for FreshAirIQ 0.25.0.7."""
from __future__ import annotations

import asyncio
import importlib
import sys
import types


def load_api():
    sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
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
    flow._normalise_legacy_entry_data = lambda data: dict(data)
    def normalise_room(raw, rooms, keep_key=None):
        room = dict(raw)
        room.setdefault("key", keep_key or f"generated_{len(rooms)}")
        return room, {}
    flow._normalise_room = normalise_room
    sys.modules["custom_components.freshairiq.config_flow"] = flow
    sys.modules.pop("custom_components.freshairiq.settings_api", None)
    return importlib.import_module("custom_components.freshairiq.settings_api")


class Services:
    def async_services(self):
        return {"notify": {"phone": object()}}


class Store:
    def __init__(self): self.reset = 0
    async def async_reset_learning(self): self.reset += 1


class Coordinator:
    def __init__(self):
        self.store = Store(); self.refresh = 0; self.rebuild = []
    async def async_request_refresh(self): self.refresh += 1
    async def async_rebuild_listeners(self, *, invalidate_weather_cache=False): self.rebuild.append(invalidate_weather_cache)


class ConfigEntries:
    def __init__(self, entry):
        self.entry = entry; self.reloads = []; self.subupdates = []
    def async_get_entry(self, entry_id): return self.entry if entry_id == self.entry.entry_id else None
    def async_update_entry(self, entry, *, data=None, options=None):
        if data is not None: entry.data = data
        if options is not None: entry.options = options
    def async_schedule_reload(self, entry_id): self.reloads.append(entry_id)
    def async_update_subentry(self, entry, subentry, *, data, title):
        subentry.data = data; subentry.title = title; self.subupdates.append(subentry.unique_id)


class Hass:
    def __init__(self, api, entry):
        self.services = Services(); self.config_entries = ConfigEntries(entry); self.tasks = []
        self.coordinator = Coordinator(); self.data = {}
        entry.runtime_data = self.coordinator
    def async_create_task(self, coro):
        task = asyncio.create_task(coro); self.tasks.append(task); return task


class Request(dict):
    def __init__(self, hass, payload=None, admin=True, json_error=None):
        super().__init__(hass_user=types.SimpleNamespace(is_admin=admin) if admin is not None else None)
        self.app = {"hass": hass}; self.payload = payload or {}; self.json_error = json_error
    async def json(self):
        if self.json_error: raise self.json_error
        return self.payload


def make_entry(api, *, domain=None, data=None, options=None):
    return types.SimpleNamespace(
        entry_id="entry", domain=domain or api.DOMAIN, title="FreshAirIQ",
        data=data or {api.CONF_OUTDOOR_WEATHER:"weather.home", api.CONF_ROOMS:[], api.CONF_LEVELS:[]},
        options=options or {}, subentries={},
    )


def run(coro): return asyncio.run(coro)


def test_sorted_rooms_tolerates_corrupt_sort_order():
    api = load_api()
    rooms = [{"key":"a", api.CONF_ROOM_SORT_ORDER:"broken"}, {"key":"b", api.CONF_ROOM_SORT_ORDER:0}]
    assert {r["key"] for r in api._sorted_rooms(rooms)} == {"a", "b"}


def test_get_authorisation_not_found_and_success():
    api = load_api(); entry = make_entry(api); hass = Hass(api, entry); view = api.FreshAirIQSettingsView()
    assert run(view.get(Request(hass, admin=False), "entry"))["status"] == 403
    assert run(view.get(Request(hass), "missing"))["status"] == 404
    response = run(view.get(Request(hass), "entry"))
    assert response["status"] == 200 and response["payload"]["entry_id"] == "entry"
    entry.domain = "other"
    assert run(view.get(Request(hass), "entry"))["status"] == 404


def test_set_option_and_set_data_runtime_paths():
    api = load_api(); entry = make_entry(api); hass = Hass(api, entry); view = api.FreshAirIQSettingsView()
    response = run(view.post(Request(hass, {"action":"set_option","key":"statistics_days","value":90}), "entry"))
    assert response["status"] == 200 and entry.options["statistics_days"] == 90
    response = run(view.post(Request(hass, {"action":"set_option","key":"adult_presence_entities","value":["person.a"]}), "entry"))
    assert response["status"] == 200
    response = run(view.post(Request(hass, {"action":"set_data","key":api.CONF_OUTDOOR_TEMPERATURE,"value":"sensor.out"}), "entry"))
    assert response["status"] == 200 and entry.data[api.CONF_OUTDOOR_TEMPERATURE] == "sensor.out"
    response = run(view.post(Request(hass, {"action":"set_data","key":"forbidden","value":"x"}), "entry"))
    assert response["status"] == 400
    run(asyncio.gather(*hass.tasks)) if False else None


def test_set_data_allows_deferred_empty_outdoor_source_and_rejects_partial_pair():
    api = load_api(); entry = make_entry(api, data={api.CONF_OUTDOOR_TEMPERATURE:"sensor.t", api.CONF_ROOMS:[], api.CONF_LEVELS:[]}); hass = Hass(api, entry); view=api.FreshAirIQSettingsView()
    # Clearing the final source is valid: FreshAirIQ remains installed and can be configured later.
    response = run(view.post(Request(hass, {"action":"set_data","key":api.CONF_OUTDOOR_TEMPERATURE,"value":""}), "entry"))
    assert response["status"] == 200
    assert api.CONF_OUTDOOR_TEMPERATURE not in entry.data
    # Starting a manual source with only half of the temperature/humidity pair is still rejected.
    response = run(view.post(Request(hass, {"action":"set_data","key":api.CONF_OUTDOOR_TEMPERATURE,"value":"sensor.t"}), "entry"))
    assert response["status"] == 400


def test_levels_upsert_delete_and_reorder_rooms():
    api=load_api(); entry=make_entry(api); hass=Hass(api,entry); view=api.FreshAirIQSettingsView()
    assert run(view.post(Request(hass,{"action":"set_levels","levels":"bad"}),"entry"))["status"] == 400
    assert run(view.post(Request(hass,{"action":"set_levels","levels":["EG","EG"," KG "]}),"entry"))["status"] == 200
    assert entry.data[api.CONF_LEVELS] == ["EG","KG"]

    room={"name":"Bad","floor":"EG","include_in_calculations":False,"contacts":[]}
    assert run(view.post(Request(hass,{"action":"upsert_room","room":room}),"entry"))["status"] == 200
    key=entry.data[api.CONF_ROOMS][0]["key"]
    assert hass.config_entries.reloads == ["entry"]
    assert run(view.post(Request(hass,{"action":"upsert_room","room":{"key":"missing",**room}}),"entry"))["status"] == 400

    # Add a second room, then reorder and delete.
    room2={"name":"Büro","floor":"OG","include_in_calculations":False,"contacts":[]}
    run(view.post(Request(hass,{"action":"upsert_room","room":room2}),"entry"))
    keys=[r["key"] for r in entry.data[api.CONF_ROOMS]]
    assert run(view.post(Request(hass,{"action":"reorder_rooms","order":[keys[1],keys[0]]}),"entry"))["status"] == 200
    assert run(view.post(Request(hass,{"action":"reorder_rooms","order":[keys[0]]}),"entry"))["status"] == 400
    assert run(view.post(Request(hass,{"action":"delete_room","room_key":"missing"}),"entry"))["status"] == 400
    assert run(view.post(Request(hass,{"action":"delete_room","room_key":keys[0]}),"entry"))["status"] == 200


def test_levels_refuse_removing_used_floor():
    api=load_api(); entry=make_entry(api, data={api.CONF_OUTDOOR_WEATHER:"weather.home",api.CONF_LEVELS:["EG"],api.CONF_ROOMS:[{"key":"r","floor":"EG"}]}); hass=Hass(api,entry); view=api.FreshAirIQSettingsView()
    result=run(view.post(Request(hass,{"action":"set_levels","levels":[]}),"entry"))
    assert result["status"] == 400 and "verwendet" in result["payload"]["error"]


def test_reset_defaults_learning_unknown_auth_and_exception_paths():
    api=load_api(); entry=make_entry(api, options={"statistics_days":12}); hass=Hass(api,entry); view=api.FreshAirIQSettingsView()
    assert run(view.post(Request(hass,admin=False),"entry"))["status"] == 403
    assert run(view.post(Request(hass,{"action":"reset_defaults"}),"entry"))["status"] == 200
    assert entry.options == api.DEFAULT_OPTIONS
    assert run(view.post(Request(hass,{"action":"reset_learning"}),"entry"))["status"] == 200
    assert hass.coordinator.store.reset == 1 and hass.coordinator.refresh >= 1
    entry.runtime_data = None
    assert run(view.post(Request(hass,{"action":"reset_learning"}),"entry"))["status"] == 400
    assert run(view.post(Request(hass,{"action":"does_not_exist"}),"entry"))["status"] == 400
    err = run(view.post(Request(hass,json_error=RuntimeError("boom")),"entry"))
    assert err["status"] == 500 and "boom" in err["payload"]["error"]
