# FreshAirIQ 0.25.0.41 — Passive-Open / Night-Strategy Priority Hotfix

- Behebt einen Prioritätsfehler, bei dem eine aktive Dauer-/Kipplüftung im Haupt-Cockpit durch die unabhängige Nachtstrategie überschrieben werden konnte.
- Die tatsächlich geöffneten Räume bleiben während `passive_open_monitor` die führende Live-Entscheidung.
- Die Nachtstrategie bleibt weiterhin berechnet und als Kontext verfügbar, wird aber nicht mehr als Hauptentscheidung über eine reale Daueröffnung gelegt.
- Keine Änderung an Raumkonfiguration, Kontaktzuordnung, Feuchteberechnung, Lernmodell oder Nachtmodell.
