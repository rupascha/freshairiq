# FreshAirIQ 0.20.2.3

Hotfix für Prognose-Vertrauen, exakte Maximaldauer und Release-Hygiene.

## Änderungen

- Die Kurzzeit-Prognose kann nicht mehr allein durch wenige Live-Beobachtungen auf 95 % Sicherheit springen. Die Obergrenze berücksichtigt jetzt persistente Lernproben, abgeschlossene Outcome-Feedbacks und Forecast-Beobachtungen.
- Der prognostizierte effiziente Schließzeitpunkt respektiert die konfigurierte Maximaldauer exakt. Bei 19 Minuten bereits gelüftet und 20 Minuten Maximum wird daher `noch ca. 1 min` statt `noch ca. 5 min` berechnet.
- Die Dashboard-Erklärung stellt klar, dass Heizsystem und Energiepreis nur die Wärmeverlust-/Kostenschätzung beeinflussen und nicht die physikalische Feuchteprognose.
- Das veröffentlichte ZIP enthält keine `__pycache__`, `.pytest_cache` oder `*.pyc` Dateien.
