# FreshAirIQ 0.25.0.52

## Reliability Foundation v3 – Upgrade & Migration Safety

- Historische Konfigurations-Fixtures und reproduzierbares Migration-Replay eingeführt.
- Upgrade-Verträge für Legacy-Kontakte, Dimensionsräume, Stockwerke, sensorlose Räume und beschädigte alte Verzögerungswerte abgesichert.
- Idempotenz abgesichert: bereits migrierte Konfigurationen werden nicht erneut verändert.
- Unbekannte Felder aktueller Schemas bleiben unverändert erhalten.
- Migration-Replay ist jetzt release-blockierender Bestandteil des Reliability Foundation Gate.
- Keine fachliche Lüftungslogik geändert.
