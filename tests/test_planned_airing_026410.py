"""0.26.4.10 (support case 472cf5b9): no close advice shortly after opening.

All windows were opened, the 15-minute forecast promised about 290 ml, and
FreshAirIQ said "close" after 3.5 minutes / 10 ml: every room on its own was
below its small-room 5-minute threshold, and the house aggregate accepted the
unanimous room closes although the house as a whole still dried well.

Rule now: within the airing duration FreshAirIQ showed when the window was
opened, a close is advised only if moisture would come in (or a hard limit /
the maximum duration applies).
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.consolidation import (
    aggregate_close_allowed, moisture_coming_in, opening_phase_protected, planned_target_min, session_target_min,
)
from custom_components.freshairiq.model import RoomInput, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "operating_profile": "comfort"}


def _room(ref_t=12.0, ref_rh=60.0, elapsed=4.0, target=None, volume=6.0):
    return RoomInput(
        "bad", "Bad", 22.0, 60.0, ref_t, ref_rh, volume, True, 600,
        session_active=True, session_elapsed_min=elapsed, session_start_temp=22.0,
        learning_rate=0.03, session_fresh_measurements=2, session_target_min=target,
    )


def test_small_room_is_not_closed_inside_the_planned_airing_time():
    before = evaluate_room(_room(), OPTIONS, False)
    assert before.action == "Close" and before.moisture_effect_next_5_min_ml > 0  # old behaviour: tiny but positive return
    held = evaluate_room(_room(target=9.0), OPTIONS, False)
    assert held.action == "Continue ventilating" and not held.close_recommended
    after = evaluate_room(_room(elapsed=9.5, target=9.0), OPTIONS, False)
    assert after.action == "Close"


def test_moisture_coming_in_still_closes_at_once():
    wet = evaluate_room(_room(ref_t=21.0, ref_rh=70.0, target=9.0), OPTIONS, False)
    assert wet.delta_g_m3 <= OPTIONS["close_delta"] and wet.action == "Close"


def test_maximum_duration_is_never_extended():
    capped = evaluate_room(_room(elapsed=float(OPTIONS["max_duration_min"]), target=40.0), OPTIONS, False)
    assert capped.action == "Close"


def _active(elapsed=3.5, action="Close", hard=False):
    return {"key": "r", "action": action, "close_decision_ready": True, "session_elapsed_min": elapsed,
            "goal_state": {"hard_close": hard, "goals": []}}


def test_house_aggregate_ignores_unanimous_small_room_closes_while_planned():
    rooms = [_active(), _active(elapsed=2.0)]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=True, min_duration_min=3.0) is True  # before
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=True, min_duration_min=3.0, target_min=9, net_next5_ml=93) is False
    # moisture would come in -> close, even early
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=False, min_duration_min=3.0, target_min=9, net_next5_ml=-5) is True
    # hard limits keep priority
    assert aggregate_close_allowed([_active(hard=True)], low_return=False, thermal_bad=False, target_min=9, net_next5_ml=50) is True
    # planned time over -> the normal rules apply again
    assert aggregate_close_allowed([_active(elapsed=9.5)], low_return=True, thermal_bad=False, min_duration_min=3.0, target_min=9, net_next5_ml=10) is True


def test_planned_phase_and_target_helpers():
    assert opening_phase_protected([_active(elapsed=3)], 9) is True
    assert opening_phase_protected([_active(elapsed=3), _active(elapsed=10)], 9) is False  # oldest window decides
    assert opening_phase_protected([_active(elapsed=None)], 9) is False
    assert opening_phase_protected([_active()], None) is False
    assert opening_phase_protected([_active()], "x") is False
    assert opening_phase_protected([_active()], 0) is False
    assert session_target_min({"recommended_duration_min": 9}, OPTIONS) == 9.0
    assert session_target_min({"recommended_duration_min": 1}, OPTIONS) == float(OPTIONS["min_duration_min"])
    assert session_target_min({"recommended_duration_min": 99}, OPTIONS) == float(OPTIONS["max_duration_min"])
    assert session_target_min({"recommended_duration_min": None}, OPTIONS) is None
    assert session_target_min({"recommended_duration_min": 0}, OPTIONS) is None
    assert session_target_min({"recommended_duration_min": float("nan")}, OPTIONS) is None
    assert session_target_min(None, OPTIONS) is None


def test_coordinator_freezes_the_target_when_the_window_opens():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'mem["session_target_min"] = None if fan_start else _session_target_min(self.data, options)' in text
    # a window opened during a fan-only airing gets its planned time from then on
    assert 'mem["session_target_min"] = round(elapsed + joined, 1) if joined is not None else None' in text
    assert 'session_target_min=mem.get("session_target_min") if mem.get("session_active") else None,' in text
    assert "recommended_duration_min=recommended," in text


# --- exhaust fan only (community: "Garage schließen", although only the fan runs) ---------
from custom_components.freshairiq.close_wording import area_close_instruction, close_instruction, fan_only, fan_stop_message, keep_instruction
from custom_components.freshairiq.live_coach import refine_live_recommendation
from custom_components.freshairiq.localize import to_english


def _fan_room(**extra):
    room = RoomInput(
        "garage", "Garage", 14.0, 70.0, 12.0, 60.0, 60.0, True, 6000,
        session_active=True, session_elapsed_min=180.0, session_start_temp=14.0,
        learning_rate=0.02, session_fresh_measurements=5, mechanical_only=True,
    )
    for key, value in extra.items():
        setattr(room, key, value)
    return room


def test_a_running_fan_is_never_stopped_by_time_or_small_return():
    result = evaluate_room(_fan_room(), OPTIONS, False)  # 3 h – far beyond the window maximum
    assert result.action == "Continue ventilating" and not result.close_recommended
    wet = evaluate_room(_fan_room(reference_temperature=14.0, reference_humidity=90.0), OPTIONS, False)
    assert wet.action == "Close"  # only moisture coming in stops it


def _payload(key, name, fan, window=False):
    return {"key": key, "name": name, "configured_actuators": {"mechanical_exhaust_active": fan, "window_open": window}}


def test_wording_says_switch_off_the_fan_not_close():
    garage, bad = _payload("garage", "Garage", True), _payload("bad", "Bad", False, True)
    assert fan_only(garage) and not fan_only(bad) and not fan_only(_payload("x", "X", True, True)) and not fan_only("x")
    assert fan_only({"configured_actuators": {"mechanical_exhaust_active": False, "ventilation_type": "mechanical_exhaust"}})
    assert close_instruction([garage]) == "Lüfter in Garage ausschalten"
    # a running fan is only named when that room itself is advised to stop
    assert close_instruction([bad, garage]) == "Bad schließen"
    assert close_instruction([bad, {**garage, "close_recommended": True}]) == "Bad schließen · Lüfter in Garage ausschalten"
    assert close_instruction([bad, garage], joiner=", ", all_rooms=True) == "Bad schließen · Lüfter in Garage ausschalten"
    assert area_close_instruction("Erdgeschoss", [bad, garage]) == "Erdgeschoss schließen"
    assert area_close_instruction("Erdgeschoss", [bad, {**garage, "close_recommended": True}]) == "Erdgeschoss schließen · Lüfter in Garage ausschalten"
    assert area_close_instruction("Erdgeschoss", [garage]) == "Lüfter in Garage ausschalten"
    assert keep_instruction([garage], None) == "Lüfter in Garage laufen lassen"  # a fan has no planned end
    assert close_instruction([]) == "Geöffnete Fenster schließen"
    assert keep_instruction([bad, garage], 3.6) == "Bad offen lassen · Lüfter in Garage laufen lassen · noch ca. 4 min"
    assert keep_instruction([], 0) == "Weiterlüften · noch ca. 1 min"
    assert to_english("Bad schließen · Lüfter in Garage ausschalten", ["Bad", "Garage"]) == "Close Bad · switch off the fan in Garage"
    assert to_english("Lüfter in Garage laufen lassen · noch ca. 4 min", ["Garage"]) == "Keep the fan in Garage running · about 4 min left"


def _coach_room(key="garage", fan=True, elapsed=180.0, target=None, next5=3.0):
    return {"key": key, "name": key.title(), "calculation_enabled": True, "data_quality": "ok", "active": True,
            "session_elapsed_min": elapsed, "session_target_min": target, "close_decision_ready": True,
            "forecast_5_min_moisture_effect_ml": next5, "forecast_5_min_temperature_change_c": -0.1, "volume_m3": 40.0,
            "configured_actuators": {"mechanical_exhaust_active": fan, "window_open": not fan}}


def test_live_coach_holds_fan_and_planned_airings():
    rec = {"kind": "continue", "duration_min": 5.0, "reasons": []}
    fan = refine_live_recommendation({"garage": _coach_room()}, OPTIONS, rec)
    assert fan["kind"] == "continue" and fan["instruction"].startswith("Lüfter in Garage laufen lassen")
    window = refine_live_recommendation({"bad": _coach_room("bad", fan=False, elapsed=4.0)}, OPTIONS, rec)
    assert window["kind"] == "close"  # old behaviour without a planned time
    planned = refine_live_recommendation({"bad": _coach_room("bad", fan=False, elapsed=4.0, target=9.0)}, OPTIONS, rec)
    assert planned["kind"] == "continue" and planned["live_coach_target_min"] >= 9.0
    wet = refine_live_recommendation({"bad": _coach_room("bad", fan=False, elapsed=4.0, target=9.0, next5=-8.0)}, OPTIONS, rec)
    assert wet["kind"] == "close"


def test_fan_only_push_says_switch_off_the_fan():
    from custom_components.freshairiq.language_confidence import room_notification_message

    garage = {"key": "garage", "name": "Garage", "configured_actuators": {"mechanical_exhaust_active": True, "window_open": False}}
    assert room_notification_message("close", garage, {}) == "Die Außenluft ist kaum noch trockener als die Raumluft. Lüfter ausschalten."
    assert fan_stop_message({**garage, "delta_g_m3": -0.4}) == "Die Außenluft ist gerade feuchter als die Raumluft. Lüfter ausschalten."
    assert fan_stop_message({**garage, "delta_g_m3": "x"}).startswith("Die Außenluft ist kaum noch") and fan_stop_message(None).endswith("Lüfter ausschalten.")
    window = {"key": "bad", "name": "Bad", "configured_actuators": {"mechanical_exhaust_active": False, "window_open": True}}
    assert "Lüfter" not in room_notification_message("close", window, {})


def test_joining_window_shares_the_running_airing_time():
    running = {"rooms": {"bad": {"active": True, "configured_actuators": {"window_open": True}}},
               "remaining_duration_min": 6, "recommended_duration_min": 15}
    assert session_target_min(running, OPTIONS) == 6.0  # ends together with the windows already open
    fan_running = {"rooms": [{"active": True, "configured_actuators": {"mechanical_exhaust_active": True}}],
                   "remaining_duration_min": 6, "recommended_duration_min": 15}
    assert session_target_min(fan_running, OPTIONS) == 15.0  # a fan does not start a planned airing
    assert session_target_min({"rooms": "odd", "recommended_duration_min": 9}, OPTIONS) == 9.0
    assert session_target_min({"recommended_duration_min": 9}, {"min_duration_min": "x"}) is None
    over = {**running, "remaining_duration_min": -3}
    assert session_target_min(over, OPTIONS) == 15.0  # running airing already over -> a fresh airing time


def test_target_comes_from_the_earliest_window_and_fans_are_ignored():
    first = {"session_elapsed_min": 8.0, "session_target_min": 12.0, "configured_actuators": {"window_open": True}}
    later = {"session_elapsed_min": 2.0, "session_target_min": 4.0, "configured_actuators": {"window_open": True}}
    fan = {"session_elapsed_min": 90.0, "session_target_min": 20.0, "configured_actuators": {"mechanical_exhaust_active": True}}
    assert planned_target_min([later, first, fan]) == 12.0
    assert planned_target_min([{"session_elapsed_min": 1.0, "session_target_min": None}]) is None
    assert planned_target_min([{"session_elapsed_min": 1.0, "session_target_min": float("nan")}]) is None
    assert opening_phase_protected([first, fan], 12.0) is True  # the fan's 90 min do not end the planned phase
    assert opening_phase_protected([fan], 12.0) is False


def test_moisture_coming_in_matches_the_room_model():
    dry = [{"delta_g_m3": 2.0}, {"delta_g_m3": 0.2}]
    assert moisture_coming_in(dry, 0.0, 0.4) is True  # no net drying
    assert moisture_coming_in(dry, 25.0, 0.4) is False  # one room still dries
    assert moisture_coming_in([{"delta_g_m3": 0.3}, {"delta_g_m3": "x"}], 25.0, 0.4) is True
    assert moisture_coming_in([{}], None, 0.4) is False


def test_ingress_does_not_bypass_the_minimum_duration():
    early = [_active(elapsed=1.0)]
    early[0]["action"] = "Continue ventilating"
    assert aggregate_close_allowed(early, low_return=True, thermal_bad=False, min_duration_min=3.0, target_min=9, net_next5_ml=-5) is False


def test_live_coach_window_and_fan_together():
    rec = {"kind": "continue", "duration_min": 5.0, "reasons": []}
    rooms = {"bad": _coach_room("bad", fan=False, elapsed=4.0, target=9.0), "garage": _coach_room(elapsed=180.0)}
    both = refine_live_recommendation(rooms, OPTIONS, rec)
    assert both["kind"] == "continue"
    assert both["instruction"].startswith("Bad offen lassen · Lüfter in Garage laufen lassen · noch ca.")
