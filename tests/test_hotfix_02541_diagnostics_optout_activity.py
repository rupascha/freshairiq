"""Heartbeat and the diagnostics switch.

0.25.4.1 deliberately kept the installation heartbeat running when automatic
diagnostics were switched off. GitHub issue #10 (0.26.4.1) showed users expect
"off" to mean no contact at all, so the heartbeat now needs consent AND a
reporting mode other than "off" (consent gate since 0.26.3.1).
"""
from pathlib import Path
ROOT = Path(__file__).parents[1]


def _heartbeat():
    text = (ROOT / 'custom_components/freshairiq/telemetry.py').read_text()
    start = text.index('async def async_activity_heartbeat')
    return text[start:text.index('    def _health(', start)]


def test_heartbeat_respects_consent_and_reporting_mode_off_before_any_request():
    heartbeat = _heartbeat()
    consent = heartbeat.index('normalise_consent(self.entry.options.get("diagnostics_consent")) != "granted"')
    mode_off = heartbeat.index('normalise_reporting_mode(self.entry.options.get("diagnostics_reporting_mode", "daily")) == "off"')
    request = heartbeat.index('/v1/activity')
    assert consent < request and mode_off < request
