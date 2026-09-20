from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
CARD = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")


def _main_card_block() -> str:
    return CARD[CARD.index("class FreshAirIQCard extends HTMLElement"):CARD.index("class FreshAirIQCardEditor extends HTMLElement")]


def test_main_card_uses_one_persistent_static_stylesheet():
    block = _main_card_block()
    assert "const FAIQ_CARD_CSS = `" in CARD
    assert "_ensureStaticStyle()" in block
    assert 'style.id = "faiq-static-style"' in block
    assert "style.textContent = FAIQ_CARD_CSS" in block
    assert "_replaceRenderedContent(html)" in block
    # Full renders may replace card content, but must no longer rebuild the 46 KB CSS.
    assert 'this.shadowRoot.innerHTML = `<style>' not in block
    assert "var(--faiq-hero-color)" in CARD
    assert 'this.style.setProperty("--faiq-hero-color", hero.color)' in block


def test_open_views_deduplicate_state_and_identical_html_before_dom_patch():
    block = _main_card_block()
    assert "_liveViewStateSnapshot(key)" in block
    assert "refs[index] === previous.refs[index]" in block
    assert "if (this._liveViewStateSnapshot(viewKey))" in block
    assert "_freshLiveNode(cacheKey, html, selector)" in block
    assert "if (this._liveHtmlCache[cacheKey] === html) return null;" in block
    assert "this._patchLiveNode(current, fresh)" in block


def test_current_freshairiq_controls_use_relevant_entity_index_with_legacy_fallback():
    block = _main_card_block()
    assert "_freshAirIQStates(status = null)" in block
    assert "Array.from(this._relevantStateIds, id => this._hass.states[id]).filter(Boolean)" in block
    # Current tagged controls use the small FreshAirIQ entity set.
    assert block.count("const indexedStates = this._freshAirIQStates(status);") >= 3
    # Backward compatibility remains: legacy untagged FreshAirIQ controls can still be found globally.
    assert block.count("const legacyStates = Object.values((this._hass && this._hass.states) || {});") >= 3


def test_chart_and_learning_html_are_reference_cached_without_changing_math():
    block = _main_card_block()
    assert "this._chartCache = { bars: new WeakMap(), line: new WeakMap() }" in block
    assert "if (cache && cache.has(rows)) return cache.get(rows);" in block
    assert "if (cache) cache.set(rows, html);" in block
    assert "if (cached && cached.model === model && cached.backtest === backtest) return cached.html;" in block
    assert "this._learningCardCache = { model, backtest, html };" in block


def test_performance_hotfix_does_not_change_backend_version_contracts():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.25.0.41"
    assert 'VERSION = "0.25.0.41"' in (COMP / "const.py").read_text(encoding="utf-8")
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.41";' in (COMP / "frontend" / name).read_text(encoding="utf-8")
