# FreshAirIQ 0.24.5.0

## Schwerpunkt: Persistenz-, Backtest- und Diagnose-Hardening

- Forecast-Backtests akzeptieren keine `NaN`-/`Infinity`-Werte mehr als Messwerte; Metriken und Kalibrierung bleiben strikt endlich und JSON-kompatibel.
- Shadow Learning repariert beschädigte persistierte Zähler und Kandidatenzeilen defensiv. Fremde Kandidaten-Keys werden nicht mehr in die Winner-Auswahl einbezogen.
- Rollback-Schutz toleriert beschädigte Samples, Fehlerakkumulatoren und Counter, ohne die Produktionsprognose zu verändern.
- Diagnostics filtert beschädigte Raum-, Learning-, Session- und Window-Event-Strukturen und ignoriert gültiges JSON, das kein Objekt ist, kontrolliert mit Export-Fehlerhinweis.
- Diagnose-Konfigurationssnapshots tolerieren beschädigte Alt-Daten, ohne CO2-/Referenzzähler zum Absturz zu bringen.
- Diagnose-Dateigrößenberechnung ist gegen Dateisystemfehler einzelner Chunks gehärtet.
- House-/Room-History-Reader reparieren beschädigte Container/Rows und begrenzen ungültige Zeitfenster sicher.
- Pure-Logic-Coverage: 92,986 %; 476/476 Tests bestanden. CI-Floor auf 92,9 % angehoben.

Die bestehende Prognosephysik und gültige Lernlogik wurden nicht fachlich verändert; die Änderungen betreffen defensive Eingabe-/Persistenzbehandlung und zusätzliche Regressionstests.
