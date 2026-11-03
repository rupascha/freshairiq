"""GitHub #14: Freshy must not say "wait" while listing rooms as "Lüften"."""
from pathlib import Path

CARD = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def _panel() -> str:
    # Hotfix 0.26.6.0 (9) F07: the IQ view's decision head moved into ``_iqFacts`` (shared with the house map, directly
    # before _compactAIPanel); the panel's contract therefore covers both methods – the rules checked are unchanged
    return CARD[CARD.index("    _iqFacts(st, rooms = []) {"):CARD.index("    _intelligentPanel(st, rooms = []) {")]


def test_wait_kind_comes_from_the_canonical_house_decision_not_the_headline():
    panel = _panel()
    assert 'const houseWaits = ["wait", "pollen_wait"].includes(String(houseDecision.kind || "").toLowerCase())' in panel
    assert ': houseWaits ? "wait"' in panel
    assert panel.index(': houseWaits ? "wait"') < panel.index(': vent.length || status === "ventilate" ? "recommend"')


def test_rooms_and_facts_follow_a_holding_house_decision():
    panel = _panel()
    # Hotfix (9) F05: a session in its final measurement still counts (``live``, as the backend's live balance) – the
    # house holds back only when no session is running at all; the wait/night rule itself is unchanged
    assert 'const houseHolds = !live && !active.length && (kind === "wait" || (kind === "night" && !freshyNightAction));' in panel
    assert 'this._t("iq.room_waiting")' in panel
    assert "const factTime = !houseHolds &&" in panel
    assert '"iq.room_waiting": { de: "Lüften möglich · noch warten"' in CARD


def test_freshy_reports_mould_like_the_classic_tile():
    panel = _panel()
    assert 'calc.filter(r => ["Elevated", "High", "Very high"].includes(r.mould_level)).length' in panel
    assert '"iq.mould_flagged_many": { de: "Schimmelrisiko: {count} Räume auffällig"' in CARD
    assert "ohne akuten Lüftungsbedarf" in CARD
