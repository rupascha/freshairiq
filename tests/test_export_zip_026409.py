"""0.26.4.9: the diagnostic export can be downloaded as ZIP – same JSON, much smaller."""
from __future__ import annotations

from datetime import datetime
import io
import json
import zipfile

from custom_components.freshairiq.export_zip import export_filename, zip_json_document
from tests.frontend_source import CARD_FILE

CARD = CARD_FILE.read_text(encoding="utf-8")


def test_zip_contains_the_unchanged_export():
    doc = {"records": [{"reason": "active_sample", "rooms": [{"key": f"r{i}", "humidity": 60 + i % 7, "voc_available": False} for i in range(6)], "n": n} for n in range(3000)], "text": "Küche ±0,5 °C"}
    data = zip_json_document(doc, "FreshAirIQ-diagnostics-x")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == ["FreshAirIQ-diagnostics-x.json"]
        assert json.loads(archive.read("FreshAirIQ-diagnostics-x.json")) == doc
    assert len(data) * 8 < len(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode())


def test_filenames():
    assert export_filename(datetime(2026, 10, 10, 9, 5, 7)) == "FreshAirIQ-diagnostics-2026-10-10T09-05-07"
    assert export_filename(None) == "FreshAirIQ-diagnostics-export"


def test_view_and_card_use_the_zip_export():
    from pathlib import Path

    view = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert 'if str(request.query.get("format", "")).lower() == "zip":' in view
    assert "await hass.async_add_executor_job(zip_json_document, exported, basename)" in view
    assert 'this._hass.callApiRaw("GET", "freshairiq/diagnostics?format=zip")' in CARD
    assert "JSON.stringify(payload, null, 2)" not in CARD
