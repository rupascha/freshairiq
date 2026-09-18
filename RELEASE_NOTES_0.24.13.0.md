# FreshAirIQ 0.24.13.0

## HA runtime coverage measurement release

This release keeps FreshAirIQ's ventilation, forecasting, learning and dashboard behaviour frozen and focuses on proving the existing Home Assistant integration surface.

### Real-HA flow test expansion
The Home Assistant runtime suite now additionally exercises:
- every top-level options section;
- rendering of all user-visible options leaf pages from persisted configuration;
- room-management menu behaviour with and without existing rooms;
- native room config-subentry creation for a sensor-only room;
- duplicate room-name validation and recovery in the native subentry flow.

### Measurable HA runtime coverage
The `ha-runtime` GitHub Actions job now:
- emits a machine-readable `coverage-ha.json` report;
- prints both total measured integration coverage and the dedicated `config_flow.py` percentage into the GitHub Actions job summary;
- uploads the raw HA runtime coverage report as the `freshairiq-ha-runtime-coverage` artifact.

A small reporting tool and local regression contract protect this measurement pipeline. This deliberately does **not** introduce a guessed HA-runtime coverage threshold: the first real CI result should establish the measured baseline before a hard gate is selected.

### Verification
- 509/509 local regression tests pass.
- Pure-logic coverage remains 95.06%, above the 95% release gate.
- Python compilation of the expanded HA tests and reporting tool passes locally.
- Home Assistant itself is not installed in the local offline environment, so the HA-runtime test suite still requires the GitHub CI job for execution.

No ventilation physics, forecasting coefficients, learning rates, recommendation thresholds or dashboard behaviour were changed by this release.
