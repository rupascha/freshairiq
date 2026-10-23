"""0.26.5.3: clicking through the room editor keeps every stored room setting.

Owner report: a ventilation goal switched "off" on the priorities page was
"on" again the next time the room was edited. The first editor page rebuilt
the room from its own fields and dropped ``disabled_goals``; the priorities
page then showed (and saved) the goal as active. The generic test below
seeds every room setting the editor pages can store and walks the whole
editor without changing anything: no stored value may change or disappear.
"""
from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from ha_tests.test_clearable_fields_026503 import SUBMIT, _abort, _forms_with_stored_values, _replay, _seed_entry, _submission

WINDOW = "binary_sensor.fenster"
EDIT_ROOM = ["home_setup", "rooms", "edit_room_select", SUBMIT]


def _entry_with(room_changes: dict) -> MockConfigEntry:
    seed = _seed_entry()
    room = {**seed.data["rooms"][0], **room_changes}
    return MockConfigEntry(domain=seed.domain, unique_id=seed.unique_id, data={**seed.data, "rooms": [room]}, options=dict(seed.options))


async def _click_through(hass, entry, change: dict | None = None) -> list[str]:
    """Open the room editor and confirm every page as shown (``change`` applies on its page)."""
    result = await _replay(hass, entry, EDIT_ROOM)
    steps = []
    while result["type"] is FlowResultType.FORM and len(steps) < 10:
        steps.append(result["step_id"])
        data = {**_submission(result["data_schema"]), **(change or {}).get(result["step_id"], {})}
        result = await hass.config_entries.options.async_configure(result["flow_id"], data)
    if result["type"] is FlowResultType.MENU:
        hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    return steps


def _norm(value):
    """Same meaning, same form: a legacy single entity is a one-element list,
    a per-opening flag that is ``False`` is the same as no entry."""
    if isinstance(value, str) and "." in value and " " not in value:
        return [value]
    if isinstance(value, dict):
        return {key: _norm(item) for key, item in value.items() if item is not False}
    if isinstance(value, (list, tuple)):
        return [_norm(item) if isinstance(item, dict) else item for item in value]
    return value


def _same(before, after) -> bool:
    return _norm(before) == _norm(after)


STORED = {
    "goal_priorities": ["humidity", "co2", "temperature"], "disabled_goals": ["temperature"],
    "target_temperature_mode": "manual", "target_temperature": 21.5,
    "ventilation_threshold_mode": "percent_room_water", "ventilation_threshold_percent": 8.0, "ventilation_threshold_ml": 150.0,
    "temperature_aggregation": "max", "humidity_aggregation": "median", "icon": "mdi:sofa",
    "length": 5.0, "width": 4.0, "height": 2.5, "volume": 50.0, "window_orientation": "s",
    "auto_sun_protection": True, "exhaust_fan_control": "moisture_source",
    "exhaust_fan_follow_up_min": 20.0, "exhaust_fan_max_runtime_min": 90.0,
    "contact_delays": {WINDOW: 30}, "contact_orientations": {WINDOW: "s"},
    "contact_passage_doors": {WINDOW: False}, "contact_cover_follow": {WINDOW: True},
    "cover_position_zero_means": "open",
}


async def test_clicking_through_the_room_editor_changes_no_stored_setting(hass) -> None:
    entry = _entry_with(STORED)
    entry.add_to_hass(hass)
    before = dict(entry.data["rooms"][0])
    steps = await _click_through(hass, entry)
    assert steps == ["edit_room", "room_goals", "contact_references"]
    after = entry.data["rooms"][0]
    changed = sorted(key for key in before if not _same(before[key], after.get(key)))
    assert changed == []
    # and a second pass is a no-op
    first = dict(after)
    await _click_through(hass, entry)
    assert dict(entry.data["rooms"][0]) == first


async def test_a_goal_switched_off_stays_off_on_the_next_edit(hass) -> None:
    """Owner case: two goals, the second set to "off", the room edited again."""
    entry = _entry_with({"co2": None})
    entry.add_to_hass(hass)
    await _click_through(hass, entry, {"room_goals": {"goal_priority_2": "off"}})
    assert entry.data["rooms"][0]["disabled_goals"] == ["temperature"]

    form = await _replay(hass, entry, [*EDIT_ROOM, SUBMIT])
    assert form["step_id"] == "room_goals"
    shown = {str(key): key.default() for key in form["data_schema"].schema if str(key).startswith("goal_priority_")}
    hass.config_entries.options.async_abort(form["flow_id"])
    assert shown == {"goal_priority_1": "humidity", "goal_priority_2": "off"}

    await _click_through(hass, entry)
    assert entry.data["rooms"][0]["disabled_goals"] == ["temperature"]


async def test_confirming_any_settings_page_unchanged_changes_nothing(hass) -> None:
    """Every options page reached by menus and plain confirmations is idempotent."""
    entry = _entry_with(STORED)
    entry.add_to_hass(hass)
    await _click_through(hass, entry)  # one normalising pass of the room editor
    pages = {step: path for path, step, _field in await _forms_with_stored_values(hass, entry)}
    assert {"edit_room", "contact_references", "outdoor", "residents", "cross_ventilation", "notifications"} <= set(pages)
    changed = []
    for step, path in pages.items():
        before = (dict(entry.data), dict(entry.options))
        form = await _replay(hass, entry, path)
        _abort(hass, await hass.config_entries.options.async_configure(form["flow_id"], _submission(form["data_schema"])))
        await hass.async_block_till_done()
        if not _same(before, (dict(entry.data), dict(entry.options))):
            changed.append(step)
    assert changed == []
