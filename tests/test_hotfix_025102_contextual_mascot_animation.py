from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
def test_states():
    for s in ("live","continuous","sensor","close","pollen","cooling","wait","success","recommend","good","pre-night","night"):
        assert f".ai-compact.{s}" in JS
def test_motion():
    for k in ("faiqSailSmooth","faiqGentleVent","faiqSensor","faiqAttention","faiqPollen","faiqCool","faiqWait","faiqCelebrateSmooth","faiqInvite","faiqContent","faiqZzzSmooth"):
        assert f"@keyframes {k}" in JS
    for obsolete in ("faiqVentilate","faiqSail{","faiqCelebrate{","faiqZzz{"):
        assert f"@keyframes {obsolete}" not in JS
    assert "prefers-reduced-motion:reduce" in JS
