# FreshAirIQ 0.24.3.0 — Settings, Notifications & Decision Hardening

0.24.3.0 setzt den 1.0-Härtungspfad fort. Der Schwerpunkt liegt auf bislang schwächer getesteten Laufzeitpfaden und defensivem Verhalten bei beschädigten/Legacy-Daten.

## Verifiziert
- 422 lokale Regression-/Hardening-Tests bestanden.
- Pure-Logic-Coverage: 90,01 %; CI-Floor auf >=90 % angehoben.
- Settings API 92 %, Notifications 97 %, Planner 95 %, Decision Brain 92 %, Post-Close-Stabilisierung 99 %.

## Robustheit
- Dashboard-Settings tolerieren ungültige Legacy-Sortierwerte.
- Benachrichtigungen degradieren bei NaN/inf, ungültigen Sessions und beschädigten Nachtprognosen sicher.
- Post-Close-Stabilisierung toleriert beschädigte Persistenzwerte und naive Legacy-Zeitstempel.
- Realtime-Entscheidungen behalten Vorrang vor Mehrstundenplanung; entsprechende Planner-/Decision-Verträge sind explizit getestet.

## Nicht verändert
- Keine absichtliche Änderung der kanonischen Lüftungsphysik.
- Keine absichtliche Änderung der bestehenden Lernkoeffizienten oder Shadow-Learning-Promotion.
- Die optionale Room Climate Intervention Engine bleibt unverändert verfügbar.

## Weiter offen vor 1.0
- >=95 % belastbare Coverage inklusive HA-Runtime-Module.
- 100 % kritische Config-Flow-/Coordinator-/Migration-Pfade.
- Browser-E2E und reale Alpha/Beta-Haushalte.
