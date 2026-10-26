# Entwicklung, Tests, Build, Release (Stand 2026-10-16)

## Arbeitsregeln
- Arbeitsbranch je Auftrag (aktuell `arbeitsauftrag-2026-10-14` in `-faiq-dev` und `-faiq-hub`); kein Push auf `main`, kein Tag/Release/PR ohne Freigabe.
- Hotfix-Ablauf: Ursache → beide Contract-Seiten → minimaler Fix → Regressionstest (muss auf dem Ausgangsstand fehlschlagen) → alle Gates von vorn → CLEAN-Build → genau dieses ZIP prüfen.
- Tests nicht abschwächen. Veraltete Erwartungen nur mit Beleg (Changelog/Nutzerauftrag) gezielt anpassen und im Commit begründen.

## Testabhängigkeiten herstellen
```bash
pip install pytest pytest-asyncio coverage aiohttp          # Pure-Suite/Gates (Python 3.13)
npm ci                                                       # Playwright 1.55.0
# Echte HA-Runtime: HA >= 2026.8 braucht Python 3.14
uv venv -p 3.14 .ha314 && VIRTUAL_ENV=.ha314 uv pip install pytest-homeassistant-custom-component pytest-cov "home-assistant-frontend==<Pin aus homeassistant/package_constraints.txt>"
# Pflicht: Frontend-Pin wie in CI (manifest.json hängt von "frontend" ab; ohne Paket scheitert jedes Setup mit DependencyError)
# CI ermittelt den Pin automatisch aus package_constraints.txt des installierten Cores (quality.yml, Job ha-runtime).
```
Im Container: vorinstalliertes Chromium über eine lokale, nicht eingecheckte Config mit
`launchOptions.executablePath=/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (Version 1194 ≠ Playwright-Build 1187).

## Gates und echte Ergebnisse (Commit-Stand siehe Übergabestand)
| Prüfung | Kommando | Ergebnis 2026-10-16 |
|---|---|---|
| Pure-Suite 3.13 / 3.14 | `pytest -q -p no:cacheprovider tests` (3.14 mit `-p no:homeassistant`, falls HA-Plugin installiert) | 2074/2074 grün (beide) |
| Quality-Gate lokal | `tools/quality_gate.py --profile local` | alle Stufen grün außer **Performance: im geteilten Container instabil** (gleicher Code schwankt +4 … +50 %; A/B Ausgangs- vs. aktueller Stand ohne systematischen Unterschied) |
| GitHub Actions (ab 2026-10-25) | alle Repos | **nur manuell** (`workflow_dispatch`): Actions-Kontingent ausgeschöpft; Push, Pull-Request und Zeitplan starten keine Workflows mehr. Pflichtprüfungen laufen lokal (Pure-Suite, HA-Suite + Coverage, Golden Master, Gates, Browser, CLEAN-Build). `release.yml` startet weiter nur bei einem freigegebenen Tag und ruft dann `quality.yml` auf |
| Quality-Gate CI (`core-quality`) | GitHub Actions | **grün** inkl. Performance auf dediziertem Runner (Commits 0710d1c, 0e31654) |
| CI python-compatibility 3.13/3.14, Validate/pure-logic, release-dry-run | GitHub Actions | grün |
| CI ha-compatibility (HA 2026.8/2026.9 Import-Smoke) | GitHub Actions | lief bis 0e31654 rot wegen fehlendem `PYTHONPATH=.` im rekonstruierten Workflow; korrigiert, lokal mit HA 2026.10.1 grün |
| CI hacs | GitHub Actions | HACS-Store-Prüfung nur in öffentlichen Repos, Source-Release-Gate immer (A-16) |
| Golden Master | `tools/coordinator_golden.py --check` | 6 Szenarien / 117 Zyklen identisch (Fixture 2026-10-16 nach A-20/A-21 neu aufgenommen; Abweichung nur `summer_cooling_and_exhaust` Zyklus 16/17) |
| Browser | Playwright Chromium/WebKit/Firefox/Android-Emulation (CI) | A-12 behoben (Fixture-Sprache); lokal Chromium/Android 46/46, CI-Matrix nach Push prüfen |
| HA-Runtime + Coverage | Pure-Suite mit `--cov` (ohne HA-Plugin: `-p no:homeassistant`), danach `ha_tests` mit `--cov-append --cov-report=json:ha_tests/coverage-ha.json`, dann `tools/report_ha_coverage.py … --min-total 100 --min-module 100 --config-flow 100` | 430/430 grün (HA 2026.10.1, Py 3.14); **Gate PASS: 100,00 % gesamt, config_flow 100 %, alle Module 100 %** (Stand 2026-10-19; Gate auf 100/100/100 angehoben, ANALYSIS A-23) |
| Hub | `tools/quality_gate.py --stage <static|pure_logic_coverage|package_coverage|robustness_fault_injection|stability|performance|parallel_load>` | alle 7 Stufen + finalize grün; 432 Tests (hub 0fdf7db) |

Hinweise: Der Golden-Master pinnt `TZ=Europe/Berlin` selbst. HA-Tests schreiben Diagnose-Traces in den geteilten `testing_config` des pytest-homeassistant-Pakets; lokal vor Messungen `…/testing_config/.storage/freshairiq_diagnostics/*.jsonl` leeren (verlangsamt sonst stark, CI startet sauber). Performance lokal immer gepinnt (`taskset -c <cpu>`) und mehrfach messen; Bewertung über CI.

## Wartbarkeit: Größen-Gate und aufgeteilte Module (0.26.5.2)
Auftrag des Eigentümers (2026-10-19): Dateien dürfen nicht mehr so groß werden, dass eine kleine Änderung an
anderer Stelle bricht.
- Grenzen: jede Python-Datei unter `custom_components/` und `tools/` ≤ 800 Zeilen, jede Funktion/Methode
  ≤ 150 Zeilen (`end_lineno − lineno + 1`, verschachtelte Funktionen zählen einzeln), jedes Frontend-Modul
  `custom_components/freshairiq/frontend/*.js` ≤ 200 000 Byte.
- `python3 tools/maintainability_gate.py` prüft die Grenzen; läuft in `tools/quality_gate.py --profile local`
  innerhalb der Stufe `static-and-version`. Ausnahmen stehen mit aktueller Größe und Begründung in
  `quality/maintainability_baseline.json`; das Gate schlägt fehl, wenn eine nicht gelistete Stelle die Grenze
  überschreitet oder eine gelistete wächst, und meldet gelistete Stellen, die inzwischen passen.
- `python3 tools/maintainability_gate.py --update-baseline` senkt oder entfernt Einträge, fügt aber nie welche hinzu
  und erhöht keine. Neue Ausnahmen gibt es nur per bewusster Baseline-Änderung mit Begründung.
- Aufteilung großer Module: das ursprüngliche Modul bleibt Einstiegspunkt und exportiert alle bisherigen Namen weiter
  (HA lädt `config_flow.py`/`coordinator.py`). Klassen werden aus Mixins zusammengesetzt, lange Methoden in benannte
  Phasen-Helfer zerlegt (Schlüsselwort-Parameter, Rückgabe als Tupel). Neue Module, die Home Assistant importieren,
  gehören wie ihr Ursprungsmodul in die `omit`-Liste von `.coveragerc-pure`; reine Module brauchen 100 % Pure-Coverage.
- Contract-Tests, die Quelltext prüfen, lesen über `tests/_source.py` (`module_source("coordinator")` usw.) den
  zusammengefügten Text eines Moduls und seiner abgespaltenen Module; `FAMILIES` dort bei neuen Modulen ergänzen.
  Der UI-Vertrag (`quality/ui_configuration_contract.json`) hasht den zusammengefügten Config-Flow-Text.
- Monkeypatches in Tests müssen das Modul treffen, in dem der Name verwendet wird (z. B. `coordinator_decision`,
  `diagnostics_export`, `config_flow_subentry`).
- Nachweis der Verhaltensgleichheit bei Umbauten: Golden Master (`--check`, `--english`, zusätzlich `--dump` vor/nach
  vergleichen), Formular-Schemas aller Flow-Schritte und Schema-Builder vor/nach serialisieren und vergleichen,
  `tests/test_coordinator_definite_assignment.py` (prüft alle Funktionen der Coordinator-Module), volle Pure-, HA- und
  Coverage-Suite.

## CI und Actions-Minuten (2026-10-23)
- Automatisch läuft nur `quality.yml`; `validate.yml` startet von Hand (Actions → Validate) den kompletten Lauf.
- Die echte HA-Runtime mit 100-%-Coverage läuft einmal im Job `ha-runtime`. Python 3.13 läuft in `core-quality` (mit Coverage), die Matrix prüft 3.14.
- Pushes auf `arbeitsauftrag-*` testen im Browser nur Chromium + Android-WebView. `main`, Pull Requests, der Wochenlauf und Releases testen alle Browser. Gleiches gilt für die HA-Versionsmatrix in `-faiq-ha`.
- Reine Doku-Pushes (`docs/**`, `*.md`) starten nichts. Ein neuerer Push bricht den laufenden Lauf desselben Branches ab (auch Hub, HA, Website).
- Arbeitsweise: alle Gates lokal prüfen, mehrere Fixes lokal committen und gebündelt pushen (z. B. vor einer ZIP), nicht nach jedem einzelnen Fix.

## Build und Artefaktprüfung
```bash
python3 tools/build_release.py --output /pfad/FreshAirIQ.zip          # führt das lokale Gate selbst aus
python3 tools/build_release.py --skip-quality --output …              # nur nach bestandenem Gate desselben Commits (z. B. CI core-quality)
python3 tools/github_release_gate.py --zip /pfad/FreshAirIQ.zip
```
Danach ZIP entpacken: Struktur, Versionen (manifest/const/JS/package/policy), keine Caches/Test-Reste, `python -m compileall`, `node --check` der JS-Dateien, Import-Smoke.

## Release (nicht Teil dieses Auftrags)
Tag `v<version>` → `release.yml` → `quality.yml` (wiederverwendbar) → `verify-release` (Tag = Manifest) → CLEAN-ZIP anhängen. Versionen nur mit `tools/bump_release_version.py`.

## Ausgangsmodell übernehmen (0.26.5.4)
Nur wenn der Hub (Admin → „Ausgangsmodell für neue Installationen“) Werte als **empfohlen** ausweist:
```bash
python3 tools/apply_start_model.py FreshAirIQ-start-model-candidate-<datum>.json --check   # zeigt, was übernommen würde
python3 tools/apply_start_model.py FreshAirIQ-start-model-candidate-<datum>.json           # schreibt start_model_data.py
```
Danach komplette Suite, Golden Master (Startwerte ändern Prognosen ungelernter Räume → Diff prüfen, neu aufnehmen) und alle Gates; CHANGELOG nennt Version und Werte. Zurücknehmen: `start_model_data.py` auf das leere Modell zurücksetzen – ungelernte Werte gehen dann auf die eingebauten Startwerte zurück, gelernte bleiben.

## Bekannte Grenzen der Entwicklungsumgebung
- Reddit und GitHub-API des öffentlichen Repos per Netzwerkrichtlinie nicht erreichbar (Proxy 403) → Live-Nachweise offen.
- Kein Zugriff auf laufenden Hub, IONOS-Postfach, echte HA-Installationen, iOS-App, Fully Kiosk, HACS-Client.
- `.github/workflows`, `.coveragerc-pure`, `.gitignore`, `FUNDING.yml` fehlten im Repo und wurden 2026-10-16 aus den Contract-Tests rekonstruiert (Hub analog: `.coveragerc-*`, `.env.example`, `.gitignore`).

## Übergabestand
**Datum:** 2026-10-16 · **Branches:** `-faiq-dev` und `-faiq-hub` jeweils `arbeitsauftrag-2026-10-14` (Commits siehe `git log`; Register mit Commit je Punkt in `docs/WORK_REGISTER.md`).
- Erledigt: Infrastruktur-Wiederherstellung, F01/F02/F04(Doku)/F05/F09/F10, F24/F25, F36, F38, F39, E03, E06 (Code), E08, E09; Hub-Gates grün.
- Offen/blockiert: siehe Register (u. a. HA-Runtime-Altfehler, Live-Nachweise E03/E06/E07, Produktentscheidungen F03/F11/F15/F16/F30, Owner-Filter für eigene GitHub-Issues).
- Entscheidungen 2026-10-16: Owner-Issues zulassen (umgesetzt), Support-Postfach = eigenes IONOS-Postfach, HA-Runtime-Tests korrigiert (75/75), Raum-Reload-Fix in den Optionen freigegeben (A-19).
- Gruppe 5 2026-10-16 erledigt: A-12, A-15 (Hub Retry-After), A-16, A-22, F12-Trace (Fehlercodes), Register H06/H07/H29/H32 verifiziert, CI-Frontend-Abhängigkeit (A-25).
- Coverage-Paket 2026-10-16 abgeschlossen: kombiniertes HA-Coverage-Gate PASS (99,88 %/100 %/≥ 98 %; seit 2026-10-19 100 %/100 %/100 % als hartes Gate, A-23 bereinigt), 255 neue Real-HA-Tests (`ha_tests/test_cov_*.py`); neue Befunde A-19 (behoben), A-20/A-21/A-24 (Lernen; nach Freigabe behoben, Golden Master neu aufgenommen – nur Abluft-Szenario Zyklus 16/17), A-22, A-23.
- Nächster Schritt: (1) Hub-Branch deployen, `SUPPORT_MAIL_*` (und optional `REDDIT_*`) als Secrets setzen, Quellenstatus prüfen; (2) Produktentscheidungen (Register, Gruppe 1); (3) Rohdaten-Punkte F31–F41 nach Datenlieferung; (4) übrige Produktentscheidungen aus dem Register.

### Geprüfte Artefakte (lokal gebaut, nicht veröffentlicht)
| Komponente | Artefakt | Stand | SHA-256 | Prüfung |
|---|---|---|---|---|
| Integration | `FreshAirIQ-v0.26.5.0-CLEAN.zip` (925 Dateien) | dev `1934983` + diese Doku-Ergänzung | `abd949f7328f1d209459a297beec48f37f44e57a7bce1401d996d064401b3d8c` | regulärer Build (Gate PASS), entpackt: keine Cache-/Test-Reste, Versionen einheitlich 0.26.5.0, 2073 Tests, HA-Import-Smoke (2026.10.1), `node --check` |
| Diagnostics Hub | `FreshAirIQ-Hub-CLEAN.zip` (237 Einträge) | hub `a6a9304` | `1b1e1b2e452391b0ca67603b6d7b7320fab792794f4ce97298dfa2189c0e8098` | `--finalize` PASS (7 Stufen), Hygiene PASS, entpackt 423 Tests |

Version 0.26.5.1 (A-26 + alle Punkte dieses Branches, siehe docs/releases/RELEASE_NOTES_0.26.5.1.md); kein Tag/Release veröffentlicht. Erstbuild enthielt eine lokale Hilfsdatei
(`playwright.local-chromium.config.mjs`) – Builder packt den Arbeitsbaum, daher vor jedem Build `git status --ignored` prüfen.
