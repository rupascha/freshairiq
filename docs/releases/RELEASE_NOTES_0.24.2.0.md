# FreshAirIQ 0.24.2.0 — Adaptive Learning & Runtime Hardening

## Ziel dieses Releases
0.24.2.0 erweitert bewusst nicht den sichtbaren Funktionsumfang, sondern reduziert das Risiko von Persistenz-, Lern- und Runtime-Fehlern auf dem Weg zu FreshAirIQ 1.0.

## Änderungen
- Pure-Logic-Backendcoverage mit identischer Messmethode von 74,5 % auf 83,85 % erhöht.
- 397 lokale Regression-/Hardening-Tests.
- Neue Verhaltens-Tests für Routine Learning, Seasonality, Resident Strategy, House Strategy und Intelligence Session Feedback.
- Nicht-finite (`NaN`, `inf`) und strukturell beschädigte Lernpersistenz wird neutralisiert/repariert statt Prognosen zu vergiften.
- House-Strategy-Learning bewahrt weiterhin negative reale Lüftungsergebnisse, ist aber gegen nicht-finite Persistenz abgesichert.
- Notification-Profile, dedupliziertes Routing und Legacy-Cooldown-Zeitstempel sind robust getestet.
- Learning-Reset und Statistics-Reset besitzen jetzt explizite Verträge für aktive Sessions und bestehende Daten.
- Wasser-/Temperatur-/History-Leser und -Schreiber tolerieren korrupte Persistenz defensiv.
- Neue echte Home-Assistant-Runtime-Smoke-Suite in CI; diese läuft außerhalb der Stub-Testumgebung und importiert zentrale Integrationsmodule gegen `homeassistant>=2026.8,<2027`.
- CI hält ab diesem Release mindestens 83 % Pure-Logic-Coverage fest; das Gate wird in weiteren Releases schrittweise bis >95 % angehoben.

## Unverändert
- Bestehende Forecast-/Session-/Learning-Physik wurde nicht vereinfacht oder ersetzt.
- Optionale Aktorik aus 0.24.0.0 bleibt opt-in und schaltet weiterhin keine Klimaanlage mit erfundenem Modus/Sollwert.
- 1.0 bleibt gesperrt, solange HA-Runtime-/Config-Flow-Coverage, Frontend-E2E und reale Fremdinstallationen die Qualitäts-Gates noch nicht erfüllen.
