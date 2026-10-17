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

## Diagnose-Upload (Integration ↔ Hub)
| Contract | Detail | Status |
|---|---|---|
| Zeitplan | daily/weekly: individueller Slot (Sekunde) 00:30–06:00 **HA-Lokalzeit**, aus `installation_id`; Fehler/Retry nach 06:00 → nächste Nacht; Mode `errors` & manuelle Sendung sofort | verifiziert (Simulation); Lastwirkung am Hub offen |
| Retry | exponentiell 5 min…6 h + individueller Versatz ≤ 25 %; `Retry-After` (429/503) als Untergrenze | Client verifiziert; **Hub sendet bei 429 keinen `Retry-After`** (Gegenseite offen) |
| Pseudonymisierung | Labels nur als ganze Tokens; FAIQ-/HUB-Codes und 0.x-/20xx-Versionen geschützt; IPs/Entities/E-Mails redigiert | verifiziert (Unit) |
| Feedback-Cooldown (F29) | Hub `/v1/feedback` 429 `detail.retry_after_seconds` ↔ `cooldown.hub_retry_after` | verifiziert (bestehende Tests) |

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
