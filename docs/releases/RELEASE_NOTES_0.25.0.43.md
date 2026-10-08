# FreshAirIQ 0.25.0.43 — Device Registry Cleanup Hotfix

- Fixes startup failure in `_async_cleanup_removed_room_registry_entries`.
- Iterates `DeviceRegistry.devices` values instead of mapping keys/device-id strings.
- Defensively skips unexpected registry items so stale-room cleanup cannot block integration setup.
- No ventilation, learning, diagnostics, dashboard, or recommendation logic changed.
