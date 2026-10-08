# FreshAirIQ 0.25.2.17

## Forecast-only three-state learning hotfix

- Restores the established recommendation behaviour for both binary and three-state opening contacts: FreshAirIQ recommends whether to ventilate, continue or close, but no longer prescribes tilt versus fully-open ventilation.
- Keeps genuine three-state opening recognition (`closed`, `tilted`, `open`) and the independent `tilted`, `open` and `cross` learning models.
- Uses the actually detected three-state opening mode to select the corresponding learned model for forecasts.
- Preserves the established long, stable opening / probable tilt-or-continuous-ventilation handling for normal two-state contacts.
- Adds privacy-safe three-state learning evidence to rolling/nightly diagnostics: proven-contact count, detected mode, active specialist model, model rate/sample/credit values, forecast snapshot values, quarantine/transient counters and aggregate passage-door learning state.
- Does not export three-state contact entity IDs or entity-keyed passage-door identifiers.
- Keeps diagnostics schema version 15 for this additive payload extension.
