"""Static release contracts for optional room-climate entities in 0.25.0.7."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_optional_entity_fields_are_available_in_native_and_dashboard_editors():
    config = (COMP / "config_flow.py").read_text(encoding="utf-8")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    for key in (
        "CONF_ROOM_VOC", "CONF_ROOM_PM25", "CONF_ROOM_ILLUMINANCE",
        "CONF_CONTACT_COVERS", "CONF_ROOM_CLIMATE", "CONF_ROOM_EXHAUST_FAN",
        "CONF_ROOM_SUPPLY_FAN", "CONF_ROOM_VENTILATION_DEVICE",
        "CONF_ROOM_DEHUMIDIFIER", "CONF_ROOM_HUMIDIFIER", "CONF_ROOM_AIR_PURIFIER",
    ):
        assert key in config
    for element_id in (
        "room-voc", "room-pm25", "room-illuminance", "room-contact-covers",
        "room-climate", "room-exhaust", "room-supply", "room-ventilation-device",
        "room-dehumidifier", "room-humidifier", "room-purifier",
    ):
        assert element_id in card


def test_explicit_intervention_action_is_documented_and_registered():
    init_py = (COMP / "__init__.py").read_text(encoding="utf-8")
    services = (COMP / "services.yaml").read_text(encoding="utf-8")
    assert '"execute_intervention"' in init_py
    assert "execute_intervention:" in services
    assert "niemals automatisch" in services
