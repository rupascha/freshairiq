# FreshAirIQ v0.18.1.0

## Diagnose- und Testaufzeichnung

- Neuer rollierender Diagnose-Recorder mit 14 Tagen Aufbewahrung und zusätzlicher 50-MB-Sicherheitsgrenze.
- Erfasst Messzustände, Raumphysik, Prognosen, Entscheidungen, Nachtstrategie, Lüftungssitzungen und kompakte Lernzustände.
- Ereignisaufzeichnung bei relevanten Zustandsänderungen plus periodischer Snapshot spätestens alle 120 Sekunden.
- Datenschutzorientierter Export: keine Home-Assistant Entity-IDs, Zugangsdaten oder Koordinaten werden absichtlich exportiert; konfigurierte Raumnamen bleiben für die Analyse erhalten.
- Neuer Export direkt in **Details → Diagnose & Test → Diagnosedaten exportieren**.
- Das bestehende Entscheidungs-, Prognose-, Lern-, Benachrichtigungs- und Dashboardverhalten wurde nicht verändert.
