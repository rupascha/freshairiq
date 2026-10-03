# FreshAirIQ 0.25.2.24 — Dashboard Variant Persistence Hotfix

- Fixes the visual card editor snapping back from `FreshAirIQ IQ` to `Classic` when Home Assistant briefly echoes the previous Lovelace card configuration during an editor update.
- Keeps the explicit user selection pending until Home Assistant confirms the same `dashboard_variant` value.
- Re-emits the pending configuration through Home Assistant's `config-changed` contract when a stale echo is received.
- Adds regression coverage for the stale-config echo path without changing the Classic default for new cards.
