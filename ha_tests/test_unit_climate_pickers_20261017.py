"""A-27 (0.26.5.1): temperature/humidity sensors with a unit but without a
device class (template/MQTT) were computed correctly but could not be picked,
because every climate picker filtered on the device class only. The pickers now
offer the device class *or* a matching unit. Real Home Assistant selectors.
"""
from __future__ import annotations

import json

import probatio
from homeassistant.helpers import config_validation as cv, selector

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq.const import CONF_ROOM_HUMIDITY, CONF_ROOM_TEMPERATURE

EXPECTED = {
    "temperature": [{"domain": ["sensor"], "device_class": ["temperature"]},
                    {"domain": ["sensor"], "unit_of_measurement": ["°C", "°F", "K"]}],
    "humidity": [{"domain": ["sensor"], "device_class": ["humidity"]},
                 {"domain": ["sensor"], "unit_of_measurement": ["%"]}],
}


def _pickers(schema, names) -> list:
    found = []
    for key, value in schema.schema.items():
        if str(key) in names:
            found.append((str(key), value))
        inner = getattr(value, "schema", None)
        if inner is not None and hasattr(inner, "schema"):
            found.extend(_pickers(inner, names))
    return found


def test_helper_offers_device_class_or_unit() -> None:
    for kind, expected in EXPECTED.items():
        picker = cf._climate_sensor_selector(device_class=kind, multiple=True)
        assert isinstance(picker, selector.EntitySelector)
        assert picker.config["filter"] == expected
        assert picker.config["multiple"] is True
        # validated by Home Assistant's own selector schema (unit filter exists since 2026.8)
        assert selector.EntitySelector(picker.serialize()["selector"]["entity"]).config["filter"] == expected


def test_room_form_climate_pickers_use_unit_fallback() -> None:
    schema = cf._room_schema({}, [])
    pickers = _pickers(schema, {CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY})
    assert {name for name, _ in pickers} == {CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY}
    for name, picker in pickers:
        kind = "temperature" if name == CONF_ROOM_TEMPERATURE else "humidity"
        assert picker.config["filter"] == EXPECTED[kind]
    # serialised exactly as Home Assistant sends a flow form to the frontend
    fields = probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
    assert '"unit_of_measurement"' in json.dumps(fields, ensure_ascii=False)


def test_no_climate_picker_filters_on_the_device_class_alone() -> None:
    with open(cf.__file__, encoding="utf-8") as handle:
        source = handle.read()
    assert 'EntitySelectorConfig(domain="sensor", device_class="temperature"' not in source
    assert 'EntitySelectorConfig(domain="sensor", device_class="humidity"' not in source
    assert source.count("_climate_sensor_selector(device_class=") == 8
