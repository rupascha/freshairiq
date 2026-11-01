"""0.26.5.4 (LM-01/LM-02): a fan-only airing uses the room's learned exhaust-fan model everywhere.

Sessions ventilated by the exhaust fan alone learn ``opening_learning["mechanical_exhaust"]``,
but the model selection only looked at the contacts, so the learned value was never read.
The forecast and its cost also used the general coefficient instead of the active one.
Deliberately different rates (general 0.03, passive 0.01, fan 0.08) show which one is used
in RoomInput, the horizon forecast, the forecast cost and the exported room data.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.freshairiq import coordinator_room_model as crm
from ha_tests.test_cov_coordinator_b import (  # noqa: F401 - fixture re-export
    BERLIN, HUM, OPTIONS, TEMP, WINDOW, _cleanup_coordinators, _data, _make, _room,
)

START = datetime(2026, 10, 27, 15, 0, tzinfo=BERLIN)
VOLUMES = {"buero": 23.0, "flur": 29.0, "wasch": 17.0, "abstell": 11.0}


def _rooms():
    return [
        _room("buero", "Büro", "ground_floor", temp=["sensor.buero_t"], hum=["sensor.buero_h"],
              contacts=["binary_sensor.buero_fenster"], volume=VOLUMES["buero"], exhaust="fan.abluft"),
        _room("flur", "Flur", "ground_floor", temp=["sensor.flur_t"], hum=["sensor.flur_h"],
              contacts=["binary_sensor.flur_tuer"], volume=VOLUMES["flur"], exhaust="fan.abluft"),
        _room("wasch", "Waschküche", "basement", temp=["sensor.wasch_t"], hum=["sensor.wasch_h"],
              volume=VOLUMES["wasch"], exhaust="fan.wasch"),
        _room("abstell", "Abstellraum", "basement", temp=["sensor.abstell_t"], hum=["sensor.abstell_h"],
              volume=VOLUMES["abstell"]),
    ]


INITIAL = {
    **{f"sensor.{k}_t": (22.0, TEMP) for k in VOLUMES}, **{f"sensor.{k}_h": (68.0, HUM) for k in VOLUMES},
    "binary_sensor.buero_fenster": ("off", WINDOW), "binary_sensor.flur_tuer": ("off", WINDOW),
    "fan.abluft": ("off", {}), "fan.wasch": ("off", {}),
}


def _models(mem, *, fan=0.08, fan_samples=3):
    mem.update(learning_rate=0.03, learning_samples=4, passive_learning_rate=0.01, passive_learning_samples=2)
    mem["opening_learning"] = {"mechanical_exhaust": {"rate": fan, "samples": fan_samples, "credit": 0.0}}


@pytest.fixture
def seen(monkeypatch):
    rates: dict[str, dict[float, list[float]]] = {"input": {}, "forecast": {}, "cost": {}}
    orig_eval, orig_fc, orig_cost = crm.evaluate_room, crm.horizon_forecast, crm.ventilation_cost_for_temperature_path

    def evaluate(room, *args, **kwargs):
        rates["input"].setdefault(room.volume_m3, []).append(round(room.learning_rate, 4))
        return orig_eval(room, *args, **kwargs)

    def forecast(**kwargs):
        rates["forecast"].setdefault(kwargs["volume_m3"], []).append(round(kwargs["rate_per_min"], 4))
        return orig_fc(**kwargs)

    def cost(volume, rate, *args, **kwargs):
        rates["cost"].setdefault(volume, []).append(round(rate, 4))
        return orig_cost(volume, rate, *args, **kwargs)

    monkeypatch.setattr(crm, "evaluate_room", evaluate)
    monkeypatch.setattr(crm, "horizon_forecast", forecast)
    monkeypatch.setattr(crm, "ventilation_cost_for_temperature_path", cost)
    return rates


def _used(seen, key):
    volume = VOLUMES[key]
    return {name: set(rows.get(volume, [])) for name, rows in seen.items()}


async def _start(hass, freezer, fan_rates=None, fan_samples=3):
    d = await _make(hass, freezer, start=START, data=_data(_rooms()), options={**OPTIONS, "forecast_horizon_min": 20}, initial=INITIAL)
    for key in VOLUMES:
        _models(d.mem(key), fan=(fan_rates or {}).get(key, 0.08), fan_samples=fan_samples)
    await d.step(60)
    return d


def _reset(seen):
    for rows in seen.values():
        rows.clear()


async def test_fan_only_with_closed_window_uses_the_exhaust_model(hass, freezer, seen) -> None:
    d = await _start(hass, freezer)
    _reset(seen)
    await d.step(60, fan__abluft="on")
    await d.step(60)
    assert d.mem("buero")["session_specialist_opening_mode"] == "mechanical_exhaust"
    assert _used(seen, "buero") == {"input": {0.08}, "forecast": {0.08}, "cost": {0.08}}
    assert d.room("buero")["learned_exchange_rate_per_min"] == 0.08


async def test_window_alone_and_fan_with_window_keep_the_general_model(hass, freezer, seen) -> None:
    d = await _start(hass, freezer)
    _reset(seen)
    await d.step(60, binary_sensor__buero_fenster="on")
    await d.step(60)
    assert _used(seen, "buero") == {"input": {0.03}, "forecast": {0.03}, "cost": {0.03}}
    _reset(seen)
    await d.step(60, fan__abluft="on")
    await d.step(60)
    # fan and window together: no proven fan-only effect, the general model stays
    assert _used(seen, "buero") == {"input": {0.03}, "forecast": {0.03}, "cost": {0.03}}
    assert d.room("buero")["learned_exchange_rate_per_min"] == 0.03


async def test_contactless_room_own_fan_versus_passive_neighbour(hass, freezer, seen) -> None:
    d = await _start(hass, freezer)
    _reset(seen)
    await d.step(60)
    assert _used(seen, "wasch")["input"] == {0.01}
    assert _used(seen, "abstell")["input"] == {0.01}
    _reset(seen)
    await d.step(60, fan__wasch="on")
    await d.step(60)
    assert _used(seen, "wasch") == {"input": {0.08}, "forecast": {0.08}, "cost": {0.08}}
    assert _used(seen, "abstell")["input"] == {0.01}


async def test_contactless_fan_room_without_fan_samples_keeps_the_passive_fallback(hass, freezer, seen) -> None:
    d = await _start(hass, freezer, fan_samples=0)
    _reset(seen)
    await d.step(60, fan__wasch="on", fan__abluft="on")
    await d.step(60)
    assert _used(seen, "wasch")["input"] == {0.01}
    assert _used(seen, "buero")["input"] == {0.03}


async def test_shared_fan_rooms_keep_their_own_models(hass, freezer, seen) -> None:
    d = await _start(hass, freezer, fan_rates={"buero": 0.08, "flur": 0.05})
    _reset(seen)
    await d.step(60, fan__abluft="on")
    await d.step(60)
    assert _used(seen, "buero") == {"input": {0.08}, "forecast": {0.08}, "cost": {0.08}}
    assert _used(seen, "flur") == {"input": {0.05}, "forecast": {0.05}, "cost": {0.05}}
    assert d.mem("buero")["opening_learning"]["mechanical_exhaust"]["rate"] == 0.08
    assert d.mem("flur")["opening_learning"]["mechanical_exhaust"]["rate"] == 0.05


async def test_learned_exhaust_model_is_read_by_the_next_fan_airing(hass, freezer, seen) -> None:
    d = await _make(hass, freezer, start=START, data=_data(_rooms()), options={**OPTIONS, "forecast_horizon_min": 20},
                    initial={**INITIAL, "sensor.wasch_h": (72.0, HUM)})
    await d.step(60, fan__wasch="on")
    for i in range(12):
        await d.step(60, sensor__wasch_h=round(72 - 1.0 * (i + 1), 1), sensor__wasch_t=round(22.0 - 0.05 * (i + 1), 2))
    await d.step(60, fan__wasch="off")
    await d.finish(sensor__wasch_h=60.5, sensor__wasch_t=21.4)
    mem = d.mem("wasch")
    assert mem["last_learning_valid"] is True, mem["diagnosis"]
    learned = mem["opening_learning"]["mechanical_exhaust"]
    assert learned["samples"] >= 1
    for _ in range(3):
        await d.step(60)
    _reset(seen)
    await d.step(60, fan__wasch="on")
    await d.step(60)
    rate = round(learned["rate"], 4)
    assert _used(seen, "wasch") == {"input": {rate}, "forecast": {rate}, "cost": {rate}}
    assert d.room("wasch")["learned_exchange_rate_per_min"] == round(learned["rate"], 3)
