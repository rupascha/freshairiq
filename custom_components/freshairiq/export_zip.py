"""Diagnostic export as ZIP (0.26.4.9).

A diagnostic export is tens of MiB of JSON; packed it is about 1/15 of that.
The ZIP holds exactly one JSON file whose content is the unchanged export –
nothing is dropped or rounded. Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from typing import Any


def export_filename(now: Any) -> str:
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S") if hasattr(now, "strftime") else "export"
    return f"FreshAirIQ-diagnostics-{stamp}"


def zip_json_document(document: Any, basename: str) -> bytes:
    """Compact JSON of ``document`` in a ZIP named ``<basename>.json``."""
    body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    info = zipfile.ZipInfo(f"{basename}.json", date_time=time.localtime()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(info, body, compresslevel=6)
    return buffer.getvalue()
