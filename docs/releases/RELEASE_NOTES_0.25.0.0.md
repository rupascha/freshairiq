# FreshAirIQ 0.25.0.0 – Release Hardening 1

Diese Version startet den verbindlichen Feature Freeze auf dem Weg zu FreshAirIQ 1.0. Sie erweitert den Funktionsumfang bewusst nicht, sondern macht Testbarkeit und Release-Gates strenger und reproduzierbar.

## Test- und Coverage-Härtung

- Die lokal ausführbare Pure-Logic-/Regression-Suite umfasst **569 Tests**.
- Der definierte Pure-Logic-Scope erreicht **100,00 % Line-Coverage: 4.744/4.744 Statements**.
- `.coveragerc-pure` erzwingt ab dieser Version **100 %**; ein Rückfall darunter lässt die CI fehlschlagen.
- Der kanonische Home-Assistant-CI-Lauf kombiniert die 100-%-Pure-Logic-Basis mit realen HA-Lifecycle-, Config-Flow-, Options-, Entity- und Integrationspfaden.
- Der v1-Coverage-Validator verlangt **mindestens 99 % kombiniert**, **mindestens 98 % für jedes einzelne Python-Integrationsmodul** und **100 % für `config_flow.py`**. FreshAirIQ strebt weiterhin 100 % an, soweit der Pfad sinnvoll testbar ist.
- Der Validator enumeriert die Python-Module aus `custom_components/freshairiq` selbst. Ein im Coverage-JSON fehlendes Modul wird damit nicht ignoriert, sondern als 0 % / Release-Fehler behandelt.

## Bereinigter Dead Code

Drei statisch unerreichbare Branches wurden entfernt, statt sie per Coverage-Ausnahme zu verstecken:

- `robustness.finite_int()`: unerreichbare Exception-Behandlung nach bereits erfolgreicher `finite_float()`-Normalisierung.
- `intervention`: unerreichbarer innerer Null-Guard, nachdem alle Aufrufer die Entity-ID bereits validiert haben.
- `planner`: unerreichbarer Fallback für eine leere Kandidatenliste; ein geschlossener Raum erzeugt konstruktiv immer mindestens den `now`-Kandidaten.

Diese Bereinigungen ändern kein beabsichtigtes Laufzeitverhalten.

## Unveränderte Fachlogik

Keine beabsichtigte Änderung an Lüftungsphysik, Forecast-Koeffizienten, Lernraten, QI-Entscheidungsgrenzen, Sensorprioritäten oder Dashboard-Verhalten.

## Noch offene v1-Gates

- Die **kanonische reale Home-Assistant-Runtime-Coverage ist lokal noch nicht belegt**, weil in der vorhandenen Offline-Umgebung das echte Home-Assistant-Testpaket nicht installiert ist und nicht nachinstalliert werden konnte. Der GitHub-CI-Job ist dafür jetzt als hartes Gate vorbereitet.
- Browser-E2E auf iPhone/iPad-WebView, Android-WebView, Chromium und Firefox bleibt offen.
- Strict-Typing-Gate gegen den echten Home-Assistant-Typbestand bleibt offen.
- Fremdhaushalt-Beta 10 → 25 → mindestens 50 Installationen bleibt vor 1.0 offen.

Daher ist 0.25.0.0 bewusst **kein** 1.0-Release, sondern der erste Release-Hardening-Meilenstein.
