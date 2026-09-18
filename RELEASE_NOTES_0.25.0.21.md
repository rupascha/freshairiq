# FreshAirIQ 0.25.0.21 — Continuous Quality System

Diese Version führt ein automatisiertes Qualitätssystem ein. Die fachliche Lüftungs-, Prognose- und Lernlogik bleibt unverändert.

## Neu
- Zentrale maschinenlesbare Quality-Policy unter `quality/quality_policy.json`.
- Ein lokaler/CI-Orchestrator prüft Korrektheit, Robustheit, Stabilität, Performance und Release-Hygiene.
- Deterministischer Langzeit-Stresstest mit Memory-/Runtime-Grenzen.
- Normalisierte Performance-Baseline für Raumphysik, Empfehlungen und Lüftungssimulation mit Warn- und Fehlergrenzen.
- Python-Kompatibilitätsmatrix für 3.13/3.14.
- Home-Assistant-Kompatibilitätsmatrix für die Mindestlinie 2026.8 und die aktuelle 2026.9-Linie sowie wöchentlicher Edge-Watch.
- Browser-Smoke-Tests für Chromium, WebKit und Firefox auf iPhone-, iPad-, Android- und Desktop-Viewports.
- Clean-Release-Builder, der Releases nur nach bestandenen Quality-Gates erzeugt und Cache-/Dev-Artefakte ausschließt.
- Automatischer HACS-Strukturcheck sowie reale HA-Lifecycle-/Config-Flow-Coverage im CI.

## Release-Prinzip
Ein automatisch erzeugtes Release wird nur gebaut, wenn alle verpflichtenden Gates grün sind. Der wöchentliche zukünftige Home-Assistant-Edge-Test ist bewusst nur Frühwarnung und blockiert aktuelle Releases nicht.
