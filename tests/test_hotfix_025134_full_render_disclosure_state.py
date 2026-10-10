from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')

def test_classic_disclosure_state_is_owned_outside_dom():
    assert 'this._classicDisclosureOpen = new Set()' in JS
    assert 'summary[data-classic-disclosure]' in JS
    assert 'this._classicDisclosureOpen.add(key)' in JS
    assert 'this._classicDisclosureOpen.delete(key)' in JS

def test_decision_disclosure_rehydrates_open_state_on_full_render():
    assert '<details class="decision-more"><summary data-classic-disclosure="decision">' in JS
    assert 'el.open = this._classicDisclosureOpen.has(key)' in JS

def test_room_disclosures_have_stable_keys_and_rehydrate_open_state():
    assert '<summary data-classic-disclosure="room:${esc(r.key)}">' in JS
    assert 'el.open = this._classicDisclosureOpen.has(key)' in JS

def test_full_render_replaces_dom_but_persistent_state_survives_in_card_instance():
    replace=JS[JS.index('    _replaceRenderedContent(html) {'):JS.index('    disconnectedCallback()')]
    assert 'this.shadowRoot.removeChild(node)' in replace
    constructor=JS[JS.index('    constructor() {'):JS.index('    _uiLanguage() {')]
    assert 'this._classicDisclosureOpen = new Set()' in constructor
