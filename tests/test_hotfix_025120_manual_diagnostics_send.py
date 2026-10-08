from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_diagnostics_send_is_explicit_direct_support_upload_with_fallback_contact():
    card = (COMP / "frontend/freshairiq-card.js").read_text()
    diag = (COMP / "diagnostics.py").read_text()
    init = (COMP / "__init__.py").read_text()
    telemetry = (COMP / "telemetry.py").read_text()
    assert 'id="diagnostics-send"' in card
    assert '<b>Diagnosedaten</b><span>an Support senden</span>' in card
    assert 'support@freshairiq.com' in card
    assert 'id="diagnostics-message"' in card
    assert 'window.prompt(' not in card
    assert 'window.confirm(this._t("support.confirm"))' not in card
    assert 'callApi("POST", "freshairiq/support-diagnostics"' in card
    assert '/api/freshairiq/support-diagnostics' in diag
    assert 'FreshAirIQSupportDiagnosticsView' in init
    assert 'async_submit_support_diagnostics' in telemetry
    assert '/v1/support/diagnostics' in telemetry


def test_support_upload_cooldown_is_persisted_only_after_success():
    telemetry = (COMP / "telemetry.py").read_text()
    method = telemetry.split('async def async_submit_support_diagnostics', 1)[1].split('async def async_maybe_upload', 1)[0]
    assert 'support_cooldown_until' in method
    assert 'SUPPORT_DIAGNOSTICS_COOLDOWN_SECONDS' in method
    assert 'response.status' in method
    assert method.index('response.status') < method.rindex('"support_cooldown_until"')


def test_support_upload_keeps_detailed_export_and_user_message_together():
    telemetry = (COMP / "telemetry.py").read_text()
    method = telemetry.split('async def async_submit_support_diagnostics', 1)[1].split('async def async_maybe_upload', 1)[0]
    assert 'exported = await self.recorder.async_export()' in method
    assert '"user_message": text' in method
    assert '"diagnostics": exported' in method
    assert 'len(text) > SUPPORT_DIAGNOSTICS_MESSAGE_MAX_CHARS' in method
