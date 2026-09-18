# FreshAirIQ 0.25.0.24 – Transport Performance Hotfix

Hotfix ausschließlich für die CPU-/Event-Loop-Belastung des optionalen Diagnostics-Clients. Die Lüftungsphysik, Forecast-Logik, Lernmodelle, Empfehlungen, Dashboard-Fachlogik und der manuelle Diagnosedatei-Export bleiben unverändert.

## Änderungen

- CPU-intensive lokale Datenschutzaufbereitung und Chunk-Erzeugung laufen im Home-Assistant-Executor statt im Event Loop.
- JSON-/GZIP-Aufbereitung jedes Upload-Chunks läuft ebenfalls außerhalb des Event Loops.
- Die Chunk-Partitionierung wurde von einem wiederholten Aufbau wachsender Kandidaten auf eine lineare, bytebasierte Partitionierung umgestellt.
- Redundante `deepcopy`-Operationen in der analyseäquivalenten Transportaufbereitung entfallen; die Sanitizer bleiben funktional und verändern den Originalexport nicht.
- Bereits berechnete Record-IDs werden für den Cursor wiederverwendet, statt den letzten Record eines Chunks erneut zu hashen.
- GZIP-Level 4 reduziert CPU-Kosten bei weiterhin starker Kompression.
- Der produktive Diagnostics-Hub-Endpunkt bleibt absichtlich leer. Diese Version sendet weiterhin keine Daten an einen externen Server.
- Der manuelle Home-Assistant-Diagnoseexport bleibt unverändert.

## Reale 30-Tage-Referenz

Mit der vorhandenen ca. 37-MB-FreshAirIQ-Diagnose (459 Records) sank die reine lokale `build_upload_chunks`-Zeit in derselben Arbeitsumgebung von ca. 16,96 s in v0.25.0.23 auf ca. 5,0 s in v0.25.0.24. Die Ausgabe bleibt bei 13 Chunks und 459 Records; alle Chunks liegen unter dem 2-MiB-Limit. Zusätzlich findet diese CPU-Arbeit im produktiven HA-Pfad nun außerhalb des Event Loops statt.
