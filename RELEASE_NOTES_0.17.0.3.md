# FreshAirIQ v0.17.0.3 – Sensorbestätigung Hotfix

Hotfix ausschließlich für zu frühe Schließentscheidungen auf Basis von v0.17.0.2.

## Änderung
- Eine Schließentscheidung wird erst freigegeben, wenn mindestens **zwei unterschiedliche neue Luftfeuchte-Sensormessungen nach dem Start der Lüftung** eingegangen sind.
- Der beim Öffnen bereits vorhandene Messwert zählt nicht.
- Reine Coordinator-/Timer-Aktualisierungen zählen nicht; entscheidend ist `last_updated` des konfigurierten Luftfeuchtesensors.
- Nach Home-Assistant-/Integrations-Neustart wird ein restaurierter Sensorzustand nicht als neue Messung gewertet.
- Bis zur zweiten neuen Messung bleibt die Lüftung aktiv und die Begründung zeigt `(0/2)` bzw. `(1/2)`.
- Ab der zweiten neuen Messung greift unverändert die bisherige Schließlogik.

Keine Änderungen an Prognoseberechnung, Lernmodell, Raumpriorisierung, Pollen-, Schimmel-, Querlüftungs- oder übriger UI-Logik.
