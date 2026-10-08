"""Characterisation ("golden master") test for the FreshAirIQ coordinator.

Runs the real coordinator update cycle against scripted household scenarios with a
frozen clock, in-memory storage and no network, then fingerprints every cycle's
output and the persisted learning state. Refactorings of the coordinator must
reproduce the recorded fingerprints exactly.

    python tools/coordinator_golden.py --record      # write the reference
    python tools/coordinator_golden.py --check       # compare (exit 1 on drift)
    python tools/coordinator_golden.py --check --coverage
    python tools/coordinator_golden.py --dump DIR    # full JSON per cycle for diffing
    python tools/coordinator_golden.py --english     # English HA: same learning state, no German output
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "coordinator_golden.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from golden import ha_stub  # noqa: E402

ha_stub.install()
for name, path in (("custom_components", ROOT / "custom_components"),
                   ("custom_components.freshairiq", ROOT / "custom_components" / "freshairiq")):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]  # type: ignore[attr-defined]
        sys.modules[name] = module

from custom_components.freshairiq import coordinator as coord_mod  # noqa: E402
from custom_components.freshairiq.storage import LearningStore  # noqa: E402

TZ = ha_stub.TZ


def _freeze_package_time() -> None:
    counter = {"n": 0}

    def fake_uuid4():
        counter["n"] += 1
        return types.SimpleNamespace(hex=f"{counter['n']:032x}")

    for name, module in list(sys.modules.items()):
        if not name.startswith("custom_components.freshairiq") or module is None:
            continue
        if getattr(module, "datetime", None) is ha_stub._real_datetime:
            module.datetime = ha_stub.FrozenDateTime
        if hasattr(module, "perf_counter"):
            module.perf_counter = ha_stub.CLOCK.perf_counter
        if hasattr(module, "uuid4"):
            module.uuid4 = fake_uuid4
        if isinstance(getattr(module, "VERSION", None), str):
            # The release number is recorded in diagnostics; pin it so the reference
            # stays valid across version bumps.
            module.VERSION = "0.0.0-golden"


# --------------------------------------------------------------------------- config
def _room(key, name, floor, *, temp, hum, contacts=(), volume=None, dims=None, co2="", climate="",
          exhaust="", include=True, orientation="south", mode="any", sort=0, extra=None):
    room = {
        "key": key, "name": name, "floor": floor, "sort_order": sort,
        "include_in_calculations": include,
        "temperature": list(temp), "humidity": list(hum),
        "temperature_aggregation": "mean", "humidity_aggregation": "mean",
        "contacts": list(contacts), "contact_mode": mode,
        "contact_delays": {c: 0 for c in contacts},
        "contact_orientations": {c: orientation for c in contacts},
        "window_orientation": orientation,
        "volume_mode": "dimensions" if dims else "direct",
        # Mirrors config_flow: complete dimensions are stored together with their volume.
        "volume": round(dims[0] * dims[1] * dims[2], 3) if dims else volume,
        "length": dims[0] if dims else None, "width": dims[1] if dims else None, "height": dims[2] if dims else None,
        "co2": co2, "climate": climate, "exhaust_fan": exhaust,
        "ventilation_threshold_mode": "automatic", "ventilation_threshold_percent": 5, "ventilation_threshold_ml": 100,
        "goal_priorities": ["humidity", "co2", "temperature"],
        "target_temperature_mode": "automatic",
        "moisture_sources": [],
    }
    room.update(extra or {})
    return room


HOUSE_ROOMS = [
    _room("bad", "Badezimmer", "ground_floor", temp=["sensor.bad_t"], hum=["sensor.bad_h"], contacts=["binary_sensor.bad_fenster"],
          dims=(3.0, 2.5, 2.5), sort=0, extra={"moisture_sources": ["shower"]}),
    _room("flur", "Flur EG", "ground_floor", temp=["sensor.flur_t1", "sensor.flur_t2"], hum=["sensor.flur_h"],
          contacts=["binary_sensor.haustuer"], volume=30, orientation="north", sort=1),
    _room("kueche", "Wohnküche", "ground_floor", temp=["sensor.kueche_t"], hum=["sensor.kueche_h"],
          contacts=["binary_sensor.kueche_fenster", "binary_sensor.terrasse"], volume=95, co2="sensor.kueche_co2",
          climate="climate.kueche", orientation="west", sort=2, extra={"moisture_sources": ["cooking"]}),
    _room("schlaf", "Schlafzimmer", "upper_floor", temp=["sensor.schlaf_t"], hum=["sensor.schlaf_h"],
          contacts=["binary_sensor.schlaf_fenster"], volume=42, orientation="east", sort=3),
    _room("buero", "Arbeitszimmer", "upper_floor", temp=["sensor.buero_t"], hum=["sensor.buero_h"],
          contacts=["binary_sensor.buero_fenster"], volume=33, exhaust="fan.buero_abluft", sort=4),
    _room("lager", "Abstellraum", "basement", temp=[], hum=[], volume=12, include=False, sort=5),
]

BASE_DATA = {
    "outdoor_weather": "weather.home",
    "outdoor_temperature": "sensor.aussen_t",
    "outdoor_humidity": "sensor.aussen_h",
    "rooms": HOUSE_ROOMS,
    "levels": ["basement", "ground_floor", "upper_floor"],
}
BASE_OPTIONS = {
    "adult_occupants": 2, "child_occupants": 1, "night_start_hour": "22:30", "night_end_hour": "06:30",
    "night_forecast_enabled": True, "notifications_enabled": False, "learning_enabled": True,
    "diagnostics_consent": "declined",
}


def _house_states() -> dict[str, tuple[Any, dict]]:
    temp = {"device_class": "temperature", "unit_of_measurement": "°C", "state_class": "measurement"}
    hum = {"device_class": "humidity", "unit_of_measurement": "%", "state_class": "measurement"}
    states: dict[str, tuple[Any, dict]] = {
        "weather.home": ("rainy", {"temperature": 9.0, "humidity": 82.0, "wind_speed": 12.0, "wind_bearing": 250}),
        "sensor.aussen_t": (9.0, temp), "sensor.aussen_h": (82.0, hum),
        "sensor.bad_t": (23.4, temp), "sensor.bad_h": (79.0, hum),
        "sensor.flur_t1": (20.6, temp), "sensor.flur_t2": (20.9, temp), "sensor.flur_h": (63.0, hum),
        "sensor.kueche_t": (22.1, temp), "sensor.kueche_h": (61.0, hum),
        "sensor.kueche_co2": (1180, {"device_class": "carbon_dioxide", "unit_of_measurement": "ppm"}),
        "climate.kueche": ("heat", {"temperature": 21.5, "current_temperature": 22.1, "hvac_action": "heating"}),
        "sensor.schlaf_t": (19.4, temp), "sensor.schlaf_h": (58.0, hum),
        "sensor.buero_t": (21.2, temp), "sensor.buero_h": (55.0, hum),
        "fan.buero_abluft": ("off", {}),
    }
    for contact in ("binary_sensor.bad_fenster", "binary_sensor.haustuer", "binary_sensor.kueche_fenster",
                    "binary_sensor.terrasse", "binary_sensor.schlaf_fenster", "binary_sensor.buero_fenster"):
        states[contact] = ("off", {"device_class": "window" if "fenster" in contact else "door"})
    return states


def _forecast(start: datetime, hours: int = 24, temp=9.0, hum=82.0) -> list[dict[str, Any]]:
    out = []
    for h in range(hours):
        out.append({"datetime": (start + timedelta(hours=h)).isoformat(), "temperature": round(temp - 0.3 * min(h, 8), 1),
                    "humidity": min(98.0, hum + h), "precipitation": 0.4 if h < 6 else 0.0, "condition": "rainy"})
    return out


# ------------------------------------------------------------------------ scenarios
def _scenario_evening() -> dict:
    steps: list[dict] = [{"advance": 60, "label": "idle"} for _ in range(4)]
    steps.append({"advance": 60, "set": {"binary_sensor.bad_fenster": "on"}, "label": "bath window open"})
    for i in range(12):
        steps.append({"advance": 60, "set": {"sensor.bad_h": round(79.0 - 1.6 * (i + 1), 1), "sensor.bad_t": round(23.4 - 0.12 * (i + 1), 2)},
                      "label": f"airing {i + 1}"})
    steps.append({"advance": 60, "set": {"binary_sensor.bad_fenster": "off"}, "label": "bath window closed"})
    for i in range(8):
        steps.append({"advance": 120, "set": {"sensor.bad_h": round(60.0 + 0.5 * (i + 1), 1)}, "label": f"post close {i + 1}"})
    steps.append({"advance": 60, "set": {"binary_sensor.kueche_fenster": "on", "binary_sensor.terrasse": "on"}, "label": "cross ventilation kitchen"})
    for i in range(6):
        steps.append({"advance": 60, "set": {"sensor.kueche_co2": 1180 - 110 * (i + 1), "sensor.kueche_h": round(61 - 0.8 * (i + 1), 1),
                                             "sensor.kueche_t": round(22.1 - 0.15 * (i + 1), 2)}, "label": f"kitchen airing {i + 1}"})
    steps.append({"advance": 60, "set": {"binary_sensor.kueche_fenster": "off", "binary_sensor.terrasse": "off"}, "label": "kitchen closed"})
    for i in range(10):  # into the night window and past midnight
        steps.append({"advance": 1800, "set": {"sensor.schlaf_h": round(58 + 0.6 * (i + 1), 1), "sensor.aussen_t": round(9 - 0.3 * i, 1)},
                      "label": f"night {i + 1}"})
    steps.append({"advance": 3 * 3600, "set": {"sensor.schlaf_h": 66.0}, "label": "morning"})
    steps.append({"advance": 60, "set": {"binary_sensor.schlaf_fenster": "on"}, "label": "bedroom window open"})
    for i in range(5):
        steps.append({"advance": 60, "set": {"sensor.schlaf_h": round(66 - 1.5 * (i + 1), 1)}, "label": f"bedroom airing {i + 1}"})
    steps.append({"advance": 60, "set": {"binary_sensor.schlaf_fenster": "off"}, "label": "bedroom closed"})
    return {"start": datetime(2026, 10, 7, 21, 0, tzinfo=TZ), "data": BASE_DATA, "options": BASE_OPTIONS, "steps": steps}


def _scenario_sensor_trouble() -> dict:
    steps: list[dict] = [{"advance": 60, "label": "idle"} for _ in range(2)]
    steps.append({"advance": 60, "set": {"sensor.bad_h": "unavailable"}, "label": "bath humidity unavailable"})
    steps.append({"advance": 60, "set": {"sensor.aussen_t": "unknown", "sensor.flur_t1": "unavailable"}, "label": "outdoor + one flur sensor gone"})
    steps.append({"advance": 60, "set": {"sensor.kueche_h": -5, "sensor.kueche_co2": "nan"}, "label": "implausible values"})
    steps.append({"advance": 60, "set": {"binary_sensor.bad_fenster": "on"}, "label": "window open without humidity"})
    steps.append({"advance": 120, "set": {"sensor.bad_h": 70.0}, "label": "bath humidity back"})
    steps.append({"advance": 60, "set": {"sensor.aussen_t": 8.5, "sensor.flur_t1": 20.5, "sensor.kueche_h": 60.0, "sensor.kueche_co2": 900}, "label": "all recovered"})
    steps.append({"advance": 60, "set": {"binary_sensor.bad_fenster": "off"}, "label": "closed"})
    for i in range(3):
        steps.append({"advance": 120, "label": f"recovery {i + 1}"})
    return {"start": datetime(2026, 10, 8, 8, 0, tzinfo=TZ), "data": BASE_DATA, "options": BASE_OPTIONS, "steps": steps}


def _scenario_summer() -> dict:
    steps: list[dict] = [{"advance": 300, "label": "warm afternoon"} for _ in range(2)]
    steps.append({"advance": 3600, "set": {"sensor.aussen_t": 19.5, "sensor.aussen_h": 55.0}, "label": "evening cools"})
    steps.append({"advance": 60, "set": {"binary_sensor.schlaf_fenster": "on"}, "label": "bedroom open for cooling"})
    for i in range(6):
        steps.append({"advance": 120, "set": {"sensor.schlaf_t": round(27.0 - 0.4 * (i + 1), 2)}, "label": f"cooling {i + 1}"})
    steps.append({"advance": 60, "set": {"binary_sensor.schlaf_fenster": "off", "fan.buero_abluft": "on"}, "label": "bedroom closed, exhaust on"})
    for i in range(4):
        steps.append({"advance": 120, "set": {"sensor.buero_h": round(68 - 1.2 * (i + 1), 1)}, "label": f"exhaust {i + 1}"})
    steps.append({"advance": 60, "set": {"fan.buero_abluft": "off"}, "label": "exhaust off"})
    steps.append({"advance": 600, "label": "settle"})
    return {"start": datetime(2026, 7, 15, 15, 0, tzinfo=TZ), "data": BASE_DATA,
            "options": {**BASE_OPTIONS, "operating_profile": "summer_cooling"}, "steps": steps,
            "initial": {"sensor.aussen_t": 29.0, "sensor.aussen_h": 40.0, "sensor.schlaf_t": 27.0, "sensor.schlaf_h": 52.0,
                        "sensor.buero_t": 26.5, "sensor.buero_h": 68.0, "sensor.bad_h": 60.0, "climate.kueche": ("off", {"temperature": 22.0})}}


def _scenario_edge() -> dict:
    data = {**BASE_DATA, "rooms": [r for r in HOUSE_ROOMS if r["key"] == "lager"]}
    steps: list[dict] = [{"advance": 60, "label": "structure only"} for _ in range(3)]
    return {"start": datetime(2026, 1, 10, 12, 0, tzinfo=TZ), "data": data, "options": {}, "steps": steps}


def _scenario_empty() -> dict:
    data = {"outdoor_weather": "weather.home", "outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": []}
    return {"start": datetime(2026, 4, 2, 9, 0, tzinfo=TZ), "data": data, "options": {}, "steps": [{"advance": 60, "label": "no rooms"} for _ in range(2)]}


def _scenario_tilt_and_passive() -> dict:
    """Three-state window sensor, radio drop-out mid-session, flapping contact and a
    closed neighbour room aired indirectly through a cross-zone connection."""
    rooms = copy.deepcopy(HOUSE_ROOMS)
    for room in rooms:
        if room["key"] == "schlaf":
            room["contacts"] = ["sensor.schlaf_fenster_lage"]
            room["contact_delays"] = {"sensor.schlaf_fenster_lage": 0}
            room["contact_orientations"] = {"sensor.schlaf_fenster_lage": "east"}
        if room["key"] == "flur":
            room["contact_passage_doors"] = {"binary_sensor.haustuer": True}
    data = {**BASE_DATA, "rooms": rooms}
    options = {**BASE_OPTIONS, "cross_zone_connections": "schlaf+buero,kueche+flur"}
    lage = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
    steps: list[dict] = [{"advance": 60, "label": "idle"} for _ in range(2)]
    steps.append({"advance": 60, "set": {"sensor.schlaf_fenster_lage": ("tilted", lage)}, "label": "bedroom tilted"})
    for i in range(6):
        steps.append({"advance": 300, "set": {"sensor.schlaf_h": round(64 - 0.7 * (i + 1), 1), "sensor.buero_h": round(58 - 0.3 * (i + 1), 1)},
                      "label": f"tilted {i + 1}"})
    steps.append({"advance": 60, "set": {"sensor.schlaf_fenster_lage": ("unavailable", lage)}, "label": "radio drop-out"})
    steps.append({"advance": 120, "set": {"sensor.schlaf_h": 59.0}, "label": "still dropped"})
    steps.append({"advance": 60, "set": {"sensor.schlaf_fenster_lage": ("open", lage)}, "label": "back: fully open"})
    for i in range(4):
        steps.append({"advance": 60, "set": {"sensor.schlaf_h": round(59 - 1.2 * (i + 1), 1)}, "label": f"open {i + 1}"})
    steps.append({"advance": 60, "set": {"sensor.schlaf_fenster_lage": ("closed", lage)}, "label": "closed"})
    steps.append({"advance": 5, "set": {"binary_sensor.kueche_fenster": "on"}, "label": "kitchen flap open"})
    steps.append({"advance": 5, "set": {"binary_sensor.kueche_fenster": "off"}, "label": "kitchen flap closed"})
    steps.append({"advance": 60, "set": {"binary_sensor.haustuer": "on"}, "label": "front door open"})
    for i in range(3):
        steps.append({"advance": 120, "set": {"sensor.flur_h": round(63 - 1.0 * (i + 1), 1)}, "label": f"door open {i + 1}"})
    steps.append({"advance": 60, "set": {"binary_sensor.haustuer": "off"}, "label": "front door closed"})
    steps.append({"advance": 900, "label": "settle"})
    return {"start": datetime(2026, 11, 3, 18, 0, tzinfo=TZ), "data": data, "options": options, "steps": steps,
            "initial": {"sensor.schlaf_fenster_lage": ("closed", lage), "sensor.schlaf_h": 64.0}}


SCENARIOS = {
    "evening_ventilation_and_night": _scenario_evening,
    "sensor_trouble": _scenario_sensor_trouble,
    "summer_cooling_and_exhaust": _scenario_summer,
    "structure_room_only": _scenario_edge,
    "no_rooms": _scenario_empty,
    "tilt_dropout_and_passive": _scenario_tilt_and_passive,
}


# --------------------------------------------------------------------------- runner
def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_canon(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True, default=str))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return repr(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return repr(value)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(_canon(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


async def _run_scenario(name: str, spec: dict, dump_dir: Path | None) -> dict:
    ha_stub.Store._MEMORY.clear()
    ha_stub.SESSION.calls.clear()
    ha_stub.CLOCK.now = spec["start"]
    ha_stub.CLOCK._perf = 1000.0
    hass = ha_stub.HomeAssistant()
    base = _house_states()
    for entity, value in {**base, **spec.get("initial", {})}.items():
        state, attrs = value if isinstance(value, tuple) else (value, base.get(entity, (None, {}))[1])
        hass.states.async_set(entity, state, attrs)
    hass.services.forecast = _forecast(spec["start"])
    entry = types.SimpleNamespace(entry_id=f"golden-{name}", title="FreshAirIQ", version=8, minor_version=1,
                                  data=copy.deepcopy(spec["data"]), options=copy.deepcopy(spec["options"]),
                                  subentries={}, runtime_data=None, async_on_unload=lambda f: None)
    store = LearningStore(hass, entry.entry_id)
    await store.async_load()
    coordinator = coord_mod.FreshAirIQCoordinator(hass, entry, store)
    await coordinator.async_start_listeners()
    cycles = []
    for index, step in enumerate([{"advance": 0, "label": "first refresh"}] + spec["steps"]):
        ha_stub.CLOCK.advance(step.get("advance", 0))
        for entity, value in (step.get("set") or {}).items():
            old = hass.states.get(entity)
            state, attrs = value if isinstance(value, tuple) else (value, old.attributes if old else {})
            hass.states.async_set(entity, state, attrs)
        data = await coordinator._async_update_data()
        coordinator.data = data
        await hass.async_block_till_done()
        cycle = {"label": step.get("label", ""), "keys": {k: _digest(v) for k, v in sorted(data.items())},
                 "all": _digest(data), "store": _digest(store.data)}
        if ENGLISH_LEAKS is not None:
            _collect_german(name, index, data, ENGLISH_LEAKS)
        cycles.append(cycle)
        if dump_dir is not None:
            dump_dir.mkdir(parents=True, exist_ok=True)
            (dump_dir / f"{name}.{index:03d}.json").write_text(
                json.dumps({"data": _canon(data), "store": _canon(store.data)}, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    await coordinator.async_stop_listeners()
    network = list(ha_stub.SESSION.calls)
    if str(entry.options.get("diagnostics_consent", "unset")) != "granted" and network:
        raise AssertionError(f"{name}: network access without consent: {network[:3]}")
    return {"cycles": cycles, "persisted": _digest(ha_stub.Store._MEMORY), "network_calls": network}


ENGLISH_LEAKS: list[str] | None = None


def _collect_german(name: str, index: int, data: dict, leaks: list[str]) -> None:
    """Every published text must be English when Home Assistant is not German."""
    from custom_components.freshairiq import localize

    rooms = data.get("rooms") if isinstance(data.get("rooms"), dict) else {}
    protected = {str(r.get(f) or "") for r in rooms.values() if isinstance(r, dict) for f in ("name", "key", "floor")}
    protected |= set(rooms)
    protected.discard("")

    def walk(value: Any, path: str, parent: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in localize._SKIP_KEYS and not (key == "status" and parent == "components"):
                    continue
                walk(item, f"{path}.{key}", str(key))
        elif isinstance(value, list):
            for item in value:
                walk(item, path + "[]", parent)
        elif isinstance(value, str) and " " in value and localize._german_score(value, protected):
            leaks.append(f"{name}#{index} {path}: {value[:160]}")

    if data.get("output_language") != "en":
        leaks.append(f"{name}#{index}: output_language missing")
    walk(data, "")


async def _run_all(dump_dir: Path | None) -> dict:
    _freeze_package_time()
    return {name: await _run_scenario(name, factory(), dump_dir) for name, factory in SCENARIOS.items()}


def _coverage(run) -> tuple[dict, dict]:
    target = coord_mod.__file__
    executed: set[int] = set()

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != target:
            return None

        def local(frame, event, arg):
            if event == "line":
                executed.add(frame.f_lineno)
            return local
        return local

    sys.settrace(tracer)
    try:
        result = run()
    finally:
        sys.settrace(None)
    import ast
    tree = ast.parse(Path(target).read_text(encoding="utf-8"))
    spans = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines = {n.lineno for n in ast.walk(node) if isinstance(n, ast.stmt) and n is not node}
            if lines:
                spans[node.name] = (len(lines & executed), len(lines))
    return result, spans


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dump", type=Path)
    mode.add_argument("--english", action="store_true")
    parser.add_argument("--coverage", action="store_true")
    args = parser.parse_args()
    if args.english:
        global ENGLISH_LEAKS
        ENGLISH_LEAKS = []
        ha_stub.Config.language = "en"
    run = lambda: asyncio.run(_run_all(args.dump))
    if args.coverage:
        result, spans = _coverage(run)
    else:
        result, spans = run(), {}
    total = sum(len(s["cycles"]) for s in result.values())
    if args.english:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        drift = [
            f"{name} cycle {i}: learning state differs from the German run"
            for name, exp in expected.items()
            for i, (e, g) in enumerate(zip(exp["cycles"], result.get(name, {}).get("cycles", [])))
            if e["store"] != g["store"]
        ]
        if drift or ENGLISH_LEAKS:
            print("english output FAILED")
            for line in (drift + (ENGLISH_LEAKS or []))[:60]:
                print("  " + line)
            return 1
        print(f"english output OK: {len(result)} scenarios / {total} cycles, identical learning state, no German text")
        return 0
    if args.record:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps({"schema": 1, "scenarios": result}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded {len(result)} scenarios / {total} cycles -> {FIXTURE.relative_to(ROOT)}")
    elif args.check:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        drift = []
        for name, exp in expected.items():
            got = result.get(name)
            if got is None:
                drift.append(f"{name}: missing")
                continue
            for i, (e, g) in enumerate(zip(exp["cycles"], got["cycles"])):
                if e["all"] != g["all"] or e["store"] != g["store"]:
                    keys = sorted(k for k in set(e["keys"]) | set(g["keys"]) if e["keys"].get(k) != g["keys"].get(k))
                    drift.append(f"{name} cycle {i} ({e['label']}): data keys {keys[:12]}{' +store' if e['store'] != g['store'] else ''}")
                    break
            if len(exp["cycles"]) != len(got["cycles"]):
                drift.append(f"{name}: cycle count {len(exp['cycles'])} != {len(got['cycles'])}")
            if exp["persisted"] != got["persisted"]:
                drift.append(f"{name}: persisted storage differs")
        if drift:
            print("GOLDEN MASTER DRIFT:")
            for d in drift:
                print("  -", d)
            return 1
        print(f"golden master OK: {len(result)} scenarios / {total} cycles identical")
    else:
        print(f"dumped {total} cycles to {args.dump}")
    if spans:
        impl = spans.get("_async_update_data_impl", (0, 0))
        print(f"coverage _async_update_data_impl: {impl[0]}/{impl[1]} statements ({100 * impl[0] / max(1, impl[1]):.1f} %)")
        tot = [sum(v[0] for v in spans.values()), sum(v[1] for v in spans.values())]
        print(f"coverage coordinator.py functions: {tot[0]}/{tot[1]} statements ({100 * tot[0] / max(1, tot[1]):.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
