"""0.26.5.3 hotfix (GitHub #19, community report): new cooling airings in the comfort profile.

Real coordinator, the whole chain: model → goals → room recommendation →
opening assessments → house recommendation → bus events. In the comfort
profile a room with a temperature goal is only asked to cool from its own
comfort target (manual, thermostat or fallback) plus the comfort margin;
the house-wide start temperature stays the lower bound.
"""
from __future__ import annotations

from custom_components.freshairiq.automation_events import AutomationEventEmitter
from ha_tests.test_cov_coordinator_b import HUM, OPTIONS, TEMP, WINDOW, _cleanup_coordinators, _make, _room  # noqa: F401

COMFORT = {**OPTIONS, "operating_profile": "comfort"}
CONTACTS = ["binary_sensor.wohn_fenster", "binary_sensor.wohn_balkon"]


def _data(climate: str = "", **extra) -> dict:
    room = _room("wohn", "Wohnzimmer", "ground_floor", temp=["sensor.wohn_t"], hum=["sensor.wohn_h"],
                 contacts=CONTACTS, volume=60, climate=climate, extra=extra)
    return {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": [room], "levels": ["ground_floor"]}


def _initial(room_t: float, outdoor_t: float, outdoor_rh: float = 75.0, thermostat: float | None = None) -> dict:
    states = {"sensor.aussen_t": (outdoor_t, TEMP), "sensor.aussen_h": (outdoor_rh, HUM),
              "sensor.wohn_t": (room_t, TEMP), "sensor.wohn_h": (50.0, HUM)}
    states.update({contact: ("off", WINDOW) for contact in CONTACTS})
    if thermostat is not None:
        states["climate.wohn"] = ("heat", {"temperature": thermostat, "current_temperature": room_t})
    return states


def _cooling_everywhere(d) -> set[bool]:
    """Room action, model flag and every single window assessment must agree.

    The house recommendation may present a cooling room as "Ventilate"; the
    room engine's own action is then kept as ``canonical_action``.
    """
    room = d.room("wohn")
    seen = {room.get("canonical_action", room["action"]) == "Ventilate for cooling", bool(room["cooling_candidate"])}
    for assessment in room["opening_assessments"]:
        seen.add(bool(assessment["cooling_candidate"]))
        seen.add(assessment["model_action"] == "Ventilate for cooling")
    return seen


def _fired(events) -> list[str]:
    return [p["action"] for name, p in events if name == "freshairiq_room_action" and p["room_key"] == "wohn"]


async def test_case_a_manual_target_and_the_way_up_to_it(hass, freezer) -> None:
    events: list = []
    emitter = AutomationEventEmitter(lambda name, payload: events.append((name, payload)), "entry")
    d = await _make(hass, freezer, data=_data(target_temperature_mode="manual", target_temperature=25.5),
                    options=COMFORT, initial=_initial(24.3, 15.0))
    await d.step(60)
    emitter.process(d.data)
    room = d.room("wohn")
    assert (room["comfort_target_c"], room["comfort_target_source"]) == (25.5, "manual")
    assert len(room["opening_assessments"]) == 2
    assert _cooling_everywhere(d) == {False}
    assert room["house_aligned_action"] != "ventilate_for_cooling"
    assert d.data["intelligent_recommendation"]["kind"] != "cooling"
    assert "ventilate_for_cooling" not in _fired(events)

    # above the target (+ margin) the room is cooled again – room, windows, house and event agree
    # (same absolute humidity, so no moisture source is involved)
    await d.step(60, sensor__wohn_t=(26.2, TEMP), sensor__wohn_h=(44.5, HUM))
    emitter.process(d.data)
    assert _cooling_everywhere(d) == {True}
    room = d.room("wohn")
    assert room["action"] in {"Ventilate", "Ventilate for cooling"}
    assert room["house_aligned_action"] in {"ventilate", "ventilate_for_cooling"}
    house = d.data["intelligent_recommendation"]
    assert house["kind"] in {"ventilate", "cooling"} and "wohn" in house["room_keys"]
    assert _fired(events)[-1] in {"ventilate", "ventilate_for_cooling"}


async def test_case_b_thermostat_target_reached(hass, freezer) -> None:
    d = await _make(hass, freezer, data=_data(climate="climate.wohn"), options=COMFORT,
                    initial=_initial(24.0, 9.7, 85.0, thermostat=24.0))
    await d.step(60)
    room = d.room("wohn")
    assert (room["comfort_target_c"], room["comfort_target_source"]) == (24.0, "thermostat")
    temperature_goal = next(goal for goal in room["goal_state"]["goals"] if goal["id"] == "temperature")
    assert temperature_goal["reached"] is True
    assert _cooling_everywhere(d) == {False}
    # room and house tell the same story
    assert room["house_aligned_action"] != "ventilate_for_cooling"
    assert d.data["intelligent_recommendation"]["kind"] != "cooling"


async def test_fallback_target_is_followed_too(hass, freezer) -> None:
    d = await _make(hass, freezer, data=_data(target_temperature_fallback=25.0), options=COMFORT, initial=_initial(24.3, 15.0))
    await d.step(60)
    assert (d.room("wohn")["comfort_target_c"], d.room("wohn")["comfort_target_source"]) == (25.0, "fallback")
    assert _cooling_everywhere(d) == {False}


async def test_room_without_thermostat_or_target_keeps_the_house_wide_threshold(hass, freezer) -> None:
    d = await _make(hass, freezer, data=_data(), options=COMFORT, initial=_initial(24.3, 15.0))
    await d.step(60)
    assert d.room("wohn")["comfort_target_c"] is None
    assert _cooling_everywhere(d) == {True}


async def test_switched_off_temperature_goal_never_asks_to_cool(hass, freezer) -> None:
    d = await _make(hass, freezer, data=_data(target_temperature_mode="manual", target_temperature=21.0, disabled_goals=["temperature"]),
                    options=COMFORT, initial=_initial(26.5, 15.0))
    await d.step(60)
    assert _cooling_everywhere(d) == {False}


async def test_summer_profile_is_unchanged(hass, freezer) -> None:
    d = await _make(hass, freezer, data=_data(target_temperature_mode="manual", target_temperature=25.5),
                    options={**OPTIONS, "operating_profile": "summer_cooling"}, initial=_initial(24.3, 15.0))
    await d.step(60)
    assert _cooling_everywhere(d) == {True}
