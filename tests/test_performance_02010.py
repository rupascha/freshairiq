from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_performance_release_version_and_render_filter_present():
    assert 'const FAIQ_VERSION = "0.25.0.72"' in JS
    assert "_relevantStateChanged(previous, next)" in JS
    assert "if (!relevantChanged) return;" in JS
    assert "_queueRender()" in JS
    assert 'typeof requestAnimationFrame === "function"' in JS


def test_entity_caches_are_invalidated_with_settings_changes():
    assert "_invalidateEntityCaches()" in JS
    assert "this._statusEntityId = null" in JS
    assert "this._roomEntityIds = null" in JS
    assert "this._entityCache = {}" in JS


def test_room_merge_uses_cached_freshairiq_room_entities():
    assert "const roomStateIds = this._roomEntityIds && this._roomEntityIds.size" in JS
    assert "Array.from(roomStateIds, id => this._hass.states[id]).filter(Boolean)" in JS


def test_forecast_and_profile_keep_instant_feedback_without_changing_services():
    assert "this._forecastOverride = v" in JS
    assert 'callService("number", "set_value"' in JS
    assert "this._profileOverride = option" in JS
    assert 'callService("select", "select_option"' in JS


def test_existing_scroll_protection_now_uses_non_destructive_live_patching():
    assert 'if (this._info || this._dialogOpen)' in JS
    assert 'this._queueLiveRefresh();' in JS
    assert '_patchLiveNode(current, fresh)' in JS
    assert "this._lastScrollAt = Date.now()" in JS
