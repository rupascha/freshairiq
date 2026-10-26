"""0.26.5.1 (owner request): goal priorities 2 and 3 offer "Off".

A room that should only dehumidify switches CO2 and temperature off: the goals
disappear from the goal state, a high CO2 level starts no airing and a warm room
gets no "Ventilate for cooling". Dehumidification cannot be switched off.
"""
from __future__ import annotations

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq import const as c
from custom_components.freshairiq.const import CONF_ROOM_DISABLED_GOALS, CONF_ROOM_GOAL_PRIORITIES
from ha_tests.test_cov_coordinator_b import (  # noqa: F401  (autouse fixture)
    CO2,
    HUM,
    OPTIONS,
    TEMP,
    _cleanup_coordinators,
    _data,
    _make,
    _rooms,
    _with,
)
from ha_tests.test_cov_options_flow import _entry, _open, _room, _submit

ALL = ["humidity", "co2", "temperature"]


def _three_goal_room(**extra) -> dict:
    room = {
        c.CONF_ROOM_HUMIDITY: "sensor.h", c.CONF_ROOM_TEMPERATURE: "sensor.t",
        c.CONF_ROOM_CO2: "sensor.co2", c.CONF_ROOM_TARGET_TEMPERATURE: 21,
        CONF_ROOM_GOAL_PRIORITIES: list(ALL),
    }
    room.update(extra)
    return room


def _options_of(schema, key):
    return schema.schema[next(k for k in schema.schema if str(k) == key)].config["options"]


def _defaults(schema) -> dict:
    return {str(k): k.default() for k in schema.schema if hasattr(k, "default") and callable(k.default)}


def test_off_is_offered_from_the_second_position_on() -> None:
    schema = cf._goal_priority_schema(_three_goal_room())
    assert _options_of(schema, "goal_priority_1") == ALL
    assert _options_of(schema, "goal_priority_2") == [*ALL, "off"]
    assert _options_of(schema, "goal_priority_3") == [*ALL, "off"]
    assert _defaults(schema) == {"goal_priority_1": "humidity", "goal_priority_2": "co2", "goal_priority_3": "temperature"}

    off = cf._goal_priority_schema(_three_goal_room(**{CONF_ROOM_DISABLED_GOALS: ["co2", "temperature"]}))
    assert _defaults(off) == {"goal_priority_1": "humidity", "goal_priority_2": "off", "goal_priority_3": "off"}


def test_shown_order_never_starts_with_off() -> None:
    # only goals the room does not have (or humidity) listed: nothing is switched off
    assert cf._shown_goal_priorities(_three_goal_room(**{CONF_ROOM_DISABLED_GOALS: ["humidity"]})) == ALL
    # every available goal switchable and switched off -> the first stays active
    room = {c.CONF_ROOM_CO2: "sensor.co2", c.CONF_ROOM_TARGET_TEMPERATURE: 21,
            CONF_ROOM_DISABLED_GOALS: ["co2", "temperature"]}
    assert cf._shown_goal_priorities(room) == ["co2", "off"]


def test_selection_switches_goals_off_and_back_on() -> None:
    room = _three_goal_room()
    only_humidity = {"goal_priority_1": "humidity", "goal_priority_2": "off", "goal_priority_3": "off"}
    assert cf._goal_priority_errors(only_humidity, room) == {}
    assert cf._ranked_goal_priorities(only_humidity, room) == ALL
    assert cf._switched_off_goals(only_humidity, room) == ["co2", "temperature"]

    # moving temperature up while switching the last position off ("move" semantics)
    moved = {"goal_priority_1": "temperature", "goal_priority_2": "co2", "goal_priority_3": "off"}
    assert cf._resolve_goal_selection(moved, room) == (["temperature", "co2"], ["humidity"])
    assert cf._goal_priority_errors(moved, room) == {"base": "humidity_goal_required"}

    partly = {"goal_priority_1": "co2", "goal_priority_2": "co2", "goal_priority_3": "off"}
    assert cf._resolve_goal_selection(partly, room) == (["co2", "humidity"], ["temperature"])
    assert cf._ranked_goal_priorities(partly, room) == ["co2", "humidity", "temperature"]

    disabled = _three_goal_room(**{CONF_ROOM_DISABLED_GOALS: ["co2", "temperature"]})
    # a position still showing "off" is kept, a changed one switches its goal on again
    back_on = {"goal_priority_1": "humidity", "goal_priority_2": "temperature", "goal_priority_3": "off"}
    assert cf._resolve_goal_selection(back_on, disabled) == (["humidity", "temperature"], ["co2"])
    all_on = {"goal_priority_1": "humidity", "goal_priority_2": "temperature", "goal_priority_3": "co2"}
    assert cf._ranked_goal_priorities(all_on, disabled) == ["humidity", "temperature", "co2"]
    assert cf._switched_off_goals(all_on, disabled) == []
    # untouched form keeps everything as it is
    untouched = {"goal_priority_1": "humidity", "goal_priority_2": "off", "goal_priority_3": "off"}
    assert cf._resolve_goal_selection(untouched, disabled) == (["humidity"], ["co2", "temperature"])


def test_invalid_off_positions_are_rejected() -> None:
    room = _three_goal_room(**{CONF_ROOM_DISABLED_GOALS: ["temperature"]})
    first_off = {"goal_priority_1": "off", "goal_priority_2": "humidity", "goal_priority_3": "co2"}
    assert cf._resolve_goal_selection(first_off, room) is None
    assert cf._goal_priority_errors(first_off, room) == {"base": "invalid_goal_order"}
    assert cf._ranked_goal_priorities(first_off, room) == ALL
    # an invalid submission keeps the stored switched-off goals
    assert cf._switched_off_goals(first_off, room) == ["temperature"]
    assert cf._switched_off_goals({}, room) == ["temperature"]


async def test_options_flow_saves_and_restores_switched_off_goals(hass) -> None:
    room = _room(co2=True)
    room[c.CONF_ROOM_TARGET_TEMPERATURE] = 21
    entry = _entry(rooms=[room])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "recommendation_priorities")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    assert result["step_id"] == "recommendation_priority_order"

    result = await _submit(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "off", "goal_priority_3": "off"})
    assert result["step_id"] == "recommendation_priority_order"
    assert result["errors"] == {"base": "humidity_goal_required"}

    result = await _submit(hass, result, {"goal_priority_1": "humidity", "goal_priority_2": "off", "goal_priority_3": "off"})
    assert result["step_id"] == "recommendation_priorities"
    stored = entry.data["rooms"][0]
    assert stored[CONF_ROOM_GOAL_PRIORITIES] == ALL
    assert stored[CONF_ROOM_DISABLED_GOALS] == ["co2", "temperature"]

    result = await _submit(hass, result, {"room": "wohnzimmer"})
    assert _defaults(result["data_schema"]) == {
        "wizard_back": False, "goal_priority_1": "humidity", "goal_priority_2": "off", "goal_priority_3": "off",
    }
    result = await _submit(hass, result, {"goal_priority_1": "humidity", "goal_priority_2": "co2", "goal_priority_3": "off"})
    assert result["step_id"] == "recommendation_priorities"
    stored = entry.data["rooms"][0]
    assert stored[CONF_ROOM_GOAL_PRIORITIES] == ALL
    assert stored[CONF_ROOM_DISABLED_GOALS] == ["temperature"]


async def _kitchen(hass, freezer, disabled, profile, states):
    rooms = _with(_rooms(), "kueche", disabled_goals=disabled)
    d = await _make(hass, freezer, data=_data(rooms), options={**OPTIONS, "operating_profile": profile}, initial=states)
    await d.step(60)
    return d.room("kueche")


async def test_switched_off_co2_starts_no_airing_but_stays_visible(hass, freezer) -> None:
    stale_air = {"sensor.kueche_co2": (1800, CO2), "sensor.kueche_h": (45.0, HUM)}
    on = await _kitchen(hass, freezer, [], "dehumidify", stale_air)
    assert on["co2_available"] is True and on["ventilation_candidate"] is True

    off = await _kitchen(hass, freezer, ["co2"], "dehumidify", stale_air)
    assert off["co2"] == 1800.0
    assert off["co2_available"] is False and off["co2_data_quality"] == "goal_disabled"
    assert off["ventilation_candidate"] is False
    goals = {g["id"]: g for g in off["goal_state"]["goals"]}
    assert goals["co2"]["active"] is False and goals["co2"]["disabled"] is True
    assert off["goal_state"]["priorities"] == ["humidity", "temperature"]
    assert off["goal_state"]["disabled_goals"] == ["co2"]


async def test_switched_off_temperature_gets_no_ventilate_for_cooling(hass, freezer) -> None:
    # CO₂ below the warning threshold: only the temperature goal decides here
    warm = {"sensor.kueche_t": (27.0, TEMP), "sensor.aussen_t": (15.0, TEMP), "sensor.kueche_h": (50.0, HUM), "sensor.kueche_co2": (600, CO2)}
    on = await _kitchen(hass, freezer, [], "summer_cooling", warm)
    assert on["action"] == "Ventilate for cooling" and on["cooling_candidate"] is True
    # 0.26.5.4: CO₂ above the warning threshold leads, cooling stays the extra benefit
    stale = await _kitchen(hass, freezer, [], "summer_cooling", {**warm, "sensor.kueche_co2": (1180, CO2)})
    assert stale["action"] == "Ventilate" and stale["cooling_candidate"] is True
    assert stale["recommendation_reasons"][0].startswith("CO₂ 1180 ppm")

    off = await _kitchen(hass, freezer, ["temperature"], "summer_cooling", warm)
    assert off["action"] != "Ventilate for cooling" and off["cooling_candidate"] is False
    assert all(row.get("cooling_candidate") is not True for row in off.get("opening_assessments") or [])
    assert off["goal_state"]["priorities"] == ["humidity", "co2"]
