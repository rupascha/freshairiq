"""0.26.5.2 (community: learning pages "kaum lesbar ohne Lupe"): every small fixed
text size of the card follows a text size setting, including the learning pages."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_learning_scale_is_configurable_and_applied():
    assert "font_scale_learning: normalizeFontScale(raw.font_scale_learning)" in CARD
    assert 'this.style.setProperty("--faiq-font-learning", String(this._config.font_scale_learning));' in CARD
    assert '["font_scale_learning","Lernmodell & Analyse",' in CARD
    assert '["font_scale_learning","Learning model & analysis",' in CARD
    assert "faiqThemeCss(faiqScaleCss(FAIQ_CARD_CSS + " in CARD  # 0.26.5.3: scaled, then themed


def test_steps_reach_200_percent_and_default_stays_100():
    steps = re.search(r"FAIQ_FONT_SCALE_STEPS = Object.freeze\(\[([^\]]*)\]\)", CARD).group(1).split(",")
    assert [float(x) for x in steps][-1] == 2.0 and "1" in steps
    assert "if(!Number.isFinite(n)) return 1" in CARD


def _scaled_css() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    fn = next(line for line in CARD.split("\n") if line.startswith("const faiqScaleCss = "))
    css = "".join(m.group(1) for m in re.finditer(r"const FAIQ_[A-Z_]+_CSS = `([\s\S]*?)`;", CARD))
    script = fn + "\nlet d='';process.stdin.on('data',c=>d+=c).on('end',()=>process.stdout.write(faiqScaleCss(JSON.parse(d))));"
    return subprocess.run([node, "-e", script], input=json.dumps(css), capture_output=True, text=True, check=True).stdout


def test_no_small_text_keeps_a_fixed_size():
    out = _scaled_css()
    fixed = [float(m.group(1)) for m in re.finditer(r"font-size:([\d.]+)px", out)]
    assert fixed and min(fixed) >= 14
    assert out.count("{") == out.count("}")


def test_learning_pages_follow_the_learning_scale():
    out = _scaled_css()
    for selector in (".learning-detail-card p", ".learning-detail-head b", ".learning-group-hero p", ".info-panel p"):
        rule = re.search(re.escape(selector) + r"[^{}]*\{([^{}]*)\}", out).group(1)
        assert "var(--faiq-font-learning,1)" in rule, selector
    # 100 % keeps the previous size exactly
    assert "font-size:calc(6.8px*var(--faiq-font-learning,1))" in out
