# FreshAirIQ 0.21.0.3 — Frontend Registration Hotfix

- Registriert die gebündelte FreshAirIQ-Karte zusätzlich als echte Lovelace-`module`-Ressource im Storage-Modus.
- Die Karte erscheint dadurch auf frischen Home-Assistant-Installationen und neuen Browsern/WebViews zuverlässig im visuellen Karten-Picker.
- Der bisherige globale Frontend-Ladeweg bleibt als kompatibler Fallback für YAML-Ressourcen und Nicht-Lovelace-Panels erhalten.
- Bestehende FreshAirIQ-Ressourcen werden versionssicher aktualisiert, statt doppelt angelegt zu werden.
- Vor Lesen oder Anlegen der Lovelace-Ressource wird der Storage explizit geladen; dadurch bleibt die Registrierung auch mit älteren Lazy-Load-Verhalten robust und kann keine vorhandenen Dashboard-Ressourcen überschreiben.
- Fehler der Frontend-Ressourcenregistrierung blockieren niemals das FreshAirIQ-Backend und werden eindeutig im Home-Assistant-Log protokolliert.
- `lovelace` ist nun explizite Integrationsabhängigkeit, damit die Ressourcenverwaltung vor FreshAirIQ verfügbar ist.
- Keine Änderungen an Physik, Prognose, Lernen, Intelligence, Empfehlungen oder Sicherheitsgrenzen.
