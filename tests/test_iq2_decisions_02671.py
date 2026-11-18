"""IQ2 (0.26.7.1): decisions, forecast quantities and time meaning – the mandatory regressions P1–P3 of the order.

P1 – photo case (two rooms, only "dehumidify", both goals reached): the rooms said "goals reached" while the house
     said "do not close yet", the main value was the target-limited 0 ml next to 148 ml, the house card showed a
     remaining time of an old plan.
P2 – C1: a goal reached in the same cycle as the temperature limit was lost afterwards.
P3 – C2: with critical CO₂ and more humid outdoor air the coach named "still drier air" instead of CO₂.
Every fixture is synthetic: the photos show neither the sensor values nor the source history, so the humidity,
temperature and weather values below are chosen test parameters – not a replay of a real session.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.freshairiq import iq2
from custom_components.freshairiq.close_wording import goal_close, protective_close
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.forecast import _boundary_at, horizon_forecast
from custom_components.freshairiq.iq2_runtime import update_goal_history
from custom_components.freshairiq.live_coach import _reassess_reason, refine_live_recommendation, room_time_fields
from custom_components.freshairiq.localize import to_english
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.notification_policy import effective_room_action
from custom_components.freshairiq.room_close_strategy import close_strategy, room_close_options
from custom_components.freshairiq.room_recommendation import _close_reason, _recommendation
from custom_components.freshairiq.storage_defaults import _room_defaults


# ------------------------------------------------------------------------------------------------ P1: photo case

def _golden():
    import sys
    from pathlib import Path
    tools = Path(__file__).resolve().parents[1] / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import coordinator_golden as golden  # noqa: PLC0415 – the harness installs its Home Assistant stub
    return golden


def _photo_chain(*, bath_rh=55.0, fitness_rh=54.0, later=7, minutes=14, strategy=None, rise=None) -> list[dict]:
    """Real coordinator chain: Badezimmer (31.2 m³) is opened first, Fitnessraum (37.8 m³) ``later`` minutes after it.

    Only goal: dehumidify to 58 %. Outdoor air 6 °C / 80 % (clearly drier). ``rise`` maps a minute to a bath humidity.
    """
    import asyncio
    from datetime import datetime

    golden = _golden()
    temp = {"device_class": "temperature", "unit_of_measurement": "°C"}
    hum = {"device_class": "humidity", "unit_of_measurement": "%"}
    rooms = [golden._room("bad", "Badezimmer", "ground_floor", temp=["sensor.bad_t"], hum=["sensor.bad_h"],
                          contacts=["binary_sensor.bad_f"], volume=31.2, sort=0),
             golden._room("fit", "Fitnessraum", "basement", temp=["sensor.fit_t"], hum=["sensor.fit_h"],
                          contacts=["binary_sensor.fit_f"], volume=37.8, sort=1)]
    for room in rooms:
        if strategy:
            room["close_strategy"] = strategy
    window = {"device_class": "window"}
    initial = {"sensor.aussen_t": (6.0, temp), "sensor.aussen_h": (80.0, hum), "sensor.bad_t": (21.0, temp),
               "sensor.bad_h": (bath_rh, hum), "sensor.fit_t": (19.9, temp), "sensor.fit_h": (fitness_rh, hum),
               "binary_sensor.bad_f": ("off", window), "binary_sensor.fit_f": ("off", window)}
    steps: list[dict] = [{"advance": 60, "label": "idle"}, {"advance": 60, "set": {"binary_sensor.bad_f": "on"}, "label": "bath"}]
    for i in range(minutes):
        change = {"sensor.bad_h": (rise or {}).get(i, round(bath_rh - 0.05 * i + (0.01 if i % 2 else 0.0), 2))}
        if i == later:
            change["binary_sensor.fit_f"] = "on"
        if i > later:
            change["sensor.fit_h"] = round(fitness_rh - 0.05 * (i - later) + (0.01 if i % 2 else 0.0), 2)
        steps.append({"advance": 60, "set": change})
    data = {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": rooms,
            "levels": ["basement", "ground_floor"]}
    scenario = {"start": datetime(2026, 11, 14, 18, 0, tzinfo=golden.TZ), "data": data, "steps": steps, "initial": initial,
                "options": {**golden.BASE_OPTIONS, "operating_profile": "dehumidify", "target_rh": 58, "min_duration_min": 3,
                            "max_duration_min": 20}}
    seen: list[dict] = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append(result)
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    try:
        asyncio.run(golden._run_scenario("iq2_photo", scenario, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return seen


def _elapsed(cycle: dict, key: str) -> float:
    return float(cycle["rooms"][key].get("session_elapsed_min") or 0.0)


@pytest.fixture(scope="module")
def photo():
    return _photo_chain()


def test_p1_reached_goals_close_room_house_and_notification_together(photo):
    aired = [c for c in photo if c["rooms"]["bad"].get("active")]
    for cycle in aired:
        room, rec = cycle["rooms"]["bad"], cycle["intelligent_recommendation"]
        if _elapsed(cycle, "bad") < 3.0:                                                 # the room's own minimum duration
            assert room["action"] == "Continue ventilating" and rec["kind"] == "continue"
            continue
        # the photo's contradiction: "goals reached" in the rooms, "do not close yet" for the house
        assert room["close_recommended"] and room["close_kind"] == "goals_reached"
        assert room["action"] == "Close" and room["house_aligned_action"] == "close", _elapsed(cycle, "bad")
        assert rec["kind"] == "close" and "bad" in rec["room_keys"]
        assert rec["live_coach_state"] == "close" and "weiter" not in str(rec["title"]).lower()
        assert effective_room_action(room, rec, cycle["rooms"]) == "Close"
        assert room["delta_g_m3"] > 0.4                                                  # the air is still clearly drier
    assert sum(1 for c in aired if _elapsed(c, "bad") < 3.0) == 3                        # not closed before, not by a clock


def test_p1_every_room_keeps_its_own_clock_and_no_old_plan_time_survives(photo):
    late = [c for c in photo if c["rooms"]["fit"].get("active")]
    assert late and [c["rooms"]["fit"]["time_state"] for c in late[:3]] == ["minimum"] * 3
    assert [c["rooms"]["fit"]["time_remaining_min"] for c in late[:3]] == [3.0, 2.0, 1.0]   # its own minimum, not the plan
    for cycle in late[:3]:
        fitness, rec = cycle["rooms"]["fit"], cycle["intelligent_recommendation"]
        assert fitness["action"] == "Continue ventilating" and rec["kind"] == "close" and rec["room_keys"] == ["bad"]
        assert effective_room_action(fitness, rec, cycle["rooms"]) != "Close"
        assert cycle["rooms"]["bad"]["time_state"] == "close" and cycle["rooms"]["bad"]["time_remaining_min"] == 0.0
    for cycle in late[3:]:
        assert cycle["rooms"]["fit"]["action"] == "Close" and cycle["rooms"]["fit"]["time_state"] == "close"
        assert sorted(cycle["intelligent_recommendation"]["room_keys"]) == ["bad", "fit"]
    for cycle in photo:                                                                 # rooms that are not aired: no time
        for room in cycle["rooms"].values():
            if not room.get("active"):
                assert room["time_state"] is None and room["time_remaining_min"] is None
    assert photo[-1]["remaining_duration_state"] in {"close", "overrun"}


def test_p1_forecast_quantities_stay_apart_in_rooms_and_house(photo):
    final = photo[-1]
    for key in ("bad", "fit"):
        room = final["rooms"][key]
        assert room["forecast_to_target_ml"] == 0                                        # the goal is reached …
        assert room["forecast_net_room_change_ml"] > 0                                   # … yet the air would still dry
        assert room["forecast_outdoor_transport_ml"] >= room["forecast_net_room_change_ml"]
        assert room["forecast_quality"]["state"] == "collecting" and room["forecast_interval_ml"] is None
        assert room["iq2"]["active"] is True and room["iq2"]["model"] == "iq2"
    assert final["forecast_net_room_change_ml"] == sum(final["rooms"][k]["forecast_net_room_change_ml"] for k in ("bad", "fit"))
    assert final["forecast_to_target_ml"] == 0
    assert final["forecast_quality_state"] == "collecting" and final["forecast_interval_ml"] is None    # unknown, not 100 %


def test_p1_fixed_values_zero_to_target_next_to_148_ml_modelled():
    """The photo's numbers as chosen parameters: 0 ml target-limited, 148 ml uncapped, −9.3 °C over 60 minutes."""
    args = dict(current_ah=8.0, source_ah=5.413, current_temp_c=20.0, source_temp_c=8.9, volume_m3=69.0, rate_per_min=0.03,
                airflow_bonus=1.0, horizon_min=60.0, target_ah=9.0, running=True, session_elapsed_min=10.0,
                session_fresh_measurements=6, max_duration_min=1e9, cap_positive_to_target=True)
    earlier = horizon_forecast(**args)                                                  # the model of 0.26.7.1 before IQ2
    assert earlier["moisture_effect_ml"] == 0 and earlier["target_limited"] is True
    assert earlier["uncapped_physical_moisture_effect_ml"] == pytest.approx(148, abs=2)
    assert earlier["temperature_change_c"] == pytest.approx(-9.3, abs=0.15)
    now = horizon_forecast(**args, moisture_air_share=0.5, thermal_air_share=0.15, anchor_ah=8.3, anchor_temp_c=20.4)
    assert now["to_target_ml"] == 0 and now["moisture_effect_ml"] == 0                    # "to the target": nothing left
    assert 0 < now["net_room_change_ml"] < 148                                           # main value: expected net change
    assert now["outdoor_transport_ml"] > now["net_room_change_ml"]                       # modelled transport is its own value
    assert -3.0 < now["temperature_change_c"] < -0.5                                     # room air ≠ outdoor air after an hour


def test_p1_just_above_the_goal_keeps_airing_and_names_no_remaining_time_of_an_old_plan():
    cycles = [c for c in _photo_chain(bath_rh=58.9, later=99, minutes=12, rise={i: 58.9 - 0.01 * (i % 2) for i in range(12)})
              if c["rooms"]["bad"].get("active")]
    assert all(c["rooms"]["bad"]["action"] == "Continue ventilating" and not c["rooms"]["bad"]["close_recommended"] for c in cycles)
    states = [c["rooms"]["bad"]["time_state"] for c in cycles]
    assert states[0] == "countdown" and states[-1] == "reassessing" and "close" not in states
    last = cycles[-1]
    assert last["rooms"]["bad"]["time_remaining_min"] is None and last["rooms"]["bad"]["forecast_to_target_ml"] > 0
    assert "Geplante Zeit erreicht" in last["intelligent_recommendation"]["live_coach_reason"]


def test_p1_goal_close_is_held_inside_the_hysteresis_and_lifted_above_it():
    """The humidity creeps up by 0.2 % per minute after the goal: held up to target + hysteresis (60 %), then reopened."""
    rise = {i: round(57.5 - 0.01 * (i % 2), 2) for i in range(6)} | {i: round(57.5 + 0.2 * (i - 5), 2) for i in range(6, 24)}
    cycles = [c for c in _photo_chain(bath_rh=57.5, later=99, minutes=24, rise=rise) if c["rooms"]["bad"].get("active")]
    seen = set()
    for cycle in cycles:
        minute = int(_elapsed(cycle, "bad"))
        if minute < 3:
            continue
        room, rh = cycle["rooms"]["bad"], rise[minute - 1]                               # the reading of this cycle
        if rh <= 58.0:
            assert (room["action"], room["close_kind"]) == ("Close", "goals_reached"), (minute, rh)
        elif rh <= 60.0:
            assert (room["action"], room["close_kind"]) == ("Close", "goals_held"), (minute, rh)
            assert "wurden in dieser Lüftung erreicht" in room["reason"] and cycle["intelligent_recommendation"]["kind"] == "close"
        else:
            assert room["action"] == "Continue ventilating" and not room["close_recommended"], (minute, rh)
            assert room["time_state"] == "reassessing" and cycle["intelligent_recommendation"]["kind"] == "continue"
        seen.add("reached" if rh <= 58.0 else "held" if rh <= 60.0 else "reopened")
    assert seen == {"reached", "held", "reopened"}


def test_p1_a_jump_in_humidity_during_the_airing_is_a_source_and_reopens_at_once():
    """Within the hysteresis band, but +2 % in one minute against clearly drier air: the source rule keeps its priority."""
    rise = {i: round(57.5 - 0.01 * (i % 2), 2) for i in range(6)} | {i: 59.5 + 0.01 * (i % 2) for i in range(6, 10)}
    cycles = [c for c in _photo_chain(bath_rh=57.5, later=99, minutes=10, rise=rise) if c["rooms"]["bad"].get("active")]
    assert cycles[5]["rooms"]["bad"]["close_kind"] == "goals_reached"
    final = cycles[-1]["rooms"]["bad"]
    assert final["action"] == "Continue ventilating" and "Feuchtequelle" in final["reason"]
    assert cycles[-1]["intelligent_recommendation"]["kind"] == "continue"


def test_p1_explicit_keep_drying_still_continues_while_the_air_helps():
    cycles = [c for c in _photo_chain(strategy="keep_drying", later=99, minutes=8) if c["rooms"]["bad"].get("active")]
    assert all(c["rooms"]["bad"]["action"] == "Continue ventilating" and c["intelligent_recommendation"]["kind"] == "continue"
               for c in cycles)


def test_goal_close_helper_is_narrow():
    assert goal_close({"close_recommended": True, "close_kind": "goals_reached"}) and goal_close({"close_recommended": True, "close_kind": "goals_held"})
    for room in ({"close_recommended": False, "close_kind": "goals_reached"}, {"close_recommended": True, "close_kind": "air_no_longer_helps"},
                 {"close_recommended": True, "close_kind": "temperature_limit"}, {"close_recommended": True}, None, "x"):
        assert not goal_close(room)
    assert protective_close({"close_recommended": True, "close_kind": "temperature_limit"})


# ------------------------------------------------------------------------------------------------ P1: model variants

DEHUMIDIFY = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "target_rh": 58.0, "min_duration_min": 3.0}
DEFAULT_ROOM = room_close_options(DEHUMIDIFY, {})                                        # nothing chosen = IQ2 default


def _bath(**extra) -> RoomInput:
    values = dict(key="bad", name="Badezimmer", temperature=21.0, humidity=55.0, reference_temperature=6.0, reference_humidity=80.0,
                  volume_m3=31.2, contact_open=True, contact_open_seconds=600, session_active=True, session_elapsed_min=10.0,
                  session_fresh_measurements=6)
    values.update(extra)
    return RoomInput(**values)


def test_default_goal_close_needs_fresh_confirmed_readings_and_no_source():
    assert evaluate_room(_bath(), DEFAULT_ROOM, False).close_kind == "goals_reached"
    for blocked in (_bath(session_fresh_measurements=0), _bath(measurements_stale=True), _bath(session_elapsed_min=2.0, contact_open_seconds=120),
                    _bath(humidity=58.4), _bath(moisture_source_active=True, moisture_source_label="Dusche")):
        result = evaluate_room(blocked, DEFAULT_ROOM, False)
        assert result.close_kind not in {"goals_reached", "goals_held"}, blocked


def test_target_limited_zero_alone_never_closes():
    """Chapter 1 of the order: a displayed 0 ml "to the target" is no proof that airing is useless."""
    keep = room_close_options(DEHUMIDIFY, {"close_strategy": "keep_drying"})
    result = evaluate_room(_bath(), keep, False)
    assert result.action == "Continue ventilating" and not result.close_recommended


def test_default_and_migration_of_the_close_strategy():
    assert close_strategy({}) == "goals_reached"
    assert close_strategy({"close_strategy": "continue_while_drying"}) == "goals_reached"   # stored former default: no choice
    assert close_strategy({"close_strategy": "keep_drying"}) == "keep_drying"               # deliberate choice
    assert close_strategy({"close_strategy": "nonsense"}) == close_strategy({"close_strategy": None}) == "goals_reached"
    assert room_close_options({"a": 1}, {})["room_close_on_goals"] is True
    assert room_close_options({"a": 1}, {"close_strategy": "keep_drying"})["room_close_on_goals"] is False
    source = {"a": 1}
    assert room_close_options(source, {}) is not source and "room_close_on_goals" not in source


# ------------------------------------------------------------------------------------------------ P2: C1

C1_OPTIONS = room_close_options({**DEFAULT_OPTIONS, "target_rh": 58.0, "min_duration_min": 5.0, "airing_min_room_temp_c": 16.0},
                                {"close_strategy": "goals_reached"})


def _c1_trace(steps, memory: dict | None = None):
    """The model with the coordinator's stored fields (close_notified, its cause, the goal history of the airing)."""
    base = RoomInput(key="bad", name="Bad", temperature=20.0, humidity=61.0, reference_temperature=0.7, reference_humidity=92.0,
                     volume_m3=9.4, contact_open=True, contact_open_seconds=300, session_active=True, session_elapsed_min=5.0,
                     session_fresh_measurements=6)
    mem = memory if memory is not None else {k: _room_defaults()[k] for k in ("close_notified", "close_notified_kind", "session_goals_reached")}
    out = []
    for minute, (temp, rh) in enumerate(steps, start=5):
        result = evaluate_room(replace(base, temperature=temp, humidity=rh, session_elapsed_min=float(minute), contact_open_seconds=minute * 60,
                                       close_notified=bool(mem["close_notified"]), close_notified_kind=mem["close_notified_kind"],
                                       session_goals_reached=bool(mem["session_goals_reached"])), C1_OPTIONS, False)
        stored, kind = mem["close_notified_kind"], result.close_kind
        mem["close_notified"] = result.close_recommended
        mem["close_notified_kind"] = ((kind if stored is None or kind == "goals_reached" else stored) if result.close_recommended else None)
        update_goal_history(mem, result)
        out.append(result)
    return out, mem


def test_p2_goal_reached_together_with_the_temperature_limit_is_not_lost():
    trace, mem = _c1_trace([(20.0, 61.0), (15.0, 57.0), (17.0, 59.0)])
    assert [(r.action, r.close_kind) for r in trace] == [
        ("Continue ventilating", None), ("Close", "temperature_limit"), ("Close", "goals_held")]
    assert trace[1].goals_reached_now is True                                           # both facts are kept apart
    assert "Temperaturgrenze" in _close_reason(trace[1], C1_OPTIONS) and "wurden in dieser Lüftung erreicht" in _close_reason(trace[2], C1_OPTIONS)
    assert mem["session_goals_reached"] is True and mem["close_notified_kind"] == "temperature_limit"
    control, _ = _c1_trace([(20.0, 61.0), (17.0, 57.0), (17.0, 59.0)])
    assert [r.close_kind for r in control] == [None, "goals_reached", "goals_held"]
    assert trace[2].delta_g_m3 == control[2].delta_g_m3 == pytest.approx(3.84, abs=0.01)


def test_p2_the_history_ends_with_a_real_reopening_and_a_never_reached_goal_is_never_claimed():
    trace, mem = _c1_trace([(20.0, 61.0), (15.0, 57.0), (17.0, 59.0), (17.0, 60.5), (17.0, 59.0)])
    assert trace[3].action == "Continue ventilating" and mem["session_goals_reached"] is False     # above the hysteresis
    assert trace[4].close_kind is None                                                  # 59 % alone is no reached goal
    never, mem = _c1_trace([(20.0, 65.0), (19.0, 63.0), (17.0, 61.0), (15.0, 59.0), (14.9, 59.0), (17.0, 59.0)])    # B3
    assert never[4].close_kind == "temperature_limit" and never[5].close_kind != "goals_held"
    assert mem["session_goals_reached"] is False


def test_p2_restore_keeps_the_history_and_old_stores_claim_nothing():
    defaults = _room_defaults()
    assert defaults["session_goals_reached"] is False and defaults["close_notified_kind"] is None
    # restart in the middle of the airing: the stored fields are all the model needs
    _, mem = _c1_trace([(20.0, 61.0), (15.0, 57.0)])
    restored = dict(mem)
    after, _ = _c1_trace([(17.0, 59.0)], restored)
    assert after[0].close_kind == "goals_held"
    # a store written before IQ2 has no goal history: a temperature close stays a temperature close
    old = {"close_notified": True, "close_notified_kind": "temperature_limit", "session_goals_reached": False}
    assert _c1_trace([(17.0, 59.0)], old)[0][0].close_kind != "goals_held"
    from custom_components.freshairiq import storage
    import inspect
    assert '"session_goals_reached"' in inspect.getsource(storage)                       # kept for a running airing


# ------------------------------------------------------------------------------------------------ P3: C2

C2_OPTIONS = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "target_rh": 58.0, "min_duration_min": 5.0,
              "co2_warn": 1000.0, "co2_critical": 1400.0}


def _c2(co2=1600.0, **extra):
    room = RoomInput(key="w", name="W", temperature=20.0, humidity=40.0, reference_temperature=18.0, reference_humidity=60.0,
                     volume_m3=48.3, contact_open=True, contact_open_seconds=3600, session_active=True, session_elapsed_min=60.0,
                     session_fresh_measurements=6, co2=co2, session_start_temp=20.4)
    result = evaluate_room(room, C2_OPTIONS, False)
    action, _reason, _reasons = _recommendation(result, C2_OPTIONS, pollen=0.0, co2=co2, airflow=1.0, wind_bearing=None, wind_speed=None)
    payload = result.as_dict() | {"key": "w", "name": "W", "action": action, "active": True, "opening_state": "open",
                                  "calculation_enabled": True, "session_elapsed_min": 60.0, "session_recommended_duration_min": 20.0,
                                  "temperature_change_c": -0.4, "co2": co2, "goal_state": {"hard_close": False, "goals": []}, **extra}
    rec = refine_live_recommendation({"w": payload}, C2_OPTIONS, {"kind": "continue", "room_keys": ["w"], "duration_min": 20.0})
    return result, action, rec


def test_p3_critical_co2_is_named_and_more_humid_air_is_not_called_drier():
    result, action, rec = _c2()
    assert action == "Continue ventilating" and result.delta_g_m3 == pytest.approx(-2.3, abs=0.05)
    assert result.moisture_effect_next_5_min_ml < 0                                      # moisture comes in
    reason = rec["live_coach_reason"]
    assert reason == ("Geplante Zeit erreicht; weitergelüftet wird wegen CO₂ (1600 ppm, kritisch ab 1400 ppm); "
                      "die Außenluft ist 2.3 g/m³ feuchter als die Raumluft und entfeuchtet gerade nicht; "
                      "Raum -0.4 °C seit Start – FreshAirIQ bewertet jeden Zyklus neu")
    assert "trockener" not in reason and rec["kind"] == "continue"
    english = to_english(reason)
    assert "CO₂ (1600 ppm, critical from 1400 ppm)" in english and "more humid" in english
    assert not any(word in english for word in ("Geplante", "Außenluft", "weitergelüftet", "bewertet"))


def _reason(rooms, next5=0.0, options=C2_OPTIONS):
    return _reassess_reason(rooms, next5, options)


def test_p3_every_reason_that_keeps_a_window_open_is_named_truthfully():
    drier = {"delta_g_m3": 3.1, "temperature_change_c": -1.2}
    assert _reason([drier], 41.6) == ("Geplante Zeit erreicht; die Außenluft ist noch 3.1 g/m³ trockener (nächste 5 min etwa 42 ml); "
                                      "Raum -1.2 °C seit Start – FreshAirIQ bewertet jeden Zyklus neu")
    open_goal = {"delta_g_m3": 3.1, "co2": 1150.0, "goal_state": {"goals": [{"id": "co2", "active": True, "reached": False}]}}
    assert "weitergelüftet wird wegen CO₂ (1150 ppm, Freigabe unter" in _reason([open_goal], 10.0)
    reached = {"delta_g_m3": 3.1, "co2": 700.0, "goal_state": {"goals": [{"id": "co2", "active": True, "reached": True}, "x"]}}
    assert "CO₂" not in _reason([reached], 10.0)
    assert "CO₂" not in _reason([{"delta_g_m3": 3.1, "co2": None, "co2_available": False, "goal_state": "broken"}], 10.0)   # no sensor
    cooling = {"delta_g_m3": -1.0, "comfort_cooling_active": True}
    assert "weitergelüftet wird zum Kühlen; die Außenluft ist 1.0 g/m³ feuchter" in _reason([cooling])
    source = {"delta_g_m3": 2.0, "moisture_source_active": True}
    assert "eine Feuchtequelle ist noch aktiv; die Außenluft ist noch 2.0 g/m³ trockener" in _reason([source], -3.0)
    assert "(nächste 5 min etwa 0 ml)" in _reason([source], -3.0)                         # never a negative "removal"
    # several rooms: CO₂ of one room is the reason, the driest path the fact; no temperature without a measurement
    both = _reason([{"delta_g_m3": -0.5, "co2": 1500.0}, {"delta_g_m3": 1.4}], 12.0)
    assert "wegen CO₂ (1500 ppm, kritisch ab 1400 ppm)" in both and "noch 1.4 g/m³ trockener" in both and "seit Start" not in both
    assert _reason([]) == ("Geplante Zeit erreicht; die Außenluft ist 0.0 g/m³ feuchter als die Raumluft und entfeuchtet gerade nicht"
                           " – FreshAirIQ bewertet jeden Zyklus neu")
    for text in (_reason([drier], 41.6), _reason([open_goal], 10.0), _reason([cooling]), _reason([source], -3.0)):
        english = to_english(text)
        assert not any(word in english for word in ("Geplante", "Außenluft", "weitergelüftet", "Feuchtequelle", "seit Start", "bewertet")), english


# ------------------------------------------------------------------------------------------------ time meaning

def _aired(**extra):
    return {"active": True, "open": True, "opening_state": "open", "data_quality": "ok", "action": "Continue ventilating",
            "session_elapsed_min": 10.0, **extra}


def test_room_time_state_has_one_meaning_per_room():
    rooms = {
        "close": _aired(action="Close"),
        "late": _aired(session_elapsed_min=1.0),
        "long": _aired(session_elapsed_min=40.0),
        "idle": {"active": False, "data_quality": "ok", "time_state": "stale", "time_remaining_min": 7.0},
        "bad_data": _aired(data_quality="missing"),
        "junk": "x",
    }
    room_time_fields(rooms, {"remaining_duration_state": "countdown", "remaining_duration_min": 2.0}, 5.0)
    assert (rooms["close"]["time_state"], rooms["close"]["time_remaining_min"]) == ("close", 0.0)
    assert (rooms["late"]["time_state"], rooms["late"]["time_remaining_min"]) == ("countdown", 4.0)    # its own minimum is longer
    assert (rooms["long"]["time_state"], rooms["long"]["time_remaining_min"]) == ("countdown", 2.0)
    assert (rooms["idle"]["time_state"], rooms["idle"]["time_remaining_min"]) == (None, None)
    assert (rooms["bad_data"]["time_state"], rooms["bad_data"]["time_remaining_min"]) == (None, None)
    room_time_fields(rooms, {"remaining_duration_state": "reassessing", "remaining_duration_min": 7.0}, 5.0)   # old plan time ignored
    assert (rooms["late"]["time_state"], rooms["late"]["time_remaining_min"]) == ("minimum", 4.0)
    assert (rooms["long"]["time_state"], rooms["long"]["time_remaining_min"]) == ("reassessing", None)
    room_time_fields(rooms, {"remaining_duration_state": "countdown", "remaining_duration_min": 0.0}, 5.0)
    assert rooms["long"]["time_state"] == "reassessing"
    room_time_fields(rooms, None, 5.0)
    assert rooms["long"]["time_state"] == "reassessing" and rooms["close"]["time_state"] == "close"
    room_time_fields(None, None, 5.0)                                                   # nothing to do, nothing raised


# ------------------------------------------------------------------------------------------------ forecast

FORECAST = dict(current_ah=9.0, source_ah=5.0, current_temp_c=20.0, source_temp_c=5.0, volume_m3=48.3, rate_per_min=0.03,
                airflow_bonus=1.0, max_duration_min=1e9)


@pytest.mark.parametrize("minutes", [5, 10, 15, 20, 30, 60])
def test_forecast_uses_the_same_physics_as_the_learning(minutes):
    plain = horizon_forecast(**FORECAST, horizon_min=minutes)
    assert plain["net_room_change_ml"] == pytest.approx(4.0 * 48.3 * iq2.net_fraction(0.03, minutes), abs=1.5)
    assert plain["outdoor_transport_ml"] == pytest.approx(plain["net_room_change_ml"], abs=1.5)      # no buffer: the same
    assert plain["to_target_ml"] is None                                                # no target given: unknown, not 0
    buffered = horizon_forecast(**FORECAST, horizon_min=minutes, moisture_air_share=0.5, thermal_air_share=0.15)
    assert buffered["net_room_change_ml"] == pytest.approx(4.0 * 48.3 * iq2.net_fraction(0.03, minutes, 1.0, 0.5), abs=1.5)
    assert buffered["net_room_change_ml"] <= plain["net_room_change_ml"] <= buffered["outdoor_transport_ml"] + 1.5
    assert abs(buffered["temperature_change_c"]) < abs(plain["temperature_change_c"])


def test_forecast_net_change_is_bounded_and_monotone_at_steady_conditions():
    previous = 0.0
    for minutes in (5, 10, 15, 20, 30, 45, 60, 90, 120):
        value = horizon_forecast(**FORECAST, horizon_min=minutes, moisture_air_share=0.5)["net_room_change_ml"]
        assert previous <= value <= 0.5 * 4.0 * 48.3 + 1.0
        previous = value


def test_forecast_reversal_zero_difference_and_target_quantities():
    wetter = horizon_forecast(**{**FORECAST, "source_ah": 11.0}, horizon_min=15, moisture_air_share=0.5)
    assert wetter["net_room_change_ml"] < 0 and wetter["outdoor_transport_ml"] < 0       # moisture comes in: negative
    same = horizon_forecast(**{**FORECAST, "source_ah": 9.0}, horizon_min=15)
    assert same["net_room_change_ml"] == 0 and same["outdoor_transport_ml"] == 0
    still = horizon_forecast(**{**FORECAST, "rate_per_min": 0.0}, horizon_min=15)
    assert still["net_room_change_ml"] == 0
    above = horizon_forecast(**FORECAST, horizon_min=15, target_ah=8.5, cap_positive_to_target=True, moisture_air_share=0.5)
    assert above["to_target_ml"] == round(0.5 * 48.3) and above["moisture_effect_ml"] <= above["to_target_ml"]
    assert above["net_room_change_ml"] > above["moisture_effect_ml"]                     # the target limit is its own value


def test_weather_change_inside_the_hour_but_not_inside_five_minutes():
    """The outdoor air turns humid after 30 minutes: the 5-minute value is untouched, the hour is not extrapolated."""
    boundaries = {m: {"absolute_humidity": 5.0 if m <= 30 else 10.5, "temperature_c": 5.0 if m <= 30 else 9.0, "confidence": 70}
                  for m in range(5, 65, 5)}
    steady5 = horizon_forecast(**FORECAST, horizon_min=5, moisture_air_share=0.5)
    change5 = horizon_forecast(**FORECAST, horizon_min=5, moisture_air_share=0.5, future_source_boundaries=boundaries)
    assert change5["net_room_change_ml"] == steady5["net_room_change_ml"]
    steady60 = horizon_forecast(**FORECAST, horizon_min=60, moisture_air_share=0.5)
    change60 = horizon_forecast(**FORECAST, horizon_min=60, moisture_air_share=0.5, future_source_boundaries=boundaries)
    change30 = horizon_forecast(**FORECAST, horizon_min=30, moisture_air_share=0.5, future_source_boundaries=boundaries)
    assert change60["net_room_change_ml"] < steady60["net_room_change_ml"]
    assert change60["net_room_change_ml"] < change30["net_room_change_ml"]               # no forced monotony with changing weather
    assert change60["future_weather_used"] is True and steady60["future_weather_used"] is False


def test_boundary_points_are_validated():
    assert _boundary_at(None, 5.0, 4.0, 15) == (5.0, 4.0, None)
    assert _boundary_at({15: "x"}, 5.0, 4.0, 15) == (5.0, 4.0, None)
    assert _boundary_at({15: {"absolute_humidity": "x"}}, 5.0, 4.0, 15) == (5.0, 4.0, None)
    assert _boundary_at({15: {"absolute_humidity": 99.0, "temperature_c": 3.0}}, 5.0, 4.0, 15) == (5.0, 4.0, None)
    assert _boundary_at({15: {"absolute_humidity": 6.0, "temperature_c": 3.0, "confidence": "70"}}, 5.0, 4.0, 14.6) == (6.0, 3.0, 70)
    assert _boundary_at({15: {"absolute_humidity": 6.0, "temperature_c": 3.0, "confidence": "x"}}, 5.0, 4.0, 15) == (6.0, 3.0, None)
    assert _boundary_at({15: {"absolute_humidity": 6.0}}, 5.0, 4.0, 15) == (6.0, 4.0, None)
