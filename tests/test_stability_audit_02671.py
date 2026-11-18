"""Stability audit 0.26.7.1: confirmed findings I01–I05 and F06–F16 with their counter cases.

Every fixture is synthetic; the numbers reproduce the findings of the audit, not a recorded household.
"""
from __future__ import annotations

import asyncio
import copy
import itertools
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import coordinator_golden as golden  # noqa: E402,F401 – installs the Home Assistant stub of the golden harness
from golden import ha_stub  # noqa: E402

if not hasattr(sys.modules["homeassistant.core"], "Event"):                              # what the controller imports beyond
    sys.modules["homeassistant.core"].Event = object                                     # the golden stub
if not hasattr(sys.modules["homeassistant.helpers.event"], "async_track_time_change"):
    sys.modules["homeassistant.helpers.event"].async_track_time_change = lambda *a, **k: (lambda: None)

from custom_components.freshairiq import iq2, iq2_runtime  # noqa: E402
from custom_components.freshairiq.actuator_control import (  # noqa: E402
    COVER_COMMAND_ATTEMPTS, COVER_OPEN, CoverSetup, CoverView, combine_cover_setups, cover_command_result, decide_cover, own_fans)
from custom_components.freshairiq.actuator_controller import ActuatorController  # noqa: E402
from custom_components.freshairiq.const import CONF_ROOM_VOLUME  # noqa: E402
from custom_components.freshairiq.coordinator_session_validation import SessionValidationMixin  # noqa: E402
from custom_components.freshairiq.coordinator_sessions import SessionFinishMixin  # noqa: E402
from custom_components.freshairiq.climate_sources import aggregate_states, celsius  # noqa: E402
from custom_components.freshairiq.coordinator_contacts import _orientation_factor  # noqa: E402
from custom_components.freshairiq.coordinator_sources import _float_state, _temperature_state, _weather_values, _weather_wind  # noqa: E402
from custom_components.freshairiq import notifications  # noqa: E402
from custom_components.freshairiq.forecast import elapsed_minutes, horizon_forecast, night_interval_bounds, overnight_forecast_ml  # noqa: E402
from custom_components.freshairiq.notification_policy import NOTIFY_TARGET_ATTEMPTS  # noqa: E402
from custom_components.freshairiq.weather_now import minutes_until_rain  # noqa: E402
from custom_components.freshairiq.house_wind import wind_state  # noqa: E402
from custom_components.freshairiq.opening_strategy import enrich_opening_recommendation  # noqa: E402
from custom_components.freshairiq.robustness import finite_float  # noqa: E402
from custom_components.freshairiq.weather_future import async_hourly_forecast  # noqa: E402
from custom_components.freshairiq.storage import LearningStore  # noqa: E402
from custom_components.freshairiq.storage_defaults import _room_defaults  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")


# ------------------------------------------------------------------------------------------------ I01 live forecast

def _live(horizon, *, recent=2.0, fresh=6, elapsed=40.0, current=7.0, source=5.0, start=12.0, **extra):
    args = iq2_runtime.iq2_forecast_arguments({"moisture_share": 0.5, "thermal_share": 0.15},
                                              {"session_start_ah": start, "session_start_temp": 21.0, "session_start_source_ah": source},
                                              running=True, current_ah=current)
    return horizon_forecast(current_ah=current, source_ah=source, current_temp_c=21.0, source_temp_c=21.0, volume_m3=48.3,
                            rate_per_min=0.03, airflow_bonus=1.0, horizon_min=horizon, running=True, session_elapsed_min=elapsed,
                            session_fresh_measurements=fresh, recent_observed_removed_ml_min=recent, **{**args, **extra})


def _relaxed(horizon, shift, share=5.0 / 7.0):
    """The same relaxation from the same start state, as one closed-form expression."""
    return (7.0 - iq2.relax(7.0, 5.0 + shift / share, 12.0, 0.03, horizon, 1.0, share)) * 48.3


def test_i01_live_forecast_integrates_short_and_stepped_horizons_from_one_state():
    assert _live(5)["live_observation_weight"] == pytest.approx(0.94)
    nets = {h: _live(h)["net_room_change_ml"] for h in (5, 10, 15, 30, 60)}
    # before: 9 / 0 / 0 / 0 / 0 ml – the 5-minute slice projected the rate, the steps saw no gradient at the plateau share
    assert nets == {5: 8, 10: 15, 15: 21, 30: 32, 60: 41}
    assert all(a < b for a, b in itertools.pairwise(nets.values()))
    # the measured 2 ml/min is no linear rate over the hour (that would be 120 ml) and no minimum was invented
    assert nets[60] < 2.0 * 60 / 2 and nets[60] < 12 * nets[5]
    # both paths are the same relaxation: the shift the measured rate implies, weighted with the live weight
    decay = -__import__("math").log1p(-0.03) / (5.0 / 7.0)
    shift = 0.94 * (0.0 - 2.0 / (decay * 48.3))
    for horizon, net in nets.items():
        assert net == round(_relaxed(horizon, shift))


def test_i01_outdoor_transport_net_change_and_target_cap_stay_separate():
    for horizon in (5, 15, 60):
        result = _live(horizon)
        assert result["outdoor_transport_ml"] > result["net_room_change_ml"] > 0
    capped = _live(30, target_ah=6.9, cap_positive_to_target=True)
    assert capped["moisture_effect_ml"] == round(0.1 * 48.3) and capped["target_limited"]
    assert capped["net_room_change_ml"] == _live(30)["net_room_change_ml"] and capped["to_target_ml"] == 5
    assert capped["outdoor_transport_ml"] == _live(30)["outdoor_transport_ml"]


def test_i01_counter_cases_plateau_source_reference_change_missing_and_stale_data():
    # plateau: no measured drying at the plateau of the buffered model – nothing is invented
    assert [_live(h, recent=0.0)["net_room_change_ml"] for h in (5, 15, 60)] == [0, 0, 0]
    # missing or stale measurement: the plain model, without live weight
    for kwargs in ({"recent": None}, {"fresh": 0}, {"elapsed": 4.0}):
        result = _live(15, **kwargs)
        assert result["live_adapted"] is False or result["live_observation_weight"] == 0.0
        assert result["net_room_change_ml"] == 0 and result["observed_projection_ml"] is None
    # an inner source lowers the net change but not the ventilation part
    sourced = _live(30, prior_source_ml_min=1.0)
    assert sourced["internal_moisture_effect_ml"] > 0
    assert sourced["net_room_change_ml"] < _live(30)["net_room_change_ml"]
    # a wetter reference ahead: the net forecast may turn – no monotonicity is forced
    wetter = {m: {"absolute_humidity": 5.0 if m <= 10 else 9.0, "temperature_c": 21.0, "confidence": 80} for m in range(5, 125, 5)}
    turned = {h: _live(h, future_source_boundaries=wetter)["net_room_change_ml"] for h in (10, 30, 60)}
    assert turned[60] < turned[30] < turned[10]
    # measured wetting is followed as well (negative rate), bounded by the physical difference
    wet = _live(30, recent=-2.0)
    assert wet["net_room_change_ml"] < 0 and abs(wet["net_room_change_ml"]) <= 2.0 * 48.3
    # an implausibly high measured rate is bounded by the outdoor difference (the room cannot pass the outdoor air)
    assert _live(120, recent=500.0)["net_room_change_ml"] <= round(2.0 * 48.3)
    # no exchange at all: a measured rate cannot be turned into an equilibrium – the model alone
    still = horizon_forecast(current_ah=7.0, source_ah=5.0, current_temp_c=21.0, source_temp_c=21.0, volume_m3=48.3, rate_per_min=0.0,
                             airflow_bonus=1.0, horizon_min=15, running=True, session_elapsed_min=40.0, session_fresh_measurements=6,
                             recent_observed_removed_ml_min=2.0)
    assert still["live_adapted"] and still["observed_projection_ml"] is None and still["net_room_change_ml"] == 0


# ------------------------------------------------------------------------------------------------ I02/I03 learning

class _Finish(SessionFinishMixin):
    def __init__(self, **options):
        self.store = SimpleNamespace(data={"rooms": {}, "iq2_house": None})
        self.options = {"learning_enabled": True, "learning_max_duration_min": 120, **options}


def _open(coordinator, key, minute=0, **mem):
    room = {"session_active": True, "iq2": iq2.room_state(None), "learning_rate": 0.03, "session_specialist_opening_mode": "open",
            "session_validation_id": f"{key}:{minute}", **mem}
    coordinator.store.data["rooms"][key] = room
    room["session_iq2_episode"] = coordinator._iq2_join_house_episode(room, key, datetime(2026, 11, 17, 12, minute, tzinfo=TZ))
    return room


def _finish(coordinator, key, *, usable=True, weight=1.0, end_ah=10.5, volume=40.0, minutes=8.0):
    room = coordinator.store.data["rooms"][key]
    coordinator._iq2_learn_airing(cfg={CONF_ROOM_VOLUME: volume}, mem=room, end_ah=end_ah, learning_start_ah=12.0,
                                  measurement_elapsed=minutes, source_ah=5.0, usable=usable, weight=weight)
    room["session_active"] = False
    return room["session_iq2"]


def test_i02_parallel_rooms_share_one_house_vote_in_every_finishing_order():
    weights = set()
    for order in itertools.permutations("abc"):
        coordinator = _Finish()
        for key in "abc":
            _open(coordinator, key)
        reports = [_finish(coordinator, key) for key in order]
        assert [r["house_weight"] for r in reports] == [pytest.approx(1 / 3, abs=1e-6)] * 3   # before: 1/3 → 1/2 → 1
        house = coordinator.store.data["iq2_house"]["rate"]["open"]
        weights.add(house["weight"])
        assert house["weight"] <= 1.0 and house["n"] == 3
        for key in "abc":                                                               # the rooms learn with full weight
            assert coordinator.store.data["rooms"][key]["iq2"]["rate"]["open"]["weight"] == pytest.approx(1.0)
    assert len(weights) == 1


def test_i02_invalid_participants_single_room_and_the_next_episode():
    coordinator = _Finish()
    for key in "abc":
        _open(coordinator, key)
    _finish(coordinator, "b", usable=False)                                              # quarantined / invalid participant
    reports = [_finish(coordinator, "a", weight=0.6), _finish(coordinator, "c")]
    assert [r["house_weight"] for r in reports] == [pytest.approx(0.2, abs=1e-6), pytest.approx(1 / 3, abs=1e-6)]
    assert coordinator.store.data["iq2_house_episode"]["used"] <= 1.0
    first = coordinator.store.data["iq2_house_episode"]["id"]
    _open(coordinator, "a", minute=30)                                                   # nothing open any more: a new episode
    assert coordinator.store.data["iq2_house_episode"]["id"] != first and coordinator.store.data["iq2_house_episode"]["members"] == 1
    assert _finish(coordinator, "a")["house_weight"] == pytest.approx(1.0)


def test_i02_a_late_joiner_never_lifts_an_episode_above_one_vote():
    coordinator = _Finish()
    _open(coordinator, "a")
    _open(coordinator, "b", minute=1)
    _finish(coordinator, "a")
    _open(coordinator, "c", minute=2)                                                    # joins while b is still open
    total = 0.5 + _finish(coordinator, "b")["house_weight"] + _finish(coordinator, "c")["house_weight"]
    assert total == pytest.approx(1.0, abs=1e-5)


def test_i02_a_damaged_episode_record_degrades_to_a_safe_vote():
    coordinator = _Finish()
    _open(coordinator, "a")
    coordinator.store.data["iq2_house_episode"].update(members="x", used="nan")
    _open(coordinator, "b")
    assert coordinator.store.data["iq2_house_episode"]["members"] == 1
    assert _finish(coordinator, "a")["house_weight"] == pytest.approx(1.0)


def _restored(coordinator, keys, episode=None):
    for key in keys:
        coordinator.store.data["rooms"][key] = {"session_active": True, "iq2": iq2.room_state(None), "learning_rate": 0.03,
                                                "session_specialist_opening_mode": "open", "session_validation_id": key,
                                                **({"session_iq2_episode": episode} if episode else {})}


@pytest.mark.parametrize("episode", [None, "lost-record"])
def test_i02_sessions_restored_after_a_restart_share_one_house_vote_in_every_order(episode):
    for order in itertools.permutations("abc"):
        coordinator = _Finish()
        _restored(coordinator, "abc", episode)                                           # saved before the field / record lost
        weights = [_finish(coordinator, key)["house_weight"] for key in order]
        # before: 1/3 → 1/2 → 1 (1.83 votes), because the rooms still open shrank the divisor
        assert weights == [pytest.approx(1 / 3, abs=1e-6)] * 3 and sum(weights) <= 1.0
        assert coordinator.store.data["iq2_house"]["rate"]["open"]["weight"] <= 1.0


def test_i02_restored_sessions_join_an_episode_still_running_and_storage_stays_minimal():
    coordinator = _Finish()
    _open(coordinator, "a")
    _restored(coordinator, "bc")
    weights = [_finish(coordinator, "b")["house_weight"], _finish(coordinator, "a")["house_weight"], _finish(coordinator, "c")["house_weight"]]
    assert weights == [pytest.approx(1 / 3, abs=1e-6)] * 3 and coordinator.store.data["iq2_house_episode"]["members"] == 3
    coordinator = _Finish()
    _restored(coordinator, "ab")
    assert _finish(coordinator, "a")["house_weight"] == pytest.approx(0.5)
    defaults = _room_defaults()
    assert defaults["session_iq2_episode"] is None and defaults["session_iq2_start"] is None
    json.dumps(coordinator.store.data)                                                   # the new fields persist as JSON


def _frozen(room, house, validation_id):
    params, _ = iq2_runtime.iq2_room_parameters(room, house, mode="open", legacy_rate=room["learning_rate"], has_contact=True,
                                                force_physics=False)
    return params, iq2_runtime.iq2_start_context(params, room, house, validation_id)


def test_i03_the_score_uses_the_model_frozen_with_the_start_forecast():
    coordinator = _Finish()
    room = _open(coordinator, "a")
    params, room["session_iq2_start"] = _frozen(room, None, room["session_validation_id"])
    predicted = (12.0 - 5.0) * 50.0 * iq2.net_fraction(params["rate"], 20.0, 1.0, params["moisture_share"])
    for i in range(5):                                                                   # another room changes the house meanwhile
        _open(coordinator, "b", minute=i + 1, iq2=coordinator.store.data["rooms"].get("b", {}).get("iq2") or iq2.room_state(None))
        _finish(coordinator, "b", end_ah=7.0, volume=30.0, minutes=10.0)
    assert iq2.parameters(room["iq2"], coordinator.store.data["iq2_house"], "open", 0.03)["rate"] != params["rate"]
    report = _finish(coordinator, "a", end_ah=12.0 - predicted / 50.0, volume=50.0, minutes=20.0)
    # before: scored against the parameters recomputed at the end (159.6 ml instead of the frozen 123.3 ml)
    assert report["scored"] and report["predicted_net_ml"] == round(predicted, 1) == report["observed_net_ml"]
    assert room["iq2"]["score"]["n"] == 1 and room["iq2"]["score"]["error_ml"] == pytest.approx(0.0, abs=0.06)
    assert room["session_iq2_start"] is None                                             # consumed: never scored twice
    assert room["iq2"]["rate"]["open"]["n"] == 1                                         # and the airing still taught the room


def test_i03_reference_and_interval_come_from_the_same_frozen_origin():
    coordinator = _Finish()
    room = _open(coordinator, "a")
    _params, room["session_iq2_start"] = _frozen(room, None, room["session_validation_id"])
    room["learning_rate"] = 0.2                                                          # changed after the start: not the reference
    _finish(coordinator, "a")
    reference = (12.0 - 5.0) * 40.0 * iq2.net_fraction(0.03, 8.0)
    assert room["iq2"]["score"]["reference_error_ml"] == round(abs((12.0 - 10.5) * 40.0 - reference), 2)


@pytest.mark.parametrize("start", [None, "other", "broken"])
def test_i03_without_a_valid_frozen_start_nothing_is_scored_but_the_room_still_learns(start):
    coordinator = _Finish()
    room = _open(coordinator, "a")
    if start == "other":
        room["session_iq2_start"] = _frozen(room, None, "another-session")[1]
    elif start == "broken":
        room["session_iq2_start"] = {"model": iq2.MODEL, "schema": iq2.SCHEMA, "rate": "x", "moisture_share": 2,
                                     "validation_id": room["session_validation_id"]}
    report = _finish(coordinator, "a")
    assert report["usable"] and report["scored"] is False and "predicted_net_ml" not in report
    assert room["iq2"]["score"] == iq2.new_score() and room["iq2"]["rate"]["open"]["n"] == 1


def test_i03_pure_learning_without_a_start_argument_scores_the_model_in_force_now():
    _r, _h, report = iq2.learn_airing(None, None, mode="open", base_rate=0.03, start_ah=12.0, end_ah=10.5, source_ah=5.0, minutes=8.0,
                                      volume_m3=30.0, quality_weight=1.0)
    assert report["scored"] and report["predicted_net_ml"] > 0
    _r, _h, none = iq2.learn_airing(None, None, mode="open", base_rate=0.03, start_ah=12.0, end_ah=10.5, source_ah=5.0, minutes=8.0,
                                    volume_m3=30.0, quality_weight=1.0, start=None)
    assert none["scored"] is False and _r["score"]["n"] == 0


def test_i03_passive_rooms_and_missing_room_state_freeze_nothing():
    assert iq2_runtime.iq2_start_context({"active": False}, {"iq2": {}}, None, "x") is None
    assert iq2_runtime.iq2_start_context({"active": True, "mode": "open"}, {}, None, "x") is None
    frozen = iq2_runtime.iq2_start_context({"active": True, "mode": "weird"}, {"iq2": iq2.room_state(None), "learning_rate": 0.03}, None, "x")
    assert frozen["mode"] == iq2.GENERAL and frozen["validation_id"] == "x" and frozen["reference_rate"] == 0.03


def _in_force(case):
    room = iq2.room_state(None)
    room["rate"]["open"] = {"sum": 0.6, "weight": 6.0, "n": 6}
    if case == "rollback":
        room["score"].update(n=6, rollback=True, error_ml=80.0, reference_error_ml=20.0)
    coordinator = _Finish()
    mem = _open(coordinator, "a", iq2=room, learning_rate=0.05)
    params, _ = iq2_runtime.iq2_room_parameters(mem, None, mode="open", legacy_rate=0.05, has_contact=True, force_physics=case == "physics")
    mem["session_iq2_start"] = iq2_runtime.iq2_start_context(params, mem, None, mem["session_validation_id"])
    shown = (12.0 - 5.0) * 50.0 * iq2.net_fraction(params["rate"], 20.0, 1.0, params["moisture_share"])
    learned = (12.0 - 5.0) * 50.0 * iq2.net_fraction(mem["session_iq2_start"]["rate"], 20.0, 1.0, mem["session_iq2_start"]["moisture_share"])
    return coordinator, mem, params, shown, learned


@pytest.mark.parametrize("case,level", [("rollback", "rollback"), ("physics", "fallback"), ("learned", "global")])
def test_i03_the_forecast_really_in_force_is_frozen_and_scored(case, level):
    coordinator, mem, params, shown, learned = _in_force(case)
    assert params["level"] == level and mem["session_iq2_start"]["level"] == level
    report = _finish(coordinator, "a", end_ah=12.0 - shown / 50.0, volume=50.0, minutes=20.0)
    # before: rollback 224.5 ml and physics 123.3 ml shown, but both scored against the learned 127.0 ml
    assert report["predicted_net_ml"] == round(shown, 1) == report["observed_net_ml"] and report["start_level"] == level
    assert report["model_predicted_net_ml"] == round(learned, 1)
    score = mem["iq2"]["score"]
    assert score["covered"] == 1                                                         # the shown forecast was a hit
    assert score["error_ml"] == pytest.approx(abs(shown - learned) if case == "physics" else
                                              (80.0 * 0.8 + abs(shown - learned) * 0.2 if case == "rollback" else 0.0), abs=0.06)


def test_i03_the_rollback_guard_follows_the_learned_model_and_can_recover():
    coordinator, mem, _params, shown, learned = _in_force("rollback")
    # the airing removes what the learned model predicted: the learned model is good again, the reference is not
    _finish(coordinator, "a", end_ah=12.0 - learned / 50.0, volume=50.0, minutes=20.0)
    score = mem["iq2"]["score"]
    assert score["error_ml"] == pytest.approx(80.0 * 0.8, abs=0.06) and score["rollback"] is True
    for _ in range(6):
        mem["session_active"], mem["session_validation_id"] = True, f"a:{_}"
        params, _x = iq2_runtime.iq2_room_parameters(mem, None, mode="open", legacy_rate=0.05, has_contact=True, force_physics=False)
        mem["session_iq2_start"] = iq2_runtime.iq2_start_context(params, mem, None, mem["session_validation_id"])
        model = (12.0 - 5.0) * 50.0 * iq2.net_fraction(mem["session_iq2_start"]["rate"], 20.0, 1.0, mem["session_iq2_start"]["moisture_share"])
        _finish(coordinator, "a", end_ah=12.0 - model / 50.0, volume=50.0, minutes=20.0)
    assert mem["iq2"]["score"]["rollback"] is False


def test_i03_a_start_frozen_before_the_effective_fields_counts_as_the_learned_model():
    coordinator = _Finish()
    room = _open(coordinator, "a")
    _params, frozen = _frozen(room, None, room["session_validation_id"])
    for key in ("level", "effective_rate", "effective_moisture_share"):
        frozen.pop(key)
    room["session_iq2_start"] = frozen
    report = _finish(coordinator, "a")
    assert report["scored"] and report["predicted_net_ml"] == report["model_predicted_net_ml"] and report["start_level"] == "learned"
    bad = dict(frozen, effective_rate=-1, validation_id="a:0")
    room.update(session_active=True, session_validation_id="a:0", session_iq2_start=bad)
    assert _finish(coordinator, "a")["scored"] is False


# ------------------------------------------------------------------------------------------------ I04 learning reset

def _store_with_house(key="i04"):
    ha_stub.Store._MEMORY.pop(f"freshairiq.learning.{key}", None)
    store = LearningStore(None, key)
    asyncio.run(store.async_load())
    house = iq2.new_house_state()
    house["rate"]["open"] = {"sum": round(12 * 0.6773, 6), "weight": 12.0, "n": 30}
    store.data["iq2_house"] = house
    return store


def _new_room_rate(data):
    params, _ = iq2_runtime.iq2_room_parameters({"learning_rate": 0.03, "learning_samples": 0}, data.get("iq2_house"), mode="open",
                                                legacy_rate=0.03, has_contact=True, force_physics=False)
    return params["rate"], params["house_weight"]


def test_i04_reset_in_rest_neutralises_the_house_model_and_persists_it():
    store = _store_with_house()
    store.data["rooms"]["a"] = {**_room_defaults(), "learning_rate": 0.0591, "learning_samples": 9}
    store.data["history"] = {"2026-11-16": {"sessions": 3}}
    assert _new_room_rate(store.data) == (pytest.approx(0.0582, abs=1e-4), 12.0)       # before: kept after the reset
    asyncio.run(store.async_reset_learning())
    reloaded = LearningStore(None, "i04")
    asyncio.run(reloaded.async_load())
    assert reloaded.data["iq2_house"] == iq2.new_house_state()
    assert _new_room_rate(reloaded.data) == (0.03, 0.0)
    assert reloaded.data["rooms"]["a"]["learning_rate"] == 0.03 and reloaded.data["rooms"]["a"]["session_learning_reset_at"] is None
    assert reloaded.data["history"] == {"2026-11-16": {"sessions": 3}}                    # statistics stay


def test_i04_reset_during_an_airing_keeps_its_protection_and_origin_and_it_teaches_nothing():
    store = _store_with_house("i04b")
    session = {"session_active": True, "session_learning_quarantined": True, "session_learning_quarantine_code": "FAIQ-OPENING-3STATE-006",
               "session_specialist_opening_mode": "tilted", "session_opening_mode": "tilted", "session_validation_start_ah": 12.0,
               "session_validation_started": "2026-11-17T12:00:00+01:00", "session_climate_report_state": {"t": {"available": True}},
               "session_climate_report_counts": {"t": 3}, "session_iq2_episode": "a:x", "session_validation_id": "a:1"}
    store.data["rooms"]["a"] = {**_room_defaults(), **session}
    asyncio.run(store.async_reset_learning())
    reloaded = LearningStore(None, "i04b")
    asyncio.run(reloaded.async_load())
    room = reloaded.data["rooms"]["a"]
    assert {k: room[k] for k in session} == session                                      # before: quarantine, mode and origin lost
    assert room["session_learning_reset_at"]
    # the airing ends later: it neither refills the reset house nor the room
    coordinator = _Finish()
    coordinator.store = SimpleNamespace(data=reloaded.data)
    room.update(session_learning_quarantined=False, iq2=iq2.room_state(None), learning_rate=0.03)
    coordinator._iq2_learn_airing(cfg={CONF_ROOM_VOLUME: 40.0}, mem=room, end_ah=10.5, learning_start_ah=12.0, measurement_elapsed=8.0,
                                  source_ah=5.0, usable=True, weight=1.0)
    assert room["session_iq2"] == {"model": iq2.MODEL, "usable": False} and reloaded.data["iq2_house"] == iq2.new_house_state()


def _exchange(mem, **extra):
    coordinator = _Finish()
    coordinator.store.data["rooms"]["a"] = mem
    base = dict(cfg={CONF_ROOM_VOLUME: 40.0, "name": "A"}, cover_learning_blocked=False, cover_session=None, end_ah=10.5,
                frame_learning_eligible=True, learning_contaminated=False, learning_start_ah=12.0, measurement_elapsed=8.0, mem=mem,
                now=datetime(2026, 11, 17, 12, 30, tzinfo=TZ), reference_moisture_reversal=False,
                session_quality={"learning_weight": 1.0}, source_ah=5.0)
    return coordinator._learn_session_exchange(**{**base, **extra})


def test_i04_room_rate_learning_is_skipped_for_an_airing_across_a_reset_and_works_again_afterwards():
    mem = {**_room_defaults(), "session_active": True, "session_learning_reset_at": "2026-11-17T12:10:00+01:00", "iq2": iq2.room_state(None)}
    rate, valid = _exchange(mem)
    assert (rate, valid) == (0.03, False) and "zurückgesetzt" in mem["diagnosis"]
    assert mem["learning_samples"] == 0 and mem["session_learning_observation"]["usable"] is False
    mem = {**_room_defaults(), "session_active": True, "iq2": iq2.room_state(None)}
    rate, valid = _exchange(mem)
    assert valid and mem["learning_samples"] == 1 and mem["session_iq2"]["usable"]


def test_i04_without_a_reset_an_unaligned_frame_keeps_its_earlier_reason():
    class Validation(SessionValidationMixin):
        options: dict = {}
    mem = {**_room_defaults(), "session_validation_started": "2026-11-17T12:00:00+01:00", "session_validation_start_ah": 12.0,
           "session_validation_start_temp": 21.0, "session_prediction_start_context": {"version": 3, "forecast_args": {
               "current_ah": 12.0, "source_ah": 5.0, "current_temp_c": 21.0, "source_temp_c": 5.0, "volume_m3": 40.0, "rate_per_min": 0.03,
               "airflow_bonus": 1.0}, "target_ah": 10.0, "controls": {}, "energy_options": {}}}
    out = Validation()._validate_session_forecast(
        cfg={CONF_ROOM_VOLUME: 40.0}, elapsed=10.0, learning_contaminated=False, mem=mem, now=datetime(2026, 11, 17, 12, 10, tzinfo=TZ),
        reference_moisture_reversal=False, session_activity_eligible=False, session_quality={"learning_weight": 0.0}, session_removed=60.0,
        temp_delta=-1.0, validation_end_ah=10.5, validation_end_temp=20.0)
    assert out[1] == "skipped" and "Sensor-Zeitstempel" in out[3]


def test_i04_outcome_feedback_of_an_airing_across_a_reset_is_skipped():
    class Validation(SessionValidationMixin):
        options: dict = {}
    mem = {**_room_defaults(), "session_learning_reset_at": "2026-11-17T12:10:00+01:00", "session_validation_started": "2026-11-17T12:00:00+01:00",
           "session_validation_start_ah": 12.0, "session_validation_start_temp": 21.0}
    before = copy.deepcopy(mem)
    out = Validation()._validate_session_forecast(
        cfg={CONF_ROOM_VOLUME: 40.0}, elapsed=10.0, learning_contaminated=False, mem=mem, now=datetime(2026, 11, 17, 12, 10, tzinfo=TZ),
        reference_moisture_reversal=False, session_activity_eligible=True, session_quality={"learning_weight": 1.0}, session_removed=60.0,
        temp_delta=-1.0, validation_end_ah=10.5, validation_end_temp=20.0)
    assert out[1] == "skipped" and out[2] is False and "zurückgesetzt" in out[3]
    assert mem["outcome_removed_factor"] == before["outcome_removed_factor"]


# ------------------------------------------------------------------------------------------------ I05 comparison

def _worker(houses):
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "iq2_compare.py"), "--worker", str(ROOT)], input=json.dumps(houses),
                          capture_output=True, text=True, check=False, timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)["records"]


def test_i05_parallel_start_forecasts_never_see_a_later_end():
    import iq2_compare

    houses = iq2_compare.build_houses(20261116, 1, 12)
    episodes = houses[0]["episodes"]
    last = next(i for i, e in enumerate(episodes) if len(e) >= 2)
    houses[0]["episodes"] = episodes[: last + 1]
    before = sum(len(e) for e in houses[0]["episodes"][:-1])

    def starts(data):
        rows = _worker(data)[before:]
        return {row["room"]: (row["forecast"], row["interval"]) for row in rows}

    base = starts(houses)
    changed = copy.deepcopy(houses)
    for row in changed[0]["episodes"][-1][0]["minutes"][1:]:                             # only A's future end changes
        row["ah"] = round(row["ah"] - 2.0, 4)
    swapped = copy.deepcopy(houses)
    swapped[0]["episodes"][-1].reverse()
    assert starts(changed) == base and starts(swapped) == base


def test_i05_naive_baselines_follow_the_same_time_order():
    import iq2_compare

    houses = iq2_compare.build_houses(7, 2, 20)
    swapped = copy.deepcopy(houses)
    for house in swapped:
        for episode in house["episodes"]:
            episode.reverse()

    def by_room(data):
        rows = iq2_compare._naive(data)["naiv (wie letzte Lüftung)"]
        flat = [(h["house"], a["room"], i) for h in data for i, e in enumerate(h["episodes"]) for a in e]
        return {key: row["forecast"] for key, row in zip(flat, rows)}

    assert by_room(houses) == by_room(swapped)


# ------------------------------------------------------------------------------------------------ F06–F08, F15 devices

COVER = {"supported_features": 4}
_ENTRIES = itertools.count()


def _controller(rooms, states, options=None):
    hass = ha_stub.HomeAssistant()
    for entity, (state, attrs) in states.items():
        hass.states.async_set(entity, state, attrs)
    coordinator = SimpleNamespace(data={"rooms": {}}, options=options or {}, async_add_listener=lambda f: (lambda: None))
    entry = SimpleNamespace(entry_id=f"audit{next(_ENTRIES)}", data={"rooms": rooms}, options=options or {})
    controller = ActuatorController(hass, coordinator, entry)
    asyncio.run(controller._async_attach())
    return hass, controller


def _covers_follow(hass, *, fail=()):
    """Covers report a command at once; ``fail`` lists services refused (once each, in order)."""
    calls, refusals, original = [], list(fail), hass.services.async_call

    async def call(domain, service, data=None, **kw):
        if refusals and refusals[0] == service:
            refusals.pop(0)
            calls.append(f"{service}!")
            raise RuntimeError("service unavailable")
        if domain == "cover":
            calls.append(service)
            entity = data["entity_id"]
            position = 100 if service == "open_cover" else 0 if service == "close_cover" else data.get("position")
            hass.states.async_set(entity, "open" if position else "closed", {"current_position": position, **COVER})
        return await original(domain, service, data, **kw)

    hass.services.async_call = call
    return calls


def _evaluate(controller, fans=False):
    asyncio.run(controller._async_evaluate(fans=fans))


def _shared_rooms(*, follow_b=True):
    return [{"key": "a", "contact_covers": {"binary_sensor.a": ["cover.shared"]}, "contact_cover_follow": {"binary_sensor.a": True}},
            {"key": "b", "contact_covers": {"binary_sensor.b": ["cover.shared"]}, "contact_cover_follow": {"binary_sensor.b": follow_b}}]


def test_f06_a_shared_cover_follows_all_its_contacts_together():
    hass, controller = _controller(_shared_rooms(), {"binary_sensor.a": ("on", {}), "binary_sensor.b": ("off", {}),
                                                     "cover.shared": ("open", {"current_position": 30, **COVER})})
    calls = _covers_follow(hass)
    for _ in range(3):
        _evaluate(controller)
    assert calls == ["open_cover"]                                                       # before: open → back → open → back
    hass.states.async_set("binary_sensor.b", "on", {})
    _evaluate(controller)
    hass.states.async_set("binary_sensor.a", "off", {})                                   # one contact closes, the other is open
    _evaluate(controller)
    assert calls == ["open_cover"] and controller._memory["covers"]["cover.shared"]["restore_position"] == 30
    reloaded = ActuatorController(hass, controller.coordinator, controller.entry)        # reload keeps the restore point
    reloaded._memory = copy.deepcopy(controller._memory)
    asyncio.run(reloaded._async_attach())
    hass.states.async_set("binary_sensor.b", "off", {})                                   # the last request ended
    _evaluate(reloaded)
    assert calls == ["open_cover", "set_cover_position"] and hass.states.get("cover.shared").attributes["current_position"] == 30


def test_f06_single_room_and_a_contact_without_follow_keep_the_earlier_behaviour():
    hass, controller = _controller(_shared_rooms(follow_b=False), {"binary_sensor.a": ("on", {}), "binary_sensor.b": ("on", {}),
                                                                   "cover.shared": ("closed", {"current_position": 0, **COVER})})
    calls = _covers_follow(hass)
    _evaluate(controller)
    hass.states.async_set("binary_sensor.a", "off", {})
    _evaluate(controller)
    assert calls == ["open_cover", "set_cover_position"]                                 # b does not ask for the cover
    memory = {"failed_attempts": "x"}
    cover_command_result(memory, dict(memory), False)
    assert memory == {"failed_attempts": 1}                                              # a damaged counter starts again
    merged = combine_cover_setups(CoverSetup(["x"], ["x"], []), CoverSetup(["y"], [], ["y"]))
    assert merged == CoverSetup(["x", "y"], ["x"], ["y"])


def test_f07_a_refused_open_is_tried_again_and_the_restore_point_stays_right():
    rooms = [{"key": "a", "contact_covers": {"binary_sensor.a": ["cover.x"]}, "contact_cover_follow": {"binary_sensor.a": True}}]
    hass, controller = _controller(rooms, {"binary_sensor.a": ("on", {}), "cover.x": ("open", {"current_position": 40, **COVER})})
    calls = _covers_follow(hass, fail=["open_cover"])
    _evaluate(controller)
    assert calls == ["open_cover!"] and controller._memory["covers"]["cover.x"]["follow_active"] is True
    _evaluate(controller)                                                                # before: never tried again
    assert calls == ["open_cover!", "open_cover"] and hass.states.get("cover.x").attributes["current_position"] == 100
    _evaluate(controller)
    assert calls == ["open_cover!", "open_cover"]                                        # open now: nothing more
    hass.states.async_set("binary_sensor.a", "off", {})
    _evaluate(controller)
    assert calls[-1] == "set_cover_position" and hass.states.get("cover.x").attributes["current_position"] == 40


def test_f07_a_window_session_without_any_successful_open_moves_nothing_back():
    rooms = [{"key": "a", "contact_covers": {"binary_sensor.a": ["cover.x"]}, "contact_cover_follow": {"binary_sensor.a": True}}]
    hass, controller = _controller(rooms, {"binary_sensor.a": ("on", {}), "cover.x": ("open", {"current_position": 40, **COVER})})
    calls = _covers_follow(hass, fail=["open_cover"] * 2)
    _evaluate(controller)
    _evaluate(controller)
    assert calls == ["open_cover!", "open_cover!"] and controller._memory["covers"]["cover.x"]["follow_active"] is True
    hass.states.async_set("binary_sensor.a", "off", {})                                  # closed before the third try
    _evaluate(controller)
    _evaluate(controller)
    assert calls == ["open_cover!", "open_cover!"] and hass.states.get("cover.x").attributes["current_position"] == 40
    assert controller._memory["covers"]["cover.x"]["follow_active"] is False
    hass.states.async_set("binary_sensor.a", "on", {})                                   # the next session starts afresh
    _evaluate(controller)
    assert calls[-1] == "open_cover" and hass.states.get("cover.x").attributes["current_position"] == 100
    hass.states.async_set("binary_sensor.a", "off", {})
    _evaluate(controller)
    assert calls[-1] == "set_cover_position" and hass.states.get("cover.x").attributes["current_position"] == 40


def test_f07_retries_are_bounded_and_a_manual_move_is_still_respected():
    rooms = [{"key": "a", "contact_covers": {"binary_sensor.a": ["cover.x"]}, "contact_cover_follow": {"binary_sensor.a": True}}]
    hass, controller = _controller(rooms, {"binary_sensor.a": ("on", {}), "cover.x": ("closed", {"current_position": 0, **COVER})})
    calls = _covers_follow(hass, fail=["open_cover"] * 10)
    for _ in range(COVER_COMMAND_ATTEMPTS + 3):
        _evaluate(controller)
    assert calls == ["open_cover!"] * COVER_COMMAND_ATTEMPTS                             # no service loop
    assert controller._memory["covers"]["cover.x"]["command_failed"] is True
    hass.states.async_set("cover.x", "open", {"current_position": 60, **COVER})          # someone moved it by hand
    hass.states.async_set("binary_sensor.a", "off", {})
    _evaluate(controller)
    assert calls == ["open_cover!"] * COVER_COMMAND_ATTEMPTS


@pytest.mark.parametrize("moved", [CoverView("open", 60, supports_position=True), CoverView("closing", 0, supports_position=True),
                                   CoverView("closing")])
def test_f07_a_pending_open_ends_with_a_manual_move_and_other_refusals_stay_bounded(moved):
    setup = CoverSetup(["binary_sensor.a"], ["binary_sensor.a"], [])
    closed = CoverView("closed", 0 if moved.position is not None else None, supports_position=moved.supports_position)

    def cover(view, mode="open"):
        return decide_cover(view=view, setup=setup, contact_modes={"binary_sensor.a": mode}, sun_auto=False, sun_wants_close=False, mem=mem)

    mem = {}
    before = dict(mem)
    assert cover(closed) == [(COVER_OPEN, None)]
    cover_command_result(mem, before, False)
    assert cover(closed) == [(COVER_OPEN, None)]                                         # still closed: sent again
    assert cover(moved) == [] and cover(moved) == []                                     # moved by hand: no further open
    assert cover(moved, "closed") == [] and mem["follow_active"] is False                # and nothing is moved back
    memory = {"failed_attempts": COVER_COMMAND_ATTEMPTS - 1}
    cover_command_result(memory, dict(memory), False)
    assert memory == {"command_failed": True}                                            # outside a window session as before


def _fan_controller(rooms, states):
    hass, controller = _controller(rooms, states)
    calls = []
    original = hass.services.async_call

    async def call(domain, service, data=None, **kw):
        if domain == "homeassistant":
            calls.append((service, list(data["entity_id"])))
            for fan in data["entity_id"]:
                hass.states.async_set(fan, "on" if service == "turn_on" else "off", {})
        return await original(domain, service, data, **kw)

    hass.services.async_call = call
    return hass, controller, calls


def _fan_cycle(controller, seconds=60, **sources):
    ha_stub.CLOCK.advance(seconds)
    controller.coordinator.data = {"rooms": {key: {"moisture_source_active": active} for key, active in sources.items()}}
    _evaluate(controller, fans=True)


def _fan_room(key, fans, **extra):
    return {"key": key, "exhaust_fan": fans, "exhaust_fan_control": "moisture_source", "exhaust_fan_follow_up_min": 0, **extra}


def test_f08_extending_a_running_group_does_not_hand_over_ownership():
    hass, controller, calls = _fan_controller([_fan_room("a", ["fan.x"])], {"fan.x": ("off", {}), "fan.y": ("on", {})})
    _fan_cycle(controller, a=True)
    _fan_cycle(controller, a=True)
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"])]               # Y (running by hand) is added
    asyncio.run(controller.async_reload())
    _fan_cycle(controller, a=False)
    assert calls == [("turn_on", ["fan.x"]), ("turn_off", ["fan.x"])]                   # before: turn_off([X, Y])
    assert hass.states.get("fan.y").state == "on"
    _fan_cycle(controller, a=False)
    assert controller.fan_snapshot("a")["command_state"] == "confirmed"                  # confirmed on X alone


def test_f08_a_new_start_owns_only_what_it_started_and_removal_spares_foreign_fans():
    hass, controller, calls = _fan_controller([_fan_room("a", ["fan.x", "fan.y"])], {"fan.x": ("off", {}), "fan.y": ("off", {})})
    _fan_cycle(controller, a=True)
    assert calls == [("turn_on", ["fan.x", "fan.y"])] and controller._memory["fans"]["a"]["owned_fans"] == ["fan.x", "fan.y"]
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x"])]                         # Y removed while running
    asyncio.run(controller.async_reload())
    assert calls[-1] == ("turn_off", ["fan.y"]) and controller._memory["fans"]["a"]["owned_fans"] == ["fan.x"]
    hass.states.async_set("fan.y", "on", {})                                             # Y on by hand, added again
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"])]
    asyncio.run(controller.async_reload())
    _fan_cycle(controller, a=False)
    assert calls[-1] == ("turn_off", ["fan.x"]) and hass.states.get("fan.y").state == "on"
    # removing a fan FreshAirIQ never started does not switch it off
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x"])]
    asyncio.run(controller.async_reload())
    assert calls[-1] == ("turn_off", ["fan.x"])
    assert own_fans({}, ["fan.x"]) == ["fan.x"] and own_fans({"owned_fans": []}, ["fan.x"]) == []


def test_f08_shared_devices_further_requests_and_follow_up_keep_working():
    rooms = [_fan_room("a", ["fan.p", "fan.s"]), _fan_room("b", ["fan.s"])]
    hass, controller, calls = _fan_controller(rooms, {"fan.p": ("off", {}), "fan.s": ("off", {})})
    _fan_cycle(controller, a=True, b=False)
    _fan_cycle(controller, a=False, b=True)                                              # B still needs the shared fan
    assert calls == [("turn_on", ["fan.p", "fan.s"]), ("turn_off", ["fan.p"])] and hass.states.get("fan.s").state == "on"
    _fan_cycle(controller, a=False, b=False)
    assert calls[-1] == ("turn_off", ["fan.p", "fan.s"])
    follow = [_fan_room("a", ["fan.x"], exhaust_fan_follow_up_min=10)]
    hass, controller, calls = _fan_controller(follow, {"fan.x": ("off", {})})
    _fan_cycle(controller, a=True)
    _fan_cycle(controller, seconds=300, a=False)                                         # follow-up still running
    assert calls == [("turn_on", ["fan.x"])]
    _fan_cycle(controller, seconds=600, a=False)
    assert calls[-1] == ("turn_off", ["fan.x"])


def test_f08_removing_the_control_the_automation_lock_and_the_lock_period_end_only_own_fans():
    hass, controller, calls = _fan_controller([_fan_room("a", ["fan.x"])], {"fan.x": ("off", {}), "fan.y": ("on", {})})
    _fan_cycle(controller, a=True)
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"])]
    asyncio.run(controller.async_reload())
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"], exhaust_fan_control="off")]
    asyncio.run(controller.async_reload())
    assert calls[-1] == ("turn_off", ["fan.x"]) and hass.states.get("fan.y").state == "on"
    assert "owned_fans" not in controller._memory["fans"]["a"]
    hass, controller, calls = _fan_controller([_fan_room("a", ["fan.x"])], {"fan.x": ("off", {}), "fan.y": ("on", {}), "input_boolean.lock": ("off", {})})
    controller.entry.options = {"automation_lock_entity": "input_boolean.lock"}
    _fan_cycle(controller, a=True)
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"])]
    asyncio.run(controller.async_reload())
    hass.states.async_set("input_boolean.lock", "on", {})
    _fan_cycle(controller, a=True)
    assert calls[-1] == ("turn_off", ["fan.x"]) and hass.states.get("fan.y").state == "on"
    now = ha_stub.CLOCK.now
    window = {"exhaust_fan_block_start": (now + timedelta(minutes=2)).strftime("%H:%M"), "exhaust_fan_block_end": (now + timedelta(hours=1)).strftime("%H:%M")}
    hass, controller, calls = _fan_controller([_fan_room("a", ["fan.x"], **window)], {"fan.x": ("off", {}), "fan.y": ("on", {})})
    _fan_cycle(controller, a=True)
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"], **window)]
    asyncio.run(controller.async_reload())
    _fan_cycle(controller, seconds=180, a=True)                                          # the lock period starts
    assert calls[-1] == ("turn_off", ["fan.x"]) and hass.states.get("fan.y").state == "on"


def test_f08_a_run_from_before_the_device_record_owns_the_fans_it_had_at_the_group_change():
    hass, controller, calls = _fan_controller([_fan_room("a", ["fan.x"])], {"fan.x": ("on", {}), "fan.y": ("on", {})})
    controller._memory["fans"]["a"] = {"owned": True, "since": ha_stub.CLOCK.now.isoformat(), "command": "on", "command_state": "confirmed"}
    controller.entry.data["rooms"] = [_fan_room("a", ["fan.x", "fan.y"])]
    asyncio.run(controller.async_reload())
    _fan_cycle(controller, a=False)
    assert calls == [("turn_off", ["fan.x"])]


@pytest.mark.parametrize("room_value,global_value,opens", [(None, "open", True), (None, None, False), ("closed", "open", False),
                                                           ("open", "closed", True)])
def test_f15_inverse_position_room_value_before_global_before_default(room_value, global_value, opens):
    room = {"key": "a", "contact_covers": {"binary_sensor.a": ["cover.inv"]}, "contact_cover_follow": {"binary_sensor.a": True}}
    if room_value is not None:
        room["cover_position_zero_means"] = room_value
    options = {"cover_position_zero_means": global_value} if global_value else {}
    position = 100 if opens else 0                                                       # closed in the cover's own scale
    hass, controller = _controller([room], {"binary_sensor.a": ("on", {}), "cover.inv": ("closed", {"current_position": position, **COVER})}, options)
    calls = _covers_follow(hass)
    _evaluate(controller)
    assert calls == ["open_cover"]                                                       # before: no open for the global "open"
    assert controller._zero_means_open(room) is opens
    assert controller.entry.data["rooms"][0].get("cover_position_zero_means") == room_value   # nothing is written back


# ------------------------------------------------------------------------------------------------ F09, F10, F13 units

T_C = {"device_class": "temperature", "unit_of_measurement": "°C"}
H_PCT = {"device_class": "humidity", "unit_of_measurement": "%"}


def _chain(rooms, initial, steps, options=None, data=None, start=datetime(2026, 11, 17, 12, 0, tzinfo=TZ)):
    """The real coordinator over scripted states (golden harness: frozen clock, in-memory storage, no network)."""
    seen = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append(copy.deepcopy(result))
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    scenario = {"start": start, "initial": initial, "steps": steps, "options": {**golden.BASE_OPTIONS, **(options or {})},
                "data": {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": rooms,
                         "levels": ["ground_floor"], **(data or {})}}
    try:
        asyncio.run(golden._run_scenario("audit", scenario, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return seen


def _unit_room(**extra):
    return golden._room("r", "Raum", "ground_floor", temp=["sensor.r_t"], hum=["sensor.r_h"], contacts=["binary_sensor.r_f"], volume=50,
                        extra=extra or None)


def _outdoor(temp=5.0, unit="°C"):
    return {"sensor.aussen_t": (temp, {"device_class": "temperature", "unit_of_measurement": unit}), "sensor.aussen_h": (70.0, H_PCT),
            "binary_sensor.r_f": ("off", {"device_class": "window"})}


@pytest.mark.parametrize("value,unit", [(20.0, "°C"), (68.0, "°F"), (293.15, "K")])
def test_f09_room_temperature_in_any_selectable_unit_gives_the_same_physics(value, unit):
    initial = {"sensor.r_t": (value, {"device_class": "temperature", "unit_of_measurement": unit}), "sensor.r_h": (65.0, H_PCT), **_outdoor()}
    room = _chain([_unit_room()], initial, [{"advance": 60}])[-1]["rooms"]["r"]
    # before: 20 / 68 / 293.15 °C → 323 / 0 / 0 ml and ok / error / error
    assert room["data_quality"] == "ok" and room["temperature"] == pytest.approx(20.0) and room["potential_ml"] == 323


@pytest.mark.parametrize("outdoor", [(5.0, "°C"), (41.0, "°F"), (278.15, "K")])
def test_f09_outdoor_sensor_units_and_mixed_room_sensors(outdoor):
    initial = {"sensor.r_t": (20.0, T_C), "sensor.r_t2": (68.0, {"unit_of_measurement": "°F"}), "sensor.r_h": (65.0, H_PCT),
               **_outdoor(*outdoor)}
    room = golden._room("r", "Raum", "ground_floor", temp=["sensor.r_t", "sensor.r_t2"], hum=["sensor.r_h"], contacts=["binary_sensor.r_f"], volume=50)
    cycle = _chain([room], initial, [{"advance": 60}])[-1]
    assert cycle["outdoor_temperature"] == pytest.approx(5.0) and cycle["outdoor_absolute_humidity"] == 4.754
    assert cycle["rooms"]["r"]["temperature"] == pytest.approx(20.0) and cycle["rooms"]["r"]["potential_ml"] == 323


def test_f09_quality_contract_for_invalid_units_and_values():
    hass = ha_stub.HomeAssistant()
    rows = {"sensor.a": ("20", T_C), "sensor.f": ("68", {"unit_of_measurement": "°F"}), "sensor.k": ("293.15", {"unit_of_measurement": "K"}),
            "sensor.none": ("20", {}), "sensor.bad": ("20", {"unit_of_measurement": "°R"}), "sensor.u": ("unavailable", T_C),
            "sensor.x": ("unknown", T_C), "sensor.inf": ("inf", T_C), "sensor.co2": ("1180", {"unit_of_measurement": "ppm"})}
    for entity, (state, attrs) in rows.items():
        hass.states.async_set(entity, state, attrs)
    assert [_temperature_state(hass, e) for e in ("sensor.a", "sensor.none", "sensor.bad", "sensor.u", "sensor.x", "sensor.inf", None)] == \
        [20.0, 20.0, None, None, None, None, None]
    assert _temperature_state(hass, "sensor.f") == pytest.approx(20.0) and _temperature_state(hass, "sensor.k") == pytest.approx(20.0)
    assert _float_state(hass, "sensor.co2") == 1180.0 and _float_state(hass, "sensor.f") == 68.0           # other numbers unchanged
    mixed = aggregate_states(hass, ["sensor.a", "sensor.f", "sensor.bad", "sensor.u"], finite=finite_float, temperature=True)
    assert mixed.value == pytest.approx(20.0) and mixed.available == 2 and mixed.configured == 4
    raw = aggregate_states(hass, ["sensor.a", "sensor.f"], finite=finite_float)                          # not a temperature: as before
    assert raw.value == 44.0
    assert celsius(None, "°F") is None and celsius(10.0, "℃") == 10.0


def test_f09_weather_attributes_and_forecast_rows_follow_the_entity_unit():
    hass = ha_stub.HomeAssistant()
    hass.states.async_set("weather.f", "cloudy", {"temperature": 41.0, "temperature_unit": "°F", "humidity": 70})
    hass.states.async_set("weather.c", "cloudy", {"temperature": 5.0, "humidity": 70})
    assert _weather_values(hass, "weather.f") == (pytest.approx(5.0), 70.0) and _weather_values(hass, "weather.c") == (5.0, 70.0)
    start = datetime(2026, 11, 17, 13, 0, tzinfo=TZ)
    hass.services.forecast = [{"datetime": start.isoformat(), "temperature": 41.0, "dew_point": 32.0},
                              {"datetime": start.replace(hour=14).isoformat(), "temperature": 50.0, "humidity": 80}]
    hass.services.has_service = lambda *a: True
    rows = asyncio.run(async_hourly_forecast(hass, "weather.f"))
    assert [r["temperature_c"] for r in rows] == [5.0, 10.0]
    assert rows[0]["humidity"] == pytest.approx(70.1, abs=0.2)                            # from the dew point, both in °C
    assert [r["temperature_c"] for r in asyncio.run(async_hourly_forecast(hass, "weather.c"))] == [41.0, 50.0]


def test_f09_neighbour_contact_reference_and_display_rooms():
    room_f = {"unit_of_measurement": "°F"}
    neighbour = _unit_room(contact_reference_temperatures={"binary_sensor.r_f": "sensor.n_t"},
                           contact_reference_humidities={"binary_sensor.r_f": "sensor.n_h"})
    initial = {"sensor.r_t": (20.0, T_C), "sensor.r_h": (65.0, H_PCT), "sensor.n_t": (41.0, room_f), "sensor.n_h": (70.0, H_PCT), **_outdoor()}
    rows = {r["entity_id"]: r for r in _chain([neighbour], initial, [{"advance": 60}])[-1]["rooms"]["r"]["opening_assessments"]}
    assert rows["binary_sensor.r_f"]["available"] and rows["binary_sensor.r_f"]["reference_temperature_c"] == pytest.approx(5.0)
    display = golden._room("m", "Wintergarten", "ground_floor", temp=["sensor.m_t"], hum=["sensor.m_h"], volume=20, include=False)
    initial = {"sensor.m_t": (68.0, room_f), "sensor.m_h": (50.0, H_PCT), **_outdoor()}
    shown = _chain([display], initial, [{"advance": 60}])[-1]["rooms"]["m"]
    assert shown["temperature"] == pytest.approx(20.0)
    steps = [{"advance": 60}, {"advance": 60, "set": {"binary_sensor.r_f": "on"}}]
    steps += [{"advance": 60, "set": {"sensor.r_t": (68.0 - 0.2 * i, room_f), "sensor.r_h": (65.0 - i, H_PCT)}} for i in range(1, 9)]
    steps += [{"advance": 60, "set": {"binary_sensor.r_f": "off"}}] + [{"advance": 60} for _ in range(4)]
    opened = _chain([_unit_room(contact_reference_temperatures={"binary_sensor.r_f": "sensor.n_t"},
                                contact_reference_humidities={"binary_sensor.r_f": "sensor.n_h"})],
                    {"sensor.r_t": (68.0, room_f), "sensor.r_h": (65.0, H_PCT), "sensor.n_t": (41.0, room_f), "sensor.n_h": (70.0, H_PCT),
                     **_outdoor()}, steps)
    running = next(c for c in opened if c["rooms"]["r"].get("active"))["rooms"]["r"]
    assert running["temperature"] == pytest.approx(20.0) and running["reference_humidity"] == pytest.approx(4.75, abs=0.01)
    ended = [c for c in opened if c.get("last_ventilation")]
    assert ended and ended[-1]["last_ventilation"]["temp_delta_c"] == pytest.approx(-1.6 * 5 / 9, abs=0.01)   # end values in °C as well


def test_f09_the_neighbouring_room_of_an_exhaust_fan_in_fahrenheit():
    room = golden._room("r", "Bad", "ground_floor", temp=["sensor.r_t"], hum=["sensor.r_h"], volume=50, exhaust="fan.x",
                        extra={"exhaust_fan_reference_temperature": "sensor.n_t", "exhaust_fan_reference_humidity": "sensor.n_h"})
    cycle = _chain([room], {"sensor.r_t": (20.0, T_C), "sensor.r_h": (65.0, H_PCT), "sensor.n_t": (41.0, {"unit_of_measurement": "°F"}),
                            "sensor.n_h": (70.0, H_PCT), "fan.x": ("on", {}), **_outdoor(12.0)}, [{"advance": 60}])[-1]
    assert cycle["rooms"]["r"]["reference_path"] == "neighbour_room"
    assert cycle["rooms"]["r"]["reference_humidity"] == pytest.approx(4.75, abs=0.01)     # 5 °C / 70 %, not 41 °C / 70 %


@pytest.mark.parametrize("speed,unit", [(3.6, "km/h"), (1.0, "m/s"), (2.2369362921, "mph"), (3.6, None), (1.9438444924, "kn")])
def test_f10_the_same_wind_gives_the_same_airflow_factor(speed, unit):
    hass = ha_stub.HomeAssistant()
    attrs = {"wind_bearing": 0, "wind_speed": speed, **({"wind_speed_unit": unit} if unit else {})}
    hass.states.async_set("weather.w", "cloudy", attrs)
    bearing, kmh = _weather_wind(hass, "weather.w")
    # before: 1.216 / 1.060 / 1.134 for the same 1 m/s north wind; the km/h calibration stays
    assert kmh == pytest.approx(3.6) and _orientation_factor("n", bearing, kmh, True) == 1.216
    assert _orientation_factor("n", bearing, kmh, False) == 1.0                          # wind bonus off
    # the house map converts the raw entity value itself – no second conversion
    assert wind_state(bearing=0, speed=speed, unit=unit)["speed_ms"] == pytest.approx(1.0, abs=0.01)


def test_f10_an_unknown_wind_unit_gives_no_bonus():
    hass = ha_stub.HomeAssistant()
    hass.states.async_set("weather.w", "cloudy", {"wind_bearing": "N", "wind_speed": 9, "wind_speed_unit": "beaufort"})
    bearing, speed = _weather_wind(hass, "weather.w")
    assert bearing == 0.0 and speed is None and _orientation_factor("n", bearing, speed, True) == 1.0
    assert _weather_wind(hass, None) == (None, None) and _weather_wind(hass, "weather.missing") == (None, None)


def _advisor_chain(humidity_attrs, humidity_value=9.79):
    room = golden._room("r", "Raum", "ground_floor", temp=["sensor.r_t"], hum=["sensor.r_h"],
                        contacts=["binary_sensor.fenster", "binary_sensor.tuer"], volume=50,
                        extra={"contact_reference_temperatures": {"binary_sensor.tuer": "sensor.n_t"},
                               "contact_reference_humidities": {"binary_sensor.tuer": "sensor.n_ah"}})
    initial = {"sensor.r_t": (20.0, T_C), "sensor.r_h": (65.0, H_PCT), "sensor.aussen_t": (5.0, T_C), "sensor.aussen_h": (70.0, H_PCT),
               "sensor.n_t": (20.0, T_C), "sensor.n_ah": (humidity_value, humidity_attrs),
               "binary_sensor.fenster": ("off", {"device_class": "window"}), "binary_sensor.tuer": ("off", {"device_class": "door"})}
    last = _chain([room], initial, [{"advance": 60}], options={"operating_profile": "dehumidify"})[-1]
    advice = enrich_opening_recommendation({"kind": "ventilate", "room_keys": ["r"]}, last["rooms"], {"operating_profile": "dehumidify"})
    return {r["entity_id"]: r for r in last["rooms"]["r"]["opening_assessments"]}, advice


def test_f13_the_opening_advisor_drops_a_reference_in_another_unit_and_keeps_the_outdoor_window():
    rows, advice = _advisor_chain({"unit_of_measurement": "g/m³"})
    # before: 9.79 g/m³ read as 9.79 % → 476 ml and "open the door, keep the window closed"
    assert rows["binary_sensor.tuer"]["available"] is False and rows["binary_sensor.fenster"]["potential_ml"] == 323
    assert advice["opening_guidance"][0]["preferred"] == ["binary_sensor.fenster"] and advice["opening_guidance"][0]["avoid"] == []
    assert "fenster öffnen" in advice["instruction"] and "tuer" not in advice["instruction"]


def test_f13_a_valid_percent_reference_is_still_assessed():
    rows, advice = _advisor_chain(H_PCT, 40.0)
    assert rows["binary_sensor.tuer"]["available"] and rows["binary_sensor.tuer"]["reference_humidity_percent"] == 40.0
    assert advice["kind"] == "ventilate"


# ------------------------------------------------------------------------------------------------ F11 floor plan save

@pytest.fixture
def house_map(monkeypatch):
    """house_map with the few Home Assistant pieces it imports beyond the golden stub."""
    import importlib
    import types

    vol = types.ModuleType("voluptuous")
    vol.Required = vol.Optional = lambda key, **_k: key
    ws = types.ModuleType("homeassistant.components.websocket_api")
    ws.ActiveConnection = object
    ws.websocket_command = lambda schema: (lambda f: f)
    ws.require_admin = lambda f: setattr(f, "admin_only", True) or f
    ws.async_response = lambda f: f
    components = types.ModuleType("homeassistant.components")
    components.__path__, components.websocket_api = [], ws
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_connect, dispatcher.async_dispatcher_send = (lambda *a, **k: (lambda: None)), (lambda *a, **k: None)
    helpers_json = types.ModuleType("homeassistant.helpers.json")
    helpers_json.json_bytes = lambda value: json.dumps(value).encode()
    for name, module in {"voluptuous": vol, "homeassistant.components": components, "homeassistant.components.websocket_api": ws,
                         "homeassistant.helpers.dispatcher": dispatcher, "homeassistant.helpers.json": helpers_json}.items():
        if name not in sys.modules or not hasattr(sys.modules[name], next(iter(vars(module).keys() - {"__name__", "__doc__", "__package__", "__loader__", "__spec__"}), "")):
            monkeypatch.setitem(sys.modules, name, module)
    for name, attribute, value in (("homeassistant.core", "callback", lambda f: f), ("homeassistant.core", "HomeAssistant", object),
                                   ("homeassistant.helpers.storage", "Store", ha_stub.Store)):
        if not hasattr(sys.modules[name], attribute):                                    # another test's lighter stub is loaded
            monkeypatch.setattr(sys.modules[name], attribute, value, raising=False)
    monkeypatch.delitem(sys.modules, "custom_components.freshairiq.house_map", raising=False)
    module = importlib.import_module("custom_components.freshairiq.house_map")
    yield module
    sys.modules.pop("custom_components.freshairiq.house_map", None)


class _Connection:
    def __init__(self):
        self.sent = []

    def send_error(self, msg_id, code, _message):
        self.sent.append((msg_id, "error", code))

    def send_result(self, msg_id, result):
        self.sent.append((msg_id, "result", result["revision"]))


def _layout_hass(house_map, entries=("e1",), fail_writes=0):
    writes = {"fail": fail_writes}

    class SlowStore(ha_stub.Store):
        async def async_save(self, data):
            await asyncio.sleep(0)                                                       # a real write yields to the loop
            if writes["fail"]:
                writes["fail"] -= 1
                raise OSError("disk full")
            await super().async_save(data)

    house_map.Store = SlowStore
    hass = ha_stub.HomeAssistant()
    loaded = {e: SimpleNamespace(entry_id=e, data={"rooms": [], "levels": ["f_g"]}, runtime_data=SimpleNamespace(data={"rooms": {}}, options={}))
              for e in entries}
    hass.config_entries = SimpleNamespace(async_get_entry=loaded.get, async_entries=lambda _d: list(loaded.values()))
    return hass


def _plan(north):
    return {"building": {"north_deg": north}}


def _save(house_map, hass, connection, msg_id, north, base=0, entry="e1"):
    return house_map.ws_save(hass, connection, {"id": msg_id, "entry_id": entry, "layout": _plan(north), "base_revision": base})


def test_f11_two_concurrent_saves_on_one_revision_give_one_success_and_one_conflict(house_map):
    for first in (10.0, 20.0):
        ha_stub.Store._MEMORY.clear()
        hass, connection = _layout_hass(house_map), _Connection()

        async def both():
            await asyncio.gather(_save(house_map, hass, connection, 1, first), _save(house_map, hass, connection, 2, 30.0 - first))
            return await house_map._store(hass, "e1")

        store = asyncio.run(both())
        # before: both requests succeeded with revision 1
        assert sorted(connection.sent) == [(1, "result", 1), (2, "error", "revision_conflict")]
        assert store.revision() == 1 and store.raw["building"]["north_deg"] == first
    assert house_map.ws_save.admin_only is True                                          # admin protection kept


def test_f11_a_failed_write_is_no_success_and_no_new_revision_and_stores_are_independent(house_map):
    ha_stub.Store._MEMORY.clear()
    hass, connection = _layout_hass(house_map, entries=("e1", "e2"), fail_writes=1), _Connection()
    with pytest.raises(OSError):
        asyncio.run(_save(house_map, hass, connection, 1, 10.0))
    store = asyncio.run(house_map._store(hass, "e1"))
    assert connection.sent == [] and store.revision() == 0 and store.raw is None and not store.lock.locked()
    asyncio.run(_save(house_map, hass, connection, 2, 20.0))
    assert connection.sent == [(2, "result", 1)]

    async def independent():
        await asyncio.gather(_save(house_map, hass, connection, 3, 5.0, entry="e2"), _save(house_map, hass, connection, 4, 6.0, base=1))
    asyncio.run(independent())
    assert (3, "result", 1) in connection.sent and (4, "result", 2) in connection.sent
    asyncio.run(_save(house_map, hass, connection, 5, 7.0, base=1))
    assert connection.sent[-1] == (5, "error", "revision_conflict")


# ------------------------------------------------------------------------------------------------ F12 clock changes

NIGHT = {"night_start_hour": "22:00", "night_end_hour": "07:00", "adult_occupants": 0, "child_occupants": 0,
         "background_night_moisture_ml_h": 100.0, "night_forecast_enabled": True}


@pytest.mark.parametrize("day,hours", [((2026, 3, 28), 8.0), ((2026, 10, 24), 10.0), ((2026, 11, 16), 9.0)])
def test_f12_a_night_lasts_its_real_hours_across_a_clock_change(day, hours):
    start, end = night_interval_bounds(datetime(*day, 12, 0, tzinfo=TZ), "22:00", "07:00")
    assert (start.hour, end.hour) == (22, 7)                                             # found by the local clock
    assert elapsed_minutes(start, end) / 60.0 == hours                                   # before: 9 h every night
    assert overnight_forecast_ml(NIGHT, None, 0, hours=hours) == round(hours * 100)
    data = _chain([_unit_room()], {"sensor.r_t": (20.0, T_C), "sensor.r_h": (55.0, H_PCT), **_outdoor()}, [{"advance": 60}],
                  options=NIGHT, start=datetime(*day, 12, 0, tzinfo=TZ))[-1]
    assert data["overnight_forecast_base_ml"] == round(hours * 100)


def test_f12_rest_of_night_rain_distance_and_zones_without_a_change():
    # rest of the night inside the repeated hour: 02:30 (+02) → 07:00 (+01) are 5.5 real hours
    now = datetime(2026, 10, 25, 2, 30, tzinfo=TZ, fold=0)
    start, end = night_interval_bounds(now, "22:00", "07:00")
    assert start == now and elapsed_minutes(start, end) == 330.0
    assert elapsed_minutes(datetime(2026, 10, 25, 2, 30, tzinfo=TZ, fold=1), end) == 270.0
    rain = {"datetime": datetime(2026, 10, 25, 2, 40, tzinfo=TZ, fold=1), "condition": "rainy"}
    assert minutes_until_rain([rain], datetime(2026, 10, 25, 2, 10, tzinfo=TZ, fold=0)) == 90   # before: 30
    assert minutes_until_rain([rain], datetime(2026, 10, 25, 2, 10, tzinfo=TZ, fold=1)) == 30
    for zone in ("Asia/Tokyo", "UTC"):
        bounds = night_interval_bounds(datetime(2026, 10, 24, 12, 0, tzinfo=ZoneInfo(zone)), "22:00", "07:00")
        assert elapsed_minutes(*bounds) == 540.0
    naive = night_interval_bounds(datetime(2026, 10, 24, 12, 0), "22:00", "07:00")    # no zone: the plain difference
    assert elapsed_minutes(*naive) == 540.0


def test_f12_the_night_rain_distance_of_the_coordinator_uses_real_minutes():
    start = datetime(2026, 10, 25, 2, 10, tzinfo=TZ)
    golden_forecast = golden._forecast

    def forecast(_start, hours=24, temp=9.0, hum=82.0):
        rows = golden_forecast(_start, hours, temp, hum)
        for row in rows:
            row["precipitation"], row["condition"] = 0.0, "cloudy"
        rows.insert(0, {"datetime": "2026-10-25T02:40:00+01:00", "temperature": 9.0, "humidity": 82.0, "precipitation": 2.0,
                        "condition": "rainy"})
        return rows

    golden._forecast = forecast
    try:
        data = _chain([_unit_room()], {"sensor.r_t": (20.0, T_C), "sensor.r_h": (55.0, H_PCT), **_outdoor()}, [{"advance": 60}],
                      options=NIGHT, data={"outdoor_weather": "weather.home"}, start=start)[-1]
    finally:
        golden._forecast = golden_forecast
    assert data["night_strategy"]["minutes_until_rain"] == 89                            # 02:11 (+02) → 02:40 (+01)


# ------------------------------------------------------------------------------------------------ F14 notifications

def _notify(order, *, cycles=2, kind="close", store=None, gap=10, broken=("broken",), later_min=0, rooms=("r",)):
    hass = ha_stub.HomeAssistant()
    sent = []
    hass.services.has_service = lambda domain, _service: domain == "notify"

    async def call(_domain, service, _data=None, **_kw):
        sent.append(service)
        if service.removeprefix("mobile_app_") in broken:
            raise RuntimeError("Service unavailable")

    hass.services.async_call = call
    store = store or SimpleNamespace(data={"rooms": {}, "notifications": {}, "notification_diagnostics": []})
    store.room = lambda key: store.data["rooms"].setdefault(key, {})
    options = {"notifications_enabled": True, "notification_targets": [f"notify.mobile_app_{n}" for n in order], "notify_close": True,
               "notify_ventilate": True, "notification_scope": "house", "notification_cooldown_min": 90}
    data = {"rooms": {"r": {"key": "r", "name": "Raum", "action": "Close", "active": True, "data_quality": "ok"}},
            "intelligent_recommendation": {"kind": kind, "room_keys": list(rooms), "instruction": f"{kind} {rooms}", "title": kind}}
    start = datetime(2026, 11, 17, 12, 0, tzinfo=TZ) + timedelta(minutes=later_min)
    for cycle in range(cycles):
        asyncio.run(notifications.process_notifications(hass, store, data, options, start + timedelta(seconds=gap * cycle), []))
    return sent, store


def _rows(store):
    return [(r["status"], r.get("reason"), r.get("exception_type")) for r in store.data["notification_diagnostics"]]


@pytest.mark.parametrize("order", [("broken", "healthy"), ("healthy", "broken")])
def test_f14_a_broken_recipient_never_stops_or_duplicates_the_healthy_one(order):
    sent, store = _notify(order)
    # before: broken→healthy reached nobody, healthy→broken sent the healthy phone the same message twice
    assert sent.count("mobile_app_healthy") == 1 and sent.count("mobile_app_broken") == 2
    assert ("failed", "notify_service_exception", "RuntimeError") in _rows(store) and ("sent", None, None) in _rows(store)
    assert store.data["notification_deliveries"]["iq_close:house"]["accepted"] == ["notify.mobile_app_healthy"]


def test_f14_the_broken_recipient_is_retried_a_bounded_number_of_times_then_the_message_is_done():
    sent, store = _notify(("broken", "healthy"), cycles=NOTIFY_TARGET_ATTEMPTS + 3)
    assert sent.count("mobile_app_broken") == NOTIFY_TARGET_ATTEMPTS and sent.count("mobile_app_healthy") == 1
    assert store.data["notification_deliveries"] == {} and store.data["last_house_recommendation_signature"].startswith("close:")
    assert "iq_close:house" in store.data["notifications"]                               # the cooldown starts when it is done
    # a new recommendation reaches the healthy recipient again once it may be sent (the close cooldown is over)
    more, store = _notify(("broken", "healthy"), cycles=1, store=store, later_min=91, rooms=("r", "s"))
    assert more == ["mobile_app_broken", "mobile_app_healthy"]


def test_f14_all_recipients_failing_keeps_the_message_open_and_a_recovered_service_gets_it_once():
    sent, store = _notify(("a", "b"), cycles=1, broken=("a", "b"))
    assert sent == ["mobile_app_a", "mobile_app_b"] and "last_house_recommendation_signature" not in store.data
    later, store = _notify(("a", "b"), cycles=1, broken=("a",), store=store)
    assert later == ["mobile_app_a", "mobile_app_b"]
    last, store = _notify(("a", "b"), cycles=1, broken=(), store=store)
    assert last == ["mobile_app_a"] and store.data["notification_deliveries"] == {}


def test_f14_errors_outside_a_recipient_and_repeated_misses_are_recorded_as_before():
    store = SimpleNamespace(data={"rooms": {}, "notifications": {}, "notification_diagnostics": []})
    hass = ha_stub.HomeAssistant()
    hass.services.has_service = lambda *_a: False                                         # no notify service at all

    async def broken(_outcome):
        raise ValueError("wording")

    now = datetime(2026, 11, 17, 12, 0, tzinfo=TZ)
    assert asyncio.run(notifications._push(hass, store, {}, now, broken, event="iq_close", scope="house", key="k", signature="s")) == (False, False, True)
    assert _rows(store)[-1] == ("failed", "notify_service_exception", "ValueError")

    async def nobody(outcome):
        return False

    first = asyncio.run(notifications._push(hass, store, {}, now, nobody, event="iq_close", scope="house", key="k", signature="s"))
    again = asyncio.run(notifications._push(hass, store, {}, now + timedelta(seconds=10), nobody, event="iq_close", scope="house", key="k",
                                            signature="s"))
    assert first == (False, False, True) and again == (False, False, False)              # the repeat folds into the row
    assert _rows(store)[-1] == ("not_sent", "no_available_notify_service", None) and store.data["notification_deliveries"] == {}


def test_f14_room_messages_isolate_recipients_too():
    hass = ha_stub.HomeAssistant()
    sent = []
    hass.services.has_service = lambda domain, _service: domain == "notify"

    async def call(_domain, service, _data=None, **_kw):
        sent.append(service)
        if service == "mobile_app_broken":
            raise RuntimeError("down")

    hass.services.async_call = call
    outcome = notifications._outcome()
    options = {"notification_targets": ["notify.mobile_app_broken", "notify.mobile_app_healthy"]}
    assert asyncio.run(notifications._send_room_personalised(hass, options, "T", "M", "r", "close", outcome)) is True
    assert outcome["accepted"] == ["notify.mobile_app_healthy"] and outcome["failed"] == {"notify.mobile_app_broken": "RuntimeError"}
    assert asyncio.run(notifications._send(hass, options, "T", "M", "night")) is True    # the night message as well
    assert sent == ["mobile_app_broken", "mobile_app_healthy"] * 2


# ------------------------------------------------------------------------------------------------ F16 learning switch

def _learning_chain(enabled, start, steps, seed):
    stores = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def hook(self):
        seed(self)
        result = await original(self)
        stores.append(copy.deepcopy(self.store.data))
        return result

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = hook
    try:
        data = _chain([_unit_room()], {"sensor.r_t": (20.0, T_C), "sensor.r_h": (55.0, H_PCT), **_outdoor()}, steps,
                      options={**NIGHT, "learning_enabled": enabled}, start=start)
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return stores, data


def _with_source(coordinator):
    room = coordinator.store.data.get("rooms", {}).get("r")
    if room is not None and room.get("forecast_source_ml_min") is None:
        room["forecast_source_ml_min"] = 2.0


@pytest.mark.parametrize("enabled,expected", [(False, (0, 0)), (True, (1, 1))])
def test_f16_routine_and_season_samples_follow_the_learning_switch(enabled, expected):
    stores, _data = _learning_chain(enabled, datetime(2026, 11, 17, 12, 0, tzinfo=TZ), [{"advance": 60}, {"advance": 60}], _with_source)
    room = stores[-1]["rooms"]["r"]
    assert (room.get("routine_source_samples"), room.get("seasonal_samples")) == expected   # before: 1 / 1 with learning off


@pytest.mark.parametrize("enabled", [False, True])
def test_f16_night_learning_follows_the_switch_and_keeps_the_forecast_and_known_rate(enabled):
    state = {"seeded": False}

    def seed(coordinator):
        data = coordinator.store.data
        if not state["seeded"]:
            data.update(night_model_ml_h=80.0, night_model_samples=3)
        if data.get("night_last_snapshot") and not state["seeded"]:
            state["seeded"] = True
            data["night_last_water_ml"] -= 25                                            # +25 ml within 15 minutes = 100 ml/h

    stores, data = _learning_chain(enabled, datetime(2026, 11, 17, 23, 0, tzinfo=TZ), [{"advance": 900}], seed)
    model = (stores[-1]["night_model_samples"], stores[-1]["night_model_ml_h"])
    assert model == ((4, 83.6) if enabled else (3, 80.0))                                # before: learned with learning off
    assert data[-1]["overnight_forecast_ml"] > 0


# ------------------------------------------------------------------------------------------------ field cases 2026-11

# Support case of installation 13 (0.26.7.0, bedroom 34.3 m³, three-state window): seconds after 17:01:33, room °C,
# room %, CO₂ ppm, window, outdoor °C, outdoor %. In the field the airing ran 64 minutes without a close advice.
SUPPORT_13 = [(0, 19.0, 53, 1620, "closed", 7.18, 74.65), (903, 19.4, 56, 1975, "closed", 6.74, 75.48),
              (1196, 19.5, 56, 2064, "tilted", 6.39, 75.48), (1320, 19.5, 56, 2012, "tilted", 6.39, 75.48),
              (1451, 19.5, 54, 2012, "tilted", 6.39, 75.48), (1572, 19.4, 54, 2012, "tilted", 6.39, 75.48),
              (1653, 19.4, 54, 1457, "tilted", 6.39, 75.48), (1785, 19.3, 54, 1457, "tilted", 6.39, 75.48),
              (1906, 19.2, 54, 1080, "tilted", 6.39, 75.48), (2157, 19.2, 54, 1080, "tilted", 6.39, 75.48),
              (2278, 19.1, 54, 866, "tilted", 5.98, 77.87), (2528, 19.1, 54, 866, "tilted", 5.87, 78.16),
              (2770, 19.0, 54, 850, "tilted", 5.87, 78.16), (3015, 18.7, 52, 836, "tilted", 5.87, 78.16),
              (3499, 18.7, 52, 798, "tilted", 5.87, 78.16), (4229, 18.6, 52, 798, "tilted", 5.36, 79.86),
              (4722, 18.5, 51, 805, "tilted", 5.36, 79.86), (5035, 18.5, 51, 805, "closed", 5.36, 79.86)]


def test_support_13_a_co2_airing_gets_its_close_advice_once_the_goals_are_reached():
    lage = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
    co2 = {"device_class": "carbon_dioxide", "unit_of_measurement": "ppm"}
    room = golden._room("schlafzimmer", "Schlafzimmer", "ground_floor", temp=["sensor.t"], hum=["sensor.h"], contacts=["sensor.lage"],
                        volume=34.269, co2="sensor.co2", orientation="east")

    def states(row):
        _s, t, rh, ppm, window, out_t, out_rh = row
        return {"sensor.t": (t, T_C), "sensor.h": (rh, H_PCT), "sensor.co2": (ppm, co2), "sensor.lage": (window, lage),
                "sensor.aussen_t": (out_t, T_C), "sensor.aussen_h": (out_rh, H_PCT)}

    steps = [{"advance": row[0] - prev[0], "set": states(row)} for prev, row in itertools.pairwise(SUPPORT_13)]
    options = {"target_rh": 58.0, "close_delta": 0.4, "min_duration_min": 5.0, "max_duration_min": 60.0, "min_return_next_5_min_ml": 25.0,
               "max_temp_loss_next_5_min_c": 0.6, "min_efficiency_ml_per_01c": 8.0, "co2_warn": 1000.0, "co2_critical": 1400.0,
               "co2_release": 0.0, "operating_profile": "comfort"}
    cycles = _chain([room], states(SUPPORT_13[0]), steps, options=options, start=datetime(2026, 11, 14, 17, 1, 33, tzinfo=TZ))[1:]
    actions = [(row[0], row[3], cycle["rooms"]["schlafzimmer"]["action"]) for row, cycle in zip(SUPPORT_13[1:], cycles)]
    first_close = next(s for s, _ppm, action in actions if action == "Close")
    # 0.26.7.0 in the field: "Continue ventilating" until the window was closed by hand after 64 minutes
    assert first_close - 1196 <= 20 * 60
    assert all(action != "Close" for s, ppm, action in actions if s < first_close)        # not before CO₂ fell below the band
    assert all(ppm < 950 for s, ppm, action in actions if action == "Close")
    assert all(action == "Close" for s, ppm, action in actions if first_close <= s < 5035)


def test_support_134_the_co2_band_gives_one_advice_per_rise_and_no_ping_pong():
    co2 = {"device_class": "carbon_dioxide", "unit_of_measurement": "ppm"}
    room = golden._room("wz", "Wohnzimmer", "ground_floor", temp=["sensor.t"], hum=["sensor.h"], contacts=["binary_sensor.f"], volume=50,
                        co2="sensor.co2")
    trace = [("off", 1050), ("off", 1050), ("on", 1000), ("on", 950), ("on", 850), ("on", 760), ("on", 740), ("on", 740), ("off", 760),
             ("off", 800), ("off", 900), ("off", 980), ("off", 990)]
    initial = {"sensor.t": (21.0, T_C), "sensor.h": (45.0, H_PCT), "sensor.co2": (900, co2), "binary_sensor.f": ("off", {"device_class": "window"}),
               "sensor.aussen_t": (8.0, T_C), "sensor.aussen_h": (80.0, H_PCT)}
    steps = [{"advance": 180, "set": {"binary_sensor.f": window, "sensor.co2": (ppm, co2)}} for window, ppm in trace]
    cycles = _chain([room], initial, steps, options={"co2_warn": 1000, "co2_release": 750, "co2_critical": 1400})[1:]
    goals = [next(g for g in c["rooms"]["wz"]["goal_state"]["goals"] if g["id"] == "co2") for c in cycles]
    actions = [c["rooms"]["wz"]["action"] for c in cycles]
    # the started CO₂ airing aims at the release level until it is reached, then the warning level is the target again
    assert [g["target"] for g in goals[:6]] == [750.0] * 6 and not any(g["reached"] for g in goals[:6])
    assert all(g["target"] == 1000.0 and g["reached"] for g in goals[6:])
    # one advice to air; between 750 and 1000 ppm after the airing no new advice (no ping-pong)
    assert actions[:2] == ["Ventilate", "Ventilate"] and "Ventilate" not in actions[2:]
