# FreshAirIQ 0.20.1.3

## Diagnostics retention hotfix

FreshAirIQ diagnostics now use adaptive, information-preserving sampling so a typical 30-day beta trace can remain inside the portable export budget.

- Normal idle operation: compact trend sample every 15 minutes.
- Active ventilation: compact trend sample every 2 minutes.
- Window transitions, configuration changes and completed ventilation sessions: immediate full-fidelity event record.
- Existing retained pre-v3 routine rows are compacted before the local storage cap is enforced.
- The exporter also compacts compatible legacy routine rows that are still present while preserving full event records.
- Export remains limited to 24 MiB for browser and mobile memory safety.

This hotfix does not change FreshAirIQ's climate calculations, recommendations, learning, energy model or dashboard behavior.
