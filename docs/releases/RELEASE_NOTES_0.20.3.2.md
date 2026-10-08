# FreshAirIQ 0.20.3.2 — Backtest Engine v1

## Neu
- Historische Backtesting-Schicht auf Basis der unveränderlichen Forecast-Snapshots der Validation Engine.
- Automatische Qualitätsauswertung nach Prognosehorizont, Confidence-Bereich, Raum und FreshAirIQ-Modellversion.
- Replay-Kurve für Start-, +5-, +10-, +15- und weitere Timeline-Prognosen, damit sichtbar wird, ob das Modell während einer Lüftung konvergiert.
- Version-gegen-Version-Vergleich ab mindestens drei vergleichbaren Raum-Samples je Version.
- Confidence-Kalibrierung: gemeldete Sicherheit wird der tatsächlich erreichten Betragsgenauigkeit gegenübergestellt.
- P90-Feuchtefehler und Liste der größten Ausreißer zur gezielten Fehlersuche.
- Backtest-Daten stehen am Status-Transport und im Diagnoseexport zur Verfügung.
- Diagnose-Schema auf Version 5 erweitert.

## Bewusst nicht verändert
- Keine Prognoseformel geändert.
- Keine Lernkoeffizienten geändert.
- Keine Empfehlungs- oder Schließschwellen geändert.
- Keine historischen Daten werden nachträglich neu interpretiert oder zum Lernen verwendet.
- Backtesting ist rein beobachtend und hat keinen Einfluss auf Live-Entscheidungen.
