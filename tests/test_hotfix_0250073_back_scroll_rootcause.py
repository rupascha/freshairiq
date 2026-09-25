from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_render_does_not_overwrite_parent_scroll_with_stale_child_dom():
    bad = "this._infoScrollByView.set(this._info, oldSubdialog.scrollTop)"
    assert bad not in JS
    assert "this._rememberInfoViewport(this._info);" in JS
    assert "this._pendingSubdialogScrollTop = restoreTop; this._render();" in JS
    assert "newSubdialog.scrollTop = oldSubScroll;" in JS


def test_current_version():
    assert 'const FAIQ_VERSION = "0.25.0.75";' in JS
