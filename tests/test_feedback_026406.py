"""0.26.4.6 user-feedback features: overnight presence hold and several pollen sensors."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from custom_components.freshairiq.presence import current_night_start, resolve_occupancy

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=2))


def _tracker(state, changed):
    return SimpleNamespace(state=state, attributes={}, last_changed=changed)


def _options(**extra):
    return {"adult_occupants": 2, "adult_presence_entities": ["device_tracker.a", "device_tracker.b"],
            "night_start_hour": "22:00", "night_end_hour": "07:00", **extra}


def test_night_window_detection_handles_midnight_and_disabled_windows():
    opts = _options()
    assert current_night_start(opts, datetime(2026, 10, 8, 23, 30, tzinfo=TZ)) == datetime(2026, 10, 8, 22, 0, tzinfo=TZ)
    assert current_night_start(opts, datetime(2026, 10, 9, 3, 0, tzinfo=TZ)) == datetime(2026, 10, 8, 22, 0, tzinfo=TZ)
    assert current_night_start(opts, datetime(2026, 10, 9, 7, 0, tzinfo=TZ)) is None
    assert current_night_start(opts, datetime(2026, 10, 9, 14, 0, tzinfo=TZ)) is None
    assert current_night_start(opts, None) is None
    assert current_night_start({"night_start_hour": "06:00", "night_end_hour": "06:00"}, datetime(2026, 10, 9, 6, 0, tzinfo=TZ)) is None
    # Same-day window and garbage values fall back to the defaults.
    assert current_night_start({"night_start_hour": "01:00", "night_end_hour": "05:30"}, datetime(2026, 10, 9, 5, 0, tzinfo=TZ)) == datetime(2026, 10, 9, 1, 0, tzinfo=TZ)
    assert current_night_start({"night_start_hour": "x", "night_end_hour": None}, datetime(2026, 10, 9, 23, 0, tzinfo=TZ)) == datetime(2026, 10, 9, 22, 0, tzinfo=TZ)


def test_phone_switched_off_at_night_keeps_resident_home_only_when_enabled():
    now = datetime(2026, 10, 9, 2, 0, tzinfo=TZ)
    states = {
        "device_tracker.a": _tracker("not_home", datetime(2026, 10, 8, 22, 40, tzinfo=TZ)),  # phone off at bedtime
        "device_tracker.b": _tracker("not_home", datetime(2026, 10, 8, 18, 0, tzinfo=TZ)),   # really away since evening
    }
    off = resolve_occupancy(_options(), states.get, now)
    assert off["home_adults"] == 0 and off["away_adults"] == 2
    assert off["presence_night_hold"] is False

    on = resolve_occupancy(_options(presence_night_hold=True), states.get, now)
    assert on["home_adults"] == 1 and on["away_adults"] == 1
    assert on["residents_held_home_overnight"] == 1
    assert on["all_known_trackers_away"] is False

    # After the night ends the tracker state counts again as reported.
    morning = resolve_occupancy(_options(presence_night_hold=True), states.get, datetime(2026, 10, 9, 8, 0, tzinfo=TZ))
    assert morning["home_adults"] == 0


def test_night_hold_tolerates_naive_timestamps_and_missing_last_changed():
    now = datetime(2026, 10, 9, 1, 0)  # naive clock
    states = {
        "device_tracker.a": _tracker("not_home", datetime(2026, 10, 8, 23, 0, tzinfo=TZ)),
        "device_tracker.b": SimpleNamespace(state="not_home", attributes={}),
    }
    result = resolve_occupancy(_options(presence_night_hold=True), states.get, now)
    assert result["home_adults"] == 1 and result["away_adults"] == 1
    aware_now = datetime(2026, 10, 9, 1, 0, tzinfo=TZ)
    states["device_tracker.a"] = _tracker("not_home", datetime(2026, 10, 8, 23, 0))
    assert resolve_occupancy(_options(presence_night_hold=True), states.get, aware_now)["home_adults"] == 1


def test_night_hold_option_is_wired_into_settings_and_translations():
    import json

    from custom_components.freshairiq.const import DEFAULT_OPTIONS
    from custom_components.freshairiq.settings_contract import NATIVE_OPTION_KEYS

    assert DEFAULT_OPTIONS["presence_night_hold"] is False
    assert "presence_night_hold" in NATIVE_OPTION_KEYS
    flow = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    assert 'native_option_key("presence_night_hold")' in flow
    for name in ("translations/de.json", "translations/en.json", "strings.json"):
        text = (ROOT / "custom_components/freshairiq" / name).read_text(encoding="utf-8")
        assert text.count('"presence_night_hold"') == 8, name
        json.loads(text)


def _pollen_level():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_pollen_level", "_float_state")]
    from custom_components.freshairiq.climate_sources import entity_ids
    from custom_components.freshairiq.robustness import finite_float

    ns = {"entity_ids": entity_ids, "finite_float": finite_float, "Any": object, "HomeAssistant": object}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), "coordinator.py", "exec"), ns)
    return ns["_pollen_level"]


def test_several_pollen_sensors_use_the_highest_valid_value():
    pollen_level = _pollen_level()
    states = {"sensor.birke": SimpleNamespace(state="3"), "sensor.graeser": SimpleNamespace(state="5.5"),
              "sensor.offline": SimpleNamespace(state="unavailable")}
    hass = SimpleNamespace(states=SimpleNamespace(get=states.get))
    assert pollen_level(hass, ["sensor.birke", "sensor.graeser", "sensor.offline"]) == 5.5
    assert pollen_level(hass, "sensor.birke") == 3.0  # legacy single entity
    assert pollen_level(hass, ["sensor.offline"]) == 0.0
    assert pollen_level(hass, None) == 0.0
    flow = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    assert 'selector.EntitySelectorConfig(domain="sensor", multiple=True)' in flow[flow.index("def _outdoor_schema"):flow.index("def _available_room_goals")]
