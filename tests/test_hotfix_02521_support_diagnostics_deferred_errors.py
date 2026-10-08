from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _support_method():
    telemetry = (COMP / "telemetry.py").read_text()
    return telemetry.split("async def async_submit_support_diagnostics", 1)[1].split("async def async_maybe_upload", 1)[0]


def test_support_upload_failures_are_queued_privacy_safe():
    telemetry = (COMP / "telemetry.py").read_text()
    method = _support_method()
    assert "FAIQ-SUPPORT-UPLOAD-001" in method
    assert "_async_queue_client_error(payload)" in method
    assert "_client_error_payload" in telemetry
    assert "str(err).startswith(\"support_diagnostics_http_\")" in method
    assert "else type(err).__name__" in method


def test_successful_support_contact_replays_retained_errors():
    telemetry = (COMP / "telemetry.py").read_text()
    method = _support_method()
    assert "_async_flush_client_error_queue(session, headers, timeout)" in method
    assert "/v1/client-errors" in telemetry
    assert "client_error_queue" in telemetry


def test_support_cooldown_still_only_follows_success_and_flush():
    method = _support_method()
    success_update = method.rsplit("self._state.update", 1)[1]
    assert method.index("_async_flush_client_error_queue") < method.rindex("self._state.update")
    assert "support_last_success_at" in success_update
    assert "support_cooldown_until" in success_update


def test_regular_successful_hub_contact_also_replays_retained_errors():
    telemetry = (COMP / "telemetry.py").read_text()
    regular = telemetry.split("async def async_maybe_upload", 1)[1]
    assert "_async_flush_client_error_queue(session, error_headers, timeout)" in regular
    assert regular.index("_async_flush_client_error_queue") < regular.index('"last_success_at": now.isoformat()')
