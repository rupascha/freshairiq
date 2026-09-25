from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_parent_view_scroll_is_stored_per_view_and_restored_on_back():
    assert "if (!this._infoScrollByView) this._infoScrollByView = new Map()" in JS
    assert "this._infoScrollByView.set(view, top)" in JS
    assert "this._infoScrollByView.get(parent)) ?? stackTop" in JS
    assert "this._pendingSubdialogScrollTop = restoreTop" in JS
    assert "this._infoScrollByView.set(this._info, newSubdialog.scrollTop)" in JS


def test_android_has_scoped_touch_scroll_fallback_without_changing_ios_path():
    assert 'if (!scroller || !/Android/i.test(navigator.userAgent || "")) return;' in JS
    assert 'scroller.addEventListener("touchmove"' in JS
    assert 'this._installAndroidTouchScroll(newDialog)' in JS
    assert 'this._installAndroidTouchScroll(newSubdialog)' in JS
    assert 'if (e.cancelable) e.preventDefault()' in JS


def test_current_version():
    assert 'const FAIQ_VERSION = "0.25.0.76";' in JS
