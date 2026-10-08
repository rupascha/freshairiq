# FreshAirIQ 0.20.1.0 – Performance

Diese Version optimiert ausschließlich den Laufzeitpfad der Dashboard-Karte. Funktionen, Ansichten, Informationsumfang und Berechnungslogik bleiben gegenüber 0.20.0.2 erhalten.

## Optimierungen

- Fremde Home-Assistant-State-Updates lösen keinen vollständigen FreshAirIQ-Neuaufbau mehr aus.
- Relevante Updates werden browser-frameweise gebündelt.
- FreshAirIQ-Status-, Raum- und Control-Entities werden sicher gecacht und bei Konfigurationsänderungen invalidiert.
- Raumdaten werden ohne wiederholten Komplettscan aller Home-Assistant-Entities zusammengeführt.
- Prognosezeitraum und Betriebsprofil erhalten sofortiges UI-Feedback, während Home Assistant im Hintergrund synchronisiert.

Die bestehende iOS-/Android-WebView-Scrollstabilisierung bleibt vollständig erhalten.
