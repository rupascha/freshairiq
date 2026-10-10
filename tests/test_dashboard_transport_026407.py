"""0.26.4.7: slimmer dashboard transport and house-aligned room recommendation."""
from __future__ import annotations

import json
from pathlib import Path

from custom_components.freshairiq.dashboard_transport import (
    DETAILS_API,
    ON_DEMAND_ROOM_KEYS,
    room_history_payload,
    slim_room,
    slim_rooms,
)
from custom_components.freshairiq.opening_strategy import HOUSE_ALIGNED_STATES, house_aligned_room_actions
from tests.frontend_source import card_text

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def _hourly(field, days=14):
    return [{"time": f"2026-10-{1 + i // 24:02d}T{i % 24:02d}:00", field: 50.0 + (i % 7) / 10} for i in range(days * 24)]


def _room(key):
    return {"key": key, "name": key, "action": "Ventilate", "humidity": 70, "history_14d": [{"date": "2026-10-09"}],
            "temperature_history_14d": _hourly("temperature_c"), "humidity_history_14d": _hourly("humidity_percent")}


def test_hourly_chart_series_leave_the_live_attributes():
    rooms = {f"r{i}": _room(f"r{i}") for i in range(13)}
    before = len(json.dumps(rooms))
    slim = slim_rooms(rooms)
    after = len(json.dumps(slim))
    assert after < before * 0.1  # 13 rooms with 14 days of hourly data: >90 % less per cycle
    for key, room in slim.items():
        assert not any(name in room for name in ON_DEMAND_ROOM_KEYS)
        assert room["history_on_demand"] is True and room["history_14d"] == rooms[key]["history_14d"]
        assert room["action"] == "Ventilate"
    assert "temperature_history_14d" in rooms["r0"]  # coordinator data itself is untouched
    assert slim_room("broken") == "broken" and slim_rooms(None) is None
    plain = {"key": "x"}
    assert slim_room(plain) is plain  # nothing to strip -> same object, no churn


def test_on_demand_payload_serves_one_or_all_rooms():
    rooms = {"a": _room("a"), "b": _room("b"), "bad": "broken"}
    one = room_history_payload(rooms, "a")
    assert one["api"] == DETAILS_API and list(one["rooms"]) == ["a"]
    assert one["rooms"]["a"]["humidity_history_14d"] == rooms["a"]["humidity_history_14d"]
    assert set(room_history_payload(rooms)["rooms"]) == {"a", "b"}
    assert room_history_payload(None, "a") == {"api": DETAILS_API, "rooms": {}}
    assert room_history_payload(rooms, "missing")["rooms"] == {}


def test_sensor_view_and_card_use_the_on_demand_path():
    sensor = (COMP / "sensor.py").read_text(encoding="utf-8")
    assert '"rooms": slim_rooms(self.coordinator.data["rooms"])' in sensor
    assert '"freshairiq_room_payload": slim_room(room)' in sensor
    assert '"freshairiq_details_api": DETAILS_API' in sensor
    view = (COMP / "room_history_api.py").read_text(encoding="utf-8")
    assert 'url = "/api/freshairiq/room-history/{entry_id}"' in view and "requires_auth = True" in view
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    assert "hass.http.register_view(FreshAirIQRoomHistoryView())" in init
    card = card_text()
    assert "freshairiq/room-history/${entryId}?room=${encodeURIComponent(key)}" in card
    assert "Date.now() - cached.at > 300000" in card  # refresh at most every 5 minutes
    assert "Array.isArray(r.humidity_history_14d) || Array.isArray(r.temperature_history_14d)" in card  # older backends


def _rooms():
    return {
        "bad": {"key": "bad", "action": "Ventilate", "active": False},
        "kueche": {"key": "kueche", "action": "Ventilate for cooling", "active": False},
        "schlaf": {"key": "schlaf", "action": "Continue ventilating", "active": True},
        "flur": {"key": "flur", "action": "Monitor only"},
        "neu": {"key": "neu", "action": "Something new"},
        "leer": {"key": "leer", "action": None},
        "kaputt": "broken",
    }


def test_room_recommendation_follows_a_waiting_house():
    rooms = _rooms()
    house_aligned_room_actions({"kind": "wait"}, rooms)
    assert rooms["bad"]["house_aligned_action"] == "ventilate_later"
    assert rooms["kueche"]["house_aligned_action"] == "ventilate_later"
    assert rooms["schlaf"]["house_aligned_action"] == "continue_ventilating"  # a running session is not overridden
    assert rooms["flur"]["house_aligned_action"] == "monitor_only"
    assert rooms["neu"]["house_aligned_action"] == "unknown" and rooms["leer"]["house_aligned_action"] == "unknown"
    assert rooms["bad"]["action"] == "Ventilate"  # the physical room action stays unchanged

    pollen = _rooms()
    house_aligned_room_actions({"kind": "pollen_wait"}, pollen)
    assert pollen["bad"]["house_aligned_action"] == "ventilate_later"

    acting = _rooms()
    house_aligned_room_actions({"kind": "ventilate"}, acting)
    assert acting["bad"]["house_aligned_action"] == "ventilate"
    house_aligned_room_actions("broken", acting)
    assert acting["bad"]["house_aligned_action"] == "ventilate"
    house_aligned_room_actions({"kind": "wait"}, None)  # tolerated


def test_new_sensor_is_translated_and_wired():
    sensor = (COMP / "sensor.py").read_text(encoding="utf-8")
    assert '("house_aligned_action", "Recommendation", None, "mdi:home-switch-outline", None, True)' in sensor
    assert 'return value if value in HOUSE_ALIGNED_STATES else "unknown"' in sensor
    for name in ("translations/de.json", "translations/en.json", "strings.json"):
        entity = json.loads((COMP / name).read_text(encoding="utf-8"))["entity"]["sensor"]["house_aligned_action"]
        assert entity["name"] and set(HOUSE_ALIGNED_STATES) | {"unknown"} == set(entity["state"])
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "house_aligned_room_actions(intelligent_recommendation, results)" in coordinator
    events = (COMP / "automation_events.py").read_text(encoding="utf-8")
    assert '"house_aligned_action": room.get("house_aligned_action")' in events
    assert "ventilate_later" in (ROOT / "docs/AUTOMATIONEN.md").read_text(encoding="utf-8")


def test_card_room_views_follow_the_house_aligned_value():
    card = card_text()
    assert 'const houseHeldRoom = r => !!r && !r.active && String(r.house_aligned_action || "") === "ventilate_later";' in card
    assert card.count("roomActionLabel(r)") >= 3  # room tile, recommendation row, decision room list
    assert 'houseHoldsRoom ? "Lüften möglich · noch warten"' in card  # room detail
    assert '["Lüften möglich · noch warten", "Airing possible · wait for now"]' in card
