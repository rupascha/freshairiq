# FreshAirIQ

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/freshairiq-branding-official.png" alt="FreshAirIQ – Intelligent Home Climate" width="720">
</p>

<p align="center"><strong>Dein Zuhause kann dir sagen, wann Lüften wirklich sinnvoll ist.</strong></p>

FreshAirIQ ist eine Home-Assistant-Integration für intelligente, nachvollziehbare Lüftungsentscheidungen. Statt nur Luftfeuchtigkeit anzuzeigen, verbindet FreshAirIQ **absolute Feuchte, Wassermenge in der Raumluft, Innen-/Außenklima, Raumvolumen, Fensterzustände, Wetter, Temperaturentwicklung, Anwesenheit und gelerntes Gebäudeverhalten** zu einer konkreten Empfehlung.

**Warten → Lüften → Weiterlüften → Schließen.** Für einzelne Räume, Etagen oder das ganze Haus.

> [!IMPORTANT]
> ## 🧪 Öffentliche Beta
> FreshAirIQ startet in die öffentliche Beta. Gesucht werden zunächst rund 20 deutschsprachige Home-Assistant-Haushalte mit unterschiedlichen Gebäuden, Sensoren und Lüftungsgewohnheiten. Feedback und Fehler können direkt aus FreshAirIQ an den Diagnose-Hub gesendet werden.
>
> **Beta-Diagnostik:** Bei dieser Beta ist die pseudonymisierte automatische Diagnoseübertragung standardmäßig auf **„Täglich nachts“** gesetzt. Der grobe **Geräte-/Browser-Kontext** ist standardmäßig **aktiv**, um Android-, iOS-, Browser- und Darstellungsprobleme unterscheiden zu können. Beide Einstellungen können jederzeit unter **FreshAirIQ → Energie & Daten → Diagnose-Freigabe** geändert oder deaktiviert werden. Direkte Identifikatoren wie Bewohnernamen, Entity-IDs, IP-Adressen, E-Mail-Adressen und URLs werden vor der Übertragung entfernt oder pseudonymisiert.

---

## FreshAirIQ in Aktion

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/01-house-ventilation.jpeg" alt="FreshAirIQ Hauslüftung mit Live-Prognose" width="520">
</p>

### Eine Entscheidung statt einer Wand aus Messwerten

FreshAirIQ bewertet die aktuelle Situation fortlaufend und formuliert eine zentrale Handlungsempfehlung. Während einer Lüftung zeigt die Karte, **wie viel Feuchtigkeit bereits entfernt wurde**, welchen zusätzlichen Nutzen die nächsten Minuten voraussichtlich bringen, wie sich die Temperatur entwickelt und wann der sinnvolle Endpunkt erreicht ist.

Die Begründung bleibt sichtbar: Schwellenwerte, erwarteter Nettoeffekt, gelernte Muster und Prognosesicherheit werden nicht hinter einem undurchsichtigen „KI sagt …“ versteckt.

---

## Was FreshAirIQ besonders macht

| Funktion | Was FreshAirIQ daraus macht |
| --- | --- |
| **Absolute Feuchte & Wasserbilanz** | Rechnet Feuchte in g/m³ und – zusammen mit dem Raumvolumen – in verständliche ml Wasserdampf um. |
| **Dynamische Lüftungsempfehlung** | Entscheidet nicht nur anhand eines starren RH-Grenzwerts, sondern bewertet den tatsächlich erwartbaren Nutzen. |
| **Raum-, Etagen- & Hauslüftung** | Erkennt, ob einzelne Räume oder mehrere aktive Räume sinnvoll gemeinsam betrachtet werden sollten. |
| **Live-Bilanz** | Verfolgt die reale Feuchte- und Temperaturänderung während einer Lüftung. |
| **Kurzzeitprognose** | Simuliert 5–120 Minuten und schätzt den effizienten Endpunkt innerhalb des Prognosefensters. |
| **Nachtstrategie** | Prognostiziert die Entwicklung bis zum Nachtende und berücksichtigt Belegung, Außenluft und gelernte Nachtmuster. |
| **Schimmel-IQ** | Liefert einen konservativen Oberflächen-RH-Indikator und macht auffällige Räume sichtbar. |
| **Energie & Kosten** | Schätzt Temperaturverlust und Wiederaufheizenergie passend zum konfigurierten Heizsystem. |
| **Anwesenheit & Gäste** | Passt Feuchteprognosen an erwartete Belegung und Übernachtungsgäste an. |
| **Zusatzsensoren** | Kann CO₂, VOC/TVOC, PM2.5, Pollen, Helligkeit, Wind und weitere Kontextdaten einbeziehen. |
| **Erklärbare Entscheidungen** | Zeigt Gründe, Datenqualität, Lernstand und Prognosesicherheit statt nur eines Ergebnisses. |
| **Persistentes Lernen** | Lernt reale Raumwirkung und Routinen aus geeigneten Beobachtungen, ohne deine Grenzwerte heimlich umzuschreiben. |

---

## Jeder Raum hat seine eigene Physik

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/02-room-overview.jpeg" alt="FreshAirIQ Raumübersicht" width="520">
</p>

FreshAirIQ betrachtet Räume nicht als identische Kästchen. Volumen, Sensorwerte, Fenster, Ausrichtung, gelernter Luftwechsel und bisherige Lüftungsergebnisse werden raumbezogen geführt. Dadurch kann ein kleines Gäste-WC anders reagieren als eine große Wohnküche oder ein Kellerraum.

Die Raumansicht bündelt unter anderem Raumklima, absolute Feuchte, Wassermenge, Schimmelindikator und Lernstatus. Räume können auch als reine Beobachtungsräume geführt werden, ohne die Hausentscheidung zu beeinflussen.

---

# FreshAirIQ Intelligence 2.0

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/03-intelligence-overview.jpeg" alt="FreshAirIQ Intelligence 2.0 Lernübersicht" width="520">
</p>

FreshAirIQ trennt bewusst **Erfahrungsreife** von **Prognosequalität**. Viele Messpunkte allein machen ein Modell nicht automatisch gut. Deshalb zählt FreshAirIQ unabhängige Tage, Lüftungen und belastbare Ergebnisvergleiche und zeigt separat, wie gut Vorhersagen bisher zur Realität passen.

### Vier Lernbereiche

**Dein Zuhause** lernt Raumphysik, Feuchtepuffer und hausweite Lüftungsstrategien. **Prognosen & Lernen** korrigiert Live-Prognosen, vergleicht Forecasts mit realen Ergebnissen und lässt alternative Shadow-Modelle parallel antreten. **Deine Gewohnheiten** erkennt Tagesroutinen, umgesetzte Strategien und persönlichen Kontext. **Langzeitlernen** sammelt Nacht- und Saisonerfahrung bewusst langsam über echte unterschiedliche Tage und Jahreszeiten.

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/05-learning-home.jpeg" alt="FreshAirIQ lernt Raumphysik und Feuchtepuffer" width="430">
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/06-learning-forecast.jpeg" alt="FreshAirIQ Prognosen und Shadow-Lernen" width="430">
</p>

### Lernen muss messbar besser werden

FreshAirIQ validiert das gelernte Prognosemodell gegen reale Ergebnisse und gegen ein eingefrorenes Grundmodell. Modellgenerationen können unter vergleichbaren Bedingungen gegeneinander replayt werden. MAE, Richtungsgenauigkeit, unabhängige Lüftungen, unterschiedliche Tage und statistische Unsicherheit bleiben sichtbar.

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/04-model-quality.jpeg" alt="FreshAirIQ Modellqualität und Diagnose" width="520">
</p>

Das Lernsystem darf eine Verbesserung nicht einfach behaupten: Für belastbare Lernwirkung sind mehrere unabhängige Lüftungen an unterschiedlichen Tagen und konservative Evidenzregeln erforderlich.

---

## Feuchtigkeit wird greifbar

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/07-water-balance.jpeg" alt="Wasser in der Hausluft nach Räumen" width="520">
</p>

Relative Luftfeuchtigkeit ist temperaturabhängig und allein oft schwer zu interpretieren. FreshAirIQ berechnet zusätzlich die **absolute Feuchte** und die daraus resultierende **Wassermenge in der Raumluft**. Dadurch lässt sich nachvollziehen, wo Feuchtigkeit sitzt und wie viel durch eine Lüftung voraussichtlich tatsächlich entfernt werden kann.

In der FreshAirIQ-Oberfläche gilt konsequent: **Minus = Feuchtigkeit wird entfernt**, **Plus = Feuchtigkeit kommt hinzu**.

---

## Schimmel-IQ – ein Frühindikator, keine Laboranalyse

<p align="center">
  <img src="https://raw.githubusercontent.com/rupascha/freshairiq/main/docs/screenshots/08-mould-iq.jpeg" alt="FreshAirIQ Schimmel-IQ" width="520">
</p>

FreshAirIQ schätzt aus dem verfügbaren Raumklima eine konservative Oberflächen-RH und hebt auffällige Räume hervor. Das hilft, längerfristig problematische Klimabedingungen zu erkennen. Ohne tatsächlich gemessene Oberflächentemperatur an einem konkreten Bauteil kann FreshAirIQ jedoch **kein reales Schimmelwachstum feststellen oder ausschließen**.

---

## Weitere Funktionen

FreshAirIQ unterstützt frei definierbare Stockwerke und Räume, mehrere Fenster-/Türkontakte je Raum, Öffnungsverzögerungen, Fensterausrichtung und Windkontext, alternative Außen-/Referenzluft, Pollen-Veto, CO₂-Kontext, VOC/TVOC, PM2.5 und Helligkeit. Bewohner können mit `person.*`/`device_tracker.*` verknüpft werden; Kinder oder andere Personen ohne Tracker bleiben unterstützt. Ein schneller Gästemodus passt Kurzzeit- und Nachtprognosen unmittelbar an.

Für Energieabschätzungen können Wärmepumpe, Gas, Heizöl, Fernwärme oder Direktstrom mit den jeweils relevanten Parametern konfiguriert werden. Optional konfigurierte Aktoren führen **nicht automatisch** zu autonomer Steuerung: FreshAirIQ bleibt standardmäßig empfehlungsorientiert und führt nur explizit freigegebene, eindeutig abbildbare Interventionen aus.

---

# Beta installieren

## Voraussetzungen

- Home Assistant **2026.8.0 oder neuer**
- HACS für die empfohlene Installation
- Für berechnete Räume: Temperatur, relative Luftfeuchtigkeit, Raumvolumen und mindestens ein Fenster-/Türkontakt
- Außenreferenz: eine lokale `weather.*`-Entität **oder** Außen-Temperatur + Außen-Luftfeuchtigkeit

## Installation über HACS

1. Öffne **HACS → Custom repositories**.
2. Füge `https://github.com/rupascha/freshairiq` als Repository vom Typ **Integration** hinzu.
3. Installiere **FreshAirIQ**.
4. Starte Home Assistant neu.
5. Öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen → FreshAirIQ**.
6. Räume, Sensoren und weitere Optionen können anschließend über **Geräte & Dienste** oder das FreshAirIQ-Zahnrad eingerichtet werden.

> FreshAirIQ lässt sich zunächst auch ohne fertiges Raumsetup hinzufügen. Solange erforderliche Klimadaten fehlen, werden Berechnungen zurückgehalten statt Werte zu erfinden.

## Manuelle Installation

Kopiere `custom_components/freshairiq` vollständig nach `/config/custom_components/freshairiq`, starte Home Assistant neu und füge FreshAirIQ anschließend unter **Einstellungen → Geräte & Dienste** hinzu.

---

# Für Betatester

Wir suchen reale Vielfalt statt möglichst vieler Installationen: Wohnungen und Häuser, Keller, unterschiedliche Sensorhersteller, kleine und große Setups, Android, iOS und Browser. Besonders hilfreich sind Rückmeldungen zu **Ersteinrichtung, Verständlichkeit der Empfehlungen, Prognoseverhalten, Lernfortschritt, mobilen Ansichten und ungewöhnlichen Gebäudesituationen**.

### Diagnose & Datenschutz in der Beta

FreshAirIQ zeichnet lokal eine begrenzte technische Diagnosehistorie auf. In dieser öffentlichen Beta ist die automatische pseudonymisierte Übertragung standardmäßig **täglich nachts** aktiv und zeitlich pro Installation verteilt. Der grobe Geräte-/Browser-Kontext ist standardmäßig aktiv. Beides ist jederzeit abschaltbar.

Vor dem Upload werden direkte Identifikatoren entfernt oder pseudonymisiert. Die Diagnose ist für technische Analyse, Forecast-/Lernvalidierung und Kompatibilitätsfehler gedacht – nicht für Werbung oder Profilbildung. Freitext-Feedback wird nur übertragen, wenn du es ausdrücklich absendest.

---

# Technische Grundsätze

FreshAirIQ ist geräteherstellerunabhängig und arbeitet mit Home-Assistant-Entitätssemantik. Die kanonische Lüftungsphysik basiert auf psychrometrischen Größen und bleibt von optionalen Zusatzsensoren getrennt. Sensorlatenz, Datenqualität und Messaktualisierung werden berücksichtigt; ungeeignete Lernmessungen sollen nicht als belastbare Erfahrung eingehen.

Das Projekt enthält ein Continuous Quality System mit Pure-Logic-Tests, Frontend-/Contract-Tests, Release-Hygiene und GitHub/HACS-Release-Gates. Ein Release-ZIP wird erst nach den vorgesehenen Quality Gates erzeugt.

### Lokale Qualitätsprüfung

```bash
python tools/quality_gate.py --profile local
python tools/build_release.py
```

### Update

Bei HACS-Installationen werden veröffentlichte GitHub-Releases als Updatequelle verwendet. Release-Tag und `custom_components/freshairiq/manifest.json` müssen dieselbe Version tragen. Lern- und Verlaufsdaten liegen getrennt im Home-Assistant-Storage und bleiben bei normalen Updates erhalten.

### Entfernen

Lösche zuerst den FreshAirIQ-Integrationseintrag unter **Einstellungen → Geräte & Dienste** und starte Home Assistant anschließend neu. Bei manueller Installation kann danach `/config/custom_components/freshairiq` entfernt werden.

---

## ☕ FreshAirIQ unterstützen

FreshAirIQ ist ein unabhängiges Open-Source-Projekt. Wenn dir FreshAirIQ gefällt und du die Weiterentwicklung freiwillig unterstützen möchtest, kannst du mir einen Kaffee ausgeben:

**[☕ Buy me a coffee – FreshAirIQ](https://buymeacoffee.com/freshairiq)**

Feedback, Fehlermeldungen und Beta-Tests sind genauso wertvoll und ausdrücklich willkommen.

---

## Projektstatus

**FreshAirIQ · Public Beta**

FreshAirIQ befindet sich aktiv in Entwicklung. Prognosen und Empfehlungen sind Entscheidungshilfen für das Raumklima und ersetzen keine fachliche Gebäude-, Schimmel-, Gesundheits- oder Sicherheitsdiagnostik.

Entwickelt von **rupascha** für Home Assistant.
