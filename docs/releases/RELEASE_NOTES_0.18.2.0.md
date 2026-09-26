# FreshAirIQ 0.18.2.0

## Diagnose & Beta-Test Recorder v2
- Aufbewahrungszeit der Diagnosedaten von 14 auf 30 Tage erweitert.
- Export enthält jetzt eine anonymisierte Testakte mit Versions-, Modell- und Hauskonfiguration.
- Sensor-/Datenqualitäts-Zusammenfassung pro Messpunkt ergänzt.
- Lüftungszustands-Wechsel pro Raum werden als anonymisierte Öffnen/Schließen-Ereignisse protokolliert.
- Empfehlungsbefolgung, Reaktionszeit und Outcome-Lernwerte werden explizit mitgeführt.
- Heizmodell-Kontext (System, Energiepreis, prognostizierter Wärmebedarf und Kosten) wird protokolliert. Ein physischer Heizungszustand wird bewusst nicht erfunden, solange FreshAirIQ keinen dedizierten Heizungszustands-Sensor konfiguriert.
- Außenklima inklusive absoluter Feuchte und Datenqualität wird im Diagnose-Trace festgehalten.
- Exportlimit und Sicherheits-Speichergrenze wurden passend zur 30-Tage-Aufbewahrung erweitert.
- Keine Entity-IDs, Presence-Entity-Namen, Benachrichtigungsziele, Koordinaten oder Zugangsdaten werden absichtlich exportiert.

Die bestehende FreshAirIQ Entscheidungs-, Lern-, Prognose- und Dashboardlogik wurde nicht verändert.
