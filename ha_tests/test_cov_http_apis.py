"""Real-HA HTTP coverage for FreshAirIQ's authenticated dashboard views.

The views are registered on Home Assistant's real ``http`` component exactly
like ``async_setup`` does; requests go through ``hass_client`` (authenticated).
The runtime behind ``entry.runtime_data`` uses the real diagnostics recorder,
the real Hub client (Hub mocked via ``aioclient_mock``) and the real store.
"""
from __future__ import annotations

import base64
from datetime import date, timedelta
from io import BytesIO
import json
from types import SimpleNamespace
from typing import Any
import zipfile

from aiohttp import ClientError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.freshairiq import feedback_api, ventilation_log_api
from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.diagnostics import (
    FreshAirIQDiagnosticsRecorder,
    FreshAirIQDiagnosticsView,
    FreshAirIQSupportDiagnosticsView,
)
from custom_components.freshairiq.feedback_api import FreshAirIQFeedbackView
from custom_components.freshairiq.room_history_api import FreshAirIQRoomHistoryView
from custom_components.freshairiq.runtime_health import RuntimeHealthMonitor
from custom_components.freshairiq.storage import LearningStore
from custom_components.freshairiq.telemetry import FreshAirIQDiagnosticsClient
from custom_components.freshairiq.ventilation_log_api import FreshAirIQVentilationLogView

HUB = "https://hub.test"
TOKEN = "k" * 64


@pytest.fixture
async def api(hass, tmp_path, hass_client):
    hass.config.config_dir = str(tmp_path)
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.language = "de"
    assert await async_setup_component(hass, "http", {})
    for view in (FreshAirIQDiagnosticsView(), FreshAirIQSupportDiagnosticsView(), FreshAirIQFeedbackView(),
                 FreshAirIQVentilationLogView(), FreshAirIQRoomHistoryView()):
        hass.http.register_view(view)
    return await hass_client()


def _runtime(hass, entry, *, data: dict[str, Any] | None = None) -> SimpleNamespace:
    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    telemetry = FreshAirIQDiagnosticsClient(hass, entry, recorder, endpoint=HUB)
    telemetry._state = {"client_token": TOKEN, "hub_enrolled": True}
    store = LearningStore(hass, entry.entry_id)
    runtime = SimpleNamespace(diagnostics=recorder, telemetry=telemetry, store=store,
                              runtime_health=RuntimeHealthMonitor(), data=data if data is not None else {})
    entry.runtime_data = runtime
    return runtime


def _entry(hass, *, loaded: bool = True, data: dict | None = None) -> tuple[MockConfigEntry, SimpleNamespace | None]:
    entry = MockConfigEntry(domain=DOMAIN, data={"rooms": []},
                            options={"diagnostics_consent": "granted", "diagnostics_reporting_mode": "daily"})
    entry.add_to_hass(hass)
    runtime = _runtime(hass, entry, data=data) if loaded else None
    return entry, runtime


# --------------------------------------------------------------------------- feedback


async def test_feedback_unknown_entry_is_404_localised(hass, api) -> None:
    other = MockConfigEntry(domain="other_domain")
    other.add_to_hass(hass)
    for entry_id in ("missing", other.entry_id):
        response = await api.post(f"/api/freshairiq/feedback/{entry_id}", json={})
        assert response.status == 404
        assert (await response.json())["error"] == "FreshAirIQ-Konfiguration nicht gefunden."
    hass.config.language = "en"
    response = await api.post("/api/freshairiq/feedback/missing", json={})
    assert (await response.json())["error"] == "FreshAirIQ configuration not found."


async def test_feedback_success_and_hub_cooldown(hass, api, aioclient_mock) -> None:
    entry, runtime = _entry(hass)
    aioclient_mock.post(f"{HUB}/v1/feedback", status=201, json={"accepted": True, "feedback_id": "fb-9"})
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json={
        "type": "bug", "message": "Karte leer", "client_context": {"platform_family": "Android", "device_name": "x"},
    })
    assert response.status == 200
    body = await response.json()
    assert body["ok"] is True and body["feedback_id"] == "fb-9"
    assert body["cooldown_seconds"] == 900
    sent = aioclient_mock.mock_calls[-1][2]
    assert sent["client_context"] == {"platform_family": "Android"}

    # Inside the local 15-minute cooldown the view answers 429 with minutes left.
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json={"type": "bug", "message": "nochmal"})
    assert response.status == 429
    body = await response.json()
    assert body["reason"] == "cooldown"
    assert body["error"] == "Feedback ist nur alle 15 Minuten möglich. Nächstes Feedback in 15 Min."
    hass.config.language = "en-GB"
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json={"type": "bug", "message": "again"})
    assert (await response.json())["error"] == "Feedback can be sent once every 15 minutes. Next feedback in 15 min."
    assert runtime.telemetry._state["feedback_cooldown_until"]


async def test_feedback_validation_and_not_loaded_are_400(hass, api) -> None:
    entry, _runtime_ns = _entry(hass)
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json={"type": "spam", "message": "hello"})
    assert response.status == 400
    assert (await response.json())["error"] == "feedback_type_invalid"

    unloaded, _ = _entry(hass, loaded=False)
    response = await api.post(f"/api/freshairiq/feedback/{unloaded.entry_id}", json={"type": "bug", "message": "hello"})
    assert response.status == 400
    assert (await response.json())["error"] == "FreshAirIQ ist gerade nicht geladen."


async def test_feedback_hub_failure_is_502_and_reported(hass, api, aioclient_mock) -> None:
    entry, runtime = _entry(hass)
    aioclient_mock.post(f"{HUB}/v1/feedback", status=500)
    aioclient_mock.post(f"{HUB}/v1/client-errors", status=200, json={"stored": True})
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json={"type": "other", "message": "hallo hub"})
    assert response.status == 502
    body = await response.json()
    assert body["error_code"] == "FAIQ-HUB-FEEDBACK-001"
    assert body["technical_detail"] == "feedback_http_500"
    reported = [call for call in aioclient_mock.mock_calls if call[1].path == "/v1/client-errors"]
    assert reported[0][2]["code"] == "FAIQ-HUB-FEEDBACK-001"
    assert reported[0][2]["message"] == "RuntimeError: feedback_http_500"
    assert runtime.telemetry._state.get("feedback_cooldown_until") is None


async def test_feedback_unreachable_hub_never_recurses(hass, api, aioclient_mock) -> None:
    entry, runtime = _entry(hass)
    aioclient_mock.post(f"{HUB}/v1/feedback", exc=ClientError("down"))
    aioclient_mock.post(f"{HUB}/v1/client-errors", exc=ClientError("down"))
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json={"type": "bug", "message": "hallo hub"})
    assert response.status == 502
    assert (await response.json())["error"] == "Feedback konnte nicht an den Diagnose-Hub übertragen werden."
    # The failed error report itself is retained locally for a later retry.
    assert runtime.telemetry._state["client_error_queue"][0]["code"] == "FAIQ-HUB-FEEDBACK-001"


async def test_feedback_failure_without_runtime_skips_error_report(hass, api) -> None:
    entry, _ = _entry(hass, loaded=False)
    # A JSON array is not a feedback object: unexpected error, no runtime to report it.
    response = await api.post(f"/api/freshairiq/feedback/{entry.entry_id}", json=["bug"])
    assert response.status == 502
    body = await response.json()
    assert body["error_code"] == "FAIQ-HUB-FEEDBACK-001"
    assert "get" in body["technical_detail"]


def test_feedback_message_language_fallback() -> None:
    assert feedback_api._msg(SimpleNamespace(), "de", "en") == "de"
    assert feedback_api._msg(SimpleNamespace(config=SimpleNamespace(language="fr")), "de", "en") == "en"
    assert ventilation_log_api._language(SimpleNamespace(config=SimpleNamespace(language=None))) == "de"


# --------------------------------------------------------------------------- ventilation log PDF


async def test_ventilation_log_pdf_success_default_and_explicit_range(hass, api) -> None:
    today = dt_util.now().date()
    recent = dt_util.now() - timedelta(days=5)
    entry, runtime = _entry(hass)
    runtime.store.data["ventilation_log"] = [
        {"room_key": "bath", "room_name": "Bad", "started_at": recent.isoformat(),
         "ended_at": (recent + timedelta(minutes=12)).isoformat(), "duration_min": 12, "removed_ml": 40.0},
        {"room_key": "bath", "room_name": "Bad", "started_at": "2025-01-01T08:00:00+01:00",
         "ended_at": "2025-01-01T08:05:00+01:00", "duration_min": 5},
    ]
    response = await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}")
    assert response.status == 200
    body = await response.json()
    assert body["filename"] == f"FreshAirIQ-Lueftungsprotokoll-{(today - timedelta(days=30)).isoformat()}-{today.isoformat()}.pdf"
    assert body["event_count"] == 1
    assert base64.b64decode(body["pdf_base64"]).startswith(b"%PDF-")

    hass.config.language = "en"
    response = await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={"start": "2024-12-31", "end": (date(2024, 12, 31) + timedelta(days=730)).isoformat()})
    body = await response.json()
    assert body["filename"] == "FreshAirIQ-Ventilation-Log-2024-12-31-2026-12-31.pdf"
    assert body["event_count"] == 2


async def test_ventilation_log_per_day_and_as_csv(hass, api) -> None:
    """0.26.5.3 (user feedback): one row per day in the PDF, CSV per airing or per day."""
    entry, runtime = _entry(hass)
    runtime.store.data["ventilation_log"] = [
        {"room_key": "bath", "room_name": "Bad", "started_at": "2026-10-20T07:00:00+02:00", "ended_at": "2026-10-20T07:10:00+02:00",
         "duration_min": 10, "removed_ml": 120.0, "measurement_valid": True},
        {"room_key": "bed", "room_name": "Schlafzimmer", "started_at": "2026-10-20T21:00:00+02:00", "ended_at": "2026-10-20T21:08:00+02:00",
         "duration_min": 8, "removed_ml": None, "measurement_valid": False},
    ]
    window = {"start": "2026-10-19", "end": "2026-10-21"}
    body = await (await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={**window, "group": "day"})).json()
    assert body["filename"] == "FreshAirIQ-Lueftungsprotokoll-pro-Tag-2026-10-19-2026-10-21.pdf"
    pdf = base64.b64decode(body["pdf_base64"])
    assert pdf.startswith(b"%PDF-") and b"pro Tag" in pdf and b"1/2" in pdf

    body = await (await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={**window, "group": "day", "format": "csv"})).json()
    assert body["filename"] == "FreshAirIQ-Lueftungsprotokoll-pro-Tag-2026-10-19-2026-10-21.csv" and "pdf_base64" not in body
    rows = body["csv"].lstrip("\ufeff").splitlines()
    assert rows[1:] == ["2026-10-19;0;0,0;;;0;", "2026-10-20;2;18,0;9,0;120;1;Bad, Schlafzimmer", "2026-10-21;0;0,0;;;0;"]

    hass.config.language = "en"
    body = await (await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={**window, "format": "csv"})).json()
    assert body["filename"] == "FreshAirIQ-Ventilation-Log-2026-10-19-2026-10-21.csv" and body["event_count"] == 2
    lines = body["csv"].lstrip("\ufeff").splitlines()
    assert lines[0].startswith("Date,Start,End,Room,Duration (min)") and lines[1].startswith("2026-10-20,07:00,07:10,Bad,10.0,120,yes")


async def test_ventilation_log_errors(hass, api, monkeypatch) -> None:
    response = await api.get("/api/freshairiq/ventilation-log/missing")
    assert response.status == 404
    assert (await response.json())["error_code"] == "FAIQ-PDF-CONFIG-001"

    loading, _ = _entry(hass, loaded=False)
    response = await api.get(f"/api/freshairiq/ventilation-log/{loading.entry_id}")
    assert response.status == 503
    assert (await response.json())["error_code"] == "FAIQ-PDF-RUNTIME-001"

    entry, runtime = _entry(hass)
    response = await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={"start": "gestern"})
    assert response.status == 400
    assert (await response.json())["error_code"] == "FAIQ-PDF-RANGE-001"
    response = await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={"start": "2026-10-10", "end": "2026-10-01"})
    assert (await response.json())["error_code"] == "FAIQ-PDF-RANGE-002"
    response = await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}", params={"start": "2020-01-01", "end": "2026-10-01"})
    assert response.status == 400
    assert (await response.json())["error"] == "Der Zeitraum muss zwischen 1 und 731 Tagen liegen."

    def broken_pdf(*_args, **_kwargs):
        raise MemoryError("pdf too big")

    monkeypatch.setattr(ventilation_log_api, "build_ventilation_pdf", broken_pdf)
    response = await api.get(f"/api/freshairiq/ventilation-log/{entry.entry_id}")
    assert response.status == 500
    body = await response.json()
    assert body == {"error": "Lüftungsprotokoll konnte nicht erstellt werden.", "error_code": "FAIQ-PDF-BUILD-001", "error_type": "MemoryError"}
    snapshot = json.dumps(runtime.runtime_health.snapshot)
    assert "ventilation_log" in snapshot and "MemoryError" in snapshot


# --------------------------------------------------------------------------- room history


async def test_room_history_api(hass, api) -> None:
    response = await api.get("/api/freshairiq/room-history/missing")
    assert response.status == 404
    assert (await response.json())["error_code"] == "FAIQ-HISTORY-CONFIG-001"

    loading, _ = _entry(hass, loaded=False)
    response = await api.get(f"/api/freshairiq/room-history/{loading.entry_id}")
    assert response.status == 503
    assert (await response.json())["error_code"] == "FAIQ-HISTORY-RUNTIME-001"

    rooms = {
        "bath": {"temperature_history_14d": [{"t": 1}], "humidity_history_14d": [{"h": 60}], "humidity": 61},
        "kitchen": {"temperature_history_14d": [], "humidity_history_14d": None},
    }
    entry, runtime = _entry(hass, data={"rooms": rooms})
    response = await api.get(f"/api/freshairiq/room-history/{entry.entry_id}", params={"room": " bath "})
    assert await response.json() == {"api": "room_history_v1", "rooms": {"bath": {"temperature_history_14d": [{"t": 1}], "humidity_history_14d": [{"h": 60}]}}}
    response = await api.get(f"/api/freshairiq/room-history/{entry.entry_id}")
    assert set((await response.json())["rooms"]) == {"bath", "kitchen"}

    runtime.data = None  # coordinator without a first refresh yet
    response = await api.get(f"/api/freshairiq/room-history/{entry.entry_id}")
    assert await response.json() == {"api": "room_history_v1", "rooms": {}}


# --------------------------------------------------------------------------- diagnostics export / support


async def test_diagnostics_view_unavailable_without_runtime(hass, api) -> None:
    _entry(hass, loaded=False)
    response = await api.get("/api/freshairiq/diagnostics")
    assert response.status == 503
    response = await api.post("/api/freshairiq/diagnostics", json={})
    assert (await response.json())["error_code"] == "FAIQ-DIAG-RUNTIME-001"
    response = await api.post("/api/freshairiq/support-diagnostics", json={})
    assert response.status == 503


async def test_diagnostics_view_export_json_zip_and_client_registration(hass, api) -> None:
    entry, runtime = _entry(hass)
    client_id = "faiq-client-" + "a1b2c3d4e5f6"
    response = await api.post("/api/freshairiq/diagnostics", json={
        "client_id": client_id, "platform_family": "iOS", "device_class": "phone",
        "user_agent": "Mozilla/5.0 (iPhone) secret", "viewport_css_px": {"width": 390, "height": 844},
    })
    assert response.status == 200
    assert await response.json() == {"registered": True, "client_id": client_id}

    response = await api.post("/api/freshairiq/diagnostics", data="not json")
    assert response.status == 400
    assert (await response.json())["error_code"] == "FAIQ-DIAG-REQUEST-001"
    response = await api.post("/api/freshairiq/diagnostics", json=[1, 2])
    assert (await response.json())["error_code"] == "FAIQ-DIAG-REQUEST-002"

    response = await api.get("/api/freshairiq/diagnostics")
    assert response.status == 200
    exported = await response.json()
    text = json.dumps(exported)
    assert "secret" not in text
    assert client_id in text

    response = await api.get("/api/freshairiq/diagnostics", params={"format": "ZIP"})
    assert response.status == 200
    assert response.headers["Content-Type"] == "application/zip"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Disposition"].endswith('.zip"')
    archive = zipfile.ZipFile(BytesIO(await response.read()))
    names = archive.namelist()
    assert len(names) == 1 and names[0].endswith(".json")
    packed = json.loads(archive.read(names[0]))
    assert packed["format"] == exported["format"] == "FreshAirIQ diagnostic export"


async def test_support_diagnostics_view(hass, api, aioclient_mock, monkeypatch) -> None:
    entry, runtime = _entry(hass)
    response = await api.post("/api/freshairiq/support-diagnostics", data="{")
    assert (await response.json())["error_code"] == "FAIQ-SUPPORT-REQUEST-001"
    response = await api.post("/api/freshairiq/support-diagnostics", json="text")
    assert (await response.json())["error_code"] == "FAIQ-SUPPORT-REQUEST-002"
    response = await api.post("/api/freshairiq/support-diagnostics", json={"message": "x" * 5000})
    assert response.status == 400
    assert (await response.json()) == {"error": "support_message_too_long", "error_code": "FAIQ-SUPPORT-VALIDATION-001"}

    aioclient_mock.post(f"{HUB}/v1/support/diagnostics", status=503)
    aioclient_mock.post(f"{HUB}/v1/client-errors", status=500)
    response = await api.post("/api/freshairiq/support-diagnostics", json={"message": "Bitte helfen"})
    assert response.status == 502
    assert (await response.json())["detail"] == "support_diagnostics_http_503"

    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{HUB}/v1/support/diagnostics", status=202)
    aioclient_mock.post(f"{HUB}/v1/client-errors", status=200, json={})
    response = await api.post("/api/freshairiq/support-diagnostics", json={"message": "Bitte helfen"})
    assert response.status == 200
    body = await response.json()
    assert body["accepted"] is True and body["support_case_id"].startswith("support-")
    response = await api.post("/api/freshairiq/support-diagnostics", json={})
    assert response.status == 429
    assert (await response.json())["reason"] == "cooldown"

    async def raising(message):
        raise raising.error

    monkeypatch.setattr(runtime.telemetry, "async_submit_support_diagnostics", raising)
    for error, detail in (
        (TimeoutError(), "timeout"),
        (RuntimeError("hub_credential_persistence_failed"), "hub_credential_persistence_failed"),
        (RuntimeError("something private /config/x"), "RuntimeError"),
        (KeyError("secret"), "KeyError"),
    ):
        raising.error = error
        response = await api.post("/api/freshairiq/support-diagnostics", json={"message": "x"})
        assert response.status == 502
        assert (await response.json())["detail"] == detail
