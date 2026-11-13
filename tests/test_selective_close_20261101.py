"""Hotfix 01.11. (S1/S2): an older window's own close is not swallowed by a window opened later.

S1  Room A aired 20 minutes and released its own close (fresh readings, ``Close``); room B was
    opened half a minute ago. The floor/house aggregate said "keep ventilating" for both and the
    presentation turned A's ``Close`` into "Continue ventilating". Now: A ``Close``, B keeps airing.
S2  The live-coach fields (state, remaining time) described the earlier close while the final
    decision was "continue" – and a ``None`` remaining time could reach a ``float()``.

The chain runs through the real coordinator (golden-master harness: real sensor states, sessions,
evaluate_room, live coach, consolidation, floor/house decision, presentation, room export).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

from custom_components.freshairiq.live_coach import align_live_coach_state
from custom_components.freshairiq.opening_strategy import (
    close_rooms_released_on_their_own,
    keep_moisture_sources_open,
    synchronize_room_presentation_actions,
)

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _golden():
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import coordinator_golden as golden  # noqa: PLC0415 – the harness installs its Home Assistant stub
    return golden


def _scenario(golden, extra_rooms: int):
    keys = ["a", "b"] + [f"r{i}" for i in range(extra_rooms)]
    rooms = [golden._room(k, f"Raum {k.upper()}", "ground_floor" if i < 3 else "upper_floor", temp=[f"sensor.{k}_t"], hum=[f"sensor.{k}_h"],
                          contacts=[f"binary_sensor.{k}_f"], volume=45, sort=i) for i, k in enumerate(keys)]
    temp = {"device_class": "temperature", "unit_of_measurement": "°C"}
    hum = {"device_class": "humidity", "unit_of_measurement": "%"}
    initial = {"sensor.aussen_t": (11.0, temp), "sensor.aussen_h": (55.0, hum)}
    for k in keys:
        initial.update({f"sensor.{k}_t": (23.0, temp), f"sensor.{k}_h": (69.0 if k in {"a", "b"} else 50.0, hum),
                        f"binary_sensor.{k}_f": ("off", {"device_class": "window"})})
    steps = [{"advance": 60, "label": "idle"}, {"advance": 60, "set": {"binary_sensor.a_f": "on"}, "label": "A open"}]
    h = 69.0
    for i in range(20):
        h = max(h - (1.2 if i < 8 else 0.0), 55)
        steps.append({"advance": 60, "set": {"sensor.a_h": round(h + (0.01 if i % 2 else 0), 2), "sensor.a_t": round(23.0 - 0.05 * min(i, 8), 2)}})
    # Testvermerk 0.26.7.0 (F11): a plateau or a small return with clearly drier outdoor air no longer closes A (there
    # is no maximum duration). For A to release its own close, the outdoor air turns humid enough that it no longer
    # dries A (difference below close_delta) – while it still dries the much more humid young room B.
    steps.append({"advance": 60, "set": {"sensor.aussen_t": 14.0, "sensor.aussen_h": 93.0}, "label": "outdoor humid"})
    steps.append({"advance": 60, "set": {"sensor.a_h": 55.01}})
    steps.append({"advance": 60, "set": {"sensor.a_h": 55.0}})
    steps.append({"advance": 30, "set": {"binary_sensor.b_f": "on"}, "label": "B open"})
    steps.append({"advance": 30, "label": "B 0.5 min"})
    data = {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": rooms, "levels": ["ground_floor", "upper_floor"]}
    return {"start": datetime(2026, 10, 20, 18, 0, tzinfo=golden.TZ), "data": data,
            "options": {**golden.BASE_OPTIONS, "min_duration_min": 3}, "steps": steps, "initial": initial}


def _run(extra_rooms: int) -> list[dict]:
    golden = _golden()
    seen: list[dict] = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        data = await original(self)
        seen.append(data)
        return data

    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    try:
        asyncio.run(golden._run_scenario("selective", _scenario(golden, extra_rooms), None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    return seen


@pytest.mark.parametrize(("extra", "scope"), [(0, "house"), (2, "floor")])
def test_s1_s2_real_chain_closes_a_and_keeps_b(extra, scope) -> None:
    final = _run(extra)[-1]
    rec = final["intelligent_recommendation"]
    a, b = final["rooms"]["a"], final["rooms"]["b"]
    assert rec["presentation_scope"] == scope
    # S1: the older window closes, the young one keeps airing – in the room export and the house text
    assert (a["action"], a["close_recommended"], a["house_aligned_action"]) == ("Close", True, "close")
    assert (b["action"], b["house_aligned_action"]) == ("Continue ventilating", "continue_ventilating")
    assert "canonical_action" not in a or a["canonical_action"] == "Close"
    assert rec["kind"] == "close" and rec["room_keys"] == ["a"] and rec["kept_running_room_keys"] == ["b"]
    assert rec["instruction"] == "Raum A schließen · Raum B offen lassen"
    assert rec["decision_brain"]["decision_label"] == "JETZT SCHLIESSEN"
    # S2: one state everywhere – the coach says close, 0 min, the IQ time is a number (over target)
    assert rec["live_coach_state"] == "close" and rec["live_coach_remaining_min"] == 0.0
    assert isinstance(final["remaining_duration_min"], float) and final["remaining_duration_min"] <= 0
    # the push path reads the same: A is asked to close, B is not
    from custom_components.freshairiq.notification_policy import effective_room_action  # noqa: PLC0415
    assert effective_room_action(a, rec, final["rooms"]) == "Close"
    assert effective_room_action(b, rec, final["rooms"]) == "Continue ventilating"


def _room(key, *, action="Continue ventilating", released=False, ready=True, elapsed=10.0, **extra):
    room = {"key": key, "name": key.upper(), "active": True, "action": action, "close_recommended": released,
            "close_decision_ready": ready, "session_elapsed_min": elapsed, "delta_g_m3": 1.2, "configured_actuators": {"window_open": True}}
    room.update(extra)
    return room


def _rec(keys, scope="floor", **extra):
    return {"kind": "continue", "status": "ventilation_running", "presentation_scope": scope, "room_keys": list(keys),
            "title": "Etagenlüftung läuft", "instruction": "Erdgeschoss gemeinsam weiterlüften", "summary": "s", "reasons": ["r"],
            "decision_brain": {"decision_label": "ETAGENLÜFTUNG", "impact": {"duration_min": 4.0}}, **extra}


def _final(rec, rooms, options=None):
    close_rooms_released_on_their_own(rec, rooms)
    keep_moisture_sources_open(rec, rooms, options or {"close_delta": 0.4})
    align_live_coach_state(rec)
    synchronize_room_presentation_actions(rec, rooms, min_duration_min=3.0)
    return rec, {k: r["action"] for k, r in rooms.items()}


@pytest.mark.parametrize("scope", ["floor", "house"])
def test_s1_selective_close_only_for_a_released_own_close(scope) -> None:
    rooms = {"a": _room("a", action="Close", released=True, elapsed=20.5), "b": _room("b", ready=False, elapsed=0.5)}
    rec, actions = _final(_rec(rooms, scope), rooms)
    assert actions == {"a": "Close", "b": "Continue ventilating"} and rec["kind"] == "close"


def test_s1_variations_leave_the_aggregate_alone() -> None:
    # both windows younger than 3 min: nobody released – the floor keeps airing, nothing closes
    rooms = {"a": _room("a", elapsed=1.0, ready=False), "b": _room("b", elapsed=0.5, ready=False)}
    rec, actions = _final(_rec(rooms), rooms)
    assert rec["kind"] == "continue" and actions == {"a": "Continue ventilating", "b": "Continue ventilating"}
    # both released: the aggregate decision ("continue" for the floor) is kept as it is
    rooms = {"a": _room("a", action="Close", released=True, elapsed=8), "b": _room("b", action="Close", released=True, elapsed=6)}
    rec, _ = _final(_rec(rooms), rooms)
    assert rec["kind"] == "continue"
    # a "Close" not released yet (gate not passed / close not recommended) is no own close
    for a in (_room("a", action="Close", released=True, ready=False), _room("a", action="Close", released=False)):
        rooms = {"a": a, "b": _room("b")}
        assert _final(_rec(rooms), rooms)[0]["kind"] == "continue"
    # room scope and other kinds are not touched
    rooms = {"a": _room("a", action="Close", released=True), "b": _room("b")}
    assert _final(_rec(rooms, "rooms"), rooms)[0]["kind"] == "continue"


def test_s1_moisture_source_co2_fan_only_and_finalising_rooms() -> None:
    # B runs a moisture source (its own decision: keep open) – A closes, B stays open
    rooms = {"a": _room("a", action="Close", released=True, elapsed=20), "b": _room("b", moisture_source_active=True, delta_g_m3=2.0)}
    rec, actions = _final(_rec(rooms), rooms)
    assert actions == {"a": "Close", "b": "Continue ventilating"} and rec["room_keys"] == ["a"]
    # B keeps airing for its CO2 goal (own action Continue): the same
    rooms = {"a": _room("a", action="Close", released=True, elapsed=20), "b": _room("b", co2=1300)}
    assert _final(_rec(rooms), rooms)[1] == {"a": "Close", "b": "Continue ventilating"}
    # a fan alone is never closed by this rule; a room in its final measurement does not count as airing
    fan = _room("a", action="Close", released=True, configured_actuators={"mechanical_exhaust_active": True, "window_open": False})
    rooms = {"a": fan, "b": _room("b")}
    assert _final(_rec(rooms), rooms)[0]["kind"] == "continue"
    rooms = {"a": _room("a", action="Close", released=True), "b": _room("b", session_finalization_pending=True, action="Okay")}
    rec, actions = _final(_rec(rooms), rooms)
    assert rec["kind"] == "continue" and actions["b"] == "Okay"  # nothing else is airing: no selective close
    # every aired room released its own close (also the young one, moisture coming in): this rule leaves the
    # aggregate alone – the floor/house close itself closes on protection (tests/test_staggered_close_026505.py)
    rooms = {"a": _room("a", action="Close", released=True), "b": _room("b", action="Close", released=True, delta_g_m3=-0.6, elapsed=0.5)}
    assert _final(_rec(rooms), rooms)[0]["kind"] == "continue"


@pytest.mark.parametrize(("kind", "state", "remaining", "expected"), [
    ("continue", "close", 0.0, ("awaiting_measurements", None)),          # close -> continue
    ("continue", "protection_close", 0.0, ("awaiting_measurements", None)),
    ("close", "on_track", 4.0, ("close", 0.0)),                           # continue -> close
    ("continue", "on_track", 4.0, ("on_track", 4.0)),                     # unchanged continue
    ("close", "close", 0.0, ("close", 0.0)),
])
def test_s2_live_coach_follows_the_final_decision(kind, state, remaining, expected) -> None:
    rec = {"kind": kind, "summary": "Etage läuft", "live_coach": True, "live_coach_state": state, "live_coach_remaining_min": remaining,
           "duration_min": 0.0 if state in {"close", "protection_close"} else remaining}
    align_live_coach_state(rec)
    assert (rec["live_coach_state"], rec["live_coach_remaining_min"]) == expected
    if expected[1] is None:
        assert rec["duration_min"] is None and rec["live_coach_reason"] == "Etage läuft"


def test_s2_without_a_live_coach_or_a_dict_nothing_changes() -> None:
    rec = {"kind": "continue", "live_coach_state": "close"}
    align_live_coach_state(rec)
    assert rec == {"kind": "continue", "live_coach_state": "close"}
    align_live_coach_state(None)  # type: ignore[arg-type]
    close_rooms_released_on_their_own(None, {})  # type: ignore[arg-type]
