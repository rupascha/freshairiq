# FreshAirIQ 0.24.4.0

## Schwerpunkt
Numerische Robustheit und tiefere Regression der zentralen Entscheidungs-, Abschluss- und Lernpfade.

## Änderungen
- Recommendation Engine verwirft nicht-finite Eingaben (`NaN`, `inf`) statt sie bis in Rundung/Entscheidung durchzureichen.
- Personal Context verwirft nicht-finite Lern-/Kosten-/Temperaturwerte defensiv.
- House-level Ventilation Result verwirft nicht-finite Sessionwerte; beschädigte Einzelwerte können die Abschlussbilanz nicht mehr vergiften.
- Diagnostics normalisiert nicht-finite Floats zu `null`, sodass Exporte auch als striktes JSON gültig bleiben.
- Zusätzliche Regression für Sensorfehler, aktive Feuchtequellen, Pollen-Veto, kritisches CO₂, Querlüftung über explizite Zonenverbindungen, Nachtvorbereitung, negative Feuchtebilanz und Langzeit-/Feedbackzustände.
- Pure-Logic-Testabdeckung auf rund 92,9 % angehoben; CI-Mindestwert von 90 % auf 92 % erhöht.

## Verifikation
- 460+ Pure-Logic-Tests
- vollständige Regression
- Python-/JSON-/YAML-/JavaScript-Syntaxprüfung
- Versionskonsistenz und ZIP-Integrität
