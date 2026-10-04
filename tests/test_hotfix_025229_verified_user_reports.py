from pathlib import Path
from types import SimpleNamespace

from custom_components.freshairiq.guardian import evaluate_guardian
from custom_components.freshairiq.opening_state import advertises_three_states, normalize_opening_state
from custom_components.freshairiq.opening_strategy import synchronize_room_presentation_actions

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_german_closed_three_state_helper_is_normalized_and_advertised():
    state = SimpleNamespace(state="Geschlossen", attributes={"options": ["Geschlossen", "Offen", "Gekippt"]})
    assert normalize_opening_state("Geschlossen") == "closed"
    assert normalize_opening_state("Offen") == "open"
    assert normalize_opening_state("Gekippt") == "tilted"
    assert advertises_three_states("input_select.fenster", state)


def test_final_presentation_override_is_provenance_tagged_and_not_false_guardian_incident():
    rooms = {"bed": {"key": "bed", "active": True, "action": "Continue ventilating", "temperature": 21, "humidity": 55, "absolute_humidity": 10}}
    synchronize_room_presentation_actions({"kind": "close", "room_keys": ["bed"]}, rooms)
    assert rooms["bed"]["action"] == "Close"
    assert rooms["bed"]["canonical_action"] == "Continue ventilating"
    assert rooms["bed"]["presentation_action_override"] == {
        "action": "Close", "recommendation_kind": "close", "reason": "final_recommendation_alignment"
    }
    findings = evaluate_guardian({"rooms": rooms})["findings"]
    assert not any(item["code"] == "FAIQ-GUARDIAN-DECISION-001" for item in findings)


def test_unexplained_visible_contradiction_is_still_guarded():
    rooms = {"bed": {"action": "Close", "canonical_action": "Continue ventilating", "temperature": 21, "humidity": 55, "absolute_humidity": 10}}
    findings = evaluate_guardian({"rooms": rooms})["findings"]
    assert any(item["code"] == "FAIQ-GUARDIAN-DECISION-001" for item in findings)


def test_iq_branding_respects_same_toggle_as_classic():
    card = (COMP / "frontend/freshairiq-card.js").read_text()
    assert 'const iqTopBar = showBranding || showProfileBadge ?' in card
    assert 'ai-top${showBranding ? "" : " profile-only"}' in card
    assert '${showBranding ? `<img class="logo"' in card


def test_dark_dashboard_room_text_has_explicit_readable_contrast_contract():
    card = (COMP / "frontend/freshairiq-card.js").read_text()
    rule = '.room-title,.room-water strong,.room-value,.room-big,.breakdown-row b,.breakdown-row strong,.ai-room b,.decision-room-disclosure>summary span,.decision-more>summary>span:first-child{color:#e9f0f4}'
    assert rule in card


def test_attic_apartment_english_copy_is_top_floor_without_migrating_internal_id():
    strings = (COMP / "strings.json").read_text()
    english = (COMP / "translations/en.json").read_text()
    card = (COMP / "frontend/freshairiq-card.js").read_text()
    assert '"attic_apartment": "Top-floor apartment"' in strings
    assert '"attic_apartment": "Top-floor apartment"' in english
    assert '["Dachgeschosswohnung", "Top-floor apartment"]' in card
    assert 'Attic apartment' not in strings + english + card


def test_support_upload_uses_dedicated_long_timeout_and_exposes_only_safe_failure_detail():
    const = (COMP / "const.py").read_text()
    telemetry = (COMP / "telemetry.py").read_text()
    diagnostics = (COMP / "diagnostics.py").read_text()
    method = telemetry.split('async def async_submit_support_diagnostics', 1)[1].split('async def async_maybe_upload', 1)[0]
    assert 'SUPPORT_DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS = 90' in const
    assert 'ClientTimeout(total=SUPPORT_DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)' in method
    assert 'support_diagnostics_http_' in diagnostics
    assert 'detail = "timeout"' in diagnostics
    assert 'str(err)' in diagnostics
    assert '"error": "support_upload_failed"' in diagnostics
    assert '"detail": detail' in diagnostics
    assert '"error_code": "FAIQ-SUPPORT-UPLOAD-001"' in diagnostics
