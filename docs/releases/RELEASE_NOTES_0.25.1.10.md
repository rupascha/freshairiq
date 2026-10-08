# FreshAirIQ v0.25.1.13 — Quality Hardening Hotfix

- Narrows the temporary sensor-recovery guard to climate sources required for humidity calculations; window contacts remain handled by their dedicated startup/session protection.
- Adds defensive startup-sensor classification tests and restores the project's pure-logic coverage gate to 100%.
- Adds a real browser regression scenario for restoring the exact dashboard page position after an overlay closes, including a delayed Home Assistant/WebView layout scroll.
- Pins the Playwright frontend quality dependency and adds the npm lock contract required by the clean CI frontend job.
- Keeps the v0.25.1.9 Freshy state animations and ventilation/learning behavior unchanged outside the audited fixes.
