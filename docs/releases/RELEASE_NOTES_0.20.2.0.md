# FreshAirIQ 0.20.2.0

- Feuchtequellen erweitert: Kochen, Dusche, Bad, Sauna; mehrdeutige Quellen werden bewusst neutral benannt.
- Nachlauf-Schutz für Feuchtequellen verhindert zu frühes Schließen.
- Erneute Lüftung desselben Raums standardmäßig 120 Minuten gesperrt; deutliche Wetterverbesserung, neue Feuchtequelle oder kritische Klimaereignisse dürfen intelligent übersteuern.
- Nachtprognose gegen übersteuernde Trend-/Routineanteile plausibilisiert; IQ-Vertrauen wird durch reale Lernreife begrenzt.
- Gäste bleiben in der Nachtprognose wirksam; Gäste-Steuerung reagiert im Dashboard sofort.
- Prognoseabweichungen werden hybrid aus absolutem und relativem Fehler bewertet; kleine ml-Abweichungen gelten nicht mehr als „sehr groß“.
- Hauslüftungsmodus mit Hysterese: bei fast vollständiger Lüftung hausweite Live-Darstellung statt störender Einzelraum-Schließhinweise.
- Live-Feuchtebilanz zeigt aktive und geschlossene Räume deutlich unterschiedlich.
- Benutzerfreundlicher Systemcheck ergänzt die bestehende Diagnose-Infrastruktur.
- Sensor-/Wetter-/CO₂-Fähigkeiten werden als optionale Qualitätsmerkmale ausgewiesen; fehlendes CO₂ bleibt ein zulässiger Betriebsmodus.
