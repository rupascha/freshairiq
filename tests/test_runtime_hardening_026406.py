"""0.26.4.6 runtime hardening: weather timeout, coalesced persistence, hot paths."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import time

from tests.test_storage_hardening_024100 import _load_storage
from tests.test_weather_future_024100 import _Hass as _WeatherHass, _State, _load_module as _load_weather


# --------------------------------------------------------------------------- weather


class _HangingServices:
    def __init__(self):
        self.calls = 0

    async def async_call(self, *args, **kwargs):
        self.calls += 1
        await asyncio.sleep(3600)


def test_hanging_weather_provider_times_out_and_uses_state_fallback():
    wf = _load_weather()
    wf.FORECAST_REQUEST_TIMEOUT_SECONDS = 0.05
    state = _State({"forecast": [{"datetime": "2026-09-14T09:00:00+00:00", "temperature": 11, "humidity": 70}]})
    hass = _WeatherHass(state=state)
    hass.services = _HangingServices()

    started = time.monotonic()
    rows = asyncio.run(wf.async_hourly_forecast(hass, "weather.home"))

    assert time.monotonic() - started < 2.0
    assert hass.services.calls == 1
    assert len(rows) == 1 and rows[0]["humidity"] == 70.0


def test_weather_timeout_constant_is_bounded():
    wf = _load_weather()
    assert 1.0 <= wf.FORECAST_REQUEST_TIMEOUT_SECONDS <= 30.0


# --------------------------------------------------------------------------- persistence


def _store_with_delay_support():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    module, Store = _load_storage(now)
    Store.delayed = []

    def async_delay_save(self, data_func, delay=0):
        Store.delayed.append((data_func, delay))

    Store.async_delay_save = async_delay_save
    store = module.LearningStore(object(), "entry")
    return module, Store, store


def test_routine_changes_are_coalesced_instead_of_rewriting_the_file():
    module, Store, store = _store_with_delay_support()
    backend = Store.instances[-1]

    async def run():
        for _ in range(5):
            await store.async_save_deferred()

    asyncio.run(run())
    assert backend.writes == []
    assert len(Store.delayed) == 5
    assert all(delay == module.SAVE_DEBOUNCE_SECONDS for _func, delay in Store.delayed)

    # Home Assistant evaluates the callback when the delayed write happens.
    data_func = Store.delayed[-1][0]
    assert data_func() is store.data
    assert store._save_pending_since is None


def test_coalescing_never_defers_beyond_the_hard_limit(monkeypatch):
    module, Store, store = _store_with_delay_support()
    backend = Store.instances[-1]
    clock = {"t": 1000.0}
    monkeypatch.setattr(module, "monotonic", lambda: clock["t"])

    async def run():
        await store.async_save_deferred()  # first pending change
        clock["t"] += module.SAVE_MAX_DEFER_SECONDS - 1
        await store.async_save_deferred()  # still within limit
        assert backend.writes == []
        clock["t"] += 2
        await store.async_save_deferred()  # limit exceeded -> immediate write

    asyncio.run(run())
    assert backend.writes == [store.data]
    assert store._save_pending_since is None


def test_immediate_save_resets_pending_window():
    module, Store, store = _store_with_delay_support()

    async def run():
        await store.async_save_deferred()
        assert store._save_pending_since is not None
        await store.async_save()

    asyncio.run(run())
    assert store._save_pending_since is None
    assert 0 < module.SAVE_DEBOUNCE_SECONDS < module.SAVE_MAX_DEFER_SECONDS <= 300


def test_coordinator_persists_critical_events_immediately():
    source = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    block = source[source.index("        if changed:\n            # Completed sessions"):]
    block = block[: block.index("self.runtime_health.observe_metric(\"coordinator_phase_persistence_ms\"")]
    assert "if completed_sessions or notification_changed:" in block
    assert "await self.store.async_save()" in block
    assert "await self.store.async_save_deferred()" in block


# --------------------------------------------------------------------------- store.room()


def test_room_access_keeps_valid_opening_learning_object():
    _module, _Store, store = _store_with_delay_support()
    first = store.room("bad")["opening_learning"]
    first["open"]["rate"] = 0.05
    second = store.room("bad")["opening_learning"]
    assert second is first
    assert second["open"]["rate"] == 0.05


def test_room_access_still_repairs_corrupt_or_drifted_opening_learning():
    _module, _Store, store = _store_with_delay_support()
    room = store.room("living")
    room["opening_learning"]["open"]["rate"] = float("nan")
    room["opening_learning"]["tilted"]["samples"] = 2.0  # float drift must normalise to int
    repaired = store.room("living")["opening_learning"]
    assert repaired["open"]["rate"] == 0.03
    assert repaired["tilted"]["samples"] == 2 and type(repaired["tilted"]["samples"]) is int

    store.data["rooms"]["broken"] = "not-a-room"
    assert store.room("broken")["learning_rate"] == 0.03

    partial = {"learning_rate": 0.04}
    store.data["rooms"]["partial"] = partial
    restored = store.room("partial")
    assert restored is partial
    assert restored["learning_rate"] == 0.04
    assert restored["three_state_contacts"] == []


def test_strict_equality_distinguishes_numeric_types():
    module, _Store, _store = _store_with_delay_support()
    assert module._strictly_equal({"a": 1}, {"a": 1})
    assert not module._strictly_equal({"a": 1}, {"a": 1.0})
    assert not module._strictly_equal({"a": 1}, {"b": 1})
    assert not module._strictly_equal({"a": True}, {"a": 1})


# --------------------------------------------------------------------------- routine projection


def _reference_project_generation_ml(rooms, start, minutes, *, fallback_rates=None):
    """Verbatim pre-0.26.4.6 algorithm used as the bit-identity oracle."""
    from custom_components.freshairiq.routines import _clamp, expected_source_rate
    from custom_components.freshairiq.seasonality import seasonal_adjust_rate

    minutes = _clamp(minutes, 0.0, 720.0)
    if minutes <= 0 or not rooms:
        return 0.0, 0.0
    fallback_rates = fallback_rates or {}
    total = 0.0
    weighted_maturity = 0.0
    steps = max(1, int((minutes + 14.999) // 15))
    step_min = minutes / steps
    for idx in range(steps):
        at = start + timedelta(minutes=step_min * (idx + 0.5))
        for room in rooms:
            key = str(room.get("key") or "")
            learned, samples = expected_source_rate(room, at)
            fallback = float(fallback_rates.get(key, room.get("forecast_source_rate_ml_min", 0.0) or 0.0))
            if learned is not None and samples >= 3:
                weight = min(samples / 12.0, 1.0)
                rate = learned * weight + fallback * (1.0 - weight)
                weighted_maturity += weight
            else:
                rate = fallback
            rate, seasonal = seasonal_adjust_rate(room, at, rate)
            weighted_maturity += min(float(seasonal.get("maturity", 0.0)) / 100.0, 1.0) * 0.15
            total += max(rate, 0.0) * step_min
    denom = steps * len(rooms)
    return round(total, 1), round(min((weighted_maturity / max(denom, 1)) / 1.15, 1.0) * 100.0, 1)


def _random_room(rng: random.Random, key: str, now: datetime) -> dict:
    from custom_components.freshairiq.routines import learn_source_pattern
    from custom_components.freshairiq.seasonality import learn_seasonal_source

    room = {"key": key, "forecast_source_rate_ml_min": rng.choice([None, 0.0, rng.uniform(-1, 6)])}
    for i in range(rng.randint(0, 300)):
        when = now - timedelta(days=rng.choice([rng.randint(0, 20), rng.randint(0, 400)]), minutes=rng.randint(0, 1440))
        rate = rng.uniform(-3, 20)
        learn_source_pattern(room, when, rate, minimum_interval_min=0)
        if i % 3 == 0:
            learn_seasonal_source(room, when, rate)
    return room


def test_optimised_routine_projection_is_bit_identical_to_reference():
    from custom_components.freshairiq.routines import project_generation_ml

    rng = random.Random(26406)
    now = datetime(2026, 11, 30, 21, 40)
    for case in range(60):
        rooms = [_random_room(rng, f"r{i}", now) for i in range(rng.randint(1, 5))]
        fallback = {f"r{i}": rng.uniform(0, 4) for i in range(5) if rng.random() < 0.5}
        minutes = rng.choice([0, 5, 14.5, 30, 95, 240, 480, 720, 900])
        expected = _reference_project_generation_ml([dict(r) for r in rooms], now, minutes, fallback_rates=fallback)
        actual = project_generation_ml(rooms, now, minutes, fallback_rates=fallback)
        assert actual == expected, case


def test_projection_fills_defaults_for_empty_rooms():
    from custom_components.freshairiq.routines import project_generation_ml

    room = {"key": "fresh"}
    assert project_generation_ml([room], datetime(2026, 1, 5, 7, 0), 60, fallback_rates={"fresh": 1.5}) == (90.0, 0.0)
    assert "routine_source_buckets" in room and "seasonal_source_profiles" in room
    assert project_generation_ml([], datetime(2026, 1, 5, 7, 0), 60) == (0.0, 0.0)


# --------------------------------------------------------------------------- diagnostics


def test_hourly_cleanup_does_not_reparse_the_active_day_file(tmp_path: Path):
    from tests.test_diagnostics import FreshAirIQDiagnosticsRecorder, _Hass

    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.26.4.6")
    recorder.directory.mkdir(parents=True)
    now = datetime(2026, 9, 30, 12, 0)
    today = recorder.directory / "2026-09-30.jsonl"
    yesterday = recorder.directory / "2026-09-29.jsonl"
    today.write_text(json.dumps({"timestamp": "2026-09-30T11:00:00"}) + "\n", encoding="utf-8")
    yesterday.write_text(json.dumps({"timestamp": "2026-09-29T11:00:00"}) + "\n", encoding="utf-8")

    compacted: list[str] = []
    original = recorder._compact_legacy_file
    recorder._compact_legacy_file = lambda path: (compacted.append(path.name), original(path))[-1]
    recorder._cleanup_files(now)

    assert compacted == ["2026-09-29.jsonl"]
    assert today.exists() and yesterday.exists()


# --------------------------------------------------------------------------- removed rooms


def test_learning_data_of_removed_rooms_ages_out_after_grace_period():
    module, _Store, store = _store_with_delay_support()
    store.room("kitchen")["learning_samples"] = 7
    store.room("old_room")["learning_samples"] = 9
    store.data["rooms"]["corrupt"] = "not-a-room"
    day0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Removal is only marked first; corrupt entries are dropped right away.
    assert store.prune_removed_rooms({"kitchen"}, day0) is True
    assert set(store.data["rooms"]) == {"kitchen", "old_room"}
    assert store.data["rooms"]["old_room"][module.REMOVED_ROOM_MARKER] == day0.isoformat()
    assert store.prune_removed_rooms({"kitchen"}, day0 + timedelta(days=5)) is False

    # Re-added within the grace period: learning is kept and the mark removed.
    assert store.prune_removed_rooms({"kitchen", "old_room"}, day0 + timedelta(days=10)) is True
    assert module.REMOVED_ROOM_MARKER not in store.data["rooms"]["old_room"]
    assert store.data["rooms"]["old_room"]["learning_samples"] == 9

    # Removed again and never re-added: deleted after the grace period.
    store.prune_removed_rooms({"kitchen"}, day0 + timedelta(days=11))
    naive_mark = (day0 + timedelta(days=11)).replace(tzinfo=None).isoformat()
    store.data["rooms"]["old_room"][module.REMOVED_ROOM_MARKER] = naive_mark
    later = day0 + timedelta(days=11 + module.REMOVED_ROOM_GRACE_DAYS)
    assert store.prune_removed_rooms({"kitchen"}, later) is True
    assert set(store.data["rooms"]) == {"kitchen"}
    assert store.data["rooms"]["kitchen"]["learning_samples"] == 7

    store.data["rooms"] = "broken"
    assert store.prune_removed_rooms(set(), later) is False


def test_setup_prunes_removed_rooms_before_the_coordinator_starts():
    source = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/__init__.py").read_text(encoding="utf-8")
    setup = source[source.index("async def async_setup_entry"):source.index("async def async_unload_entry")]
    assert setup.index("await store.async_load()") < setup.index("store.prune_removed_rooms(") < setup.index("FreshAirIQCoordinator(hass, entry, store)")
