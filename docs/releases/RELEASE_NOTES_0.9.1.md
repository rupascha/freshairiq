# FreshAirIQ v0.9.1 — Stability Hotfix

Basis: v0.9.0. Die Berechnungs-, Forecast-, Lern- und Recommendation-Logik aus v0.9.0 bleibt erhalten. Der Hotfix behebt Konfigurations-/Darstellungsfehler und vervollständigt die Presence-UX.

## Behoben
- **Räume sortieren:** Der nicht überall unterstützte `reorder`-Parameter im Home-Assistant-Selector wurde entfernt. Die Sortierung funktioniert wieder robust über persistente Positionswerte.
- **Bereiche sortieren:** gleiche Kompatibilitätskorrektur.
- **Raum/Bereich-Zuordnung:** benutzerdefinierte Bereiche bleiben auswählbar; alte interne Werte wie `ground_floor` oder `basement` werden verständlich deutsch beschriftet.
- **Räume-Popup:** Bei mehreren passenden Statussensoren wird der Datensatz mit den meisten vollständigen Raumdaten bevorzugt; bei wirklich fehlenden Raumdaten erscheint eine Diagnose statt einer leeren Ansicht.
- **Presence Intelligence:** zusätzliche Präsenz-/Bewegungssensoren und haustiersichere Präsenzsensoren sind jeweils echte Mehrfachauswahlen.
- **Deutsch & Erklärungen:** die neuen Presence-Felder sind vollständig deutsch beschriftet und erklären Sensorfusion, Bewohner ohne Tracker und Haustiermodus.

## Berechnungslogik
Die physikalische Raum-/Feuchteberechnung, Lernraten, dynamische Prognose, Nachtprognose, Heizkostenberechnung und die in v0.9.0 ergänzte Recommendation-/Stabilisierungslogik wurden nicht zurückgebaut.
