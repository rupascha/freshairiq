"""Support case (2026-10-17, IKEA VINDSTYRKA via Zigbee2MQTT): the entity
``sensor.ik_co_az01_voc_index`` has neither unit nor device class and could not
be picked as VOC/TVOC sensor. Real form schema and real coordinator.
"""
from __future__ import annotations

from homeassistant.helpers import selector

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq.const import CONF_ROOM_VOC
from ha_tests.test_cov_coordinator_b import _cleanup_coordinators, _data, _make, _rooms, _with  # noqa: F401

VOC_INDEX = ("106", {"state_class": "measurement", "icon": "mdi:molecule", "friendly_name": "IK-CO-AZ01 VOC index"})


def _voc_selectors(schema) -> list:
    found = []
    for key, value in schema.schema.items():
        if str(key) == CONF_ROOM_VOC:
            found.append(value)
        inner = getattr(value, "schema", None)
        if inner is not None and hasattr(inner, "schema"):
            found.extend(_voc_selectors(inner))
    return found


def test_voc_picker_accepts_sensors_without_device_class() -> None:
    selectors = _voc_selectors(cf._room_schema({}, []))
    assert selectors
    for picker in selectors:
        assert isinstance(picker, selector.EntitySelector)
        config = picker.config
        filters = config.get("filter") or [config]
        assert all(not f.get("device_class") for f in filters)
        assert all("sensor" in (f.get("domain") or ["sensor"]) for f in filters)


async def test_unitless_voc_index_is_read_as_index(hass, freezer) -> None:
    rooms = _with(_rooms(), "schlaf", **{CONF_ROOM_VOC: "sensor.ik_co_az01_voc_index"})
    d = await _make(hass, freezer, data=_data(rooms), initial={"sensor.ik_co_az01_voc_index": VOC_INDEX})
    await d.step(60)
    room = d.room("schlaf")
    assert room["voc"] == 106.0 and room["voc_available"] is True
    assert room["voc_scale"] == "index"
    # a concentration sensor keeps the previous scale
    d.set("sensor.ik_co_az01_voc_index", "320", {"device_class": "volatile_organic_compounds_parts", "unit_of_measurement": "ppb"})
    await d.step(60)
    assert d.room("schlaf")["voc_scale"] == "concentration"
    # rooms without a VOC sensor carry no scale (unchanged room payload)
    assert "voc_scale" not in d.room("bad")
