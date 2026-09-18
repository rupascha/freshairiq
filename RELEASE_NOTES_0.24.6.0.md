# FreshAirIQ 0.24.6.0

## Quality milestone: honest 95% pure-logic gate

This release is a hardening/release-engineering milestone. It does not redesign the proven ventilation physics.

- 498 regression/hardening tests pass locally.
- Pure-logic coverage is now **95.09%**, measured only across modules without a direct Home Assistant import.
- CI now enforces a real **>=95% pure-logic coverage gate** using `.coveragerc-pure`.
- Home Assistant runtime modules are measured separately in the HA CI job instead of being mixed into the pure-logic number.
- Fixed a release-engineering bug where the previous `--cov=custom_components.freshairiq --cov-fail-under=92.9` command also counted unexecuted HA runtime modules and therefore could not truthfully satisfy the advertised gate.
- Hardened Anticipation, Decision Engine, Language Confidence and Live Coach against `NaN`/`inf` values.
- Added branch regression for anticipation/pre-ventilation, locked live states, adaptive behaviour duration, weather wait options, night/routine paths, decision refinements, model-learning rejection paths and legacy runtime coordinator fallbacks.
- No intended change to valid-input ventilation physics or learned production coefficients.
