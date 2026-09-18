# FreshAirIQ 0.23.0.4 – Hotfix

## Behoben
- Frontend-Registrierung auf genau einen aktiven Ladeweg umgestellt.
- Storage-Dashboards laden den FreshAirIQ-Bootstrap ausschließlich als Lovelace-Modul.
- `add_extra_js_url` dient nur noch als Fallback für YAML-/Legacy-Konfigurationen oder wenn die Storage-Resource nicht registriert werden kann.
- Verhindert, dass derselbe ES-Modul-Loader während des Home-Assistant-Starts gegen unterschiedliche Custom-Element-Registries registriert wird und anschließend als generischer „Configuration error“ endet.

Keine Änderungen an Empfehlungs-, Lern-, Prognose-, Raum- oder Einstellungslogik.
