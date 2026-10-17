# Architektur – FreshAirIQ (Stand 2026-10-16, Branch `arbeitsauftrag-2026-10-14`)

Verifiziert am Code von `-faiq-dev` (Basis `dbdbdcb`, Version 0.26.5.0), `-faiq-hub` 0.3.3.86 und
`-faiq-ha` 0.5.2. Nicht live geprüft: laufende Hub-Instanz, echte HA-Installationen.

## Komponenten
| Komponente | Ort | Aufgabe |
|---|---|---|
| Integration | `-faiq-dev/custom_components/freshairiq` | Config-Flow, Coordinator, Raumphysik, Lernen, Entities, Events, Push, Diagnose-Client |
| Frontend | `…/frontend/freshairiq-card.js` (ES-Modul, per `freshairiq-loader.js` via `import()`), `freshairiq-panel.js`, `freshairiq-card-i18n-en.js` (DE→EN-Paare) | Lovelace-Karte (Varianten `iq` Standard, `classic`), Unteransichten im `.subdialog` |
| Blueprints | `blueprints/automation/freshairiq/*.yaml` | Ansage/Gerätesteuerung auf `freshairiq_room_action`, Feuchtequelle, Sonnenschutz |
| Automatische Steuerung (Opt-in, 0.26.5.1) | `actuator_control.py` (rein) + `actuator_controller.py` (HA) | Nur Räume mit eingeschalteter Steuerung: Rollo folgt Fenster/Tür (Position zurück), Aussperrschutz bei Durchgangstür, Sonnenschutz, Ablüfter; Kontakt-/Rollo-Listener + Koordinator-Takt |
| Diagnostics Hub | `-faiq-hub/src/freshairiq_hub` | `/v1/enroll`, Chunk-Upload, Analyzer (Regeln/Cluster), Guardian-Arbeitsliste (`repository.triage_work_queue`), Read-/Control-APIs, Collector-Loop |
| Diagnostics-HA | `-faiq-ha/custom_components/freshairiq_diagnostics` | HA-Admin-Integration; zeigt Hub-Übersicht, Quellenstatus, To-dos |

## Entscheidungs-Datenfluss (Sensor → Ausgabe)
1. HA-States (Temp/RH/CO₂/Kontakte/Wetter) → `FreshAirIQCoordinator._async_update_data_impl` (Takt 30 s, zusätzlich Quellereignisse).
2. Je Raum `model.evaluate_room` → `RoomResult.action` (`Ventilate`, `Continue ventilating`, `Close` mit Latch `close_notified`, `Wait`, `Okay`, `Do not ventilate`, `Ventilate for cooling`, `Check sensor`, `Monitor only`); Coordinator ersetzt für Räume ohne Öffnungskontakt `Ventilate*` → `Ventilate indirectly`.
3. Hausebene: `_house_recommendation_and_plan` → `consolidation.stabilise_recommendation(…, previous=…)` (Echtzeit-Invarianten, Daueröffnung `passive_open_monitor`, Aggregat-Schließschutz mit Hysterese seit 2026-10-16) → `decision_brain`.
4. Präsentation: `synchronize_room_presentation_actions` überschreibt `room.action` für die von der finalen Hausentscheidung genannten Räume (Original in `canonical_action`); `house_aligned_room_actions` setzt `house_aligned_action` (`ventilate_later`, `monitor_open`, …).
5. Ausgabe: `sensor.<raum>_aktion` (`ACTION_STATE_MAP`), `sensor.<raum>_empfehlung`, Bus-Events (`AutomationEventEmitter.process`, Coordinator-Listener), `notifications.process_notifications` (Push + `freshairiq_notification`, Cooldown je Art/Raum), Frontend über Status-/Raum-Attribute.

## Diagnose-Datenfluss (Client → Hub → HA-Admin)
`diagnostics.py` (Recorder, anonyme `installation_id`) → `diagnostic_transport.build_upload_chunks` (Pseudonymisierung `_redact_text`, Cursor) → `telemetry.FreshAirIQDiagnosticsClient.async_maybe_upload` (Opt-in, Nachtslot 00:30–06:00 HA-Lokalzeit, Backoff) → Hub `/v1/…` Ingestion → Analyzer → Cluster/Findings → Guardian-Arbeitsliste → Read-API → Diagnostics-HA.

## Externe Quellen → To-do (Hub)
Collector-Loop in `api.create_app` (`_collector_loop`, Intervall `EXTERNAL_COLLECTOR_INTERVAL_MINUTES`=60, sequentiell): `external_collector.collect_sources` (GitHub-Issues+Kommentare, Discourse-Thread/Suche, YouTube, Reddit, RSS) und – falls `SUPPORT_MAIL_ENABLED` – `mail_collector.collect_mailbox` (IMAP read-only) → `_store_collected_reports` (Dedupe über `external_id`, Lifecycle, Owner-Filter `EXTERNAL_COLLECTOR_IGNORED_REPORTERS`) → `ExternalReport` → `triage_work_queue` (GitHub: 1 To-do je Issue; sonst Gruppierung nach Finding-Ähnlichkeit, Mail-Antworten nach Thread) → Read-API/Overview → Diagnostics-HA.

## Persistenz
- Integration: HA `Store` (`storage.LearningStore`, Telemetrie-Zustand `freshairiq.diagnostics_upload.<entry>`, Steuerungsgedächtnis `freshairiq.actuators.<entry>`), Config-Entry-Daten/Optionen/Subentries (Räume), Device-/Entity-Registry (Raumgeräte, `room_devices.py`).
- Hub: SQLAlchemy (Postgres prod, SQLite Tests); Laufzeit-Schalter/Cursor in `HubRuntimeSetting` (z. B. `support_mail_cursor`).
- Runtime-Health (`runtime_health.py`) ist nur im Speicher (Neustart = neue Baseline).
