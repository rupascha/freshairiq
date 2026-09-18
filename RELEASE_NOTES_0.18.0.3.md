# FreshAirIQ 0.18.0.3 — Night Strategy Consistency Hotfix

Hotfix auf Basis von 0.18.0.2. Keine bestehende Funktion wurde entfernt.

- Nachtprognose und Nachtstrategie verwenden jetzt dasselbe exakte Nachtfenster und dieselben stündlichen Wetterdaten.
- Die alte starre Freigabe „trockener + mindestens 14 °C = nachts offen“ wurde entfernt.
- Kontrollierte Nachtlüftung berücksichtigt nun prognostizierte Raumabkühlung und Wiederaufheizbedarf.
- Bei trockener, aber thermisch zu kalter Nacht wird gezieltes Vorlüften statt Daueröffnung empfohlen.
- Bei prognostiziertem Regen wird keine unbeaufsichtigte Daueröffnung empfohlen; absolute Feuchte bleibt Teil der Bewertung.
- Die neue Aktion `pre_ventilate` ist in Unified Decision Brain und Dashboard integriert.
- Nachtstrategie bleibt nachrangig gegenüber akuten Schließen-/Lüften-/Sensor-/Pollenentscheidungen.
- Zusätzliche Pipeline-Tests für Nachtstrategie-Priorität ergänzt.
