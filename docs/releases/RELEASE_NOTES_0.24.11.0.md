# FreshAirIQ 0.24.11.0

## Runtime typing and single-source lifecycle

This release removes the remaining dual-runtime architecture. `ConfigEntry.runtime_data` is now the only per-entry coordinator runtime source; the legacy `hass.data[DOMAIN]` mirror and all internal fallbacks are gone.

A shared `FreshAirIQConfigEntry` type contract is used by setup/unload/migration, the coordinator, Repairs, entity base, sensor/binary-sensor/button/number/select platforms and the dashboard Settings API. The migrated HA-facing core has fully annotated function signatures and ships a `py.typed` marker.

Three local typing-contract tests protect the migration: they reject unannotated signatures in the migrated surface, any reintroduction of the old runtime mirror/fallback, or loss of the ConfigEntry type alias/typing marker. Real-HA import smoke now also imports the typing module and every entity platform.

`strict-typing` is deliberately still marked `todo`. The Config Flow and a small set of remaining HA-facing edge modules still need the same treatment, and FreshAirIQ will not claim Platinum strict typing until a real mypy strict gate passes against Home Assistant's type information.

## Verified locally

- 506/506 regression tests pass.
- Pure-logic coverage is 95.06%, above the 95% gate.
- Existing ventilation physics, learning coefficients and dashboard behaviour are unchanged.
