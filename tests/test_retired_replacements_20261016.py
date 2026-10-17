"""Replacements (2026-10-16) for pure tests retired with the CSS-drawn Freshy.

0.26.4.1 replaced the CSS-drawn mascot (airflow spans, sailing keyframes) by
the animated Freshy SVG. The intent "while a ventilation runs, Freshy visibly
moves with the airflow" still applies and is checked against the real mood
logic and the animated character's stylesheet.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _mood(kind: str, close: list[dict] | None = None) -> str:
    start = CARD.index("    _freshyMood(st, ctx) {")
    method = CARD[start:CARD.index("\n    _freshyMotion", start)].strip()
    ctx = {"kind": kind, "close": close or [], "nightRecommendation": False, "nightStrategy": {},
           "isNight": False, "isPreNight": False, "timeKind": "good", "calc": []}
    script = f"const o = {{ {method} }};\nprocess.stdout.write(o._freshyMood({json.dumps({})}, {json.dumps(ctx)}));"
    return subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_active_ventilation_shows_the_moving_run_freshy():
    """Replaces test_active_ventilation_has_airflow_and_sailing_freshy."""
    # a running (live or continuous) ventilation selects the "run" mood ...
    assert _mood("live") == "run"
    assert _mood("continuous") == "run"
    # ... unless a running room should be closed now
    assert _mood("live", close=[{"active": True}]) == "done"
    assert _mood("wait") != "run"
    # "run" shows the airflow (wind lines) and moves: the leaves flutter and the
    # running halo replaces the resting one.
    assert ".fr-act .frx-wind,.fr-run .frx-wind{display:inline}" in CARD
    flutter = re.search(r"\.fr-run \.fr-leaves\{animation:(\w+) [^}]*infinite", CARD)
    assert flutter, "run mood has no looping leaf animation"
    assert f"@keyframes {flutter.group(1)}" in CARD
    assert ".fr-run .fr-halo-run{display:inline}" in CARD
