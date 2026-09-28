# FreshAirIQ 0.25.1.22

## Recorder attribute-size hotfix

Home Assistant Recorder no longer attempts to persist the large live dashboard transport attributes published by FreshAirIQ. The full attributes remain available in Home Assistant's live state machine and therefore remain available to the FreshAirIQ dashboard. Per-room dashboard payloads are protected in the same way.

This hotfix does not change ventilation calculations, recommendations, learning calculations, diagnostics export data, room configuration, or dashboard functionality.
