# FreshAirIQ 0.25.2.32

## Hotfix

- Adds bounded, privacy-safe notification delivery diagnostics to persistent runtime state and manual diagnostic exports.
- Records send outcome, event/scope, configured target count, available notify-service count, suppression reason and exception class.
- Does not export notify entity IDs, service names, notification title/message content or resident names.
- Keeps the v0.25.2.31 notification-processing short-circuit fix unchanged.
