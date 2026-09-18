# FreshAirIQ 0.20.3.0 — Validation Engine v1

## Neu
- Persistente, vom Lernmodell getrennte Forecast-Validierung für abgeschlossene Lüftungen.
- Eine Bewertung wird nur erzeugt, wenn eingefrorene Startprognose und reale Messung dieselbe Zeitbasis besitzen.
- Objektive Kennzahlen: Feuchte-MAE, Feuchte-RMSE, Bias, Richtungsgenauigkeit, Temperatur-MAE, Schließzeit-MAE und Kosten-MAE.
- Raumbezogene Qualitätsstatistik für vergleichbare Lüftungen.
- 30-Tage-Validierungshistorie mit Deduplizierung und Größenlimit.
- Validierungsdaten werden in Coordinator-Daten und Diagnoseexport aufgenommen.
- Diagnose-Schema auf Version 4 erweitert.

## Bewusst nicht verändert
- Keine Prognoseformel wurde geändert.
- Keine Lernkoeffizienten wurden geändert.
- Keine Empfehlungsschwellen wurden geändert.
- Validation Engine misst ausschließlich; sie greift nicht in das adaptive Lernen ein.
