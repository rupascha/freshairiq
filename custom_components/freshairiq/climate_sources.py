"""Room climate source aggregation with strict single-sensor compatibility."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, median
from typing import Any, Callable


@dataclass(frozen=True)
class AggregatedClimateSource:
    """Aggregated room-climate reading and conservative freshness metadata."""
    value: float | None
    configured: int
    available: int
    oldest_reported: datetime | None
    newest_reported: datetime | None


def entity_ids(value: Any) -> list[str]:
    """Return configured entity IDs while preserving legacy scalar configs."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return list(dict.fromkeys(str(item) for item in value if item))
    return []


def aggregate_states(hass: Any, configured: Any, *, finite: Callable[[Any], float | None], strategy: str = "mean") -> AggregatedClimateSource:
    """Aggregate all currently valid sources; one valid source is unchanged exactly.

    Invalid/unavailable secondary sensors do not take a healthy room offline. The
    oldest contributing report timestamp is exposed so freshness checks remain
    conservative when several sensors participate in one room value.
    """
    ids = entity_ids(configured)
    values: list[float] = []
    stamps: list[datetime] = []
    for entity_id in ids:
        state = hass.states.get(entity_id)
        if state is None or str(getattr(state, "state", "")).lower() in {"unknown", "unavailable", "none", ""}:
            continue
        value = finite(getattr(state, "state", None))
        if value is None:
            continue
        values.append(value)
        stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
        if stamp is not None:
            stamps.append(stamp)
    return AggregatedClimateSource(
        value=(None if not values else values[0] if len(values) == 1 else min(values) if strategy == "min" else max(values) if strategy == "max" else median(values) if strategy == "median" else fmean(values)),
        configured=len(ids),
        available=len(values),
        oldest_reported=min(stamps) if stamps else None,
        newest_reported=max(stamps) if stamps else None,
    )


def logical_climate_sensor_groups(temperature_configured: Any, humidity_configured: Any) -> list[tuple[str | None, str | None]]:
    """Pair room temperature/humidity entities into logical climate sensors.

    Multi-sensor UI selections are kept in selection order. A logical sensor may
    expose both temperature and humidity or only one measurement. Legacy scalar
    configs therefore remain exactly one logical sensor pair.
    """
    temperatures = entity_ids(temperature_configured)
    humidities = entity_ids(humidity_configured)
    size = max(len(temperatures), len(humidities))
    return [
        (
            temperatures[index] if index < len(temperatures) else None,
            humidities[index] if index < len(humidities) else None,
        )
        for index in range(size)
    ]


def climate_report_snapshot(hass: Any, temperature_configured: Any, humidity_configured: Any) -> dict[str, dict[str, Any]]:
    """Return privacy-local report clocks/availability per logical room sensor."""
    result: dict[str, dict[str, Any]] = {}
    for index, (temperature_id, humidity_id) in enumerate(logical_climate_sensor_groups(temperature_configured, humidity_configured)):
        reports: dict[str, str | None] = {}
        available = False
        for kind, entity_id in (("temperature", temperature_id), ("humidity", humidity_id)):
            if not entity_id:
                continue
            state = hass.states.get(entity_id)
            raw = str(getattr(state, "state", "")).lower() if state is not None else ""
            valid = state is not None and raw not in {"unknown", "unavailable", "none", ""}
            available = available or valid
            stamp = (getattr(state, "last_reported", None) or getattr(state, "last_updated", None)) if state is not None else None
            reports[kind] = stamp.isoformat() if stamp is not None else None
        result[str(index)] = {"available": available, "reports": reports}
    return result


def advance_climate_report_activity(previous: dict[str, Any] | None, counts: dict[str, Any] | None,
                                    current: dict[str, dict[str, Any]], *, window_start: datetime,
                                    window_end: datetime | None = None) -> tuple[dict[str, Any], dict[str, int], int]:
    """Advance per-logical-sensor report evidence and return the room gate.

    At least one currently available logical climate sensor must contribute two
    fresh reports during the ventilation. The two reports may be 2x temperature,
    2x humidity, or 1x each. Other sensors participate in the session measurement
    as soon as they have contributed one fresh report. Sensors with no in-session
    activity and unavailable redundant sensors never block a healthy source.
    """
    previous = dict(previous or {})
    out_counts = {str(k): max(int(v), 0) for k, v in dict(counts or {}).items()}
    next_previous: dict[str, Any] = {}
    eligible_counts: list[int] = []
    for key, row in current.items():
        old_reports = dict((previous.get(key) or {}).get("reports") or {})
        reports = dict(row.get("reports") or {})
        for kind, stamp in reports.items():
            old = old_reports.get(kind)
            if stamp and stamp != old:
                try:
                    report_at = datetime.fromisoformat(stamp)
                    inside = report_at > window_start and (window_end is None or report_at <= window_end)
                except (TypeError, ValueError):
                    inside = False
                if inside:
                    out_counts[key] = min(out_counts.get(key, 0) + 1, 99)
        next_previous[key] = {"reports": reports}
        if bool(row.get("available")):
            eligible_counts.append(out_counts.get(key, 0))
    # No available climate sensor is never evidence. Otherwise the strongest
    # proven active source opens the established 0/1/2 room gate.
    fresh = min(max(eligible_counts), 2) if eligible_counts else 0
    return next_previous, out_counts, fresh


def participating_climate_entities(temperature_configured: Any, humidity_configured: Any,
                                   snapshot: dict[str, dict[str, Any]], counts: dict[str, Any],
                                   *, min_reports: int = 1) -> tuple[list[str], list[str]]:
    """Return session-qualified climate entities without changing live aggregation.

    A logical sensor joins the ventilation measurement after at least one fresh
    in-session report. This filter is deliberately session-only: normal live room
    values continue to use every currently valid configured source.
    """
    temperatures: list[str] = []
    humidities: list[str] = []
    for index, (temperature_id, humidity_id) in enumerate(logical_climate_sensor_groups(temperature_configured, humidity_configured)):
        key = str(index)
        if not bool((snapshot.get(key) or {}).get("available")):
            continue
        try:
            report_count = max(int((counts or {}).get(key, 0)), 0)
        except (TypeError, ValueError):
            report_count = 0
        if report_count < min_reports:
            continue
        if temperature_id:
            temperatures.append(temperature_id)
        if humidity_id:
            humidities.append(humidity_id)
    return temperatures, humidities
