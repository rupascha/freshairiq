"""Real-HA coverage for the opt-in diagnostics Hub client (telemetry.py).

All Hub traffic goes through ``aioclient_mock``; no request leaves the test.
The scheduler is driven with ``freezer`` + ``async_fire_time_changed``.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aiohttp import ClientError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse
from homeassistant.util import dt as dt_util

from custom_components.freshairiq import telemetry as telemetry_module
from custom_components.freshairiq import telemetry_reports
from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.diagnostic_transport import next_nightly_upload_time
from custom_components.freshairiq.diagnostics import FreshAirIQDiagnosticsRecorder
from custom_components.freshairiq.telemetry import (
    FreshAirIQDiagnosticsClient,
    _normalise_hub_base,
)

HUB = "https://hub.test"
GRANTED = {"diagnostics_consent": "granted", "diagnostics_reporting_mode": "daily"}
TOKEN = "t" * 64


class Hub:
    """Route mocked Hub requests per path; queued answers first, then a default."""

    def __init__(self, aioclient_mock) -> None:
        self.mock = aioclient_mock
        self.queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.defaults: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, Any, Any]] = []
        self.blocker: asyncio.Event | None = None
        self.reached = asyncio.Event()
        for path in ("/v1/enroll", "/v1/activity", "/v1/diagnostics/chunks", "/v1/feedback",
                     "/v1/client-errors", "/v1/support/diagnostics"):
            aioclient_mock.post(f"{HUB}{path}", side_effect=self._answer)

    def queue(self, path: str, **kwargs: Any) -> None:
        self.queues[path].append(kwargs)

    def default(self, path: str, **kwargs: Any) -> None:
        self.defaults[path] = kwargs

    async def _answer(self, method, url, data):
        path = url.path
        if path == "/v1/diagnostics/chunks" and self.blocker is not None:
            self.reached.set()
            await self.blocker.wait()
        self.calls.append((path, data, None))
        spec = self.queues[path].pop(0) if self.queues[path] else self.defaults.get(path, {"json": {"ok": True}})
        return AiohttpClientMockResponse(method=method, url=url, **spec)

    def paths(self) -> list[str]:
        return [path for path, _data, _headers in self.calls]

    def headers_for(self, path: str) -> list[dict[str, str]]:
        return [dict(headers or {}) for _m, url, _d, headers in self.mock.mock_calls if url.path == path]


@pytest.fixture
async def berlin(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    await hass.config.async_set_time_zone("Europe/Berlin")
    return tmp_path


@pytest.fixture
def hub(aioclient_mock) -> Hub:
    return Hub(aioclient_mock)


def _entry(hass, options: dict[str, Any] | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={"rooms": []}, options=dict(GRANTED if options is None else options))
    entry.add_to_hass(hass)
    return entry


def _store_key(entry) -> str:
    return f"{DOMAIN}.diagnostics_upload.{entry.entry_id}"


def _seed(hass_storage, entry, data: dict[str, Any]) -> None:
    hass_storage[_store_key(entry)] = {"version": 1, "minor_version": 1, "key": _store_key(entry), "data": data}


class FakeRecorder:
    def __init__(self, installation_id: str | None = "faiq-install-fake", export: dict | None = None, fail: bool = False) -> None:
        self.installation_id = installation_id
        self.export = export or {}
        self.fail = fail

    async def async_get_identity(self) -> dict[str, Any]:
        if self.fail:
            raise OSError("identity storage broken")
        return {"installation_id": self.installation_id}

    async def async_export(self) -> dict[str, Any]:
        return dict(self.export)


def _client(hass, entry, recorder, endpoint: str = HUB, **kwargs) -> FreshAirIQDiagnosticsClient:
    return FreshAirIQDiagnosticsClient(hass, entry, recorder, endpoint=endpoint, **kwargs)


def _gunzip_json(data: bytes) -> dict[str, Any]:
    return json.loads(gzip.decompress(data).decode("utf-8"))


# --------------------------------------------------------------------------- URL validation


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("", ""),
        ("http://[::1", ""),  # urlsplit raises ValueError
        ("ftp://hub.example", ""),
        ("https://user:pw@hub.example", ""),
        ("https://:443", ""),  # netloc without hostname
        ("http://localhost:8000/v1/diagnostics/chunks", "http://localhost:8000"),
        ("http://hub.example/v1/enroll", ""),  # plain HTTP to a DNS name
        ("http://8.8.8.8", ""),  # plain HTTP to a public IP
        ("http://192.168.1.20:8080/base/v1/diagnostics/", "http://192.168.1.20:8080/base"),
        ("https://hub.example/api/v1/enroll", "https://hub.example/api"),
    ],
)
def test_normalise_hub_base_accepts_only_safe_endpoints(endpoint: str, expected: str) -> None:
    assert _normalise_hub_base(endpoint) == expected


# --------------------------------------------------------------------------- scheduled uploads


async def test_start_heartbeat_and_nightly_slot_timer_upload(hass, berlin, hass_storage, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    identity = await recorder.async_get_identity()
    _seed(hass_storage, entry, {
        "diagnostics_first_seen_at": "2026-10-01T10:00:00+02:00",
        "last_success_at": "2026-10-14T03:00:00+02:00",
        "client_token": TOKEN,
        "hub_enrolled": True,
    })
    client = _client(hass, entry, recorder, health_provider=lambda: {"robustness": {}})
    await client.async_start()
    await hass.async_block_till_done()

    # Daytime start: heartbeat only, no diagnostic payload, slot timer armed for tonight.
    assert hub.paths() == ["/v1/activity"]
    assert client.status["state"] == "waiting"
    slot = next_nightly_upload_time(dt_util.now(), identity["installation_id"])
    assert client._slot_armed_for == slot.isoformat()
    assert dt_util.as_local(slot).date().isoformat() == "2026-10-16"
    assert timedelta(minutes=30) <= slot - dt_util.start_of_local_day(slot) < timedelta(hours=6)

    # A second check at the same time must not re-arm or re-send the heartbeat.
    client.request_check()
    await hass.async_block_till_done()
    assert hub.paths() == ["/v1/activity"]
    assert client._slot_armed_for == slot.isoformat()

    freezer.move_to(slot)
    async_fire_time_changed(hass, slot)
    freezer.tick(2)  # the check task runs a moment after the slot callback
    await hass.async_block_till_done()

    assert "/v1/diagnostics/chunks" in hub.paths()
    status = client.status
    assert status["state"] == "sent"
    assert status["last_success_at"] == dt_util.now().isoformat()
    assert status["consecutive_failures"] == 0
    assert status["initial_snapshot_received"] is True  # no acknowledged cursor yet
    headers = hub.headers_for("/v1/diagnostics/chunks")[0]
    assert headers["Content-Encoding"] == "gzip"
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Idempotency-Key"] == headers["X-FreshAirIQ-Chunk-ID"]
    chunk = _gunzip_json(hub.calls[[p for p, *_ in hub.calls].index("/v1/diagnostics/chunks")][1])
    assert chunk["batch_id"] == status["last_batch_id"]
    # Next night's slot is armed again after the upload.
    assert client._slot_armed_for == (slot + timedelta(days=1)).isoformat()
    assert hass_storage[_store_key(entry)]["data"]["last_success_at"] == status["last_success_at"]

    await client.async_stop()
    assert client.status["state"] == "stopped"
    assert client._unsub is None and client._unsub_slot is None
    # A stopped client ignores further checks.
    client.request_check()
    assert client._task is None


async def test_start_twice_is_idempotent_and_first_start_records_first_seen(hass, berlin, hass_storage, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass, {"diagnostics_consent": "declined"})
    client = _client(hass, entry, FakeRecorder())
    await client.async_start()
    first_unsub = client._unsub
    await client.async_start()
    await hass.async_block_till_done()
    assert client._unsub is first_unsub
    assert hass_storage[_store_key(entry)]["data"]["diagnostics_first_seen_at"].startswith("2026-10-15T12:00:00")
    assert client.status["state"] == "disabled"
    assert client._unsub_slot is None
    assert hub.calls == []
    await client.async_stop()


async def test_start_survives_unreadable_state_store(hass, berlin, hub, monkeypatch) -> None:
    entry = _entry(hass, {"diagnostics_consent": "unset"})
    client = _client(hass, entry, FakeRecorder())

    async def broken_load():
        raise ValueError("corrupt json")

    monkeypatch.setattr(client._store, "async_load", broken_load)
    await client.async_start()
    await hass.async_block_till_done()
    assert client._started is True
    assert "diagnostics_first_seen_at" in client._state
    await client.async_stop()


async def test_first_sync_waits_for_onboarding_grace_then_uploads(hass, berlin, hass_storage, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    # Naive first-seen timestamp from an older release.
    _seed(hass_storage, entry, {"diagnostics_first_seen_at": "2026-10-15T11:50:00"})
    client = _client(hass, entry, recorder)
    await client._store.async_load()
    client._state = dict(hass_storage[_store_key(entry)]["data"])

    assert await client.async_maybe_upload() is False
    assert client.status["state"] == "onboarding_grace"
    assert client.status["hub_enrolled"] is True  # registration happens before the grace gate
    assert hub.paths() == ["/v1/enroll"]
    enroll = json.loads(hub.calls[0][1])
    assert enroll["client_token"] == client._state["client_token"]
    assert enroll["anonymous_installation_id"].startswith("faiq-install-")

    freezer.move_to("2026-10-15T12:30:00+02:00")
    assert await client.async_maybe_upload() is True
    assert client.status["initial_snapshot_received"] is True
    assert hub.paths().count("/v1/enroll") == 1


async def test_hub_429_retry_after_and_backoff_gate(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass, {**GRANTED, "diagnostics_reporting_mode": "errors"})
    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    client = _client(hass, entry, recorder)
    client._state = {"client_token": TOKEN, "hub_enrolled": True, "diagnostics_first_seen_at": "2026-10-01T00:00:00+02:00"}
    hub.queue("/v1/diagnostics/chunks", status=429, headers={"Retry-After": "7200"})

    assert await client.async_maybe_upload(force=True) is False
    status = client.status
    assert status["state"] == "error"
    assert status["last_status_code"] == 429
    assert status["last_error_type"] == "RuntimeError"
    assert status["consecutive_failures"] == 1
    next_retry = datetime.fromisoformat(status["next_retry_at"])
    assert next_retry - dt_util.now() >= timedelta(seconds=7200)

    # Inside the server-requested backoff a scheduled check does nothing.
    assert await client.async_maybe_upload() is False
    assert client.status["state"] == "backoff"

    # 503 with an unparsable Retry-After falls back to the exponential delay.
    hub.queue("/v1/diagnostics/chunks", status=503, headers={"Retry-After": "soon"})
    assert await client.async_maybe_upload(force=True) is False
    assert client._retry_after_seconds is None
    delay = datetime.fromisoformat(client.status["next_retry_at"]) - dt_util.now()
    assert timedelta(seconds=600) <= delay <= timedelta(seconds=750)
    assert client.status["consecutive_failures"] == 2

    # Naive persisted retry timestamp is aligned to local time before comparison.
    client._state["next_retry_at"] = (dt_util.now() + timedelta(minutes=5)).replace(tzinfo=None).isoformat()
    assert await client.async_maybe_upload() is False
    assert client.status["state"] == "backoff"


async def test_chunk_401_reenrolls_same_token_and_succeeds(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    client = _client(hass, entry, recorder)
    client._state = {"client_token": TOKEN, "hub_enrolled": True, "diagnostics_first_seen_at": "2026-10-01T00:00:00+02:00"}
    hub.queue("/v1/diagnostics/chunks", status=401)

    assert await client.async_maybe_upload(force=True, manual=True) is True
    assert hub.paths() == ["/v1/diagnostics/chunks", "/v1/enroll", "/v1/diagnostics/chunks"]
    assert json.loads(hub.calls[1][1])["client_token"] == TOKEN
    assert client.status["hub_enrolled"] is True


async def test_chunk_persistent_401_fails_after_single_reenroll(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    client = _client(hass, entry, FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test"))
    client._state = {"client_token": TOKEN, "hub_enrolled": True}
    hub.default("/v1/diagnostics/chunks", status=401)
    assert await client.async_maybe_upload(force=True) is False
    assert hub.paths().count("/v1/diagnostics/chunks") == 2
    assert client.status["last_status_code"] == 401


async def test_enrollment_failure_schedules_retry(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass, {**GRANTED, "diagnostics_reporting_mode": "weekly"})
    client = _client(hass, entry, FakeRecorder())
    hub.queue("/v1/enroll", status=500)
    assert await client.async_maybe_upload(force=True) is False
    status = client.status
    assert status["state"] == "error"
    assert status["last_error_type"] == "RuntimeError"
    assert status["last_status_code"] == 500
    assert status["hub_enrolled"] is False
    assert status["next_retry_at"] is not None
    assert "/v1/diagnostics/chunks" not in hub.paths()


async def test_enrollment_409_recovers_locally_owned_legacy_credential(hass, berlin, hub) -> None:
    storage = Path(hass.config.path(".storage"))
    storage.mkdir(parents=True, exist_ok=True)
    legacy_a = "a" * 48
    legacy_b = "b" * 48
    (storage / f"{DOMAIN}.diagnostics_upload.old1").write_text(json.dumps({"data": {"client_token": legacy_a}}), encoding="utf-8")
    (storage / f"{DOMAIN}.diagnostics_upload.old2").write_text(json.dumps({"data": {"client_token": legacy_b}}), encoding="utf-8")
    (storage / f"{DOMAIN}.diagnostics_upload.broken").write_text("{not json", encoding="utf-8")
    (storage / f"{DOMAIN}.diagnostics_upload.short").write_text(json.dumps({"data": {"client_token": "short"}}), encoding="utf-8")
    (storage / f"{DOMAIN}.diagnostics_upload.list").write_text(json.dumps([1, 2]), encoding="utf-8")
    entry = _entry(hass)
    client = _client(hass, entry, FakeRecorder())
    hub.queue("/v1/enroll", status=409)
    hub.queue("/v1/enroll", exc=ClientError("reset"))
    hub.queue("/v1/enroll", status=200)

    assert await client.async_activity_heartbeat() is True
    adopted = client._state["client_token"]
    assert adopted in {legacy_a, legacy_b}
    assert client._state["enrollment_recovered_from_local_credential"] is True
    assert client._state["hub_enrolled"] is True
    activity = hub.headers_for("/v1/activity")[0]
    assert activity["Authorization"] == f"Bearer {adopted}"


async def test_enrollment_409_without_recoverable_credential_fails(hass, berlin, hub) -> None:
    entry = _entry(hass)
    client = _client(hass, entry, FakeRecorder())
    hub.queue("/v1/enroll", status=409)
    assert await client.async_activity_heartbeat() is False
    assert client._state["hub_enrolled"] is False
    assert client._state["last_status_code"] == 409


async def test_consent_and_endpoint_gates(hass, berlin, hub) -> None:
    declined = _client(hass, _entry(hass, {"diagnostics_consent": "declined", "diagnostics_reporting_mode": "daily"}), FakeRecorder())
    assert await declined.async_maybe_upload() is False
    assert declined.status["state"] == "disabled"
    assert declined.status["reporting_mode"] == "off"
    assert declined.status["configured_reporting_mode"] == "daily"
    assert await declined.async_activity_heartbeat() is False

    off = _client(hass, _entry(hass, {"diagnostics_consent": "granted", "diagnostics_reporting_mode": "off"}), FakeRecorder())
    assert await off.async_activity_heartbeat() is False
    assert off.status["state"] == "disabled"

    unconfigured = _client(hass, _entry(hass), FakeRecorder(), endpoint="")
    assert await unconfigured.async_maybe_upload(manual=True) is False
    assert unconfigured.status["state"] == "hub_unconfigured"
    assert unconfigured.status["hub_configured"] is False
    assert await unconfigured.async_activity_heartbeat() is False

    local = _client(hass, _entry(hass), FakeRecorder(), endpoint="http://127.0.0.1:8000")
    assert local.status["hub_environment"] == "local_staging"
    assert hub.calls == []


async def test_manual_send_ignores_consent_but_needs_identity(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass, {"diagnostics_consent": "declined"})
    no_identity = _client(hass, entry, FakeRecorder(installation_id=None))
    assert await no_identity.async_maybe_upload(force=True, manual=True) is False
    assert no_identity.status["state"] == "identity_unavailable"

    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    manual = _client(hass, entry, recorder)
    assert await manual.async_maybe_upload(force=True, manual=True) is True
    assert hub.paths() == ["/v1/enroll", "/v1/diagnostics/chunks"]
    # Successful upload flushes queued client errors as well.
    assert manual.status["state"] == "sent"


async def test_upload_flushes_queued_client_errors_and_requeues_failures(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    client = _client(hass, entry, FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test"))
    client._state = {
        "client_token": TOKEN, "hub_enrolled": True,
        "client_error_queue": [{"fingerprint": "f1", "code": "A"}, {"fingerprint": "f2", "code": "B"}, "junk"],
    }
    hub.queue("/v1/client-errors", status=200)
    hub.queue("/v1/client-errors", status=500)
    assert await client.async_maybe_upload(force=True) is True
    assert hub.paths().count("/v1/client-errors") == 2
    assert client._state["client_error_queue"] == [{"fingerprint": "f2", "code": "B"}]


async def test_waiting_outside_window_and_errors_mode_without_problem(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass, {**GRANTED, "diagnostics_reporting_mode": "errors"})
    client = _client(hass, entry, FakeRecorder())
    assert await client.async_maybe_upload() is False
    assert client.status["state"] == "waiting"
    # Errors mode does not use the night slot timer.
    client._started = True
    client._unsub_slot = lambda: None
    client._slot_armed_for = "x"
    await client._async_arm_slot_timer()
    assert client._unsub_slot is None and client._slot_armed_for is None
    assert hub.calls == []


async def test_slot_timer_tolerates_identity_errors(hass, berlin, hub) -> None:
    entry = _entry(hass)
    failing = _client(hass, entry, FakeRecorder(fail=True))
    failing._started = True
    await failing._async_arm_slot_timer()
    assert failing._unsub_slot is None
    missing = _client(hass, entry, FakeRecorder(installation_id=""))
    missing._started = True
    await missing._async_arm_slot_timer()
    assert missing._unsub_slot is None


async def test_stop_cancels_running_upload(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    client = _client(hass, entry, FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test"))
    client._state = {"client_token": TOKEN, "hub_enrolled": True}
    client._started = True
    hub.blocker = asyncio.Event()
    client._task = hass.async_create_task(client.async_maybe_upload(force=True))
    # Wait (event-driven, no sleeping) until the chunk request hangs at the Hub.
    await asyncio.wait_for(hub.reached.wait(), timeout=10)
    assert client._runtime_state == "uploading"
    await client.async_stop()
    assert client._task is None
    assert client.status["state"] == "stopped"
    assert client.status["last_success_at"] is None
    assert client.status["consecutive_failures"] == 0


# --------------------------------------------------------------------------- heartbeat


async def test_activity_heartbeat_interval_identity_and_http_errors(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    client = _client(hass, entry, FakeRecorder())
    client._state = {"client_token": TOKEN, "hub_enrolled": True,
                     "last_activity_heartbeat_at": "2026-10-15T10:00:00"}  # naive, 2 h ago
    assert await client.async_activity_heartbeat() is False
    assert hub.calls == []

    client._state["last_activity_heartbeat_at"] = "2026-10-15T00:00:00+02:00"
    hub.queue("/v1/activity", status=503)
    assert await client.async_activity_heartbeat() is False
    assert client._state["last_activity_heartbeat_at"] == "2026-10-15T00:00:00+02:00"

    assert await client.async_activity_heartbeat() is True
    assert client._state["last_activity_heartbeat_at"] == dt_util.now().isoformat()
    payload = hub.calls[-1][1]
    assert payload["anonymous_installation_id"] == "faiq-install-fake"
    assert payload["client_token"] == TOKEN

    nobody = _client(hass, entry, FakeRecorder(installation_id=""))
    assert await nobody.async_activity_heartbeat() is False


async def test_naive_clock_paths_are_aligned(hass, berlin, hub, monkeypatch) -> None:
    """Defensive branches for a naive ``now`` with aware persisted timestamps."""
    naive_now = datetime(2026, 10, 15, 12, 0, 0)
    monkeypatch.setattr(telemetry_module, "dt_util", SimpleNamespace(now=lambda: naive_now))
    monkeypatch.setattr(telemetry_reports, "dt_util", SimpleNamespace(now=lambda: naive_now))
    entry = _entry(hass)
    client = _client(hass, entry, FakeRecorder())
    client._state = {"client_token": TOKEN, "hub_enrolled": True,
                     "last_activity_heartbeat_at": "2026-10-15T11:00:00+02:00",
                     "next_retry_at": "2026-10-15T12:30:00+02:00",
                     "support_cooldown_until": "2026-10-15T12:10:00+02:00"}
    assert await client.async_activity_heartbeat() is False
    assert await client.async_maybe_upload() is False
    assert client.status["state"] == "backoff"
    result = await client.async_submit_support_diagnostics("x")
    assert result["reason"] == "cooldown" and result["retry_after_seconds"] == 600
    # Error-driven first sync with an aware first-seen timestamp and a naive clock:
    # enrollment happens, the diagnostic payload waits for the onboarding grace.
    client.entry = _entry(hass, {**GRANTED, "diagnostics_reporting_mode": "errors"})
    client.health_provider = lambda: {"robustness": {"consecutive_failures": 3, "last_failure_type": "UpdateFailed"}}
    client._state = {"client_token": TOKEN, "hub_enrolled": False,
                     "diagnostics_first_seen_at": "2026-10-15T11:50:00+02:00"}
    assert await client.async_maybe_upload() is False
    assert client.status["state"] == "onboarding_grace"
    assert hub.paths() == ["/v1/enroll"]


async def test_missing_home_assistant_version_is_sent_as_null(hass, berlin, hub, monkeypatch) -> None:
    import homeassistant.const as ha_const

    monkeypatch.delattr(ha_const, "__version__")
    client = _client(hass, _entry(hass), FakeRecorder())
    client._state = {"client_token": TOKEN, "hub_enrolled": True}
    hub.queue("/v1/feedback", status=200, json={"accepted": True})
    await client.async_submit_feedback("bug", "no version")
    assert hub.calls[-1][1]["home_assistant_version"] is None
    hub.queue("/v1/client-errors", status=200, json={"stored": True})
    await client.async_report_client_error(code="C", component="x", operation="y", message="m")
    assert hub.calls[-1][1]["home_assistant_version"] is None


# --------------------------------------------------------------------------- helpers


async def test_health_providers_are_isolated(hass, berlin) -> None:
    entry = _entry(hass)

    def boom(*_args):
        raise RuntimeError("provider bug")

    client = _client(hass, entry, FakeRecorder(), health_provider=boom)
    assert client._health() == {}
    client.health_provider = lambda: ["not", "a", "mapping"]
    assert client._health() == {}
    client.health_provider = lambda: {"ok": 1}
    now = dt_util.now()
    assert client._health_snapshot(now) == {"ok": 1}
    client.health_snapshot_provider = boom
    assert client._health_snapshot(now) == {"ok": 1}
    client.health_snapshot_provider = lambda _now: "invalid"
    assert client._health_snapshot(now) == {"ok": 1}
    client.health_snapshot_provider = lambda when: {"captured_at": when.isoformat()}
    assert client._health_snapshot(now) == {"captured_at": now.isoformat()}
    assert client._parse_dt("not-a-date") is None
    assert client._parse_dt(None) is None
    assert client._safe_failure_count("x") == 0
    assert client._safe_failure_count(-3) == 0


async def test_cpu_job_falls_back_to_thread_without_executor(hass, berlin) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    assert await client._async_cpu_job(sum, [1, 2, 3]) == 6
    client.hass = SimpleNamespace()
    assert await client._async_cpu_job(lambda a, *, b: a + b, 2, b=5) == 7


async def test_state_persistence_failures_are_contained(hass, berlin, hub, monkeypatch) -> None:
    entry = _entry(hass)
    client = _client(hass, entry, FakeRecorder())

    async def broken_save(_data):
        raise OSError("disk full")

    monkeypatch.setattr(client._store, "async_save", broken_save)
    assert await client._save_state() is False
    # Without a persisted credential no enrollment may happen.
    with pytest.raises(RuntimeError, match="hub_credential_persistence_failed"):
        await client._async_client_token()
    assert "client_token" not in client._state
    assert hub.calls == []


# --------------------------------------------------------------------------- feedback


async def test_feedback_validation_and_unconfigured_hub(hass, berlin) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    with pytest.raises(ValueError, match="feedback_type_invalid"):
        await client.async_submit_feedback("praise", "hello")
    with pytest.raises(ValueError, match="feedback_message_invalid"):
        await client.async_submit_feedback("bug", "x")
    unconfigured = _client(hass, _entry(hass), FakeRecorder(), endpoint="")
    with pytest.raises(RuntimeError, match="hub_unconfigured"):
        await unconfigured.async_submit_feedback("bug", "broken card")
    no_identity = _client(hass, _entry(hass), FakeRecorder(installation_id=""))
    with pytest.raises(RuntimeError, match="identity_unavailable"):
        await no_identity.async_submit_feedback("bug", "broken card")


async def test_feedback_success_filters_client_context_and_starts_cooldown(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    client = _client(hass, _entry(hass), FakeRecorder())
    hub.queue("/v1/feedback", status=201, json={"accepted": True, "feedback_id": "fb-1"})
    result = await client.async_submit_feedback(
        "improvement", "  More charts please  ",
        client_context={"platform_family": "iOS", "user_agent": "Mozilla/5.0 secret", "device_name": "Paschas iPhone"},
    )
    assert result["feedback_id"] == "fb-1"
    assert result["cooldown_seconds"] == 900
    assert result["cooldown_until"] == (dt_util.now() + timedelta(minutes=15)).isoformat()
    sent = hub.calls[-1][1]
    assert sent["message"] == "More charts please"
    assert sent["client_context"] == {"platform_family": "iOS"}

    again = await client.async_submit_feedback("bug", "second one")
    assert again["reason"] == "cooldown"
    assert again["retry_after_seconds"] == 900
    assert hub.paths().count("/v1/feedback") == 1


async def test_feedback_legacy_hub_without_client_context(hass, berlin, hub) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    hub.queue("/v1/feedback", status=422)
    hub.queue("/v1/feedback", status=200, json={"accepted": True})
    result = await client.async_submit_feedback("bug", "card broken", client_context={"browser_family": "Safari"})
    assert result["client_context_accepted"] is False
    legacy = hub.calls[-1][1]
    assert "client_context" not in legacy


async def test_feedback_legacy_retry_failure_falls_through_to_error(hass, berlin, hub) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    hub.queue("/v1/feedback", status=400)
    hub.queue("/v1/feedback", status=400)
    with pytest.raises(RuntimeError, match="feedback_http_400"):
        await client.async_submit_feedback("bug", "card broken", client_context={"browser_family": "Safari"})


async def test_feedback_401_reenrolls_and_retries(hass, berlin, hub) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    client._state = {"client_token": TOKEN, "hub_enrolled": True}
    hub.queue("/v1/feedback", status=401)
    hub.queue("/v1/feedback", status=200, json={"accepted": True})
    result = await client.async_submit_feedback("other", "hello hub")
    assert result["accepted"] is True
    assert hub.paths() == ["/v1/feedback", "/v1/enroll", "/v1/feedback"]

    client._state["feedback_cooldown_until"] = None
    hub.queue("/v1/feedback", status=401)
    hub.queue("/v1/feedback", status=500)
    with pytest.raises(RuntimeError, match="feedback_http_500"):
        await client.async_submit_feedback("other", "hello hub")


async def test_feedback_hub_cooldown_and_errors(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    client = _client(hass, _entry(hass), FakeRecorder())
    hub.queue("/v1/feedback", status=429, json={"detail": {"retry_after_seconds": 120}})
    result = await client.async_submit_feedback("bug", "hub says later")
    assert result["reason"] == "cooldown" and result["retry_after_seconds"] == 120
    assert client._state["feedback_cooldown_until"] == result["cooldown_until"]

    client._state["feedback_cooldown_until"] = None
    hub.queue("/v1/feedback", status=429, text="<html>busy</html>")
    result = await client.async_submit_feedback("bug", "hub says later")
    assert result["retry_after_seconds"] == 900

    client._state["feedback_cooldown_until"] = None
    hub.queue("/v1/feedback", status=500)
    with pytest.raises(RuntimeError, match="feedback_http_500"):
        await client.async_submit_feedback("bug", "hub broken")
    assert client._state["feedback_cooldown_until"] is None


# --------------------------------------------------------------------------- client errors


async def test_client_error_report_success_flushes_queue(hass, berlin, hub) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    client._state = {"client_token": TOKEN, "hub_enrolled": True,
                     "client_error_queue": [{"fingerprint": "old", "code": "X"}]}
    hub.queue("/v1/client-errors", status=200, json={"stored": True})
    hub.queue("/v1/client-errors", exc=ClientError("down again"))
    result = await client.async_report_client_error(code="FAIQ-1", component="card", operation="load", message="boom" * 300)
    assert result == {"stored": True}
    sent = hub.calls[0][1]
    assert sent["code"] == "FAIQ-1"
    assert len(sent["message"]) == 1200
    assert len(sent["fingerprint"]) == 64
    assert client._state["client_error_queue"] == [{"fingerprint": "old", "code": "X"}]


async def test_client_error_report_failures_are_queued_once(hass, berlin, hub) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    client._state = {"client_token": TOKEN, "hub_enrolled": True}
    hub.default("/v1/client-errors", status=502)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="client_error_http_502"):
            await client.async_report_client_error(code="C", component="x", operation="y", message="same")
    assert len(client._state["client_error_queue"]) == 1

    unconfigured = _client(hass, _entry(hass), FakeRecorder(), endpoint="")
    with pytest.raises(RuntimeError, match="hub_unconfigured"):
        await unconfigured.async_report_client_error(code="C", component="x", operation="y", message="m")
    assert len(unconfigured._state["client_error_queue"]) == 1

    nobody = _client(hass, _entry(hass), FakeRecorder(installation_id=None))
    with pytest.raises(RuntimeError, match="identity_unavailable"):
        await nobody.async_report_client_error(code="C", component="x", operation="y", message="m")
    assert nobody._state["client_error_queue"][0]["code"] == "C"


# --------------------------------------------------------------------------- support diagnostics


async def test_support_diagnostics_success_and_cooldown(hass, berlin, hub, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    entry = _entry(hass)
    recorder = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, "test")
    client = _client(hass, entry, recorder, health_snapshot_provider=lambda now: {"captured_at": now.isoformat(), "ok": True})
    client._state = {"client_error_queue": [{"fingerprint": "q", "code": "Q"}]}
    result = await client.async_submit_support_diagnostics("  Card shows nothing  ")
    assert result["accepted"] is True
    case_id = result["support_case_id"]
    assert case_id.startswith("support-")
    assert result["cooldown_until"] == (dt_util.now() + timedelta(hours=1)).isoformat()
    assert hub.paths() == ["/v1/enroll", "/v1/support/diagnostics", "/v1/client-errors"]
    headers = hub.headers_for("/v1/support/diagnostics")[0]
    assert headers["X-FreshAirIQ-Support-Case-ID"] == case_id == headers["Idempotency-Key"]
    body = _gunzip_json(hub.calls[1][1])
    assert body["user_message"] == "Card shows nothing"
    assert body["health_snapshot"]["ok"] is True
    assert body["diagnostics"]["records"] == [] or isinstance(body["diagnostics"], dict)
    assert client.status["support_last_case_id"] == case_id
    assert client._state["client_error_queue"] == []

    again = await client.async_submit_support_diagnostics("again")
    assert again["accepted"] is False and again["reason"] == "cooldown"
    assert again["retry_after_seconds"] == 3600

    # Naive persisted cooldown from an older release.
    client._state["support_cooldown_until"] = (dt_util.now() + timedelta(minutes=2)).replace(tzinfo=None).isoformat()
    assert (await client.async_submit_support_diagnostics(""))["retry_after_seconds"] == 120


async def test_support_diagnostics_401_retry_and_http_errors(hass, berlin, hub) -> None:
    entry = _entry(hass)
    client = _client(hass, entry, FakeRecorder(export={"records": []}))
    client._state = {"client_token": TOKEN, "hub_enrolled": True}
    hub.queue("/v1/support/diagnostics", status=401)
    hub.queue("/v1/support/diagnostics", status=202)
    assert (await client.async_submit_support_diagnostics("x"))["accepted"] is True
    assert hub.paths() == ["/v1/support/diagnostics", "/v1/enroll", "/v1/support/diagnostics"]

    client._state.pop("support_cooldown_until")
    hub.queue("/v1/support/diagnostics", status=401)
    hub.queue("/v1/support/diagnostics", status=500)
    with pytest.raises(RuntimeError, match="support_diagnostics_http_500"):
        await client.async_submit_support_diagnostics("x")

    hub.queue("/v1/support/diagnostics", status=413)
    with pytest.raises(RuntimeError, match="support_diagnostics_http_413"):
        await client.async_submit_support_diagnostics("x")

    hub.queue("/v1/support/diagnostics", exc=ClientError("reset"))
    with pytest.raises(ClientError):
        await client.async_submit_support_diagnostics("x")
    messages = [item["message"] for item in client._state["client_error_queue"]]
    assert "RuntimeError: support_diagnostics_http_500" in messages
    assert "ClientError: ClientError" in messages
    assert client._state.get("support_cooldown_until") is None


async def test_support_diagnostics_validation_and_preflight_errors(hass, berlin, hub) -> None:
    client = _client(hass, _entry(hass), FakeRecorder())
    with pytest.raises(ValueError, match="support_message_too_long"):
        await client.async_submit_support_diagnostics("x" * 5000)

    unconfigured = _client(hass, _entry(hass), FakeRecorder(), endpoint="")
    with pytest.raises(RuntimeError, match="hub_unconfigured"):
        await unconfigured.async_submit_support_diagnostics("help")
    assert unconfigured._state["client_error_queue"][0]["code"] == "FAIQ-SUPPORT-UPLOAD-001"

    nobody = _client(hass, _entry(hass), FakeRecorder(installation_id=""))
    with pytest.raises(RuntimeError, match="identity_unavailable"):
        await nobody.async_submit_support_diagnostics("help")
    assert nobody._state["client_error_queue"][0]["message"] == "RuntimeError: identity_unavailable"

    broken = _client(hass, _entry(hass), FakeRecorder(fail=True))
    with pytest.raises(OSError):
        await broken.async_submit_support_diagnostics("help")
    assert broken._state["client_error_queue"][0]["message"] == "OSError: OSError"
    assert hub.calls == []
