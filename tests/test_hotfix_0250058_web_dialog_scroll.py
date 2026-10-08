from pathlib import Path

JS = Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_main_details_dialog_handles_desktop_wheel_inside_scrollport():
    assert 'newDialog.addEventListener("wheel", e =>' in JS
    assert 'newDialog.scrollTop += e.deltaY' in JS
    assert 'e.preventDefault();' in JS
    assert 'e.stopPropagation();' in JS
    assert '{ passive: false }' in JS

def test_main_dialog_keeps_native_overflow_scrolling():
    assert '.dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto' in JS
