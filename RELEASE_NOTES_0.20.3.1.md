# FreshAirIQ 0.20.3.1 — Validation Engine v2

## Änderungen
- Zeitaufgelöste Forecast-Timeline je Lüftungssession: Start, 5-Minuten-Checkpoints und Ende.
- Jeder Live-Checkpoint prognostiziert den Endzustand am ursprünglich eingefrorenen Zielzeitpunkt.
- Tatsächlicher Feuchte- und Temperaturverlauf wird parallel zur Prognose gespeichert.
- Validation Engine bewertet, ob sich die Live-Prognose gegenüber der Startprognose verbessert oder verschlechtert.
- Neue Kennzahlen: Timeline-Start-MAE, letzter Timeline-MAE und Verbesserungsquote.
- Start-Snapshot bei leicht verzögertem ersten Sensorframe korrigiert: bereits eingetretener Effekt wird in die Endprognose einbezogen und die Restdauer korrekt verwendet.
- Laufende Forecast-/Timeline-Daten bleiben bei einem manuellen Lernreset erhalten.

## Unverändert
- Die Validation Engine verändert keine Lernkoeffizienten.
- Prognose-, Empfehlungs- und Hauslüftungslogik bleiben außerhalb der beschriebenen Validierungs-/Snapshot-Korrektur unverändert.
