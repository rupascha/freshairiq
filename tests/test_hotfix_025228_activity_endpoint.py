from pathlib import Path
from tests._source import module_source
ROOT=Path(__file__).parents[1]
def test_heartbeat_uses_authenticated_activity_endpoint():
 t=module_source("telemetry")
 start=t.index('async def async_activity_heartbeat')
 end=t.index('    def _health(', start)
 heartbeat=t[start:end]
 assert 'token = await self._async_ensure_enrolled(session, installation_id, timeout)' in heartbeat
 assert 'activity_url = f"{self.endpoint}/v1/activity"' in heartbeat
 assert 'headers={"Authorization": f"Bearer {token}"}' in heartbeat
 assert 'force=True' not in heartbeat
