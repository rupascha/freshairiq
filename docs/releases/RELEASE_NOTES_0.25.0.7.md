# FreshAirIQ 0.25.0.7 – Validation Session Identity Hotfix

- Jede neue Lüftung erhält eine stabile `session_validation_id`, die Startzustand, laufende Prognose und Abschluss eindeutig zusammenhält.
- Die eingefrorene Startprognose und ihre Zeitbasis bleiben auch bei einem manuellen Learning-Reset während einer aktiven Session erhalten.
- Abgeschlossene Sessions exportieren ihre Validierungs-ID für eine eindeutige Diagnosezuordnung.
- Die Validierung meldet jetzt den tatsächlichen Ablehnungsgrund: fehlende Startprognose, nicht auswertbare Zeitbasis, unsynchroner Messrahmen oder Feuchtequellen-Kontamination.
- Sicherheitsgrenzen für Messqualität wurden bewusst nicht gelockert; schlechte/stale Messrahmen werden weiterhin nicht zum objektiven Lernen zugelassen.
- Keine Änderung an Feuchtephysik, Schwellenwerten, Empfehlungen oder Dashboard-Logik.

## Noch offene v1-Gates

Die bereits dokumentierten v1-Qualitätsgates bleiben unverändert bestehen. Insbesondere bleibt die reale Home-Assistant-Runtime-Coverage außerhalb dieser lokalen Pure-Logic-Prüfung offen.

Dieser Hotfix ist **kein** 1.0-Release; die offenen v1-Gates werden dadurch nicht als erfüllt markiert.
