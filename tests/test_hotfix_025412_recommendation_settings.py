import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
FLOW = (COMP / "config_flow.py").read_text(encoding="utf-8")
CARD = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_recommendation_affecting_settings_are_grouped_together():
    start = FLOW.index("async def async_step_ventilation_settings")
    block = FLOW[start:FLOW.index("async def async_step_notification_energy_settings", start)]
    for step in ("profile", "forecast", "air_quality", "cross_ventilation", "recommendation_priorities", "threshold", "model"):
        assert f'"{step}"' in block


def test_priorities_are_one_complete_ranked_form():
    block = FLOW[FLOW.index("def _goal_priority_schema"):FLOW.index("# Legacy room-level reference keys")]
    assert 'goal_priority_{idx}' in block
    assert 'wizard_back' in block
    assert 'goal_to_move' not in block
    assert 'move_direction' not in block


def test_priority_ui_and_recommendations_copy_is_localized_de_en():
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    assert de["options"]["step"]["ventilation_settings"]["title"] == "Empfehlungen"
    assert en["options"]["step"]["ventilation_settings"]["title"] == "Recommendations"
    for lang in (de, en):
        step = lang["options"]["step"]["recommendation_priority_order"]
        assert all(f"goal_priority_{i}" in step["data"] for i in range(1, 4))
        assert all(f"goal_priority_{i}" in step["data_description"] for i in range(1, 4))
        assert "wizard_back" in step["data"]


def test_support_diagnostics_path_is_single_and_correct():
    assert "Energie & Daten → Diagnose-Freigabe" not in CARD
    assert CARD.count("Daten & Lernen → Diagnose-Freigabe") >= 1


def test_optional_room_entity_selectors_are_clearable_by_contract():
    # Optional entity fields must use vol.Optional; no optional sensor may become
    # required merely because it was configured once.
    room = FLOW[FLOW.index("def _room_schema"):FLOW.index("def _contact_reference_field")]
    for key in ("CONF_ROOM_CO2", "CONF_ROOM_VOC", "CONF_ROOM_PM25", "CONF_ROOM_ILLUMINANCE", "CONF_ROOM_CLIMATE", "CONF_ROOM_EXHAUST_FAN", "CONF_ROOM_SUPPLY_FAN", "CONF_ROOM_VENTILATION_DEVICE", "CONF_ROOM_DEHUMIDIFIER", "CONF_ROOM_HUMIDIFIER", "CONF_ROOM_AIR_PURIFIER"):
        assert f"_optional({key}" in room
