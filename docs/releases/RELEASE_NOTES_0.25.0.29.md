# FreshAirIQ 0.25.0.29 – Measurement Quality & Final Sensor Refresh Hotfix

## Geändert

- Messqualität wird nicht mehr allein aus dem Alter eines gehaltenen Batteriewerts abgeleitet. Entscheidend ist jetzt, ob seit dem physischen Öffnen mindestens zwei echte Raumklima-Meldungen eingegangen sind – 2× Temperatur, 2× Feuchte oder je 1× Temperatur/Feuchte.
- Beim bestätigten Start einer Raumlüftung wird nach Sicherung des Startwerts ein generischer Best-Effort-`homeassistant.update_entity` für bereits konfigurierte Raum-/Referenzsensoren ausgelöst. Es sind **keine neuen Entitäten oder Einstellungen** nötig.
- Nach dem letzten Schließen eines Raums bleiben die bestehenden 3 s Schließbestätigung unverändert. Danach fordert FreshAirIQ erneut die bereits konfigurierten Klimasensoren an und wartet höchstens 10 s auf Temperatur-/Feuchte-Rückmeldungen.
- Wenn beide Raumklima-Rückmeldungen früher eintreffen, wird sofort ausgewertet. Antwortet ein schlafender Batteriesensor nicht, läuft die 10-s-Gnadenfrist aus; die Session wird danach anhand der real beobachteten Sensoraktivität bewertet.
- Während der Abschluss-Gnadenfrist zeigt die Dashboard-Hauptkarte deutlich **„Warte kurz auf die Klimasensoren“** statt scheinbar verzögert ein Ergebnis zu liefern. Das Lüftungsergebnis erscheint erst nach Abschluss dieser Phase.
- Die physische Lüftungsdauer endet weiterhin exakt mit dem Fensterkontakt. Die zusätzliche Sensorwartezeit verlängert weder Dauer noch Energie-/Feuchteberechnung.
- Öffnet ein Fenster während der Gnadenfrist wieder, wird die Finalisierung abgebrochen und dieselbe Lüftung fortgesetzt.
- Öffnungsspezifische Referenzsensoren werden nun ebenfalls als Live-Quellen überwacht, damit deren Rückmeldungen ohne 30-s-Polling-Verzögerung in die Auswertung einfließen.

## Unverändert

- Feuchtephysik, Prognoseformeln, Grenzwerte, Prioritäten und Dashboard-Einstellungen wurden nicht verändert.
- Der Refresh ist integrations- und herstellerneutral und bleibt Best-Effort; schlafende Push-/Batteriesensoren müssen nicht auf eine Update-Anforderung reagieren.
