"""Privacy-minimised production-incident replay contracts.

The snapshot contains only decision-relevant state classes, never Home Assistant
entity IDs, room labels or free text. Replays call the production recommendation
engine instead of duplicating its decision rules.
"""
from __future__ import annotations

from typing import Any, Mapping

from .recommendation import build_recommendation

REPLAY_SCHEMA_VERSION = 1
_ALLOWED_QUALITY = {"ok", "missing", "stale", "invalid", "unavailable", "unknown"}


def build_sensor_replay_snapshot(sensor_quality: Mapping[str, Any] | None) -> dict[str, Any] | None:
    quality = sensor_quality if isinstance(sensor_quality, Mapping) else {}
    raw_counts = quality.get("issue_quality_counts")
    issue_counts: dict[str, int] = {}
    if isinstance(raw_counts, Mapping):
        for raw_key, raw_value in raw_counts.items():
            key = str(raw_key or "unknown").strip().lower()
            if key not in _ALLOWED_QUALITY:
                key = "unknown"
            try:
                count = max(int(raw_value), 0)
            except (TypeError, ValueError, OverflowError):
                count = 0
            if count:
                issue_counts[key] = issue_counts.get(key, 0) + count
    try:
        rooms_ok = max(int(quality.get("rooms_ok", 0)), 0)
    except (TypeError, ValueError, OverflowError):
        rooms_ok = 0
    if not issue_counts and rooms_ok <= 0:
        return None
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "target": "build_recommendation",
        "rooms_ok": rooms_ok,
        "issue_quality_counts": dict(sorted(issue_counts.items())),
        "outdoor_data_quality": str(quality.get("outdoor_data_quality") or "")[:32],
    }


def replay_sensor_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Replay the minimal sensor state through the production recommendation engine."""
    source = snapshot if isinstance(snapshot, Mapping) else {}
    if source.get("schema_version") != REPLAY_SCHEMA_VERSION or source.get("target") != "build_recommendation":
        raise ValueError("unsupported replay snapshot")
    rooms: dict[str, dict[str, Any]] = {}
    try:
        ok_count = max(int(source.get("rooms_ok", 0)), 0)
    except (TypeError, ValueError, OverflowError):
        ok_count = 0
    for index in range(min(ok_count, 100)):
        rooms[f"replay-ok-{index}"] = {"key": f"replay-ok-{index}", "name": "Replay", "calculation_enabled": True, "data_quality": "ok"}
    counts = source.get("issue_quality_counts") if isinstance(source.get("issue_quality_counts"), Mapping) else {}
    offset = 0
    for raw_quality, raw_count in sorted(counts.items()):
        quality = str(raw_quality or "unknown").lower()
        if quality not in _ALLOWED_QUALITY or quality == "ok":
            quality = "unknown"
        try:
            count = max(int(raw_count), 0)
        except (TypeError, ValueError, OverflowError):
            count = 0
        for index in range(min(count, 100)):
            key = f"replay-bad-{offset}"
            rooms[key] = {"key": key, "name": "Replay", "calculation_enabled": True, "data_quality": quality}
            offset += 1
    recommendation = build_recommendation(
        rooms, {}, threshold_ml=100.0, total_potential_ml=0.0,
        recommended_duration_min=10.0,
    )
    return {
        "kind": str(recommendation.get("kind") or ""),
        "status": str(recommendation.get("status") or ""),
        "reproduces_sensor_error": recommendation.get("kind") == "sensor" and recommendation.get("status") == "sensor_error",
    }
