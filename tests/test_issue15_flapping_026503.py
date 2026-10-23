"""0.26.5.3 (GitHub #15): Ventilate/Close flapping in small, chronically humid rooms.

Reported room: 9.4 m³, 61–68 % RH, surface humidity 77–87 % (always above the
mould warning). Observed: "Lüften" – window opened – "Schließen" after about
3 minutes – "Lüften" again 20 minutes later, all day.

* a window opened without a shown FreshAirIQ duration gets a default plan
  (10 min, within min/max duration) instead of being closed at the earliest
  legal moment;
* the repeat cooldown after a close is no longer lifted by "surface RH above
  the warning" – only by the critical level, a rise of >= 3 points since the
  close, critical CO2 (and, unchanged, a strong new source or drier weather);
* no "ventilate" message for a room within the repeat cooldown after its
  "close" message, unless protection is needed (critical mould risk or CO2).
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from tests.test_user_feedback_026409 import T0, _hass, _options, _room, _Store  # installs the HA stubs

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.consolidation import SELF_STARTED_PLAN_MIN, session_target_min
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.notifications import EVENT_NOTIFICATION, process_notifications
from custom_components.freshairiq.repeat_cooldown import SURFACE_RISE_PCT, remember_close_surface_rh, repeat_cooldown_urgent
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OPTIONS = {**DEFAULT_OPTIONS, "operating_profile": "comfort"}


def _types(hass) -> list[str]:
    return [d["type"] for e, d in hass.bus.events if e == EVENT_NOTIFICATION]


def _reported_room(elapsed: float, target: float | None) -> RoomInput:
    return RoomInput(
        "gast", "Gästezimmer", 21.0, 65.0, 10.0, 75.0, 9.4, True, 600,
        session_active=True, session_elapsed_min=elapsed, session_start_temp=21.0,
        learning_rate=0.03, session_fresh_measurements=2, session_target_min=target,
    )


# --- point 2: default plan for a self-started airing ---------------------------------------
def test_a_self_started_airing_gets_the_default_plan() -> None:
    assert SELF_STARTED_PLAN_MIN == 10.0
    assert session_target_min({"rooms": {}}, OPTIONS) == 10.0
    assert session_target_min({"rooms": {}}, {**OPTIONS, "max_duration_min": 6}) == 6.0
    assert session_target_min({"rooms": {}}, {**OPTIONS, "min_duration_min": 12}) == 12.0
    assert session_target_min({"rooms": {}, "recommended_duration_min": 7}, OPTIONS) == 7.0  # a shown duration wins
    assert session_target_min(None, OPTIONS) is None


def test_the_reported_small_room_is_aired_for_the_plan_not_three_minutes() -> None:
    plan = session_target_min({"rooms": {}}, OPTIONS)
    early = evaluate_room(_reported_room(3.5, None), OPTIONS, False)
    assert early.action == "Close"  # old behaviour without a plan
    held = evaluate_room(_reported_room(3.5, plan), OPTIONS, False)
    assert held.action == "Continue ventilating" and not held.close_recommended
    done = evaluate_room(_reported_room(plan + 0.5, plan), OPTIONS, False)
    assert done.action == "Close"


# --- point 3: stricter cooldown override ---------------------------------------------------
def test_the_close_humidity_is_remembered_once_per_airing() -> None:
    mem: dict = {}
    assert not remember_close_surface_rh(mem, 80.0)  # no airing ended yet
    mem["last_ventilation_ended_at"] = "2026-10-09T10:00:00+00:00"
    assert remember_close_surface_rh(mem, 81.04) and mem["repeat_surface_rh_at_close"] == 81.0
    assert not remember_close_surface_rh(mem, 86.0) and mem["repeat_surface_rh_at_close"] == 81.0
    mem["last_ventilation_ended_at"] = "2026-10-09T12:00:00+00:00"
    assert remember_close_surface_rh(mem, 79.0) and mem["repeat_surface_rh_at_close"] == 79.0


def test_only_critical_values_or_a_clear_rise_lift_the_cooldown() -> None:
    def urgent(surface, at_close=80.0, co2=None, **options):
        return repeat_cooldown_urgent(surface_rh=surface, surface_rh_at_close=at_close, co2=co2, options={**OPTIONS, **options})

    assert SURFACE_RISE_PCT == 3.0
    # the reported room: 77–87 %, always above the 80 % warning – no longer urgent by itself
    assert not any(urgent(s, at_close=s) for s in (77.0, 80.0, 84.0, 87.0))
    assert not urgent(82.9, at_close=80.0)
    assert urgent(83.0, at_close=80.0)  # clear rise since the close
    assert not urgent(79.0, at_close=70.0)  # a rise below the warning is no mould urgency
    assert urgent(90.0, at_close=89.0) and urgent(86.0, mould_critical_surface_rh=85.0)
    assert urgent(60.0, co2=1400.0) and not urgent(60.0, co2=1399.0)
    assert not urgent(87.0, at_close=None) and not urgent(87.0, at_close="kaputt")


def test_the_cooldown_uses_the_stricter_rule() -> None:
    source = (ROOT / "custom_components/freshairiq/coordinator_room_result.py").read_text(encoding="utf-8")
    assert "changed |= remember_close_surface_rh(mem, float(result.surface_rh or 0.0))" in source
    assert "urgent_override = repeat_cooldown_urgent(" in source
    assert 'surface_rh >= float(options.get("mould_warn_surface_rh"' not in source


# --- point 4: no "ventilate" right after "close" -------------------------------------------
def _cycle(hass, store, minute, action, *, active=False, **room):
    data = {"rooms": {"bad": _room(action=action, active=active, surface_rh=room.pop("surface_rh", 84), **room)}}
    asyncio.run(process_notifications(hass, store, data, _options(), T0 + timedelta(minutes=minute), []))


def test_no_ventilate_message_within_the_cooldown_after_close() -> None:
    hass, store = _hass(), _Store()
    _cycle(hass, store, 0, "Close", active=True)
    _cycle(hass, store, 5, "Okay")
    _cycle(hass, store, 25, "Ventilate")
    _cycle(hass, store, 119, "Ventilate")
    assert _types(hass) == ["close"]
    assert store.room("bad")["last_action"] == "Okay"
    _cycle(hass, store, 120, "Ventilate")
    assert _types(hass) == ["close", "ventilate"]


def test_a_held_ventilate_that_disappears_is_never_sent() -> None:
    hass, store = _hass(), _Store()
    _cycle(hass, store, 0, "Close", active=True)
    _cycle(hass, store, 20, "Ventilate")
    _cycle(hass, store, 40, "Close", active=False)
    _cycle(hass, store, 200, "Close", active=False)
    assert _types(hass) == ["close"]


def test_protection_still_asks_to_ventilate_at_once() -> None:
    hass, store = _hass(), _Store()
    _cycle(hass, store, 0, "Close", active=True)
    _cycle(hass, store, 20, "Ventilate", surface_rh=90)
    assert _types(hass) == ["close", "ventilate"]
    hass, store = _hass(), _Store()
    _cycle(hass, store, 0, "Close", active=True)
    _cycle(hass, store, 20, "Ventilate for cooling", co2=1500)
    assert store.room("bad")["last_action"] == "Ventilate for cooling"
    hass, store = _hass(), _Store()
    _cycle(hass, store, 0, "Close", active=True)
    _cycle(hass, store, 20, "Ventilate", co2=1500, co2_available=False)
    assert _types(hass) == ["close"]  # a CO2 value the room does not use is no protection
    _cycle(hass, store, 21, "Ventilate", surface_rh="kaputt")
    assert _types(hass) == ["close", "ventilate"]  # unreadable value: never hold a message


def test_older_state_and_other_options() -> None:
    hass, store = _hass(), _Store()
    store.room("bad")["last_action"] = "Close"  # stored by 0.26.5.2: no close time
    _cycle(hass, store, 0, "Ventilate")
    assert _types(hass) == ["ventilate"]
    hass, store = _hass(), _Store()
    data = {"rooms": {"bad": _room(action="Close", active=True)}}
    short = _options(repeat_recommendation_cooldown_min=20)
    asyncio.run(process_notifications(hass, store, data, short, T0, []))
    asyncio.run(process_notifications(hass, store, {"rooms": {"bad": _room()}}, short, T0 + timedelta(minutes=20), []))
    assert _types(hass) == ["close", "ventilate"]
    hass, store = _hass(), _Store()
    broken = _options(repeat_recommendation_cooldown_min="x")
    asyncio.run(process_notifications(hass, store, data, broken, T0, []))
    asyncio.run(process_notifications(hass, store, {"rooms": {"bad": _room()}}, broken, T0 + timedelta(minutes=60), []))
    assert _types(hass) == ["close"]  # falls back to 120 min


def test_a_whole_day_of_the_reported_room_flaps_at_most_once_per_cooldown() -> None:
    """Room recommendation flips every 20 minutes for 24 h: messages stay rare."""
    hass, store = _hass(), _Store()
    for minute in range(0, 24 * 60, 20):
        closing = (minute // 20) % 2 == 0
        _cycle(hass, store, minute, "Close" if closing else "Ventilate", active=closing)
    sent = _types(hass)
    assert sent.count("ventilate") <= 24 * 60 // 120
    assert len(sent) <= 2 * (24 * 60 // 120) + 1
    # before 0.26.5.3 every flip was a message: 72 per day
    assert len(sent) == 19

