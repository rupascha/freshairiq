# FreshAirIQ v0.25.0.76 – Home Assistant Room Import Hotfix

## Home Assistant room/floor import
- Adds an import action to FreshAirIQ room management.
- Reads Home Assistant Areas and their Floor assignments from the native registries.
- Lets the user select multiple HA areas at once.
- Reuses the HA room/area name and floor automatically.
- Existing FreshAirIQ room names are excluded to avoid accidental duplicates.
- FreshAirIQ-specific data such as volume and sensors is completed room by room before import.
- Imported rooms start with calculations disabled until the user explicitly provides the required FreshAirIQ inputs.

## Scope
- No ventilation, learning, diagnostics or frontend scroll/navigation logic changed.
