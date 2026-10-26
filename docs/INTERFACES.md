# Schnittstellen und Contracts (Stand 2026-10-16)

Status: **verifiziert** = am Code beider Seiten bzw. per Test geprüft; **offen** = Gegenprüfung fehlt.

## HA-Entities und Events (Integration → Nutzer-Automationen)
| Contract | Werte / Payload | Status |
|---|---|---|
| `sensor.<raum>_aktion` | `ACTION_STATE_MAP`: ventilate, continue_ventilating, close, wait, do_not_ventilate, ventilate_for_cooling, okay, check_sensor, monitor_only, **ventilate_indirectly**, **open_fully** (reserviert, ohne Erzeuger) | verifiziert (Test `test_arbeitsauftrag_20261014_actions.py` prüft alle produktiven Erzeuger gegen Sensor/Event/Frontend/Übersetzung) |
| `sensor.<raum>_empfehlung` (`house_aligned_action`) | Aktionswerte + `ventilate_later`, **`monitor_open`** | verifiziert |
| `freshairiq_room_action` (schema 1) | Rohstrom: feuert bei jeder Änderung von `room.action`, still nach Neustart, kein Cooldown | unverändert |
| **`freshairiq_room_recommendation`** (schema 1, neu 2026-10-16) | feuert bei Änderung von `house_aligned_action`; Felder wie room_action + `recommendation`, `previous_recommendation`, `recommendation_label`, `message` | verifiziert (Unit); Live-HA offen |
| `freshairiq_house_recommendation`, `freshairiq_mould_risk`, `freshairiq_notification` | siehe `docs/AUTOMATIONEN.md` | unverändert |
| Blueprints | triggern auf `freshairiq_room_action` | unverändert; neues Event dokumentiert, Blueprint nicht umgestellt |
| Dashboard-Live-Kanal (0.26.5.3) | Websocket `freshairiq/dashboard/subscribe` (optional `entry_id`) → Ergebnis, dann Ereignisse mit dem Dashboard-Zustand (bis 0.26.5.2 die Attribute des Statussensors, Inhalt unverändert), nur bei Änderung; Abo folgt dem Config-Entry über Reloads; Statussensor: `freshairiq_live_api: dashboard_ws_v1` + Zusammenfassung | verifiziert (HA-Runtime + Browser) |
| Ablüfter-Automatik (0.26.5.4) | Raum-Ergebnis + `freshairiq_room_action`/`freshairiq_room_recommendation`: `fan_automation` (`mode`, `state`, `owned`, `command`, `command_state`, `user_action_needed`; im Raum-Ergebnis zusätzlich `blocked`, `command_at`, `reason`, `off_pending_since`, `label`, `label_key`), `reference_path` (`default`/`opening`/`neighbour_room`), `configured_actuators.exhaust_fan_control`; `action`-Codes unverändert, `category` = `status`, wenn FreshAirIQ die Aktion selbst ausführt; `freshairiq_notification` `type: fan_auto` (Status), Haus-Ereignis `house_close`/`house_ventilate` mit `category: status`, `fan_automation_only: true`; Diagnose-Satz `fan_automation_trace` (Raum-Key, Modus, Befehl, Grund, Ergebnis; keine Entity-IDs; Hub speichert vollständig, kompakter Export ohne dieses Feld) | verifiziert (HA-Runtime + Browser) |
| Luftaustausch-Anzeige (0.26.5.4) | Raum-Ergebnis `air_exchange` nur während einer Lüftung (sonst `null`): `exchanged_percent`, `minutes_to_95`, `rate_per_min`, `estimate`; reine Anzeige (Karte: Raumkachel + geöffneter Raum), kein Einfluss auf Empfehlungen; über den Live-Kanal, nicht in `freshairiq_room_payload` (`VOLATILE_ROOM_KEYS`); in Diagnose-Räumen enthalten | verifiziert (HA-Runtime + Browser) |

## Diagnose-Upload (Integration ↔ Hub)
| Contract | Detail | Status |
|---|---|---|
| Zeitplan | daily/weekly: individueller Slot (Sekunde) 00:30–06:00 **HA-Lokalzeit**, aus `installation_id`; Fehler/Retry nach 06:00 → nächste Nacht; Mode `errors` & manuelle Sendung sofort | verifiziert (Simulation); Lastwirkung am Hub offen |
| Retry | exponentiell 5 min…6 h + individueller Versatz ≤ 25 %; `Retry-After` (429/503) als Untergrenze | Client verifiziert; **Hub sendet bei 429 keinen `Retry-After`** (Gegenseite offen) |
| Pseudonymisierung | Labels nur als ganze Tokens; FAIQ-/HUB-Codes und 0.x-/20xx-Versionen geschützt; IPs/Entities/E-Mails redigiert | verifiziert (Unit) |
| Feedback-Cooldown (F29) | Hub `/v1/feedback` 429 `detail.retry_after_seconds` ↔ `cooldown.hub_retry_after` | verifiziert (bestehende Tests) |
| Lüftungsdatensatz (Hub 0.3.3.90) | Hub zieht bei jeder Analyse aus `completed_sessions` je Raum-Lüftung einen Datensatz (Prognose inkl. `learning_effectiveness.forecast_args`, Messung, Vergleich, Kontext aus `rooms`/`house`/`learning.rooms`/`configuration_snapshot`, Verlauf aus den Routine-Records); Export JSON Lines `GET /admin/api/exports/ventilation-dataset`, `GET /v1/read/ventilation-dataset`. Integration unverändert – alle Felder werden schon gesendet | verifiziert (Hub-Tests mit Integration-Feldnamen) |
| Prognosequalität (Hub 0.3.3.91, Diagnostics HA 0.5.4) | Hub wertet vergleichbare Lüftungen des Datensatzes aus (`GET /admin/api/forecast-quality`, `GET /v1/read/forecast-quality`); die HA-Admin-Karte lädt sie über `GET /api/freshairiq_diagnostics/forecast-quality/{entry_id}` beim Öffnen von „Lernen“ (≤ 1×/5 min). Integration unverändert | verifiziert (Hub-, HA-Laufzeit- und Browser-Tests) |
| Ausgangsmodell (Integration 0.26.5.4, Hub 0.3.3.92) | Integration sendet je Lüftung `learning_observation` (`observed_rate_per_min`, `usable`, `start_ah`, `end_ah`, `source_ah`, `elapsed_min`, `rate_before`, `samples_before`; Formel/Regeln wie `update_learning`). Hub berechnet daraus `GET /admin/api/start-model` (Format `freshairiq-start-model-candidate`, Zellen Lüftungsart × Größe `<15`/`15-30`/`30-60`/`>=60`/`all`, `recommended`). Übernahme nur per Release: `tools/apply_start_model.py` → `start_model_data.START_MODEL` (Format `freshairiq-start-model` v1); Startwerte wirken nur für Räume/Lüftungsarten ohne Lernprobe | verifiziert (Vertragstest mit echtem Hub-Kandidaten `tests/fixtures/hub_start_model_candidate.json`) |

## Hub-Quellen (externe Eingänge → To-do)
| Quelle | Contract | Status |
|---|---|---|
| GitHub (öffentlich `rupascha/freshairiq`) | `/issues?state=all&sort=updated`, PRs ausgefiltert, Kommentare je Issue (30), Issue-Status steuert To-do; vom Owner eröffnete Issues sind To-dos (seit 2026-10-16), Owner-Kommentare nicht | Code verifiziert; Live-Abruf in dieser Umgebung nicht möglich |
| Reddit | `search.json` (anonym) oder app-only OAuth (`REDDIT_CLIENT_ID/SECRET`) über `oauth.reddit.com`; Fehler mit HTTP-Status in Quellenstatus | Mock-Contract verifiziert; Reddit-API-Contract aus Fachwissen, **nicht gegen aktuelle offizielle Doku/Live geprüft** |
| Support-Mail (E03) | IMAP TLS `imap.ionos.de:993`, SELECT readonly, UID SEARCH, BODY.PEEK[]; Cursor UIDVALIDITY+UID in `HubRuntimeSetting.support_mail_cursor` | Mock-Contract verifiziert; eigenes IONOS-Postfach bestätigt (2026-10-16); Live-Lauf offen bis Secrets gesetzt |
| Diagnostics-HA | rendert `external_sources[]` generisch über `label/status/error` | verifiziert (Code) |

## Offene Gegenprüfungen
- Live-Hub: Quellenstatus Reddit/GitHub, Bestand `external_reports` (F40-Altlasten) – kein Zugriff.
- Echte HA 2026.8/2026.9 (lokal nur 2026.10.1 unter Python 3.14 geprüft).
- iOS-App/WKWebView, Fully Kiosk, HACS-Client (nicht verfügbar; WebKit-Engine via Playwright in CI geprüft).
