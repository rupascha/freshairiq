"""0.26.4.8: Freshy – rain only when it rains, same eyes, more situations, seamless loops."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from custom_components.freshairiq.weather_now import minutes_until_rain, weather_now

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
CSS = CARD[CARD.index("const FAIQ_FRESHY_CSS = `"):CARD.index("`;", CARD.index("const FAIQ_FRESHY_CSS = `"))]
FRESHY = CARD[CARD.index("const FRESHY_MOODS"):CARD.index("class FreshAirIQCard extends HTMLElement")]
MOODS = json.loads(re.search(r"const FRESHY_MOODS = (\[[^\]]*\]);", CARD).group(1))
NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)


def _row(minutes, mm=0.0, prob=0.0, condition="cloudy"):
    return {"datetime": NOW + timedelta(minutes=minutes), "precipitation_mm": mm, "precipitation_probability": prob, "condition": condition}


# --- weather_now (pure) --------------------------------------------------------------
def test_rain_now_comes_from_the_current_condition_only():
    dry = weather_now("cloudy", [_row(0), _row(60), _row(600, mm=4, prob=90)], NOW, 14)
    assert dry["raining"] is False and dry["rain_soon"] is False and dry["rain_in_min"] is None
    wet = weather_now("pouring", [], NOW, 14)
    assert wet["raining"] and wet["rain_in_min"] == 0 and not wet["rain_soon"]
    storm = weather_now("lightning", None, NOW, 20)
    assert storm["thunder"] and not storm["raining"]
    snow = weather_now("Snowy", [], NOW, -2)
    assert snow["snowing"] and snow["frost"] and snow["condition"] == "snowy"
    assert weather_now("unavailable", [], NOW, None)["condition"] is None


def test_rain_soon_needs_real_precipitation_within_two_hours():
    assert minutes_until_rain([_row(-120, mm=3), _row(-30), _row(45, mm=0.4), _row(100, prob=95)], NOW) == 45
    assert minutes_until_rain([_row(-30, prob=80)], NOW) == 0  # current hour counts as now
    assert minutes_until_rain([_row(90, condition="rainy")], NOW) == 90
    assert minutes_until_rain([_row(30, mm=0.1, prob=40), _row(150, mm=5)], NOW) is None  # light/late
    assert minutes_until_rain([{"datetime": "x"}, "bad", _row(10, mm=1)], NOW) == 10
    assert minutes_until_rain("nope", NOW) is None
    soon = weather_now("cloudy", [_row(30, mm=1.2)], NOW, "21.36")
    assert soon["rain_soon"] and soon["rain_in_min"] == 30 and soon["outdoor_temperature"] == 21.4


def test_frost_and_heat_thresholds():
    assert weather_now("sunny", [], NOW, 0)["frost"] and not weather_now("sunny", [], NOW, 0.1)["frost"]
    assert weather_now("sunny", [], NOW, 28)["heat"] and not weather_now("sunny", [], NOW, 27.9)["heat"]
    odd = weather_now(None, [], NOW, float("nan"))
    assert odd["outdoor_temperature"] is None and not odd["frost"] and not odd["heat"]


def test_weather_now_is_published_for_the_dashboard():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    sensor = (ROOT / "custom_components/freshairiq/sensor.py").read_text(encoding="utf-8")
    assert '"weather_now": weather_situation,' in coordinator
    assert '"weather_now": self.coordinator.data.get("weather_now", {}),' in sensor


# --- card contract ----------------------------------------------------------------------
def test_nineteen_moods_with_labels_in_both_languages():
    assert len(MOODS) == 19
    for new in ("sleepy", "morning", "rain_soon", "snow", "frost", "heat", "wait", "dust"):
        assert new in MOODS
    for lang in ("de", "en"):
        block = re.search(rf"\n    {lang}: \{{(.*?)\}},\n", FRESHY).group(1)
        for mood in MOODS:
            assert re.search(rf"\b{mood}: \"", block), (lang, mood)
    for mood in MOODS:
        assert re.search(rf"\.fr-{mood} [^{{]*\{{[^}}]*(display:inline|animation|stroke)", CSS), mood


def test_both_eyes_always_share_one_drawing():
    # Every face draws its eyes through freshyEyePair (same shape at x=89 and x=111);
    # only the mirrored pollen squint is drawn by hand.
    starts = [(m.group(1), m.start()) for m in re.finditer(r'<g class="fr-face fr-face-([a-z]+)"', FRESHY)]
    faces = [(name, FRESHY[pos:FRESHY.index("\n", pos)]) for name, pos in starts]
    assert len(faces) == 11
    for name, body in faces:
        if name == "squint":
            continue
        assert "freshyEyePair(" in body, name
    # the old happy face mixed a filled eye with an open arc
    assert 'C 77 58, 99 58, 99 72 C 92 68.5' not in CARD


def test_every_loop_is_anchored_and_never_waits_visibly():
    animations = re.findall(r"animation:([^;}]+)", CSS)
    assert animations
    for value in animations:
        if "none" in value or value.startswith("frIn"):
            continue
        assert "var(--frp)" in value, value
    for delay in re.findall(r"animation-delay:([^;}]+)", CSS):
        assert re.fullmatch(r"calc\(var\(--frp\) - [\d.]+s\)", delay.strip()), delay
    assert ".fr{display:block;overflow:visible;--frp:0s;--frin:-9s;animation:frIn .55s ease-out var(--frin) both}" in CSS
    assert "@media (prefers-reduced-motion: reduce){.fr,.fr *{animation:none!important}}" in CSS


def test_keyframes_end_like_they_start():
    """Static check of the rule enforced by tools/freshy_loop_check.mjs in the browser."""
    for name, body in re.findall(r"@keyframes (\w+)\{(.*?)\}\}", CSS):
        if name == "frIn":
            continue
        frames = {}
        for selectors, decl in re.findall(r"([\d%,]+)\{([^}]*)", body + "}"):
            for sel in selectors.split(","):
                frames[sel] = decl
        start, end = frames.get("0%"), frames.get("100%")
        assert start is not None and end is not None, name
        uses_alternate = re.search(rf"{name} [^;]*alternate", CSS) is not None
        invisible = "opacity:0" in start and "opacity:0" in end
        full_turn = start.replace("0deg", "X") == end.replace("360deg", "X")
        assert start == end or uses_alternate or invisible or full_turn, name


def test_night_cap_and_morning_belong_to_the_time_of_day():
    assert '        return inMorning ? "morning" : "good";' in CARD
    motion = CARD[CARD.index("    _freshyMotion(mood, timeKind) {"):CARD.index("    _compactAIPanel(st, rooms = []) {")]
    assert 'cap: ["pre-night", "night"].includes(timeKind) && mood !== "rain",' in motion
    assert "phase: -(now - FRESHY_EPOCH) / 1000," in motion


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node not installed")
@pytest.mark.parametrize(
    ("kind", "extra", "weather", "time_kind", "expected"),
    [
        ("wait", {}, {}, "good", "wait"),
        ("wait", {}, {"rain_soon": True}, "good", "rain_soon"),
        ("wait", {"nightStrategy": {"rain_expected": True, "action": "close"}}, {}, "good", "wait"),  # rain only tonight: no umbrella
        ("good", {}, {"raining": True}, "good", "rain"),
        ("good", {}, {"raining": True, "snowing": True}, "good", "snow"),
        ("good", {}, {}, "pre-night", "sleepy"),
        ("good", {"isPreNight": True}, {}, "pre-night", "sleepy"),
        ("wait", {"isPreNight": True}, {}, "pre-night", "sleepy"),
        ("good", {"isNight": True}, {}, "night", "night"),
        ("good", {}, {"frost": True}, "good", "frost"),
        ("good", {}, {"heat": True}, "good", "heat"),
        ("good", {}, {}, "morning", "morning"),
        ("pollen", {"pm25": True}, {}, "good", "dust"),
        ("pollen", {}, {}, "good", "pollen"),
        ("recommend", {}, {"raining": True}, "good", "act"),
        ("good", {}, {"thunder": True}, "good", "ok"),  # dry thunder: no umbrella
        ("good", {}, {}, "good", "ok"),
    ],
)
def test_mood_selection_in_the_real_card_code(kind, extra, weather, time_kind, expected):
    start = CARD.index("    _freshyMood(st, ctx) {")
    method = CARD[start:CARD.index("\n    _freshyMotion", start)].strip()
    ctx = {
        "kind": kind, "close": [], "nightRecommendation": False, "nightStrategy": extra.get("nightStrategy", {}),
        "isNight": extra.get("isNight", time_kind == "night"), "isPreNight": extra.get("isPreNight", time_kind == "pre-night"),
        "timeKind": time_kind, "calc": [],
    }
    st = {"weather_now": weather, "outdoor_pm25_blocked": bool(extra.get("pm25"))}
    script = f"const o = {{ {method} }};\nprocess.stdout.write(o._freshyMood({json.dumps(st)}, {json.dumps(ctx)}));"
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    assert result.stdout == expected
