from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
JS = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
FLOW = (COMP / "config_flow.py").read_text(encoding="utf-8")
CONST = (COMP / "const.py").read_text(encoding="utf-8")


def test_023009_version_is_current():
    assert 'VERSION = "0.25.0.66"' in CONST
    assert 'const FAIQ_VERSION = "0.25.0.66";' in JS


def test_reference_pair_is_atomic_in_devices_services_flow():
    assert 'def _apply_contact_references' in FLOW
    assert 'if bool(temp) != bool(humidity):' in FLOW
    assert 'errors["base"] = "contact_reference_pair_required"' in FLOW
    assert 'CONF_CONTACT_REFERENCE_TEMPERATURES' in FLOW
    assert 'CONF_CONTACT_REFERENCE_HUMIDITIES' in FLOW


def test_reference_sensor_selectors_do_not_require_device_class():
    # Reference-air sensors must accept legitimate °C/% sensors without HA device_class metadata.
    assert 'async def async_step_room_references' in FLOW
    assert 'async def async_step_contact_references' in FLOW
    assert '_contact_reference_schema(room, self.hass)' in FLOW


def test_dashboard_accepts_unit_based_temperature_and_humidity_sensors():
    assert 'deviceClass === "temperature" && ["°c","°f","c","f","k"].includes(unit)' in JS
    assert 'deviceClass === "humidity" && ["%","%rh","rh%"].includes(unit)' in JS


def test_unsaved_room_reference_pair_survives_live_refresh():
    assert 'current.closest(".room-form")' in JS
    assert 'if (isUnsavedRoomControl) return;' in JS
