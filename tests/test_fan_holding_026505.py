"""0.26.5.5: when a room still holds a shared fan, and when another automation has it (pure)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.actuator_control import external_lock_active, still_holding

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def test_follow_up_time_of_a_moisture_source_room() -> None:
    mem = {"last_demand": (NOW - timedelta(minutes=4)).isoformat()}
    assert still_holding("moisture_source", mem, NOW, follow_up_min=10, off_confirm_s=60)
    assert not still_holding("moisture_source", mem, NOW, follow_up_min=3, off_confirm_s=60)
    assert not still_holding("recommendation", mem, NOW, follow_up_min=10, off_confirm_s=60)  # no follow-up there
    assert not still_holding("moisture_source", {"last_demand": "broken"}, NOW, follow_up_min=10, off_confirm_s=60)


def test_owner_waiting_for_its_switch_off_confirmation() -> None:
    pending = {"owned": True, "off_pending_since": (NOW - timedelta(seconds=20)).isoformat()}
    assert still_holding("recommendation", pending, NOW, follow_up_min=0, off_confirm_s=60)
    assert not still_holding("recommendation", pending, NOW, follow_up_min=0, off_confirm_s=10)
    assert not still_holding("recommendation", {**pending, "owned": False}, NOW, follow_up_min=0, off_confirm_s=60)
    assert not still_holding("recommendation", {}, NOW, follow_up_min=0, off_confirm_s=60)


def test_external_lock_states() -> None:
    assert [external_lock_active(s) for s in ("on", "ON", "active", "paused")] == [True] * 4
    assert [external_lock_active(s) for s in ("off", "idle", "unavailable", "unknown", None, "")] == [False] * 6
