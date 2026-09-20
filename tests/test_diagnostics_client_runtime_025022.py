"""Standalone runtime tests for the HA-facing diagnostics client.

The real Home Assistant lifecycle remains covered by ha_tests in CI; these
stubs verify that the optional client fails closed and cannot break FreshAirIQ.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import sys
import types

# Minimal Home Assistant surface required by telemetry.py.
ha = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
core = types.ModuleType("homeassistant.core")
class HomeAssistant: ...
def callback(func): return func
core.HomeAssistant = HomeAssistant
core.callback = callback
sys.modules["homeassistant.core"] = core

helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
aio = types.ModuleType("homeassistant.helpers.aiohttp_client")
aio.async_get_clientsession = lambda hass: hass.session
sys.modules["homeassistant.helpers.aiohttp_client"] = aio

event = types.ModuleType("homeassistant.helpers.event")
def async_track_time_interval(hass, action, interval):
    hass.tracked = (action, interval)
    return lambda: setattr(hass, "unsubscribed", True)
event.async_track_time_interval = async_track_time_interval
sys.modules["homeassistant.helpers.event"] = event

storage = types.ModuleType("homeassistant.helpers.storage")
class Store:
    def __init__(self, hass, version, key):
        self.hass = hass; self.version = version; self.key = key
    async def async_load(self):
        if getattr(self.hass, "load_raises", False):
            raise OSError("broken storage")
        return getattr(self.hass, "stored", None)
    async def async_save(self, value):
        if getattr(self.hass, "save_raises", False):
            raise OSError("broken storage")
        self.hass.stored = dict(value)
storage.Store = Store
sys.modules["homeassistant.helpers.storage"] = storage

util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
dt = types.ModuleType("homeassistant.util.dt")
dt.now = lambda: datetime(2026, 9, 16, 23, 0, tzinfo=timezone.utc)
sys.modules["homeassistant.util.dt"] = dt
util.dt = dt

from custom_components.freshairiq.telemetry import FreshAirIQDiagnosticsClient


class _Entry:
    entry_id = "entry"
    def __init__(self, options=None):
        self.options = options or {}


class _Recorder:
    def __init__(self):
        self.identity_calls = 0
        self.export_calls = 0
    async def async_get_identity(self):
        self.identity_calls += 1
        return {"installation_id": "faiq-install-runtime"}
    async def async_export(self):
        self.export_calls += 1
        return {
            "schema_version": 10,
            "freshairiq_version": "0.25.0.39",
            "exported_at": "2026-09-16T23:00:00+00:00",
            "field_test": {
                "anonymous_installation_id": "faiq-install-runtime",
                "runtime_environment": {"home_assistant_version": "2026.9.2"},
                "observation": {"record_count": 1},
                "freshairiq_version_history": [],
                "home_assistant_version_history": [],
                "known_clients": [],
            },
            "test_dossier": {
                "record_count": 1,
                "configuration": {"rooms": [{"key": "living", "name": "Private Room"}]},
                "forecast_validation": {},
                "forecast_backtest": {},
            },
            "records": [{"rooms": [{"key": "living", "name": "Private Room"}]}],
        }


class _Response:
    def __init__(self, status): self.status = status


class _PostContext:
    def __init__(self, response): self.response = response
    async def __aenter__(self): return self.response
    async def __aexit__(self, exc_type, exc, tb): return False


class _Session:
    def __init__(self, status=204): self.status = status; self.calls = []
    def post(self, endpoint, *, data, headers, timeout):
        self.calls.append({"endpoint": endpoint, "data": data, "headers": headers, "timeout": timeout})
        return _PostContext(_Response(self.status))


class _Hass:
    def __init__(self, status=204):
        self.session = _Session(status)
        self.stored = None
        self.tracked = None
        self.unsubscribed = False
        self.load_raises = False
        self.save_raises = False
    def async_create_task(self, coro):
        return asyncio.create_task(coro)


def test_off_and_unconfigured_modes_never_prepare_or_send_payload():
    async def run():
        hass = _Hass(); recorder = _Recorder()
        off = FreshAirIQDiagnosticsClient(hass, _Entry({"diagnostics_reporting_mode": "off"}), recorder, endpoint="https://hub.example")
        assert await off.async_maybe_upload(force=True) is False
        assert off.status["state"] == "disabled"
        assert recorder.identity_calls == recorder.export_calls == 0
        assert hass.session.calls == []

        pending = FreshAirIQDiagnosticsClient(hass, _Entry({"diagnostics_reporting_mode": "daily"}), recorder, endpoint="")
        assert await pending.async_maybe_upload(force=True) is False
        assert pending.status["state"] == "hub_unconfigured"
        assert recorder.identity_calls == recorder.export_calls == 0
    asyncio.run(run())


def test_successful_force_upload_is_gzipped_minimised_and_persisted():
    async def run():
        hass = _Hass(); recorder = _Recorder(); entry = _Entry({
            "diagnostics_reporting_mode": "daily",
            "diagnostics_include_client_context": False,
        })
        client = FreshAirIQDiagnosticsClient(hass, entry, recorder, endpoint="https://hub.example")
        assert await client.async_maybe_upload(force=True) is True
        assert recorder.identity_calls == 1 and recorder.export_calls == 1
        assert len(hass.session.calls) == 2
        enroll_call, call = hass.session.calls
        assert enroll_call["endpoint"] == "https://hub.example/v1/enroll"
        enroll_body = json.loads(enroll_call["data"].decode())
        assert enroll_body["anonymous_installation_id"] == "faiq-install-runtime"
        assert enroll_body["upload_schema_version"] == 2
        assert enroll_body["freshairiq_version"] == "0.25.0.39"
        assert len(enroll_body["client_token"]) >= 32
        assert call["endpoint"] == "https://hub.example/v1/diagnostics/chunks"
        assert call["headers"]["Authorization"] == f"Bearer {enroll_body['client_token']}"
        assert call["headers"]["Content-Encoding"] == "gzip"
        assert call["headers"]["User-Agent"] == "FreshAirIQ/0.25.0.39"
        import gzip
        body = json.loads(gzip.decompress(call["data"]).decode())
        text = json.dumps(body)
        assert "Private Room" not in text
        assert '"living"' not in text
        assert body["anonymous_installation_id"] == "faiq-install-runtime"
        assert client.status["state"] == "sent"
        assert client.status["consecutive_failures"] == 0
        assert hass.stored["last_success_at"]
        assert hass.stored["hub_enrolled"] is True
        assert hass.stored["client_token"] == enroll_body["client_token"]
        assert "client_token" not in client.status
        assert hass.stored["last_payload_sha256"] == body["content_sha256"]
    asyncio.run(run())


def test_http_failure_enters_backoff_without_raising():
    async def run():
        hass = _Hass(status=503); recorder = _Recorder(); entry = _Entry({"diagnostics_reporting_mode": "daily"})
        client = FreshAirIQDiagnosticsClient(hass, entry, recorder, endpoint="https://hub.example")
        assert await client.async_maybe_upload(force=True) is False
        assert client.status["state"] == "error"
        assert client.status["consecutive_failures"] == 1
        assert client.status["last_status_code"] == 503
        assert client.status["last_error_type"] == "RuntimeError"
        assert client.status["next_retry_at"]
        # A normal retry inside the backoff window does not hit the recorder/server.
        first_exports = recorder.export_calls
        assert await client.async_maybe_upload(force=False) is False
        assert client.status["state"] == "backoff"
        assert recorder.export_calls == first_exports
    asyncio.run(run())


def test_corrupt_state_and_storage_failures_are_non_fatal_and_lifecycle_is_idempotent():
    async def run():
        hass = _Hass(); hass.load_raises = True; hass.save_raises = True
        recorder = _Recorder(); entry = _Entry({"diagnostics_reporting_mode": "off"})
        client = FreshAirIQDiagnosticsClient(hass, entry, recorder, endpoint="")
        client._state["consecutive_failures"] = "corrupt"
        assert client.status["consecutive_failures"] == 0
        await client.async_start()
        await client.async_start()
        await asyncio.sleep(0)
        assert hass.tracked is not None
        await client.async_stop()
        assert hass.unsubscribed is True
        assert client.status["state"] == "stopped"
    asyncio.run(run())


def test_identity_failure_and_health_provider_failure_fail_closed():
    class BadRecorder(_Recorder):
        async def async_get_identity(self):
            return {"installation_id": None}
    async def run():
        hass = _Hass(); entry = _Entry({"diagnostics_reporting_mode": "errors"})
        client = FreshAirIQDiagnosticsClient(hass, entry, BadRecorder(), endpoint="https://hub.example", health_provider=lambda: (_ for _ in ()).throw(RuntimeError("health")))
        assert await client.async_maybe_upload(force=True) is False
        assert client.status["state"] == "identity_unavailable"
        assert client._health() == {}
    asyncio.run(run())



def test_chunk_progress_is_persisted_and_retry_resumes_without_acked_records():
    class LargeRecorder(_Recorder):
        async def async_export(self):
            base = await super().async_export()
            base["records"] = [
                {
                    "timestamp": f"2026-09-16T{index:02d}:00:00+00:00",
                    "rooms": [{"key": "living", "name": "Private Room"}],
                    "blob": "x" * 1200,
                }
                for index in range(10)
            ]
            base["field_test"]["observation"]["record_count"] = 10
            base["test_dossier"]["record_count"] = 10
            return base

    class SequenceSession:
        def __init__(self, statuses):
            self.statuses = list(statuses)
            self.calls = []
        def post(self, endpoint, *, data, headers, timeout):
            status = self.statuses.pop(0) if self.statuses else 204
            self.calls.append({"endpoint": endpoint, "data": data, "headers": headers, "timeout": timeout})
            return _PostContext(_Response(status))

    async def run():
        import gzip

        hass = _Hass(); recorder = LargeRecorder(); entry = _Entry({"diagnostics_reporting_mode": "daily"})
        hass.session = SequenceSession([204, 204, 503])
        client = FreshAirIQDiagnosticsClient(
            hass, entry, recorder, endpoint="https://hub.example", max_chunk_bytes=7500
        )
        assert await client.async_maybe_upload(force=True) is False
        assert len(hass.session.calls) == 3
        assert hass.session.calls[0]["endpoint"] == "https://hub.example/v1/enroll"
        accepted = json.loads(gzip.decompress(hass.session.calls[1]["data"]).decode())
        failed = json.loads(gzip.decompress(hass.session.calls[2]["data"]).decode())
        assert accepted["records"]
        assert failed["records"]
        assert hass.stored["last_record_cursor"] == accepted["cursor_after"]
        assert hass.stored.get("last_success_at") is None
        accepted_ids = set(accepted["record_ids"])

        # Clear backoff only for the deterministic retry test; a normal runtime
        # retry would wait for the stored backoff deadline.
        client._state["next_retry_at"] = None
        hass.session = SequenceSession([204] * 20)
        assert await client.async_maybe_upload(force=True) is True
        retry_bodies = [json.loads(gzip.decompress(call["data"]).decode()) for call in hass.session.calls]
        retry_ids = {record_id for body in retry_bodies for record_id in body["record_ids"]}
        assert accepted_ids.isdisjoint(retry_ids)
        assert len(accepted_ids) + len(retry_ids) == 10
        assert client.status["last_batch_record_count"] == len(retry_ids)
        assert client.status["last_batch_chunk_count"] == len(retry_bodies)
        assert client.status["last_record_cursor"] == retry_bodies[-1]["cursor_after"]
        for body, call in zip(retry_bodies, hass.session.calls):
            assert call["headers"]["Idempotency-Key"] == body["chunk_id"]
            assert call["headers"]["X-FreshAirIQ-Batch-ID"] == body["batch_id"]
            assert call["headers"]["X-FreshAirIQ-Chunk-ID"] == body["chunk_id"]

        # Re-exporting unchanged history after the cursor was acknowledged sends
        # only a metadata snapshot, not the same diagnostic records again.
        hass.session = SequenceSession([204])
        assert await client.async_maybe_upload(force=True) is True
        body = json.loads(gzip.decompress(hass.session.calls[0]["data"]).decode())
        assert body["records"] == []
        assert body["incremental"] is True
    asyncio.run(run())


def test_cpu_heavy_transport_work_uses_home_assistant_executor_when_available():
    class ExecutorHass(_Hass):
        def __init__(self):
            super().__init__()
            self.executor_calls = 0
        async def async_add_executor_job(self, target, *args):
            self.executor_calls += 1
            return await asyncio.to_thread(target, *args)

    async def run():
        hass = ExecutorHass()
        recorder = _Recorder()
        client = FreshAirIQDiagnosticsClient(
            hass,
            _Entry({"diagnostics_reporting_mode": "daily"}),
            recorder,
            endpoint="https://hub.example",
        )
        assert await client.async_maybe_upload(force=True) is True
        # At least one executor job for privacy/chunk preparation and one for
        # JSON+gzip encoding. Network I/O itself remains asynchronous.
        assert hass.executor_calls >= 2

    asyncio.run(run())


def test_first_daily_opt_in_syncs_immediately_but_errors_mode_without_problem_waits():
    async def run():
        daily_hass = _Hass(); daily_recorder = _Recorder()
        daily = FreshAirIQDiagnosticsClient(
            daily_hass,
            _Entry({"diagnostics_reporting_mode": "daily"}),
            daily_recorder,
            endpoint="https://hub.example",
        )
        assert await daily.async_maybe_upload(force=False) is True
        assert daily_recorder.export_calls == 1
        assert [call["endpoint"] for call in daily_hass.session.calls] == [
            "https://hub.example/v1/enroll",
            "https://hub.example/v1/diagnostics/chunks",
        ]

        errors_hass = _Hass(); errors_recorder = _Recorder()
        errors = FreshAirIQDiagnosticsClient(
            errors_hass,
            _Entry({"diagnostics_reporting_mode": "errors"}),
            errors_recorder,
            endpoint="https://hub.example",
        )
        assert await errors.async_maybe_upload(force=False) is False
        assert errors.status["state"] == "waiting"
        assert errors_recorder.export_calls == 0
        assert errors_hass.session.calls == []

    asyncio.run(run())


def test_401_reenrolls_with_same_persisted_token_and_retries_once():
    class SequenceSession:
        def __init__(self):
            self.statuses = [204, 401, 204, 204]
            self.calls = []
        def post(self, endpoint, *, data, headers, timeout):
            status = self.statuses.pop(0)
            self.calls.append({"endpoint": endpoint, "data": data, "headers": headers, "timeout": timeout})
            return _PostContext(_Response(status))

    async def run():
        hass = _Hass(); hass.session = SequenceSession()
        client = FreshAirIQDiagnosticsClient(
            hass,
            _Entry({"diagnostics_reporting_mode": "daily"}),
            _Recorder(),
            endpoint="https://hub.example",
        )
        assert await client.async_maybe_upload(force=True) is True
        assert [call["endpoint"] for call in hass.session.calls] == [
            "https://hub.example/v1/enroll",
            "https://hub.example/v1/diagnostics/chunks",
            "https://hub.example/v1/enroll",
            "https://hub.example/v1/diagnostics/chunks",
        ]
        first_enroll = json.loads(hass.session.calls[0]["data"].decode())
        second_enroll = json.loads(hass.session.calls[2]["data"].decode())
        assert first_enroll["client_token"] == second_enroll["client_token"]
        bearer = f"Bearer {first_enroll['client_token']}"
        assert hass.session.calls[1]["headers"]["Authorization"] == bearer
        assert hass.session.calls[3]["headers"]["Authorization"] == bearer
        assert client.status["hub_enrolled"] is True

    asyncio.run(run())
