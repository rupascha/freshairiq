"""0.26.5.4: start model in the real coordinator.

A room that has not learned yet starts from the shipped start model; the first
airing learns from that value, and the finished airing reports its measured
exchange rate in the session record (the hub builds the start model from it).
"""
from __future__ import annotations

from datetime import datetime

from custom_components.freshairiq import coordinator_house, coordinator_room_model
from custom_components.freshairiq.start_model import FORMAT, validate

from ha_tests.test_cov_coordinator_b import BERLIN, _cleanup_coordinators, _make  # noqa: F401

MODEL = validate({"format": FORMAT, "format_version": 1, "version": "test-1", "cells": [
    {"mode": "open", "size": "all", "rate_per_min": 0.045}, {"mode": "tilted", "size": "all", "rate_per_min": 0.02},
]})


async def _bath_airing(d) -> None:
    await d.step(60, binary_sensor__bad_fenster="on")
    for i in range(12):
        await d.step(60, sensor__bad_h=round(79.0 - 1.6 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.12 * (i + 1), 2))
    await d.step(60, binary_sensor__bad_fenster="off")
    for i in range(8):
        await d.step(120, sensor__bad_h=round(60.0 + 0.5 * (i + 1), 1), sensor__bad_t=round(22.0 + 0.05 * i, 2))


def _capture(monkeypatch) -> list[dict]:
    """Completed session records as the coordinator hands them to the airing group."""
    seen: list[dict] = []
    original = coordinator_house.append_completed_sessions

    def spy(group, sessions):
        seen.extend(dict(s) for s in sessions if isinstance(s, dict) and s.get("key") == "bad")
        return original(group, sessions)

    monkeypatch.setattr(coordinator_house, "append_completed_sessions", spy)
    return seen


async def test_new_room_starts_from_the_start_model_and_learns_from_there(hass, freezer, monkeypatch) -> None:
    monkeypatch.setattr(coordinator_room_model, "START_MODEL", MODEL)
    sessions = _capture(monkeypatch)
    d = await _make(hass, freezer, start=datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN))
    mem = d.mem("bad")
    assert mem["learning_rate"] == 0.045 and mem["opening_learning"]["tilted"]["rate"] == 0.02
    assert mem["start_model"] == {"version": "test-1", "rates": {"open": 0.045, "tilted": 0.02}}
    assert d.room("bad")["learned_exchange_rate_per_min"] == 0.045
    await _bath_airing(d)
    mem = d.mem("bad")
    session = sessions[-1]
    observation = session["learning_observation"]
    assert observation["rate_before"] == 0.045 and observation["samples_before"] == 0
    # learned from the start value (0.045 → 0.044 towards the measured 0.040), not from the old 0.03
    assert mem["learning_samples"] == 1 and mem["learning_rate"] == 0.044
    assert observation["usable"] is True and observation["observed_rate_per_min"] == 0.03996
    # a learned room keeps its own value when the start model is withdrawn; unlearned ways of airing go back
    monkeypatch.setattr(coordinator_room_model, "START_MODEL", validate(None))
    await d.step(60)
    assert d.mem("bad")["learning_rate"] == 0.044 and d.mem("bad")["opening_learning"]["tilted"]["rate"] == 0.015


async def test_without_a_start_model_nothing_changes(hass, freezer, monkeypatch) -> None:
    sessions = _capture(monkeypatch)
    d = await _make(hass, freezer, start=datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN))
    mem = d.mem("bad")
    assert mem["learning_rate"] == 0.03 and "start_model" not in mem
    await _bath_airing(d)
    assert set(sessions[-1]["learning_observation"]) == {
        "observed_rate_per_min", "usable", "start_ah", "end_ah", "source_ah", "elapsed_min", "rate_before", "samples_before"}


async def test_a_tilted_window_without_tilt_learning_uses_the_tilt_start_value(hass, freezer, monkeypatch) -> None:
    from ha_tests.test_cov_coordinator_b import _data, _rooms

    monkeypatch.setattr(coordinator_room_model, "START_MODEL", MODEL)
    lage = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
    rooms = _rooms()
    for room in rooms:
        if room["key"] == "schlaf":
            room["contacts"] = ["sensor.schlaf_fenster_lage"]
            room["contact_delays"] = {"sensor.schlaf_fenster_lage": 0}
            room["contact_orientations"] = {"sensor.schlaf_fenster_lage": "east"}
    d = await _make(hass, freezer, data=_data(rooms), initial={"sensor.schlaf_fenster_lage": ("closed", lage), "sensor.schlaf_h": 64.0})
    assert d.room("schlaf")["learned_exchange_rate_per_min"] == 0.045  # closed: the general start value
    await d.step(60, sensor__schlaf_fenster_lage=("tilted", lage))
    await d.step(60)
    assert d.room("schlaf")["learned_exchange_rate_per_min"] == 0.02  # tilted, not learned yet: tilt start value
