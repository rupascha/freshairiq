# Ergebnisregister – Arbeitsauftrag 2026-10-14 (inkl. E09 vom 15.10., Z01 vom 16.10.)

Stand 2026-10-16. Backlog-Snapshot: F01–F41, E01–E09, H01–H42 (historisches Inventar, Reihenfolge wie im Auftrag), Z01.
Commits: dev = `-faiq-dev` Branch `arbeitsauftrag-2026-10-14`, hub = `-faiq-hub` gleicher Branch.
Prüfläufe: P1 = Pure-Suite 2074/2074 (Py 3.13+3.14); P2 = Quality-Gate lokal (alle Stufen außer instabiler Performance) + CI `core-quality` grün;
P3 = Golden Master 117/117; P4 = Playwright (lokal Chromium/Android, CI +WebKit/Firefox); P5 = HA-Runtime 2026.10.1 (377/377 grün; kombiniertes HA-Coverage-Gate 99,88 % / config_flow 100 % / jedes Modul ≥ 98 %, PASS seit dev 9a72f55 + Coordinator-Tests);
P6 = Hub 423 Tests + 7 Gate-Stufen grün. Nicht geprüft = ausdrücklich genannt.

Status: UV = UMGESETZT UND VERIFIZIERT · BV = BEREITS VORHANDEN UND VERIFIZIERT · BO = BEREITS VORHANDEN, GEZIELT OPTIMIERT ·
TU = TEILWEISE UMGESETZT · VO = VORHANDEN, VERIFIKATION OFFEN · BL = BLOCKIERT · NU = AKTUELL NICHT UMSETZBAR · NZ = NICHT ZUTREFFEND – BEGRÜNDET

| ID | Status | Festgestellt / geändert | Nachweis | Fehlt | Nächster Schritt |
|---|---|---|---|---|---|
| Z01 | TU | Ist-Stand ermittelt (dev = dbdbdcb = öffentl. 0.26.5.0; Hub 0.3.3.86; HA 0.5.2; internal leer); Baseline rot wegen fehlender Dotfiles → rekonstruiert; Merkdateien angelegt | docs/ARCHITECTURE/INTERFACES/DEVELOPMENT/ANALYSIS/WORK_REGISTER.md; P1–P6 | Live-Komponenten (Hub, IONOS, HA-Installationen) | Übergabestand in DEVELOPMENT.md fortschreiben |
| F01 | UV | Ursache reproduziert: Aggregat-Close-Guard ohne Hysterese kippt jede 30 s, Präsentationssync überträgt in alle Räume. Fix: Hysterese 125 % nach veröffentlichtem Close; harte Closes/Neustart unverändert; Rohstrom unverändert | dev 5ea6d56; tests/test_arbeitsauftrag_20261014_actions.py (9 Defekttests rot am Ausgangsstand); P1–P3 | Live-HA/Telegram | Nach Deployment Ereignisprotokoll eines Morgens prüfen |
| F02 | UV | passive_open_monitor ⇒ `house_aligned_action=monitor_open`; Raumliste „Daueröffnung überwachen“; physikalische Aktion bleibt (Diagnose); Auskühl-Close nie toleriert | dev 5ea6d56; Tests F02; P1, P4 | echte HA | – |
| F03 | NU | Kein Gerätecontract für gemeinsame Lüfter (Entity-IDs/Luftweg fehlen); Regelwerk (Einstimmigkeit, Stopps) ist Produktentscheidung | Analyse coordinator `mechanical_exhaust_active` | Topologie-Konfiguration + Entscheidung | Regeln festlegen; Fixture mit gemeinsamem Aktor |
| F04 | UV | Contract dokumentiert: action (nach Hausabgleich, `canonical_action`), Empfehlung, Haus, Benachrichtigung inkl. Cooldown/Neustart | docs/AUTOMATIONEN.md/AUTOMATIONS.md; Doku-Contract-Test | – | – |
| F05 | UV | Bestätigt: aligned-only-Änderung → 0 Raumevents. Neu additiv `freshairiq_room_recommendation`; Rohstrom unverändert. **2026-10-17:** beide Blueprints mit Auswahl „Grundlage“ (Hausentscheidung/Raumlokal); Ansage standardmäßig Hausentscheidung (Feedback FAIQ-FB-EE8489B6176D), Lüfter standardmäßig raumlokal | dev 5ea6d56; ha_tests/test_blueprint_basis_20261017.py (echte HA-Automationen, rot auf Alt-Blueprints) | Nutzer müssen Blueprints neu importieren | – |
| F06 | BV | `scaled_min_return`, Hysterese, Repeat-Cooldown vorhanden | tests/test_support_cases_026407.py, test_planned_airing_026410.py in P1 | 9,4-m³-Realfall live | – |
| F07 | VO | Planned-Airing-Schutz vorhanden und getestet; Nutzerbestätigung fehlt | test_planned_airing_026410.py (P1) | Nutzerbestätigung | Rückmeldung einholen |
| F08 | BV | Lüfter-Wortlaut (`fan_only`) in Event/Frontend/Push | bestehende Tests P1 | – | – |
| F09 | UV | DE/EN-Labels für indirektes Lüften in Event, Frontend, Übersetzungen | dev 5ea6d56; Test F09 | – | – |
| F10 | UV | Vokabular vollständig (Sensor/Event/Frontend/Übersetzung); `Open fully` ohne produktiven Erzeuger (reserviert) | Test prüft alle Erzeuger | – | – |
| F11 | UV | **2026-10-17:** gelöst mit A-33 (VOC-Index-Sensoren auswählbar, Index-Schwelle 250; IKEA VINDSTYRKA via Zigbee2MQTT) | tests/test_voc_index_20261017.py, ha_tests/test_voc_index_20261017.py | Nutzerbestätigung | – |
| F12 | UV | Orientierung je Kontakt; Kontakt-Referenzpaar-Fehler korrigierbar und gespeichert; Name/Position des Kontakts im Formular; End-to-End in echtem HA: HA-Import, Neuanlage, Bearbeiten, 0/1/mehrere Kontakte, Zurück, Speichern, Reload. **2026-10-16:** neuer Raum in den Optionen bekam keine Entities (A-19, behoben); abgelehnte Raumanlage traced jetzt die festen Fehlercodes (`validation_error_codes`, keine Namen/Entities). Gemeldetes intermittierendes Orientierungsproblem nicht reproduziert | ha_tests/test_options_add_room_reload_20261016.py, test_room_trace_error_codes_20261016.py, test_cov_options_flow.py, test_cov_room_subentry_flow.py (dev 5301e50 + dieser Stand) | Nutzerfall (intermittierend) | bei neuer Meldung Trace-Codes auswerten |
| F13 | VO | Mehrfachkontakte (`multiple=True`) vorhanden; HA-Flow-Suite grün | Code, ha_tests 75/75 | Nutzerbestätigung | – |
| F14 | NU | Topologie-/Doku-Bedarf; keine Code-Lücke belegt | Analyse | Produktentscheidung Referenz-Paare | Doku-Abschnitt ergänzen |
| F15 | NU | Zentrale Empfängerverwaltung = größere Erweiterung | Analyse notifications.py | Design/Freigabe | Konzept |
| F16 | UV | **2026-10-17 (Feedback FAIQ-FB-7C943C054B43, Owner-Entscheidung):** Optionen „Nur senden, wenn der Empfänger zuhause ist“ (Standard aus) und „Wichtige Warnungen auch unterwegs senden“ (Standard an); Bewohner-Handy folgt dem eigenen Tracker (Slot-Reihenfolge), allgemeine Ziele nur, wenn nicht alle abwesend; unbekannt = zuhause; Diagnosegrund `recipients_away` | ha_tests/test_notify_presence_20261017.py (5 Fälle rot auf Altstand) | Nutzerbestätigung | – |
| A-31 | UV | **2026-10-17 (Owner-Wunsch „Ziel komplett aus“):** Lüftungsziele ab Priorität 2 mit „Aus“; Raumschlüssel `disabled_goals`; abgeschaltetes CO₂-/Temperaturziel ausgeblendet, kein „Zum Kühlen lüften“ bzw. keine CO₂-Lüftung, Schutzgrenzen unverändert; Entfeuchtung nicht abschaltbar (Fehler `humidity_goal_required`) | tests/test_goal_off_20261017.py, ha_tests/test_goal_off_20261017.py | Nutzerbestätigung | – |
| A-32 | UV | **2026-10-17 (Nutzer-Feedback Node-RED, Owner-Auftrag):** Raum-Hysterese für „Schließen“ im rohen Strom (`close_notified` gesetzt, Freigabe ab 125 % der Schwelle) | tests/test_close_hysteresis_20261017.py, ha_tests/test_close_hysteresis_20261017.py (rot auf Altstand) | Nutzerbestätigung | – |
| A-33 | UV | **2026-10-17 (Support-Fall VINDSTYRKA, Owner-Auftrag):** VOC-Index-Sensoren auswählbar und mit Index-Schwelle 250 bewertet | tests/test_voc_index_20261017.py, ha_tests/test_voc_index_20261017.py | Nutzerbestätigung | – |
| A-34 | UV | **2026-10-17 (Owner-Test iOS 18.6.2):** Zurück zur Raumliste springt unter iOS nicht mehr nach oben (Nachsetzen der Zielposition, ohne gegen Nutzer-Scrollen zu arbeiten) | frontend_tests/e08-scroll.spec.mjs „E08 iOS …“ (2 Tests, rot auf Altstand) | Bestätigung auf iOS-Gerät | – |
| A-35 | UV | **2026-10-17 (Community-Hinweis):** Zustands-Sensoren als Enum mit Optionen, damit der Automations-Editor die Zustände anbietet | ha_tests/test_state_sensor_options_20261017.py | Nutzerbestätigung | – |
| A-36 | UV | **2026-10-17 (Community, Owner-Auftrag):** Feuchtequelle als Entität, Ereignis und Blueprint für Automationen | tests/test_moisture_source_event_20261017.py, ha_tests/test_moisture_source_entity_blueprint_20261017.py (echte Blueprints in echten Automationen) | Nutzerbestätigung | – |
| A-37 | UV | **2026-10-17 (Community, Owner-Auftrag):** Nachtkühlung im Profil „Sommer kühlen“ ohne Höchstdauer-Schluss, ausdrückliches Schließen bei wärmer werdender Außenluft | tests/test_summer_night_cooling_20261017.py, ha_tests/test_sun_protection_20261017.py (Begründungstexte), Golden Master neu aufgezeichnet (nur Begründung) | Nutzerbestätigung | – |
| A-38 | UV | **2026-10-17 (Community, Owner-Auftrag):** Sonnenschutz nach Himmelsrichtung und Sonnenstand, Entität „Sonnenschutz empfohlen“, Blueprint „Rollos gegen die Sonne“ (DE/EN) | tests/test_sun_exposure_20261017.py, ha_tests/test_sun_protection_20261017.py (echte Blueprints in echten Automationen) | Nutzerbestätigung | – |
| A-39 | UV | **2026-10-17 (Owner-Auftrag):** Automatische Steuerung von Rollos (Fenster öffnen → Rollo hoch, Schließen → alte Position; Durchgang-Aussperrschutz; Sonnenschutz) und Ablüfter (Feuchtequelle/Empfehlung) als Opt-in in den Raumeinstellungen | tests/test_actuator_control_20261017.py, ha_tests/test_actuator_control_20261017.py (echte Flows, echte Dienstaufrufe, Neustart-Wiederherstellung) | Nutzerbestätigung am echten Rollo | – |
| A-40 | UV | **2026-10-17 (Owner-Auftrag):** Sonnenschutz mit Vorlauf (15 min), Wärmeerwartung aus Vorhersage/Komfortziel und Bewölkungsprüfung | tests/test_sun_exposure_20261017.py (Sonnenstand gegen Referenzwerte), ha_tests/test_sun_protection_20261017.py (Berlin, eingefrorene Zeit) | Nutzerbestätigung im Sommer | – |
| A-41 | UV | **2026-10-18 (Community):** kein „offen lassen · schließen“ für dasselbe Fenster, kein Wechsel Schließen/Weiterlüften bei einem Fenster | tests/test_opening_flapping_026502.py (3 von 4 Tests rot auf altem Code) | Nutzerbestätigung | – |
| A-42 | UV | **2026-10-18 (Community):** Außen-PM2.5-Auswahl bietet auch µg/m³- und WAQI-Sensoren | tests/test_outdoor_pm25_026407.py, ha_tests/test_outdoor_pm25_picker_026502.py | Nutzerbestätigung | – |
| A-43 | UV | **2026-10-18 (Community):** alle kleinen Kartentexte inkl. Lernseiten skalierbar, neue Kategorie „Lernmodell & Analyse“, bis 200 % | tests/test_text_scale_small_text_026502.py (keine feste Größe < 14 px übrig), Browser-Suite 50/50, Sichtprüfung 100/200 % | Nutzerbestätigung | – |
| A-44 | UV | **2026-10-19 (Owner):** kein Schließen bei laufender Sauna/Feuchtequelle, auch nicht über Haus-/Etagenlüftung | tests/test_moisture_source_never_closed_026502.py (Haus- und Etagenpfad, Grenzfälle) | Nutzerbestätigung | – |
| A-45 | UV | **2026-10-19 (Community):** Ablüfter-Automatik wirkt ohne Neustart und bei Räumen ohne Fensterkontakt | ha_tests/test_exhaust_fan_live_026502.py | Nutzerbestätigung | – |
| A-46 | UV | **2026-10-19 (Owner):** Diagnose je Kontakt (Art, Herkunft, Drei-Zustand, gleiche Namen) | ha_tests/test_diagnostics_contacts_026502.py | – | – |
| A-47 | UV | **2026-10-19 (Support):** „geöffnet“ als offen erkannt | tests/test_opening_state_geoeffnet_026502.py, ha_tests/test_geoeffnet_template_026502.py (Coordinator geschlossen → gekippt → geöffnet → geschlossen; ohne Fix rot) | Nutzerbestätigung | – |
| A-48 | UV | **2026-10-23 (Community):** Nebenraum-Referenz für Ablüfter | tests/test_exhaust_reference_026503.py, ha_tests/test_exhaust_reference_026503.py (ohne Änderung rot) | Nutzerbestätigung | – |
| A-49 | UV | **2026-10-23 (Owner):** Gespeicherte Felder wieder entfernbar | ha_tests/test_clearable_fields_026503.py (läuft alle Optionsseiten ab, leert jedes vorbelegte Feld; ohne Fix 15 Funde) | Nutzerbestätigung | – |
| A-50 | UV | **2026-10-23 (Owner):** Einstellungen ohne Neustart wirksam (Rollladen-Automatik, neue Kontakte) | ha_tests/test_live_config_026503.py (ohne Fix 4 von 5 rot; Optionsflow-Pfad mit geschlossenem Dialog) | Nutzerbestätigung | – |
| A-51 | UV | **2026-10-23 (Owner):** „Aus“ bei Lüftungszielen bleibt beim erneuten Bearbeiten erhalten | ha_tests/test_room_edit_keeps_settings_026503.py (ohne Fix 3 von 3 rot; generisch: Raum-Editor + alle Optionsseiten ohne Änderung bestätigt ⇒ nichts geändert) | Nutzerbestätigung | – |
| A-52 | UV | **2026-10-23 (Community):** Schimmel-Event und Haus-Event ohne Flut | tests/test_event_flood_026503.py (ohne Fix 3 rot, Tagestest 60/h) | Nutzerbestätigung | – |
| A-53 | UV | **2026-10-23 (Community):** Aktion/Status, Erinnerung, abgestimmte Raum-Meldungen | tests/test_notification_policy_026503.py | Nutzerbestätigung | – |
| A-54 | UV | **2026-10-23 (Community):** Temperaturziel hält Fenster offen | tests/test_comfort_cooling_026503.py | Nutzerbestätigung | – |
| A-55 | UV | **2026-10-23 (Community):** Offene Verbindungen | tests/test_open_connections_026503.py, ha_tests/test_open_connections_026503.py | Nutzerbestätigung | – |
| A-56 | UV | **2026-10-23 (Community):** Geteilter Lüfter | ha_tests/test_open_connections_026503.py (ohne Fix rot) | Nutzerbestätigung | – |
| A-57 | UV | **2026-10-23 (Community):** Lüftung endet am Feuchte-Plateau | tests/test_humidity_plateau_026503.py | Nutzerbestätigung | – |
| A-58 | UV | **2026-10-23 (Owner):** jede Einstellung sofort wirksam | ha_tests/test_live_settings_026503.py (ohne Fix 4 von 5 rot) | Nutzerbestätigung | – |
| A-59 | UV | **2026-10-23 (Community, GitHub #15):** kein Lüften/Schließen-Pendeln | tests/test_issue15_flapping_026503.py (Tagestest: 72 → 19 Meldungen) | Nutzerbestätigung | – |
| A-60 | UV | **2026-10-23 (Owner):** Hub sammelt alle Lüftungen mit Prognosen zur Optimierung von Grundformel, Prognosen und Lernmodellen | -faiq-hub tests/test_ventilation_dataset_20261023.py (Hub 0.3.3.90) | Auswertung echter Daten | – |
| A-61 | UV | **2026-10-23 (Community, GitHub #17):** Theme-Unterstützung, card-mod/UIX-Styles bleiben | frontend_tests/theme.spec.mjs (ohne Fix 6 von 6 rot) | Nutzerbestätigung | – |
| A-62 | UV | **2026-10-23 (Community):** Recorder-Last senken ohne Funktionsverlust | ha_tests/test_recorder_load_026503.py, tests/test_recorder_load_026503.py, frontend_tests/live.spec.mjs; Messung mit echtem Recorder | Nutzerbestätigung | – |
| A-63 | UV | **2026-10-23 (Nutzerfeedback):** Lüftungsprotokoll pro Tag und als CSV | tests/test_ventilation_daily_026503.py, ha_tests/test_cov_http_apis.py, frontend_tests/ventlog.spec.mjs | Nutzerbestätigung | – |
| A-64 | UV | **2026-10-25 (Community, GitHub #19):** Kühlentscheidung im Komfortprofil folgt dem Komfortziel des Raums; Kühl-Untergrenze im Komfortprofil einstellbar (0.26.5.4) | tests/test_comfort_cooling_start_026503.py (ohne Fix 7 rot), ha_tests/test_comfort_cooling_start_026503.py (ohne Fix 3 rot; nur Modellfix ohne Fensterbewertung ebenfalls 3 rot) ; UI 0.26.5.4: ha_tests/test_cov_options_flow.py::test_profile_comfort_details_offer_the_cooling_lower_limit, test_retired_replacements (keine Doppelfelder) | Nutzerbestätigung | – |
| A-65 | UV | **2026-10-25 (Support-Diagnose + Owner):** Ablüfter-Automatik ohne Rückkopplung, Meldungen je Steuerungsmodus, Nebenraumreferenz beim Start, Diagnose | tests/test_fan_automation_026504.py, ha_tests/test_fan_automation_026504.py (Garage durchgängig; alter Code: Neustart nach 33 s, Ein/Aus im Sekundenwechsel), frontend_tests/fanauto.spec.mjs | Nutzerbestätigung (Garage, heinzel) | – |
| A-66 | UV | **2026-10-25 (Community):** Anzeige des Luftaustauschs während der Lüftung (Prozent + Zeit bis 95 %), nur Anzeige | tests/test_air_exchange_026504.py, ha_tests/test_air_exchange_026504.py, frontend_tests/airexchange.spec.mjs | Nutzerbestätigung | – |
| A-67 | UV | **2026-10-25 (Support-Fall):** Pop-ups überdecken den Bildschirm auch mit UIX/card-mod/Glas-Theme | frontend_tests/e08-scroll.spec.mjs (Overlays × iPhone/Desktop × normal/backdrop-filter/transform+overflow, 30 Räume, Touch-Wisch; ohne Fix 8 von 12 rot), frontend_tests/theme.spec.mjs (UIX/card-mod, Glas/hell/Standard, Raumübersicht/Raum/Support/Gäste/settings, Erklärfenster; ohne Fix 6 von 6 rot) | Nutzerbestätigung; echter iOS-WebKit-Lauf (Playwright-WebKit-Download hier gesperrt) | – |
| A-68 | UV | **2026-10-25 (Support-Diagnose e119):** Lüfterraum zählt nicht als offenes Fenster (kein 10-s-Pendeln, Keys/Namen konsistent), Ablüfterraum ohne Kontakt „Ablüfter einschalten“, Räume ohne Fenster nennen nur bekannte Luftwege, CO₂ führt vor Kühlung (Hysterese), automatisches AUS bei Höchstlaufzeit ohne Handaufforderung | ha_tests/test_support_e119_026504.py (alter Code: beide rot – Namen/Keys, fehlender Hinweis), tests/test_support_e119_026504.py, ha_tests/test_fan_automation_026504.py (Garage: ein EIN, AUS nach 60 min, keine „ausschalten“-Pushes) | Nutzerbestätigung; BLOCKIERT: Sollziel Schlafzimmer, Referenz-Sensorzuordnung | – |
| A-69 | UV | **2026-10-25 (Owner, Punkt 2):** Ausgangsmodell für neue Installationen aus Hub-Daten (nur empfohlene Werte, nur per Release; ausgeliefert leer) | tests/test_start_model_026504.py (inkl. Vertragstest mit echtem Hub-Kandidaten), ha_tests/test_start_model_026504.py (Startwert → erstes Lernen 0,045→0,044; Rückzug), Hub tests/test_start_model_20261025.py | Echte Daten im Hub, erste Empfehlung | Übernahme per Release |
| A-70 | UV | **2026-10-25 (Owner, Punkt 3):** Deutlicherer Hinweis auf den Nutzen geteilter Diagnosen (Karte + Einstellungsseite), veraltete Aussagen (Beta standardmäßig aktiv, nur lokaler Staging-Hub) korrigiert | tests/test_start_model_026504.py::test_the_diagnostics_hint_names_the_benefit_in_both_languages, frontend_tests/freshairiq.spec.mjs (Consent-Hinweis, passt auf 390 px), UI-Vertrag mit Freigabevermerk | Wirkung: Anteil teilender Installationen im Hub beobachten | – |
| A-71 | UV | **2026-10-25 (Owner, Review):** Review-Fixes A04, A02/A03/A05/A06/A10, A09, A01 (Namen), A11/A12 (Tests) | tests/test_review_fixes_026504.py (alter Code: 6/6 rot), ha_tests/test_review_fixes_026504.py (alter Code: 4/4 rot), ha_tests/test_fan_automation_026504.py (Trace mit Ergebnis) | Nutzerbestätigung; A07 als nächster Schritt | – |
| A-72 | UV | **2026-10-25 (Owner, Review A07):** CO₂ ab Warnschwelle fordert selbst zum Lüften auf (Leitplanken, Stoßlüftung) | tests/test_co2_airing_026504.py (Schwellen 950–1220, feuchtere Luft, Ziel aus, Pollen, kritisch, Feuchtefall, Hysterese, Kühlung, Schließen, keine Freigabe), ha_tests/test_co2_airing_026504.py (Küche: Lüften → Fenster auf → Schließen nach CO₂-Abbau; mit Kühlbedarf offen) | Nutzerbestätigung | Nebenbefund → A-73 |
| A-73 | UV | **2026-10-25 (Owner):** kein „Weiterlüften“/„Schließen“ für ein geschlossenes Fenster während der Schlussmessung | tests/test_final_measurement_026504.py (alter Code: 5/5 Logiktests rot), ha_tests/test_final_measurement_026504.py (alter Code rot: Küche „Continue ventilating“) | Nutzerbestätigung | – |
| A-74 | UV | **2026-10-26 (Owner, Audit .4(2)):** P1-03, P1-04, P1-06, P1-07, P2-08 beheben; P1-05 nur Diagnose; P1-01 Regel bleibt | tests/test_audit_026504b.py (alter Code: 11 rot, 10 Grenzfälle grün), ha_tests/test_audit_026504b.py (alter Code 3/3 rot), ha_tests/test_review_fixes_026504.py (Teilstart/Steuerung-aus, alter Code rot), tests/test_review_fixes_026504.py (Teilstart = partial) | Nutzerbestätigung | – |
| A-75 | UV | **2026-10-26 (Owner, Auftrag S01–S19):** S01–S08, S11, S12, S19 beheben; S13/S14/S18 Entscheidung; S09/S10/S15–S17 bewertet | tests/test_audit_026504c.py (alter Code: 8 rot, 4 Grenzfälle grün), ha_tests/test_audit_026504c.py (alter Code 5/5 rot), ha_tests/test_blueprint_start_sync_026504.py (alte Blueprints: 5 rot, 3 Grenzfälle grün) | Nutzerbestätigung | S13/S14 → A-76; S18 nicht umgesetzt (Owner) |
| A-76 | UV | **2026-10-26 (Owner):** S13 und S14 umsetzen, S18 nicht; Nachprüfung N01–N05 | tests/test_audit_026504c.py (N04/N01: 3 rot am alten Code), ha_tests/test_audit_026504c.py (N01/N02: 5 rot), ha_tests/test_blueprint_start_sync_026504.py (N03/N05/Reload: 4 rot, 2 Grenzfälle grün), frontend_tests/live.spec.mjs + theme.spec.mjs (alter Frontend-Stand: 12 rot) | Nutzerbestätigung | – |
| A-77 | UV | **2026-10-26 (Owner, Audit .4(5)):** F01–F04 | ha_tests/test_audit_026504c.py (F01/F02 + N02 umgestellt: alter Code rot), ha_tests/test_blueprint_start_sync_026504.py (F03/N03: 4 rot, Grenzfälle grün), frontend_tests/live.spec.mjs (F04: alter Stand 2 rot) | Nutzerbestätigung | – |
| A-27 | UV | **2026-10-17 (Owner-Auftrag):** Temperatur-/Feuchte-Auswahl bietet Geräteklasse oder passende Einheit an (8 Felder, Helfer `_climate_sensor_selector`) | ha_tests/test_unit_climate_pickers_20261017.py; bestehender Laufzeittest test_unit_based_climate_sensors_are_accepted_by_room_flow_and_runtime | Nutzerbestätigung | – |
| F17 | NU | Nur title/message; Deep-Link/gespeicherte Nachricht braucht Design + iOS-Runtime | Analyse `_send_target` | Design, iOS | Konzept |
| F18 | NU | Event-Bausteine vorhanden, kein Kiosk-Workflow | Analyse | Infrastruktur-Entscheidung | Doku-Workflow |
| F19 | VO | 6 Font-Scale-Optionen; Layout ohne Geräte nicht abschließend prüfbar | Code | Screenshots/Geräte | – |
| F20 | VO | Kontexterklärungen (`data-explain`) vorhanden | Code | Nutzertest | – |
| F21 | NZ | Nutzer hat Freshy gefunden (bestätigt) | Quelle S92–95 | – | – |
| F22 | NU | Theme-Variablen = Erweiterung (#17) | Code ha-card | Design | Konzept |
| F23 | BV | Subentry-/Raumgerät-Migration vorhanden + Tests | test_room_devices_026409.py, test_room_deletion_026406.py (P1) | – | – |
| F24 | UV | öffentliche Iteration statt Mapping | dev 0f4d20a; ha_tests/test_registry_deprecations_20261016.py (rot am Ausgangsstand) | HA 2026.8/2026.9 live | – |
| F25 | UV | `async_get_device_by_identifier` (ab HA 2026.8 vorhanden) | wie F24 | wie F24 | – |
| F26 | VO | Kein Backend-Fehler; Karte ist ES-Modul (iPadOS ≥ 11.1 nötig) | CI WebKit-Lauf | Gerät/Browser-Version | Version des iPad erfragen |
| F27 | TU | Restlücke F09 geschlossen; Gesamt-DE/EN-Durchlauf nicht automatisiert | Tests F09/F10, Golden `--english` vorhanden | vollständiger UI-Durchlauf | – |
| F28 | VO | Release-Metadaten/Workflow-Gates vorhanden | github_release_gate | HACS-Client | – |
| F29 | BV | Cooldown-Contract beidseitig | test_feedback_cooldown_026410.py (P1) + Hub-Tests (P6) | – | – |
| F30 | BL | Keine Antwortroute; anonymes Postfach erfordert Design/Datenschutzentscheidung | Analyse Hub-APIs | Entscheidung | Konzept |
| F31 | VO | Abschlussmessungs-Gate verhindert Lernen mit fehlenden Werten; Timeout-Ursache ohne Rohdaten offen | Code measurement_frame/post_stabilization | Rohchunks Batch 0.26.5.0 | Daten bereitstellen |
| F32 | VO | Stale-Startframe-Gate vorhanden (Schutz, kein Defekt belegt) | Code | Sensor-Reportingdaten | – |
| F33 | VO | Ungültigkeitsgründe werden je Vergleich geführt; kleine Stichprobe | forecast_validation + Tests P1 | Rohdaten | – |
| F34 | VO | Unterbrechungsgründe erfasst; Ursachenverteilung ohne Daten offen | post_stabilization | Rohdaten | – |
| F35 | VO | Recovery-Grace vorhanden; Evidenz teils Altversionen | Code | aktuelle Daten | – |
| F36 | UV | Fallback nicht mehr als Invarianzverletzung | dev 0710d1c; test_arbeitsauftrag_20261014_guardian.py | – | – |
| F37 | VO | Lückenursache ohne Rohdaten nicht trennbar | – | Rohdaten | – |
| F38 | UV | Erholung + Mindestwirkung | dev 7d99fb2/fe8cc95; test_arbeitsauftrag_20261014_runtime.py | – | – |
| F39 | UV | Strukturbezogener Token-Schutz; Altdaten-Markierung im Hub vorhanden (`release_insights`) | dev 0f6f7c4; test_arbeitsauftrag_20261014_anonymisation.py | – | – |
| F40 | BL | Lifecycle-Code geprüft; Live-Bestand nicht zugreifbar; keine Issues/To-dos verändert | Code | Live-Hub-Zugriff | Hub-Export nach Deploy prüfen |
| F41 | VO | Zähldefinitionen nicht ohne Daten prüfbar | – | Exportdaten | – |
| E01 | TU | Bestehende Importe erhalten; Mail-Quelle ergänzt; keine Dubletten (Message-ID/external_id) | hub 1206762; P6 | Live | Deploy |
| E02 | TU | Antworten/Anhänge (Mail) ergänzen denselben Vorgang; Anhänge nur Metadaten, **keine** OCR/Bildanalyse im Hub (sichtbar vermerkt) | Test E2E Mail→To-do | Analyse-Provider + Freigabe | Entscheidung KI/OCR |
| E03 | TU | IMAP read-only im bestehenden 60-min-Loop, Cursor, Thread, Datenschutz; Postfachart bestätigt (eigenes IONOS-Postfach, 2026-10-16) → Defaults `imap.ionos.de:993` passen **2026-10-17 (Owner-Auftrag):** Zugangsdaten alternativ in der Hub-Weboberfläche (/admin → „Support-Postfach (IONOS)“): serverseitig in `$UPDATER_DIR/secrets/support_mail.json` (0600), Passwort nie an den Browser, Verbindungstest nur lesend (Login + SELECT readonly), Abruf unabhängig vom Schalter „Öffentliche Quellen“; Konto-/Ordnerwechsel liest neu (Dedupe per Message-ID). | hub 1206762; 26 Tests mit IMAP-Double; hub tests/test_support_mail_web_settings_20261017.py | Zugangsdaten eintragen (Weboberfläche oder Env) | Hub deployen, unter /admin Postfach eintragen und „Verbindung testen“ |
| E04 | TU | Kanonischer Vorgang über bestehende Arbeitsliste; strukturierte Exportausgabe nicht erweitert | Code triage_work_queue | Exportformat-Entscheidung | – |
| E05 | TU | Regressionen (1)–(10) für Mail/Reddit abgedeckt soweit lokal möglich | Hub-Tests P6 | Live | – |
| E06 | TU | Fehlerstatus sichtbar, Reddit-UA, optional OAuth, Kommentarbudget je Thread | hub 1206762 | Live-Ursache (Netz gesperrt), Reddit-App-Credentials | Credentials setzen, Quellenstatus lesen |
| E07 | TU | Pfad verifiziert; Ursache Owner-Filter behoben nach Entscheidung „zulassen“ (eigene Issues = To-do, Migration für bereits verworfene) | hub 3e7c697; tests/test_owner_github_issues_20261016.py; 428 Hub-Tests, 7 Gates grün | Live-Abgleich nach Deploy | Hub deployen, To-do-Liste mit GitHub vergleichen |
| E08 | UV | Anker (Raum + Abstand) je Karteninstanz; Navigation reproduzierbar getestet | dev 7d99fb2; frontend_tests/e08-scroll.spec.mjs (Anker-Test rot am Ausgangsstand), CI WebKit/Firefox grün | echte iOS-App | – |
| E09 | UV | Slot 00:30–06:00 HA-Lokalzeit, Sekunde, Timer, Nachholung/Retry nachts, Retry-After | dev a21d74a; test_arbeitsauftrag_20261014_nightly_uploads.py | Hub-Lastmessung | Hub-Metriken vorher/nachher vergleichen |

## Historische Restwünsche (H01–H42, Reihenfolge des Inventars)
| ID | Quelle | Status | Kurzbewertung |
|---|---|---|---|
| H01 | C2/5; S45–47 CO₂ in Entscheidung | BV | vorhanden, P1 |
| H02 | C7 Feuchtequellen | BV | vorhanden |
| H03 | C9 Raum-Betriebsmodus | VO | Prioritäten vorhanden, unabhängiger Modus nicht belegt |
| H04 | C15 klickbare Details | BV | P4 „Rooms button…“ grün |
| H05 | C18 Recorder-Attribute | BV | `recorder_exposed=false` |
| H06 | G#1 HA-Räume importieren | BV | Real-HA-Flow-Tests (Subentry + Optionen, echte Area/Floor/Device/Entity-Registries): `test_import_ha_room_builds_suggestions_and_creates_room`, `test_import_ha_rooms_with_entity_suggestions` |
| H07 | G#3 Raum erstellen/NameError | BV | Raumanlage über Subentry- und Optionen-Assistent in echtem HA ohne Fehler (`test_create_room_wizard_goals_references_back_and_commit`, `test_add_room_full_wizard_with_goals_and_contact_references`); neuer Raum bekommt Entities (A-19) |
| H08 | S3/10 kontaktlose Räume | BV | indirekter Pfad + F09/F10 |
| H09 | G#4 Dashboard-Ansicht | BV | historisch bestätigt |
| H10 | G#5 Querlüftung verständlich | NU | wie F14 |
| H11 | G#6 Diagnose-Senden | BV | Tests P1 |
| H12 | G#7 Drei-Zustands-Kontakte | BV | Tests P1 |
| H13 | G#8 Fenster offen+schließen | BV | via F02-Absicherung |
| H14 | G#9 PDF kompakt | BV | historisch bestätigt |
| H15 | Schrift/Theme Lesbarkeit | NU | F19/F22 |
| H16 | S18 Logo ausblenden | BV | Option vorhanden |
| H17 | Icon selbst wählen | BV | vorhanden |
| H18 | S22 Anwesenheit BLE | NZ | Nutzer bestätigte Lösung |
| H19 | S23 Multi-Sensor | BV | mean/median/min/max |
| H20 | S26 Notify-Ziele | BV | Entity-Erkennung vorhanden |
| H21 | S27 Testbenachrichtigung Platzierung | NU | UX-Wunsch offen |
| H22 | S39 Selektor-Filter | VO | Selektoren nativ |
| H23 | S39 Climate-Gruppe | VO | domain=climate |
| H24 | S52 E-Mail-Empfänger | BV | Versand bestätigt |
| H25 | S53 Mehrfachlüfter | BV | bestätigt; F03 separat |
| H26 | S33 Startup-Pushs | BV | Recovery-Grace |
| H27 | S36 Zieltemperatur | BV | Mehrzielmodell |
| H28 | S44 Diagnose Opt-in | BV | Consent-Gates; E09-Tests prüfen Opt-out |
| H29 | S54 Wizard-Sackgasse | BV | Zurück auf jeder Assistentenseite (Ziele, je Kontakt, Bearbeiten) und Rückfall ins Raummenü in echtem HA getestet (`test_cov_options_flow.py`, `test_cov_room_subentry_flow.py`) |
| H30 | S62 y-Achse Feuchtehistorie | NU | Wunsch offen |
| H31 | S72 Namen statt „Erwachsener 1“ | BV | historisch |
| H32 | S73 Icon→Fehler | BV | Raumicon speichern → Lüftungsprioritäten → Speichern ohne Fehler (`ha_tests/test_room_icon_goals_20261016.py`, echtes HA) |
| H33 | S74 „2,0 Personen“ | NU | kosmetischer Wunsch |
| H34 | S75 Raumkachel klickbar | BV | P4 |
| H35 | manual1 To-do-Entwurf | VO | Hub-Dashboard nicht geändert |
| H36 | manual4/5/6 eigene Antworten | BV | Owner-Filter (s. A-14) |
| H37 | manual7 To-dos verschwinden | VO | live |
| H38 | manual8 Feedbacksperre | BV | F29 |
| H39 | manual9 Fenster schließen | VO | live |
| H40 | guardian-comment2 Haustyp | BV | vorhanden |
| H41 | FAIQ-CONFIG-001 | NZ | Setupzustand 0.25.0.68 |
| H42 | HUB-SCHEMA-001 | BV | Schema 15 unterstützt (Hub-Test) |
