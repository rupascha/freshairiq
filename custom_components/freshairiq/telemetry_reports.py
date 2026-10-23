"""Diagnostics client reports: user feedback, frontend client errors and support diagnostics."""
from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Mapping

from aiohttp import ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    DIAGNOSTICS_SCHEMA_VERSION,
    DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS,
    SUPPORT_DIAGNOSTICS_COOLDOWN_SECONDS,
    SUPPORT_DIAGNOSTICS_MESSAGE_MAX_CHARS,
    SUPPORT_DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS,
    VERSION,
)
from .cooldown import (
    FEEDBACK_COOLDOWN_SECONDS,
    cooldown_result,
    hub_retry_after,
    remaining_seconds,
    started_cooldown,
)
from .runtime_health import HEALTH_CONTRACT_VERSION
from .telemetry_hub import _encode_chunk_for_upload


class TelemetryReportsMixin:
    """Diagnostics client reports: user feedback, frontend client errors and support diagnostics."""

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
        # 0.26.4.10 (to-do "Feedback alle 15min"): one feedback per 15 minutes.
        now = dt_util.now()
        left = remaining_seconds(self._state.get("feedback_cooldown_until"), now)
        if left:
            return cooldown_result(left, now)
        result = await self._async_post_feedback(kind, text, client_context)
        if isinstance(result, dict) and result.get("reason") == "cooldown":
            self._state["feedback_cooldown_until"] = result["cooldown_until"]
            await self._save_state()
            return result
        until = started_cooldown(now)
        self._state["feedback_cooldown_until"] = until
        await self._save_state()
        out = dict(result) if isinstance(result, dict) else {}
        out.update({"cooldown_until": until, "cooldown_seconds": FEEDBACK_COOLDOWN_SECONDS})
        return out

    async def _async_post_feedback(self, kind: str, text: str, client_context: Mapping[str, Any] | None) -> dict[str, Any]:
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
            if response.status == 429:
                try:
                    body = await response.json()
                except Exception:  # noqa: BLE001 - an unreadable 429 still means "later"
                    body = None
                return cooldown_result(hub_retry_after(body) or FEEDBACK_COOLDOWN_SECONDS, dt_util.now())
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
