# FreshAirIQ 0.25.0.12 – Frontend Single Registration Hotfix

Dieser Hotfix behebt einen erneut vorhandenen doppelten Frontend-Ladeweg, der insbesondere in WebKit/iPad-Kontexten sporadisch als generischer Lovelace-„Konfigurationsfehler“ sichtbar werden kann.

## Änderung
- Storage-Lovelace registriert `freshairiq-card.js` genau einmal als verwaltete Modul-Resource.
- Der globale `add_extra_js_url`-Pfad wird nur noch verwendet, wenn Storage-Resources nicht verfügbar sind oder ihre Registrierung fehlschlägt.
- Alte Loader- und doppelte FreshAirIQ-Resources werden weiterhin auf eine direkte `freshairiq-card.js`-Resource migriert bzw. entfernt.
- `freshairiq-loader.js` bleibt außerhalb des aktiven Dashboard-Startpfads.

Keine Änderungen an Lüftungslogik, Prognosen, Lernen, Grenzwerten, Sensorverarbeitung oder Dashboard-Fachlogik.
