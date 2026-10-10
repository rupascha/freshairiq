# FreshAirIQ in eigenen Automationen nutzen

FreshAirIQ **entscheidet**, schaltet aber **nie selbst** Geräte. Was daraus passiert – Lüfter an, Alexa-Ansage, Licht, Node-RED-Flow – legst du fest. Dafür gibt es drei Bausteine:

| Baustein | Wofür | Beispiel |
| --- | --- | --- |
| **Entitäten** (Sensoren je Raum und fürs Haus) | Zustand abfragen, auf Zustandswechsel reagieren | `sensor.schlafzimmer_aktion` wird `close` |
| **Ereignisse** `freshairiq_*` (ab 0.26.4.6) | Auf eine *Änderung* reagieren und gleich einen fertigen Text bekommen | Alexa sagt „Schlafzimmer: Bitte Fenster schließen.“ |
| **Aktion** `freshairiq.execute_intervention` | Eine von FreshAirIQ berechnete Maßnahme bewusst ausführen | Ablüfter im Bad einschalten |

> Die genauen Entitäts-IDs hängen von deinen Raumnamen und der Home-Assistant-Sprache ab. Du findest sie unter **Einstellungen → Geräte & Dienste → FreshAirIQ → Gerät (Raum) → Entitäten**. Die Beispiele unten verwenden typische deutsche IDs.

---

## 1. Entitäten

### Pro Raum

| Entität (Beispiel) | Zustände / Wert | Typische Nutzung |
| --- | --- | --- |
| `sensor.<raum>_aktion` | `ventilate` (lüften), `continue_ventilating`, `close`, `wait`, `do_not_ventilate`, `ventilate_for_cooling`, `okay`, `check_sensor`, `monitor_only` | **Wichtigster Trigger** pro Raum |
| `binary_sensor.<raum>_schliessen_empfohlen` | `on` / `off` | Ansage „Fenster schließen“ |
| `sensor.<raum>_schimmelrisiko` | `low`, `slightly_elevated`, `elevated`, `high`, `very_high` | Warnung, Entfeuchter |
| `sensor.<raum>_feuchtepotenzial` | ml | Bedingung „lohnt sich“ |
| `sensor.<raum>_geschatzte_oberflachenfeuchte` | % | Schimmel-Bedingung |

Die Raum-Aktion trägt zusätzlich das komplette Raum-Ergebnis als Attribut `freshairiq_room_payload` (Begründungen, Prognose, Messwerte). In Templates: `{{ state_attr('sensor.bad_aktion', 'freshairiq_room_payload').recommendation_reasons }}`.

### Fürs ganze Haus

| Entität | Inhalt |
| --- | --- |
| `sensor.freshairiq_status` | Hausstatus: `okay`, `ventilate`, `ventilation_running`, `close_windows`, `wait`, `pollen_warning`, `cooling_recommended`, `sensor_error`, `critical_mould`, … |
| `sensor.freshairiq_empfohlene_luftungsdauer` | Minuten |
| `sensor.freshairiq_entfernbare_feuchtigkeit` | ml |
| `binary_sensor.freshairiq_querluftung` | Querlüftung erkannt |

**Wichtig:** Die Raum-Aktion beschreibt, was *für diesen Raum allein* physikalisch sinnvoll ist. Die Haus-Empfehlung kann trotzdem „warten“ sagen (z. B. Regen in 10 Minuten, nachts geschlossen halten). Für Ansagen an Mitbewohner ist deshalb meist das **Haus-Ereignis** (Abschnitt 2) die bessere Quelle; für Geräte im Raum (Ablüfter) das **Raum-Ereignis**.

---

## 2. Ereignisse (ab 0.26.4.6)

FreshAirIQ feuert Ereignisse auf dem Home-Assistant-Event-Bus – nur bei **Änderungen**. Nach einem Neustart wird der aktuelle Zustand still übernommen; alte Ansagen werden nicht wiederholt. Die Texte kommen in der Home-Assistant-Sprache.

### `freshairiq_room_action` – Raum-Aktion hat sich geändert

| Feld | Beispiel | Bedeutung |
| --- | --- | --- |
| `room_key` | `schlafzimmer` | Interner Raum-Schlüssel (stabil) |
| `room_name` | `Schlafzimmer` | Dein Raumname |
| `action` / `previous_action` | `close` / `continue_ventilating` | Gleiche Codes wie `sensor.<raum>_aktion` |
| `message` | `Schlafzimmer: Bitte Fenster schließen.` | **Fertiger Satz für Alexa/TTS** |
| `action_label` | `Bitte Fenster schließen` | Nur die Handlung |
| `reasons` | `["Raumluftfeuchte 64 % …"]` | Bis zu 4 Begründungen |
| `humidity`, `temperature`, `surface_rh` | `64`, `21.4`, `78` | Messwerte |
| `potential_ml`, `recommended_duration_min` | `120`, `9` | Nutzen und Dauer |
| `mould_level` | `high` | Wie `sensor.<raum>_schimmelrisiko` |
| `ventilation_active` | `false` | Läuft eine Lüftung (Fenster/Tür offen)? |
| `ventilation_measures_active` | `true` | Fenster offen **oder** Ablüfter an **oder** Dusche/Erholungsphase erkannt |
| `floor`, `data_quality`, `entry_id`, `schema_version` | | Kontext |

### `freshairiq_house_recommendation` – Haus-Empfehlung hat sich geändert

| Feld | Beispiel |
| --- | --- |
| `kind` / `previous_kind` | `ventilate`, `wait`, `continue`, `close`, `okay`, `prepare`, `pollen_wait` (Außenluft belastet: Pollen und/oder Feinstaub, ab 0.26.4.7), `sensor` |
| `status` | wie `sensor.freshairiq_status` |
| `title`, `instruction`, `summary` | Texte der Empfehlung |
| `message` | `Jetzt ist ein guter Zeitpunkt zum Lüften. Wohnzimmer und Bad öffnen` |
| `room_keys`, `room_names` | betroffene Räume |
| `duration_min`, `estimated_removed_ml`, `reasons`, `night_strategy`, `severity` | Details |

### `freshairiq_mould_risk` – Schimmelrisiko eines Raums hat sich geändert

Alle Felder von `freshairiq_room_action`, dazu `previous_mould_level` und `rising` (`true` = Risiko steigt). Mit `ventilation_measures_active` kannst du selbst entscheiden, ob eine Warnung während des Duschens sinnvoll ist.

### `freshairiq_notification` – jede FreshAirIQ-Meldung als Ereignis (ab 0.26.4.9)

Genau die Texte, die FreshAirIQ als Push aufs Handy schicken würde – **auch wenn Handy-Benachrichtigungen ausgeschaltet sind oder kein notify-Dienst eingetragen ist**. Ideal für Alexa-Ansagen, Telegram-Gruppen oder Node-RED. Gleiche Meldungen kommen höchstens einmal pro Benachrichtigungs-Abstand (Standard 90 min).

| Feld | Beispiel | Bedeutung |
| --- | --- | --- |
| `type` | `ventilate`, `close`, `cool`, `mould`, `sensor`, `learning`, `complete`, `night`, `house_ventilate`, `house_close`, `house_wait`, `house_continue`, … | Art der Meldung (`house_*` = Empfehlung fürs ganze Haus) |
| `room_key`, `room_name` | `bad`, `Bad` | Betroffener Raum (bei Haus-Meldungen leer) |
| `title` | `FreshAirIQ · Bad` | Titel wie beim Push |
| `message` | `Jetzt lüften. Alternativ den Lüfter einschalten.` | Text wie beim Push |
| `speech` | `Bad: Jetzt lüften. Alternativ den Lüfter einschalten.` | **Fertiger Satz für Alexa/TTS** |
| `kind`, `room_keys` | `ventilate`, `["bad"]` | nur bei Haus-Meldungen |
| `night_quiet_hours` | `true` | Ruhezeit laut FreshAirIQ-Einstellung – selbst entscheiden, ob angesagt wird |
| `created_at` | ISO-Zeit | |

Hat ein Raum einen Ablüfter, enthalten Lüft- und Schimmel-Meldungen den Zusatz „Alternativ den Lüfter einschalten“. Eine laufende Lüftung („Lüftung läuft · weiter beobachten“) wird ab 0.26.4.9 nicht mehr als Push verschickt – sie verlangt nichts vom Nutzer; als Ereignis (`house_continue`) steht sie weiter zur Verfügung.

> Die Ereignisse bleiben im lokalen Home Assistant. Sie werden **nicht** an den Diagnostics Hub übertragen.

Ausprobieren: **Entwicklerwerkzeuge → Ereignisse → „Ereignis abonnieren“** → `freshairiq_room_action` eintragen → Fenster öffnen/schließen.

---

## 3. Beispiele

### Alexa sagt an, wenn ein Fenster geschlossen werden soll

```yaml
alias: FreshAirIQ – Alexa Fenster schließen
mode: queued
triggers:
  - trigger: event
    event_type: freshairiq_room_action
    event_data:
      action: close
actions:
  - action: notify.alexa_media_wohnzimmer      # dein Echo-Gerät (Alexa Media Player)
    data:
      message: "{{ trigger.event.data.message }}"
      data:
        type: announce
```

### Ablüfter im Bad einschalten, solange FreshAirIQ Lüften empfiehlt

```yaml
alias: FreshAirIQ – Ablüfter Bad
mode: restart
triggers:
  - trigger: event
    event_type: freshairiq_room_action
    event_data:
      room_key: bad
conditions: []
actions:
  - if: "{{ trigger.event.data.action in ['ventilate', 'continue_ventilating'] }}"
    then:
      - action: switch.turn_on
        target: { entity_id: switch.ablufter_bad }
    else:
      - action: switch.turn_off
        target: { entity_id: switch.ablufter_bad }
```

Alternativ führt `freshairiq.execute_intervention` die Maßnahme aus, die FreshAirIQ für den Raum berechnet hat (z. B. konfigurierter Ablüfter oder Beschattung):

```yaml
- action: freshairiq.execute_intervention
  data:
    room_key: bad
```

### Haus-Empfehlung an alle ansagen (statt Push aufs Handy)

```yaml
alias: FreshAirIQ – Haus-Empfehlung ansagen
triggers:
  - trigger: event
    event_type: freshairiq_house_recommendation
conditions:
  - "{{ trigger.event.data.kind in ['ventilate', 'close'] }}"
  - condition: time
    after: "08:00:00"
    before: "21:30:00"
actions:
  - action: notify.alexa_media_kueche
    data:
      message: "{{ trigger.event.data.message }}"
      data: { type: announce }
```

### Fertige Blueprints

Im Repository unter `blueprints/automation/freshairiq/`:

* `announce_room_action.yaml` – **Raum-Empfehlung ansagen**: Räume aus einer Liste wählen, Empfehlungen (z. B. „Fenster schließen“) und Ruhezeit festlegen, Ausgabe wählen (Alexa, Sprachausgabe, Telegram …).
* `device_follows_room_action.yaml` – **Lüfter folgt der Raum-Empfehlung**: Raum und Gerät auswählen; das Gerät läuft, solange FreshAirIQ Lüften empfiehlt, und nicht, während das Fenster offen ist.

Den Raum wählst du jeweils über seinen FreshAirIQ-Sensor „Aktion“ – einen internen Raum-Schlüssel musst du nicht kennen.

Import: **Einstellungen → Automationen & Szenen → Blueprints → Blueprint importieren** und die Raw-URL der Datei auf GitHub einfügen.

### Node-RED

* **Ansagen:** Node `events: all` mit *Event Type* `freshairiq_notification`. Ansagetext: `msg.payload.event.speech`; Raum: `msg.payload.event.room_key`; Art: `msg.payload.event.type`. Damit ersetzt du deinen eigenen „Fenster schließen“-/„Lüfter an“-Flow, ohne dass Pushs aufs Handy gehen (Handy-Benachrichtigungen in FreshAirIQ einfach ausgeschaltet lassen).
* **Ereignisse:** Node `events: all` mit *Event Type* `freshairiq_room_action` (bzw. `freshairiq_house_recommendation`). Die Daten stehen in `msg.payload.event` – z. B. `msg.payload.event.message` für die Ansage, `msg.payload.event.room_key` und `msg.payload.event.action` für den Switch-Node.
* **Lüfter schalten:** Trigger auf `freshairiq_room_action` mit `action` = `ventilate` (bzw. `house_aligned_action` = `ventilate`, wenn die Hausentscheidung berücksichtigt werden soll), danach `fan.turn_on`; aus bei `close`/`okay`.
* **Zustände:** Node `events: state` auf `sensor.<raum>_aktion`; `msg.payload` ist der Code (`close`, `ventilate`, …).

---

## 4. Häufige Fragen aus der Praxis

### Zwei Kontakte an einem Fenster (unten = offen, oben = gekippt)

FreshAirIQ versteht **Drei-Zustands-Kontakte** (`closed` / `tilted` / `open`) und lernt gekippt und offen getrennt. Fasse die beiden Kontakte mit einem Template-Sensor zu einem Fensterzustand zusammen und trage **nur diesen** als Fensterkontakt des Raums ein:

```yaml
template:
  - sensor:
      - name: "Schlafzimmer Fenster"
        unique_id: schlafzimmer_fenster_zustand
        device_class: enum
        state: >
          {% if is_state('binary_sensor.schlafzimmer_fenster_unten', 'on') %}open
          {% elif is_state('binary_sensor.schlafzimmer_fenster_oben', 'on') %}tilted
          {% else %}closed{% endif %}
        availability: >
          {{ states('binary_sensor.schlafzimmer_fenster_unten') not in ['unknown', 'unavailable']
             and states('binary_sensor.schlafzimmer_fenster_oben') not in ['unknown', 'unavailable'] }}
        attributes:
          options: "{{ ['closed', 'tilted', 'open'] }}"
```

Ohne YAML geht es auch über **Einstellungen → Geräte & Dienste → Helfer → Helfer erstellen → Template → Template-Sensor** (nur das Zustandstemplate einfügen); FreshAirIQ erkennt den Sensor dann spätestens beim ersten Kippen als Drei-Zustands-Kontakt. Schritt für Schritt: [README_DE.md](../README_DE.md).

Logik: unten offen → Fenster **offen** (beim Drehen öffnen sich beide Kontakte); nur oben offen → **gekippt**; beide zu → **geschlossen**. Die Option „Durchgangstür“ bitte für solche Helfer **nicht** aktivieren.

### Räume ohne eigenes Fenster (Flur, Gäste-WC, Waschküche, Abstellraum)

* **Mit Ablüfter (Limodor):** Raum normal anlegen, Volumen eintragen, den Lüfter unter *Optionale Geräte → Ablüfter / mechanische Lüftung* zuordnen. FreshAirIQ erkennt Lüftung über den laufenden Lüfter und lernt den mechanischen Luftwechsel getrennt.
* **Mit Türkontakt zum Flur:** Den Türkontakt als „Fenster/Tür“ eintragen und als **Referenzluft dieser Tür** die Sensoren des Raums dahinter (z. B. Flur) wählen – Referenzen werden pro Öffnung festgelegt.
* **Flur selbst:** Er hat keine eigene Außenöffnung. Ohne Türkontakte gibt es keine eigene Lüftungsempfehlung; seine Feuchte zählt aber zur Wasserbilanz des Hauses, und FreshAirIQ kann passive Mitlüftung anzeigen, wenn benachbarte Räume gelüftet werden (nur Anzeige, ohne Einfluss auf die Bilanz). Gibt es Türkontakte zu den Zimmern, bekommt jede Tür als Referenz die Sensoren des jeweiligen Zimmers. Sind mehrere offen, rechnet FreshAirIQ vorsichtig mit der feuchtesten Quelle.
* **Abstellraum mit Gefrierschrank:** Wenn er nur zur Beobachtung dienen soll: *In Berechnungen einbeziehen* ausschalten (Raum bleibt sichtbar, beeinflusst aber nichts).

### Schimmelwarnung während des Duschens

Ab 0.26.4.6 sendet FreshAirIQ keine Schimmel-Push-Nachricht mehr, solange im Raum etwas gegen die Feuchte arbeitet: Fenster offen, Ablüfter an, Dusche oder deren Erholungsphase erkannt (dafür im Raum die Feuchtequelle „Dusche“ angeben). Bleibt die Oberflächenfeuchte danach hoch, kommt die Warnung – dann ist Handeln wirklich nötig.

## Empfehlung passend zur Hausentscheidung (ab 0.26.4.7)

Der Sensor **Aktion** eines Raums beschreibt, was physikalisch für diesen Raum allein sinnvoll wäre. Der zusätzliche Sensor **Empfehlung** (`sensor.<raum>_empfehlung`) berücksichtigt die Entscheidung für das ganze Haus: Wartet das Haus bewusst (besseres Lüftungsfenster später, Pollen/Feinstaub, Nachtstrategie), zeigt er `ventilate_later` („Lüften möglich · noch warten“) statt `ventilate`. Für Ansagen und Lüfter-Automationen ist meist dieser Sensor die bessere Wahl. Im Ereignis `freshairiq_room_action` steht derselbe Wert im Feld `house_aligned_action`.
