# FreshAirIQ 0.25.0.13 – Frontend Performance Hotfix

Dieser Hotfix optimiert ausschließlich die Darstellungsschicht der FreshAirIQ-Karte. Die Lüftungsphysik, Empfehlungen, Prognosen, Lernmodelle, Schwellenwerte und Home-Assistant-Backendlogik bleiben unverändert gegenüber 0.25.0.12.

## Änderungen

- Das rund 46 KB große Karten-Stylesheet wird pro Karteninstanz nur noch einmal in das Shadow DOM geschrieben und nicht bei jedem vollständigen Render neu geparst.
- Die dynamische Hero-/Profilfarbe bleibt über CSS-Variablen vollständig erhalten.
- Profil-, Prognose- und Gäste-Controls verwenden im normalen aktuellen Datenpfad den bereits vorhandenen FreshAirIQ-Entity-Index statt wiederholt alle Home-Assistant-States zu durchsuchen.
- Der Legacy-Fallback für ältere, noch nicht mit stabilen FreshAirIQ-Metadaten versehene Entities bleibt unverändert erhalten.
- Offene Details- und Unterfenster überspringen identische Live-Refreshes anhand der HA-State-Objektreferenzen. Zusätzlich wird identisches gerendertes HTML vor dem DOM-Parsing verworfen.
- SVG-Verlaufsdiagramme werden per WeakMap auf Basis ihrer unveränderten Eingabearrays wiederverwendet.
- Die Lernkomponenten-Kachel wird wiederverwendet, solange Learning-Model und Forecast-Backtest unverändert sind.

## Ziel

Weniger CSS-Parsing, weniger DOM-Arbeit und weniger globale Entity-Suchen, insbesondere in iOS/iPadOS-WebViews, ohne die fachliche Berechnung oder sichtbare Information zu verändern.
