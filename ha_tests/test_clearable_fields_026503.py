"""0.26.5.3: every prefilled optional field can be emptied again and stays empty.

Owner report: per-window reference sensors could not be removed once set.
Cause: ``vol.Optional(default=<stored>)`` re-inserts the stored value when the
frontend drops an emptied field, and ``{**old, **new}`` merges keep it.

The guard is generic on purpose: it walks every options-flow page that is
reachable through menus and plain submissions, and for each clearable field
with a stored value it saves the page with that field emptied and reopens it.
A new form, step or field with the same defect fails here automatically.
"""
from __future__ import annotations

import inspect

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType, section
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq import config_flow, config_flow_options, config_flow_subentry
from custom_components.freshairiq.const import CONF_OUTDOOR_WEATHER, DOMAIN
from custom_components.freshairiq.config_flow_fields import ClearableFormMixin, _clearable_empty, clearable_form_schema
from ha_tests import test_cov_options_flow as opt

WINDOW = "binary_sensor.fenster"
SUBMIT = "<submit shown values>"


def _seed_entry():
    room = opt._room(contacts=[WINDOW], co2=True)
    room.update({
        "contact_reference_temperatures": {WINDOW: "sensor.ref_t"},
        "contact_reference_humidities": {WINDOW: "sensor.ref_h"},
        "contact_covers": {WINDOW: ["cover.rollo"]},
        "voc": "sensor.voc", "pm25": "sensor.pm25", "illuminance": "sensor.lux", "climate": "climate.wz",
        "exhaust_fan": "fan.bad",
        "exhaust_fan_reference_temperature": "sensor.flur_t", "exhaust_fan_reference_humidity": "sensor.flur_h",
        "supply_fan": "fan.zuluft", "dehumidifier": "humidifier.trockner", "moisture_sources": ["cooking"],
    })
    options = {
        "adult_occupants": 1, "adult_resident_names": "Anna", "adult_presence_entities": ["person.anna"],
        "child_occupants": 1, "child_resident_names": "Ben", "child_presence_entities": ["person.ben"],
        "presence_sensor_entities": ["binary_sensor.praesenz"], "pet_safe_presence_entities": ["binary_sensor.tier"],
        "cross_ventilation_pairs": "wohnzimmer:bad", "cross_zone_connections": "eg:og",
        "notification_targets": ["phone"], "notification_room_keys": ["wohnzimmer"],
    }
    return MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, options=options, data={
        CONF_OUTDOOR_WEATHER: "weather.home", "rooms": [room], "levels": ["EG"],
        "outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h",
        "pollen_entity": "sensor.pollen", "outdoor_pm25_entity": "sensor.aussen_pm25",
    })


def _fields(schema, prefix=()):
    for key, validator in schema.schema.items():
        if isinstance(validator, section):
            yield from _fields(validator.schema, (*prefix, str(key)))
        else:
            yield prefix, key, validator


def _shown(key):
    """The value the form shows for a field (what the frontend submits back)."""
    suggested = (getattr(key, "description", None) or {}).get("suggested_value")
    if suggested is not None:
        return suggested
    return key.default() if key.default is not vol.UNDEFINED else None


def _submission(schema, *, drop: tuple | None = None) -> dict:
    """What the frontend sends: every shown value, emptied fields left out."""
    data: dict = {}
    for prefix, key, validator in _fields(schema):
        value = _shown(key)
        if value is None and isinstance(key, vol.Required) and isinstance(validator, selector.SelectSelector):
            first = validator.config["options"][0]
            value = first["value"] if isinstance(first, dict) else first
        if value is None and isinstance(key, vol.Required) and isinstance(validator, selector.BooleanSelector):
            value = False
        if value in (None, "") or (*prefix, str(key)) == drop:
            continue
        target = data
        for part in prefix:
            target = target.setdefault(part, {})
        target[str(key)] = value
    return data


def _clearable(schema) -> list[tuple]:
    return [
        (*prefix, str(key)) for prefix, key, validator in _fields(schema)
        if isinstance(key, vol.Optional) and _clearable_empty(validator) is not None and _shown(key) not in (None, "", [])
    ]


async def _replay(hass, entry, path):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    for action in path:
        user_input = _submission(result["data_schema"]) if action == SUBMIT else {"next_step_id": action}
        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    return result


def _abort(hass, result) -> None:
    if result["type"] in (FlowResultType.FORM, FlowResultType.MENU):
        hass.config_entries.options.async_abort(result["flow_id"])


async def _forms_with_stored_values(hass, entry) -> list[tuple[list, str, tuple]]:
    found, seen = [], set()

    async def walk(path, depth):
        result = await _replay(hass, entry, path)
        _abort(hass, result)
        if result["type"] is FlowResultType.FORM and result.get("data_schema"):
            found.extend((path, result["step_id"], field) for field in _clearable(result["data_schema"]))
            children = [SUBMIT]
        elif result["type"] is FlowResultType.MENU:
            children = [n for n in result["menu_options"] if n not in {"finish", "reset_learning", "reset_defaults"}]
        else:
            return
        for child in children if depth < 8 else []:
            try:
                nxt = await _replay(hass, entry, [*path, child])
            except Exception:  # noqa: BLE001 - a page that needs typed input ends this branch
                continue
            _abort(hass, nxt)
            marker = (nxt.get("step_id"), str(nxt["type"]))
            if nxt["type"] in (FlowResultType.FORM, FlowResultType.MENU) and marker not in seen:
                seen.add(marker)
                await walk([*path, child], depth + 1)

    await walk([], 0)
    return found


async def test_every_stored_optional_field_can_be_removed_in_the_options_flow(hass) -> None:
    entry = _seed_entry()
    entry.add_to_hass(hass)
    targets = await _forms_with_stored_values(hass, entry)
    steps = {step for _path, step, _field in targets}
    # the walk really reaches the pages of the owner report and the other editors
    assert {"contact_references", "edit_room", "outdoor", "residents", "cross_ventilation", "notifications"} <= steps
    assert len(targets) >= 25
    stuck = []
    for path, step, field in targets:
        await hass.config_entries.async_remove(entry.entry_id)
        entry = _seed_entry()
        entry.add_to_hass(hass)
        form = await _replay(hass, entry, path)
        result = await hass.config_entries.options.async_configure(form["flow_id"], _submission(form["data_schema"], drop=field))
        _abort(hass, result)
        if result.get("step_id") == step and result.get("errors"):
            continue  # validation refused the change (e.g. half of a sensor pair): nothing saved
        reopened = await _replay(hass, entry, path)
        _abort(hass, reopened)
        if field in _clearable(reopened["data_schema"]):
            stuck.append(f"{step}:{'/'.join(field)}")
    assert stuck == []


async def test_window_reference_pair_is_removed_from_the_stored_room(hass) -> None:
    """Owner report, end to end: the pair is gone from the entry, not only from the form."""
    entry = _seed_entry()
    entry.add_to_hass(hass)
    targets = await _forms_with_stored_values(hass, entry)
    path = next(p for p, step, _f in targets if step == "contact_references")
    form = await _replay(hass, entry, path)
    data = _submission(form["data_schema"])
    data.pop("reference_temperature")
    data.pop("reference_humidity")
    result = await hass.config_entries.options.async_configure(form["flow_id"], data)
    _abort(hass, result)
    room = entry.data["rooms"][0]
    assert room["contact_reference_temperatures"] == {}
    assert room["contact_reference_humidities"] == {}


def test_stored_values_never_become_voluptuous_defaults_of_clearable_fields() -> None:
    entity = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    schema = clearable_form_schema(vol.Schema({
        vol.Optional("sensor", default="sensor.alt"): entity,
        vol.Optional("many", default=["a"]): selector.SelectSelector(selector.SelectSelectorConfig(options=["a", "b"], multiple=True)),
        vol.Optional("text", default="x"): selector.TextSelector(),
        vol.Optional("delay", default=5): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10)),
        vol.Required("part"): section(vol.Schema({vol.Optional("inner", default="sensor.innen"): entity})),
    }))
    keys = {str(k): k for k in schema.schema}
    assert all(keys[name].default is vol.UNDEFINED for name in ("sensor", "many", "text"))
    assert keys["sensor"].description == {"suggested_value": "sensor.alt"}
    assert keys["delay"].default() == 5  # numbers keep their default: an empty number is no removal
    assert schema({"part": {}}) == {"sensor": "", "many": [], "text": "", "delay": 5, "part": {"inner": ""}}
    assert schema({"sensor": "sensor.neu", "part": {"inner": "sensor.x"}})["sensor"] == "sensor.neu"
    assert clearable_form_schema(None) is None


@pytest.mark.parametrize("flow_class", [
    config_flow.FreshAirIQConfigFlow, config_flow_options.FreshAirIQOptionsFlow, config_flow_subentry.FreshAirIQRoomSubentryFlow,
])
def test_every_flow_shows_its_forms_through_the_clearing_schema(flow_class) -> None:
    assert flow_class.async_show_form is ClearableFormMixin.async_show_form


def test_no_other_flow_handler_exists_without_the_clearing_schema() -> None:
    handlers = {
        cls for module in (config_flow, config_flow_options, config_flow_subentry)
        for _name, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, (config_entries.ConfigFlow, config_entries.OptionsFlow, config_entries.ConfigSubentryFlow))
        and cls.__module__.startswith("custom_components.freshairiq")
    }
    assert handlers and all(cls.async_show_form is ClearableFormMixin.async_show_form for cls in handlers)
