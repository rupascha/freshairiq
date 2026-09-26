# FreshAirIQ 0.6.2 — Reliability Update

This release fixes the remaining issues observed after the 0.6.1 restart/configuration update.

## Fixed

- **Restart/live balance:** completed room-session values are no longer carried into a new session. The house live balance is calculated only from rooms that are actively ventilating.
- **Startup sensor restoration:** FreshAirIQ never finalizes a closed session with `999/-1` startup placeholders. Invalid or stale persisted session baselines are re-based using the first plausible live measurements.
- **Temperature after restart:** a valid recent session keeps its real start temperature; an invalid/stale session is re-based, preventing extreme negative temperature changes.
- **Pollen & wind / Model parameters / Heating details:** dimensionless number selectors no longer serialize a null unit, fixing Home Assistant's `Unknown error occurred` / blank `Fehler` dialogs on affected HA versions.
- **Details popup scroll:** the dialog remembers scroll position continuously and restores it immediately, on animation frames and once after layout stabilization, preventing live updates from jumping to the top.
- **Migration:** repaired the per-contact delay/orientation migration and moved the config-entry schema to version 6.

## Data retention

Room configuration, learned air-exchange rates, IQ sample counts, night-model learning and statistics remain persistent. A normal upgrade does not reset learning data. `__pycache__` is not part of the required installation and may be deleted before copying the release.

## Upgrade

1. Replace `/config/custom_components/freshairiq/` with the directory from this release.
2. Do not copy/create `__pycache__`.
3. Restart Home Assistant completely.
4. Open **Settings → Devices & services → FreshAirIQ → Configure** and verify Pollen & wind, Heating & energy costs, and Model parameters.
5. Open **FreshAirIQ Details**, scroll down, and leave it open through a live sensor update to verify scroll persistence.
