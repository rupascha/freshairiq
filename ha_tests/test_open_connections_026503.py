"""0.26.5.3 (community): open connections page and one exhaust fan shared by two rooms."""
from __future__ import annotations

from types import SimpleNamespace

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.freshairiq.actuator_controller import ActuatorController
from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.open_connections import OPTION
from ha_tests import test_cov_options_flow as opt

FAN = "switch.luefter"


async def _connections_page(hass, entry):
    return await opt._open(hass, entry, "home_setup", "open_connections")


async def test_open_connections_are_set_symmetric_and_can_be_removed(hass) -> None:
    entry = opt._entry(rooms=[opt._room("Flur", key="flur"), opt._room("Wohnzimmer", key="wohnzimmer"), opt._room("Bad", key="bad")])
    entry.add_to_hass(hass)
    form = await _connections_page(hass, entry)
    assert form["step_id"] == "open_connections" and form["description_placeholders"]["overview"] == "–"
    form = await opt._submit(hass, form, {"room": "flur"})
    assert form["step_id"] == "open_connection_rooms" and form["description_placeholders"]["room_name"] == "Flur"
    options = [o["value"] for o in form["data_schema"].schema["connected_rooms"].config["options"]]
    assert options == ["wohnzimmer", "bad"]  # never the room itself
    form = await opt._submit(hass, form, {"connected_rooms": ["wohnzimmer"]})
    assert form["step_id"] == "open_connections"
    assert entry.options[OPTION] == {"flur": ["wohnzimmer"], "wohnzimmer": ["flur"]}
    assert form["description_placeholders"]["overview"] == "• Flur ↔ Wohnzimmer"

    # from the other side: the existing link is shown, emptying the field removes it
    form = await opt._submit(hass, form, {"room": "wohnzimmer"})
    shown = form["data_schema"].schema
    key = next(k for k in shown if str(k) == "connected_rooms")
    assert key.description == {"suggested_value": ["flur"]}
    form = await opt._submit(hass, form, {})
    assert entry.options[OPTION] == {}
    hass.config_entries.options.async_abort(form["flow_id"])


async def test_back_and_too_few_rooms(hass) -> None:
    entry = opt._entry(rooms=[opt._room("Flur", key="flur"), opt._room("Bad", key="bad")])
    entry.add_to_hass(hass)
    form = await _connections_page(hass, entry)
    form = await opt._submit(hass, form, {"room": "flur"})
    form = await opt._submit(hass, form, {"wizard_back": True, "connected_rooms": ["bad"]})
    assert form["step_id"] == "open_connections" and OPTION not in entry.options
    menu = await opt._submit(hass, form, {"wizard_back": True})
    assert menu["type"] is FlowResultType.MENU and menu["step_id"] == "home_setup"
    flow = opt._flow(hass, menu)
    flow._selected_room_key = "weg"
    assert (await flow.async_step_open_connection_rooms())["step_id"] == "open_connections"
    hass.config_entries.options.async_abort(menu["flow_id"])

    single = MockConfigEntry(domain=DOMAIN, data={"rooms": [opt._room("Flur", key="flur")], "levels": ["EG"]}, options={})
    single.add_to_hass(hass)
    menu = await _connections_page(hass, single)
    assert menu["type"] is FlowResultType.MENU and menu["step_id"] == "home_setup"


def _fan_room(key: str) -> dict:
    return {**opt._room(key.title(), key=key), "exhaust_fan": FAN, "exhaust_fan_control": "moisture_source",
            "exhaust_fan_follow_up_min": 0, "exhaust_fan_max_runtime_min": 240}


async def test_a_shared_fan_stays_on_while_another_room_needs_it(hass) -> None:
    on = async_mock_service(hass, "homeassistant", "turn_on")
    off = async_mock_service(hass, "homeassistant", "turn_off")
    hass.states.async_set(FAN, "off")
    entry = MockConfigEntry(domain=DOMAIN, data={"rooms": [_fan_room("buero"), _fan_room("wohnkueche")], "levels": ["EG"]})
    entry.add_to_hass(hass)
    listeners = []
    coordinator = SimpleNamespace(data={"rooms": {}}, async_add_listener=lambda cb: listeners.append(cb) or (lambda: None))
    controller = ActuatorController(hass, coordinator, entry)

    async def cycle(buero: bool, wohnkueche: bool) -> None:
        coordinator.data = {"rooms": {"buero": {"moisture_source_active": buero}, "wohnkueche": {"moisture_source_active": wohnkueche}}}
        await controller._async_evaluate(fans=True)
        await hass.async_block_till_done()

    await controller.async_start()
    await cycle(True, False)  # Büro switches the fan on
    assert len(on) == 1
    hass.states.async_set(FAN, "on")
    await cycle(False, True)  # Büro is done, the kitchen still needs the fan
    await cycle(False, True)
    assert off == []
    await cycle(False, False)  # nobody needs it any more
    assert len(off) == 1
    await controller.async_stop()
