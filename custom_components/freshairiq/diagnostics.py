"""Privacy-conscious rolling diagnostics recorder for FreshAirIQ.

The recorder deliberately stores calculated FreshAirIQ state instead of raw
Home Assistant entity identifiers. Files are kept as daily JSONL chunks under
``.storage/freshairiq_diagnostics`` and are exported through an authenticated
Home Assistant API view.
"""
from __future__ import annotations

from copy import deepcopy

import hashlib
import json
import platform
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .runtime import iter_runtime_coordinators
from .const import DIAGNOSTICS_SCHEMA_VERSION
from .diagnostic_transport import normalise_resident_names
from .export_zip import export_filename, zip_json_document
from .support_incident import build_support_incident
# The recorder is split into the diagnostics_* modules; every name that used to live here
# stays importable from this module.
from .diagnostics_limits import DIAGNOSTICS_IDENTITY_SCHEMA_VERSION, DIAGNOSTICS_IDENTITY_FILENAME, DIAGNOSTICS_CLIENTS_FILENAME, DIAGNOSTICS_MAX_CLIENTS, DIAGNOSTICS_RETENTION_DAYS, DIAGNOSTICS_INTERVAL_SECONDS, DIAGNOSTICS_IDLE_INTERVAL_SECONDS, DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS, DIAGNOSTICS_MAX_EXPORT_RECORDS, DIAGNOSTICS_MAX_EXPORT_BYTES, DIAGNOSTICS_MAX_TOTAL_BYTES  # noqa: F401 - re-exported
from .diagnostics_privacy import _SAFE_OPTION_KEYS, _collection_size, _latest_evidence, _compact_learning_components, _safe_int, _json_safe, _sha256_json, _bounded_text, _sanitise_client_context, _runtime_environment_snapshot, _longest_consecutive_day_streak, _privacy_safe_decision, _privacy_safe_iq_state, _pick, _three_state_learning_diagnostic, _TOP_LEVEL_KEYS, _ROOM_KEYS, _LEARNING_ROOM_KEYS, _TREND_TOP_LEVEL_KEYS, _TREND_ROOM_KEYS  # noqa: F401 - re-exported
from .diagnostics_records import DiagnosticsRecordsMixin
from .diagnostics_export import DiagnosticsExportMixin


class FreshAirIQDiagnosticsRecorder(DiagnosticsExportMixin, DiagnosticsRecordsMixin):
    """Record a rolling, anonymised diagnostic trace."""

    def _notifications_configured(self) -> bool:
        """True when push messages are enabled and at least one target exists (no IDs exported)."""
        try:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            options = dict(entry.options) if entry is not None else {}
            from .notifications import _has_notification_targets
            return bool(options.get("notifications_enabled")) and bool(_has_notification_targets(options))
        except Exception:  # diagnostics must never fail because of this hint
            return False

    def __init__(self, hass: HomeAssistant, entry_id: str, version: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.version = version
        self.directory = Path(hass.config.path(".storage", "freshairiq_diagnostics"))
        self._last_recorded_at: datetime | None = None
        self._last_signature: str | None = None
        self._last_cleanup_at: datetime | None = None
        self.last_error: str | None = None
        self.record_count_session = 0
        self._last_room_active: dict[str, bool] = {}
        self._last_room_opened_at: dict[str, str] = {}
        self._config_snapshot: dict[str, Any] = {}
        self._config_signature: str | None = None
        self._configuration_changed = False
        self._legacy_compaction_mtime_ns: dict[str, int] = {}
        self._last_export_client: dict[str, Any] = {}
        self._notification_delivery_snapshot: list[dict[str, Any]] = []
        self._field_test_storage_lock = Lock()

    @property
    def _identity_path(self) -> Path:
        return self.directory / DIAGNOSTICS_IDENTITY_FILENAME

    @property
    def _clients_path(self) -> Path:
        return self.directory / DIAGNOSTICS_CLIENTS_FILENAME

    def _load_or_create_field_test_identity(self, now: datetime) -> dict[str, Any]:
        """Load or atomically create the stable anonymous installation identity."""
        with self._field_test_storage_lock:
            return self._load_or_create_field_test_identity_unlocked(now)

    def _load_or_create_field_test_identity_unlocked(self, now: datetime) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        identity: dict[str, Any] = {}
        identity_status = "existing"
        if self._identity_path.exists():
            try:
                raw = json.loads(self._identity_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    identity = raw
                else:
                    identity_status = "recreated_invalid_identity"
            except (OSError, json.JSONDecodeError):
                identity_status = "recreated_invalid_identity"

        installation_id = str(identity.get("installation_id") or "")
        if not installation_id.startswith("faiq-install-"):
            installation_id = f"faiq-install-{uuid4().hex}"
            # A broken identity file stays reported as such (A-22); only a missing
            # or empty identity counts as newly created.
            if identity_status != "recreated_invalid_identity":
                identity_status = "created" if not identity else "recreated_invalid_identity"
        created_at = identity.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            created_at = now.isoformat()
        export_sequence = _safe_int(identity.get("export_sequence"), 0, low=0, high=10_000_000) + 1
        persisted = {
            "identity_schema_version": DIAGNOSTICS_IDENTITY_SCHEMA_VERSION,
            "installation_id": installation_id,
            "created_at": created_at,
            "export_sequence": export_sequence,
            "last_exported_at": now.isoformat(),
        }
        tmp = self._identity_path.with_suffix(self._identity_path.suffix + ".tmp")
        tmp.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self._identity_path)
        entry_fingerprint = hashlib.sha256(f"{installation_id}|{self.entry_id}".encode("utf-8")).hexdigest()[:24]
        return {**persisted, "identity_status": identity_status, "entry_fingerprint": entry_fingerprint}

    def _load_field_test_clients(self) -> list[dict[str, Any]]:
        if not self._clients_path.exists():
            return []
        raw = json.loads(self._clients_path.read_text(encoding="utf-8"))
        rows = raw.get("clients") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)][-DIAGNOSTICS_MAX_CLIENTS:]

    def _register_client_sync(self, context: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Persist one anonymous dashboard client without raw UA or device names."""
        with self._field_test_storage_lock:
            return self._register_client_sync_unlocked(context, now)

    def _register_client_sync_unlocked(self, context: dict[str, Any], now: datetime) -> dict[str, Any]:
        safe = _sanitise_client_context(context)
        if not safe:
            return {"registered": False, "reason": "invalid_client_context"}
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            clients = self._load_field_test_clients()
        except (OSError, json.JSONDecodeError):
            clients = []
        client_id = safe["client_id"]
        existing = next((row for row in clients if row.get("client_id") == client_id), None)
        if existing is None:
            existing = {"client_id": client_id, "first_seen_at": now.isoformat(), "seen_count": 0}
            clients.append(existing)
        existing["last_seen_at"] = now.isoformat()
        existing["seen_count"] = _safe_int(existing.get("seen_count"), 0, low=0, high=10_000_000) + 1
        existing["current"] = safe
        for field in (
            "platform_family", "os_version", "device_class", "device_family", "device_model",
            "companion_app_version", "browser_family", "browser_version", "webview_engine_version",
            "home_assistant_version_reported_by_frontend", "freshairiq_frontend_version",
        ):
            value = safe.get(field)
            if not value:
                continue
            history_key = f"{field}_history"
            history = existing.get(history_key)
            if not isinstance(history, list):
                history = []
            if value not in history:
                history.append(value)
            existing[history_key] = history[-12:]
        clients = clients[-DIAGNOSTICS_MAX_CLIENTS:]
        tmp = self._clients_path.with_suffix(self._clients_path.suffix + ".tmp")
        tmp.write_text(json.dumps({"clients": clients}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self._clients_path)
        self._last_export_client = safe
        return {"registered": True, "client_id": client_id}

    async def async_register_client(self, context: dict[str, Any]) -> dict[str, Any]:
        now = dt_util.now()
        try:
            return await self.hass.async_add_executor_job(self._register_client_sync, context, now)
        except OSError as err:
            return {"registered": False, "reason": f"{type(err).__name__}: {err}"}

    async def async_get_identity(self) -> dict[str, Any]:
        """Return the existing random field-test identity without exporting records."""
        now = dt_util.now()
        try:
            identity = await self.hass.async_add_executor_job(
                self._load_or_create_field_test_identity, now
            )
        except OSError as err:
            return {"installation_id": None, "identity_status": f"storage_error:{type(err).__name__}"}
        return {
            "installation_id": identity.get("installation_id"),
            "identity_status": identity.get("identity_status"),
            "created_at": identity.get("created_at"),
        }

    async def _async_runtime_environment(self) -> dict[str, Any]:
        """Collect HA-provided system metadata and whitelist field-test-safe facts."""
        fallback = _runtime_environment_snapshot()
        try:
            from homeassistant.helpers.system_info import async_get_system_info
            info = await async_get_system_info(self.hass)
        except Exception:
            return fallback
        if not isinstance(info, dict):
            return fallback
        safe = {
            "home_assistant_version": info.get("version") or fallback.get("home_assistant_version"),
            "installation_type": info.get("installation_type"),
            "channel": info.get("channel"),
            "dev": info.get("dev"),
            "hassio": info.get("hassio"),
            "docker": info.get("docker"),
            "virtualenv": info.get("virtualenv"),
            "python_version": info.get("python_version") or fallback.get("python_version"),
            "os_name": info.get("os_name") or fallback.get("os_name"),
            "os_version": info.get("os_version") or fallback.get("os_version"),
            "architecture": info.get("arch") or fallback.get("architecture"),
            "container_architecture": info.get("container_arch"),
            "timezone": info.get("timezone"),
        }
        return _json_safe(safe)

    @property
    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "retention_days": DIAGNOSTICS_RETENTION_DAYS,
            "interval_seconds": DIAGNOSTICS_IDLE_INTERVAL_SECONDS,
            "active_interval_seconds": DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS,
            "max_storage_mb": round(DIAGNOSTICS_MAX_TOTAL_BYTES / 1024 / 1024),
            "last_recorded_at": self._last_recorded_at.isoformat() if self._last_recorded_at else None,
            "records_this_runtime": self.record_count_session,
            "last_error": self.last_error,
        }

    def _contact_profile(self, contact: str, three_state: set[str]) -> dict[str, Any]:
        """Kind and origin of one window/door contact, without its name (0.26.5.2).

        Shows e.g. a self-built three-state template next to the two plain
        contacts it was made from.
        """
        try:
            from homeassistant.helpers import entity_registry as er  # noqa: PLC0415 - optional at runtime

            entity = er.async_get(self.hass).async_get(contact)
        except Exception:  # noqa: BLE001 - a missing registry must not break the snapshot
            entity = None
        return {
            "entity_domain": contact.split(".", 1)[0],
            "platform": _json_safe(getattr(entity, "platform", None)),
            # proven once (options or a reported tilt) and remembered by the room
            "three_state": contact in three_state,
        }

    def _duplicate_contact_names(self, contacts: list[Any]) -> int:
        """Contacts of one room that share a display name with another one."""
        states = getattr(self.hass, "states", None)
        names = []
        for contact in contacts:
            state = states.get(str(contact)) if states is not None else None
            names.append(str((state.attributes.get("friendly_name") if state is not None else None) or contact).strip().casefold())
        return sum(1 for name in names if names.count(name) > 1)


    async def async_record(
        self,
        data: dict[str, Any],
        store_data: dict[str, Any],
        now: datetime,
        completed_sessions: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Record compact trends and preserve meaningful events in full."""
        completed_sessions = completed_sessions or []
        trace = store_data.get("notification_diagnostics")
        self._notification_delivery_snapshot = _json_safe(trace[-50:]) if isinstance(trace, list) else []
        signature = self._signature(data)
        window_events = self._window_events(data, now)
        active_ventilation = self._is_active_ventilation(data)
        elapsed = (
            (now - self._last_recorded_at).total_seconds()
            if self._last_recorded_at is not None
            else DIAGNOSTICS_IDLE_INTERVAL_SECONDS
        )
        changed = signature != self._last_signature
        event_reason: str | None = None
        if completed_sessions:
            event_reason = "session_completed"
        elif window_events:
            event_reason = "window_event"
        elif self._configuration_changed:
            event_reason = "configuration_changed"
        elif changed:
            event_reason = "state_change"

        interval = DIAGNOSTICS_ACTIVE_INTERVAL_SECONDS if active_ventilation else DIAGNOSTICS_IDLE_INTERVAL_SECONDS
        if event_reason is None and elapsed < interval:
            return False

        if event_reason in {"session_completed", "window_event", "configuration_changed"}:
            record = self._build_record(
                data, store_data, now, event_reason, completed_sessions, window_events=window_events
            )
        elif event_reason == "state_change" and self._last_signature is not None:
            # v0.25.0.2: preserve decision transitions at compact fidelity.
            # Critical session/window/configuration evidence remains full fidelity.
            record = self._build_trend_record(data, now, "state_change")
            record["record_type"] = "decision_event"
        elif event_reason == "state_change":
            # Keep the first baseline snapshot complete so configuration and
            # environment evidence remain reconstructable after restart.
            record = self._build_record(data, store_data, now, event_reason, completed_sessions, window_events=window_events)
        else:
            reason = "active_sample" if active_ventilation else "idle_sample"
            record = self._build_trend_record(data, now, reason)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        path = self.directory / f"{now.date().isoformat()}.jsonl"
        try:
            await self.hass.async_add_executor_job(self._append_line, path, line)
            self._last_recorded_at = now
            self._last_signature = signature
            self._configuration_changed = False
            self.record_count_session += 1
            self.last_error = None
            if self._last_cleanup_at is None or (now - self._last_cleanup_at) >= timedelta(hours=1):
                await self.hass.async_add_executor_job(self._cleanup_files, now)
                self._last_cleanup_at = now
            return True
        except OSError as err:
            self.last_error = f"{type(err).__name__}: {err}"
            return False

    async def async_record_room_creation_trace(self, event: dict[str, Any]) -> bool:
        """Persist one privacy-safe room-creation trace event immediately.

        These sparse events exist solely to reconstruct configuration failures.
        They never include room names, entity IDs, raw form payloads or exception
        messages.  Room identity is represented only by a short one-way digest.
        """
        now = dt_util.now()
        record = {
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "freshairiq_version": self.version,
            "timestamp": now.isoformat(),
            "reason": "room_creation_trace",
            "record_type": "room_creation_trace",
            **_json_safe(event),
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        path = self.directory / f"{now.date().isoformat()}.jsonl"
        try:
            await self.hass.async_add_executor_job(self._append_line, path, line)
            self.record_count_session += 1
            self.last_error = None
            return True
        except OSError as err:
            self.last_error = f"{type(err).__name__}: {err}"
            return False

    async def async_record_flow_error(self, event: dict[str, Any]) -> bool:
        """Persist one configuration-flow exception (type + code location only, 0.26.4.3)."""
        now = dt_util.now()
        record = {
            "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
            "freshairiq_version": self.version,
            "timestamp": now.isoformat(),
            "reason": "config_flow_error",
            "record_type": "config_flow_error",
            **_json_safe(event),
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        path = self.directory / f"{now.date().isoformat()}.jsonl"
        try:
            await self.hass.async_add_executor_job(self._append_line, path, line)
            self.record_count_session += 1
            return True
        except OSError as err:
            self.last_error = f"{type(err).__name__}: {err}"
            return False

    def _append_line(self, path: Path, line: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _compact_legacy_file(self, path: Path) -> None:
        """Atomically compact retained pre-v3 routine rows in-place."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        changed = False
        output: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                # Keep damaged rows untouched so the exporter can still report
                # their location instead of silently discarding evidence.
                output.append(line)
                continue
            compact = self._compact_legacy_record(raw)
            if compact != raw:
                changed = True
            output.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
        if not changed:
            return
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)

    def _cleanup_files(self, now: datetime) -> None:
        if not self.directory.exists():
            return
        cutoff = now.date() - timedelta(days=DIAGNOSTICS_RETENTION_DAYS - 1)
        for path in self.directory.glob("*.jsonl"):
            try:
                day = datetime.fromisoformat(path.stem).date()
            except ValueError:
                continue
            if day < cutoff:
                path.unlink(missing_ok=True)

        # Upgrade still-retained traces from older versions before applying
        # the storage cap.  This protects the 30-day window from being lost
        # simply because old routine rows were much larger than v3 rows.
        today_stem = now.date().isoformat()
        for path in sorted(self.directory.glob("*.jsonl")):
            # The active day file is appended to continuously, so its mtime
            # always changes and it would be fully re-read and re-parsed on
            # every hourly cleanup. It only contains current-format rows (or a
            # few pre-upgrade rows that are compacted once the day has ended).
            if path.stem == today_stem:
                continue
            try:
                mtime_ns = path.stat().st_mtime_ns
            except OSError:
                continue
            cache_key = str(path)
            if self._legacy_compaction_mtime_ns.get(cache_key) == mtime_ns:
                continue
            self._compact_legacy_file(path)
            try:
                self._legacy_compaction_mtime_ns[cache_key] = path.stat().st_mtime_ns
            except OSError:
                self._legacy_compaction_mtime_ns.pop(cache_key, None)

        # Secondary safety cap: if unusually frequent state changes produce more
        # data than expected, remove the oldest complete daily chunks first.
        files = sorted(self.directory.glob("*.jsonl"))
        total = 0
        for path in files:
            try:
                if path.exists():
                    total += path.stat().st_size
            except OSError:
                continue
        current_name = now.date().isoformat() + ".jsonl"
        for path in files:
            if total <= DIAGNOSTICS_MAX_TOTAL_BYTES:
                break
            if path.name == current_name:
                continue
            try:
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                total -= size
            except OSError:
                continue


class FreshAirIQDiagnosticsView(HomeAssistantView):
    """Authenticated endpoint used by the FreshAirIQ dashboard export button."""

    url = "/api/freshairiq/diagnostics"
    name = "api:freshairiq:diagnostics"
    requires_auth = True

    @staticmethod
    def _recorder(hass: HomeAssistant):
        coordinators = iter_runtime_coordinators(hass)
        if not coordinators:
            return None
        return getattr(coordinators[0], "diagnostics", None)

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]
        recorder = self._recorder(hass)
        if recorder is None:
            return self.json({"error": "FreshAirIQ diagnostics are unavailable", "error_code": "FAIQ-DIAG-RUNTIME-001"}, status_code=503)
        exported = await recorder.async_export()
        if str(request.query.get("format", "")).lower() == "zip":
            # 0.26.4.9: same export, packed (≈1/15 of the size, content unchanged).
            from aiohttp import web

            basename = export_filename(dt_util.now())
            data = await hass.async_add_executor_job(zip_json_document, exported, basename)
            return web.Response(body=data, content_type="application/zip",
                                headers={"Content-Disposition": f'attachment; filename="{basename}.zip"', "Cache-Control": "no-store"})
        return self.json(exported)

    async def post(self, request):
        """Register an anonymous dashboard/client observation before export."""
        hass: HomeAssistant = request.app["hass"]
        recorder = self._recorder(hass)
        if recorder is None:
            return self.json({"error": "FreshAirIQ diagnostics are unavailable", "error_code": "FAIQ-DIAG-RUNTIME-001"}, status_code=503)
        try:
            payload = await request.json()
        except Exception:
            return self.json({"registered": False, "reason": "invalid_json", "error_code": "FAIQ-DIAG-REQUEST-001"}, status_code=400)
        if not isinstance(payload, dict):
            return self.json({"registered": False, "reason": "invalid_payload", "error_code": "FAIQ-DIAG-REQUEST-002"}, status_code=400)
        return self.json(await recorder.async_register_client(payload))


class FreshAirIQSupportDiagnosticsView(HomeAssistantView):
    """Authenticated endpoint for an explicit detailed support-diagnostic send."""

    url = "/api/freshairiq/support-diagnostics"
    name = "api:freshairiq:support-diagnostics"
    requires_auth = True

    async def post(self, request):
        hass: HomeAssistant = request.app["hass"]
        coordinators = iter_runtime_coordinators(hass)
        if not coordinators:
            return self.json({"error": "FreshAirIQ diagnostics are unavailable", "error_code": "FAIQ-DIAG-RUNTIME-001"}, status_code=503)
        coordinator = coordinators[0]
        try:
            payload = await request.json()
        except Exception:
            return self.json({"error": "invalid_json", "error_code": "FAIQ-SUPPORT-REQUEST-001"}, status_code=400)
        if not isinstance(payload, dict):
            return self.json({"error": "invalid_payload", "error_code": "FAIQ-SUPPORT-REQUEST-002"}, status_code=400)
        message = str(payload.get("message") or "").strip()
        try:
            result = await coordinator.telemetry.async_submit_support_diagnostics(message)
        except ValueError as err:
            return self.json({"error": str(err), "error_code": "FAIQ-SUPPORT-VALIDATION-001"}, status_code=400)
        except Exception as err:  # Do not expose traceback or diagnostic contents to the browser.
            raw = str(err)
            if isinstance(err, TimeoutError):
                detail = "timeout"
            elif isinstance(err, RuntimeError) and raw.startswith("support_diagnostics_http_"):
                detail = raw
            elif isinstance(err, RuntimeError) and raw in {"identity_unavailable", "hub_unconfigured", "hub_credential_persistence_failed"}:
                detail = raw
            else:
                detail = type(err).__name__
            return self.json({"error": "support_upload_failed", "detail": detail, "error_code": "FAIQ-SUPPORT-UPLOAD-001"}, status_code=502)
        status = 429 if result.get("reason") == "cooldown" else 200
        return self.json(result, status_code=status)

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: Any) -> dict[str, Any]:
    """Return a compact Home Assistant native diagnostic without entity IDs.

    The full rolling support dossier remains available through FreshAirIQ's
    explicit support export. Native HA diagnostics intentionally expose only a
    current, privacy-reduced runtime snapshot.
    """
    from .runtime import get_runtime_coordinator
    coordinator = get_runtime_coordinator(hass, entry)
    data = coordinator.data if isinstance(getattr(coordinator, "data", None), dict) else {}
    rooms = []
    for room in (data.get("rooms") or {}).values() if isinstance(data.get("rooms"), dict) else []:
        if not isinstance(room, dict):
            continue
        rooms.append({k: _json_safe(room.get(k)) for k in (
            "name", "floor", "data_quality", "temperature", "humidity", "absolute_humidity",
            "co2", "co2_available", "surface_rh", "mould_level", "action", "active",
            "ventilation_type", "mechanical_exhaust_active", "goal_state", "comfort_target_c",
            "comfort_target_source", "learning_status", "learning_samples",
        )})
    return {
        "freshairiq_version": getattr(coordinator, "version", None) or getattr(coordinator, "integration_version", None),
        "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "runtime_available": True,
        "house_status": data.get("status"),
        "rooms": rooms,
        "privacy": "Entity IDs, coordinates, credentials, notification targets and resident names are omitted.",
    }
