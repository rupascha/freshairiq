# FreshAirIQ 0.2.0 – Devices & Room Management

This release turns the technical preview into a proper multi-device Home Assistant integration.

## New

- Integration is declared as a **hub** instead of a helper.
- A central **FreshAirIQ** device is created for house-level entities.
- Every configured room gets its own Home Assistant device.
- Room entities are grouped below their room device.
- The **Configure** flow now provides a menu for:
  - outdoor-air source
  - room management
  - V14.2.1 model settings
- Rooms can be added after initial setup.
- Existing rooms can be edited without deleting/re-adding the integration.
- Rooms can be removed from the configuration.
- Multiple ventilation contacts and ANY/ALL path logic remain supported.
- Room volume now has an explicit input mode:
  - direct m³
  - length × width × height
- Existing V0.1.x entries migrate automatically to config schema version 3.

## Migration

Replace the existing `custom_components/freshairiq` directory with the V0.3.0 directory and restart Home Assistant. The existing config entry is migrated; rooms do not need to be entered again.

## Test status

Python syntax, JSON translations/manifest and the calculation model were validated outside Home Assistant. Real Home Assistant UI/device-registry behavior must still be tested on a running 2026.9 instance before public release.
