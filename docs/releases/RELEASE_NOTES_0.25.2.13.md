# FreshAirIQ 0.25.2.13 — Settings Surface Parity Contract Hotfix

This hotfix verifies and locks the two configuration surfaces to one canonical configuration.

- Devices & Services and Dashboard settings read/write the same ConfigEntry data/options.
- Every canonical native global option is covered by the Dashboard settings surface.
- Room configuration and per-contact settings use the same canonical room storage.
- Dashboard room changes synchronize Home Assistant room subentries.
- Native room changes synchronize the canonical parent room data consumed by the Dashboard.
- Reopening Dashboard settings forces a fresh canonical read.
- Regression coverage prevents future settings from silently appearing on only one surface.
