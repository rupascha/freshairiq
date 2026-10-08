# FreshAirIQ 0.23.0.5 — Mobile Configuration Error Safe-Panel Hotfix

- Ergänzt ein automatisch registriertes Home-Assistant-Custom-Panel **FreshAirIQ** unter `/freshairiq-safe`.
- Das Panel umgeht bewusst den Lovelace-Custom-Card-Resolver, der in aktuellen Home-Assistant-Frontends bei Kaltstarts trotz korrekt registrierter Custom Elements sporadisch einen permanenten generischen „Configuration error“ erzeugen kann.
- Die bestehende `custom:freshairiq-card` bleibt unverändert verfügbar; keine Dashboard-, Lern-, Prognose- oder Empfehlungsfunktion wurde entfernt.
- Das Panel lädt dieselbe FreshAirIQ-Implementierung und verwendet damit dieselben Daten, Einstellungen und Funktionen wie die Dashboard-Karte.
- `panel_custom` wurde als explizite Integrationsabhängigkeit ergänzt.
