"""Regression contracts for v0.26.2.14: Rooms overview render crash, save-room crash, UI layer."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def _class_bodies():
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"^class (\w+)", CARD, re.M)] + [(len(CARD), None)]
    for (start, name), (end, _) in zip(starts, starts[1:]):
        yield name, CARD[start:end]


def test_every_this_method_call_in_the_card_classes_is_defined():
    """`this._lang()` was called but never defined and silently broke the Rooms overview."""
    problems = []
    for name, body in _class_bodies():
        defined = set(re.findall(r"^    (?:static\s+|async\s+|get\s+|set\s+)*(_?\w+)\s*\(", body, re.M))
        assigned = set(re.findall(r"this\.(_?\w+)\s*=", body))
        called = set(re.findall(r"this\.(_\w+)\(", body))
        problems += [f"{name}.{m}" for m in sorted(called - defined - assigned)]
    assert problems == [], f"undefined methods called: {problems}"


def test_goal_tracker_uses_existing_language_helper():
    assert "this._lang()" not in CARD
    start = CARD.index("    _goalTracker(r, compact=false) {")
    assert "this._uiLanguage()" in CARD[start:start + 600]


# test_save_room_handler_does_not_use_an_undefined_room_variable: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).


def test_goal_tracker_styles_live_in_the_card_stylesheet_not_only_in_the_editor():
    design = CARD[CARD.index("const FAIQ_DESIGN_CSS"):CARD.index("class FreshAirIQCard ")]
    assert ".goal-tracker{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in design
    assert ".goal-pill{" in design
    assert "FAIQ_CARD_CSS + FAIQ_AI_COMPACT_CSS + FAIQ_COMPACT_DISCLOSURE_CSS + FAIQ_DESIGN_CSS" in CARD


def test_render_error_boundary_is_present_and_recovers_to_dashboard():
    assert "    _renderImpl() {" in CARD
    assert "this._renderImpl();" in CARD
    assert "_handleRenderFailure(error, \"render\")" in CARD
    assert "FAIQ-UI-RENDER-001" in CARD and "FAIQ-UI-ROOM-001" in CARD
    handler = CARD[CARD.index("    _handleRenderFailure("):CARD.index("    _showRenderNotice(")]
    assert "this._info = null; this._dialogOpen = false" in handler
    assert "    _roomCardImpl(r) {" in CARD
    assert "_refreshOpenViewsLiveImpl" in CARD


def test_quick_actions_are_real_touch_targets():
    assert ".compact-actions .details-btn{display:flex;flex-direction:column" in CARD
    assert "min-height:58px" in CARD
    assert "touch-action:manipulation" in CARD
    for button_id in ("details", "guests", "rooms", "support"):
        assert f'<button class="details-btn" id="{button_id}"><ha-icon' in CARD


def test_room_tiles_are_keyboard_operable_and_show_status():
    assert 'class="room clickable" role="button" tabindex="0" data-room=' in CARD
    assert '[data-room][role="button"]' in CARD
    assert 'class="room-status"' in CARD
    assert "rooms-summary" in CARD


def test_night_window_clock_regex_is_not_double_escaped():
    """`/^(\\\\d{1,2}):(\\\\d{2})/` never matched "23:30", so the configured night window was ignored."""
    start = CARD.index("    _freshyClockMinutes(value, fallback) {")
    block = CARD[start:start + 400]
    assert r".match(/^(\d{1,2}):(\d{2})/)" in block
    assert "\\\\d" not in block


def test_small_dashboard_controls_have_finger_sized_tap_areas():
    design = CARD[CARD.index("const FAIQ_DESIGN_CSS"):CARD.index("class FreshAirIQCard ")]
    assert ".ai-scope.clickable::before{content:\"\";position:absolute;inset:-10px -8px}" in design
    assert ".top .pill[data-info]{position:relative;display:inline-flex;align-items:center;min-height:36px" in design
    assert ".ai-all-good{min-height:44px" in design
    assert ".ai-context" not in design  # 0.26.4.9: the Nacht/Pollen/Lernen tiles were removed
    assert ".decision-more>summary{min-height:48px}" in design
