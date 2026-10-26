"""0.26.5.4 support case: fan room without window, rooms without opening, CO₂ vs cooling, automatic stop.

Diagnosis 25.10.: a laundry room without window contact but with an exhaust
fan was told "Über Nachbarraum lüften"; a store room open to the hallway got a
text claiming an unknown connection; elevated CO₂ (1445 ppm, warning 1200)
was shown as "Zum Kühlen lüften" and only became "Lüften" at the critical
threshold; a fan FreshAirIQ stopped at its maximum runtime produced a manual
"switch off the fan".
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.freshairiq.automation_events import recommendation_payload, room_payload
from custom_components.freshairiq.close_wording import FAN_ON_HINT, close_instruction, fan_stop_message, no_opening_wording
from custom_components.freshairiq.fan_automation import auto_stop, handled_label, room_fan_automation
from custom_components.freshairiq.room_recommendation import CO2_HYSTERESIS_PPM, _recommendation, co2_lead

OPTIONS = {"co2_warn": 1200, "co2_critical": 1450}
_DEFAULT = "No opening is assigned to this room; ventilate it via a connected room"


def _result(**overrides):
    base = {"data_quality": "ok", "humidity": 45.0, "surface_rh": 60.0, "delta_g_m3": 0.5, "active": False,
            "close_recommended": False, "ventilation_candidate": False, "cooling_candidate": True,
            "potential_ml": 0, "moisture_effect_next_5_min_ml": 0}
    base.update(overrides)
    return SimpleNamespace(**base)


def _rec(co2, *, latched=False, **result):
    return _recommendation(_result(**result), OPTIONS, pollen=0.0, co2=co2, airflow=1.0, wind_bearing=None,
                           wind_speed=None, co2_latched=latched)


# --------------------------------------------------------------------------- CO₂ vs cooling

@pytest.mark.parametrize(("co2", "action", "first"), [
    (1474, "Ventilate", "CO₂ 1474 ppm ist kritisch"),               # record 1277
    (1445, "Ventilate", "CO₂ 1445 ppm liegt über der Warnschwelle"),  # record 1275: was "Ventilate for cooling"
    (1200, "Ventilate", "CO₂ 1200 ppm liegt über der Warnschwelle"),
    (1100, "Ventilate for cooling", "Außenluft ist ausreichend kühler"),
    (None, "Ventilate for cooling", "Außenluft ist ausreichend kühler"),  # CO₂ goal switched off / no sensor
])
def test_co2_leads_and_cooling_is_the_extra_benefit(co2, action, first) -> None:
    got, reason, reasons = _rec(co2)
    assert got == action and reasons[0].startswith(first) and reason.startswith(first)
    if action == "Ventilate" and co2 < 1450:
        assert reasons[-1].startswith("Zusätzlich kühlt die Außenluft den Raum")


def test_co2_recommendation_has_a_hysteresis() -> None:
    band = 1200 - CO2_HYSTERESIS_PPM / 2
    action, _, reasons = _rec(band, latched=True)
    assert action == "Ventilate" and "knapp unter der Warnschwelle 1200 ppm" in reasons[0]
    assert _rec(band)[0] == "Ventilate for cooling"  # not reached before: no CO₂ lead
    assert _rec(1200 - CO2_HYSTERESIS_PPM - 1, latched=True)[0] == "Ventilate for cooling"
    assert co2_lead(None, OPTIONS, True) is False
    assert co2_lead(1200, OPTIONS, False) and co2_lead(1151, OPTIONS, True) and not co2_lead(1149, OPTIONS, True)


def test_co2_without_cooling_keeps_the_existing_priorities() -> None:
    # warning level alone is attention, not an airing candidate (only critical is a health override)
    assert _rec(1300, cooling_candidate=False)[0] == "Wait"
    assert _rec(1300, cooling_candidate=False, ventilation_candidate=True)[0] == "Ventilate"


# --------------------------------------------------------------------------- rooms without window contact

def _room(key, name, *, contacts=0, fan=False, running=False, action="Ventilate indirectly", reason=_DEFAULT):
    return {"key": key, "name": name, "contact_count": contacts, "action": action, "reason": reason,
            "configured_actuators": {"exhaust_fan": fan, "mechanical_exhaust_active": running}}


def test_rooms_without_window_name_their_real_air_path() -> None:
    rooms = {
        "wk": _room("wk", "Waschküche", fan=True), "wk2": _room("wk2", "Bad", fan=True, running=True),
        "ab": _room("ab", "Abstellraum"), "ka": _room("ka", "Kammer"), "flur": _room("flur", "Flur", contacts=1, action="Wait"),
        "own": _room("own", "Keller", fan=True, reason="Eigene Begründung"), "win": _room("win", "Bad 2", contacts=1),
        "ok": _room("ok", "Gäste", action="Okay"), "broken": "x",
    }
    no_opening_wording(rooms, {"ab": {"flur", "gone"}, "flur": {"ab"}})
    assert rooms["wk"]["action_hint"] == FAN_ON_HINT == "Ablüfter einschalten"
    assert rooms["wk"]["reason"] == "No window is assigned to this room; switch on its exhaust fan"
    assert "action_hint" not in rooms["wk2"]  # the fan already runs
    assert rooms["ab"]["reason"] == "No window is assigned to this room; it is aired through the open connection to Flur"
    assert "connected room" not in rooms["ka"]["reason"] and "action_hint" not in rooms["ka"]
    assert rooms["own"]["reason"] == "Eigene Begründung" and rooms["own"]["action_hint"] == FAN_ON_HINT
    for key in ("win", "ok", "flur"):
        assert "action_hint" not in rooms[key] and rooms[key]["reason"] == _DEFAULT


@pytest.mark.parametrize(("language", "label"), [("de", "Bitte Ablüfter einschalten"), ("en", "Please switch on the exhaust fan")])
def test_events_ask_for_the_fan_not_a_connected_room(language, label) -> None:
    room = {**_room("wk", "Waschküche", fan=True), "action_hint": FAN_ON_HINT, "house_aligned_action": "ventilate_indirectly"}
    assert room_payload(room, previous_action=None, language=language, entry_id="e")["action_label"] == label
    assert recommendation_payload(room, previous_recommendation=None, language=language, entry_id="e")["recommendation_label"] == label
    plain = _room("ab", "Abstellraum")
    assert room_payload(plain, previous_action=None, language="de", entry_id="e")["action_label"] == "Über Nachbarraum lüften"


# --------------------------------------------------------------------------- automatic stop

def test_a_fan_freshairiq_switched_off_needs_no_manual_switch_off() -> None:
    room = {"key": "garage", "name": "Garage", "house_aligned_action": "close", "close_recommended": True,
            "configured_actuators": {"exhaust_fan": "switch.g", "exhaust_fan_control": "recommendation",
                                     "mechanical_exhaust_active": True}}
    # maximum runtime: off command pending, the room data still sees the running fan
    room["fan_automation"] = room_fan_automation({**room, "configured_actuators": {**room["configured_actuators"], "mechanical_exhaust_active": False}},
                                                 {"command": "off", "command_state": "pending", "reason": "max_runtime"})
    assert room["fan_automation"]["state"] == "completed" and room["fan_automation"]["label"] is None
    assert auto_stop(room)
    assert handled_label(room, "close") == "Automatische Lüftung abgeschlossen"
    assert handled_label(room, "close", "en") == "Automatic airing finished"
    assert handled_label(room, "ventilate") is None
    assert fan_stop_message(room) == "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung."
    assert close_instruction([room]) == "FreshAirIQ beendet die automatische Lüftung in Garage"
