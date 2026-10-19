"""0.26.5.2 (community): the outdoor PM2.5 picker offers sensors without the pm25 device class.

WAQI publishes PM2.5 without a device class (some setups show µg/m³ as unit);
the picker only listed sensors with device class pm25. It now accepts the
device class, the µg/m³ unit or a sensor of the WAQI integration.
"""
from __future__ import annotations

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq.const import CONF_OUTDOOR_PM25_ENTITY


def test_outdoor_pm25_picker_accepts_device_class_unit_or_waqi() -> None:
    schema = cf._outdoor_schema({})
    field = next(v for k, v in schema.schema.items() if str(k) == CONF_OUTDOOR_PM25_ENTITY)
    config = field.config
    assert config["multiple"] is True
    filters = config["filter"]
    assert {"domain": ["sensor"], "device_class": ["pm25"]} in filters
    assert any(f.get("unit_of_measurement") and "µg/m³" in f["unit_of_measurement"] for f in filters)
    assert any(f.get("integration") == "waqi" for f in filters)
