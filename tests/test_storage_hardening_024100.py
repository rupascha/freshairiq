from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import sys
import types

import pytest


def _install_homeassistant_stubs(now: datetime):
    ha = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    core = types.ModuleType("homeassistant.core")
    class HomeAssistant:  # pragma: no cover - type marker only
        pass
    core.HomeAssistant = HomeAssistant
    sys.modules["homeassistant.core"] = core

    helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    storage_mod = types.ModuleType("homeassistant.helpers.storage")

    class Store:
        saved_payload = None
        legacy_payload = None
        instances = []

        def __init__(self, hass, version, key):
            self.hass = hass
            self.version = version
            self.key = key
            self.writes = []
            Store.instances.append(self)

        async def async_load(self):
            if self.key.startswith("ventilation_assistant.learning."):
                return Store.legacy_payload
            return Store.saved_payload

        async def async_save(self, data):
            self.writes.append(data)

    storage_mod.Store = Store
    sys.modules["homeassistant.helpers.storage"] = storage_mod

    util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.now = lambda: now
    dt_mod.parse_datetime = lambda value: datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    dt_mod.as_local = lambda value: value
    sys.modules["homeassistant.util.dt"] = dt_mod
    util.dt = dt_mod
    return Store


def _load_storage(now: datetime):
    Store = _install_homeassistant_stubs(now)
    sys.modules.pop("custom_components.freshairiq.storage", None)
    module = importlib.import_module("custom_components.freshairiq.storage")
    return module, Store


def test_prune_discards_corrupt_dates_rows_and_old_history():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    recent = (now.date() - timedelta(days=20)).isoformat()
    old = (now.date() - timedelta(days=731)).isoformat()
    store.data["history"] = {recent: {"sessions": 1}, old: {"sessions": 9}, "broken": {"sessions": 99}, now.date().isoformat(): "bad-row"}
    store.data["rooms"] = {"living": {**storage._room_defaults(), "history": {recent: {"sessions": 1}, "not-a-date": {}}}, "bad-room": "corrupt"}

    store.prune(730)

    assert store.data["history"] == {recent: {"sessions": 1}}
    assert store.data["rooms"]["living"]["history"] == {recent: {"sessions": 1}}
    assert isinstance(store.data["rooms"]["bad-room"], dict)


def test_record_session_rejects_nan_inf_and_keeps_aggregate_history_long_term():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    keep_day = (now.date() - timedelta(days=365)).isoformat()
    store.data["history"][keep_day] = {"removed_ml": 10, "sessions": 1}

    store.record_session(now, float("nan"), float("inf"), -0.8, float("nan"), float("inf"), "living")

    today = store.data["history"][now.date().isoformat()]
    assert today["removed_ml"] == 0.0
    assert today["ventilation_minutes"] == 0.0
    assert today["energy_kwh"] == 0.0
    assert today["cost"] == 0.0
    assert today["temp_loss_sum_c"] == -0.8
    assert keep_day in store.data["history"]


def test_temperature_recording_drops_corrupt_points_instead_of_crashing():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    store.data["temperature_points"] = [{"time": "broken", "temperature_c": 99}, "bad"]
    store.room("living")["temperature_points"] = [{"time": "broken"}, None]

    assert store.record_temperature_point(now, 21.25) is True
    assert store.record_room_temperature_point("living", now, 20.75) is True

    assert store.data["temperature_points"] == [{"time": "2026-09-14T08:00", "temperature_c": 21.25}]
    assert store.room("living")["temperature_points"] == [{"time": "2026-09-14T08:00", "temperature_c": 20.75}]


@pytest.mark.asyncio
async def test_load_repairs_corrupt_persistence_and_legacy_migrates():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, Store = _load_storage(now)
    Store.saved_payload = {"rooms": {"living": {"learning_rate": "nan", "history": []}}, "history": []}
    store = storage.LearningStore(object(), "current")
    await store.async_load()
    assert store.data["history"] == {}
    assert store.room("living")["learning_rate"] == 0.03
    assert isinstance(store.room("living")["history"], dict)

    Store.saved_payload = None
    Store.legacy_payload = {"rooms": {"old": {"learning_samples": 12}}}
    migrated = storage.LearningStore(object(), "new", legacy_entry_id="legacy")
    await migrated.async_load()
    assert migrated.room("old")["learning_samples"] == 12
    assert migrated._store.writes, "legacy migration must persist into the current store"

@pytest.mark.asyncio
async def test_reset_learning_preserves_live_session_and_statistics():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    room = store.room("living")
    room.update({
        "learning_samples": 50,
        "history": {now.date().isoformat(): {"sessions": 2}},
        "temperature_points": [{"time": "2026-09-14T07:00", "temperature_c": 21}],
        "session_active": True,
        "session_started": "2026-09-14T07:55:00+00:00",
        "session_start_ah": 10.1,
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": 120,
    })
    store.data.update({"night_model_ml_h": 12, "night_model_samples": 8, "house_strategy_samples": 20})

    await store.async_reset_learning()

    reset = store.room("living")
    assert reset["learning_samples"] == 0
    assert reset["history"]
    assert reset["temperature_points"]
    assert reset["session_active"] is True
    assert reset["session_start_ah"] == 10.1
    assert reset["session_predicted_removed_ml"] == 120
    assert store.data["night_model_ml_h"] is None
    assert store.data["night_model_samples"] == 0
    assert store.data["house_strategy_samples"] == 0
    assert store._store.writes


@pytest.mark.asyncio
async def test_reset_statistics_preserves_learning_and_live_state():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    room = store.room("living")
    room.update({"learning_samples": 15, "session_active": True, "history": {"x": {}}, "temperature_points": [{"time": "x"}]})
    store.data.update({"history": {"x": {}}, "temperature_points": [{"time": "x"}], "water_daily": {"x": {}}, "last_ventilation": {"x": 1}, "forecast_validation_history": [{"x": 1}]})

    await store.async_reset_statistics()

    assert store.data["history"] == {}
    assert store.data["temperature_points"] == []
    assert store.data["water_daily"] == {}
    assert store.data["last_ventilation"] is None
    assert store.data["forecast_validation_history"] == []
    assert room["history"] == {}
    assert room["temperature_points"] == []
    assert room["learning_samples"] == 15
    assert room["session_active"] is True


def test_water_history_is_finite_throttled_and_repairs_corrupt_rows():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    store.data["water_daily"] = []
    assert store.record_house_water(now, float("nan")) is True
    assert store.data["water_daily"][now.date().isoformat()]["mean_ml"] == 0.0
    assert store.record_house_water(now + timedelta(seconds=30), 100) is False
    assert store.record_house_water(now + timedelta(minutes=2), 100) is True
    rows = store.water_history_days(1)
    assert rows[0]["water_ml"] == 50
    assert rows[0]["samples"] == 2

    store.data["water_daily"][now.date().isoformat()] = "broken"
    rows = store.water_history_days(1)
    assert rows[0]["water_ml"] == 0
    assert rows[0]["samples"] == 0


def test_history_and_temperature_readers_ignore_corruption_and_respect_windows():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    day = now.date().isoformat()
    store.data["history"] = {day: {"sessions": 2, "removed_ml": 50}}
    store.data["temperature_points"] = [
        {"time": "broken", "temperature_c": 99},
        {"time": "2026-09-14T08:00", "temperature_c": 21},
        {},
    ]
    room = store.room("living")
    room["history"] = {day: {"sessions": 1}}
    room["temperature_points"] = list(store.data["temperature_points"])

    assert store.history_days(1)[0]["sessions"] == 2
    assert store.room_history_days("living", 1)[0]["sessions"] == 1
    assert store.temperature_points(1) == [{"time": "2026-09-14T08:00", "temperature_c": 21}]
    assert store.room_temperature_points("living", 1) == [{"time": "2026-09-14T08:00", "temperature_c": 21}]


def test_history_readers_repair_corrupt_containers_and_rows():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    store.data["history"] = ["bad"]
    room = store.room("living")
    room["history"] = {now.date().isoformat(): "bad-row"}

    house_rows = store.history_days("broken")
    room_rows = store.room_history_days("living", "broken")

    assert len(house_rows) == 14
    assert store.data["history"] == {}
    assert len(room_rows) == 14
    assert room_rows[-1]["sessions"] == 0


def test_history_readers_clamp_requested_retention_window():
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    storage, _ = _load_storage(now)
    store = storage.LearningStore(object(), "abc")
    assert len(store.history_days(0)) == 1
    assert len(store.room_history_days("living", 999999)) == storage.AGGREGATE_HISTORY_DAYS
