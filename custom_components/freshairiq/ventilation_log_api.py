"""Authenticated local ventilation-log PDF endpoint."""
from __future__ import annotations
from datetime import datetime, time, timedelta
import base64
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .runtime import get_runtime_coordinator
from .ventilation_log import build_ventilation_pdf, filter_ventilation_log

class FreshAirIQVentilationLogView(HomeAssistantView):
    url = "/api/freshairiq/ventilation-log/{entry_id}"
    name = "api:freshairiq:ventilation-log"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return self.json({"error": "FreshAirIQ-Konfiguration nicht gefunden.", "error_code": "FAIQ-PDF-CONFIG-001"}, status_code=404)
        try:
            coordinator = get_runtime_coordinator(hass, entry)
        except RuntimeError:
            # Dashboard requests can arrive while Home Assistant is still loading
            # the ConfigEntry. Runtime unavailability is temporary, not a server error.
            return self.json({"error": "FreshAirIQ ist noch nicht bereit.", "error_code": "FAIQ-PDF-RUNTIME-001"}, status_code=503)
        today = dt_util.now().date()
        try:
            start_date = datetime.fromisoformat(request.query.get("start", "")).date() if request.query.get("start") else today - timedelta(days=30)
            end_date = datetime.fromisoformat(request.query.get("end", "")).date() if request.query.get("end") else today
        except ValueError:
            return self.json({"error": "Ungültiger Zeitraum.", "error_code": "FAIQ-PDF-RANGE-001"}, status_code=400)
        if end_date < start_date or (end_date - start_date).days > 730:
            return self.json({"error": "Der Zeitraum muss zwischen 1 und 731 Tagen liegen.", "error_code": "FAIQ-PDF-RANGE-002"}, status_code=400)
        tz = dt_util.DEFAULT_TIME_ZONE
        start = datetime.combine(start_date, time.min, tzinfo=tz)
        end = datetime.combine(end_date, time.max, tzinfo=tz)
        try:
            events = filter_ventilation_log(coordinator.store.data.get("ventilation_log", []), start, end)
            pdf = build_ventilation_pdf(events, start, end)
        except Exception as err:  # PDF errors must be screenshot-actionable without exposing private data.
            coordinator.runtime_health.record_exception("ventilation_log", "build_pdf", err, dt_util.now())
            return self.json({"error": "Lüftungsprotokoll konnte nicht erstellt werden.", "error_code": "FAIQ-PDF-BUILD-001", "error_type": type(err).__name__}, status_code=500)
        filename = f"FreshAirIQ-Lueftungsprotokoll-{start_date.isoformat()}-{end_date.isoformat()}.pdf"
        return self.json({"filename": filename, "pdf_base64": base64.b64encode(pdf).decode("ascii"), "event_count": len(events)})
