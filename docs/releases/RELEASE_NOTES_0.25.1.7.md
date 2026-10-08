# FreshAirIQ v0.25.1.8

## Hotfix

- Prevents the diagnostics support classifier from escalating the narrow transient startup state where all calculation rooms are still `unknown` while outdoor climate data is simultaneously unavailable.
- Real sensor faults (`missing`, `stale`, `invalid`, `unavailable`), mixed-quality failures, and sensor errors with valid outdoor data continue to produce `FAIQ-SENSOR-DATA-001`.
- Ventilation recommendation and sensor-safety decision logic are unchanged.
- Adds regression coverage for transient startup classification and preservation of real sensor incidents.
