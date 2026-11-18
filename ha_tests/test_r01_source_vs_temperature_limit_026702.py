"""R01 (0.26.7.2): an explicit temperature limit released by the room model survives the source/presentation layers.

Real coordinator, real model, real house decision and every overlay up to the published room payload and house
recommendation. Only the moisture-source detector is forced (monkeypatch) so a shower is "running" – the order's case:
bath cooled below the configured limit while the shower source is active.
"""
from __future__ import annotations

import pytest

import custom_components.freshairiq.coordinator_room_model as crm
from custom_components.freshairiq.room_close_strategy import CONF_ROOM_AIRING_MIN_TEMP
from ha_tests.test_cov_coordinator_b import CO2, HUM, OPTIONS, TEMP, _cleanup_coordinators, _data, _make, _rooms, _with  # noqa: F401


def _force_source(monkeypatch, active: bool):
    real = crm.update_moisture_source

    def forced(*args, **kwargs):
        out = dict(real(*args, **kwargs))
        if active:
            out.update({"active": True, "label": "Dusche", "confidence": 90, "source_rate_ml_min": 12.0})
        return out
    monkeypatch.setattr(crm, "update_moisture_source", forced)


async def _cold_bath(hass, freezer, monkeypatch, *, source: bool, options: dict, room_extra: dict | None = None, co2=None):
    _force_source(monkeypatch, source)
    rooms = _with(_rooms(), "bad", **(room_extra or {}))
    d = await _make(hass, freezer, data=_data(rooms), options={**OPTIONS, "target_rh": 58.0, "min_duration_min": 5, **options})
    await d.step(60)
    await d.step(60, binary_sensor__bad_fenster="on")
    # the bath cools down while the reference air stays clearly drier (moisture still leaves the room)
    for t in (20.0, 18.0, 16.5, 15.5, 14.9, 14.9):
        states = {"sensor__bad_t": (t, TEMP), "sensor__bad_h": (70.0, HUM)}
        if co2 is not None:
            states["sensor__kueche_co2"] = (co2, CO2)
        await d.step(60, **states)
    for _ in range(3):
        await d.step(60, sensor__bad_t=(14.9, TEMP), sensor__bad_h=(70.0, HUM))
    return d


def _final(d):
    room = d.room("bad")
    rec = d.data.get("intelligent_recommendation") or {}
    return room, rec


async def test_active_shower_does_not_hide_the_released_temperature_close(hass, freezer, monkeypatch) -> None:
    d = await _cold_bath(hass, freezer, monkeypatch, source=True, options={"airing_min_room_temp_c": 16.0})
    room, rec = _final(d)
    assert room["moisture_source_active"] is True and room["delta_g_m3"] > 0.4      # the shower runs, the air still dries
    assert room["close_recommended"] is True and room["close_kind"] == "temperature_limit"
    assert room["action"] == "Close", (room["action"], room.get("reason"))
    assert room.get("house_aligned_action") == "close"
    assert "16.0 °C" in " ".join(room.get("recommendation_reasons") or []) or "16.0 °C" in str(room.get("reason"))
    assert "bad" not in (rec.get("moisture_source_kept_open") or [])
    assert rec.get("kind") == "close" and "bad" in (rec.get("room_keys") or []), (rec.get("kind"), rec.get("room_keys"))   # R09
    assert d.data.get("close_reason_kind") == "temperature_limit"                                                         # R07
    assert not (rec.get("kind") == "continue" and "bad" in (rec.get("room_keys") or []) and rec.get("status") == "moisture_source_active")


async def test_room_own_temperature_limit_behaves_like_the_global_one(hass, freezer, monkeypatch) -> None:
    d = await _cold_bath(hass, freezer, monkeypatch, source=True, options={}, room_extra={CONF_ROOM_AIRING_MIN_TEMP: 16.0})
    room, _rec = _final(d)
    assert room["close_kind"] == "temperature_limit" and room["action"] == "Close"


async def test_no_source_with_limit_still_closes(hass, freezer, monkeypatch) -> None:
    d = await _cold_bath(hass, freezer, monkeypatch, source=False, options={"airing_min_room_temp_c": 16.0})
    room, _rec = _final(d)
    assert room["close_kind"] == "temperature_limit" and room["action"] == "Close"


async def test_source_without_limit_keeps_the_shower_open(hass, freezer, monkeypatch) -> None:
    d = await _cold_bath(hass, freezer, monkeypatch, source=True, options={"airing_min_room_temp_c": 0.0})
    room, rec = _final(d)
    assert room["action"] == "Continue ventilating" and room["close_recommended"] is False
    assert room.get("close_kind") is None
    assert room.get("house_aligned_action") in {"continue_ventilating", None}


async def test_r02_held_goal_close_keeps_its_true_reason_up_to_the_payload(hass, freezer, monkeypatch) -> None:
    """R02: goals reached (57 %, target 58) → close; humidity back at 60 % stays inside the 2 % hysteresis → still close,
    explained as held goal close, never as "reference air no longer removes moisture" (the air is clearly drier)."""
    from custom_components.freshairiq.room_close_strategy import CONF_ROOM_CLOSE_STRATEGY, STRATEGY_GOALS
    _force_source(monkeypatch, False)
    rooms = _with(_rooms(), "bad", **{CONF_ROOM_CLOSE_STRATEGY: STRATEGY_GOALS})
    d = await _make(hass, freezer, data=_data(rooms), options={**OPTIONS, "target_rh": 58.0, "min_duration_min": 5, "airing_min_room_temp_c": 0.0})
    await d.step(60)
    await d.step(60, binary_sensor__bad_fenster="on")
    for rh in (66.0, 63.0, 60.0, 58.0, 57.0, 57.0, 57.0):
        await d.step(60, sensor__bad_t=(20.0, TEMP), sensor__bad_h=(rh, HUM))
    reached = d.room("bad")
    assert reached["action"] == "Close" and reached["close_kind"] == "goals_reached", (reached["action"], reached.get("close_kind"))
    for _ in range(3):
        await d.step(60, sensor__bad_t=(20.0, TEMP), sensor__bad_h=(60.0, HUM))
    room = d.room("bad")
    text = " ".join(room.get("recommendation_reasons") or [])
    assert room["delta_g_m3"] > 0.4
    assert room["action"] == "Close" and room["close_kind"] == "goals_held", (room["action"], room.get("close_kind"), text)
    # the test instance runs in English (DE wording: tests/test_r01_r02_close_kind_026702.py)
    assert "until humidity rises above 60 % (now 60 %, target 58 %)" in text
    assert "hardly drier" not in text and "no longer removes moisture" not in text
    await d.step(60, sensor__bad_t=(20.0, TEMP), sensor__bad_h=(61.0, HUM))   # above target + hysteresis → released
    assert d.room("bad")["close_kind"] != "goals_held"


async def test_b3_stored_temperature_close_is_never_held_as_reached_goals(hass, freezer, monkeypatch) -> None:
    """B3 (0.26.7.1): goals mode + limit 16 °C; the bath cools below the limit (close: temperature_limit), the humidity
    goal 58 % is never reached; after warming up again the close is not presented as "goals reached"."""
    from custom_components.freshairiq.room_close_strategy import CONF_ROOM_CLOSE_STRATEGY, STRATEGY_GOALS
    _force_source(monkeypatch, False)
    rooms = _with(_rooms(), "bad", **{CONF_ROOM_CLOSE_STRATEGY: STRATEGY_GOALS})
    d = await _make(hass, freezer, data=_data(rooms), options={**OPTIONS, "target_rh": 58.0, "min_duration_min": 5, "airing_min_room_temp_c": 16.0})
    await d.step(60)
    await d.step(60, binary_sensor__bad_fenster="on")
    for t, rh in ((20.0, 65.0), (19.0, 63.0), (17.0, 61.0), (15.0, 59.0), (14.9, 59.0), (14.9, 59.0)):
        await d.step(60, sensor__bad_t=(t, TEMP), sensor__bad_h=(rh, HUM))
    cold = d.room("bad")
    assert cold["close_kind"] == "temperature_limit" and cold["action"] == "Close"
    assert d.coordinator.store.room("bad").get("close_notified_kind") == "temperature_limit"
    for _ in range(3):
        await d.step(60, sensor__bad_t=(17.0, TEMP), sensor__bad_h=(59.0, HUM))
    warm = d.room("bad")
    text = " ".join(warm.get("recommendation_reasons") or [])
    assert warm.get("close_kind") != "goals_held", (warm["action"], warm.get("close_kind"), text)
    assert "goals of this room were reached" not in text
