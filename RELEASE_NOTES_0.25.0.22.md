# FreshAirIQ 0.25.0.22 – Diagnostics Client Foundation

## Neu
- Optionaler Diagnose-Client direkt in FreshAirIQ vorbereitet; keine zweite HA-Integration nötig.
- Standard bleibt **Aus**. Der produktive Hub-Endpunkt ist in dieser Version absichtlich leer, daher kann v0.25.0.22 noch keine Diagnose nach außen senden.
- Modi vorbereitet: Aus, nur bei erkannten Problemen, täglich nachts, wöchentlich.
- Nachtversand wird deterministisch über 02:00–03:59 Uhr verteilt, um Lastspitzen zu vermeiden.
- Persistenter Retry-/Backoff-Zustand und Uploadstatus ohne Einfluss auf den Coordinator.
- Upload-Payload wird **vor** einem zukünftigen Netzwerkzugriff lokal minimiert: Raumnamen entfernt, Raumschlüssel pseudonymisiert, Entity-IDs/IP/E-Mail/URLs redigiert, Bewohnernamen und Benachrichtigungsziele entfernt.
- Optionaler grober Geräte-/Browser-Kontext ist separat abschaltbar und enthält keine exakten Gerätemodelle.

## Sicherheit
- Kein produktiver Diagnostics-Hub ist hart codiert. Ohne Endpunkt wird niemals ein HTTP-Upload gestartet.
- Fehler des Diagnose-Clients können die Lüftungslogik nicht blockieren.
- Maximale unkomprimierte Uploadgröße ist auf 2 MiB begrenzt; historische Records werden bei Bedarf automatisch reduziert.

## Unverändert
- Lüftungsphysik, Prognosemodell, Lernlogik, Priorisierung und bestehende Dashboard-Logik bleiben unverändert.
