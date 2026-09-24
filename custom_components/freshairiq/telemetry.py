"""Optional outbound diagnostics client for FreshAirIQ.

No data leaves Home Assistant unless the user explicitly selects a reporting
mode other than ``off``. The staging configuration is deliberately local: its
Hub base URL points only at the developer's private LAN endpoint. Public HTTP
endpoints are rejected; production rollout still requires HTTPS.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
import gzip
import json
import logging
import ipaddress
import secrets
from functools import partial
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DIAGNOSTICS_HUB_ENDPOINT,
    DIAGNOSTICS_SCHEMA_VERSION,
    DIAGNOSTICS_UPLOAD_MAX_BYTES,
    DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS,
    DOMAIN,
    VERSION,
)
from .diagnostic_transport import (
    build_upload_chunks,
    normalise_reporting_mode,
    problem_fingerprint,
    retry_delay_seconds,
    upload_due,
)

_LOGGER = logging.getLogger(__name__)
_STORE_VERSION = 1
_CHECK_INTERVAL = timedelta(minutes=15)
_GZIP_COMPRESSLEVEL = 4


def _normalise_hub_base(endpoint: str) -> str:
    """Return a safe Hub base URL or an empty string.

    HTTPS is accepted for normal deployments. Plain HTTP is accepted only for
    loopback/private IP addresses so this local staging release cannot silently
    turn into an Internet-facing clear-text diagnostics transport.
    """
    value = str(endpoint or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return ""
    host = parsed.hostname
    if not host:
        return ""
    if parsed.scheme == "http":
        if host.lower() != "localhost":
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                return ""
            if not (address.is_private or address.is_loopback):
                return ""

    path = parsed.path.rstrip("/")
    for suffix in ("/v1/diagnostics/chunks", "/v1/diagnostics", "/v1/enroll"):
        if path.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _encode_chunk_for_upload(chunk: Mapping[str, Any]) -> bytes:
    """Encode and compress one chunk outside the Home Assistant event loop."""
    raw = json.dumps(chunk, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=_GZIP_COMPRESSLEVEL)


class FreshAirIQDiagnosticsClient:
    """Schedule and upload locally anonymised diagnostics bundles."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: Any,
        recorder: Any,
        *,
        endpoint: str = DIAGNOSTICS_HUB_ENDPOINT,
        health_provider: Callable[[], Mapping[str, Any]] | None = None,
        max_chunk_bytes: int = DIAGNOSTICS_UPLOAD_MAX_BYTES,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.recorder = recorder
        self.endpoint = _normalise_hub_base(endpoint)
        self.enroll_endpoint = f"{self.endpoint}/v1/enroll" if self.endpoint else ""
        self.upload_endpoint = f"{self.endpoint}/v1/diagnostics/chunks" if self.endpoint else ""
        self.health_provider = health_provider or (lambda: {})
        self.max_chunk_bytes = max_chunk_bytes
        self._store = Store(hass, _STORE_VERSION, f"{DOMAIN}.diagnostics_upload.{entry.entry_id}")
        self._state: dict[str, Any] = {}
        self._unsub = None
        self._task: asyncio.Task | None = None
        self._started = False
        self._runtime_state = "not_started"

    @staticmethod
    def _safe_failure_count(value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError, OverflowError):
            return 0

    @property
    def status(self) -> dict[str, Any]:
        mode = normalise_reporting_mode(self.entry.options.get("diagnostics_reporting_mode", "off"))
        return {
            "reporting_mode": mode,
            "hub_configured": bool(self.endpoint),
            "hub_environment": "local_staging" if self.endpoint.startswith("http://") else "production",
            "hub_enrolled": bool(self._state.get("hub_enrolled")),
            "registered": bool(self._state.get("hub_enrolled")),
            "initial_snapshot_received": bool(self._state.get("initial_snapshot_sent")),
            "daily_upload_received": bool(self._state.get("regular_upload_sent")),
            "last_successful_upload": self._state.get("last_success_at"),
            "next_scheduled_upload": self._state.get("next_retry_at"),
            "initial_snapshot_sent": bool(self._state.get("initial_snapshot_sent")),
            "regular_upload_sent": bool(self._state.get("regular_upload_sent")),
            "state": self._runtime_state,
            "last_success_at": self._state.get("last_success_at"),
            "last_attempt_at": self._state.get("last_attempt_at"),
            "consecutive_failures": self._safe_failure_count(self._state.get("consecutive_failures")),
            "next_retry_at": self._state.get("next_retry_at"),
            "last_status_code": self._state.get("last_status_code"),
            "last_error_type": self._state.get("last_error_type"),
            "last_batch_id": self._state.get("last_batch_id"),
            "last_chunk_id": self._state.get("last_chunk_id"),
            "last_record_cursor": self._state.get("last_record_cursor"),
            "last_batch_record_count": self._state.get("last_batch_record_count"),
            "last_batch_chunk_count": self._state.get("last_batch_chunk_count"),
            "client_context_enabled": bool(self.entry.options.get("diagnostics_include_client_context", False)),
        }

    async def async_start(self) -> None:
        if self._started:
            return
        try:
            stored = await self._store.async_load()
        except Exception:  # noqa: BLE001 - telemetry persistence must never block FreshAirIQ
            stored = None
            _LOGGER.debug("Could not load FreshAirIQ diagnostics-upload state", exc_info=True)
        self._state = dict(stored) if isinstance(stored, dict) else {}
        self._started = True
        self._runtime_state = "idle"
        self._unsub = async_track_time_interval(self.hass, self._schedule_check, _CHECK_INTERVAL)
        self._schedule_check(dt_util.now())

    async def async_stop(self) -> None:
        self._started = False
        if self._unsub:
            self._unsub()
            self._unsub = None
        task = self._task
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._task = None
        await self._save_state()
        self._runtime_state = "stopped"

    @callback
    def _schedule_check(self, _now: datetime) -> None:
        if not self._started or (self._task and not self._task.done()):
            return
        self._task = self.hass.async_create_task(self.async_maybe_upload())

    @callback
    def request_check(self) -> None:
        """Request a non-blocking upload check after a live option change."""
        self._schedule_check(dt_util.now())

    def _health(self) -> Mapping[str, Any]:
        try:
            value = self.health_provider()
        except Exception:  # noqa: BLE001 - diagnostics must never affect FreshAirIQ runtime
            return {}
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError):
            return None

    async def _save_state(self) -> bool:
        try:
            await self._store.async_save(dict(self._state))
        except Exception:  # noqa: BLE001 - telemetry persistence is strictly non-critical
            _LOGGER.debug("Could not persist FreshAirIQ diagnostics-upload state", exc_info=True)
            return False
        return True

    async def _async_cpu_job(self, func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        """Run diagnostics CPU work away from the Home Assistant event loop.

        Home Assistant exposes ``async_add_executor_job`` for this purpose. The
        ``asyncio.to_thread`` fallback keeps standalone unit tests and defensive
        non-HA execution safe without changing production behaviour.
        """
        job = partial(func, *args, **kwargs)
        executor = getattr(self.hass, "async_add_executor_job", None)
        if callable(executor):
            return await executor(job)
        return await asyncio.to_thread(job)

    async def _async_client_token(self) -> str:
        """Return the persistent installation credential used by the Hub.

        The token is saved *before* enrollment. This prevents a successful
        server-side enrollment from becoming unrecoverable if Home Assistant
        restarts between enrollment and the first diagnostic chunk. The token is
        never exposed through ``status`` or the diagnostic payload.
        """
        existing = self._state.get("client_token")
        if isinstance(existing, str) and 32 <= len(existing) <= 256:
            return existing
        token = secrets.token_urlsafe(48)
        self._state["client_token"] = token
        self._state["hub_enrolled"] = False
        if not await self._save_state():
            self._state.pop("client_token", None)
            raise RuntimeError("hub_credential_persistence_failed")
        return token

    async def _async_ensure_enrolled(
        self,
        session: Any,
        installation_id: str,
        timeout: ClientTimeout,
        *,
        force: bool = False,
    ) -> str:
        """Enroll this anonymous installation idempotently and return its token."""
        token = await self._async_client_token()
        if self._state.get("hub_enrolled") and not force:
            return token

        body = json.dumps(
            {
                "anonymous_installation_id": installation_id,
                "client_token": token,
                "upload_schema_version": 2,
                "freshairiq_version": VERSION,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"FreshAirIQ/{VERSION}",
        }
        self._runtime_state = "enrolling"
        async with session.post(self.enroll_endpoint, data=body, headers=headers, timeout=timeout) as response:
            status = int(response.status)
            self._state["last_status_code"] = status
            if status < 200 or status >= 300:
                raise RuntimeError(f"hub_enroll_http_{status}")
        self._state["hub_enrolled"] = True
        self._state["last_enrolled_at"] = dt_util.now().isoformat()
        await self._save_state()
        return token

    async def _async_post_chunk(
        self,
        session: Any,
        *,
        compressed: bytes,
        chunk: Mapping[str, Any],
        token: str,
        installation_id: str,
        timeout: ClientTimeout,
    ) -> int:
        """Upload one chunk, re-enrolling once after an authentication loss."""
        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
                "Accept": "application/json",
                "User-Agent": f"FreshAirIQ/{VERSION}",
                "X-FreshAirIQ-Upload-Schema": str(chunk.get("upload_schema_version") or 1),
                "X-FreshAirIQ-Batch-ID": str(chunk.get("batch_id") or ""),
                "X-FreshAirIQ-Chunk-ID": str(chunk.get("chunk_id") or ""),
                "X-FreshAirIQ-Chunk-Index": str(chunk.get("chunk_index") or 0),
                "X-FreshAirIQ-Chunk-Count": str(chunk.get("chunk_count") or 1),
                "Idempotency-Key": str(chunk.get("chunk_id") or ""),
            }
            async with session.post(self.upload_endpoint, data=compressed, headers=headers, timeout=timeout) as response:
                status = int(response.status)
                self._state["last_status_code"] = status
            if status != 401 or attempt:
                return status
            # A Hub database restore/reset can forget enrollments while the HA
            # client still has its credential. Re-enroll the same persisted
            # token exactly once and retry the same idempotent chunk.
            self._state["hub_enrolled"] = False
            await self._save_state()
            token = await self._async_ensure_enrolled(
                session, installation_id, timeout, force=True
            )
        return status

    async def async_submit_feedback(self, feedback_type: str, message: str, *, client_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Submit explicit user-authored feedback to the configured diagnostics Hub."""
        kind = str(feedback_type or "").strip()
        text = str(message or "").strip()
        if kind not in {"bug", "improvement", "other"}:
            raise ValueError("feedback_type_invalid")
        if not 3 <= len(text) <= 10000:
            raise ValueError("feedback_message_invalid")
        if not self.endpoint:
            raise RuntimeError("hub_unconfigured")
        identity = await self.recorder.async_get_identity()
        installation_id = str(identity.get("installation_id") or "")
        if not installation_id:
            raise RuntimeError("identity_unavailable")
        session = async_get_clientsession(self.hass)
        timeout = ClientTimeout(total=DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)
        token = await self._async_ensure_enrolled(session, installation_id, timeout)
        try:
            from homeassistant.const import __version__ as ha_version
        except (ImportError, AttributeError):
            ha_version = None
        payload = {"feedback_type": kind, "message": text, "freshairiq_version": VERSION, "home_assistant_version": ha_version, "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION}
        safe_client = {}
        if isinstance(client_context, Mapping):
            # Allow-list only anonymous UI compatibility fields. Never forward
            # raw UA, exact model, device name, serial, IP/network data or stable IDs.
            allowed = {"platform_family", "device_class", "companion_app", "companion_app_version", "browser_family", "webview_engine_version", "viewport_css_px", "device_pixel_ratio"}
            safe_client = {str(k): v for k, v in client_context.items() if k in allowed}
            if safe_client:
                payload["client_context"] = safe_client
        headers = {"Authorization": f"Bearer {token}", "Content-Type":"application/json", "Accept":"application/json", "User-Agent":f"FreshAirIQ/{VERSION}"}
        async with session.post(f"{self.endpoint}/v1/feedback", json=payload, headers=headers, timeout=timeout) as response:
            # Compatibility fallback for an older Hub that does not yet accept
            # the optional anonymous client_context field. Feedback itself must
            # never be lost because Hub and integration were updated separately.
            if response.status in {400, 422} and "client_context" in payload:
                legacy_payload = dict(payload)
                legacy_payload.pop("client_context", None)
                async with session.post(f"{self.endpoint}/v1/feedback", json=legacy_payload, headers=headers, timeout=timeout) as legacy:
                    if 200 <= legacy.status < 300:
                        result = await legacy.json()
                        if isinstance(result, dict): result["client_context_accepted"] = False
                        return result
            if response.status == 401:
                self._state["hub_enrolled"] = False; await self._save_state()
                token = await self._async_ensure_enrolled(session, installation_id, timeout, force=True)
                headers["Authorization"] = f"Bearer {token}"
                async with session.post(f"{self.endpoint}/v1/feedback", json=payload, headers=headers, timeout=timeout) as retry:
                    if retry.status < 200 or retry.status >= 300: raise RuntimeError(f"feedback_http_{retry.status}")
                    return await retry.json()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"feedback_http_{response.status}")
            return await response.json()

    async def async_maybe_upload(self, *, force: bool = False) -> bool:
        """Upload once if the opt-in cadence is due.

        Returns ``True`` only after the hub accepted the payload.  Every failure
        is isolated from the coordinator and kept as a coarse error type only.
        """
        mode = normalise_reporting_mode(self.entry.options.get("diagnostics_reporting_mode", "off"))
        if mode == "off":
            self._runtime_state = "disabled"
            return False
        if not self.endpoint:
            self._runtime_state = "hub_unconfigured"
            return False

        now = dt_util.now()
        next_retry = self._parse_dt(self._state.get("next_retry_at"))
        if next_retry is not None:
            if now.tzinfo is not None and next_retry.tzinfo is None:
                next_retry = next_retry.replace(tzinfo=now.tzinfo)
            elif now.tzinfo is None and next_retry.tzinfo is not None:
                next_retry = next_retry.replace(tzinfo=None)
            if now < next_retry and not force:
                self._runtime_state = "backoff"
                return False

        health = self._health()
        current_problem = problem_fingerprint(health)
        identity = await self.recorder.async_get_identity()
        installation_id = str(identity.get("installation_id") or "")
        if not installation_id:
            self._runtime_state = "identity_unavailable"
            return False
        first_sync_due = not self._state.get("last_success_at") and (
            mode in {"daily", "weekly"} or current_problem is not None
        )
        if not force and not first_sync_due and not upload_due(
            mode,
            now,
            installation_id,
            last_success_at=self._state.get("last_success_at"),
            problem_fingerprint=current_problem,
            last_problem_fingerprint=self._state.get("last_problem_fingerprint"),
        ):
            self._runtime_state = "waiting"
            return False

        self._runtime_state = "preparing"
        self._state["last_attempt_at"] = now.isoformat()
        await self._save_state()
        try:
            session = async_get_clientsession(self.hass)
            timeout = ClientTimeout(total=DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)
            # Authenticate before doing the relatively expensive 30-day export
            # and chunk build. An unreachable Hub therefore fails fast without
            # spending several seconds on diagnostics preparation.
            token = await self._async_ensure_enrolled(session, installation_id, timeout)
            exported = await self.recorder.async_export()
            chunks = await self._async_cpu_job(
                build_upload_chunks,
                exported,
                include_client_context=bool(self.entry.options.get("diagnostics_include_client_context", False)),
                after_cursor=self._state.get("last_record_cursor"),
                max_chunk_bytes=self.max_chunk_bytes,
            )

            self._runtime_state = "uploading"
            total_records = sum(len(chunk.get("records") or []) for chunk in chunks)
            for chunk in chunks:
                compressed = await self._async_cpu_job(_encode_chunk_for_upload, chunk)
                status = await self._async_post_chunk(
                    session,
                    compressed=compressed,
                    chunk=chunk,
                    token=token,
                    installation_id=installation_id,
                    timeout=timeout,
                )
                if status < 200 or status >= 300:
                    raise RuntimeError(f"hub_http_{status}")

                # Persist progress after every acknowledged chunk. If a later
                # chunk fails, the next retry resumes after this cursor instead
                # of retransmitting the already acknowledged 30-day history.
                if chunk.get("cursor_after"):
                    self._state["last_record_cursor"] = chunk.get("cursor_after")
                self._state.update({
                    "last_batch_id": chunk.get("batch_id"),
                    "last_chunk_id": chunk.get("chunk_id"),
                    "last_payload_sha256": chunk.get("content_sha256"),
                })
                await self._save_state()

            self._state.update({
                "last_success_at": now.isoformat(),
                "last_problem_fingerprint": current_problem,
                "last_batch_record_count": total_records,
                "last_batch_chunk_count": len(chunks),
                "initial_snapshot_sent": bool(self._state.get("initial_snapshot_sent")) or any(bool(c.get("initial_snapshot")) for c in chunks),
                "regular_upload_sent": bool(self._state.get("regular_upload_sent")) or any(not bool(c.get("initial_snapshot")) for c in chunks),
                "consecutive_failures": 0,
                "next_retry_at": None,
                "last_error_type": None,
            })
            self._runtime_state = "sent"
            await self._save_state()
            return True
        except asyncio.CancelledError:
            raise
        except (ClientError, TimeoutError, RuntimeError, ValueError, TypeError, OSError) as err:
            failures = self._safe_failure_count(self._state.get("consecutive_failures")) + 1
            delay = retry_delay_seconds(failures)
            self._state.update({
                "consecutive_failures": failures,
                "next_retry_at": (now + timedelta(seconds=delay)).isoformat(),
                "last_error_type": type(err).__name__,
            })
            self._runtime_state = "error"
            await self._save_state()
            _LOGGER.debug("FreshAirIQ diagnostics upload failed safely: %s", type(err).__name__)
            return False
