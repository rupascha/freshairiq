from pathlib import Path
from tests._source import module_source
ROOT=Path(__file__).parents[1]
def test_activity_heartbeat_privacy_contract():
 t=module_source("telemetry")
 assert '_ACTIVITY_HEARTBEAT_INTERVAL = timedelta(hours=6)' in t
 assert 'async def async_activity_heartbeat' in t
 assert 'last_activity_heartbeat_at' in t
 assert 'if mode == "off" or not self.endpoint' not in t
 assert 'if not self.endpoint' in t
 assert 'force=True' in t
