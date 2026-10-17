"""0.26.5.1 (community: summer cooling with blinds and night airing).

* ``binary_sensor.<room>_shading`` ("Sun protection recommended") lists the
  covers whose opening gets direct sun while the room is warm in the
  "summer cooling" profile; a cover leaves the list once the sun is gone.
* The real blueprint "covers against the sun" (DE/EN) closes newly listed covers
  and opens the ones the sun has left (optionally not after sunset).
* Night cooling: the room reasons explain why an airing continues or closes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq import coordinator as coordinator_module
from custom_components.freshairiq.const import (
    CONF_CONTACT_COVERS,
    CONF_CONTACT_ORIENTATIONS,
    CONF_ROOM_COVERS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from custom_components.freshairiq.model import RoomInput, evaluate_room
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints" / "automation" / "freshairiq"
SENSOR = "binary_sensor.wohnzimmer_sonnenschutz"
WINDOW = "binary_sensor.wohnzimmer_window"


# --------------------------------------------------------------------------- entity
def _shading_entity(hass, room_key: str = "wohnzimmer"):
    registry = er.async_get(hass)
    return next(e for e in registry.entities.values()
                if e.platform == DOMAIN and e.unique_id.endswith(f"{room_key}_shading"))


BERLIN_NOON = datetime(2026, 7, 15, 11, 20, tzinfo=timezone.utc)      # sun in the south, 59°
BERLIN_EVENING = datetime(2026, 7, 15, 17, 30, tzinfo=timezone.utc)   # sun in the west-north-west


async def _locate(hass, freezer, when: datetime) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.latitude, hass.config.longitude = 52.52, 13.405
    freezer.move_to(when)


def _sun(hass, azimuth: float, elevation: float) -> None:
    hass.states.async_set("sun.sun", "above_horizon" if elevation > 0 else "below_horizon",
                          {"azimuth": azimuth, "elevation": elevation})


async def test_shading_sensor_follows_the_sun_on_the_window(hass, freezer) -> None:
    room = {**_room(), CONF_CONTACT_COVERS: {WINDOW: ["cover.wohnzimmer_sued"]}, CONF_CONTACT_ORIENTATIONS: {WINDOW: "s"}}
    plain = _room("kueche", "Küche")
    _set_sources(hass, "wohnzimmer", "kueche")
    hass.states.async_set("sensor.wohnzimmer_temperature", "27", {"unit_of_measurement": "°C"})
    await _locate(hass, freezer, BERLIN_NOON)
    entry = await _setup(hass, _entry(rooms=[room, plain], options={**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}))
    assert _shading_entity(hass, "kueche").disabled_by is er.RegistryEntryDisabler.INTEGRATION
    entity = _shading_entity(hass)
    assert entity.disabled_by is None
    state = hass.states.get(entity.entity_id)
    assert state.state == "on"
    assert state.attributes["covers_to_close"] == ["cover.wohnzimmer_sued"]
    assert state.attributes["sunlit_covers"] == ["cover.wohnzimmer_sued"]
    assert state.attributes["sun_tracking"] is True
    coordinator = entry.runtime_data
    shade = [i for i in coordinator.data["rooms"]["wohnzimmer"]["interventions"] if i["key"] == "shade"]
    assert [i["entity_id"] for i in shade] == ["cover.wohnzimmer_sued"]

    # the room cooled down: the cover stays in the list while the sun is on the window
    hass.states.async_set("sensor.wohnzimmer_temperature", "22", {"unit_of_measurement": "°C"})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state == "on"

    # afternoon: the sun has left the south window
    hass.states.async_set("sensor.wohnzimmer_temperature", "27", {"unit_of_measurement": "°C"})
    freezer.move_to(BERLIN_EVENING)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity.entity_id)
    assert state.state == "off"
    assert state.attributes["covers_to_close"] == [] and state.attributes["shaded_side_covers"] == ["cover.wohnzimmer_sued"]
    assert not [i for i in coordinator.data["rooms"]["wohnzimmer"]["interventions"] if i["key"] == "shade"]
    await _unload(hass, entry)


async def test_legacy_room_covers_without_location(hass) -> None:
    # no location and no sun.sun: warmth and brightness decide (cover without direction)
    room = {**_room(), CONF_ROOM_COVERS: ["cover.alt"]}
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set("sensor.wohnzimmer_temperature", "27", {"unit_of_measurement": "°C"})
    hass.config.latitude = None
    entry = await _setup(hass, _entry(rooms=[room], options={**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}))
    state = hass.states.get(_shading_entity(hass).entity_id)
    assert state.state == "on"
    assert state.attributes["covers_to_close"] == ["cover.alt"] and state.attributes["sun_tracking"] is False
    # without a location the sun.sun position is used
    _sun(hass, 180.0, 50.0)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(_shading_entity(hass).entity_id).attributes["sun_tracking"] is True
    await _unload(hass, entry)


async def test_covers_close_ahead_of_the_sun_on_a_hot_day(hass, freezer) -> None:
    """Cool room in the morning, hot forecast: the east cover closes before the sun."""
    room = {**_room(), CONF_CONTACT_COVERS: {WINDOW: ["cover.ost"]}, CONF_CONTACT_ORIENTATIONS: {WINDOW: "e"}}
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set("sensor.wohnzimmer_temperature", "21", {"unit_of_measurement": "°C"})
    # 03:20 UTC: sun 1.4° high – not yet on the east window; 30 min later 5° high
    start = datetime(2026, 7, 15, 3, 20, tzinfo=timezone.utc)
    await _locate(hass, freezer, start)
    entry = await _setup(hass, _entry(rooms=[room], options={**DEFAULT_OPTIONS, "operating_profile": "summer_cooling", "shade_lead_min": 30}))
    coordinator = entry.runtime_data
    entity_id = _shading_entity(hass).entity_id
    state = hass.states.get(entity_id)
    assert state.state == "off"  # cool room, no hot forecast
    assert state.attributes["sun_soon_covers"] == ["cover.ost"] and state.attributes["sunlit_covers"] == []

    coordinator._hourly_forecast_cache = [{"datetime": start + timedelta(hours=9), "temperature_c": 31.0}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
    await _unload(hass, entry)


async def test_shading_context_reads_forecast_comfort_target_and_clouds(hass, freezer) -> None:
    _set_sources(hass, "wohnzimmer")
    await _locate(hass, freezer, BERLIN_NOON)
    hass.states.async_set("weather.home", "sunny", {"cloud_coverage": 90})
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    with patch.object(coordinator, "entry", SimpleNamespace(data={"outdoor_weather": "weather.home"})):
        now = dt_util.now()
        options = dict(DEFAULT_OPTIONS)
        context = coordinator._shading_context(now, options, 22.0, 21.0)
        assert context["cloudy"] is True and context["heat_expected"] is True  # above the comfort target
        assert context["sun_soon"][0] > context["sun"][0]
        context = coordinator._shading_context(now, {**options, "shade_max_cloud_coverage": 95}, 20.0, 21.0)
        assert context["cloudy"] is False and context["heat_expected"] is False
        coordinator._hourly_forecast_cache = [{"datetime": now + timedelta(hours=2), "temperature_c": 26.0}]
        assert coordinator._shading_context(now, options, 20.0, None)["heat_expected"] is True
        # naive time (never in practice): no calculated sun, sun.sun fallback
        assert coordinator._shading_context(now.replace(tzinfo=None), options, 20.0, None)["sun_soon"] is None
    await _unload(hass, entry)


# --------------------------------------------------------------------------- night cooling reasons
def _night_room(**overrides) -> RoomInput:
    values = dict(
        key="schlaf", name="Schlafzimmer", temperature=26.0, humidity=50.0,
        reference_temperature=18.0, reference_humidity=60.0, volume_m3=40.0,
        contact_open=True, contact_open_seconds=3600, session_active=True, session_elapsed_min=60,
        session_start_temp=28.0, learning_rate=0.04, session_fresh_measurements=2,
    )
    values.update(overrides)
    return RoomInput(**values)


def test_night_cooling_reasons() -> None:
    options = {**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}
    kwargs = dict(pollen=0.0, co2=None, airflow=1.0, wind_bearing=None, wind_speed=None)
    action, _, reasons = coordinator_module._recommendation(evaluate_room(_night_room(), options, False), options, **kwargs)
    assert action == "Continue ventilating"
    assert "Kühlen wirkt weiter: die Außenluft ist deutlich kühler als der Raum" in reasons
    warm = evaluate_room(_night_room(reference_temperature=27.0, session_elapsed_min=5), options, False)
    action, _, reasons = coordinator_module._recommendation(warm, options, **kwargs)
    assert action == "Close"
    assert "Die Außenluft ist nicht mehr kühler als der Raum; Schließen hält die Kühle im Raum" in reasons


# --------------------------------------------------------------------------- blueprint
@pytest.fixture
async def blueprints(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    target = tmp_path / "blueprints" / "automation" / "freshairiq"
    target.mkdir(parents=True)
    for path in SOURCE.glob("*.yaml"):
        shutil.copy(path, target / path.name)
    _sun(hass, 180.0, 40.0)
    _shading(hass, [])
    return {
        "close": async_mock_service(hass, "cover", "close_cover"),
        "open": async_mock_service(hass, "cover", "open_cover"),
    }


def _shading(hass, covers: list[str], state: str | None = None) -> None:
    hass.states.async_set(SENSOR, state or ("on" if covers else "off"), {"covers_to_close": covers})


async def _automation(hass, file="covers_follow_sun_protection.yaml", **inputs) -> None:
    assert await async_setup_component(hass, "automation", {"automation": [
        {"id": "covers_sun", "use_blueprint": {"path": f"freshairiq/{file}", "input": {"shading": SENSOR, **inputs}}},
    ]})
    await hass.async_block_till_done()


async def _change(hass, covers: list[str], state: str | None = None) -> None:
    _shading(hass, covers, state)
    await hass.async_block_till_done()


def _targets(calls) -> list[str]:
    result: list[str] = []
    for call in calls:
        ids = call.data["entity_id"]
        result.extend([ids] if isinstance(ids, str) else ids)
    return result


@pytest.mark.parametrize("file", ["covers_follow_sun_protection.yaml", "covers_follow_sun_protection_en.yaml"])
async def test_covers_close_with_the_sun_and_open_when_it_is_gone(hass, blueprints, file) -> None:
    await _automation(hass, file)
    await _change(hass, ["cover.ost"])
    assert _targets(blueprints["close"]) == ["cover.ost"]
    # a second window gets sun: only the new one is closed
    await _change(hass, ["cover.ost", "cover.sued"])
    assert _targets(blueprints["close"]) == ["cover.ost", "cover.sued"]
    assert blueprints["open"] == []
    # the sun has left the east window
    await _change(hass, ["cover.sued"])
    assert _targets(blueprints["open"]) == ["cover.ost"]
    await _change(hass, [])
    assert _targets(blueprints["open"]) == ["cover.ost", "cover.sued"]
    assert len(blueprints["close"]) == 2


async def test_selected_covers_unavailable_sensor_and_night(hass, blueprints) -> None:
    await _automation(hass, covers=["cover.sued"], reopen_at_night=False)
    await _change(hass, ["cover.ost", "cover.sued"])
    assert _targets(blueprints["close"]) == ["cover.sued"]
    # a restart / reload makes the sensor unavailable for a moment: nothing moves
    await _change(hass, [], "unavailable")
    await _change(hass, ["cover.ost", "cover.sued"])
    assert _targets(blueprints["close"]) == ["cover.sued", "cover.sued"]
    assert blueprints["open"] == []
    # sunset: the west-facing cover stays closed over night
    _sun(hass, 300.0, -2.0)
    await _change(hass, [])
    assert blueprints["open"] == []


async def test_reopening_can_be_switched_off(hass, blueprints) -> None:
    await _automation(hass, reopen=False)
    await _change(hass, ["cover.ost"])
    await _change(hass, [])
    assert _targets(blueprints["close"]) == ["cover.ost"] and blueprints["open"] == []
