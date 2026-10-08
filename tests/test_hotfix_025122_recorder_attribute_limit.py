from tests.release_version import CURRENT_RELEASE_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/freshairiq/sensor.py").read_text(encoding="utf-8")
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_status_dashboard_payload_is_live_only_for_recorder():
    assert "from homeassistant.const import MATCH_ALL, PERCENTAGE" in SENSOR
    house = SENSOR.split("class HouseSensor", 1)[1].split("class RoomSensor", 1)[0]
    assert "_unrecorded_attributes = frozenset({MATCH_ALL})" in house
    # The live dashboard contract must remain intact; this hotfix must not remove payloads.
    assert '"rooms": self.coordinator.data["rooms"]' in house
    assert '"history_14d": self.coordinator.data["history_14d"]' in house
    assert '"diagnostics": self.coordinator.data.get("diagnostics", {})' in house


def test_room_dashboard_payload_is_not_recorded_but_remains_live():
    room = SENSOR.split("class RoomSensor", 1)[1]
    assert '_unrecorded_attributes = frozenset({"freshairiq_room_payload"})' in room
    assert '"freshairiq_room_payload": room' in room
    assert 'attrs.freshairiq_room_payload' in CARD
    assert '["room_v1", "room_v2"]' in CARD


def test_release_version_is_025122():
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    manifest = (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert f'VERSION = "{CURRENT_RELEASE_VERSION}"' in const
    assert f'"version": "{CURRENT_RELEASE_VERSION}"' in manifest
