# FreshAirIQ 0.25.0.6 – Threshold Settings Consistency Hotfix

- Geräte & Dienste: eigener geführter Menüpunkt „Lüftungsschwelle“.
- Automatisch zeigt nur die Moduswahl; es ist kein Zahlenwert erforderlich.
- Prozentmodus zeigt im Folgeschritt ausschließlich den Prozentwert.
- Fester ml-Modus zeigt im Folgeschritt ausschließlich den ml-Wert.
- Die bisher doppelt sichtbaren Haus-Schwellenfelder wurden aus „Erweiterte Modellparameter“ entfernt.
- Dashboard und Geräte-&-Dienste erklären den Automatikalgorithmus nun konkret: Tagesfeuchte / 4, Begrenzung auf 6–12 % der überwachten Wassermenge sowie 25-%-Absenkung bei kühlen Sommerfenstern.
- Berechnungslogik der Lüftungsschwelle wurde nicht verändert.

## Noch offene v1-Gates
Die vollständigen Tests gegen eine reale Home-Assistant-Testumgebung bleiben als separates Quality Gate offen, solange die Home-Assistant-Testabhängigkeiten in der Build-Umgebung nicht installiert sind.
**Dies ist kein** 1.0-Release; die offenen v1-Gates bleiben bestehen.
