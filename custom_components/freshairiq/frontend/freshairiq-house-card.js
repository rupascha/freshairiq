const FAIQ_VERSION = "0.26.7.0";
// FreshAirIQ house map card (optional, custom:freshairiq-house-card).
// Shows the canonical room decisions of FreshAirIQ on a free floor plan, the
// wind and a clearly marked air-path *hypothesis*. It never decides anything
// itself: actions come from the same room payload as the dashboard, pushes and
// automation events. Layout: freshairiq/house_map/*; rooms: freshairiq/dashboard/subscribe.

// the query of this module's own URL (version + build revision b=) reaches every module it imports
const Q = new URL(import.meta.url).search || `?v=${FAIQ_VERSION}`;
const G = await import(new URL(`./freshairiq-house-geometry.js${Q}`, import.meta.url).href);
const V = await import(new URL(`./freshairiq-house-view.js${Q}`, import.meta.url).href);
const A = await import(new URL(`./freshairiq-house-atmos.js${Q}`, import.meta.url).href);  // 0.26.6.1(7): sky, weather, climate, air
const F = await import(new URL(`./freshairiq-house-flow.js${Q}`, import.meta.url).href);  // order 8: the modelled wind field
const FL = await import(new URL(`./freshairiq-house-flowlayer.js${Q}`, import.meta.url).href);  // order 8: the visible air (canvas)
const W = await import(new URL(`./freshairiq-house-weather.js${Q}`, import.meta.url).href);  // 0.26.7.0: the weather world and overview
const M = await import(new URL(`./freshairiq-house-motion.js${Q}`, import.meta.url).href);  // 0.26.7.0(2): animation levels, the shared loop
const P = await import(new URL(`./freshairiq-house-panels.js${Q}`, import.meta.url).href);  // 0.26.7.0(2): rooms, room details, house details, menu
const D = await import(new URL(`./freshairiq-house-design.js${Q}`, import.meta.url).href);  // 0.26.7.0 UI order: FreshAirIQ / Home Assistant / own design
// Order 9: the FreshAirIQ dashboard card module (loaded in the background) – the house map takes "removable now" and
// its time from the card's own function, so both cards always show the same value.
let CARD = null;
const CARD_READY = import(new URL(`./freshairiq-card.js${Q}`, import.meta.url).href).then(m => { CARD = m; return m; }, () => null);

const LIVE = "freshairiq/dashboard/subscribe";
const HOUSE = "freshairiq/house_map/subscribe";
const RETRY_MS = 30000;
const GESTURE_LOST_MS = 60000;  // only for a release event that never arrived
const LAYERS = ["action", "temperature", "humidity", "co2", "airflow", "quality"];
const FOCUS_MODES = ["off", "hint", "auto"];
const AUTO_COOLDOWN_MS = 60000;

const T = {
  de: {
    title: "Hauskarte", loading: "Hauskarte wird geladen …", not_loaded: "FreshAirIQ ist nicht geladen.",
    live_failed: "Live-Verbindung gestört – neuer Versuch läuft", proposal: "Automatischer Vorschlag – noch nicht gespeichert",
    schematic: "Schemaplan: Raumgrößen unbekannt, keine Maßstabstreue", estimated: "Teilweise geschätzte Raumgrößen",
    edit: "Grundriss bearbeiten", all_floors: "Alle Etagen", layers: "Ebenen", empty: "Noch keine Raumposition bekannt.",
    layer_action: "Aktion", layer_temperature: "Temperatur", layer_humidity: "Feuchte", layer_co2: "CO₂", layer_airflow: "Luftwege", layer_quality: "Qualität",
    wind_from: "Wind aus", wind_none: "Keine Windrichtung", wind_calm: "Windstill", wind_stale: "Winddaten veraltet", wind_speed_unknown: "Geschwindigkeit unbekannt",
    wind_assumed: "Einheit angenommen (km/h)", ago: "vor", min: "min", source: "Quelle", north_unconfirmed: "Nordrichtung nicht bestätigt – nur grobe Himmelsrichtungen",
    focus_paused: "Auto-Fokus pausiert bis", focus_resume: "Fortsetzen", other_floor: "Handlung auf anderer Etage",
    model: "Modellstufe", topology_only: "nur Verbindungen (keine Richtung)", wind_heuristic: "Wind-Schätzung", opening_aware: "Wind + Öffnungsart (Schätzung)",
    hypothesis: "Luftwege sind eine Schätzung aus Wind, Fassaden und Öffnungen – keine Messung, keine Luftgeschwindigkeit.",
    no_paths: "Kein Luftweg ableitbar.", close: "Schließen", detail: "Details", reason: "Begründung", measured: "gemessen", estimate: "Schätzung",
    not_measured: "nicht gemessen", sensor_missing: "Sensor fehlt", air_exchange: "Luftaustausch (Modellwert)", learning: "Lernproben",
    rate: "Luftwechsel-Koeffizient", quality_ok: "Daten aktuell", quality_bad: "Daten unvollständig", target: "Ziel",
    ah: "abs. Feuchte", surface: "Wandfeuchte (geschätzt)", mould_warn: "Schimmelrisiko-Hinweis (Schätzung)",
    st_closed: "geschlossen", st_tilted: "gekippt", st_open: "ganz offen", st_open_unspecified: "offen – Öffnungsart unbekannt",
    st_unknown: "Zustand unbekannt", st_no_sensor: "ohne Sensor", st_pending: "Kontakt offen – Bestätigung läuft",
    delay: "Verzögerung", s: "s", opening: "Öffnung", wall: "Fassade", windward: "dem Wind zugewandt", leeward: "windabgewandt",
    side: "seitlich angeströmt", calm: "windstill", unknown: "unbekannt", interior: "Innenwand",
    basis: "Grundlage", assumptions: "Annahmen", unknowns: "Unbekannt", confidence: "Vertrauen", low: "gering", medium: "mittel",
    k_cross: "Querlüftung (vermutet)", k_cross_possible: "Austausch möglich (Richtung unbekannt)", k_single_sided: "Einseitiges Lüften: Austausch am Fenster",
    k_exhaust: "Ablüfter: Ersatzluft (vermutet)", k_exhaust_replacement_unconfirmed: "Ablüfter: Ersatzluftweg nicht nachgewiesen",
    b_wind: "Windrichtung", b_facade: "Fassadenlage", b_opening_state: "Öffnungszustand", b_opening_class: "Öffnungsart", b_topology: "Raumverbindungen", b_fan_on: "Ablüfter läuft",
    a_no_obstacles: "keine Hindernisse berücksichtigt", a_no_measured_flow: "keine gemessene Strömung", a_fan_underpressure: "Unterdruck durch Ablüfter angenommen",
    a_reference_is_not_airflow: "Referenzsensor ist kein Nachweis eines Luftwegs",
    u_wind: "Windrichtung", u_infiltration: "Undichtigkeiten", u_replacement_air_path: "Ersatzluftweg",
    floors: { basement: "Keller", ground_floor: "Erdgeschoss", upper_floor: "Obergeschoss", attic: "Dachgeschoss", unassigned: "Ohne Etage" },
    actions: { ventilate: "Jetzt lüften", continue_ventilating: "Weiterlüften", close: "Schließen", ventilate_for_cooling: "Zum Kühlen lüften",
      do_not_ventilate: "Nicht lüften", wait: "Warten", okay: "In Ordnung", check_sensor: "Sensor prüfen", monitor_only: "Nur Beobachtung",
      open_fully: "Ganz öffnen", ventilate_indirectly: "Über Nachbarraum lüften", ventilate_later: "Lüften möglich · noch warten",
      monitor_open: "Daueröffnung überwachen", unknown: "Unbekannt",
      // 0.26.7.0: a room aired only by its exhaust fan has no window to close – the fan's real state decides the word
      fan_off: "Lüfter ausschalten", fan_auto_off: "Lüfter stoppt automatisch", fan_follow_up: "Lüfter-Nachlauf", fan_source: "Lüfter wegen Feuchtequelle",
      fan_completed: "Lüftung beendet", fan_shared: "Gemeinsamer Lüfter läuft", fan_external: "Lüfter extern gesteuert", fan_block: "Lüfter-Sperrzeit" },
    critical: "Kritisch", no_room_data: "keine Raumdaten",
    kpi_wind: "Wind", kpi_forecast: "Prognose", kpi_night: "Nachtprognose", kpi_night_sub: "Feuchte bis zum Morgen", kpi_outdoor: "Draußen",
    tile_temp: "Temperatur", tile_rh: "Luftfeuchte", tile_next5: "Nächste 5 min", openings_title: "Fenster & Türen",
    tile_fan: "Ablüfter", fan_left: "Nachlauf noch {m} min", fan_limit: "spätestens aus {t}",
    streams_note: "Windströme schematisch – Tempo nach Windstärke, keine Messung",
    mould_low: "Schimmelrisiko gering", mould_slightly_elevated: "leicht erhöht", mould_elevated: "erhöht", mould_high: "hoch", mould_very_high: "sehr hoch",
    weather_corner: "Wetter vor Ort", outdoor_temp: "Außentemperatur", outdoor_rh: "Außenluftfeuchte",
    moist_chip: "Entfernbare Feuchtigkeit und Lüftungszeit wie auf der FreshAirIQ-Karte – antippen für die Erklärung", moist_title: "Entfernbare Feuchtigkeit",
    moist_now: "Jetzt entfernbar", moist_now_sub: "in der empfohlenen Lüftungszeit – derselbe Wert wie auf der FreshAirIQ-Karte",
    moist_so_far: "Bisher entfernt", moist_so_far_sub: "seit Beginn der laufenden Lüftung",
    moist_duration: "Empfohlene Lüftungszeit", moist_remaining: "Restzeit", moist_confidence: "Prognosesicherheit", min_short: "Min.", about: "ca.",
    moist_in: "in", moist_left: "noch", moist_possible: "möglich", moist_so_far_chip: "bisher",
    moist_over: "über Ziel", moist_over_tile: "Über Ziel", moist_added: "eingetragen", moist_would_add: "würde eingetragen",
    moist_added_sub: "seit Beginn der Lüftung ist Feuchte hinzugekommen – wie auf der FreshAirIQ-Karte", moist_would_add_sub: "die Außenluft ist feuchter – Lüften würde Feuchte eintragen",
    moist_none: "Zurzeit nichts zu entfernen – die Außenluft ist nicht trockener als die Raumluft oder FreshAirIQ hat noch keinen Wert berechnet.",
    moist_wait: "FreshAirIQ rät gerade abzuwarten – die Menge wäre möglich, eine Lüftungszeit wird deshalb nicht angezeigt.",
    moist_intro_now: "Hier siehst du, wie viel Feuchtigkeit FreshAirIQ voraussichtlich in der empfohlenen Lüftungszeit aus den berechneten Räumen entfernen kann.",
    moist_intro_live: "Hier siehst du die bisher geschätzte Feuchteabgabe der aktuell lüftenden Räume. Der Wert wird anhand neuer Messungen aktualisiert.",
    moist_rooms_now: "Die Liste enthält alle berechneten Räume mit gültigen Messwerten – auch die, die gerade nicht gelüftet werden.",
    moist_rooms_live: "Während einer Lüftung zählen nur die Räume, die gerade gelüftet werden; die übrigen erscheinen wieder, wenn die Lüftung endet.",
    moist_zero: "Direkt nach dem Öffnen kann hier noch 0 ml stehen: Gezählt wird nur der gemessene Rückgang der Raumfeuchte seit Lüftungsbeginn. Viele Feuchtesensoren melden erst nach einer spürbaren Änderung oder in festen Abständen; FreshAirIQ rechnet alle 30 Sekunden und bei jeder neuen Messung neu.",
    moist_more: "Mehr zur Berechnung",
    moist_explain: "Der Wert ist FreshAirIQs „Jetzt entfernbar“ (Sensor „Entfernbare Feuchtigkeit“) – genau wie auf der FreshAirIQ-Karte: die Wassermenge, die alle berechneten Räume des ganzen Hauses (alle Etagen, jeder Raum einmal, nur mit gültigen Messwerten) mit dem gelernten Luftaustausch in der empfohlenen Lüftungszeit voraussichtlich abgeben. Die Zeit ist diese empfohlene Lüftungszeit (aus Außentemperatur und Feuchteunterschied, begrenzt durch deine Einstellungen) – die Menge gilt also für genau diese Zeit, nicht für ein vollständiges Austrocknen. Während einer Lüftung zeigen beide Karten die bisher entfernte Menge und die Restzeit. Die Strömungsbilder sind eine modellierte Darstellung – gemessen sind Temperatur und Feuchte.",
    moist_rooms: "Je Raum",
    need_act: "hier jetzt lüften", need_close: "hier Fenster schließen", need_critical: "hier kritischer Zustand",
    support_title: "Support & Diagnose", support_unavailable: "Der Support-Bereich konnte nicht geladen werden (Fehlercode FAIQ-UI-SUPPORT-001).",
    support_intro: "Hilfe, Diagnose und Feedback – direkt an den FreshAirIQ-Support.", support_diag: "Diagnose", support_message: "Fehlerbeschreibung (Pflicht)",
    support_privacy: "Die Diagnose wird verschlüsselt über Home Assistant an den FreshAirIQ-Diagnose-Server übertragen. Zugangsdaten und Tokens werden nicht übertragen.",
    support_placeholder: "Was ist passiert?", support_export: "Diagnosedaten exportieren", support_send: "Diagnosedaten an Support senden",
    feedback: "Feedback", feedback_kind: "Art der Meldung", feedback_bug: "Fehler / Bug", feedback_idea: "Verbesserungsvorschlag", feedback_other: "Sonstiges",
    feedback_text: "Beschreibung", feedback_secret: "Bitte keine Passwörter, Tokens oder persönlichen Geheimnisse eintragen.", feedback_send: "Meldung senden",
    support_mail: "Support per E-Mail", support_auto: "Automatische Diagnoseübertragung",
    upload_off: "Aus", upload_errors: "Nur bei erkannten Problemen", upload_daily: "Täglich nachts", upload_weekly: "Wöchentlich",
    // 0.26.7.0: rooms overview, moisture by room, weather overview
    rooms_btn: "Räume", rooms_title: "Räume", rooms_jump: "Im Grundriss zeigen", rooms_none: "Noch keine Raumdaten.", mould: "Schimmelrisiko",
    moist_by_room: "Nach Räumen", moist_rounding: "Rundung der Einzelwerte: {d} ml Unterschied zur Summe", moist_room_left: "noch {m} Min.", moist_room_for: "für {m} Min.",
    moist_room_live: "lüftet", moist_room_final: "Endmessung", moist_total: "Summe wie auf der FreshAirIQ-Karte",
    weather_title: "Wetter", weather_open: "Wetterübersicht öffnen",
    info: { temperature: "{v} °C", humidity: "{v} %", absolute_humidity: "{v} g/m³", co2: "{v} ppm", mould: "Schimmel {v}" },
    mould_short: { Low: "niedrig", "Slightly elevated": "leicht", Elevated: "erhöht", High: "hoch", "Very high": "sehr hoch" },
    menu: "Menü", details: "Details", notes: "Hinweise zur Darstellung", connection: "Verbindung ohne eingezeichnete Öffnung", floors_title: "Etagen", guests: "Gäste", guest_adults: "Erwachsene", guest_children: "Kinder",
    guests_readonly: "Gästezahl ist in Home Assistant nicht als Einstellung verfügbar", support: "Support & Diagnose",
    support_hint: "Öffnet die FreshAirIQ-Integration – dort Diagnose herunterladen", source_on: "Feuchtequelle aktiv", fan_running: "Ablüfter läuft",
  },
  en: {
    title: "House map", loading: "Loading house map …", not_loaded: "FreshAirIQ is not loaded.",
    live_failed: "Live connection disrupted – retrying", proposal: "Automatic proposal – not saved yet",
    schematic: "Schematic plan: room sizes unknown, not to scale", estimated: "Some room sizes are estimated",
    edit: "Edit floor plan", all_floors: "All floors", layers: "Layers", empty: "No room position known yet.",
    layer_action: "Action", layer_temperature: "Temperature", layer_humidity: "Humidity", layer_co2: "CO₂", layer_airflow: "Air paths", layer_quality: "Quality",
    wind_from: "Wind from", wind_none: "No wind direction", wind_calm: "Calm", wind_stale: "Wind data outdated", wind_speed_unknown: "speed unknown",
    wind_assumed: "unit assumed (km/h)", ago: "", min: "min ago", source: "Source", north_unconfirmed: "North not confirmed – rough compass directions only",
    focus_paused: "Auto focus paused until", focus_resume: "Resume", other_floor: "Action on another floor",
    model: "Model level", topology_only: "connections only (no direction)", wind_heuristic: "wind estimate", opening_aware: "wind + opening type (estimate)",
    hypothesis: "Air paths are an estimate from wind, facades and openings – not a measurement, no air speed.",
    no_paths: "No air path can be derived.", close: "Close", detail: "Details", reason: "Reason", measured: "measured", estimate: "estimate",
    not_measured: "not measured", sensor_missing: "Sensor missing", air_exchange: "Air exchange (model value)", learning: "Learning samples",
    rate: "Exchange coefficient", quality_ok: "Data up to date", quality_bad: "Data incomplete", target: "Target",
    ah: "abs. humidity", surface: "Wall humidity (estimated)", mould_warn: "Mould risk hint (estimate)",
    st_closed: "closed", st_tilted: "tilted", st_open: "fully open", st_open_unspecified: "open – kind unknown",
    st_unknown: "state unknown", st_no_sensor: "no sensor", st_pending: "Contact open – confirmation running",
    delay: "Delay", s: "s", opening: "Opening", wall: "Facade", windward: "facing the wind", leeward: "sheltered from the wind",
    side: "wind from the side", calm: "calm", unknown: "unknown", interior: "inner wall",
    basis: "Basis", assumptions: "Assumptions", unknowns: "Unknown", confidence: "Confidence", low: "low", medium: "medium",
    k_cross: "Cross ventilation (presumed)", k_cross_possible: "Exchange possible (direction unknown)", k_single_sided: "Single-sided airing: exchange at the window",
    k_exhaust: "Exhaust fan: replacement air (presumed)", k_exhaust_replacement_unconfirmed: "Exhaust fan: replacement air path not proven",
    b_wind: "wind direction", b_facade: "facade orientation", b_opening_state: "opening state", b_opening_class: "opening type", b_topology: "room connections", b_fan_on: "exhaust fan running",
    a_no_obstacles: "no obstacles considered", a_no_measured_flow: "no measured flow", a_fan_underpressure: "under-pressure from the fan assumed",
    a_reference_is_not_airflow: "a reference sensor does not prove an air path",
    u_wind: "wind direction", u_infiltration: "leaks", u_replacement_air_path: "replacement air path",
    floors: { basement: "Basement", ground_floor: "Ground floor", upper_floor: "Upper floor", attic: "Attic", unassigned: "No floor" },
    actions: { ventilate: "Air now", continue_ventilating: "Keep airing", close: "Close", ventilate_for_cooling: "Air for cooling",
      do_not_ventilate: "Do not air", wait: "Wait", okay: "All good", check_sensor: "Check sensor", monitor_only: "Monitoring only",
      open_fully: "Open fully", ventilate_indirectly: "Air via a connected room", ventilate_later: "Airing possible · wait for now",
      monitor_open: "Long opening monitored", unknown: "Unknown",
      fan_off: "Switch the fan off", fan_auto_off: "Fan stops automatically", fan_follow_up: "Fan follow-up", fan_source: "Fan for a moisture source",
      fan_completed: "Airing finished", fan_shared: "Shared fan running", fan_external: "Fan run by another automation", fan_block: "Fan lock period" },
    critical: "Critical", no_room_data: "no room data",
    kpi_wind: "Wind", kpi_forecast: "Forecast", kpi_night: "Night forecast", kpi_night_sub: "humidity until morning", kpi_outdoor: "Outdoors",
    tile_temp: "Temperature", tile_rh: "Humidity", tile_next5: "Next 5 min", openings_title: "Windows & doors",
    tile_fan: "Exhaust fan", fan_left: "follow-up {m} min left", fan_limit: "off at the latest {t}",
    streams_note: "Wind streams are schematic – speed follows the wind, not a measurement",
    mould_low: "mould risk low", mould_slightly_elevated: "slightly elevated", mould_elevated: "elevated", mould_high: "high", mould_very_high: "very high",
    weather_corner: "Local weather", outdoor_temp: "Outdoor temperature", outdoor_rh: "Outdoor humidity",
    moist_chip: "Removable moisture and airing time as on the FreshAirIQ card – tap for the explanation", moist_title: "Removable moisture",
    moist_now: "Removable now", moist_now_sub: "within the recommended airing time – the same value as on the FreshAirIQ card",
    moist_so_far: "Removed so far", moist_so_far_sub: "since the current airing started",
    moist_duration: "Recommended airing time", moist_remaining: "Time left", moist_confidence: "Forecast confidence", min_short: "min", about: "approx.",
    moist_in: "in", moist_left: "left", moist_possible: "possible", moist_so_far_chip: "so far",
    moist_over: "over target", moist_over_tile: "Over target", moist_added: "added", moist_would_add: "would be added",
    moist_added_sub: "moisture was added since the airing started – as on the FreshAirIQ card", moist_would_add_sub: "the outdoor air is more humid – airing would add moisture",
    moist_none: "Nothing to remove at the moment – the outdoor air is not drier than the room air, or FreshAirIQ has not computed a value yet.",
    moist_wait: "FreshAirIQ advises to wait right now – the amount would be possible, so no airing time is shown.",
    moist_intro_now: "This shows how much moisture FreshAirIQ expects to remove from the calculated rooms within the recommended airing time.",
    moist_intro_live: "This shows the estimated moisture given off so far by the rooms being aired right now. The value is updated with new readings.",
    moist_rooms_now: "The list holds every calculated room with valid readings – also those not being aired right now.",
    moist_rooms_live: "While airing, only the rooms being aired count; the others come back when the airing ends.",
    moist_zero: "Right after opening this can still read 0 ml: only the measured drop in room humidity since the airing started is counted. Many humidity sensors report only after a noticeable change or at fixed intervals; FreshAirIQ recalculates every 30 seconds and with every new reading.",
    moist_more: "More about the calculation",
    moist_explain: "The value is FreshAirIQ's \"removable now\" (sensor \"Removable moisture\") – exactly as on the FreshAirIQ card: the water all calculated rooms of the whole house (all floors, each room once, valid readings only) are expected to give off with their learned air exchange within the recommended airing time. The time is that recommended airing time (from outdoor temperature and humidity difference, limited by your settings) – so the amount belongs to exactly this time, not to drying out completely. While airing, both cards show the amount removed so far and the time left. The air movement is a modelled picture – temperature and humidity are measured.",
    moist_rooms: "Per room",
    need_act: "air here now", need_close: "close windows here", need_critical: "critical state here",
    support_title: "Support & diagnostics", support_unavailable: "The support section could not be loaded (error code FAIQ-UI-SUPPORT-001).",
    support_intro: "Help, diagnostics and feedback – straight to FreshAirIQ support.", support_diag: "Diagnostics", support_message: "Problem description (required)",
    support_privacy: "The diagnostics are sent encrypted through Home Assistant to the FreshAirIQ diagnostics server. Credentials and tokens are not sent.",
    support_placeholder: "What happened?", support_export: "Export diagnostics", support_send: "Send diagnostics to support",
    feedback: "Feedback", feedback_kind: "Kind of report", feedback_bug: "Problem / bug", feedback_idea: "Suggestion", feedback_other: "Other",
    feedback_text: "Description", feedback_secret: "Please do not enter passwords, tokens or personal secrets.", feedback_send: "Send report",
    support_mail: "Support by e-mail", support_auto: "Automatic diagnostics upload",
    upload_off: "Off", upload_errors: "Only on detected problems", upload_daily: "Nightly", upload_weekly: "Weekly",
    rooms_btn: "Rooms", rooms_title: "Rooms", rooms_jump: "Show on the plan", rooms_none: "No room data yet.", mould: "Mould risk",
    moist_by_room: "By room", moist_rounding: "Rounding of the room values: {d} ml difference to the total", moist_room_left: "{m} min left", moist_room_for: "for {m} min",
    moist_room_live: "airing", moist_room_final: "final measurement", moist_total: "Total as on the FreshAirIQ card",
    weather_title: "Weather", weather_open: "Open the weather overview",
    info: { temperature: "{v} °C", humidity: "{v} %", absolute_humidity: "{v} g/m³", co2: "{v} ppm", mould: "mould {v}" },
    mould_short: { Low: "low", "Slightly elevated": "slight", Elevated: "elevated", High: "high", "Very high": "very high" },
    menu: "Menu", details: "Details", notes: "About this view", connection: "Connection without a drawn opening", floors_title: "Floors", guests: "Guests", guest_adults: "Adults", guest_children: "Children",
    guests_readonly: "The guest count is not available as a setting in Home Assistant", support: "Support & diagnostics",
    support_hint: "Opens the FreshAirIQ integration – download diagnostics there", source_on: "Moisture source active", fan_running: "Exhaust fan running",
  },
};
const ACTION_CODES = { "Ventilate": "ventilate", "Continue ventilating": "continue_ventilating", "Close": "close", "Ventilate for cooling": "ventilate_for_cooling",
  "Do not ventilate": "do_not_ventilate", "Wait": "wait", "Okay": "okay", "Check sensor": "check_sensor", "Monitor only": "monitor_only",
  "Open fully": "open_fully", "Ventilate indirectly": "ventilate_indirectly" };
const TONE = { ventilate: "act", ventilate_for_cooling: "act", open_fully: "act", ventilate_indirectly: "act", continue_ventilating: "run",
  close: "close", wait: "wait", do_not_ventilate: "wait", check_sensor: "sensor", okay: "ok", monitor_only: "ok",
  // house-aligned codes (opening_strategy.house_aligned_room_actions): held back by the house = waiting, a tolerated
  // long opening = a supervised airing (never the close colour – hard closes never become monitor_open)
  ventilate_later: "wait", monitor_open: "run" };
// Tone of the house recommendation by its kind (recommendation.py / consolidation.py: ventilate, continue, close,
// wait, prepare, pollen_wait, okay, sensor). Warnings and unknown kinds are never shown as a plain "all good".
const REC_TONE = { ventilate: "act", continue: "run", keep: "run", close: "close", wait: "wait", prepare: "wait", pollen_wait: "wait",
  sensor: "sensor", okay: "ok", ok: "ok", none: "ok" };
export const heroTone = rec => {
  const tone = REC_TONE[String((rec && rec.kind) || "")] || "wait";
  return tone === "ok" && ["warning", "danger"].includes(String((rec && rec.severity) || "")) ? "wait" : tone;
};
// A selector for the focused control that survives a re-render (its data attribute and value).
const FOCUS_ATTRS = ["data-floor", "data-layer", "data-room", "data-opening", "data-path", "data-edit", "data-resume", "data-close-detail", "data-motion-level", "data-nav-back"];  // 0.26.7.0 UI hotfix: the Animation buttons and Back keep the focus too
export const focusKey = el => {
  if (!el || !el.getAttribute) return "";
  const attr = FOCUS_ATTRS.find(a => el.hasAttribute(a));
  if (!attr) return "";
  const inDialog = el.closest && el.closest("dialog") ? "dialog " : "";
  return `${inDialog}${el.tagName.toLowerCase()}[${attr}="${String(el.getAttribute(attr)).replace(/["\\]/g, "\\$&")}"]`;
};
// A number that is really known: null, undefined, "" and text are unknown (Number(null) would be 0).
export const known = value => (value == null || value === "" || typeof value === "boolean" ? NaN : Number(value));
// Unsubscribe callbacks of home-assistant-js-websocket may return a promise (rejected on a closed socket).
const release = unsubs => { for (const unsub of unsubs) { try { Promise.resolve(unsub()).catch(() => {}); } catch (_) { /* gone */ } } };
const PRIORITY = { critical: 3, close: 3, sensor: 2, act: 2, run: 1, wait: 1, ok: 0 };
// 0.26.7.0: what a room shows on the plan (card option room_info, per room room_overrides) – any combination
export const ROOM_INFO = ["name", "temperature", "humidity", "absolute_humidity", "action", "co2", "mould"];
const list = value => (Array.isArray(value) ? value : String(value == null ? "" : value).split(",")).map(x => String(x).trim()).filter(Boolean);
export const roomInfo = (config, roomKey) => {
  const own = config && config.room_overrides && typeof config.room_overrides === "object" ? config.room_overrides[roomKey] : null;
  const chosen = own != null ? list(own) : config && config.room_info != null ? list(config.room_info) : null;
  return chosen == null ? null : ROOM_INFO.filter(k => chosen.includes(k));   // null: the classic label (name, state, layer readings)
};
// 0.26.7.0: the floors a card shows (floors_visible: ids, level keys or names) – never none
export const visibleFloors = (floors, wanted) => {
  const keys = list(wanted).map(x => x.toLowerCase());
  if (!keys.length) return floors;
  const shown = floors.filter(f => [f.id, f.level_key, f.name].some(v => keys.includes(String(v || "").toLowerCase())));
  return shown.length ? shown : floors;
};

// 0.26.6.1(7): the real width of a label text in px (canvas, the card's font stack); an estimate without a canvas
let measureCtx = null;
export const textWidth = (text, size, weight = 700) => {
  try {
    if (!measureCtx) measureCtx = document.createElement("canvas").getContext("2d");
    measureCtx.font = `${weight} ${size}px Nunito, "Baloo 2", ui-rounded, "SF Pro Rounded", "Segoe UI", system-ui, sans-serif`;
    return measureCtx.measureText(String(text)).width;
  } catch (_) { return String(text).length * size * 0.6; }
};
// 0.26.6.1(7): a short form of a room name for small rooms – its last word when that is short ("Gäste-WC" → "WC",
// "Kinderzimmer Nord" → "Nord"), else the name itself (shortened with an ellipsis where needed)
export const shortName = name => { const last = String(name).trim().split(/[\s\-–/]+/).filter(Boolean).pop() || String(name); return last.length <= 5 && last !== String(name).trim() ? last : String(name); };
// 0.26.6.1(9): a compound room name in two rows – at a space or hyphen, else before a common German room word
// ("Arbeitszimmer" → "Arbeits-" / "zimmer"); null when it cannot be split sensibly
const ROOM_WORDS = ["zimmer", "küche", "kueche", "raum", "keller", "kammer", "diele", "garage", "stube", "bad", "room", "kitchen"];
export const splitName = name => {
  const n = String(name).trim(), at = n.search(/[\s\-–/]/);
  if (at > 1 && at < n.length - 2) return [n.slice(0, n[at] === " " ? at : at + 1), n.slice(at + 1).trim()];
  const low = n.toLowerCase(), word = ROOM_WORDS.find(w => low.endsWith(w) && n.length - w.length >= 3);
  return word ? [`${n.slice(0, n.length - word.length)}-`, n.slice(n.length - word.length)] : null;
};
export const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// 0.26.7.0: the room is aired by its exhaust fan alone (no window open) – the same rule as the integration
// (close_wording.fan_only) and the FreshAirIQ dashboard card (fanOnlyRoom)
export const fanOnlyRoom = r => { const a = (r && r.configured_actuators) || {}; return !!r && !a.window_open && (Boolean(a.mechanical_exhaust_active) || a.ventilation_type === "mechanical_exhaust"); };
// States in which FreshAirIQ stops the fan itself (fan_automation.AUTO_STOP_STATES): a status, no task for the user
const FAN_CLOSE = { stopping: ["fan_auto_off", "run"], follow_up: ["fan_follow_up", "run"], source: ["fan_source", "run"], completed: ["fan_completed", "ok"],
  shared: ["fan_shared", "run"], external: ["fan_external", "run"], blocked_time: ["fan_block", "wait"] };
// "Close" for a fan-only room: what the fan really does – switch it off by hand (manual, failed, no automation, automation
// lock) or FreshAirIQ / another automation / the lock period handles it. null for every other room or action.
export const fanClose = room => {
  if (!room || actionCode(room) !== "close" || !fanOnlyRoom(room)) return null;
  const [word, tone] = FAN_CLOSE[String((room.fan_automation && room.fan_automation.state) || "")] || ["fan_off", "close"];
  return { word, tone };
};
export const actionCode = room => {
  if (!room) return "unknown";
  if (room.house_aligned_action) return String(room.house_aligned_action);
  const action = String(room.action || "");
  return ACTION_CODES[action] || action.trim().toLowerCase().replace(/ /g, "_") || "unknown";
};
// Mould levels as published per room (model._mould_level): "High" = at/above the warning limit,
// "Very high" = at/above the critical limit. The limits themselves are options, not room fields.
export const MOULD_WARNING = new Set(["High", "Very high"]);
export const mouldWarning = room => !!room && MOULD_WARNING.has(String(room.mould_level || ""));
// Display tone of a room: the canonical action, raised to "critical" by a critical mould level and never
// green with a mould warning, "sensor" without valid data. Presentation only – the action itself is unchanged.
// 0.26.5.5: a real follow-up countdown from the fan control's end time; else when the maximum runtime stops it
export const fanCountdown = (fa, now, t, lang) => {
  const left = Math.ceil((Date.parse((fa && fa.follow_up_until) || "") - now) / 60000);
  if (left > 0) return t("fan_left").replace("{m}", left);
  const limit = Date.parse((fa && fa.runtime_limit_at) || "");
  return limit > now ? t("fan_limit").replace("{t}", new Date(limit).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" })) : "";
};
export const roomTone = room => {
  if (!room) return "sensor";
  if (String(room.mould_level || "") === "Very high") return "critical";
  const fan = fanClose(room);
  const tone = room.data_quality && room.data_quality !== "ok" ? "sensor" : fan ? fan.tone : TONE[actionCode(room)] || "wait";
  if (tone === "ok" && mouldWarning(room)) return "wait";
  return tone;
};
// 0.26.6.1(2): the action a floor needs, for its pulsing button – "critical" before "close" before "act" (air now).
// Waiting, a running airing, sensor trouble and normal values are no reason to pulse.
const PULSE = ["critical", "close", "act"];
export const floorAction = (layout, rooms, floorId) => {
  const tones = new Set((layout.rooms || []).filter(r => r.floor_id === floorId).map(r => roomTone(rooms[r.room_key])));
  return PULSE.find(tone => tones.has(tone)) || null;
};
export const floorPriority = (layout, rooms, floorId) => Math.max(0, ...(layout.rooms || []).filter(r => r.floor_id === floorId).map(r => PRIORITY[roomTone(rooms[r.room_key])] || 0));

// Auto focus: a newly appeared relevant action on another floor moves the view there (mode "auto"),
// unless the user picked a floor (lock) or the last automatic switch was less than a minute ago.
export const focusDecision = ({ mode, current, priorities, previous, lockUntil, lastAutoAt, now }) => {
  if (current === "__all") return { floor: current, hint: null }; // the overview already shows every floor
  const rising = Object.keys(priorities).filter(f => f !== current && priorities[f] >= 2 && priorities[f] > (previous[f] || 0));
  if (!rising.length) return { floor: current, hint: null };
  const best = rising.sort((a, b) => priorities[b] - priorities[a] || a.localeCompare(b))[0];
  if (mode === "auto" && !(lockUntil && now < lockUntil) && !(lastAutoAt && now - lastAutoAt < AUTO_COOLDOWN_MS)) return { floor: best, hint: null, switched: true };
  return { floor: current, hint: mode === "off" ? null : best };
};


// 0.26.7.0(2): what the windows module (freshairiq-house-panels.js) needs from the card – the same words, tones and rules
const H = { T, roomTone, actionCode, fanClose, fanCountdown, mouldWarning, known, heroTone, chosenLevel: M.chosenLevel };
class FreshAirIQHouseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {}; this._hass = null; this._rooms = {}; this._roomsLang = null; this._house = null; this._layoutInfo = null;
    this._proposal = null; this._floor = null; this._layer = "action"; this._selected = null; this._lockUntil = 0; this._lastAutoAt = 0;
    this._prevPriorities = {}; this._hint = null; this._subs = []; this._failed = false; this._editing = null; this._windSmooth = null; this._frame = null;
    // hotfix F01: one start at a time; _gen ends a start that a disconnect or a newer start overtook
    this._gen = 0; this._starting = false; this._retry = null;
    // re-audit F01/F02: the subscription target (connection + entry) and one layout request at a time
    this._subConn = null; this._subEntry = null; this._wantRev = undefined; this._layoutBusy = null;
    // hotfix F02 / re-audit F03: a live update waits while a finger or pointer is down on the card – for as long
    // as it stays down (no time limit). Released by pointerup/cancel, the last touchend (touches = 0), a mouse
    // button let go, the page hidden or the window blurred, and – only for a release that never arrived – a
    // minute without any pointer or touch event.
    this._pointers = new Set(); this._touching = false; this._gestureSeen = 0; this._pending = false;
    this._lastActive = Date.now();   // 0.26.7.0(2): the last touch, click or key – a long untouched card calms its motion
    this._onKey = () => this._touched();
    this._onDown = ev => {
      this._gestureSeen = Date.now(); this._touched();
      if (ev && ev.type === "touchstart") this._touching = true;
      else if (ev && ev.pointerId != null) this._pointers.add(ev.pointerId);
    };
    this._onMove = () => { if (this._gestureActive()) this._gestureSeen = Date.now(); };
    this._onUp = ev => {
      if (!this._gestureActive()) return;
      this._gestureSeen = Date.now();
      if (ev && (ev.type === "touchend" || ev.type === "touchcancel")) {
        this._touching = !!(ev.touches && ev.touches.length);
        if (!this._touching) this._pointers.clear();  // no finger left on the screen
      } else if (ev && ev.pointerId != null) {
        this._pointers.delete(ev.pointerId);
        if (ev.pointerType === "mouse" || ev.buttons === 0 && ev.pointerType !== "touch") this._pointers.clear();
      } else { this._pointers.clear(); this._touching = false; }  // blur / hidden page
      if (!this._gestureActive() && this._pending) { this._pending = false; this._queue(); }
    };
    this._onVisibility = () => { if (document.hidden) this._onUp(null); else this._touched(); this._syncPaused(); };
  }
  static getConfigElement() { return document.createElement("freshairiq-house-card-editor"); }
  static get weatherModule() { return W; }   // 0.26.7.0: for the tests (shared forecast subscriptions)
  static getStubConfig() { return { auto_focus: "hint" }; }
  setConfig(config) {
    if (config && config.auto_focus && !FOCUS_MODES.includes(config.auto_focus)) throw new Error("auto_focus: off | hint | auto");
    if (config && config.weather_effects && !W.EFFECT_LEVELS.includes(config.weather_effects)) throw new Error("weather_effects: off | subtle | dynamic | full");
    if (config && config.layout && !W.LAYOUTS.includes(config.layout)) throw new Error("layout: auto | focus | info");
    if (config && config.animation_level && !M.ANIMATION_LEVELS.includes(config.animation_level)) throw new Error("animation_level: off | minimal | normal | intense | auto");
    if (config && config.design && !D.DESIGN_MODES.includes(config.design)) throw new Error("design: freshairiq | ha | custom");
    const before = this._config.entry_id || null;
    this._config = Object.assign({ auto_focus: "hint", layer: "action", manual_lock_min: 10, animation: true }, config || {});
    if (LAYERS.includes(this._config.layer)) this._layer = this._config.layer;
    // re-audit F01: another FreshAirIQ entry – the subscriptions and the data of the old one end here
    if ((this._config.entry_id || null) !== before && (this._subs.length || this._starting || this._subEntry !== null || this._layoutInfo)) {
      this._stop();
      this._layoutInfo = null; this._proposal = null; this._rooms = {}; this._payload = null; this._house = null; this._selected = null;
      this._start();
    }
    this._restore();
    this._queue();
    this._applyMotion();  // 0.26.7.0(2): the animation level – "animation: false" (still) as before, now also off/minimal/normal/intense/auto
    this._windSync();  // hotfix F04: "animation: false" stops a running wind loop at once
    this.setAttribute("data-fx", this._fx());  // 0.26.7.0: the weather effect level (CSS)
    this._applyDesign();  // 0.26.7.0 UI order: the card's design (FreshAirIQ unless chosen otherwise)
    this._syncForecast();  // a changed weather entity: the old forecast subscription ends
  }
  // ---- 0.26.7.0 UI order: the design of this card (custom properties on this card only – never global, never another card)
  _applyDesign() {
    const mode = D.designMode(this._config), style = this.style;
    for (const k of this._designKeys || []) style.removeProperty(k);
    this._designKeys = [];
    if (mode === "freshairiq") { for (const a of ["data-design", "data-scheme", "data-glass"]) this.removeAttribute(a); this._designIssues = []; return; }
    let p, vars = {};
    if (mode === "custom") {
      const c = D.customChoice(this._config), solid = c.background && c.background !== "transparent" ? c.background : null;
      p = D.palette({ dialog: c.dialog || solid, accent: c.accent, textMode: c.text });
      vars = { "--fq-card-bg": c.background === "transparent" ? "transparent" : solid ? D.css(solid) : p.vars["--fq-dlg-bg"],
        "--fq-card-fg": solid ? D.onColor(solid) : p.vars["--fq-fg"], "--fq-card-line": p.vars["--fq-line"] };
      if (c.border != null) vars["--fq-border-w"] = `${c.border}px`;
      if (c.radius != null) vars["--fq-radius"] = `${c.radius}px`;
      this.toggleAttribute("data-glass", c.background === "transparent");
      if (c.background === "transparent") vars["--fq-card-blur"] = "blur(10px)";
      this._designIssues = [...c.issues, ...p.issues];
    } else {
      // the theme's colours as this card sees them (resolved by the browser); a translucent ("glass") card stays so,
      // its windows get an opaque colour over the theme's page colour
      const r = this._themeColors();
      p = D.palette({ dialog: r.card, text: r.text, muted: r.secondary, accent: r.accent, onAccent: r.onAccent, base: r.page });
      vars = { "--fq-card-bg": "var(--ha-card-background,var(--card-background-color,#fff))", "--fq-card-fg": r.card && r.text && r.card[3] >= 0.98 && D.contrast(r.text, r.card) >= 4.5 ? D.css(r.text) : p.vars["--fq-fg"],
        "--fq-card-line": "var(--ha-card-border-color,var(--divider-color,rgba(0,0,0,.12)))", "--fq-border-w": "var(--ha-card-border-width,1px)",
        "--fq-radius": "var(--ha-card-border-radius,12px)", "--fq-card-shadow": "var(--ha-card-box-shadow,none)", "--fq-card-blur": "var(--ha-card-backdrop-filter,none)" };
      this.toggleAttribute("data-glass", !!(r.card && r.card[3] < 0.98));
      this._designIssues = p.issues;
    }
    for (const [k, v] of Object.entries({ ...D.paletteVars(p), ...vars })) { style.setProperty(k, v); this._designKeys.push(k); }
    this.setAttribute("data-design", mode); this.setAttribute("data-scheme", p.scheme);
  }
  _themeColors() {
    const root = this.shadowRoot;
    if (!root || !this.isConnected) return {};
    let probe = root.querySelector("span[data-theme-probe]");
    if (!probe) { probe = document.createElement("span"); probe.dataset.themeProbe = ""; probe.hidden = true; root.appendChild(probe); }
    const read = value => { probe.style.color = ""; probe.style.color = value; const c = D.parseRgb(getComputedStyle(probe).color); return c; };
    return { card: read("var(--ha-card-background,var(--card-background-color,#ffffff))"), text: read("var(--primary-text-color,#212121)"),
      secondary: read("var(--secondary-text-color,#727272)"), accent: read("var(--primary-color,#03a9f4)"), onAccent: read("var(--text-primary-color,#ffffff)"),
      page: read("var(--primary-background-color,#fafafa)") };
  }
  // ---- 0.26.7.0: weather world settings
  _fx() { return W.EFFECT_LEVELS.includes(this._config.weather_effects) ? this._config.weather_effects : "dynamic"; }   // "dynamic" = the look until now
  _info() { return this._config.weather_info == null ? W.DEFAULT_WEATHER_INFO : list(this._config.weather_info).filter(k => W.WEATHER_INFO.includes(k)); }
  _details() { return W.detailsFor(this._config); }   // 0.26.7.0(2) error A: the values the card shows, never brought back by themselves
  // ---- 0.26.7.0(2): how much moves – the level the user chose, the device, reduced motion, how long the card was untouched
  _reduced() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  _motion() { return M.motionProfile({ config: this._config, reduced: this._reduced(), small: M.isSmallDevice(this._lastWidth), idleMs: Date.now() - this._lastActive }); }
  _applyMotion() {
    const m = this._motion(); this._motionNow = m;
    this.toggleAttribute("data-still", this._config.animation === false || m.level === "off" || m.level === "rest");  // no breathing rooms either
    this.toggleAttribute("data-rest", m.level === "rest");
    this.setAttribute("data-motion", m.level);
    for (const part of M.MOTION_PARTS) this.toggleAttribute(`data-no-${part}`, !m.still && !m.parts[part]);
    // one timer, only for the next step down (calm, then rest); a touch moves it on
    clearTimeout(this._idleTimer); this._idleTimer = null;
    const idle = Date.now() - this._lastActive, next = m.still ? null : idle < M.CALM_AFTER_MS ? M.CALM_AFTER_MS : idle < M.REST_AFTER_MS ? M.REST_AFTER_MS : null;
    if (next != null && this.isConnected) this._idleTimer = setTimeout(() => { this._idleTimer = null; this._queue(); }, next - idle + 50);
    return m;
  }
  // a touch, a click or a key wakes a calmed card at once (at most once a second the work of re-deciding)
  _touched() {
    const now = Date.now(), was = this._motionNow && this._motionNow.level;
    this._lastActive = now;
    if ((was === "rest" || (was === "minimal" && M.chosenLevel(this._config) !== "minimal" && !M.isSmallDevice(this._lastWidth))) && now - (this._wokeAt || 0) > 1000) { this._wokeAt = now; this._queue(); }
  }
  _weatherEntity() {
    const own = String(this._config.weather_entity || "").trim();
    if (own) return own;
    const src = this._house && this._house.wind && this._house.wind.source;   // the weather entity FreshAirIQ itself uses
    return typeof src === "string" && src.startsWith("weather.") ? src : null;
  }
  _moonState() {
    const states = (this._hass && this._hass.states) || {}, own = String(this._config.moon_entity || "").trim();
    return states[own] || states["sensor.moon_phase"] || states["sensor.moon"] || null;
  }
  _weatherModel() {
    const states = (this._hass && this._hass.states) || {}, id = this._weatherEntity(), fc = this._forecast || {};
    const hw = this._house && this._house.wind;   // FreshAirIQ's wind: a current reading (also calm), never a stale one
    return W.weatherModel({ entityId: id, entity: id ? states[id] : null, weatherNow: this._payload && this._payload.weather_now, sun: states["sun.sun"],
      wind: hw && (hw.available || hw.calm) && !hw.stale ? hw : null, hourly: fc.hourly, daily: fc.daily, moon: this._moonState(), own: !!String(this._config.weather_entity || "").trim(),
      outdoor: this._payload ? { temperature: this._payload.outdoor_temperature, humidity: this._payload.outdoor_humidity, absolute_humidity: this._payload.outdoor_absolute_humidity } : null });
  }
  // 0.26.7.0: the outdoor wind of the picture (streams, air field, mood, wind tile). With a weather entity chosen in the card
  // its speed, gusts and direction are used; a value it lacks comes from FreshAirIQ (weatherModel.windSource says which).
  // Without an own entity: FreshAirIQ's wind as until now. The indoor air paths stay FreshAirIQ's ventilation model.
  _outdoorWind() {
    const house = this._house && this._house.wind;
    if (!String(this._config.weather_entity || "").trim()) return { wind: house, smooth: this._windSmooth };
    const m = this._weatherModel(), src = m.windSource || {};
    if (src.bearing !== "entity" && src.speed !== "entity" && src.gust !== "entity") return { wind: house, smooth: this._windSmooth };
    const calm = m.windMs != null && m.windMs < 0.5;
    this._windSmoothOwn = m.bearing == null ? null : G.smoothBearing(this._windSmoothOwn, m.bearing);
    return { smooth: this._windSmoothOwn, wind: { available: m.bearing != null && m.windMs != null && !calm, reason: null, from_deg: m.bearing, to_deg: m.bearing == null ? null : (m.bearing + 180) % 360,
      speed_ms: m.windMs, gust_ms: m.gustMs, calm, stale: false, age_s: null, source: m.entityId, sources: src,
      label_de: W.compassPoint(m.bearing, "de"), label_en: W.compassPoint(m.bearing, "en") } };
  }
  _tz() { return W.haTimeZone(this._hass); }
  // Home Assistant's location (for the sun's day in the weather window); null when it is not known
  _geo() { const c = this._hass && this._hass.config; return c && Number.isFinite(Number(c.latitude)) && Number.isFinite(Number(c.longitude)) && c.latitude !== null && c.longitude !== null ? { lat: Number(c.latitude), lon: Number(c.longitude) } : null; }
  // Forecasts only while something shows them (overview open, side panel) – one shared subscription per entity and type
  _syncForecast() {
    const info = this._info(), wanted = (this._selected && this._selected.type === "weather") || this._sideShown;
    const id = wanted && this.isConnected ? this._weatherEntity() : null, conn = this._hass && this._hass.connection;
    const overview = !!(this._selected && this._selected.type === "weather");
    const types = id ? [...(info.includes("hourly") || this._sideShown ? ["hourly"] : []), ...(overview && info.includes("daily") ? ["daily"] : [])] : [];
    const key = id && types.length ? `${id}|${types.join(",")}` : null;
    if (key === this._fcKey && conn === this._fcConn) return;
    this._fcStop();
    this._fcKey = key; this._fcConn = conn;
    if (!key) return;
    this._fcUnsubs = types.map(type => W.subscribeForecast(conn, id, type, rows => { this._forecast = { ...this._forecast, [type]: rows || [], [`${type}Failed`]: rows === null }; this._queue(); }));
  }
  _fcStop() { for (const unsub of this._fcUnsubs || []) unsub(); this._fcUnsubs = []; this._forecast = {}; this._fcKey = null; }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    // 0.26.7.0 UI order: a theme switched in Home Assistant (light/dark, another theme) is taken over at once
    const theme = hass && hass.themes;
    if (theme !== this._themeSeen) { this._themeSeen = theme; if (D.designMode(this._config) === "ha") requestAnimationFrame(() => this._applyDesign()); }
    if (this._editing) this._editing.hass = hass; // the editor keeps its own state; no re-render on hass
    // re-audit F01: a new Home Assistant connection – subscribe there once and release the old ones
    const conn = hass && hass.connection;
    if (this._subConn && conn !== this._subConn) { this._stop(); this._start(); return; }
    if (first || (!this._subs.length && !this._failed)) this._start();
    // 0.26.6.1(7): day, twilight and night follow sun.sun – redraw when the phase changes, not on every state
    // 0.26.6.1(10): also when the sun moves on within the same phase – in 2° steps of azimuth and elevation (about
    // every eight minutes), not on every state change of Home Assistant
    const sunNow = A.skyState(null, hass && hass.states && hass.states["sun.sun"]);
    const sunKey = `${sunNow.phase}|${sunNow.azimuth == null ? "-" : Math.round(sunNow.azimuth / 2)}|${sunNow.elevation == null ? "-" : Math.round(sunNow.elevation / 2)}`;
    if (!first && sunKey !== this._sunKey && this._layoutInfo) this._queue();
    this._sunKey = sunKey; this._sunPhase = sunNow.phase;
    // 0.26.7.0: a new reading of the weather entity redraws the weather world (not every other state change)
    const wid = this._weatherEntity(), wst = wid && hass && hass.states ? hass.states[wid] : null, wKey = wst ? `${wst.state}|${wst.last_updated}` : "";
    if (!first && wKey !== this._wxKey && this._layoutInfo) this._queue();
    this._wxKey = wKey;
  }
  get hass() { return this._hass; }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: 8, min_rows: 4 }; }
  connectedCallback() {
    document.addEventListener("visibilitychange", this._onVisibility);
    if (D.designMode(this._config) === "ha") requestAnimationFrame(() => this._applyDesign());   // the theme is known once connected
    // 0.26.7.0(2): the FreshAirIQ card's English texts arrive later on an English dashboard – its views are drawn again then
    this._onEnglish = this._onEnglish || (() => { if (this._lang() === "en") this._queue(); });
    window.addEventListener("freshairiq-i18n-en-ready", this._onEnglish);
    for (const type of ["touchstart", "pointerdown"]) this.addEventListener(type, this._onDown, { passive: true });
    this.addEventListener("keydown", this._onKey, { passive: true });
    this._lastActive = Date.now();
    for (const type of ["touchend", "touchcancel", "pointerup", "pointercancel", "blur"]) window.addEventListener(type, this._onUp, { passive: true });
    for (const type of ["touchmove", "pointermove"]) window.addEventListener(type, this._onMove, { passive: true });
    // "reduce motion" switched while the card is shown: stop or continue the wind right away
    if (!this._motionQuery && window.matchMedia) {
      this._motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this._onMotion = () => { this._windSync(); this._queue(); };  // the air layer switches between moving and still
      if (this._motionQuery.addEventListener) this._motionQuery.addEventListener("change", this._onMotion);
    }
    if (!this._resize && typeof ResizeObserver === "function") {
      // the labels keep a readable pixel size: re-render when the card width really changes
      this._resize = new ResizeObserver(entries => { const w = Math.round(entries[0].contentRect.width); if (w && Math.abs(w - (this._observedWidth || 0)) > 24) { this._observedWidth = w; this._queue(); } });
      this._resize.observe(this);
    }
    // 0.26.7.0: a card scrolled out of view pauses its animations (like a hidden page)
    if (!this._io && typeof IntersectionObserver === "function") {
      this._io = new IntersectionObserver(entries => { const off = !entries[entries.length - 1].isIntersecting; if (this._offscreen && !off) this._touched(); this._offscreen = off; this._syncPaused(); });
      this._io.observe(this);
    }
    if (this._config.default_floor) this._floor = null;   // 0.26.7.0: this floor whenever the card is opened
    if (this._hass && !this._subs.length) this._start();
    this._syncForecast();
    this._queue();
  }
  _syncPaused() {
    // 0.26.7.0(2): also while a window of the card covers the plan (room, rooms, weather, menu, support) – nobody sees it move
    const paused = document.hidden || !!this._offscreen || !!this._covered;
    this.toggleAttribute("data-paused", paused);
    if (paused) this._windStop(); else this._windSync();
  }
  disconnectedCallback() {
    if (this._io) { this._io.disconnect(); this._io = null; }
    this._fcStop(); this._fcConn = null;
    document.removeEventListener("visibilitychange", this._onVisibility);
    if (this._onEnglish) window.removeEventListener("freshairiq-i18n-en-ready", this._onEnglish);
    clearTimeout(this._idleTimer); this._idleTimer = null;
    this.removeEventListener("keydown", this._onKey);
    for (const type of ["touchstart", "pointerdown"]) this.removeEventListener(type, this._onDown);
    for (const type of ["touchend", "touchcancel", "pointerup", "pointercancel", "blur"]) window.removeEventListener(type, this._onUp);
    for (const type of ["touchmove", "pointermove"]) window.removeEventListener(type, this._onMove);
    this._pointers.clear(); this._touching = false;
    if (this._resize) { this._resize.disconnect(); this._resize = null; }
    if (this._motionQuery && this._motionQuery.removeEventListener) this._motionQuery.removeEventListener("change", this._onMotion);
    this._motionQuery = null;
    this._stop(); this._windStop();
  }

  _lang() {
    const data = this._roomsLang;
    if (data === "de" || data === "en") return data;
    const raw = String((this._hass && (this._hass.locale?.language || this._hass.language)) || navigator.language || "en").toLowerCase();
    return raw.startsWith("de") ? "de" : "en";
  }
  _t(key) { const table = T[this._lang()]; return table[key] != null ? table[key] : key; }
  // UI hotfix: one stored choice per card instance – a card with its own start floor ("floor") keeps its own
  // choice, so several house maps on one dashboard show different floors without switching each other
  _storeKey() { return `freshairiq-house:${this._config.entry_id || "default"}${this._config.floor ? `:${this._config.floor}` : ""}`; }
  // the configured start floor (floor id, level key or name), else the lowest floor
  _startFloor(floors) {
    const want = String(this._config.default_floor || this._config.floor || "").trim().toLowerCase();
    const hit = want && floors.find(f => [f.id, f.level_key, f.name].some(v => String(v || "").toLowerCase() === want));
    return (hit || floors[0]).id;
  }
  _restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(this._storeKey()) || "{}");
      if (saved.floor) this._floor = saved.floor;
      if (saved.lockUntil > Date.now()) this._lockUntil = saved.lockUntil;
      // 0.26.7.0 UI hotfix: the view on the plan is set in the card's settings; a view chosen earlier in the menu stays as long
      // as the card's setting is still the one it was chosen against – a new setting wins
      if (LAYERS.includes(saved.layer) && (saved.layerBase == null || saved.layerBase === (this._config.layer || "action"))) this._layer = saved.layer;
      // 0.26.7.0(2): the animation level chosen in the menu, as long as the card's own setting is the one it replaced
      const motion = JSON.parse(localStorage.getItem(`${this._storeKey()}:motion`) || "null"), base = M.chosenLevel(this._config);
      this._baseLevel = null;
      if (motion && M.ANIMATION_LEVELS.includes(motion.level) && motion.base === base) { this._baseLevel = base; this._config = { ...this._config, animation_level: motion.level }; if (motion.level !== "off" && this._config.animation === false) this._config.animation = true; }
    } catch (_) { /* private mode */ }
  }
  _persist() {
    try { localStorage.setItem(this._storeKey(), JSON.stringify({ floor: this._floor, lockUntil: this._lockUntil, layer: this._layer, layerBase: this._config.layer || "action" })); } catch (_) { /* ignore */ }
  }
  _entryMsg(type) { const msg = { type }; if (this._config.entry_id) msg.entry_id = this._config.entry_id; return msg; }

  // Hotfix F01: exactly two subscriptions per shown card. A start runs only while the card is connected and
  // never twice at once; a disconnect (or a newer start) during any await ends it and releases what it got,
  // also the channel that did subscribe when the other one failed.
  async _start() {
    const conn = this._hass && this._hass.connection;
    if (!conn || typeof conn.subscribeMessage !== "function" || this._subs.length || this._starting || !this.isConnected) return;
    const gen = ++this._gen;
    const live = () => gen === this._gen && this.isConnected;
    this._starting = true;
    this._subConn = conn; this._subEntry = this._config.entry_id || null;  // the target of this start
    this._failed = false;
    try {
      const info = await this._hass.callWS(this._entryMsg("freshairiq/house_map/get"));
      if (!live()) return;
      this._layoutInfo = info;
      if (!info.layout || !info.layout.rooms.length) {
        const proposal = await this._hass.callWS(this._entryMsg("freshairiq/house_map/propose"));
        if (!live()) return;
        this._proposal = proposal;
      }
      const settled = await Promise.allSettled([
        conn.subscribeMessage(p => this._onRooms(p), this._entryMsg(LIVE)),
        conn.subscribeMessage(p => this._onHouse(p), this._entryMsg(HOUSE)),
      ]);
      const got = settled.filter(s => s.status === "fulfilled" && typeof s.value === "function").map(s => s.value);
      const failed = settled.find(s => s.status === "rejected");
      if (!live() || failed || got.length !== 2) {
        release(got);
        if (!live()) return;
        throw failed ? failed.reason : new Error("subscription");
      }
      this._subs = got;
    } catch (err) {
      if (!live()) return;
      this._failed = err && err.code === "not_loaded" ? "not_loaded" : true;
      this._retryLater();
    } finally {
      if (gen === this._gen) this._starting = false;
    }
    if (live()) this._queue();
  }
  _retryLater() {
    clearTimeout(this._retry);
    this._retry = setTimeout(() => { this._retry = null; if (this.isConnected) this._start(); }, RETRY_MS);
  }
  _stop() {
    this._gen += 1; this._starting = false; this._subConn = null; this._subEntry = null; this._layoutBusy = null;
    clearTimeout(this._retry); this._retry = null;
    release(this._subs); this._subs = [];
  }
  _onRooms(payload) {
    if (!payload || typeof payload !== "object") return;
    this._payload = payload;
    this._rooms = payload.rooms || {};
    this._roomsLang = payload.output_language || null;
    this._updateFocus();
    this._queue();
  }
  _onHouse(payload) {
    if (!payload || typeof payload !== "object") return;
    const known = this._layoutInfo && this._layoutInfo.revision;
    this._house = payload;
    this._wantRev = payload.revision;
    if (payload.wind && payload.wind.from_deg != null) this._windSmooth = G.smoothBearing(this._windSmooth, payload.wind.from_deg);
    if (payload.revision !== known && !this._editing) this._refreshLayout();
    this._queue();
  }
  // Re-audit F02: one layout request at a time; a revision announced meanwhile is fetched right after it, an
  // older answer never replaces a newer layout, and a request of a previous connection/entry is dropped.
  async _refreshLayout() {
    if (this._layoutBusy !== null && this._layoutBusy === this._gen) return;
    const gen = this._gen;
    this._layoutBusy = gen;
    try {
      for (let round = 0; round < 4; round += 1) {
        const wanted = this._wantRev;
        let info;
        try { info = await this._hass.callWS(this._entryMsg("freshairiq/house_map/get")); } catch (_) { break; }  // keep the old one
        if (gen !== this._gen) return;
        const have = this._layoutInfo && this._layoutInfo.revision;
        const older = info && Number.isFinite(Number(have)) && Number.isFinite(Number(info.revision)) && Number(info.revision) < Number(have);
        if (info && !older) {
          this._layoutInfo = info;
          if (info.layout && info.layout.rooms && info.layout.rooms.length) this._proposal = null; // a saved plan replaces the proposal
        }
        if (this._wantRev === wanted || (this._layoutInfo && this._layoutInfo.revision === this._wantRev)) break;
      }
    } finally {
      if (this._layoutBusy === gen) this._layoutBusy = null;
    }
    if (gen === this._gen) this._queue();
  }
  _layout() {
    const info = this._layoutInfo;
    if (info && info.layout && info.layout.rooms && info.layout.rooms.length) return { layout: info.layout, saved: true };
    if (this._proposal && this._proposal.layout) return { layout: this._proposal.layout, saved: false };
    return null;
  }
  _floors(layout) {
    const used = new Set(layout.rooms.map(r => r.floor_id));
    // 0.26.7.0: only the floors this card shows (display only – the plan and every calculation keep all floors)
    return visibleFloors((layout.floors || []).filter(f => used.has(f.id)).sort((a, b) => (a.order || 0) - (b.order || 0)), this._config.floors_visible);
  }
  _updateFocus() {
    const current = this._layout();
    if (!current) return;
    const floors = this._floors(current.layout);
    if (!floors.length) return;
    if (!floors.some(f => f.id === this._floor)) this._floor = this._startFloor(floors);  // also a stored "__all" of older versions
    const priorities = Object.fromEntries(floors.map(f => [f.id, floorPriority(current.layout, this._rooms, f.id)]));
    const now = Date.now();
    const decision = focusDecision({ mode: this._config.auto_focus, current: this._floor, priorities, previous: this._prevPriorities,
      lockUntil: this._lockUntil, lastAutoAt: this._lastAutoAt, now });
    if (decision.switched) { this._floor = decision.floor; this._lastAutoAt = now; this._selected = null; this._persist(); }
    if (decision.hint) this._hint = decision.hint;
    if (this._hint && (priorities[this._hint] || 0) < 2) this._hint = null;
    this._prevPriorities = priorities;
  }
  _gestureActive() {
    if (!this._touching && !this._pointers.size) return false;
    if (Date.now() - this._gestureSeen > GESTURE_LOST_MS) { this._touching = false; this._pointers.clear(); return false; }  // a release was lost
    return true;
  }
  _queue() {
    if (this._frame || this._editing) return;
    if (this._gestureActive()) { this._pending = true; return; }  // drawn on release
    this._frame = requestAnimationFrame(() => { this._frame = null; this._render(); });
  }
  _chooseFloor(id) {
    this._floor = id; this._selected = null; this._hint = null;
    this._lockUntil = Date.now() + Number(this._config.manual_lock_min || 10) * 60000;
    this._persist(); this._render();
  }

  // ------------------------------------------------------------------ rendering
  _floorName(floor) { const names = T[this._lang()].floors; return esc(names[floor.level_key] || floor.name || floor.level_key || floor.id); }
  // 0.26.6.1(2): the floors as buttons at the bottom left of the plan – every floor but the one shown (and
  // "All floors"); a floor that needs an action (air now, close, critical) pulses gently, statically with
  // reduced motion. The choice is kept like before (_chooseFloor: manual lock, stored).
  _floorButtons(layout, floors) {
    if (floors.length < 2) return "";
    const btn = (id, label, act) => `<button class="floorbtn${act ? ` pulse p-${act}` : ""}" data-floor="${esc(id)}"${act ? ` data-action="${act}" aria-description="${esc(this._t(`need_${act}`))}"` : ""}>${label}</button>`;
    // UI hotfix: no "All floors" – several floors at once = the card several times on the dashboard
    const others = floors.filter(f => f.id !== this._floor).map(f => btn(f.id, this._floorName(f), floorAction(layout, this._rooms, f.id)));
    return `<div class="floors" role="group" aria-label="${esc(this._t("floors_title"))}">${others.join("")}</div>`;
  }
  // 0.26.6.1(7): outdoor temperature and humidity from FreshAirIQ, or the card's own sensors (weather_sensors:
  // list or comma-separated entity ids) – each with its unit; unknown values are left out, nothing is invented
  _weatherChip() {
    const p = this._payload || {}, states = (this._hass && this._hass.states) || {}, parts = [];
    const fmt = v => (Number.isFinite(v) ? (Math.abs(v) >= 100 ? Math.round(v) : v.toFixed(1)).toString().replace(".", this._lang() === "de" ? "," : ".") : null);
    const own = (Array.isArray(this._config.weather_sensors) ? this._config.weather_sensors : String(this._config.weather_sensors || "").split(","))
      .map(x => String(x).trim()).filter(Boolean);
    // 0.26.7.0(2) correction: an explicit new choice (weather_chip) wins over the older own sensors; a card with only
    // weather_sensors keeps showing them exactly as before
    if (own.length && this._config.weather_chip == null) {
      for (const id of own) {
        const st = states[id], a = (st && st.attributes) || {}, v = fmt(known(st && st.state));
        if (v == null) continue;
        const icon = a.device_class === "temperature" ? "🌡️" : a.device_class === "humidity" ? "💧" : "•";
        const shown = a.unit_of_measurement === "%" ? String(Math.round(known(st.state))) : v;
        parts.push([`${icon} ${shown}${a.unit_of_measurement ? ` ${a.unit_of_measurement}` : ""}`, a.friendly_name || id]);
      }
    } else {
      // 0.26.7.0(2): what the chip shows is the card's choice (weather_chip, in its order); without one as before – outdoor
      // temperature and humidity. A narrow card shows the first ones of the choice; everything is in the weather window.
      const own2 = !!String(this._config.weather_entity || "").trim();
      const items = W.chipFor(this._config).slice(0, W.chipRoom(this._lastWidth));
      for (const [, html, title] of W.chipItems(this._weatherModel(), { items, lang: this._lang(), tz: this._tz(), own: own2,
        outdoor: { temperature: known(p.outdoor_temperature ?? (p.weather_now || {}).outdoor_temperature), humidity: known(p.outdoor_humidity) } })) parts.push([html, title, true]);
    }
    // 0.26.7.0: the chip looks as before (weather_info: compact). 0.26.7.0(2) correction: whatever it shows, a tap always
    // opens the weather window – which parts the window shows is still the card's choice (weather_info, weather_details)
    const info = this._info();
    if (!info.includes("compact")) return "";
    if (!parts.length) return "";
    const inner = parts.map(([text, title, html]) => `<span title="${esc(title)}">${html ? text : esc(text)}</span>`).join("");
    return `<button class="weather" data-weather-open aria-label="${esc(this._t("weather_open"))}">${inner}</button>`;
  }
  // order 8: removable moisture of the whole house and the airing time (top left). Values come from FreshAirIQ's
  // published results only; a missing value is left out. Shown values glide to new ones (no jumping numbers).
  // Order 9 / Hotfix (9): "removable now", its time and whether the house holds back come from the FreshAirIQ
  // dashboard card's own decision (_iqFacts in freshairiq-card.js, the IQ view's head) – same data, same session state
  // (a session counts until its final measurement, as in the backend's live balance), same signs, same wait/night rule.
  _moistureFacts() {
    if (!CARD || !CARD.FreshAirIQCard) return null;
    const p = this._payload || {};
    if (p.potential_total_ml == null && p.live_balance_ml == null) return null;   // nothing computed yet: nothing shown
    const host = this._iqHost || (this._iqHost = Object.create(CARD.FreshAirIQCard.prototype, { _config: { value: {} }, _uiLanguage: { value: () => this._lang() } }));
    const f = host._iqFacts(p, Object.values(this._rooms || {}).filter(r => r && typeof r === "object"));
    // the same visibility as the card: a time only when it is shown there; a live session: left (≥ 0) or over (< 0)
    const minutes = !f.houseHolds && Number.isFinite(f.duration) && Math.abs(f.duration) >= 0.5 ? (f.live ? Math.ceil(Math.abs(f.duration)) : Math.max(1, Math.round(f.duration))) : null;
    return { live: !!f.live, amount: Math.round(f.amount), minutes, over: !!f.live && f.duration < 0, waits: !!f.houseHolds, confidence: known(p.prognosis_confidence) };
  }
  _moistureChip() {
    const f = this._moistureFacts();
    if (!CARD && !this._cardWait) this._cardWait = CARD_READY.then(() => this._queue());
    if (!f) return "";
    const t = k => esc(this._t(k)), ml = this._tweenValue("ml", Math.abs(f.amount));
    // sign as on the card: removed (or removable) shows "≈ N ml"; moisture added (or that would be added) "+N ml"
    const amount = f.amount <= -1 ? `${f.live ? `${t("moist_so_far_chip")} ` : ""}<span class="added">+<b data-tw="ml">${ml}</b> ml ${t(f.live ? "moist_added" : "moist_would_add")}</span>`
      : `${f.live ? `${t("moist_so_far_chip")} ` : ""}≈ <b data-tw="ml">${ml}</b> ml${f.waits && f.amount >= 1 ? ` ${t("moist_possible")}` : ""}`;
    const showTime = f.minutes != null && (f.live || f.amount >= 1);
    const time = showTime ? ` <span>⏱ ${f.live ? (f.over ? `<b>${f.minutes}</b> ${t("min_short")} ${t("moist_over")}` : `${t("moist_left")} <b>${f.minutes}</b> ${t("min_short")}`) : `${t("moist_in")} <b>${f.minutes}</b> ${t("min_short")}`}</span>` : "";
    return `<button class="moist" data-moisture aria-label="${t("moist_chip")}"><span>💧 ${amount}</span>${time}</button>`;
  }
  // the number shown glides from its last value to the new one (~0.8 s, only when the value changes)
  _tweenValue(key, target) {
    const tw = this._tw || (this._tw = {}), shown = tw[key] ? tw[key].shown : target;
    if (this._windStill()) { tw[key] = { from: target, to: target, start: 0, shown: target }; return target; }   // no motion: the new value at once
    tw[key] = { from: shown, to: target, start: performance.now(), shown };
    if (shown !== target && !this._tweenRaf) this._tweenRaf = requestAnimationFrame(t => this._tweenStep(t));
    return shown;
  }
  _tweenStep(now) {
    let busy = false;
    for (const [k, v] of Object.entries(this._tw)) {
      const x = Math.min(Math.max((now - v.start) / 800, 0), 1);
      v.shown = Math.round(v.from + (v.to - v.from) * (1 - Math.pow(1 - x, 3)));
      const el = this.shadowRoot && this.shadowRoot.querySelector(`[data-tw="${k}"]`);
      if (el) el.textContent = String(v.shown);
      if (x < 1) busy = true;
    }
    this._tweenRaf = busy && this.isConnected ? requestAnimationFrame(t => this._tweenStep(t)) : null;
  }
  _maps(layout) { return `<div class="map">${this._svg(layout, this._floor)}</div>`; }
  // Guests (the integration's own number settings guest_adults / guest_children), changed with −/+.
  // Hotfix 0.26.6.1: the stable mapping of the FreshAirIQ dashboard card (``_guestEntity`` in freshairiq-card.js) –
  // the number entity whose attributes name the entity key and this card's config entry, so a renamed entity
  // still works and a second FreshAirIQ entry is never changed. Registry metadata only as an unambiguous fallback.
  _guestEntity(kind) {
    const key = `guest_${kind}`, entry = this._config.entry_id || (this._layoutInfo && this._layoutInfo.entry_id) || null;
    const tagged = Object.values((this._hass && this._hass.states) || {}).filter(st => st && String(st.entity_id || "").startsWith("number.")
      && st.attributes && st.attributes.freshairiq_entity_key === key && (!entry || st.attributes.freshairiq_entry_id === entry));
    if (tagged.length === 1 || (entry && tagged.length)) return tagged[0].entity_id;
    if (tagged.length > 1) return null;  // several FreshAirIQ entries and none named: never the wrong house
    const listed = Object.values((this._hass && this._hass.entities) || {}).filter(e => e && e.platform === "freshairiq" && e.translation_key === key);
    return listed.length === 1 ? listed[0].entity_id : null;
  }
  _guests() {
    const p = this._payload || {}, t = k => this._t(k);
    const row = kind => {
      const value = Number(p[`guest_${kind}`] || 0), entity = this._guestEntity(kind);
      const btn = (delta, label) => entity ? `<button class="small" data-guest="${kind}" data-delta="${delta}" aria-label="${esc(t(`guest_${kind}`))} ${label}">${label}</button>` : "";
      return `<div class="guest">${esc(t(`guest_${kind}`))}: ${btn(-1, "−")}<b>${value}</b>${btn(1, "+")}</div>`;
    };
    const missing = !this._guestEntity("adults") && !this._guestEntity("children");
    return `<h5>${esc(t("guests"))}</h5><div class="row">${row("adults")}${row("children")}</div>${missing ? `<div class="legend">${esc(t("guests_readonly"))}</div>` : ""}`;
  }
  _setGuests(kind, delta) {
    const entity = this._guestEntity(kind), p = this._payload || {};
    if (!entity || !this._hass) return;
    const shown = Number(((this._hass.states || {})[entity] || {}).state);
    const current = Number.isFinite(shown) ? shown : Number(p[`guest_${kind}`] || 0);
    const value = Math.max(0, Math.min(20, Math.round(current + delta)));  // hotfix 0.26.6.1: the setting's range 0–20
    if (value === current) return;  // at a limit: nothing to send
    this._hass.callService("number", "set_value", { entity_id: entity, value });
  }

  // Hero: what matters for the whole house – recommendation, wind, forecast for the set horizon, night, outdoors.
  _hero(layout) {
    const p = this._payload || {}, t = k => this._t(k), lang = this._lang();
    const rec = p.intelligent_recommendation && typeof p.intelligent_recommendation === "object" ? p.intelligent_recommendation : {};
    const recTone = heroTone(rec);
    const north = layout ? Number(layout.building.north_deg || 0) : 0;
    const ow = this._outdoorWind(), w = ow.wind;
    const windVal = !w ? "–" : w.from_deg == null ? t("wind_none") : w.stale ? t("wind_stale") : w.calm ? t("wind_calm")
      : `${esc(lang === "de" ? w.label_de : w.label_en)} · ${w.speed_ms != null ? `${Math.round(w.speed_ms * 3.6)} km/h` : t("wind_speed_unknown")}`;  // Hotfix (9) F04
    const windSub = w && w.from_deg != null ? `${t("wind_from")} ${Math.round(w.from_deg)}°${w.age_s != null ? ` · ${lang === "de" ? `${t("ago")} ${Math.round(w.age_s / 60)} ${t("min")}` : `${Math.round(w.age_s / 60)} ${t("min")}`}` : ""}` : "";
    const ml = known(p.forecast_moisture_effect_ml);  // re-audit F04: null is unknown, not 0 ml
    const fc = Number.isFinite(ml) ? `<span class="${ml > 0 ? "good" : ml < 0 ? "bad" : ""}">${ml > 0 ? "−" : ml < 0 ? "+" : "±"}${Math.abs(Math.round(ml))} ml</span>` : "–";
    const dt = known(p.forecast_temperature_change_c);
    const night = known(p.overnight_forecast_ml);
    const out = p.weather_now && p.weather_now.outdoor_temperature != null ? `${Number(p.weather_now.outdoor_temperature).toFixed(1)} °C` : "–";
    const kpi = (icon, label, value, subText) => `<div class="kpi">${icon}<div><div class="lbl">${esc(label)}</div><div class="val">${value}</div>${subText ? `<div class="sub">${subText}</div>` : ""}</div></div>`;
    const horizon = Number(p.forecast_horizon_min || 5);
    return `<div class="hero">
      <div class="brand">${V.LOGO}<div><div class="title">${esc(this._config.title || this._t("title"))}</div><div class="status">${esc(p.status_text || "")}</div></div></div>
      ${rec.title ? `<div class="bubble" role="status" data-tone="${recTone}" style="border-left:10px solid ${V.TONE_COLOR[recTone]}"><span class="emo">${V.TONE_EMOJI[recTone]}</span><div>${esc(rec.title)}${rec.instruction || rec.summary ? `<small>${esc(rec.instruction || rec.summary)}</small>` : ""}</div></div>` : ""}
      <div class="kpis">
        ${kpi(V.windDial(ow.smooth, north, w && w.speed_ms), t("kpi_wind"), windVal, windSub)}
        ${kpi("", `${t("kpi_forecast")} ${horizon} min`, fc, Number.isFinite(dt) ? `${dt > 0 ? "+" : ""}${dt.toFixed(1)} °C` : "")}
        ${kpi("", t("kpi_night"), Number.isFinite(night) ? `+${Math.round(night)} ml` : "–", t("kpi_night_sub"))}
        ${kpi("", t("kpi_outdoor"), out, p.weather_now && p.weather_now.condition ? esc(V.conditionText(p.weather_now.condition, lang)) : "")}
      </div></div>`;
  }
  _roomLines(room, layoutRoom) {
    const lang = this._lang(), t = k => this._t(k);
    if (!room) return { name: esc(layoutRoom.room_key), action: t("no_room_data"), extra: "", tone: "sensor" };
    const name = esc(room.name || layoutRoom.room_key);
    const tone = roomTone(room);
    const fan = fanClose(room);  // 0.26.7.0: a fan-only room never reads "Close"
    const action = `${V.TONE_EMOJI[tone] || ""} ${esc(T[lang].actions[fan ? fan.word : actionCode(room)] || T[lang].actions.unknown)}`;  // canonical action word
    const num = (v, d = 1) => (v == null || !Number.isFinite(Number(v)) ? "–" : Number(v).toFixed(d));
    const climate = A.roomClimate(room), rise = climate.rising ? " ↑" : climate.falling ? " ↓" : "";  // measured trend ≥ 3 %/h up or down
    const extra = {
      temperature: `${num(room.temperature)} °C${room.comfort_target_c != null ? ` → ${num(room.comfort_target_c)} °C` : ""}`,
      humidity: `${num(room.humidity, 0)} %${rise} · ${num(room.absolute_humidity)} g/m³`,
      co2: room.co2 != null ? `${Math.round(room.co2)} ppm CO₂` : t("not_measured"),
      quality: `${room.data_quality === "ok" ? t("quality_ok") : t("quality_bad")} · ${t("learning")} ${room.learning_samples ?? "–"}`,
    }[this._layer] || `${num(room.temperature)} °C · ${num(room.humidity, 0)} %${rise}`;
    // 0.26.7.0: the card's own choice of what a room shows (room_info, room_overrides) – on the action layer; another
    // layer chosen in the menu still shows its reading. Hidden values stay one tap away in the room window.
    const show = roomInfo(this._config, layoutRoom.room_key);
    if (!show || this._layer !== "action") return { name, action, extra, tone };
    const I = T[lang].info, known2 = v => v != null && Number.isFinite(Number(v));
    const parts = [
      show.includes("temperature") && known2(room.temperature) ? I.temperature.replace("{v}", num(room.temperature)) : null,
      show.includes("humidity") && known2(room.humidity) ? `${I.humidity.replace("{v}", num(room.humidity, 0))}${rise}` : null,
      show.includes("absolute_humidity") && known2(room.absolute_humidity) ? I.absolute_humidity.replace("{v}", num(room.absolute_humidity)) : null,
      show.includes("co2") && known2(room.co2) ? I.co2.replace("{v}", Math.round(room.co2)) : null,
      show.includes("mould") && T[lang].mould_short[room.mould_level] ? I.mould.replace("{v}", T[lang].mould_short[room.mould_level]) : null,
    ].filter(Boolean);
    return { name, action, extra: parts.join(" · "), tone, showName: show.includes("name"), showAction: show.includes("action") };
  }
  _unitPx(vbWidth) {
    const measured = (this.shadowRoot.querySelector(".map") || this).getBoundingClientRect().width || this._lastWidth || 640;
    const width = Math.max(measured, 1);  // community hotfix: the plan fits the card (no sideways swiping on phones)
    this._lastWidth = measured;
    return vbWidth / width;  // plan units per screen pixel
  }
  _svg(layout, floorId) {
    this._flowScene = null;
    const rooms = layout.rooms.filter(r => r.floor_id === floorId && Array.isArray(r.polygon) && r.polygon.length >= 3);
    if (!rooms.length) return `<div class="notice">${esc(this._t("empty"))}</div>`;
    const box = G.bbox(rooms.map(r => r.polygon));
    const span = Math.max(box.maxX - box.minX, box.maxY - box.minY, 1);
    const margin = span * 0.16;  // the streams arrive from the edge of the drawing
    const vb = [box.minX - margin, -box.maxY - margin, box.maxX - box.minX + 2 * margin, box.maxY - box.minY + 2 * margin];
    const u = this._unitPx(vb[2]);
    const px = n => G.round3(n * u);
    // 0.26.7.0 UI hotfix: one continuous surface – the drawing reaches under the slim control bars at the top and the bottom
    // (their measured height, see _render), so sky, weather and wind run on under them in the same coordinates; the rooms keep
    // their own margin and are never under a bar. The stored geometry is untouched (only the visible window grows).
    const bars = this._bars || { top: 0, bottom: 0 };
    const planFrame = { minX: vb[0], minY: -(vb[1] + vb[3]), maxX: vb[0] + vb[2], maxY: -vb[1] };
    // the drawing's real scale: a plan limited by the screen height (78vh, see the style) is drawn smaller than its width allows –
    // then the sky widens to the full width as well (no plain strips beside the drawing); labels keep their sizes as before
    const mapW = this._lastWidth || 640, viewH = (typeof window !== "undefined" && window.innerHeight) || 900;
    const scale = this._bars && mapW * vb[3] / vb[2] > viewH * 0.78 ? Math.max(u, vb[3] / (viewH * 0.78)) : u;
    vb[1] -= bars.top * scale; vb[3] += (bars.top + bars.bottom) * scale;
    if (this._bars && mapW * scale > vb[2] + 0.5 * scale) { const wide = mapW * scale; vb[0] -= (wide - vb[2]) / 2; vb[2] = wide; }
    const S = p => `${G.round3(p[0])},${G.round3(-p[1])}`;
    const north = Number(layout.building.north_deg || 0);
    const ids = new Set(rooms.map(r => r.id));
    const air = this._house && this._house.airflow;
    const opState = air ? air.openings : {};
    const ow = this._outdoorWind(), w = ow.wind, smooth = ow.smooth;   // 0.26.7.0: the card's weather source
    const dur = V.streamSeconds(w && w.speed_ms) * 1.6;   // 0.26.7.0(2): calmer – the same order (stronger wind, faster air), slower overall
    // 0.26.6.1(7): no technical grid – a sky that follows the real weather (FreshAirIQ weather summary, sun.sun)
    // sky and weather cover the whole surface (the moving weather lies in the composed layer under the plan, see atmos weatherSvg
    // under – its area costs nearly nothing); the wind ribbons from "normal" up, "minimal" (phones, energy saving) keeps them
    // around the house
    const lvl = (this._motionNow || this._motion()).level, wxFrame = { minX: vb[0], minY: -(vb[1] + vb[3]), maxX: vb[0] + vb[2], maxY: -vb[1] };
    const frame = lvl === "minimal" ? planFrame : wxFrame;
    // 0.26.7.0: a chosen weather entity that reports a state decides the sky (one source for the picture and the overview)
    const wnRaw = (this._payload && this._payload.weather_now) || {}, wxm = this._weatherModel(), own = String(this._config.weather_entity || "").trim();
    const wnSky = own && wxm.available && wxm.condition ? { ...wnRaw, condition: wxm.condition, raining: ["rainy", "pouring", "lightning-rainy"].includes(wxm.condition),
      snowing: ["snowy", "snowy-rainy"].includes(wxm.condition), thunder: ["lightning", "lightning-rainy"].includes(wxm.condition) } : wnRaw;
    const sky = { ...A.skyState(wnSky, this._hass && this._hass.states && this._hass.states["sun.sun"]), directional: layout.building.north_confirmed !== false };
    // order 9: the wind's character from the real weather (speed, measured gust, HA condition, rain/thunder, sun.sun)
    const wn = wnSky;   // 0.26.7.0: the same weather source as the sky
    const mood = F.windMood({ speed: Number(w && w.speed_ms) || 0, gust: w && w.gust_ms, condition: wn.condition, raining: wn.raining === true, thunder: wn.thunder === true, phase: sky.phase });
    this._windMood = mood.name;
    // 0.26.7.0: the weather world – "dynamic" is the look until now, "subtle" calmer, "off" without weather effects,
    // "full" adds the light of the real sun (colour, strength, the house's shadow), the sky's colour by the sun's
    // elevation and the clouds, darker storms, rain on the ground, fog, frost and the moon's phase
    const fx = this._fx(), model = this._weatherModel(), small = this._lastWidth > 0 && this._lastWidth < 520;
    const light = fx === "full" ? W.sunLight({ elevation: sky.elevation, azimuth: sky.azimuth, cover: model.cover, northDeg: north, directional: sky.directional }) : null;
    const skyColors = fx === "full" && sky.elevation != null ? W.skyColors(sky.elevation, model.cover) : null;
    this._skyColors = skyColors || A.skyPalette(sky.phase);
    const fxVars = fx === "full" ? `;--cloud-dur:${({ calm: 90, light: 70, fresh: 45, strong: 26, storm: 14 })[model.level] || 60}s;--fall-dur:${model.precip.level >= 3 ? 0.35 : model.precip.level === 1 ? 0.8 : 0.55}s;--ray-o:${light ? G.round3(0.03 + 0.09 * light.strength) : 0.07}` : "";
    // 0.26.7.0(2): a room chosen (its window open): its outline drawn clearly, the other rooms of the floor quieter
    const chosen = this._selected && this._selected.type === "room" ? rooms.find(r => r.id === this._selected.id) : null;
    // 0.26.7.0 UI hotfix: the sky and the large moving weather layers lie under the plan (see atmos weatherSvg ``under``)
    const under = { html: "", vb: vb.slice(), ppu: 1 / scale };
    let out = `<svg class="plan${chosen ? " focus" : ""}" data-mood="${esc(this._windMood || "neutral")}" data-fx="${fx}" viewBox="${vb.map(G.round3).join(" ")}" role="group" aria-label="${esc(this._t("title"))}" style="--dash:${px(10)} ${px(8)};--dot:${px(3)} ${px(7)};--dashlen:${px(54)};--dur:${G.round3(dur)}s${fxVars}">`;
    const marker = (id, color) => `<marker id="${id}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="${color}" stroke="${V.BRAND.ink}" stroke-width="1"/></marker>`;
    out += `<defs>${marker("ah", V.BRAND.lime)}${marker("ahx", V.BRAND.orange)}${marker("ahc", V.BRAND.cyan)}
      <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${px(2.2)}" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="comic" x="-10%" y="-10%" width="130%" height="130%"><feDropShadow dx="${px(5)}" dy="${px(5)}" stdDeviation="0" flood-color="${V.BRAND.ink}" flood-opacity="1"/></filter>
      ${V.roomDefs(px)}
      ${A.skyDefs(sky, px, skyColors)}${W.worldDefs(model, light, px)}${A.climateDefs(px)}${A.weatherMask("wx-out", wxFrame, rooms, px)}
      ${rooms.map(r => `<clipPath id="rc-${esc(r.id)}"><polygon points="${r.polygon.map(S).join(" ")}"/></clipPath>`).join("")}</defs>
      ${fx === "off" ? "" : fx === "full" && light ? A.weatherSvg(sky, wxFrame, w, north, px, "wx-out", under).replace(/#fff4c9/g, light.color) : A.weatherSvg(sky, wxFrame, w, north, px, "wx-out", under)}${fx === "full" ? W.worldSvg({ model, light, frame: wxFrame, rooms, northDeg: north, px, mask: "wx-out", small, under }) : ""}`;
    // wind streams behind the house
    const openings = (layout.openings || []).map(o => ({ ...o, ...(opState[o.id] || {}) }));
    // 0.26.6: the air runs only through openings and connections between rooms and streams out of the outlet
    const pathPts = (air && air.paths ? air.paths : []).map(p => { const r = G.airRoute(layout, p, { outside: span * 0.14, strict: true }); return { ...p, points: r.points, exits: r.exits }; });
    // 0.26.7.0(2): fewer, calmer streams that never look alike – their number by the animation level, each its own lane, length,
    // wave, pace and brightness (the same for the same floor, so a redraw does not shuffle them)
    const motion = this._motionNow || this._motion();
    // the wind's strength stays readable: a breath of air – a few faint ribbons; a storm – more, livelier, brighter ones
    const strength = mood.name === "storm" ? 1.45 : ({ calm: 0.6, weak: 0.8, moderate: 1, strong: 1.25 })[F.strengthClass(Number(w && w.speed_ms) || 0)] || 1;
    const variety = M.streamVariety(Math.max(2, Math.min(9, Math.round(motion.streams * strength))), rooms.length * 7 + String(floorId).length * 13 + Math.round(span))
      .map(v => ({ ...v, amp: v.amp * Math.pow(strength, 0.8) * (motion.amp || 1), opacity: Math.min(0.95, v.opacity * (0.7 + 0.3 * strength) * (motion.glow || 1)) }));
    const streams = w && w.available && smooth != null
      ? V.windStreams({ rooms, openings, fromDeg: smooth, northDeg: north, G, paths: pathPts,
        frame, variety }) : [];
    // Soft wind waves: three translucent strands per stream that fade in and out at its ends. Their phase
    // comes from the card's own clock (_windPhase), so a redraw continues the motion where it was.
    // order 8: the wind field around the house and the routes of the air through it (drawn on the canvas layer)
    const closing = new Set(rooms.map((r, i) => (roomTone(this._rooms[r.room_key]) === "close" ? i : -1)).filter(i => i >= 0));
    const flowRoutes = streams.filter(s => s.kind === "inflow").map(s => {
      const o = openings.find(x => x.id === s.opening) || {}, r = rooms.find(x => x.id === o.room_id);
      const len = r && o.edge >= 0 ? G.edgeLength(r.polygon, o.edge) : 1, half = Math.min(o.width_m || Math.min(0.9, len * 0.4), len) / 2;
      const profile = F.routeProfile(V.streamLine(s), rooms, G, { openingHalf: half, tilted: !!s.tilted, step: span / 120 });
      return profile && { id: `${s.opening}:${s.tilted ? "t" : "o"}:${s.points.length}`, profile, tilted: !!s.tilted, closing };
    }).filter(Boolean);
    this._flowScene = { field: w && w.available && smooth != null ? F.buildField({ rooms, G, wind: { ...w, from_deg: smooth }, northDeg: north, mood }) : null,
      vb, routes: flowRoutes, rooms, key: `${mood.name}|${floorId}|${Math.round((smooth || 0) / 5)}|${F.strengthClass(Number(w && w.speed_ms) || 0)}|${rooms.length}|${G.round3(span)}` };
    let inflow = "";  // air coming in is drawn over the rooms, the rest behind the house
    const waves = this._wavesNext || (this._wavesNext = []);
    const COLORS = { mid: "#bfe9ff", hi: "#e6f7ff", lo: "#7cc8f0" };
    // the layers of each ribbon: the stream itself, and – from "normal" on – a broad, nearly transparent air mass around it
    const strands = motion.strands >= 3 ? V.WAVE_STRANDS : motion.strands >= 2 ? [V.WAVE_STRANDS[0], V.WAVE_STRANDS[2]] : [V.WAVE_STRANDS[0]];
    streams.forEach(s => {
      const frame = V.waveFrame(V.streamLine(s), px(9));   // 0.26.7.0(2): fewer points per ribbon (the curve stays smooth)
      if (frame.samples.length < 2) return;
      const first = frame.samples[0].p, last = frame.samples[frame.samples.length - 1].p;
      const vr = s.variety != null && variety[s.variety] ? variety[s.variety] : { amp: 1, wave: 1, pace: 1, offset: 0, opacity: 0.85, width: 1 };
      const base = (s.kind === "inflow" ? (s.tilted ? 5 : 7) : 4.5) * (s.kind === "inflow" ? 1 : vr.width);
      let line = "";
      strands.forEach((st, j) => {
        const index = waves.length;
        const geo = { amp: px(6.5) * st.amp * vr.amp * (s.kind === "pass" ? 0.8 : 1), wavelength: px(175) * st.wave * vr.wave, shift: st.shift + index * 0.37, pace: vr.pace, offset: vr.offset };
        waves.push({ frame, geo });
        const gid = `wg${index}`, color = s.kind === "inflow" && j === 0 ? V.BRAND.white : COLORS[st.cls];
        const endOpacity = s.kind === "inflow" && !s.exits ? 1 : 0;  // air streaming out fades outside the house
        line += `<linearGradient id="${gid}" gradientUnits="userSpaceOnUse" x1="${G.round3(first[0])}" y1="${G.round3(-first[1])}" x2="${G.round3(last[0])}" y2="${G.round3(-last[1])}"><stop offset="0" stop-color="${color}" stop-opacity="0"/><stop offset=".2" stop-color="${color}"/><stop offset=".8" stop-color="${color}"/><stop offset="1" stop-color="${color}" stop-opacity="${endOpacity}"/></linearGradient>`;
        const cls = `${j === 0 ? `stream ${s.kind} ` : ""}wave ${st.cls} k-${s.kind}${s.tilted ? " tilted" : ""}${s.exits ? " exits" : ""}`;
        line += `<path class="${cls}" data-wave="${index}" d="${V.wavePath(frame, geo, this._wavePhase({ geo }))}" stroke="url(#${gid})" stroke-width="${px(base * st.width)}"${s.kind === "inflow" ? "" : ` stroke-opacity="${G.round3(vr.opacity)}"`}${s.kind === "inflow" && j === 0 && !s.exits ? ' marker-end="url(#ahc)"' : ""}/>`;
      });
      // order 8: the fine particles of the incoming air are drawn on the canvas air layer (freshairiq-house-flowlayer.js)
      if (s.kind === "inflow") inflow += line; else out += line;
    });
    // 0.26.6.1(2): one comic shadow under the whole house (not one per room – that drew every shared wall thick);
    // the rooms have no outline of their own, the walls come from G.wallSegments exactly as in the editor
    // 0.26.6.1(7): a soft shadow that lifts the house off the ground instead of the hard comic offset
    // 0.26.7.0 ("full"): the shadow falls away from the real sun, longer when it stands low
    const cast = W.shadowOffset(light, px, span);
    out += `<g class="house-shadow" transform="translate(${cast ? `${cast[0]} ${cast[1]}` : `${px(3)} ${px(7)}`})" fill="#000814" fill-opacity="${cast ? G.round3(cast[2] + 0.12) : ".5"}" filter="url(#soft)">${rooms.map(r => `<polygon points="${r.polygon.map(S).join(" ")}"/>`).join("")}</g>`;
    for (const r of rooms) {
      const live = this._rooms[r.room_key];
      const lines = this._roomLines(live, r);
      const tone = V.ROOM_TONES[lines.tone] ? lines.tone : "wait", pts = r.polygon.map(S).join(" ");
      out += `<polygon class="room t-${lines.tone}${this._selected && this._selected.id === r.id ? " sel" : ""}${this._spot && this._spot.id === r.id && Date.now() - this._spot.at < 4000 ? " spot" : ""}" fill="url(#rf-${tone})" stroke-width="${px(3.5)}" tabindex="0" role="button" data-room="${esc(r.id)}" aria-label="${`${lines.name}, ${lines.action}, ${lines.extra}`.replace(/<[^>]+>/g, "")}" points="${pts}"/>`;
      // 0.26.6.1(6): a soft inner rim where something is to do (clipped to the room), a faint hatch when critical
      if (V.ROOM_TONES[tone].rim) out += `<polygon class="rim r-${tone}" clip-path="url(#rc-${esc(r.id)})" points="${pts}" stroke="${V.ROOM_TONES[tone].rim}" stroke-width="${px(9)}" stroke-opacity=".55"/>`;
      if (tone === "critical") out += `<polygon class="hatch" fill="url(#rf-hatch)" points="${pts}"/>`;
      // 0.26.6.1(7): the room climate at rest – warm/cool, humid (mist, livelier while rising)/dry, mould risk
      out += A.climateSvg(A.roomClimate(live), r.polygon, `rc-${esc(r.id)}`, px, live && live.moisture_source_active ? this._sourceAt(r, px) : null);
    }
    out += A.nightVeil(sky, rooms);  // 0.26.6.1(8): night and twilight over the house (sun.sun), under walls and labels
    out += V.wallsSvg(G.wallSegments(rooms, openings), px);
    // the outline of the chosen room over its walls – its windows and doors are drawn after it and stay visible
    if (chosen) { const pts = chosen.polygon.map(S).join(" "); out += `<polygon class="sel-glow" points="${pts}" stroke-width="${px(9)}"/><polygon class="sel-outline" data-outline="${esc(chosen.id)}" points="${pts}" stroke-width="${px(3.5)}"/>`; }
    let plumes = "";
    for (const o of openings) {
      const r = rooms.find(x => x.id === o.room_id);
      if (!r || !(o.edge >= 0 && o.edge < r.polygon.length)) continue;
      const len = G.edgeLength(r.polygon, o.edge);
      const width = Math.min(o.width_m || Math.min(0.9, len * 0.4), len);
      const half = width / len / 2;
      const a = G.edgePoint(r.polygon, o.edge, Math.max(o.offset - half, 0)), b = G.edgePoint(r.polygon, o.edge, Math.min(o.offset + half, 1));
      const st = opState[o.id] || { state: o.kind === "passage" ? "open" : (o.contacts && o.contacts.length ? "unknown" : "no_sensor") };
      out += `<line class="op ${st.state}${st.pending ? " pending" : ""}" data-opening="${esc(o.id)}" tabindex="0" role="button" aria-label="${esc(this._openingText(o, st))}" x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke-width="${px(st.state === "tilted" ? 5 : 7)}"/>`;
      // the kind as a symbol (window panes, door leaf with its swing, passage as a gap), the state as its colour band
      const inward = V.inwardNormal(G, r.polygon, o.edge);
      out += `<g class="symbol k-${esc(o.kind)}" pointer-events="none">${V.openingSymbol(o.kind, a, b, inward, st.state, px, V.BRAND.night, o.kind === "door" ? G.doorGeometry(a, b, inward, o) : null, { arc: false })}</g>`;
      // 0.26.6.1(7): fresh air reaching into the room at an open (deep) or tilted (short) outside opening; just
      // closed, it fades out for a few seconds
      const outside = st.target === "outside" || o.target === "outside";
      if (outside && o.kind !== "door") {
        const now = Date.now(), seen = this._airSeen || (this._airSeen = {});
        if (A.isOpenState(st.state) && !st.pending) { seen[o.id] = { at: now, state: st.state }; plumes += A.plumeSvg(esc(o.id), a, b, inward, st.state, px, `rc-${esc(r.id)}`); }
        else if (seen[o.id] && now - seen[o.id].at < 4000) plumes += A.plumeSvg(esc(o.id), a, b, inward, seen[o.id].state, px, `rc-${esc(r.id)}`, true);
        else delete seen[o.id];
      }
    }
    out += plumes;
    // 0.26.5.5: a connection without a drawn opening is a logical link (dashed, with its kind) – never drawn as
    // a door or window; one that an opening already shows is not drawn twice
    const linked = new Set(openings.filter(o => o.target && o.target !== "outside").map(o => [o.room_id, o.target].sort().join("|")));
    const CONN = { open_passage: "⇄", door: "🚪", stairs: "🪜", shaft: "⇵", duct: "〰" };
    let markers = "";
    for (const c of layout.connections || []) {
      const a = rooms.find(x => x.id === c.a), b = rooms.find(x => x.id === c.b);
      if (!a || !b || linked.has([c.a, c.b].sort().join("|"))) continue;
      const pa = G.labelPoint(a.polygon), pb = G.labelPoint(b.polygon), m = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2];
      out += `<g class="conn logical k-${esc(c.kind)}" data-connection="${esc(c.id)}"><line x1="${G.round3(pa[0])}" y1="${G.round3(-pa[1])}" x2="${G.round3(pb[0])}" y2="${G.round3(-pb[1])}" stroke-width="${px(2.5)}"/></g>`;
      // its marker on the wall the two rooms share (else half way), drawn over the room labels
      const wall = G.wallParts([a, b], a).find(w => w.interior);
      const at = wall ? [(wall.a[0] + wall.b[0]) / 2, (wall.a[1] + wall.b[1]) / 2] : m;
      markers += `<g class="conn-mark k-${esc(c.kind)}" role="img" aria-label="${esc(this._t("connection"))}"><circle cx="${G.round3(at[0])}" cy="${G.round3(-at[1])}" r="${px(13)}" stroke-width="${px(2)}"/><text x="${G.round3(at[0])}" y="${G.round3(-at[1] + px(5))}" text-anchor="middle" font-size="${px(13)}">${CONN[c.kind] || "⇄"}</text></g>`;
    }
    if (this._layer === "airflow" && air) out += this._paths(layout, air, ids, px);
    out += inflow;
    const blocks = this._labelBlocks(rooms, openings, px);
    for (const r of rooms) {
      out += this._tag(r, this._roomLines(this._rooms[r.room_key], r), px, u, blocks);
      const live = this._rooms[r.room_key];
      if (live && A.roomClimate(live).fan) {  // 0.26.6.1(7): an exhaust fan that really runs turns slowly
        const p = G.labelPoint(r.polygon), rb = G.bbox([r.polygon]);
        out += A.fanSvg([Math.max(p[0] - px(44), rb.minX + px(16)), Math.min(p[1] + px(30), rb.maxY - px(16))], px, esc(this._t("fan_running")));
      }
      if (live && live.moisture_source_active) {  // 0.26.5.5: a detected moisture source, where the room is
        const [x, y] = this._sourceAt(r, px);
        out += `<g class="source" role="img" aria-label="${esc(String(live.moisture_source_label || this._t("source_on")))}"><circle cx="${G.round3(x)}" cy="${G.round3(-y)}" r="${px(13)}" stroke-width="${px(2)}"/><text x="${G.round3(x)}" y="${G.round3(-y + px(5))}" text-anchor="middle" font-size="${px(14)}">💧</text></g>`;
      }
    }
    // 0.26.7.0: a compass rose in the corner when the card asks for one (north as drawn on this plan)
    if (this._info().includes("compass") && layout.building.north_confirmed !== false) out += W.compassSvg(north, [planFrame.maxX - px(30), planFrame.minY + px(30)], px, this._lang());
    const underlay = `<div class="wxu" aria-hidden="true" style="${fxVars.replace(/^;/, "")}"><svg class="wxsky" viewBox="${vb.map(G.round3).join(" ")}" focusable="false">${A.skyBackground(vb)}</svg>${under.html}</div>`;
    return underlay + out + markers + "</svg>";
  }
  // 0.26.6.1(6/7): the room label without a box – the name on the room surface (colour chosen for contrast, a soft
  // halo against the wind), the state as a small dark capsule (symbol + word), the readings below in large rooms.
  // Every part stays inside the room's real outline (an L- or U-shaped room is not measured by its bounding box):
  // the richest variant that fits where the room is widest enough is drawn – all rows, then without the readings,
  // smaller name, short state word, only the state symbol in the capsule, a shortened name. A room too small even
  // for that shows a state dot sized to the room, with a thin ring; its name and values are one tap away.
  // where the moisture source symbol sits in a room (steam rises above it)
  _sourceAt(r, px) {
    const p = G.labelPoint(r.polygon), rb = G.bbox([r.polygon]);
    return [Math.min(p[0] + px(44), rb.maxX - px(14)), Math.min(p[1] + px(30), rb.maxY - px(14))];
  }
  // 0.26.6.1(7): the areas a label keeps free – a door's swing (hinge, free end, open leaf) and the sashes of a window
  _labelBlocks(rooms, openings, px) {
    const out = [];
    for (const o of openings) {
      const r = rooms.find(x => x.id === o.room_id);
      if (!r || !(o.edge >= 0 && o.edge < r.polygon.length)) continue;
      const len = G.edgeLength(r.polygon, o.edge), width = Math.min(o.width_m || Math.min(0.9, len * 0.4), len), half = width / len / 2;
      const a = G.edgePoint(r.polygon, o.edge, Math.max(o.offset - half, 0)), b = G.edgePoint(r.polygon, o.edge, Math.min(o.offset + half, 1));
      const n = V.inwardNormal(G, r.polygon, o.edge), w = Math.hypot(b[0] - a[0], b[1] - a[1]);
      let pts;
      // 0.26.6.1(10): the live map draws no door swing, so it takes no label space either (only an open door's leaf)
      if (o.kind === "door") { if (!(o.state === "open" || o.state === "open_unspecified")) continue; const d = G.doorGeometry(a, b, n, o); const tip = [d.hinge[0] + d.swing[0] * w, d.hinge[1] + d.swing[1] * w]; pts = [d.hinge, tip, [d.hinge[0] + (tip[0] - d.hinge[0]) * 0.5 + (d.free[0] - d.hinge[0]) * 0.12, d.hinge[1] + (tip[1] - d.hinge[1]) * 0.5 + (d.free[1] - d.hinge[1]) * 0.12]]; }
      else if (o.state === "open" || o.state === "open_unspecified") { const k = w * 0.45; pts = [a, b, [a[0] + n[0] * k, a[1] + n[1] * k], [b[0] + n[0] * k, b[1] + n[1] * k]]; }
      else continue;  // 0.26.6.1(9): a closed or tilted window takes no room space (its symbol lies in the wall)
      const box = G.bbox([pts]);
      out.push({ minX: box.minX, maxX: box.maxX, minY: box.minY, maxY: box.maxY });
    }
    return out;
  }
  _tag(r, lines, px, u, blocks = []) {
    const tone = V.ROOM_TONES[lines.tone] || V.ROOM_TONES.wait, dark = tone.text === "dark";
    const unesc = v => String(v).replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
    const action = unesc(lines.action), icon = action.split(" ")[0], word = action.slice(icon.length).trim(), shortWord = word.split(" · ")[0];
    const name = unesc(lines.name), extra = unesc(lines.extra || "");
    const measure = (text, f, weight) => textWidth(text, f, weight);
    const pillF = 12.5, metricF = 12.5, pad = 5;
    const pill = text => ({ kind: "pill", text, f: pillF, w: measure(text, pillF, 800) + 18, h: pillF * 1.9 + 4 });
    const nameRow = (f, text = name) => ({ kind: "n", text, f, w: measure(text, f, 900) + 4, h: f * 1.3 });
    const metricRow = { kind: "c", text: extra, f: metricF, w: measure(extra, metricF, 700) + 4, h: metricF * 1.45 };
    // 0.26.6.1(7/9): the readings may stand in two rows (°C, %), the state may shrink to its symbol – a room keeps its
    // readings before the state word, and its full name before a shortened one: a compound name may break into two
    // rows ("Arbeits-" / "zimmer"), a long name of a small room becomes its last word ("Gäste-WC" → "WC").
    // 0.26.6.1(9) regression fix: every variant is tried keeping door swings and open sashes free, then – rather than
    // dropping readings or cutting the name – over the quiet swing hairline.
    const parts = extra.split(" · ").filter(Boolean), metricRows = parts.map(text => ({ kind: "c", text, f: metricF, w: measure(text, metricF, 700) + 4, h: metricF * 1.4 }));
    const short = shortName(name), split = splitName(name);
    const names = [[nameRow(15)], [nameRow(13)], [nameRow(12)], ...(split ? [split.map(t => nameRow(13, t)), split.map(t => nameRow(12, t))] : []), ...(short !== name ? [[nameRow(12, short)]] : [])];
    const withMetrics = (n, p) => (extra ? [[...n, p, metricRow], ...(parts.length > 1 ? [[...n, p, ...metricRows]] : [])] : []);
    const variants = [
      ...withMetrics(names[0], pill(`${icon} ${word}`)), ...withMetrics(names[1], pill(`${icon} ${shortWord}`)),
      ...names.slice(1).flatMap(n => withMetrics(n, pill(icon))),
      // compact: the state symbol in front of the name, the readings below (a low room keeps its values)
      ...names.slice(1).flatMap(n => (extra ? [[{ ...n[0], text: `${icon} ${n[0].text}`, w: n[0].w + measure(`${icon} `, n[0].f, 900) }, ...n.slice(1), metricRow],
        ...(parts.length > 1 ? [[{ ...n[0], text: `${icon} ${n[0].text}`, w: n[0].w + measure(`${icon} `, n[0].f, 900) }, ...n.slice(1), ...metricRows]] : [])] : [])),
      [...names[0], pill(`${icon} ${word}`)], [...names[1], pill(`${icon} ${word}`)], [...names[1], pill(`${icon} ${shortWord}`)],
      ...names.slice(1).map(n => [...n, pill(icon)]),
      // a small room with a long name ("Gäste-WC"): at last its short name alone – the surface shows its state
      ...(short !== name ? [[nameRow(12, short)]] : []),
    ];
    // 0.26.7.0: only what the card shows – without the state its capsule (and the symbol in front of the name) is left
    // out, without the name its rows; the fitting below is the same for every combination
    const showName = lines.showName !== false, showAction = lines.showAction !== false;
    const adapt = rows => rows.filter(row => (row.kind !== "pill" || showAction) && (row.kind !== "n" || showName))
      .map(row => (row.kind === "n" && !showAction && row.text.startsWith(`${icon} `) ? { ...row, text: row.text.slice(icon.length + 1), w: measure(row.text.slice(icon.length + 1), row.f, 900) + 4 } : row));
    const shown = showName && showAction ? variants : variants.map(adapt).filter(v => v.length);
    // first every variant with readings keeping the swings free, then over the swing hairline, then without readings
    const withValues = shown.filter(v => v.some(row => row.kind === "c")), rest = shown.filter(v => !v.some(row => row.kind === "c"));
    for (const [group, free] of [[withValues, blocks], [withValues, []], [rest, blocks], [rest, []]]) {
      if (free !== blocks && !blocks.length) continue;  // no swings to keep free: nothing to retry
      for (const rows of group) {
        const h = rows.reduce((sum, row) => sum + row.h, 0), w = Math.max(...rows.map(row => row.w));
        const spot = G.labelSpot(r.polygon, px(h), px(pad), free);
        if (spot && spot.w >= px(w)) return this._tagRows(rows, spot, h, px, dark, name);
      }
    }
    // a shortened name with the state symbol, when only the name is too long
    const slim = !showName ? null : G.labelSpot(r.polygon, px(13 * 1.3 + pillF * 1.9 + 4), px(pad), blocks) || G.labelSpot(r.polygon, px(13 * 1.3 + pillF * 1.9 + 4), px(pad));
    if (slim && slim.w >= px(measure("Ab…", 12, 900) + 4)) {
      let cut = short;
      while (cut.length > 1 && measure(`${cut}…`, 12, 900) + 4 > slim.w / px(1)) cut = cut.slice(0, -1);
      return this._tagRows([nameRow(12, cut === short ? short : `${cut}…`), ...(showAction ? [pill(icon)] : [])], slim, 13 * 1.3 + pillF * 1.9 + 4, px, dark, name);
    }
    // too small for any text: a state dot as large as the room allows (at least 18 px across)
    const box = G.bbox([r.polygon]), inner = Math.min(box.maxX - box.minX, box.maxY - box.minY) / u;
    const spot = G.labelSpot(r.polygon, Math.min(px(30), (box.maxY - box.minY) * 0.8), 0) || { x: G.labelPoint(r.polygon)[0], y: G.labelPoint(r.polygon)[1] };
    const radius = Math.max(9, Math.min(15, inner * 0.42));
    if (!showAction && !showName && !extra) return `<g class="tag"><title>${esc(name)}</title></g>`;   // nothing chosen: the surface's colour shows the state
    return `<g class="tag"><title>${esc(name)}</title><circle class="dot" cx="${G.round3(spot.x)}" cy="${G.round3(-spot.y)}" r="${px(radius)}" stroke-width="${px(1.5)}"/>${showAction ? `<text class="a" x="${G.round3(spot.x)}" y="${G.round3(-spot.y + px(radius * 0.36))}" text-anchor="middle" font-size="${px(Math.max(12, radius))}">${icon}</text>` : ""}</g>`;
  }
  _tagRows(rows, spot, total, px, dark, title = "") {
    const ink = dark ? V.BRAND.ink : V.BRAND.white, halo = dark ? "rgba(255,255,255,.55)" : "rgba(2,16,36,.6)", x = G.round3(spot.x);
    let y = -spot.y - px(total) / 2, out = "";
    for (const row of rows) {
      if (row.kind === "pill") {
        const top = y + px(2), h = row.f * 1.9;
        out += `<rect class="pill" x="${G.round3(spot.x - px(row.w) / 2)}" y="${G.round3(top)}" width="${px(row.w)}" height="${px(h)}" rx="${px(h / 2)}" stroke-width="${px(1)}"/>`
          + `<text class="a pill-t" x="${x}" y="${G.round3(top + px(h / 2 + row.f * 0.36))}" text-anchor="middle" font-size="${px(row.f)}">${esc(row.text)}</text>`;
      } else {
        out += `<text class="${row.kind}" x="${x}" y="${G.round3(y + px(row.f * 1.05))}" text-anchor="middle" font-size="${px(row.f)}" fill="${ink}" stroke="${halo}" stroke-width="${px(row.kind === "n" ? 3 : 2.5)}">${esc(row.text)}</text>`;
      }
      y += px(row.h);
    }
    return `<g class="tag">${title ? `<title>${esc(title)}</title>` : ""}${out}</g>`;
  }
  _pathPoints(layout, p) { return G.airRoute(layout, p).points; }  // 0.26.6: through the passages, not the walls
  _paths(layout, air, ids, px) {
    let out = "";
    (air.paths || []).forEach((p, index) => {
      if (!p.rooms.every(id => ids.has(id))) return;
      const pts = this._pathPoints(layout, p);
      if (pts.length < 2) return;
      const directed = p.direction === "directed";
      const anim = directed && this._config.animation !== false ? " flow" : "";
      const m = p.kind.startsWith("exhaust") ? "ahx" : "ah";
      // a redraw continues the dash motion where it was: the delay follows one clock for every redraw
      const clock = anim ? ` style="animation-delay:-${G.round3((performance.now() / 1000) % V.streamSeconds(this._house && this._house.wind && this._house.wind.speed_ms))}s"` : "";
      out += `<polyline class="path ${p.confidence}${m === "ahx" ? " exhaust" : ""}${anim}"${clock} data-path="${index}" tabindex="0" role="button" aria-label="${esc(this._t(`k_${p.kind}`))}" points="${pts.map(q => `${G.round3(q[0])},${G.round3(-q[1])}`).join(" ")}" stroke-width="${px(6)}"${directed ? ` marker-end="url(#${m})"` : ` marker-start="url(#${m})" marker-end="url(#${m})"`}/>`;
    });
    return out;
  }
  _openingText(o, st) {
    const state = st.pending ? this._t("st_pending") : this._t(`st_${st.state}`);
    const exp = st.exposure && st.exposure !== "interior" ? ` · ${this._t("wall")}: ${this._t(st.exposure)}` : "";
    return `${this._t("opening")}: ${state}${exp}`;
  }
  // 0.26.7.0: the room's floor name in the layout (or "–")
  _roomFloor(layout, lr) { const f = lr && (layout.floors || []).find(x => x.id === lr.floor_id); return f ? this._floorName(f) : "–"; }
  _actionWord(room) {
    const fan = fanClose(room), lang = this._lang();
    return `${V.TONE_EMOJI[roomTone(room)] || ""} ${T[lang].actions[fan ? fan.word : actionCode(room)] || T[lang].actions.unknown}`;
  }
  // The rooms overview: every room of the shown floors with what FreshAirIQ publishes for it; a tap opens its details,
  // "show on the plan" switches to its floor and highlights it
  _roomsBody(layout) { return P.roomsBody(this, H, layout); }   // 0.26.7.0(2): the whole room card is the button
  // The removable moisture by room – the very values FreshAirIQ publishes for each room (no second calculation): during an
  // airing the rooms that air (their result so far, their time left), otherwise every valid room's realistic amount for the
  // recommended time. The total is the card's own; a difference from rounding the room values is said, never hidden.
  _moistureRooms(layout, f) {
    const t = k => this._t(k), rooms = Object.values(this._rooms || {}).filter(r => r && typeof r === "object" && r.calculation_enabled !== false && (r.data_quality == null || r.data_quality === "ok"));
    const pick = f.live ? rooms.filter(r => r.active) : rooms;
    const rows = pick.map(r => {
      const ml = known(f.live ? r.result_ml : r.realistic_potential_ml);
      if (!Number.isFinite(ml)) return null;
      const lr = layout.rooms.find(x => x.room_key === r.key) || null;
      const target = known(r.session_target_min ?? r.session_recommended_duration_min), elapsed = known(r.session_elapsed_min), horizon = known(r.potential_horizon_min);
      const time = f.live ? (Number.isFinite(target) && Number.isFinite(elapsed) ? t("moist_room_left").replace("{m}", Math.max(0, Math.ceil(target - elapsed))) : "")
        : Number.isFinite(horizon) && horizon > 0 ? t("moist_room_for").replace("{m}", Math.round(horizon)) : "";
      const state = f.live ? t(r.session_finalization_pending ? "moist_room_final" : "moist_room_live") : this._actionWord(r);
      return { ml, html: `<div class="rrow t-${roomTone(r)}" style="--tone:${V.TONE_COLOR[roomTone(r)]}"><button class="rmain" ${lr ? `data-room-open="${esc(lr.id)}"` : "disabled"}><b>${esc(r.name || r.key)}</b><span class="rsub">${lr ? this._roomFloor(layout, lr) : "–"}</span>`
        + `<span class="rvals"><span><b>${ml <= -1 ? "+" : "≈ "}${Math.abs(Math.round(ml))} ml</b></span>${time ? `<span>⏱ ${esc(time)}</span>` : ""}<span>${esc(state)}</span></span></button></div>` };
    }).filter(Boolean).sort((a, b) => Math.abs(b.ml) - Math.abs(a.ml));
    if (!rows.length) return "";
    const sum = rows.reduce((s, r) => s + Math.round(r.ml), 0), diff = Math.round(f.amount) - sum;
    return `<h4>${esc(t("moist_by_room"))}</h4><div class="rlist">${rows.map(r => r.html).join("")}</div>`
      + `<div class="legend">${esc(t("moist_total"))}: ${f.amount <= -1 ? "+" : "≈ "}${Math.abs(Math.round(f.amount))} ml${diff ? ` · ${esc(t("moist_rounding").replace("{d}", Math.abs(diff)))}` : ""}</div>`;
  }
  _tile(label, value, subText) { return `<div class="tile"><div class="l">${esc(label)}</div><div class="v">${value}</div>${subText ? `<div class="s">${subText}</div>` : ""}</div>`; }
  // The detail window (tap on a room, an opening or an air path).
  _dialogHtml(layout) {
    const sel = this._selected;
    if (!sel) return "";
    const t = k => this._t(k), lang = this._lang();
    const air = this._house && this._house.airflow;
    const n = (v, d = 1, unit = "") => (v == null || !Number.isFinite(Number(v)) ? "–" : `${Number(v).toFixed(d)}${unit}`);
    // UI order (0.26.7.0): every window in the house map's style (the moisture, opening and air-path windows were white);
    // the head's text is ink or white, whichever is readable on its colour
    const wrap = (headColor, emo, title, act, body, cls = " dark world") => `<dialog class="roomdlg" aria-label="${esc(title)}"><div class="dlg${cls}">
      <header style="background:${headColor};color:${D.onColor(headColor)}">${this._nav && this._nav.length ? `<button class="navback" data-nav-back aria-label="${esc(P.TXT[lang].back)}">‹ ${esc(P.TXT[lang].back)}</button>` : ""}<span class="emo">${emo}</span><div><h3>${esc(title)}</h3>${act ? `<div class="act">${act}</div>` : ""}</div></header>
      <div class="body">${body}</div><div class="foot"><button data-close-detail>${esc(t("close"))}</button></div></div></dialog>`;
    if (sel.type === "support") return wrap(V.BRAND.cyan, "🛟", t("support_title"), "", this._supportBody(), " dark world support");
    // 0.26.7.0: the overviews belong to the house map's world – its sky as background, its colours and symbols
    if (sel.type === "rooms") return wrap(V.BRAND.cyan, "▦", t("rooms_title"), "", this._roomsBody(layout), " dark world");
    if (sel.type === "weather") {
      // 0.26.7.0(2) error B: the condition switched off shows no symbol – also not in the window's head
      const m = this._weatherModel(), fc = this._forecast || {}, details = this._details();
      const emo = details.includes("condition") && W.hasSymbol(m.condition) ? W.weatherSvg(m.condition, { size: 30, night: m.sun.phase === "night" }) : "";
      return wrap(V.BRAND.sky, emo, t("weather_title"), "", W.overviewHtml(m, { lang, info: this._info(), details, geo: this._geo(), forecastFailed: !!(fc.hourlyFailed || fc.dailyFailed), tz: this._tz() }), " dark world wxdlg");
    }
    // 0.26.7.0(2): more about the house's decision, the airing log – in the map's world
    if (sel.type === "house") return wrap(V.BRAND.cyan, "📊", P.TXT[lang].details_title, "", P.houseBody(this, H, layout), " dark world");
    if (sel.type === "ventlog") return wrap(V.BRAND.cyan, "📄", P.TXT[lang].log_title, "", P.ventLogBody(this), " dark world");
    // 0.26.7.0(2): a view of the FreshAirIQ card's details (learning, forecast quality with the formula comparison, water, …)
    if (sel.type === "classic") { const v = this._classicView(sel.id); return wrap(V.BRAND.cyan, P.classicIcon(sel.id), v.title || P.TXT[lang].learn_title, "", P.classicBody(this, v.html, sel.id), " dark world classicview"); }
    if (sel.type === "moisture") {
      const f = this._moistureFacts() || { amount: 0, minutes: null, live: false, waits: false, over: false };
      const value = f.amount <= -1 ? `+${Math.abs(f.amount)} ml` : `≈ ${Math.max(f.amount, 0)} ml`, sub = f.amount <= -1 ? t(f.live ? "moist_added_sub" : "moist_would_add_sub") : t(f.live ? "moist_so_far_sub" : "moist_now_sub");
      const time = f.minutes != null ? (f.over ? `+${f.minutes} ${esc(t("min_short"))}` : `${f.minutes} ${esc(t("min_short"))}`) : "–";
      return wrap(V.BRAND.sky, "💧", t("moist_title"), "", `<p class="lead" data-moist-intro>${esc(t(f.live ? "moist_intro_live" : "moist_intro_now"))} ${esc(t(f.live ? "moist_rooms_live" : "moist_rooms_now"))}</p><div class="tiles">${this._tile(t(f.live ? "moist_so_far" : "moist_now"), value, esc(sub))}`
        + `${this._tile(t(f.live ? (f.over ? "moist_over_tile" : "moist_remaining") : "moist_duration"), time, "")}${this._tile(t("moist_confidence"), Number.isFinite(f.confidence) ? `${Math.round(f.confidence)} %` : "–", "")}</div>`
        + `${f.amount >= 1 || f.live ? "" : `<p>${esc(t("moist_none"))}</p>`}${f.waits ? `<p>${esc(t("moist_wait"))}</p>` : ""}${f.live && Math.abs(f.amount) < 1 ? `<p class="hint" data-moist-zero>${esc(t("moist_zero"))}</p>` : ""}${this._moistureRooms(layout, f)}`
        // UI order (0.26.7.0): a short answer first, the full explanation folded away – nothing of it is lost
        + `<details class="more"><summary>${esc(t("moist_more"))}</summary><p class="hint">${esc(t("moist_explain"))}</p>${f.live && Math.abs(f.amount) >= 1 ? `<p class="hint">${esc(t("moist_zero"))}</p>` : ""}</details>`);
    }
    if (sel.type === "room") {
      const lr = layout.rooms.find(r => r.id === sel.id);
      const room = lr && this._rooms[lr.room_key];
      if (!room) return wrap(V.BRAND.slate, "🔧", lr ? lr.room_key : "–", "", `<p>${esc(t("no_room_data"))}</p>`);
      const tone = roomTone(room);
      const fan = fanClose(room);
      // 0.26.7.0(2): everything the FreshAirIQ card tells about the room, in the house map's style (freshairiq-house-panels.js)
      return wrap(V.TONE_COLOR[tone], V.TONE_EMOJI[tone], room.name || lr.room_key, esc(T[lang].actions[fan ? fan.word : actionCode(room)] || actionCode(room)),
        P.roomBody(this, H, layout, lr, room), " dark world roomview");
    }
    if (sel.type === "opening") {
      const o = (layout.openings || []).find(x => x.id === sel.id);
      const st = (air && air.openings[sel.id]) || { state: "unknown" };
      const room = o && layout.rooms.find(r => r.id === o.room_id);
      // hotfix after review (F01): a contact's live state by its sensor – also when the room it airs (setup) is not
      // the room it is drawn in (e.g. a guest WC window set up for the hall)
      const allRooms = (this._house && this._house.rooms) || {}, homeKey = room && room.room_key;
      const sensor = c => [homeKey, ...Object.keys(allRooms).sort()].map(k => allRooms[k] && allRooms[k].contacts && allRooms[k].contacts[c]).find(Boolean);
      const rows = ((o && o.contacts) || []).map(c => { const d = sensor(c); return `<li>${esc(c)}: ${d ? esc(d.pending ? t("st_pending") : t(`st_${d.state}`)) : "–"}${d && d.delay_s ? ` · ${t("delay")} ${d.delay_s} ${t("s")}` : ""}</li>`; }).join("");
      const facade = st.facade_deg != null ? `${Math.round(st.facade_deg)}° · ${t(st.exposure)}` : t(st.exposure || "unknown");
      return wrap(V.BRAND.sky, "🪟", this._openingText(o || {}, st), "", `<div class="tiles">${this._tile(t("wall"), esc(facade), st.facade_basis === "configured_orientation" ? esc(t("north_unconfirmed")) : "")}</div>${rows ? `<ul>${rows}</ul>` : `<p>${esc(t("st_no_sensor"))}</p>`}`);
    }
    const p = air && air.paths[sel.id];
    if (!p) return "";
    const list = (prefix, items) => (items || []).map(x => esc(this._t(`${prefix}_${x}`) === `${prefix}_${x}` ? x : this._t(`${prefix}_${x}`))).join(", ") || "–";
    return wrap(V.BRAND.lime, "🌬️", t(`k_${p.kind}`), esc(`${t("confidence")}: ${t(p.confidence)}`),
      `<div class="tiles">${this._tile(t("basis"), "", list("b", p.basis))}${this._tile(t("assumptions"), "", list("a", p.assumptions))}${this._tile(t("unknowns"), "", list("u", p.unknowns))}</div><p class="hint">${esc(t("hypothesis"))}</p>`);
  }
  // ---- wind clock (owner request 31.10.): one continuous phase per card, never reset by a redraw or new data
  _bindWaves() {
    const els = this.shadowRoot.querySelectorAll("path[data-wave]");
    this._waves = [...els].map(el => Object.assign({ el }, (this._wavesNext || [])[Number(el.dataset.wave)])).filter(w => w.frame);
    this._wavesNext = null;
    const svg = this.shadowRoot.querySelector("svg.plan");
    if (svg) this._windDur = parseFloat(svg.style.getPropertyValue("--dur")) || this._windDur || 2;
    this._windSync();
  }
  // order 8: one canvas per card over the plan; it survives redraws (the air keeps flowing) and is moved into the new
  // map. Positioned exactly over the drawing; labels are kept clear on it.
  _bindFlow() {
    const map = this.shadowRoot.querySelector(".map"), svg = map && map.querySelector("svg.plan"), scene = this._flowScene;
    // 0.26.7.0 UI hotfix: the sky and weather layer under the plan lies exactly under the drawing (same box, same viewBox)
    const under = map && map.querySelector(":scope > .wxu");
    if (under && svg) { const mr = map.getBoundingClientRect(), sr = svg.getBoundingClientRect(); Object.assign(under.style, { left: `${sr.left - mr.left + map.scrollLeft}px`, top: `${sr.top - mr.top + map.scrollTop}px`, width: `${sr.width}px`, height: `${sr.height}px` }); }
    if (!svg || !scene || (!scene.field && !scene.routes.length)) { if (this._flowCanvas) this._flowCanvas.remove(); if (this._flowLayer) this._flowLayer.field = null; return; }
    if (!this._flowCanvas) { this._flowCanvas = document.createElement("canvas"); this._flowCanvas.className = "flow"; this._flowCanvas.setAttribute("aria-hidden", "true"); }
    const cv = this._flowCanvas, mr = map.getBoundingClientRect(), sr = svg.getBoundingClientRect();
    Object.assign(cv.style, { left: `${sr.left - mr.left + map.scrollLeft}px`, top: `${sr.top - mr.top + map.scrollTop}px`, width: `${sr.width}px`, height: `${sr.height}px` });
    map.appendChild(cv);
    if (!this._flowLayer) this._flowLayer = new FL.FlowLayer(cv, F);
    const clear = [...svg.querySelectorAll(".tag, g.source, g.fan, g.conn-mark")].map(g => { try { const b = g.getBBox(); return { x: b.x, y: b.y, w: b.width, h: b.height }; } catch (_) { return null; } }).filter(Boolean);
    // 0.26.7.0(2): the share of threads and their pace from the animation level (a still picture keeps a few to draw)
    const m = this._motionNow || this._motion();
    // 0.26.7.0(2) (owner: "remove the small white strokes completely"): no threads around the house any more – the wind there is
    // the calm ribbons; the canvas carries only the air that flows in through an open window (its share by the level)
    this._flowLayer.setScene({ ...scene, clear, budget: { particles: 0, routeParts: m.still || !m.parts.wind ? 0.4 : m.routeParts, pace: m.pace || 0.7, dpr: m.dpr || 2 } });
    this._flowSceneKey = scene.key;
    if (this._windStill()) this._flowLayer.still();
  }
  // Hotfix F04: animation off or "reduce motion" stops a running loop at once; switching back continues the
  // same phase. Never two loops per card.
  // 0.26.7.0(2): still with reduced motion, the animation off, the level off or resting, or the wind part switched off
  _windStill() { if (this._config.animation === false || this._reduced()) return true; const m = this._motionNow || this._motion(); return m.still || !m.parts.wind; }
  _windSync() {
    if (this._windStill() || !this.isConnected || !this._waves || !this._waves.length || this.hasAttribute("data-paused")) { this._windStop(); return; }  // 0.26.7.0: no loop while paused
    // one loop for every house map on the page (freshairiq-house-motion.js), at this card's frame rate – never two per card
    const fps = (this._motionNow && this._motionNow.fps) || 20;
    if (!this._windRaf || this._windRaf.fps !== fps) { if (this._windRaf) M.untick(this); this._windRaf = M.tick(this, (now, dt) => this._windFrame(now, dt), fps); }
  }
  // the wind's clock: one continuous time per card (a redraw or new data never restarts it); each stream reads its own phase
  // from it (its own pace and offset), so the streams never move in step
  _wavePhase(w) { return (((this._windClock || 0) / ((this._windDur || 2) / (w.geo.pace || 1)) + (w.geo.offset || 0)) % 1 + 1) % 1; }
  _windFrame(now, dtMs) {
    if (!this.isConnected || !this._waves || !this._waves.length || this._windStill() || this.hasAttribute("data-paused")) { this._windStop(); return; }
    const m = this._motionNow || this._motion(), dt = Math.min(Math.max(dtMs || 0, 0), 250) / 1000, pace = m.pace || 0.8;   // a long gap continues calmly instead of jumping
    this._windPhase = ((this._windPhase || 0) + dt * pace / (this._windDur || 2)) % 1;
    this._windClock = (this._windClock || 0) + dt * pace;
    // order 8: the broad air layers breathe – their bend changes slowly, each layer in its own rhythm
    const t = this._windClock;
    for (const w of this._waves) w.el.setAttribute("d", V.wavePath(w.frame, { ...w.geo, amp: w.geo.amp * (1 + 0.3 * Math.sin(t * 0.21 + w.geo.shift * 1.7)) }, this._wavePhase(w)));
    if (this._flowLayer) this._flowLayer.frame(dt);
    // a long untouched card steps down (calmer) or rests (still): decided here, where the time passes anyway
    if (now - (this._levelCheck || 0) > 5000) { this._levelCheck = now; if (this._motion().level !== m.level) this._queue(); }
  }
  _windStop() { if (this._windRaf) M.untick(this); this._windRaf = null; this._windLast = null; }
  // The card frame: <style> and <ha-card> once, the content in .faiq-main, the room window next to it.
  _frameElements() {
    const root = this.shadowRoot;
    const find = () => [...root.children].find(n => n.localName === "ha-card");  // (":scope" does not apply to a shadow root)
    let card = find();
    if (!card) {
      root.innerHTML = `<style>${V.STYLE}${A.ATMOS_STYLE}${W.WORLD_STYLE}${WORKSPACE_STYLE}${PLUS_STYLE}${P.PANELS_STYLE}${D.DESIGN_STYLE}</style><ha-card></ha-card>`;
      card = find();
    }
    let main = card.querySelector(":scope > .faiq-main");
    if (!main) { card.replaceChildren(); main = document.createElement("div"); main.className = "faiq-main"; card.appendChild(main); }
    return { card, main };
  }
  // The room window is opened (showModal) once; a live update refreshes its content in place – no new focus,
  // no scroll jump – and a different room replaces it.
  _syncDialog(card, html) {
    const old = card.querySelector(":scope > dialog.roomdlg");
    if (!html) { if (old) { try { old.close(); } catch (_) { /* closed */ } old.remove(); } return; }
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    const next = tpl.content.querySelector("dialog.roomdlg");
    const key = this._selected ? `${this._selected.type}:${this._selected.id}` : "";
    if (old && old.dataset.key === key && old.open) { if (key !== "support:" && key !== "ventlog:") old.innerHTML = next.innerHTML; return; }
    if (old) { try { old.close(); } catch (_) { /* closed */ } old.remove(); }
    next.dataset.key = key;
    next.addEventListener("cancel", ev => { ev.preventDefault(); this._back(); });   // 0.26.7.0 UI hotfix: Escape = one level back
    next.addEventListener("click", ev => { if (ev.target === next) this._closeDialog(); });  // backdrop
    card.insertBefore(next, card.querySelector(":scope > dialog.menudlg"));  // the room window first, then the menu
    try { next.showModal(); } catch (_) { next.setAttribute("open", ""); }
  }
  _closeDialog() { this._nav = []; this._selected = null; this._menuOpen = false; this._render(); }
  // ---- 0.26.7.0 UI hotfix: one history for every window of the house map. A window opened from the menu or from another window
  // remembers where it came from (and its scroll); "Back" returns exactly one level, "Close" and the backdrop close them all; a
  // window opened right from the map starts a new history (no menu as a made-up step in between). Only one window is open.
  _go(type, id) {
    const card = [...this.shadowRoot.children].find(n => n.localName === "ha-card"), body = card && card.querySelector(":scope > dialog[open] .body");
    const top = body ? body.scrollTop : 0;
    if (this._menuOpen) (this._nav || (this._nav = [])).push({ menu: true, top });
    else if (this._selected) (this._nav || (this._nav = [])).push({ type: this._selected.type, id: this._selected.id, top });
    else this._nav = [];
    this._menuOpen = false; this._selected = { type, id }; this._render();
  }
  _back() {
    const prev = (this._nav || []).pop();
    if (!prev) { this._closeDialog(); return; }
    this._restoreTop = prev.top;
    if (prev.menu) { this._selected = null; this._menuOpen = true; } else { this._selected = { type: prev.type, id: prev.id }; this._menuOpen = false; }
    this._render();
  }
  _render() {
    if (this._editing) return;
    this._applyMotion();   // 0.26.7.0(2): the level in effect now (device, reduced motion, untouched time)
    this._wavesNext = [];
    const root = this.shadowRoot;
    const isAdmin = !!(this._hass && this._hass.user && this._hass.user.is_admin);
    let body, dialogHtml = "";
    const current = this._layout();
    if (this._failed === "not_loaded") body = `<div class="notice warn">${esc(this._t("not_loaded"))}</div>`;
    else if (!current) body = `<div class="notice">${esc(this._failed ? this._t("live_failed") : this._t("loading"))}</div>`;
    else {
      const layout = current.layout;
      const floors = this._floors(layout);
      if (floors.length && !floors.some(f => f.id === this._floor)) this._floor = this._startFloor(floors);
      // 0.26.6: the plan fills the card. Warnings that need a tap now lie on the plan (top left), notes about the
      // drawing (proposal, estimates, north, the schematic wind) are in the menu, whose button sits at the bottom
      // right of the plan; the wind tile is gone – the animated streams show where the wind comes from.
      const warn = [];
      if (this._failed) warn.push(`<div class="notice warn" role="status">${esc(this._t("live_failed"))}</div>`);
      // 0.26.6.1(2): no "action on another floor" notice – that floor's button pulses (see _floorButtons)
      if (this._config.auto_focus === "auto" && this._lockUntil > Date.now()) {
        const until = new Date(this._lockUntil).toLocaleTimeString(this._lang(), { hour: "2-digit", minute: "2-digit" });
        warn.push(`<div class="notice">${esc(this._t("focus_paused"))} ${esc(until)} <button class="small" data-resume>${esc(this._t("focus_resume"))}</button></div>`);
      }
      const menuOpen = !!this._menuOpen;
      // UI hotfix: floors and menu sit in a bar at the bottom edge of the card, below the plan – they never cover
      // rooms, walls, windows or labels; the plan's own bottom margin stays a free zone for the wind streams
      // 0.26.6.1(7): a slim bar above the plan – notes that need a tap on the left, the local weather (or the card's
      // own sensors) on the right; like the bottom bar it never covers the plan
      const weather = this._weatherChip(), moist = this._moistureChip();
      const top = warn.length || weather || moist ? `<div class="topbar">${moist || warn.length ? `<div class="warns">${moist}${warn.join("")}</div>` : ""}${weather}</div>` : "";
      // 0.26.7.0: an optional "Rooms" button next to the menu; a wide card uses its free sides for weather and status
      const roomsBtn = this._config.rooms_button ? `<button class="rooms-btn fab" data-rooms aria-haspopup="dialog">▦ ${esc(this._t("rooms_btn"))}</button>` : "";
      const side = this._sideWidth(layout);
      this._sideShown = side > 0;
      const mapPart = side ? `<div class="duo" style="--side:${side}px">${this._maps(layout)}<aside class="wxside" aria-label="${esc(this._t("weather_title"))}">${this._sidePanel()}</aside></div>` : this._maps(layout);
      // 0.26.7.0 UI hotfix: with a drawing the bars lie over it (``over``) – the drawing reaches under them (see _svg)
      const over = mapPart.includes("<svg");
      body = `<div class="stage${side ? " side" : ""}${over ? " over" : ""}" style="--bar-top:${(this._bars && this._bars.top) || 0}px;--bar-bottom:${(this._bars && this._bars.bottom) || 0}px">${top}${mapPart}<div class="mapbar">${this._floorButtons(layout, floors)}`
        + `${roomsBtn}<button class="menu-btn fab" data-menu aria-haspopup="dialog" aria-expanded="${menuOpen}">☰ ${esc(this._t("menu"))}</button></div></div>`;
      dialogHtml = this._dialogHtml(layout);
    }
    // Community hotfix: a live update keeps where the user scrolled (map, room window)
    const scroll = [...root.querySelectorAll(".map, dialog.roomdlg .dlg .body")].map(el => [el.scrollLeft, el.scrollTop]);
    const scrollKey = ((root.querySelector("dialog.roomdlg") || {}).dataset || {}).key;
    // Hotfix F02 ("the house map keeps jumping up"): <ha-card> and the open room window stay the same elements.
    // A new <ha-card> has no content until Home Assistant has drawn it (a microtask later); the scroll
    // restore below measured the page in that moment, the card was a few pixels high and the browser cut the
    // page scroll back – WebKit keeps that cut. Only the content inside the card is replaced now.
    const focus = focusKey(root.activeElement);
    const { card, main } = this._frameElements();
    main.innerHTML = current ? body : `${this._hero(null)}${body}`;
    card.classList.toggle("plan-first", !!current);
    // 0.26.7.0: the weather column changed the plan's width – the labels are fitted again for the new width (once)
    const mapNow = main.querySelector(".map"), mapW = mapNow ? mapNow.getBoundingClientRect().width : 0;
    if (mapW && this._lastWidth && Math.abs(mapW - this._lastWidth) > 24) requestAnimationFrame(() => this._queue());
    // 0.26.7.0 UI hotfix: the bars' real height decides how far the drawing reaches under them – measured after drawing; a
    // changed height (another width, a warning more) draws once more (the bars never depend on the drawing: no loop)
    const stageNow = main.querySelector(".stage.over");
    if (stageNow) {
      const h = sel => { const n = stageNow.querySelector(`:scope > ${sel}`); return n ? Math.ceil(n.getBoundingClientRect().height) : 0; };
      const bars = { top: h(".topbar"), bottom: h(".mapbar") }, old = this._bars || { top: 0, bottom: 0 };
      if (Math.abs(bars.top - old.top) > 1 || Math.abs(bars.bottom - old.bottom) > 1) { this._bars = bars; requestAnimationFrame(() => this._queue()); }
      // the side column is never taller than the drawing (it scrolls inside), so the bars lie over the drawing on both sides
      const aside = stageNow.querySelector(".wxside"), drawn = stageNow.querySelector("svg.plan");
      if (aside && drawn) aside.style.maxHeight = `${Math.max(Math.round(drawn.getBoundingClientRect().height) - bars.top - bars.bottom, 160)}px`;
    }
    this._bindFlow();
    this._bindWaves();
    this._syncMenu(card, current ? current.layout : null);  // before the bindings below: its buttons are bound with the rest
    root.querySelectorAll("[data-floor]").forEach(b => b.addEventListener("click", () => this._chooseFloor(b.dataset.floor)));
    root.querySelectorAll("[data-layer]").forEach(b => b.addEventListener("click", () => { this._layer = b.dataset.layer; this._persist(); this._render(); }));
    const select = (type, id) => { this._nav = []; this._selected = { type, id }; this._render(); };   // from the map: a new history
    const bind = (selector, attr, type) => root.querySelectorAll(selector).forEach(el => {
      el.addEventListener("click", () => select(type, type === "path" ? Number(el.dataset[attr]) : el.dataset[attr]));
      el.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(type, type === "path" ? Number(el.dataset[attr]) : el.dataset[attr]); } });
    });
    this._syncDialog(card, dialogHtml);
    bind("[data-room]", "room", "room"); bind("[data-opening]", "opening", "opening"); bind("[data-path]", "path", "path");
    const dialog = card.querySelector(":scope > dialog.roomdlg");
    if (dialog) dialog.querySelector("[data-close-detail]").addEventListener("click", () => this._closeDialog());
    // a live update keeps the scroll of the same window; another window (navigation) starts at its top
    const sameWindow = ((card.querySelector(":scope > dialog.roomdlg") || {}).dataset || {}).key === scrollKey;
    root.querySelectorAll(".map, dialog.roomdlg .dlg .body").forEach((el, i) => { if (scroll[i] && (i === 0 || sameWindow)) [el.scrollLeft, el.scrollTop] = scroll[i]; });
    if (this._restoreTop != null) { const b = card.querySelector(":scope > dialog[open] .body"); if (b) b.scrollTop = this._restoreTop; this._restoreTop = null; }   // back: where it was
    const again = focus && root.querySelector(focus);  // a live update keeps the focused button where it still exists
    if (again && root.activeElement !== again) { try { again.focus({ preventScroll: true }); } catch (_) { /* old engine */ } }
    const resume = root.querySelector("[data-resume]");
    if (resume) resume.addEventListener("click", () => { this._lockUntil = 0; this._persist(); this._updateFocus(); this._render(); });
    const edit = root.querySelector("[data-edit]");
    if (edit) edit.addEventListener("click", () => { this._nav = []; this._closeMenu(); this._selected = null; this._openEditor(); });
    const menuBtn = root.querySelector("[data-menu]");
    if (menuBtn) menuBtn.addEventListener("click", () => this._openMenu());
    const support = root.querySelector("[data-support]");
    if (support) support.addEventListener("click", () => this._openSupport());
    const closeMenu = root.querySelector("[data-close-menu]");
    if (closeMenu) closeMenu.addEventListener("click", () => this._closeMenu());
    if (this._selected && this._selected.type === "support" && this._support) this._bindSupport(root);
    root.querySelectorAll("[data-guest]").forEach(b => b.addEventListener("click", () => this._setGuests(b.dataset.guest, Number(b.dataset.delta))));
    // 0.26.7.0: rooms overview, weather overview, a room chosen in an overview (its details) or shown on the plan
    // 0.26.7.0(2): the same windows also from the menu (the menu closes first); more about the decision; the airing log
    const fromMenu = (selector, type) => root.querySelectorAll(selector).forEach(b => b.addEventListener("click", () => this._go(type, "")));
    fromMenu("[data-moisture]", "moisture"); fromMenu("[data-rooms]", "rooms"); fromMenu("[data-weather-open]", "weather");
    fromMenu("[data-house-details]", "house"); fromMenu("[data-moisture-side]", "moisture");
    root.querySelectorAll("[data-ventlog]").forEach(b => b.addEventListener("click", async () => { try { await this._supportHost(); } catch (_) { /* the export says so */ } this._go("ventlog", ""); }));
    // a room from the overview: its details – and its floor on the plan behind, where it is outlined
    root.querySelectorAll("[data-room-open]").forEach(b => b.addEventListener("click", () => this._openRoom(b.dataset.roomOpen)));
    root.querySelectorAll("[data-room-jump]").forEach(b => b.addEventListener("click", () => this._jumpTo(b.dataset.roomJump)));
    root.querySelectorAll("[data-motion-level]").forEach(b => b.addEventListener("click", () => this._setMotionLevel(b.dataset.motionLevel)));
    // 0.26.7.0(2): the FreshAirIQ card's views and the links inside them (another view, a room by its key)
    root.querySelectorAll("[data-classic-info]").forEach(b => b.addEventListener("click", ev => { ev.stopPropagation(); this._go("classic", b.dataset.classicInfo); }));
    root.querySelectorAll("[data-nav-back]").forEach(b => b.addEventListener("click", ev => { ev.stopPropagation(); this._back(); }));
    root.querySelectorAll("[data-classic-room]").forEach(b => b.addEventListener("click", () => {
      const cur = this._layout(), lr = cur && cur.layout.rooms.find(r => r.room_key === b.dataset.classicRoom);
      if (lr) this._openRoom(lr.id);
    }));
    if (this._selected && this._selected.type === "ventlog") this._bindVentLog(root);
    if (this._sky0 !== JSON.stringify(this._skyColors)) {   // the overviews share the plan's sky
      this._sky0 = JSON.stringify(this._skyColors);
      if (this._skyColors) { this.style.setProperty("--sky-top", this._skyColors[0]); this.style.setProperty("--sky-bottom", this._skyColors[1]); }
      else { this.style.removeProperty("--sky-top"); this.style.removeProperty("--sky-bottom"); }
    }
    // 0.26.7.0(2): a window over the plan (room, rooms, weather, menu, support) pauses the plan's motion while it is open
    const covered = !!card.querySelector(":scope > dialog[open]");
    if (covered !== !!this._covered) { this._covered = covered; this._syncPaused(); }
    this._syncForecast();
  }
  // 0.26.7.0(2): a room from the overview – its details, with its floor shown behind (the room outlined there)
  _openRoom(id) {
    const current = this._layout(), lr = current && current.layout.rooms.find(r => r.id === id);
    if (lr && lr.floor_id !== this._floor && this._floors(current.layout).some(f => f.id === lr.floor_id)) { this._floor = lr.floor_id; this._lockUntil = Date.now() + Number(this._config.manual_lock_min || 10) * 60000; this._persist(); }
    this._go("room", id);
  }
  // the animation level chosen in the menu: kept for this card in this browser (the card's own setting stays as configured)
  _setMotionLevel(level) {
    if (!M.ANIMATION_LEVELS.includes(level)) return;
    // kept with the configured level it replaces: a new level set in the card's settings later wins again
    const base = this._baseLevel != null ? this._baseLevel : M.chosenLevel(this._config);
    this._baseLevel = base;
    this._config = { ...this._config, animation_level: level }; if (level !== "off" && this._config.animation === false) this._config.animation = true;
    try { localStorage.setItem(`${this._storeKey()}:motion`, JSON.stringify({ level, base })); } catch (_) { /* private mode */ }
    this._touched(); this._render(); this._windSync();
  }
  // The FreshAirIQ card's own views, computed by the card itself on a small host bound to this card (as "removable now" and
  // support): no second calculation. Their links lead to the house map's windows (a room's details, another view).
  _classicView(id) {
    if (!CARD || !CARD.FreshAirIQCard) { if (!this._cardWait) this._cardWait = CARD_READY.then(() => this._queue()); return { html: "", title: "" }; }
    const card = this;
    const h = this._clHost || (this._clHost = Object.create(CARD.FreshAirIQCard.prototype, { _config: { value: {}, writable: true }, _uiLanguage: { value: () => card._lang() },
      _hass: { get: () => card._hass }, _learningCardCache: { value: null, writable: true }, _info: { value: null, writable: true } }));
    const st = this._payload || {}, rooms = Object.values(this._rooms || {}).filter(r => r && typeof r === "object");
    let html = "";
    try { if (id === "learning") html = h._learningComponentsCard(st, rooms); else { h._info = id; html = h._infoPanel(st, rooms) || ""; } }
    catch (err) { console.error("FreshAirIQ house map: card view failed", id, err); html = ""; }
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    try { h._localizeLegacyFragment(tpl.content); } catch (_) { /* German stays */ }
    for (const [from, to] of [["data-info", "data-classic-info"], ["data-room", "data-classic-room"]]) tpl.content.querySelectorAll(`[${from}]`).forEach(el => { el.setAttribute(to, el.getAttribute(from)); el.removeAttribute(from); });
    tpl.content.querySelectorAll("[id]").forEach(el => el.removeAttribute("id"));
    const head = tpl.content.querySelector("h2, h3");
    let out = tpl.innerHTML;
    // the passive formula comparison belongs to "Wie gut FreshAirIQ aktuell vorhersagt": the FreshAirIQ card's own section
    // (freshairiq-card-shadow.js shadowSection), added here when the card class this host comes from carries no patch yet
    if (id === "learning:quality" && !out.includes("faiq-shadow-test")) {
      const en = this._lang() === "en", end = out.lastIndexOf("</section>");
      if (this._shadow && this._shadow.shadowSection) out = out.slice(0, end < 0 ? out.length : end) + this._shadow.shadowSection(st.forecast_shadow_comparison, en) + (end < 0 ? "" : out.slice(end));
      else if (this._shadow && this._shadow.failed) out += `<div class="learning-overview-note faiq-shadow-test" role="alert"><span><b>${esc(en ? "Experiment: new moisture formula (passive test)" : "Experiment: Neue Feuchteformel (passiver Test)")}</b><br>${esc(en ? "This section could not be loaded on this device. Please reload the page." : "Dieser Abschnitt konnte auf diesem Gerät nicht geladen werden. Bitte die Seite neu laden.")}<br><small>FAIQ-UI-SHADOW-001</small></span></div>`;
      else if (!this._shadowWait) this._shadowWait = import(new URL(`./freshairiq-card-shadow.js${Q}`, import.meta.url).href)
        .then(m => { this._shadow = m; }, err => { console.error("FreshAirIQ formula test section failed", err); this._shadow = { failed: true }; }).then(() => this._queue());
    }
    return { html: out, title: head ? head.textContent.trim() : "" };
  }
  _bindVentLog(root) {
    const dialog = root.querySelector("dialog.roomdlg");
    if (!dialog || dialog.dataset.bound || !this._support) return;   // drawn once: the chosen dates stay during live updates
    dialog.dataset.bound = "1";
    const h = this._support;
    for (const [id, fmt] of [["ventlog-export", "pdf"], ["ventlog-csv", "csv"]]) { const el = root.getElementById(id); if (el) el.addEventListener("click", ev => { ev.stopPropagation(); h._exportVentilationLog(fmt); }); }
  }
  // 0.26.7.0: from an overview to the room on the plan – its floor, a short highlight, no window over it
  _jumpTo(id) {
    const current = this._layout(), lr = current && current.layout.rooms.find(r => r.id === id);
    if (!lr) return;
    this._floor = lr.floor_id; this._selected = null; this._spot = { id, at: Date.now() };
    this._lockUntil = Date.now() + Number(this._config.manual_lock_min || 10) * 60000;
    this._persist(); this._render();
    clearTimeout(this._spotTimer);
    this._spotTimer = setTimeout(() => { this._spot = null; if (this.isConnected) this._queue(); }, 4100);
  }
  // The free width beside the plan on a wide card: "info" always uses a side column, "auto" only where the plan –
  // limited by the screen height – leaves at least 300 px unused; "focus" never. The plan's geometry is unchanged.
  _sideWidth(layout) {
    const mode = W.LAYOUTS.includes(this._config.layout) ? this._config.layout : "auto";
    const cw = this.getBoundingClientRect().width || 0;
    if (mode === "focus" || cw < 640) return 0;
    if (mode === "info") return Math.round(Math.min(Math.max(cw * 0.32, 260), 380));
    const rooms = layout.rooms.filter(r => r.floor_id === this._floor && Array.isArray(r.polygon) && r.polygon.length >= 3);
    if (!rooms.length) return 0;
    const box = G.bbox(rooms.map(r => r.polygon)), span = Math.max(box.maxX - box.minX, box.maxY - box.minY, 1), m = span * 0.32;
    const aspect = (box.maxY - box.minY + m) / (box.maxX - box.minX + m), cap = (window.innerHeight || 800) * 0.78;
    const free = cw - Math.min(cw, cap / aspect);
    return free >= 300 ? Math.round(Math.min(free, 400)) : 0;
  }
  // the side column: the weather (as far as the card shows it) and the house's state, in the plan's sky
  _sidePanel() {
    const p = this._payload || {}, rec = p.intelligent_recommendation && typeof p.intelligent_recommendation === "object" ? p.intelligent_recommendation : {};
    const tone = heroTone(rec), f = this._moistureFacts();
    const status = rec.title ? `<div class="bubble" data-tone="${tone}" style="border-left:8px solid ${V.TONE_COLOR[tone]}"><span class="emo">${V.TONE_EMOJI[tone]}</span><div>${esc(rec.title)}${rec.instruction || rec.summary ? `<small>${esc(rec.instruction || rec.summary)}</small>` : ""}</div></div>` : "";
    const moist = f ? `<button class="moist side-moist" data-moisture-side><span>💧 ${f.amount <= -1 ? `+${Math.abs(f.amount)}` : `≈ ${Math.max(f.amount, 0)}`} ml</span>${f.minutes != null ? `<span>⏱ ${f.minutes} ${esc(this._t("min_short"))}</span>` : ""}</button>` : "";
    const info = this._info().filter(k => k !== "daily");
    return `${status}${moist}${W.overviewHtml(this._weatherModel(), { lang: this._lang(), info, compact: true, geo: this._geo(), details: this._details(), forecastFailed: !!(this._forecast && this._forecast.hourlyFailed), tz: this._tz() })}`
      + `${this._info().includes("overview") ? `<button class="small" data-weather-open>${esc(this._t("weather_open"))}</button>` : ""}`;
  }
  // 0.26.6.1(2): the menu is a real window (<dialog>) over the plan. The dialog element stays: live updates refresh
  // its content in place (an open menu stays open, keeps its scroll and the focused button); it opens with showModal.
  _syncMenu(card, layout) {
    let dlg = card.querySelector(":scope > dialog.menudlg");
    if (!layout) { if (dlg) { try { dlg.close(); } catch (_) { /* closed */ } dlg.remove(); } return; }
    if (!dlg) {
      dlg = document.createElement("dialog");
      dlg.className = "menudlg roomdlg-like";
      dlg.addEventListener("cancel", ev => { ev.preventDefault(); this._closeMenu(); });
      dlg.addEventListener("click", ev => { if (ev.target === dlg) this._closeMenu(); });  // backdrop
      card.appendChild(dlg);
    }
    dlg.setAttribute("aria-label", this._t("menu"));
    const html = `<div class="dlg dark world"><header style="background:${V.BRAND.cyan};color:${D.onColor(V.BRAND.cyan)}"><span class="emo">☰</span><div><h3>${esc(this._t("menu"))}</h3></div></header>`
      + `<div class="body">${this._menuBody(layout)}</div><div class="foot"><button data-close-menu>${esc(this._t("close"))}</button></div></div>`;
    const body = dlg.querySelector(".body"), top = body ? body.scrollTop : 0;
    dlg.innerHTML = html;  // new content every render, so every button is bound exactly once; its scroll is kept
    const again = dlg.querySelector(".body");
    if (again) again.scrollTop = top;
    if (this._menuOpen && !dlg.open) { try { dlg.showModal(); } catch (_) { dlg.setAttribute("open", ""); } }
    if (!this._menuOpen && dlg.open) { try { dlg.close(); } catch (_) { dlg.removeAttribute("open"); } }
  }
  _openMenu() { this._menuOpen = true; this._render(); }
  _closeMenu() { if (!this._menuOpen) return; this._nav = []; this._menuOpen = false; this._render(); }
  // 0.26.6.1(2): the menu as a window over the plan (layers, details, guests, notes, support, editing)
  _menuBody(layout) {
    const t = k => this._t(k), current = this._layout(), air = this._house && this._house.airflow;
    const notes = [];
    if (current && !current.saved) notes.push(t("proposal"));
    if (layout.building.units === "schematic") notes.push(t("schematic"));
    else if (layout.rooms.some(r => r.provenance === "estimated" || r.provenance === "schematic")) notes.push(t("estimated"));
    if (!layout.building.north_confirmed) notes.push(t("north_unconfirmed"));
    notes.push(t("streams_note"));
    if (this._layer === "airflow") notes.push(`${t("model")}: ${air ? t(air.model_level) : "–"} · ${t("hypothesis")}${air && !air.paths.length ? ` · ${t("no_paths")}` : ""}`);
    // 0.26.7.0(2): grouped – information, control and modes, tools, notes (freshairiq-house-panels.js)
    return P.menuBody(this, H, layout, notes);
  }
  // 0.26.6.1(2): support in its own window over the house map – the very support functions of the FreshAirIQ
  // dashboard card (diagnostics with required description, download, feedback, cooldowns, error codes); only the
  // look is the house map's. The card's methods run on a small host bound to this card (no second support logic).
  async _supportHost() {
    if (this._support) return this._support;
    const mod = await import(new URL(`./freshairiq-card.js${Q}`, import.meta.url).href);
    const card = this;
    const host = Object.create(mod.FreshAirIQCard.prototype, {
      shadowRoot: { get: () => card.shadowRoot },
      _hass: { get: () => card._hass },
      _uiLanguage: { value: () => card._lang() },
      _settingsEntryId: { value: () => card._config.entry_id || (card._layoutInfo && card._layoutInfo.entry_id) || null },
    });
    Object.assign(host, { _supportCooldownUntil: null, _feedbackCooldownUntil: null, _fieldTestRegistrationPromise: null, _lastSupportError: null });
    this._support = host;
    return host;
  }
  async _openSupport() {
    try { await this._supportHost(); } catch (err) { console.error("FreshAirIQ support module failed to load", err); }
    this._go("support", "");   // from the menu: Back returns there
  }
  _supportBody() {
    const t = k => this._t(k), h = this._support;
    if (!h) return `<p>${esc(t("support_unavailable"))}</p>`;
    const st = this._payload || {}, up = st.diagnostics_upload || {};
    const until = Date.parse(h._supportCooldownUntil || up.support_cooldown_until || "");
    const mins = until > Date.now() ? Math.max(1, Math.ceil((until - Date.now()) / 60000)) : 0;
    const feedbackMins = h._feedbackCooldownMinutes(st);
    const mode = t(`upload_${String(up.configured_reporting_mode || "daily")}`);
    return `<p>${esc(t("support_intro"))}</p>
      <h4>${esc(t("support_diag"))}</h4><label class="field"><b>${esc(t("support_message"))}</b><span class="hint2">${esc(t("support_privacy"))}</span>
      <textarea id="diagnostics-message" rows="4" minlength="10" maxlength="4000" required placeholder="${esc(t("support_placeholder"))}"></textarea></label>
      <div class="diag-actions"><button id="diagnostics-export"><span class="ico" aria-hidden="true">⬇️</span><b>${esc(t("support_export"))}</b></button>
      <button id="diagnostics-send"><span class="ico" aria-hidden="true">🔒</span><b>${mins ? esc(h._t("support.cooldown_button", { mins })) : esc(t("support_send"))}</b></button></div>
      <h4>${esc(t("feedback"))}</h4><label class="field"><b>${esc(t("feedback_kind"))}</b><select id="feedback-type"><option value="bug">${esc(t("feedback_bug"))}</option><option value="improvement">${esc(t("feedback_idea"))}</option><option value="other">${esc(t("feedback_other"))}</option></select></label>
      <label class="field"><b>${esc(t("feedback_text"))}</b><span class="hint2">${esc(t("feedback_secret"))}</span><textarea id="feedback-message" rows="5" maxlength="10000"></textarea></label>
      <div class="row"><button id="feedback-send"${feedbackMins ? " disabled" : ""}>${feedbackMins ? esc(h._t("feedback.cooldown_button", { mins: feedbackMins })) : `✉️ ${esc(t("feedback_send"))}`}</button></div>
      <div id="feedback-result" class="hint2">${esc(feedbackMins ? h._t("feedback.cooldown_next", { mins: feedbackMins }) : h._t("feedback.cooldown_hint"))}</div>
      <h4>${esc(t("support_mail"))}</h4><div>support@freshairiq.com</div><div class="hint2">${esc(t("support_auto"))}: ${esc(mode)}</div>`;
  }
  _bindSupport(root) {
    const dialog = root.querySelector("dialog.roomdlg");
    if (!dialog || dialog.dataset.bound) return;  // the support window is drawn once; its fields keep what was typed
    dialog.dataset.bound = "1";
    const h = this._support, on = (id, fn) => { const el = root.getElementById(id); if (el) el.addEventListener("click", ev => { ev.stopPropagation(); fn(el); }); };
    on("diagnostics-export", () => h._exportDiagnostics());
    on("diagnostics-send", () => h._sendDiagnosticsToDeveloper());
    on("feedback-send", el => h._sendFeedback(el));
  }
  async _openEditor() {
    const mod = await import(new URL(`./freshairiq-house-editor.js${Q}`, import.meta.url).href);
    const current = this._layout();
    const editor = document.createElement(mod.EDITOR_TAG);
    editor.hass = this._hass;
    editor.setup({
      entryId: this._config.entry_id || (this._layoutInfo && this._layoutInfo.entry_id) || null,
      layout: current ? current.layout : null, revision: this._layoutInfo ? this._layoutInfo.revision : 0,
      rooms: this._layoutInfo ? this._layoutInfo.rooms : [], liveRooms: this._rooms, language: this._lang(), floor: this._floor,
      underlays: this._layoutInfo ? this._layoutInfo.underlays : {},
    });
    // v0.26.6.1: the editor opens in its own workspace over the whole screen – as large as the screen allows, not as
    // narrow as the dashboard card; in the browser's top layer (popover) so no transformed parent can clip it. The
    // house map stays as it is underneath (it pauses while editing).
    const workspace = document.createElement("div");
    workspace.className = "faiq-editor-workspace";
    workspace.setAttribute("role", "dialog"); workspace.setAttribute("aria-modal", "true");
    workspace.setAttribute("aria-label", this._lang() === "de" ? "Grundriss bearbeiten" : "Edit floor plan");
    workspace.appendChild(editor);
    editor.addEventListener("freshairiq-house-editor-done", async ev => {
      this._editing = null;
      try { if (workspace.matches(":popover-open")) workspace.hidePopover(); } catch (_) { /* no Popover API */ }
      workspace.remove();
      if (ev.detail && ev.detail.saved) {
        try { this._layoutInfo = await this._hass.callWS(this._entryMsg("freshairiq/house_map/get")); this._proposal = null; } catch (_) { /* next push */ }
      }
      this._render();
    });
    this._editing = editor;
    this._frameElements();
    this.shadowRoot.appendChild(workspace);
    if (typeof workspace.showPopover === "function") {
      workspace.setAttribute("popover", "manual");
      try { workspace.showPopover(); } catch (_) { /* stays a fixed overlay */ }
    }
  }
}

// v0.26.6.1: the floor plan editor's own workspace – the full viewport (safe areas kept), its own scrolling
const WORKSPACE_STYLE = `.faiq-editor-workspace{position:fixed;inset:0;margin:0;width:100vw;height:100vh;height:100dvh;max-width:none;max-height:none;border:0;
padding:max(12px,env(safe-area-inset-top)) max(12px,env(safe-area-inset-right)) max(12px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left));
box-sizing:border-box;overflow:hidden;overscroll-behavior:contain;z-index:10050;background:var(--card-background-color,var(--primary-background-color,#ffffff));color:var(--primary-text-color,#1b1f23)}
.faiq-editor-workspace:popover-open{display:block}.faiq-editor-workspace::backdrop{background:rgba(0,0,0,.45)}
.faiq-editor-workspace>freshairiq-house-layout-editor{max-width:1800px;margin:0 auto;height:100%;min-height:0}`;

// 0.26.7.0: rooms button, rooms/moisture lists, the side column of a wide card, the weather effect levels
const PLUS_STYLE = `
dialog.roomdlg .dlg,dialog.menudlg .dlg{max-height:calc(100vh - 40px);max-height:calc(100dvh - 40px)}
.rooms-btn{margin-left:auto}.rooms-btn+.menu-btn{margin-left:0}
.stage.side .duo{display:grid;grid-template-columns:minmax(0,1fr) var(--side);align-items:stretch;background:linear-gradient(160deg,var(--sky-top,#0f4479),var(--sky-bottom,#072a4f))}
.wxside{display:grid;align-content:start;gap:10px;padding:12px;min-width:0;overflow:auto;max-height:78vh;border-left:1px solid rgba(201,243,255,.18);background:rgba(2,16,36,.28)}
.stage.over .wxside{box-sizing:border-box;margin-top:var(--bar-top,0px);margin-bottom:var(--bar-bottom,0px)}
.wxside .bubble{margin:0}.wxside .side-moist{justify-self:start}
.dlg.dark.world{background:linear-gradient(170deg,var(--sky-top,#0f4479),var(--sky-bottom,#06223f))}
.rlist{display:grid;gap:6px}
.rrow{display:flex;gap:6px;align-items:stretch}
.rrow .rmain{flex:1 1 auto;min-width:0;display:grid;grid-template-columns:1fr auto;gap:2px 10px;text-align:left;padding:8px 12px;border-radius:14px;border:2px solid var(--fq-line2,rgba(201,243,255,.25));border-left:8px solid var(--tone,#7cc8f0);background:var(--fq-surface,rgba(2,16,36,.45));color:inherit;min-height:44px}
.rrow .rmain b{overflow-wrap:anywhere}.rrow .ract{font-weight:800;font-size:13px;text-align:right}
.rrow .rsub{font-size:12px;opacity:.85}.rrow .rvals{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px}
.rrow .rjump{flex:none;min-width:44px;font-size:18px}
.dlg:not(.dark) .rrow .rmain{background:rgba(255,255,255,.7);border-color:rgba(2,16,36,.2)}
polygon.room.spot{animation:spot 1s ease-in-out 4}
@keyframes spot{0%,100%{stroke-width:inherit;filter:none}50%{filter:drop-shadow(0 0 10px #fff)}}
button.weather{color:inherit;font:inherit;font-weight:800;font-size:13px;cursor:pointer;min-height:30px}
button.weather:focus-visible{outline:3px solid #ffd27a;outline-offset:2px}
:host([data-fx="subtle"]) .wx.flash,:host([data-fx="subtle"]) .wx.sunlight .ray{display:none}
:host([data-fx="subtle"]) .wx .fall{animation-duration:calc(1.2s * var(--k,1))}:host([data-fx="subtle"]) .wx.snow .fall{animation-duration:calc(9s * var(--k,1))}:host([data-fx="subtle"]) .wx.clouds > *{animation-duration:120s}
:host([data-fx="full"]) .wx.clouds > *{animation-duration:var(--cloud-dur,60s)}:host([data-fx="full"]) .wx.rain .fall{animation-duration:calc(var(--fall-dur,.55s) * var(--k,1))}
:host([data-fx="full"]) .wx.sunlight .ray{fill-opacity:var(--ray-o,.07)}
:host([data-fx="full"]) .wx.flash{animation:flash-soft 13s linear infinite}
@keyframes flash-soft{0%,93%,100%{opacity:0}94%{opacity:.32}95%{opacity:.04}96%{opacity:.18}97.5%{opacity:0}}
@media (prefers-reduced-motion:reduce){polygon.room.spot{animation:none;stroke:#fff}:host([data-fx="full"]) .wx.flash{animation:none;opacity:0}}
`;

class FreshAirIQHouseCardEditor extends HTMLElement {
  setConfig(config) { this._config = Object.assign({}, config || {}); this._render(); }
  set hass(hass) { this._hass = hass; if (!this._rendered) this._render(); this._loadPlan(); }
  // 0.26.7.0: floors and rooms of the saved plan for the floor and per-room choices (read only)
  async _loadPlan() {
    if (this._plan !== undefined || !this._hass || typeof this._hass.callWS !== "function") return;
    this._plan = null;
    try {
      const msg = { type: "freshairiq/house_map/get" };
      if (this._config && this._config.entry_id) msg.entry_id = this._config.entry_id;
      const info = await this._hass.callWS(msg);
      this._plan = info && info.layout ? { floors: info.layout.floors || [], rooms: info.layout.rooms || [], names: Object.fromEntries((info.rooms || []).map(r => [r.key, r.name])) } : null;
    } catch (_) { this._plan = null; }
    if (this._plan) this._render();
  }
  // 0.26.7.0 UI order: "Design & colours" – the three designs; own colours only where they stay readable
  _designGroup(c, de, note) {
    const L = de
      ? { mode: "Design", modes: { freshairiq: "FreshAirIQ-Design (Standard)", ha: "Home-Assistant-Theme übernehmen", custom: "Benutzerdefiniert" },
        accent: "Akzentfarbe (Schaltflächen)", background: "Kartenhintergrund", glass: "Transparent (Glas-Effekt, für transparente Dashboards)", dialog: "Fensterhintergrund",
        text: "Textfarbe in Fenstern", texts: { auto: "Automatisch (bester Kontrast)", light: "Hell", dark: "Dunkel" }, border: "Rahmenstärke (0–6 px)", radius: "Eckenrundung (0–32 px)", reset: "zurücksetzen",
        keep: "Gilt nur für Rahmen und Fenster dieser Karte. Grundriss, Wetter, Licht und die Zustandsfarben (Lüften, Warten, Schließen, Kritisch) bleiben unverändert.",
        ha: "Übernimmt Hintergrund, Text-, Akzent- und Rahmenfarbe, Rahmenstärke und Eckenrundung deines Home-Assistant-Themes. Unlesbare Kombinationen ersetzt die Karte automatisch durch lesbare. Das Wetterfenster bleibt im Himmelsstil.",
        issues: { text_contrast: "Die gewählte Textfarbe wäre auf dem Fensterhintergrund schlecht lesbar – es wird automatisch die lesbarste verwendet.", accent_contrast: "Auf der Akzentfarbe wäre keine Schrift lesbar – es wird die Standard-Akzentfarbe verwendet.",
          dialog_translucent: "Fenster brauchen einen deckenden Hintergrund – die Farbe wird deckend dargestellt.", design_accent_invalid: "Akzentfarbe: bitte als #rrggbb angeben.", design_background_invalid: "Kartenhintergrund: bitte als #rrggbb oder transparent angeben.",
          design_dialog_invalid: "Fensterhintergrund: bitte als #rrggbb angeben.", design_text_invalid: "Textfarbe: auto, light oder dark." } }
      : { mode: "Design", modes: { freshairiq: "FreshAirIQ design (default)", ha: "Use the Home Assistant theme", custom: "Custom" },
        accent: "Accent colour (buttons)", background: "Card background", glass: "Transparent (glass effect, for transparent dashboards)", dialog: "Window background",
        text: "Text colour in windows", texts: { auto: "Automatic (best contrast)", light: "Light", dark: "Dark" }, border: "Border width (0–6 px)", radius: "Corner radius (0–32 px)", reset: "reset",
        keep: "Only the frame and the windows of this card change. Plan, weather, light and the state colours (ventilate, wait, close, critical) stay as they are.",
        ha: "Takes the background, text, accent and border colour, border width and corner radius of your Home Assistant theme. The card replaces unreadable combinations with readable ones by itself. The weather window keeps its sky.",
        issues: { text_contrast: "The chosen text colour would be hard to read on the window background – the most readable one is used instead.", accent_contrast: "No text would be readable on the accent colour – the default accent is used.",
          dialog_translucent: "Windows need an opaque background – the colour is shown opaque.", design_accent_invalid: "Accent colour: please use #rrggbb.", design_background_invalid: "Card background: please use #rrggbb or transparent.",
          design_dialog_invalid: "Window background: please use #rrggbb.", design_text_invalid: "Text colour: auto, light or dark." } };
    const mode = D.designMode(c), choice = D.customChoice(c);
    const colour = (k, label, fallback) => { const v = D.parseHex(c[k]) ? c[k] : fallback;
      return `<label style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">${esc(label)} <input type="color" data-k="${k}" value="${esc(v)}" style="min-width:44px;min-height:32px">${c[k] != null && c[k] !== "transparent" ? `<button type="button" data-design-reset="${k}">${esc(L.reset)}</button>` : ""}</label>`; };
    let issues = [];
    if (mode === "custom") { const solid = choice.background && choice.background !== "transparent" ? choice.background : null; issues = [...choice.issues, ...D.palette({ dialog: choice.dialog || solid, accent: choice.accent, textMode: choice.text }).issues]; }
    const custom = mode !== "custom" ? "" : `${colour("design_accent", L.accent, "#00d8f0")}
      ${c.design_background === "transparent" ? "" : colour("design_background", L.background, "#06305c")}
      <label><input type="checkbox" data-design-glass${c.design_background === "transparent" ? " checked" : ""}> ${esc(L.glass)}</label>
      ${colour("design_dialog", L.dialog, "#0b2f57")}
      <label>${esc(L.text)}<br><select data-k="design_text">${D.TEXT_MODES.map(v => `<option value="${v}"${choice.text === v ? " selected" : ""}>${esc(L.texts[v])}</option>`).join("")}</select></label>
      <label>${esc(L.border)}<br><input data-k="design_border" type="number" min="0" max="${D.BORDER_MAX}" value="${esc(c.design_border ?? "")}" placeholder="1"></label>
      <label>${esc(L.radius)}<br><input data-k="design_radius" type="number" min="0" max="${D.RADIUS_MAX}" value="${esc(c.design_radius ?? "")}" placeholder="12"></label>`;
    return `<label>${esc(L.mode)}<br><select data-k="design">${D.DESIGN_MODES.map(v => `<option value="${v}"${mode === v ? " selected" : ""}>${esc(L.modes[v])}</option>`).join("")}</select></label>
      ${note(L.keep)}${mode === "ha" ? note(L.ha) : ""}${custom}
      ${[...new Set(issues)].map(k => `<div data-design-issue="${esc(k)}" style="color:var(--warning-color,#b26b00)">${esc(L.issues[k] || k)}</div>`).join("")}`;
  }
  _emit(next) {
    this._config = next;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: next }, bubbles: true, composed: true }));
  }
  _render() {
    if (!this._config) return;
    this._rendered = true;
    const de = String((this._hass && (this._hass.locale?.language || this._hass.language)) || navigator.language || "en").toLowerCase().startsWith("de");
    const L = de
      ? { weather: "Oben rechts statt Außenwetter: eigene Sensoren (optional, Entity-IDs mit Komma getrennt)", floor: "Etage dieser Karte (optional, z. B. ground_floor oder upper_floor) – für mehrere Karten mit verschiedenen Etagen", focus: "Etagen-Auto-Fokus", off: "Aus", hint: "Nur Hinweis", auto: "Automatisch", layer: "Start-Ebene", lock: "Manuelle Etagenwahl halten (min)", anim: "Luftweg-Animation", entry: "FreshAirIQ-Eintrag (optional)", title: "Titel",
        sec_rooms: "Räume im Grundriss", room_info: "Angezeigte Informationen (keine Auswahl = wie bisher)", per_room: "Eigene Auswahl je Raum", same: "wie oben", own: "eigene", rooms_button: "Button „Räume“ neben dem Menü",
        sec_floors: "Etagen", floors_visible: "Sichtbare Etagen (keine Auswahl = alle)", default_floor: "Beim Öffnen zeigen", default_none: "zuletzt gewählte",
        sec_weather: "Wetter", effects: "Wetterdarstellung", fx: { off: "Aus", subtle: "Dezent", dynamic: "Dynamisch (wie bisher)", full: "Vollständig animiert" }, weather_entity: "Wetterentität (optional, sonst die von FreshAirIQ)", weather_info: "Wetterinformationen",
        wi: { compact: "Kompakte Wetteranzeige", overview: "Erweiterte Wetterübersicht", hourly: "Stundenprognose", daily: "Tagesprognose", wind: "Windinformationen", sun: "Sonneninformationen", datetime: "Datum/Uhrzeit", compass: "Kompassrose im Grundriss",
          condition: "Wetterzustand", temperature: "Außentemperatur", apparent: "Gefühlte Temperatur", humidity: "Luftfeuchtigkeit", abs_humidity: "Absolute Luftfeuchtigkeit", pressure: "Luftdruck", rain_chance: "Regenwahrscheinlichkeit", dew_point: "Taupunkt", uv: "UV-Index" },
        layout: "Layout", lay: { auto: "Automatisch", focus: "Grundriss im Fokus", info: "Grundriss mit Wetter- und Statusinformationen" },
        weather_views: "Bereiche", weather_chip: "Oben rechts direkt sichtbar (keine Auswahl = keine Anzeige oben rechts)", weather_details: "Werte im Wetterfenster",
        ci: { temperature: "Außentemperatur", condition: "Wetterzustand (Symbol)", humidity: "Luftfeuchtigkeit", abs_humidity: "Absolute Luftfeuchtigkeit (g/m³)", wind: "Wind", rain: "Regen", apparent: "Gefühlte Temperatur", pressure: "Luftdruck", sun: "Sonne (Auf-/Untergang)", datetime: "Datum/Uhrzeit" },
        sec_motion: "Animation", motion_level: "Animationsstufe", ml: { auto: "Auto (nach Gerät)", off: "Aus", minimal: "Minimal (energiesparend)", normal: "Normal", intense: "Intensiv" },
        motion_parts: "Bewegt sich", mp: { wind: "Wind", weather: "Wettereffekte", light: "Licht & Sonne", ambient: "Atmosphäre (Räume, Dunst)" },
        ri: { name: "Raumname", temperature: "Temperatur", humidity: "Relative Feuchte", absolute_humidity: "Absolute Feuchte", action: "Lüftungsempfehlung", co2: "CO₂", mould: "Schimmelrisiko" } }
      : { weather: "Top right instead of the outdoor weather: own sensors (optional, entity ids separated by commas)", floor: "Floor of this card (optional, e.g. ground_floor or upper_floor) – for several cards showing different floors", focus: "Floor auto focus", off: "Off", hint: "Hint only", auto: "Automatic", layer: "Start layer", lock: "Keep a manual floor choice (min)", anim: "Air path animation", entry: "FreshAirIQ entry (optional)", title: "Title",
        sec_rooms: "Rooms on the plan", room_info: "Information shown (nothing chosen = as before)", per_room: "Own choice per room", same: "as above", own: "own", rooms_button: "\"Rooms\" button next to the menu",
        sec_floors: "Floors", floors_visible: "Floors shown (nothing chosen = all)", default_floor: "Show when opened", default_none: "last chosen",
        sec_weather: "Weather", effects: "Weather effects", fx: { off: "Off", subtle: "Subtle", dynamic: "Dynamic (as before)", full: "Fully animated" }, weather_entity: "Weather entity (optional, else FreshAirIQ's)", weather_info: "Weather information",
        wi: { compact: "Compact weather", overview: "Weather overview", hourly: "Hourly forecast", daily: "Daily forecast", wind: "Wind", sun: "Sun", datetime: "Date/time", compass: "Compass rose on the plan",
          condition: "Weather condition", temperature: "Outdoor temperature", apparent: "Feels like", humidity: "Humidity", abs_humidity: "Absolute humidity", pressure: "Pressure", rain_chance: "Chance of rain", dew_point: "Dew point", uv: "UV index" },
        layout: "Layout", lay: { auto: "Automatic", focus: "Plan in focus", info: "Plan with weather and status" },
        weather_views: "Parts", weather_chip: "Shown at the top right (nothing chosen = no display there)", weather_details: "Values in the weather window",
        ci: { temperature: "Outdoor temperature", condition: "Condition (symbol)", humidity: "Humidity", abs_humidity: "Absolute humidity (g/m³)", wind: "Wind", rain: "Rain", apparent: "Feels like", pressure: "Pressure", sun: "Sun (rise/set)", datetime: "Date/time" },
        sec_motion: "Animation", motion_level: "Animation level", ml: { auto: "Auto (by device)", off: "Off", minimal: "Minimal (saves energy)", normal: "Normal", intense: "Intense" },
        motion_parts: "What moves", mp: { wind: "Wind", weather: "Weather effects", light: "Light & sun", ambient: "Atmosphere (rooms, haze)" },
        ri: { name: "Room name", temperature: "Temperature", humidity: "Relative humidity", absolute_humidity: "Absolute humidity", action: "Recommendation", co2: "CO₂", mould: "Mould risk" } };
    const c = this._config, plan = this._plan, chosen = c.room_info == null ? [] : list(c.room_info), visible = list(c.floors_visible), info = c.weather_info == null ? W.DEFAULT_WEATHER_INFO : list(c.weather_info);
    const chip = W.chipFor(c), details = W.detailsFor(c), parts = M.chosenParts(c);
    const box = (k, value, label, on) => `<label style="display:inline-flex;gap:6px;align-items:center;min-height:32px;margin-right:12px"><input type="checkbox" data-list="${k}" value="${esc(value)}"${on ? " checked" : ""}> ${esc(label)}</label>`;
    const floorName = f => f.name || f.level_key || f.id;
    const floors = plan && plan.floors.length ? plan.floors : null;
    const overrides = c.room_overrides && typeof c.room_overrides === "object" ? c.room_overrides : {};
    const perRoom = plan ? plan.rooms.map(r => {
      const own = overrides[r.room_key] != null, sel = own ? list(overrides[r.room_key]) : [];
      return `<details style="margin:4px 0"${own ? " open" : ""}><summary>${esc(plan.names[r.room_key] || r.room_key)} · ${own ? L.own : L.same}</summary><div>
        <label><input type="checkbox" data-own="${esc(r.room_key)}"${own ? " checked" : ""}> ${L.own}</label><div>${ROOM_INFO.map(k => box(`ov:${r.room_key}`, k, L.ri[k], sel.includes(k))).join("")}</div></div></details>`;
    }).join("") : "";
    // 0.26.7.0 (order "Logikprüfung, Innentüren und UX", point 4): seven groups with a short explanation each – every key,
    // stored value and default as before; a group's open state survives a redraw, and nothing typed is lost by opening another
    const S = de
      ? { general: ["Allgemein", "Titel, Integration und was die Karte beim Öffnen zeigt."], floors: ["Etagen & Navigation", "Welche Etagen die Karte zeigt und wie sie zwischen ihnen wechselt."],
        rooms: ["Rauminformationen", "Was in jedem Raum des Grundrisses steht – für alle Räume oder einzeln."], wx: ["Wetteranzeige", "Woher das Wetter kommt und was oben rechts direkt sichtbar ist."],
        wxwin: ["Wetterfenster", "Was das Wetterfenster nach einem Tipp auf die Wetteranzeige enthält."], motion: ["Animation & Darstellung", "Wie lebendig die Karte ist und wie viel Platz sie nutzt."],
        adv: ["Erweitert", "Ältere Zuordnungen und technische Einstellungen – meist nicht nötig."], design: ["Design & Farben", "Wie Rahmen und Fenster dieser Karte aussehen – passend zu deinem Dashboard."], entry_hint: "Normalerweise leer lassen: FreshAirIQ wird nur einmal eingerichtet.",
        lock_hint: "Nur bei automatischem Fokus oder Hinweis wirksam.", details_hint: "Gilt für die erweiterte Wetterübersicht.", stale: "Nicht mehr im Grundriss", stale_fix: "Veraltete Einträge entfernen",
        weather_sensors_hint: "Ältere Einstellung: eigene Sensoren statt der Wetteranzeige.", floor_hint: "Ältere Einstellung für eine feste Etage – neuer: „Sichtbare Etagen“." }
      : { general: ["General", "Title, integration and what the card shows when it opens."], floors: ["Floors & navigation", "Which floors the card shows and how it moves between them."],
        rooms: ["Room information", "What each room on the plan shows – for all rooms or one by one."], wx: ["Weather display", "Where the weather comes from and what is shown at the top right."],
        wxwin: ["Weather window", "What the weather window holds after a tap on the weather display."], motion: ["Animation & look", "How lively the card is and how it uses its space."],
        adv: ["Advanced", "Older assignments and technical settings – rarely needed."], design: ["Design & colours", "How the frame and the windows of this card look – to match your dashboard."], entry_hint: "Usually leave empty: FreshAirIQ is set up only once.",
        lock_hint: "Only used with automatic focus or hints.", details_hint: "Used by the weather overview.", stale: "No longer on the plan", stale_fix: "Remove outdated entries",
        weather_sensors_hint: "Older setting: own sensors instead of the weather display.", floor_hint: "Older setting for one fixed floor – newer: \"Floors shown\"." };
    const open = this._open || (this._open = new Set(["general"]));
    const group = (id, body) => `<details data-group="${id}" style="border:1px solid var(--divider-color,#ccc);border-radius:10px;padding:6px 10px"${open.has(id) ? " open" : ""}>
      <summary style="cursor:pointer;min-height:36px;display:flex;flex-direction:column;justify-content:center"><b>${esc(S[id][0])}</b><span style="font-size:.85em;opacity:.75">${esc(S[id][1])}</span></summary>
      <div style="display:grid;gap:10px;padding:8px 0 4px">${body}</div></details>`;
    const boxes = html => `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:2px 8px">${html}</div>`;
    const note = text => `<span style="font-size:.85em;opacity:.7">${esc(text)}</span>`;
    // the stored floor/room choices still on the plan of the (possibly changed) integration entry
    const knownFloors = new Set((plan ? plan.floors : []).map(f => f.id)), knownRooms = new Set((plan ? plan.rooms : []).map(r => r.room_key));
    const staleFloors = plan ? [...visible, ...(c.default_floor ? [c.default_floor] : [])].filter(f => !knownFloors.has(f)) : [];
    const staleRooms = plan ? Object.keys(overrides).filter(k => !knownRooms.has(k)) : [];
    const stale = staleFloors.length || staleRooms.length ? `<div style="color:var(--warning-color,#b26b00)">${esc(S.stale)}: ${esc([...new Set([...staleFloors, ...staleRooms])].join(", "))} <button type="button" data-stale="1">${esc(S.stale_fix)}</button></div>` : "";
    const lockHidden = (c.auto_focus || "hint") === "off" ? " hidden" : "";
    const detailsHidden = info.includes("overview") ? "" : " hidden";
    this.innerHTML = `<div style="display:grid;gap:10px;padding:8px 0">
      ${group("general", `<label>${L.title}<br><input data-k="title" value="${esc(c.title || "")}" style="width:100%"></label>
        <label>${L.entry}<br><input data-k="entry_id" value="${esc(c.entry_id || "")}" style="width:100%"><br>${note(S.entry_hint)}</label>
        <label>${L.layer}<br><select data-k="layer">${LAYERS.map(l => `<option value="${l}"${(c.layer || "action") === l ? " selected" : ""}>${esc(T[de ? "de" : "en"][`layer_${l}`])}</option>`).join("")}</select></label>`)}
      ${group("floors", `${floors ? `<div>${L.floors_visible}</div>${boxes(floors.map(f => box("floors_visible", f.id, floorName(f), visible.includes(f.id))).join(""))}
        <label>${L.default_floor}<br><select data-k="default_floor"><option value="">${L.default_none}</option>${floors.map(f => `<option value="${esc(f.id)}"${c.default_floor === f.id ? " selected" : ""}>${esc(floorName(f))}</option>`).join("")}</select></label>`
        : `<label>${L.floors_visible}<br><input data-k="floors_visible" value="${esc(visible.join(", "))}" placeholder="ground_floor, upper_floor" style="width:100%"></label>
        <label>${L.default_floor}<br><input data-k="default_floor" value="${esc(c.default_floor || "")}" placeholder="ground_floor" style="width:100%"></label>`}
        ${stale}
        <label>${L.focus}<br><select data-k="auto_focus">${FOCUS_MODES.map(m => `<option value="${m}"${(c.auto_focus || "hint") === m ? " selected" : ""}>${L[m]}</option>`).join("")}</select></label>
        <label data-when="auto_focus"${lockHidden}>${L.lock}<br><input data-k="manual_lock_min" type="number" min="1" max="240" value="${esc(c.manual_lock_min || 10)}"><br>${note(S.lock_hint)}</label>
        <label><input data-k="rooms_button" type="checkbox"${c.rooms_button ? " checked" : ""}> ${L.rooms_button}</label>`)}
      ${group("rooms", `<div>${L.room_info}</div>${boxes(ROOM_INFO.map(k => box("room_info", k, L.ri[k], chosen.includes(k))).join(""))}
        ${perRoom ? `<div style="margin-top:6px">${L.per_room}</div>${perRoom}` : ""}`)}
      ${group("wx", `<label>${L.weather_entity}<br><input data-k="weather_entity" value="${esc(c.weather_entity || "")}" placeholder="weather.home" list="faiq-weather-entities" style="width:100%"></label>
        <datalist id="faiq-weather-entities">${Object.keys((this._hass && this._hass.states) || {}).filter(e => e.startsWith("weather.")).map(e => `<option value="${esc(e)}">`).join("")}</datalist>
        <div>${L.weather_chip}</div>${boxes(W.CHIP_ITEMS.map(k => box("weather_chip", k, L.ci[k], chip.includes(k))).join(""))}`)}
      ${group("wxwin", `<div>${L.weather_views}</div>${boxes(W.WEATHER_INFO.filter(k => !W.WEATHER_DETAILS.includes(k)).map(k => box("weather_info", k, L.wi[k], info.includes(k))).join(""))}
        <div data-when="overview"${detailsHidden}><div>${L.weather_details}</div>${note(S.details_hint)}${boxes(W.WEATHER_DETAILS.map(k => box("weather_details", k, L.wi[k], details.includes(k))).join(""))}</div>`)}
      ${group("motion", `<label>${L.motion_level}<br><select data-k="animation_level">${["auto", "off", "minimal", "normal", "intense"].map(v => `<option value="${v}"${M.chosenLevel(c) === v ? " selected" : ""}>${L.ml[v]}</option>`).join("")}</select></label>
        <div>${L.motion_parts}</div>${boxes(M.MOTION_PARTS.map(k => box("animation_parts", k, L.mp[k], parts.includes(k))).join(""))}
        <label>${L.effects}<br><select data-k="weather_effects">${W.EFFECT_LEVELS.map(v => `<option value="${v}"${(c.weather_effects || "dynamic") === v ? " selected" : ""}>${L.fx[v]}</option>`).join("")}</select></label>
        <label><input data-k="animation" type="checkbox"${c.animation === false ? "" : " checked"}> ${L.anim}</label>
        <label>${L.layout}<br><select data-k="layout">${W.LAYOUTS.map(v => `<option value="${v}"${(c.layout || "auto") === v ? " selected" : ""}>${L.lay[v]}</option>`).join("")}</select></label>`)}
      ${group("design", this._designGroup(c, de, note))}
      ${group("adv", `<label>${L.weather}<br><input data-k="weather_sensors" value="${esc(Array.isArray(c.weather_sensors) ? c.weather_sensors.join(", ") : c.weather_sensors || "")}" placeholder="sensor.aussen_temperatur, sensor.aussen_feuchte" style="width:100%"><br>${note(S.weather_sensors_hint)}</label>
        <label>${L.floor}<br><input data-k="floor" value="${esc(c.floor || "")}" placeholder="ground_floor" style="width:100%"><br>${note(S.floor_hint)}</label>`)}</div>`;
    this.querySelectorAll("details[data-group]").forEach(d => d.addEventListener("toggle", () => { if (d.open) open.add(d.dataset.group); else open.delete(d.dataset.group); }));
    const staleButton = this.querySelector("[data-stale]");
    if (staleButton) staleButton.addEventListener("click", () => {
      const next = Object.assign({}, this._config);
      const keepFloors = list(next.floors_visible).filter(f => knownFloors.has(f));
      if (keepFloors.length) next.floors_visible = keepFloors; else delete next.floors_visible;
      if (next.default_floor && !knownFloors.has(next.default_floor)) delete next.default_floor;
      if (next.room_overrides) { const ov = Object.fromEntries(Object.entries(next.room_overrides).filter(([k]) => knownRooms.has(k))); if (Object.keys(ov).length) next.room_overrides = ov; else delete next.room_overrides; }
      this._emit(next); this._render();
    });
    this.querySelectorAll("[data-k]").forEach(el => el.addEventListener("change", () => {
      const k = el.dataset.k;
      const value = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
      const next = Object.assign({}, this._config);
      if (value === "" || value == null || (k === "rooms_button" && value === false) || (k === "design" && value === "freshairiq") || (k === "design_text" && value === "auto")) delete next[k]; else next[k] = value;
      // 0.26.7.0(2): the level replaces the older on/off switch – "off" is said by the level, the switch stays as it was
      if (k === "animation_level") { if (value === "auto") delete next.animation_level; if (value !== "off" && next.animation === false) delete next.animation; }
      this._emit(next);
      // another integration entry: its plan decides which stored floors and rooms are still valid
      if (k === "entry_id") { this._plan = undefined; this._loadPlan(); }
      if (k === "auto_focus") { const lock = this.querySelector('[data-when="auto_focus"]'); if (lock) lock.hidden = value === "off"; }
      if (k.startsWith("design")) this._render();   // the custom fields and the readability notes follow the choice
    }));
    this.querySelectorAll("[data-design-reset]").forEach(el => el.addEventListener("click", () => { const next = Object.assign({}, this._config); delete next[el.dataset.designReset]; this._emit(next); this._render(); }));
    const glass = this.querySelector("[data-design-glass]");
    if (glass) glass.addEventListener("change", () => { const next = Object.assign({}, this._config); if (glass.checked) next.design_background = "transparent"; else delete next.design_background; this._emit(next); this._render(); });
    // a list option is written only once something differs from "nothing chosen" (older cards keep their look)
    this.querySelectorAll("[data-list]").forEach(el => el.addEventListener("change", () => {
      const k = el.dataset.list, next = Object.assign({}, this._config);
      const values = [...this.querySelectorAll(`[data-list="${k}"]`)].filter(x => x.checked).map(x => x.value);
      if (k.startsWith("ov:")) {
        const key = k.slice(3), ov = Object.assign({}, next.room_overrides || {});
        ov[key] = values; next.room_overrides = ov;
      } else if (k === "weather_info") {
        // 0.26.7.0(2): the parts only; the single values are their own choice (weather_details), so switching parts never
        // brings a value back – an older card's values listed here move over once
        const legacy = list(next.weather_info).filter(x => W.WEATHER_DETAILS.includes(x));
        if (legacy.length && next.weather_details == null) next.weather_details = legacy;
        next.weather_info = values;
        const more = this.querySelector('[data-when="overview"]'); if (more) more.hidden = !values.includes("overview");
      } else if (k === "weather_chip" || k === "weather_details" || k === "animation_parts") {
        next[k] = values;   // an explicit choice, also when empty: nothing switched off comes back by itself
        if (k === "weather_details" && next.weather_info != null) next.weather_info = list(next.weather_info).filter(x => !W.WEATHER_DETAILS.includes(x));
      }
      else if (values.length) next[k] = values; else delete next[k];
      this._emit(next);
    }));
    this.querySelectorAll("[data-own]").forEach(el => el.addEventListener("change", () => {
      const next = Object.assign({}, this._config), ov = Object.assign({}, next.room_overrides || {});
      if (el.checked) ov[el.dataset.own] = next.room_info == null ? ROOM_INFO.slice() : list(next.room_info); else delete ov[el.dataset.own];
      if (Object.keys(ov).length) next.room_overrides = ov; else delete next.room_overrides;
      this._emit(next); this._render();
    }));
  }
}

if (!customElements.get("freshairiq-house-card-impl")) customElements.define("freshairiq-house-card-impl", FreshAirIQHouseCard);
if (!customElements.get("freshairiq-house-card-editor-impl")) customElements.define("freshairiq-house-card-editor-impl", FreshAirIQHouseCardEditor);
