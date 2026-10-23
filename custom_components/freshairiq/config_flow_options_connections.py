"""Options flow: open connections between rooms without a door or contact (0.26.5.3)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import selector

from .const import CONF_ROOM_NAME
from .open_connections import OPTION, connection_map, with_connections


class OptionsConnectionsMixin:
    """"Offene Verbindungen": pick a room, then the rooms it is openly connected with."""

    async def async_step_open_connections(self, user_input=None):
        self._ensure_working_copy()
        rooms = self._rooms()
        if user_input is not None:
            if bool(user_input.get("wizard_back")) or "room" not in user_input:
                return await self.async_step_home_setup()
            self._selected_room_key = str(user_input["room"])
            return await self.async_step_open_connection_rooms()
        if len(rooms) < 2:
            return await self.async_step_home_setup()
        names = {r["key"]: r.get(CONF_ROOM_NAME, r["key"]) for r in rooms}
        connections = connection_map(self._working_options, names)
        options = [{"value": key, "label": name} for key, name in names.items()]
        return self.async_show_form(
            step_id="open_connections",
            data_schema=vol.Schema({
                vol.Optional("wizard_back", default=False): selector.BooleanSelector(),
                vol.Required("room", default=options[0]["value"]): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)),
            }),
            description_placeholders={"overview": _overview(connections, names)},
        )

    async def async_step_open_connection_rooms(self, user_input=None):
        names = {r["key"]: r.get(CONF_ROOM_NAME, r["key"]) for r in self._rooms()}
        key = getattr(self, "_selected_room_key", None)
        if key not in names:
            return await self.async_step_open_connections()
        if user_input is not None:
            if not bool(user_input.get("wizard_back")):
                connected = [str(x) for x in (user_input.get("connected_rooms") or []) if str(x) in names]
                self._working_options[OPTION] = with_connections(
                    {OPTION: connection_map(self._working_options, names)}, key, connected)
                self._persist_working_state(reload_entry=False)
            return await self.async_step_open_connections()
        current = sorted(connection_map(self._working_options, names).get(key, set()))
        return self.async_show_form(
            step_id="open_connection_rooms",
            data_schema=vol.Schema({
                vol.Optional("wizard_back", default=False): selector.BooleanSelector(),
                vol.Optional("connected_rooms", default=current): selector.SelectSelector(selector.SelectSelectorConfig(
                    options=[{"value": k, "label": n} for k, n in names.items() if k != key],
                    multiple=True, mode=selector.SelectSelectorMode.LIST)),
            }),
            description_placeholders={"room_name": str(names[key])},
        )


def _overview(connections: dict[str, set[str]], names: dict[str, str]) -> str:
    pairs = sorted({tuple(sorted((a, b))) for a, others in connections.items() for b in others})
    return "\n".join(f"• {names[a]} ↔ {names[b]}" for a, b in pairs) or "–"
