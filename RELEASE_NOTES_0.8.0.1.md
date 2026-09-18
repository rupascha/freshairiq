# FreshAirIQ 0.8.0.1

Hotfix for upgrades from 0.7.x.

- Fixes migration crash:
  `ConfigEntries.async_update_entry() got an unexpected keyword argument 'subentries'`.
- The migration now updates only supported ConfigEntry fields.
- Existing rooms are mirrored into native Home Assistant room subentries during
  normal setup via the dedicated subentry APIs.
- No FreshAirIQ room configuration or learning data is intentionally discarded.
