# FreshAirIQ 0.25.0.10 – Close-Gate Aggregation Hotfix

Gezielter Hotfix auf Basis von 0.25.0.9.

## Behoben

- Die Hauslüftungs- und Etagenlüftungs-Aggregation darf nicht mehr direkt nach dem Öffnen aufgrund eines niedrigen prognostizierten 5-Minuten-Zusatznutzens auf „Jetzt schließen“ wechseln.
- Eine aggregierte Schließentscheidung ist nur noch erlaubt, wenn **alle** betroffenen aktiven Räume ihre vorhandene `close_decision_ready`-Freigabe erhalten haben.
- Damit gilt auch in Haus-/Etagenmodus unverändert: vor 15 Minuten sind zwei neue Feuchtesensor-Meldungen erforderlich; ab 15 Minuten darf der bereits vorhandene Modell-Fallback die Schließentscheidung freigeben.
- Solange die Freigabe fehlt, bleibt FreshAirIQ auf „Lüftung läuft“ und erklärt, wie viele aktive Räume bereits schließbereit sind.
- Eine aus einem vorherigen Pfad geerbte `0 min`-Restzeit wird während der gesperrten Schließentscheidung entfernt, damit die Oberfläche nicht gleichzeitig „weiterlüften“ und „0 min“ signalisiert.

Keine Änderung an Lüftungsphysik, Empfehlungsschwellen, Forecast-Formeln, Lernraten, Outcome-Learning oder der Batteriesensor-Logik aus 0.25.0.9.
