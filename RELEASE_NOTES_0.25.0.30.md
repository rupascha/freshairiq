# FreshAirIQ 0.25.0.30 – Strict Timestamp Learning Gate Hotfix

## Geändert

- Physikalisches Raumlernen, Prognosekalibrierung und objektive Prognosebewertung dürfen eine Lüftung nur noch verwenden, wenn **Temperatur und Luftfeuchtigkeit während genau dieser Lüftung jeweils mindestens einen neueren Sensor-Zeitstempel geliefert haben**.
- Ein vor dem Öffnen gehaltener Wert kann die Lernfreigabe nicht mehr über die ältere Measurement-Frame-Klasse (`excellent`, `acceptable` oder `held`) umgehen.
- Der Abschluss-Refresh nach dem letzten Schließen bleibt Best-Effort und kann eine bereits gültige Session auf hohe Messqualität anheben; er darf fehlende Sensoraktivität während der Lüftung **nicht rückwirkend ersetzen**.
- Die beim Öffnen gesehenen Temperatur-/Feuchte-Zeitstempel sowie die letzten während der Session beobachteten Zeitstempel werden als Diagnoseevidenz im Lüftungsereignis gespeichert.
- Bei reparierten/älteren laufenden Sessions werden keine historischen Report-Zähler erfunden; erst ein danach wirklich fortgeschrittener Sensor-Zeitstempel zählt als neue Lernmeldung.
- Eine Session mit guter Messqualität bleibt mit 0,75 gewichtet. Alte Frame-Klassen können diese Gewichtung nicht mehr auf 1,0 anheben.

## Unverändert

- Die in 0.25.0.29 eingeführte 3-s-Schließbestätigung, der Best-Effort-Sensorrefresh, die maximal 10-s-Abschlusswartezeit und die sichtbare Meldung „Warte kurz auf die Klimasensoren“ bleiben unverändert.
- Feuchtephysik, Prognoseformeln, Grenzwerte, Prioritäten, Raumkonfiguration und Dashboard-Einstellungen wurden nicht verändert.
