const FAIQ_VERSION = "0.26.6.0";
// FreshAirIQ house map card (optional, custom:freshairiq-house-card).
// Shows the canonical room decisions of FreshAirIQ on a free floor plan, the
// wind and a clearly marked air-path *hypothesis*. It never decides anything
// itself: actions come from the same room payload as the dashboard, pushes and
// automation events. Layout: freshairiq/house_map/*; rooms: freshairiq/dashboard/subscribe.

// the query of this module's own URL (version + build revision b=) reaches every module it imports
const Q = new URL(import.meta.url).search || `?v=${FAIQ_VERSION}`;
const G = await import(new URL(`./freshairiq-house-geometry.js${Q}`, import.meta.url).href);
const V = await import(new URL(`./freshairiq-house-view.js${Q}`, import.meta.url).href);
const A = await import(new URL(`./freshairiq-house-atmos.js${Q}`, import.meta.url).href);  // 0.26.6.0(7): sky, weather, climate, air
const F = await import(new URL(`./freshairiq-house-flow.js${Q}`, import.meta.url).href);  // order 8: the modelled wind field
const FL = await import(new URL(`./freshairiq-house-flowlayer.js${Q}`, import.meta.url).href);  // order 8: the visible air (canvas)
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
      monitor_open: "Daueröffnung überwachen", unknown: "Unbekannt" },
    critical: "Kritisch", no_room_data: "keine Raumdaten",
    kpi_wind: "Wind", kpi_forecast: "Prognose", kpi_night: "Nachtprognose", kpi_night_sub: "Feuchte bis zum Morgen", kpi_outdoor: "Draußen",
    tile_temp: "Temperatur", tile_rh: "Luftfeuchte", tile_next5: "Nächste 5 min", openings_title: "Fenster & Türen",
    tile_fan: "Ablüfter", fan_left: "Nachlauf noch {m} min", fan_limit: "spätestens aus {t}",
    streams_note: "Windströme schematisch – Tempo nach Windstärke, keine Messung",
    mould_low: "Schimmelrisiko gering", mould_slightly_elevated: "leicht erhöht", mould_elevated: "erhöht", mould_high: "hoch", mould_very_high: "sehr hoch",
    weather_corner: "Wetter vor Ort", outdoor_temp: "Außentemperatur", outdoor_rh: "Außenluftfeuchte",
    moist_chip: "Entfernbare Feuchte und Lüftungszeit wie auf der FreshAirIQ-Karte – antippen für die Erklärung", moist_title: "Entfernbare Feuchte",
    moist_now: "Jetzt entfernbar", moist_now_sub: "in der empfohlenen Lüftungszeit – derselbe Wert wie auf der FreshAirIQ-Karte",
    moist_so_far: "Bisher entfernt", moist_so_far_sub: "seit Beginn der laufenden Lüftung",
    moist_duration: "Empfohlene Lüftungszeit", moist_remaining: "Restzeit", moist_confidence: "Prognose-Sicherheit", min_short: "Min.", about: "ca.",
    moist_in: "in", moist_left: "noch", moist_possible: "möglich", moist_so_far_chip: "bisher",
    moist_over: "über Ziel", moist_over_tile: "Über Ziel", moist_added: "eingetragen", moist_would_add: "würde eingetragen",
    moist_added_sub: "seit Beginn der Lüftung ist Feuchte hinzugekommen – wie auf der FreshAirIQ-Karte", moist_would_add_sub: "die Außenluft ist feuchter – Lüften würde Feuchte eintragen",
    moist_none: "Zurzeit nichts zu entfernen – die Außenluft ist nicht trockener als die Raumluft oder FreshAirIQ hat noch keinen Wert berechnet.",
    moist_wait: "FreshAirIQ rät gerade abzuwarten – die Menge wäre möglich, eine Lüftungszeit wird deshalb nicht angezeigt.",
    moist_explain: "Der Wert ist FreshAirIQs „Jetzt entfernbar“ (Sensor „Entfernbare Feuchte“) – genau wie auf der FreshAirIQ-Karte: die Wassermenge, die alle berechneten Räume des ganzen Hauses (alle Etagen, jeder Raum einmal, nur mit gültigen Messwerten) mit dem gelernten Luftaustausch in der empfohlenen Lüftungszeit voraussichtlich abgeben. Die Zeit ist diese empfohlene Lüftungszeit (aus Außentemperatur und Feuchteunterschied, begrenzt durch deine Einstellungen) – die Menge gilt also für genau diese Zeit, nicht für ein vollständiges Austrocknen. Während einer Lüftung zeigen beide Karten die bisher entfernte Menge und die Restzeit. Die Strömungsbilder sind eine modellierte Darstellung – gemessen sind Temperatur und Feuchte.",
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
      monitor_open: "Long opening monitored", unknown: "Unknown" },
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
const FOCUS_ATTRS = ["data-floor", "data-layer", "data-room", "data-opening", "data-path", "data-edit", "data-resume", "data-close-detail"];
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

// 0.26.6.0(7): the real width of a label text in px (canvas, the card's font stack); an estimate without a canvas
let measureCtx = null;
export const textWidth = (text, size, weight = 700) => {
  try {
    if (!measureCtx) measureCtx = document.createElement("canvas").getContext("2d");
    measureCtx.font = `${weight} ${size}px Nunito, "Baloo 2", ui-rounded, "SF Pro Rounded", "Segoe UI", system-ui, sans-serif`;
    return measureCtx.measureText(String(text)).width;
  } catch (_) { return String(text).length * size * 0.6; }
};
// 0.26.6.0(7): a short form of a room name for small rooms – its last word when that is short ("Gäste-WC" → "WC",
// "Kinderzimmer Nord" → "Nord"), else the name itself (shortened with an ellipsis where needed)
export const shortName = name => { const last = String(name).trim().split(/[\s\-–/]+/).filter(Boolean).pop() || String(name); return last.length <= 5 && last !== String(name).trim() ? last : String(name); };
// 0.26.6.0(9): a compound room name in two rows – at a space or hyphen, else before a common German room word
// ("Arbeitszimmer" → "Arbeits-" / "zimmer"); null when it cannot be split sensibly
const ROOM_WORDS = ["zimmer", "küche", "kueche", "raum", "keller", "kammer", "diele", "garage", "stube", "bad", "room", "kitchen"];
export const splitName = name => {
  const n = String(name).trim(), at = n.search(/[\s\-–/]/);
  if (at > 1 && at < n.length - 2) return [n.slice(0, n[at] === " " ? at : at + 1), n.slice(at + 1).trim()];
  const low = n.toLowerCase(), word = ROOM_WORDS.find(w => low.endsWith(w) && n.length - w.length >= 3);
  return word ? [`${n.slice(0, n.length - word.length)}-`, n.slice(n.length - word.length)] : null;
};
export const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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
  const tone = room.data_quality && room.data_quality !== "ok" ? "sensor" : TONE[actionCode(room)] || "wait";
  if (tone === "ok" && mouldWarning(room)) return "wait";
  return tone;
};
// 0.26.6.0(2): the action a floor needs, for its pulsing button – "critical" before "close" before "act" (air now).
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
    this._onDown = ev => {
      this._gestureSeen = Date.now();
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
    this._onVisibility = () => { if (document.hidden) { this.setAttribute("data-paused", ""); this._onUp(null); } else this.removeAttribute("data-paused"); };
  }
  static getConfigElement() { return document.createElement("freshairiq-house-card-editor"); }
  static getStubConfig() { return { auto_focus: "hint" }; }
  setConfig(config) {
    if (config && config.auto_focus && !FOCUS_MODES.includes(config.auto_focus)) throw new Error("auto_focus: off | hint | auto");
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
    this._windSync();  // hotfix F04: "animation: false" stops a running wind loop at once
    this.toggleAttribute("data-still", this._config.animation === false);  // no breathing rooms either
  }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._editing) this._editing.hass = hass; // the editor keeps its own state; no re-render on hass
    // re-audit F01: a new Home Assistant connection – subscribe there once and release the old ones
    const conn = hass && hass.connection;
    if (this._subConn && conn !== this._subConn) { this._stop(); this._start(); return; }
    if (first || (!this._subs.length && !this._failed)) this._start();
    // 0.26.6.0(7): day, twilight and night follow sun.sun – redraw when the phase changes, not on every state
    // 0.26.6.0(10): also when the sun moves on within the same phase – in 2° steps of azimuth and elevation (about
    // every eight minutes), not on every state change of Home Assistant
    const sunNow = A.skyState(null, hass && hass.states && hass.states["sun.sun"]);
    const sunKey = `${sunNow.phase}|${sunNow.azimuth == null ? "-" : Math.round(sunNow.azimuth / 2)}|${sunNow.elevation == null ? "-" : Math.round(sunNow.elevation / 2)}`;
    if (!first && sunKey !== this._sunKey && this._layoutInfo) this._queue();
    this._sunKey = sunKey; this._sunPhase = sunNow.phase;
  }
  get hass() { return this._hass; }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: 8, min_rows: 4 }; }
  connectedCallback() {
    document.addEventListener("visibilitychange", this._onVisibility);
    for (const type of ["touchstart", "pointerdown"]) this.addEventListener(type, this._onDown, { passive: true });
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
    if (this._hass && !this._subs.length) this._start();
    this._queue();
  }
  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisibility);
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
    const want = String(this._config.floor || "").trim().toLowerCase();
    const hit = want && floors.find(f => [f.id, f.level_key, f.name].some(v => String(v || "").toLowerCase() === want));
    return (hit || floors[0]).id;
  }
  _restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(this._storeKey()) || "{}");
      if (saved.floor) this._floor = saved.floor;
      if (saved.lockUntil > Date.now()) this._lockUntil = saved.lockUntil;
      if (LAYERS.includes(saved.layer)) this._layer = saved.layer;
    } catch (_) { /* private mode */ }
  }
  _persist() {
    try { localStorage.setItem(this._storeKey(), JSON.stringify({ floor: this._floor, lockUntil: this._lockUntil, layer: this._layer })); } catch (_) { /* ignore */ }
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
    return (layout.floors || []).filter(f => used.has(f.id)).sort((a, b) => (a.order || 0) - (b.order || 0));
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
  // 0.26.6.0(2): the floors as buttons at the bottom left of the plan – every floor but the one shown (and
  // "All floors"); a floor that needs an action (air now, close, critical) pulses gently, statically with
  // reduced motion. The choice is kept like before (_chooseFloor: manual lock, stored).
  _floorButtons(layout, floors) {
    if (floors.length < 2) return "";
    const btn = (id, label, act) => `<button class="floorbtn${act ? ` pulse p-${act}` : ""}" data-floor="${esc(id)}"${act ? ` data-action="${act}" aria-description="${esc(this._t(`need_${act}`))}"` : ""}>${label}</button>`;
    // UI hotfix: no "All floors" – several floors at once = the card several times on the dashboard
    const others = floors.filter(f => f.id !== this._floor).map(f => btn(f.id, this._floorName(f), floorAction(layout, this._rooms, f.id)));
    return `<div class="floors" role="group" aria-label="${esc(this._t("floors_title"))}">${others.join("")}</div>`;
  }
  // 0.26.6.0(7): outdoor temperature and humidity from FreshAirIQ, or the card's own sensors (weather_sensors:
  // list or comma-separated entity ids) – each with its unit; unknown values are left out, nothing is invented
  _weatherChip() {
    const p = this._payload || {}, states = (this._hass && this._hass.states) || {}, parts = [];
    const fmt = v => (Number.isFinite(v) ? (Math.abs(v) >= 100 ? Math.round(v) : v.toFixed(1)).toString().replace(".", this._lang() === "de" ? "," : ".") : null);
    const own = (Array.isArray(this._config.weather_sensors) ? this._config.weather_sensors : String(this._config.weather_sensors || "").split(","))
      .map(x => String(x).trim()).filter(Boolean);
    if (own.length) {
      for (const id of own) {
        const st = states[id], a = (st && st.attributes) || {}, v = fmt(known(st && st.state));
        if (v == null) continue;
        const icon = a.device_class === "temperature" ? "🌡️" : a.device_class === "humidity" ? "💧" : "•";
        const shown = a.unit_of_measurement === "%" ? String(Math.round(known(st.state))) : v;
        parts.push([`${icon} ${shown}${a.unit_of_measurement ? ` ${a.unit_of_measurement}` : ""}`, a.friendly_name || id]);
      }
    } else {
      const t = fmt(known(p.outdoor_temperature ?? (p.weather_now || {}).outdoor_temperature)), h = known(p.outdoor_humidity), rh = Number.isFinite(h) ? String(Math.round(h)) : null;
      if (t != null) parts.push([`🌡️ ${t} °C`, this._t("outdoor_temp")]);
      if (rh != null) parts.push([`💧 ${rh} %`, this._t("outdoor_rh")]);
    }
    if (!parts.length) return "";
    return `<div class="weather" role="group" aria-label="${esc(this._t("weather_corner"))}">${parts.map(([text, title]) => `<span title="${esc(title)}">${esc(text)}</span>`).join("")}</div>`;
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
  // Hotfix 0.26.6.0: the stable mapping of the FreshAirIQ dashboard card (``_guestEntity`` in freshairiq-card.js) –
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
    return `<h4>${esc(t("guests"))}</h4><div class="row">${row("adults")}${row("children")}</div>${missing ? `<div class="legend">${esc(t("guests_readonly"))}</div>` : ""}`;
  }
  _setGuests(kind, delta) {
    const entity = this._guestEntity(kind), p = this._payload || {};
    if (!entity || !this._hass) return;
    const shown = Number(((this._hass.states || {})[entity] || {}).state);
    const current = Number.isFinite(shown) ? shown : Number(p[`guest_${kind}`] || 0);
    const value = Math.max(0, Math.min(20, Math.round(current + delta)));  // hotfix 0.26.6.0: the setting's range 0–20
    if (value === current) return;  // at a limit: nothing to send
    this._hass.callService("number", "set_value", { entity_id: entity, value });
  }
  _layerTabs() {
    return `<div class="row" role="toolbar" aria-label="${esc(this._t("layers"))}">${LAYERS.map(l => `<button class="small" data-layer="${l}" aria-pressed="${l === this._layer}">${esc(this._t(`layer_${l}`))}</button>`).join("")}</div>`;
  }
  // Hero: what matters for the whole house – recommendation, wind, forecast for the set horizon, night, outdoors.
  _hero(layout) {
    const p = this._payload || {}, t = k => this._t(k), lang = this._lang();
    const rec = p.intelligent_recommendation && typeof p.intelligent_recommendation === "object" ? p.intelligent_recommendation : {};
    const recTone = heroTone(rec);
    const north = layout ? Number(layout.building.north_deg || 0) : 0;
    const w = this._house && this._house.wind;
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
        ${kpi(V.windDial(this._windSmooth, north, w && w.speed_ms), t("kpi_wind"), windVal, windSub)}
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
    const action = `${V.TONE_EMOJI[tone] || ""} ${esc(T[lang].actions[actionCode(room)] || T[lang].actions.unknown)}`;  // canonical action word
    const num = (v, d = 1) => (v == null || !Number.isFinite(Number(v)) ? "–" : Number(v).toFixed(d));
    const climate = A.roomClimate(room), rise = climate.rising ? " ↑" : climate.falling ? " ↓" : "";  // measured trend ≥ 3 %/h up or down
    const extra = {
      temperature: `${num(room.temperature)} °C${room.comfort_target_c != null ? ` → ${num(room.comfort_target_c)} °C` : ""}`,
      humidity: `${num(room.humidity, 0)} %${rise} · ${num(room.absolute_humidity)} g/m³`,
      co2: room.co2 != null ? `${Math.round(room.co2)} ppm CO₂` : t("not_measured"),
      quality: `${room.data_quality === "ok" ? t("quality_ok") : t("quality_bad")} · ${t("learning")} ${room.learning_samples ?? "–"}`,
    }[this._layer] || `${num(room.temperature)} °C · ${num(room.humidity, 0)} %${rise}`;
    return { name, action, extra, tone };
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
    const S = p => `${G.round3(p[0])},${G.round3(-p[1])}`;
    const north = Number(layout.building.north_deg || 0);
    const ids = new Set(rooms.map(r => r.id));
    const air = this._house && this._house.airflow;
    const opState = air ? air.openings : {};
    const w = this._house && this._house.wind;
    const dur = V.streamSeconds(w && w.speed_ms);
    // 0.26.6.0(7): no technical grid – a sky that follows the real weather (FreshAirIQ weather summary, sun.sun)
    const frame = { minX: vb[0], minY: -(vb[1] + vb[3]), maxX: vb[0] + vb[2], maxY: -vb[1] };
    const sky = { ...A.skyState(this._payload && this._payload.weather_now, this._hass && this._hass.states && this._hass.states["sun.sun"]), directional: layout.building.north_confirmed !== false };
    // order 9: the wind's character from the real weather (speed, measured gust, HA condition, rain/thunder, sun.sun)
    const wn = (this._payload && this._payload.weather_now) || {};
    const mood = F.windMood({ speed: Number(w && w.speed_ms) || 0, gust: w && w.gust_ms, condition: wn.condition, raining: wn.raining === true, thunder: wn.thunder === true, phase: sky.phase });
    this._windMood = mood.name;
    let out = `<svg class="plan" data-mood="${esc(this._windMood || "neutral")}" viewBox="${vb.map(G.round3).join(" ")}" role="group" aria-label="${esc(this._t("title"))}" style="--dash:${px(10)} ${px(8)};--dot:${px(3)} ${px(7)};--dashlen:${px(54)};--dur:${G.round3(dur)}s">`;
    const marker = (id, color) => `<marker id="${id}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="${color}" stroke="${V.BRAND.ink}" stroke-width="1"/></marker>`;
    out += `<defs>${marker("ah", V.BRAND.lime)}${marker("ahx", V.BRAND.orange)}${marker("ahc", V.BRAND.cyan)}
      <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${px(2.2)}" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="comic" x="-10%" y="-10%" width="130%" height="130%"><feDropShadow dx="${px(5)}" dy="${px(5)}" stdDeviation="0" flood-color="${V.BRAND.ink}" flood-opacity="1"/></filter>
      ${V.roomDefs(px)}
      ${A.skyDefs(sky, px)}${A.climateDefs(px)}${A.weatherMask("wx-out", frame, rooms, px)}
      ${rooms.map(r => `<clipPath id="rc-${esc(r.id)}"><polygon points="${r.polygon.map(S).join(" ")}"/></clipPath>`).join("")}</defs>
      ${A.skyBackground(vb)}${A.weatherSvg(sky, frame, w, north, px, "wx-out")}`;
    // wind streams behind the house
    const openings = (layout.openings || []).map(o => ({ ...o, ...(opState[o.id] || {}) }));
    // 0.26.6: the air runs only through openings and connections between rooms and streams out of the outlet
    const pathPts = (air && air.paths ? air.paths : []).map(p => { const r = G.airRoute(layout, p, { outside: span * 0.14, strict: true }); return { ...p, points: r.points, exits: r.exits }; });
    const streams = w && w.available && this._windSmooth != null
      ? V.windStreams({ rooms, openings, fromDeg: this._windSmooth, northDeg: north, G, paths: pathPts,
        frame }) : [];
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
    this._flowScene = { field: w && w.available && this._windSmooth != null ? F.buildField({ rooms, G, wind: { ...w, from_deg: this._windSmooth }, northDeg: north, mood }) : null,
      vb, routes: flowRoutes, rooms, key: `${mood.name}|${floorId}|${Math.round((this._windSmooth || 0) / 5)}|${F.strengthClass(Number(w && w.speed_ms) || 0)}|${rooms.length}|${G.round3(span)}` };
    let inflow = "";  // air coming in is drawn over the rooms, the rest behind the house
    const waves = this._wavesNext || (this._wavesNext = []);
    const COLORS = { mid: "#bfe9ff", hi: "#e6f7ff", lo: "#7cc8f0" };
    streams.forEach(s => {
      const frame = V.waveFrame(V.streamLine(s), px(6));
      if (frame.samples.length < 2) return;
      const first = frame.samples[0].p, last = frame.samples[frame.samples.length - 1].p;
      const base = s.kind === "inflow" ? (s.tilted ? 5 : 7) : 4.5;
      let line = "";
      V.WAVE_STRANDS.forEach((st, j) => {
        const index = waves.length;
        const geo = { amp: px(6.5) * st.amp * (s.kind === "pass" ? 0.8 : 1), wavelength: px(175) * st.wave, shift: st.shift + index * 0.37 };
        waves.push({ frame, geo });
        const gid = `wg${index}`, color = s.kind === "inflow" && j === 0 ? V.BRAND.white : COLORS[st.cls];
        const endOpacity = s.kind === "inflow" && !s.exits ? 1 : 0;  // air streaming out fades outside the house
        line += `<linearGradient id="${gid}" gradientUnits="userSpaceOnUse" x1="${G.round3(first[0])}" y1="${G.round3(-first[1])}" x2="${G.round3(last[0])}" y2="${G.round3(-last[1])}"><stop offset="0" stop-color="${color}" stop-opacity="0"/><stop offset=".2" stop-color="${color}"/><stop offset=".8" stop-color="${color}"/><stop offset="1" stop-color="${color}" stop-opacity="${endOpacity}"/></linearGradient>`;
        const cls = `${j === 0 ? `stream ${s.kind} ` : ""}wave ${st.cls} k-${s.kind}${s.tilted ? " tilted" : ""}${s.exits ? " exits" : ""}`;
        line += `<path class="${cls}" data-wave="${index}" d="${V.wavePath(frame, geo, this._windPhase || 0)}" stroke="url(#${gid})" stroke-width="${px(base * st.width)}"${s.kind === "inflow" && j === 0 && !s.exits ? ' marker-end="url(#ahc)"' : ""}/>`;
      });
      // order 8: the fine particles of the incoming air are drawn on the canvas air layer (freshairiq-house-flowlayer.js)
      if (s.kind === "inflow") inflow += line; else out += line;
    });
    // 0.26.6.0(2): one comic shadow under the whole house (not one per room – that drew every shared wall thick);
    // the rooms have no outline of their own, the walls come from G.wallSegments exactly as in the editor
    // 0.26.6.0(7): a soft shadow that lifts the house off the ground instead of the hard comic offset
    out += `<g class="house-shadow" transform="translate(${px(3)} ${px(7)})" fill="#000814" fill-opacity=".5" filter="url(#soft)">${rooms.map(r => `<polygon points="${r.polygon.map(S).join(" ")}"/>`).join("")}</g>`;
    for (const r of rooms) {
      const live = this._rooms[r.room_key];
      const lines = this._roomLines(live, r);
      const tone = V.ROOM_TONES[lines.tone] ? lines.tone : "wait", pts = r.polygon.map(S).join(" ");
      out += `<polygon class="room t-${lines.tone}${this._selected && this._selected.id === r.id ? " sel" : ""}" fill="url(#rf-${tone})" stroke-width="${px(3.5)}" tabindex="0" role="button" data-room="${esc(r.id)}" aria-label="${`${lines.name}, ${lines.action}, ${lines.extra}`.replace(/<[^>]+>/g, "")}" points="${pts}"/>`;
      // 0.26.6.0(6): a soft inner rim where something is to do (clipped to the room), a faint hatch when critical
      if (V.ROOM_TONES[tone].rim) out += `<polygon class="rim r-${tone}" clip-path="url(#rc-${esc(r.id)})" points="${pts}" stroke="${V.ROOM_TONES[tone].rim}" stroke-width="${px(9)}" stroke-opacity=".55"/>`;
      if (tone === "critical") out += `<polygon class="hatch" fill="url(#rf-hatch)" points="${pts}"/>`;
      // 0.26.6.0(7): the room climate at rest – warm/cool, humid (mist, livelier while rising)/dry, mould risk
      out += A.climateSvg(A.roomClimate(live), r.polygon, `rc-${esc(r.id)}`, px, live && live.moisture_source_active ? this._sourceAt(r, px) : null);
    }
    out += A.nightVeil(sky, rooms);  // 0.26.6.0(8): night and twilight over the house (sun.sun), under walls and labels
    out += V.wallsSvg(G.wallSegments(rooms, openings), px);
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
      // 0.26.6.0(7): fresh air reaching into the room at an open (deep) or tilted (short) outside opening; just
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
      if (live && A.roomClimate(live).fan) {  // 0.26.6.0(7): an exhaust fan that really runs turns slowly
        const p = G.labelPoint(r.polygon), rb = G.bbox([r.polygon]);
        out += A.fanSvg([Math.max(p[0] - px(44), rb.minX + px(16)), Math.min(p[1] + px(30), rb.maxY - px(16))], px, esc(this._t("fan_running")));
      }
      if (live && live.moisture_source_active) {  // 0.26.5.5: a detected moisture source, where the room is
        const [x, y] = this._sourceAt(r, px);
        out += `<g class="source" role="img" aria-label="${esc(String(live.moisture_source_label || this._t("source_on")))}"><circle cx="${G.round3(x)}" cy="${G.round3(-y)}" r="${px(13)}" stroke-width="${px(2)}"/><text x="${G.round3(x)}" y="${G.round3(-y + px(5))}" text-anchor="middle" font-size="${px(14)}">💧</text></g>`;
      }
    }
    return out + markers + "</svg>";
  }
  // 0.26.6.0(6/7): the room label without a box – the name on the room surface (colour chosen for contrast, a soft
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
  // 0.26.6.0(7): the areas a label keeps free – a door's swing (hinge, free end, open leaf) and the sashes of a window
  _labelBlocks(rooms, openings, px) {
    const out = [];
    for (const o of openings) {
      const r = rooms.find(x => x.id === o.room_id);
      if (!r || !(o.edge >= 0 && o.edge < r.polygon.length)) continue;
      const len = G.edgeLength(r.polygon, o.edge), width = Math.min(o.width_m || Math.min(0.9, len * 0.4), len), half = width / len / 2;
      const a = G.edgePoint(r.polygon, o.edge, Math.max(o.offset - half, 0)), b = G.edgePoint(r.polygon, o.edge, Math.min(o.offset + half, 1));
      const n = V.inwardNormal(G, r.polygon, o.edge), w = Math.hypot(b[0] - a[0], b[1] - a[1]);
      let pts;
      // 0.26.6.0(10): the live map draws no door swing, so it takes no label space either (only an open door's leaf)
      if (o.kind === "door") { if (!(o.state === "open" || o.state === "open_unspecified")) continue; const d = G.doorGeometry(a, b, n, o); const tip = [d.hinge[0] + d.swing[0] * w, d.hinge[1] + d.swing[1] * w]; pts = [d.hinge, tip, [d.hinge[0] + (tip[0] - d.hinge[0]) * 0.5 + (d.free[0] - d.hinge[0]) * 0.12, d.hinge[1] + (tip[1] - d.hinge[1]) * 0.5 + (d.free[1] - d.hinge[1]) * 0.12]]; }
      else if (o.state === "open" || o.state === "open_unspecified") { const k = w * 0.45; pts = [a, b, [a[0] + n[0] * k, a[1] + n[1] * k], [b[0] + n[0] * k, b[1] + n[1] * k]]; }
      else continue;  // 0.26.6.0(9): a closed or tilted window takes no room space (its symbol lies in the wall)
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
    // 0.26.6.0(7/9): the readings may stand in two rows (°C, %), the state may shrink to its symbol – a room keeps its
    // readings before the state word, and its full name before a shortened one: a compound name may break into two
    // rows ("Arbeits-" / "zimmer"), a long name of a small room becomes its last word ("Gäste-WC" → "WC").
    // 0.26.6.0(9) regression fix: every variant is tried keeping door swings and open sashes free, then – rather than
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
    // first every variant with readings keeping the swings free, then over the swing hairline, then without readings
    const withValues = variants.filter(v => v.some(row => row.kind === "c")), rest = variants.filter(v => !v.some(row => row.kind === "c"));
    for (const [group, free] of [[withValues, blocks], [withValues, []], [rest, blocks], [rest, []]]) {
      if (free !== blocks && !blocks.length) continue;  // no swings to keep free: nothing to retry
      for (const rows of group) {
        const h = rows.reduce((sum, row) => sum + row.h, 0), w = Math.max(...rows.map(row => row.w));
        const spot = G.labelSpot(r.polygon, px(h), px(pad), free);
        if (spot && spot.w >= px(w)) return this._tagRows(rows, spot, h, px, dark, name);
      }
    }
    // a shortened name with the state symbol, when only the name is too long
    const slim = G.labelSpot(r.polygon, px(13 * 1.3 + pillF * 1.9 + 4), px(pad), blocks) || G.labelSpot(r.polygon, px(13 * 1.3 + pillF * 1.9 + 4), px(pad));
    if (slim && slim.w >= px(measure("Ab…", 12, 900) + 4)) {
      let cut = short;
      while (cut.length > 1 && measure(`${cut}…`, 12, 900) + 4 > slim.w / px(1)) cut = cut.slice(0, -1);
      return this._tagRows([nameRow(12, cut === short ? short : `${cut}…`), pill(icon)], slim, 13 * 1.3 + pillF * 1.9 + 4, px, dark, name);
    }
    // too small for any text: a state dot as large as the room allows (at least 18 px across)
    const box = G.bbox([r.polygon]), inner = Math.min(box.maxX - box.minX, box.maxY - box.minY) / u;
    const spot = G.labelSpot(r.polygon, Math.min(px(30), (box.maxY - box.minY) * 0.8), 0) || { x: G.labelPoint(r.polygon)[0], y: G.labelPoint(r.polygon)[1] };
    const radius = Math.max(9, Math.min(15, inner * 0.42));
    return `<g class="tag"><title>${esc(name)}</title><circle class="dot" cx="${G.round3(spot.x)}" cy="${G.round3(-spot.y)}" r="${px(radius)}" stroke-width="${px(1.5)}"/><text class="a" x="${G.round3(spot.x)}" y="${G.round3(-spot.y + px(radius * 0.36))}" text-anchor="middle" font-size="${px(Math.max(12, radius))}">${icon}</text></g>`;
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
  _tile(label, value, subText) { return `<div class="tile"><div class="l">${esc(label)}</div><div class="v">${value}</div>${subText ? `<div class="s">${subText}</div>` : ""}</div>`; }
  // The detail window (tap on a room, an opening or an air path).
  _dialogHtml(layout) {
    const sel = this._selected;
    if (!sel) return "";
    const t = k => this._t(k), lang = this._lang();
    const air = this._house && this._house.airflow;
    const n = (v, d = 1, unit = "") => (v == null || !Number.isFinite(Number(v)) ? "–" : `${Number(v).toFixed(d)}${unit}`);
    const wrap = (headColor, emo, title, act, body, cls = "") => `<dialog class="roomdlg" aria-label="${esc(title)}"><div class="dlg${cls}">
      <header style="background:${headColor}"><span class="emo">${emo}</span><div><h3>${esc(title)}</h3>${act ? `<div class="act">${act}</div>` : ""}</div></header>
      <div class="body">${body}</div><div class="foot"><button data-close-detail>${esc(t("close"))}</button></div></div></dialog>`;
    if (sel.type === "support") return wrap(V.BRAND.cyan, "🛟", t("support_title"), "", this._supportBody(), " dark support");
    if (sel.type === "moisture") {
      const f = this._moistureFacts() || { amount: 0, minutes: null, live: false, waits: false, over: false };
      const value = f.amount <= -1 ? `+${Math.abs(f.amount)} ml` : `≈ ${Math.max(f.amount, 0)} ml`, sub = f.amount <= -1 ? t(f.live ? "moist_added_sub" : "moist_would_add_sub") : t(f.live ? "moist_so_far_sub" : "moist_now_sub");
      const time = f.minutes != null ? (f.over ? `+${f.minutes} ${esc(t("min_short"))}` : `${f.minutes} ${esc(t("min_short"))}`) : "–";
      return wrap(V.BRAND.sky, "💧", t("moist_title"), "", `<div class="tiles">${this._tile(t(f.live ? "moist_so_far" : "moist_now"), value, esc(sub))}`
        + `${this._tile(t(f.live ? (f.over ? "moist_over_tile" : "moist_remaining") : "moist_duration"), time, "")}${this._tile(t("moist_confidence"), Number.isFinite(f.confidence) ? `${Math.round(f.confidence)} %` : "–", "")}</div>`
        + `${f.amount >= 1 || f.live ? "" : `<p>${esc(t("moist_none"))}</p>`}${f.waits ? `<p>${esc(t("moist_wait"))}</p>` : ""}<p class="hint">${esc(t("moist_explain"))}</p>`);
    }
    if (sel.type === "room") {
      const lr = layout.rooms.find(r => r.id === sel.id);
      const room = lr && this._rooms[lr.room_key];
      if (!room) return wrap(V.BRAND.slate, "🔧", lr ? lr.room_key : "–", "", `<p>${esc(t("no_room_data"))}</p>`);
      const tone = roomTone(room);
      const ex = room.air_exchange && room.air_exchange.exchanged_percent != null ? `${Math.round(room.air_exchange.exchanged_percent)} %` : "–";
      const next = known(room.moisture_effect_next_5_min_ml);
      const live = this._house && this._house.rooms ? this._house.rooms[lr.room_key] : null;
      const contacts = live ? Object.entries(live.contacts || {}).map(([id, c]) => `<li>${esc(id)}: ${esc(c.pending ? t("st_pending") : t(`st_${c.state}`))}${c.delay_s ? ` · ${t("delay")} ${c.delay_s} ${t("s")}` : ""}</li>`).join("") : "";
      const tiles = [
        this._tile(t("tile_temp"), n(room.temperature, 1, " °C"), room.comfort_target_c != null ? `${t("target")} ${n(room.comfort_target_c, 1, " °C")}` : ""),
        this._tile(t("tile_rh"), n(room.humidity, 0, " %"), `${t("ah")} ${n(room.absolute_humidity, 2, " g/m³")}`),
        this._tile("CO₂", room.co2 != null ? `${Math.round(room.co2)} ppm` : "–", room.co2 != null ? "" : t("not_measured")),
        this._tile(t("surface"), n(room.surface_rh, 0, " %"), mouldWarning(room) ? `${V.TONE_EMOJI[tone === "critical" ? "critical" : "wait"]} ${t("mould_warn")}` : esc(t(`mould_${String(room.mould_level || "").replace(/ /g, "_").toLowerCase()}`))),
        this._tile(t("tile_next5"), Number.isFinite(next) ? `${next > 0 ? "−" : next < 0 ? "+" : "±"}${Math.abs(Math.round(next))} ml` : "–", n(room.temp_next_5_min_c, 1, " °C")),
        this._tile(t("air_exchange"), room.active ? ex : "–", room.active ? t("estimate") : ""),
        this._tile(t("learning"), `${room.learning_samples ?? "–"}`, `${t("rate")} ${n(room.learned_exchange_rate_per_min, 3, "/min")}`),
        room.fan_automation ? this._tile(t("tile_fan"), esc(room.fan_automation.label || "–"), esc(fanCountdown(room.fan_automation, Date.now(), t, lang))) : "",
      ].join("");
      return wrap(V.TONE_COLOR[tone], V.TONE_EMOJI[tone], room.name || lr.room_key, esc(T[lang].actions[actionCode(room)] || actionCode(room)),
        `<div class="why"><b>${esc(t("reason"))}:</b> ${esc(room.reason || "–")}</div><div class="tiles">${tiles}</div>${contacts ? `<div><b>${esc(t("openings_title"))}</b><ul>${contacts}</ul></div>` : ""}`);
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
    if (!svg || !scene || (!scene.field && !scene.routes.length)) { if (this._flowCanvas) this._flowCanvas.remove(); if (this._flowLayer) this._flowLayer.field = null; return; }
    if (!this._flowCanvas) { this._flowCanvas = document.createElement("canvas"); this._flowCanvas.className = "flow"; this._flowCanvas.setAttribute("aria-hidden", "true"); }
    const cv = this._flowCanvas, mr = map.getBoundingClientRect(), sr = svg.getBoundingClientRect();
    Object.assign(cv.style, { left: `${sr.left - mr.left + map.scrollLeft}px`, top: `${sr.top - mr.top + map.scrollTop}px`, width: `${sr.width}px`, height: `${sr.height}px` });
    map.appendChild(cv);
    if (!this._flowLayer) this._flowLayer = new FL.FlowLayer(cv, F);
    const clear = [...svg.querySelectorAll(".tag, g.source, g.fan, g.conn-mark")].map(g => { try { const b = g.getBBox(); return { x: b.x, y: b.y, w: b.width, h: b.height }; } catch (_) { return null; } }).filter(Boolean);
    this._flowLayer.setScene({ ...scene, clear });
    this._flowSceneKey = scene.key;
    if (this._windStill()) this._flowLayer.still();
  }
  // Hotfix F04: animation off or "reduce motion" stops a running loop at once; switching back continues the
  // same phase. Never two loops per card.
  _windStill() { return this._config.animation === false || !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  _windSync() {
    if (this._windStill() || !this.isConnected || !this._waves || !this._waves.length) { this._windStop(); return; }
    if (!this._windRaf) this._windRaf = requestAnimationFrame(t => this._windFrame(t));
  }
  _windFrame(now) {
    this._windRaf = null;
    if (!this.isConnected || !this._waves || !this._waves.length || this._windStill()) { this._windLast = null; return; }
    // a hidden tab or a long frame continues calmly instead of jumping
    const dt = this._windLast == null || this.hasAttribute("data-paused") ? 0 : Math.min(now - this._windLast, 100);
    this._windLast = now;
    this._windPhase = ((this._windPhase || 0) + dt / 1000 / (this._windDur || 2)) % 1;
    this._flowAcc = (this._flowAcc || 0) + dt;
    if (now - (this._windDrawn || 0) >= 33) {  // ~30 frames per second are plenty for soft waves
      this._windDrawn = now;
      // order 8: the broad air layers breathe – their bend changes slowly, each layer in its own rhythm
      const t = (this._flowLayer ? this._flowLayer.t : now / 1000);
      for (const w of this._waves) w.el.setAttribute("d", V.wavePath(w.frame, { ...w.geo, amp: w.geo.amp * (1 + 0.35 * Math.sin(t * 0.27 + w.geo.shift * 1.7)) }, this._windPhase));
      if (this._flowLayer) this._flowLayer.frame(this._flowAcc / 1000);
      this._flowAcc = 0;
    }
    this._windRaf = requestAnimationFrame(t => this._windFrame(t));
  }
  _windStop() { if (this._windRaf) cancelAnimationFrame(this._windRaf); this._windRaf = null; this._windLast = null; }
  // The card frame: <style> and <ha-card> once, the content in .faiq-main, the room window next to it.
  _frameElements() {
    const root = this.shadowRoot;
    const find = () => [...root.children].find(n => n.localName === "ha-card");  // (":scope" does not apply to a shadow root)
    let card = find();
    if (!card) {
      root.innerHTML = `<style>${V.STYLE}${A.ATMOS_STYLE}</style><ha-card></ha-card>`;
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
    if (old && old.dataset.key === key && old.open) { if (key !== "support:") old.innerHTML = next.innerHTML; return; }
    if (old) { try { old.close(); } catch (_) { /* closed */ } old.remove(); }
    next.dataset.key = key;
    next.addEventListener("cancel", ev => { ev.preventDefault(); this._closeDialog(); });
    next.addEventListener("click", ev => { if (ev.target === next) this._closeDialog(); });  // backdrop
    card.insertBefore(next, card.querySelector(":scope > dialog.menudlg"));  // the room window first, then the menu
    try { next.showModal(); } catch (_) { next.setAttribute("open", ""); }
  }
  _closeDialog() { this._selected = null; this._render(); }
  _render() {
    if (this._editing) return;
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
      // 0.26.6.0(2): no "action on another floor" notice – that floor's button pulses (see _floorButtons)
      if (this._config.auto_focus === "auto" && this._lockUntil > Date.now()) {
        const until = new Date(this._lockUntil).toLocaleTimeString(this._lang(), { hour: "2-digit", minute: "2-digit" });
        warn.push(`<div class="notice">${esc(this._t("focus_paused"))} ${esc(until)} <button class="small" data-resume>${esc(this._t("focus_resume"))}</button></div>`);
      }
      const menuOpen = !!this._menuOpen;
      // UI hotfix: floors and menu sit in a bar at the bottom edge of the card, below the plan – they never cover
      // rooms, walls, windows or labels; the plan's own bottom margin stays a free zone for the wind streams
      // 0.26.6.0(7): a slim bar above the plan – notes that need a tap on the left, the local weather (or the card's
      // own sensors) on the right; like the bottom bar it never covers the plan
      const weather = this._weatherChip(), moist = this._moistureChip();
      const top = warn.length || weather || moist ? `<div class="topbar">${moist || warn.length ? `<div class="warns">${moist}${warn.join("")}</div>` : ""}${weather}</div>` : "";
      body = `<div class="stage">${top}${this._maps(layout)}<div class="mapbar">${this._floorButtons(layout, floors)}`
        + `<button class="menu-btn fab" data-menu aria-haspopup="dialog" aria-expanded="${menuOpen}">☰ ${esc(this._t("menu"))}</button></div></div>`;
      dialogHtml = this._dialogHtml(layout);
    }
    // Community hotfix: a live update keeps where the user scrolled (map, room window)
    const scroll = [...root.querySelectorAll(".map, dialog.roomdlg .dlg .body")].map(el => [el.scrollLeft, el.scrollTop]);
    // Hotfix F02 ("the house map keeps jumping up"): <ha-card> and the open room window stay the same elements.
    // A new <ha-card> has no content until Home Assistant has drawn it (a microtask later); the scroll
    // restore below measured the page in that moment, the card was a few pixels high and the browser cut the
    // page scroll back – WebKit keeps that cut. Only the content inside the card is replaced now.
    const focus = focusKey(root.activeElement);
    const { card, main } = this._frameElements();
    main.innerHTML = current ? body : `${this._hero(null)}${body}`;
    card.classList.toggle("plan-first", !!current);
    this._bindFlow();
    this._bindWaves();
    this._syncMenu(card, current ? current.layout : null);  // before the bindings below: its buttons are bound with the rest
    root.querySelectorAll("[data-floor]").forEach(b => b.addEventListener("click", () => this._chooseFloor(b.dataset.floor)));
    root.querySelectorAll("[data-layer]").forEach(b => b.addEventListener("click", () => { this._layer = b.dataset.layer; this._persist(); this._render(); }));
    const select = (type, id) => { this._selected = { type, id }; this._render(); };
    const bind = (selector, attr, type) => root.querySelectorAll(selector).forEach(el => {
      el.addEventListener("click", () => select(type, type === "path" ? Number(el.dataset[attr]) : el.dataset[attr]));
      el.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(type, type === "path" ? Number(el.dataset[attr]) : el.dataset[attr]); } });
    });
    this._syncDialog(card, dialogHtml);
    bind("[data-room]", "room", "room"); bind("[data-opening]", "opening", "opening"); bind("[data-path]", "path", "path");
    const dialog = card.querySelector(":scope > dialog.roomdlg");
    if (dialog) dialog.querySelector("[data-close-detail]").addEventListener("click", () => this._closeDialog());
    root.querySelectorAll(".map, dialog.roomdlg .dlg .body").forEach((el, i) => { if (scroll[i]) [el.scrollLeft, el.scrollTop] = scroll[i]; });
    const again = focus && root.querySelector(focus);  // a live update keeps the focused button where it still exists
    if (again && root.activeElement !== again) { try { again.focus({ preventScroll: true }); } catch (_) { /* old engine */ } }
    const resume = root.querySelector("[data-resume]");
    if (resume) resume.addEventListener("click", () => { this._lockUntil = 0; this._persist(); this._updateFocus(); this._render(); });
    const edit = root.querySelector("[data-edit]");
    if (edit) edit.addEventListener("click", () => { this._closeMenu(); this._selected = null; this._openEditor(); });
    const menuBtn = root.querySelector("[data-menu]");
    if (menuBtn) menuBtn.addEventListener("click", () => this._openMenu());
    const support = root.querySelector("[data-support]");
    if (support) support.addEventListener("click", () => { this._closeMenu(); this._openSupport(); });
    const closeMenu = root.querySelector("[data-close-menu]");
    if (closeMenu) closeMenu.addEventListener("click", () => this._closeMenu());
    if (this._selected && this._selected.type === "support" && this._support) this._bindSupport(root);
    root.querySelectorAll("[data-guest]").forEach(b => b.addEventListener("click", () => this._setGuests(b.dataset.guest, Number(b.dataset.delta))));
    const moist = root.querySelector("[data-moisture]");
    if (moist) moist.addEventListener("click", () => select("moisture", ""));
  }
  // 0.26.6.0(2): the menu is a real window (<dialog>) over the plan. The dialog element stays: live updates refresh
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
    const html = `<div class="dlg dark"><header style="background:${V.BRAND.cyan}"><span class="emo">☰</span><div><h3>${esc(this._t("menu"))}</h3></div></header>`
      + `<div class="body">${this._menuBody(layout)}</div><div class="foot"><button data-close-menu>${esc(this._t("close"))}</button></div></div>`;
    const body = dlg.querySelector(".body"), top = body ? body.scrollTop : 0;
    dlg.innerHTML = html;  // new content every render, so every button is bound exactly once; its scroll is kept
    const again = dlg.querySelector(".body");
    if (again) again.scrollTop = top;
    if (this._menuOpen && !dlg.open) { try { dlg.showModal(); } catch (_) { dlg.setAttribute("open", ""); } }
    if (!this._menuOpen && dlg.open) { try { dlg.close(); } catch (_) { dlg.removeAttribute("open"); } }
  }
  _openMenu() { this._menuOpen = true; this._render(); }
  _closeMenu() { if (!this._menuOpen) return; this._menuOpen = false; this._render(); }
  // 0.26.6.0(2): the menu as a window over the plan (layers, details, guests, notes, support, editing)
  _menuBody(layout) {
    const t = k => this._t(k), current = this._layout(), air = this._house && this._house.airflow;
    const notes = [];
    if (current && !current.saved) notes.push(t("proposal"));
    if (layout.building.units === "schematic") notes.push(t("schematic"));
    else if (layout.rooms.some(r => r.provenance === "estimated" || r.provenance === "schematic")) notes.push(t("estimated"));
    if (!layout.building.north_confirmed) notes.push(t("north_unconfirmed"));
    notes.push(t("streams_note"));
    if (this._layer === "airflow") notes.push(`${t("model")}: ${air ? t(air.model_level) : "–"} · ${t("hypothesis")}${air && !air.paths.length ? ` · ${t("no_paths")}` : ""}`);
    const admin = !!(this._hass && this._hass.user && this._hass.user.is_admin);
    return `<h4>${esc(t("layers"))}</h4>${this._layerTabs()}<h4>${esc(t("details"))}</h4>${this._hero(layout)}${this._guests()}`
      + `<h4>${esc(t("notes"))}</h4>${notes.map(n => `<div class="legend">${esc(n)}</div>`).join("")}`
      + `<div class="row"><button class="small" data-support>🛟 ${esc(t("support"))}</button>${admin ? `<button class="small" data-edit>✏️ ${esc(t("edit"))}</button>` : ""}</div>`;
  }
  // 0.26.6.0(2): support in its own window over the house map – the very support functions of the FreshAirIQ
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
    this._selected = { type: "support", id: "" };
    this._render();
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
    editor.addEventListener("freshairiq-house-editor-done", async ev => {
      this._editing = null;
      if (ev.detail && ev.detail.saved) {
        try { this._layoutInfo = await this._hass.callWS(this._entryMsg("freshairiq/house_map/get")); this._proposal = null; } catch (_) { /* next push */ }
      }
      this._render();
    });
    this._editing = editor;
    const { card } = this._frameElements();  // hotfix F02: the same <ha-card> – no empty frame, no jump
    card.classList.remove("plan-first");
    card.replaceChildren(editor);
  }
}

class FreshAirIQHouseCardEditor extends HTMLElement {
  setConfig(config) { this._config = Object.assign({}, config || {}); this._render(); }
  set hass(hass) { this._hass = hass; if (!this._rendered) this._render(); }
  _render() {
    if (!this._config) return;
    this._rendered = true;
    const de = String((this._hass && (this._hass.locale?.language || this._hass.language)) || navigator.language || "en").toLowerCase().startsWith("de");
    const L = de
      ? { weather: "Oben rechts statt Außenwetter: eigene Sensoren (optional, Entity-IDs mit Komma getrennt)", floor: "Etage dieser Karte (optional, z. B. ground_floor oder upper_floor) – für mehrere Karten mit verschiedenen Etagen", focus: "Etagen-Auto-Fokus", off: "Aus", hint: "Nur Hinweis", auto: "Automatisch", layer: "Start-Ebene", lock: "Manuelle Etagenwahl halten (min)", anim: "Luftweg-Animation", entry: "FreshAirIQ-Eintrag (optional)", title: "Titel" }
      : { weather: "Top right instead of the outdoor weather: own sensors (optional, entity ids separated by commas)", floor: "Floor of this card (optional, e.g. ground_floor or upper_floor) – for several cards showing different floors", focus: "Floor auto focus", off: "Off", hint: "Hint only", auto: "Automatic", layer: "Start layer", lock: "Keep a manual floor choice (min)", anim: "Air path animation", entry: "FreshAirIQ entry (optional)", title: "Title" };
    const c = this._config;
    this.innerHTML = `<div style="display:grid;gap:10px;padding:8px 0">
      <label>${L.title}<br><input data-k="title" value="${esc(c.title || "")}" style="width:100%"></label>
      <label>${L.focus}<br><select data-k="auto_focus">${FOCUS_MODES.map(m => `<option value="${m}"${(c.auto_focus || "hint") === m ? " selected" : ""}>${L[m]}</option>`).join("")}</select></label>
      <label>${L.layer}<br><select data-k="layer">${LAYERS.map(l => `<option value="${l}"${(c.layer || "action") === l ? " selected" : ""}>${esc(T[de ? "de" : "en"][`layer_${l}`])}</option>`).join("")}</select></label>
      <label>${L.lock}<br><input data-k="manual_lock_min" type="number" min="1" max="240" value="${esc(c.manual_lock_min || 10)}"></label>
      <label><input data-k="animation" type="checkbox"${c.animation === false ? "" : " checked"}> ${L.anim}</label>
      <label>${L.weather}<br><input data-k="weather_sensors" value="${esc(Array.isArray(c.weather_sensors) ? c.weather_sensors.join(", ") : c.weather_sensors || "")}" placeholder="sensor.aussen_temperatur, sensor.aussen_feuchte" style="width:100%"></label>
      <label>${L.floor}<br><input data-k="floor" value="${esc(c.floor || "")}" placeholder="ground_floor" style="width:100%"></label>
      <label>${L.entry}<br><input data-k="entry_id" value="${esc(c.entry_id || "")}" style="width:100%"></label></div>`;
    this.querySelectorAll("[data-k]").forEach(el => el.addEventListener("change", () => {
      const k = el.dataset.k;
      const value = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
      const next = Object.assign({}, this._config);
      if (value === "" || value == null) delete next[k]; else next[k] = value;
      this._config = next;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: next }, bubbles: true, composed: true }));
    }));
  }
}

if (!customElements.get("freshairiq-house-card-impl")) customElements.define("freshairiq-house-card-impl", FreshAirIQHouseCard);
if (!customElements.get("freshairiq-house-card-editor-impl")) customElements.define("freshairiq-house-card-editor-impl", FreshAirIQHouseCardEditor);
