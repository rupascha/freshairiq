from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# test_dashboard_multiselect_preserves_legacy_scalar_sensor: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).


def test_repairs_normalizes_legacy_and_multi_sensor_references():
    source = (ROOT / "custom_components/freshairiq/repairs.py").read_text()
    assert "from .climate_sources import entity_ids" in source
    assert "for temperature in entity_ids(room.get(CONF_ROOM_TEMPERATURE))" in source
    assert "for humidity in entity_ids(room.get(CONF_ROOM_HUMIDITY))" in source
    assert 'str(room.get(CONF_ROOM_TEMPERATURE) or "").strip()' not in source


def test_sensor_recovery_is_group_based_for_redundant_room_sources():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text()
    assert "def _required_source_groups" in source
    assert "any_available = False" in source
    assert "if not any_available:" in source
    assert 'groups.append((f"room:{room_key}:{key}", ids))' in source
