from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"

def test_diagnostics_send_uses_user_controlled_file_share_not_hub_upload():
    card=(COMP/"frontend/freshairiq-card.js").read_text()
    diag=(COMP/"diagnostics.py").read_text()
    init=(COMP/"__init__.py").read_text()
    telemetry=(COMP/"telemetry.py").read_text()
    assert 'id="diagnostics-send"' in card
    assert 'an Entwickler schicken' in card
    assert 'support@freshairiq.com' in card
    assert 'navigator.share' in card
    assert 'files: [file]' in card
    assert 'freshairiq/diagnostics/send' not in card
    assert '/api/freshairiq/diagnostics/send' not in diag
    assert 'FreshAirIQDiagnosticsSendView' not in init
    assert 'async_manual_upload' not in telemetry

def test_diagnostics_share_exports_same_complete_diagnostics_payload():
    card=(COMP/"frontend/freshairiq-card.js").read_text()
    assert 'callApi("GET", "freshairiq/diagnostics")' in card
    assert 'new File([JSON.stringify(payload, null, 2)]' in card
    assert 'FreshAirIQ-diagnostics-${stamp}.json' in card

def test_diagnostics_share_has_safe_fallback_without_fake_attachment_claim():
    card=(COMP/"frontend/freshairiq-card.js").read_text()
    assert 'mailto:support@freshairiq.com' in card
    assert 'Diagnosedatei bitte anhängen' in card
    assert 'a.download = filename' in card
    assert 'cooldown' not in card[card.index('async _sendDiagnosticsToDeveloper()'):card.index('_settingsEntryId()', card.index('async _sendDiagnosticsToDeveloper()'))]
