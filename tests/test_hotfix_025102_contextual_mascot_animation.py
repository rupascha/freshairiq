from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
def test_states():
    for s in ("live","sensor","close","pollen","cooling","wait","success","recommend","good"):
        assert f".ai-compact.{s}" in JS
def test_motion():
    for k in ("faiqVentilate","faiqSensor","faiqAttention","faiqPollen","faiqCool","faiqWait","faiqCelebrate","faiqInvite","faiqContent"):
        assert f"@keyframes {k}" in JS
    assert "prefers-reduced-motion:reduce" in JS
