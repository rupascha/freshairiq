"""Options-flow settings steps: areas, thresholds, model, profile, residents, forecast, air quality, energy and notifications."""
from __future__ import annotations


import voluptuous as vol
from homeassistant.helpers import selector

from .const import (
    CONF_LEVELS,
    CONF_ROOM_DISABLED_GOALS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_NAME,
    DEFAULT_OPTIONS,
    HEATING_HEAT_PUMP,
    PROFILE_COMFORT,
    PROFILE_SUMMER_COOLING,
)
from .config_flow_fields import (
    _HEATING_LABELS_DE,
    _HEATING_LABELS_EN,
    _PROFILE_LABELS_DE,
    _PROFILE_LABELS_EN,
    _bounded,
    _choice,
    _flow_language,
    _is_de,
    _level_label,
    _number,
    _safe_int,
    _txt,
)
from .config_flow_goals import (
    _available_room_goals,
    _goal_priority_errors,
    _goal_priority_schema,
    _ranked_goal_priorities,
    _switched_off_goals,
)
from .config_flow_rooms import _flatten_sections
from .config_flow_schemas import (
    _air_quality_schema,
    _building_schema,
    _cross_ventilation_schema,
    _diagnostics_sharing_schema,
    _energy_details_schema,
    _energy_system_schema,
    _forecast_schema,
    _model_schema,
    _notification_schema,
    _profile_details_schema,
    _profile_schema,
    _resident_name_list,
    _resident_profiles_dict,
    _resident_slot_overview,
    _resident_slot_placeholders,
    _residents_schema,
)
from .notifications import _all_notification_targets, _send_targets
from .settings_contract import native_option_key
from .validation import option_relationship_error


class OptionsSettingsMixin:
    """Options-flow settings steps: areas, thresholds, model, profile, residents, forecast, air quality, energy and notifications."""

    async def async_step_levels(self, user_input=None):
        self._ensure_working_copy()
        levels = list(self._working_data.get(CONF_LEVELS, []))
        for room in self._rooms():
            label = str(room.get(CONF_ROOM_FLOOR, "")).strip()
            if label and label not in levels:
                levels.append(label)
        self._working_data[CONF_LEVELS] = levels
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_level_add()
            if action == "reorder":
                return await self.async_step_level_reorder()
            if action == "remove":
                return await self.async_step_level_remove()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="levels",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["add", "reorder", "remove", "back"],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="level_action",
                        )
                    )
                }
            ),
            description_placeholders={
                "levels": ", ".join(_level_label(x, _flow_language(self.hass)) for x in levels)
                if levels
                else _txt(_flow_language(self.hass), "Noch keine Bereiche", "No areas yet")
            },
        )

    async def async_step_level_add(self, user_input=None):
        if user_input is not None:
            name = str(user_input.get("name", "")).strip()
            levels = self._working_data.setdefault(CONF_LEVELS, [])
            if name and name not in levels:
                levels.append(name)
                self._persist_working_state()
            return await self.async_step_levels()
        return self.async_show_form(
            step_id="level_add",
            data_schema=vol.Schema({vol.Required("name"): selector.TextSelector()}),
        )

    async def async_step_level_reorder(self, user_input=None):
        levels = list(self._working_data.get(CONF_LEVELS, []))
        # Home Assistant renders dynamic schema keys literally. Localized labels
        # therefore become the form keys, while stored level ids stay unchanged.
        if user_input is not None:
            indexed = {level: i for i, level in enumerate(levels)}
            ordered = sorted(
                levels,
                key=lambda level: (
                    int(user_input.get(_level_label(level, _flow_language(self.hass)), indexed[level] + 1)),
                    indexed[level],
                ),
            )
            self._working_data[CONF_LEVELS] = ordered
            self._persist_working_state()
            return await self.async_step_levels()
        fields = {
            vol.Required(_level_label(level, _flow_language(self.hass)), default=idx): _number(
                1, max(len(levels), 1), 1
            )
            for idx, level in enumerate(levels, start=1)
        }
        if not fields:
            return await self.async_step_levels()
        return self.async_show_form(
            step_id="level_reorder",
            data_schema=vol.Schema(fields),
        )

    async def async_step_level_remove(self, user_input=None):
        levels = list(self._working_data.get(CONF_LEVELS, []))
        used = {str(r.get(CONF_ROOM_FLOOR, "")) for r in self._rooms()}
        removable = [x for x in levels if x not in used]
        if user_input is not None:
            name = user_input.get("name")
            self._working_data[CONF_LEVELS] = [x for x in levels if x != name]
            self._persist_working_state()
            return await self.async_step_levels()
        opts = [{"value": x, "label": _level_label(x, _flow_language(self.hass))} for x in removable]
        if not opts:
            return await self.async_step_levels()
        return self.async_show_form(
            step_id="level_remove",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=opts, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_threshold(self, user_input=None):
        """Configure the house-wide ventilation threshold without ambiguous fields."""
        self._ensure_working_copy()
        if user_input is not None:
            mode = _choice(user_input.get("threshold_mode"), "adaptive_home_size", ["adaptive_home_size", "percent_total_water", "fixed_ml"])
            self._working_options["threshold_mode"] = mode
            self._persist_working_state()
            if mode == "percent_total_water":
                return await self.async_step_threshold_percent()
            if mode == "fixed_ml":
                return await self.async_step_threshold_fixed()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="threshold",
            data_schema=vol.Schema({
                vol.Required(native_option_key("threshold_mode"), default=_choice(self._working_options.get("threshold_mode"), "adaptive_home_size", ["adaptive_home_size", "percent_total_water", "fixed_ml"])): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["adaptive_home_size", "percent_total_water", "fixed_ml"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="threshold_mode")
                )
            }),
        )

    async def async_step_threshold_percent(self, user_input=None):
        """Configure only the percentage value for percentage mode."""
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["min_potential_percent_total_water"] = float(user_input["min_potential_percent_total_water"])
            self._working_options["threshold_mode"] = "percent_total_water"
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="threshold_percent",
            data_schema=vol.Schema({
                vol.Required(native_option_key("min_potential_percent_total_water"), default=_bounded(self._working_options.get("min_potential_percent_total_water"), 10, 1, 30)): _number(1, 30, 0.5, "%")
            }),
        )

    async def async_step_threshold_fixed(self, user_input=None):
        """Configure only the fixed mL value for fixed mode."""
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["min_potential_total_ml"] = float(user_input["min_potential_total_ml"])
            self._working_options["threshold_mode"] = "fixed_ml"
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="threshold_fixed",
            data_schema=vol.Schema({
                vol.Required(native_option_key("min_potential_total_ml"), default=_bounded(self._working_options.get("min_potential_total_ml"), 500, 50, 5000)): _number(50, 5000, 10, "mL")
            }),
        )

    async def async_step_model(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            submitted = _flatten_sections(user_input)
            candidate = {**self._working_options, **submitted}
            relation_error = option_relationship_error(candidate)
            if relation_error:
                return self.async_show_form(
                    step_id="model",
                    data_schema=_model_schema(candidate),
                    errors={"base": relation_error},
                )
            self._working_options.update(submitted)
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="model", data_schema=_model_schema(self._working_options)
        )

    async def async_step_recommendation_priorities(self, user_input=None):
        """Choose a room and edit its recommendation-goal ranking centrally."""
        self._ensure_working_copy()
        eligible = [r for r in self._rooms() if len(_available_room_goals(r)) > 1]
        if not eligible:
            return await self.async_step_ventilation_settings()
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_ventilation_settings()
            self._selected_room_key = str(user_input["room"])
            return await self.async_step_recommendation_priority_order()
        options = [{"value": r["key"], "label": r.get(CONF_ROOM_NAME, r["key"])} for r in eligible]
        return self.async_show_form(
            step_id="recommendation_priorities",
            data_schema=vol.Schema({
                vol.Optional("wizard_back", default=False): selector.BooleanSelector(),
                vol.Required("room", default=options[0]["value"]): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)),
            }),
        )

    async def async_step_recommendation_priority_order(self, user_input=None):
        room = next((r for r in self._rooms() if r.get("key") == self._selected_room_key), None)
        if room is None:
            return await self.async_step_recommendation_priorities()
        errors = {}
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_recommendation_priorities()
            errors = _goal_priority_errors(user_input, room)
            if not errors:
                room[CONF_ROOM_GOAL_PRIORITIES], room[CONF_ROOM_DISABLED_GOALS] = (
                    _ranked_goal_priorities(user_input, room), _switched_off_goals(user_input, room)
                )
                # Priority order does not change the room structure. Avoid a
                # config-entry reload while the options dialog is still active.
                self._persist_working_state(reload_entry=False)
                return await self.async_step_recommendation_priorities()
        return self.async_show_form(
            step_id="recommendation_priority_order",
            data_schema=_goal_priority_schema(room, include_back=True),
            errors=errors,
        )

    async def async_step_cross_ventilation(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        room_keys = ", ".join(
            f"{room.get(CONF_ROOM_NAME, room['key'])} = {room['key']}"
            for room in self._rooms()
        ) or _txt(_flow_language(self.hass), "Noch keine Räume eingerichtet", "No rooms set up yet")
        return self.async_show_form(
            step_id="cross_ventilation",
            data_schema=_cross_ventilation_schema(self._working_options),
            description_placeholders={"room_keys": room_keys},
        )

    async def async_step_profile(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["operating_profile"] = user_input[
                "operating_profile"
            ]
            self._persist_working_state()
            if self._working_options["operating_profile"] in {PROFILE_SUMMER_COOLING, PROFILE_COMFORT}:
                return await self.async_step_profile_details()
            # The efficiency fields for Comfort/Dehumidify already live in the
            # canonical ventilation model. Do not expose duplicate controls;
            # Comfort only gets its cooling lower limit (0.26.5.4).
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="profile", data_schema=_profile_schema(self._working_options)
        )

    async def async_step_profile_details(self, user_input=None):
        # 0.26.5.4: the comfort profile shows its cooling lower limit here too
        if self._working_options.get("operating_profile", PROFILE_COMFORT) not in {PROFILE_SUMMER_COOLING, PROFILE_COMFORT}:
            return await self.async_step_ventilation_settings()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="profile_details",
            data_schema=_profile_details_schema(self._working_options),
            description_placeholders={
                "profile": (
                    _PROFILE_LABELS_DE if _is_de(_flow_language(self.hass)) else _PROFILE_LABELS_EN
                ).get(
                    self._working_options.get("operating_profile", PROFILE_COMFORT),
                    _txt(_flow_language(self.hass), "Komfort", "Comfort"),
                )
            },
        )

    async def async_step_building(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="building", data_schema=_building_schema(self._working_options)
        )

    def _resident_placeholders(self) -> dict[str, str]:
        language = self.hass.config.language if self.hass else "de"
        return {
            "resident_slots": _resident_slot_overview(self._working_options, language),
            **_resident_slot_placeholders(self._working_options, language),
        }

    async def async_step_residents(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            values = _flatten_sections(dict(user_input))
            # Keep the same compact string representation used by the dashboard
            # resident-profile editor so both UIs write exactly one setting.
            # Convert readable per-person controls back to the existing compact profile contract.
            import json
            existing_profiles = _resident_profiles_dict(self._working_options.get("resident_room_profiles"))
            adult_names = _resident_name_list(values.get("adult_resident_names", self._working_options.get("adult_resident_names")))
            child_names = _resident_name_list(values.get("child_resident_names", self._working_options.get("child_resident_names")))
            structured = any(key.startswith(("adult_", "child_")) and key.endswith(("_rooms", "_thermal", "_notifications")) for key in values)
            if structured:
                rebuilt = {}
                for role, names, count in (("adult", adult_names, int(values.get("adult_occupants", self._working_options.get("adult_occupants", 0)) or 0)), ("child", child_names, int(values.get("child_occupants", self._working_options.get("child_occupants", 0)) or 0))):
                    for idx in range(min(max(count, len(names)), 4)):
                        prefix = f"{role}_{idx + 1}"
                        previous = existing_profiles.get(f"{role}:{idx}", {})
                        notifications = str(values.pop(f"{prefix}_notifications", ", ".join(previous.get("notification_targets") or [])) or "")
                        rebuilt[f"{role}:{idx}"] = {
                            "name": names[idx] if idx < len(names) else "",
                            "room_keys": list(values.pop(f"{prefix}_rooms", previous.get("room_keys") or [])),
                            "thermal_preference": str(values.pop(f"{prefix}_thermal", previous.get("thermal_preference") or "inherit")),
                            "notification_targets": [x.strip() for x in notifications.replace(";", ",").split(",") if x.strip()],
                        }
                values["resident_room_profiles"] = json.dumps(rebuilt, ensure_ascii=False, separators=(",", ":"))
            profiles = values.get("resident_room_profiles")
            if isinstance(profiles, str):
                import json
                try:
                    parsed = json.loads(profiles or "{}")
                    if not isinstance(parsed, dict):
                        raise ValueError
                    values["resident_room_profiles"] = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    return self.async_show_form(
                        step_id="residents",
                        data_schema=_residents_schema(self._working_options, self._rooms()),
            description_placeholders=self._resident_placeholders(),
                        errors={"base": "resident_profiles_invalid"},
                    )
            self._working_options.update(values)
            self._persist_working_state()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="residents", data_schema=_residents_schema(self._working_options, self._rooms()),
            description_placeholders=self._resident_placeholders()
        )

    async def async_step_house(self, user_input=None):
        """Compatibility route for flows created before the unified settings UI."""
        self._ensure_working_copy()
        if user_input is not None:
            # Still accept a form that was already open before an update, so no
            # user-entered value is lost during a Home Assistant reload.
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_home_setup()
        # Do not render the former combined house/resident form again: its
        # fields now live canonically under Gebäude and Bewohner.
        return await self.async_step_home_setup()

    async def async_step_personalisation(self, user_input=None):
        """Compatibility route for the former duplicate personalisation form."""
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_home_setup()
        # Personalisation is part of the unified Bewohner form now.
        return await self.async_step_residents()

    async def async_step_forecast(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="forecast", data_schema=_forecast_schema(self._working_options)
        )

    async def async_step_air_quality(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="air_quality",
            data_schema=_air_quality_schema(self._working_options),
        )

    async def async_step_energy(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["heating_system"] = user_input["heating_system"]
            self._persist_working_state()
            return await self.async_step_energy_details()
        return self.async_show_form(
            step_id="energy", data_schema=_energy_system_schema(self._working_options)
        )

    async def async_step_energy_details(self, user_input=None):
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_notification_energy_settings()
        return self.async_show_form(
            step_id="energy_details",
            data_schema=_energy_details_schema(self._working_options),
            description_placeholders={
                "heating_system": (
                    _HEATING_LABELS_DE if _is_de(_flow_language(self.hass)) else _HEATING_LABELS_EN
                ).get(
                    self._working_options.get("heating_system", HEATING_HEAT_PUMP),
                    _txt(_flow_language(self.hass), "Wärmepumpe", "Heat pump"),
                )
            },
        )

    async def async_step_notifications(self, user_input=None):
        self._ensure_working_copy()
        errors = {}
        if user_input is not None:
            submitted = dict(user_input)
            test_now = bool(submitted.pop("test_notification_now", False))
            self._working_options.update(submitted)
            self._persist_working_state()
            if test_now:
                targets = _all_notification_targets({**DEFAULT_OPTIONS, **self._working_options})
                if not targets:
                    errors["test_notification_now"] = "notification_test_no_target"
                else:
                    sent = await _send_targets(
                        self.hass, targets, "FreshAirIQ · Test",
                        _txt(_flow_language(self.hass), "Test erfolgreich: FreshAirIQ kann dieses Benachrichtigungsziel erreichen.",
                             "Test successful: FreshAirIQ can reach this notification target."),
                    )
                    if not sent:
                        errors["test_notification_now"] = "notification_test_failed"
                return self.async_show_form(
                    step_id="notifications",
                    data_schema=_notification_schema(self.hass, self._working_options, self._rooms()),
                    errors=errors,
                )
            return await self.async_step_notification_energy_settings()
        return self.async_show_form(
            step_id="notifications",
            data_schema=_notification_schema(self.hass, self._working_options, self._rooms()),
        )

    async def async_step_statistics(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["statistics_days"] = int(
                user_input["statistics_days"]
            )
            self._persist_working_state()
            return await self.async_step_data_learning_settings()
        return self.async_show_form(
            step_id="statistics",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        native_option_key("statistics_days"),
                        default=_safe_int(self._working_options.get("statistics_days"), 14, minimum=1, maximum=365),
                    ): _number(1, 365, 1, "Tage")
                }
            ),
        )

    async def async_step_diagnostics_sharing(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_data_learning_settings()
        return self.async_show_form(
            step_id="diagnostics_sharing",
            data_schema=_diagnostics_sharing_schema(self._working_options),
        )
