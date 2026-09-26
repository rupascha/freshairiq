# FreshAirIQ 0.25.0.5 – Threshold UI Hotfix

- Lüftungsschwellen-Modus bleibt beim Umschalten stabil und springt nicht auf „Automatisch“ zurück.
- Prozentmodus zeigt ausschließlich das Prozentfeld.
- Fester-ml-Modus zeigt ausschließlich das ml-Feld.
- Automatik zeigt kein irrelevantes Wertefeld.
- Beim Übernehmen wird nur der zum gewählten Modus gehörende Wert gespeichert; versteckte Werte werden nicht überschrieben.
- Keine Änderung an Lüftungsphysik, AH-Berechnung oder Lernlogik.

## Noch offene v1-Gates

Die reale Home-Assistant-Runtime-Coverage bleibt ein separates offenes Quality Gate und wird erst in einer vollständigen HA-Testumgebung verifiziert.

Solange diese realen HA-Gates offen sind, ist dies **kein** 1.0-Release.
