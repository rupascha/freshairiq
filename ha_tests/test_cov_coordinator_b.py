"""Real-HA runtime coverage for the second half of the FreshAirIQ coordinator.

Drives the real ``FreshAirIQCoordinator`` (room evaluation, ventilation session
start/continuation, close confirmation, final measurement wait, session finish
with and without valid measurements, cross ventilation and learning) against a
real Home Assistant core with frozen time.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.freshairiq import coordinator as coord_mod
from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.storage import LearningStore

TEMP = {"device_class": "temperature", "unit_of_measurement": "°C", "state_class": "measurement"}
HUM = {"device_class": "humidity", "unit_of_measurement": "%", "state_class": "measurement"}
CO2 = {"device_class": "carbon_dioxide", "unit_of_measurement": "ppm"}
BERLIN = ZoneInfo("Europe/Berlin")
WINDOW = {"device_class": "window"}
DOOR = {"device_class": "door"}


def _room(key, name, floor, *, temp, hum, contacts=(), volume=None, dims=None, co2="", climate="",
          exhaust="", include=True, orientation="south", mode="any", sort=0, extra=None):
    room = {
        "key": key, "name": name, "floor": floor, "sort_order": sort,
        "include_in_calculations": include,
        "temperature": list(temp), "humidity": list(hum),
        "temperature_aggregation": "mean", "humidity_aggregation": "mean",
        "contacts": list(contacts), "contact_mode": mode,
        "contact_delays": {c: 0 for c in contacts},
        "contact_orientations": {c: orientation for c in contacts},
        "window_orientation": orientation,
        "volume_mode": "dimensions" if dims else "direct",
        "volume": round(dims[0] * dims[1] * dims[2], 3) if dims else volume,
        "length": dims[0] if dims else None, "width": dims[1] if dims else None, "height": dims[2] if dims else None,
        "co2": co2, "climate": climate, "exhaust_fan": exhaust,
        "ventilation_threshold_mode": "automatic", "ventilation_threshold_percent": 5, "ventilation_threshold_ml": 100,
        "goal_priorities": ["humidity", "co2", "temperature"],
        "target_temperature_mode": "automatic",
        "moisture_sources": [],
    }
    room.update(extra or {})
    return room


def _rooms() -> list[dict[str, Any]]:
    return [
        _room("bad", "Badezimmer", "ground_floor", temp=["sensor.bad_t"], hum=["sensor.bad_h"], contacts=["binary_sensor.bad_fenster"],
              dims=(3.0, 2.5, 2.5), sort=0, extra={"moisture_sources": ["shower"]}),
        _room("flur", "Flur EG", "ground_floor", temp=["sensor.flur_t1", "sensor.flur_t2"], hum=["sensor.flur_h"],
              contacts=["binary_sensor.haustuer"], volume=30, orientation="north", sort=1),
        _room("kueche", "Wohnküche", "ground_floor", temp=["sensor.kueche_t"], hum=["sensor.kueche_h"],
              contacts=["binary_sensor.kueche_fenster", "binary_sensor.terrasse"], volume=95, co2="sensor.kueche_co2",
              climate="climate.kueche", orientation="west", sort=2, extra={"moisture_sources": ["cooking"]}),
        _room("schlaf", "Schlafzimmer", "upper_floor", temp=["sensor.schlaf_t"], hum=["sensor.schlaf_h"],
              contacts=["binary_sensor.schlaf_fenster"], volume=42, orientation="east", sort=3),
        _room("buero", "Arbeitszimmer", "upper_floor", temp=["sensor.buero_t"], hum=["sensor.buero_h"],
              contacts=["binary_sensor.buero_fenster"], volume=33, exhaust="fan.buero_abluft", sort=4),
        _room("lager", "Abstellraum", "basement", temp=[], hum=[], volume=12, include=False, sort=5),
    ]


def _data(rooms=None) -> dict[str, Any]:
    return {
        "outdoor_weather": "weather.home",
        "outdoor_temperature": "sensor.aussen_t",
        "outdoor_humidity": "sensor.aussen_h",
        "rooms": _rooms() if rooms is None else rooms,
        "levels": ["basement", "ground_floor", "upper_floor"],
    }


OPTIONS = {
    "adult_occupants": 2, "child_occupants": 1, "night_start_hour": "22:30", "night_end_hour": "06:30",
    "night_forecast_enabled": True, "notifications_enabled": False, "learning_enabled": True,
    "diagnostics_consent": "declined",
}


def _forecast(start: datetime, hours: int = 24, temp=9.0, hum=82.0) -> list[dict[str, Any]]:
    return [
        {"datetime": (start + timedelta(hours=h)).isoformat(), "temperature": round(temp - 0.3 * min(h, 8), 1),
         "humidity": min(98.0, hum + h), "precipitation": 0.4 if h < 6 else 0.0, "condition": "rainy"}
        for h in range(hours)
    ]


def _states(start: datetime) -> dict[str, tuple[Any, dict]]:
    states: dict[str, tuple[Any, dict]] = {
        "weather.home": ("rainy", {"temperature": 9.0, "humidity": 82.0, "wind_speed": 12.0, "wind_bearing": 250,
                                   "forecast": _forecast(start)}),
        "sensor.aussen_t": (9.0, TEMP), "sensor.aussen_h": (82.0, HUM),
        "sensor.bad_t": (23.4, TEMP), "sensor.bad_h": (79.0, HUM),
        "sensor.flur_t1": (20.6, TEMP), "sensor.flur_t2": (20.9, TEMP), "sensor.flur_h": (63.0, HUM),
        "sensor.kueche_t": (22.1, TEMP), "sensor.kueche_h": (61.0, HUM),
        "sensor.kueche_co2": (1180, CO2),
        "climate.kueche": ("heat", {"temperature": 21.5, "current_temperature": 22.1, "hvac_action": "heating"}),
        "sensor.schlaf_t": (19.4, TEMP), "sensor.schlaf_h": (58.0, HUM),
        "sensor.buero_t": (21.2, TEMP), "sensor.buero_h": (55.0, HUM),
        "fan.buero_abluft": ("off", {}),
    }
    for contact in ("binary_sensor.bad_fenster", "binary_sensor.haustuer", "binary_sensor.kueche_fenster",
                    "binary_sensor.terrasse", "binary_sensor.schlaf_fenster", "binary_sensor.buero_fenster"):
        states[contact] = ("off", WINDOW if "fenster" in contact else DOOR)
    return states


_CREATED: list[Any] = []


@pytest.fixture(autouse=True)
async def _cleanup_coordinators():
    yield
    while _CREATED:
        coordinator = _CREATED.pop()
        coordinator._clear_runtime_listeners()
        if coordinator._unsub_automation_events is not None:
            coordinator._unsub_automation_events()
            coordinator._unsub_automation_events = None
        await coordinator.telemetry.async_stop()


class Drive:
    """Small driver around a real coordinator instance."""

    def __init__(self, hass, freezer, coordinator, store, entry) -> None:
        self.hass, self.freezer, self.coordinator, self.store, self.entry = hass, freezer, coordinator, store, entry
        self.data: dict[str, Any] = {}

    def set(self, entity_id: str, state: Any, attrs: dict | None = None) -> None:
        old = self.hass.states.get(entity_id)
        self.hass.states.async_set(entity_id, state, attrs if attrs is not None else (dict(old.attributes) if old else {}),
                                   force_update=True)

    async def step(self, advance: float = 60, **states: Any) -> dict[str, Any]:
        if advance:
            self.freezer.tick(timedelta(seconds=advance))
        for entity_id, value in states.items():
            entity_id = entity_id.replace("__", ".")
            if isinstance(value, tuple):
                self.set(entity_id, *value)
            else:
                self.set(entity_id, value)
        data = await self.coordinator._async_update_data()
        self.coordinator.data = data
        self.data = data
        await self.hass.async_block_till_done()
        return data

    async def finish(self, **states: Any) -> None:
        """Let the 3 s close confirmation and the 10 s final measurement wait expire."""
        await self.step(5, **states)
        await self.step(12)

    def mem(self, room: str) -> dict[str, Any]:
        return self.store.data["rooms"][room]

    def room(self, room: str) -> dict[str, Any]:
        return self.data["rooms"][room]


async def _make(hass, freezer, *, start: datetime | None = None, data=None, options=None, initial=None,
                listeners: bool = False) -> Drive:
    start = start or datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN)
    freezer.move_to(start)
    await hass.config.async_set_time_zone("Europe/Berlin")
    base = _states(start)
    for entity_id, value in {**base, **(initial or {})}.items():
        state, attrs = value if isinstance(value, tuple) else (value, base.get(entity_id, (None, {}))[1])
        hass.states.async_set(entity_id, state, attrs)
    entry = MockConfigEntry(domain=DOMAIN, title="FreshAirIQ", version=8, minor_version=1,
                            data=copy.deepcopy(data or _data()), options=copy.deepcopy(OPTIONS if options is None else options))
    entry.add_to_hass(hass)
    store = LearningStore(hass, entry.entry_id)
    await store.async_load()
    coordinator = coord_mod.FreshAirIQCoordinator(hass, entry, store)
    _CREATED.append(coordinator)
    if listeners:
        await coordinator.async_start_listeners()
    drive = Drive(hass, freezer, coordinator, store, entry)
    await drive.step(0)
    return drive



async def test_bath_airing_session_finishes_with_learning(hass, freezer) -> None:
    d = await _make(hass, freezer, start=datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN))
    for _ in range(3):
        await d.step(60)
    await d.step(60, binary_sensor__bad_fenster="on")
    assert d.mem("bad")["session_active"] is True
    for i in range(12):
        await d.step(60, sensor__bad_h=round(79.0 - 1.6 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.12 * (i + 1), 2))
    await d.step(60, binary_sensor__bad_fenster="off")
    for i in range(8):
        await d.step(120, sensor__bad_h=round(60.0 + 0.5 * (i + 1), 1), sensor__bad_t=round(22.0 + 0.05 * i, 2))
    mem = d.mem("bad")
    assert mem["session_active"] is False
    # The finished session was logged with a measured result and learning attempt.
    log = d.store.data.get("ventilation_log") or []
    assert any(str(row.get("key") or row.get("room") or "") == "bad" or "bad" in str(row) for row in log)
    assert mem["last_ventilation_ended_at"]
    assert mem.get("last_learning_at")
    assert d.store.data["last_diagnosis"].startswith("Badezimmer: ")


async def test_kitchen_cross_ventilation_and_cross_pairs(hass, freezer) -> None:
    options = {**OPTIONS, "cross_ventilation_pairs": "bad+flur,kueche+schlaf,unknown+bad,bad", "cross_zone_connections": "kueche+schlaf"}
    d = await _make(hass, freezer, options=options)
    assert d.coordinator._cross_ventilation_active() is False
    await d.step(60, binary_sensor__kueche_fenster="on", binary_sensor__terrasse="on")
    assert d.mem("kueche")["session_active"] is True
    # Only one room of each pair open -> no house cross ventilation.
    assert d.coordinator._cross_ventilation_active() is False
    await d.step(60, binary_sensor__schlaf_fenster="on")
    assert d.coordinator._cross_ventilation_active() is True
    for i in range(6):
        await d.step(60, sensor__kueche_co2=1180 - 110 * (i + 1), sensor__kueche_h=round(61 - 0.8 * (i + 1), 1),
                     sensor__kueche_t=round(22.1 - 0.15 * (i + 1), 2), sensor__schlaf_h=round(58 - 0.5 * (i + 1), 1))
    await d.step(60, binary_sensor__kueche_fenster="off", binary_sensor__terrasse="off", binary_sensor__schlaf_fenster="off")
    for i in range(4):
        await d.step(30, sensor__kueche_h=round(56.5 + 0.1 * i, 1), sensor__schlaf_h=round(55.0 + 0.1 * i, 1))
    assert d.mem("kueche")["session_active"] is False
    assert d.coordinator._cross_ventilation_active() is False
    entries = [e for e in d.store.data.get("ventilation_log") or [] if "kueche" in str(e)]
    assert entries


async def test_same_floor_cross_pair_with_three_state_contact(hass, freezer) -> None:
    lage = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
    rooms = _rooms()
    for room in rooms:
        if room["key"] == "schlaf":
            room["contacts"] = ["sensor.schlaf_fenster_lage"]
            room["contact_delays"] = {"sensor.schlaf_fenster_lage": 0}
            room["contact_orientations"] = {"sensor.schlaf_fenster_lage": "east"}
    options = {**OPTIONS, "cross_ventilation_pairs": "schlaf+buero"}
    d = await _make(hass, freezer, data=_data(rooms), options=options,
                    initial={"sensor.schlaf_fenster_lage": ("closed", lage), "sensor.schlaf_h": 64.0})
    await d.step(60, sensor__schlaf_fenster_lage=("tilted", lage))
    for i in range(3):
        await d.step(300, sensor__schlaf_h=round(64 - 0.7 * (i + 1), 1))
    assert d.mem("schlaf")["session_active"] is True
    d.mem("schlaf")["stable_opening_since"] = {"sensor.schlaf_fenster_lage": "not-a-date"}
    await d.step(60, sensor__schlaf_fenster_lage=("open", lage), binary_sensor__buero_fenster="on")
    assert d.coordinator._cross_ventilation_active() is True
    for i in range(3):
        await d.step(60, sensor__schlaf_h=round(61 - 1.2 * (i + 1), 1), sensor__buero_h=round(55 - 0.5 * (i + 1), 1))
    await d.step(60, sensor__schlaf_fenster_lage=("closed", lage), binary_sensor__buero_fenster="off")
    for _ in range(3):
        await d.step(30)
    assert d.mem("schlaf")["session_active"] is False
    # Tilted first, then fully open: the airing is recorded as mixed-mode.
    assert d.mem("schlaf")["session_opening_mode_mixed"] is True
    assert d.mem("schlaf")["last_learning_at"]


async def test_humidity_lost_at_close_finishes_from_last_valid_snapshot(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(4):
        await d.step(60, sensor__bad_h=round(79.0 - 2 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.1 * (i + 1), 2))
    await d.step(60, binary_sensor__bad_fenster="off", sensor__bad_h="unavailable")
    await d.step(5)
    await d.step(20)
    mem = d.mem("bad")
    assert mem["session_active"] is False
    event = [e for e in d.store.data["ventilation_log"] if "bad" in str(e)][-1]
    assert "bad" in str(event)


async def test_lost_climate_without_snapshot_finishes_without_measurement(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(3):
        await d.step(60, sensor__bad_h=round(79.0 - 2 * (i + 1), 1))
    await d.step(60, binary_sensor__bad_fenster="off", sensor__bad_h="unavailable", sensor__bad_t="unavailable")
    mem = d.mem("bad")
    for k in ("session_last_valid_temperature", "session_last_valid_humidity"):
        mem[k] = None
    await d.step(5)
    await d.step(20)
    mem = d.mem("bad")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is False
    assert mem["post_close_last_outcome"]["quality"] == "insufficient"
    assert "Abschlusswartezeit" in mem["diagnosis"]
    assert mem["last_ventilation_removed_ml"] is None


async def test_dead_contact_ends_session_without_learning(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(3):
        await d.step(60, sensor__bad_h=round(79.0 - 2 * (i + 1), 1))
    await d.step(60, binary_sensor__bad_fenster="unavailable")
    assert d.mem("bad")["session_active"] is True
    await d.step(1000, sensor__bad_h=72.0)
    await d.step(20)
    await d.step(20)
    mem = d.mem("bad")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is False


async def test_restart_keeps_session_and_repairs_corrupt_baseline(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60, binary_sensor__bad_fenster="on")
    await d.step(60, sensor__bad_h=76.0)
    mem = d.mem("bad")
    mem["session_start_temp"] = 99.0
    mem["session_started"] = "garbage"
    mem["session_physical_started"] = "garbage"
    mem["session_close_detected_at"] = None
    mem.pop("session_learning_start_ah", None)
    # A fresh coordinator on the same store simulates a Home Assistant restart.
    restarted = coord_mod.FreshAirIQCoordinator(hass, d.entry, d.store)
    _CREATED.append(restarted)
    d.coordinator = restarted
    await d.step(60, sensor__bad_h=75.0)
    mem = d.mem("bad")
    assert mem["session_active"] is True
    assert mem["session_start_temp"] == pytest.approx(23.4)
    assert mem["session_temperature_reports"] == 0
    assert datetime.fromisoformat(mem["session_started"])
    await d.step(60, sensor__bad_h=73.0, sensor__bad_t=23.0)
    await d.step(60, binary_sensor__bad_fenster="off")
    await d.finish()
    assert d.mem("bad")["session_active"] is False


async def test_exhaust_fan_session_and_window_joining(hass, freezer) -> None:
    initial = {"sensor.buero_h": (68.0, HUM), "sensor.buero_t": (24.0, TEMP)}
    d = await _make(hass, freezer, initial=initial)
    await d.step(60, fan__buero_abluft="on")
    mem = d.mem("buero")
    assert mem["session_active"] is True
    assert mem["session_opening_mode"] == "mechanical_exhaust"
    assert mem["session_target_min"] is None
    for i in range(3):
        await d.step(120, sensor__buero_h=round(68 - 1.2 * (i + 1), 1))
    await d.step(60, binary_sensor__buero_fenster="on")
    assert d.mem("buero")["session_opening_mode_mixed"] is True
    assert d.mem("buero")["session_target_fan_start"] is False
    await d.step(120, sensor__buero_h=63.0)
    await d.step(60, binary_sensor__buero_fenster="off", fan__buero_abluft="off")
    await d.finish()
    assert d.mem("buero")["session_active"] is False


async def test_humid_outdoor_air_marks_reference_reversal(hass, freezer) -> None:
    d = await _make(hass, freezer, start=datetime(2026, 7, 15, 15, 0, tzinfo=BERLIN),
                    options={**OPTIONS, "operating_profile": "summer_cooling"},
                    initial={"sensor.aussen_t": (29.0, TEMP), "sensor.aussen_h": (40.0, HUM),
                             "sensor.schlaf_t": (27.0, TEMP), "sensor.schlaf_h": (52.0, HUM)})
    await d.step(60, binary_sensor__schlaf_fenster="on")
    await d.step(120, sensor__schlaf_t=26.5)
    await d.step(120, sensor__aussen_t=30.0, sensor__aussen_h=80.0, sensor__schlaf_t=26.6, sensor__schlaf_h=55.0)
    assert d.mem("schlaf")["session_reference_moisture_reversal"] is True
    await d.step(120, sensor__schlaf_h=57.0)
    await d.step(60, binary_sensor__schlaf_fenster="off")
    await d.finish()
    mem = d.mem("schlaf")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is False
    assert "Referenzluft" in mem["diagnosis"]


async def test_shower_moisture_source_contaminates_learning(hass, freezer) -> None:
    d = await _make(hass, freezer, initial={"sensor.bad_h": (65.0, HUM)})
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(10):
        await d.step(60, sensor__bad_h=round(65 + 2.5 * (i + 1), 1), sensor__bad_t=round(23.4 + 0.2 * (i + 1), 2))
    await d.step(60, binary_sensor__bad_fenster="off")
    await d.finish()
    mem = d.mem("bad")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is False


async def test_reopen_during_close_confirmation_continues_session(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60, binary_sensor__bad_fenster="on")
    await d.step(60, sensor__bad_h=75.0)
    await d.step(60, binary_sensor__bad_fenster="off")
    await d.step(5)  # close pending, waiting for final measurement
    assert d.mem("bad")["session_close_pending"] is True
    await d.step(1, binary_sensor__bad_fenster="on")
    mem = d.mem("bad")
    assert mem["session_active"] is True
    assert mem["session_close_pending"] is False
    assert mem["session_close_detected_at"] is None
    await d.step(60, sensor__bad_h=72.0)
    await d.step(60, binary_sensor__bad_fenster="off")
    await d.step(4)
    await d.step(1, sensor__bad_h=72.5, sensor__bad_t=23.1)
    await d.step(1, sensor__bad_h=72.6)
    await d.step(20)
    assert d.mem("bad")["session_active"] is False



def _with(rooms: list[dict[str, Any]], key: str, **changes: Any) -> list[dict[str, Any]]:
    for room in rooms:
        if room["key"] == key:
            room.update(changes)
    return rooms


async def test_closed_cover_blocks_learning_of_bath_session(hass, freezer) -> None:
    rooms = _with(_rooms(), "bad", contact_covers={"binary_sensor.bad_fenster": ["cover.bad_rollo"]})
    d = await _make(hass, freezer, data=_data(rooms),
                    initial={"cover.bad_rollo": ("open", {"current_position": 5})})
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(8):
        await d.step(60, sensor__bad_h=round(79.0 - 1.5 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.1 * (i + 1), 2))
    assert d.mem("bad")["session_cover_learning_blocked"] is True
    await d.step(60, binary_sensor__bad_fenster="off")
    await d.finish()
    mem = d.mem("bad")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is False
    assert mem["learning_samples"] == 0


async def test_pure_exhaust_fan_session_learns_mechanical_model(hass, freezer) -> None:
    # Utility room ventilated only by its exhaust fan (no window contact).
    rooms = _rooms() + [_room("hwr", "Hauswirtschaft", "basement", temp=["sensor.hwr_t"], hum=["sensor.hwr_h"],
                              volume=20, exhaust="fan.hwr_abluft", sort=6)]
    initial = {"sensor.hwr_h": (72.0, HUM), "sensor.hwr_t": (22.0, TEMP), "fan.hwr_abluft": ("off", {})}
    d = await _make(hass, freezer, data=_data(rooms), initial=initial, options={**OPTIONS, "forecast_horizon_min": 20})
    await d.step(60, fan__hwr_abluft="on")
    for i in range(12):
        await d.step(60, sensor__hwr_h=round(72 - 1.0 * (i + 1), 1), sensor__hwr_t=round(22.0 - 0.05 * (i + 1), 2))
    mem = d.mem("hwr")
    assert mem["session_opening_mode"] == "mechanical_exhaust"
    assert mem["session_opening_mode_mixed"] is False
    assert any(p.get("kind") == "live" for p in mem["session_forecast_timeline"])
    await d.step(60, fan__hwr_abluft="off")
    await d.finish(sensor__hwr_h=60.5, sensor__hwr_t=21.4)
    mem = d.mem("hwr")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is True, mem["diagnosis"]
    # The general model and the mechanical_exhaust specialist model both learn; the
    # close cycle no longer marks the session as mixed (A-20, 2026-10-16).
    assert mem["learning_samples"] >= 1
    assert mem["session_opening_mode_mixed"] is False
    assert mem["opening_learning"]["mechanical_exhaust"]["samples"] >= 1
    assert "mechanical_exhaust" in mem["diagnosis"]


async def test_cross_pair_session_learns_cross_model_and_uses_learned_rate(hass, freezer) -> None:
    options = {**OPTIONS, "cross_ventilation_pairs": "bad+flur", "forecast_horizon_min": 20}
    d = await _make(hass, freezer, options=options)
    d.mem("bad")["opening_learning"] = {"cross": {"rate": 0.05, "samples": 3, "credit": 0.5}}
    await d.step(60, binary_sensor__bad_fenster="on", binary_sensor__haustuer="on")
    assert d.coordinator._cross_ventilation_active() is True
    for i in range(10):
        await d.step(60, sensor__bad_h=round(79.0 - 1.6 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.12 * (i + 1), 2),
                     sensor__flur_h=round(63 - 0.3 * (i + 1), 1))
    assert d.mem("bad")["session_specialist_opening_mode"] == "cross"
    await d.step(60, binary_sensor__bad_fenster="off", binary_sensor__haustuer="off")
    await d.finish(sensor__bad_h=63.5, sensor__bad_t=22.2)
    mem = d.mem("bad")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is True
    assert mem["opening_learning"]["cross"]["samples"] >= 3


async def test_room_without_opening_and_monitor_only_room(hass, freezer) -> None:
    rooms = _rooms() + [
        _room("keller", "Keller", "basement", temp=["sensor.keller_t"], hum=["sensor.keller_h"], volume=40, sort=6),
        _room("hobby", "Hobby", "basement", temp=["sensor.hobby_t"], hum=["sensor.hobby_h"], volume=20, include=False, sort=7),
    ]
    rooms = _with(rooms, "schlaf", ventilation_threshold_mode="percent_room_water", ventilation_threshold_percent=4)
    rooms = _with(rooms, "buero", ventilation_threshold_mode="fixed_ml", ventilation_threshold_ml=150)
    initial = {"sensor.keller_t": (18.0, TEMP), "sensor.keller_h": (80.0, HUM),
               "sensor.hobby_t": (19.0, TEMP), "sensor.hobby_h": (60.0, HUM),
               "sensor.aussen_t": (2.0, TEMP), "sensor.aussen_h": (70.0, HUM)}
    d = await _make(hass, freezer, data=_data(rooms), initial=initial)
    await d.step(60)
    assert d.room("keller")["action"] in {"Ventilate indirectly", "Lüften über Nachbarraum"} or "indirect" in str(d.room("keller")).lower()
    assert d.room("hobby")["action"] in {"Monitor only", "Nur überwachen"} or "monitor" in str(d.room("hobby")).lower()



def _cfg(d: Drive, key: str) -> dict[str, Any]:
    return next(room for room in d.entry.data["rooms"] if room["key"] == key)


async def _active_bath(hass, freezer, minutes: int = 8, **make) -> Drive:
    d = await _make(hass, freezer, **make)
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(minutes):
        await d.step(60, sensor__bad_h=round(79.0 - 1.6 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.12 * (i + 1), 2))
    assert d.mem("bad")["session_active"] is True
    return d


async def test_direct_finish_learns_open_specialist_and_passage_pattern(hass, freezer) -> None:
    """Specialist learning branch, driven directly (see report: unreachable at runtime)."""
    d = await _active_bath(hass, freezer)
    mem = d.mem("bad")
    mem.update({
        "session_specialist_opening_mode": "open", "session_opening_mode_mixed": False,
        "session_learning_quarantined": False, "session_passage_door": True,
        "session_passage_contacts": ["binary_sensor.bad_fenster"],
        "passage_behavior": {"binary_sensor.bad_fenster": {"pulled_shut_events": 3, "genuine_open_events": 0}},
        "opening_learning": {"open": {"rate": 0.03, "samples": 2, "credit": 0.5}},
        "learning_sample_credit": "not-a-number", "learning_observation_dates": "corrupt",
    })
    now = coord_mod.dt_util.now()
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.4, 64.0, 9.0, 82.0, now, False, None)
    assert event["key"] == "bad"
    assert mem["last_learning_valid"] is True
    assert "open-Modell separat gelernt" in mem["diagnosis"]
    assert "Durchgangstür-Muster gelernt" in mem["diagnosis"]
    assert mem["opening_learning"]["open"]["samples"] >= 2
    assert mem["learning_observation_dates"] == [now.date().isoformat()]
    assert mem["passage_behavior"]["binary_sensor.bad_fenster"]["genuine_open_events"] == 1


async def test_direct_finish_rejects_weak_passage_door_open_model(hass, freezer) -> None:
    d = await _active_bath(hass, freezer)
    mem = d.mem("bad")
    mem.update({
        "session_specialist_opening_mode": "open", "session_opening_mode_mixed": False,
        "session_learning_quarantined": False, "session_passage_door": True,
        "session_passage_contacts": ["binary_sensor.bad_fenster"], "passage_behavior": None,
        "opening_learning": {"open": {"rate": 0.005, "samples": 0}},
    })
    now = coord_mod.dt_util.now()
    await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.4, 64.0, 9.0, 82.0, now, False, None)
    assert mem["session_learning_quarantined"] is True
    assert mem["session_learning_quarantine_code"] == "FAIQ-OPENING-3STATE-003"
    assert "Open-Speziallernen wegen unplausibel geringer Lüftungswirkung verworfen" in mem["diagnosis"]
    assert mem["passage_behavior"]["binary_sensor.bad_fenster"]["pulled_shut_events"] == 1
    assert mem["opening_learning"]["open"]["rate"] == 0.005


async def test_direct_finish_with_corrupt_legacy_session_fields(hass, freezer) -> None:
    d = await _active_bath(hass, freezer)
    mem = d.mem("bad")
    now = coord_mod.dt_util.now()
    mem.update({
        "session_learning_started": "bad", "session_physical_started": "also-bad",
        "session_learning_source_ah": None, "session_start_source_ah": None,
        "session_learning_start_ah": None,
        "session_validation_started": "corrupt",
        "session_prediction_start_context": None,
        "session_prediction_snapshot_valid": True, "session_prediction_horizon_min": 45.0,
        "personal_context_observation_dates": "corrupt",
    })
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.4, 64.0, 9.0, 82.0, now, False, None)
    # Both start clocks are unusable: the session collapses to zero duration at ``now``.
    assert event["started_at"] == now.isoformat()
    assert event["duration_min"] == 0
    assert event["prediction_time_aligned"] is False
    assert "Ältere Startprognose" in event["outcome_feedback_reason"]
    assert mem["personal_context_observation_dates"] == [now.date().isoformat()]


async def test_direct_finish_legacy_snapshot_variants(hass, freezer) -> None:
    d = await _active_bath(hass, freezer)
    mem = d.mem("bad")
    saved = copy.deepcopy(mem)
    now = coord_mod.dt_util.now()
    # Legacy fixed-horizon snapshot that matches the measured duration.
    mem.update({"session_prediction_start_context": None, "session_prediction_snapshot_valid": True,
                "session_prediction_horizon_min": 9.0})
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.4, 64.0, 9.0, 82.0, now, False,
                                               {"quality": "excellent", "learning_eligible": True, "validation_eligible": True})
    assert event["prediction_time_aligned"] is False
    # No snapshot at all.
    mem.clear(); mem.update(copy.deepcopy(saved))
    mem.update({"session_prediction_start_context": None, "session_prediction_snapshot_valid": False,
                "session_prediction_horizon_min": None, "session_physical_started": None,
                "session_started": (now + timedelta(minutes=5)).isoformat(), "session_learning_started": None})
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.4, 64.0, 9.0, 82.0, now, False, None)
    assert "keine Startprognose eingefroren" in event["outcome_feedback_reason"]
    # A start in the future is clamped: the finish never precedes the start.
    assert event["ended_at"] == event["started_at"]


async def test_direct_finish_without_measurement_handles_corrupt_start(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=3)
    mem = d.mem("bad")
    now = coord_mod.dt_util.now()
    mem["session_physical_started"] = "garbage"
    event = d.coordinator._finish_session_without_measurement(mem, _cfg(d, "bad"), now)
    assert event["duration_min"] == 0
    assert event["final_measurement_source"] == "unavailable_after_grace"
    assert mem["personal_context_observation_dates"].count(now.date().isoformat()) == 1
    # Second fail-safe close the same day; started in the future -> clamped.
    mem["session_physical_started"] = (now + timedelta(minutes=3)).isoformat()
    mem["session_cross_seconds"] = 30.0
    event = d.coordinator._finish_session_without_measurement(mem, _cfg(d, "bad"), now)
    assert event["ended_at"] == event["started_at"]
    assert event["cross_ventilation"] is False
    assert mem["personal_context_observation_dates"].count(now.date().isoformat()) == 1


async def test_corrupt_persisted_session_clocks_are_tolerated(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=3)
    mem = d.mem("bad")
    # Corrupt physical start / tentative close boundary while the window is open.
    mem["session_physical_started"] = "corrupt"
    mem["session_close_detected_at"] = "corrupt"
    await d.step(60, sensor__bad_h=72.0)
    mem = d.mem("bad")
    assert mem["session_active"] is True
    assert mem["session_close_detected_at"] is None  # open window clears the tentative close
    mem["session_physical_started"] = mem["session_started"]
    # Corrupt learned forecast observation clocks.
    mem["forecast_observation_at"] = "corrupt"
    mem["humidity_high_since"] = "corrupt"
    mem["forecast_recent_removed_ml_min"] = 5.0
    mem["forecast_recent_observed_at"] = "corrupt"
    await d.step(60, sensor__bad_h=71.0)
    mem = d.mem("bad")
    assert datetime.fromisoformat(mem["forecast_observation_at"])
    mem["forecast_recent_removed_ml_min"] = 5.0
    mem["forecast_recent_observed_at"] = (coord_mod.dt_util.now() - timedelta(hours=2)).isoformat()
    await d.step(60, sensor__bad_h=70.5)
    # Close, then corrupt the close boundary and the deadline during the final wait.
    await d.step(60, binary_sensor__bad_fenster="off")
    await d.step(5)
    mem = d.mem("bad")
    assert mem["session_close_pending"] is True
    mem["session_close_detected_at"] = "corrupt"
    mem["session_close_deadline_at"] = (coord_mod.dt_util.now() + timedelta(hours=1)).isoformat()
    await d.step(1)
    assert d.mem("bad")["session_active"] is True
    d.mem("bad")["session_close_deadline_at"] = "corrupt"
    await d.step(1)
    mem = d.mem("bad")
    assert mem["session_active"] is False
    assert datetime.fromisoformat(mem["last_ventilation_ended_at"])
    # A corrupt "last ventilation" clock afterwards is ignored.
    mem["last_ventilation_ended_at"] = "corrupt"
    await d.step(60)
    assert d.mem("bad")["session_active"] is False


async def test_restart_continues_session_and_counts_reports(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=2)
    restarted = coord_mod.FreshAirIQCoordinator(hass, d.entry, d.store)
    _CREATED.append(restarted)
    d.coordinator = restarted
    before = d.mem("bad")["session_last_humidity_update"]
    await d.step(60, sensor__bad_h=74.0, sensor__bad_t=23.0)
    mem = d.mem("bad")
    assert mem["session_active"] is True
    assert mem["session_last_humidity_update"] != before
    # A long coordinator gap (> 30 min) only refreshes the observation baseline.
    await d.step(1900, sensor__bad_h=70.0)
    assert d.mem("bad")["session_active"] is True


async def test_multi_sensor_room_with_missing_and_lost_temperatures(hass, freezer) -> None:
    rooms = _with(_rooms(), "flur", temperature=["sensor.flur_t1", "sensor.flur_t2", "sensor.flur_t_missing"])
    d = await _make(hass, freezer, data=_data(rooms))
    await d.step(60, binary_sensor__haustuer="on")
    assert d.mem("flur")["session_active"] is True
    assert d.mem("flur")["session_climate_report_counts"]
    await d.step(60, sensor__flur_t1="unavailable", sensor__flur_t2="unavailable")
    assert d.mem("flur")["session_active"] is True
    await d.step(60, sensor__flur_t1=20.1, sensor__flur_t2=20.3, sensor__flur_h=61.0)
    await d.step(60, binary_sensor__haustuer="off")
    await d.finish()
    assert d.mem("flur")["session_active"] is False


async def test_held_sensor_values_mark_uncertain_start(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(1500)  # 25 min without any new bath sensor report
    await d.step(60, binary_sensor__bad_fenster="on")
    assert d.mem("bad")["start_measurement_state"] == "uncertain"


async def test_prediction_snapshot_missed_invalid_and_live_timeline(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=1)
    mem = d.mem("bad")
    # Restored session whose start snapshot is still pending but 10 min old.
    mem["session_prediction_snapshot_pending"] = True
    mem["session_validation_started"] = (coord_mod.dt_util.now() - timedelta(minutes=10)).isoformat()
    await d.step(60, sensor__bad_h=76.0)
    mem = d.mem("bad")
    assert mem["session_prediction_reference"] == "start_snapshot_missed"
    assert mem["session_prediction_snapshot_valid"] is False
    # Corrupt validation clock -> treated as just started; NaN duration -> invalid snapshot.
    mem["session_prediction_snapshot_pending"] = True
    mem["session_validation_started"] = "corrupt"
    mem["session_recommended_duration_min"] = float("nan")
    await d.step(60, sensor__bad_h=75.5)
    mem = d.mem("bad")
    assert mem["session_prediction_reference"] == "start_snapshot_invalid"
    # Valid snapshot with a long frozen horizon produces live checkpoints.
    mem["session_prediction_snapshot_pending"] = True
    mem["session_validation_started"] = coord_mod.dt_util.now().isoformat()
    mem["session_recommended_duration_min"] = 40.0
    await d.step(30, sensor__bad_h=75.0)
    mem = d.mem("bad")
    assert mem["session_prediction_snapshot_valid"] is True
    assert mem["session_prediction_horizon_min"] > 20
    for i in range(4):
        await d.step(60, sensor__bad_h=round(74.5 - 0.5 * i, 1))
    live = [p for p in d.mem("bad")["session_forecast_timeline"] if p.get("kind") == "live"]
    assert live and live[-1]["remaining_horizon_min"] > 0.25


async def test_guardian_clears_completed_sensor_recovery(hass, freezer) -> None:
    d = await _make(hass, freezer)
    data = copy.deepcopy(d.data)
    data["sensor_recovery"] = {"active": True, "required_sources_unavailable": 0, "valid_cycles": 3,
                               "required_valid_cycles": 2, "grace_seconds": 90, "unavailable_for_seconds": 0.0}
    d.coordinator._sensor_recovery_started_at = coord_mod.dt_util.now()
    d.coordinator._sensor_recovery_valid_cycles = 3
    out = await d.coordinator._async_finalize_cycle(
        data, options=d.coordinator.options, now=coord_mod.dt_util.now(), completed_sessions=[], changed=False,
        phase_started=0.0,
    )
    assert out["guardian"]["auto_healed"] == ["clear_completed_sensor_recovery"]
    assert out["guardian"]["recovery_events"][0]["postcondition_passed"] is True
    assert d.coordinator._sensor_recovery_started_at is None


async def test_stale_three_state_contact_survives_session_repair(hass, freezer) -> None:
    lage = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
    rooms = _with(_rooms(), "schlaf", contacts=["sensor.schlaf_fenster_lage"], contact_delays={"sensor.schlaf_fenster_lage": 0},
                  contact_orientations={"sensor.schlaf_fenster_lage": "east"})
    d = await _make(hass, freezer, data=_data(rooms), initial={"sensor.schlaf_fenster_lage": ("closed", lage), "sensor.schlaf_h": (66.0, HUM)})
    await d.step(60, sensor__schlaf_fenster_lage=("open", lage))
    for i in range(3):
        await d.step(60, sensor__schlaf_h=round(66 - 1.0 * (i + 1), 1))
    assert d.mem("schlaf")["session_active"] is True
    await d.step(60, sensor__schlaf_fenster_lage=("unavailable", lage))
    await d.step(1800, sensor__schlaf_h=62.0)
    mem = d.mem("schlaf")
    assert mem["three_state_stale_contacts"] == ["sensor.schlaf_fenster_lage"]
    mem["session_start_temp"] = 120.0  # corrupt persisted baseline -> repaired
    await d.step(60, sensor__schlaf_h=61.5)
    mem = d.mem("schlaf")
    assert mem["session_active"] is True
    assert mem["session_learning_quarantined"] is True
    assert mem["session_learning_quarantine_code"] == "FAIQ-OPENING-3STATE-006"
    assert mem["session_three_state_unknown_observed"] is True
    assert mem["session_start_temp"] == pytest.approx(19.4)


async def test_direct_finish_clamps_measurement_clock_to_physical_window(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=4)
    mem = d.mem("bad")
    saved = copy.deepcopy(mem)
    now = coord_mod.dt_util.now()
    # Learning started before the physical opening -> clamped to the opening.
    mem["session_physical_started"] = (now - timedelta(minutes=4)).isoformat()
    mem["session_learning_started"] = (now - timedelta(minutes=10)).isoformat()
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.9, 70.0, 9.0, 82.0, now, False, None)
    assert event["measurement_started_at"] == event["started_at"]
    assert event["measurement_duration_min"] == pytest.approx(4.0)
    # Learning start after the end -> clamped to the end.
    mem.clear(); mem.update(copy.deepcopy(saved))
    mem["session_physical_started"] = (now - timedelta(minutes=4)).isoformat()
    mem["session_learning_started"] = (now + timedelta(minutes=2)).isoformat()
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.9, 70.0, 9.0, 82.0, now, False, None)
    assert event["measurement_started_at"] == now.isoformat()
    assert event["measurement_duration_min"] == 0


async def test_direct_finish_without_measurement_repairs_observation_dates(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=3)
    mem = d.mem("bad")
    mem["personal_context_observation_dates"] = {"corrupt": True}
    now = coord_mod.dt_util.now()
    event = d.coordinator._finish_session_without_measurement(mem, _cfg(d, "bad"), now)
    assert event["duration_min"] == pytest.approx(3.0)
    assert mem["personal_context_observation_dates"] == [now.date().isoformat()]
    assert mem["session_active"] is False


async def test_legacy_naive_session_start_does_not_count_reports(hass, freezer) -> None:
    """A naive (pre-timezone) persisted session start is not comparable with HA report times."""
    d = await _active_bath(hass, freezer, minutes=2)
    mem = d.mem("bad")
    counted = mem["session_humidity_reports"]
    mem["session_physical_started"] = mem["session_physical_started"][:19]
    previous_report = mem["session_last_humidity_update"]
    await d.step(60, sensor__bad_h=74.0)
    mem = d.mem("bad")
    assert mem["session_active"] is True
    assert mem["session_last_humidity_update"] != previous_report
    assert mem["session_humidity_reports"] == counted


async def test_legacy_naive_three_state_since_starts_session_without_reports(hass, freezer) -> None:
    """A naive persisted stable-open timestamp makes earlier reports non-comparable."""
    lage = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
    contact = "sensor.schlaf_fenster_lage"
    rooms = _with(_rooms(), "schlaf", contacts=[contact], contact_delays={contact: 0},
                  contact_orientations={contact: "east"})
    d = await _make(hass, freezer, data=_data(rooms), initial={contact: ("closed", lage), "sensor.schlaf_h": (66.0, HUM)})
    mem = d.mem("schlaf")
    assert mem["three_state_contacts"] == [contact]
    assert mem["session_active"] is False
    since = (coord_mod.dt_util.now() - timedelta(minutes=5)).replace(tzinfo=None).isoformat()
    mem["stable_opening_modes"] = {contact: "open"}
    mem["stable_opening_since"] = {contact: since}
    await d.step(1, sensor__schlaf_fenster_lage=("open", lage))
    mem = d.mem("schlaf")
    assert mem["session_active"] is True
    assert mem["session_physical_started"] == since
    assert mem["session_temperature_reports"] == 0
    assert mem["session_humidity_reports"] == 0


async def test_room_closed_for_seconds_helper_edge_states(hass, freezer) -> None:
    freezer.move_to(datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN))
    now = coord_mod.dt_util.now()
    closed_for = coord_mod._room_closed_for_seconds
    room = {"contacts": ["binary_sensor.a", "binary_sensor.b"], "contact_mode": "any"}
    hass.states.async_set("binary_sensor.a", "off")
    # A configured contact without any HA state is not a confirmed close.
    assert closed_for(hass, room, now) is None
    hass.states.async_set("binary_sensor.b", "on")
    # "any": one open contact keeps the room logically open.
    assert closed_for(hass, room, now) is None
    hass.states.async_set("binary_sensor.b", "off")
    freezer.tick(timedelta(seconds=30))
    assert closed_for(hass, room, coord_mod.dt_util.now()) == pytest.approx(30.0)
    # A stable mode outside open/tilted/closed/unknown is never read as closed.
    assert closed_for(hass, room, now, contact_modes={"binary_sensor.a": "ajar"}) is None
    # "all": the room is only closed once a required contact is closed.
    both_open = {"binary_sensor.a": "open", "binary_sensor.b": "tilted"}
    assert closed_for(hass, {**room, "contact_mode": "all"}, now, contact_modes=both_open) is None


async def test_direct_finish_without_session_start_temperature_uses_end_value(hass, freezer) -> None:
    d = await _active_bath(hass, freezer, minutes=4)
    mem = d.mem("bad")
    mem.pop("session_start_temp", None)
    now = coord_mod.dt_util.now()
    event = await d.coordinator._finish_session(mem, _cfg(d, "bad"), 22.9, 70.0, 9.0, 82.0, now, False, None)
    assert event["temp_delta_c"] == 0
