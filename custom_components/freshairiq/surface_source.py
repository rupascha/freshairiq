"""Surface humidity from Home Assistant's Mold Indicator helper (v0.26.6.1, issue #21).

FreshAirIQ estimates the relative humidity at the coldest surface of a room from
an assumed surface temperature (``model.surface_relative_humidity``). A room may
instead name a Mold Indicator helper (integration ``mold_indicator``) that knows
its own calibrated cold spot – a roof window, a thermal bridge. Only a plain
percentage from 0 to 100 of such a helper is taken; anything else falls back to
the internal estimate. Either value stays an *estimate*, never a measurement.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

MOLD_INDICATOR_PLATFORM = "mold_indicator"
SOURCE_HELPER = "ha_mold_indicator"
SOURCE_INTERNAL = "internal_estimate"


def helper_reading(state: Any, unit: Any, platform: Any) -> tuple[float | None, str]:
    """(value, "ok") for a usable helper reading, else (None, reason).

    ``platform`` is the entity registry's integration of the entity (None when the entity is not registered, e.g. a
    YAML helper without unique id – then only value and unit can be checked)."""
    if platform is not None and platform != MOLD_INDICATOR_PLATFORM:
        return None, "not_mold_indicator"
    if state is None:
        return None, "missing"
    if str(state) in ("unknown", "unavailable", ""):
        return None, "unavailable"
    if unit != "%":
        return None, "wrong_unit"
    try:
        value = float(state)
    except (TypeError, ValueError):
        return None, "invalid"
    if not isfinite(value):
        return None, "invalid"
    if not 0.0 <= value <= 100.0:
        return None, "out_of_range"
    return value, "ok"


def source_fields(entity: str, value: float | None, reason: str) -> dict[str, Any]:
    """What the room publishes about its surface-humidity source (only when a helper is configured)."""
    fields: dict[str, Any] = {"surface_rh_source": SOURCE_HELPER if value is not None else SOURCE_INTERNAL, "surface_rh_source_entity": entity}
    if value is None:
        fields["surface_rh_source_issue"] = reason
    return fields
