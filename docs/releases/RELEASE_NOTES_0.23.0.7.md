# FreshAirIQ 0.23.0.8 — Native Dashboard Launcher Hotfix

This hotfix removes `custom:freshairiq-card` from the automatically generated dashboard content.

## What changed

- The generated dashboard now contains a Home Assistant Core `tile` card bound to `sensor.freshairiq_status`.
- Tapping the tile navigates to `/freshairiq-safe`, where the full FreshAirIQ UI is loaded through Home Assistant's custom panel system.
- The compatibility `custom:freshairiq` dashboard strategy generates native Lovelace content only.
- The legacy custom card remains packaged for backwards compatibility with manually maintained dashboards.
- No additional HACS cards or integrations are required.

## Scope

No recommendation, IQ/learning, forecast, room, sensor, settings or diagnostics logic was changed.
