"""Real Home Assistant runtime coverage for the first half of the FreshAirIQ coordinator.

Every test sets up a real config entry, feeds Home Assistant states and drives
the real update cycle (refresh + time travel). Assertions target the published
coordinator data, persisted learning memory and fired events.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.freshairiq.const import (
    CONF_CONTACT_MODE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_CO2,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
    CONTACT_MODE_ANY,
    DOMAIN,
)

START = datetime(2026, 1, 14, 10, 0, 0, tzinfo=dt_util.UTC)


def room(key: str, *, contacts: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    row = {
        "key": key,
        CONF_ROOM_NAME: key.title(),
        CONF_ROOM_TEMPERATURE: f"sensor.{key}_t",
        CONF_ROOM_HUMIDITY: f"sensor.{key}_h",
        CONF_ROOM_CONTACTS: list(contacts if contacts is not None else [f"binary_sensor.{key}_window"]),
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
        CONF_ROOM_VOLUME: 50.0,
        CONF_ROOM_FLOOR: "EG",
        CONF_ROOM_INCLUDE_CALCULATIONS: True,
    }
    row.update(extra)
    return row


def forecast_rows(start: datetime, hours: int = 30, *, temp: float = 2.0, rh: float = 70.0, **extra: Any) -> list[dict[str, Any]]:
    return [
        {"datetime": (start + timedelta(hours=i)).isoformat(), "temperature": temp, "humidity": rh, **extra}
        for i in range(hours)
    ]


def set_weather(hass: HomeAssistant, *, temp: float = 2.0, rh: float = 70.0, forecast: list | None = None, state: str = "cloudy", **attrs: Any) -> None:
    attributes = {"temperature": temp, "humidity": rh, "wind_bearing": 270, "wind_speed": 4.0, **attrs}
    if forecast is not None:
        attributes["forecast"] = forecast
    hass.states.async_set("weather.home", state, attributes)


def set_climate(hass: HomeAssistant, key: str, t: float, h: float) -> None:
    hass.states.async_set(f"sensor.{key}_t", str(t), {"unit_of_measurement": "°C"}, force_update=True)
    hass.states.async_set(f"sensor.{key}_h", str(h), {"unit_of_measurement": "%"}, force_update=True)


@pytest.fixture(autouse=True)
def _isolated_config_dir(hass: HomeAssistant, tmp_path) -> None:
    """Keep diagnostics trace files out of the shared testing config directory."""
    hass.config.config_dir = str(tmp_path)


async def setup(hass: HomeAssistant, rooms: list[dict[str, Any]], *, data: dict | None = None, options: dict | None = None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.home", "rooms": rooms, "levels": ["EG", "OG"], **(data or {})},
        options=dict(options or {}),
        title="FreshAirIQ",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


async def step(hass: HomeAssistant, freezer, coordinator, seconds: float) -> dict[str, Any]:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success, coordinator.last_exception
    return coordinator.data


async def test_full_window_session_lifecycle_records_last_ventilation(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0, forecast=forecast_rows(START))
    set_climate(hass, "bath", 22.0, 75.0)
    hass.states.async_set("binary_sensor.bath_window", "off")
    entry, coordinator = await setup(hass, [room("bath")])

    data = await step(hass, freezer, coordinator, 30)
    bath = data["rooms"]["bath"]
    assert bath["data_quality"] == "ok"
    assert bath["active"] is False
    assert data["future_weather_available"] is True

    hass.states.async_set("binary_sensor.bath_window", "on")
    data = await step(hass, freezer, coordinator, 5)
    assert data["rooms"]["bath"]["active"] is True
    assert coordinator.store.room("bath")["session_active"] is True

    for minute in range(1, 9):
        set_climate(hass, "bath", 22.0 - minute * 0.3, 75.0 - minute * 1.5)
        data = await step(hass, freezer, coordinator, 60)
    assert data["rooms"]["bath"]["active"] is True
    assert data["live_balance_ml"] >= 0

    # A corrupt persisted group event must not break the house finalisation.
    coordinator.store.data["ventilation_group"]["sessions"].append({"event_id": "corrupt", "ended_at": "garbage"})
    hass.states.async_set("binary_sensor.bath_window", "off")
    data = await step(hass, freezer, coordinator, 1)
    # Still logically open during the 3 s close confirmation window.
    assert data["rooms"]["bath"]["active"] is True
    set_climate(hass, "bath", 19.5, 62.0)
    for _ in range(4):
        data = await step(hass, freezer, coordinator, 5)
    assert coordinator.store.room("bath")["session_active"] is False
    assert coordinator.store.data.get("last_ventilation") is not None


async def test_exhaust_fan_session_without_contacts_and_thermostat_target(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass)
    set_climate(hass, "bath", 22.0, 74.0)
    hass.states.async_set("fan.bath", "off")
    hass.states.async_set("climate.bath", "heat", {"temperature": 21.5})
    hass.states.async_set("sensor.bath_co2", "unavailable")
    _entry, coordinator = await setup(
        hass, [room("bath", contacts=[], exhaust_fan="fan.bath", climate="climate.bath", co2="sensor.bath_co2")]
    )
    data = await step(hass, freezer, coordinator, 30)
    mem = coordinator.store.room("bath")
    assert mem["last_plausible_comfort_target_c"] == 21.5
    assert data["rooms"]["bath"]["co2_available"] is False
    assert data["rooms"]["bath"]["configured_actuators"]["mechanical_exhaust_active"] is False

    hass.states.async_set("fan.bath", "on")
    data = await step(hass, freezer, coordinator, 30)
    assert data["rooms"]["bath"]["configured_actuators"]["mechanical_exhaust_active"] is True
    assert mem["session_active"] is True
    assert mem["session_opening_mode"] == "mechanical_exhaust"
    for _ in range(3):
        data = await step(hass, freezer, coordinator, 60)

    hass.states.async_set("fan.bath", "off")
    for _ in range(5):
        data = await step(hass, freezer, coordinator, 5)
    assert mem["session_active"] is False
    assert data["rooms"]["bath"]["active"] is False


async def test_redundant_room_sensors_are_aggregated_and_total_outage_is_reported(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass)
    for sid, value in (("sensor.a_t1", "21.0"), ("sensor.a_t2", "23.0"), ("sensor.a_h1", "60"), ("sensor.a_h2", "64")):
        hass.states.async_set(sid, value)
    hass.states.async_set("sensor.b_t1", "unavailable")
    hass.states.async_set("sensor.b_t2", "unavailable")
    hass.states.async_set("sensor.b_h1", "60")
    hass.states.async_set("sensor.b_h2", "61")
    rooms = [
        room("a", temperature=["sensor.a_t1", "sensor.a_t2"], humidity=["sensor.a_h1", "sensor.a_h2"]),
        room("b", temperature=["sensor.b_t1", "sensor.b_t2"], humidity=["sensor.b_h1", "sensor.b_h2"]),
    ]
    hass.states.async_set("binary_sensor.a_window", "off")
    hass.states.async_set("binary_sensor.b_window", "off")
    _entry, coordinator = await setup(hass, rooms)
    data = await step(hass, freezer, coordinator, 30)
    assert data["rooms"]["a"]["data_quality"] == "ok"
    assert data["rooms"]["a"]["temperature"] == pytest.approx(22.0)
    assert data["rooms"]["a"]["humidity"] == pytest.approx(62.0)
    assert data["rooms"]["b"]["data_quality"] != "ok"
    assert data["system_check"]["stale_or_invalid_rooms"] == 1


async def test_cover_guard_marks_closed_shutters_and_moving_and_unknown_covers(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass)
    set_climate(hass, "liv", 22.0, 70.0)
    hass.states.async_set("binary_sensor.liv_window", "on")
    hass.states.async_set("cover.moving", "closing", {"current_position": 50})
    hass.states.async_set("cover.nopos", "open", {})
    hass.states.async_set("cover.down", "closed", {"current_position": 10})
    covers = {"binary_sensor.liv_window": ["cover.moving", "cover.nopos", "cover.down"]}
    _entry, coordinator = await setup(hass, [room("liv", contact_covers=covers)])
    data = await step(hass, freezer, coordinator, 30)
    guard = data["rooms"]["liv"]["cover_learning_guard"]
    assert guard["blocked"] is True
    assert guard["moving"] is True
    assert guard["unknown"] == ["cover.nopos"]
    assert guard["affected"][0]["cover"] == "cover.down"
    assert guard["affected"][0]["closed_percent"] == 90.0
    assert coordinator.store.room("liv")["session_active"] is True
    assert coordinator.store.room("liv")["session_cover_learning_guard"]["blocked"] is True


async def test_cover_guard_respects_inverse_position_convention(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass)
    set_climate(hass, "liv", 22.0, 70.0)
    hass.states.async_set("binary_sensor.liv_window", "on")
    hass.states.async_set("cover.down", "open", {"current_position": 10})
    covers = {"binary_sensor.liv_window": ["cover.down"]}
    _entry, coordinator = await setup(hass, [room("liv", contact_covers=covers, cover_position_zero_means="open")])
    data = await step(hass, freezer, coordinator, 30)
    guard = data["rooms"]["liv"]["cover_learning_guard"]
    assert guard["zero_means"] == "open"
    assert guard["blocked"] is False


async def test_contact_specific_reference_air_pairs(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    hass.states.async_set("sensor.wg_t", "15.0")
    hass.states.async_set("sensor.wg_h", "80")
    hass.states.async_set("sensor.wg_invalid_h", "150")
    for key in ("full", "half", "bad"):
        set_climate(hass, key, 22.0, 65.0)
        hass.states.async_set(f"binary_sensor.{key}_window", "on")
        hass.states.async_set(f"binary_sensor.{key}_door", "off")
    rooms = [
        room("full", contacts=["binary_sensor.full_window", "binary_sensor.full_door"],
             contact_reference_temperatures={"binary_sensor.full_window": "sensor.wg_t"},
             contact_reference_humidities={"binary_sensor.full_window": "sensor.wg_h"}),
        room("half", contacts=["binary_sensor.half_window", "binary_sensor.half_door"],
             contact_reference_temperatures={"binary_sensor.half_window": "sensor.wg_t"}),
        room("bad", contacts=["binary_sensor.bad_window", "binary_sensor.bad_door"],
             contact_reference_temperatures={"binary_sensor.bad_window": "sensor.wg_t"},
             contact_reference_humidities={"binary_sensor.bad_window": "sensor.wg_invalid_h"}),
    ]
    _entry, coordinator = await setup(hass, rooms)
    data = await step(hass, freezer, coordinator, 30)
    full = data["rooms"]["full"]
    assert full["data_quality"] == "ok"
    assert coordinator.store.room("full")["session_start_source_temp"] == pytest.approx(15.0)
    assert data["rooms"]["half"]["data_quality"] != "ok"
    assert data["rooms"]["bad"]["data_quality"] != "ok"
    assessments = {row["entity_id"]: row for row in full["opening_assessments"]}
    assert assessments["binary_sensor.full_window"]["source_kind"] == "local_reference"
    half = {row["entity_id"]: row for row in data["rooms"]["half"]["opening_assessments"]}
    assert half["binary_sensor.half_window"]["available"] is False


THREE_STATE_ATTRS = {"options": ["closed", "open", "tilted"]}


async def test_three_state_handle_is_debounced_held_while_unavailable_and_quarantined(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "liv", 22.0, 72.0)
    handle = "sensor.liv_handle"
    hass.states.async_set(handle, "closed", THREE_STATE_ATTRS)
    _entry, coordinator = await setup(hass, [room("liv", contacts=[handle])])
    data = await step(hass, freezer, coordinator, 30)
    mem = coordinator.store.room("liv")
    assert data["rooms"]["liv"]["three_state_contacts"] == [handle]
    assert mem["stable_opening_modes"] == {handle: "closed"}

    # Stale entries of removed contacts and a corrupt timestamp are repaired.
    mem["stable_opening_modes"] = {handle: "closed", "sensor.removed": "open"}
    mem["stable_opening_since"] = {handle: "not-a-timestamp", "sensor.removed": START.isoformat()}
    mem["passage_behavior"] = {"sensor.removed": {"samples": 1}}
    data = await step(hass, freezer, coordinator, 30)
    assert set(mem["stable_opening_modes"]) == {handle}
    assert set(mem["stable_opening_since"]) == {handle}
    assert mem["passage_behavior"] == {}

    # A fresh transition is suppressed until it is stable for 3 s.
    hass.states.async_set(handle, "tilted", THREE_STATE_ATTRS)
    data = await step(hass, freezer, coordinator, 1)
    assert data["rooms"]["liv"]["three_state_transition_suppressed"] is True
    assert mem["three_state_transients_suppressed"] >= 1
    assert mem["session_active"] is False
    data = await step(hass, freezer, coordinator, 5)
    assert mem["stable_opening_modes"][handle] == "tilted"
    assert mem["session_active"] is True

    # A contact that disappears from the session passage list during a session
    # quarantines the specialised learning.
    mem["session_passage_contacts"] = [handle, "sensor.removed"]
    data = await step(hass, freezer, coordinator, 30)
    assert mem["session_passage_contacts"] == [handle]
    assert mem["session_learning_quarantine_code"] == "FAIQ-OPENING-3STATE-004"

    # Unavailable: hold the last stable physical state, then mark stale.
    hass.states.async_set(handle, "unavailable", THREE_STATE_ATTRS)
    data = await step(hass, freezer, coordinator, 5)
    assert data["rooms"]["liv"]["three_state_unknown_contacts"] == [handle]
    assert mem["session_active"] is True
    assert mem["session_three_state_unknown_observed"] is True
    data = await step(hass, freezer, coordinator, 60)
    assert data["rooms"]["liv"]["three_state_stale_contacts"] == [handle]
    assert mem["session_learning_quarantine_code"] == "FAIQ-OPENING-3STATE-006"

    hass.states.async_set(handle, "closed", THREE_STATE_ATTRS)
    for _ in range(5):
        data = await step(hass, freezer, coordinator, 5)
    assert mem["session_active"] is False


async def test_contact_mode_all_requires_every_opening_and_delays(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "liv", 22.0, 72.0)
    w1, w2 = "binary_sensor.liv_w1", "binary_sensor.liv_w2"
    hass.states.async_set(w1, "off")
    hass.states.async_set(w2, "off")
    _entry, coordinator = await setup(
        hass, [room("liv", contacts=[w1, w2], contact_mode="all", contact_delays={w1: 60, w2: 0})]
    )
    mem = coordinator.store.room("liv")
    hass.states.async_set(w1, "on")
    data = await step(hass, freezer, coordinator, 30)
    assert data["rooms"]["liv"]["open"] is False
    hass.states.async_set(w2, "on")
    data = await step(hass, freezer, coordinator, 10)
    # Both open, but w1's 60 s start delay is not yet satisfied.
    assert data["rooms"]["liv"]["open"] is True
    assert mem["session_active"] is False
    data = await step(hass, freezer, coordinator, 60)
    assert mem["session_active"] is True
    data = await step(hass, freezer, coordinator, 60)
    hass.states.async_set(w2, "off")
    data = await step(hass, freezer, coordinator, 1)
    assert mem["session_active"] is True
    for _ in range(4):
        data = await step(hass, freezer, coordinator, 5)
    assert mem["session_active"] is False


async def test_contact_left_unknown_beyond_hold_ends_session_without_learning(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "liv", 22.0, 72.0)
    w1, w2 = "binary_sensor.liv_w1", "binary_sensor.liv_w2"
    hass.states.async_set(w1, "on")
    hass.states.async_set(w2, "off")
    _entry, coordinator = await setup(hass, [room("liv", contacts=[w1, w2])])
    mem = coordinator.store.room("liv")
    data = await step(hass, freezer, coordinator, 30)
    assert mem["session_active"] is True
    hass.states.async_set(w1, "unavailable")
    data = await step(hass, freezer, coordinator, 30)
    # Unknown restore state is never a close.
    assert mem["session_active"] is True
    assert data["rooms"]["liv"]["active"] is True
    data = await step(hass, freezer, coordinator, 950)
    assert mem["session_contact_unknown_expired"] is True
    assert mem["session_learning_quarantine_code"] == "FAIQ-CONTACT-UNKNOWN-001"
    for _ in range(4):
        data = await step(hass, freezer, coordinator, 5)
    assert mem["session_active"] is False


async def test_removed_contact_entity_expires_after_hold(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "liv", 22.0, 72.0)
    w1 = "binary_sensor.liv_w1"
    hass.states.async_set(w1, "on")
    _entry, coordinator = await setup(hass, [room("liv", contacts=[w1])])
    mem = coordinator.store.room("liv")
    data = await step(hass, freezer, coordinator, 30)
    assert mem["session_active"] is True
    hass.states.async_remove(w1)
    data = await step(hass, freezer, coordinator, 30)
    assert mem["session_active"] is True
    data = await step(hass, freezer, coordinator, 950)
    assert mem["session_contact_unknown_expired"] is True
    # The vanished contact can never confirm a close: the room stays undecided.
    assert data["rooms"]["liv"]["open"] is False


async def test_unknown_three_state_contact_without_stable_state_blocks_close_detection(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "liv", 22.0, 72.0)
    w1, handle = "binary_sensor.liv_w1", "sensor.liv_handle"
    hass.states.async_set(w1, "on")
    hass.states.async_set(handle, "unavailable", THREE_STATE_ATTRS)
    _entry, coordinator = await setup(hass, [room("liv", contacts=[w1, handle])])
    mem = coordinator.store.room("liv")
    mem["three_state_contacts"] = [handle]
    data = await step(hass, freezer, coordinator, 30)
    assert mem["session_active"] is True
    hass.states.async_set(w1, "off")
    data = await step(hass, freezer, coordinator, 950)
    assert mem["session_contact_unknown_expired"] is True
    assert data["rooms"]["liv"]["three_state_contacts"] == [handle]


async def test_three_state_handle_removed_while_open_keeps_session_and_repairs_timestamps(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "liv", 22.0, 72.0)
    handle = "sensor.liv_handle"
    hass.states.async_set(handle, "open", THREE_STATE_ATTRS)
    _entry, coordinator = await setup(hass, [room("liv", contacts=[handle])])
    mem = coordinator.store.room("liv")
    data = await step(hass, freezer, coordinator, 30)
    assert mem["session_active"] is True
    # Corrupt persisted timestamp + fresh transition: the suppressed candidate
    # gets a conservative "now" timestamp.
    mem["stable_opening_since"] = {handle: "garbage"}
    hass.states.async_set(handle, "tilted", THREE_STATE_ATTRS)
    data = await step(hass, freezer, coordinator, 1)
    assert data["rooms"]["liv"]["three_state_transition_suppressed"] is True
    assert datetime.fromisoformat(mem["stable_opening_since"][handle]) == dt_util.utcnow()
    # Unknown while the stored timestamp is corrupt: HA's last_changed is used.
    hass.states.async_set(handle, "unavailable", THREE_STATE_ATTRS)
    mem["stable_opening_since"] = {handle: "garbage"}
    data = await step(hass, freezer, coordinator, 5)
    assert mem["session_active"] is True
    assert data["rooms"]["liv"]["three_state_unknown_contacts"] == [handle]
    # Entity vanishes completely: held state stays, age unknown => stale.
    hass.states.async_remove(handle)
    data = await step(hass, freezer, coordinator, 5)
    assert data["rooms"]["liv"]["three_state_stale_contacts"] == [handle]
    assert mem["session_active"] is True


def _result(**overrides: Any):
    from types import SimpleNamespace

    base = dict(
        data_quality="ok", humidity=55.0, surface_rh=60.0, active=False, close_recommended=False,
        delta_g_m3=1.0, ventilation_candidate=False, cooling_candidate=False, potential_ml=0.0,
        moisture_effect_next_5_min_ml=12.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _rec(result, options=None, **kw):
    from custom_components.freshairiq.coordinator import _recommendation

    args = dict(pollen=0.0, co2=None, airflow=1.0, wind_bearing=None, wind_speed=None)
    args.update(kw)
    return _recommendation(result, dict(options or {}), **args)


def test_recommendation_room_triggers_and_actions() -> None:
    action, text, reasons = _rec(_result(data_quality="missing"))
    assert action == "Check sensor"

    action, text, reasons = _rec(_result(humidity=70.0, surface_rh=85.0), co2=1500.0)
    assert action == "Wait"
    assert any("CO₂ 1500 ppm ist kritisch" in r for r in reasons)
    assert any("Oberflächenfeuchte" in r for r in reasons)
    action, _t, reasons = _rec(_result(humidity=63.0), co2=1100.0)
    assert any("Warnschwelle" in r for r in reasons)
    assert any("Lüftungsstartwert" in r for r in reasons)

    action, _t, reasons = _rec(_result(humidity=70.0, delta_g_m3=-0.2))
    assert action == "Do not ventilate"
    assert "gleich feucht oder feuchter" in reasons[-1]
    assert _rec(_result(delta_g_m3=-1.0))[0] == "Do not ventilate"
    assert _rec(_result(potential_ml=40.0))[0] == "Wait"
    assert _rec(_result())[0] == "Okay"

    action, _t, reasons = _rec(_result(cooling_candidate=True), wind_bearing=90.0, wind_speed=None, airflow=1.0)
    assert action == "Ventilate for cooling"
    assert "Wind" not in reasons[-1]
    action, _t, reasons = _rec(_result(cooling_candidate=True), wind_bearing=90.0, wind_speed=3.0, airflow=1.0)
    assert reasons[-1] == "Wind hat aktuell nur geringen Einfluss"


def test_recommendation_ventilate_latch_profile_and_wind() -> None:
    result = _result(humidity=63.0, ventilation_candidate=True, delta_g_m3=2.0, potential_ml=100.0)
    action, _t, reasons = _rec(result, {"operating_profile": "dehumidify"}, ventilation_latched=True,
                               wind_bearing=270.0, airflow=1.2)
    assert action == "Ventilate"
    # Dehumidify profile lowers the required delta to 85 %.
    assert any("mindestens 2.1 g/m³" in r for r in reasons)
    assert any("Empfehlung bleibt trotz leichter Schwankung" in r for r in reasons)
    assert reasons[-1] == "Windrichtung unterstützt den Luftwechsel"
    action, _t, reasons = _rec(_result(humidity=70.0, ventilation_candidate=True, delta_g_m3=2.0),
                               ventilation_latched=True, wind_bearing=90.0, airflow=0.8)
    assert not any("Schwankung" in r for r in reasons)
    assert reasons[-1] == "Windrichtung bremst den Luftwechsel"


def test_recommendation_outdoor_air_vetoes() -> None:
    options = {"pollen_enabled": True, "pollen_max": 3, "outdoor_pm25_enabled": True, "outdoor_pm25_max": 25}
    action, _t, reasons = _rec(_result(ventilation_candidate=True, humidity=70.0, delta_g_m3=3.0), options,
                               pollen=4.0, outdoor_pm25=80.0)
    assert action == "Do not ventilate"
    assert any("Pollenindex 4.0" in r for r in reasons)
    assert len(reasons) >= 3  # trigger + pollen + fine-dust explanation
    # Urgent room conditions override the outdoor veto.
    assert _rec(_result(ventilation_candidate=True, surface_rh=95.0, delta_g_m3=3.0), options, pollen=4.0)[0] == "Ventilate"


def test_recommendation_active_session_branches() -> None:
    src = dict(active=True, moisture_source_active=True, moisture_source_label="Dusche",
               moisture_source_confidence=80, moisture_source_rate_ml_min=5.0, delta_g_m3=2.0)
    action, _t, reasons = _rec(_result(**src))
    assert action == "Continue ventilating"
    assert any("Dusche wahrscheinlich aktiv (80 % Sicherheit)" in r and "300 ml/h" in r for r in reasons)
    assert "aktiven Feuchtequelle" in reasons[-1]

    action, _t, reasons = _rec(_result(active=True, close_recommended=True))
    assert (action, reasons[-1]) == ("Close", "Lüftungsziel erreicht oder zusätzlicher Nutzen ist zu gering")
    _a, _t, reasons = _rec(_result(active=True, close_recommended=True, close_decision_model_fallback=True))
    assert "ersatzweise" in reasons[-1]
    _a, _t, reasons = _rec(_result(active=True, close_recommended=True, close_decision_model_fallback=True,
                                   future_moisture_risk_15=True))
    assert "Wetterprognose" in reasons[-1]

    action, _t, reasons = _rec(_result(active=True, close_decision_ready=False, fresh_measurements=1))
    assert (action, reasons[-1]) == ("Continue ventilating", "Schließentscheidung wartet auf neue Klimamessungen (1/2)")
    _a, _t, reasons = _rec(_result(active=True, close_decision_model_fallback=True))
    assert "sinnvollen Lüftungsvorteil" in reasons[-1]
    _a, _t, reasons = _rec(_result(active=True, moisture_effect_next_5_min_ml=33.4))
    assert reasons[-1] == "Kurzfristiger Schließcheck (5 min): voraussichtlich 33 ml Feuchteabbau"


NOON = datetime(2026, 1, 14, 20, 0, 0, tzinfo=dt_util.UTC)  # 12:00 in the HA test time zone (US/Pacific)


async def test_night_moisture_learning_snapshots_and_reset_outside_night(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)  # 02:00 local, inside the default 22:00-07:00 night
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "bed", 19.0, 55.0)
    hass.states.async_set("binary_sensor.bed_window", "off")
    _entry, coordinator = await setup(hass, [room("bed")], options={"night_start_hour": "22", "night_end_hour": "07:00"})
    store = coordinator.store.data
    await step(hass, freezer, coordinator, 30)
    assert store["night_last_snapshot"] is not None
    first_water = store["night_last_water_ml"]
    set_climate(hass, "bed", 19.0, 60.0)
    await step(hass, freezer, coordinator, 30 * 60)
    assert store["night_model_samples"] == 1
    assert len(store["night_observed_dates"]) == 1
    assert store["night_last_water_ml"] > first_water
    # A gap longer than 1.5 h only re-anchors the snapshot.
    await step(hass, freezer, coordinator, 2 * 3600)
    assert store["night_model_samples"] == 1
    store["night_observed_dates"] = "corrupt"
    store["night_last_snapshot"] = (dt_util.now() - timedelta(minutes=20)).isoformat()
    await step(hass, freezer, coordinator, 30)
    assert store["night_model_samples"] == 2
    assert isinstance(store["night_observed_dates"], list) and len(store["night_observed_dates"]) == 1
    store["night_last_snapshot"] = "broken"
    await step(hass, freezer, coordinator, 30)
    assert datetime.fromisoformat(store["night_last_snapshot"]) == dt_util.now()
    freezer.move_to(NOON)
    await step(hass, freezer, coordinator, 1)
    assert store["night_last_snapshot"] is None
    assert store["night_last_water_ml"] is None


@pytest.mark.parametrize("night_start", ["abc", "21:30"])
async def test_night_room_selection_and_pre_ventilation_effect(hass: HomeAssistant, freezer, night_start: str) -> None:
    freezer.move_to(NOON)
    set_weather(hass, temp=4.0, rh=60.0, forecast=forecast_rows(NOON, 30, temp=3.0, rh=65.0))
    for key, (t, h) in {"liv": (21.0, 70.0), "bed": (20.0, 72.0), "dry": (21.0, 30.0)}.items():
        set_climate(hass, key, t, h)
        hass.states.async_set(f"binary_sensor.{key}_window", "off")
    set_climate(hass, "hall", 21.0, 70.0)
    rooms = [room("liv"), room("bed"), room("dry"), room("hall", contacts=[])]
    _entry, coordinator = await setup(hass, rooms, options={"night_start_hour": night_start})
    data = await step(hass, freezer, coordinator, 30)
    strategy = data["night_strategy"]
    assert set(strategy["selected_rooms"]) == {"Liv", "Bed"}
    assert strategy["average_temperature_c"] == 3.0


async def test_warm_humid_night_closes_windows_and_warm_night_has_no_reheat_cost(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    # Night air warmer than the room but still drier in absolute terms.
    set_weather(hass, temp=24.0, rh=40.0, forecast=forecast_rows(START, 12, temp=24.0, rh=40.0))
    set_climate(hass, "bed", 20.0, 90.0)
    hass.states.async_set("binary_sensor.bed_window", "off")
    _entry, coordinator = await setup(hass, [room("bed")])
    data = await step(hass, freezer, coordinator, 30)
    assert data["night_strategy"]["projected_reheat_cost"] == 0.0
    assert data["night_strategy"]["selected_rooms"] == ["Bed"]

    set_weather(hass, temp=15.0, rh=95.0, forecast=forecast_rows(START, 12, temp=15.0, rh=95.0))
    set_climate(hass, "bed", 20.0, 50.0)
    coordinator._hourly_forecast_fetched_at = None
    data = await step(hass, freezer, coordinator, 30)
    assert data["night_strategy"]["action"] == "close"
    assert data["night_recommendation"] == data["night_strategy"]["instruction"]


async def test_monitor_only_room_and_legacy_contact_and_orientation(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "wg", 12.0, 80.0)
    set_climate(hass, "liv", 22.0, 70.0)
    hass.states.async_set("sensor.wg_voc", "120")
    hass.states.async_set("sensor.wg_pm25", "8")
    hass.states.async_set("sensor.wg_lux", "300")
    hass.states.async_set("sensor.liv_voc", "200")
    hass.states.async_set("binary_sensor.liv_window", "on")
    liv = room("liv", contact_orientations={"binary_sensor.liv_window": "w"})
    rooms = [
        room("wg", contacts=[], include_in_calculations=False, voc="sensor.wg_voc", pm25="sensor.wg_pm25", illuminance="sensor.wg_lux"),
        room("ghost", contacts=[], include_in_calculations=False, temperature=None, humidity=None),
        room("gone", contacts=[], include_in_calculations=False, temperature="sensor.gone_t", humidity="sensor.gone_h"),
        dict(liv, voc="sensor.liv_voc"),
    ]
    _entry, coordinator = await setup(hass, rooms)
    data = await step(hass, freezer, coordinator, 30)
    wg = data["rooms"]["wg"]
    assert wg["monitor_only"] is True
    assert wg["data_quality"] == "monitor_only"
    assert wg["temperature"] == 12.0
    assert wg["voc"] == 120.0 and wg["pm25"] == 8.0 and wg["illuminance"] == 300.0
    assert wg["last_measurement_at"] is not None
    assert data["rooms"]["ghost"]["data_quality"] == "not_configured"
    assert data["rooms"]["gone"]["data_quality"] == "missing"
    assert data["rooms"]["gone"]["reason"] == "Configured climate sensors are currently unavailable"
    assert data["rooms"]["liv"]["airflow_factor"] > 1.12
    # Optional VOC sensors are tracked sources: a report schedules a coalesced refresh.
    assert coordinator._refresh_coalesce_unsub is None
    hass.states.async_set("sensor.liv_voc", "250")
    assert coordinator._refresh_coalesce_unsub is not None
    groups = dict(coordinator._required_source_groups())
    assert "room:wg:temperature" not in groups and "room:liv:temperature" in groups


def test_legacy_single_contact_key_is_used() -> None:
    from custom_components.freshairiq.coordinator import _contact_ids

    assert _contact_ids({"contacts": "binary_sensor.x"}) == ["binary_sensor.x"]
    assert _contact_ids({"contact": "binary_sensor.legacy"}) == ["binary_sensor.legacy"]
    assert _contact_ids({}) == []


async def test_pre_ventilation_skips_rooms_drier_than_current_outdoor_air(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(NOON)
    set_weather(hass, temp=10.0, rh=95.0, forecast=forecast_rows(NOON, 30, temp=3.0, rh=65.0))
    set_climate(hass, "liv", 21.0, 45.0)
    hass.states.async_set("binary_sensor.liv_window", "off")
    _entry, coordinator = await setup(hass, [room("liv")])
    data = await step(hass, freezer, coordinator, 30)
    assert data["night_strategy"]["selected_rooms"] == ["Liv"]
    # Current outdoor air is wetter than the room: no pre-ventilation benefit.
    assert data["night_strategy"]["strategy_moisture_effect_ml"] in (None, 0)


async def _simple(hass: HomeAssistant, freezer, *, options: dict | None = None):
    freezer.move_to(NOON)
    set_weather(hass)
    set_climate(hass, "liv", 21.0, 55.0)
    hass.states.async_set("binary_sensor.liv_window", "off")
    return await setup(hass, [room("liv")], options=options)


async def test_update_failures_are_wrapped_and_previous_data_retained(hass: HomeAssistant, freezer, monkeypatch) -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed

    _entry, coordinator = await _simple(hass, freezer)
    await step(hass, freezer, coordinator, 30)
    previous = coordinator.data

    async def boom() -> dict:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(coordinator, "_async_update_data_impl", boom)
    with pytest.raises(UpdateFailed, match="RuntimeError"):
        await coordinator._async_update_data()
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.data is previous
    assert coordinator.robustness.snapshot()["consecutive_failures"] >= 1

    async def explicit() -> dict:
        raise UpdateFailed("explicit")

    monkeypatch.setattr(coordinator, "_async_update_data_impl", explicit)
    with pytest.raises(UpdateFailed, match="explicit"):
        await coordinator._async_update_data()


async def test_update_survives_metric_repair_and_translation_failures(hass: HomeAssistant, freezer, monkeypatch) -> None:
    import custom_components.freshairiq.coordinator as coord_mod

    _entry, coordinator = await _simple(hass, freezer)

    original_metric = coordinator.runtime_health.observe_metric

    def bad_metric(name, *a, **k):
        if name == "coordinator_update_ms":
            raise TypeError("metric")
        return original_metric(name, *a, **k)

    def bad_repairs(*_a, **_k):
        raise RuntimeError("repairs")

    class BadTranslator:
        def __init__(self, *_a):
            raise RuntimeError("translator")

    monkeypatch.setattr(coordinator.runtime_health, "observe_metric", bad_metric)
    monkeypatch.setattr(coord_mod, "async_sync_missing_entity_issue", bad_repairs)
    monkeypatch.setattr(coord_mod, "Translator", BadTranslator)
    coordinator._output_translator = None
    data = await step(hass, freezer, coordinator, 30)
    assert "output_language" not in data  # German texts published unchanged
    assert data["rooms"]["liv"]["data_quality"] == "ok"


async def test_german_server_publishes_german_texts(hass: HomeAssistant, freezer) -> None:
    hass.config.language = "de"
    _entry, coordinator = await _simple(hass, freezer)
    data = await step(hass, freezer, coordinator, 30)
    assert data["output_language"] == "de"
    hass.config.language = "en"
    data = await step(hass, freezer, coordinator, 30)
    assert data["output_language"] == "en"


async def test_automation_event_failures_are_swallowed(hass: HomeAssistant, freezer, monkeypatch) -> None:
    _entry, coordinator = await _simple(hass, freezer)

    def boom(_data):
        raise RuntimeError("consumer")

    monkeypatch.setattr(coordinator.automation_events, "process", boom)
    data = await step(hass, freezer, coordinator, 30)
    assert data["rooms"]["liv"]["data_quality"] == "ok"
    coordinator.data = None
    coordinator._async_fire_automation_events()  # non-dict data is ignored


async def test_presence_entities_are_tracked_and_listeners_rebuilt(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set("person.anna", "home")
    _entry, coordinator = await _simple(hass, freezer, options={"adult_presence_entities": ["person.anna"]})
    await step(hass, freezer, coordinator, 30)
    assert coordinator.robustness.listener_sources >= 5
    coordinator._hourly_forecast_cache = [{"stale": True}]
    # Pending contact confirmation + coalesced refresh are cancelled on rebuild.
    hass.states.async_set("binary_sensor.liv_window", "on")
    hass.states.async_set("binary_sensor.liv_window", "off")
    assert "binary_sensor.liv_window" in coordinator._contact_confirm_unsubs
    assert coordinator._refresh_coalesce_unsub is not None
    await coordinator.async_rebuild_listeners(invalidate_weather_cache=True)
    assert coordinator._contact_confirm_unsubs == {}
    assert coordinator._refresh_coalesce_unsub is None
    assert coordinator._hourly_forecast_cache == []
    assert coordinator._hourly_forecast_fetched_at is None
    hass.states.async_set("person.anna", "not_home")
    assert coordinator._refresh_coalesce_unsub is not None
    await hass.async_block_till_done()


async def test_final_measurement_helpers(hass: HomeAssistant, freezer, monkeypatch) -> None:
    _entry, coordinator = await _simple(hass, freezer)
    calls = []

    async def record(call):
        calls.append(call.data)

    hass.services.async_register("homeassistant", "update_entity", record)
    # No known entities -> no service call at all.
    hass.states.async_remove("weather.home")
    await coordinator._async_request_room_sensor_refresh({"key": "x"})
    assert calls == []
    hass.states.async_set("sensor.ref_t", "3")
    await coordinator._async_request_room_sensor_refresh({"key": "x"}, active_reference_temperature="sensor.ref_t")
    await hass.async_block_till_done()
    assert calls and list(calls[0]["entity_id"]) == ["sensor.ref_t"]
    mem = {"session_close_pending": True, "session_close_deadline_at": "kept"}
    coordinator._begin_final_measurement_wait(
        mem, {"key": "liv"}, now=dt_util.now(), physical_closed_at=dt_util.now(),
        temperature_state=None, humidity_state=None,
        active_reference_temperature=None, active_reference_humidity=None,
    )
    assert mem["session_close_deadline_at"] == "kept"
    assert "liv" not in coordinator._final_measurement_unsubs


async def _open_session(hass, freezer, rooms_keys=("liv",), *, outdoor=(2.0, 70.0), climate=(22.0, 72.0), options=None, extra_rooms=()):
    freezer.move_to(NOON)
    set_weather(hass, temp=outdoor[0], rh=outdoor[1])
    for key in rooms_keys:
        set_climate(hass, key, *climate)
        hass.states.async_set(f"binary_sensor.{key}_window", "off")
    entry, coordinator = await setup(hass, [room(k) for k in rooms_keys] + list(extra_rooms), options=options)
    await step(hass, freezer, coordinator, 30)
    for key in rooms_keys:
        hass.states.async_set(f"binary_sensor.{key}_window", "on")
    await step(hass, freezer, coordinator, 5)
    for key in rooms_keys:
        assert coordinator.store.room(key)["session_active"] is True
    return entry, coordinator


async def test_restart_rebuilds_house_group_from_persisted_sessions(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(NOON)
    set_weather(hass)
    handle = "sensor.liv_handle"
    hass.states.async_set(handle, "open", THREE_STATE_ATTRS)
    hass.states.async_set("sensor.kit_handle", "open", THREE_STATE_ATTRS)
    set_climate(hass, "liv", 22.0, 72.0)
    set_climate(hass, "kit", 22.0, 72.0)
    _entry, coordinator = await setup(hass, [room("liv", contacts=[handle]), room("kit", contacts=["sensor.kit_handle"])])
    store = coordinator.store
    earliest = dt_util.utcnow() - timedelta(minutes=20)
    liv = store.room("liv")
    liv.update(session_active=True, session_started=(dt_util.utcnow() - timedelta(minutes=5)).isoformat(),
               three_state_contacts=[handle], stable_opening_modes={handle: "open"},
               stable_opening_since={handle: earliest.isoformat()})
    kit = store.room("kit")
    kit.update(session_active=True, session_started="garbage", three_state_contacts=["sensor.kit_handle"],
               stable_opening_modes={"sensor.kit_handle": "open"}, stable_opening_since={"sensor.kit_handle": "garbage"})
    store.data["ventilation_group"] = None
    await coordinator.async_refresh()
    group = store.data["ventilation_group"]
    assert group["active"] is True
    assert datetime.fromisoformat(group["started_at"]) == earliest


async def test_session_completed_without_house_group_creates_one_and_ignores_bad_stamps(hass: HomeAssistant, freezer) -> None:
    _entry, coordinator = await _open_session(hass, freezer)
    store = coordinator.store
    for _ in range(3):
        set_climate(hass, "liv", 21.0, 66.0)
        await step(hass, freezer, coordinator, 60)
    mem = store.room("liv")
    hass.states.async_set("binary_sensor.liv_window", "off")
    await step(hass, freezer, coordinator, 1)
    store.data["ventilation_group"] = {"active": False, "sessions": []}
    mem["session_started"] = "garbage"
    set_climate(hass, "liv", 20.5, 64.0)
    await step(hass, freezer, coordinator, 5)
    assert store.data["ventilation_group"] is None
    assert mem["session_active"] is False
    assert store.data["ventilation_log"]


async def test_finalisation_with_vanished_sensor_and_corrupt_deadline(hass: HomeAssistant, freezer) -> None:
    _entry, coordinator = await _open_session(hass, freezer)
    mem = coordinator.store.room("liv")
    await step(hass, freezer, coordinator, 120)
    hass.states.async_set("binary_sensor.liv_window", "off")
    hass.states.async_remove("sensor.liv_h")
    data = await step(hass, freezer, coordinator, 4)
    assert data["finalizing_measurements"]["active"] is True
    assert data["finalizing_measurements"]["humidity_feedback_count"] == 0
    assert mem["session_close_humidity_baseline"] is None  # vanished sensor has no report timestamp
    # A corrupt deadline can never extend the wait: the session is finalised at once.
    mem["session_close_deadline_at"] = "garbage"
    data = await step(hass, freezer, coordinator, 2)
    assert mem["session_active"] is False
    assert data["finalizing_measurements"]["active"] is False
    # A stale pending flag on an idle room is reported but its corrupt deadline ignored.
    mem["session_close_pending"] = True
    mem["session_close_deadline_at"] = "garbage"
    data = await step(hass, freezer, coordinator, 2)
    assert data["finalizing_measurements"]["active"] is True
    assert data["finalizing_measurements"]["wait_remaining_s"] == 0.0


async def test_passive_ventilation_of_linked_closed_room_is_observed_and_learned(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(NOON)
    set_weather(hass, temp=0.0, rh=60.0)
    for key in ("liv", "kit"):
        set_climate(hass, key, 22.0, 70.0)
        hass.states.async_set(f"binary_sensor.{key}_window", "off")
    set_climate(hass, "hall", 22.0, 70.0)
    set_climate(hass, "store", 22.0, 70.0)
    rooms = [room("liv"), room("kit"), room("hall", contacts=[]), room("store", contacts=[], floor="OG")]
    _entry, coordinator = await setup(hass, rooms, options={"cross_zone_connections": "hall+liv, store+liv,broken"})
    await step(hass, freezer, coordinator, 30)
    hass.states.async_set("binary_sensor.liv_window", "on")
    hass.states.async_set("binary_sensor.kit_window", "on")
    data = await step(hass, freezer, coordinator, 5)
    hall = coordinator.store.room("hall")
    assert hall["passive_group_id"] == coordinator.store.data["ventilation_group"]["started_at"]
    assert coordinator.store.room("store")["passive_samples"][0]["elapsed_min"] == 0.0
    coordinator.store.room("store")["passive_observation_started_at"] = "garbage"
    for minute in range(1, 13):
        set_climate(hass, "liv", 22.0 - minute * 0.2, 70.0 - minute * 2.0)
        set_climate(hass, "kit", 22.0 - minute * 0.2, 70.0 - minute * 2.0)
        set_climate(hass, "hall", 22.0 - minute * 0.1, 70.0 - minute * 1.5)
        data = await step(hass, freezer, coordinator, 60)
    room_hall = data["rooms"]["hall"]
    assert room_hall["passive_ventilation_elapsed_min"] >= 11.0
    assert room_hall["passive_ventilation_estimated"] is True
    assert len(hall["passive_samples"]) > 1
    assert hall.get("passive_learning_samples", 0) >= 1
    assert hall["passive_learning_last_group_id"] == hall["passive_group_id"]
    hass.states.async_set("binary_sensor.liv_window", "off")
    hass.states.async_set("binary_sensor.kit_window", "off")
    for _ in range(5):
        data = await step(hass, freezer, coordinator, 5)
    assert hall["passive_group_id"] is None
    assert data["rooms"]["hall"]["passive_ventilation_active"] is False


async def test_second_room_joins_running_house_group_and_wet_air_triggers_close(hass: HomeAssistant, freezer) -> None:
    _entry, coordinator = await _open_session(hass, freezer, outdoor=(18.0, 95.0), climate=(20.0, 50.0), extra_rooms=[room("kit")])
    set_climate(hass, "kit", 20.0, 50.0)
    group = coordinator.store.data["ventilation_group"]
    # Kitchen window was physically opened before the running group began.
    hass.states.async_set("binary_sensor.kit_window", "on")
    group["started_at"] = (dt_util.utcnow() + timedelta(minutes=5)).isoformat()
    data = await step(hass, freezer, coordinator, 30)
    assert coordinator.store.room("kit")["session_active"] is True
    assert datetime.fromisoformat(coordinator.store.data["ventilation_group"]["started_at"]) <= dt_util.utcnow()
    for minute in range(4):
        set_climate(hass, "liv", 20.0, 52.0 + minute)
        set_climate(hass, "kit", 20.0, 52.0 + minute)
        data = await step(hass, freezer, coordinator, 60)
    assert data["intelligent_recommendation"]["kind"] == "close"
    assert data["remaining_duration_min"] <= 0.0


async def test_mature_routine_and_house_strategy_layers_refine_outputs(hass: HomeAssistant, freezer, monkeypatch) -> None:
    import custom_components.freshairiq.coordinator as coord_mod

    fit = {"signature": "s", "maturity": 60.0, "efficiency_factor": 1.25}
    monkeypatch.setattr(coord_mod, "house_strategy_fit", lambda *a, **k: dict(fit))
    monkeypatch.setattr(coord_mod, "project_generation_ml", lambda valid, now, minutes: (5000.0, 40.0))
    seen: list[list[str]] = []
    original = coord_mod.stabilise_recommendation

    def spy(rec, *a, **k):
        seen.append(list(rec.get("reasons") or []))
        return original(rec, *a, **k)

    monkeypatch.setattr(coord_mod, "stabilise_recommendation", spy)
    freezer.move_to(START)
    set_weather(hass)
    set_climate(hass, "bed", 19.0, 55.0)
    hass.states.async_set("binary_sensor.bed_window", "off")
    _entry, coordinator = await setup(hass, [room("bed")])
    seen.clear()
    data = await step(hass, freezer, coordinator, 30)
    assert data["routine_night_maturity"] == 40
    assert data["overnight_routine_projection_ml"] == 5000
    assert data["overnight_routine_adjustment_ml"] > 0
    assert any("überdurchschnittlich effizient" in r for r in seen[-1])
    fit["efficiency_factor"] = 0.8
    data = await step(hass, freezer, coordinator, 30)
    assert any("unterdurchschnittlich effizient" in r for r in seen[-1])
    fit["efficiency_factor"] = 1.0
    data = await step(hass, freezer, coordinator, 30)
    assert not any("Hauslernen" in r for r in seen[-1])
    assert data["intelligent_recommendation"]["house_strategy"]["maturity"] == 60.0
