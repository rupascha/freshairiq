# FreshAirIQ 0.19.2.0 — Interaktives IQ-Dashboard

## Neu
- Dashboard-Informationskacheln öffnen jetzt passende Detailansichten statt reine Anzeigewerte zu bleiben.
- Die Live-Feuchtebilanz zeigt alle Räume mit ihrem individuellen ml-Beitrag; jeder Raum ist direkt weiter anklickbar.
- Die Schimmel-Kachel öffnet eine nach Risiko sortierte Raumübersicht mit Oberflächen-RH und führt in die jeweilige Raum-Intelligenz.
- Weitere IQ-Werte wie Wasserdampfmenge, Temperaturänderung, Lüftungszeit, Nachtprognose, Lüftungsschwelle und Pollenbewertung besitzen erklärende Detailansichten.
- Verschachtelte Detailansichten besitzen einen echten Navigationsverlauf: Zurück führt zur vorherigen Detailansicht, Schließen beendet den gesamten Detailpfad.
- Die Raumdetailansicht wurde als „Raum-Intelligenz“ neu strukturiert: Empfehlung, Begründungen, Datenqualität, Klima, Feuchtebilanz, Prognose, Schimmel, Lernmodell, Historie und Raummodell werden zusammenhängend erklärt.

## Bedienung / Stabilität
- Alle Subdialoge verwenden die bewährte stabile Snapshot-/Scroll-Logik der Raumübersicht, um iOS-/WebView-Sprünge durch Home-Assistant-State-Updates zu vermeiden.
- Scroll-Chaining und Scroll-Anker bleiben deaktiviert; Momentum-Scrolling bleibt erhalten.
- Dialoge beginnen mit zusätzlichem Safe-Area-Abstand nach oben.
- Schließen- und Zurück-Schaltflächen wurden vergrößert und besser erreichbar positioniert.

## Kompatibilität
- Keine Änderung an Raumkonfigurationen, Entity-Namen, Berechnungsmodellen oder gespeicherten Lerndaten.
- Daten werden ausschließlich aus den bereits vorhandenen FreshAirIQ-Status-/Raum-Payloads dargestellt.
