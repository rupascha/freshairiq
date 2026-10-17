"""Regressions (2026-10-16, owner-approved) for two learning defects in the coordinator.

A-20: the close confirmation / final measurement wait (room closed, current
specialist mode ``None``) marked every specialist session as mixed, so the
separate open/tilted/cross/mechanical_exhaust models never learned.

A-21: a fan-only airing in a room with (long closed) window contacts took its
end from the window close time, ended before it started and was logged with
0 minutes, so it was never learned.
"""
from __future__ import annotations

from datetime import datetime

from ha_tests.test_cov_coordinator_b import (  # noqa: F401  (autouse fixture)
    BERLIN,
    HUM,
    TEMP,
    _cleanup_coordinators,
    _data,
    _make,
    _rooms,
    _with,
)

LAGE = {"options": ["closed", "tilted", "open"], "device_class": "enum"}


async def test_three_state_open_session_learns_open_specialist_model(hass, freezer) -> None:
    rooms = _with(_rooms(), "schlaf", contacts=["sensor.schlaf_fenster_lage"],
                  contact_delays={"sensor.schlaf_fenster_lage": 0},
                  contact_orientations={"sensor.schlaf_fenster_lage": "east"})
    d = await _make(hass, freezer, data=_data(rooms),
                    initial={"sensor.schlaf_fenster_lage": ("closed", LAGE), "sensor.schlaf_h": (66.0, HUM)})
    before = dict((d.mem("schlaf").get("opening_learning") or {}).get("open") or {})
    await d.step(60, sensor__schlaf_fenster_lage=("open", LAGE))
    await d.step(5)  # three-state transitions are debounced for 3 s
    assert d.mem("schlaf")["session_specialist_opening_mode"] == "open"
    for i in range(8):
        await d.step(60, sensor__schlaf_h=round(66 - 0.9 * (i + 1), 1), sensor__schlaf_t=round(19.4 - 0.1 * (i + 1), 2))
    await d.step(60, sensor__schlaf_fenster_lage=("closed", LAGE))
    # closing is not a source change
    assert d.mem("schlaf")["session_opening_mode_mixed"] is False
    await d.finish(sensor__schlaf_h=58.5, sensor__schlaf_t=18.7)
    mem = d.mem("schlaf")
    assert mem["session_active"] is False
    assert mem["last_learning_valid"] is True, mem.get("diagnosis")
    assert mem["session_opening_mode_mixed"] is False
    after = mem["opening_learning"]["open"]
    assert int(after["samples"]) == int(before.get("samples", 0)) + 1


async def test_tilted_then_open_stays_mixed(hass, freezer) -> None:
    rooms = _with(_rooms(), "schlaf", contacts=["sensor.schlaf_fenster_lage"],
                  contact_delays={"sensor.schlaf_fenster_lage": 0},
                  contact_orientations={"sensor.schlaf_fenster_lage": "east"})
    d = await _make(hass, freezer, data=_data(rooms),
                    initial={"sensor.schlaf_fenster_lage": ("closed", LAGE), "sensor.schlaf_h": (66.0, HUM)})
    await d.step(60, sensor__schlaf_fenster_lage=("tilted", LAGE))
    await d.step(5)
    assert d.mem("schlaf")["session_specialist_opening_mode"] == "tilted"
    await d.step(300, sensor__schlaf_h=64.0)
    await d.step(60, sensor__schlaf_fenster_lage=("open", LAGE))
    await d.step(5)
    assert d.mem("schlaf")["session_opening_mode_mixed"] is True


async def test_fan_only_airing_in_room_with_closed_window_keeps_its_duration(hass, freezer) -> None:
    d = await _make(hass, freezer, start=datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN),
                    initial={"sensor.buero_h": (68.0, HUM), "sensor.buero_t": (21.2, TEMP)})
    assert d.hass.states.get("binary_sensor.buero_fenster").state == "off"
    await d.step(60, fan__buero_abluft="on")
    mem = d.mem("buero")
    assert mem["session_active"] is True and mem["session_opening_mode"] == "mechanical_exhaust"
    for i in range(12):
        await d.step(60, sensor__buero_h=round(68 - 0.8 * (i + 1), 1), sensor__buero_t=round(21.2 - 0.03 * (i + 1), 2))
    await d.step(60, fan__buero_abluft="off")
    # the fan just stopped: close confirmation like a window, not an instant 0-minute end
    assert d.mem("buero")["session_active"] is True
    await d.finish(sensor__buero_h=58.0, sensor__buero_t=20.8)
    mem = d.mem("buero")
    assert mem["session_active"] is False
    # fan on 21:01 -> off 21:14: the airing keeps its real 13 minutes
    assert mem["last_ventilation_ended_at"] == "2026-10-07T21:14:00+02:00"
    assert mem["preferred_duration_min"] == 13.0
    assert mem["last_learning_valid"] is True, mem.get("diagnosis")
    assert mem["opening_learning"]["mechanical_exhaust"]["samples"] >= 1


async def test_fan_stop_with_corrupt_session_start_falls_back_to_contact_close(hass, freezer) -> None:
    d = await _make(hass, freezer, initial={"sensor.buero_h": (68.0, HUM), "sensor.buero_t": (21.2, TEMP)})
    await d.step(60, fan__buero_abluft="on")
    for i in range(3):
        await d.step(60, sensor__buero_h=round(68 - 0.8 * (i + 1), 1))
    d.mem("buero")["session_started"] = "not-a-date"
    await d.step(60, fan__buero_abluft="off")
    # without a usable session start the fan stop cannot be attributed: the long
    # closed window decides as before and the session goes straight to the final wait
    assert d.mem("buero")["session_close_pending"] is True
    await d.finish()
    assert d.mem("buero")["session_active"] is False


async def test_window_session_with_idle_fan_ends_at_window_close(hass, freezer) -> None:
    d = await _make(hass, freezer, initial={"sensor.buero_h": (68.0, HUM), "sensor.buero_t": (21.2, TEMP)})
    await d.step(60, binary_sensor__buero_fenster="on")
    for i in range(6):
        await d.step(60, sensor__buero_h=round(68 - 1.0 * (i + 1), 1))
    await d.step(60, binary_sensor__buero_fenster="off")
    await d.finish(sensor__buero_h=61.0, sensor__buero_t=20.9)
    mem = d.mem("buero")
    assert mem["session_active"] is False
    # the fan was off before the airing started, so the window close decides
    assert mem["last_ventilation_ended_at"] == "2026-10-07T21:08:00+02:00"


async def test_binary_contact_joining_open_specialist_session_marks_mixed(hass, freezer) -> None:
    # Room-level mode stays "open"; only the specialist provenance changes because an
    # unproven binary contact becomes active next to the proven three-state window.
    rooms = _with(_rooms(), "kueche", contacts=["sensor.kueche_fenster_lage", "binary_sensor.terrasse"],
                  contact_delays={"sensor.kueche_fenster_lage": 0, "binary_sensor.terrasse": 0},
                  contact_orientations={"sensor.kueche_fenster_lage": "west", "binary_sensor.terrasse": "west"})
    d = await _make(hass, freezer, data=_data(rooms), initial={"sensor.kueche_fenster_lage": ("closed", LAGE)})
    await d.step(60, sensor__kueche_fenster_lage=("open", LAGE))
    await d.step(5)
    mem = d.mem("kueche")
    assert mem["session_specialist_opening_mode"] == "open"
    assert mem["session_opening_mode_mixed"] is False
    await d.step(60, binary_sensor__terrasse="on")
    await d.step(5)
    assert d.mem("kueche")["session_opening_mode"] == "open"
    assert d.mem("kueche")["session_opening_mode_mixed"] is True
