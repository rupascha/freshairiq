from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
DIAG=(ROOT/"custom_components/freshairiq/diagnostics.py").read_text()

def test_setup_requires_real_room_configuration():
    assert "setup_completed = configured_rooms > 0" in DIAG
    assert "bool(configured_rooms or records)" not in DIAG

def test_back_navigation_uses_pending_scroll_restore_not_overwritten_by_child_view():
    assert "this._pendingSubdialogScrollTop = restoreTop; this._render();" in JS
    assert "const oldSubScroll = this._pendingSubdialogScrollTop !== null" in JS
    assert "this._infoScrollByView" in JS
    assert "this._pendingSubdialogScrollTop = null;" in JS

def test_forward_navigation_explicitly_starts_new_view_at_top():
    assert "this._pendingSubdialogScrollTop = 0; this._info = next; this._render();" in JS

def test_android_has_single_native_scrollport_without_zero_height_hack():
    assert ".dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto" in JS
    assert ".dialog-scroll{touch-action:pan-y pinch-zoom}" in JS
    assert ".dialog-scroll,.dialog-scroll *{touch-action:pan-y}" not in JS
    assert ".dialog-scroll{min-height:0;height:0" not in JS
