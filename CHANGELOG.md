## 0.25.0.75

## 0.25.0.76
- Added import of Home Assistant Areas and Floor assignments into FreshAirIQ room setup.
- Multiple HA areas can be selected and completed sequentially with FreshAirIQ-specific room data.
- Existing FreshAirIQ room names are excluded from import to prevent accidental duplicates.

- Added automatic English dashboard localization for non-German Home Assistant profiles.
- German dashboard behavior remains unchanged.
- No calculation, learning, diagnostics or scroll/navigation logic changed.


## 0.25.0.64
- Hotfix: freigegebene Dashboard-Einstellungen und Geräte-&-Dienste-Konfiguration durch verpflichtende UI-/Configuration-Contracts gegen unbeabsichtigte Regressionen geschützt.
- Keine Änderung der FreshAirIQ-Fachlogik.
# 0.25.0.60 – Learning Effectiveness Validation v1

- Führt eine gepaarte Same-Session-Baseline ein, damit der reale Nutzen gelernter Forecast-Parameter unabhängig von wechselnden Start-/Wetterbedingungen messbar wird.
- Aggregiert Lernwirkung konservativ nach unabhängigen Lüftungen und verhindert Scheinsicherheit durch gleichzeitig gelüftete Räume.
- Zeigt Lernwirkung, gelerntes/Grundmodell-MAE, Evidenzstatus und 95-%-Intervall im Dashboard und Diagnoseexport.
- Segmentiert die Auswertung nach Raum, Horizont, Jahreszeit, Quelltemperatur, AH-Differenz und Lernstufe.
- Vergleicht zusätzlich jede aktuelle Forecast-Generation mit dem neuesten abweichenden, zuvor real beobachteten Modell-Snapshot desselben Raums unter identischer aktueller Startlage und realer Messdauer.
- Ändert keinerlei produktive Lernparameter oder Lüftungsentscheidungen; die Funktion ist ausschließlich beobachtend.
- Ergänzt umfassende Regressionstests und hält die Pure-Logic-Coverage bei 100 %.

# 0.25.0.54 – Production Incident Replay Foundation

- Erweitert datenschutzminimierte Sensor-Incidents um einen versionierten, identitätsfreien Replay-Snapshot.
- Speichert nur aggregierte Entscheidungsinputs: Anzahl gültiger Räume, Sensor-Qualitätsklassen/-anzahlen und Außenluft-Qualitätsstatus.
- Ergänzt einen deterministischen Replay-Runner, der die bestehende produktive `build_recommendation()`-Engine ausführt statt Entscheidungslogik zu duplizieren.
- Regressionstests belegen, dass vollständige Sensor-Ausfälle `sensor_error` reproduzieren, gemischte gültige/ungültige Zustände aber keinen falschen Haus-Sensorfehler erzeugen.
- Keine Raum-Namen, Raum-Schlüssel, Entity-IDs oder Freitexte werden dem Replay-Snapshot hinzugefügt.

# 0.25.0.49 – Sensorless Room Creation Hotfix

- Räume können jetzt zunächst nur mit Name und Raumvolumen angelegt werden, auch wenn noch keine Sensoren installiert sind.
- Vollständig sensorlose Räume werden sicher mit deaktivierter Berechnung gespeichert, bis die erforderlichen Sensoren/Kontakte ergänzt wurden.
- Begonnene Sensorkonfigurationen behalten die bestehenden Vollständigkeitsprüfungen.
- Keine Änderungen an Entscheidungs-, Lern-, Diagnose-, Übersetzungs- oder Workflow-Logik.

# 0.25.0.48 – German Config Flow Completeness Hotfix

- Behebt rohe interne Feldnamen in Home Assistant Datenabschnitten (z. B. `adult_occupants`, `adult_presence_entities`).
- Übersetzt insbesondere Raum-, Sensor-, Bewohner-, Anwesenheits- und Expertenfelder in Geräte & Dienste vollständig ins Deutsche.
- Nutzt die aktuelle Home-Assistant-Struktur für Abschnittsübersetzungen (`section`) und behält eine kompatible Spiegelung für ältere Frontends.
- Jede deutsche Einstellung besitzt jetzt eine Erklärung sowie expliziten Standardwert und ein Beispiel.
- Keine Änderung an Lüftungs-, Prognose-, Lern- oder Decision-Intelligence-Logik.

# FreshAirIQ Changelog

## 0.25.0.48 – Release Asset & Changelog Hygiene Hotfix

- GitHub tag releases now download the exact CLEAN ZIP produced by the mandatory quality workflow, revalidate it with the GitHub/HACS ZIP gate and attach that verified archive to the GitHub release.
- Corrected the historically mislabelled `0.25.0.44 – Native Config, Scroll & Quality Hotfix` changelog entry so the later 0.25.0.45 locale correction is no longer contradictory.
- Removed redundant secondary `# Changelog` wrapper headings while preserving all historical release entries.
- No changes to ventilation physics, recommendation logic, forecasts, learning, diagnostics payload semantics or Decision Intelligence.

## 0.25.0.46 – Android Touch & Settings Contract Hardening Hotfix

- Android/WebView detail scrolling is now covered by a trusted touch-swipe E2E regression, not only mouse-wheel scrolling.
- Every native Config Flow option key is resolved through the canonical settings contract and fails fast on drift/typos.
- Added exact semantic regression coverage for all 92 native option keys.
- Release artifact folder/ZIP naming now matches v0.25.0.46.
- No changes to ventilation physics, recommendation logic, forecasts, learning or Decision Intelligence.

## 0.25.0.45 – Release, Scroll & Locale Hardening Hotfix

- Full Continuous Quality workflow is now a mandatory release dependency.
- Real detail-overlay scroll E2E regression added.
- English and German native Config Flow translations separated correctly.
- Room-add default and statistics-range labels corrected.
- Settings contract regression coverage strengthened.
- Stability runtime separated from hard correctness/memory checks; dedicated performance gate remains authoritative for speed.

## 0.25.0.44 — Native Config, Scroll & Quality Hotfix
- Monitor-only bzw. von Berechnungen ausgeschlossene Räume bleiben diagnostisch sichtbar, werden aber nicht mehr als Sensorqualitätsfehler gezählt.
- Detail-Unterfenster scrollen in Web/Home-Assistant-WebView wieder nativ vertikal; der blockierende `touch-action: none`-Ancestor wurde entfernt.
- Geräte-&-Dienste-Config-Flow vollständig deutsch dokumentiert, einschließlich Erklärungen, Standardwerten und Beispielen; der Flow bleibt auch bei englischer Frontend-Sprache deutsch.
- Dashboard-Zahnrad und nativer Options-Flow verwenden einen gemeinsamen kanonischen Einstellungsschlüssel-Vertrag und dieselbe ConfigEntry.
- Keine Änderung an Lüftungsphysik, Prognose-, Lern- oder Decision-Intelligence-Logik.

## 0.25.0.39 — Public Diagnostics Endpoint Hotfix
- Diagnostics Hub endpoint switched from private LAN staging to `https://diagnostics.freshairiq.com`.
- No ventilation/recommendation logic changes.


## 0.25.0.35 – Passive-Open UI Hotfix

- Behebt die widersprüchliche Hauptempfehlung bei erkannter Dauer-/Kippöffnung: `passive_open_monitor` wird im Decision Brain nicht mehr zu „Fenster geschlossen lassen“ umformuliert.
- Zeigt Dauer-/Kipplüftung als eigenen überwachten Zustand mit offenem-Fenster-Icon und klarer Handlungsempfehlung.
- Ersetzt im Daueröffnungsmodus die irreführende Anzeige „+X min über Ziel“ durch einen Monitoring-Status.
- Die bestehende Erkennungs-, Feuchte-, Temperatur-, Prognose- und Lernlogik bleibt unverändert.

## 0.25.0.34 – Maximum Hardening Hotfix

- Abschluss-Refresh bleibt optional: fehlende neue Rückmeldung verwirft keine ansonsten gültige Session.
- 10-s-Abschluss-Failsafe beendet Sessions auch bei tatsächlich `unavailable` gewordenen Klimasensoren deterministisch; letzter gültiger numerischer Zustand derselben Session wird nur als Verfügbarkeitsfallback verwendet und erzeugt keine neue Timestamp-Evidenz.
- Ist kein verwertbarer Session-Endzustand vorhanden, wird ohne erfundenen Feuchtewert und ohne physikalisches Lernen/Forecast-Kalibrierung abgeschlossen.
- Diagnostics-Privacy für kommagetrennte Bewohnernamen korrigiert; Versionsfelder werden nicht mehr irrtümlich als IPv4 geschwärzt.
- `resident_profile_count` zählt Bewohner korrekt.
- Android-WebView-Test prüft mit echtem Mobile-Viewport-Meta die tatsächliche CSS-Breite bei 360/412/600/800 px.
- Abschlussbenachrichtigung für nicht ausreichend gemessene Sessions enthält keinen synthetischen 0-ml-Erfolg.
- Keine Änderung an Timestamp-Gate, 0,75/1,0-Lerngewichtung, Feuchtephysik, Forecast-Formeln oder Diagnostics-HA-/Hub-Protokollschemas.

## 0.25.0.33 – Maximum Hardening Hotfix

- Corrected live IQ wording: before the strict temperature+humidity timestamp gate passes, the dashboard now states that the ventilation is being observed instead of falsely claiming active model learning.
- Measurement-based repeat/recommendation baselines are now written only for sessions that pass the strict in-session timestamp gate. Invalid sessions clear these baselines, preventing stale pre-ventilation climate values from influencing later anti-flap/recommendation decisions.
- Added semantic regression coverage for trusted/untrusted repeat baselines and live learning wording.
- Added a dedicated Android 15 / Home Assistant WebView-like Playwright target with mobile mode, touch input, high device-pixel ratio and 360/412/600/800 px viewport checks.
- Replaced stale staging-version labels with version-neutral wording while preserving Diagnostics HA / Diagnostics Hub transport contracts, endpoints, schemas and compatibility paths.
- No changes to ventilation physics, forecast formulas, thresholds, Diagnostics Hub protocol schemas or stored-data migrations.

## 0.25.0.32 – Safe Code Cleanup Hotfix

- Entfernt ausschließlich nachweislich ungenutzte private Schemahelfer und redundante lokale Variablen.
- Vereinfacht den bereits strikten Timestamp-Lerngate-Code ohne Verhaltensänderung.
- Schützt Diagnostics-HA-/Hub-Verträge mit einem eigenen Regressionstest; Transport-, Export-, Feedback-, Cursor- und Migrationspfade bleiben unverändert.
- Keine Änderung an Prognosephysik, Messqualitätsregeln, Abschlusswartephase, Lerngewichtung oder Diagnose-Schemas.

## 0.25.0.31 – Finalisation Evidence Consistency Hotfix

- Abschlussanzeige ist jetzt im realen Pending-Zustand erreichbar, ohne laufende Räume zu verdecken.
- Physischer Schließzeitpunkt wird bereits während der 3-s-Bestätigung eingefroren; Meldungen danach zählen nicht mehr fälschlich als In-Session-Evidenz.
- Klimameldungen innerhalb der 3-s-Bestätigung werden als gültige Abschlussrückmeldung erkannt.
- Nicht belastbare Feuchtemessungen werden als unbekannt statt als 0 ml gespeichert/angezeigt und fließen nicht in Feuchtestatistik, Prognosekalibrierung oder Post-Close-Lernen ein.
- „LERNT JETZT“ folgt nun dem strikten Timestamp-Gate statt dem Legacy-Measurement-Frame-Gate.
- 0,75-Qualitätsproben erhöhen die Lernreife nur mit 0,75 Evidenz; Teil-Evidenz wird persistent gesammelt.
- Laufende Sessions behalten Opening-Timestamps auch bei einem manuellen Lernreset.
- Diagnoseexport erweitert um Timestamp-/Evidenzfelder.

## 0.25.0.30

- Strikter Timestamp-Lerngate-Hotfix: Temperatur **und** Luftfeuchtigkeit müssen während der konkreten Lüftung jeweils mindestens einen neueren Sensorbericht liefern, bevor physikalisches Lernen oder Prognosekalibrierung freigegeben wird.
- Vor der Lüftung gehaltene Werte können die Lernfreigabe nicht mehr über alte Measurement-Frame-Klassen umgehen.
- Post-Close-Refresh bleibt reine Abschlussverbesserung und kann fehlende In-Session-Aktivität nicht rückwirkend ersetzen.
- Start-/End-Zeitstempel der Raumklimasensoren werden als Diagnoseevidenz gespeichert.
- `good`-Messqualität bleibt auf 0,75 Lerngewicht begrenzt und wird nicht mehr durch ältere Frame-Qualität auf 1,0 hochgestuft.
- Keine Änderung an Feuchtephysik, Forecast-Formeln, Grenzwerten, Prioritäten oder der 0.25.0.29-Abschlusswarte-UX.

## 0.25.0.29

- Messqualitäts-Hotfix für niedrig sendende Batterie-/Push-Klimasensoren: mindestens zwei reale Raumklima-Meldungen während einer Lüftung ersetzen die bisher zu starre Altersbewertung als Session-Vertrauenssignal.
- Best-Effort-Refresh beim Lüftungsstart und nach bestätigtem letzten Schließen mit ausschließlich bereits konfigurierten Sensorentitäten; keine neuen Nutzerfelder.
- Bestehende 3-s-Schließbestätigung plus maximal 10 s Abschlussmessungs-Gnadenfrist; frühes Ende sobald Temperatur und Feuchte frisch zurückgemeldet wurden.
- Dashboard zeigt währenddessen „Warte kurz auf die Klimasensoren“; die physische Lüftungsdauer endet weiterhin am echten Kontaktschließzeitpunkt.
- Öffnungsspezifische Referenzsensoren reagieren live; Reopen während der Gnadenfrist setzt dieselbe Session fort.
- Lüftungsphysik, Forecast-Koeffizienten, Grenzwerte und Prioritäten unverändert.

## 0.25.0.25

- Local Hub Staging Connection für `http://192.168.178.150`; weiterhin standardmäßig deaktiviert und nur nach explizitem Diagnose-Opt-in aktiv.
- Hub-v0.3-Vertrag vollständig angebunden: idempotentes `/v1/enroll`, persistente lokale Client-Credential, Bearer-authentifizierte `/v1/diagnostics/chunks` und einmalige Re-Enrollment-Recovery nach HTTP 401.
- Unsicheres HTTP wird ausschließlich für private/Loopback-IP-Adressen akzeptiert; ein späterer öffentlicher Hub benötigt HTTPS.
- Daily/Weekly-Erstsynchronisation startet nach Opt-in sofort; bestehende Cursor-, Chunk-, Privacy- und Performance-Härtung bleibt erhalten.
- Manueller Diagnosedatei-Export und Lüftungs-/Forecast-/Learning-Fachlogik unverändert.

## 0.25.0.24
- Transport-Performance-Hotfix: CPU-intensive Datenschutz-/Chunk-Aufbereitung und JSON/GZIP-Kompression des optionalen Diagnostics-Clients werden aus dem Home-Assistant-Event-Loop ausgelagert.
- Chunk-Partitionierung von wiederholtem Kandidaten-Rebuild auf lineare Byte-Gewichtung umgestellt; reale 459-Record-Diagnose lokal von ca. 16,96 s auf ca. 5,0 s reduziert.
- Redundante Deepcopies und Record-Rehashing im Transportpfad reduziert.
- Manueller Diagnoseexport, Lüftungsphysik, Forecast, Lernen, Empfehlungen und Dashboard-Fachlogik unverändert; produktiver Hub-Endpunkt weiterhin leer.

## 0.25.0.23
- Diagnostics Client Hardening: automatische Hub-Übertragung nutzt Transport-Schema v2 mit Chunking, inkrementellem Cursor, Resume und Record-/Chunk-Deduplizierungs-IDs.
- Der automatische Client verwirft keine Historie mehr über das frühere 240-Record-Limit; übertragen werden alle Datensätze, die auch im normalen 30-Tage-Diagnoseexport enthalten sind, nach lokaler Datenschutzfilterung.
- Manueller Diagnosedatei-Export unverändert; produktiver Hub-Endpunkt weiterhin absichtlich leer.
- Keine Änderung an Lüftungsphysik, Forecast, Lernlogik, Prioritäten oder Empfehlungen.

## 0.25.0.22
- Diagnostics Client Foundation: lokales Opt-in, Privacy-Minimierung, Pseudonymisierung, deterministische Uploadplanung, Retry/Backoff und Hub-Status.
- Kein produktiver Hub-Endpunkt in dieser Version; somit keine externe Übertragung.
- Keine Änderung an Lüftungs-, Prognose- oder Lernlogik.

## 0.25.0.21

- Continuous Quality System eingeführt: Korrektheit, Robustheit, Stabilität, Kompatibilität, Performance und Release-Hygiene werden automatisiert geprüft.
- Maschinenlesbare Quality-Policy und normalisierte Performance-Baseline ergänzt.
- 3.000-Zyklen-Stabilitäts-Stresstest mit Memory-/Runtime-Grenzen ergänzt.
- Python-3.13/3.14- und Home-Assistant-2026.8/2026.9-Kompatibilitätsmatrix sowie wöchentlicher HA-Edge-Watch ergänzt.
- Playwright-Browser-Smoke für Chromium, WebKit und Firefox mit iPhone-, iPad-, Android- und Desktop-Viewports ergänzt.
- Clean-Release-Builder erzeugt ZIPs nur aus einer bereinigten Staging-Struktur und blockiert Cache-/Dev-Artefakte.
- Lokale Regression: **646/646 Tests**, Pure-Logic-Coverage **100,00 % = 4.947/4.947 Statements**.
- Keine beabsichtigte Änderung an Lüftungsphysik, Forecast, Learning, Empfehlungen oder Dashboard-Fachlogik.

## 0.25.0.13

- Frontend performance hotfix: persistentes Karten-CSS statt erneutem CSS-Parsing bei jedem Render.
- Live-Dialoge deduplizieren unveränderte HA-State-Snapshots und identisches HTML vor dem DOM-Patch.
- Aktuelle FreshAirIQ-Controls nutzen den vorhandenen relevanten Entity-Index; Legacy-Fallbacks bleiben erhalten.
- SVG-Historien und Lernkomponenten-HTML werden referenzbasiert wiederverwendet.
- Keine Änderung an Lüftungslogik, Prognosen, Lernen oder Backend-Berechnungen.

## 0.25.0.12
- Frontend-Registrierung wieder auf genau einen aktiven Ladeweg begrenzt: Storage-Lovelace nutzt ausschließlich die verwaltete `freshairiq-card.js`-Resource.
- `add_extra_js_url` dient nur noch als Fallback für YAML-/Legacy-Modus oder fehlgeschlagene Storage-Registrierung.
- Bereinigung alter `freshairiq-loader.js`- und doppelter FreshAirIQ-Lovelace-Ressourcen bleibt erhalten.
- Keine Änderungen an Lüftungs-, Prognose-, Lern-, Sensor- oder Dashboard-Fachlogik.

## 0.25.0.11
- Pure-Logic-Coverage wieder auf **100,00 % (4.773/4.773 Statements)** gebracht.
- Drei bislang ungetestete Diagnose-/Invalidierungszweige in `forecast_validation.py` mit gezielten Regressionstests abgedeckt; keine Produktionslogik geändert.
- Das GitHub-CI-Gate erzwingt nun tatsächlich `--cov-fail-under=100` und stimmt damit wieder mit `.coveragerc-pure` und `QUALITY_GATES_1.0.md` überein.
- Keine Änderung an Lüftungsphysik, Forecast-Berechnung, Sensorbewertung, Lernlogik, Empfehlungen oder Dashboard-Verhalten.

## 0.25.0.10
- Hotfix: Haus- und Etagenlüftung dürfen eine Schließempfehlung erst erzeugen, wenn für alle betroffenen aktiven Räume `close_decision_ready` freigegeben ist.
- Die bestehende 2-Messwerte-/15-Minuten-Logik gilt damit jetzt auch für die nachgelagerte Aggregation, die zuvor nach der finalen Konsolidierung noch eigenständig `close` setzen konnte.
- Vor Freigabe bleibt die Empfehlung auf Weiterlüften; eine eventuell geerbte Restzeit von `0 min` wird dabei entfernt.
- Keine Änderung an Lüftungsphysik, Schwellen, Forecast-Formeln, Lernlogik oder Batteriesensor-Gewichtung.

## 0.25.0.9
- Hotfix: `held`-Messrahmen von langsam meldenden Batterie-Klimasensoren dürfen wieder mit 35 % Gewicht ins adaptive Prognose-Lernfeedback einfließen.
- Die objektive Prognosegenauigkeit bleibt streng auf `excellent`/`acceptable` begrenzt; `uncertain` und `stale` bleiben vom Prognoselernen ausgeschlossen.
- Dashboard-Texte unterscheiden jetzt zwischen strenger Genauigkeitswertung und vorsichtigem Lernfeedback.


## 0.25.0.3
- Deutsche Etagenbezeichnungen in laufenden Etagenempfehlungen.
- Haus-Lüftungsschwelle direkt über die Detail-Kachel einstellbar.
- Optionale individuelle Raum-Lüftungsgrenzen: automatisch, Prozent der Raum-Wassermenge oder fester mL-Wert.
- Sicherheits-/Gesundheitsprioritäten bleiben von benutzerdefinierten Schwellen unberührt.

## 0.25.0.1

- Hotfix ausschließlich für Diagnose-/Feldtest-Nachweisführung; keine beabsichtigte Änderung an Lüftungsphysik, Forecast, Learning, Prioritäten oder Empfehlungen.
- Diagnose-Schema 10 mit stabiler anonymer Installations-ID, pseudonymen Client-IDs, Export-ID/-Sequenz sowie Home-Assistant-, Plattform-, OS-, App-/Browser-/WebView- und Frontend-Versionen.
- Privacy-sicherer Konfigurations-/Raum-Snapshot, Konfigurations- und Versionshistorien sowie Langzeitmetriken (Zeitraum, erfasste Kalendertage, längste Tagesserie, Sampling-Lücken).
- SHA-256-Fingerprint der Records zur Erkennung von Beschädigung/Duplikaten; keine kryptografische Echtheits-Signatur.
- Exportierendes Dashboard registriert seine Client-Metadaten vor dem Download; iOS-Hardwaremodell bleibt auf die vom WebView tatsächlich offengelegte Gerätefamilie begrenzt.
- Abschlussprüfung: **576/576** lokale Pure-Logic-/Regressionstests grün; Pure-Logic-Coverage weiterhin **100,00 % = 4.744/4.744 Statements**; Python-/Frontend-Syntax grün.
- Reale HA-Runtime-Suite bleibt in der lokalen Umgebung mangels installiertem `homeassistant`-Paket unverifiziert und ist weiterhin CI-/v1-Gate.

## 0.25.0.0

- Release-Hardening / Feature Freeze auf dem Weg zu 1.0; keine beabsichtigte Änderung an Lüftungsphysik, Forecast-Koeffizienten, Lernraten, Entscheidungsgrenzen oder Dashboard-Verhalten.
- Pure-Logic-Regressionssuite auf **569 Tests** und **100,00 % Line-Coverage (4.744/4.744 Statements)** gebracht.
- Pure-Logic-CI-Gate von 95 % auf **100 %** angehoben.
- Kanonischen realen Home-Assistant-Coverage-Pfad gehärtet: kombinierter Bericht aus Pure Logic + HA-Runtime, v1-Floor **≥99 % gesamt**, **≥98 % je Python-Modul**, **100 % `config_flow.py`**, fehlende Module sind ein harter Fehler.
- Drei nachweislich unerreichbare Schutzbranches entfernt statt Coverage-Ausnahmen einzuführen; kein beabsichtigter Runtime-Verhaltenswechsel.
- Reale HA-Runtime-Coverage, Strict Typing gegen echten HA-Typbestand, Browser-E2E und Fremdhaushalt-Beta bleiben vor 1.0 offene Gates.

## 0.24.14.1

- Hotfix: Startprognosen werden auf die tatsächliche Messdauer derselben Lüftung abgeglichen, ohne Endmesswerte als Prognoseeingang zu verwenden.
- Hotfix: langsam meldende Sensoren verhindern die Startprognose nicht mehr; strenge Qualitätsgrenzen für Modelllernen bleiben bestehen.
- Hotfix: veraltete doppelte Einstellungsrouten leiten auf die kanonischen Einstellungsbereiche weiter.
- Abschlussprüfung: 523/523 Pure-Logic-/Regressionstests bestanden; Pure-Logic-Coverage 95,06 %.

## 0.24.14.0
- FreshAirIQ can be installed without creating a room or selecting an outdoor source up front; manual outdoor temperature/humidity remains pair-validated.
- Added explicit global enable/disable controls for optional VOC/TVOC, PM2.5 and illuminance inputs in both Devices & Services and the dashboard settings.
- Clarified throughout the German UI that these optional sensors do not alter canonical ventilation physics, ml forecasts or learning, but may enrich supplemental recommendations and future diagnostics.
- Consolidated resident/presence/personalisation settings and removed duplicated normal-navigation entries while keeping compatibility flow handlers; native grouped forms have section icons where supported.
- Added the same global VOC/TVOC, PM2.5 and illuminance enable/disable controls to the general dashboard-card editor, plus independent per-card visibility controls.
- Diagnostics schema 9 now exports optional-sensor values, availability, enabled/configured state and 30-day trend data plus configuration capability counts.
- No intended change to ventilation physics, forecast coefficients, learning rates or canonical recommendation thresholds.
- Final local regression: 514/514; isolated pure-logic coverage 95.06%.

## 0.24.13.0
- Verification-only release; no ventilation physics, learning or dashboard behaviour changed.
- Expanded real-HA flow coverage across all main options sections/leaves, room administration, native room subentry creation and duplicate-room recovery.
- HA-runtime CI now writes machine-readable coverage JSON, publishes total + `config_flow.py` coverage in the job summary and uploads the raw report as an artifact.
- Added a local regression contract for the HA coverage measurement pipeline.
- Local regression: 509/509; pure-logic coverage remains 95.06%.

## 0.24.12.0
- Verification-focused release; no ventilation physics, learning or dashboard behaviour changed.
- Hardened all contact-delay editing paths against corrupt persisted values via `_safe_int()` and consistent 0–600 s bounds.
- Expanded real-HA flow tests for legacy import, reference-pair recovery, outdoor-options recovery, statistics persistence and reset-defaults.
- Added a local regression contract preventing unsafe raw `int()` conversion of delay persistence.
- Local regression: 507/507; pure-logic coverage remains above the 95% gate.

## 0.24.11.0

- Made `ConfigEntry.runtime_data` the single coordinator runtime source and removed the legacy `hass.data[DOMAIN]` mirror/fallbacks.
- Added a shared typed `FreshAirIQConfigEntry` contract and propagated it through integration lifecycle, coordinator, Repairs, entity base/platforms and Settings API.
- Completed function-signature annotations for the migrated HA-facing core and added a packaged `py.typed` marker.
- Added local typing-contract regression checks and expanded real-HA import smoke coverage to all entity platforms and the typing module.
- Kept `strict-typing` honestly open until Config Flow/remaining edge modules are typed and an actual mypy strict gate passes.
- Local regression: 506/506; isolated pure-logic coverage: 95.06%.

## 0.24.10.0

- HA entity-quality pass: RoomSensor availability now includes coordinator health.
- Added native sensor device classes for humidity, absolute humidity, duration, absolute temperature and temperature deltas.
- Added one-shot INFO logging for required source loss and recovery.
- Moved static entity icons to Home Assistant `icons.json` icon translations.
- Low-value learning diagnostic entities are disabled by default for new registry entries only; existing user choices are preserved.
- Extended HA runtime tests for setup rollback, repair-failure isolation, availability transitions and entity metadata.

## 0.24.9.0

- Added native Home Assistant Repair issues for required configured entities that were actually removed; transient unavailable/unknown states do not create Repairs.
- Repair issues clear automatically after recovery and on successful unload, while Repairs subsystem failures cannot break the FreshAirIQ coordinator.
- Completed the configuration-entity category audit: number/select/reset-button controls use `EntityCategory.CONFIG`.
- Added translation keys for all FreshAirIQ number controls and supplied German/English entity names.
- Added an explicit Home Assistant entity compatibility matrix to the README.
- Added HA-runtime CI tests for Repair detection/recovery and entity metadata; local pure-logic regression remains 503/503 at 95.07% coverage.

## 0.24.8.0

- Fixed transactional config-entry unloading: listeners/runtime are preserved when a Home Assistant platform refuses to unload.
- Switched runtime consumers to prefer `ConfigEntry.runtime_data` while retaining a compatibility alias for older internal callers.
- Converted intervention/select/button action failures to native translatable `ServiceValidationError` / `HomeAssistantError`.
- Hardened v7→v8 migration against malformed room containers/rows, corrupt contact delays and invalid legacy threshold values.
- Added real-HA lifecycle, platform-action and migration robustness tests to the HA-runtime CI suite.
- Pure-logic gate remains >=95%; 503 local tests pass at 95.07% measured coverage.

## 0.24.7.0

- Added a native Home Assistant reconfigure flow for the fundamental outdoor-air source; learned data and room configuration are preserved.
- Added real Home Assistant config-flow tests (initial validation, full happy path, duplicate prevention and reconfigure) using the custom-component HA test framework in CI.
- Split current-runtime HA tests from a minimum-supported-2026.8 import compatibility job.
- Hardened config-flow rendering against corrupt/non-finite persisted sort orders, contact delays and statistics-day values.
- Hardened the optional Intervention Engine against NaN/Infinity sensor values.
- Added an honest `quality_scale.yaml` roadmap and expanded removal, action, troubleshooting and known-limitations documentation.
- Pure-logic release gate remains >=95%; 501 local regression tests pass at 95.05% measured coverage.

## 0.24.6.0

- Quality milestone: 498 tests and a correctly isolated **95.09% pure-logic coverage** gate.
- CI coverage split into Pure Logic (`>=95%` hard gate) and a separate Home Assistant runtime baseline/smoke path.
- Fixed the previous coverage-wiring defect that mixed unexecuted HA runtime modules into the claimed pure-logic threshold.
- Hardened Anticipation, Decision Engine, Language Confidence and Live Coach against non-finite values and expanded branch regression around decision simulation and runtime fallback handling.

## 0.24.4.0

- Numerische Robustheit in Recommendation, Personal Context, Ventilation Result und Diagnostics.
- Nicht-finite Werte werden defensiv normalisiert und können zentrale Entscheidungspfade nicht mehr abbrechen.
- Zusätzliche Regression für Feuchtequellen, Pollen, CO₂, Querlüftung, Nachtvorbereitung und Abschlussfeedback.
- Pure-Logic-Coverage auf rund 92,9 % erhöht; CI-Floor auf 92 %.

## 0.24.4.0
- Pure-Logic-Coverage-Gate auf 90 % angehoben; 422 Tests, gemessen 90,01 %.
- Settings API tief getestet (92 %) und gegen beschädigte Legacy-Raumsortierung gehärtet.
- Notification-Orchestrierung tief getestet (97 %) und gegen NaN/inf, malformed Sessions/Payloads sowie ungültige Nachtprognosen gehärtet.
- Planner/Decision Brain auf 95 %/92 % Coverage erweitert; Warte-, Nacht-, Querlüftungs- und Vergleichspfade abgesichert.
- Post-Close-Stabilisierung auf 99 % Coverage; Legacy naive Zeitstempel und beschädigte Persistenzwerte brechen die Nachlaufanalyse nicht mehr.
- Keine absichtliche Änderung an kanonischer Lüftungsphysik oder Lernkoeffizienten.

## 0.24.2.0
- Qualitäts-/Hardening-Release: Pure-Logic-Coverage auf 83,85 % erhöht (vergleichbare 0.24.1.0-Baseline 74,5 %); 397 lokale Tests.
- Routine-, Saison-, Bewohnerstrategie- und Hausstrategie-Lernen gegen beschädigte Persistenz sowie NaN/inf gehärtet.
- Benachrichtigungsrouting/Cooldowns gegen ungültige Profile und Legacy-Zeitstempel gehärtet.
- Storage-Reset-Verträge und Historien-/Wasser-/Temperaturpfade deutlich breiter getestet und defensiver gemacht.
- Separater Home-Assistant-Runtime-Smoke in CI für Config Flow, Coordinator, Sensoren, Diagnostics, Settings API und Storage.
- CI-Coverage-Floor eingeführt, damit Testtiefe nicht unbemerkt zurückfällt.

## 0.24.1.0

- Start der 1.0-Robustheits-/Coverage-Härtung.
- Settings-API-NameError beim Dashboard-Raumupdate behoben.
- Storage gegen korrupte Datums-/Messwerte und NaN/inf abgesichert.
- Langzeitaggregate 730 Tage; Dashboard-Statistikzeitraum bis 365 Tage.
- Neue gezielte Tests für Storage, Weather-Future und Settings-API; 363 Tests grün, Coverage 48 %.

## 0.24.0.0

- Added optional room-climate sensors (VOC/TVOC, PM2.5, illuminance).
- Added optional covers, HVAC, exhaust/supply/HRV, dehumidifier, humidifier and air-purifier targets.
- Added a non-invasive intervention engine that ranks extra measures without modifying canonical ventilation physics or learning.
- Added explicit `freshairiq.execute_intervention` action; no background actuation.
- Added native + dashboard configuration and tunable intervention thresholds.
- Added CI quality gates and dedicated intervention regression tests.

## 0.23.0.11

- Hotfix: mixed-source running ventilation can keep a useful opening open while closing a harmful local-reference opening instead of presenting a blanket room close.
- Hotfix: unavailable/incomplete configured contact references fail closed and never masquerade as outside air.
- Hotfix: removed duplicate wind/orientation weighting from opening ranking.
- Added focused regression tests for all three cases.

## 0.23.0.10

- Hotfix: Öffnungsbezogene Referenzluft wird pro Fenster/Tür separat bewertet.
- Empfehlungen nennen bevorzugte bzw. ungünstige Öffnungen direkt.
- Lokale Referenzluft bleibt während einer laufenden Lüftung auch in der 15-Minuten-Bewertung lokal; kein Wechsel auf Außenwetter.
- Bestehende Raum-, Haus-, Lern- und Prognosekerne bleiben unverändert.

## 0.23.0.9

- Hotfix: robuste Referenzsensor-Auswahl auch für Sensoren ohne `device_class`, sofern ihre Einheit Temperatur bzw. Feuchte eindeutig kennzeichnet.
- Kontaktbezogene Temperatur-/Feuchte-Referenzen sind jetzt auch über Home Assistant **Geräte & Dienste** konfigurierbar.
- Ungespeicherte Raumformular-Werte werden bei Live-Refreshes nicht mehr überschrieben.
- Referenzsensoren pro Öffnung bleiben atomare Paare und veraltete Zuordnungen entfernter Kontakte werden bereinigt.
- Keine Änderungen an IQ, Lernen, Prognosen, Empfehlungen oder Lüftungsphysik.

## 0.23.0.8

- Replaced the generated FreshAirIQ dashboard content with a native Home Assistant `tile` launcher.
- The launcher navigates to `/freshairiq-safe`, avoiding Lovelace custom-card instantiation for the default dashboard path.
- Dashboard strategy compatibility is retained, but it now generates native content only.
- Legacy `custom:freshairiq-card` remains available for existing manual dashboards.
- No recommendation, forecast, learning, room, sensor or settings logic changed.

## 0.23.0.6

- Hotfix: generated FreshAirIQ dashboards now use a native `vertical-stack` as the top-level Lovelace card and nest `custom:freshairiq-card` inside it.
- Keeps the existing safe panel fallback and all FreshAirIQ intelligence/UI functionality unchanged.

## 0.23.0.5

- Hotfix: zusätzlicher sicherer Home-Assistant-Custom-Panel-Pfad `/freshairiq-safe`, der den aktuell fehleranfälligen Lovelace-Custom-Card-Resolver umgeht.

## 0.23.0.4
- Hotfix: FreshAirIQ-Frontend verwendet pro Start nur noch einen Registrierungsweg; Lovelace-Storage ist kanonisch, `add_extra_js_url` ausschließlich Fallback.

## 0.23.0.3

- Hotfix: hardens FreshAirIQ against Home Assistant's un-awaited custom-resource cold-load race.
- Registers the tiny versioned bootstrap via the global frontend loader before/alongside the storage-mode Lovelace resource.
- Keeps the same exact ES-module URL on both paths so browser module evaluation remains deduplicated.
- No recommendation, learning, room, forecast, settings, or dashboard-layout logic changed.

## 0.23.0.2
- Unified resident/profile/device settings into one dashboard configuration path without duplicating people and presence fields.
- Added/retained per-window and per-door reference temperature/humidity pairs and clarified fallback/reference-air behavior.
- Reassesses deliberate multi-room ventilation as floor ventilation and prevents stale single-room close wording.
- Hardened post-ventilation re-arming, removed user-facing raw decision scores, and expanded IQ-Aktiv learning status.
- Added conservative low-cadence battery-sensor learning while keeping objective forecast validation strict.
- Canonical room sorting now propagates through coordinator payload, settings API and dashboard views.
- Mitigates Home Assistant custom-resource cold-load Configuration Error races by registering public card/editor/strategy elements immediately and using exactly one frontend resource path.

# 0.23.0.1

- Korrekturen für Referenzluft je Öffnung, Etagenlüftung, Lernmessungen, Wiederholungsempfehlungen, IQ-Aktiv-Anzeige und globale Raumreihenfolge.

# 0.23.0.0

- Learning 3.0: Shadow-Modelle, evidenzbasierte Promotion und automatischer Rollback für die Feuchte-Prognosekalibrierung.

## 0.22.1.0

### Fault Injection & Behavioural Hardening
- Reject non-finite sensor and weather values at runtime boundaries.
- Guard forecast interpolation against malformed/non-finite cached provider rows.
- Reject implausible future sensor timestamps from learning/validation.
- Harden persisted active ventilation sessions against corrupt runtime values.
- Add behavioural fault-injection regression coverage for restart and sensor failure scenarios.

## 0.22.0.0

- Robustness Foundation: Coordinator-Fehler werden kontrolliert als `UpdateFailed` behandelt, ohne letzte gültige Daten zu verwerfen.
- Runtime-Robustness-Monitor ergänzt Update-/Fehlerzähler, Event-Coalescing, Listener- und Wetter-Fetch-Status ohne personenbezogene Messwerte.
- Persistierte adaptive Kernwerte werden gegen `NaN`, `inf`, falsche Datentypen und physikalisch unmögliche Werte gehärtet.
- Einzelne beschädigte Raumkonfigurationen werden isoliert, statt die gesamte Hausberechnung zu Fall zu bringen.
- Numerische Optionen erhalten eine defensive zweite Validierung für beschädigte oder hand-editierte Storage-Werte.
- Runtime-Daten nutzen bevorzugt `ConfigEntry.runtime_data`; `hass.data` bleibt als Kompatibilitätsalias erhalten.
- Teilweise fehlgeschlagenes Platform-Setup räumt Listener und Runtime-Daten sauber auf.
- Lüftungsphysik, Forecast-Gewichtung, Reifestufen, Empfehlungen und Sicherheitsgrenzen bleiben unverändert.

## 0.21.0.3

- Hotfix: zuverlässige FreshAirIQ-Kartenregistrierung auf frischen Home-Assistant-Installationen und neuen Endgeräten.
- Doppelte Absicherung über globale Frontend-Einbindung plus Lovelace-Storage-Ressource.
- Sichere Lazy-Load-Behandlung und versionsbasierte Aktualisierung vorhandener Ressourcen.
- Keine Änderungen an Berechnungs- oder Lernlogik.

## 0.21.0.2
- Hotfix: echte Sensorwerte bleiben auch bei „Nur anzeigen“ sichtbar, ohne in Berechnungen oder Lernen einzufließen.
- Raumdetails unterscheiden klar zwischen berechneten Räumen und reinen Monitoring-/Strukturräumen.
- Grundlagen-Icon auf kompatibles `mdi:home-outline` umgestellt.
- Bewohnerprofile als besonderes persönliches FreshAirIQ-Profil prominent hervorgehoben.

## 0.21.0.1

- Stability & Performance Hotfix: robuste Struktur-Räume, Wetter-Fallback/Retry, Event-Coalescing, reduzierte Persistenz-I/O, effizientere Diagnostik und zusätzliche iOS/WebView-CSS-Kompatibilität.
- Keine fachliche Prognose-, Lern-, Entscheidungs- oder Sicherheitslogik verändert.

## 0.20.4.4

- Bewohnerprofile erweitert: Räume können einzelnen Erwachsenen und Kindern zugeordnet werden.
- Pro Bewohner kann optional ein eigenes Temperaturempfinden hinterlegt werden.
- Personal Context Engine nutzt Raumzuordnungen ausschließlich für nachvollziehbare, persönliche Formulierungen; technische Entscheidung, Räume, Dauer, Prognose und Sicherheitsgrenzen bleiben unverändert.
- Kinder werden weiterhin nie direkt zu einer Handlung aufgefordert; ihre Raumzuordnung dient nur als Haushaltskontext.
- Datenschutz-Härtung der Diagnostik: personalisierte Namen und Freitexte werden aus exportierten Entscheidungsdaten entfernt.
- Dashboard erhält einen strukturierten Bewohnerprofil-Editor mit Raum-Mehrfachauswahl und Komfortprofil.

## 0.20.4.3

- Bewohnernamen können optional Erwachsenen und Kindern zugeordnet werden; die Reihenfolge folgt den konfigurierten Person-/Tracker-Entitäten.
- Die Personal Context Engine adressiert eine erwachsene Person nur dann namentlich, wenn sie als einzige erwachsene Person eindeutig zuhause erkannt wird. Bei ungetrackten Mitbewohnern wird bewusst nicht geraten.
- Kindernamen bleiben Kontextdaten und werden nicht für direkte Handlungsaufforderungen verwendet.
- Persönliche Ansprache wird sparsam vor allem bei konkreten Lüftungsstarts genutzt; Physik, Dauer, Räume, Sicherheitsgrenzen und Prognosen bleiben unverändert.
- Bewohnernamen bleiben lokal in der ConfigEntry-Konfiguration und werden nicht in die FreshAirIQ-Diagnostik exportiert.

## 0.20.4.2

- Language Confidence Layer v1: Empfehlungen passen ihre sprachliche Sicherheit an den tatsächlichen Lernfortschritt an.
- Modellreife und Situationssicherheit werden getrennt bewertet; ein gut gelerntes Modell bleibt bei ungewöhnlichen oder unsicheren Messsituationen bewusst vorsichtig.
- Die Schicht ist rein präsentativ und verändert weder Aktion, Räume, Dauer, Prognosewerte noch Sicherheitsgrenzen.
- Empfehlungen zeigen einen kompakten Lernstand mit Reife und Situationssicherheit in der Begründung.

## 0.20.4.1
- Die Detail-Kachel „Lernkomponenten“ zeigt jetzt vollständig alle aktuell adaptiven Lernmodelle mit eigenem Fortschritt.
- Neu sichtbar: Live-Prognosemodell (laufende Feuchte-/Temperaturkorrektur) und Persönlicher Kontext (Umsetzungs- und Lüftungsgewohnheiten).
- Jede Lernkomponente zeigt weiterhin Proben, Zielwert, Reifegrad, Status und eine verständliche Detailbeschreibung.
- Keine Prognose-, Entscheidungs- oder Lernlogik wurde verändert; ergänzt wurde ausschließlich die vollständige Transparenz der bereits vorhandenen Lernmodelle.

## 0.20.4.0
- UI: Die Kachel „BEI LÜFTUNG · <Horizont> MIN“ wird vor Lüftungsbeginn nicht mehr angezeigt.
- UI: Die IQ-Aktiv-Leiste zeigt den Prognosehorizont nur noch während einer aktiven Lüftung.
- Die interne Prognoseberechnung und die Live-Prognose während einer aktiven Lüftung bleiben unverändert.

## 0.20.3.7
- Performance-Hotfix: nicht-strukturelle Konfigurationsänderungen werden live angewendet, ohne den kompletten Config Entry neu zu laden.
- Prognosezeitraum/Betriebsmodus veröffentlichen ihre neue Auswahl sofort; die vollständige Neuberechnung läuft im Hintergrund.
- Außen-/Anwesenheitsquellen bauen bei Bedarf nur die Runtime-Listener neu auf.
- Vollständige Reloads bleiben auf strukturelle Raumänderungen begrenzt.

## 0.20.3.5

- Added Forecast Quality & Model Reliability v1 with separate magnitude accuracy, direction accuracy, calibration gap, evidence maturity and a guarded composite reliability score.
- Added room-level reliability summaries without changing live forecast physics or learning coefficients.
- Added a component-level learning-status model covering room physics, forecast feedback, routines, user strategy, night model, house strategy, validation and post-close stabilization.
- Added a new Learning Components card to the Details window, styled to match the existing FreshAirIQ dashboard and showing maturity, sample depth, status and component-specific context.
- Diagnostics/status transport now includes the component learning model and Backtest Engine v2 reliability output; diagnostics schema raised to 8.

## 0.20.3.4
- Added post-close stabilization tracking to measure hygroscopic moisture rebound for 10 minutes after ventilation.
- Stabilization observations are diagnostic-only and cannot yet alter forecast or learning coefficients.
- Added contamination/reopen/frame-quality guards and diagnostics schema 7.

## 0.20.3.3

- Measurement Frames v1: FreshAirIQ now records the report age and temporal skew of room temperature, relative humidity and reference-air inputs.
- Frames are classified as excellent (<=30 s), acceptable (<=90 s), uncertain (<=180 s) or stale, with sensor age included in the decision.
- Uncertain/stale frames remain usable for live display/forecasting when numeric data is valid, but are excluded from adaptive learning and forecast validation.
- Frozen start forecasts, live forecast timeline points and completed-session diagnostics now carry their measurement-frame quality.
- Diagnostics schema raised to 6 with frame age/skew fields for room-level and learning analysis.
- No forecast physics or learned coefficients were retuned in this release.

## 0.20.3.2
- Added Backtest Engine v1 on top of immutable Validation Engine forecast snapshots.
- Added model-quality breakdowns by forecast horizon, confidence, room and FreshAirIQ version.
- Added timeline replay curves showing how start and live forecasts converge toward measured outcomes.
- Added confidence calibration, P90 moisture error, largest-outlier diagnostics and guarded version-to-version comparisons.
- Backtesting remains read-only and cannot modify learning coefficients or live recommendations.
- Diagnostics schema raised to v5 and now includes backtest results.

## 0.20.3.0
- Added Validation Engine v1 with persistent 30-day objective forecast scoring.
- Validation only compares frozen start forecasts against observations with the same time basis.
- Added moisture MAE/RMSE/bias, direction accuracy, temperature MAE, close-time MAE and cost MAE, including room-level summaries.
- Validation remains isolated from adaptive learning and does not alter forecast coefficients.
- Diagnostics schema raised to v4 and now exports validation status.

## 0.20.2.6

- Hotfix: belastbarer Startprognose-vs.-Endmessung-Vergleich mit identischer Zeitbasis; inkonsistente Haus-5-Minuten-Anzeige korrigiert.

## 0.20.2.4

- Hotfix: geschlossene Räume können während einer laufenden Hauslüftung konservativ als „PASSIV MITGELÜFTET“ erkannt werden, wenn ihr eigener Feuchtesensor eine plausible Bewegung zur Lüftungsreferenz zeigt.
- Passive Feuchteänderungen werden mit ≈ und eigener Sicherheit als Schätzung gekennzeichnet und bewusst nicht zur Haus-Live-Bilanz addiert, um Doppelzählung zu vermeiden.
- Aktive, passive und geschlossene Räume sind in der Live-Feuchtebilanz optisch klar getrennt.

## 0.20.2.3

- Hotfix: Prognose-Sicherheit wird jetzt durch echte Raum-Lernreife und Outcome-Feedback begrenzt.
- Hotfix: prognostizierter Schließzeitpunkt respektiert die konfigurierte Maximaldauer minutengenau statt erst am nächsten 5-Minuten-Schritt.
- Erklärung der Prognose trennt physikalische Feuchte-/Temperaturprognose von Heizkostenmodell.
- Release-Paket wird ohne Python-/Pytest-Caches erstellt.

## 0.20.2.2
- Hotfix: Prognose zeigt den erwarteten effizienten Schließzeitpunkt innerhalb längerer Prognosefenster; keine Änderung an der autoritativen 5-Minuten-Echtzeit-Schließlogik.

## 0.20.2.1
- Hotfix: user-selected forecasts above 5 minutes now use a rolling 5-minute room-state simulation.
- Future outdoor temperature/absolute humidity from the configured weather entity is applied step-by-step when available.
- The established internal 5-minute control path remains unchanged.

## 0.20.2.0

- Adaptive Feuchtequellen, Cooldown, Nachtmodell-Plausibilität, Hauslüftungsmodus, Systemcheck und UI-Optimierungen.

# 0.20.1.5

- Hotfix: Details-Kopfzeile und scrollender Inhalt sind technisch getrennt. Nur der neue `.dialog-scroll`-Bereich scrollt; Inhalte können nicht mehr hinter/über die Kopfzeile laufen.
- Laufende Kurzzeitprognose nutzt nach genügend echten Sensormessungen zusätzlich den jüngsten gemessenen Feuchteabbau. Bei langen, real stagnierenden Lüftungen wird die theoretische Luftaustauschprognose dadurch stark zurückgenommen.
- Die 5-Minuten-Live-Coach-Prognose verwendet dieselbe vorsichtige Messwertkorrektur, sodass stagnierende Lüftungen nicht unnötig verlängert werden.
- IQ-Zeit zeigt nach Überschreiten der Zieldauer die tatsächlichen Minuten „über Ziel“ statt dauerhaft `+0 min`.
- Ergebnis-IQ erklärt jetzt, ob eine Prognoseabweichung regulär, vorsichtig oder nur minimal ins Lernmodell übernommen wurde. Große Ausreißer verändern das Modell nur minimal und müssen sich durch weitere Lüftungen bestätigen.
- Keine Änderung an Sensorzuordnung, Raumkonfiguration oder Sicherheitsgrenzen.

# 0.20.1.4

- Hotfix: Das große Details-Fenster scrollt jetzt in einem eigenen gekapselten Container; die feste Kopfzeile bleibt oben und Inhalte können nicht mehr über die Kopfzeile hinauslaufen.
- Lüftungsprognose transparenter: Die für Entscheidungen weiterhin sicher am Feuchteziel begrenzte Wirkung bleibt erhalten, zusätzlich wird bei Zielbegrenzung die tatsächlich horizonabhängige physische Luftaustauschwirkung ausgewiesen.
- Plattformkompatibilität des Frontends verbessert, insbesondere für ältere iPad-/WebView-Engines: Objekt-Spreads aus dem Laufzeitpfad entfernt, DOM-Collections kompatibel behandelt und Live-Patching von browserabhängigen DOM-Klassen entkoppelt.
- Keine Änderung an Sicherheits-, Lern- oder Lüftungsentscheidungslogik.

# 0.20.1.2

- Hotfix: Live-Werte in allen geöffneten Dashboard-Fenstern ohne vollständigen DOM-Neuaufbau.
- Scrollcontainer und Navigation bleiben während Live-Updates stabil; fokussierte Formulareingaben werden geschützt.

# 0.20.1.1

- Hotfix: Das große Details-Fenster verwendet jetzt dieselbe stabile Snapshot-Scrollstrategie wie die übrigen langen Detailfenster.
- Home-Assistant-State-Updates ersetzen den Details-DOM während des geöffneten Fensters nicht mehr; dadurch bleibt die Scrollposition auch in iOS-/Android-WebViews stabil.
- Interaktive Unterfenster (Betriebsprofil, Prognosezeitraum, Gäste) bleiben weiterhin live aktualisierbar.
- Keine Änderungen an Layout, Berechnungslogik, Datenmodell oder Funktionsumfang.

# 0.20.1.0

- Performance-Release ohne Funktions- oder Layoutänderungen.
- Dashboard rendert nicht mehr bei fremden Home-Assistant-State-Updates, sondern nur bei für FreshAirIQ relevanten Zustandsänderungen.
- Mehrere unmittelbar aufeinanderfolgende relevante Updates werden pro Browser-Frame zusammengefasst.
- Status-, Raum- und Steuerelement-Entitäten werden zwischengespeichert, statt bei jedem Render alle Home-Assistant-States erneut vollständig zu durchsuchen.
- Raum-Payload-Merge arbeitet nach der ersten Erkennung nur noch auf den FreshAirIQ-Raumentitäten.
- Prognosezeitraum und Betriebsprofil reagieren optimistisch sofort in der Oberfläche und synchronisieren anschließend mit Home Assistant.
- Bestehende Scroll-Snapshot-, Overlay-, Navigations- und Berechnungslogik bleibt unverändert.

# 0.20.0.2

- Hotfix: Detailfenster-Kopfzeile bleibt am tatsächlichen oberen Fensterrand fixiert.
- Entfernt die redundante Prognosezeitraum-Schnelleinstellung aus dem Details-Fenster.
- Letzte-Lüftung-Detailansicht zeigt keine irreführende weitere „Details“-Aktion mehr; die 5-Minuten-Ergebniskarte bleibt weiterhin öffnbar.
- Einzelraum-Detailansicht auf kleinen Displays verdichtet (zweispaltige Kennzahlen statt langer einspaltiger Liste).

# 0.20.0.1

- Hotfix: Querlüftung wird während jeder laufenden Raumsitzung zeitlich erfasst statt erst beim Schließen aus dem aktuellen Kontaktzustand abgeleitet. Teilweise Querlüftung fließt zeitgewichtet in Luftaustausch, Energie und Kosten ein.
- Hotfix: Hausweites Strategielernen wertet eine Mehrraum-Lüftung erst nach dem Schließen des letzten beteiligten Fensters als einen vollständigen Hausdurchlauf aus.
- Hotfix: Die Haus-Lüftungsdauer beginnt am ersten erkannten physischen Öffnungszeitpunkt und endet am tatsächlichen letzten Schließzeitpunkt; die 3-Sekunden-Schließbestätigung verlängert das Ergebnis nicht künstlich.
- Hotfix: Widersprüchliche Feuchte-, Differenz-, Dauer-, Schimmel- und CO₂-Grenzwerte werden in Geräte & Dienste und im Dashboard-Einstellungszentrum abgewiesen; ältere widersprüchliche Konfigurationen werden beim Laden sicher geordnet.
- Hotfix: Neu ausgewählte Fenster-/Türkontakte zeigen Ausrichtung und Öffnungsverzögerung im Dashboard sofort ohne Speichern/Neuöffnen.
- Englische Übersetzung vollständig bereinigt, Platzhalter zwischen Basis/Deutsch/Englisch vereinheitlicht und README auf den aktuellen Release-Stand gebracht.

# 0.20.0.0

- Neues FreshAirIQ-Einstellungszentrum direkt im Dashboard über ein Zahnrad im Details-Kopf.
- Dashboard-Einstellungen verwenden dieselben Config-Entry-Daten und Optionen wie „Geräte & Dienste“; kein zweiter Konfigurationsspeicher.
- Vollständige, thematisch gruppierte Konfiguration für Außenluft, Gebäude/Anwesenheit, Bereiche, Räume/Sensoren, Betriebsprofil, Prognose, Pollen/Wind, Querlüftung, Lüftungsmodell, Energie/Kosten, Benachrichtigungen, Statistik und Wartung.
- Deutsche Erklärungen, Standardwerte und Beispiele für komplexe Eingaben ergänzt.
- Fehlenden Status-Export für `ventilation_threshold_mode`, `presence_explanation`, `pets_in_household` und `house_strategy_samples` korrigiert.
- Deutsche Übersetzungsschlüssel vervollständigt.

# 0.19.4.0

- Dashboard-Karteneditor auf Informationspräferenzen umgestellt: Nutzer wählen Themen, FreshAirIQ entscheidet weiterhin situationsabhängig, wann sie eingeblendet werden.
- Präferenzen für Feuchte/Wasser, Temperatur, Lüftungszeit, Kurzzeitprognose, Nacht, Schimmel, Energie/Kosten, Pollen und Querlüftung.
- Darstellungsoptionen für Branding, Betriebsmodus-Badge und IQ-Aktiv/Analyseleiste; die Karte kann dadurch deutlich kompakter werden.
- Sicherheitsrelevante Hauptentscheidung und Begründungen bleiben unabhängig von Anzeigepräferenzen sichtbar.
- Alte Kartenoptionen werden automatisch auf die neuen Präferenzen übernommen; bestehende Dashboard-Konfigurationen bleiben kompatibel.
- Die 5-Minuten-Ergebnisansicht respektiert die Anzeigepräferenzen, während die bewusst geöffnete Detailauswertung vollständig bleibt.

# 0.19.3.1

- Hotfix: kompakte „Letzte Lüftung“-Kachel im Details-Fenster; vollständige Auswertung erst nach Antippen.
- Hotfix: 3-Sekunden-Schließbestätigung für aktive Lüftungssitzungen, inklusive Wiederöffnen ohne Sitzungsabbruch.

# 0.19.3.0

- Verständliche IQ-Erklärung: „Hausmittel“ durch „bisheriger Lüftungsdurchschnitt“ ersetzt.
- Neue zusammenhängende Haus-Lüftungssitzung: Ergebnisse werden vom ersten aktiven Lüftungsfenster bis zum Schließen des letzten Fensters gruppiert.
- Nach Abschluss wird das vollständige Lüftungsergebnis fünf Minuten lang prominent auf dem Dashboard angezeigt und danach automatisch wieder durch die normale IQ-Darstellung ersetzt.
- „Letzte Lüftung“ erhält einen dauerhaften, detaillierten Platz im Details-Fenster inklusive Raumaufteilung, Feuchtebilanz, Dauer, Temperatur, Heizkosten/Energie und Prognosevergleich.
- Letztes Lüftungsergebnis wird jetzt explizit über den Statussensor an das Dashboard transportiert.

# 0.19.2.1

- Hotfix: Zurück- und Schließen-Navigation bleibt in allen Dashboard-Detailfenstern beim Scrollen fest sichtbar.
- Einheitliche Position der Navigationsbuttons; Top-Level-Zurück führt zum Dashboard, verschachteltes Zurück zum vorherigen Fenster.
- Keine Änderung an Klima-, Prognose-, Lern- oder Empfehlungslogik.

# 0.19.2.0

- Interaktives IQ-Dashboard mit klickbaren Informationskacheln und erklärenden Detailansichten.
- Live-Feuchtebilanz und Schimmelrisiko jetzt raumweise drill-down-fähig.
- Einheitliche, iOS-stabile Overlay-/Scroll-Logik mit Navigationsverlauf und größeren Safe-Area-Bedienelementen.
- Raumdetails zur erklärenden Raum-Intelligenz-Ansicht erweitert.

# 0.19.1.1

- Hotfix: Schließempfehlung nicht mehr allein durch Ziel-RH/Schließdifferenz; relevanter kurzfristiger Feuchteertrag hält die Lüftung offen.
- Hotfix: kombinierter 5-Minuten-Restnutzen offener Räume verhindert verfrühte Haus-Schließempfehlungen; Maximaldauer und klar schlechte thermische Effizienz bleiben harte Schließgründe.
- Hotfix: „Jetzt schließen“ setzt die IQ-Restzeit konsistent auf 0 min.

# 0.19.1.0

- Einstellungen neu strukturiert: Zuhause & Räume, Lüftung & Empfehlungen, Benachrichtigungen & Energie, Daten & Lernen sowie Wartung.
- Alle deutschen Einstellungsseiten vollständig beschriftet und ausführlicher erklärt; dokumentierte Standardwerte stehen direkt an den Feldern bzw. in den Beschreibungen.
- Querlüftung in eine eigene, verständlich erklärte Seite ausgelagert, inklusive konkreter Eingabebeispiele und Anzeige der verfügbaren Raumschlüssel.
- Explizite „← Zurück“-Navigation in allen Einstellungsmenüs ergänzt. Home-Assistant-Formulare selbst unterstützen derzeit keinen integrationsseitig definierbaren nativen Zurück-Pfeil in der Kopfzeile.
- Bestätigte Einstellungsseiten werden sofort in Config-Entry/Options gespeichert und FreshAirIQ wird bei Änderungen neu geladen; „Fertig“ schließt nur noch den Dialog.
- Raum-Subentry-Änderungen werden nach jeder bestätigten Unterseite sofort gespeichert.
- Feuchtequellen (Dusche, Badewanne, Sauna) vollständig in deutschen Raum-Einstellungen dokumentiert.
- Erweiterte Modellparameter in verständliche Abschnitte gegliedert; keine Berechnungslogik oder Empfehlungsschwelle wurde inhaltlich verändert.

# 0.19.0.0

- Adaptive Feuchtequellen-Erkennung für Dusche, Badewanne und Sauna; Recommendation Engine trennt interne Feuchteproduktion von Lüftungswirkung.

## 0.18.2.4
- Hotfix: critical CO₂ is now an actionable ventilation priority; warn vs. critical semantics are consistent across room/coordinator/live-coach logic.
- Hotfix: minute-precise night-end calculation and consistent disabled night window when start equals end.
- Added regression coverage for CO₂/pollen priority and night-time edge cases.

## 0.18.2.3
- Hotfix: diagnostic learning keys, room-history fallback, stale status selection and safe dashboard control binding.


## 0.18.2.2
- Hotfix: preserve signed ventilation outcomes across statistics and learning.
- Hotfix: treat unavailable CO₂ as unavailable instead of 0 ppm across all decision layers.
- Hotfix: room statistics follow the configured 1–30 day period.
- Reduce duplicated dashboard state-history payload and cap diagnostic export memory use.

## 0.18.2.0
- Diagnose-Recorder v2: 30 Tage, Testakte, Datenqualität, Lüftungsereignisse, Empfehlungsbefolgung und erweiterter Modellkontext.

## 0.18.1.0
- Diagnose-/Test-Recorder mit anonymisiertem 14-Tage-Rolling-Log und Dashboard-Export ergänzt.
- Keine Änderung an Entscheidungs-, Prognose- oder Lernlogik.

## 0.18.0.4
- Hotfix: frei einstellbarer Prognosezeitraum wird nun in Recommendation Engine, Raum-Benachrichtigungen und Dashboard-Fallbacks konsistent verwendet; interne 5-Minuten-Schließchecks sind explizit als solche gekennzeichnet.
- Nachtlüftung simuliert nur noch konkret ausgewählte Räume mit konfigurierten Lüftungskontakten und nennt diese Räume in Empfehlung und Decision Brain.
- Regenphasen werden zeitlich ausgewertet; Vorlüften wird nur empfohlen, wenn vor dem prognostizierten Regen ein ausreichend trockenes und langes Zeitfenster verbleibt.
- Nachtprognose unterscheidet aktuellen Zustand, geschlossene Fenster und Wirkung der empfohlenen Strategie; Dashboard und Nachtbenachrichtigung zeigen keine vermischten Szenarien mehr.
- Nachtbeginn/-ende werden nun minutengenau verarbeitet (z. B. 22:30 bis 06:45).
- Geräte-, Status- und Frontend-Version sowie Cache-Buster auf 0.18.0.4 vereinheitlicht.
- 56 automatisierte Tests bestanden.

## 0.18.0.3
- Hotfix: Nachtprognose und Nachtstrategie auf identische Wetter-/Zeitbasis vereinheitlicht.
- Kontrollierte Nachtlüftung bewertet Feuchtenutzen, prognostizierte Raumabkühlung und Wiederaufheizbedarf gemeinsam.
- Neue Zwischenstrategie: vor dem Schlafengehen stoßlüften statt Fenster bei thermisch ungünstiger Nacht dauerhaft offen zu lassen.
- `pre_ventilate` vollständig in Unified Decision Brain und Dashboard integriert.
- 53 automatisierte Tests bestanden.

## 0.18.0.2
- Neue intelligente Nachtstrategie ab drei Stunden vor Nachtbeginn und während der Nacht.
- Wetterprognose, absolute Außenfeuchte, Temperatur, Niederschlag und aktuelle Fensterzustände werden gemeinsam bewertet.
- Nachtstrategie erscheint situationsabhängig als Hauptentscheidung oder Kontext; unmittelbare Sicherheits-/Lüftungsentscheidungen behalten Vorrang.
- Nachtbenachrichtigung nutzt dieselbe kanonische Strategie.
- Status-Entity exportiert Nachtstrategie und Wetterverfügbarkeit an das Dashboard.

## 0.18.0.1
- Hotfix: Frontend-Modul-URL auf `freshairiq-card.js?v=0.18.0.1` aktualisiert, damit Home Assistant/iOS die neue Karte sicher neu lädt.

## 0.18.0.0
- Intelligent Home Climate Dashboard: zentrale KI-Entscheidung mit kontextbezogenen Live-Werten und explizitem Prognosezeitraum.
- Prognosezeitraum in Integrationseinstellungen und Detailansicht synchron steuerbar.
- Kompakte Hauptnavigation; separate Haupt-Metriksektion entfernt.
- IQ-Aktivitätsanzeige aus realen Systemzuständen und Bewertungsdaten.

## 0.17.0.8
- Pipeline-Konsistenz-Hotfix: finale Konsolidierung vor Decision Brain/UI-Texten.
- Verhindert widersprüchliche Top-Level- und Dashboard-Schließempfehlungen.

## 0.17.0.7
- Hotfix: Dynamische Restdauer einer laufenden Lüftung darf unter die Mindestlüftungsdauer sinken.
- Neue Lüftungen behalten weiterhin die konfigurierte Mindestdauer; `close` bleibt 0,0 min.

## 0.17.0.6
- Hotfix: finale Schließentscheidung bleibt eine unmittelbare Aktion (`duration_min = 0`) und wird nicht mehr durch `min_duration_min` verlängert.
- Regressionstests für Close/Continue-Dauer ergänzt.

## 0.17.0.5

- Hotfix: Schließfreigabe ist jetzt auch für Live Coach und finale Konsolidierung verbindlich.
- Sensorberichtszählung nutzt `last_reported` mit `last_updated`-Fallback.
- Regressionstests für 0/2, 1/2, 2/2, <15 min und >=15 min aktualisiert/ergänzt.

## 0.16.0.0 — Intelligence Consolidation / Release Candidate

- Added a final recommendation consolidation layer after all intelligence engines.
- Running ventilation and close states are authoritative over future planning/prediction layers.
- Invalid/stale room references and non-finite numeric recommendation values are normalised before UI/state output.
- Recommendation duration is bounded by configured min/max at the final output boundary.
- Hardened persisted learning migration against malformed nested dictionaries.
- Manual learning reset now also clears house-wide strategy learning and stale active recommendation episodes.
- No new major intelligence feature; this release focuses on consistency, migration safety and release readiness.


## 0.9.9.0
- Phase 5: adaptive user-strategy learning for recommendation adherence and physical success.
- Decision Engine v4 uses mature strategy data only as a bounded tie-breaker below health-critical pressure.
- Compact Strategy-IQ diagnostics added without enlarging the main dashboard.

## 0.9.8.0
- Routine Intelligence: zeitabhängiges Feuchte- und Empfehlungsbefolgungslernen.
- Decision Engine v3 berücksichtigt gelernte Tagesmuster in Warteoptionen.
- Nachtprognose kann reife Routinen konservativ einblenden.

## 0.9.7.0
- Future weather boundaries for Decision Engine v2.
- Closed-loop prediction-vs-reality learning per room.
- Intelligence Engine v3 exposes future-weather and outcome-feedback context.

## 0.9.6.0
- Decision & Simulation Engine: bewertet mehrere Handlungsoptionen und wählt eine priorisierte Hauptempfehlung.
- Bewohnerlernen personalisiert die Lüftungsdauer konservativ.
- Simulationsmatrix enthält Nutzen, Temperatur, Kosten, Confidence und transparente Annahmen.
- Bestehende v0.9.5.0 Berechnungslogik bleibt unverändert als Basis erhalten.

## 0.9.5.0
- Added the central FreshAirIQ Intelligence Layer (`iq_state`) with explainable status, activities and combined confidence.
- Added persistent behavioural learning for recommendation following and actual ventilation duration.
- Preserved all existing room, forecast, learning and recommendation calculations as the stable physics layer.

## 0.9.4.10
- Raumkarten-Layout an die Referenzansicht angepasst, inklusive dreispaltiger Statuszeile auf Mobilgeräten und ausgeschriebener Fensterausrichtung.

## 0.9.4.9
- Raumkacheln optisch an die gewünschte Referenz angepasst: Feuchtemenge oben rechts, darunter drei gleichwertige Bereiche für Raumklima, Schimmelrisiko und Lernstatus.
- Schimmelrisiko zeigt die berechnete Oberflächen-RH als Hauptwert und die Risikostufe darunter.
- Fensterausrichtungen werden ausgeschrieben (z. B. „Ost“ statt „O“, „Nordost“ statt „NO“).
- Raumübersicht nutzt für die neue Kachelbreite eine einspaltige Darstellung; Berechnungs-, Lern-, Forecast- und Recommendation-Logik unverändert.

## 0.9.4.8
- Raumübersicht neu fokussiert: Raumklima, gesamte Feuchtemenge in ml, Schimmelrisiko, Lernstatus und konfigurierte Raumeigenschaften.
- Aus Raumkacheln entfernt: Aktionsstatus (z. B. Warten/Lüften), Entfernungspotenzial, Live-Bilanz, 5-Minuten-Prognose, Empfehlungsbegründungen und letzte Messung.
- Letzte Messung inklusive Plausibilitätsstatus sowie letzte Lernmessung/Diagnose werden in der detaillierten Raumansicht angezeigt.
- Keine Änderungen an Berechnungs-, Lern-, Forecast- oder Recommendation-Engine.

## 0.9.4.7
- Hotfix: realistische entfern-/eintragbare Feuchte wieder aus absoluter Feuchtedifferenz × Raumvolumen × gelerntem Luftaustausch berechnet.
- Explizites Außenluft-Feuchteveto mit möglichem Feuchteeintrag.
- Live-Lüftungsbilanz unverändert.

# 0.9.4.6
- Hotfix: Vereinheitlichte Feuchteprognose für 5–120 Minuten; Recommendation Engine und Prognosekachel verwenden dieselbe Forecast Engine.
- Hotfix: Benutzeranzeige „Weitere X Min“ zeigt den Lüftungseffekt selbst; interne Feuchtequellen bleiben als separater Netto-Diagnosewert erhalten.
- Hotfix: „Entfernbar“ entspricht jetzt exakt der Summe der angezeigten Raum-Potenziale; die Empfehlungsschwelle nutzt weiterhin nur tatsächlich lüftungsrelevante Kandidaten.
- Live-Feuchtebilanz während laufender Lüftungen unverändert.

# 0.9.4.5

- Hotfix: ausstehenden Deferred-Render beim Eintritt in die Raumansicht sicher abbrechen.
- Hotfix: Haus-Empfehlung erst nach erfolgreicher/absichtlich unterdrückter Notification als verarbeitet markieren.
- Release-Bereinigung: `__pycache__` und `.pyc` entfernt.

# 0.9.4.4

- Hotfix: Raumübersicht und Raumdetail werden während HA-State-Updates nicht mehr neu gerendert; verhindert sporadisches Zurückspringen des iOS/WebView-Scrollcontainers auf 0.
- Keine Änderungen an Berechnungen, Empfehlungen oder UX-Struktur.


## 0.9.4.3 — Scroll hotfix
- Raumdetailansicht: verbleibendes sporadisches Hochspringen auf iOS/Home-Assistant-WebView behoben.
- Touch-/Momentum-Scroll bleibt im Raumdetail-Container; Scroll-Chaining/Rubber-Band an Ober- und Unterkante wird abgefangen.
- Keine Änderungen an Berechnungs-, Lern-, Prognose-, Empfehlungs- oder Raumlogik.
- Paketordner folgt wieder dem Schema `FreshAirIQ-v0.9.4.3`.

# 0.9.4.2

Hotfix based strictly on 0.9.4.1:

- preserve the room-detail subdialog scroll position across unavoidable card re-renders
- disable browser scroll anchoring in the room-detail scroll container to prevent sporadic iOS/WebView jumps to the top
- no calculation, recommendation, room-data, settings, or layout changes

# 0.9.4.1

Hotfix based strictly on 0.9.4:
- prevent the status sensor from failing on a missing house-level `temperature_history_14d` key
- preserve active ventilation sessions during Home Assistant startup until climate measurements are valid
- make dashboard headline metrics prefer the resolved status payload, avoiding stale/suffixed entity-ID mismatches
- avoid mutating Home Assistant state attributes in-place in the frontend
- make statistics reset also clear `water_daily` and `last_ventilation`
- start notification cooldown only after at least one notify service was actually called
- align device/frontend/integration version metadata to 0.9.4.1
- add the four missing forecast sensor translation keys

# 0.9.4

- Raumdetailansicht: Zurück-Pfeil oben links hinzugefügt.
- Der Zurück-Pfeil führt direkt zurück zur vollständigen Raumübersicht, ohne das Overlay zu schließen.
- Basis ist der stabile v0.9.3 Room-Detail-Scroll-Hotfix 5; keine Änderungen an Berechnungs-, Lern-, Prognose- oder Empfehlungslogik.

# 0.9.3

- Dashboard status-entity selection fixed for duplicate/stale entities.
- Expose `water_history_14d` on status sensor.
- No calculation-engine changes.

# 0.9.2

- Dashboard-Status-Erkennung repariert und Frontend-Cache-Busting korrigiert.
- Keine Änderungen an Berechnungs- oder Intelligenzlogik.

# 0.9.1
- Stability hotfix for room/level sorting, area assignment UI, room popup source selection and German Presence Intelligence UX.
- No rollback of v0.9.0 calculation/forecast/recommendation logic.

# 0.9.0

- Vollständige Requirements-Release gemäß Anforderungskatalog v3 (20 Punkte).
- Recommendation Engine v3, Stabilisierung/Wiederempfehlungslogik, zonenplausible Querlüftung, Presence-Sensorfusion/Haustiermodus, Hauswasser-Tagesstatistik und native Reorder-Listen.


## 0.8.6
- Optionale Zuordnung von Home-Assistant-`person`/`device_tracker`-Entitäten zu Erwachsenen und Kindern; Anwesenheitswechsel lösen sofort eine Neuberechnung aus.
- Bewohner ohne Handy bleiben unterstützt; optional folgen sie dem Haushalts-Anwesenheitssignal (praktisch für Kinder ohne eigenes Smartphone).
- Persistenter Gästemodus mit getrennten Zählern für übernachtende Erwachsene und Kinder; direkte +/- Bedienung im integrierten Dashboard.
- Kurzzeitprognose verwendet die aktuell erwartete Belegung statt immer die volle konfigurierte Bewohnerzahl.
- Nachtprognose auf ein belegungsabhängiges Hybridmodell erweitert: gelernte Nachtbasis, aktuelle Bewohner/Gäste, Live-Feuchtequellen, Außenfeuchte, offene Fenster, Wind/Orientierung, Querlüftung und gelernter Luftwechsel.
- Während der Nacht wird nur noch bis zum tatsächlichen Nachtende prognostiziert statt stets das komplette Nachtfenster anzusetzen.
- Nachtlernen wird auf die konfigurierte Haushaltsbelegung normalisiert, damit Nächte mit abwesenden Bewohnern das Langzeitmodell nicht verzerren.
- Neuer Nacht-IQ/Confidence-Wert sowie Wetter- und Trendbeitrag in Dashboard/Statusattributen.

## 0.8.5
- Intelligent, frei einstellbare 1–120-Minuten-Kurzzeitprognose für Feuchte, Temperatur und Wiederaufheizkosten.
- Hybridmodell aus physikalischem Luftaustausch und gelerntem Live-Residual (interne Feuchtequellen, Pufferung, thermische Raumreaktion).
- Absolute-Feuchte-Trendbeobachtung mit Glättung und Plausibilitätsgrenzen.
- Neuer `number`-Regler für den Prognosezeitraum und direkte Bedienung im Dashboard.
- Kumulative Lüftungs-Heizlast für längere Zeiträume; Legacy-5-Minuten-Felder bleiben kompatibel.

## 0.8.4 — Recommendation Engine v2
- Hauptkarte zeigt nur noch eine priorisierte intelligente Handlungsempfehlung statt einer Liste konkurrierender Raumaktionen.
- Neue Engine bewertet Raumrisiko, absolute Feuchtedifferenz, Entfeuchtungspotenzial, Wind/Orientierung, Temperaturverlust, Kosten und gelernte Raumwirkung gemeinsam.
- Gezielte Raumlüftung kann bei echtem Raumproblem weiterhin unterhalb der Hausschwelle ausgelöst werden.
- Ungeeignete Außenluft führt zu einer begründeten Warteempfehlung statt zu widersprüchlichen Raumkarten.
- Konfigurierte Querlüftungspaare werden bei sinnvoller Eignung bevorzugt.
- Persistente Feuchtedauer und 5-Minuten-RH-Trend ergänzen die Momentaufnahme.
- Haus-Benachrichtigungen verwenden dieselbe zentrale Empfehlung.
- Dehumidify-Profil zeigt nun den tatsächlich wirksamen reduzierten Δ-Feuchte-Grenzwert an.

## 0.8.3 — Raumbezogene Empfehlungen & lesbare Begründungen
- Raumprobleme werden unabhängig von der Haus-Lüftungsschwelle bewertet.
- Hohe Raum-RH, Schimmelrisiko und CO₂ werden als konkrete Auslöser in der Empfehlung genannt.
- Bei ungeeigneter Außen-/Referenzluft wird ausdrücklich erklärt, warum aktuell nicht gelüftet werden soll.
- Dashboard um einen eigenen, mehrzeiligen Empfehlungsbereich mit gut lesbaren raumbezogenen Gründen erweitert.
- Raumkarten und Lüftungsbenachrichtigungen verwenden dieselben erklärenden Gründe.

## 0.8.2 — Korrektur 5.0
- Sechs UX-/Logikkorrekturen: Sortierung, Schimmel-Popup, natives Overlay-Scrolling, getrennte Details/Räume, letzte Lüftung und konsistente Hausschwelle.

## 0.8.0 — Native room UX, restart continuity & profile intelligence

- Exposed every room as a native Home Assistant config subentry with room-local reconfiguration.
- Kept global settings on the parent FreshAirIQ entry; global room administration is limited to add/remove/order.
- Added user-defined floors/zones and expanded dwelling types (detached, semi-detached, mid/end terrace, apartment, maisonette, multi-family).
- Reworked room and live-moisture drill-downs as separate modal overlays.
- Removed repeated delayed scroll restoration and defer live DOM replacement while an iOS/HA touch scroll is active.
- Main dashboard mould risk now uses verbal levels instead of a percentage.
- Operating profile is clickable/explained and can be changed through a FreshAirIQ select entity.
- Dehumidify, Comfort and Summer Cooling now apply distinct decision priorities without changing psychrometric fundamentals.
- Preserved the original ventilation-session humidity baseline across Home Assistant restarts; persisted mL is retained as a startup fallback.
- `Close windows` now outranks generic `Ventilation running` at house level.
- Statistics reset clears house and room history/temperature series.
- Unified Home Assistant local-time handling for statistics windows and aligned house pollen veto semantics with room logic.
- Added real pytest execution to CI and expanded profile/restart unit coverage.

## 0.7.0 — Ten-point intelligence & UX update

- Weather-aware night forecast when windows are open; occupant prior retained.
- Unified priority-based recommendations with explicit reasons, wind/orientation and optional pollen veto.
- Visual dashboard card editor with visibility toggles.
- Full-surface touch scrolling in Details.
- Timestamped valid/invalid measurements and learning results with subtle status styling.
- Detailed room drill-down with room-specific 14-day statistics and charts.
- Live-balance restart continuity via persisted result + safe post-start rebase.
- Defaults shown in settings and one-click reset of all options to defaults.
- Per-contact window orientation moved into the room add/edit workflow.
- Schema/version metadata updated to 0.7.0 / config-entry version 7.

## 0.6.3 — Nine-point dashboard correction pass

- Show mould risk directly on the main card.
- Warn "Nicht lüften" and quantify expected moisture ingress when outside/reference air is wetter.
- Keep the idle card compact; temperature, ventilation time and 5-minute session forecast are only shown while airing.
- Colour-code mould risk in every room.
- Show the latest learning measurement in every room card.
- Add an overall learning-model status to Details.
- Translate the remaining "Keep windows closed" status to German in the bundled UI.
- Preserve Details scroll position when opening room information and disable scroll anchoring jumps.
- Harden signed moisture rendering so moisture ingress cannot make the dashboard card fail.
- Bound legacy model and pollen/wind option defaults before rendering Home Assistant forms.


## 0.6.2 — Restart, config-flow and details-scroll reliability
- Fixed live moisture balances carrying completed-session values into a new or restarted ventilation session.
- Live whole-house balance now sums active sessions only; every new session starts from a zero result baseline.
- Valid recent sessions survive a Home Assistant restart, while stale/invalid legacy baselines are safely re-based on plausible measurements.
- Prevented closed sessions from being finalized with startup placeholder sensor values, eliminating extreme moisture/temperature artifacts and protecting learning/statistics.
- Fixed `Pollen & wind`, `Model parameters` and heating detail forms on Home Assistant versions that reject `unit_of_measurement: null` in number selectors.
- Fixed config-entry migration for per-contact delays/orientations and bumped schema/version metadata.
- Reworked details-popup scroll persistence: scroll position is tracked continuously and restored after multiple browser layout frames on every live refresh.
- Updated frontend cache version, integration/device version metadata and repository documentation.

## 0.6.1 — Adaptive threshold correction
- Changed the untouched 0.6.0 10%-of-water default to the adaptive dwelling-size threshold.
- Added per-contact window orientation and simplified room sorting.
- Added first-pass protection against invalid restart baselines and expanded clickable dashboard explanations.
- Preserved learning data across updates and kept manual learning reset available.

## 0.6.0 — Adaptive house model & live intelligence
- Reworked the integrated dashboard: removed the old `CLIMATE INTELLIGENCE · V14.2.1` eyebrow and added an in-card details modal.
- Unified UI moisture semantics: green/minus means moisture removed; red/plus means moisture added.
- Added live next-five-minute moisture, temperature and reheating-cost context plus night forecast to the main tile.
- Added 10%-of-current-house-water as the default ventilation threshold, with fixed-mL compatibility mode.
- Added floor assignment, room sorting and calculation-exclusion / monitor-only rooms.
- Simplified room volume setup and added individual delays per contact sensor.
- Added property type and improved adult/child + night-time controls.
- Added pollen-aware ventilation veto and optional wind/window-orientation airflow correction.
- Expanded heating-cost configuration for heat pump, gas, oil, district heating and direct electric systems.
- Exposed learned room rates, samples and diagnoses; learning remains persistent and can be reset manually.
- Replaced the fixed 45-minute learning ceiling with a configurable maximum (default 120 minutes).
- Extended selectable statistics retention/view period to 30 days.
- Reworked operating-profile configuration so each profile exposes relevant parameters and explanations.
- Aligned full-session exchange forecasting with the exponential replacement model used by the supplied V14.2.1 YAML.

## 0.5.0 — Integrated dashboard
- Added bundled `custom:freshairiq-card`.
- Registers in Home Assistant's graphical Community card picker.
- Added FreshAirIQ Community dashboard strategy for Home Assistant 2026.5+.
- Frontend JavaScript and logo are served and loaded automatically by FreshAirIQ.
- No manual YAML, Browser Mod or `custom:button-card` is required for the integrated dashboard.
- Card discovers configured rooms dynamically.
- Compact view: current recommendation, removable/live moisture, temperature change, ventilation time and 5-minute forecast.
- Expanded view: rooms, learning, mould risk, night forecast, 14-day moisture statistics, temperature history and energy context.


## 0.4.3 — Immediate room/device reload
- Fixed rooms being saved and visible in `sensor.freshairiq_status` but not appearing as Home Assistant room devices/entities.
- Structural changes in `ConfigEntry.data` now explicitly schedule a FreshAirIQ reload.
- Add/edit/remove room and outdoor-source changes rebuild the sensor and binary-sensor platforms immediately.
- Options-only changes continue to use Home Assistant's `OptionsFlowWithReload`.
- Existing rooms already saved by v0.4.2 will appear after the first reload/restart with v0.4.3.


## 0.4.2 — Config menu translations
- Fixed six blank menu entries in the FreshAirIQ options flow.
- Added German and English labels for Operating profile, Home & occupants, Heating & energy costs, Notifications, Statistics & history and Reset learning data.
- Updated the configuration-menu description to reflect all v0.4 modules.
- Added static navigation validation for all top-level v0.4 menu steps.


## 0.4.1 — Home Assistant registry identifier compatibility
- Fixed FreshAirIQ failing during setup with `ValueError: too many values to unpack`.
- Device-registry identifier parsing no longer assumes exactly two tuple values.
- FreshAirIQ now reads only the domain and stable identifier value and ignores additional registry metadata.
- Deleted-room/orphan cleanup remains enabled.
- No learning, history, night-model or notification data is reset by this update.


## 0.4.0 — Climate intelligence
- Notification Center with room / whole-home / both scopes and selectable notify services.
- Continuation forecast in close notifications: moisture, temperature and estimated cost.
- Dehumidify, Comfort and Summer Cooling operating profiles.
- House/occupant profile with persistent adaptive night-moisture model.
- Heating-system and energy-price profile with physical exchanged-air heat-loss calculation.
- Persistent 14-day session and temperature statistics.
- Manual learning reset and statistics reset buttons; learning survives restarts.
- Dashboard updated with overnight forecast and 14-day analytics.


## 0.3.7 — Orphan device cleanup
- Fixed deleted rooms that survived as fully orphaned Home Assistant devices.
- Registry reconciliation now scans all registered devices by FreshAirIQ's stable room identifier instead of only devices still attached to the Config Entry.
- Removes disabled as well as enabled entity-registry entries before deleting the stale device.
- Existing orphaned room devices from 0.3.5/0.3.6 are cleaned automatically on the next FreshAirIQ setup/reload.


## 0.3.6 — Deleted-room registry cleanup
- Fixed deleted rooms remaining visible as unavailable devices.
- FreshAirIQ now reconciles configured rooms with Home Assistant's Device Registry on setup.
- Stale FreshAirIQ room entities are removed from the Entity Registry.
- The corresponding orphaned room device is removed afterwards.
- Existing ghost rooms from earlier releases are cleaned automatically on the next reload/restart.


## 0.3.5 — Room save fix
- Fixed room creation from **Configure → Manage rooms → Add room**.
- Saving a new room now immediately persists the Config Entry and reloads FreshAirIQ.
- Editing a room now persists immediately.
- Removing a room now persists immediately after confirmation.
- Outdoor-source and model-setting forms now also follow true Save semantics.
- The separate Finish action remains available but is no longer required after saving a form.


## 0.3.4 — Native HA branding & localization
- Added Home Assistant 2026.3+ local branding under `custom_components/freshairiq/brand/`.
- FreshAirIQ now supplies icon/logo plus dark and high-DPI variants directly to Home Assistant.
- Added translated device names.
- Added translated sensor and binary-sensor names.
- Added translated states for room action, mould risk and learning status.
- Replaced `FreshAirIQ monitored room` with neutral model `FreshAirIQ RM / FAIQ-RM1`.
- Updated software version to 0.3.4.


## 0.3.3 — Dashboard logo
- Replaced the generic MDI icon in the FreshAirIQ dashboard with the official FreshAirIQ logo asset.
- The main card and popup now load `/local/freshairiq/freshairiq-icon.png`.
- Kept the dashboard fully dynamic and room-independent.


## 0.3.2 — Live dashboard
- Added adaptive FreshAirIQ dashboard card with Browser Mod room popup.
- Dashboard reads rooms dynamically from the FreshAirIQ status entity.
- Added recommended ventilation duration and live remaining/overrun time.
- Added live temperature change since ventilation start.
- Added session elapsed time and room volume to room status data.
- Added a reduced dashboard icon asset under `www/freshairiq/`.


## 0.3.1 — Branding
- Added the approved official FreshAirIQ branding artwork.
- Added reduced 512/256/128 px icon assets using the house + airflow + leaf mark.
- Set developer/code owner to `rupascha`.
- Prepared repository branding assets for later Home Assistant brands submission.


## 0.3.0
- Renamed project and integration to **FreshAirIQ**.
- Developer metadata set to **rupascha**.
- Clean integration domain changed to `freshairiq`.
- Added one-click import from the previous `ventilation_assistant` config entry.
- Added migration of existing persistent learning data.
- Updated device branding, repository metadata, translations, examples and documentation.

## 0.2.0
- Changed integration type from helper to hub.
- Added central-device and per-room device registry grouping.
- Added full Configure menu.
- Added outdoor source editing after setup.
- Added room add/edit/remove flows.
- Added model-settings menu to the same Configure flow.
- Added explicit direct-vs-dimensions volume input mode.
- Added automatic migration to config-entry schema version 3.

## 0.1.2
- Added multiple ventilation contacts per room.
- Added ANY/ALL contact logic for multi-window and indirect ventilation paths.
- Added room volume calculation from length × width × height.

## 0.1.1
- Added local `weather.*` entity as an outdoor reference source.
- Dedicated local outdoor temperature/humidity sensors can override weather attributes.

## 0.1.0
- Initial Python port of the V14.2.1 calculation model.
- Config flow, coordinator, sensors, binary sensors and persistent learning store.
## 0.17.0.4
- Hotfix: Bei weniger als zwei neuen Feuchtesensor-Messungen bleibt die Schließsperre zunächst aktiv. Nach 15 Minuten darf FreshAirIQ ersatzweise modellbasiert entscheiden.
- Die Fallback-Entscheidung nutzt die bestehende physikalische/Lernlogik; bei direkter Außenreferenz wird zusätzlich die 15-Minuten-Wetterprognose als Feuchteeintrags-Veto berücksichtigt.
- Keine Änderung an normaler Schließlogik bei zwei frischen Messungen, Prognoseberechnung, Lernmodell, UI oder übrigen Funktionen.

## 0.17.0.3
- Hotfix: Schließentscheidungen warten auf zwei echte neue Feuchte-Sensormessungen nach Fensteröffnung.
- Startwert und restaurierte Zustände nach Neustart zählen nicht als neue Messung.
- Keine Nebenänderungen an Prognose, Lernen oder UI.

## 0.17.0.2
- Hotfix: long-horizon ventilation forecasts are target-limited for user-facing decision forecasts.
- Hotfix: multi-hour planning no longer treats 100% of projected internal moisture generation as removable ventilation potential.
- Live 5-minute close/continue logic intentionally unchanged.


## 0.24.5.0
- Backtest, Shadow Learning, Diagnostics und History-Persistenz gegen beschädigte/non-finite Alt-Daten gehärtet.
- Fremde Shadow-Kandidaten können die Modellauswahl nicht mehr beeinflussen.
- Diagnoseexport bleibt bei beschädigten JSONL-/Session-/Raumstrukturen funktionsfähig und nachvollziehbar.
- 476 Regressionstests; Pure-Logic-Coverage 92,986 %, CI-Floor 92,9 %.


## 0.25.0.72
- Hotfix: Scrollpositionen werden pro Detail-/Raumansicht gespeichert und bei Back-Navigation wiederhergestellt.
- Android: Touch-Scroll-Fallback für `.dialog-scroll` und `.subdialog`; iOS-native Scrollpfade bleiben unverändert.


## 0.25.0.73
- Root-Cause-Hotfix: Back-Navigation überschreibt die gespeicherte Scrollposition der Parent-Ansicht nicht mehr mit der Scrollposition des Child-Fensters.
- Betrifft Details-/Räume-Unterfenster; Android-Touch-Scroll-Verhalten aus 0.25.0.72 bleibt unverändert.
