from tests.release_version import CURRENT_RELEASE_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


def card_text() -> str:
    return CARD.read_text(encoding="utf-8")


def test_details_header_sticks_to_top_of_actual_scroll_viewport():
    text = card_text()
    assert '.dialog-head{display:grid;grid-template-columns:42px minmax(0,1fr) 42px;align-items:center;gap:8px;position:relative' in text
    assert '.dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto' in text
    assert 'position:sticky;top:calc(env(safe-area-inset-top,0px) + 58px)' not in text


def test_details_window_no_longer_contains_redundant_forecast_quick_setting():
    text = card_text()
    details_start = text.index('    _details(st, rooms) {')
    details_end = text.index('async _exportDiagnostics()', details_start)
    details = text[details_start:details_end]
    assert 'class="detail-quick"' not in details
    assert 'Prognosezeitraum' not in details
    # Forecast configuration remains available through the settings/info system.
    assert '_forecastControls(st)' in text
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).


def test_last_ventilation_detail_has_no_fake_deeper_details_action():
    text = card_text()
    assert 'const openAttr = hero ? ` data-info="lastvent"` : "";' in text
    assert 'vent-result-panel' in text
    assert 'Vollständige Auswertung' in text
    assert '<b>Details ›</b>' not in text
    assert 'Ergebnis öffnen ›' in text


def test_mobile_room_detail_metrics_are_compact_two_column_grid():
    text = card_text()
    assert '.info-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}' in text
    assert '.history-grid,.learn-panel,.info-grid{grid-template-columns:1fr}' not in text


def test_hotfix_version_is_consistent():
    text = card_text()
    assert f'const FAIQ_VERSION = "{CURRENT_RELEASE_VERSION}";' in text
    assert f'VERSION = "{CURRENT_RELEASE_VERSION}"' in (ROOT / 'custom_components/freshairiq/const.py').read_text(encoding='utf-8')
    assert f'"version": "{CURRENT_RELEASE_VERSION}"' in (ROOT / 'custom_components/freshairiq/manifest.json').read_text(encoding='utf-8')
