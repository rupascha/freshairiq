"""F39: pseudonymisation must never damage technical identifiers or versions.

Synthetic boundary cases: custom floor labels that equal a number ("1") or a
rule-ID segment ("DATA") - the historic hub evidence showed
FAIQ-SENSOR-DATA-00level-e4a3e09fb5 and damaged timestamps.
"""
from __future__ import annotations

from custom_components.freshairiq.diagnostic_transport import _redact_text, _sanitize_analysis_tree

LABELS = {"1": "level-aaaaaaaaaa", "DATA": "level-bbbbbbbbbb", "Keller": "level-cccccccccc"}


def test_rule_ids_timestamps_and_versions_survive_custom_floor_labels():
    for text in ("FAIQ-SENSOR-DATA-001", "FAIQ-GUARDIAN-DECISION-001", "HUB-SCHEMA-001",
                 "2026-10-06T01:01:00+02:00", "v0.26.5.0", "0.26.4.10", "HA 2026.10.1"):
        assert _redact_text(text, LABELS) == text


def test_private_labels_are_still_pseudonymised_around_codes():
    assert _redact_text("FAIQ-SENSOR-DATA-001 im DATA und Keller", LABELS) == (
        "FAIQ-SENSOR-DATA-001 im level-bbbbbbbbbb und level-cccccccccc")
    assert _redact_text("1", LABELS) == "level-aaaaaaaaaa"
    assert _redact_text("DATA", LABELS) == "level-bbbbbbbbbb"


def test_ip_addresses_and_entities_are_still_redacted():
    assert _redact_text("192.168.1.10 / 10.0.0.1 / 100.0.0.1", LABELS) == "<redacted_ip> / <redacted_ip> / <redacted_ip>"
    assert _redact_text("sensor.bad_temp", LABELS) == "<redacted_entity>"
    assert _redact_text("x.0.26.5", LABELS).startswith("<redacted_entity>")


def test_structured_fields_keep_codes_and_drop_custom_floor_names():
    tree = _sanitize_analysis_tree({"rule_id": "FAIQ-SENSOR-DATA-001", "floor": "DATA", "note": "Raum im DATA, v0.26.5.0"}, LABELS)
    assert tree == {"rule_id": "FAIQ-SENSOR-DATA-001", "floor": "custom", "note": "Raum im level-bbbbbbbbbb, v0.26.5.0"}
