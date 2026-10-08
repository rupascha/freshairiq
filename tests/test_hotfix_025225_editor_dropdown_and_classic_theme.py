from pathlib import Path

CARD = Path('custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')


def _editor_source():
    return CARD.split('class FreshAirIQCardEditor extends HTMLElement', 1)[1]


def test_editor_hass_updates_do_not_unconditionally_rebuild_shadow_dom():
    editor = _editor_source()
    setter = editor.split('set hass(h) {', 1)[1].split('    _settingsEntryId()', 1)[0]
    assert 'this._editorRenderContext !== renderContext' in setter
    assert 'this._editorRenderContext = renderContext' in setter
    assert 'this._render();' in setter
    assert 'const renderContext = `${language}|${this._settingsEntryId() || ""}`;' in setter
    # The render must be guarded by the context comparison, rather than running
    # once for every Home Assistant state update and closing a native select.
    assert setter.index('this._editorRenderContext !== renderContext') < setter.index('this._render();')


def test_classic_room_disclosure_uses_home_assistant_theme_text_color():
    assert '.decision-room-disclosure>summary{grid-template-columns:minmax(0,1fr) auto 20px;gap:8px;padding:10px 11px;color:var(--primary-text-color,#fff)}' in CARD
    assert '.decision-room-disclosure>summary span{font-size:12.5px;font-weight:900;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--primary-text-color,#fff)}' in CARD
