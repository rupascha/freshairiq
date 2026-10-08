# FreshAirIQ v0.17.0.7 – Dynamische Restdauer Hotfix

## Änderung
- Während einer bereits laufenden Lüftung wird `duration_min` als Restdauer behandelt und nicht mehr auf die konfigurierte Mindestlüftungsdauer angehoben.
- Beispiel: 0,5 Minuten Restzeit bleiben 0,5 Minuten und werden nicht wieder zu 3 Minuten.
- Eine echte Schließentscheidung bleibt weiterhin eine Sofortaktion mit 0,0 Minuten.
- Bei einer neu gestarteten Lüftung gilt die konfigurierte Mindestlüftungsdauer weiterhin unverändert.

## Unverändert
Keine Änderungen an Lernmodell, Prognose, Zwei-Messwerte-Sperre, 15-Minuten-Fallback, Pollen, Schimmel, Querlüftung, Raumpriorisierung oder Dashboard-Logik.
