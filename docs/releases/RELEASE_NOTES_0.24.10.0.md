# FreshAirIQ 0.24.10.0

This release focuses on Home Assistant entity quality and lifecycle correctness without changing FreshAirIQ's ventilation physics or learning coefficients.

## Home Assistant entity quality

- Room sensors now combine room-data quality with the coordinator's native availability state.
- Native sensor device classes are used where semantics are unambiguous: relative humidity, absolute humidity, duration, absolute temperature and temperature delta.
- Static entity icons moved to `icons.json`, Home Assistant's preferred icon-translation mechanism.
- Three low-value learning diagnostics are disabled by default for newly created entity-registry entries to reduce recorder noise. Existing installations retain their current enabled/disabled choices.

## Source availability logging

FreshAirIQ now logs required source loss and recovery exactly once per transition at INFO level. Temporary repeated `unavailable` updates no longer create log spam.

## Runtime test expansion

The real-Home-Assistant CI suite now covers coordinator-aware entity availability, device-class/default metadata, source availability transition logging, setup rollback after platform failure, and failure isolation if the Repairs subsystem itself errors.

## Compatibility

No calculation formulas, forecast coefficients, learning rates, configured entity IDs, unique IDs, or dashboard transport payloads were intentionally changed.
