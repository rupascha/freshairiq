# FreshAirIQ 0.25.0.34 – Maximum Hardening Hotfix

## Ziel

Dieser Hotfix härtet ausschließlich Abschluss-, Diagnose- und Android-Randfälle. Die in 0.25.0.33 stabilisierte Mess- und Lernlogik wird **nicht neu entworfen**.

## Abschluss einer Lüftung

- Der Best-Effort-Refresh nach dem letzten geschlossenen Fenster bleibt eine Qualitätsverbesserung, keine Pflichtbedingung.
- Bleibt eine neue Rückmeldung aus, aber der aktuell gehaltene Temperatur-/Feuchte-/Referenzwert ist numerisch verwendbar, wird die Session normal abgeschlossen. Ein fehlender Refresh verwirft die Messung **nicht**.
- Ist ein benötigter Wert beim Ablauf der maximal 10-s-Abschlusswartezeit tatsächlich `unavailable`, verwendet FreshAirIQ als Verfügbarkeits-Failsafe den letzten gültigen numerischen Klimazustand, der bereits während derselben Session beobachtet wurde.
- Dieser Fallback erhöht weder Temperatur- noch Feuchte-Reportzähler und erzeugt keine Timestamp-Evidenz. Der bestehende strikte In-Session-Gate bleibt alleinige Lernfreigabe.
- Existiert auch kein solcher Session-Snapshot, endet der Vorgang deterministisch als *nicht ausreichend gemessen*. Dauer und Vorgang bleiben erhalten; Feuchteergebnis, physikalisches Lernen, Forecast-Kalibrierung und vertrauenswürdige Repeat-Baseline bleiben unbekannt/gesperrt.

## Unveränderte Mess-/Lernregeln

- Mindestens eine neue Temperaturmeldung **und** eine neue Feuchtemeldung während der konkreten Lüftung bleiben Voraussetzung für physikalisches Lernen.
- `good` bleibt mit 0,75 gewichtet; `high` bleibt 1,0.
- Ein frischer Abschluss-Refresh kann die Qualität verbessern, aber fehlende In-Session-Evidenz niemals rückwirkend ersetzen.
- Feuchtephysik, Forecast-Koeffizienten, Grenzwerte und Lernformeln wurden nicht verändert.

## Diagnostics / Hub

- Bewohnernamen werden nun sowohl aus Listen als auch aus der real verwendeten kommagetrennten String-Konfiguration erkannt und in Diagnose-Freitexten anonymisiert.
- Bekannte Software-Versionsfelder werden nicht mehr durch die IPv4-Erkennung geschwärzt; echte IP-Adressen in normalen Diagnosefeldern bleiben redigiert.
- `resident_profile_count` zählt normalisierte Bewohnernamen statt String-Zeichen.
- Diagnostics-HA-/Hub-Protokolle und Endpunkte bleiben kompatibel; keine Schemaänderung.

## Android / UI

- Der Android-WebView-Test enthält jetzt `meta viewport` und prüft zusätzlich `window.innerWidth` sowie `documentElement.clientWidth` gegen 360/412/600/800 CSS-Pixel.
- Nicht ausreichend gemessene Sessions erzeugen keine irreführende Abschlussmeldung „0 ml entfernt“.

## Kompatibilität

Keine absichtliche Änderung an bestehenden Konfigurationsfeldern, Entity-Verträgen, Storage-Migrationen, Diagnose-Schemas oder Hub-Transportpfaden.
