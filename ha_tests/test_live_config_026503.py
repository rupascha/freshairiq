"""0.26.5.3: saved settings work at once – no Home Assistant restart needed.

Owner report: the automatic cover control on opening a window only started
working after a restart. The cover controller read the room setup once at
startup (and did not even follow coordinator updates when no room used it
yet); the options-flow room editor never told it about a change. The source
listeners had the same gap whenever the room wizard was closed before its
last page. Every config-entry change is now applied to both at once.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.freshairiq.const import (
    CONF_CONTACT_COVER_FOLLOW,
    CONF_CONTACT_COVERS,
    CONF_ROOM_CONTACTS,
)
from ha_tests.test_actuator_control_20261017 import COVER, POSITION_COVER, WINDOW, _calls, _services, _state
from ha_tests.test_clearable_fields_026503 import SUBMIT, _replay, _submission
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

WINDOW_2 = "binary_sensor.wohnzimmer_window_2"
COVER_2 = "cover.wohnzimmer_2"
EDIT_ROOM = ["home_setup", "rooms", "edit_room_select", SUBMIT]


async def _open_opening_page(hass, entry):
    """Room editor up to the page of the window (the goals page only shows with several goals)."""
    path = [*EDIT_ROOM, SUBMIT]
    form = await _replay(hass, entry, path)
    while form["step_id"] != "contact_references":
        hass.config_entries.options.async_abort(form["flow_id"])
        assert len(path) < 8, form["step_id"]
        path.append(SUBMIT)
        form = await _replay(hass, entry, path)
    return form


def _room_with_cover(*, follow: bool) -> dict:
    return {**_room(), CONF_CONTACT_COVERS: {WINDOW: [COVER]}, CONF_CONTACT_COVER_FOLLOW: {WINDOW: follow}}


async def _save_room(hass, entry, **changes) -> None:
    room = {**entry.data["rooms"][0], **changes}
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [room]})
    await hass.async_block_till_done()


async def test_cover_control_switched_on_while_running_reacts_to_the_window(hass) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    entry = await _setup(hass, _entry(rooms=[_room_with_cover(follow=False)]))

    await _save_room(hass, entry, **{CONF_CONTACT_COVER_FOLLOW: {WINDOW: True}})
    await _state(hass, WINDOW, "on")
    assert _calls(calls["open_cover"]) == [(COVER, None)]
    await _unload(hass, entry)


async def test_cover_control_set_in_the_options_flow_works_when_the_dialog_is_closed(hass) -> None:
    """The real path: opening page of the room editor, saved, dialog closed (no finish)."""
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    entry = await _setup(hass, _entry(rooms=[_room()]))

    form = await _open_opening_page(hass, entry)
    data = {**_submission(form["data_schema"]), "covers": [COVER], "cover_follow": True}
    result = await hass.config_entries.options.async_configure(form["flow_id"], data)
    if result["type"] in (FlowResultType.FORM, FlowResultType.MENU):
        hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert entry.data["rooms"][0][CONF_CONTACT_COVER_FOLLOW] == {WINDOW: True}

    await _state(hass, WINDOW, "on")
    assert _calls(calls["open_cover"]) == [(COVER, None)]
    await _unload(hass, entry)


async def test_a_window_with_cover_added_to_a_controlled_room_works_at_once(hass) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(WINDOW_2, "off")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    hass.states.async_set(COVER_2, "closed", POSITION_COVER)
    entry = await _setup(hass, _entry(rooms=[_room_with_cover(follow=True)]))
    coordinator = entry.runtime_data
    assert WINDOW_2 not in coordinator._contact_entities

    await _save_room(hass, entry, **{
        CONF_ROOM_CONTACTS: [WINDOW, WINDOW_2],
        CONF_CONTACT_COVERS: {WINDOW: [COVER], WINDOW_2: [COVER_2]},
        CONF_CONTACT_COVER_FOLLOW: {WINDOW: True, WINDOW_2: True},
    })
    # the coordinator listens to the new window, the cover control moves its cover
    assert WINDOW_2 in coordinator._contact_entities
    await _state(hass, WINDOW_2, "on")
    assert _calls(calls["open_cover"]) == [(COVER_2, None)]
    await _unload(hass, entry)


async def test_cover_control_switched_off_while_running_leaves_the_cover_alone(hass) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    entry = await _setup(hass, _entry(rooms=[_room_with_cover(follow=True)]))

    await _save_room(hass, entry, **{CONF_CONTACT_COVER_FOLLOW: {WINDOW: False}})
    await _state(hass, WINDOW, "on")
    assert calls["open_cover"] == []
    await _unload(hass, entry)


async def test_unrelated_saves_do_not_rebuild_listeners_or_the_cover_control(hass) -> None:
    """Pending window confirmations survive saves that change no source or control."""
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry(rooms=[_room_with_cover(follow=True)]))
    coordinator = entry.runtime_data
    unsub_state = coordinator._unsub_state
    controller_rooms = coordinator.actuator_controller._rooms
    hass.config_entries.async_update_entry(entry, options={**entry.options, "start_rh": 61})
    await hass.async_block_till_done()
    assert coordinator._unsub_state is unsub_state
    assert coordinator.actuator_controller._rooms is controller_rooms
    await _unload(hass, entry)


async def test_cover_control_follows_the_next_update_without_the_change_signal(hass) -> None:
    """Safety net: the change watcher could not be set up – the next coordinator update suffices."""
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    entry = await _setup(hass, _entry(rooms=[_room_with_cover(follow=False)]))
    coordinator = entry.runtime_data
    with patch.object(coordinator, "async_sync_runtime_config", AsyncMock()):
        await _save_room(hass, entry, **{CONF_CONTACT_COVER_FOLLOW: {WINDOW: True}})
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    await _state(hass, WINDOW, "on")
    assert _calls(calls["open_cover"]) == [(COVER, None)]
    await _unload(hass, entry)
