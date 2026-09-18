from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_all_open_windows_use_live_patch_queue_without_full_rerender():
    assert "if (this._info || this._dialogOpen)" in JS
    assert "this._queueLiveRefresh();" in JS
    assert "_refreshOpenViewsLive()" in JS
    assert "_patchLiveNode(current, fresh)" in JS


def test_live_patching_preserves_the_scroll_container_nodes():
    block = JS[JS.index("_refreshOpenViewsLive() {"):JS.index("_relevantStateChanged(previous, next)")]
    assert 'this.shadowRoot.querySelector(".modal")' in block
    assert 'this.shadowRoot.querySelector(".subdialog")' in block
    assert "this._patchLiveNode(current, fresh)" in block
    assert "this.shadowRoot.innerHTML" not in block


def test_scroll_restore_and_scroll_tracking_remain_intact():
    assert "newDialog.scrollTop = oldScroll" in JS
    assert "this._dialogScrollTop = newDialog.scrollTop" in JS
    assert "this._lastScrollAt = Date.now()" in JS
