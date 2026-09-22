"""Shared settings contract for FreshAirIQ configuration surfaces.

This module deliberately has no Home Assistant imports so it can be consumed by
the native options flow, dashboard API and lightweight tests without creating
config-flow/runtime import coupling.
"""
from __future__ import annotations

# Canonical contract for every preference exposed through Home Assistant's
# native Devices & Services options flow. The dashboard settings API consumes
# this exact set, so both surfaces stay in lockstep.
NATIVE_OPTION_KEYS = frozenset({
    # model
    "start_rh", "high_rh", "target_rh", "min_delta", "min_delta_high_rh",
    "close_delta", "threshold_mode", "min_potential_percent_total_water",
    "min_potential_total_ml", "min_potential_room_ml", "min_duration_min",
    "max_duration_min", "post_ventilation_stabilization_min",
    "repeat_recommendation_cooldown_min", "repeat_min_benefit_ml",
    "min_return_next_5_min_ml", "max_temp_loss_next_5_min_c",
    "min_efficiency_ml_per_01c", "surface_factor", "mould_warn_surface_rh",
    "mould_critical_surface_rh", "co2_warn", "co2_critical",
    "learning_enabled", "learning_max_duration_min",
    # cross ventilation / profile / forecast / air quality
    "cross_ventilation_pairs", "cross_zone_connections", "operating_profile",
    "personalisation_enabled", "thermal_preference", "personal_priority",
    "night_window_preference",
    "cooling_start_temp_c", "cooling_min_outdoor_delta_c",
    "cooling_max_indoor_rh", "cooling_max_moisture_gain_5min_ml",
    "forecast_horizon_min", "pollen_enabled", "pollen_max",
    "pollen_strict_veto", "wind_orientation_enabled",
    "voc_sensor_enabled", "pm25_sensor_enabled", "illuminance_sensor_enabled",
    "voc_warn", "voc_critical", "pm25_warn", "pm25_critical",
    "humidify_below_rh", "shade_above_temp_c", "shade_min_illuminance_lx",
    # household / presence
    "property_type", "adult_occupants", "child_occupants",
    "adult_presence_entities", "child_presence_entities",
    "adult_resident_names", "child_resident_names", "resident_room_profiles",
    "presence_sensor_entities", "pet_safe_presence_entities",
    "pets_in_household", "untracked_follow_household",
    "night_start_hour", "night_end_hour", "night_forecast_enabled",
    # energy
    "heating_system", "electricity_price_per_kwh", "heat_pump_cop",
    "gas_price_per_kwh", "gas_efficiency", "district_price_per_kwh",
    "district_efficiency", "oil_price_per_liter", "oil_kwh_per_liter",
    "oil_efficiency",
    # notifications
    "notifications_enabled", "notification_targets", "notification_scope",
    "notification_room_keys", "notify_ventilate", "notify_close",
    "notify_complete", "notify_cooling", "notify_mould", "notify_sensor",
    "notify_night", "notify_learning", "notification_cooldown_min",
    # statistics / optional diagnostics sharing
    "statistics_days", "diagnostics_reporting_mode",
    "diagnostics_include_client_context",
})


def native_option_key(key: str) -> str:
    """Return a canonical native option key or fail fast for drift/typos.

    Config-flow schemas call this for every option field. This makes
    ``NATIVE_OPTION_KEYS`` an executable contract instead of documentation only.
    """
    if key not in NATIVE_OPTION_KEYS:
        raise KeyError(f"Unknown FreshAirIQ native option key: {key}")
    return key
