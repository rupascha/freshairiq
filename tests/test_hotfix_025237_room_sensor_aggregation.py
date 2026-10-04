from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path

from custom_components.freshairiq.climate_sources import aggregate_states
from custom_components.freshairiq.const import (
    CONF_ROOM_TEMPERATURE_AGGREGATION,
    CONF_ROOM_HUMIDITY_AGGREGATION,
)

class States:
    def __init__(self, data): self.data = data
    def get(self, entity_id): return self.data.get(entity_id)

def state(value):
    stamp = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    return SimpleNamespace(state=str(value), last_updated=stamp, last_reported=stamp)

def finite(value):
    try: return float(value)
    except (TypeError, ValueError): return None

def hass(values):
    return SimpleNamespace(states=States({k: state(v) for k, v in values.items()}))

def test_mean_max_min_are_available_for_multiple_valid_sources():
    h = hass({'sensor.a': 18, 'sensor.b': 22, 'sensor.c': 20})
    ids = ['sensor.a', 'sensor.b', 'sensor.c']
    assert aggregate_states(h, ids, finite=finite, strategy='mean').value == 20
    assert aggregate_states(h, ids, finite=finite, strategy='max').value == 22
    assert aggregate_states(h, ids, finite=finite, strategy='min').value == 18

def test_single_sensor_is_exactly_unchanged_for_every_strategy():
    h = hass({'sensor.only': 21.37})
    for strategy in ('mean', 'max', 'min', 'garbage'):
        assert aggregate_states(h, 'sensor.only', finite=finite, strategy=strategy).value == 21.37

def test_unknown_strategy_falls_back_to_mean_for_safe_legacy_behavior():
    h = hass({'sensor.a': 10, 'sensor.b': 20})
    assert aggregate_states(h, ['sensor.a','sensor.b'], finite=finite, strategy='invalid').value == 15

def test_invalid_secondary_source_is_ignored_before_aggregation():
    h = hass({'sensor.a': 19, 'sensor.b': 'unavailable', 'sensor.c': 23})
    assert aggregate_states(h, ['sensor.a','sensor.b','sensor.c'], finite=finite, strategy='max').value == 23
    assert aggregate_states(h, ['sensor.a','sensor.b','sensor.c'], finite=finite, strategy='min').value == 19

def test_dashboard_and_native_room_flow_expose_independent_controls_and_multi_select():
    root=Path(__file__).resolve().parents[1]
    card=(root/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
    flow=(root/'custom_components/freshairiq/config_flow.py').read_text()
    assert 'id="room-temp-aggregation"' in card
    assert 'id="room-humidity-aggregation"' in card
    assert 'temperature_aggregation: get("room-temp-aggregation")' in card
    assert 'humidity_aggregation: get("room-humidity-aggregation")' in card
    assert flow.count('device_class="temperature", multiple=True') >= 2
    assert flow.count('device_class="humidity", multiple=True') >= 2
    assert 'room.setdefault(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean")' in flow
    assert 'room.setdefault(CONF_ROOM_HUMIDITY_AGGREGATION, "mean")' in flow
    assert 'if str(room.get(aggregation_key, "mean")) not in {"mean", "median", "min", "max"}' in flow
    assert 'options=["mean", "median", "max", "min"]' in flow
