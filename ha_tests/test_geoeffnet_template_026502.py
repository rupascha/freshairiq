"""0.26.5.2 (support case): a user template reports "geöffnet / gekippt / geschlossen".

"geöffnet" was read as an unknown state: a running tilt was kept as "tilted" and
after 30 s the learning session was quarantined (FAIQ-OPENING-3STATE-006). Real
coordinator run through closed → tilted → open → closed.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from ha_tests.test_cov_coordinator_a import START, room, set_climate, set_weather, setup, step

HANDLE = "sensor.fenster_schlafzimmer"  # template without an options list, as in the report


async def test_template_words_drive_one_clean_session(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "schlaf", 21.3, 62.0)
    hass.states.async_set(HANDLE, "geschlossen")
    _entry, coordinator = await setup(hass, [room("schlaf", contacts=[HANDLE])])
    data = await step(hass, freezer, coordinator, 30)
    mem = coordinator.store.room("schlaf")
    assert data["rooms"]["schlaf"]["active"] is False and mem["session_active"] is False

    hass.states.async_set(HANDLE, "gekippt")
    for _ in range(2):
        data = await step(hass, freezer, coordinator, 5)
    assert data["rooms"]["schlaf"]["opening_state"] == "tilted"
    assert data["rooms"]["schlaf"]["three_state_contacts"] == [HANDLE]
    assert mem["session_active"] is True
    started = mem["session_started"]

    hass.states.async_set(HANDLE, "geöffnet")
    for _ in range(2):
        data = await step(hass, freezer, coordinator, 5)
    data = await step(hass, freezer, coordinator, 60)  # longer than the 30 s unknown hold
    schlaf = data["rooms"]["schlaf"]
    assert schlaf["opening_state"] == "open"
    assert mem["stable_opening_modes"] == {HANDLE: "open"}
    assert schlaf["three_state_unknown_contacts"] == [] and schlaf["three_state_stale_contacts"] == []
    assert mem.get("session_learning_quarantine_code") != "FAIQ-OPENING-3STATE-006"
    assert mem["session_active"] is True and mem["session_started"] == started  # same airing, no new session

    hass.states.async_set(HANDLE, "geschlossen")
    for _ in range(5):
        data = await step(hass, freezer, coordinator, 5)
    assert mem["session_active"] is False and data["rooms"]["schlaf"]["active"] is False


async def test_first_opening_with_geoeffnet_starts_an_open_airing(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "schlaf", 21.3, 62.0)
    hass.states.async_set(HANDLE, "geschlossen")
    _entry, coordinator = await setup(hass, [room("schlaf", contacts=[HANDLE])])
    await step(hass, freezer, coordinator, 30)
    hass.states.async_set(HANDLE, "geöffnet")
    for _ in range(2):
        data = await step(hass, freezer, coordinator, 5)
    data = await step(hass, freezer, coordinator, 60)
    mem = coordinator.store.room("schlaf")
    assert data["rooms"]["schlaf"]["active"] is True and data["rooms"]["schlaf"]["opening_state"] == "open"
    assert mem["session_active"] is True and not mem.get("session_learning_quarantined")


async def test_real_unavailable_keeps_its_protection(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "schlaf", 21.3, 62.0)
    hass.states.async_set(HANDLE, "geschlossen")
    _entry, coordinator = await setup(hass, [room("schlaf", contacts=[HANDLE])])
    await step(hass, freezer, coordinator, 30)
    hass.states.async_set(HANDLE, "gekippt")
    for _ in range(2):
        await step(hass, freezer, coordinator, 5)
    hass.states.async_set(HANDLE, "unavailable")
    await step(hass, freezer, coordinator, 5)
    data = await step(hass, freezer, coordinator, 60)
    mem = coordinator.store.room("schlaf")
    assert data["rooms"]["schlaf"]["three_state_stale_contacts"] == [HANDLE]
    assert mem["session_learning_quarantine_code"] == "FAIQ-OPENING-3STATE-006"
