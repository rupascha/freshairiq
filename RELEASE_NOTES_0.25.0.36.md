# FreshAirIQ 0.25.0.36 – Partial Forecast Validation Hotfix

Hotfix auf Basis von 0.25.0.35. Keine Lockerung der bestehenden Messqualitäts- oder Timestamp-Gates.

## Änderung
- Hauslüftungen mit gemischter Sensorqualität werden nicht mehr vollständig von der Genauigkeitswertung ausgeschlossen.
- Die Genauigkeit wird ausschließlich aus den bereits streng als `prediction_comparable` freigegebenen Raumsessions berechnet.
- Nicht ausreichend synchrone Räume bleiben im Ergebnis sichtbar, werden aber aus der Genauigkeitswertung ausgeschlossen.
- Räume erhalten den Diagnosezustand `valid`, `restricted`, `not_comparable` oder `unavailable`.
- Die Oberfläche kennzeichnet Teilvalidierungen und nennt verwertbare sowie ausgeschlossene Räume.
- Das bestehende Lern-Gate bleibt unverändert: nur bereits als lernfähig freigegebene Sessions dürfen das Modell beeinflussen.

## Sicherheit
Der Hotfix verändert weder Lüftungsempfehlungs-Schwellen noch Prognosemodell, Sensor-Gates oder Lernfreigaben. Er korrigiert ausschließlich Aggregation und Darstellung bereits vorhandener, streng validierter Prognoseevidenz.
