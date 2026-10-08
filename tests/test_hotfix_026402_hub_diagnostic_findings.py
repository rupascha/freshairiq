"""0.26.4.2: fixes derived from the Diagnostics Hub export of 2026-10-08."""
from custom_components.freshairiq.diagnostic_transport import _redact_text
from custom_components.freshairiq.guardian import evaluate_guardian


def test_numeric_floor_label_no_longer_corrupts_codes_and_timestamps():
    labels = {"1": "level-e4a3e09fb5"}
    assert _redact_text("FAIQ-SENSOR-DATA-001", labels) == "FAIQ-SENSOR-DATA-001"
    assert _redact_text("2026-10-06T18:39:12.112306+02:00", labels) == "2026-10-06T18:39:12.112306+02:00"
    assert _redact_text("1", labels) == "level-e4a3e09fb5"
    assert _redact_text("Flur 1", labels) == "Flur 1"
    assert _redact_text("unchanged", {"": "x"}) == "unchanged"


def test_labels_are_replaced_as_whole_words_only():
    labels = {"Bad": "room-aaaa", "Jo": "<redacted_resident>", "Obergeschoss": "level-bbbb"}
    assert _redact_text("Badezimmer und Bad", labels) == "Badezimmer und room-aaaa"
    assert _redact_text("Jo, bitte lüften. Job erledigt", labels) == "<redacted_resident>, bitte lüften. Job erledigt"
    assert _redact_text("Fenster im Obergeschoss offen", labels) == "Fenster im level-bbbb offen"


def _sensor_002(recovery):
    codes = {f["code"] for f in evaluate_guardian({"rooms": {}, "sensor_recovery": recovery})["findings"]}
    return "FAIQ-GUARDIAN-SENSOR-002" in codes


def test_persistent_outage_after_grace_is_not_a_guardian_violation():
    # Hub: 45 findings in 24 installations, all long outages that correctly left grace.
    assert not _sensor_002({"active": False, "required_sources_unavailable": 1, "grace_seconds": 90, "unavailable_for_seconds": 3600})
    assert not _sensor_002({"active": False, "required_sources_unavailable": 1, "grace_seconds": 90, "unavailable_for_seconds": 90})


def test_guard_that_should_still_run_is_still_reported():
    assert _sensor_002({"active": False, "required_sources_unavailable": 1, "grace_seconds": 90, "unavailable_for_seconds": 30})
    assert _sensor_002({"active": False, "required_sources_unavailable": 1})  # legacy state without age
    assert not _sensor_002({"active": True, "required_sources_unavailable": 1, "grace_seconds": 90, "unavailable_for_seconds": 30})


from pathlib import Path

CARD = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_living_rooms_no_longer_get_the_kitchen_pot():
    start = CARD.index("const roomVisual = r => {")
    body = CARD[start:CARD.index("};", start)]
    kitchen = body.index('name.includes("küche")')
    assert 'name.includes("wohn")' not in body[:kitchen]
    assert 'if (name.includes("wohn") || name.includes("living"))\n        return ["mdi:sofa-outline"' in body


# test_admins_reach_the_dashboard_settings_from_the_details_header: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).
