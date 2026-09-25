from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_status_transport_keeps_complete_room_history_fallback():
    text = (ROOT / "custom_components/freshairiq/sensor.py").read_text(encoding="utf-8")
    assert '"rooms": self.coordinator.data["rooms"]' in text
    assert '"freshairiq_transport": "status_v2"' in text
    assert '"freshairiq_entry_id": self._entry.entry_id' in text


def test_room_transport_is_versioned_and_keeps_payload():
    text = (ROOT / "custom_components/freshairiq/sensor.py").read_text(encoding="utf-8")
    assert '"freshairiq_room_payload": room' in text
    assert '"freshairiq_transport": "room_v2"' in text
    assert '"freshairiq_version": VERSION' in text


def test_dashboard_status_selection_does_not_prioritise_room_count():
    text = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'roomCount(s) * 10000' not in text
    assert 'a.freshairiq_transport === "status_v2"' in text
    assert 'String(a.freshairiq_version || a.version || "") === FAIQ_VERSION' in text


def test_dashboard_controls_are_bound_to_freshairiq_identity():
    text = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'a.freshairiq_entity_key === "operating_profile"' in text
    assert 'a.freshairiq_entity_key === "forecast_horizon_min"' in text
    assert 'a.freshairiq_entry_id === entryId' in text
    # The old generic helper match could target unrelated HA number entities.
    assert 'unit === "min" && min === 1 && max === 120 && step === 1' not in text


def test_version_is_consistent():
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    manifest = (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    card = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'VERSION = "0.25.0.70"' in const
    assert '"version": "0.25.0.70"' in manifest
    assert 'const FAIQ_VERSION = "0.25.0.70"' in card


def test_room_payload_merge_is_scoped_to_current_config_entry():
    text = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'const activeEntryId = st.freshairiq_entry_id || null' in text
    assert 'a.freshairiq_entry_id !== activeEntryId' in text
    assert 'a.freshairiq_transport !== "room_v2"' in text


def test_explicit_current_status_entity_is_authoritative():
    text = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'configured.attributes.freshairiq_transport === "status_v2"' in text
    assert 'return remember(configured);' in text
