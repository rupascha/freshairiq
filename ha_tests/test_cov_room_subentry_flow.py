"""Real-HA coverage of the native room subentry flow (FreshAirIQRoomSubentryFlow).

The quick add-room flow (manual creation and HA area import, goals, per-opening
references, atomic post-commit persistence) is driven through
``hass.config_entries.subentries``. The legacy room-edit steps are not reachable
through Home Assistant's reconfigure entry point (the class intentionally has no
``async_step_reconfigure``), so they are exercised on a flow instance bound to a
real config entry and a real room subentry in a reconfigure context.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.data_entry_flow import FlowResultType, UnknownStep
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq.config_flow import FreshAirIQRoomSubentryFlow
from custom_components.freshairiq.const import (
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_ILLUMINANCE,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
    CONTACT_MODE_ANY,
    DOMAIN,
)

WINDOW_A = "binary_sensor.buero_window_a"
WINDOW_B = "binary_sensor.buero_window_b"


@pytest.fixture
def fast_commit_sleep(monkeypatch):
    """Replace the bounded commit-wait sleeps with scheduler yields (no real waiting)."""

    async def _yield(_delay=0):
        await asyncio.sleep(0)

    monkeypatch.setattr(cf, "asyncio", SimpleNamespace(sleep=_yield))


def _room(key: str = "wohnzimmer", name: str = "Wohnzimmer", **extra) -> dict:
    room = {
        "key": key,
        CONF_ROOM_NAME: name,
        CONF_ROOM_TEMPERATURE: [f"sensor.{key}_temperature"],
        CONF_ROOM_HUMIDITY: [f"sensor.{key}_humidity"],
        CONF_ROOM_CONTACTS: [],
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
        CONF_ROOM_VOLUME: 40.0,
        CONF_ROOM_FLOOR: "EG",
        CONF_ROOM_INCLUDE_CALCULATIONS: True,
    }
    room.update(extra)
    return room


def _entry(rooms=None, *, subentries=None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.home", "rooms": list(rooms or []), "levels": ["EG"]},
        options={},
        subentries_data=list(subentries or []),
    )


def _sections(name: str, *, floor: str = "EG", contacts=None, co2=None, climate=None, volume=35.0, prefix="buero") -> dict:
    sensors = {
        CONF_ROOM_TEMPERATURE: [f"sensor.{prefix}_temperature"],
        CONF_ROOM_HUMIDITY: [f"sensor.{prefix}_humidity"],
        CONF_ROOM_CONTACTS: list(contacts or []),
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
    }
    if co2:
        sensors[CONF_ROOM_CO2] = co2
    if climate:
        sensors[CONF_ROOM_CLIMATE] = climate
    return {
        "identity": {CONF_ROOM_NAME: name, CONF_ROOM_FLOOR: floor, CONF_ROOM_INCLUDE_CALCULATIONS: True},
        "sensors": sensors,
        "geometry": {CONF_ROOM_VOLUME: volume} if volume is not None else {},
    }


async def _start(hass, entry, step: str):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["create_room", "import_ha_room"]
    return await hass.config_entries.subentries.async_configure(result["flow_id"], {"next_step_id": step})


def _configure(hass, result, user_input):
    return hass.config_entries.subentries.async_configure(result["flow_id"], user_input)


# ---------------------------------------------------------------------------
# Quick add: manual room with goals and per-opening references
# ---------------------------------------------------------------------------


async def test_create_room_wizard_goals_references_back_and_commit(hass, fast_commit_sleep) -> None:
    entry = _entry([_room()])
    entry.add_to_hass(hass)
    hass.states.async_set(WINDOW_A, "off", {"friendly_name": "Büro Fenster links"})

    result = await _start(hass, entry, "create_room")
    assert result["step_id"] == "create_room"

    # Validation failure keeps the form.
    result = await _configure(hass, result, _sections("Büro", volume=None))
    assert result["step_id"] == "create_room"
    assert result["errors"] == {"base": "room_volume_required"}

    room_input = _sections(
        "Büro", floor="OG", contacts=[WINDOW_A, WINDOW_B], co2="sensor.buero_co2", climate="climate.buero"
    )
    result = await _configure(hass, result, room_input)
    assert result["step_id"] == "add_goals"
    assert "wizard_back" in result["data_schema"].schema

    # Back from goals returns to the manual creation page with the entered room.
    result = await _configure(hass, result, {"wizard_back": True, "goal_priority_1": "humidity", "goal_priority_2": "co2", "goal_priority_3": "temperature"})
    assert result["step_id"] == "create_room"
    result = await _configure(hass, result, room_input)
    assert result["step_id"] == "add_goals"

    # Unknown goals are already rejected by the selector schema.
    from homeassistant.data_entry_flow import InvalidData
    with pytest.raises(InvalidData):
        await _configure(hass, result, {"goal_priority_1": "bogus", "goal_priority_2": "co2", "goal_priority_3": "temperature"})

    # Move CO2 to the top.
    result = await _configure(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "co2", "goal_priority_3": "temperature"})
    assert result["step_id"] == "add_references"
    placeholders = result["description_placeholders"]
    assert placeholders["room_name"] == "Büro"
    assert placeholders["contact_name"] == "Büro Fenster links"
    assert placeholders["contact_entity"] == WINDOW_A
    assert (placeholders["contact_position"], placeholders["contact_count"]) == ("1", "2")

    # Back on the first opening with several goals -> goals page.
    result = await _configure(hass, result, {"wizard_back": True})
    assert result["step_id"] == "add_goals"
    result = await _configure(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "humidity", "goal_priority_3": "temperature"})
    assert result["step_id"] == "add_references"

    # Only one half of the reference pair -> error.
    result = await _configure(hass, result, {"reference_temperature": "sensor.outside_t", "delay_seconds": 0, "orientation": "s", "cover_position_zero_means": "closed"})
    assert result["errors"] == {"base": "contact_reference_pair_required"}

    result = await _configure(hass, result, {
        "reference_temperature": "sensor.outside_t", "reference_humidity": "sensor.outside_h",
        "delay_seconds": 30, "orientation": "s", "covers": ["cover.buero"],
        "cover_position_zero_means": "closed", "passage_door": False,
    })
    assert result["step_id"] == "add_references"
    assert result["description_placeholders"]["contact_position"] == "2"
    assert result["description_placeholders"]["contact_name"] == "Buero Window B"

    # Back from the second opening -> first opening again.
    result = await _configure(hass, result, {"wizard_back": True})
    assert result["description_placeholders"]["contact_position"] == "1"
    result = await _configure(hass, result, {
        "reference_temperature": "sensor.outside_t", "reference_humidity": "sensor.outside_h",
        "delay_seconds": 30, "orientation": "s", "cover_position_zero_means": "closed",
    })
    result = await _configure(hass, result, {"delay_seconds": 5, "orientation": "n", "cover_position_zero_means": "open", "passage_door": True})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Büro"
    created = result["data"]
    assert created[CONF_ROOM_GOAL_PRIORITIES] == ["co2", "humidity", "temperature"]
    assert created[CONF_CONTACT_REFERENCE_TEMPERATURES] == {WINDOW_A: "sensor.outside_t"}
    assert created[CONF_CONTACT_REFERENCE_HUMIDITIES] == {WINDOW_A: "sensor.outside_h"}
    assert created[CONF_CONTACT_ORIENTATIONS] == {WINDOW_A: "s", WINDOW_B: "n"}
    assert created[CONF_CONTACT_DELAYS] == {WINDOW_A: 30, WINDOW_B: 5}

    await hass.async_block_till_done()
    # The parent entry is updated only after HA committed the subentry; the new floor is added.
    assert [room["key"] for room in entry.data["rooms"]] == ["wohnzimmer", "buro"]
    assert entry.data["levels"] == ["EG", "OG"]
    assert any(sub.unique_id == "room:buro" for sub in entry.subentries.values())


async def test_single_goal_room_skips_goals_and_back_returns_to_create(hass, fast_commit_sleep) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    result = await _start(hass, entry, "create_room")
    result = await _configure(hass, result, _sections("Bad", contacts=[WINDOW_A], prefix="bad"))
    # Only "humidity" is available: goals page is skipped.
    assert result["step_id"] == "add_references"
    result = await _configure(hass, result, {"wizard_back": True})
    assert result["step_id"] == "create_room"
    result = await _configure(hass, result, _sections("Bad", contacts=[WINDOW_A], prefix="bad"))
    assert result["step_id"] == "add_references"
    result = await _configure(hass, result, {"delay_seconds": 0, "orientation": "e", "cover_position_zero_means": "closed"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ROOM_GOAL_PRIORITIES] == ["humidity"]
    await hass.async_block_till_done()
    assert entry.data["rooms"][0]["key"] == "bad"
    assert entry.data["levels"] == ["EG"]


async def test_commit_timeout_leaves_parent_untouched(hass, fast_commit_sleep) -> None:
    """Without an observable HA subentry commit the parent data is not mutated."""
    entry = _entry()
    entry.add_to_hass(hass)
    flow = _bound_flow(hass, entry, source=config_entries.SOURCE_USER)
    flow._working_room = cf._normalise_room(_sections("Keller", floor="UG", prefix="keller"), [])[0]
    flow._room_key = "keller"
    result = await flow.async_step_add_references()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["unique_id"] == "room:keller"
    await hass.async_block_till_done()
    # Nobody committed the CREATE_ENTRY result -> no ghost room, no new level.
    assert entry.data["rooms"] == []
    assert entry.data["levels"] == ["EG"]
    assert entry.subentries == {}


# ---------------------------------------------------------------------------
# Quick add: Home Assistant area import
# ---------------------------------------------------------------------------


async def test_import_ha_room_without_areas_reports_error(hass) -> None:
    entry = _entry([_room("kueche", "Küche")])
    entry.add_to_hass(hass)
    ar.async_get(hass).async_create("Küche")  # already configured -> skipped
    result = await _start(hass, entry, "import_ha_room")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "import_ha_room"
    assert result["errors"] == {"base": "no_ha_areas_to_import"}


async def test_import_ha_room_builds_suggestions_and_creates_room(hass, fast_commit_sleep) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    floor = fr.async_get(hass).async_create("Obergeschoss")
    area_reg = ar.async_get(hass)
    hass.states.async_set("sensor.area_pref_temperature", "21", {"device_class": "temperature"})
    office = area_reg.async_create("Arbeitszimmer", floor_id=floor.floor_id, temperature_entity_id="sensor.area_pref_temperature")
    attic = area_reg.async_create("Abstellraum")
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    device_entry = MockConfigEntry(domain="test")
    device_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(config_entry_id=device_entry.entry_id, identifiers={("test", "dev1")})
    device_reg.async_update_device(device.id, area_id=office.id)

    def _add(domain: str, uid: str, device_class: str | None, *, area: str | None = office.id, dev: str | None = None, disabled: bool = False):
        ent = entity_reg.async_get_or_create(
            domain, "test", uid, suggested_object_id=uid, device_id=dev,
            disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
        )
        if area:
            entity_reg.async_update_entity(ent.entity_id, area_id=area)
        if device_class:
            hass.states.async_set(ent.entity_id, "1", {"device_class": device_class})
        return ent.entity_id

    temp = _add("sensor", "office_temp", "temperature")
    hum = _add("sensor", "office_hum", "humidity", area=None, dev=device.id)  # area via device
    co2 = _add("sensor", "office_co2", "carbon_dioxide")
    lux = _add("sensor", "office_lux", "illuminance")
    window = _add("binary_sensor", "office_window", "window")
    climate = _add("climate", "office_climate", None)
    _add("sensor", "office_disabled", "temperature", disabled=True)
    _add("sensor", "office_power", "power")
    _add("sensor", "other_room_temp", "temperature", area=attic.id)

    flow = _bound_flow(hass, entry, source=config_entries.SOURCE_USER)
    choices, defaults = flow._quick_ha_area_defaults()
    assert choices == [
        {"value": attic.id, "label": "Abstellraum"},
        {"value": office.id, "label": "Obergeschoss · Arbeitszimmer"},
    ]
    office_defaults = defaults[office.id]
    assert office_defaults[CONF_ROOM_FLOOR] == "Obergeschoss"
    assert office_defaults[CONF_ROOM_TEMPERATURE] == ["sensor.area_pref_temperature", temp]
    assert office_defaults[CONF_ROOM_HUMIDITY] == [hum]
    assert office_defaults[CONF_ROOM_CO2] == co2
    assert office_defaults[CONF_ROOM_ILLUMINANCE] == lux
    assert office_defaults[CONF_ROOM_CLIMATE] == climate
    assert office_defaults[CONF_ROOM_CONTACTS] == [window]
    assert defaults[attic.id][CONF_ROOM_TEMPERATURE] == ["sensor.other_room_temp"]
    assert defaults[attic.id][CONF_ROOM_FLOOR] == "Unassigned"  # hass.config.language is "en" in tests

    result = await _start(hass, entry, "import_ha_room")
    assert result["step_id"] == "import_ha_room"
    assert result["errors"] == {}
    # A stale/unknown area id (bypassing the selector) re-shows the choice with an error.
    stale = await _bound_flow(hass, entry, source=config_entries.SOURCE_USER).async_step_import_ha_room({"area": "unknown_area"})
    assert stale["step_id"] == "import_ha_room"
    assert stale["errors"] == {"base": "select_ha_area"}
    result = await _configure(hass, result, {"area": office.id})
    assert result["step_id"] == "import_ha_room_details"
    assert result["description_placeholders"] == {"room_name": "Arbeitszimmer"}

    details = _sections("Arbeitszimmer", floor="Obergeschoss", contacts=[window], co2=co2, climate=climate, volume=None)
    result = await _configure(hass, result, details)
    assert result["step_id"] == "import_ha_room_details"
    assert result["errors"] == {"base": "room_volume_required"}

    details["geometry"] = {CONF_ROOM_VOLUME: 30.0}
    result = await _configure(hass, result, details)
    assert result["step_id"] == "add_goals"
    # Back from goals returns to the import details page, prefilled with the working room.
    result = await _configure(hass, result, {"wizard_back": True})
    assert result["step_id"] == "import_ha_room_details"
    result = await _configure(hass, result, details)
    assert result["step_id"] == "add_goals"
    result = await _configure(hass, result, {"goal_priority_1": "humidity", "goal_priority_2": "co2", "goal_priority_3": "temperature"})
    assert result["step_id"] == "add_references"
    result = await _configure(hass, result, {"delay_seconds": 0, "orientation": "w", "cover_position_zero_means": "closed"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Arbeitszimmer"
    await hass.async_block_till_done()
    assert entry.data["rooms"][0][CONF_ROOM_NAME] == "Arbeitszimmer"
    assert "Obergeschoss" in entry.data["levels"]


async def test_import_details_without_selected_area_falls_back_to_area_choice(hass) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Flur")
    flow = _bound_flow(hass, entry, source=config_entries.SOURCE_USER)
    result = await flow.async_step_import_ha_room_details()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "import_ha_room"
    assert [o["value"] for o in result["data_schema"].schema["area"].config["options"]] == [area.id]


async def test_native_reconfigure_is_not_offered(hass) -> None:
    sub = ConfigSubentryData(data=_room(), subentry_type="room", title="Wohnzimmer", unique_id="room:wohnzimmer")
    entry = _entry([_room()], subentries=[sub])
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    with pytest.raises(UnknownStep):
        await hass.config_entries.subentries.async_init(
            (entry.entry_id, "room"),
            context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": subentry_id},
        )


# ---------------------------------------------------------------------------
# Legacy room-edit steps (reconfigure context on a real subentry)
# ---------------------------------------------------------------------------


def _bound_flow(hass, entry, *, source: str, subentry_id: str | None = None) -> FreshAirIQRoomSubentryFlow:
    flow = FreshAirIQRoomSubentryFlow()
    flow.hass = hass
    flow.handler = (entry.entry_id, "room")
    flow.flow_id = "test_flow"
    flow.context = {"source": source}
    if subentry_id:
        flow.context["subentry_id"] = subentry_id
    return flow


class _Coordinator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def async_rebuild_listeners(self) -> None:
        self.calls.append("rebuild")

    async def async_request_refresh(self) -> None:
        self.calls.append("refresh")


def _reconfigure_setup(hass, room: dict, *, in_parent: bool = True, unique_id: str | None = "room:wohnzimmer"):
    sub = ConfigSubentryData(data=dict(room), subentry_type="room", title=room[CONF_ROOM_NAME], unique_id=unique_id)
    entry = _entry([room] if in_parent else [], subentries=[sub])
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    flow = _bound_flow(hass, entry, source=config_entries.SOURCE_RECONFIGURE, subentry_id=subentry_id)
    return entry, subentry_id, flow


async def test_legacy_basics_goals_and_save(hass) -> None:
    room = _room(**{CONF_ROOM_CONTACTS: [WINDOW_A, WINDOW_B], CONF_ROOM_CO2: "sensor.wz_co2",
                                   CONF_CONTACT_ORIENTATIONS: {WINDOW_A: "s", WINDOW_B: "n"},
                                   CONF_CONTACT_DELAYS: {WINDOW_A: 10, WINDOW_B: 20}})
    entry, subentry_id, flow = _reconfigure_setup(hass, room)
    coordinator = _Coordinator()
    entry.runtime_data = coordinator

    menu = await flow._async_step_reconfigure_legacy()
    assert menu["type"] is FlowResultType.MENU
    assert menu["menu_options"] == ["room_basics", "room_goals", "room_references", "save_room"]
    assert menu["description_placeholders"] == {"room_name": "Wohnzimmer"}

    form = await flow.async_step_room_basics()
    assert form["step_id"] == "room_basics"
    bad = _sections("Wohnzimmer", prefix="wohnzimmer", volume=None, contacts=[WINDOW_A], co2="sensor.wz_co2", floor="DG")
    form = await flow.async_step_room_basics(bad)
    assert form["errors"] == {"base": "room_volume_required"}
    good = _sections("Wohnzimmer neu", prefix="wohnzimmer", contacts=[WINDOW_A], co2="sensor.wz_co2", floor="DG")
    menu = await flow.async_step_room_basics(good)
    assert menu["type"] is FlowResultType.MENU
    await hass.async_block_till_done()
    persisted = entry.data["rooms"][0]
    assert persisted["key"] == "wohnzimmer"
    assert persisted[CONF_ROOM_NAME] == "Wohnzimmer neu"
    # Metadata of the removed contact is dropped, the remaining contact keeps it.
    assert persisted[CONF_CONTACT_ORIENTATIONS] == {WINDOW_A: "s"}
    assert persisted[CONF_CONTACT_DELAYS] == {WINDOW_A: 10}
    assert entry.data["levels"] == ["EG", "DG"]
    assert entry.subentries[subentry_id].title == "Wohnzimmer neu"
    assert coordinator.calls == ["rebuild", "refresh"]

    form = await flow.async_step_room_goals()
    assert form["step_id"] == "room_goals"
    menu = await flow.async_step_room_goals({"wizard_back": True})
    assert menu["step_id"] == "reconfigure"
    form = await flow.async_step_room_goals({"goal_priority_1": "bogus", "goal_priority_2": "co2"})
    assert form["errors"] == {"base": "invalid_goal_order"}
    menu = await flow.async_step_room_goals({"goal_priority_1": "co2", "goal_priority_2": "co2"})
    assert menu["step_id"] == "reconfigure"
    assert entry.data["rooms"][0][CONF_ROOM_GOAL_PRIORITIES] == ["co2", "humidity"]

    result = await flow.async_step_save_room()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[subentry_id].data[CONF_ROOM_GOAL_PRIORITIES] == ["co2", "humidity"]
    assert entry.data["rooms"][0][CONF_ROOM_FLOOR] == "DG"


async def test_legacy_single_goal_and_room_missing_from_parent(hass) -> None:
    """A subentry whose room is missing from parent data is restored on save."""
    room = _room("gast", "Gast", **{CONF_ROOM_FLOOR: "KG"})
    entry, subentry_id, flow = _reconfigure_setup(hass, room, in_parent=False, unique_id=None)

    menu = await flow.async_step_room_goals()
    assert menu["step_id"] == "reconfigure"
    assert entry.data["rooms"][0]["key"] == "gast"
    assert entry.data["rooms"][0][CONF_ROOM_GOAL_PRIORITIES] == ["humidity"]
    assert entry.data["levels"] == ["EG", "KG"]

    # No contacts: orientation/delay/reference pages go straight back to the menu.
    for step in (flow.async_step_room_orientations, flow.async_step_room_delays, flow.async_step_room_references):
        assert (await step())["step_id"] == "reconfigure"

    # Save path with the room absent from parent data appends it.
    entry2, _sid2, flow2 = _reconfigure_setup(hass, _room("dach", "Dach", **{CONF_ROOM_FLOOR: "DG"}), in_parent=False, unique_id="room:dach")
    result = await flow2.async_step_save_room()
    assert result["type"] is FlowResultType.ABORT
    assert [r["key"] for r in entry2.data["rooms"]] == ["dach"]
    assert entry2.data["levels"] == ["EG", "DG"]


async def test_legacy_orientations_delays_and_references(hass) -> None:
    room = _room(**{CONF_ROOM_CONTACTS: [WINDOW_A, WINDOW_B], CONF_CONTACT_DELAYS: {WINDOW_A: 15}})
    entry, subentry_id, flow = _reconfigure_setup(hass, room)

    form = await flow.async_step_room_orientations()
    assert form["step_id"] == "room_orientations"
    assert set(form["data_schema"].schema) == {WINDOW_A, WINDOW_B}
    await flow.async_step_room_orientations({WINDOW_A: "e"})
    assert entry.data["rooms"][0][CONF_CONTACT_ORIENTATIONS] == {WINDOW_A: "e", WINDOW_B: "unknown"}

    form = await flow.async_step_room_delays()
    assert form["step_id"] == "room_delays"
    defaults = {str(k): k.default() for k in form["data_schema"].schema}
    assert defaults == {WINDOW_A: 15, WINDOW_B: 0}
    await flow.async_step_room_delays({WINDOW_A: 999, WINDOW_B: "7"})
    assert entry.data["rooms"][0][CONF_CONTACT_DELAYS] == {WINDOW_A: 600, WINDOW_B: 7}

    form = await flow.async_step_room_references()
    assert form["step_id"] == "room_references"
    assert form["description_placeholders"]["contact_position"] == "1"
    form = await flow.async_step_room_references({"reference_humidity": "sensor.out_h", "delay_seconds": 0, "orientation": "e"})
    assert form["errors"] == {"base": "contact_reference_pair_required"}
    form = await flow.async_step_room_references({"reference_temperature": "sensor.out_t", "reference_humidity": "sensor.out_h", "delay_seconds": 3, "orientation": "e"})
    assert form["description_placeholders"]["contact_position"] == "2"
    menu = await flow.async_step_room_references({"delay_seconds": 4, "orientation": "w"})
    assert menu["step_id"] == "reconfigure"
    persisted = entry.data["rooms"][0]
    assert persisted[CONF_CONTACT_REFERENCE_TEMPERATURES] == {WINDOW_A: "sensor.out_t"}
    assert persisted[CONF_CONTACT_DELAYS] == {WINDOW_A: 3, WINDOW_B: 4}
    assert entry.subentries[subentry_id].data[CONF_CONTACT_ORIENTATIONS] == {WINDOW_A: "e", WINDOW_B: "w"}
