from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manual_support_send_uses_explicit_point_in_time_health_snapshot():
    telemetry = (ROOT / "custom_components/freshairiq/telemetry.py").read_text(encoding="utf-8")
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    method = telemetry.split("async def async_submit_support_diagnostics", 1)[1].split("async def async_maybe_upload", 1)[0]
    assert '"health_snapshot": dict(self._health_snapshot(now))' in method
    assert '"health_snapshot": dict(self._health())' not in method
    assert "health_snapshot_provider=lambda now:" in coordinator
    assert '"captured_at": now.isoformat()' in coordinator
    assert 'self.runtime_health.health_snapshot(now)' in coordinator


def test_health_snapshot_provider_is_fail_safe():
    telemetry = (ROOT / "custom_components/freshairiq/telemetry.py").read_text(encoding="utf-8")
    assert "def _health_snapshot(self, now: datetime)" in telemetry
    assert "return dict(self._health())" in telemetry
