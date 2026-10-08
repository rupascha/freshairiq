from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components" / "freshairiq" / "frontend" / "freshairiq-card.js"


def test_passive_open_classic_disclosure_uses_canonical_display_action():
    js = CARD.read_text(encoding="utf-8")
    assert 'const canonicalMonitor = passiveOpenMonitor && r.active' in js
    assert 'const displayAction = canonicalMonitor ? "Daueröffnung überwachen" : actionDE(r.action)' in js
    assert '<strong>${esc(displayAction)}</strong>' in js


def test_passive_open_compact_priority_does_not_promote_raw_close():
    js = CARD.read_text(encoding="utf-8")
    assert 'const isCanonicalMonitorRoom = r => passiveOpenMonitor && r.active && monitoredRoomKeys.has(String(r.key))' in js
    assert 'r.action === "Close" && !isCanonicalMonitorRoom(r)' in js
    assert 'const priority = passiveOpenMonitor && active.length ? active' in js
    assert '"Daueröffnung überwachen" : "Monitor long-term opening"' in js


def test_hotfix_preserves_raw_room_action_for_model_and_diagnostics():
    js = CARD.read_text(encoding="utf-8")
    assert 'displayAction = canonicalMonitor' in js
    # Presentation is derived locally; the room object is not rewritten.
    assert re.search(r'r\.action\s*=(?!=)', js) is None
