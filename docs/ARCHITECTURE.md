# Architektur – FreshAirIQ (Stand 2026-10-16, Branch `arbeitsauftrag-2026-10-14`)

Verifiziert am Code von `-faiq-dev` (Basis `dbdbdcb`, Version 0.26.5.0), `-faiq-hub` 0.3.3.86 und
`-faiq-ha` 0.5.2. Nicht live geprüft: laufende Hub-Instanz, echte HA-Installationen.

## Komponenten
| Komponente | Ort | Aufgabe |
|---|---|---|
| Integration | `-faiq-dev/custom_components/freshairiq` | Config-Flow, Coordinator, Raumphysik, Lernen, Entities, Events, Push, Diagnose-Client |
| Frontend | `…/frontend/freshairiq-card.js` (ES-Modul, per `freshairiq-loader.js` via `import()`), `freshairiq-panel.js`, `freshairiq-card-i18n-en.js` (DE→EN-Paare), `freshairiq-card-style.js` (Farben/Themes, `theme: auto`), `freshairiq-card-freshy.js` (Maskottchen), `freshairiq-card-data.js` (Live-Kanal, Statustexte) – Kartenteile per `import(…?v=<Version>)`; Dashboard-Daten per Websocket `freshairiq/dashboard/subscribe` (`dashboard_live.py`), Statussensor nur Zusammenfassung | Lovelace-Karte (Varianten `iq` Standard, `classic`), Unteransichten im `.subdialog` |
| Blueprints | `blueprints/automation/freshairiq/*.yaml` | Ansage/Gerätesteuerung auf `freshairiq_room_action`, Feuchtequelle, Sonnenschutz |
| Automatische Steuerung (Opt-in, 0.26.5.1) | `actuator_control.py` (rein) + `actuator_controller.py` (HA) | Nur Räume mit eingeschalteter Steuerung: Rollo folgt Fenster/Tür (Position zurück), Aussperrschutz bei Durchgangstür, Sonnenschutz, Ablüfter; Kontakt-/Rollo-Listener + Koordinator-Takt |
| Diagnostics Hub | `-faiq-hub/src/freshairiq_hub` | `/v1/enroll`, Chunk-Upload, Analyzer (Regeln/Cluster), Guardian-Arbeitsliste (`repository.triage_work_queue`), Read-/Control-APIs, Collector-Loop |
| Diagnostics-HA | `-faiq-ha/custom_components/freshairiq_diagnostics` | HA-Admin-Integration; zeigt Hub-Übersicht, Quellenstatus, To-dos |

## Modulkarte (Wartbarkeit, 0.26.5.2)
Die drei größten Module wurden verhaltensgleich aufgeteilt (Golden Master, Formular-Schemas und Coverage
unverändert). Die ursprünglichen Module bleiben die Einstiegspunkte und exportieren alle bisherigen Namen weiter;
die Klassen setzen sich aus Mixins zusammen, große Methoden aus benannten Phasen-Helfern (je ≤ 150 Zeilen).

| Datei | Verantwortung |
|---|---|
| `coordinator.py` | `FreshAirIQCoordinator`: Init, Optionen, Update-Transaktion, Lokalisierung, Ablauf `_async_update_data_impl` (Außenluft → Räume → Haus → Nacht → Entscheidung/Ausgabe), `_async_finalize_cycle` |
| `coordinator_sources.py` / `coordinator_contacts.py` | HA-State-Leser (Sensoren, Wetter, Ablüfter, Rollos) / Öffnungskontakte, Referenzluft je Öffnung, Windausrichtung |
| `room_recommendation.py` (rein) | Raumbezogene Empfehlung `_recommendation` (Auslöser, Eignung, Aktion) |
| `coordinator_listeners.py` | Quell-Listener, Refresh-Bündelung, Wartezeit auf die Abschlussmessung |
| `coordinator_room.py` | Raumauswertung `_async_evaluate_room`: Sensoren, Phasenreihenfolge, Overlays (Sonnenschutz, Interventionen, Aktoren) |
| `coordinator_room_contacts.py` | Dreistufige Kontakte (Entprellung), Kontaktwahrheit, Kontaktablauf |
| `coordinator_room_session.py` | Lüftungssitzung je Raum: Start, Neustart/Reparatur, Verfolgung, Schließen |
| `coordinator_room_model.py` | Raummodell, Empfehlung, Prognose, eingefrorene Sitzungsprognose |
| `coordinator_room_result.py` | Wiederholsperre, Ziele, veröffentlichtes Raumergebnis |
| `coordinator_house.py` / `coordinator_night.py` | Außenprognose, Lüftungsgruppe, Hausaggregate, passive Lüftung / Nachtlernen, Nachtprognose, Nachtstrategie |
| `coordinator_decision.py` | Finale Hausempfehlung, Präsentationsschichten, Status-Extras, veröffentlichte Daten |
| `coordinator_sessions.py` / `coordinator_session_validation.py` / `coordinator_session_events.py` | Sitzungsabschluss (Messung, Lernen) / Statistik und Prognosevalidierung / Ereignisdatensätze |
| `config_flow.py` | `FreshAirIQConfigFlow`, Weiterexport, Fehlerschutz (`guard_flow_steps`) für alle Flows und Mixins |
| `config_flow_fields.py` / `config_flow_schemas.py` | Feld-Helfer, Sprachlabels, Klima-Picker / Außenluft- und Einstellungsformulare |
| `config_flow_goals.py` / `config_flow_rooms.py` | Zielprioritäten / Raumformulare, Öffnungsreferenzen, Normalisierung der Raumdaten |
| `config_flow_subentry.py` | `FreshAirIQRoomSubentryFlow` (Raum als Subentry) |
| `config_flow_options.py` + `config_flow_options_rooms.py` + `config_flow_options_settings.py` | `FreshAirIQOptionsFlow`: Menü/Arbeitskopie/Persistenz + Raum-Schritte + Einstellungs-Schritte |
| `diagnostics.py` | `FreshAirIQDiagnosticsRecorder` (Identität, Clients, Aufzeichnung, Aufräumen), Views, HA-Diagnose |
| `diagnostics_limits.py` (rein) / `diagnostics_privacy.py` | Grenzwerte / datenschutzsichere Schlüssel, Bereinigung, Kurzfassungen |
| `diagnostics_records.py` / `diagnostics_export.py` | Konfigurations-Snapshot, Zyklus-/Trend-Datensätze / Export (Datensätze, Funnel, Historien) |
| `diagnostic_chunks.py` (rein) | Analyse-Export und Upload-Chunks (`build_upload_chunks`); `diagnostic_transport` exportiert die Namen weiter |
| `telemetry_hub.py` (rein) / `telemetry_reports.py` | Hub-Basis-URL, Chunk-Kodierung / Feedback, Client-Fehler, Support-Diagnose |
| `storage_defaults.py` (rein) | Standardwerte je Raum des Lernspeichers (Schlüsselreihenfolge unverändert) |

Wachstumsgrenzen: `tools/maintainability_gate.py` (≤ 800 Zeilen je Python-Datei, ≤ 150 Zeilen je Funktion,
≤ 200 000 Byte je Frontend-Modul); bestehende Ausnahmen stehen mit Begründung in `quality/maintainability_baseline.json`
und dürfen nur schrumpfen.

## Entscheidungs-Datenfluss (Sensor → Ausgabe)
1. HA-States (Temp/RH/CO₂/Kontakte/Wetter) → `FreshAirIQCoordinator._async_update_data_impl` (Takt 30 s, zusätzlich Quellereignisse); die Phasen liegen seit 0.26.5.2 in den `coordinator_*`-Modulen (siehe Modulkarte).
2. Je Raum `model.evaluate_room` → `RoomResult.action` (`Ventilate`, `Continue ventilating`, `Close` mit Latch `close_notified`, `Wait`, `Okay`, `Do not ventilate`, `Ventilate for cooling`, `Check sensor`, `Monitor only`); Coordinator ersetzt für Räume ohne Öffnungskontakt `Ventilate*` → `Ventilate indirectly`.
3. Hausebene: `_house_recommendation_and_plan` (`coordinator_decision.py`) → `consolidation.stabilise_recommendation(…, previous=…)` (Echtzeit-Invarianten, Daueröffnung `passive_open_monitor`, Aggregat-Schließschutz mit Hysterese seit 2026-10-16) → `decision_brain`.
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
