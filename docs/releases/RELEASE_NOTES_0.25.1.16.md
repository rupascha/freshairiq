# FreshAirIQ 0.25.1.16

## Reliability Foundation v1

- Release-Metadaten zentral synchronisiert.
- Verhaltensbasierte Regression-Gates konsolidiert.
- Release wird bei roten Pflichtprüfungen blockiert.

### Coverage quality-gate hardening
- The 100% promise is now explicitly **Pure-Logic line coverage**; HA/aiohttp-bound adapters remain in the dedicated HA runtime coverage gate.
- Pure vs. HA-bound modules are classified fail-closed from imports, preventing a new pure module from silently disappearing from the denominator.
- Coverage now starts before pytest imports project modules and verifies denominator integrity from the generated JSON report.
- Current canonical Pure-Logic result: **6,194 / 6,194 statements (100.00%) across 39 modules**.
