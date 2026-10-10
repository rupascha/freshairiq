"""0.26.4.9: larger room view text and an explanation window per tile (community: "Was bedeutet Oberflächen-RH?")."""
from __future__ import annotations

import re

from tests.frontend_source import CARD_FILE

CARD = CARD_FILE.read_text(encoding="utf-8")


def _room_detail_line() -> str:
    return next(line for line in CARD.splitlines() if "RAUM-INTELLIGENZ · ${days} TAGE" in line and "room-iq-hero" in line)


def test_every_room_tile_opens_an_explanation():
    line = _room_detail_line()
    keys = set(re.findall(r'data-explain="([a-z_]+)"', line)) | {"balance", "potential"}
    texts = CARD[CARD.index("    _explainText(key, r, st) {"):]
    texts = texts[: texts.index("        const row = texts[key];")]
    for key in keys:
        assert re.search(rf"\n            {key}: \[t\(", texts), key
    assert {"climate", "surface_rh", "learning", "last_learning", "data_quality", "routine", "strategy", "feedback", "shadow"} <= keys
    assert 'data-explain="${r.active ? "balance" : "potential"}"' in line


def test_rh_is_explained_in_both_languages():
    assert "RH steht für relative Luftfeuchte (englisch „relative humidity“)" in CARD
    assert "RH stands for relative humidity." in CARD
    assert "Referenzluft wurde während der Lüftung zu feucht" in CARD


def test_explanation_window_survives_rerender_and_closes_cleanly():
    assert "        this.shadowRoot.appendChild(template.content);\n        this._syncExplainSheet();" in CARD
    assert 'data-explain-close aria-label="${de ? "Schließen" : "Close"}"' in CARD
    assert 'e.key === "Escape" && this._explain' in CARD
    # above the room window (.submodal z-index 10010)
    assert ".explain-backdrop{position:fixed;inset:0;z-index:10050;" in CARD
    assert "+ FAIQ_FRESHY_CSS + FAIQ_ROOM_VIEW_CSS;" in CARD


def test_room_view_text_is_larger_and_respects_font_scales():
    css = CARD[CARD.index("const FAIQ_ROOM_VIEW_CSS = `"):]
    css = css[: css.index("`;")]
    assert ".room-detail .info-grid b{font-size:calc(15px * var(--faiq-font-metrics,1))" in css
    assert ".room-detail .info-grid span{font-size:calc(10.5px * var(--faiq-font-meta,1))" in css
    # previously 12 px values and 7.5 px labels
    assert ".info-grid span{font-size:7.5px" in CARD


def test_freshy_room_goals_are_not_squeezed_into_the_reason_grid():
    # The reason rows use a 17 px icon column; the goal tracker inherited it, so the
    # first goal became an empty 18 px dashed strip (screenshot 10.10.).
    assert ".ai-inline-detail>div:not(.ai-inline-title):not(.ai-inline-values):not(.goal-tracker){" in CARD
    # one row, equal columns for 1, 2 or 3 goals (humidity, CO2, temperature)
    assert ".ai-inline-detail>.goal-tracker{margin:4px 0 2px;grid-template-columns:repeat(var(--goal-count,2),minmax(0,1fr))}" in CARD
    assert '<div class="goal-tracker ${compact?"compact":""}" style="--goal-count:${goals.length}">' in CARD


def test_freshy_card_has_no_night_pollen_learning_tiles_any_more():
    panel = CARD[CARD.index("    _compactAIPanel(st, rooms = []) {"):]
    panel = panel[: panel.index("\n    _", 10)]
    assert '<div class="ai-context">' not in panel
    assert 'data-info="pollen"' not in panel and 'data-info="learning:quality"' not in panel
