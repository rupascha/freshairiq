# FreshAirIQ 0.25.0.55

## Learning Effectiveness Validation v1

### Neu
- Paired Same-Session Baseline: gelerntes Forecast-Modell gegen ungelerntes 0,03/min-Grundmodell bei exakt gleicher Startlage und Messdauer.
- Lernwirkung insgesamt und nach Raum, Horizont, Jahreszeit, Quelltemperatur, AH-Differenz und Lernstufe.
- Modell-Snapshot-IDs für echte Forecast-Parameteränderungen.
- Gepaarter Replay der aktuellen Forecast-Generation gegen den neuesten abweichenden, zuvor real beobachteten Modell-Snapshot desselben Raums bei identischer aktueller Startlage und Messdauer.
- Früher-vs.-aktuell-Fortschritt ab 12 unabhängigen Lüftungen.
- Dashboard-Anzeige und Diagnoseexport der Learning-Effectiveness-Kennzahlen.

### Evidenzschutz
- Mindestens 12 Raumvergleiche, 8 unabhängige Lüftungen und 4 unterschiedliche Tage.
- Mindestens 5 % Effekt, mindestens 55 % unabhängige Gewinnrate und vollständig positives, nach Lüftungen geclustertes approximatives 95-%-Intervall für den Status „Lernmodell besser belegt“.
- Gleichzeitig gelüftete Räume werden im Konfidenzintervall nicht als unabhängige Experimente behandelt.
- Historische Sessions ohne gespeicherte Baseline werden nicht rückwirkend rekonstruiert.

### Sicherheitsvertrag
- Rein beobachtend: keine Rückkopplung in Raumlernen, Forecast-Koeffizienten, Shadow Learning, Decision Brain oder Empfehlungen.
- Bestehende Prognose-, Lern-, Config-, Dashboard- und Diagnostics-Protokolle bleiben kompatibel; die neuen Felder sind additiv.
- 100 % Pure-Logic-Coverage inklusive Learning Effectiveness.

### Basis
- Baut ausschließlich additiv auf FreshAirIQ 0.25.0.54 – Production Incident Replay Foundation auf; Replay-Snapshot, Support-Incident- und Produktions-Replay-Logik bleiben erhalten.
