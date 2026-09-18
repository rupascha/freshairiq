# FreshAirIQ 0.25.0.31

## Finalisation Evidence Consistency Hotfix

Diese Version härtet ausschließlich die in 0.25.0.29/0.25.0.30 eingeführte Abschluss- und Messqualitätslogik. Die Feuchtephysik, Prognoseformeln, Grenzwerte und Priorisierung wurden nicht verändert.

### Änderungen

- **Erreichbare Abschlussanzeige:** Wenn nur noch Räume auf die finale Klimasensor-Rückmeldung warten, zeigt das Dashboard zuverlässig „Warte kurz auf die Klimasensoren“. Noch tatsächlich geöffnete/laufende Räume haben weiterhin Vorrang.
- **Exakte physische Schließgrenze:** Der Kontakt-Schließzeitpunkt wird bereits beim Roh-Schließen erfasst, nicht erst nach der 3-s-Bestätigung. Sensorberichte nach diesem Zeitpunkt dürfen den In-Session-Timestamp-Gate nicht mehr nachträglich erfüllen.
- **Rückmeldung während der 3-s-Bestätigung zählt:** Eine Temperatur-/Feuchtemeldung, die direkt nach dem Schließen aber vor Ablauf der 3 Sekunden kommt, wird als Abschlussfeedback erkannt.
- **Keine falschen 0-ml-Ergebnisse:** Feuchtewerte ohne vollständige Timestamp-Evidenz werden als **nicht belastbar** gekennzeichnet. Der rohe Rechenwert bleibt nur diagnostisch (`raw_removed_ml`) erhalten.
- **Keine Kontamination weiterer Lernpfade:** Nicht belastbare Sessions verändern weder Feuchtestatistik noch Prognosekalibrierung noch Post-Close-Rebound-Lernen. Dauer, Temperatur und Energie der Lüftung bleiben als reale Ereignisdaten erhalten.
- **Strikte Lernanzeige:** „LERNT JETZT“ verwendet denselben Timestamp-Gate wie die Backend-Lernfreigabe.
- **Gewichtete Lernreife:** `good`-Sessions mit Gewicht 0,75 erzeugen nur 0,75 Reife-Evidenz. Bruchteile werden persistent in `learning_sample_credit` gesammelt; vier 0,75-Proben entsprechen drei vollen Reifeproben.
- **Reset-/Diagnosekonsistenz:** Opening-Timestamps laufender Sessions bleiben bei Lernreset erhalten; Diagnosefelder wurden ergänzt.

### Kompatibilität

Keine neuen Entitäten oder Benutzereinstellungen erforderlich. Bestehende Konfigurationen und Legacy-Migrationspfade bleiben unverändert.
