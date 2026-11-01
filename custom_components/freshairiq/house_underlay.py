"""House map: the floor plan template (underlay) – validation only (pure).

A user may upload a picture of their floor plan (architect plan, estate agent
plan, scan or photo) as a tracing template for the house map editor. The image
is stored locally in Home Assistant, next to the layout, and is never part of
diagnostics or uploads. The editor downscales it before sending; the server
accepts only real PNG/JPEG/WebP data (checked by signature, not by the stated
type) up to ``MAX_DATA_CHARS`` of base64.

Per floor one template: ``{floor_id, mime, data, width, height,
scale_m_per_px, calibration, walls, close_px, opacity}``. ``calibration`` is the
measured reference (two image points and their real distance); ``walls`` are
extra separator lines (image pixels) the user drew to close open passages for
the room detection.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

import base64
import binascii
import math
from typing import Any

MAX_DATA_CHARS = 3_000_000  # base64 of about 2.2 MB; the editor sends a downscaled JPEG well below this
MAX_SIDE_PX = 4000
MAX_WALLS = 200
SIGNATURES = {
    "image/png": lambda raw: raw.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda raw: raw.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda raw: raw[:4] == b"RIFF" and raw[8:12] == b"WEBP",
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _point(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    x, y = _finite(value[0]), _finite(value[1])
    return [x, y] if x is not None and y is not None else None


def validate(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """A cleaned template, or ``(None, error_code)``."""
    if not isinstance(raw, dict):
        return None, "E_UNDERLAY_SCHEMA"
    mime, data = raw.get("mime"), raw.get("data")
    if mime not in SIGNATURES or not isinstance(data, str) or not data:
        return None, "E_UNDERLAY_TYPE"
    if len(data) > MAX_DATA_CHARS:
        return None, "E_UNDERLAY_TOO_LARGE"
    try:
        decoded = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        return None, "E_UNDERLAY_DATA"
    if not SIGNATURES[mime](decoded):
        return None, "E_UNDERLAY_DATA"
    width, height = _finite(raw.get("width")), _finite(raw.get("height"))
    if width is None or height is None or not (16 <= width <= MAX_SIDE_PX and 16 <= height <= MAX_SIDE_PX):
        return None, "E_UNDERLAY_SIZE"
    scale = _finite(raw.get("scale_m_per_px"))
    if scale is not None and not 0 < scale < 1:
        return None, "E_UNDERLAY_SCALE"
    calibration = raw.get("calibration")
    clean_cal = None
    if isinstance(calibration, dict):
        a, b, meters = _point(calibration.get("a")), _point(calibration.get("b")), _finite(calibration.get("meters"))
        if a is None or b is None or meters is None or meters <= 0 or math.dist(a, b) < 2:
            return None, "E_UNDERLAY_CALIBRATION"
        clean_cal = {"a": a, "b": b, "meters": meters}
    walls_raw = raw.get("walls") if isinstance(raw.get("walls"), list) else []
    if len(walls_raw) > MAX_WALLS:
        return None, "E_UNDERLAY_WALLS"
    walls = []
    for wall in walls_raw:
        values = [_finite(v) for v in wall] if isinstance(wall, (list, tuple)) and len(wall) == 4 else [None]
        if any(v is None for v in values):
            return None, "E_UNDERLAY_WALLS"
        walls.append(values)
    close_px = int(_finite(raw.get("close_px")) or 0)
    opacity = _finite(raw.get("opacity"))
    return {
        "floor_id": str(raw.get("floor_id") or "")[:120],
        "mime": mime, "data": data, "width": int(width), "height": int(height),
        "scale_m_per_px": scale, "calibration": clean_cal, "walls": walls,
        "close_px": min(max(close_px, 0), 8),
        "opacity": min(max(opacity, 0.1), 1.0) if opacity is not None else 0.55,
    }, None


def summary(underlays: dict[str, Any]) -> dict[str, Any]:
    """Which floors have a template (without the image data)."""
    return {floor: {"width": u.get("width"), "height": u.get("height"), "calibrated": u.get("scale_m_per_px") is not None}
            for floor, u in underlays.items() if isinstance(u, dict)}
