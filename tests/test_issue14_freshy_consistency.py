"""GitHub #14: Freshy must not say "wait" while listing rooms as "Lüften"."""
from pathlib import Path

CARD = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def _panel() -> str:
    return CARD[CARD.index("    _compactAIPanel(st, rooms = []) {"):CARD.index("    _intelligentPanel(st, rooms = []) {")]


def test_wait_kind_comes_from_the_canonical_house_decision_not_the_headline():
    panel = _panel()
    assert 'const houseWaits = ["wait", "pollen_wait"].includes(String(houseDecision.kind || "").toLowerCase())' in panel
    assert ': houseWaits ? "wait"' in panel
    assert panel.index(': houseWaits ? "wait"') < panel.index(': vent.length || status === "ventilate" ? "recommend"')


def test_rooms_and_facts_follow_a_holding_house_decision():
    panel = _panel()
    assert 'const houseHolds = !active.length && (kind === "wait" || (kind === "night" && !freshyNightAction));' in panel
    assert 'this._t("iq.room_waiting")' in panel
    assert "const factTime = !houseHolds &&" in panel
    assert '"iq.room_waiting": { de: "Lüften möglich · noch warten"' in CARD


def test_freshy_reports_mould_like_the_classic_tile():
    panel = _panel()
    assert 'calc.filter(r => ["Elevated", "High", "Very high"].includes(r.mould_level)).length' in panel
    assert '"iq.mould_flagged_many": { de: "Schimmelrisiko: {count} Räume auffällig"' in CARD
    assert "ohne akuten Lüftungsbedarf" in CARD
