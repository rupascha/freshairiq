"""Real-HA coverage for the initial setup flow and module-level config-flow helpers.

The legacy initial-flow room wizard (``room`` -> ``room_orientations`` ->
``room_references`` -> ``more_rooms``) is no longer offered from the ``user``
step since 0.24.14.0, but its steps are still registered ``async_step_*``
handlers. Home Assistant's flow manager starts a flow at the step named by
``context["source"]`` and then dispatches every ``async_configure`` call to the
step id of the last shown form, so these tests drive the wizard exactly as the
flow manager would (``async_init`` with ``source="room"`` etc.), including
schema validation of every submitted page.

Helpers whose only remaining callers live in the options/subentry flows are
exercised directly where the selector schema would reject the corrupt/legacy
input they are meant to tolerate (e.g. a string instead of a list).
"""
from __future__ import annotations

import math

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq import const as c


def _schema_keys(schema: vol.Schema) -> list[str]:
    return [str(key) for key in schema.schema]


def _schema_defaults(schema: vol.Schema) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in schema.schema:
        default = getattr(key, "default", vol.UNDEFINED)
        out[str(key)] = default() if callable(default) else default
    return out


# ---------------------------------------------------------------------------
# Initial setup flow (FreshAirIQConfigFlow)
# ---------------------------------------------------------------------------


async def test_legacy_import_step_without_legacy_entry_falls_back_to_empty_setup(hass) -> None:
    """Starting at ``legacy_import`` with no legacy entry creates an empty shell entry."""
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "legacy_import"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FreshAirIQ"
    assert result["data"] == {c.CONF_ROOMS: [], c.CONF_LEVELS: []}
    entry = hass.config_entries.async_entries(c.DOMAIN)[0]
    assert entry.unique_id == c.DOMAIN


async def test_legacy_import_migrates_single_contact_and_room_covers(hass) -> None:
    """Legacy single ``contact`` + room-wide covers migrate to per-opening data."""
    legacy = MockConfigEntry(
        domain=c.LEGACY_DOMAIN,
        data={
            c.CONF_OUTDOOR_WEATHER: "weather.legacy",
            c.CONF_ROOMS: [
                {
                    "key": "bath",
                    c.CONF_ROOM_NAME: "Bad",
                    c.CONF_ROOM_CONTACT: "binary_sensor.bath_window",
                    c.CONF_ROOM_COVERS: ["cover.bath"],
                    c.CONF_ROOM_TEMPERATURE: "sensor.bath_t",
                    c.CONF_ROOM_HUMIDITY: "sensor.bath_h",
                    c.CONF_CONTACT_DELAY: 30,
                },
                {"key": "store", c.CONF_ROOM_NAME: "Abstellraum", c.CONF_ROOM_CONTACT: ""},
            ],
        },
    )
    legacy.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "legacy_import"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"import_legacy": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    bath, store = result["data"][c.CONF_ROOMS]
    assert bath[c.CONF_ROOM_CONTACTS] == ["binary_sensor.bath_window"]
    assert c.CONF_ROOM_CONTACT not in bath
    assert bath[c.CONF_CONTACT_COVERS] == {"binary_sensor.bath_window": ["cover.bath"]}
    assert bath[c.CONF_CONTACT_DELAYS] == {"binary_sensor.bath_window": 30}
    assert bath[c.CONF_ROOM_FLOOR] == c.FLOOR_GROUND
    assert bath[c.CONF_ROOM_GOAL_PRIORITIES] == ["humidity"]
    assert store[c.CONF_ROOM_CONTACTS] == []
    assert store[c.CONF_CONTACT_COVERS] == {}
    assert result["data"][c.CONF_LEVELS] == [c.FLOOR_GROUND]
    entry = hass.config_entries.async_entries(c.DOMAIN)[0]
    titles = sorted(sub.title for sub in entry.subentries.values())
    assert titles == ["Abstellraum", "Bad"]
    assert {sub.unique_id for sub in entry.subentries.values()} == {"room:bath", "room:store"}


async def test_legacy_room_wizard_full_drive_creates_entry_with_room_subentries(hass) -> None:
    """Drive room -> orientations -> per-opening references -> more_rooms -> entry."""
    hass.states.async_set("binary_sensor.living_window", "off", {"friendly_name": "Wohnzimmerfenster"})

    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "room"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "room"
    assert result["description_placeholders"] == {"room_count": "1"}
    flow_id = result["flow_id"]

    # Active room with humidity only: temperature missing + no geometry.
    result = await hass.config_entries.flow.async_configure(flow_id, {
        c.CONF_ROOM_NAME: "  ",
        c.CONF_ROOM_HUMIDITY: ["sensor.living_h"],
    })
    assert result["step_id"] == "room"
    assert result["errors"] == {
        c.CONF_ROOM_TEMPERATURE: "required",
        "base": "room_volume_required",
        c.CONF_ROOM_NAME: "room_name_required",
    }

    # Temperature present, humidity missing, dimensions too small for an active room.
    result = await hass.config_entries.flow.async_configure(flow_id, {
        c.CONF_ROOM_NAME: "Wohnzimmer",
        c.CONF_ROOM_TEMPERATURE: ["sensor.living_t"],
        c.CONF_ROOM_LENGTH: 0.5, c.CONF_ROOM_WIDTH: 0.5, c.CONF_ROOM_HEIGHT: 1,
    })
    assert result["errors"] == {c.CONF_ROOM_HUMIDITY: "required", "base": "room_volume_too_small"}

    result = await hass.config_entries.flow.async_configure(flow_id, {
        c.CONF_ROOM_NAME: "Wohnzimmer",
        c.CONF_ROOM_TEMPERATURE: ["sensor.living_t"],
        c.CONF_ROOM_HUMIDITY: ["sensor.living_h"],
        c.CONF_ROOM_CO2: "sensor.living_co2",
        c.CONF_ROOM_CLIMATE: "climate.living",
        c.CONF_ROOM_CONTACTS: ["binary_sensor.living_window", "binary_sensor.living_door"],
        c.CONF_ROOM_LENGTH: 4, c.CONF_ROOM_WIDTH: 3, c.CONF_ROOM_HEIGHT: 2.5,
        c.CONF_ROOM_FLOOR: "Erdgeschoss",
        c.CONF_ROOM_MOISTURE_SOURCES: [c.MOISTURE_SOURCES[0]],
    })
    assert result["step_id"] == "room_orientations"
    assert result["description_placeholders"] == {"room_name": "Wohnzimmer"}
    assert _schema_keys(result["data_schema"]) == ["binary_sensor.living_window", "binary_sensor.living_door"]

    result = await hass.config_entries.flow.async_configure(flow_id, {
        "binary_sensor.living_window": "s", "binary_sensor.living_door": "n",
    })
    assert result["step_id"] == "room_references"
    placeholders = result["description_placeholders"]
    assert placeholders["contact_name"] == "Wohnzimmerfenster"
    assert placeholders["contact_entity"] == "binary_sensor.living_window"
    assert (placeholders["contact_position"], placeholders["contact_count"]) == ("1", "2")
    assert placeholders["room_name"] == "Wohnzimmer"

    # Temperature without humidity reference is refused.
    base_ref = {"delay_seconds": 15, "orientation": "s", "cover_position_zero_means": "closed"}
    result = await hass.config_entries.flow.async_configure(flow_id, {**base_ref, "reference_temperature": "sensor.hall_t"})
    assert result["step_id"] == "room_references"
    assert result["errors"] == {"base": "contact_reference_pair_required"}

    result = await hass.config_entries.flow.async_configure(flow_id, {
        **base_ref,
        "reference_temperature": "sensor.hall_t",
        "reference_humidity": "sensor.hall_h",
        "covers": ["cover.living", "cover.living"],
        "passage_door": False,
    })
    assert result["step_id"] == "room_references"
    # The second opening has no friendly name: readable entity-id fallback.
    assert result["description_placeholders"]["contact_name"] == "Living Door"
    assert result["description_placeholders"]["contact_position"] == "2"

    result = await hass.config_entries.flow.async_configure(flow_id, {
        "delay_seconds": 0, "orientation": "n", "cover_position_zero_means": "open", "passage_door": True,
    })
    assert result["step_id"] == "more_rooms"
    assert result["description_placeholders"] == {"room_count": "1"}

    result = await hass.config_entries.flow.async_configure(flow_id, {"add_another": True})
    assert result["step_id"] == "room"
    assert result["description_placeholders"] == {"room_count": "2"}

    # Passive rooms: incomplete or too-small geometry is still rejected.
    result = await hass.config_entries.flow.async_configure(flow_id, {
        c.CONF_ROOM_NAME: "Keller", c.CONF_ROOM_LENGTH: 3,
    })
    assert result["errors"] == {"base": "room_dimensions_incomplete"}
    result = await hass.config_entries.flow.async_configure(flow_id, {
        c.CONF_ROOM_NAME: "Keller", c.CONF_ROOM_LENGTH: 0.5, c.CONF_ROOM_WIDTH: 0.5, c.CONF_ROOM_HEIGHT: 1,
    })
    assert result["errors"] == {"base": "room_volume_too_small"}

    # A passive planning room without sensors/contacts/geometry is accepted and
    # skips the per-opening pages entirely.
    result = await hass.config_entries.flow.async_configure(flow_id, {
        c.CONF_ROOM_NAME: "Wohnzimmer", c.CONF_ROOM_TARGET_TEMPERATURE: 21,
    })
    assert result["step_id"] == "more_rooms"
    assert result["description_placeholders"] == {"room_count": "2"}

    result = await hass.config_entries.flow.async_configure(flow_id, {"add_another": False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    living, passive = result["data"][c.CONF_ROOMS]
    assert living["key"] == "wohnzimmer"
    assert living[c.CONF_ROOM_VOLUME] == 30.0
    assert living[c.CONF_ROOM_GOAL_PRIORITIES] == ["humidity", "co2", "temperature"]
    assert living[c.CONF_CONTACT_ORIENTATIONS] == {"binary_sensor.living_window": "s", "binary_sensor.living_door": "n"}
    assert living[c.CONF_CONTACT_REFERENCE_TEMPERATURES] == {"binary_sensor.living_window": "sensor.hall_t"}
    assert living[c.CONF_CONTACT_REFERENCE_HUMIDITIES] == {"binary_sensor.living_window": "sensor.hall_h"}
    assert living[c.CONF_CONTACT_COVERS] == {"binary_sensor.living_window": ["cover.living"]}
    assert living[c.CONF_CONTACT_DELAYS] == {"binary_sensor.living_window": 15, "binary_sensor.living_door": 0}
    assert living[c.CONF_CONTACT_PASSAGE_DOORS] == {"binary_sensor.living_window": False, "binary_sensor.living_door": True}
    assert living["cover_position_zero_means"] == "open"
    assert passive["key"] == "wohnzimmer_2"
    assert passive[c.CONF_ROOM_INCLUDE_CALCULATIONS] is False
    assert c.CONF_ROOM_VOLUME not in passive and c.CONF_ROOM_LENGTH not in passive
    assert passive[c.CONF_ROOM_GOAL_PRIORITIES] == ["temperature"]
    assert result["data"][c.CONF_LEVELS] == ["Erdgeschoss", "Unzugeordnet"]
    entry = hass.config_entries.async_entries(c.DOMAIN)[0]
    assert sorted(sub.unique_id for sub in entry.subentries.values()) == ["room:wohnzimmer", "room:wohnzimmer_2"]


async def test_legacy_room_wizard_reference_pages_without_pending_room_go_to_more_rooms(hass) -> None:
    """Opening/reference steps without a pending room fall through to ``more_rooms``."""
    for source in ("room_orientations", "room_references"):
        result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": source})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "more_rooms"
        assert result["description_placeholders"] == {"room_count": "0"}
        hass.config_entries.flow.async_abort(result["flow_id"])


async def test_room_references_uses_language_fallback_name_when_room_has_no_name(hass) -> None:
    """A pending room without a stored name uses the key in the reference page title."""
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "more_rooms"})
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._rooms = [{"key": "nameless", c.CONF_ROOM_CONTACTS: ["binary_sensor.x"]}]
    flow._pending_room_key = "nameless"
    form = await flow.async_step_room_references()
    assert form["step_id"] == "room_references"
    assert form["description_placeholders"]["room_name"] == "nameless"
    hass.config_entries.flow.async_abort(result["flow_id"])


def test_supported_subentry_types_and_options_flow_factory() -> None:
    entry = MockConfigEntry(domain=c.DOMAIN, data={})
    assert cf.FreshAirIQConfigFlow.async_get_supported_subentry_types(entry) == {"room": cf.FreshAirIQRoomSubentryFlow}
    assert isinstance(cf.FreshAirIQConfigFlow.async_get_options_flow(entry), cf.FreshAirIQOptionsFlow)


# ---------------------------------------------------------------------------
# Module helpers: tolerance for legacy/corrupt persisted values
# ---------------------------------------------------------------------------


def test_entity_list_and_number_parsing_tolerate_legacy_shapes() -> None:
    assert cf._entity_list("sensor.a") == ["sensor.a"]
    assert cf._entity_list("") == []
    assert cf._entity_list(("sensor.a", "", "sensor.a", "sensor.b")) == ["sensor.a", "sensor.b"]
    assert cf._entity_list(42) == []
    assert cf._number_or_none("2.5") == 2.5
    assert cf._number_or_none("abc") is None
    assert cf._number_or_none(object()) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("23:75", "23:15"), ("xx:yy", "07:00"), (25, "01:00"), ("abc", "07:00"), (None, "07:00")],
)
def test_time_default_normalises_hours(value, expected) -> None:
    assert cf._time_default(value, "07:00") == expected


def test_bounded_choice_and_language_helpers() -> None:
    assert cf._bounded(math.nan, 5, 1, 30) == 5
    assert cf._bounded(math.inf, 5, 1, 30) == 5
    assert cf._choice(None, "a", ["a", "b"]) == "a"

    class _NoConfig:
        pass

    assert cf._flow_language(_NoConfig()) == "de"
    assert cf._flow_language(None) == "de"
    assert cf._txt("en", "Raum", "Room") == "Room"
    assert cf._txt("de-AT", "Raum", "Room") == "Raum"
    assert cf._level_label("attic", "de") == "Dachgeschoss"
    assert cf._level_label("", "de") == "Nicht zugeordnet"
    assert cf._level_label("Unzugeordnet", "en") == "Unassigned"
    assert cf._level_options(["basement", "Hobby"], "de") == [
        {"value": "basement", "label": "Kellergeschoss"},
        {"value": "Hobby", "label": "Hobby"},
    ]


def test_goal_priority_schema_errors_and_move_ranking() -> None:
    room = {
        c.CONF_ROOM_HUMIDITY: "sensor.h", c.CONF_ROOM_TEMPERATURE: "sensor.t",
        c.CONF_ROOM_CO2: "sensor.co2", c.CONF_ROOM_TARGET_TEMPERATURE: 21,
        c.CONF_ROOM_GOAL_PRIORITIES: ["co2", "bogus"],
    }
    schema = cf._goal_priority_schema(room, include_back=True)
    assert _schema_keys(schema) == ["wizard_back", "goal_priority_1", "goal_priority_2", "goal_priority_3"]
    assert _schema_defaults(schema)["goal_priority_1"] == "co2"
    assert "wizard_back" not in _schema_keys(cf._goal_priority_schema(room))
    assert cf._goal_priority_schema({}).schema == {}

    # Unchanged submission keeps the order; empty submission returns current.
    assert cf._ranked_goal_priorities({}, room) == ["co2", "humidity", "temperature"]
    assert cf._ranked_goal_priorities({"goal_priority_1": "x"}, room) == ["co2", "humidity", "temperature"]
    # Moving "temperature" to slot 1 shifts the others (no duplicate error).
    moved = {"goal_priority_1": "temperature", "goal_priority_2": "humidity", "goal_priority_3": "temperature"}
    assert cf._ranked_goal_priorities(moved, room) == ["temperature", "humidity", "co2"]

    assert cf._goal_priority_errors(moved, room) == {}
    assert cf._goal_priority_errors({"goal_priority_1": "co2"}, room) == {"base": "invalid_goal_order"}
    assert cf._goal_priority_errors({"wizard_back": True}, room) == {}
    assert cf._goal_priority_errors({}, {}) == {}


async def test_contact_display_name_prefers_friendly_name(hass) -> None:
    hass.states.async_set("binary_sensor.kitchen_window", "off", {"friendly_name": " Küchenfenster "})
    assert cf._contact_display_name(hass, "binary_sensor.kitchen_window") == "Küchenfenster"
    assert cf._contact_display_name(None, "binary_sensor.bath-door_2") == "Bath Door 2"
    assert cf._contact_display_name(None, "___") == "___"


def test_apply_single_contact_reference_accepts_single_cover_string_and_clears_pair() -> None:
    room = {
        c.CONF_CONTACT_REFERENCE_TEMPERATURES: {"binary_sensor.w": "sensor.t"},
        c.CONF_CONTACT_REFERENCE_HUMIDITIES: {"binary_sensor.w": "sensor.h"},
        c.CONF_CONTACT_COVERS: {"binary_sensor.w": ["cover.old"]},
    }
    assert cf._apply_single_contact_reference(room, "binary_sensor.w", {"covers": "cover.new", "delay_seconds": 9999})
    assert room[c.CONF_CONTACT_REFERENCE_TEMPERATURES] == {}
    assert room[c.CONF_CONTACT_REFERENCE_HUMIDITIES] == {}
    assert room[c.CONF_CONTACT_COVERS] == {"binary_sensor.w": ["cover.new"]}
    assert room[c.CONF_CONTACT_DELAYS] == {"binary_sensor.w": 600}


def test_normalise_room_tolerates_legacy_string_values() -> None:
    room, errors = cf._normalise_room(
        {
            "identity": {c.CONF_ROOM_NAME: "Bad"},
            c.CONF_ROOM_CONTACTS: "binary_sensor.bath_window",
            c.CONF_ROOM_TEMPERATURE: ["sensor.t"],
            c.CONF_ROOM_HUMIDITY: ["sensor.h"],
            c.CONF_ROOM_VOLUME: 12,
            c.CONF_ROOM_MOISTURE_SOURCES: c.MOISTURE_SOURCES[0],
            c.CONF_ROOM_TEMPERATURE_AGGREGATION: "weird",
        },
        [],
    )
    assert errors == {}
    assert room[c.CONF_ROOM_CONTACTS] == ["binary_sensor.bath_window"]
    assert room[c.CONF_ROOM_MOISTURE_SOURCES] == [c.MOISTURE_SOURCES[0]]
    assert room[c.CONF_ROOM_TEMPERATURE_AGGREGATION] == "mean"
    assert room[c.CONF_ROOM_VOLUME] == 12.0

    _, errors = cf._normalise_room({c.CONF_ROOM_NAME: "X", c.CONF_ROOM_TEMPERATURE: ["t"], c.CONF_ROOM_HUMIDITY: ["h"], c.CONF_ROOM_VOLUME: 1}, [])
    assert errors == {c.CONF_ROOM_VOLUME: "room_volume_too_small"}
    _, errors = cf._normalise_room({c.CONF_ROOM_NAME: "X", c.CONF_ROOM_INCLUDE_CALCULATIONS: False, c.CONF_ROOM_VOLUME: 1}, [])
    assert errors == {c.CONF_ROOM_VOLUME: "room_volume_too_small"}


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (c.PROFILE_SUMMER_COOLING, ["cooling_start_temp_c", "cooling_min_outdoor_delta_c", "cooling_max_indoor_rh", "cooling_max_moisture_gain_5min_ml"]),
        (c.PROFILE_DEHUMIDIFY, ["min_return_next_5_min_ml", "max_temp_loss_next_5_min_c", "min_efficiency_ml_per_01c"]),
        (c.PROFILE_COMFORT, ["min_return_next_5_min_ml", "max_temp_loss_next_5_min_c", "min_efficiency_ml_per_01c"]),
    ],
)
def test_profile_details_schema_per_profile(profile, expected) -> None:
    current = {
        "operating_profile": profile, "cooling_start_temp_c": 24, "cooling_min_outdoor_delta_c": 2,
        "cooling_max_indoor_rh": 65, "cooling_max_moisture_gain_5min_ml": 50,
    }
    schema = cf._profile_details_schema(current)
    assert _schema_keys(schema) == expected
    if profile == c.PROFILE_DEHUMIDIFY:
        assert _schema_defaults(schema)["min_return_next_5_min_ml"] == 15.0
    if profile == c.PROFILE_COMFORT:
        assert _schema_defaults(schema)["min_return_next_5_min_ml"] == 25.0


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        (c.HEATING_HEAT_PUMP, ["electricity_price_per_kwh", "heat_pump_cop"]),
        (c.HEATING_GAS, ["gas_price_per_kwh", "gas_efficiency"]),
        (c.HEATING_OIL, ["oil_price_per_liter", "oil_kwh_per_liter", "oil_efficiency"]),
        (c.HEATING_DISTRICT, ["district_price_per_kwh", "district_efficiency"]),
        (c.HEATING_ELECTRIC, ["electricity_price_per_kwh"]),
    ],
)
def test_energy_details_schema_per_heating_system(system, expected) -> None:
    assert _schema_keys(cf._energy_details_schema({"heating_system": system})) == expected


def test_diagnostics_sharing_schema_defaults() -> None:
    schema = cf._diagnostics_sharing_schema({"diagnostics_consent": "granted"})
    defaults = _schema_defaults(schema)
    assert defaults == {
        "diagnostics_consent": "granted",
        "diagnostics_reporting_mode": "daily",
        "diagnostics_include_client_context": True,
    }


def test_resident_helpers_tolerate_corrupt_values() -> None:
    assert cf._resident_slot_overview({"adult_occupants": "many", "child_resident_names": "Mia"}, "de") == "Kind 1 = Mia"
    assert cf._resident_slot_overview({"adult_occupants": 1}, "en") == "Adult 1 = no name yet"
    assert cf._resident_profiles_dict({"adult:0": {"room_keys": ["a"]}, "bad": 1}) == {"adult:0": {"room_keys": ["a"]}}
    assert cf._resident_profiles_dict("{not json") == {}
    assert cf._resident_profiles_dict("[1, 2]") == {}
    assert cf._resident_profiles_dict('{"child:0": {"thermal_preference": "warm"}}') == {"child:0": {"thermal_preference": "warm"}}
