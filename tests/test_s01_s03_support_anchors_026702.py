"""S01/S03 (0.26.7.2): support-case anchors as synthetic regressions on the current code.

All states are synthetic fixtures (rounded, no room names, no case data): they vary only what the anchors describe.
Unit contract: ``RoomInput.reference_humidity`` is relative humidity (%); the exported room field of the same name is
absolute humidity (g/m³) – the fixtures below derive the relative value from the stated absolute one.

S01 – dehumidify profile with helpful drier air: the compatible default (F11) does not close because of time, a
plateau or the humidity target while the reference air still takes moisture out; the house aggregate and the
presentation layers do not reintroduce such a close.
S03 – CO₂ start 1000 / release 750 / critical 1400: falling and jittering trace, quiet band after the need ended; the
action that reaches the notification policy (enabled test receivers) is the same effective decision – one start
message, none in the quiet band.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, co2_lead, evaluate_room
from custom_components.freshairiq.notification_policy import room_notification_events
from custom_components.freshairiq.room_recommendation import _recommendation

DEHUMIDIFY = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "target_rh": 58.0, "start_rh": 62.0, "high_rh": 68.0,
              "close_delta": 0.4, "min_duration_min": 3.0, "max_duration_min": 20.0, "min_return_next_5_min_ml": 25.0,
              "airing_min_room_temp_c": 0.0}


def _running(t, rh, minutes, *, volume, ref_t=5.0, ref_rh=84.4, **extra):
    # ref 5.0 °C / 84.4 % ≈ 5.74 g/m³ absolute (the anchor's reference)
    return RoomInput(key="r", name="R", temperature=t, humidity=rh, reference_temperature=ref_t, reference_humidity=ref_rh,
                     volume_m3=volume, contact_open=True, contact_open_seconds=int(minutes * 60), session_active=True,
                     session_elapsed_min=minutes, session_start_temp=19.9, learning_rate=0.03, session_fresh_measurements=6, **extra)


def _action(room, options, co2=None, latched=False):
    result = evaluate_room(room, options, False)
    action, _reason, reasons = _recommendation(result, options, pollen=0.0, co2=co2, airflow=1.0, wind_bearing=None,
                                               wind_speed=None, co2_latched=latched)
    return result, action, reasons


@pytest.mark.parametrize("t,rh,minutes,volume", [
    (19.9, 62.0, 8.94, 48.0),     # first observed close display of the anchor (now: drying continues)
    (18.4, 55.0, 206.0, 48.0),    # humidity already below the 58 % target – the air still dries
    (18.0, 54.0, 410.0, 48.0),
    (19.9, 48.0, 30.0, 38.0),     # second anchor: well below target, clearly drier reference
    (21.0, 51.7, 4.2, 31.0),      # counter case: early phase below target
    (20.6, 44.0, 105.0, 31.0),
])
def test_s01_dehumidify_default_keeps_drying_while_the_air_helps(t, rh, minutes, volume):
    result, action, reasons = _action(_running(t, rh, minutes, volume=volume), DEHUMIDIFY)
    assert result.delta_g_m3 > 0.4
    assert action == "Continue ventilating" and not result.close_recommended, (action, result.reason, reasons)


def test_s01_the_physical_close_still_comes_when_the_air_no_longer_helps():
    # same room, reference air now as humid as the room (≈ 8.6 g/m³ at 10 °C/91 %) → physical close (case C)
    result, action, _ = _action(_running(18.4, 55.0, 206.0, volume=48.0, ref_t=10.0, ref_rh=91.0), DEHUMIDIFY)
    assert result.delta_g_m3 <= 0.4 and action == "Close" and result.close_kind == "air_no_longer_helps"


# ------------------------------------------------------------------------------------------------ S03

CO2_OPTIONS = {**DEFAULT_OPTIONS, "co2_warn": 1000.0, "co2_release": 750.0, "co2_critical": 1400.0, "operating_profile": "comfort",
               "target_rh": 58.0, "min_duration_min": 3.0, "airing_min_room_temp_c": 16.0, "action_reminder_min": 0}


class _Store:
    def __init__(self):
        self.rooms: dict = {}

    def room(self, key):
        return self.rooms.setdefault(key, {})


def _closed_room(co2, latched):
    # window closed, dry and comfortable room – only CO₂ decides
    return RoomInput(key="wohnen", name="Wohnen", temperature=21.0, humidity=45.0, reference_temperature=8.0, reference_humidity=80.0,
                     volume_m3=49.0, contact_open=False, contact_open_seconds=0, co2=co2, co2_lead_latched=latched)


def test_s03_falling_and_jittering_co2_one_start_message_and_a_quiet_band():
    store, now, latched, actions, sent = _Store(), datetime(2026, 11, 15, 8, 0), False, [], []
    for i, co2 in enumerate((980, 1000, 990, 999, 900, 820, 760, 751, 750, 749, 752, 760, 990, 999, 760)):
        latched = co2_lead(float(co2), CO2_OPTIONS, latched)
        result, action, _ = _action(_closed_room(float(co2), latched), CO2_OPTIONS, co2=float(co2), latched=latched)
        room = {"key": "wohnen", "name": "Wohnen", "action": action, "data_quality": "ok", "active": False,
                "house_aligned_action": action.lower().replace(" ", "_")}
        events, _changed = room_notification_events({"wohnen": room}, store, now + timedelta(minutes=5 * i), CO2_OPTIONS, None,
                                                    sensor_alerts=lambda r: False)
        actions.append(action)
        sent += [(co2, name) for name, rooms in events.items() if rooms and name in {"Ventilate", "Close", "reminder", "retry"}]
    # start at exactly 1000, kept down to 750 (inclusive), released at 749, quiet afterwards below 1000
    assert actions[0] != "Ventilate" and actions[1] == "Ventilate"
    assert all(a == "Ventilate" for a in actions[1:9])            # 1000 … 750 (the helper keeps the need at exactly 750)
    assert all(a != "Ventilate" for a in actions[9:])             # 749 and the quiet band 752–999
    assert sent == [(1000, "Ventilate")]                          # one start message, no ping-pong in the quiet band


@pytest.mark.parametrize("co2,latched,needed", [
    (749, True, False), (750, True, True), (751, True, True),
    (999, False, False), (1000, False, True), (1001, False, True),
])
def test_s03_exact_boundaries_are_documented_and_unchanged(co2, latched, needed):
    assert co2_lead(float(co2), CO2_OPTIONS, latched) is needed
