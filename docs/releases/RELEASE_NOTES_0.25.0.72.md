# FreshAirIQ 0.25.0.72

## Dialog-Scroll-Hotfix

- Behält die Scrollposition jeder FreshAirIQ-Unteransicht separat bei und stellt beim Zurückgehen exakt die Position der übergeordneten Ansicht wieder her.
- Gilt u. a. für `Details → Unterfenster → zurück` und `Räume → Raum → zurück`.
- Ergänzt für Android einen gezielten Touch-Scroll-Fallback ausschließlich an den beiden bestehenden FreshAirIQ-Scrollcontainern; iOS bleibt beim nativen Scrolling.
- Keine Änderung an Lüftungs-, Lern-, Diagnose- oder Berechnungslogik.
