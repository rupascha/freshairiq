# FreshAirIQ 0.18.2.4

Hotfix für CO₂-Priorisierung und Nachtzeitlogik.

- CO₂-Warnschwelle und kritische CO₂-Schwelle werden jetzt konsistent getrennt.
- Nur kritisches CO₂ übersteuert strikte Komfort-Vetos wie Pollen; die Warnschwelle bleibt eine erhöhte Priorität ohne kritischen Override.
- Kritisches CO₂ erzeugt auch bei leicht feuchterer Außen-/Referenzluft eine priorisierte Lüftungsempfehlung.
- Empfehlungstexte erklären in diesem Fall den Feuchte-Nachteil korrekt, statt fälschlich von trockener Außenluft zu sprechen.
- Nachtende wird minutengenau berechnet, auch wenn aktuelle Stunde und Endstunde identisch sind (z. B. 07:15 bei Ende 07:30).
- Identische Nachtstart-/Nachtendzeit deaktiviert das Nachtfenster konsistent statt es teils als 24 Stunden zu interpretieren.
- Regressionstests für alle genannten Fälle ergänzt.
