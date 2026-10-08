"""Privacy-safe signature of an exception raised inside a FreshAirIQ setup flow.

Pure module (no Home Assistant imports). A signature contains the exception type
and the FreshAirIQ code locations it passed through - never the exception message,
form input, entity IDs or names. That is enough to find bugs like GitHub #12
(``NameError`` in ``_single_contact_reference_schema``) from the Hub.
"""
from __future__ import annotations

import hashlib
from pathlib import PurePath
from types import TracebackType
from typing import Any

PACKAGE_DIR = "freshairiq"
MAX_FRAMES = 4


def flow_error_signature(
    error: BaseException, tb: TracebackType | None, *, flow: str, step: str
) -> dict[str, Any]:
    """Return {flow, step, error_type, locations, code, fingerprint} for one exception."""
    locations: list[str] = []
    frame = tb
    while frame is not None:
        code = frame.tb_frame.f_code
        path = PurePath(code.co_filename)
        if PACKAGE_DIR in path.parts:
            locations.append(f"{path.stem}:{frame.tb_lineno} {code.co_name}")  # no ".py": diagnostics redact dotted names
        frame = frame.tb_next
    locations = locations[-MAX_FRAMES:]
    error_type = type(error).__name__[:80]
    flow_name = str(flow)[:40]
    step_name = str(step)[:80]
    raw = "|".join([flow_name, step_name, error_type, *locations])
    return {
        "flow": flow_name,
        "step": step_name,
        "error_type": error_type,
        "locations": locations,
        "code": "FAIQ-CONFIG-FLOW-001",
        "fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24],
    }


def flow_error_message(signature: dict[str, Any]) -> str:
    """One-line technical message for the Hub's client-error list."""
    where = " <- ".join(reversed(list(signature.get("locations") or []))) or "unknown location"
    return f"{signature.get('error_type')} in {signature.get('flow')}.{signature.get('step')} at {where}"[:2000]
