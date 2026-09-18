# FreshAirIQ 0.19.1.0 – Einstellungen & Bedienbarkeit

Diese Version überarbeitet ausschließlich die Konfiguration und Bedienbarkeit der Einstellungen. Die in v0.19.0.0 eingeführte Feuchtequellenlogik sowie die bestehende Recommendation Engine bleiben fachlich unverändert.

## Neu

- Klarere Hauptnavigation mit fünf logisch getrennten Einstellungsbereichen.
- Deutsche Feldnamen und Erklärungen inklusive dokumentierter Standardwerte.
- Eigene Querlüftungsseite mit Beispielen wie `wohnzimmer+schlafzimmer` und Erklärung für bereichsübergreifende Verbindungen.
- Verfügbare Raumschlüssel werden direkt auf der Querlüftungsseite angezeigt.
- Erweiterte Modellparameter sind in Feuchteschwellen, Empfehlungsschwellen, Lüftungsdauer, Effizienz, Schimmel/CO₂ und Lernen gegliedert.
- Feuchtequellen pro Raum werden als Raumeigenschaft verständlich erklärt.
- Bestätigte Seiten werden sofort gespeichert; ein abschließendes Sammel-Speichern ist nicht mehr erforderlich.
- In Menüs gibt es eindeutige `← Zurück`-Einträge.

## Technischer Hinweis zur Navigation

Home Assistant stellt Integrationen im Data-Entry-/Options-Flow derzeit keine API bereit, mit der ein nativer Zurück-Pfeil oben links in einem Formular erzwungen werden kann. Deshalb verwendet FreshAirIQ dort, wo Home Assistant es zulässt, explizite Zurück-Einträge in den Menüs. Formulare behalten die von Home Assistant vorgegebene Kopfzeile.

## Kompatibilität

Es wurden keine vorhandenen Optionsschlüssel entfernt. `cross_ventilation_pairs` bleibt unverändert kompatibel; `cross_zone_connections` erhält lediglich einen expliziten leeren Standardwert.
