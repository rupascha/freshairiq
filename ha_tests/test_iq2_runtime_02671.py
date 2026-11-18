"""IQ2 (0.26.7.1) in the real coordinator: one state for decision, forecast, learning, storage and diagnostics.

A bath airing against clearly drier outdoor air (synthetic values): the room and house payloads carry the separate
forecast quantities, the finished airing is scored and learned once (room and house), the session record reports it,
the learning state survives a restart, older stored data without it starts cleanly, and a fan-only airing or a
disabled learning leaves the window model untouched.
"""
from __future__ import annotations

import copy
from datetime import datetime
import json

from custom_components.freshairiq import coordinator_house, iq2
from custom_components.freshairiq.dashboard_live import _payload_bytes
from custom_components.freshairiq.diagnostics_privacy import _ROOM_KEYS as ROOM_KEYS, _TOP_LEVEL_KEYS as TOP_LEVEL_KEYS
from custom_components.freshairiq.storage import LearningStore

from ha_tests.test_cov_coordinator_b import BERLIN, OPTIONS, _cleanup_coordinators, _data, _make  # noqa: F401

START = datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN)
ROOM_FIELDS = ("forecast_net_room_change_ml", "forecast_outdoor_transport_ml", "forecast_to_target_ml", "forecast_interval_ml",
               "forecast_quality", "iq2", "time_state", "time_remaining_min")
HOUSE_FIELDS = ("forecast_net_room_change_ml", "forecast_outdoor_transport_ml", "forecast_to_target_ml", "forecast_interval_ml",
                "forecast_quality_state", "forecast_scored_airings")


def _sessions(monkeypatch) -> list[dict]:
    seen: list[dict] = []
    original = coordinator_house.append_completed_sessions

    def spy(group, sessions):
        seen.extend(dict(s) for s in sessions if isinstance(s, dict))
        return original(group, sessions)

    monkeypatch.setattr(coordinator_house, "append_completed_sessions", spy)
    return seen


async def _air(d, room: str = "bad", *, start_rh: float = 79.0, start_t: float = 23.4, contact: str = "binary_sensor__bad_fenster") -> list[dict]:
    """Open, 12 minutes of falling humidity, close, final measurements. Returns the payloads while the window was open."""
    seen = []
    await d.step(60, **{contact: "on"})
    for i in range(12):
        await d.step(60, **{f"sensor__{room}_h": round(start_rh - 1.6 * (i + 1), 1), f"sensor__{room}_t": round(start_t - 0.12 * (i + 1), 2)})
        seen.append(copy.deepcopy(d.data))
    await d.step(60, **{contact: "off"})
    for i in range(8):
        await d.step(120, **{f"sensor__{room}_h": round(start_rh - 19.0 + 0.5 * (i + 1), 1), f"sensor__{room}_t": round(start_t - 1.4 + 0.05 * i, 2)})
    return seen


async def test_one_airing_is_forecast_scored_learned_and_reported_once(hass, freezer, monkeypatch) -> None:
    sessions = _sessions(monkeypatch)
    d = await _make(hass, freezer, start=START)
    mem = d.mem("bad")
    assert mem["iq2"]["schema"] == iq2.SCHEMA and mem["iq2"]["score"]["n"] == 0        # created on the first run
    idle = d.room("bad")
    assert idle["iq2"] == {"model": "iq2", "active": True, "level": "global", "mode": "general", "rate_per_min": 0.03,
                           "moisture_air_share": 0.5, "thermal_air_share": 0.15, "room_airings": 0}
    assert idle["time_state"] is None and idle["time_remaining_min"] is None           # not aired: no time
    assert d.room("lager").get("iq2", {"active": False})["active"] is False            # excluded room: no window model
    assert all(d.data[key] is None for key in HOUSE_FIELDS)                            # nothing aired: unknown, not 0

    open_cycles = await _air(d)
    running = open_cycles[4]
    room = running["rooms"]["bad"]
    assert all(key in room for key in ROOM_FIELDS)
    assert room["forecast_net_room_change_ml"] > 0 and room["forecast_outdoor_transport_ml"] >= room["forecast_net_room_change_ml"]
    assert room["forecast_to_target_ml"] > 0 and room["forecast_interval_ml"] is None and room["forecast_quality"]["state"] == "collecting"
    assert room["time_state"] in {"countdown", "minimum", "reassessing"}
    assert running["forecast_net_room_change_ml"] == room["forecast_net_room_change_ml"]   # house = its aired rooms
    assert running["forecast_quality_state"] == "collecting" and running["forecast_scored_airings"] == 0
    # the published keys pass the diagnostics allowlist (nothing new leaves the installation unlisted)
    assert set(HOUSE_FIELDS) <= set(TOP_LEVEL_KEYS) and set(ROOM_FIELDS) <= set(ROOM_KEYS)

    record = next(s for s in sessions if s.get("key") == "bad")
    report = record["iq2"]
    assert report["model"] == "iq2" and report["usable"] is True and report["mode"] == "general"
    assert report["predicted_net_ml"] > 0 and report["observed_net_ml"] > 0
    assert record["learning_observation"]["rate_inversion"] == "exponential"
    mem = d.mem("bad")
    assert "session_iq2" not in mem                                                    # reported once, not kept
    assert mem["iq2"]["score"]["n"] == 1 and mem["iq2"]["rate"]["general"]["n"] == 1
    house = d.store.data["iq2_house"]
    assert house["rate"]["general"]["n"] == 1 and house["rate"]["general"]["weight"] <= 1.0
    after = d.room("bad")["iq2"]
    assert after["room_airings"] == 1 and after["rate_per_min"] != 0.03                # the parameters in force moved
    assert d.room("flur")["iq2"]["level"] == "house"                                   # another room profits from the house
    assert d.mem("bad")["learning_samples"] == 1                                       # the reference learning still runs


async def test_learning_state_survives_a_restart_and_old_data_starts_cleanly(hass, freezer) -> None:
    d = await _make(hass, freezer, start=START)
    await _air(d)
    stored_room, stored_house = copy.deepcopy(d.mem("bad")["iq2"]), copy.deepcopy(d.store.data["iq2_house"])
    await d.store.async_save()
    again = LearningStore(hass, d.entry.entry_id)
    await again.async_load()
    assert again.data["rooms"]["bad"]["iq2"] == stored_room and again.data["iq2_house"] == stored_house

    # data written before IQ2: no room state, no house state, learned legacy values → seeded once as weak evidence
    mem = d.mem("flur")
    mem.pop("iq2", None)
    mem.update(learning_rate=0.05, learning_samples=30)
    d.store.data.pop("iq2_house", None)
    await d.step(60)
    assert mem["iq2"]["seeded_from_legacy"] is True and 0.03 < d.room("flur")["iq2"]["rate_per_min"] < 0.05
    # a state of an unknown schema is not trusted and not fatal
    mem["iq2"] = {"schema": 99, "rate": {"general": {"sum": 9, "weight": 9, "n": 9}}}
    d.store.data["iq2_house"] = "broken"
    await d.step(60)
    assert mem["iq2"]["schema"] == iq2.SCHEMA and d.room("flur")["action"]


async def test_disabled_learning_and_fan_only_airings_do_not_teach_the_window_model(hass, freezer, monkeypatch) -> None:
    sessions = _sessions(monkeypatch)
    d = await _make(hass, freezer, start=START, options={**OPTIONS, "learning_enabled": False})
    await _air(d)
    record = next(s for s in sessions if s.get("key") == "bad")
    assert record["iq2"] == {"model": "iq2", "usable": False}
    assert d.mem("bad")["iq2"]["score"]["n"] == 0 and not d.store.data.get("iq2_house", {}).get("rate")

    sessions.clear()
    fan = await _make(hass, freezer, start=START)
    fan.mem("buero").setdefault("opening_learning", {})["mechanical_exhaust"] = {"rate": 0.08, "samples": 3}
    await fan.step(60)
    await _air(fan, "buero", start_rh=70.0, start_t=21.5, contact="fan__buero_abluft")
    assert fan.mem("buero")["iq2"]["score"]["n"] == 0                                  # the exhaust model learns, not IQ2
    exhaust = [s for s in sessions if s.get("key") == "buero"]
    assert all(s["iq2"] == {"model": "iq2", "usable": False} for s in exhaust)


async def test_rooms_aired_together_count_once_for_the_house(hass, freezer) -> None:
    d = await _make(hass, freezer, start=START)
    await d.step(60, binary_sensor__bad_fenster="on", binary_sensor__schlaf_fenster="on")
    for i in range(12):
        await d.step(60, sensor__bad_h=round(79.0 - 1.6 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.12 * (i + 1), 2),
                     sensor__schlaf_h=round(66.0 - 1.0 * (i + 1), 1), sensor__schlaf_t=round(20.0 - 0.1 * (i + 1), 2))
    # both cards read one state: the live channel carries the house quantities and every room's own time and forecast
    live = json.loads(_payload_bytes(d.coordinator, d.entry.entry_id))
    assert all(key in live for key in (*HOUSE_FIELDS, "remaining_duration_state"))
    assert live["forecast_net_room_change_ml"] == sum(live["rooms"][k]["forecast_net_room_change_ml"] for k in ("bad", "schlaf"))
    for key in ("bad", "schlaf"):
        assert all(field in live["rooms"][key] for field in ROOM_FIELDS)
        assert live["rooms"][key]["time_state"] == d.room(key)["time_state"] is not None
    assert live["rooms"]["flur"]["time_state"] is None
    await d.step(60, binary_sensor__bad_fenster="off", binary_sensor__schlaf_fenster="off")
    for i in range(8):
        await d.step(120, sensor__bad_h=round(60.0 + 0.5 * (i + 1), 1), sensor__schlaf_h=round(54.2 + 0.3 * (i + 1), 1))
    learned = [key for key in ("bad", "schlaf") if d.mem(key)["iq2"]["score"]["n"] == 1]
    house = d.store.data.get("iq2_house") or {}
    if len(learned) == 2:
        # both learned: together they are one house vote, not two
        assert house["rate"]["general"]["n"] == 2 and house["rate"]["general"]["weight"] <= 1.0 + 1e-6
    else:
        assert learned, "at least one of the two airings must have been usable"
