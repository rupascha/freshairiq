const FAIQ_VERSION = "0.26.5.5";
// FreshAirIQ house map card (optional, custom:freshairiq-house-card).
// Shows the canonical room decisions of FreshAirIQ on a free floor plan, the
// wind and a clearly marked air-path *hypothesis*. It never decides anything
// itself: actions come from the same room payload as the dashboard, pushes and
// automation events. Layout: freshairiq/house_map/*; rooms: freshairiq/dashboard/subscribe.

// the query of this module's own URL (version + build revision b=) reaches every module it imports
const Q = new URL(import.meta.url).search || `?v=${FAIQ_VERSION}`;
const G = await import(new URL(`./freshairiq-house-geometry.js${Q}`, import.meta.url).href);
const V = await import(new URL(`./freshairiq-house-view.js${Q}`, import.meta.url).href);

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
    wind_from: "Wind aus", wind_none: "Keine Windrichtung", wind_calm: "Windstill", wind_stale: "Winddaten veraltet",
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
  },
  en: {
    title: "House map", loading: "Loading house map …", not_loaded: "FreshAirIQ is not loaded.",
    live_failed: "Live connection disrupted – retrying", proposal: "Automatic proposal – not saved yet",
    schematic: "Schematic plan: room sizes unknown, not to scale", estimated: "Some room sizes are estimated",
    edit: "Edit floor plan", all_floors: "All floors", layers: "Layers", empty: "No room position known yet.",
    layer_action: "Action", layer_temperature: "Temperature", layer_humidity: "Humidity", layer_co2: "CO₂", layer_airflow: "Air paths", layer_quality: "Quality",
    wind_from: "Wind from", wind_none: "No wind direction", wind_calm: "Calm", wind_stale: "Wind data outdated",
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
  }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._editing) this._editing.hass = hass; // the editor keeps its own state; no re-render on hass
    // re-audit F01: a new Home Assistant connection – subscribe there once and release the old ones
    const conn = hass && hass.connection;
    if (this._subConn && conn !== this._subConn) { this._stop(); this._start(); return; }
    if (first || (!this._subs.length && !this._failed)) this._start();
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
      this._onMotion = () => this._windSync();
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
  _storeKey() { return `freshairiq-house:${this._config.entry_id || "default"}`; }
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
    if (this._floor !== "__all" && !floors.some(f => f.id === this._floor)) this._floor = floors[0].id;
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
  _floorTabs(layout) {
    const floors = this._floors(layout);
    if (floors.length < 2) return "";
    const all = `<button role="tab" data-floor="__all" aria-pressed="${this._floor === "__all"}" aria-selected="${this._floor === "__all"}">🏠 ${esc(this._t("all_floors"))}</button>`;
    return `<div class="row" role="tablist" aria-label="${esc(this._t("all_floors"))}">${all}${floors.map(f => {
      const count = layout.rooms.filter(r => r.floor_id === f.id && (PRIORITY[roomTone(this._rooms[r.room_key])] || 0) >= 2).length;
      return `<button role="tab" data-floor="${esc(f.id)}" aria-pressed="${f.id === this._floor}" aria-selected="${f.id === this._floor}">${this._floorName(f)}${count ? `<span class="badge" aria-label="${count}">${count}</span>` : ""}</button>`;
    }).join("")}</div>`;
  }
  _maps(layout, floors) {
    if (this._floor !== "__all") return `<div class="map">${this._svg(layout, this._floor)}</div>`;
    return floors.map(f => `<h4 class="floorhead">${this._floorName(f)}</h4><div class="map overview">${this._svg(layout, f.id)}</div>`).join("");
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
      : `${esc(lang === "de" ? w.label_de : w.label_en)} · ${w.speed_ms != null ? Math.round(w.speed_ms * 3.6) : "–"} km/h`;
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
    const extra = {
      temperature: `${num(room.temperature)} °C${room.comfort_target_c != null ? ` → ${num(room.comfort_target_c)} °C` : ""}`,
      humidity: `${num(room.humidity, 0)} % · ${num(room.absolute_humidity)} g/m³`,
      co2: room.co2 != null ? `${Math.round(room.co2)} ppm CO₂` : t("not_measured"),
      quality: `${room.data_quality === "ok" ? t("quality_ok") : t("quality_bad")} · ${t("learning")} ${room.learning_samples ?? "–"}`,
    }[this._layer] || `${num(room.temperature)} °C · ${num(room.humidity, 0)} %`;
    return { name, action, extra, tone };
  }
  _unitPx(vbWidth) {
    const measured = (this.shadowRoot.querySelector(".map") || this).getBoundingClientRect().width || this._lastWidth || 640;
    const width = Math.max(measured, 1);  // community hotfix: the plan fits the card (no sideways swiping on phones)
    this._lastWidth = measured;
    return vbWidth / width;  // plan units per screen pixel
  }
  _svg(layout, floorId) {
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
    let out = `<svg class="plan" viewBox="${vb.map(G.round3).join(" ")}" role="group" aria-label="${esc(this._t("title"))}" style="--dash:${px(10)} ${px(8)};--dot:${px(3)} ${px(7)};--dashlen:${px(54)};--dur:${G.round3(dur)}s">`;
    const marker = (id, color) => `<marker id="${id}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="${color}" stroke="${V.BRAND.ink}" stroke-width="1"/></marker>`;
    out += `<defs>${marker("ah", V.BRAND.lime)}${marker("ahx", V.BRAND.orange)}${marker("ahc", V.BRAND.cyan)}
      <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${px(2.2)}" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="comic" x="-10%" y="-10%" width="130%" height="130%"><feDropShadow dx="${px(5)}" dy="${px(5)}" stdDeviation="0" flood-color="${V.BRAND.ink}" flood-opacity="1"/></filter>
      <pattern id="grid" width="${px(28)}" height="${px(28)}" patternUnits="userSpaceOnUse"><path d="M ${px(28)} 0 L 0 0 0 ${px(28)}" fill="none" stroke="rgba(201,243,255,.08)" stroke-width="${px(1)}"/></pattern></defs>
      <rect x="${G.round3(vb[0])}" y="${G.round3(vb[1])}" width="${G.round3(vb[2])}" height="${G.round3(vb[3])}" fill="url(#grid)"/>`;
    // wind streams behind the house
    const openings = (layout.openings || []).map(o => ({ ...o, ...(opState[o.id] || {}) }));
    const pathPts = (air && air.paths ? air.paths : []).map(p => ({ ...p, points: this._pathPoints(layout, p) }));
    const streams = w && w.available && this._windSmooth != null
      ? V.windStreams({ rooms, openings, fromDeg: this._windSmooth, northDeg: north, G, paths: pathPts,
        frame: { minX: vb[0], minY: -(vb[1] + vb[3]), maxX: vb[0] + vb[2], maxY: -vb[1] } }) : [];
    // Soft wind waves: three translucent strands per stream that fade in and out at its ends. Their phase
    // comes from the card's own clock (_windPhase), so a redraw continues the motion where it was.
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
        const endOpacity = s.kind === "inflow" ? 1 : 0;
        line += `<linearGradient id="${gid}" gradientUnits="userSpaceOnUse" x1="${G.round3(first[0])}" y1="${G.round3(-first[1])}" x2="${G.round3(last[0])}" y2="${G.round3(-last[1])}"><stop offset="0" stop-color="${color}" stop-opacity="0"/><stop offset=".2" stop-color="${color}"/><stop offset=".8" stop-color="${color}"/><stop offset="1" stop-color="${color}" stop-opacity="${endOpacity}"/></linearGradient>`;
        const cls = `${j === 0 ? `stream ${s.kind} ` : ""}wave ${st.cls} k-${s.kind}${s.tilted ? " tilted" : ""}`;
        line += `<path class="${cls}" data-wave="${index}" d="${V.wavePath(frame, geo, this._windPhase || 0)}" stroke="url(#${gid})" stroke-width="${px(base * st.width)}"${s.kind === "inflow" && j === 0 ? ' marker-end="url(#ahc)"' : ""}/>`;
      });
      if (s.kind === "inflow") inflow += line; else out += line;
    });
    for (const r of rooms) {
      const live = this._rooms[r.room_key];
      const lines = this._roomLines(live, r);
      out += `<polygon class="room t-${lines.tone}${this._selected && this._selected.id === r.id ? " sel" : ""}" filter="url(#comic)" stroke-width="${px(3.5)}" tabindex="0" role="button" data-room="${esc(r.id)}" aria-label="${`${lines.name}, ${lines.action}, ${lines.extra}`.replace(/<[^>]+>/g, "")}" points="${r.polygon.map(S).join(" ")}"/>`;
    }
    for (const o of openings) {
      const r = rooms.find(x => x.id === o.room_id);
      if (!r || !(o.edge >= 0 && o.edge < r.polygon.length)) continue;
      const len = G.edgeLength(r.polygon, o.edge);
      const width = Math.min(o.width_m || Math.min(0.9, len * 0.4), len);
      const half = width / len / 2;
      const a = G.edgePoint(r.polygon, o.edge, Math.max(o.offset - half, 0)), b = G.edgePoint(r.polygon, o.edge, Math.min(o.offset + half, 1));
      const st = opState[o.id] || { state: o.kind === "passage" ? "open" : (o.contacts && o.contacts.length ? "unknown" : "no_sensor") };
      out += `<line x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke="${V.BRAND.ink}" stroke-width="${px(st.state === "tilted" ? 9 : 12)}" stroke-linecap="round"/>`;
      out += `<line class="op ${st.state}${st.pending ? " pending" : ""}" data-opening="${esc(o.id)}" tabindex="0" role="button" aria-label="${esc(this._openingText(o, st))}" x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke-width="${px(st.state === "tilted" ? 5 : 7)}"/>`;
    }
    for (const c of layout.connections || []) {
      const a = rooms.find(x => x.id === c.a), b = rooms.find(x => x.id === c.b);
      if (!a || !b || c.kind === "open_passage") continue;
      const pa = G.labelPoint(a.polygon), pb = G.labelPoint(b.polygon);
      out += `<line class="conn" x1="${G.round3(pa[0])}" y1="${G.round3(-pa[1])}" x2="${G.round3(pb[0])}" y2="${G.round3(-pb[1])}" stroke-width="${px(2)}"/>`;
    }
    if (this._layer === "airflow" && air) out += this._paths(layout, air, ids, px);
    out += inflow;
    for (const r of rooms) out += this._tag(r, this._roomLines(this._rooms[r.room_key], r), px, u);
    return out + "</svg>";
  }
  // Room tag: a white comic label inside the room; readable size (about 15/13 px) whatever the plan size.
  _tag(r, lines, px, u) {
    const anchor = G.labelPoint(r.polygon), rb = G.bbox([r.polygon]);
    const roomW = (rb.maxX - rb.minX) / u, roomH = (rb.maxY - rb.minY) / u;  // room size on screen (px)
    if (roomW < 84 || roomH < 44) {  // tiny room: just the action symbol; name and details on tap
      return `<g class="tag"><circle cx="${G.round3(anchor[0])}" cy="${G.round3(-anchor[1])}" r="${px(15)}" stroke-width="${px(2.5)}"/><text class="a" x="${G.round3(anchor[0])}" y="${G.round3(-anchor[1] + px(5.5))}" text-anchor="middle" font-size="${px(15)}">${lines.action.split(" ")[0]}</text></g>`;
    }
    const compact = roomW < 150 || roomH < 80;
    const plain = s => String(s).replace(/<[^>]+>/g, "").replace(/&[a-z#0-9]+;/g, "x");
    const rows = compact ? [[lines.name, 14, "n"], [lines.action, 12.5, "a"]] : [[lines.name, 16, "n"], [lines.action, 14, "a"], [lines.extra, 13, "c"]];
    const widthPx = Math.max(...rows.map(([s, f]) => plain(s).length * f * 0.58)) + 20;  // readable first: a tag may overlap a narrow room's walls
    const heightPx = rows.reduce((h, [, f]) => h + f * 1.25, 0) + 10;
    let y = -anchor[1] - px(heightPx) / 2;
    let text = "";
    rows.forEach(([s, f, cls]) => { y += px(f * 1.2); text += `<text class="${cls}" x="${G.round3(anchor[0])}" y="${G.round3(y)}" text-anchor="middle" font-size="${px(f)}">${s}</text>`; });
    return `<g class="tag"><rect x="${G.round3(anchor[0] - px(widthPx) / 2)}" y="${G.round3(-anchor[1] - px(heightPx) / 2)}" width="${px(widthPx)}" height="${px(heightPx)}" rx="${px(12)}" stroke-width="${px(2.5)}"/>${text}</g>`;
  }
  _pathPoints(layout, p) {
    const roomPoint = id => { const r = layout.rooms.find(x => x.id === id); return r ? G.labelPoint(r.polygon) : null; };
    const openingPoint = id => {
      const o = (layout.openings || []).find(x => x.id === id), r = o && layout.rooms.find(x => x.id === o.room_id);
      return r ? G.edgePoint(r.polygon, o.edge, o.offset) : null;
    };
    return [p.from ? openingPoint(p.from) : null, ...p.rooms.map(roomPoint), p.to && p.to !== p.from && p.kind !== "exhaust" ? openingPoint(p.to) : null].filter(Boolean);
  }
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
    const wrap = (headColor, emo, title, act, body) => `<dialog class="roomdlg" aria-label="${esc(title)}"><div class="dlg">
      <header style="background:${headColor}"><span class="emo">${emo}</span><div><h3>${esc(title)}</h3>${act ? `<div class="act">${act}</div>` : ""}</div></header>
      <div class="body">${body}</div><div class="foot"><button data-close-detail>${esc(t("close"))}</button></div></div></dialog>`;
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
      const live = room && this._house && this._house.rooms ? this._house.rooms[room.room_key] : null;
      const rows = ((o && o.contacts) || []).map(c => { const d = live && live.contacts[c]; return `<li>${esc(c)}: ${d ? esc(d.pending ? t("st_pending") : t(`st_${d.state}`)) : "–"}${d && d.delay_s ? ` · ${t("delay")} ${d.delay_s} ${t("s")}` : ""}</li>`; }).join("");
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
    if (now - (this._windDrawn || 0) >= 33) {  // ~30 frames per second are plenty for soft waves
      this._windDrawn = now;
      for (const w of this._waves) w.el.setAttribute("d", V.wavePath(w.frame, w.geo, this._windPhase));
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
      root.innerHTML = `<style>${V.STYLE}</style><ha-card></ha-card>`;
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
    if (old && old.dataset.key === key && old.open) { old.innerHTML = next.innerHTML; return; }
    if (old) { try { old.close(); } catch (_) { /* closed */ } old.remove(); }
    next.dataset.key = key;
    next.addEventListener("cancel", ev => { ev.preventDefault(); this._closeDialog(); });
    next.addEventListener("click", ev => { if (ev.target === next) this._closeDialog(); });  // backdrop
    card.appendChild(next);
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
      if (floors.length && this._floor !== "__all" && !floors.some(f => f.id === this._floor)) this._floor = floors[0].id;
      const notices = [];
      if (this._failed) notices.push(`<div class="notice warn" role="status">${esc(this._t("live_failed"))}</div>`);
      if (!current.saved) notices.push(`<div class="notice">${esc(this._t("proposal"))}</div>`);
      if (layout.building.units === "schematic") notices.push(`<div class="notice">${esc(this._t("schematic"))}</div>`);
      else if (layout.rooms.some(r => r.provenance === "estimated" || r.provenance === "schematic")) notices.push(`<div class="notice">${esc(this._t("estimated"))}</div>`);
      if (!layout.building.north_confirmed) notices.push(`<div class="notice">${esc(this._t("north_unconfirmed"))}</div>`);
      if (this._hint && this._hint !== this._floor) {
        const f = floors.find(x => x.id === this._hint);
        if (f) notices.push(`<div class="notice warn" role="status">${esc(this._t("other_floor"))}: <button class="small" data-floor="${esc(f.id)}">${this._floorName(f)}</button></div>`);
      }
      if (this._config.auto_focus === "auto" && this._lockUntil > Date.now()) {
        const until = new Date(this._lockUntil).toLocaleTimeString(this._lang(), { hour: "2-digit", minute: "2-digit" });
        notices.push(`<div class="notice">${esc(this._t("focus_paused"))} ${esc(until)} <button class="small" data-resume>${esc(this._t("focus_resume"))}</button></div>`);
      }
      const air = this._house && this._house.airflow;
      const legend = `<div class="legend">${esc(this._t("streams_note"))}${this._layer === "airflow" ? ` · ${esc(this._t("model"))}: ${esc(air ? this._t(air.model_level) : "–")} · ${esc(this._t("hypothesis"))}${air && !air.paths.length ? ` · ${esc(this._t("no_paths"))}` : ""}` : ""}</div>`;
      body = `${this._floorTabs(layout)}${this._layerTabs()}${notices.join("")}${this._maps(layout, floors)}${legend}${isAdmin ? `<div class="row"><button class="small" data-edit>✏️ ${esc(this._t("edit"))}</button></div>` : ""}`;
      dialogHtml = this._dialogHtml(layout);
    }
    // Community hotfix: a live update keeps where the user scrolled (map, room window)
    const scroll = [...root.querySelectorAll(".map, .dlg .body")].map(el => [el.scrollLeft, el.scrollTop]);
    // Hotfix F02 ("the house map keeps jumping up"): <ha-card> and the open room window stay the same elements.
    // A new <ha-card> has no content until Home Assistant has drawn it (a microtask later); the scroll
    // restore below measured the page in that moment, the card was a few pixels high and the browser cut the
    // page scroll back – WebKit keeps that cut. Only the content inside the card is replaced now.
    const focus = focusKey(root.activeElement);
    const { card, main } = this._frameElements();
    main.innerHTML = `${this._hero(current && current.layout)}${body}`;
    this._bindWaves();
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
    root.querySelectorAll(".map, .dlg .body").forEach((el, i) => { if (scroll[i]) [el.scrollLeft, el.scrollTop] = scroll[i]; });
    const again = focus && root.querySelector(focus);  // a live update keeps the focused button where it still exists
    if (again && root.activeElement !== again) { try { again.focus({ preventScroll: true }); } catch (_) { /* old engine */ } }
    const resume = root.querySelector("[data-resume]");
    if (resume) resume.addEventListener("click", () => { this._lockUntil = 0; this._persist(); this._updateFocus(); this._render(); });
    const edit = root.querySelector("[data-edit]");
    if (edit) edit.addEventListener("click", () => this._openEditor());
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
      ? { focus: "Etagen-Auto-Fokus", off: "Aus", hint: "Nur Hinweis", auto: "Automatisch", layer: "Start-Ebene", lock: "Manuelle Etagenwahl halten (min)", anim: "Luftweg-Animation", entry: "FreshAirIQ-Eintrag (optional)", title: "Titel" }
      : { focus: "Floor auto focus", off: "Off", hint: "Hint only", auto: "Automatic", layer: "Start layer", lock: "Keep a manual floor choice (min)", anim: "Air path animation", entry: "FreshAirIQ entry (optional)", title: "Title" };
    const c = this._config;
    this.innerHTML = `<div style="display:grid;gap:10px;padding:8px 0">
      <label>${L.title}<br><input data-k="title" value="${esc(c.title || "")}" style="width:100%"></label>
      <label>${L.focus}<br><select data-k="auto_focus">${FOCUS_MODES.map(m => `<option value="${m}"${(c.auto_focus || "hint") === m ? " selected" : ""}>${L[m]}</option>`).join("")}</select></label>
      <label>${L.layer}<br><select data-k="layer">${LAYERS.map(l => `<option value="${l}"${(c.layer || "action") === l ? " selected" : ""}>${esc(T[de ? "de" : "en"][`layer_${l}`])}</option>`).join("")}</select></label>
      <label>${L.lock}<br><input data-k="manual_lock_min" type="number" min="1" max="240" value="${esc(c.manual_lock_min || 10)}"></label>
      <label><input data-k="animation" type="checkbox"${c.animation === false ? "" : " checked"}> ${L.anim}</label>
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
