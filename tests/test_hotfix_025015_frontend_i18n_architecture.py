from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


def source():
    return CARD.read_text(encoding="utf-8")


def block(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def test_keyed_frontend_catalog_has_both_languages():
    s = source()
    catalog = block(s, "const FAIQ_UI = Object.freeze({", "});")
    assert ' de: ' in catalog and ' en: ' in catalog
    assert '"iq.handling"' in catalog
    assert '"shell.rooms"' in catalog


def test_iq_dashboard_uses_keyed_i18n_not_new_hardcoded_copy():
    s = source()
    iq = block(s, "    _compactAIPanel(st, rooms = []) {", "    _intelligentPanel(st, rooms = []) {")
    for literal in ["FreshAirIQ übernimmt", "Aktuell ist kein Eingreifen nötig.", "weitere Räume ohne akuten Handlungsbedarf", ">Nacht<", ">Lernen<"]:
        assert literal not in iq
    assert 'this._t("iq.handling")' in iq
    assert 'this._t("iq.no_action")' in iq


def test_shared_dual_dashboard_shell_uses_keyed_i18n():
    s = source()
    render = block(s, "    _render() {", "    getCardSize()")
    assert 'this._t("shell.subtitle_iq")' in render
    assert 'this._t("shell.details")' in render
    assert 'this._t("shell.guests")' in render
    assert 'this._t("shell.rooms")' in render


def test_legacy_translation_happens_before_fragment_is_mounted():
    s = source()
    fn = block(s, "    _replaceRenderedContent(html) {", "    disconnectedCallback()")
    localize = fn.index("this._localizeLegacyFragment(template.content)")
    append = fn.index("this.shadowRoot.appendChild(template.content)")
    assert localize < append
    assert "_localizeRenderedUi" not in s


def test_new_keyed_translator_has_english_fallback_and_variables():
    s = source()
    fn = block(s, "    _t(key, vars = {}) {", "    _localizeLegacyFragment(root) {")
    assert "entry.en ?? entry.de" in fn
    assert "Object.entries(vars)" in fn
