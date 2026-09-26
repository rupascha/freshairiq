# FreshAirIQ 0.23.0.6 — Native Dashboard Wrapper Hotfix

This hotfix changes only the automatically generated Lovelace dashboard structure.

- FreshAirIQ is no longer emitted as the direct top-level card of the generated view.
- A native Home Assistant `vertical-stack` is created first and contains `custom:freshairiq-card`.
- This gives Lovelace a native top-level element during cold/mobile view construction and reduces exposure to the current custom-card resolver race.
- The safe custom panel at `/freshairiq-safe` remains unchanged.
- Recommendation, forecast, IQ/learning, room, sensor and settings logic are unchanged.
