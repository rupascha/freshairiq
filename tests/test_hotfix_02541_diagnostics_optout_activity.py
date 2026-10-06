from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_diagnostics_optout_does_not_disable_installation_heartbeat():
    text=(ROOT/'custom_components/freshairiq/telemetry.py').read_text()
    start=text.index('async def async_activity_heartbeat')
    end=text.index('    def _health(', start)
    heartbeat=text[start:end]
    assert 'diagnostics_reporting_mode' not in heartbeat
    assert 'mode == "off"' not in heartbeat
    assert '/v1/activity' in heartbeat
