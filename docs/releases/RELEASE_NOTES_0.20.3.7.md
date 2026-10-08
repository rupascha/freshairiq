# FreshAirIQ 0.20.3.7 – Performance-Hotfix für Konfiguration

Diese Version verändert keine Prognose-, Lern-, Feuchte-, Energie- oder Entscheidungslogik. Sie reduziert ausschließlich unnötige vollständige Config-Entry-Reloads bei Konfigurationsänderungen.

## Änderungen

- Normale Optionsänderungen werden live vom bestehenden Coordinator übernommen und lösen nur noch einen gezielten Refresh aus.
- Prognosezeitraum, Betriebsmodus und Gäste-Zahlen veröffentlichen ihren neuen Entity-Wert sofort; die komplette Hausberechnung läuft anschließend asynchron im Hintergrund.
- Das Dashboard-Settings-API bestätigt gespeicherte nicht-strukturelle Änderungen sofort und wartet nicht mehr auf die komplette Berechnungspipeline.
- Änderungen an Außenwetter-/Außensensor-Quellen bauen nur die betroffenen State-Listener neu auf, statt die komplette Integration neu zu laden.
- Änderungen an Anwesenheits-Entity-Listen bauen ebenfalls nur die Listener neu auf.
- Stockwerks-/Bereichsänderungen und reine Raumreihenfolge werden ohne vollständigen Reload übernommen.
- Die Raumreihenfolge wird weiterhin in die nativen Home-Assistant-Raum-Subentries gespiegelt.
- Nur strukturelle Raumänderungen (Raum hinzufügen/bearbeiten bzw. löschen) behalten bewusst den vollständigen Reload, weil die HA-Plattform-Entities pro Raum beim Setup erzeugt werden.
- Der native Home-Assistant-Optionsflow nutzt für nicht-strukturelle Änderungen ebenfalls den leichten Runtime-Pfad.
- Neue Regressionstests sichern die Reload-Klassifizierung und Listener-Aktualisierung ab.

## Unverändert

- kompletter Funktionsumfang
- Prognoseberechnungen und Prognosewerte
- Lernmodell und gespeicherte Lerndaten
- Entscheidungslogik
- Dashboard-Funktionen
- Entity-Namen und Unique IDs
- Diagnose-/Validierungs-/Backtest-System
