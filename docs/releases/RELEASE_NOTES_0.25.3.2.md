# FreshAirIQ v0.25.3.2

Hotfix for two runtime issues found after v0.25.3.1.

- Fixes the local ventilation-log PDF export HTTP 500 error by resolving the loaded runtime from the actual Home Assistant ConfigEntry.
- Fixes missing German/English labels and help text for Mean, Median, Minimum and Maximum in Devices & Services → Manage rooms → Add/Edit room.
- Keeps all v0.25.3/v0.25.3.1 multi-sensor, notification, diagnostics and ventilation-log functionality unchanged otherwise.
