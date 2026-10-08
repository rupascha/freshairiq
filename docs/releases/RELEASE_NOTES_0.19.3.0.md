# FreshAirIQ 0.19.3.0 — Lüftungsergebnis & verständlichere IQ-Erklärungen

- Die missverständliche Formulierung „effizienter als dein Hausmittel“ wurde durch „effizienter als dein bisheriger Lüftungsdurchschnitt“ ersetzt.
- FreshAirIQ fasst eine Lüftung jetzt hausweit zusammen: vom Beginn der ersten aktiven Lüftung bis zum Schließen des letzten Fensters.
- Direkt nach dem Abschluss bleibt das Ergebnis fünf Minuten lang als eigene IQ-Auswertung auf dem Hauptdashboard sichtbar.
- Die Ergebnisansicht zeigt Gesamt-Feuchtebilanz, Dauer, Temperaturänderung, Wiederaufheizenergie/-kosten, Prognosegenauigkeit und die Einzelwerte aller beteiligten Räume.
- Beginnt innerhalb dieser fünf Minuten eine neue Lüftung, hat die neue Live-Lüftung Vorrang.
- Im Details-Fenster bleibt die letzte vollständig abgeschlossene Lüftung dauerhaft abrufbar und führt bei Bedarf weiter in die jeweilige Raumansicht.
- Die hausweite Ergebnisgruppe und bereits abgeschlossene Teilräume bleiben über Home-Assistant-Neustarts erhalten, solange noch weitere Räume derselben Lüftung aktiv sind.
