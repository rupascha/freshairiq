#!/usr/bin/env python3
"""Versioned replay comparison of the forecast, learning and room-decision models of several FreshAirIQ source trees.

Every tree (for example the tags v0.26.6.0 and v0.26.7.0, the delivered 0.26.7.1 before IQ2 and the current tree
with IQ2) runs in its own process and sees the same synthetic houses: the same start values, time stamps, room
volumes, sources and weather basis. Each model forecasts an airing from its start values only (no end value, no later
outdoor value), is scored against what the simulated sensors report, and learns from the airing afterwards
(prequential, so every score is out of sample for that room).

The synthetic truth is deliberately richer than any of the models: two moisture buffer nodes, a wall node, sources,
weather drift, exchange rates that vary from airing to airing, sensor lag, quantisation and noise. It is a consistency
and robustness comparison – no field validation: real houses, sensors and users are not in it.

Usage:
    python3 tools/iq2_compare.py --tree label=/path/to/tree [--tree …] [--seed 20261116] [--houses 30] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

HORIZONS = (5, 10, 15, 20, 30, 60)
DURATIONS = (6, 8, 10, 12, 15, 20, 25, 30, 45, 60, 90)
TARGET_RH = 58.0
STEP = 0.25  # simulation step in minutes


# ------------------------------------------------------------------------------------------------ synthetic truth

def absolute_humidity(temp_c: float, rh: float) -> float:
    saturation = 6.112 * math.exp(17.62 * temp_c / (243.12 + temp_c))
    return 216.7 * (rh / 100.0 * saturation) / (273.15 + temp_c)


def relative_humidity(temp_c: float, ah: float) -> float:
    saturation = 6.112 * math.exp(17.62 * temp_c / (243.12 + temp_c))
    return max(min(ah * (273.15 + temp_c) / 216.7 / saturation * 100.0, 100.0), 0.0)


def _quantise(value: float, step: float) -> float:
    return round(round(value / step) * step, 4)


def _room(rnd: random.Random, house_factor: float, index: int) -> dict[str, Any]:
    return {
        "key": f"r{index}", "volume": round(rnd.uniform(14.0, 60.0), 1),
        "rate_k": min(max(0.03 * house_factor * math.exp(rnd.gauss(0.0, 0.45)), 0.005), 0.14),   # true exchange, 1/min
        "surface_capacity": rnd.uniform(1.0, 6.0), "surface_coupling": rnd.uniform(0.02, 0.15),
        "deep_capacity": rnd.uniform(10.0, 40.0), "deep_coupling": rnd.uniform(0.002, 0.01),
        "wall_capacity": rnd.uniform(20.0, 80.0), "wall_coupling": rnd.uniform(0.05, 0.3),
        "sensor_lag": rnd.uniform(1.0, 4.0), "rh_step": rnd.choice((0.1, 0.5, 1.0)), "noise_rh": rnd.uniform(0.05, 0.3),
        "humid_bias": rnd.uniform(-4.0, 8.0),
    }


def _airing(rnd: random.Random, room: dict[str, Any], weather: dict[str, float], wind: float, source: bool, drift: float) -> dict[str, Any]:
    """Simulate one airing; returns what the integration would have seen (per-minute sensor values)."""
    duration = rnd.choice(DURATIONS)
    out_t, out_rh = weather["t"], weather["rh"]
    temp = wall = rnd.uniform(19.0, 23.0)
    rh0 = min(max(rnd.gauss(62.0 + room["humid_bias"], 6.0), 35.0), 88.0)
    air = absolute_humidity(temp, rh0)
    surface, deep = air - (rnd.uniform(0.0, 1.5) if source else rnd.uniform(-0.2, 0.3)), air - rnd.uniform(-0.2, 0.6)
    k = room["rate_k"] * wind
    source_ml_min = rnd.uniform(4.0, 25.0) if source else 0.0
    source_until = rnd.uniform(3.0, 25.0) if source else 0.0
    sensed_t, sensed_ah = temp, air
    minutes: list[dict[str, float]] = []
    steps = int(round(duration / STEP))
    for i in range(steps + 1):
        t = i * STEP
        if i % int(round(1.0 / STEP)) == 0:
            seen_t = _quantise(sensed_t + rnd.gauss(0.0, 0.03), 0.1)
            seen_rh = min(max(_quantise(relative_humidity(sensed_t, sensed_ah) + rnd.gauss(0.0, room["noise_rh"]), room["rh_step"]), 1.0), 100.0)
            now_out_t = out_t + weather["t_drift"] * t
            now_out_ah = absolute_humidity(out_t, out_rh) + drift * t
            minutes.append({"t": seen_t, "rh": seen_rh, "ah": round(absolute_humidity(seen_t, seen_rh), 4),
                            "out_t": round(now_out_t, 2), "out_ah": round(now_out_ah, 4)})
        outdoor_ah = absolute_humidity(out_t, out_rh) + drift * t
        outdoor_t = out_t + weather["t_drift"] * t
        gain = source_ml_min / room["volume"] if t < source_until else 0.0
        d_air = k * (outdoor_ah - air) + room["surface_coupling"] * (surface - air) + gain
        d_surface = room["surface_coupling"] / room["surface_capacity"] * (air - surface) + room["deep_coupling"] / room["surface_capacity"] * (deep - surface)
        d_deep = room["deep_coupling"] / room["deep_capacity"] * (surface - deep)
        d_temp = k * (outdoor_t - temp) + room["wall_coupling"] * (wall - temp)
        d_wall = room["wall_coupling"] / room["wall_capacity"] * (temp - wall)
        air, surface, deep = air + d_air * STEP, surface + d_surface * STEP, deep + d_deep * STEP
        temp, wall = temp + d_temp * STEP, wall + d_wall * STEP
        sensed_ah += (air - sensed_ah) * STEP / room["sensor_lag"]
        sensed_t += (temp - sensed_t) * STEP / room["sensor_lag"]
    return {"room": room["key"], "volume": room["volume"], "duration": duration, "source": source, "minutes": minutes,
            "season": weather["season"]}


def build_houses(seed: int, count: int, airings_per_room: int) -> list[dict[str, Any]]:
    """Independent houses; within a house some airings run in parallel (one weather, one wind: a correlated episode)."""
    rnd = random.Random(seed)
    houses = []
    for h in range(count):
        factor = math.exp(rnd.gauss(0.0, 0.4))
        rooms = [_room(rnd, factor, i) for i in range(rnd.randint(2, 5))]
        drift_room = rnd.choice(rooms)["key"] if rnd.random() < 0.5 else None      # a room whose windows change half way
        episodes = []
        for e in range(airings_per_room):
            summer = rnd.random() < 0.25
            weather = {"t": rnd.uniform(16.0, 27.0) if summer else rnd.uniform(-4.0, 12.0),
                       "rh": rnd.uniform(45.0, 90.0) if summer else rnd.uniform(65.0, 95.0),
                       "t_drift": rnd.gauss(0.0, 0.01), "season": "summer" if summer else "winter"}
            wind = math.exp(rnd.gauss(0.0, 0.25))
            together = rooms if rnd.random() < 0.3 else [rnd.choice(rooms)]
            drift = rnd.gauss(0.0, 0.004) + (0.03 if rnd.random() < 0.05 else 0.0)  # sometimes the weather turns
            episode = []
            for room in together:
                actual = dict(room)
                if room["key"] == drift_room and e >= airings_per_room // 2:
                    actual["rate_k"] = room["rate_k"] * 0.45
                airing = _airing(rnd, actual, weather, wind, rnd.random() < 0.15, drift)
                airing["drifted"] = bool(room["key"] == drift_room and e >= airings_per_room // 2)
                airing["parallel"] = len(together)
                episode.append(airing)
            episodes.append(episode)
        houses.append({"house": f"h{h}", "episodes": episodes})
    return houses


# ------------------------------------------------------------------------------------------------ worker (one tree)

def _worker(root: Path) -> None:
    """Runs inside the process of one source tree: forecast → score inputs → learn, airing by airing."""
    import inspect
    import runpy

    sys.path.insert(0, str(root))
    runpy.run_path(str(root / "tests" / "conftest.py"))  # the tree's own Home Assistant stub
    from dataclasses import fields

    from custom_components.freshairiq import const, forecast, model

    try:
        from custom_components.freshairiq import iq2, iq2_runtime
    except ImportError:
        iq2 = iq2_runtime = None
    try:
        from custom_components.freshairiq.room_close_strategy import room_close_options
    except ImportError:
        room_close_options = None

    options = {**const.DEFAULT_OPTIONS, "operating_profile": "dehumidify", "target_rh": TARGET_RH, "min_duration_min": 3.0}
    protect = {**options, "airing_min_room_temp_c": 16.0}
    if room_close_options is not None:
        options, protect = room_close_options(options, {}), room_close_options(protect, {})
    no_limit = getattr(const, "NO_DURATION_LIMIT_MIN", None)
    room_fields = {f.name for f in fields(model.RoomInput)}
    has_limit = hasattr(model, "temperature_limit_reached")       # the user's temperature limit exists since 0.26.7.0
    manifest = json.loads((root / "custom_components" / "freshairiq" / "manifest.json").read_text(encoding="utf-8"))
    tree = {"version": manifest.get("version"), "module": str(Path(model.__file__).resolve()), "iq2": iq2 is not None,
            "temperature_limit": has_limit, "goal_close_default": bool(options.get("room_close_on_goals"))}
    houses = json.load(sys.stdin)
    learn_parameters = inspect.signature(iq2.learn_airing).parameters if iq2 is not None else {}
    out = []
    for house in houses:
        memory: dict[str, dict[str, Any]] = {}
        house_state = None
        for episode in house["episodes"]:
            # the rooms of one episode open together: every start forecast sees the house state of that moment,
            # the airings teach afterwards in the order they end (never a later end before an earlier start)
            ended = []
            for airing in episode:
                mem = memory.setdefault(airing["room"], {"learning_rate": 0.03, "learning_samples": 0, "seen": 0})
                first = airing["minutes"][0]
                params, extra, start = None, {}, None
                rate = mem["learning_rate"]
                if iq2 is not None:
                    params, _ = iq2_runtime.iq2_room_parameters(mem, house_state, mode=None, legacy_rate=mem["learning_rate"],
                                                                has_contact=True, force_physics=False)
                    rate = params["rate"]
                    extra = iq2_runtime.iq2_forecast_arguments(params, mem, running=False, current_ah=first["ah"])
                    if "start" in learn_parameters:
                        start = iq2_runtime.iq2_start_context(params, mem, house_state, None)
                record = {"house": house["house"], "room": airing["room"], "seen": mem["seen"], "forecast": {}, "interval": {}}
                for horizon in HORIZONS:
                    result = forecast.horizon_forecast(
                        current_ah=first["ah"], source_ah=first["out_ah"], current_temp_c=first["t"], source_temp_c=first["out_t"],
                        volume_m3=airing["volume"], rate_per_min=rate, airflow_bonus=1.0, horizon_min=float(horizon),
                        min_duration_min=3.0, max_duration_min=no_limit if no_limit is not None else float(options.get("max_duration_min", 20.0)),
                        operating_profile="dehumidify", **extra)
                    net = result.get("net_room_change_ml", result.get("uncapped_physical_moisture_effect_ml", result.get("moisture_effect_ml")))
                    record["forecast"][str(horizon)] = [float(net), float(result.get("temperature_change_c") or 0.0)]
                    if iq2 is not None:
                        record["interval"][str(horizon)] = iq2.forecast_quality(mem.get("iq2"), float(net))["interval_ml"]
                record["decisions"] = _decide(model, room_fields, options, protect if has_limit else None, airing, rate, params)
                out.append(record)
                ended.append((airing, mem, start))
            for airing, mem, start in sorted(ended, key=lambda item: (float(item[0]["duration"]), item[0]["room"])):
                # learn after the airing, as the integration does (source airings are excluded by its quality gates)
                first, last, elapsed = airing["minutes"][0], airing["minutes"][-1], float(airing["duration"])
                if not airing["source"]:
                    if iq2 is not None:
                        frozen = {"start": start} if "start" in learn_parameters else {}
                        mem["iq2"], house_state, _ = iq2.learn_airing(
                            mem.get("iq2"), house_state, mode=iq2.GENERAL, base_rate=iq2_runtime.iq2_base_rate(mem, iq2.GENERAL),
                            start_ah=first["ah"], end_ah=last["ah"], source_ah=first["out_ah"], minutes=elapsed, volume_m3=airing["volume"],
                            quality_weight=1.0, parallel_rooms=airing["parallel"], legacy_rate=mem["learning_rate"],
                            start_temp=first["t"], end_temp=last["t"], source_temp=first["out_t"], **frozen)
                    mem["learning_rate"], mem["learning_samples"], _text, _valid = model.update_learning(
                        old_rate=mem["learning_rate"], old_samples=mem["learning_samples"], elapsed_min=elapsed, start_ah=first["ah"],
                        end_ah=last["ah"], source_ah=first["out_ah"], learning_enabled=True)
                mem["seen"] += 1
    json.dump({"tree": tree, "records": out}, sys.stdout)


def _decide(model: Any, room_fields: set[str], options: dict, protect: dict | None, airing: dict, rate: float, params: Any) -> dict[str, Any]:
    """The tree's own room model, minute by minute, with the stored close state the coordinator keeps."""
    latched, kind, goals, actions, cold, exposed = False, None, False, [], 0, 0
    critical = float(options.get("mould_critical_surface_rh", 90.0))
    for minute, row in enumerate(airing["minutes"]):
        out_rh = relative_humidity(row["out_t"], row["out_ah"])
        values = dict(key="r", name="R", temperature=row["t"], humidity=row["rh"], reference_temperature=row["out_t"],
                      reference_humidity=out_rh, volume_m3=airing["volume"], contact_open=True, contact_open_seconds=minute * 60.0,
                      learning_rate=rate, session_active=True, session_elapsed_min=float(minute), session_fresh_measurements=min(minute, 6),
                      session_start_temp=airing["minutes"][0]["t"], close_notified=latched, close_notified_kind=kind,
                      session_goals_reached=goals, moisture_source_active=False,
                      thermal_air_share=float(params["thermal_share"]) if params else 1.0)
        room = model.RoomInput(**{k: v for k, v in values.items() if k in room_fields})
        result = model.evaluate_room(room, options, False)
        close = bool(result.close_recommended)
        stored_kind = getattr(result, "close_kind", None)
        kind = ((stored_kind if kind is None or stored_kind == "goals_reached" else kind) if close else None)
        latched = close
        if getattr(result, "goals_reached_now", False):
            goals = True
        elif goals and not getattr(result, "goals_in_band", False):
            goals = False
        actions.append(1 if result.action == "Close" else 0)
        if protect is not None and row["t"] < 16.0 and row["out_t"] < row["t"] and minute >= 3:
            limited = model.evaluate_room(room, protect, False)
            # the tree's own rule: critical mould risk (surface humidity) outranks the user's temperature limit
            if float(getattr(limited, "surface_rh", 0.0) or 0.0) < critical:
                exposed += 1
                cold += 0 if limited.action == "Close" else 1
    return {"close": actions, "cold_open": cold if protect is not None else None, "cold_cycles": exposed}


# ------------------------------------------------------------------------------------------------ scoring

def _observed(airing: dict[str, Any], horizon: int) -> tuple[float, float] | None:
    if horizon > airing["duration"]:
        return None
    first, row = airing["minutes"][0], airing["minutes"][horizon]
    return (first["ah"] - row["ah"]) * airing["volume"], row["t"] - first["t"]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _house_equal(per_house: dict[str, list[float]]) -> tuple[float | None, int, int]:
    means = [sum(v) / len(v) for v in per_house.values() if v]
    return _mean(means), len(means), sum(len(v) for v in per_house.values())


def _bootstrap(per_house_a: dict[str, list[float]], per_house_b: dict[str, list[float]], seed: int = 7) -> tuple[float, float] | None:
    """90 % interval of the house-equal relative MAE change of a against b (houses resampled, not airings)."""
    houses = [h for h in per_house_a if per_house_a[h] and per_house_b.get(h)]
    if len(houses) < 5:
        return None
    rnd, values = random.Random(seed), []
    for _ in range(2000):
        pick = [rnd.choice(houses) for _ in houses]
        a = sum(statistics.fmean(per_house_a[h]) for h in pick)
        b = sum(statistics.fmean(per_house_b[h]) for h in pick)
        values.append((a - b) / b * 100.0 if b else 0.0)
    values.sort()
    return round(values[int(0.05 * len(values))], 1), round(values[int(0.95 * len(values))], 1)


def _naive(houses: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Honest simple baselines: "nothing changes" and "like this room's previous airing" (same removed share)."""
    null, last = [], []
    for house in houses:
        previous: dict[str, dict[int, tuple[float, float]]] = {}
        counts: dict[str, int] = {}
        for episode in house["episodes"]:
            # the same time order as the models: all starts of the episode first, then the ends by end time
            for airing in episode:
                first = airing["minutes"][0]
                difference = (first["ah"] - first["out_ah"]) * airing["volume"]
                t_difference = first["out_t"] - first["t"]
                seen = previous.setdefault(airing["room"], {})
                count = counts.get(airing["room"], 0)
                counts[airing["room"]] = count + 1
                null.append({"seen": count, "forecast": {str(h): [0.0, 0.0] for h in HORIZONS}})
                last.append({"seen": count, "forecast": {str(h): [seen.get(h, (0.0, 0.0))[0] * difference, seen.get(h, (0.0, 0.0))[1] * t_difference] for h in HORIZONS}})
            for airing in sorted(episode, key=lambda item: (float(item["duration"]), item["room"])):
                first = airing["minutes"][0]
                difference = (first["ah"] - first["out_ah"]) * airing["volume"]
                t_difference = first["out_t"] - first["t"]
                seen = previous.setdefault(airing["room"], {})
                if not airing["source"]:
                    for h in HORIZONS:
                        got = _observed(airing, h)
                        if got and abs(difference) > 1.0 and abs(t_difference) > 0.5:
                            seen[h] = (got[0] / difference, got[1] / t_difference)
    return {"null (keine Änderung)": null, "naiv (wie letzte Lüftung)": last}


def _decision_metrics(airing: dict[str, Any], decisions: dict[str, Any]) -> dict[str, float]:
    """Decision facts of one airing against configured goals and observable states (no counterfactual about the user)."""
    close, minutes = decisions["close"], airing["minutes"]
    early = reversals = 0
    reached_at = closed_at = None
    for minute, row in enumerate(minutes):
        delta = row["ah"] - row["out_ah"]
        if minute >= 1 and close[minute - 1] and not close[minute]:
            reversals += 1                               # "close" taken back
        # "close" although the only goal is open, the air clearly dries, nothing is added and the room is not warmed
        if close[minute] and row["rh"] > TARGET_RH + 2.0 and delta > 0.4 and not airing["source"] and row["out_t"] < row["t"] - 2.0:
            early = 1
        if reached_at is None and minute >= 3 and row["rh"] <= TARGET_RH and minutes[minute - 1]["rh"] <= TARGET_RH and not airing["source"]:
            reached_at = minute
        if reached_at is not None and closed_at is None and close[minute]:
            closed_at = minute
    out = {"early_close": float(early), "reversals": float(reversals)}
    if decisions.get("cold_open") is not None and decisions.get("cold_cycles"):
        out["limit_cycles_not_closed"] = float(decisions["cold_open"])
    if reached_at is not None:
        out["minutes_after_goal"] = float((closed_at if closed_at is not None else len(minutes) - 1) - reached_at)
        out["never_closed_after_goal"] = float(closed_at is None)
    return out


def score(houses: list[dict[str, Any]], records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    airings = [(house["house"], airing) for house in houses for episode in house["episodes"] for airing in episode]
    result: dict[str, Any] = {"airings": len(airings), "houses": len(houses), "models": {}}
    errors: dict[str, dict[str, dict[str, list[float]]]] = {}
    for label, rows in records.items():
        assert len(rows) == len(airings), (label, len(rows), len(airings))
        model: dict[str, Any] = {"horizons": {}, "strata": {}, "decisions": {}, "interval": {}}
        errors[label] = {}
        for horizon in HORIZONS:
            per_house: dict[str, list[float]] = {}
            bias: dict[str, list[float]] = {}
            temp: dict[str, list[float]] = {}
            direction: dict[str, list[float]] = {}
            covered, width = [], []
            for (house, airing), row in zip(airings, rows):
                got = _observed(airing, horizon)
                if got is None:
                    continue
                predicted, predicted_t = row["forecast"][str(horizon)]
                per_house.setdefault(house, []).append(abs(predicted - got[0]))
                bias.setdefault(house, []).append(predicted - got[0])
                temp.setdefault(house, []).append(abs(predicted_t - got[1]))
                if abs(got[0]) >= 5.0:
                    direction.setdefault(house, []).append(0.0 if (predicted > 0) == (got[0] > 0) else 1.0)
                interval = (row.get("interval") or {}).get(str(horizon))
                if interval:
                    covered.append(1.0 if interval[0] <= got[0] <= interval[1] else 0.0)
                    width.append(interval[1] - interval[0])
            mae, n_houses, n = _house_equal(per_house)
            errors[label][str(horizon)] = per_house
            model["horizons"][str(horizon)] = {
                "mae_ml": round(mae, 2), "bias_ml": round(_house_equal(bias)[0], 2), "temperature_mae_c": round(_house_equal(temp)[0], 3),
                "direction_error_pct": round(100.0 * (_house_equal(direction)[0] or 0.0), 1), "houses": n_houses, "airings": n}
            if covered:
                model["interval"][str(horizon)] = {"coverage_pct": round(100.0 * sum(covered) / len(covered), 1),
                                                   "mean_width_ml": round(sum(width) / len(width), 1), "airings": len(covered)}
        strata = {
            "erste 5 Lüftungen je Raum": lambda a, r: r.get("seen", 99) < 5, "6.–20. Lüftung": lambda a, r: 5 <= r.get("seen", 99) < 20,
            "ab 21. Lüftung": lambda a, r: r.get("seen", 0) >= 20, "mit Feuchtequelle": lambda a, r: a["source"],
            "ohne Feuchtequelle": lambda a, r: not a["source"], "Raum < 25 m³": lambda a, r: a["volume"] < 25,
            "Raum 25–40 m³": lambda a, r: 25 <= a["volume"] <= 40, "Raum > 40 m³": lambda a, r: a["volume"] > 40,
            "Winter": lambda a, r: a["season"] == "winter", "Sommer": lambda a, r: a["season"] == "summer",
            "nach Änderung des Raums": lambda a, r: a["drifted"], "parallele Räume": lambda a, r: a["parallel"] > 1,
        }
        for name, keep in strata.items():
            per_house = {}
            for (house, airing), row in zip(airings, rows):
                got = _observed(airing, 15)
                if got is not None and keep(airing, row):
                    per_house.setdefault(house, []).append(abs(row["forecast"]["15"][0] - got[0]))
            mae, n_houses, n = _house_equal(per_house)
            model["strata"][name] = {"mae_ml_15": None if mae is None else round(mae, 2), "houses": n_houses, "airings": n}
        if rows and "decisions" in rows[0]:
            sums: dict[str, dict[str, list[float]]] = {}
            for (house, airing), row in zip(airings, rows):
                for key, value in _decision_metrics(airing, row["decisions"]).items():
                    sums.setdefault(key, {}).setdefault(house, []).append(value)
            for key, per_house in sums.items():
                mean, n_houses, n = _house_equal(per_house)
                model["decisions"][key] = {"mean": round(mean, 3), "houses": n_houses, "airings": n}
        result["models"][label] = model
    result["errors"] = errors
    return result


def compare(result: dict[str, Any], candidate: str, baseline: str) -> dict[str, Any]:
    out = {}
    for horizon in HORIZONS:
        a, b = result["errors"][candidate][str(horizon)], result["errors"][baseline][str(horizon)]
        mae_a, mae_b = _house_equal(a)[0], _house_equal(b)[0]
        out[str(horizon)] = {"candidate_mae_ml": round(mae_a, 2), "baseline_mae_ml": round(mae_b, 2),
                             "change_pct": round((mae_a - mae_b) / mae_b * 100.0, 1) if mae_b else None, "interval_90": _bootstrap(a, b)}
    return out


def run(trees: dict[str, Path], seed: int, houses: int, airings: int) -> dict[str, Any]:
    data = build_houses(seed, houses, airings)
    payload = json.dumps(data)
    records: dict[str, list[dict[str, Any]]] = {}
    provenance: dict[str, dict[str, Any]] = {}
    for label, root in trees.items():
        done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(root)], input=payload,
                              capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise SystemExit(f"{label}: worker failed\n{done.stderr[-2000:]}")
        payload_out = json.loads(done.stdout)
        if not payload_out["tree"]["module"].startswith(str(root)):
            raise SystemExit(f"{label}: the model was loaded from {payload_out['tree']['module']}, not from {root}")
        records[label], provenance[label] = payload_out["records"], {**payload_out["tree"], "path": str(root)}
    records.update(_naive(data))
    result = score(data, records)
    result["seed"], result["trees"] = seed, provenance
    return result


def _markdown(result: dict[str, Any]) -> str:
    lines = [f"Häuser: {result['houses']} · Lüftungen: {result['airings']} · Seed: {result['seed']}", "",
             "| Modell | " + " | ".join(f"MAE {h} min (ml)" for h in HORIZONS) + " |", "|---|" + "---:|" * len(HORIZONS)]
    for label, model in result["models"].items():
        lines.append(f"| {label} | " + " | ".join(str(model["horizons"][str(h)]["mae_ml"]) for h in HORIZONS) + " |")
    lines += ["", "| Modell | " + " | ".join(f"Bias {h} (ml)" for h in HORIZONS) + " |", "|---|" + "---:|" * len(HORIZONS)]
    for label, model in result["models"].items():
        lines.append(f"| {label} | " + " | ".join(str(model["horizons"][str(h)]["bias_ml"]) for h in HORIZONS) + " |")
    lines += ["", "| Modell | " + " | ".join(f"Temp.-MAE {h} (°C)" for h in HORIZONS) + " |", "|---|" + "---:|" * len(HORIZONS)]
    for label, model in result["models"].items():
        lines.append(f"| {label} | " + " | ".join(str(model["horizons"][str(h)]["temperature_mae_c"]) for h in HORIZONS) + " |")
    keys = sorted({key for model in result["models"].values() for key in model.get("decisions", {})})
    if keys:
        lines += ["", "| Modell | " + " | ".join(f"Entscheidung {k}" for k in keys) + " |", "|---|" + "---:|" * len(keys)]
        for label, model in result["models"].items():
            if model.get("decisions"):
                lines.append(f"| {label} | " + " | ".join(str((model["decisions"].get(k) or {}).get("mean")) for k in keys) + " |")
    lines += ["", "Fallzahlen je Horizont (Lüftungen, die mindestens so lange liefen): "
              + ", ".join(f"{h} min: {next(iter(result['models'].values()))['horizons'][str(h)]['airings']}" for h in HORIZONS)]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--tree", action="append", default=[], help="label=path of a source tree (custom_components + tests/conftest.py)")
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--houses", type=int, default=30)
    parser.add_argument("--airings", type=int, default=120, help="airing episodes per house")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.worker:
        _worker(args.worker)
        return 0
    trees = {item.split("=", 1)[0]: Path(item.split("=", 1)[1]).resolve() for item in args.tree}
    if not trees:
        parser.error("at least one --tree label=path is required")
    result = run(trees, args.seed, args.houses, args.airings)
    labels = list(trees)
    result["comparison"] = {f"{labels[-1]} vs {other}": compare(result, labels[-1], other) for other in [*labels[:-1], *list(_naive([]))]}
    result.pop("errors")
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
