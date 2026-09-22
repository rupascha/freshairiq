from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_release_version_is_020102():
    assert 'const FAIQ_VERSION = "0.25.0.53"' in JS
    assert 'VERSION = "0.25.0.53"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.53"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")


def test_every_open_window_receives_coalesced_live_updates():
    assert '_queueLiveRefresh()' in JS
    assert 'if (this._info || this._dialogOpen)' in JS
    setter = JS[JS.index('    set hass(h) {'):JS.index('    getCardSize()', JS.index('    set hass(h) {'))]
    assert 'this._queueLiveRefresh();' in setter
    assert 'return;' in setter


def test_live_refresh_updates_both_details_and_subdialogs_in_place():
    block = JS[JS.index('    _refreshOpenViewsLive() {'):JS.index('    _relevantStateChanged(previous, next)')]
    assert 'this._details(st, rooms)' in block
    assert 'this._infoPanel(st, rooms)' in block
    assert 'this._patchLiveNode(current, fresh)' in block
    assert 'this.shadowRoot.innerHTML' not in block


def test_live_patcher_does_not_overwrite_focused_form_controls():
    block = JS[JS.index('    _patchLiveNode(current, fresh) {'):JS.index('    _refreshOpenViewsLive() {')]
    assert 'activeElement === current' in block
    assert 'if (!active)' in block
    assert 'const tag = String(current.tagName || "").toUpperCase()' in block
    assert 'tag === "INPUT"' in block
    assert 'tag === "TEXTAREA" || tag === "SELECT"' in block


def test_live_patcher_never_replaces_interactive_subtrees_on_shape_change():
    block = JS[JS.index('    _patchLiveNode(current, fresh) {'):JS.index('    _refreshOpenViewsLive() {')]
    assert 'interactiveSelector' in block
    assert 'containsInteraction' in block
    assert 'if (!containsInteraction)' in block
    assert 'current.innerHTML = fresh.innerHTML' in block
