"""Regression contract: native HA and dashboard are two views of one configuration."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components/freshairiq"
FLOW=(COMP/"config_flow.py").read_text(encoding="utf-8")
API=(COMP/"settings_api.py").read_text(encoding="utf-8")
CARD=(COMP/"frontend/freshairiq-card.js").read_text(encoding="utf-8")

def _native_keys():
    tree=ast.parse((COMP/"settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="NATIVE_OPTION_KEYS" for t in node.targets):
            value=node.value.args[0] if isinstance(node.value,ast.Call) else node.value
            return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS missing")

def test_every_native_global_option_is_exposed_by_dashboard():
    keys=_native_keys()
    for key in keys:
        assert f'key:"{key}"' in CARD, f"Dashboard missing native option {key}"

def test_dashboard_cannot_create_dashboard_only_global_options():
    assert "EDITABLE_OPTION_KEYS = set(NATIVE_OPTION_KEYS)" in API
    assert '"options": {key: options.get(key) for key in sorted(EDITABLE_OPTION_KEYS)}' in API
    assert '"option_keys": sorted(EDITABLE_OPTION_KEYS)' in API

def test_both_surfaces_use_same_configentry_option_store():
    # Dashboard writes entry.options and returns a freshly generated canonical payload.
    assert "options = dict(entry.options)" in API
    assert "hass.config_entries.async_update_entry(entry, options=options)" in API
    assert "return self.json(_entry_payload(hass, entry))" in API
    # Native flow also commits its working options into that same ConfigEntry.
    assert 'kwargs["options"] = new_options' in FLOW
    assert "self.hass.config_entries.async_update_entry(self.config_entry, **kwargs)" in FLOW

def test_dashboard_always_loads_fresh_canonical_state_when_settings_are_opened():
    assert "this._settingsData = null;" in CARD
    assert "await this._loadSettings(true);" in CARD
    assert 'callApi("GET", `freshairiq/settings/${entryId}`)' in CARD
    assert 'if (result && result.data) this._settingsData = result;' in CARD

def test_base_data_surface_parity():
    for key in ("outdoor_weather","outdoor_temperature","outdoor_humidity","pollen_entity"):
        assert f'key:"{key}"' in CARD
        assert key.upper() in API or f"CONF_{key.upper()}" in API
    assert "_DATA_KEYS = {CONF_OUTDOOR_WEATHER, CONF_OUTDOOR_TEMPERATURE, CONF_OUTDOOR_HUMIDITY, CONF_POLLEN_ENTITY}" in API

def test_room_core_fields_exist_on_both_surfaces():
    dashboard_ids={
        "name":"room-name","floor":"room-floor","include_in_calculations":"room-include",
        "temperature":"room-temp","humidity":"room-humidity","contacts":"room-contacts",
        "contact_mode":"room-contact-mode","volume":"room-volume","length":"room-length",
        "width":"room-width","height":"room-height","reference_temperature":"room-ref-temp",
        "reference_humidity":"room-ref-humidity","co2":"room-co2","voc":"room-voc",
        "pm25":"room-pm25","illuminance":"room-illuminance","climate":"room-climate",
        "exhaust_fan":"room-exhaust","supply_fan":"room-supply",
        "ventilation_device":"room-ventilation-device","dehumidifier":"room-dehumidifier",
        "humidifier":"room-humidifier","air_purifier":"room-purifier",
    }
    native_constants={
        "name":"CONF_ROOM_NAME","floor":"CONF_ROOM_FLOOR","include_in_calculations":"CONF_ROOM_INCLUDE_CALCULATIONS",
        "temperature":"CONF_ROOM_TEMPERATURE","humidity":"CONF_ROOM_HUMIDITY","contacts":"CONF_ROOM_CONTACTS",
        "contact_mode":"CONF_CONTACT_MODE","volume":"CONF_ROOM_VOLUME","length":"CONF_ROOM_LENGTH",
        "width":"CONF_ROOM_WIDTH","height":"CONF_ROOM_HEIGHT","reference_temperature":"CONF_ROOM_REFERENCE_TEMPERATURE",
        "reference_humidity":"CONF_ROOM_REFERENCE_HUMIDITY","co2":"CONF_ROOM_CO2","voc":"CONF_ROOM_VOC",
        "pm25":"CONF_ROOM_PM25","illuminance":"CONF_ROOM_ILLUMINANCE","climate":"CONF_ROOM_CLIMATE",
        "exhaust_fan":"CONF_ROOM_EXHAUST_FAN","supply_fan":"CONF_ROOM_SUPPLY_FAN",
        "ventilation_device":"CONF_ROOM_VENTILATION_DEVICE","dehumidifier":"CONF_ROOM_DEHUMIDIFIER",
        "humidifier":"CONF_ROOM_HUMIDIFIER","air_purifier":"CONF_ROOM_AIR_PURIFIER",
    }
    for key,dom_id in dashboard_ids.items():
        assert (f'id="{dom_id}"' in CARD or f'entitySelect("{dom_id}"' in CARD), f"Dashboard room field missing: {key}"
        assert native_constants[key] in FLOW, f"Native room field missing: {key}"

def test_per_contact_settings_share_same_room_storage():
    pairs={
        "contact_delays":"CONF_CONTACT_DELAYS",
        "contact_orientations":"CONF_CONTACT_ORIENTATIONS",
        "contact_reference_temperatures":"CONF_CONTACT_REFERENCE_TEMPERATURES",
        "contact_reference_humidities":"CONF_CONTACT_REFERENCE_HUMIDITIES",
        "contact_covers":"CONF_CONTACT_COVERS",
        "contact_passage_doors":"CONF_CONTACT_PASSAGE_DOORS",
    }
    for js_key,py_key in pairs.items():
        assert js_key in CARD
        assert py_key in FLOW and py_key in API
    assert '_contact_reference_field(str(contact), "passage")' in FLOW
    assert 'room.contact_passage_doors[contact]' in CARD

def test_room_changes_sync_parent_and_native_subentries_in_both_directions():
    # Dashboard -> parent + HA room subentry.
    assert "data[CONF_ROOMS] = _sorted_rooms(rooms)" in API
    assert "_sync_room_subentries(hass, entry, data[CONF_ROOMS])" in API
    # Native room editor -> parent + current subentry.
    assert "data[CONF_ROOMS] = rooms" in FLOW
    assert "self.hass.config_entries.async_update_subentry(" in FLOW
    # Native parent options flow -> all room subentries.
    assert "Keep native room subentries in lockstep with the canonical room data." in FLOW
