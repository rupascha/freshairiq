# FreshAirIQ 0.25.0.3 – Individuelle Lüftungsschwellen & Lokalisierung

- Etagenempfehlungen verwenden jetzt konsequent deutsche Anzeigenamen (z. B. `Erdgeschoss` statt `ground_floor`).
- Die Detail-Kachel **Lüftungsschwelle** ist direkt konfigurierbar: automatisch, Prozent der aktuellen Gesamtwassermenge oder fester mL-Wert.
- Räume besitzen optional eine eigene Lüftungsgrenze: automatisch (Standard), Prozent der aktuellen Raum-Wassermenge oder fester mL-Wert.
- Raumgrenzen beeinflussen die individuelle Priorisierung nicht-kritischer Problemräume; Schimmel-/Gesundheits- und kritische CO₂-Regeln behalten Vorrang.
- Dashboard-Zahnrad und native Geräte-&-Dienste-Raumkonfiguration verwenden dieselben persistierten Raumfelder.
- Bestehende Installationen migrieren sicher auf `Automatisch`; die bisherige Raum-Schwelle bleibt damit unverändert wirksam.

## Noch offene v1-Gates
- Reale Home-Assistant-Runtime-/Config-Flow-Coverage bleibt in dieser Arbeitsumgebung unverifiziert, da die vollständigen Home-Assistant-Testabhängigkeiten nicht installiert sind.
- Vor öffentlicher Freigabe weiterhin Feldtest auf iOS/iPadOS/Android und realer HA-Installation durchführen.

Dies ist ausdrücklich **kein** 1.0-Release; die offenen Runtime-Gates bleiben bestehen.
