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
from pathlib import Path
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
    SUPPORT_DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS,
    SUPPORT_DIAGNOSTICS_COOLDOWN_SECONDS,
    SUPPORT_DIAGNOSTICS_MESSAGE_MAX_CHARS,
    DOMAIN,
    VERSION,
)
from .runtime_health import HEALTH_CONTRACT_VERSION
from .diagnostic_transport import (
    build_upload_chunks,
    effective_reporting_mode,
    normalise_consent,
    normalise_reporting_mode,
    problem_fingerprint,
    retry_delay_seconds,
    upload_due,
)

_LOGGER = logging.getLogger(__name__)
_STORE_VERSION = 1
_CHECK_INTERVAL = timedelta(minutes=15)
_INITIAL_UPLOAD_GRACE = timedelta(minutes=30)
_ACTIVITY_HEARTBEAT_INTERVAL = timedelta(hours=6)
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
        health_snapshot_provider: Callable[[datetime], Mapping[str, Any]] | None = None,
        max_chunk_bytes: int = DIAGNOSTICS_UPLOAD_MAX_BYTES,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.recorder = recorder
        self.endpoint = _normalise_hub_base(endpoint)
        self.enroll_endpoint = f"{self.endpoint}/v1/enroll" if self.endpoint else ""
        self.upload_endpoint = f"{self.endpoint}/v1/diagnostics/chunks" if self.endpoint else ""
        self.health_provider = health_provider or (lambda: {})
        self.health_snapshot_provider = health_snapshot_provider
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
        mode = effective_reporting_mode(dict(self.entry.options))
        return {
            "reporting_mode": mode,
            "configured_reporting_mode": normalise_reporting_mode(self.entry.options.get("diagnostics_reporting_mode", "daily")),
            "consent": normalise_consent(self.entry.options.get("diagnostics_consent")),
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
            "client_context_enabled": bool(self.entry.options.get("diagnostics_include_client_context", True)),
            "support_last_success_at": self._state.get("support_last_success_at"),
            "support_cooldown_until": self._state.get("support_cooldown_until"),
            "support_last_case_id": self._state.get("support_last_case_id"),
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
        if not self._state and not self._state.get("diagnostics_first_seen_at"):
            self._state["diagnostics_first_seen_at"] = dt_util.now().isoformat()
            await self._save_state()
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
        self._task = self.hass.async_create_task(self._async_periodic_check())

    @callback
    def request_check(self) -> None:
        """Request a non-blocking upload check after a live option change."""
        self._schedule_check(dt_util.now())

    async def _async_periodic_check(self) -> bool:
        """Run the privacy-safe activity heartbeat before the diagnostics cadence check."""
        await self.async_activity_heartbeat()
        return await self.async_maybe_upload()

    async def async_activity_heartbeat(self) -> bool:
        """Refresh anonymous installation activity without sending diagnostics payload."""
        mode = normalise_reporting_mode(self.entry.options.get("diagnostics_reporting_mode", "daily"))
        if mode == "off":
            return False
        if not self.endpoint:
            return False
        # 0.26.3: even the minimal heartbeat (installation id + version) contacts the
        # hub and enrolls the installation, so it needs the same explicit consent.
        if normalise_consent(self.entry.options.get("diagnostics_consent")) != "granted":
            self._runtime_state = "disabled"
            return False
        # GitHub #10: automatic diagnostics switched off means no heartbeat either.
        if normalise_reporting_mode(self.entry.options.get("diagnostics_reporting_mode", "daily")) == "off":
            self._runtime_state = "disabled"
            return False
        now = dt_util.now()
        last = self._parse_dt(self._state.get("last_activity_heartbeat_at"))
        if last is not None:
            if now.tzinfo is not None and last.tzinfo is None: last = last.replace(tzinfo=now.tzinfo)
            elif now.tzinfo is None and last.tzinfo is not None: last = last.replace(tzinfo=None)
            if now - last < _ACTIVITY_HEARTBEAT_INTERVAL:
                return False
        identity = await self.recorder.async_get_identity()
        installation_id = str(identity.get("installation_id") or "")
        if not installation_id:
            return False
        session = async_get_clientsession(self.hass)
        timeout = ClientTimeout(total=DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)
        try:
            token = await self._async_ensure_enrolled(session, installation_id, timeout)
            activity_url = f"{self.endpoint}/v1/activity"
            payload = {
                "anonymous_installation_id": installation_id,
                "client_token": token,
                "upload_schema_version": 2,
                "freshairiq_version": VERSION,
            }
            async with session.post(
                activity_url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            ) as response:
                if response.status >= 400:
                    raise RuntimeError(f"activity_http_{response.status}")
        except (ClientError, TimeoutError, RuntimeError, ValueError, TypeError, OSError):
            _LOGGER.debug("FreshAirIQ activity heartbeat failed", exc_info=True)
            return False
        self._state["last_activity_heartbeat_at"] = now.isoformat()
        await self._save_state()
        return True

    def _health(self) -> Mapping[str, Any]:
        try:
            value = self.health_provider()
        except Exception:  # noqa: BLE001 - diagnostics must never affect FreshAirIQ runtime
            return {}
        return value if isinstance(value, Mapping) else {}

    def _health_snapshot(self, now: datetime) -> Mapping[str, Any]:
        """Return an explicit point-in-time health snapshot for support sends."""
        if self.health_snapshot_provider is None:
            return dict(self._health())
        try:
            value = self.health_snapshot_provider(now)
        except Exception:  # noqa: BLE001 - diagnostics must never affect FreshAirIQ runtime
            return dict(self._health())
        return value if isinstance(value, Mapping) else dict(self._health())

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

    def _candidate_persisted_client_tokens(self) -> list[str]:
        """Return other locally persisted diagnostics tokens for this HA instance.

        The anonymous installation identity is shared across FreshAirIQ config
        entries, while older releases stored the Hub credential per config entry.
        A second/recreated entry could therefore hit HTTP 409 although this Home
        Assistant instance still owns the original credential.
        """
        storage = Path(self.hass.config.path(".storage"))
        current = str(self._state.get("client_token") or "")
        found: list[str] = []
        for path in storage.glob(f"{DOMAIN}.diagnostics_upload.*"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeError):
                continue
            data = raw.get("data") if isinstance(raw, dict) else None
            token = str((data or {}).get("client_token") or "") if isinstance(data, dict) else ""
            if len(token) >= 32 and token != current and token not in found:
                found.append(token)
        return found

    async def _async_recover_enrollment_token(self, session: Any, installation_id: str, timeout: ClientTimeout) -> str | None:
        """Adopt a locally owned legacy credential that the Hub already knows."""
        candidates = await self.hass.async_add_executor_job(self._candidate_persisted_client_tokens)
        for token in candidates:
            body = json.dumps({
                "anonymous_installation_id": installation_id,
                "client_token": token,
                "upload_schema_version": 2,
                "freshairiq_version": VERSION,
            }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers = {"Content-Type":"application/json","Accept":"application/json","User-Agent":f"FreshAirIQ/{VERSION}"}
            try:
                async with session.post(self.enroll_endpoint, data=body, headers=headers, timeout=timeout) as response:
                    if 200 <= int(response.status) < 300:
                        self._state["client_token"] = token
                        self._state["hub_enrolled"] = True
                        self._state["last_enrolled_at"] = dt_util.now().isoformat()
                        self._state["enrollment_recovered_from_local_credential"] = True
                        await self._save_state()
                        return token
            except (ClientError, TimeoutError, OSError):
                continue
        return None

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
            if status == 409:
                recovered = await self._async_recover_enrollment_token(session, installation_id, timeout)
                if recovered is not None:
                    return recovered
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

    def _client_error_payload(self, *, code: str, component: str, operation: str, message: str) -> dict[str, Any]:
        """Build the bounded privacy-safe payload used by live and deferred error reports."""
        import hashlib
        normalized = f"{code}|{component}|{operation}|{str(message)[:500]}"
        fingerprint = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()
        return {"code":str(code)[:80],"component":str(component)[:80],"operation":str(operation)[:120],"message":str(message)[:2000],"fingerprint":fingerprint,"freshairiq_version":VERSION}

    async def _async_flush_client_error_queue(self, session, headers: Mapping[str, str], timeout: ClientTimeout) -> None:
        """Best-effort delivery of locally retained errors after Hub connectivity recovers."""
        queued=[item for item in list(self._state.get("client_error_queue") or []) if isinstance(item, dict)]
        if not queued:
            return
        self._state["client_error_queue"]=[]; await self._save_state()
        for old in queued[:50]:
            try:
                async with session.post(f"{self.endpoint}/v1/client-errors",json=old,headers=headers,timeout=timeout) as retry:
                    if not 200 <= retry.status < 300: raise RuntimeError("retry_failed")
            except Exception:
                await self._async_queue_client_error(old)

    async def async_report_client_error(self, *, code: str, component: str, operation: str, message: str) -> dict[str, Any]:
        """Report a privacy-safe error and persist a bounded retry queue on transport failure."""
        payload=self._client_error_payload(code=code, component=component, operation=operation, message=message)
        if not self.endpoint:
            await self._async_queue_client_error(payload); raise RuntimeError("hub_unconfigured")
        identity = await self.recorder.async_get_identity(); installation_id = str(identity.get("installation_id") or "")
        if not installation_id:
            await self._async_queue_client_error(payload); raise RuntimeError("identity_unavailable")
        session = async_get_clientsession(self.hass); timeout = ClientTimeout(total=DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)
        try:
            from homeassistant.const import __version__ as ha_version
        except (ImportError, AttributeError):
            ha_version = None
        payload["home_assistant_version"] = ha_version
        try:
            token = await self._async_ensure_enrolled(session, installation_id, timeout)
            headers={"Authorization":f"Bearer {token}","Content-Type":"application/json","Accept":"application/json","User-Agent":f"FreshAirIQ/{VERSION}"}
            async with session.post(f"{self.endpoint}/v1/client-errors",json=payload,headers=headers,timeout=timeout) as response:
                if not 200 <= response.status < 300: raise RuntimeError(f"client_error_http_{response.status}")
                result=await response.json()
            # A successful path may opportunistically flush queued errors; failure to
            # flush never changes the successful current report.
            await self._async_flush_client_error_queue(session, headers, timeout)
            return result
        except Exception:
            await self._async_queue_client_error(payload)
            raise

    async def _async_queue_client_error(self, payload: Mapping[str, Any]) -> None:
        queue=[item for item in list(self._state.get("client_error_queue") or []) if isinstance(item, dict)]
        fingerprint=str(payload.get("fingerprint") or "")
        if fingerprint and any(str(item.get("fingerprint") or "") == fingerprint for item in queue):
            return
        queue.append(dict(payload)); self._state["client_error_queue"]=queue[-50:]; await self._save_state()

    async def async_submit_support_diagnostics(self, message: str = "") -> dict[str, Any]:
        """Send an explicit, user-requested detailed support diagnostic bundle.

        This path is deliberately separate from automatic telemetry. A successful
        Hub acknowledgement starts a persisted 60-minute cooldown. Failed sends
        never consume the cooldown.
        """
        text = str(message or "").strip()
        if len(text) > SUPPORT_DIAGNOSTICS_MESSAGE_MAX_CHARS:
            raise ValueError("support_message_too_long")
        if not self.endpoint:
            payload=self._client_error_payload(code="FAIQ-SUPPORT-UPLOAD-001", component="support_diagnostics", operation="submit_support_diagnostics", message="RuntimeError: hub_unconfigured")
            await self._async_queue_client_error(payload)
            raise RuntimeError("hub_unconfigured")
        now = dt_util.now()
        cooldown_until = self._parse_dt(self._state.get("support_cooldown_until"))
        if cooldown_until is not None:
            if now.tzinfo is not None and cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=now.tzinfo)
            elif now.tzinfo is None and cooldown_until.tzinfo is not None:
                cooldown_until = cooldown_until.replace(tzinfo=None)
            if now < cooldown_until:
                remaining = max(1, int((cooldown_until - now).total_seconds()))
                return {"accepted": False, "reason": "cooldown", "retry_after_seconds": remaining,
                        "cooldown_until": cooldown_until.isoformat()}

        try:
            identity = await self.recorder.async_get_identity()
            installation_id = str(identity.get("installation_id") or "")
            if not installation_id:
                raise RuntimeError("identity_unavailable")
            session = async_get_clientsession(self.hass)
            timeout = ClientTimeout(total=SUPPORT_DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)
            token = await self._async_ensure_enrolled(session, installation_id, timeout)
            exported = await self.recorder.async_export()
            case_id = f"support-{secrets.token_hex(12)}"
        except Exception as err:
            detail = str(err) if isinstance(err, RuntimeError) and str(err) in {"identity_unavailable", "hub_unconfigured"} else type(err).__name__
            payload=self._client_error_payload(code="FAIQ-SUPPORT-UPLOAD-001", component="support_diagnostics", operation="submit_support_diagnostics", message=f"{type(err).__name__}: {detail}")
            await self._async_queue_client_error(payload)
            raise
        envelope = {
            "support_schema_version": 2,
            "health_contract_version": HEALTH_CONTRACT_VERSION,
            "support_case_id": case_id,
            "submitted_at": now.isoformat(),
            "anonymous_installation_id": installation_id,
            "freshairiq_version": VERSION,
            "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "user_message": text,
            "health_snapshot": dict(self._health_snapshot(now)),
            "diagnostics": exported,
        }
        headers = {
            "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            "Content-Encoding": "gzip", "Accept": "application/json",
            "User-Agent": f"FreshAirIQ/{VERSION}", "X-FreshAirIQ-Support-Schema": "2",
            "X-FreshAirIQ-Health-Contract": str(HEALTH_CONTRACT_VERSION),
            "X-FreshAirIQ-Support-Case-ID": case_id, "Idempotency-Key": case_id,
        }
        try:
            compressed = await self._async_cpu_job(_encode_chunk_for_upload, envelope)
            async with session.post(f"{self.endpoint}/v1/support/diagnostics", data=compressed,
                                    headers=headers, timeout=timeout) as response:
                status = int(response.status)
                if status == 401:
                    self._state["hub_enrolled"] = False
                    await self._save_state()
                    token = await self._async_ensure_enrolled(session, installation_id, timeout, force=True)
                    headers["Authorization"] = f"Bearer {token}"
                    async with session.post(f"{self.endpoint}/v1/support/diagnostics", data=compressed,
                                            headers=headers, timeout=timeout) as retry:
                        status = int(retry.status)
                        if status < 200 or status >= 300:
                            raise RuntimeError(f"support_diagnostics_http_{status}")
                elif status < 200 or status >= 300:
                    raise RuntimeError(f"support_diagnostics_http_{status}")
        except Exception as err:
            detail = str(err) if isinstance(err, RuntimeError) and str(err).startswith("support_diagnostics_http_") else type(err).__name__
            payload=self._client_error_payload(code="FAIQ-SUPPORT-UPLOAD-001", component="support_diagnostics", operation="submit_support_diagnostics", message=f"{type(err).__name__}: {detail}")
            await self._async_queue_client_error(payload)
            raise
        await self._async_flush_client_error_queue(session, headers, timeout)
        cooldown = now + timedelta(seconds=SUPPORT_DIAGNOSTICS_COOLDOWN_SECONDS)
        self._state.update({"support_last_success_at": now.isoformat(),
                            "support_cooldown_until": cooldown.isoformat(),
                            "support_last_case_id": case_id})
        await self._save_state()
        return {"accepted": True, "support_case_id": case_id,
                "cooldown_until": cooldown.isoformat(),
                "cooldown_seconds": SUPPORT_DIAGNOSTICS_COOLDOWN_SECONDS}

    async def async_maybe_upload(self, *, force: bool = False, manual: bool = False) -> bool:
        """Upload once if the opt-in cadence is due.

        Returns ``True`` only after the hub accepted the payload.  Every failure
        is isolated from the coordinator and kept as a coarse error type only.
        """
        # Scheduled uploads require explicit consent (0.26.3); an explicit manual send is separate consent.
        mode = effective_reporting_mode(dict(self.entry.options))
        if mode == "off" and not manual:
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

        # Register the anonymous installation immediately once reporting is due,
        # but deliberately keep diagnostic/device payloads out of the Hub during
        # the first 30 minutes of a brand-new installation.
        session = async_get_clientsession(self.hass)
        timeout = ClientTimeout(total=DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS)
        try:
            await self._async_ensure_enrolled(session, installation_id, timeout)
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
            return False
        first_seen = self._parse_dt(self._state.get("diagnostics_first_seen_at"))
        if not force and not self._state.get("last_success_at") and first_seen is not None:
            if now.tzinfo is not None and first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=now.tzinfo)
            elif now.tzinfo is None and first_seen.tzinfo is not None:
                first_seen = first_seen.replace(tzinfo=None)
            if now < first_seen + _INITIAL_UPLOAD_GRACE:
                self._runtime_state = "onboarding_grace"
                return False

        self._runtime_state = "preparing"
        self._state["last_attempt_at"] = now.isoformat()
        await self._save_state()
        try:
            # Enrollment already happened before the onboarding grace gate.
            # Reusing the persistent token here keeps installation registration
            # and diagnostic upload as two separate lifecycle stages.
            token = await self._async_client_token()
            exported = await self.recorder.async_export()
            chunks = await self._async_cpu_job(
                build_upload_chunks,
                exported,
                include_client_context=bool(self.entry.options.get("diagnostics_include_client_context", True)),
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

            error_headers={"Authorization":f"Bearer {token}","Content-Type":"application/json","Accept":"application/json","User-Agent":f"FreshAirIQ/{VERSION}"}
            await self._async_flush_client_error_queue(session, error_headers, timeout)

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
