# FreshAirIQ 1.0 – verbindliche Qualitäts-Gates

Ein Release mit Kennzeichnung 1.0 ist erst zulässig, wenn **alle** Gates erfüllt sind. Neue Produktfunktionen sind bis dahin eingefroren; vor 1.0 sind nur Stabilisierung, Testbarkeit, Kompatibilität, Migration, Dokumentation und notwendige Fehlerkorrekturen vorgesehen.


## Continuous Quality System ab 0.25.0.21
Die Release-Prüfung ist in fünf feste Qualitätsachsen aufgeteilt: **Korrektheit, Robustheit, Stabilität, Kompatibilität und Performance**. Release-Hygiene ist ein zusätzliches zwingendes Build-Gate. Die Grenzwerte werden zentral in `quality/quality_policy.json` gepflegt.

- **Korrektheit:** vollständige Regression plus 100 % Pure-Logic-Line-Coverage.
- **Robustheit:** dedizierte Fault-Injection-/Numeric-/Optional-Entity-Suite.
- **Stabilität:** deterministische Langzeitsimulation mit Grenzwerten für retained memory, peak memory und Laufzeit.
- **Kompatibilität:** Python 3.13/3.14, Home Assistant Mindest-/Aktuallinie, reale HA-Lifecycle-Suite, HACS und Browser-Matrix.
- **Performance:** normalisierte, runner-unabhängiger gemachte Microbenchmarks gegen eine akzeptierte Baseline; Warn- und Fehlergrenzen sind getrennt.
- **Release-Hygiene:** das veröffentlichte ZIP darf keine `__pycache__`, `.pyc`, `.pytest_cache`, `.coverage`, `node_modules`, `.git` oder Betriebssystem-Artefakte enthalten.
- **Release-Erzeugung:** der Clean-Release-Builder bricht ab, wenn ein verpflichtendes Gate fehlschlägt.
- **Edge-Watch:** zukünftige Home-Assistant-Versionen werden wöchentlich advisory getestet, damit kommende Brüche früh sichtbar werden, ohne die aktuell unterstützte Matrix unnötig zu blockieren.

## Funktionale Konsistenz
- Eine kanonische Berechnungskette für Sensorzustand → Forecast → Entscheidung → Session → Ergebnis → Learning.
- Golden-Dataset-Regression gegen reale Lüftungssessions; kein Release bei signifikanter Verschlechterung.
- Alle optionalen Sensoren/Aktoren degradieren sauber: nicht konfiguriert oder `unavailable` darf die Kernlogik nicht brechen.

## Robustheit
- Neustart, Reload, Sensor `unavailable`/`unknown`, gelöschte Entity, geänderte Entity-ID, fehlendes Wetter, prellende Kontakte, parallele Öffnungen und beschädigter/alter Storage werden getestet.
- Keine automatische Aktorbetätigung ohne explizites Opt-in bzw. explizite Home-Assistant-Aktion.
- Migrationen sind idempotent und rückwärtskompatibel.

## Test & CI
- Python-Kompilierung, JSON-Validierung, Frontend-Syntax und Regressionstests bei jedem Commit.
- **Pure Logic: 100 % Line-Coverage als hartes CI-Gate.** Kein Release bei 99,99 %.
- **Kanonische reale HA-Coverage für den v1-Kandidaten:** kombiniert mindestens **99 %**, jedes einzelne Python-Integrationsmodul mindestens **98 %**, `config_flow.py` **100 %**. Projektziel bleibt **100 %**, soweit der Pfad sinnvoll testbar ist.
- Kein Modul darf durch einen unvollständigen Coverage-Report aus dem Nenner verschwinden; fehlende Integrationsmodule gelten als 0 % und lassen das Gate scheitern.
- Coverage darf nicht durch `# pragma: no cover` oder künstliches Ausblenden fachlich erreichbarer Pfade beschönigt werden. Unerreichbarer Code wird begründet entfernt.
- Browser-E2E: iPhone/iPad WebView, Android WebView, Chromium und Firefox.

## UX
- Installation, Räume, optionale Sensoren/Aktoren und Dashboard vollständig über UI.
- Keine YAML-Pflicht für Standardbetrieb.
- Alle Dialoge scrollstabil, live-update-fähig und touch-tauglich.
- Deutsch/Englisch vollständig und konsistent.

## Performance
- Keine merkliche UI-Blockade bei typischen Haushalten.
- Messbare Budgets für Coordinator-Laufzeit, Frontend-Renderzeit, Recorder-/Storage-Wachstum und Speicherverbrauch.

## Produktreife
- Diagnose + Datenschutzprüfung.
- Repair-Hinweise für vom Nutzer behebbaren Konfigurationsverlust.
- Quickstart, vollständige Doku, Troubleshooting, bekannte Grenzen und Beispiele.
- Stufenweise Fremdtests: 10 → 25 → mindestens 50 Haushalte vor 1.0.

## Aktueller verifizierter Stand
- Der lokale Gesamtstand wird bei jedem Release erneut durch das Continuous Quality System bestimmt; die verbindliche Zahl steht im zugehörigen Release-Report.
- Pure-Logic-Coverage: **100,00 % = 5.313/5.313 Statements** im definierten Scope.
- Stabilitäts-Gate lokal bestanden: **3.000 Zyklen**, deterministische Entscheidungen, retained memory praktisch null und Peak weit unter dem 16-MiB-Limit.
- Performance-Baseline wurde für drei repräsentative Kernpfade erzeugt und der direkte Wiederholungslauf lag innerhalb der definierten Warn-/Fehlergrenzen.
- Diagnostics-Transport: die Performance-Härtung sowie der authentifizierte `/v1/enroll` → Bearer-Chunk-Vertrag für den privaten Staging-Hub bleiben Bestandteil des verpflichtenden Kompatibilitätsvertrags.
- Frontend-JavaScript sowie die neuen Playwright-Testdateien bestehen den lokalen Syntaxcheck.
- CI ist für Python 3.13/3.14, Home Assistant 2026.8/2026.9, reale HA-Lifecycle-/Coverage-Tests, HACS, Chromium/WebKit/Firefox und vier Viewportklassen konfiguriert.
- Ein wöchentlicher HA-Edge-Watch prüft die jeweils neueste Home-Assistant-Version advisory.
- Der Clean-Release-Builder erzeugt ZIPs aus einer bereinigten Staging-Struktur und führt danach erneut einen Forbidden-Artifact-Scan durch.
- **Reale HA-Runtime-Coverage bleibt offen**, bis der tatsächliche GitHub-CI-Lauf den kanonischen Bericht erzeugt; lokal ist kein vollständiges Home-Assistant-Testpaket installiert.
- **Browser-E2E bleibt bis zum tatsächlichen GitHub-CI-Lauf offen**; die Playwright-Matrix ist implementiert, die Browser-Runtimes werden erst im CI installiert.
- **Strict Typing bleibt offen.**
- **Fremdhaushalt-Beta 10 → 25 → mindestens 50 bleibt offen.**
- Kein 1.0-Tag, solange eines dieser offenen Produktreife-Gates besteht.

## Historischer Referenzstand – 0.24.13.0
- **509** lokale Pure-Logic-/Regressionstests grün.
- Korrekt getrennte Pure-Logic-Coverage: **95,06 %**; damaliges CI-Gate **≥95 %**.
- Die Fachlogik war für diesen Verifikationsblock eingefroren; 0.24.13.0 änderte keine Lüftungsphysik, Forecast-Koeffizienten, Lernraten oder Dashboard-Logik.
- Der `ha-runtime`-CI-Job erzeugte bereits `coverage-ha.json`; der reale HA-Coverage-Baselinewert blieb ohne tatsächlichen CI-Lauf offen.
- `config-flow-test-coverage`, reale Gesamtcoverage, Strict Typing, Browser-E2E und Fremdhaushalte waren zu diesem Stand offen.
