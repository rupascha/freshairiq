"""Authenticated on-demand room chart history for the dashboard (0.26.4.7).

See ``dashboard_transport``: the hourly temperature/humidity series are no
longer pushed through entity attributes every cycle; the card loads them here
when a room's detail view is opened.
"""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .dashboard_transport import room_history_payload
from .runtime import get_runtime_coordinator


class FreshAirIQRoomHistoryView(HomeAssistantView):
    url = "/api/freshairiq/room-history/{entry_id}"
    name = "api:freshairiq:room-history"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return self.json({"error": "FreshAirIQ configuration not found.", "error_code": "FAIQ-HISTORY-CONFIG-001"}, status_code=404)
        try:
            coordinator = get_runtime_coordinator(hass, entry)
        except RuntimeError:
            return self.json({"error": "FreshAirIQ is not ready yet.", "error_code": "FAIQ-HISTORY-RUNTIME-001"}, status_code=503)
        data = coordinator.data if isinstance(getattr(coordinator, "data", None), dict) else {}
        room_key = str(request.query.get("room") or "").strip() or None
        return self.json(room_history_payload(data.get("rooms"), room_key))
