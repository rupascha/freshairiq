# FreshAirIQ 0.24.7.0

## Home Assistant runtime & configuration hardening

This release moves FreshAirIQ from import-only Home Assistant smoke tests toward real config-flow verification. It adds a native parent reconfigure flow for the outdoor-air source, a Home Assistant custom-component test harness in CI, duplicate-entry and full setup-flow regression tests, and a separate minimum-supported Home Assistant 2026.8 import-compatibility job.

Persisted configuration is now treated as untrusted input in additional config-flow paths. Invalid/non-finite room sort orders, contact delays and statistics retention values fall back to bounded defaults instead of making configuration pages fail. The optional Intervention Engine now also rejects NaN/Infinity sensor values.

A `quality_scale.yaml` file now tracks Home Assistant Bronze/Silver/Gold/Platinum progress honestly. Documentation now includes reconfiguration, removal, action usage, troubleshooting and known limitations.

Local release verification: 501/501 pure regression tests pass and the pure-logic gate remains above 95%. Real Home Assistant runtime/config-flow tests are designed to run in CI because Home Assistant is not installed in the offline build container.
