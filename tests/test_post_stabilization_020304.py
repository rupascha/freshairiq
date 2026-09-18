from datetime import datetime, timedelta
from pathlib import Path

from custom_components.freshairiq.post_stabilization import (
    start_post_close_observation,
    update_post_close_observation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_rebound_is_quantified_without_changing_session_result():
    room = {}
    start = datetime(2026, 9, 11, 20, 0, 0)
    start_post_close_observation(
        room, event_id="living:1", room_key="living", room_name="Wohnzimmer", now=start, close_ah=8.0,
        close_temp_c=20.0, removed_ml=200.0, volume_m3=100.0,
        frame_quality="excellent",
    )
    update_post_close_observation(
        room, now=start + timedelta(minutes=5), absolute_humidity_g_m3=8.2,
        temperature_c=20.2, frame_quality="excellent", frame_valid=True,
        window_open=False, moisture_source_active=False,
    )
    outcome, _ = update_post_close_observation(
        room, now=start + timedelta(minutes=10), absolute_humidity_g_m3=8.4,
        temperature_c=20.4, frame_quality="excellent", frame_valid=True,
        window_open=False, moisture_source_active=False,
    )
    assert outcome is not None
    assert outcome["moisture_rebound_ml"] == 40.0
    assert outcome["retained_removed_ml"] == 160.0
    assert outcome["interpretation"] == "moisture_rebound"
    assert outcome["valid_for_analysis"] is True


def test_reopening_interrupts_post_close_observation():
    room = {}
    start = datetime(2026, 9, 11, 20, 0, 0)
    start_post_close_observation(room, event_id="room:1", room_key="room", room_name="Raum", now=start, close_ah=8.0,
                                 close_temp_c=20.0, removed_ml=100.0, volume_m3=50.0,
                                 frame_quality="acceptable")
    outcome, changed = update_post_close_observation(
        room, now=start + timedelta(minutes=2), absolute_humidity_g_m3=8.1,
        temperature_c=20.1, frame_quality="acceptable", frame_valid=True,
        window_open=True, moisture_source_active=False,
    )
    assert changed is True
    assert outcome["status"] == "interrupted"
    assert outcome["valid_for_analysis"] is False
    assert room["post_close_active"] is False


def test_moisture_source_contaminates_stabilization():
    room = {}
    start = datetime(2026, 9, 11, 20, 0, 0)
    start_post_close_observation(room, event_id="bath:1", room_key="bath", room_name="Bad", now=start, close_ah=8.0,
                                 close_temp_c=20.0, removed_ml=100.0, volume_m3=50.0,
                                 frame_quality="excellent")
    update_post_close_observation(room, now=start + timedelta(minutes=5), absolute_humidity_g_m3=8.3,
                                  temperature_c=20.1, frame_quality="excellent", frame_valid=True,
                                  window_open=False, moisture_source_active=True)
    outcome, _ = update_post_close_observation(room, now=start + timedelta(minutes=10), absolute_humidity_g_m3=8.4,
                                               temperature_c=20.2, frame_quality="excellent", frame_valid=True,
                                               window_open=False, moisture_source_active=False)
    assert outcome["contaminated"] is True
    assert outcome["valid_for_analysis"] is False


def test_release_version_020304():
    assert 'VERSION = "0.25.0.35"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.35"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.35"' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
