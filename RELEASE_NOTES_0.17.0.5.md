# FreshAirIQ v0.17.0.5 – Schließfreigabe-Hotfix

Basis: v0.17.0.4.

Dieser Hotfix korrigiert ausschließlich die drei geprüften Punkte der Messwert-/Schließfreigabe:

- Der Live Coach darf eine laufende Lüftung nicht mehr auf „Jetzt schließen“ umstellen, solange die Raumlogik die Schließentscheidung nicht freigegeben hat.
- Die finale Konsolidierung erzwingt dieselbe Regel als zentrale Invariante, damit auch spätere Entscheidungsschichten die Sperre nicht umgehen können.
- Sensorberichte werden bevorzugt über Home Assistants `last_reported` erkannt; auf älteren HA-Versionen wird kompatibel auf `last_updated` zurückgefallen. Dadurch können auch neue Berichte mit unverändertem Zahlenwert als neue Messung zählen.
- Die Regressionstests wurden auf die gültige Regel angepasst: 0/2 und 1/2 Messungen sperren vor 15 Minuten, 2/2 geben frei, unter 15 Minuten bleibt der Modell-Fallback gesperrt, ab 15 Minuten darf das Modell entscheiden, ohne automatisch schließen zu müssen.

Keine Änderungen an Prognosemodell, Lernmodell, Pollen, Schimmel, Querlüftung, Raumpriorisierung oder Dashboard-Layout.
