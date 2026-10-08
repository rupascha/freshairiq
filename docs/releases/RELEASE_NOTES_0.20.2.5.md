# FreshAirIQ 0.20.2.5 — Hotfix

Gezielter Hotfix auf Basis von 0.20.2.4.

- Hauslüftungsmodus entscheidet jetzt tatsächlich aggregiert über alle aktiven Räume statt nur die Einzelraumentscheidung anders darzustellen.
- Energie-/Kostenprognose verwendet dieselben rollierenden 5-Minuten-Zukunftstemperaturen wie das Zukunftsmodell.
- Prognostizierte Schließzeit wird zusätzlich gegen kumulativen Temperaturverlust und eine zu niedrige Endtemperatur abgesichert.
- Passive Mitlüftung benötigt nun mehrere konsistente Messpunkte, eine belastbarere Verbindungsbewertung und berücksichtigt die Referenzluft vom Beobachtungsbeginn.

Keine sonstigen Funktionsentfernungen oder Vereinfachungen.
