# FreshAirIQ 0.24.12.0

## Verification-focused release

This release deliberately avoids new ventilation features and concentrates on config-flow robustness and test coverage.

### Fixed
- Contact-delay values from old/corrupt config entries are now sanitized with `_safe_int()` in every delay-editing path.
- This closes a remaining case where opening the global options or native room-subentry delay page could raise `ValueError` before the user had a chance to repair the value.
- Submitted delay values are bounded to 0–600 seconds consistently across the affected flows.

### Test expansion
The real Home Assistant CI suite now additionally exercises:
- recovery from an incomplete per-opening reference sensor pair;
- declining a legacy import and continuing through normal setup;
- accepting a legacy import;
- options-flow recovery from an incomplete outdoor temperature/humidity pair;
- immediate persistence of statistics settings;
- reset-to-defaults persistence.

A local AST regression guard prevents raw `int()` conversion of persisted/contact-delay form values from being reintroduced.

### Verification
- 507/507 local regression tests pass.
- Pure-logic coverage remains above the 95% release gate.
- Real Home Assistant tests are compiled locally but must execute in the HA CI job because Home Assistant is not installed in the local offline environment.

No ventilation physics, forecasting coefficients, learning rates, recommendation thresholds or dashboard behaviour were changed by this release.
