# FreshAirIQ 0.20.1.2

Hotfix: Live-Daten in allen Dashboard-Fenstern ohne Scroll-Sprünge.

- Geöffnete Haupt- und Unterfenster behalten ihren bestehenden Scroll-DOM.
- Relevante Home-Assistant-Updates werden pro Browser-Frame gebündelt und als nicht-destruktive Teilupdates eingespielt.
- Texte, Zahlen, Zustände und Darstellungsattribute aktualisieren sich live.
- Gerade fokussierte Eingabefelder werden während der Bearbeitung nicht überschrieben.
- Interaktive Teilbäume werden bei Strukturänderungen nicht ersetzt; dadurch bleiben Event-Handler und Navigation stabil.
- Keine Änderungen an Klima-, Prognose-, Lern-, Lüftungs- oder Ergebnislogik.
