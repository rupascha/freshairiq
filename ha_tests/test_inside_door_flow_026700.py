"""0.26.7.0: 'Opening leads to' in the per-opening form – save, connected room, conflicts, pruning.

Real Home Assistant subentry flow plus the shared normalisation used by every config path.
"""
from __future__ import annotations

from custom_components.freshairiq.config_flow_rooms import _normalise_room
from custom_components.freshairiq.const import (
    CONF_CONTACT_CONNECTED_ROOMS,
    CONF_CONTACT_COVER_FOLLOW,
    CONF_CONTACT_COVERS,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_KINDS,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_PASSAGE_DOORS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_CONTACT_SIDES,
    CONF_ROOM_CONTACTS,
)
from custom_components.freshairiq.robustness import prepare_runtime_rooms
from ha_tests.test_cov_room_subentry_flow import (  # noqa: F401 - fixture re-export
    WINDOW_A, _configure, _entry, _room, _sections, _start, fast_commit_sleep,
)

DOOR = "binary_sensor.buero_tuer"
STEP = {"delay_seconds": 0, "orientation": "s", "cover_position_zero_means": "closed"}


async def _to_references(hass, entry, contacts):
    result = await _start(hass, entry, "create_room")
    result = await _configure(hass, result, _sections("Büro", contacts=contacts))
    if result["step_id"] == "add_goals":
        result = await _configure(hass, result, {"goal_priority_1": "humidity", "goal_priority_2": "co2", "goal_priority_3": "temperature"})
    assert result["step_id"] == "add_references"
    return result


async def test_inside_door_with_connected_room_is_saved_and_new_contacts_default_to_outside(hass, fast_commit_sleep) -> None:
    entry = _entry([_room()])
    entry.add_to_hass(hass)
    result = await _to_references(hass, entry, [WINDOW_A, DOOR])
    schema = result["data_schema"].schema
    side = next(k for k in schema if str(k) == "contact_side")
    assert side.default() == "outside"                                       # nothing changes unless the user says so
    room_field = next(k for k in schema if str(k) == "connected_room")
    assert [o["label"] for o in schema[room_field].config["options"]] == ["Wohnzimmer"]   # names, not keys; never itself
    result = await _configure(hass, result, {**STEP, "contact_side": "outside"})
    result = await _configure(hass, result, {**STEP, "contact_side": "inside", "connected_room": "wohnzimmer"})
    created = result["data"]
    assert created[CONF_CONTACT_SIDES] == {DOOR: "inside"}
    assert created[CONF_CONTACT_CONNECTED_ROOMS] == {DOOR: "wohnzimmer"}
    await hass.async_block_till_done()
    rooms, issues = prepare_runtime_rooms(entry.data["rooms"])
    buero = next(r for r in rooms if r["key"] == "buro")
    assert issues == [] and buero[CONF_ROOM_CONTACTS] == [WINDOW_A] and buero["_inside_contacts"] == [DOOR]


async def test_a_contact_classified_differently_in_another_room_is_refused(hass, fast_commit_sleep) -> None:
    entry = _entry([_room(contacts=[DOOR])])                                 # existing room: the door is an outside opening
    entry.add_to_hass(hass)
    result = await _to_references(hass, entry, [DOOR])
    result = await _configure(hass, result, {**STEP, "contact_side": "inside"})
    assert result["step_id"] == "add_references" and result["errors"] == {"base": "contact_side_conflict"}
    result = await _configure(hass, result, {**STEP, "contact_side": "outside"})
    assert CONF_CONTACT_SIDES not in result["data"] or result["data"][CONF_CONTACT_SIDES] == {}


ALL_META = (CONF_CONTACT_DELAYS, CONF_CONTACT_ORIENTATIONS, CONF_CONTACT_REFERENCE_TEMPERATURES, CONF_CONTACT_REFERENCE_HUMIDITIES,
            CONF_CONTACT_COVERS, CONF_CONTACT_PASSAGE_DOORS, CONF_CONTACT_KINDS, CONF_CONTACT_COVER_FOLLOW, CONF_CONTACT_SIDES,
            CONF_CONTACT_CONNECTED_ROOMS)


def _stored(**extra):
    room = {"key": "bad", "name": "Bad", "temperature": "sensor.t", "humidity": "sensor.h", "volume": 20, CONF_ROOM_CONTACTS: [WINDOW_A, DOOR],
            CONF_CONTACT_DELAYS: {WINDOW_A: 0, DOOR: 30}, CONF_CONTACT_ORIENTATIONS: {WINDOW_A: "s", DOOR: "n"},
            CONF_CONTACT_REFERENCE_TEMPERATURES: {DOOR: "sensor.rt"}, CONF_CONTACT_REFERENCE_HUMIDITIES: {DOOR: "sensor.rh"},
            CONF_CONTACT_COVERS: {DOOR: ["cover.x"]}, CONF_CONTACT_PASSAGE_DOORS: {WINDOW_A: False, DOOR: True},
            CONF_CONTACT_KINDS: {DOOR: "door"}, CONF_CONTACT_COVER_FOLLOW: {DOOR: True},
            CONF_CONTACT_SIDES: {DOOR: "inside"}, CONF_CONTACT_CONNECTED_ROOMS: {DOOR: "flur"}}
    room.update(extra)
    return room


def test_remove_save_reload_and_add_again_leaves_no_old_contact_setting_behind() -> None:
    form = {"name": "Bad", "temperature": "sensor.t", "humidity": "sensor.h", "volume": 20}
    stored = _stored()
    removed, errors = _normalise_room({**form, CONF_ROOM_CONTACTS: [WINDOW_A]}, [stored], keep_key="bad")
    assert errors == {} and all(DOOR not in removed[key] for key in ALL_META)
    reloaded = prepare_runtime_rooms([removed])[0][0]                         # what a restart reads
    assert reloaded[CONF_ROOM_CONTACTS] == [WINDOW_A] and reloaded["_inside_contacts"] == []
    again, _ = _normalise_room({**form, CONF_ROOM_CONTACTS: [WINDOW_A, DOOR]}, [removed], keep_key="bad")
    assert again[CONF_CONTACT_SIDES] == {} and again[CONF_CONTACT_CONNECTED_ROOMS] == {} and again[CONF_CONTACT_COVERS] == {}
    assert again[CONF_CONTACT_PASSAGE_DOORS][DOOR] is False and DOOR not in again[CONF_CONTACT_KINDS]
    assert prepare_runtime_rooms([again])[0][0][CONF_ROOM_CONTACTS] == [WINDOW_A, DOOR]      # back as an outside opening


def test_editing_a_room_keeps_every_valid_contact_setting_and_is_idempotent() -> None:
    form = {"name": "Bad", "temperature": "sensor.t", "humidity": "sensor.h", "volume": 20}
    stored = _stored()
    once, _ = _normalise_room({**form, CONF_ROOM_CONTACTS: [WINDOW_A, DOOR]}, [stored], keep_key="bad")
    for key in ALL_META:
        assert once[key] == stored[key], key
    twice, _ = _normalise_room({**form, CONF_ROOM_CONTACTS: [WINDOW_A, DOOR]}, [once], keep_key="bad")
    assert twice == once
    # a connected room pointing at the room itself, or set for an outside opening, is never kept
    odd, _ = _normalise_room({**form, CONF_ROOM_CONTACTS: [WINDOW_A, DOOR]},
                             [_stored(**{CONF_CONTACT_CONNECTED_ROOMS: {DOOR: "bad", WINDOW_A: "flur"}})], keep_key="bad")
    assert odd[CONF_CONTACT_CONNECTED_ROOMS] == {}


def test_configuration_without_the_setting_loads_unchanged_with_every_contact_outside() -> None:
    legacy = {k: v for k, v in _stored().items() if k not in (CONF_CONTACT_SIDES, CONF_CONTACT_CONNECTED_ROOMS)}
    rooms, issues = prepare_runtime_rooms([legacy])
    assert issues == [] and rooms[0][CONF_ROOM_CONTACTS] == [WINDOW_A, DOOR] and rooms[0]["_inside_contacts"] == []
    assert CONF_CONTACT_SIDES not in legacy                                  # the stored data itself is not touched


# ---------------------------------------------------------------- the same check in the other three contact pages
async def test_first_setup_page_refuses_a_conflicting_side_and_keeps_an_inside_door_without_a_named_room(hass) -> None:
    from custom_components.freshairiq import config_flow as c
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "more_rooms"})
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._rooms = [{"key": "flur", "name": "Flur", CONF_ROOM_CONTACTS: [DOOR]},
                   {"key": "bad", "name": "Bad", CONF_ROOM_CONTACTS: [DOOR, WINDOW_A]}]
    flow._pending_room_key = "bad"
    form = await flow.async_step_room_references({**STEP, "contact_side": "inside"})
    assert form["errors"] == {"base": "contact_side_conflict"}                 # the hall calls it an outside opening
    flow._rooms[0][CONF_CONTACT_SIDES] = {DOOR: "inside"}
    await flow.async_step_room_references({**STEP, "contact_side": "inside"})
    bad = flow._rooms[1]
    assert bad[CONF_CONTACT_SIDES] == {DOOR: "inside"} and bad[CONF_CONTACT_CONNECTED_ROOMS] == {}
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_options_page_refuses_a_conflicting_side(hass) -> None:
    from ha_tests.test_cov_options_flow import _entry as options_entry, _flow, _open, _room as options_room, _room_input, _submit
    from unittest.mock import patch
    entry = options_entry(rooms=[options_room(), options_room("Flur", key="flur", contacts=[DOOR])])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await _submit(hass, result, _room_input("Küche", "kueche", contacts=[DOOR]))
        if result["step_id"] == "room_goals":
            result = await _submit(hass, result, {"goal_priority_1": "humidity"})
        assert result["step_id"] == "contact_references"
        result = await _submit(hass, result, {**STEP, "contact_side": "inside"})
        assert result["errors"] == {"base": "contact_side_conflict"}
        assert _flow(hass, result) is not None


async def test_reconfigure_page_refuses_a_conflicting_side(hass) -> None:
    from ha_tests.test_cov_room_subentry_flow import _reconfigure_setup
    room = _room(**{CONF_ROOM_CONTACTS: [DOOR]})
    entry, _subentry_id, flow = _reconfigure_setup(hass, room)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [room, _room("flur", "Flur", **{CONF_ROOM_CONTACTS: [DOOR]})]})
    form = await flow.async_step_room_references({**STEP, "contact_side": "inside"})
    assert form["step_id"] == "room_references" and form["errors"] == {"base": "contact_side_conflict"}


# ---------------------------------------------------------------- U04: a connected room is never dropped silently
async def test_u04_a_connected_room_chosen_for_an_outside_opening_is_refused_with_an_explanation(hass, fast_commit_sleep) -> None:
    """U04: before, 'Outside' + a chosen room saved without the room and without a word; now the form explains it."""
    entry = _entry([_room()])
    entry.add_to_hass(hass)
    result = await _to_references(hass, entry, [WINDOW_A, DOOR])
    result = await _configure(hass, result, {**STEP, "contact_side": "outside", "connected_room": "wohnzimmer"})
    assert result["step_id"] == "add_references" and result["errors"] == {"base": "connected_room_outside"}
    result = await _configure(hass, result, {**STEP, "contact_side": "outside"})          # empty field: accepted
    result = await _configure(hass, result, {**STEP, "contact_side": "inside", "connected_room": "wohnzimmer"})
    assert result["data"][CONF_CONTACT_CONNECTED_ROOMS] == {DOOR: "wohnzimmer"}           # inside door: kept as before


async def test_u04_switching_a_named_inside_door_to_outside_keeps_working_on_every_contact_page(hass) -> None:
    """The prefilled room of a door that becomes an outside opening goes with the side change (no blocking error)."""
    from custom_components.freshairiq import config_flow as c
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "more_rooms"})
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._rooms = [{"key": "flur", "name": "Flur", CONF_ROOM_CONTACTS: [WINDOW_A]},
                   {"key": "bad", "name": "Bad", CONF_ROOM_CONTACTS: [DOOR], CONF_CONTACT_SIDES: {DOOR: "inside"},
                    CONF_CONTACT_CONNECTED_ROOMS: {DOOR: "flur"}}]
    flow._pending_room_key = "bad"
    form = await flow.async_step_room_references({**STEP, "contact_side": "outside", "connected_room": "kueche"})
    assert form["errors"] == {"base": "connected_room_outside"}                           # a different room: explained
    await flow.async_step_room_references({**STEP, "contact_side": "outside", "connected_room": "flur"})
    bad = flow._rooms[1]
    assert bad[CONF_CONTACT_SIDES] == {} and bad[CONF_CONTACT_CONNECTED_ROOMS] == {}
    hass.config_entries.flow.async_abort(result["flow_id"])


def test_u04_t01_t04_texts_are_present_in_german_and_english() -> None:
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"
    de = (base / "translations" / "de.json").read_text(encoding="utf-8")
    en = (base / "translations" / "en.json").read_text(encoding="utf-8")
    assert (base / "strings.json").read_text(encoding="utf-8") == en
    for text in ("Veraltetete", "Mindestens ein Kontakt offen", "anders eingestuft"):
        assert text not in de
    assert "Diese Einstellung dient nur der Kompatibilität mit älteren Versionen." in de                     # T01
    assert "Innentüren zählen nicht als Lüftungsauslöser." in de and "Inside doors do not trigger ventilation." in en   # T02
    assert de.count("Dieser Kontaktsensor ist in einem anderen Raum unterschiedlich eingestellt.") == 3       # T03
    assert en.count("This contact sensor is set up differently in another room.") == 3
    assert de.count("Wähle den Raum, den diese Innentür verbindet.") == 4 and en.count("Choose the room this inside door connects.") == 4  # T04
    for doc in (json.loads(de), json.loads(en)):
        for flow in ("config", "options"):
            assert "connected_room_outside" in doc[flow]["error"]
