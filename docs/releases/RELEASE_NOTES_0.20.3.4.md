# FreshAirIQ 0.20.3.4 — Post-close stabilization v1

- Adds a 10-minute post-close observation linked to each completed ventilation session.
- Quantifies moisture rebound, continued drying, retained moisture removal and temperature recovery.
- Rejects observations contaminated by a reopened window, an internal moisture source or poor measurement-frame timing.
- Keeps this layer diagnostic-only: production forecast and adaptive coefficients are unchanged.
- Persists up to 30 days of bounded stabilization outcomes and exports them in diagnostics schema 7.
