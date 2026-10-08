# FreshAirIQ v0.25.0.32 – Safe Code Cleanup Hotfix

Diese Version räumt ausschließlich nachweislich ungenutzte oder redundante interne Codepfade auf. Die Mess-, Prognose-, Lern- und Abschlusslogik aus v0.25.0.31 bleibt funktional unverändert.

## Bereinigt

- zwei nicht mehr aufgerufene private Config-Flow-Schemahelfer entfernt (`_personalisation_schema`, `_house_schema`); aktiv bleiben die vereinheitlichten `_residents_schema`- und `_building_schema`-Pfade
- redundante Zwischenvariablen im strikten Timestamp-Lerngate entfernt, ohne die Gate-Bedingung zu verändern
- weitere nachweislich ungenutzte lokale Variablen in Forecast, Intelligence, Storage, Recommendation, Anticipation, Learning-Status und Config-Flow entfernt
- veralteten Kommentarrest der früheren Measurement-Frame-Gewichtung entfernt

## Bewusst geschützt / nicht entfernt

- Diagnostics Export (`/api/freshairiq/diagnostics`)
- Diagnostics Feedback Proxy (`/api/freshairiq/feedback/{entry_id}`)
- Diagnostics Hub v2 Transport (`/v1/enroll`, `/v1/diagnostics/chunks`, `/v1/feedback`)
- Upload-Schema v2, Cursor-Schema v1 und Diagnostics-Schema v10
- öffentliche/Legacy-Transporthelfer wie `build_cloud_payload`, `record_cursor` und `DEFAULT_MAX_UPLOAD_RECORDS`
- bestehende Storage-/Migrationspfade und Diagnosefelder
- sämtliche älteren Release Notes und Kompatibilitätsdaten

## Ziel

Weniger Altcode und weniger unnötige lokale Zustände, ohne bestehende Funktionen oder die Kommunikation mit FreshAirIQ Diagnostics HA bzw. Diagnostics Hub zu verändern.
