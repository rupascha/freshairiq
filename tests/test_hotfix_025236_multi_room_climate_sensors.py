from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.freshairiq.climate_sources import aggregate_states, entity_ids


class States:
    def __init__(self, data): self.data = data
    def get(self, entity_id): return self.data.get(entity_id)


def state(value, second=0):
    stamp = datetime(2026, 10, 4, 10, 0, second, tzinfo=timezone.utc)
    return SimpleNamespace(state=str(value), last_updated=stamp, last_reported=stamp)


def finite(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def test_legacy_single_sensor_is_bit_for_bit_value_compatible():
    hass = SimpleNamespace(states=States({"sensor.old": state(21.37)}))
    result = aggregate_states(hass, "sensor.old", finite=finite)
    assert entity_ids("sensor.old") == ["sensor.old"]
    assert result.value == 21.37
    assert result.configured == result.available == 1


def test_multiple_valid_sensors_use_arithmetic_mean():
    hass = SimpleNamespace(states=States({"sensor.a": state(20), "sensor.b": state(22)}))
    result = aggregate_states(hass, ["sensor.a", "sensor.b"], finite=finite)
    assert result.value == 21.0
    assert result.configured == result.available == 2


def test_unavailable_secondary_sensor_does_not_break_healthy_room():
    hass = SimpleNamespace(states=States({"sensor.a": state(20), "sensor.b": state("unavailable")}))
    result = aggregate_states(hass, ["sensor.a", "sensor.b"], finite=finite)
    assert result.value == 20.0
    assert result.configured == 2
    assert result.available == 1


def test_no_valid_sensor_remains_unavailable():
    hass = SimpleNamespace(states=States({"sensor.a": state("unknown")}))
    result = aggregate_states(hass, ["sensor.a", "sensor.missing"], finite=finite)
    assert result.value is None
    assert result.available == 0


def test_duplicates_are_removed_without_reordering():
    assert entity_ids(["sensor.a", "sensor.a", "sensor.b"]) == ["sensor.a", "sensor.b"]


def test_dashboard_and_native_flow_are_multi_select_but_legacy_storage_is_supported():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    config = (root / "custom_components/freshairiq/config_flow.py").read_text()
    card = (root / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert 'device_class="temperature", multiple=True' in config
    assert 'device_class="humidity", multiple=True' in config
    assert 'entitySelect("room-temp",["sensor"],r.temperature,"temperature",true)' in card
    assert 'entitySelect("room-humidity",["sensor"],r.humidity,"humidity",true)' in card
    assert 'Array.from(get("room-temp").selectedOptions)' in card
    assert 'Array.from(get("room-humidity").selectedOptions)' in card


def test_entity_ids_rejects_non_collection_values():
    assert entity_ids(None) == []
    assert entity_ids(42) == []


def test_non_numeric_sensor_value_is_ignored_even_when_state_is_available():
    hass = SimpleNamespace(states=States({"sensor.bad": state("not-a-number"), "sensor.good": state(19)}))
    result = aggregate_states(hass, ["sensor.bad", "sensor.good"], finite=finite)
    assert result.value == 19.0
    assert result.available == 1
