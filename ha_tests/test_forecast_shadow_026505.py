"""Passive shadow formula against the real coordinator (Home Assistant runtime).

A real bath airing produces the pair on the frozen start curve, the validation history and the
published comparison; a broken shadow changes nothing in decisions, learning or the session record
apart from its own field; a restart in the middle keeps the start provenance; the diagnostics
upload keeps the formula IDs and the version.
"""
from __future__ import annotations

import copy
from datetime import datetime

from custom_components.freshairiq import coordinator as coord_mod
from custom_components.freshairiq import forecast_shadow as fs
from custom_components.freshairiq.const import VERSION
from custom_components.freshairiq.diagnostic_transport import _sanitize_tree
from ha_tests.test_cov_coordinator_b import _CREATED, BERLIN, _cleanup_coordinators, _make  # noqa: F401

START = datetime(2026, 10, 7, 21, 0, tzinfo=BERLIN)


async def _airing(d, *, restart=False):
    trace = []
    for _ in range(3):
        trace.append(await d.step(60))
    trace.append(await d.step(60, binary_sensor__bad_fenster="on"))
    for i in range(12):
        if restart and i == 6:
            restarted = coord_mod.FreshAirIQCoordinator(d.hass, d.entry, d.store)
            _CREATED.append(restarted)
            d.coordinator = restarted
        trace.append(await d.step(60, sensor__bad_h=round(79.0 - 1.6 * (i + 1), 1), sensor__bad_t=round(23.4 - 0.12 * (i + 1), 2)))
    trace.append(await d.step(60, binary_sensor__bad_fenster="off"))
    for i in range(8):
        trace.append(await d.step(120, sensor__bad_h=round(60.0 + 0.5 * (i + 1), 1), sensor__bad_t=round(22.0 + 0.05 * i, 2)))
    return trace


def _without_shadow(value):
    """The record without the shadow's own field (everything else must be identical)."""
    if isinstance(value, dict):
        return {k: _without_shadow(v) for k, v in value.items() if k != "shadow_forecast"}
    if isinstance(value, list):
        return [_without_shadow(v) for v in value]
    return value


def _decisions(trace):
    return [({k: (r.get("action"), r.get("house_aligned_action"), r.get("forecast_5_min_moisture_effect_ml"), r.get("close_recommended"))
              for k, r in data["rooms"].items()},
             (data.get("intelligent_recommendation") or {}).get("kind"), data.get("forecast_validation"), data.get("learning_effectiveness"),
             data.get("forecast_backtest")) for data in trace]


def _rooms(history):
    return [room for record in history for room in record.get("room_results") or []]


async def test_a_real_airing_produces_the_pair_on_the_frozen_start(hass, freezer) -> None:
    d = await _make(hass, freezer, start=START)
    await _airing(d)
    rooms = _rooms(d.store.data["forecast_validation_history"])
    shadow = rooms[0]["shadow_forecast"]
    assert shadow["paired_valid"] is True and shadow["exclusion_reason"] is None
    assert shadow["freshairiq_version_at_start"] == VERSION and shadow["start_context_version"] == 2
    assert shadow["production_predicted_removed_ml"] == rooms[0]["predicted_removed_ml"]
    assert shadow["measured_removed_ml"] == rooms[0]["actual_removed_ml"]
    assert shadow["null_abs_error_ml"] == abs(shadow["measured_removed_ml"]) and shadow["opening_learning_quarantined"] is False
    summary = d.data["forecast_shadow_comparison"]
    assert summary["samples"] == 1 and summary["status"] == "collecting" and summary["auto_activation"] is False
    assert summary["production_mae_ml"] == shadow["production_abs_error_ml"] and summary["candidate_mae_ml"] == shadow["candidate_abs_error_ml"]
    assert summary["null_mae_ml"] == shadow["null_abs_error_ml"] and summary["quarantined_pairs"] == 0
    # audit F02: the long-term ventilation log keeps version and formula ids of the same airing
    entry = d.store.data["ventilation_log"][-1]
    assert (entry["freshairiq_version"], entry["freshairiq_version_at_start"]) == (VERSION, VERSION)
    assert (entry["production_formula_id"], entry["candidate_formula_id"]) == (fs.PRODUCTION_FORMULA_ID, fs.CANDIDATE_FORMULA_ID)
    assert (entry["formula_pair_valid"], entry["production_abs_error_ml"], entry["candidate_abs_error_ml"]) == (
        True, shadow["production_abs_error_ml"], shadow["candidate_abs_error_ml"])


async def test_a_failing_shadow_changes_no_decision_and_no_learning(hass, freezer, monkeypatch) -> None:
    normal = await _make(hass, freezer, start=START)
    normal_trace = await _airing(normal)
    normal_store = copy.deepcopy(normal.store.data)

    def boom(**_kwargs):
        raise RuntimeError("shadow down")

    monkeypatch.setattr(fs, "shadow_removed_ml", boom)
    hass.states.async_remove("binary_sensor.bad_fenster")
    broken = await _make(hass, freezer, start=START)
    broken_trace = await _airing(broken)
    for index, (got, want) in enumerate(zip(_decisions(broken_trace), _decisions(normal_trace))):
        for part, (a, b) in enumerate(zip(got, want)):
            assert _without_shadow(a) == _without_shadow(b), (index, part)
    for key in ("learning_rate", "learning_samples", "outcome_removed_factor", "forecast_observation_samples", "last_ventilation_removed_ml"):
        assert broken.mem("bad").get(key) == normal_store["rooms"]["bad"].get(key), key
    normal_room, broken_room = _rooms(normal_store["forecast_validation_history"])[0], _rooms(broken.store.data["forecast_validation_history"])[0]
    assert broken_room["shadow_forecast"]["exclusion_reason"] == "shadow_error" and broken_room["shadow_forecast"]["paired_valid"] is False
    assert {k: v for k, v in broken_room.items() if k != "shadow_forecast"} == {k: v for k, v in normal_room.items() if k != "shadow_forecast"}
    assert broken.data["forecast_shadow_comparison"]["samples"] == 0
    assert broken.data["forecast_shadow_comparison"]["excluded"] == {"shadow_error": 1}


async def test_a_restart_during_the_airing_keeps_the_start_provenance(hass, freezer) -> None:
    d = await _make(hass, freezer, start=START)
    await _airing(d, restart=True)
    shadow = _rooms(d.store.data["forecast_validation_history"])[0]["shadow_forecast"]
    # 0.26.6.0: the running version (VERSION) instead of a fixed number – the version bump changed it, not the behaviour
    assert shadow["freshairiq_version_at_start"] == VERSION and shadow["paired_valid"] is True
    assert len(_rooms(d.store.data["forecast_validation_history"])) == 1  # evaluated once


async def test_diagnostics_record_and_upload_keep_the_pair(hass, freezer) -> None:
    d = await _make(hass, freezer, start=START)
    await _airing(d)
    shadow = _rooms(d.store.data["forecast_validation_history"])[0]["shadow_forecast"]
    session = {"event_id": "bad:1", "key": "bad", "name": "Badezimmer", "shadow_forecast": shadow}
    record = d.coordinator.diagnostics._build_record(d.data, d.store.data, coord_mod.dt_util.now(), "test", [session])
    assert record["completed_sessions"][0]["shadow_forecast"] == shadow
    assert record["forecast_shadow_comparison"]["samples"] == 1 and record["freshairiq_version"] == VERSION
    clean = _sanitize_tree(record, {"bad": "room-1", "r1": "room-2", "Badezimmer": "room-1"})
    sent = clean["completed_sessions"][0]["shadow_forecast"]
    assert sent["candidate_formula_id"] == fs.CANDIDATE_FORMULA_ID and sent["production_formula_id"] == fs.PRODUCTION_FORMULA_ID
    assert sent["freshairiq_version_at_start"] == VERSION and "name" not in clean["completed_sessions"][0]
    assert clean["forecast_shadow_comparison"]["candidate_formula_ids"] == [fs.CANDIDATE_FORMULA_ID]
