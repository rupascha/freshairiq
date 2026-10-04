# FreshAirIQ 0.25.3.3

## Runtime polish hotfix

- Suppresses transient sensor-error push notifications while the existing 90-second startup/recovery guard is active; persistent sensor failures remain eligible afterwards.
- Removes the obsolete visible technical support-code card from the dashboard while retaining internal diagnostic collection.
- Strengthens room-overview contrast with an explicitly dark room surface and high-contrast room names.
- Redesigns the local ventilation PDF into a structured multi-page report with summary tiles, per-ventilation cards and clear before/after climate values.
- Replaces the unsupported Unicode arrow in the dependency-free WinAnsi PDF path so climate values no longer render with question marks.
