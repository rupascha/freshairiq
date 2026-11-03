# Hauskarte (optional)

Die Hauskarte zeigt deine FreshAirIQ-Räume auf einem frei formbaren Grundriss: welcher Raum gerade
Handlung braucht, warum, welche Fenster und Türen wie offen sind, woher der Wind kommt und welche
Luftwege daraus **vermutlich** entstehen. Sie ist eine zusätzliche Karte – das bisherige Dashboard,
alle Entities, Empfehlungen, Meldungen und Automationen bleiben unverändert.

![Hauskarte – Querlüftung durchs Haus (Demo-Render)](images/house_map_cross_ventilation_de.png)

## Einrichten in vier Schritten

1. **Karte hinzufügen:** Dashboard bearbeiten → Karte hinzufügen → „FreshAirIQ Hauskarte“
   (YAML: `type: custom:freshairiq-house-card`). Oder in einer vorhandenen FreshAirIQ-Karte unter
   „Darstellung“ **Hauskarte (Grundriss)** wählen – die Karte zeigt dann den Grundriss statt des Dashboards.
2. **Vorschlag ansehen:** Beim ersten Öffnen erstellt FreshAirIQ einen Grundrissvorschlag aus deinen
   Räumen, Etagen, Raummaßen bzw. Volumen, gemeinsamen Türkontakten, offenen Verbindungen und
   Fensterausrichtungen. Er ist als „Automatischer Vorschlag – noch nicht gespeichert“ markiert.
3. **Anpassen:** „Grundriss bearbeiten“ (nur für Administratoren). Räume verschieben, Größe ändern,
   drehen, Ecken setzen, Fenster an die richtige Wand ziehen.
4. **Nordrichtung prüfen und speichern:** Im Editor ohne Auswahl „Norden (Grad, Richtung ‚oben‘)“ eintragen
   und „Nordrichtung geprüft“ anhaken. Erst dann ordnet die Karte den Wind einzelnen Wänden zu.

Du kannst jederzeit überspringen: Auch der ungespeicherte Vorschlag zeigt sofort Temperatur, Feuchte,
Empfehlungen und Öffnungszustände.

## Was der Vorschlag weiß – und was nicht

Home Assistant kennt Raumnamen und Etagen, aber **keine** Wandkoordinaten oder Fensterflächen. Jeder Raum
trägt deshalb seine Herkunft:

| Herkunft | Bedeutung |
|---|---|
| aus Konfiguration berechnet | Länge × Breite aus der Raumeinrichtung |
| geschätzt | Fläche aus Volumen ÷ Höhe (2,5 m, wenn unbekannt), quadratisch angenommen |
| schematisch | keine Größe bekannt – Schemaplan ohne Maßstab |
| vom Nutzer bestätigt | von dir gezeichnet oder verändert |

Der Vorschlag verändert **nie** Raumvolumen oder Raumkonfiguration und wird nach einem Neustart,
Wetterwechsel oder Update nicht neu platziert. „Neu vorschlagen“ zeigt vorher, wie viele Räume sich
ändern würden; „Fehlende Räume ergänzen“ fügt nur neue Räume hinzu, ohne vorhandene zu verschieben.

## Editor

![Editor: Wandlänge, Winkel, 90° und Sperren](images/house_map_editor_90_locks_de.png)

- **Schnell:** Raum ziehen = verschieben, Griff oben rechts = Größe, „Drehen 90°“, Vorlagen
  Rechteck/L/U für neue Räume, Öffnungen entlang der Wand ziehen.
- **Präzision:** Ecken ziehen, Punkt in der Wandmitte = Ecke einfügen, Ecke auswählen + Entf/✕ = löschen,
  Koordinaten numerisch eingeben, Raster 0,05–0,5 m.
- Rückgängig/Wiederholen (auch Strg+Z/Strg+Y), Zoom, Einpassen, Zwei-Finger-Zoom, Pfeiltasten verschieben.
- Öffnungen: Art (Fenster, Tür, Dachfenster, Durchgang, Lüftungsöffnung), Mechanik (Dreh-Kipp, Drehflügel,
  nur Kipp, Schiebe …), Breite, zugeordnete Kontakte.
- **Ansicht (0.26.6.0):** der Grundriss füllt die ganze Karte. Unten rechts auf dem Plan liegt **☰ Menü** mit Ebenen
  (Aktion, Temperatur, Feuchte, CO₂, Luftwege, Qualität), Details (Empfehlung, Wetter, Wind und Kennzahlen), Etagen,
  Gästen, Hinweisen zur Darstellung (Vorschlag, geschätzte Raumgrößen, Nordrichtung, Windströme schematisch, Luftweg-Modell)
  sowie Support & Diagnose und Bearbeiten. Hinweise, die einen Tipp brauchen (andere Etage, Live-Verbindung gestört,
  Auto-Fokus pausiert), liegen oben links auf dem Plan. Außenwände dick, gemeinsame Innenwände dünn; Fenster, Türen und
  Durchgänge mit eigenem Symbol; Verbindungen ohne eingezeichnete Öffnung mit Markierung auf der Wand.
- **Luftstrom (0.26.6.0):** Luft, die durch ein offenes Fenster hereinkommt, bewegt sich nur durch Verbindungen –
  die eingezeichnete Tür bzw. den Durchgang zwischen zwei Räumen, sonst die Mitte der gemeinsamen Wand einer Verbindung –
  und nie durch eine Wand; ohne solche Stelle endet der Strom. Am anderen Ende strömt sie aus dem offenen Fenster wieder
  hinaus (auch aus einem zweiten offenen Fenster desselben Raums, wenn kein Luftweg bekannt ist).
- **Etagen (UI-Hotfix 0.26.6.0):** die anderen Etagen als Buttons in einer Leiste am unteren Kartenrand, unter dem Plan (nie darüber); kein „Alle Etagen“ – für mehrere Etagen die Karte mehrfach einfügen, je Karte mit `floor: ground_floor` / `floor: upper_floor` (Etagen-ID, Ebene oder Name); jede Karte merkt sich ihre Wahl getrennt; eine Etage mit Handlungsbedarf (jetzt lüften, schließen, kritisch) pulsiert dezent, bei „Bewegung reduzieren“ mit festem Punkt.
- **Menü und Support:** das Menü ist ein eigenes Fenster über dem Plan; „Support & Diagnose“ öffnet ein Fenster mit denselben Funktionen wie die FreshAirIQ-Karte (Diagnose mit Pflichtbeschreibung, Export, Feedback).
- **Editor per Touch:** Raum, Wand, Tür oder Fenster antippen; Finger auf Ungewähltem verschiebt die Ansicht, zwei Finger zoomen, nur der gewählte Raum lässt sich ziehen. Wand antippen → Länge in m eingeben, festen Eckpunkt wählen, Übernehmen; „Maß sperren“ hält die Länge. Türen: Anschlag links/rechts und Öffnungsrichtung. Eine Verbindung „Tür“/„offener Durchgang“ lässt sich auf der gemeinsamen Wand als Tür/Durchgang einzeichnen.
- **Wände einzeln, Winkel und Sperren (Editor):** Eine Wandlänge ändert nur diese Wand – die gewählte Ecke bleibt
  stehen, die andere wandert entlang der Wand, die nächste Wand gleicht aus. Die gegenüberliegende Wand behält ihre Länge;
  ein Raum muss kein Rechteck bleiben. Nachbarräume werden nie mitgezogen – würde die Wand in einen Nachbarraum wachsen,
  lehnt der Editor ab und erklärt warum.
  - **Sperren Wand für Wand:** „Maß sperren“ hält eine Länge, „Winkel an Ecke … sperren“ hält einen Winkel. Gesperrte
    Wände und Winkel werden bei späteren Änderungen mitgetragen (der gesperrte Abschnitt verschiebt sich als Ganzes).
    Geht das nicht, ändert sich **nichts**, und der Hinweis nennt die Wand bzw. Ecke und einen Ausweg („Sperre lösen
    oder die andere Ecke stehen lassen“). Freie Geometrie bleibt frei.
  - **90°:** Im Wandfenster stehen die Winkel an beiden Ecken (Innenecken von L- und U-Räumen als 270°) und je ein
    Knopf „Ecke … auf 90°“ – nur diese Ecke wird rechtwinklig, nie alle Räume. „90° einrasten“ in der Werkzeugleiste
    lässt eine gezogene Ecke nahe 90° (±6°) genau rechtwinklig einrasten; das Raster gilt weiter.
- **Räume zusammenfügen (Editor):** Räume einzeln ausmessen, grob aneinanderschieben (bis etwa 35 cm) und
  „Räume zusammenfügen“ tippen. Gegenüberliegende Wände werden erkannt (auch 3,92 m neben 3,98 m), jeder Raum wird nur
  als Ganzes verschoben – nichts wird skaliert oder verbogen, gesperrte Maße haben Vorrang. Erst erscheint eine
  **Vorschau** (gestrichelte Räume, erkannte Innenwände grün, Hinweise zu unterschiedlichen Längen, gesperrten Ecken
  oder Überlappungen); gespeichert wird erst nach „Übernehmen“, Rückgängig/Wiederholen funktionieren. Danach sind die
  gemeinsamen Wände Innenwände (einmal gezeichnet), Türen darauf verbinden beide Räume, Fenster bleiben an der Außenwand.

  ![Räume zusammenfügen – Vorschau](images/house_map_join_preview_de.png)

- **Türbögen nur im Editor:** Der Editor zeigt den Schwenkbereich einer Tür als feinen Bogen (zum Einzeichnen von
  Anschlag und Richtung). Die Hauskarte zeigt das Türblatt mit seinem Zustand ohne Bogen; ein unsichtbarer Bogen
  belegt keinen Platz für Beschriftungen.
- **Sonnenstand:** Die Sonne steht auf der Karte dort, wo `sun.sun` sie gerade meldet (Azimut und Höhe, gedreht nach
  der Nordrichtung des Grundrisses) und wandert im Tagesverlauf mit – neu gezeichnet in 2°-Schritten, nicht bei jeder
  Zustandsänderung in Home Assistant. Ohne geprüfte Nordrichtung zeigt die Karte nur gleichmäßiges Tageslicht von
  oben, keine Sonne und keine Strahlen auf einer Seite, die falsch sein könnte.
- **Fenster mit Kontakt eines anderen Raums:** Ein Fenster wird dort gezeichnet, wo es ist – auch wenn sein Kontakt
  in der Einrichtung einem anderen Raum zugeordnet ist (z. B. Gäste-WC-Fenster, das den Flur lüftet). Im Editor stehen
  beim Fenster alle Kontakte zur Wahl, die anderer Räume mit „(lüftet …)“. Die Karte zeigt den echten Zustand des
  Sensors; die Lüftungsentscheidung des Flurs bleibt, wie sie ist. Ein von zwei Räumen genutzter Kontakt wird im
  Vorschlag nur dann zur Tür, wenn er als Tür eingerichtet oder in Home Assistant ein Türsensor ist.
- **Etagennamen:** Editor und Karte zeigen lesbare Namen (Erdgeschoss, Obergeschoss, Kellergeschoss, Dachgeschoss …);
  die internen Kennungen bleiben unverändert.
- **Raumdarstellung (0.26.6.0, 6. Build):** Raumfläche zeigt den Zustand (ruhig/kühl = alles gut, gedämpftes Bernstein = warten, Grün/Cyan/Orange = handeln, Koralle mit Schraffur = kritisch, sanfter Innenrand bei Handlungsbedarf); Name direkt auf der Fläche, Zustand als dunkle Kapsel, Temperatur/Feuchte in großen Räumen. Fenster an einer Innenwand meldet der Editor und setzt sie per Tipp an die Außenwand.
- **Beschriftung und Wetter (7. Build):** Beschriftungen bleiben immer im echten Raumumriss (auch L-/U-Form); zu kleine Räume zeigen einen Zustandspunkt. Oben rechts das Außenwetter oder eigene Sensoren (`weather_sensors: sensor.a, sensor.b`).
- **Atmosphäre (8. Build):** kein Raster – ein Himmel nach dem echten Wetter (`sun.sun` für Tag/Dämmerung/Nacht – nachts tiefer Nachthimmel, Räume in gedämpftem kühlem Licht, Sterne je nach Bewölkung; Sonne, Wolkenschatten, Nebel, Regen und Schnee schräg mit dem Wind, Gewitterblitz – nur aus Home-Assistant-Daten, nie über dem Haus). Räume zeigen ihr Klima auch ohne Lüften: warm/kühl, Dunst bei hoher Feuchte („↑“ bei steigender Feuchte), trockene Struktur, Schimmelrisiko als Sprenkel an den Wänden, Dampf an einer Feuchtequelle, ein drehender Lüfter. Beim Lüften dringt Frischluft an offenen Fenstern ein (gekippt kürzer), feine Partikel ziehen mit den Strömen durchs Haus; nach dem Schließen klingt sie aus. Beschriftungen behalten Messwerte vor dem Zustandswort und meiden Türbögen; kleine Räume zeigen einen Kurznamen („WC“). Modellierte Darstellung, keine Strömungssimulation.
- **Wind und Luft (9. Build):** ein modelliertes Windfeld auf einer Canvas-Ebene: feine leuchtende Fäden mit nachleuchtenden Spuren, breite durchsichtige Luftmassen, Umlenkung an den Außenwänden, gelegentliche Wirbel hinter den Gebäudeecken, Böen als Ereignis (gemessene Böe, wenn vorhanden). Durch geöffnete Fenster strömt die Luft ins Haus und über Türen zum anderen Fenster hinaus; nach dem Schließen klingt sie aus. Oben links: entfernbare Feuchte des ganzen Hauses und Lüftungsdauer (antippen für die Erklärung). Beschriftungen behalten Messwerte und vollständige Namen (notfalls zweizeilig). Modellierte Darstellung, keine Messung und keine Strömungssimulation.
- **10. Build:** oben links steht genau FreshAirIQs „Jetzt entfernbar“ der FreshAirIQ-Karte mit der empfohlenen Lüftungszeit (während einer Lüftung: bisher entfernt und Restzeit). Der Wind hat je nach Wetter einen eigenen Charakter – leicht und warm bei Sonne, ruhig bei Bewölkung, dichter bei Regen, episch bei Sturm.
- **Tastatur im Editor:** Raum antippen, dann Pfeiltasten (Shift = zehn Rasterschritte); Rückgängig mit Strg/⌘+Z.
  Beim Ziehen rastet ein Raum an der Wandlinie des Nachbarn ein (Hilfslinie) und kann nicht auf einen anderen gelegt werden.
- **Öffnungen setzen** (Leiste über der Zeichnung, auch ohne Grundriss-Vorlage): „Fenster antippen“, „Innentür
  antippen“, „Durchgang antippen“ und dann auf eine Wand tippen. Innentür und Durchgang gehören auf eine Wand
  zwischen zwei Räumen (sonst Hinweis „keine Innenwand“); die Luftwege lesen sie als Verbindung beider Räume.
  Eine Tür zählt nach ihrem Kontakt als offen, ein Durchgang ist immer offen.
  Die ganze Breite muss auf einer gemeinsamen Wandstrecke liegen (Wandabstand bis 5 cm; eine gemeinsame Ecke
  reicht nicht); der Editor setzt die Öffnung mittig auf diese Strecke und kürzt die Breite bei Bedarf. Passt sie
  später nicht mehr, zeigt er „zählt als Außenöffnung“.
- **Breite:** bei einer ausgewählten Öffnung die beiden runden Griffe an ihren Enden ziehen (bleibt mittig, in
  ihrer Wand, mindestens 0,3 m, am Raster) oder „−“/„+“ (je 5 cm) bzw. das Feld „Breite (m)“ nutzen.
- Verbindungen je Raum (offener Durchgang, Tür, Treppe, Schacht, Kanal) – zu einem anderen Raum oder nach außen.
- Fehler stehen direkt am Raum („Wände kreuzen sich“, „überlappt einen anderen Raum“ …); ein ungültiger
  Grundriss wird nicht gespeichert.
- Hat jemand anderes inzwischen gespeichert, wird **nicht überschrieben**: Entwurf exportieren, neu laden.
- Export/Import als JSON.

## Grundriss-Vorlage (Bild hochladen und Räume antippen)

Statt alles von Hand zu zeichnen, kannst du je Etage ein Bild deines Grundrisses als Vorlage hinterlegen
(Architektenplan, Exposé-Grundriss, Scan oder Foto) und die Räume darauf antippen:

1. **Bild hochladen** (Editor → „Grundriss-Vorlage“). PNG, JPEG oder WebP. **PDF wird nicht unterstützt** –
   speichere die Seite vorher als Bild (Bildschirmfoto/Export) oder fotografiere den Plan gerade von oben ab.
   Das Bild wird im Browser verkleinert (längste Seite 2000 Pixel) und bleibt lokal in Home Assistant.
2. **Maßstab:** zwei Punkte einer Strecke mit bekannter Länge antippen (z. B. eine bemaßte Wand) und die Länge
   in Metern eingeben. Ohne Maßstab werden keine Räume übernommen.
3. **Norden** (optional): zwei Punkte entlang des Nordpfeils im Plan antippen – erst das Ende, dann die Spitze.
   Die Nordrichtung des Grundrisses wird damit gesetzt und als geprüft markiert.
4. **Raum antippen:** in einen Raum der Vorlage tippen. Die von Wänden umschlossene Fläche wird erkannt, als Umriss
   gezeigt und mit ihrer Fläche angezeigt. Darunter stehen die passendsten FreshAirIQ-Räume (Vergleich mit Länge ×
   Breite bzw. Volumen ÷ Raumhöhe aus der Raumeinrichtung); ein Tipp ordnet zu. Jeder andere Raum ist über die
   Auswahl erreichbar. Ein schon gezeichneter Raum wird ersetzt; seine Fenster wandern an die Wand mit derselben
   Himmelsrichtung und behalten ihre Kontakte.
5. **Fenster antippen:** auf eine Wand tippen – dort entsteht ein Fenster, das du wie gewohnt einstellst.

Wenn die Erkennung nicht passt:
- „**Das ist eine Wand**“ – etwas weiter in den Raum tippen.
- „**Der Bereich ist nicht geschlossen**“ oder der Umriss läuft in den Nachbarraum: eine offene Tür oder ein
  Durchgang verbindet die Räume. Den Regler „**Lücken schließen**“ erhöhen oder mit „**Trennlinie**“ eine Linie
  quer über den Durchgang ziehen.
- Möbel, Beschriftungen und Maßketten im Raum stören in der Regel nicht; Fotos mit starkem Schatten,
  schräger Aufnahme oder sehr dünnen Wandlinien können schlechter erkannt werden – dann hilft eine Trennlinie
  oder das Nachzeichnen von Hand.

Die Erkennung läuft vollständig im Browser, ohne Internet und ohne fremde Dienste. Eine vollautomatische
Erkennung aller Räume (inklusive Fenster und Türen aus Symbolen) gibt es bewusst nicht – sie wäre auf
unterschiedlichen Plänen zu unzuverlässig.

## Ebenen

Aktion · Temperatur · Feuchte · CO₂ · Luftwege · Qualität. Die Aktion jedes Raums stammt aus genau
denselben Daten wie Dashboard, Push und Automations-Events – die Karte entscheidet nichts selbst.
Farbe ist nie die einzige Information: jeder Raum zeigt Wort und Symbol. Ein Schimmelrisiko „hoch“
verhindert „grün“, „sehr hoch“ färbt den Raum rot – das Aktionswort bleibt dabei die FreshAirIQ-Empfehlung.

## Fenster und Türen ehrlich dargestellt

| Darstellung | Bedeutung |
|---|---|
| geschlossen | Kontakt meldet geschlossen |
| gekippt | nur mit nachgewiesenem 3-Zustands-Kontakt |
| ganz offen | nur mit nachgewiesenem 3-Zustands-Kontakt |
| offen – Öffnungsart unbekannt | normaler Fensterkontakt (auf/zu) |
| Kontakt offen – Bestätigung läuft | die eingestellte Öffnungsverzögerung dieses Kontakts läuft noch |
| Zustand unbekannt / ohne Sensor | keine verlässliche Angabe |

## Wind und Luftwege

![Aktives Lüften: Frischluft am offenen Fenster](images/house_map_airing_de.png)

Wind kommt aus der Wetterentität (Grad oder Himmelsrichtung, Einheit km/h, m/s, mph, Knoten). Der Pfeil
zeigt, **woher** der Wind kommt. Fehlt die Richtung, ist sie veraltet oder windstill, wird kein Pfeil
gezeichnet.

Der Wind wird als weiche, halbtransparente Wellenbänder gezeichnet, die an Wänden umgelenkt werden und durch
bestätigt offene Fenster einströmen. Die Wellen laufen ohne Neustart weiter – auch wenn sich Daten ändern
oder die Karte neu gezeichnet wird; stärkerer Wind lässt sie schneller laufen. Bei „Bewegung reduzieren“ des
Geräts oder ausgeschalteter Animation stehen sie still.

Luftwege sind eine **Schätzung**, keine Messung und keine Luftgeschwindigkeit:

| Modellstufe | Grundlage |
|---|---|
| nur Verbindungen | bekannte Durchgänge und Kontaktzustände, keine Richtung |
| Wind-Schätzung | Wind + Fassadenlage (nur mit geprüfter Nordrichtung oder eingestellter Fensterausrichtung) |
| Wind + Öffnungsart | zusätzlich nachgewiesene Kipp/Offen-Stellung jeder aktiven Außenöffnung |

Ein Tipp auf einen Luftweg erklärt Grundlage, Annahmen und Unbekanntes. Einseitiges Lüften erscheint als
„Austausch am Fenster“, ohne passende Gegenöffnung entsteht kein erfundener Querweg, eine geschlossene
Zwischentür stoppt den Weg, und über Treppen oder Decken wird nichts behauptet. Ein Ablüfter zeigt seine
vermutete Ersatzluft; ein Referenzsensor im Nachbarraum ist **kein** Nachweis eines Luftwegs.

## Etagen

Die anderen Etagen stehen als Buttons in einer Leiste unter dem Plan; eine Etage mit Handlungsbedarf pulsiert
dezent. Eine Gesamtansicht „Alle Etagen“ gibt es nicht mehr – für mehrere Etagen die Karte mehrfach einfügen
(`floor: ground_floor`, `floor: upper_floor` …).

![Etagen als Buttons unter dem Plan](images/house_map_sunny_de.png)

Auto-Fokus (Karteneinstellung `auto_focus`):

- `off` – nie automatisch wechseln
- `hint` (Standard) – Hinweis „Handlung auf anderer Etage“ mit Sprung-Schaltfläche
- `auto` – bei einer **neuen** Handlung auf einer anderen Etage dorthin wechseln. Eine manuelle Wahl hält
  `manual_lock_min` Minuten (Standard 10, sichtbar „Auto-Fokus pausiert bis …“); höchstens ein
  automatischer Wechsel pro Minute.

## Karteneinstellungen

```yaml
type: custom:freshairiq-house-card
title: Hauskarte          # optional
auto_focus: hint          # off | hint | auto
layer: action             # action | temperature | humidity | co2 | airflow | quality
manual_lock_min: 10
animation: true           # Luftweg-Animation (bei „Bewegung reduzieren“ immer aus)
entry_id: ...             # nur bei mehreren FreshAirIQ-Einträgen
```

## Was die Karte bewusst (noch) nicht kann

- **Keine Strömungsberechnung:** Windumlenkung um Ecken, Wirbel an Fassaden oder Hindernisse werden nicht berechnet.
  Die Anströmung jeder Wand ist eine Einordnung (zugewandt/seitlich/abgewandt), Luftwege sind Linien zwischen
  Öffnungen und Raummitten – eine Topologie-Annahme.
- **Kipp vs. ganz offen** unterscheidet Symbol und Einordnung (klein/groß), nicht Öffnungswinkel, Flügelrichtung,
  Höhe, wirksame Fläche oder Volumenstrom.
- **Auto-Vorschlag** erzeugt nur rechteckige Räume in zwei einfachen Anordnungen; echte L-/U-Formen, die
  Gebäudeaußenkontur und Höhenversätze kennt FreshAirIQ nicht – diese zeichnest du im Editor.
- **Etagen-Auto-Fokus** ist standardmäßig auf „Nur Hinweis“; automatisches Wechseln schaltest du mit `auto_focus: auto` ein.
- Keine PDF-Vorlage (nur Bilder), keine vollautomatische Raumerkennung, keine Kalibrierung abgeleiteter Luftmengen.

## Datenschutz und Grenzen

- Der Grundriss wird lokal in Home Assistant gespeichert (`.storage/freshairiq.house_layout.<entry>`) und
  **nicht** an den Diagnose-Hub übertragen; er ist nicht Teil des Diagnose-Exports.
- Eine Grundriss-Vorlage (Bild) liegt getrennt davon in `.storage/freshairiq.house_underlay.<entry>`, ebenfalls
  nur lokal und nicht in Diagnose oder Upload. Sie wird nur im Editor angezeigt. „Vorlage löschen“ entfernt sie.
- Wird die FreshAirIQ-Integration in Home Assistant gelöscht, werden Grundriss und Vorlage mitgelöscht.
- Keine Cloud, keine Kartendienste; ohne Internet und ohne Winddaten bleibt die Karte vollständig nutzbar.
- Speichern nur für Administratoren. Home-Assistant-Bereiche, Etagen und Geräte werden nur gelesen.
- Keine Strömungssimulation (CFD), keine gemessenen Luftmengen; Hindernisse wie Nachbarhäuser werden
  nicht berücksichtigt.
- Beispiel-Grundriss ohne echte Daten: [examples/house_map_demo.json](examples/house_map_demo.json).
