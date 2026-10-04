# FreshAirIQ 0.25.2.35

## Presence Normalization Hotfix

- Centralizes primary presence-state normalization for occupancy and personal context.
- Treats canonical `home`, `not_home` and `away` deterministically.
- Preserves Home Assistant `person.*` zone semantics as away from home.
- Stops classifying unknown/custom `device_tracker.*` states as away by guesswork.
- Adds privacy-safe aggregate presence diagnostics without entity IDs, resident names, or raw custom state values.
