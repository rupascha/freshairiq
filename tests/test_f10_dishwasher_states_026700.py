"""0.26.7.0 F10 (release blocker): exact normalisation of dishwasher device states.

Error: "drying_complete" and "not_drying" were read as drying (substring "dry"); a finished or switched-off appliance
was announced as an active moisture source. Now states are normalised (case, spaces, hyphens, camelCase, enum paths)
and matched exactly; anything unknown says nothing. Active drying, completed drying, the door opening and the
after-evaporation are separate phases.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from custom_components.freshairiq.dishwasher import (
    AFTER_EVAPORATION, AFTER_EVAPORATION_MIN, DOOR_OPEN, DRYING, FINISHED, IDLE, WASHING, dishwasher_phase,
    effective_phase, normalize_state,
)
from custom_components.freshairiq.moisture_source import (
    DEVICE_AFTER_MESSAGE, DEVICE_DOOR_MESSAGE, DEVICE_DRYING_MESSAGE, update_moisture_source,
)

T0 = datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc)

POSITIVE = [
    # active drying
    ("Drying", DRYING), ("drying", DRYING), ("DRYING", DRYING), ("Dry", DRYING), ("eco_dry", DRYING), ("Eco Dry", DRYING),
    ("ecoDry", DRYING), ("AutoOpen", DRYING), ("auto-open", DRYING), ("Extra dry", DRYING), ("Trocknen", DRYING),
    ("Trocknung", DRYING), ("Trockenphase", DRYING), ("BSH.Common.EnumType.ProgramPhase.Drying", DRYING),
    # completed drying / programme end
    ("drying_complete", FINISHED), ("Drying complete", FINISHED), ("dryingComplete", FINISHED), ("drying-completed", FINISHED),
    ("drying_finished", FINISHED), ("Finished", FINISHED), ("finish", FINISHED), ("End", FINISHED), ("program_ended", FINISHED),
    ("Programme ended", FINISHED), ("done", FINISHED), ("Complete", FINISHED), ("Fertig", FINISHED), ("Programm beendet", FINISHED),
    ("Programmende", FINISHED), ("Trocknung beendet", FINISHED), ("BSH.Common.EnumType.OperationState.Finished", FINISHED),
    # door
    ("door_open", DOOR_OPEN), ("Door open", DOOR_OPEN), ("open", DOOR_OPEN), ("Tür offen", DOOR_OPEN), ("geöffnet", DOOR_OPEN),
    # washing
    ("Main wash", WASHING), ("main_dishwash", WASHING), ("Pre wash", WASHING), ("Rinse", WASHING), ("final_rinse", WASHING),
    ("Spülen", WASHING), ("Klarspülen", WASHING), ("Running", WASHING), ("run", WASHING), ("BSH.Common.EnumType.OperationState.Run", WASHING),
    ("preDrain", WASHING), ("heating", WASHING),
    # idle / switched off
    ("not_drying", IDLE), ("Not drying", IDLE), ("notDrying", IDLE), ("no_drying", IDLE), ("drying_off", IDLE), ("Off", IDLE),
    ("ready", IDLE), ("Inactive", IDLE), ("standby", IDLE), ("Bereit", IDLE), ("Aus", IDLE), ("not_running", IDLE),
    ("waiting_to_start", IDLE), ("DelayedStart", IDLE), ("Pause", IDLE), ("cancelled", IDLE), ("closed", IDLE),
]

NEGATIVE = [  # unknown: says nothing – never drying
    "unknown", "unavailable", "", None, "Strange", "pending", "dry_run_test", "drying?", "drying_error", "undrying",
    "predrying_check", "dried", "error", "failure", "service", "42", "on", "true", "drying complete now", "no",
]


@pytest.mark.parametrize(("state", "phase"), POSITIVE)
def test_text_states_are_matched_exactly(state, phase):
    assert dishwasher_phase("sensor.gs_phase", state) == phase
    assert dishwasher_phase("select.gs_programm", state) == phase


@pytest.mark.parametrize("state", NEGATIVE)
def test_unknown_states_say_nothing(state):
    assert dishwasher_phase("sensor.gs_phase", state) is None


@pytest.mark.parametrize("state", ["drying_complete", "Drying complete", "not_drying", "Not drying", "drying_off", "no_drying"])
def test_the_reported_error_is_no_drying_any_more(state):
    assert dishwasher_phase("sensor.gs_phase", state) != DRYING


def test_normalisation():
    assert normalize_state("  Drying-Complete ") == "drying_complete"
    assert normalize_state("dryingComplete") == "drying_complete"
    assert normalize_state("BSH.Common.EnumType.OperationState.Finished") == "finished"
    assert normalize_state(SimpleNamespace(state="Eco  Dry")) == "eco_dry"
    assert normalize_state(None) == ""


@pytest.mark.parametrize(("entity", "state", "attributes", "phase"), [
    ("binary_sensor.gs_trocknen", "on", {}, DRYING), ("binary_sensor.gs_trocknen", "off", {}, IDLE),
    ("binary_sensor.gs_tuer", "on", {"device_class": "door"}, DOOR_OPEN), ("binary_sensor.gs_tuer", "off", {"device_class": "door"}, IDLE),
    ("binary_sensor.gs_tuer", "on", {"device_class": "opening"}, DOOR_OPEN), ("switch.gs", "on", {}, DRYING),
    ("binary_sensor.gs", "unavailable", {}, None), ("binary_sensor.gs", "unknown", {"device_class": "door"}, None),
    ("binary_sensor.gs", "drying", {}, None),
])
def test_binary_signals(entity, state, attributes, phase):
    assert dishwasher_phase(entity, SimpleNamespace(state=state, attributes=attributes)) == phase


def test_after_evaporation_follows_drying_or_the_door_and_ends():
    mem: dict = {}
    assert effective_phase(mem, DRYING, T0) == DRYING
    assert effective_phase(mem, IDLE, T0 + timedelta(minutes=5)) == AFTER_EVAPORATION
    assert effective_phase(mem, FINISHED, T0 + timedelta(minutes=10)) == AFTER_EVAPORATION
    assert effective_phase(mem, None, T0 + timedelta(minutes=AFTER_EVAPORATION_MIN)) == AFTER_EVAPORATION
    assert effective_phase(mem, None, T0 + timedelta(minutes=AFTER_EVAPORATION_MIN + 1)) is None
    assert "dishwasher_release_at" not in mem
    effective_phase(mem, DOOR_OPEN, T0)
    assert effective_phase(mem, WASHING, T0 + timedelta(minutes=2)) == WASHING            # a new programme ends it
    assert effective_phase(mem, IDLE, T0 + timedelta(minutes=3)) == IDLE
    assert effective_phase({"dishwasher_release_at": "garbage"}, IDLE, T0) == IDLE


def _update(mem, minute, ah, phase):
    return update_moisture_source(mem, now=T0 + timedelta(minutes=minute), absolute_humidity_g_m3=ah, reference_ah_g_m3=6.0,
                                  temperature_c=21.0, volume_m3=30.0, window_open=False, learning_rate_per_min=0.03,
                                  airflow_factor=1.0, cross_ventilation=False, configured_sources=["dishwasher"],
                                  device_phase=phase)


@pytest.mark.parametrize("state", ["drying_complete", "not_drying", "Drying complete", "drying_off", "Strange", "unknown"])
def test_end_to_end_no_announced_source_for_finished_or_switched_off(state):
    mem: dict = {}
    for minute in range(4):
        result = _update(mem, minute, 9.0, dishwasher_phase("sensor.gs_phase", state))
    assert result["active"] is False and result["identified_source"] is None


def test_end_to_end_drying_and_door_are_announced_with_their_own_message():
    mem: dict = {}
    drying = _update(mem, 0, 9.0, dishwasher_phase("sensor.gs_phase", "Drying"))
    assert drying["active"] and drying["message"] == DEVICE_DRYING_MESSAGE
    mem = {}
    door = _update(mem, 0, 9.0, dishwasher_phase("binary_sensor.gs_tuer", SimpleNamespace(state="on", attributes={"device_class": "door"})))
    assert door["active"] and door["message"] == DEVICE_DOOR_MESSAGE and door["identified_source"] == "dishwasher"


def test_end_to_end_after_evaporation_names_a_measured_rise():
    mem: dict = {}
    _update(mem, 0, 9.0, DOOR_OPEN)
    state = None
    for minute in range(1, 9):                      # door closed again; the device says idle
        state = _update(mem, minute, 9.0, IDLE)
    assert state["active"] is False                  # quiet room: the source ends by its hysteresis
    for minute, ah in ((10, 9.6), (12, 10.4), (14, 11.2)):
        state = _update(mem, minute, ah, IDLE)       # still inside the after-evaporation window
    assert state["active"] is True and state["identified_source"] == "dishwasher" and state["message"] == DEVICE_AFTER_MESSAGE
