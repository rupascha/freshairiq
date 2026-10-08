# FreshAirIQ 0.25.0.25 – Local Hub Staging Connection

Diese Version verbindet den integrierten Diagnostics Client erstmals mit dem bereits laufenden privaten FreshAirIQ Diagnostics Hub v0.3.0 unter `http://192.168.178.150`. Sie ist bewusst **nur für lokales Staging** vorgesehen.

## Geändert

- `/v1/enroll` wird vor dem ersten Upload mit anonymer Installations-ID, Upload-Schema 2 und FreshAirIQ-Version ausgeführt.
- Pro Installation wird lokal ein zufälliger Client-Token erzeugt und **vor** dem Enrollment persistent gespeichert.
- Diagnose-Chunks gehen an `/v1/diagnostics/chunks` und tragen `Authorization: Bearer …` sowie den vorhandenen `Idempotency-Key`.
- Bei einem einmaligen `401` wird mit demselben persistenten Token erneut enrolled und der identische Chunk genau einmal wiederholt.
- Plain HTTP wird nur für private bzw. Loopback-IP-Adressen akzeptiert; öffentliche HTTP-Ziele werden fail-closed verworfen.
- Der erste Daily-/Weekly-Abgleich nach explizitem Opt-in darf sofort starten, damit das lokale Staging nicht bis zum nächtlichen Slot warten muss.
- Der Standard bleibt `diagnostics_reporting_mode: off`. Ohne explizites Opt-in findet weder Enrollment noch Upload statt.

## Unverändert

- manueller Diagnosedatei-Export
- lokale Datenschutz-/Pseudonymisierungslogik
- 30-Tage-Vollabgleich beim ersten Transfer, danach inkrementeller Cursor
- Chunking, Resume, Deduplizierung und Event-Loop-Auslagerung aus 0.25.0.24
- Lüftungsphysik, Forecast, Learning, Priorisierung und Dashboard-Fachlogik
