"""Authenticated feedback endpoint for the FreshAirIQ dashboard card.

Since 0.26.4.3 FreshAirIQ has exactly one settings surface: Devices & services
(config/options flow). The former dashboard settings API that wrote ConfigEntry
data and options was removed; the card only reads state and sends feedback.
"""
from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN


def _msg(hass: HomeAssistant, de: str, en: str) -> str:
    language = getattr(getattr(hass, "config", None), "language", None)
    language = language if isinstance(language, str) else "de"
    return de if language.lower().startswith("de") else en


class FreshAirIQFeedbackView(HomeAssistantView):
    """Authenticated proxy for explicit user feedback; no Hub credential reaches the browser."""
    url = "/api/freshairiq/feedback/{entry_id}"
    name = "api:freshairiq:feedback"
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return self.json({"error": _msg(hass, "FreshAirIQ-Konfiguration nicht gefunden.", "FreshAirIQ configuration not found.")}, status_code=404)
        try:
            payload = await request.json()
            kind = str(payload.get("type") or "").strip()
            message = str(payload.get("message") or "").strip()
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is None:
                raise ValueError(_msg(hass, "FreshAirIQ ist gerade nicht geladen.", "FreshAirIQ is not loaded right now."))
            client_context = payload.get("client_context") if isinstance(payload.get("client_context"), dict) else None
            result = await coordinator.telemetry.async_submit_feedback(kind, message, client_context=client_context)
            return self.json({"ok":True, **result})
        except ValueError as err:
            return self.json({"error":str(err)}, status_code=400)
        except Exception as err:
            code = "FAIQ-HUB-FEEDBACK-001"
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is not None:
                try:
                    await coordinator.telemetry.async_report_client_error(code=code, component="feedback", operation="submit_feedback", message=f"{type(err).__name__}: {err}")
                except Exception:
                    pass  # Never recurse when the Hub itself is unreachable.
            return self.json({"error": _msg(hass, "Feedback konnte nicht an den Diagnose-Hub übertragen werden.", "Feedback could not be sent to the diagnostics hub."), "error_code":code, "technical_detail":str(err)}, status_code=502)
