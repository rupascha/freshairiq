"""Live channel for the FreshAirIQ dashboard (0.26.5.3).

Community (recorder load): the complete dashboard state used to travel as
attributes of the status sensor. Home Assistant writes a recorder row for every
attribute change, also for attributes kept out of the database, so the status
sensor wrote a row every cycle. The dashboard (card and panel) now subscribes to
``freshairiq/dashboard/subscribe`` and receives exactly the same payload over the
websocket; the status sensor keeps only a small, stable summary.

The payload is built once per coordinator cycle and sent to each subscriber only
when it changed.
"""
from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.json import json_bytes

from .const import DOMAIN, VERSION
from .dashboard_transport import DETAILS_API, slim_rooms

LIVE_API = "dashboard_ws_v1"
SUBSCRIBE = "freshairiq/dashboard/subscribe"


class DashboardPayload:
    """The dashboard state (until 0.26.5.2 the attributes of the status sensor, unchanged)."""

    def __init__(self, coordinator: Any, entry_id: str) -> None:
        self.coordinator = coordinator
        self._entry = SimpleNamespace(entry_id=entry_id)

    def build(self) -> dict[str, Any]:
        return {
            "freshairiq_live_api": LIVE_API,
            "status": self.coordinator.data.get("status"),
            "status_text": self.coordinator.data["status_text"],
            # Hotfix 0.18.2.3: keep the complete room payload as the authoritative
            # fallback. Per-room Action entities still expose the same payload, but
            # disabling/missing one of those entities must never remove room history
            # from the dashboard.
            # 0.26.4.7: hourly chart series are served on demand
            # (/api/freshairiq/room-history/<entry_id>), not pushed every cycle.
            "rooms": slim_rooms(self.coordinator.data["rooms"]),
            "freshairiq_transport": "status_v2",
            "freshairiq_details_api": DETAILS_API,
            "freshairiq_entry_id": self._entry.entry_id,
            "freshairiq_version": VERSION,
            "output_language": self.coordinator.data.get("output_language", "de"),  # 0.26.5.0: the dashboard speaks this language
            "levels": self.coordinator.data.get("levels", []),
            "potential_total_ml": self.coordinator.data.get("potential_total_ml", 0),
            "live_balance_ml": self.coordinator.data.get("live_balance_ml", 0),
            "next_5_min_ml": self.coordinator.data.get("next_5_min_ml", 0),
            "next_5_min_effect_ml": self.coordinator.data.get("next_5_min_effect_ml", 0),
            "moisture_gain_next_5_min_ml": self.coordinator.data.get("moisture_gain_next_5_min_ml", 0),
            "forecast_horizon_min": self.coordinator.data.get("forecast_horizon_min", 5),
            "forecast_moisture_effect_ml": self.coordinator.data.get("forecast_moisture_effect_ml", 0),
            "forecast_uncapped_moisture_effect_ml": self.coordinator.data.get("forecast_uncapped_moisture_effect_ml", self.coordinator.data.get("forecast_moisture_effect_ml", 0)),
            "forecast_target_limited": self.coordinator.data.get("forecast_target_limited", False),
            "forecast_live_adapted": self.coordinator.data.get("forecast_live_adapted", False),
            "forecast_live_observation_weight": self.coordinator.data.get("forecast_live_observation_weight", 0),
            "forecast_temperature_change_c": self.coordinator.data.get("forecast_temperature_change_c", 0),
            "forecast_cost": self.coordinator.data.get("forecast_cost", 0),
            "forecast_heat_kwh": self.coordinator.data.get("forecast_heat_kwh", 0),
            "forecast_confidence": self.coordinator.data.get("forecast_confidence", 0),
            "total_water_ml": self.coordinator.data.get("total_water_ml", 0),
            "max_surface_rh": self.coordinator.data.get("max_surface_rh", 0),
            "prognosis_confidence": self.coordinator.data.get("prognosis_confidence", 0),
            "cross_ventilation": self.coordinator.data["cross_ventilation"],
            "recommended_duration_min": self.coordinator.data["recommended_duration_min"],
            "remaining_duration_min": self.coordinator.data["remaining_duration_min"],
            "temperature_change_live_c": self.coordinator.data["temperature_change_live_c"],
            "operating_profile": self.coordinator.data["operating_profile"],
            "overnight_forecast_ml": self.coordinator.data["overnight_forecast_ml"],
            "overnight_forecast_base_ml": self.coordinator.data.get("overnight_forecast_base_ml", 0),
            "overnight_weather_effect_ml": self.coordinator.data.get("overnight_weather_effect_ml", 0),
            "overnight_trend_effect_ml": self.coordinator.data.get("overnight_trend_effect_ml", 0),
            "overnight_hours_remaining": self.coordinator.data.get("overnight_hours_remaining", 0),
            "overnight_confidence": self.coordinator.data.get("overnight_confidence", 0),
            "night_model_ml_h": self.coordinator.data["night_model_ml_h"],
            "night_model_samples": self.coordinator.data["night_model_samples"],
            "night_recommendation": self.coordinator.data["night_recommendation"],
            "night_strategy": self.coordinator.data.get("night_strategy", {}),
            "history_14d": self.coordinator.data["history_14d"],
            "water_history_14d": self.coordinator.data.get("water_history_14d", []),
            "temperature_history_14d": self.coordinator.data.get("temperature_history_14d", []),
            "history_summary": self.coordinator.data["history_summary"],
            "occupants": self.coordinator.data["occupants"],
            "heating_system": self.coordinator.data["heating_system"],
            "energy_price_per_kwh": self.coordinator.data.get("energy_price_per_kwh", 0),
            "adult_occupants": self.coordinator.data.get("adult_occupants", 0),
            "child_occupants": self.coordinator.data.get("child_occupants", 0),
            "effective_occupants": self.coordinator.data.get("effective_occupants", 0),
            "effective_adults": self.coordinator.data.get("effective_adults", 0),
            "effective_children": self.coordinator.data.get("effective_children", 0),
            "tracked_occupants": self.coordinator.data.get("tracked_occupants", 0),
            "home_tracked_occupants": self.coordinator.data.get("home_tracked_occupants", 0),
            "away_tracked_occupants": self.coordinator.data.get("away_tracked_occupants", 0),
            "unknown_tracked_occupants": self.coordinator.data.get("unknown_tracked_occupants", 0),
            "untracked_adults": self.coordinator.data.get("untracked_adults", 0),
            "untracked_children": self.coordinator.data.get("untracked_children", 0),
            "guest_adults": self.coordinator.data.get("guest_adults", 0),
            "guest_children": self.coordinator.data.get("guest_children", 0),
            "presence_confidence": self.coordinator.data.get("presence_confidence", 0),
            "property_type": self.coordinator.data.get("property_type", "house"),
            "ventilation_threshold_ml": self.coordinator.data.get("ventilation_threshold_ml", 0),
            "ventilation_threshold_percent": self.coordinator.data.get("ventilation_threshold_percent", 10),
            "ventilation_threshold_mode": self.coordinator.data.get("ventilation_threshold_mode", "adaptive_home_size"),
            "presence_explanation": self.coordinator.data.get("presence_explanation", ""),
            "pets_in_household": self.coordinator.data.get("pets_in_household", False),
            "house_strategy_samples": self.coordinator.data.get("house_strategy_samples", 0),
            "pollen_enabled": self.coordinator.data.get("pollen_enabled", False),
            "pollen_index": self.coordinator.data.get("pollen_index", 0),
            "pollen_limit": self.coordinator.data.get("pollen_limit", 4),
            "pollen_blocked": self.coordinator.data.get("pollen_blocked", False),
            "outdoor_pm25": self.coordinator.data.get("outdoor_pm25"),
            "outdoor_pm25_limit": self.coordinator.data.get("outdoor_pm25_limit"),
            "outdoor_pm25_blocked": self.coordinator.data.get("outdoor_pm25_blocked", False),
            "outdoor_air_veto_cause": self.coordinator.data.get("outdoor_air_veto_cause"),
            "weather_now": self.coordinator.data.get("weather_now", {}),
            "wind_bearing": self.coordinator.data.get("wind_bearing"),
            "wind_speed": self.coordinator.data.get("wind_speed"),
            "last_ventilation": self.coordinator.data.get("last_ventilation"),
            "finalizing_measurements": self.coordinator.data.get("finalizing_measurements", {}),
            "statistics_days": self.coordinator.data.get("statistics_days", 14),
            "notifications_enabled": self.coordinator.data["notifications_enabled"],
            "intelligent_recommendation": self.coordinator.data.get("intelligent_recommendation", {}),
            "recommendation_engine": self.coordinator.data.get("recommendation_engine", "v3"),
            "iq_state": self.coordinator.data.get("iq_state", {}),
            "future_weather_available": self.coordinator.data.get("future_weather_available", False),
            "intelligence_engine": self.coordinator.data.get("intelligence_engine", "v1"),
            "estimated_moisture_generation_day_ml": self.coordinator.data["estimated_moisture_generation_day_ml"],
            "moisture_balance_today_ml": self.coordinator.data["moisture_balance_today_ml"],
            "forecast_validation": self.coordinator.data.get("forecast_validation", {}),
            "forecast_backtest": self.coordinator.data.get("forecast_backtest", {}),
            "learning_effectiveness": self.coordinator.data.get("learning_effectiveness", {}),
            "post_close_stabilization": self.coordinator.data.get("post_close_stabilization", {}),
            "learning_components": self.coordinator.data.get("learning_components", {}),
            "diagnostics": self.coordinator.data.get("diagnostics", {}),
            "diagnostics_upload": self.coordinator.data.get("diagnostics_upload", {}),
            "support_status": self.coordinator.runtime_health.user_summary,
            "version": VERSION,
        }


def _payload_bytes(coordinator: Any, entry_id: str) -> bytes:
    """JSON of the current payload, built once per coordinator data object."""
    data = coordinator.data
    cache = getattr(coordinator, "_dashboard_live_cache", None)
    if cache is not None and cache[0] is data:
        return cache[1]
    payload = DashboardPayload(coordinator, entry_id).build()
    coordinator.runtime_health.observe_attribute_payload("status", payload, recorder_exposed=False)
    encoded = json_bytes(payload)
    coordinator._dashboard_live_cache = (data, encoded)
    return encoded


def live_signal(entry_id: str) -> str:
    return f"{DOMAIN}_dashboard_live_{entry_id}"


@callback
def async_track_dashboard(hass: HomeAssistant, entry: Any) -> Callable[[], None]:
    """Announce every coordinator update of ``entry`` to its live subscribers.

    Subscriptions follow the config entry, not one coordinator object: after a
    reload (e.g. a saved setting) the open dashboards receive the new
    coordinator's state without subscribing again.
    """
    @callback
    def _updated() -> None:
        async_dispatcher_send(hass, live_signal(entry.entry_id))

    unsub = entry.runtime_data.async_add_listener(_updated)
    _updated()  # dashboards that were open during a reload get the new state at once
    return unsub


def _coordinator(hass: HomeAssistant, entry_id: str | None) -> Any:
    entries = [hass.config_entries.async_get_entry(entry_id)] if entry_id else hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        coordinator = getattr(entry, "runtime_data", None) if entry is not None else None
        if coordinator is not None and isinstance(getattr(coordinator, "data", None), dict):
            return entry.entry_id, coordinator
    return None


@callback
@websocket_api.websocket_command({vol.Required("type"): SUBSCRIBE, vol.Optional("entry_id"): str})
def ws_subscribe_dashboard(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    found = _coordinator(hass, msg.get("entry_id"))
    if found is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    entry_id = found[0]
    msg_id = int(msg["id"])
    last: list[bytes | None] = [None]

    @callback
    def push() -> None:
        current = _coordinator(hass, entry_id)
        if current is None:
            return
        encoded = _payload_bytes(current[1], entry_id)
        if encoded == last[0]:
            return
        last[0] = encoded
        connection.send_message(b'{"id":' + str(msg_id).encode() + b',"type":"event","event":' + encoded + b"}")

    connection.subscriptions[msg_id] = async_dispatcher_connect(hass, live_signal(entry_id), push)
    connection.send_result(msg_id)
    push()


@callback
def async_register_dashboard_live(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe_dashboard)
