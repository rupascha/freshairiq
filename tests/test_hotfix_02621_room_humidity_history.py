from datetime import datetime
from pathlib import Path
from tests._source import module_source


def test_room_humidity_history_contract_is_wired_end_to_end():
    storage = module_source("storage")
    coordinator = module_source("coordinator")
    card = Path('custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
    assert 'def record_room_humidity_point' in storage
    assert 'def room_humidity_points' in storage
    assert 'record_room_humidity_point(key, now.replace(tzinfo=None), rh, days=30)' in coordinator
    assert '"humidity_history_14d": self.store.room_humidity_points' in coordinator
    assert 'RAUMLUFTFEUCHTE · ${Math.min(days, 30)} TAGE · %' in card
    assert 'this._svgLine(this._roomChartHistory(r).humidity_history_14d || [], "humidity_percent")' in card  # 0.26.4.7: chart series served on demand (dashboard_transport)
    assert 'FEUCHTE · ${days} TAGE' not in card


def test_room_humidity_history_is_preserved_and_reset_with_statistics():
    storage = module_source("storage")
    assert 'fresh["humidity_points"] = old.get("humidity_points", [])' in storage
    assert 'room["humidity_points"] = []' in storage
