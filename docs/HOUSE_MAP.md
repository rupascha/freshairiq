# Hauskarte (optional) – Architektur, Verträge, Risiken

Stand: Auftrag „Intelligente Hauskarte“ vom 27.10.2026. Basis: 0.26.5.4, Commit `2a2cf5e`
(Hotfix Türverzögerung/Komfortkühlung `12c2365` und Lernmodell-Fix `2a2cf5e` abgeschlossen und geprüft).

Die Hauskarte ist ein **zusätzlicher, opt-in Kartentyp** `custom:freshairiq-house-card`.
Die bestehende Karte `custom:freshairiq-card` (klassisch/IQ), das Panel, alle Entities,
Events, Optionen, Lern- und Entscheidungslogik bleiben unverändert.

## 1. Bestandsaufnahme (verifiziert im lokalen Code)

| Quelle | Befund für die Karte |
|---|---|
| `dashboard_live.py` | Live-Kanal `freshairiq/dashboard/subscribe` liefert `rooms` (kanonische Raumergebnisse inkl. `action`, `house_aligned_action`, `floor`, `contact_entities`, `contact_orientations`, `contact_delays`, `opening_state`, `active`, `mechanical_exhaust_active`, `exhaust_fan`, `air_exchange`, Klima), `levels`, `wind_bearing`, `wind_speed`, `weather_now`. Wird einmal je Coordinator-Datenobjekt gebaut und nur bei Änderung gesendet. |
| `coordinator_sources._weather_wind` | `wind_bearing` nur numerisch (`finite_float`), Text-Kardinalrichtungen werden verworfen; keine Einheit. **Physik bleibt so** – die Karte parst die Wetterentität separat. |
| `const.ORIENTATIONS` | 8 Richtungen + unbekannt je Raum/Kontakt; keine Azimute, keine Koordinaten. |
| `open_connections.py` | Symmetrischer Graph offener Durchgänge (Option `open_connections`). |
| Optionen `cross_ventilation_pairs`, `cross_zone_connections` | Querlüftungspaare / Zonenverbindungen (Text). |
| Kontakte | Binär oder nachgewiesen dreiwertig (`three_state_contacts`), Entprellung (`stable_opening_modes/since` im Raumspeicher), Verzögerung je Kontakt (`contact_delays`). Gleicher Kontakt in zwei Räumen möglich (Community-Fall A). |
| `diagnostics_privacy.py` | Positivlisten (`_ROOM_KEYS`, `_TOP_LEVEL_KEYS`): neue Felder gelangen **nicht** automatisch in Diagnose/Hub. |
| `tools/coordinator_golden.py` | Vergleicht alle Schlüssel von `coordinator.data` → neue Kartendaten **nicht** in `coordinator.data`. |
| Frontend | `freshairiq-loader.js` registriert Proxys und lädt Module lazy; Modulgrenze 200 000 Byte (Wartbarkeits-Gate), `freshairiq-card.js` darf nicht wachsen. |
| Persistenz | HA `Store` je Entry (`freshairiq.<entry>`, Aktoren, Telemetrie). |

## 2. Architektur

**Drei getrennte Ebenen** (Auftrag §11):
1. Beobachtung: HA-Zustände, Wetterentität, gespeicherte Geometrie.
2. Kanonische Entscheidung: unverändert aus dem Coordinator (`rooms[*].action/house_aligned_action`).
3. Strömungshypothese: nur Erklärung/Visualisierung, fließt **nie** in Entscheidung, Lernen oder Prognose.

### Backend (Python)
| Modul | Art | Inhalt |
|---|---|---|
| `house_layout.py` | rein | Schema v1, Validierung (Fehlercodes je Objekt), Normalisierung, Migration, Grenzen, Polygon-Geometrie (Fläche, Selbstüberschneidung, Kante, Außennormale mit Gebäudedrehung). |
| `house_autolayout.py` | rein | Deterministischer Vorschlag aus Räumen/Etagen/Maßen/Verbindungen/Orientierungen; Herkunft je Objekt (`ha`, `config`, `estimated`, `schematic`, `user`); Bewertung der Alternativen. |
| `house_wind.py` | rein | Windrichtung (Grad oder Text, 16 Richtungen), Einheiten → m/s, Alter/Gültigkeit, FROM→TO, Fassaden-Anströmung (luv/lee/seitlich/ruhig). |
| `house_airflow.py` | rein | Luftweg-Graph (Räume, außen), Kantenzustand, Modellstufe (`topology_only`, `wind_heuristic`, `opening_aware`; `calibrated` wird **nicht** behauptet), Pfade mit `confidence/basis/assumptions/unknowns`. |
| `house_map.py` | HA | `Store` `freshairiq.house_layout.<entry>`, WebSocket `freshairiq/house_layout/get` (lesen) und `…/save` (nur Admin, Revision gegen Überschreiben), Vorschlag on demand, Live-Zusatz für den Kartenkanal. |

**Live-Zusatz (additiv, nur Live-Kanal):** `house_map_live` mit Wind (geparst, Quelle, Zeitstempel,
Einheit) und je Raum die Kontaktzustände (`closed`/`tilted`/`open`/`open_unspecified`/`unknown`,
dreiwertig ja/nein, seit, Verzögerung, Sitzung bestätigt). Nicht in `coordinator.data`, nicht in
Entity-Attributen, nicht im Recorder, nicht in der Diagnose.

### Frontend
| Modul | Inhalt |
|---|---|
| `freshairiq-house-geometry.js` | Gleiche Geometrie-/Validierungsregeln wie Python (Editor-Prüfung, Hit-Test). |
| `freshairiq-house-card.js` | SVG-Karte, Etagenwahl + Auto-Fokus, Ebenen, Wind/Luftwege, Erklärdialog, DE/EN, Themes, reduzierte Bewegung. |
| `freshairiq-house-editor.js` | Schnell- und Präzisionsmodus, Touch, Undo/Redo, Snap, Zoom, Validierung an der Wand, Export/Import, Grundriss-Vorlage (Hochladen, Maßstab, Norden, Trennlinie, Raum/Fenster antippen). |
| `freshairiq-house-trace.js` | Raumerkennung auf der Vorlage im Browser (Graustufen → Otsu-Schwelle → Wandmaske + Lückenschluss + Trennlinien → Flutfüllung → Kontur → Vereinfachung → Begradigung), Zuordnungsvorschlag nach Fläche, Übernahme in das Layout. |
| `freshairiq-house-view.js` | Markenfarben, Stil, Windströme (Abprallen/Einströmen), Windrose, Wettertext. |
`freshairiq-loader.js` registriert zusätzlich nur den Proxy `freshairiq-house-card` (+ Lovelace-Editor) und lädt das Modul lazy.

## 3. Verträge
- Layout-Schema v1 (`schema_version: 1`), stabile IDs, Raum ↔ FreshAirIQ-`room_key`.
- Geometrie ändert **nie** Raumvolumen oder Konfiguration (keine Synchronisation in v1).
- WebSocket: Lesen für angemeldete Nutzer, Speichern nur Admin; Größenlimits; Revisionskonflikt → Fehler `revision_conflict`, kein stilles Überschreiben.
- Keine Schreibzugriffe auf HA-Areas/Floors/Entities.

## 4. Risiken und Gegenmaßnahmen
| Risiko | Maßnahme |
|---|---|
| Karte widerspricht Dashboard/Push | Aktion ausschließlich aus `rooms[*]` (gleiche Quelle wie Dashboard); Test kanonische Konsistenz. |
| Schein-Präzision (Wind/Strömung) | Modellstufen, Konfidenz, Kennzeichnung „Schätzung/schematisch“, keine Geschwindigkeiten, Binärkontakt = „offen – Art unbekannt“. |
| Golden/Recorder/Diagnose verändert | Kartendaten nur im Live-Kanal; Golden-Check; Diagnose-Positivliste unverändert. |
| Modulgrößen / Ladezeit | Eigene Module < 200 kB, lazy; Bestandskarte unverändert. |
| Datenverlust Layout | Atomares Speichern, Revision, Validierung vor Speichern, kaputte Daten → Schemaansicht. |
| iOS-Editor-Reset durch `hass`-Rerender | Editorzustand außerhalb des Renderpfads, kein Neuaufbau bei `hass`. |
| Performance-Gate schwankt | Keine Änderung an `evaluate_room`/Coordinator-Hotpath. |

## 5. Bewusste Grenzen v1
- Grundrissvorlage (Bild/PDF) wird **nicht angeboten** (kein sicherer Parser; keine Übertragung).
- Modellstufe `calibrated` wird nicht erreicht/behauptet (keine dokumentierte Kalibrierung).
- Hindernisse nur als manuelle Abschattung je Fassade.
- Geometrie → Volumen-Synchronisation nicht enthalten.
