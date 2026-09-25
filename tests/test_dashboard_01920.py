from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


def card_text() -> str:
    return CARD.read_text(encoding="utf-8")


def test_dashboard_information_tiles_open_details():
    text = card_text()
    assert 'data-info="moisture"><span>BISHER</span>' in text
    assert 'data-info="moisture"><span>JETZT ENTFERNBAR</span>' in text
    assert 'data-info="mould"><span>SCHIMMEL</span>' in text
    assert 'data-info="water"><span>WASSER IN DER LUFT</span>' in text
    assert 'data-info="night"><span>NACHTPROGNOSE</span>' in text
    assert 'data-info="temperature"><span>TEMPERATUR LIVE</span>' in text
    assert 'data-info="time"><span>IQ-ZEIT</span>' in text


def test_live_moisture_and_mould_breakdowns_link_to_rooms():
    text = card_text()
    assert 'LIVE-FEUCHTEBILANZ NACH RÄUMEN' in text
    assert 'SCHIMMEL-IQ · RISIKO NACH RÄUMEN' in text
    assert 'breakdown-row clickable" data-room="${esc(r.key)}"' in text


def test_nested_detail_navigation_uses_history_stack():
    text = card_text()
    assert 'this._infoStack = []' in text
    assert 'if (this._info) this._infoStack.push(this._info)' in text
    assert 'const parent = this._infoStack.length ? this._infoStack.pop() : null' in text
    assert '_infoBackButton()' in text
    assert '_infoNav()' in text


def test_all_subdialogs_keep_stable_scrollers_while_values_update_live():
    text = card_text()
    assert 'if (this._info || this._dialogOpen)' in text
    assert 'this._queueLiveRefresh();' in text
    assert '_patchLiveNode(current, fresh)' in text
    assert 'overscroll-behavior-y:contain' in text
    assert 'overflow-anchor:none' in text
    assert '-webkit-overflow-scrolling:touch' in text


def test_room_detail_is_intelligence_view():
    text = card_text()
    assert 'RAUM-INTELLIGENZ' in text
    assert 'FRESHAIRIQ EMPFIEHLT' in text
    assert 'WARUM?' in text
    assert 'RAUMMODELL' in text


def test_close_controls_respect_safe_area_and_have_large_targets():
    text = card_text()
    assert 'env(safe-area-inset-top,0px) + 58px' in text
    assert '.info-nav{position:sticky;top:0;z-index:30' in text
    assert '.info-close{position:static;width:42px;height:42px' in text
    assert '.info-back{position:static;width:42px;height:42px' in text
    assert '.dialog-head{display:grid;grid-template-columns:42px minmax(0,1fr) 42px' in text
    assert '.dialog-head{display:grid;grid-template-columns:42px minmax(0,1fr) 42px 42px;align-items:center;gap:8px;position:relative' in text
    assert '.dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto' in text
    assert '.close{font-size:18px;width:42px;height:42px' in text


def test_interactive_subdialogs_are_live_without_special_case_freezing():
    text = card_text()
    assert 'this._info === "profile" ? this._profileControls(st)' in text
    assert 'this._info === "next5" ? this._forecastControls(st)' in text
    assert 'this._info === "guests" ? this._guestControls(st)' in text


def test_hotfix_01921_all_windows_keep_navigation_visible_while_scrolling():
    text = card_text()
    assert 'role="toolbar" aria-label="Fensternavigation"' in text
    assert '${this._infoNav()}${this._infoPanel(st, rooms)}' in text
    assert 'id="details-back" class="dialog-back" aria-label="Zurück"' in text
    assert 'const detailsBack = this.shadowRoot.getElementById("details-back")' in text
    # The subwindow back button is always rendered; with an empty history the
    # existing handler returns to the dashboard instead of inventing a fake level.
    assert 'return `<button class="info-back" id="info-back" aria-label="Zurück"' in text
    assert 'const parent = this._infoStack.length ? this._infoStack.pop() : null' in text
