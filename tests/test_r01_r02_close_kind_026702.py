"""R01 (P0) / R02 (0.26.7.2): a released temperature close beats a running moisture source; a held goal close keeps its reason.

R01 fixture of the order: bath 9.4 m³, 14.9 °C / 70 %, reference 0.7 °C / 92 %, 30 min, 6 fresh readings, source
"Dusche", limit 16 °C, target_rh 58, min_duration 5, comfort, CO₂ none. Control table:
    source + limit            → close (was: continue)          no source + limit → close
    source + limit 0          → continue                       source + limit + CO₂ 1600 (critical 1400) → continue
Not every ``close_recommended`` is a protective close: only ``close_kind == "temperature_limit"`` overrules the source.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.localize import Translator
from custom_components.freshairiq.model import (
    GOALS_HELD_CLOSE_REASON, TEMPERATURE_LIMIT_CLOSE_REASON, VENTILATION_HYSTERESIS_RH, RoomInput, evaluate_room,
)
from custom_components.freshairiq.opening_strategy import (
    keep_moisture_sources_open, protective_close, synchronize_room_presentation_actions,
)
from custom_components.freshairiq.room_close_strategy import CONF_ROOM_AIRING_MIN_TEMP, CONF_ROOM_CLOSE_STRATEGY, STRATEGY_GOALS, room_close_options
from custom_components.freshairiq.room_recommendation import _recommendation

BASE = {**DEFAULT_OPTIONS, "target_rh": 58.0, "min_duration_min": 5.0, "operating_profile": "comfort"}
LIMIT = {**BASE, "airing_min_room_temp_c": 16.0}
NO_LIMIT = {**BASE, "airing_min_room_temp_c": 0.0}
SHOWER = dict(moisture_source_active=True, moisture_source_label="Dusche", moisture_source_confidence=90, moisture_source_rate_ml_min=12.0)


def _bath(**extra) -> RoomInput:
    values = dict(key="bad", name="Bad", temperature=14.9, humidity=70.0, reference_temperature=0.7, reference_humidity=92.0,
                  volume_m3=9.4, contact_open=True, contact_open_seconds=1800, session_active=True, session_elapsed_min=30.0,
                  session_start_temp=20.0, learning_rate=0.03, session_fresh_measurements=6)
    values.update(extra)
    return RoomInput(**values)


def _full_path(room: RoomInput, options: dict, co2: float | None = None):
    """Model → room recommendation (the path that overwrote the model's close before R01)."""
    result = evaluate_room(room, options, False)
    action, reason, reasons = _recommendation(result, options, pollen=0.0, co2=co2, airflow=1.0, wind_bearing=None, wind_speed=None)
    return result, action, reasons


# --------------------------------------------------------------------------------------------- control table (R01)

def test_source_and_released_limit_closes():
    result, action, reasons = _full_path(_bath(**SHOWER), LIMIT)
    assert result.close_recommended and result.close_kind == "temperature_limit" and result.reason == TEMPERATURE_LIMIT_CLOSE_REASON
    assert action == "Close"
    assert any("Temperaturgrenze beim Lüften (16.0 °C)" in r for r in reasons)
    assert any("Dusche wahrscheinlich aktiv" in r for r in reasons)        # the source is still named, not hidden


def test_no_source_and_limit_closes():
    result, action, _ = _full_path(_bath(), LIMIT)
    assert result.close_kind == "temperature_limit" and action == "Close"


def test_source_without_limit_keeps_ventilating():
    result, action, reasons = _full_path(_bath(**SHOWER), NO_LIMIT)
    assert action == "Continue ventilating" and result.close_kind is None
    assert any("aktiven Feuchtequelle" in r for r in reasons)


def test_critical_co2_keeps_the_existing_priority_over_the_limit():
    result, action, _ = _full_path(_bath(co2=1600.0, **SHOWER), {**LIMIT, "co2_critical": 1400.0}, co2=1600.0)
    assert action == "Continue ventilating" and result.close_kind != "temperature_limit"


def test_the_rooms_own_limit_behaves_like_the_global_one():
    options = room_close_options(NO_LIMIT, {CONF_ROOM_AIRING_MIN_TEMP: 16.0})
    result, action, _ = _full_path(_bath(**SHOWER), options)
    assert result.close_kind == "temperature_limit" and action == "Close"


def test_source_follow_up_does_not_hide_the_limit_either():
    result, action, _ = _full_path(_bath(moisture_source_recovery=True, moisture_source_ended_min=2.0, moisture_source_label="Dusche"), LIMIT)
    assert result.close_kind == "temperature_limit" and action == "Close"


@pytest.mark.parametrize("temperature,expected", [(16.1, "Continue ventilating"), (16.0, "Close"), (15.9, "Close")])
def test_limit_boundary_with_running_source(temperature, expected):
    _result, action, _ = _full_path(_bath(temperature=temperature, **SHOWER), LIMIT)
    assert action == expected


def test_not_every_close_is_protective():
    assert protective_close({"close_recommended": True, "close_kind": "temperature_limit"})
    for kind in ("goals_reached", "goals_held", "air_no_longer_helps", "summer_warming", "model_fallback", None):
        assert not protective_close({"close_recommended": True, "close_kind": kind})
    assert not protective_close({"close_recommended": False, "close_kind": "temperature_limit"})
    assert not protective_close(None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------- house overlays (R01)

OVERLAY = {"close_delta": 0.4}


def _room(key, **extra):
    room = {"key": key, "name": key.title(), "floor": "ground_floor", "volume_m3": 9.4, "active": True, "open": True,
            "close_decision_ready": True, "delta_g_m3": 2.9, "session_elapsed_min": 30.0, "moisture_source_active": True,
            "moisture_source_label": "Dusche"}
    room.update(extra)
    return room


def _limited(key, **extra):
    return _room(key, **{"action": "Close", "close_recommended": True, "close_kind": "temperature_limit", **extra})


def test_a_limited_source_room_is_never_kept_open_by_the_source_overlay():
    # a stale "Continue" from an earlier layer must not let the overlay revive the source keep-open
    rooms = {"bad": _limited("bad", action="Continue ventilating")}
    rec = {"kind": "close", "room_keys": ["bad"], "instruction": "Bad schließen"}
    keep_moisture_sources_open(rec, rooms, OVERLAY)
    assert rec == {"kind": "close", "room_keys": ["bad"], "instruction": "Bad schließen"}


def test_house_continue_does_not_rewrite_a_released_temperature_close():
    rooms = {"bad": _limited("bad"), "kueche": _room("kueche", action="Continue ventilating", close_recommended=False, moisture_source_active=False)}
    rec = {"kind": "continue", "room_keys": ["bad", "kueche"]}
    synchronize_room_presentation_actions(rec, rooms)
    assert rooms["bad"]["action"] == "Close"
    assert rooms["kueche"]["action"] == "Continue ventilating"


def test_two_rooms_one_limited_one_source_open():
    # multiple rooms: the limited bath closes, the second shower room without a released limit stays open
    rooms = {"bad": _limited("bad"), "gaestebad": _room("gaestebad", action="Continue ventilating", close_recommended=False)}
    rec = {"kind": "close", "status": "close_windows", "room_keys": ["bad", "gaestebad"], "instruction": "Jetzt schließen", "reasons": []}
    keep_moisture_sources_open(rec, rooms, OVERLAY)
    synchronize_room_presentation_actions(rec, rooms)
    assert rec["room_keys"] == ["bad"] and rec["moisture_source_kept_open"] == ["gaestebad"]
    assert rooms["bad"]["action"] == "Close" and rooms["gaestebad"]["action"] == "Continue ventilating"


def test_staggered_opening_keeps_the_own_gate_but_not_against_the_limit():
    # a room opened later (2 of 5 minutes) is held by its own gate – a released temperature close is not
    rec = {"kind": "close", "room_keys": ["spaet", "bad"]}
    rooms = {"spaet": _room("spaet", action="Continue ventilating", close_recommended=False, moisture_source_active=False, session_elapsed_min=2.0),
             "bad": _limited("bad", session_elapsed_min=2.0)}
    synchronize_room_presentation_actions(rec, rooms, min_duration_min=5.0)
    assert rooms["spaet"]["action"] == "Continue ventilating"   # own clock and minimum time stay (unchanged behaviour)
    assert rooms["bad"]["action"] == "Close"


# --------------------------------------------------------------------------------------------- held goal close (R02)

GOALS = room_close_options({**BASE, "airing_min_room_temp_c": 0.0}, {CONF_ROOM_CLOSE_STRATEGY: STRATEGY_GOALS})


def _held(rh):
    # Testvermerk 0.26.7.1 (B3): a held goal close needs the stored cause of a really reached goal
    room = _bath(humidity=rh, close_notified=True, close_notified_kind="goals_reached")
    return _full_path(room, GOALS)


def test_held_goal_close_inside_the_hysteresis_keeps_its_true_reason():
    result, action, reasons = _held(60.0)                    # target 58 + hysteresis 2 → still held
    assert result.close_recommended and action == "Close"
    assert result.close_kind == "goals_held" and result.reason == GOALS_HELD_CLOSE_REASON
    text = next(r for r in reasons if "Ziele dieses Raums" in r)
    assert "bis die Luftfeuchte über 60 % steigt (jetzt 60 %, Ziel 58 %)" in text
    assert "kaum noch trockener" not in " ".join(reasons)   # no false "≤ 0.4 g/m³" claim (real delta ≈ 2.9)
    assert result.delta_g_m3 > 2.5
    english = Translator().text(text)
    assert english != text and "60 %" in english and "58 %" in english


def test_held_goal_close_is_released_above_the_hysteresis():
    result, action, _ = _held(58.0 + VENTILATION_HYSTERESIS_RH + 0.6)
    assert action == "Continue ventilating" and result.close_kind is None


def test_held_goal_close_yields_to_co2_need():
    result, action, _ = _full_path(_bath(humidity=60.0, close_notified=True, co2=1500.0), {**GOALS, "co2_critical": 1400.0}, co2=1500.0)
    assert result.close_kind != "goals_held"


# --------------------------------------------------------------------------------------------- fan push wording

from custom_components.freshairiq.close_wording import fan_stop_message  # noqa: E402


@pytest.mark.parametrize("kind,start", [
    ("temperature_limit", "Deine Temperaturgrenze beim Lüften ist erreicht."),
    ("goals_reached", "Die Ziele dieses Raums sind erreicht."),
    ("goals_held", "Die Ziele dieses Raums wurden in dieser Lüftung erreicht."),
])
def test_fan_stop_push_names_the_real_cause(kind, start):
    room = {"delta_g_m3": 2.95, "close_recommended": True, "close_kind": kind}
    text = fan_stop_message(room)
    assert text == f"{start} Lüfter ausschalten." and "kaum noch trockener" not in text
    assert Translator().text(text) != text


@pytest.mark.parametrize("room,expected", [
    ({"delta_g_m3": 0.3, "close_recommended": True, "close_kind": "air_no_longer_helps"}, "Die Außenluft ist kaum noch trockener als die Raumluft. Lüfter ausschalten."),
    ({"delta_g_m3": -0.5, "close_recommended": True, "close_kind": "air_no_longer_helps"}, "Die Außenluft ist gerade feuchter als die Raumluft. Lüfter ausschalten."),
    ({"delta_g_m3": 2.95, "close_recommended": False, "close_kind": "temperature_limit"}, "Die Außenluft ist kaum noch trockener als die Raumluft. Lüfter ausschalten."),
])
def test_fan_stop_push_physics_wording_unchanged(room, expected):
    assert fan_stop_message(room) == expected
