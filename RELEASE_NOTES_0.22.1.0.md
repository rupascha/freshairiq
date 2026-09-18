# FreshAirIQ 0.22.1.0 — Fault Injection & Behavioural Hardening

## Ziel

Phase 2 des Robustness-Tracks. Dieses Release fügt keine neue Nutzerfunktion hinzu. Es härtet die bestehenden Laufzeit- und Lernpfade gezielt gegen reale Fehlerzustände, die beim Home-Assistant-Start, bei Sensor-/Provider-Ausfällen oder durch beschädigte Persistenz auftreten können.

## Änderungen

- Nicht-endliche Sensorwerte (`NaN`, `inf`, `-inf`) werden bereits an den zentralen State-/Weather-Grenzen verworfen.
- Weather-Forecast-Payloads werden vor der Interpolation erneut auf finite, physikalisch plausible Werte geprüft.
- Measurement Frames erkennen Sensorzeitstempel, die mehr als 60 Sekunden in der Zukunft liegen, als nicht lern-/validierungsfähig. Kleine Clock-Jitter bleiben zulässig.
- Das Raum-Modell besitzt eine zusätzliche Finite-Value-Schranke und führt bei `NaN`/`inf` keine Physik aus.
- Persistierte aktive Lüftungssessions werden beim Laden und bei jedem Raumzugriff runtime-sicher normalisiert. Ungültige Baselines werden neutralisiert und beim nächsten belastbaren Messrahmen sauber neu aufgebaut.
- Wahrheitsähnliche Strings wie `"false"` können keine Phantom-Session mehr aktiv halten.
- Session-Abschlussberechnungen verwenden finite Fallbacks für Baselines, Ergebnisbasis und Cross-Ventilation-Laufzeit.
- Neue Fault-Injection-Tests decken unavailable/unknown/non-finite Werte, Zukunftszeitstempel, Restart-Session-Persistenz und beschädigte Laufzeitdaten ab.

## Unverändert

- Lüftungsphysik und Schwellenwerte
- Forecast-Gewichtung
- Intelligence-2.0-Reifemodell
- Empfehlungen und Sicherheitsgrenzen
- Dashboard-Funktionalität

## Release-Charakter

Technisches Hardening-Release als Vorbereitung auf Learning 3.0 / Shadow-Modelle.
