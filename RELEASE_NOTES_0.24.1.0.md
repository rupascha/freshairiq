# FreshAirIQ 0.24.1.0 — Robustness & Long-Term Data Foundation

## Schwerpunkt
Diese Version beginnt die systematische Abarbeitung der FreshAirIQ-1.0-Qualitätsgates. Es wurden bewusst keine neuen Komfortfunktionen priorisiert.

## Behoben
- Dashboard-Settings-API: fehlender Import von `CONF_ROOM_INCLUDE_CALCULATIONS` konnte beim Speichern/Bearbeiten eines Raums einen `NameError` auslösen.
- Beschädigte Datums-Schlüssel oder Temperaturpunkte im persistenten Storage können die Historienbereinigung nicht mehr abbrechen.
- Nicht-finite Sessionwerte (`NaN`/`inf`) werden vor der Statistikaggregation neutralisiert und vergiften keine Langzeitstatistik mehr.

## Verbessert
- Kompakte Tages-/Sessionhistorien werden bis zu 730 Tage lokal vorgehalten.
- Dashboard-Auswertungszeitraum von 1–30 auf 1–365 Tage erweitert.
- Hochaufgelöste Temperaturpunkte bleiben bewusst auf 30 Tage begrenzt, um Storage und Frontend klein zu halten.
- Weather-Future- und Settings-API-Pfade erhalten erstmals gezielte automatisierte Tests.

## Verifikation
- 363/363 Tests bestanden.
- Gemessene Backend-Coverage von 43 % auf 48 % erhöht.
- `weather_future.py`: 95 % Coverage.
- Python-Kompilierung, JSON und Frontend-Syntax werden zusätzlich geprüft.

## Wichtig
Das 1.0-Ziel von >=95 % belastbarer Backend-Coverage ist noch nicht erreicht. Diese Version ist ein kontrollierter Qualitätsfortschritt, kein Abschluss der Master-Roadmap.
