"""Constants for FreshAirIQ."""
from __future__ import annotations

DOMAIN = "freshairiq"
VERSION = "0.25.0.56"
PLATFORMS = ["sensor", "binary_sensor", "button", "select", "number"]
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.learning"
DEFAULT_SCAN_INTERVAL = 30

# Diagnostics Hub production endpoint. Public HTTPS is terminated by Cloudflare
# and forwarded through the private Cloudflare Tunnel to the Diagnostics Hub.
DIAGNOSTICS_HUB_ENDPOINT = "https://diagnostics.freshairiq.com"
DIAGNOSTICS_UPLOAD_MAX_BYTES = 2 * 1024 * 1024
DIAGNOSTICS_UPLOAD_TIMEOUT_SECONDS = 20
POST_VENTILATION_RESULT_MINUTES = 5
SESSION_CLOSE_CONFIRM_SECONDS = 3.0
SESSION_END_MEASUREMENT_WAIT_SECONDS = 10.0
LEGACY_DOMAIN = "ventilation_assistant"
CONF_LEGACY_ENTRY_ID = "legacy_entry_id"

CONF_OUTDOOR_WEATHER = "outdoor_weather"
CONF_OUTDOOR_TEMPERATURE = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"
CONF_POLLEN_ENTITY = "pollen_entity"
CONF_ROOMS = "rooms"
CONF_LEVELS = "levels"
CONF_ROOM_NAME = "name"
CONF_ROOM_TEMPERATURE = "temperature"
CONF_ROOM_HUMIDITY = "humidity"
CONF_ROOM_CONTACT = "contact"
CONF_ROOM_CONTACTS = "contacts"
CONF_CONTACT_MODE = "contact_mode"
CONTACT_MODE_ANY = "any"
CONTACT_MODE_ALL = "all"
CONF_ROOM_VOLUME = "volume"
CONF_ROOM_LENGTH = "length"
CONF_ROOM_WIDTH = "width"
CONF_ROOM_HEIGHT = "height"
CONF_VOLUME_MODE = "volume_mode"  # legacy compatibility only
VOLUME_MODE_DIRECT = "direct"
VOLUME_MODE_DIMENSIONS = "dimensions"
CONF_ROOM_REFERENCE_TEMPERATURE = "reference_temperature"
CONF_ROOM_REFERENCE_HUMIDITY = "reference_humidity"
CONF_ROOM_CO2 = "co2"

# Optional room air-quality sensors. They enrich decisions but are never required.
CONF_ROOM_VOC = "voc"
CONF_ROOM_PM25 = "pm25"
CONF_ROOM_ILLUMINANCE = "illuminance"

# Optional room actuators / intervention targets. FreshAirIQ only recommends
# interventions by default; explicit service calls are required for actuation.
CONF_ROOM_COVERS = "covers"  # legacy room-wide fallback; new UI assigns covers per opening
CONF_CONTACT_COVERS = "contact_covers"
CONF_ROOM_CLIMATE = "climate"
CONF_ROOM_EXHAUST_FAN = "exhaust_fan"
CONF_ROOM_SUPPLY_FAN = "supply_fan"
CONF_ROOM_VENTILATION_DEVICE = "ventilation_device"
CONF_ROOM_DEHUMIDIFIER = "dehumidifier"
CONF_ROOM_HUMIDIFIER = "humidifier"
CONF_ROOM_AIR_PURIFIER = "air_purifier"
CONF_CONTACT_DELAY = "contact_delay_seconds"  # legacy room-wide fallback
CONF_CONTACT_DELAYS = "contact_delays"
CONF_CONTACT_ORIENTATIONS = "contact_orientations"
CONF_CONTACT_REFERENCE_TEMPERATURES = "contact_reference_temperatures"
CONF_CONTACT_REFERENCE_HUMIDITIES = "contact_reference_humidities"
CONF_ROOM_FLOOR = "floor"
CONF_ROOM_SORT_ORDER = "sort_order"
CONF_ROOM_INCLUDE_CALCULATIONS = "include_in_calculations"
CONF_ROOM_WINDOW_ORIENTATION = "window_orientation"
CONF_ROOM_MOISTURE_SOURCES = "moisture_sources"
# Optional per-room ventilation relevance threshold. "automatic" preserves the
# established global room threshold; percentage/fixed modes only refine when a
# non-urgent room becomes individually actionable. Safety/health overrides remain authoritative.
CONF_ROOM_THRESHOLD_MODE = "ventilation_threshold_mode"
CONF_ROOM_THRESHOLD_PERCENT = "ventilation_threshold_percent"
CONF_ROOM_THRESHOLD_ML = "ventilation_threshold_ml"
ROOM_THRESHOLD_AUTOMATIC = "automatic"
ROOM_THRESHOLD_PERCENT = "percent_room_water"
ROOM_THRESHOLD_FIXED = "fixed_ml"
MOISTURE_SOURCE_SHOWER = "shower"
MOISTURE_SOURCE_BATH = "bath"
MOISTURE_SOURCE_SAUNA = "sauna"
MOISTURE_SOURCE_COOKING = "cooking"
MOISTURE_SOURCES = [MOISTURE_SOURCE_SHOWER, MOISTURE_SOURCE_BATH, MOISTURE_SOURCE_SAUNA, MOISTURE_SOURCE_COOKING]

FLOOR_BASEMENT = "basement"
FLOOR_GROUND = "ground_floor"
FLOOR_UPPER = "upper_floor"
FLOOR_ATTIC = "attic"
FLOOR_OTHER = "other"

ORIENTATION_UNKNOWN = "unknown"
ORIENTATIONS = ["unknown", "n", "ne", "e", "se", "s", "sw", "w", "nw"]

PROPERTY_HOUSE = "house"  # legacy/general
PROPERTY_APARTMENT = "apartment"
PROPERTY_MAISONETTE = "maisonette"
PROPERTY_ROW_MID = "row_mid"
PROPERTY_ROW_END = "row_end"
PROPERTY_SEMI_DETACHED = "semi_detached"
PROPERTY_DETACHED = "detached"
PROPERTY_MULTI_FAMILY = "multi_family"
PROPERTY_OTHER = "other"
PROPERTY_TYPES = [
    PROPERTY_DETACHED, PROPERTY_SEMI_DETACHED, PROPERTY_ROW_MID, PROPERTY_ROW_END,
    PROPERTY_APARTMENT, PROPERTY_MAISONETTE, PROPERTY_MULTI_FAMILY, PROPERTY_HOUSE, PROPERTY_OTHER,
]

PROFILE_DEHUMIDIFY = "dehumidify"
PROFILE_COMFORT = "comfort"
PROFILE_SUMMER_COOLING = "summer_cooling"

HEATING_HEAT_PUMP = "heat_pump"
HEATING_GAS = "gas"
HEATING_DISTRICT = "district_heating"
HEATING_ELECTRIC = "electric"
HEATING_OIL = "oil"

NOTIFY_SCOPE_ROOM = "room"
NOTIFY_SCOPE_HOUSE = "house"
NOTIFY_SCOPE_BOTH = "both"

DEFAULT_OPTIONS = {
    # V14.2.1 moisture / closing model
    "start_rh": 62.0,
    "high_rh": 68.0,
    "target_rh": 58.0,
    "min_delta": 2.5,
    "min_delta_high_rh": 1.5,
    "close_delta": 0.4,
    # Default recommendation threshold adapts to monitored dwelling size and
    # expected daily moisture production, targeting roughly 3–5 meaningful
    # ventilation cycles per day. Fixed and percentage modes remain available.
    "threshold_mode": "adaptive_home_size",
    "min_potential_percent_total_water": 10.0,
    "min_potential_total_ml": 500.0,
    "min_potential_room_ml": 100.0,
    "min_duration_min": 3.0,
    "max_duration_min": 20.0,
    "min_return_next_5_min_ml": 25.0,
    "post_ventilation_stabilization_min": 4.0,
    "repeat_recommendation_cooldown_min": 120.0,
    "repeat_min_benefit_ml": 80.0,
    "repeat_weather_improvement_g_m3": 1.0,
    "moisture_source_postrun_min": 8.0,
    "house_ventilation_enter_ratio": 0.75,
    "house_ventilation_exit_ratio": 0.50,
    # User-selectable live forecast horizon. The legacy fixed 5-minute fields
    # remain available for backwards compatibility.
    "forecast_horizon_min": 5,
    "max_temp_loss_next_5_min_c": 0.6,
    "min_efficiency_ml_per_01c": 8.0,
    "surface_factor": 0.25,
    "mould_warn_surface_rh": 80.0,
    "mould_critical_surface_rh": 90.0,
    "co2_warn": 1000.0,
    "co2_critical": 1400.0,
    # Optional post-v0.23 sensors are explicitly gated. They can enrich
    # supplemental recommendations and diagnostics, but never alter the
    # canonical ventilation/forecast physics.
    "voc_sensor_enabled": True,
    "pm25_sensor_enabled": True,
    "illuminance_sensor_enabled": True,
    "voc_warn": 600.0,
    "voc_critical": 1200.0,
    "pm25_warn": 15.0,
    "pm25_critical": 35.0,
    "humidify_below_rh": 35.0,
    "shade_above_temp_c": 24.0,
    "shade_min_illuminance_lx": 10000.0,
    "learning_enabled": True,
    "learning_max_duration_min": 120.0,
    "cross_ventilation_pairs": "",
    "cross_zone_connections": "",

    # Operating profiles. Profile-specific adjustments are applied internally;
    # these are the advanced comfort/cooling bounds exposed to the user.
    "operating_profile": PROFILE_COMFORT,
    # Personal Context Engine: presentation preferences only. These never change
    # health/safety thresholds or the physical forecast.
    "personalisation_enabled": True,
    "thermal_preference": "balanced",
    "personal_priority": "balanced",
    "night_window_preference": "automatic",
    "cooling_start_temp_c": 24.0,
    "cooling_min_outdoor_delta_c": 2.0,
    "cooling_max_indoor_rh": 70.0,
    "cooling_max_moisture_gain_5min_ml": 60.0,

    # Building / occupants. Human moisture production is deliberately modelled
    # by FreshAirIQ rather than being a user-tuned parameter. The learned night
    # model gradually receives more weight as valid observations accumulate.
    "property_type": PROPERTY_HOUSE,
    "adult_occupants": 2,
    "child_occupants": 0,
    # Optional HA person/device_tracker entities. Residents without a tracker
    # remain supported; by default they follow the household away/home signal.
    "adult_presence_entities": [],
    "child_presence_entities": [],
    # Optional display names aligned with the resident/tracker order. Names are
    # local presentation context only and never exported through diagnostics.
    "adult_resident_names": "",
    "child_resident_names": "",
    # Compact local JSON written by the dashboard resident-profile editor.
    # Example: {"adult:0":{"room_keys":["office"],"thermal_preference":"warm"}}
    "resident_room_profiles": "{}",
    "untracked_follow_household": True,
    # Optional soft presence evidence. Motion is deliberately weak; true
    # presence sensors can be marked pet-safe and receive more weight.
    "presence_sensor_entities": [],
    "pet_safe_presence_entities": [],
    "pets_in_household": False,
    # Fast, persistent guest controls. Zero means guest mode is inactive.
    "guest_adults": 0,
    "guest_children": 0,
    "night_start_hour": "22:00",
    "night_end_hour": "07:00",
    "night_forecast_enabled": True,

    # Biological/background moisture assumptions used as priors only.
    "adult_night_moisture_ml_h": 45.0,
    "child_night_moisture_ml_h": 30.0,
    "background_night_moisture_ml_h": 10.0,
    "adult_day_moisture_ml": 1000.0,
    "child_day_moisture_ml": 700.0,
    "household_day_moisture_ml": 1000.0,

    # Pollen / local weather assistance.
    "pollen_enabled": False,
    "pollen_max": 4.0,
    "pollen_strict_veto": True,
    "wind_orientation_enabled": True,

    # Energy model. System-specific prices avoid presenting heat-pump-only
    # inputs to gas/oil/district-heating users.
    "heating_system": HEATING_HEAT_PUMP,
    "electricity_price_per_kwh": 0.30,
    "heat_pump_cop": 3.5,
    "gas_price_per_kwh": 0.11,
    "gas_efficiency": 0.92,
    "district_price_per_kwh": 0.15,
    "district_efficiency": 0.98,
    "oil_price_per_liter": 1.00,
    "oil_kwh_per_liter": 10.0,
    "oil_efficiency": 0.88,
    # v0.5 compatibility keys
    "energy_price_per_kwh": 0.30,
    "heating_efficiency": 0.92,

    # Notifications
    "notifications_enabled": False,
    "notification_targets": [],
    "notification_scope": NOTIFY_SCOPE_HOUSE,
    "notification_room_keys": [],
    "notify_ventilate": True,
    "notify_close": True,
    "notify_complete": True,
    "notify_mould": True,
    "notify_sensor": True,
    "notify_night": False,
    "notify_learning": False,
    "notify_cooling": True,
    "notification_cooldown_min": 90,

    # Statistics
    "statistics_days": 14,

    # Optional remote diagnostics sharing. Selecting any non-off mode is an
    # explicit opt-in. v0.25.0.28 is wired only to the private local staging
    # Hub; the default stays off and public rollout still requires HTTPS.
    "diagnostics_reporting_mode": "off",
    "diagnostics_include_client_context": False,

    # Dashboard visibility defaults (card editor can override per card).
    "dashboard_show_temperature": True,
    "dashboard_show_time": True,
    "dashboard_show_next5": True,
    "dashboard_show_night": True,
    "dashboard_show_mould": True,
    "dashboard_show_history": True,
}
