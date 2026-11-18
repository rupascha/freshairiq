# IQ2 – Prognose-, Lern- und Entscheidungsmodell (ab 0.26.7.1)

Stand 16.11.2026. IQ2 ist der aktive Pfad der Integration (kein Schattenmodell): Raumentscheidung, Prognose, Lernen,
beide Karten und die Benachrichtigungen lesen denselben Stand. Dieses Dokument beschreibt das Modell, seine Parameter
und Annahmen, die Migration, den Vergleich mit den älteren Ständen und die Grenzen der Aussagen.

## 1. Was sich für Nutzer ändert

| Thema | bis 0.26.7.1 (vor IQ2) | mit IQ2 |
|---|---|---|
| Schließen bei erreichtem Ziel | nur wenn je Raum gewählt; sonst weiterlüften, solange die Außenluft trockener ist | Standard: schließen, sobald die aktiven Ziele des Raums verlässlich erreicht sind. Wahlweise je Raum „Weiterentfeuchten, solange die Außenluft Feuchte abführt“ |
| Hausempfehlung bei erreichtem Ziel | konnte „Noch nicht schließen“ zeigen, obwohl die Räume „Ziele erreicht“ meldeten | folgt dem Zielabschluss der Räume |
| Hauptwert „Weitere N min“ | am Feuchteziel begrenzt (bei erreichtem Ziel 0 ml) | erwartete Netto-Änderung der Raumluft; „bis zum Feuchteziel noch“ ist ein eigener Wert |
| Temperaturprognose | Raumluft nähert sich ungebremst der Außentemperatur | thermische Masse des Raums berücksichtigt |
| „Prognosesicherheit 100 %“ | Zahl der Lernbeispiele | heißt „Lernreife“; die Prognosegüte ist ein eigener, kalibrierter Erwartungsbereich oder „wird kalibriert“ |
| Restzeit je Raum (Hauskarte) | aus altem Plan nachgerechnet | von der Integration je Raum geliefert (`time_state`) |
| Lüfter-Automatik | lief bis zur Maximaldauer, solange die Luft trocknete | stoppt mit dem Standard bei erreichtem Feuchteziel; mit „Weiterentfeuchten“ wie bisher |

Unverändert: Entity-IDs, Dienste, Ereignisse, Optionen und Schwellen. Die Schutzregeln behalten ihren Vorrang
(kritisches CO₂, kritisches Schimmelrisiko, Temperaturgrenze, hereinkommende Feuchte, aktive Feuchtequelle).

## 2. Modell

### 2.1 Raumluft mit Puffer

Reduzierte Ein-Zonen-Bilanz nach der Zonen-Feuchtebilanz von EnergyPlus (Quellen, Oberflächenaustausch, Lüftung;
analytische Exponentiallösung). Die Raumluft läuft gegen ein Gleichgewicht aus Außenluft und dem Puffer des Raums
(Oberflächen, Möbel, Nachbarräume):

    A_gl = s · A_außen + (1 − s) · A_Anker        A(t) = A_gl + (A(0) − A_gl) · (1 − r)^(t / s)

`r` ist die Luftwechselrate je Minute, `s` der Luftanteil (0 < s ≤ 1), `A_Anker` der Raumzustand beim Öffnen. Für
`s = 1` ist das genau das bisherige Exponentialmodell. Dieselbe Form gilt für die Temperatur (thermische Masse) mit
eigenem Anteil. Vorwärtsmodell und Rückrechnung sind konsistent: die frühere lineare Rückrechnung
(`Abnahme / Differenz / Minuten`) ließ dieselbe echte Rate bei längerer Lüftung kleiner erscheinen
(0,0296 → 0,0279 / 0,0226 / 0,0139 bei 5 / 20 / 60 Minuten); jetzt ergibt jede Dauer 0,0296.

Verworfen, weil aus einem Endpunkt je Lüftung nicht bestimmbar: mehrschichtige Puffermodelle (EMPD mit Oberflächen-
und Tiefenschicht) und größere ML-Modelle. Reine Ablüfter-Lüftung (Fenster zu) behält ihr eigenes Abluftmodell.

### 2.2 Lernen

* Hierarchie: mitgelieferter Startwert → Haus → Raum und Lüftungsart (allgemein, offen, gekippt, quer). Ein neuer
  Raum in einem gelernten Haus startet beim Hauswert; mit eigenen Lüftungen zählt zunehmend der Raum selbst.
* Eine gültige Lüftung = eine begrenzte Stimme (höchstens Faktor 2 gegenüber dem aktuellen Stand). Parallel gelüftete
  Räume zählen fürs Haus zusammen als eine Stimme. Häufiges Abfragen ist kein zusätzlicher Beleg.
* Der Prognosefehler einer Lüftung wird auf Rate und Luftanteil nach ihrer Empfindlichkeit verteilt (normierter
  Kleinste-Quadrate-Schritt): eine kurze Lüftung lehrt die Rate, eine Lüftung am Plateau den Luftanteil.
* Gedächtnis: 12 gewichtete Lüftungen. Ältere Stimmen klingen aus, der Startwert verliert mit eigener Erfahrung sein
  Gewicht. So kann ein Raum sich auch nach Jahren noch ändern (neue Fenster, Möbel).
* Gelernt wird nur aus Lüftungen, die die bestehenden Qualitätsregeln bestehen (frische, zeitgleiche Messwerte, keine
  innere Feuchtequelle, stabile Referenz). Eine Lüftung, in der der Raum feuchter wurde, wird bewertet, lehrt aber
  keinen Luftwechsel.
* Das frühere Lernen läuft als Referenz weiter. Vorhandene gelernte Raten starten IQ2 als schwacher Beleg
  (höchstens drei Lüftungen Gewicht), weil sie mit der alten Rückrechnung entstanden sind.

### 2.3 Prognosegrößen (getrennt, additiv)

| Feld (Raum und Haus) | Bedeutung |
|---|---|
| `forecast_net_room_change_ml` | erwartete Netto-Änderung des Wasserdampfs in der Raumluft im Horizont – Hauptwert |
| `forecast_outdoor_transport_ml` | modellierter Transport nach außen (nicht gemessen; größer als die Netto-Änderung, weil der Puffer nachliefert) |
| `forecast_to_target_ml` | Menge bis zum Feuchteziel; 0 = Ziel erreicht; leer = kein Ziel bekannt |
| `forecast_interval_ml` | Erwartungsbereich der Netto-Änderung; leer, solange nicht kalibriert |
| `forecast_quality` / `forecast_quality_state` | `collecting` (weniger als 8 bewertete Lüftungen) oder `calibrated`, Zahl der Vergleiche |
| `iq2` (Raum) | Modellkennung, Lernstufe (`global`, `house`, `room`, `fallback`, `rollback`), Rate, Anteile |
| `time_state`, `time_remaining_min` (Raum) | `close`, `countdown`, `minimum` (eigene Mindestdauer), `reassessing`; leer ohne Lüftung |

Die bisherigen Felder (`forecast_moisture_effect_ml` = zielbegrenzt, `forecast_uncapped_moisture_effect_ml`) bleiben
erhalten. Eine zielbegrenzte 0 ist kein Beleg, dass Lüften nichts bringt, und führt allein nie zum Schließen.

Wetter: Verwendet ein Raum die Außen-/Wetterreferenz, rechnet die Prognose mit dem stündlichen Vorhersagepfad,
interpoliert auf 5-Minuten-Schritte und an der lokalen Messung verankert. Ein Wetterumschwung nach 30 Minuten ändert
den 60-Minuten-Wert, nicht den 5-Minuten-Wert.

### 2.4 Prognosegüte

Jede Lüftung wird vor dem Lernen gegen die Prognose bewertet, die mit dem Stand davor gemacht wurde. Der
Erwartungsbereich folgt der adaptiven konformen Kalibrierung (Gibbs/Candès): er wird nach einem Treffer schmaler, nach
einem Fehlgriff breiter, sodass im Langzeitmittel etwa 80 % der Lüftungen im Bereich liegen. Das ist eine Aussage
über viele Lüftungen über die Zeit, keine Wahrscheinlichkeit für die einzelne Prognose. Angezeigt wird der Bereich
erst nach 8 bewerteten Lüftungen; vorher steht „wird kalibriert“ – nie eine Prozentzahl aus der Beispielanzahl.

Rückfall: Sind die eigenen bewerteten Prognosen eines Raums deutlich schlechter als die des Referenzmodells
(ab 6 Vergleichen, mehr als 25 % plus 5 ml), rechnet der Raum mit der Referenzrate ohne Pufferanteil
(Stufe `rollback`), bis IQ2 wieder gleichauf ist. Die Zielentscheidung, die Zeitbedeutung und die getrennten Größen
gelten auch im Rückfall – die früheren Widersprüche kehren damit nicht zurück.

## 3. Parameter und ihr Status

Keiner dieser Werte ist an Felddaten kalibriert. Es sind begründete Startannahmen; die Lernregeln sollen sie je Raum
ersetzen.

| Parameter | Wert | Herkunft / Status |
|---|---:|---|
| Luftanteil Feuchte, Startwert (Minimum) | 0,5 (0,1) | Annahme: hygroskopische Pufferung ist in Wohnräumen erheblich (ASHRAE, EnergyPlus EMPD). Nicht feldkalibriert |
| Luftanteil Temperatur, Startwert (Minimum) | 0,15 (0,02) | Annahme: die gemessene Raumluft kühlt beim Lüften nur um einen Bruchteil der Außendifferenz ab, weil Wände und Einrichtung Wärme nachliefern (EnergyPlus-Zonenbilanz). Nicht feldkalibriert |
| Gewicht Startwert Raum / Haus / Anteil | 8 / 6 / 6 Lüftungen | aus dem Forschungsprototyp übernommen, klingt mit eigener Erfahrung aus |
| Gedächtnis | 12 Lüftungen | entspricht der bisherigen Langzeitglättung (0,08); auf Entwicklungs-Simulationen geprüft |
| Stimme je Lüftung | höchstens Faktor 2 | Einflussgrenze gegen Ausreißer |
| Altes Lernen als Startbeleg | 0,5 je Beispiel, höchstens 3 | Annahme (alte Raten sind durch die lineare Rückrechnung verzerrt) |
| Erwartungsbereich | Ziel 80 %, ab 8 Vergleichen | Verfahren nach Gibbs/Candès; Abdeckung siehe Abschnitt 5 |
| Rückfall | ab 6 Vergleichen, Faktor 1,25 + 5 ml | Annahme |
| Lernbereich Rate | 0,002 … 0,25 je Minute | wie bisher |

## 4. Standard, Migration, Speicherung

* Schließstrategie: nichts gewählt = „Schließen, wenn die Ziele erreicht sind“. Testbuilds haben den damaligen
  Standard `continue_while_drying` bei jedem Speichern des Raums mitgeschrieben; ein gespeicherter alter Standard ist
  deshalb keine bewusste Wahl und gilt als „nichts gewählt“. Wer weiterentfeuchten will, wählt im Raum
  „Weiterentfeuchten, solange die Außenluft Feuchte abführt“ (`keep_drying`).
* Neuer Raumspeicher `iq2` (Schema 1) und Hausspeicher `iq2_house`; beim ersten Lauf aus dem bisherigen Lernen
  angelegt. Fehlt der Stand (ältere Daten, Wiederherstellung), startet der Raum beim Start-/Hauswert. Unbekannte
  Schemata werden verworfen, nichts wird gelöscht, die bisherigen Lernfelder bleiben erhalten. Keine
  Speicherversions-Änderung: ein Rückwechsel auf einen älteren Stand lädt weiterhin.
* `session_goals_reached` hält fest, dass die Ziele in dieser Lüftung erreicht wurden – auch wenn im selben Zyklus die
  Temperaturgrenze der genannte Schließgrund war. Der Speicher wächst nicht: Zähler und Summen, keine Listen.
* Sitzungsdatensatz: zusätzlich `iq2` (Bericht der Lüftung) und `learning_observation.rate_inversion = "exponential"`.
  Hub und Diagnostics HA lesen die bestehenden Felder unverändert.

## 5. Vergleich .6 / .7.0 / .7.1 / IQ2

Werkzeug: `tools/iq2_compare.py`. Jeder Stand läuft im eigenen Prozess mit seinem tatsächlichen Code
(`forecast.horizon_forecast`, `model.update_learning`, `model.evaluate_room`, bei IQ2 zusätzlich `iq2`), auf denselben
synthetischen Häusern: gleiche Startwerte, Zeitpunkte, Volumina, Quellen, Wetterbasis. Die Startprognose bekommt nur
Startwerte (keinen Endwert, keinen späteren Außenwert), wird gegen die simulierten Sensorwerte bewertet, danach lernt
das Modell aus der Lüftung. Bewertet wird die ungekappte Netto-Feuchteänderung – für die älteren Stände also ihr
physikalischer, nicht ihr zielbegrenzter Wert.

Die simulierte Wirklichkeit ist bewusst reicher als jedes der Modelle: zwei Feuchtepuffer, Wandknoten, Quellen in 15 %
der Lüftungen, Wetterdrift, von Lüftung zu Lüftung schwankender Luftwechsel, Sensorträgheit, Quantisierung, Rauschen,
Raumänderung zur Halbzeit in der Hälfte der Häuser. Entwickelt wurde auf den Seeds 1–3; die Zahlen unten stammen aus
den getrennten Testhäusern (Seed 20261116, 30 Häuser, 6 054 Lüftungen), die erst nach dem Einfrieren des Modells
gerechnet wurden. Gewichtung: jedes Haus zählt gleich.

    python3 tools/iq2_compare.py --tree v0.26.6.0=<Baum> --tree v0.26.7.0=<Baum> --tree "v0.26.7.1 vor IQ2=<Baum>" \
        --tree IQ2=. --seed 20261116 --houses 30 --airings 120

(Bäume der älteren Stände: `git archive <Tag> custom_components/freshairiq tests/conftest.py`; .7.1 vor IQ2 = das
ausgelieferte Paket vom 15.11.2026.)

### 5.1 Netto-Feuchteänderung

| Horizont | Fälle | .6 / .7.0 / .7.1 MAE (Bias) | IQ2 MAE (Bias) | Änderung (90 %-Bereich über Häuser) | naiv MAE | „keine Änderung“ MAE |
|---:|---:|---:|---:|---:|---:|---:|
| 5 min | 6054 | 12,06 (+5,36) ml | 11,18 (+7,84) ml | −7,3 % (−11,7 … −2,3) | 12,29 ml | 21,11 ml |
| 10 min | 4942 | 21,63 (+7,65) ml | 17,12 (+9,70) ml | −20,9 % (−24,5 … −16,9) | 20,18 ml | 41,73 ml |
| 15 min | 3840 | 26,99 (+10,88) ml | 20,03 (+10,65) ml | −25,8 % (−29,8 … −21,3) | 24,20 ml | 55,09 ml |
| 20 min | 3265 | 30,32 (+14,87) ml | 20,76 (+10,94) ml | −31,5 % (−36,4 … −26,6) | 24,65 ml | 64,37 ml |
| 30 min | 2194 | 34,51 (+21,96) ml | 19,02 (+9,40) ml | −44,9 % (−50,2 … −38,7) | 24,36 ml | 75,55 ml |
| 60 min | 1084 | 52,14 (+43,48) ml | 16,67 (+2,35) ml | −68,0 % (−72,0 … −63,0) | 34,77 ml | 97,30 ml |

Die drei älteren Stände liefern hier identische Zahlen: ihr ungekappter Prognose- und Lernpfad ist derselbe. „naiv“
nimmt für jeden Horizont den Anteil der letzten Lüftung desselben Raums. Der positive Bias bei kurzen Horizonten
(alle Modelle sagen etwas zu viel voraus) kommt in dieser Simulation vor allem aus der Sensorträgheit; IQ2 hat ihn
bei 5 und 10 Minuten etwas stärker als die älteren Stände.

### 5.2 Temperatur und Richtung

| Horizont | .6 / .7.0 / .7.1 Temp.-MAE | IQ2 Temp.-MAE | naiv | Richtungsfehler (alle Modelle gleich) |
|---:|---:|---:|---:|---:|
| 5 min | 0,50 °C | 0,33 °C | 0,33 °C | 10,1 % |
| 10 min | 0,94 °C | 0,42 °C | 0,50 °C | 8,9 % |
| 15 min | 1,51 °C | 0,49 °C | 0,59 °C | 7,4 % |
| 20 min | 2,20 °C | 0,53 °C | 0,63 °C | 6,1 % |
| 30 min | 3,56 °C | 0,53 °C | 0,67 °C | 3,4 % |
| 60 min | 6,61 °C | 0,59 °C | 0,91 °C | 1,3 % |

### 5.3 Kohorten (15 Minuten)

| Kohorte | Fälle / Häuser | .6–.7.1 MAE | IQ2 MAE | naiv MAE |
|---|---:|---:|---:|---:|
| erste 5 Lüftungen je Raum (Kaltstart, Hauswissen) | 314 / 30 | 37,43 ml | 28,32 ml | 36,81 ml |
| 6.–20. Lüftung | 922 / 30 | 29,15 ml | 20,27 ml | 22,75 ml |
| ab 21. Lüftung | 2604 / 30 | 24,79 ml | 18,79 ml | 23,25 ml |
| mit Feuchtequelle | 568 / 30 | 70,24 ml | 67,85 ml | 66,81 ml |
| ohne Feuchtequelle | 3272 / 30 | 19,27 ml | 11,54 ml | 16,62 ml |
| Raum < 25 m³ | 762 / 15 | 16,53 ml | 13,84 ml | 16,21 ml |
| Raum 25–40 m³ | 1570 / 22 | 26,12 ml | 20,62 ml | 24,62 ml |
| Raum > 40 m³ | 1508 / 23 | 32,25 ml | 22,26 ml | 27,14 ml |
| Winter | 2880 / 30 | 29,05 ml | 21,12 ml | 25,80 ml |
| Sommer | 960 / 30 | 20,90 ml | 16,92 ml | 19,71 ml |
| nach Änderung des Raums | 324 / 16 | 30,16 ml | 22,93 ml | 19,20 ml |
| parallele Räume | 2284 / 30 | 27,39 ml | 20,40 ml | 23,84 ml |

Keine Kohorte ist mit IQ2 schlechter als mit den älteren Ständen. Zwei Schwächen bleiben sichtbar: Mit aktiver
Feuchtequelle ist die Startprognose aller Modelle schlechter als „keine Änderung“ (55,8 ml) – die Quelle ist beim
Öffnen nicht bekannt. Nach einer Raumänderung lernt IQ2 schneller nach als die älteren Stände, aber langsamer als das
naive Vergleichsmodell.

### 5.4 Erwartungsbereich (nur IQ2)

| Horizont | Abdeckung | mittlere Breite | Fälle |
|---:|---:|---:|---:|
| 5 min | 69,2 % | 21,6 ml | 4971 |
| 10 min | 72,1 % | 33,5 ml | 4062 |
| 15 min | 75,2 % | 43,7 ml | 3148 |
| 20 min | 76,9 % | 52,1 ml | 2678 |
| 30 min | 82,0 % | 61,9 ml | 1824 |
| 60 min | 88,0 % | 74,6 ml | 905 |

Kalibriert wird am Endpunkt jeder Lüftung über ihre tatsächliche Dauer. Bei kurzen Horizonten ist der Bereich in
dieser Simulation zu schmal (69–77 % statt 80 %), bei langen zu breit. Die Karten nennen deshalb keinen Prozentwert.

### 5.5 Raumentscheidung (einziges Ziel: Entfeuchten auf 58 %)

Referenz sind konfigurierte Ziele und beobachtbare Zustände – nicht, wie lange jemand gelüftet hat.

| Kennzahl (Mittel je Lüftung, hausgleich) | .6 | .7.0 | .7.1 vor IQ2 | IQ2 | Fälle |
|---|---:|---:|---:|---:|---:|
| „Schließen“, obwohl Ziel offen (> 60 %), Außenluft klar trockener, keine Quelle, kein Erwärmungsfall | 43,0 % | 0,4 % | 0,4 % | 0,4 % | 6054 |
| Minuten Weiterlüften nach verlässlich erreichtem Ziel | 1,0 | 22,4 | 22,4 | 0,0 | 1422 |
| Ziel erreicht, bis zum Ende nie „Schließen“ | 3,7 % | 84,9 % | 84,9 % | 0,0 % | 1422 |
| zurückgenommenes „Schließen“ je Lüftung | 0,084 | 0,008 | 0,008 | 0,021 | 6054 |
| Zyklen unter der Temperaturgrenze (16 °C) ohne „Schließen“, kein kritisches Schimmelrisiko | – (Option gab es nicht) | 0 | 0 | 0 | 599 |

Lesehilfe: .6 schloss wegen Zeit/Effizienz oft, obwohl das Ziel offen war (der mit F11 behobene Fehler). .7.x lüftete
nach erreichtem Ziel weiter – damals die gewählte Regel, mit IQ2 laut Entscheidung vom 15.11.2026 nicht mehr der
Standard. Die 0,4 % frühes Schließen sind in allen drei neueren Ständen dieselben 23 Grenzfälle: die
Außenluft war nur noch 0,4–0,5 g/m³ trockener (Schließgrund „Außenluft hilft nicht mehr“, Schwelle 0,4 g/m³). IQ2 nimmt ein „Schließen“ etwas häufiger zurück als .7.x, weil es häufiger
eines ausspricht (Ziel erreicht, Feuchte steigt später über Ziel + 2 %).

Der Widerspruch auf Hausebene (Räume „Ziele erreicht“, Haus „Noch nicht schließen“) ist nicht Teil dieses Werkzeugs;
er ist über den echten Koordinator in `tests/test_iq2_decisions_02671.py` (P1) geprüft.

## 6. Grenzen der Aussagen

* Kein Feldnachweis. Alle Zahlen stammen aus Simulationen; echte Häuser, Sensoren und Nutzer sind nicht enthalten.
  Die Größenordnung der Verbesserung (z. B. −26 % bei 15 Minuten) ist damit für reale Installationen nicht belegt.
  Das Qualitätsziel „mindestens 10 % bessere hausgleichgewichtete Feuchte-MAE“ ist in der Simulation erreicht
  (außer bei 5 Minuten: −7,3 %), auf unabhängigen Felddaten aber noch zu prüfen.
* Die Startwerte der Luftanteile (0,5 / 0,15) sind Annahmen. Sind sie für ein Haus falsch, korrigiert das Lernen sie
  über einige Lüftungen; bis dahin kann die Prognose daneben liegen. Der Rückfall greift erst nach 6 Vergleichen.
* Nur Fensterlüftung „allgemein“ wurde verglichen; Kipp-/Querlüftung und Ablüfter nicht.
* Die Entscheidungskennzahlen prüfen das Raummodell Minute für Minute, ohne die Haus-, Etagen- und
  Benachrichtigungsschichten der älteren Stände.
* Prospektiver Lauf auf echter Infrastruktur: nicht durchgeführt (keine Laufzeitumgebung mit echten Sensoren).
* Die grobe Plantabelle für die Dauer vor dem Öffnen (`coordinator_house.py`) ist unverändert.

## 7. Quellen (abgerufen am 15.11.2026)

* EnergyPlus Engineering Reference (NREL): „Moisture Predictor-Corrector“ (Zonen-Feuchtebilanz, analytische Lösung),
  „Effective Moisture Penetration Depth (EMPD) Model“ (Oberflächen- und Tiefenpuffer), „Hybrid Model“ (Bedingungen,
  unter denen Infiltration aus Messwerten rückgerechnet werden darf) –
  github.com/NREL/EnergyPlus, `doc/engineering-reference/src/`.
* NIST: „Building Air Change Rate Estimates for CBR Analysis“ (2008) – Luftwechselraten eines Gebäudes variieren um
  den Faktor 10 und mehr mit Wetter und Betrieb. nist.gov/publications/building-air-change-rate-estimates-cbr-analysis
* WHO: „Air Change Rate – Input Parameter Protocol“ – Abklingmessung nur ohne Quelle während des Abklingens gültig.
  who.int/publications/m/item/air-change-rate-input-parameter-protocol
* ASHRAE Handbook – HVAC Applications, Kapitel 37 „Moisture Management in Buildings“ – hygroskopische Pufferung.
* Gibbs, Candès: „Conformal Inference for Online Prediction with Arbitrary Distribution Shifts“, JMLR 25 (2024),
  arXiv 2208.08401 – adaptive konforme Intervalle; die Zusage gilt über Zeitabschnitte, nicht je Prognose.
* Home Assistant Entwicklerdokumentation, „Weather entity“ – Vorhersagedienst und Felder.

Übernommen: Exponentiallösung der Zonenbilanz, Pufferung als zweiter Speicher, Gültigkeitsbedingungen des Lernens
(keine Quelle, stabile Referenz), adaptive Intervallkalibrierung. Nicht übernommen: Mehrschicht-Puffer, feste
Luftwechsel-Tabellen (die Streuung zwischen und in Gebäuden ist zu groß), Wahrscheinlichkeitsangaben je Prognose.
