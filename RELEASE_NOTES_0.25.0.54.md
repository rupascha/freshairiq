# FreshAirIQ 0.25.0.54 — Production Incident Replay Foundation

- Extends privacy-safe sensor incidents with a versioned, identity-free replay snapshot.
- Preserves only aggregate decision inputs: valid-room count, sensor quality classes/counts and outdoor quality state.
- Adds a deterministic replay runner that executes the existing production `build_recommendation()` engine rather than duplicating decision logic.
- Adds regression contracts proving all-invalid sensor states reproduce `sensor_error`, while mixed valid/invalid states do not falsely reproduce it.
- No room names, room keys, entity IDs or free text are added to the replay snapshot.
