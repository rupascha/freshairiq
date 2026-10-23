"""0.26.5.3 (community, HarryP): bedroom with temperature goal, comfort target 19 °C.

The window was open since the morning, the room at 21–22 °C, outdoors 13–16 °C,
the dashboard showed "Abkühlen läuft" – and FreshAirIQ kept saying "Fenster
schließen": the model knew neither the room's comfort target nor its
temperature goal. Cooling only counted from the house-wide 24 °C in the summer
profile, so the maximum airing duration and the temperature loss closed it.

Now a room whose temperature goal is set (and not switched off) keeps airing
while it is above its comfort target and the reference air is clearly cooler.
Moisture protection still wins; without a temperature goal nothing changes.
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.goals import room_comfort_target
from custom_components.freshairiq.model import COMFORT_COOLING_MARGIN_C, RoomInput, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "operating_profile": "comfort", "min_duration_min": 3, "max_duration_min": 30}


def _bedroom(**overrides) -> RoomInput:
    values = dict(
        key="schlafzimmer", name="Schlafzimmer", temperature=21.8, humidity=52, reference_temperature=14.5,
        reference_humidity=70, volume_m3=40, contact_open=True, contact_open_seconds=4 * 3600,
        session_active=True, session_elapsed_min=240, session_start_temp=20.0, learning_rate=0.03,
        session_fresh_measurements=8, comfort_target_c=19.0,
    )
    values.update(overrides)
    return RoomInput(**values)


def test_the_bedroom_above_its_target_keeps_airing() -> None:
    result = evaluate_room(_bedroom(), OPTIONS, False)
    assert result.action == "Continue ventilating"
    assert result.reason.startswith("Cooling remains useful")


def test_without_temperature_goal_the_old_decision_stays() -> None:
    assert evaluate_room(_bedroom(comfort_target_c=None), OPTIONS, False).action == "Close"
    assert evaluate_room(_bedroom(cooling_allowed=False), OPTIONS, False).action == "Close"


def test_closing_once_the_target_is_reached_or_the_air_is_not_cooler() -> None:
    near_target = 19.0 + COMFORT_COOLING_MARGIN_C - 0.1
    assert evaluate_room(_bedroom(temperature=near_target, session_start_temp=near_target + 0.1), OPTIONS, False).action == "Close"
    assert evaluate_room(_bedroom(reference_temperature=20.5), OPTIONS, False).action == "Close"


def test_moisture_protection_still_wins() -> None:
    wet = _bedroom(reference_humidity=99, reference_temperature=17.5, humidity=40)
    assert evaluate_room(wet, OPTIONS, False).action == "Close"
    # a humid room (above "cooling_max_indoor_rh") is not kept open for cooling
    assert evaluate_room(_bedroom(humidity=75, reference_humidity=95, reference_temperature=16.5), OPTIONS, False).action == "Close"


def test_a_closed_window_is_not_asked_to_open_for_this_alone() -> None:
    closed = _bedroom(contact_open=False, contact_open_seconds=0, session_active=False, session_elapsed_min=0)
    assert evaluate_room(closed, OPTIONS, False).action != "Ventilate for cooling"


def test_comfort_target_sources() -> None:
    assert room_comfort_target({"target_temperature_mode": "manual", "target_temperature": 19}, {}) == (19.0, "manual")
    assert room_comfort_target({"target_temperature_mode": "automatic"}, {"last_plausible_comfort_target_c": 20.5})[0] == 20.5
    assert room_comfort_target({"target_temperature_fallback": 18}, {}) == (18.0, "fallback")
    assert room_comfort_target({}, {})[0] is None


# --------------------------------------------------------------------------- house level
def _active(key: str, name: str, **extra) -> dict:
    room = {"key": key, "name": name, "active": True, "data_quality": "ok", "calculation_enabled": True,
            "action": "Continue ventilating", "session_elapsed_min": 25, "volume_m3": 40, "close_decision_ready": True}
    room.update(extra)
    return room


def test_the_house_does_not_close_a_room_that_still_cools_towards_its_target() -> None:
    from custom_components.freshairiq.consolidation import stabilise_recommendation

    rooms = {"schlaf": _active("schlaf", "Schlafzimmer", comfort_cooling_active=True)}
    close = {"kind": "close", "status": "close_windows", "room_keys": ["schlaf"], "title": "Der sinnvolle Lüftungspunkt ist erreicht",
             "instruction": "Hauslüftung beenden"}
    out = stabilise_recommendation(close, rooms, OPTIONS)
    assert out["kind"] == "continue" and out["room_keys"] == ["schlaf"]
    assert out["instruction"] == "Schlafzimmer offen lassen" and "comfort_cooling_keeps_rooms_open" in out["consolidation_checks"]


def test_mixed_house_close_closes_only_the_other_rooms() -> None:
    from custom_components.freshairiq.consolidation import stabilise_recommendation

    # the house (live coach / aggregate) ends the airing of both released rooms
    rooms = {"schlaf": _active("schlaf", "Schlafzimmer", comfort_cooling_active=True), "bad": _active("bad", "Bad")}
    close = {"kind": "close", "status": "close_windows", "room_keys": ["schlaf", "bad"], "title": "Jetzt schließen", "instruction": "Hauslüftung beenden"}
    out = stabilise_recommendation(close, rooms, OPTIONS)
    assert out["kind"] == "close" and out["room_keys"] == ["bad"]
    assert out["instruction"] == "Bad schließen · Schlafzimmer offen lassen"
    # a room asking to close itself: only that room is named (existing rule)
    rooms["bad"] = _active("bad", "Bad", action="Close", close_recommended=True)
    out = stabilise_recommendation(close, rooms, OPTIONS)
    assert out["kind"] == "close" and out["room_keys"] == ["bad"] and out["instruction"] == "Bad schließen"


def test_hard_protection_still_closes_and_other_kinds_are_untouched() -> None:
    from custom_components.freshairiq.consolidation import stabilise_recommendation

    hard = {"schlaf": _active("schlaf", "Schlafzimmer", comfort_cooling_active=True, goal_state={"hard_close": True})}
    close = {"kind": "close", "status": "close_windows", "room_keys": ["schlaf"], "title": "Jetzt schließen", "instruction": "Schlafzimmer schließen"}
    assert stabilise_recommendation(close, hard, OPTIONS)["kind"] == "close"
    plain = {"schlaf": _active("schlaf", "Schlafzimmer")}
    assert stabilise_recommendation(close, plain, OPTIONS)["kind"] == "close"
    running = {"kind": "continue", "status": "ventilation_running", "room_keys": ["schlaf"], "title": "Weiterlüften", "instruction": "x"}
    assert stabilise_recommendation(running, {"schlaf": _active("schlaf", "Schlafzimmer", comfort_cooling_active=True)}, OPTIONS)["instruction"] == "x"


def test_the_model_reports_the_cooling_state() -> None:
    assert evaluate_room(_bedroom(), OPTIONS, False).comfort_cooling_active is True
    assert evaluate_room(_bedroom(comfort_target_c=None), OPTIONS, False).comfort_cooling_active is False
