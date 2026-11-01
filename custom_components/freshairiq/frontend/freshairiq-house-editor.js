const FAIQ_VERSION = "0.26.5.5";
// FreshAirIQ house map – floor plan editor (opened from the house card by administrators).
// Quick mode: move/scale/rotate rooms, slide openings along their wall, templates.
// Precision mode: drag/add/delete corners, numeric coordinates, snap to grid and walls.
// Floor plan template: a picture per floor behind the drawing, scale from a measured distance, north from
// the plan's arrow, rooms by tapping into them (detected locally) and windows by tapping on a wall.
// The draft lives only in this element (no re-render on hass updates); saving sends
// it with the base revision so a concurrent edit is refused instead of overwritten.

// the query of this module's own URL (version + build revision b=) reaches every module it imports
const Q = new URL(import.meta.url).search || `?v=${FAIQ_VERSION}`;
// Hotfix F02: a re-render (selection, undo/redo, input, save) keeps the focused control, its caret and the page
// position (focus without scrolling). Controls are found again by their data attribute and value.
const FOCUS_ATTRS = ["data-a", "data-f", "data-k", "data-mode", "data-tool", "data-w", "data-i", "data-id", "data-assign", "data-contact"];
const editorFocus = el => {
  if (!el || !el.getAttribute) return null;
  const attr = FOCUS_ATTRS.find(a => el.hasAttribute(a));
  if (!attr) return null;
  let caret = null;
  try { caret = typeof el.selectionStart === "number" ? [el.selectionStart, el.selectionEnd] : null; } catch (_) { caret = null; }
  return { selector: `${el.tagName.toLowerCase()}[${attr}="${String(el.getAttribute(attr)).replace(/["\\]/g, "\\$&")}"]`, caret };
};
const restoreFocus = (root, keep) => {
  const el = keep && root.querySelector(keep.selector);
  if (!el || el.disabled) return;
  try { el.focus({ preventScroll: true }); if (keep.caret && typeof el.setSelectionRange === "function") el.setSelectionRange(...keep.caret); } catch (_) { /* not a text field */ }
};
const G = await import(new URL(`./freshairiq-house-geometry.js${Q}`, import.meta.url).href);
const T = await import(new URL(`./freshairiq-house-trace.js${Q}`, import.meta.url).href);

export const EDITOR_TAG = "freshairiq-house-layout-editor";
const HISTORY = 100;
const GRIDS = [0, 0.05, 0.1, 0.25, 0.5];
const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clone = value => JSON.parse(JSON.stringify(value));

const L = {
  de: {
    quick: "Schnell", precise: "Präzision", undo: "Rückgängig", redo: "Wiederholen", zoom_in: "Vergrößern", zoom_out: "Verkleinern", fit: "Einpassen",
    grid: "Raster", off: "aus", floor: "Etage", add_room: "Raum hinzufügen", template: "Vorlage", rect: "Rechteck", l: "L-Form", u: "U-Form",
    propose: "Neu vorschlagen", missing: "Fehlende Räume ergänzen", export: "Export", import: "Import", save: "Speichern", cancel: "Verwerfen",
    saving: "Speichert …", saved: "Gespeichert", conflict: "Der Grundriss wurde inzwischen anderswo gespeichert. Bitte Entwurf exportieren und neu laden.",
    reload: "Neu laden", invalid: "Der Grundriss ist noch nicht gültig:", failed: "Speichern fehlgeschlagen", discard: "Ungespeicherte Änderungen verwerfen?",
    delete_room: "Raum aus dem Grundriss entfernen? (Die FreshAirIQ-Raumkonfiguration bleibt unverändert.)", delete: "Entfernen", rotate: "Drehen 90°",
    add_window: "Fenster hinzufügen", add_corner: "Ecke einfügen", corner: "Ecke", x: "x (m)", y: "y (m)", area: "Fläche", room: "Raum", opening: "Öffnung",
    kind: "Art", mechanics: "Mechanik", width: "Breite (m)", contacts: "Kontakte", wall: "Wand", position: "Position", building: "Gebäude",
    north: "Norden (Grad, Richtung „oben“)", north_confirmed: "Nordrichtung geprüft", connections: "Verbindungen", outside: "außen", add: "Hinzufügen",
    preview: "Vorschau", apply: "Übernehmen", changed_rooms: "Räume ändern sich", provenance: "Herkunft", none: "Nichts ausgewählt – Raum, Ecke oder Öffnung antippen.",
    import_failed: "Datei konnte nicht gelesen werden", help: "Ziehen: Raum verschieben · Griffe: Größe/Ecken · Öffnungen entlang der Wand ziehen · Pfeiltasten verschieben · Entf löscht",
    k: { window: "Fenster", door: "Tür", roof_window: "Dachfenster", passage: "Durchgang", vent: "Lüftungsöffnung" },
    m: { unknown: "unbekannt", turn_tilt: "Dreh-Kipp", casement: "Drehflügel", tilt_only: "nur Kipp", sliding: "Schiebe", roof: "Dach", door: "Tür", fixed_vent: "feste Öffnung" },
    c: { open_passage: "offener Durchgang", door: "Tür", stairs: "Treppe", shaft: "Schacht", duct: "Kanal" },
    p: { ha: "aus HA übernommen", config: "aus Konfiguration berechnet", estimated: "geschätzt", schematic: "schematisch", auto: "automatisch vorgeschlagen", unplaced: "ohne freie Außenwand", traced: "aus der Vorlage erkannt", user: "vom Nutzer bestätigt" },
    ul_title: "Grundriss-Vorlage", ul_upload: "Bild hochladen", ul_replace: "Anderes Bild", ul_hint: "PNG, JPEG oder WebP – ein PDF bitte vorher als Bild speichern oder abfotografieren. Das Bild bleibt lokal in Home Assistant.",
    ul_show: "Vorlage zeigen", ul_opacity: "Deckkraft", ul_close: "Lücken schließen", ul_delete: "Vorlage löschen", ul_delete_q: "Vorlage dieser Etage löschen? Der gezeichnete Grundriss bleibt.",
    ul_failed: "Vorlage konnte nicht gespeichert werden", ul_bad_file: "Nur PNG, JPEG oder WebP – ein PDF bitte vorher als Bild speichern.", ul_meters: "Länge der Strecke (m)",
    ul_scale: "Maßstab: 1 m ≙ {px} Pixel", ul_uncal: "Noch kein Maßstab – zwei Punkte mit bekannter Länge antippen (z. B. eine bemaßte Wand).",
    ul_found: "Erkannt: {a} m²", ul_assign: "Zuordnen zu", ul_expected: "erwartet", ul_other: "anderer Raum …", ul_no_wall: "Keine Wand in der Nähe – näher an eine Raumkante tippen.",
    tool: { calibrate: "Maßstab", north: "Norden", separator: "Trennlinie", trace: "Raum antippen", window: "Fenster antippen", door: "Innentür antippen", passage: "Durchgang antippen" },
    openings_bar: "Öffnungen setzen", no_interior: "Hier ist keine Innenwand – auf eine Wand zwischen zwei Räumen tippen.",
    not_interior: "Liegt nicht vollständig auf einer Wand zwischen zwei Räumen – zählt als Außenöffnung.", width_handle: "Breite ziehen", narrower: "schmaler", wider: "breiter",
    tool_help: { calibrate: "Tippe Anfang und Ende einer Strecke mit bekannter Länge.", north: "Tippe zwei Punkte entlang des Nordpfeils: erst das Ende, dann die Spitze.",
      separator: "Tippe Anfang und Ende einer Trennlinie, z. B. quer über einen offenen Durchgang.", trace: "Tippe in einen Raum der Vorlage.", window: "Tippe auf eine Wand – dort entsteht ein Fenster.",
      door: "Tippe auf eine Wand zwischen zwei Räumen – dort entsteht eine Innentür.", passage: "Tippe auf eine Wand zwischen zwei Räumen – dort entsteht ein offener Durchgang." },
    reason: { wall: "Das ist eine Wand – bitte in den Raum tippen.", open: "Der Bereich ist nicht geschlossen (offene Tür oder Durchgang). „Lücken schließen“ erhöhen oder eine Trennlinie ziehen.",
      small: "Der Bereich ist zu klein für einen Raum.", scale: "Bitte zuerst den Maßstab festlegen." },
    e: { E_POLY_POINTS: "zu wenige Ecken", E_LIMIT_VERTICES: "zu viele Ecken", E_POLY_NONFINITE: "ungültige Koordinate", E_POLY_DEGENERATE: "Wand zu kurz",
      E_POLY_SELF_INTERSECT: "Wände kreuzen sich", E_POLY_AREA: "Fläche zu klein", E_ROOM_OVERLAP: "überlappt einen anderen Raum", E_FLOOR_UNKNOWN: "Etage fehlt",
      E_OPENING_ROOM: "Öffnung ohne Raum", E_OPENING_EDGE: "Öffnung liegt auf keiner Wand", E_OPENING_OFFSET: "Öffnung außerhalb der Wand", E_OPENING_WIDTH: "Öffnung breiter als die Wand" },
  },
  en: {
    quick: "Quick", precise: "Precision", undo: "Undo", redo: "Redo", zoom_in: "Zoom in", zoom_out: "Zoom out", fit: "Fit",
    grid: "Grid", off: "off", floor: "Floor", add_room: "Add room", template: "Template", rect: "Rectangle", l: "L shape", u: "U shape",
    propose: "Propose again", missing: "Add missing rooms", export: "Export", import: "Import", save: "Save", cancel: "Discard",
    saving: "Saving …", saved: "Saved", conflict: "The floor plan was saved elsewhere in the meantime. Please export your draft and reload.",
    reload: "Reload", invalid: "The floor plan is not valid yet:", failed: "Saving failed", discard: "Discard unsaved changes?",
    delete_room: "Remove the room from the floor plan? (FreshAirIQ's room configuration stays unchanged.)", delete: "Remove", rotate: "Rotate 90°",
    add_window: "Add window", add_corner: "Insert corner", corner: "Corner", x: "x (m)", y: "y (m)", area: "Area", room: "Room", opening: "Opening",
    kind: "Kind", mechanics: "Mechanism", width: "Width (m)", contacts: "Contacts", wall: "Wall", position: "Position", building: "Building",
    north: "North (degrees, direction of 'up')", north_confirmed: "North direction checked", connections: "Connections", outside: "outside", add: "Add",
    preview: "Preview", apply: "Apply", changed_rooms: "rooms change", provenance: "Origin", none: "Nothing selected – tap a room, corner or opening.",
    import_failed: "The file could not be read", help: "Drag: move room · handles: size/corners · drag openings along the wall · arrow keys move · Del deletes",
    k: { window: "Window", door: "Door", roof_window: "Roof window", passage: "Passage", vent: "Vent" },
    m: { unknown: "unknown", turn_tilt: "Turn-tilt", casement: "Casement", tilt_only: "Tilt only", sliding: "Sliding", roof: "Roof", door: "Door", fixed_vent: "Fixed vent" },
    c: { open_passage: "open passage", door: "Door", stairs: "Stairs", shaft: "Shaft", duct: "Duct" },
    p: { ha: "from HA", config: "calculated from the setup", estimated: "estimated", schematic: "schematic", auto: "proposed automatically", unplaced: "no free outside wall", traced: "detected on the template", user: "confirmed by you" },
    ul_title: "Floor plan template", ul_upload: "Upload picture", ul_replace: "Other picture", ul_hint: "PNG, JPEG or WebP – please save a PDF as a picture first or take a photo of it. The picture stays local in Home Assistant.",
    ul_show: "Show template", ul_opacity: "Opacity", ul_close: "Close gaps", ul_delete: "Delete template", ul_delete_q: "Delete this floor's template? The drawn floor plan stays.",
    ul_failed: "The template could not be saved", ul_bad_file: "Only PNG, JPEG or WebP – please save a PDF as a picture first.", ul_meters: "Length of the distance (m)",
    ul_scale: "Scale: 1 m ≙ {px} pixels", ul_uncal: "No scale yet – tap two points with a known distance (e.g. a dimensioned wall).",
    ul_found: "Detected: {a} m²", ul_assign: "Assign to", ul_expected: "expected", ul_other: "other room …", ul_no_wall: "No wall nearby – tap closer to a room edge.",
    tool: { calibrate: "Scale", north: "North", separator: "Separator", trace: "Tap a room", window: "Tap a window", door: "Tap an interior door", passage: "Tap a passage" },
    openings_bar: "Place openings", no_interior: "This is no interior wall – tap a wall between two rooms.",
    not_interior: "Not entirely on a wall between two rooms – counts as an outside opening.", width_handle: "Drag the width", narrower: "narrower", wider: "wider",
    tool_help: { calibrate: "Tap the start and end of a distance with a known length.", north: "Tap two points along the north arrow: first its tail, then its tip.",
      separator: "Tap the start and end of a separator line, e.g. across an open passage.", trace: "Tap inside a room of the template.", window: "Tap on a wall – a window is placed there.",
      door: "Tap on a wall between two rooms – an interior door is placed there.", passage: "Tap on a wall between two rooms – an open passage is placed there." },
    reason: { wall: "That is a wall – please tap inside the room.", open: "The area is not closed (open door or passage). Increase 'Close gaps' or draw a separator.",
      small: "The area is too small for a room.", scale: "Please set the scale first." },
    e: { E_POLY_POINTS: "too few corners", E_LIMIT_VERTICES: "too many corners", E_POLY_NONFINITE: "invalid coordinate", E_POLY_DEGENERATE: "wall too short",
      E_POLY_SELF_INTERSECT: "walls cross", E_POLY_AREA: "area too small", E_ROOM_OVERLAP: "overlaps another room", E_FLOOR_UNKNOWN: "floor missing",
      E_OPENING_ROOM: "opening without room", E_OPENING_EDGE: "opening on no wall", E_OPENING_OFFSET: "opening outside its wall", E_OPENING_WIDTH: "opening wider than its wall" },
  },
};

export const TEMPLATES = {
  rect: (w, d) => [[0, 0], [w, 0], [w, d], [0, d]],
  l: (w, d) => [[0, 0], [w, 0], [w, d / 2], [w / 2, d / 2], [w / 2, d], [0, d]],
  u: (w, d) => [[0, 0], [w, 0], [w, d], [w * 2 / 3, d], [w * 2 / 3, d / 3], [w / 3, d / 3], [w / 3, d], [0, d]],
};
// Pure helpers (exported for tests).
export const translate = (polygon, dx, dy) => polygon.map(p => [G.round3(p[0] + dx), G.round3(p[1] + dy)]);
export const rotate90 = polygon => {
  const c = G.labelPoint(polygon);
  return polygon.map(p => [G.round3(c[0] - (p[1] - c[1])), G.round3(c[1] + (p[0] - c[0]))]);
};
export const scaleTo = (polygon, anchor, sx, sy) => polygon.map(p => [G.round3(anchor[0] + (p[0] - anchor[0]) * sx), G.round3(anchor[1] + (p[1] - anchor[1]) * sy)]);
export const insertVertex = (polygon, index) => {
  const a = polygon[index], b = polygon[(index + 1) % polygon.length];
  const out = polygon.slice();
  out.splice(index + 1, 0, [G.round3((a[0] + b[0]) / 2), G.round3((a[1] + b[1]) / 2)]);
  return out;
};
// Openings keep their wall when a corner is inserted/removed before it.
// The width an opening is drawn with (stored width, else the default the map uses).
export const shownWidth = (room, o) => {
  const len = room ? G.edgeLength(room.polygon, o.edge) || 1 : 1;
  return G.round3(Math.min(o.width_m || Math.min(0.9, len * 0.4), len));
};
// Width from dragging one end of an opening to p: symmetric around its position, within its wall,
// at least 0.3 m, on the grid when one is set.
export const openingWidthAt = (polygon, o, p, grid = 0) => {
  const a = polygon[o.edge], b = polygon[(o.edge + 1) % polygon.length];
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (len * len);
  let width = 2 * Math.abs(t - o.offset) * len;
  if (grid > 0) width = Math.round(width / grid) * grid;
  const room = 2 * Math.min(o.offset, 1 - o.offset) * len;
  return G.round3(Math.min(Math.max(width, 0.3), Math.max(room, 0.3), len));
};
export const shiftOpenings = (openings, roomId, index, delta) => openings.map(o => (o.room_id === roomId && o.edge > index ? Object.assign({}, o, { edge: o.edge + delta }) : o));
export const changedRooms = (current, proposal) => {
  const before = new Map((current.rooms || []).map(r => [r.room_key, JSON.stringify(r.polygon)]));
  return (proposal.rooms || []).filter(r => before.has(r.room_key) && before.get(r.room_key) !== JSON.stringify(r.polygon)).length;
};
export class History {
  constructor(limit = HISTORY) { this.limit = limit; this.past = []; this.future = []; }
  push(state) { this.past.push(clone(state)); if (this.past.length > this.limit) this.past.shift(); this.future = []; }
  undo(current) { if (!this.past.length) return null; this.future.push(clone(current)); return this.past.pop(); }
  redo(current) { if (!this.future.length) return null; this.past.push(clone(current)); return this.future.pop(); }
}

const STYLE = `
:host{display:block;color:var(--primary-text-color)}
.bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px}
button,select,input{font:inherit;color:inherit}
button{cursor:pointer;border-radius:14px;border:1px solid var(--divider-color,#8884);background:transparent;padding:6px 10px;min-height:40px;min-width:40px}
button[aria-pressed="true"]{background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff)}
button.primary{background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);border-color:transparent}
select,input{background:var(--card-background-color,transparent);border:1px solid var(--divider-color,#8884);border-radius:8px;padding:6px;min-height:36px}
.canvas{border-radius:12px;background:var(--secondary-background-color,#8881);touch-action:none;user-select:none;-webkit-user-select:none}
svg{display:block;width:100%;height:60vh;max-height:620px}
.wbox{display:inline-flex;gap:4px;align-items:center}.wbox input{width:5.5em}
.room{fill:var(--primary-color,#03a9f4);fill-opacity:.18;stroke:var(--primary-text-color);cursor:move}
.room.sel{fill-opacity:.32;stroke:var(--primary-color,#03a9f4)}
.room.err{stroke:var(--error-color,#db4437);fill:var(--error-color,#db4437);fill-opacity:.2}
.other{fill:none;stroke:var(--secondary-text-color);opacity:.35;pointer-events:none}
.handle{fill:var(--card-background-color,#fff);stroke:var(--primary-color,#03a9f4);cursor:grab}
.handle.sel{fill:var(--primary-color,#03a9f4)}
.mid{fill:var(--primary-color,#03a9f4);opacity:.55;cursor:copy}
.op{stroke:var(--success-color,#43a047);stroke-linecap:round;cursor:ew-resize}
.op.sel{stroke:var(--warning-color,#ffa600)} .op.err{stroke:var(--error-color,#db4437)}
.op.inner{stroke:var(--info-color,#039be5)} .op.inner.sel{stroke:var(--warning-color,#ffa600)} .wh{cursor:ew-resize}
text{fill:var(--primary-text-color);pointer-events:none}
.err-text{fill:var(--error-color,#db4437);font-weight:600}
.grid line{stroke:var(--divider-color,#8884)}
.panel{margin-top:8px;padding:10px;border:1px solid var(--divider-color,#8884);border-radius:12px;font-size:13px;display:grid;gap:8px}
.panel h4{margin:0}
.fields{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px}
.vertex{display:grid;grid-template-columns:auto 1fr 1fr auto;gap:4px;align-items:center}
.msg{padding:8px;border-radius:10px;border:1px solid var(--divider-color,#8884)} .msg.err{border-color:var(--error-color,#db4437)}
.help{font-size:12px;color:var(--secondary-text-color)}
.ul{pointer-events:none}
.sep{stroke:#ff5d5d;stroke-linecap:round;pointer-events:none}
.tp{fill:#ff9f43;stroke:#021024;pointer-events:none}
.tracepoly{fill:#39e07a;fill-opacity:.35;stroke:#0a7a3b;pointer-events:none}
.tracepoly.bad{fill:#ff5d5d;stroke:#a32020}
.chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
input[type=range]{min-height:auto;padding:0}
`;

class FreshAirIQHouseLayoutEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._history = new History(); this._mode = "quick"; this._sel = null; this._grid = 0.1; this._view = null; this._drag = null;
    this._pointers = new Map(); this._msg = null; this._preview = null; this._dirty = false; this._busy = false;
    this._ul = {}; this._ulUrl = {}; this._pix = {}; this._ulSummary = {}; this._showUl = true; this._tool = null; this._toolPts = []; this._calib = null; this._trace = null;
  }
  set hass(hass) { this._hass = hass; } // never re-render on hass: keeps open pickers and the draft (iOS)
  setup({ entryId, layout, revision, rooms, liveRooms, language, floor, underlays }) {
    this._entryId = entryId; this._revision = revision || 0; this._rooms = rooms || []; this._live = liveRooms || {}; this._lang = language === "de" ? "de" : "en";
    this._layout = clone(layout || { schema_version: 1, revision: 0, building: { north_deg: 0, units: "schematic", north_confirmed: false }, floors: [], rooms: [], openings: [], connections: [], shading: [] });
    for (const key of ["floors", "rooms", "openings", "connections", "shading"]) if (!Array.isArray(this._layout[key])) this._layout[key] = [];
    this._floor = floor && this._layout.floors.some(f => f.id === floor) ? floor : (this._layout.floors[0] || {}).id;
    this._ulSummary = Object.assign({}, underlays || {});
    this._render();
    this._loadUnderlay(this._floor);
  }
  connectedCallback() {
    this._onKey = ev => this._key(ev);
    this.shadowRoot.addEventListener("keydown", this._onKey);
  }
  disconnectedCallback() {
    this.shadowRoot.removeEventListener("keydown", this._onKey);
    for (const url of Object.values(this._ulUrl)) URL.revokeObjectURL(url);
    this._ulUrl = {}; this._ul = {}; this._pix = {};
  }
  _t(k) { return L[this._lang][k] != null ? L[this._lang][k] : k; }
  _msgWs(type, extra = {}) { const m = Object.assign({ type }, extra); if (this._entryId) m.entry_id = this._entryId; return m; }

  // ------------------------------------------------------------------ state changes
  _commit(mutator) {
    this._history.push(this._layout);
    mutator(this._layout);
    this._dirty = true; this._msg = null;
    this._render();
  }
  _undo() { const prev = this._history.undo(this._layout); if (prev) { this._layout = prev; this._dirty = true; this._render(); } }
  _redo() { const next = this._history.redo(this._layout); if (next) { this._layout = next; this._dirty = true; this._render(); } }
  _room(id) { return this._layout.rooms.find(r => r.id === id); }
  _floorRooms() { return this._layout.rooms.filter(r => r.floor_id === this._floor); }
  _issues() { return G.validateLayout(this._layout); }
  _snap(v) { return G.snap(v, this._grid); }

  // ------------------------------------------------------------------ view
  _fit() {
    const rooms = this._floorRooms().filter(r => r.polygon.length);
    const u = this._showUl && this._ul[this._floor], s = T.displayScale(u);
    const box = G.bbox(rooms.map(r => r.polygon).concat(u ? [[[0, 0], [u.width * s, u.height * s]]] : []));
    const span = Math.max(box.maxX - box.minX, box.maxY - box.minY, 4);
    this._view = { cx: (box.minX + box.maxX) / 2, cy: (box.minY + box.maxY) / 2, size: span * 1.4 };
  }
  _viewBox() {
    if (!this._view) this._fit();
    const v = this._view, w = v.size, h = v.size * 0.75;
    return [v.cx - w / 2, -v.cy - h / 2, w, h];
  }
  _zoom(factor) { if (!this._view) this._fit(); this._view.size = Math.min(Math.max(this._view.size * factor, 1), 2000); this._render(); }
  _plan(ev) {
    const svg = this.shadowRoot.querySelector("svg");
    const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [p.x, -p.y];
  }
  _unit() { const svg = this.shadowRoot.querySelector("svg"); const vb = this._viewBox(); return vb[2] / Math.max((svg && svg.clientWidth) || 600, 1); }

  // ------------------------------------------------------------------ pointer
  _down(ev) {
    const target = ev.target.closest("[data-k]");
    ev.currentTarget.setPointerCapture(ev.pointerId);
    this._pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
    if (this._pointers.size === 2) { this._drag = { kind: "pinch", dist: this._pinchDist(), size: this._view.size }; return; }
    const start = this._plan(ev);
    if (this._tool) { this._drag = { kind: "pan", start: [ev.clientX, ev.clientY], view: Object.assign({}, this._view), tap: start }; return; }
    if (!target) { this._drag = { kind: "pan", start: [ev.clientX, ev.clientY], view: Object.assign({}, this._view) }; return; }
    const k = target.dataset.k, id = target.dataset.id, index = Number(target.dataset.i);
    if (k === "mid") {
      this._history.push(this._layout);
      const r = this._room(id);
      r.polygon = insertVertex(r.polygon, index);
      this._layout.openings = shiftOpenings(this._layout.openings, id, index, 1);
      this._dirty = true;
      this._sel = { type: "vertex", id, index: index + 1 };
      this._drag = { kind: "v", id, index: index + 1, start, before: clone(this._layout), moved: true, inserted: true };
      this._renderCanvas(); return;
    }
    this._history.push(this._layout);
    this._drag = { kind: k, id, index, start, before: clone(this._layout), moved: false };
    this._sel = k === "op" || k === "ow" ? { type: "opening", id } : k === "v" ? { type: "vertex", id, index } : { type: "room", id };
    this._renderCanvas();
  }
  _pinchDist() { const pts = [...this._pointers.values()]; return Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]) || 1; }
  _move(ev) {
    if (!this._drag) return;
    if (this._pointers.has(ev.pointerId)) this._pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
    const d = this._drag;
    if (d.kind === "pinch") { if (this._pointers.size === 2) { this._view.size = Math.min(Math.max(d.size * d.dist / this._pinchDist(), 1), 2000); this._renderCanvas(); } return; }
    if (d.kind === "pan") {
      const u = this._unit();
      this._view = Object.assign({}, d.view, { cx: d.view.cx - (ev.clientX - d.start[0]) * u, cy: d.view.cy + (ev.clientY - d.start[1]) * u });
      this._renderCanvas(); return;
    }
    const p = this._plan(ev), dx = p[0] - d.start[0], dy = p[1] - d.start[1];
    const isOpening = d.kind === "op" || d.kind === "ow";
    const base = d.before.rooms.find(r => r.id === (isOpening ? (d.before.openings.find(o => o.id === d.id) || {}).room_id : d.id));
    if (!base) return;
    const room = this._room(base.id);
    d.moved = true;
    if (d.kind === "room") {
      const first = base.polygon[0];
      const sx = this._snap(first[0] + dx) - first[0], sy = this._snap(first[1] + dy) - first[1];
      room.polygon = translate(base.polygon, sx, sy);
    } else if (d.kind === "v") {
      room.polygon[d.index] = [G.round3(this._snap(base.polygon[d.index][0] + dx)), G.round3(this._snap(base.polygon[d.index][1] + dy))];
    } else if (d.kind === "scale") {
      const box = G.bbox([base.polygon]), anchor = [box.minX, box.minY];
      const w = Math.max(box.maxX - box.minX, 0.1), h = Math.max(box.maxY - box.minY, 0.1);
      const nw = Math.max(this._snap(w + dx), 0.3), nh = Math.max(this._snap(h + dy), 0.3);
      room.polygon = scaleTo(base.polygon, anchor, nw / w, nh / h);
    } else if (d.kind === "op") {
      const o = this._layout.openings.find(x => x.id === d.id);
      const hit = G.nearestEdge(room.polygon, p);
      o.edge = hit.index; o.offset = G.round3(Math.min(Math.max(hit.t, 0.02), 0.98)); o.provenance = "user";
    } else if (d.kind === "ow") {
      const o = this._layout.openings.find(x => x.id === d.id);
      o.width_m = openingWidthAt(room.polygon, o, p, this._grid); o.provenance = "user";
    }
    if (!isOpening) room.provenance = "user";
    this._renderCanvas();
  }
  _up(ev) {
    this._pointers.delete(ev.pointerId);
    const d = this._drag;
    this._drag = null;
    if (d && d.tap && Math.hypot(ev.clientX - d.start[0], ev.clientY - d.start[1]) < 8) { this._toolTap(d.tap); return; }
    if (!d || d.kind === "pan" || d.kind === "pinch") return;
    if (!d.moved) this._history.past.pop();
    else this._dirty = true;
    this._render(); // selection and inspector follow after the gesture
  }
  _key(ev) {
    const mod = ev.ctrlKey || ev.metaKey;
    if (mod && ev.key.toLowerCase() === "z") { ev.preventDefault(); if (ev.shiftKey) this._redo(); else this._undo(); return; }
    if (mod && ev.key.toLowerCase() === "y") { ev.preventDefault(); this._redo(); return; }
    if (ev.target && /INPUT|SELECT|TEXTAREA/.test(ev.target.tagName)) return;
    if (ev.key === "Escape") { this._sel = null; this._render(); return; }
    if ((ev.key === "Delete" || ev.key === "Backspace") && this._sel) { ev.preventDefault(); this._deleteSelected(); return; }
    const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[ev.key];
    if (step && this._sel && this._sel.type === "room") {
      ev.preventDefault();
      const s = this._grid || 0.1;
      this._commit(l => { const r = l.rooms.find(x => x.id === this._sel.id); r.polygon = translate(r.polygon, step[0] * s, step[1] * s); r.provenance = "user"; });
    }
  }
  _deleteSelected() {
    const sel = this._sel;
    if (sel.type === "vertex") {
      const room = this._room(sel.id);
      if (!room || room.polygon.length <= 3) return;
      this._commit(l => { const r = l.rooms.find(x => x.id === sel.id); r.polygon.splice(sel.index, 1); l.openings = shiftOpenings(l.openings, sel.id, sel.index - 1, -1).map(o => (o.room_id === sel.id ? Object.assign({}, o, { edge: Math.min(o.edge, r.polygon.length - 1) }) : o)); });
      this._sel = { type: "room", id: sel.id };
    } else if (sel.type === "opening") {
      this._commit(l => { l.openings = l.openings.filter(o => o.id !== sel.id); });
      this._sel = null;
    } else if (sel.type === "room" && window.confirm(this._t("delete_room"))) {
      this._commit(l => { l.rooms = l.rooms.filter(r => r.id !== sel.id); l.openings = l.openings.filter(o => o.room_id !== sel.id); l.connections = l.connections.filter(c => c.a !== sel.id && c.b !== sel.id); });
      this._sel = null;
    }
    this._render();
  }

  // ------------------------------------------------------------------ actions
  _addRoom(key, template) {
    const meta = this._rooms.find(r => r.key === key);
    if (!meta) return;
    const floorId = this._floor || `f_${meta.floor || "unassigned"}`;
    const others = this._floorRooms();
    const box = G.bbox(others.map(r => r.polygon));
    const x0 = others.length ? box.maxX + 1 : 0;
    this._commit(l => {
      if (!l.floors.some(f => f.id === floorId)) l.floors.push({ id: floorId, name: meta.floor || "", level_key: meta.floor || "", order: l.floors.length });
      l.rooms.push({ id: `r_${key}`, room_key: key, floor_id: floorId, polygon: translate(TEMPLATES[template](4, 4), x0, 0), provenance: "user" });
    });
    this._floor = floorId; this._sel = { type: "room", id: `r_${key}` }; this._render();
  }
  _addWindow(roomId) {
    const room = this._room(roomId);
    let best = 0;
    for (let i = 1; i < room.polygon.length; i++) if (G.edgeLength(room.polygon, i) > G.edgeLength(room.polygon, best)) best = i;
    const id = `o_${room.room_key}_${Date.now().toString(36)}`;
    this._commit(l => { l.openings.push({ id, room_id: roomId, edge: best, offset: 0.5, width_m: null, kind: "window", mechanics: "unknown", contacts: [], provenance: "user" }); });
    this._sel = { type: "opening", id }; this._render();
  }
  async _propose(missingOnly) {
    try {
      const result = await this._hass.callWS(this._msgWs("freshairiq/house_map/propose", missingOnly ? { missing_only: true } : {}));
      if (missingOnly) { this._commit(l => Object.assign(l, clone(result.layout), { revision: l.revision })); return; }
      this._preview = { layout: result.layout, changed: changedRooms(this._layout, result.layout) };
    } catch (err) { this._msg = { err: true, text: `${this._t("failed")}: ${esc(err && (err.message || err.code))}` }; }
    this._render();
  }
  async _save() {
    const issues = this._issues();
    if (issues.length) { this._msg = { err: true, text: this._issueText(issues) }; this._render(); return; }
    this._busy = true; this._msg = { text: this._t("saving") }; this._render();
    try {
      const result = await this._hass.callWS(this._msgWs("freshairiq/house_map/save", { layout: this._layout, base_revision: this._revision }));
      this._revision = result.revision; this._dirty = false;
      this.dispatchEvent(new CustomEvent("freshairiq-house-editor-done", { detail: { saved: true } }));
    } catch (err) {
      const code = err && err.code;
      this._msg = { err: true, conflict: code === "revision_conflict", text: code === "revision_conflict" ? this._t("conflict") : `${this._t("failed")}: ${esc(err && (err.message || code))}` };
    }
    this._busy = false; this._render();
  }
  async _reload() {
    try {
      const info = await this._hass.callWS(this._msgWs("freshairiq/house_map/get"));
      this._history.push(this._layout);
      this._layout = clone(info.layout || this._layout); this._revision = info.revision; this._msg = null;
    } catch (_) { /* keep the draft */ }
    this._render();
  }
  _export() {
    const blob = new Blob([JSON.stringify(this._layout, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "freshairiq-house-layout.json";
    this.shadowRoot.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  _import(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(String(reader.result));
        if (!data || data.schema_version !== 1 || !Array.isArray(data.rooms)) throw new Error("schema");
        this._commit(l => Object.assign(l, data, { revision: l.revision }));
      } catch (_) { this._msg = { err: true, text: this._t("import_failed") }; this._render(); }
    };
    reader.readAsText(file);
  }
  _cancel() {
    if (this._dirty && !window.confirm(this._t("discard"))) return;
    this.dispatchEvent(new CustomEvent("freshairiq-house-editor-done", { detail: { saved: false } }));
  }
  _issueText(issues) {
    const names = id => { const r = this._room(id); const meta = r && this._rooms.find(m => m.key === r.room_key); return esc((meta && meta.name) || id); };
    return `${this._t("invalid")}<br>${issues.slice(0, 8).map(i => `${names(i.id)}: ${esc(this._t("e")[i.code] || i.code)}`).join("<br>")}`;
  }

  // ------------------------------------------------------------------ floor plan template
  _setUnderlay(floor, u) {
    if (this._ulUrl[floor]) URL.revokeObjectURL(this._ulUrl[floor]);
    delete this._ulUrl[floor]; delete this._pix[floor];
    if (!u) { delete this._ul[floor]; delete this._ulSummary[floor]; return; }
    const bin = atob(u.data), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    this._ul[floor] = u;
    this._ulUrl[floor] = URL.createObjectURL(new Blob([bytes], { type: u.mime }));
  }
  async _loadUnderlay(floor) {
    if (!floor || this._ul[floor] || !this._ulSummary[floor]) return;
    try {
      const result = await this._hass.callWS(this._msgWs("freshairiq/house_map/underlay_get", { floor_id: floor }));
      if (!result.underlay) return;
      this._setUnderlay(floor, result.underlay);
      if (floor === this._floor) { this._fit(); this._render(); }
    } catch (_) { /* the editor works without the template */ }
  }
  async _saveUnderlay(patch, replace = false) {
    const floor = this._floor, u = Object.assign({}, replace ? {} : this._ul[floor], patch, { floor_id: floor });
    try {
      const result = await this._hass.callWS(this._msgWs("freshairiq/house_map/underlay_save", { underlay: u }));
      this._ulSummary = result.underlays || Object.assign(this._ulSummary, { [floor]: {} });
      if (replace) this._setUnderlay(floor, u); else { this._ul[floor] = u; delete this._pix[floor]; }
      return true;
    } catch (err) {
      this._msg = { err: true, text: `${this._t("ul_failed")}: ${esc(err && (err.message || err.code))}` };
      return false;
    } finally { this._render(); }
  }
  _ensureFloor() {
    if (this._floor) return;
    const level = ((this._rooms[0] || {}).floor) || "";
    const id = `f_${level || "main"}`;
    this._commit(l => { if (!l.floors.some(f => f.id === id)) l.floors.push({ id, name: level, level_key: level, order: l.floors.length }); });
    this._floor = id;
  }
  async _upload(file) {
    this._ensureFloor();
    let encoded;
    try { encoded = await T.encodeFile(file); } catch (_) { this._msg = { err: true, text: this._t("ul_bad_file") }; this._render(); return; }
    const ok = await this._saveUnderlay(Object.assign(encoded, { scale_m_per_px: null, calibration: null, walls: [], close_px: 2, opacity: 0.55 }), true);
    if (ok) { this._showUl = true; this._setTool("calibrate"); this._fit(); this._render(); }
  }
  async _deleteUnderlay() {
    if (!window.confirm(this._t("ul_delete_q"))) return;
    try {
      await this._hass.callWS(this._msgWs("freshairiq/house_map/underlay_delete", { floor_id: this._floor }));
      this._setUnderlay(this._floor, null); this._setTool(null);
    } catch (err) { this._msg = { err: true, text: `${this._t("ul_failed")}: ${esc(err && (err.message || err.code))}` }; }
    this._render();
  }
  _setTool(tool, toggle = false) { this._tool = toggle && this._tool === tool ? null : tool; this._toolPts = []; this._calib = null; this._trace = null; }
  async _pixels(floor) {
    if (!this._pix[floor]) { const u = this._ul[floor]; this._pix[floor] = await T.pixelsOf(this._ulUrl[floor], u.width, u.height); }
    return this._pix[floor];
  }
  async _toolTap(p) {
    const tool = this._tool, u = this._ul[this._floor];
    if (tool === "window" || T.INTERIOR_KINDS.has(tool)) {
      const o = T.openingAt(this._layout, this._floor, p, Math.max(0.3, 24 * this._unit()), tool);
      if (!o || o.error) { this._msg = { err: true, text: this._t(o ? "no_interior" : "ul_no_wall") }; this._render(); return; }
      this._msg = null;
      this._commit(l => l.openings.push(o));
      this._sel = { type: "opening", id: o.id }; this._render(); return;
    }
    if (!u) return;
    const q = T.toImage(u, p).map(v => Math.round(v * 10) / 10);
    this._msg = null;
    if (tool === "trace") { await this._detect(u, q); return; }
    this._toolPts.push(q);
    if (this._toolPts.length < 2) { this._render(); return; }
    const [a, b] = this._toolPts;
    this._toolPts = [];
    if (tool === "calibrate") this._calib = { a, b };
    else if (tool === "north") {
      const deg = T.northFromArrow(a, b);
      if (deg != null) { this._commit(l => { l.building.north_deg = deg; l.building.north_confirmed = true; }); this._tool = null; }
    } else if (tool === "separator") { await this._saveUnderlay({ walls: [...(u.walls || []), [...a, ...b]] }); return; }
    this._render();
  }
  async _detect(u, q) {
    const pix = await this._pixels(this._floor);
    const result = T.detectRoom(pix.image, [q[0] * pix.k, q[1] * pix.k], {
      scale: u.scale_m_per_px ? u.scale_m_per_px / pix.k : null, closePx: u.close_px, walls: (u.walls || []).map(w => w.map(v => v * pix.k)) });
    const plan = result.pixels ? result.pixels.map(px => T.toPlan(u, [px[0] / pix.k, px[1] / pix.k])) : null;
    this._trace = Object.assign(result, { plan, matches: result.ok ? T.matchRooms(result.areaM2, this._rooms, this._layout.rooms.filter(r => r.provenance === "traced").map(r => r.room_key)) : [] });
    this._render();
  }
  _assign(key) {
    const trace = this._trace;
    if (!trace || !trace.ok || !key) return;
    let id = null;
    this._commit(l => { id = T.assignTraced(l, { key, floorId: this._floor, plan: trace.plan }); });
    this._trace = null; this._sel = { type: "room", id }; this._render();
  }
  async _calibrate(meters) {
    const scale = this._calib && T.scaleFromCalibration(this._calib.a, this._calib.b, meters);
    if (!scale) return;
    const ok = await this._saveUnderlay({ scale_m_per_px: scale, calibration: { a: this._calib.a, b: this._calib.b, meters } });
    if (ok) { this._setTool("trace"); this._fit(); this._render(); }
  }
  _underlaySvg(u, unit) {
    const s = T.displayScale(u), P = q => T.toPlan(u, q), S = p => `${G.round3(p[0])},${G.round3(-p[1])}`;
    let out = `<image class="ul" href="${this._ulUrl[this._floor]}" x="0" y="${G.round3(-u.height * s)}" width="${G.round3(u.width * s)}" height="${G.round3(u.height * s)}" opacity="${u.opacity}" preserveAspectRatio="none"/>`;
    for (const w of u.walls || []) { const a = P([w[0], w[1]]), b = P([w[2], w[3]]); out += `<line class="sep" x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke-width="${G.round3(4 * unit)}"/>`; }
    for (const q of this._toolPts.concat(this._calib ? [this._calib.a, this._calib.b] : [])) { const c = P(q); out += `<circle class="tp" cx="${G.round3(c[0])}" cy="${G.round3(-c[1])}" r="${G.round3(6 * unit)}" stroke-width="${G.round3(unit)}"/>`; }
    if (this._trace && this._trace.plan) out += `<polygon class="tracepoly${this._trace.ok ? "" : " bad"}" points="${this._trace.plan.map(S).join(" ")}" stroke-width="${G.round3(2 * unit)}"/>`;
    return out;
  }
  _underlayPanel() {
    const t = k => this._t(k), u = this._ul[this._floor], num = v => Number(v).toLocaleString(this._lang, { maximumFractionDigits: 1 });
    const upload = `<label><button data-a="ul-pick">${u ? t("ul_replace") : t("ul_upload")}</button><input type="file" accept="image/png,image/jpeg,image/webp" data-f="ul_file" hidden></label>`;
    if (!u) return `<div class="panel"><h4>${t("ul_title")}</h4><div class="chips">${upload}</div><div class="help">${t("ul_hint")}</div></div>`;
    const tools = ["calibrate", "north", "separator", "trace"].map(k => `<button data-tool="${k}" aria-pressed="${this._tool === k}">${esc(t("tool")[k])}</button>`).join("");
    const scale = u.scale_m_per_px ? t("ul_scale").replace("{px}", String(Math.round(1 / u.scale_m_per_px))) : t("ul_uncal");
    let detail = this._tool ? `<div class="help">${esc(t("tool_help")[this._tool])}</div>` : "";
    if (this._calib) detail += `<div class="chips"><label>${t("ul_meters")} <input type="number" step="0.01" min="0.1" data-f="ul_meters"></label><button class="primary" data-a="ul-calibrate">${t("apply")}</button></div>`;
    const tr = this._trace;
    if (tr && !tr.ok) detail += `<div class="msg err" role="alert">${esc(t("reason")[tr.reason] || tr.reason)}</div>`;
    if (tr && tr.ok) {
      const chips = tr.matches.slice(0, 3).map(m => `<button data-assign="${esc(m.key)}">${esc(m.name)}${m.expected ? ` · ${t("ul_expected")} ${num(m.expected)} m²` : ""}</button>`).join("");
      detail += `<div class="msg" role="status">${t("ul_found").replace("{a}", num(tr.areaM2))} – ${t("ul_assign")}:<div class="chips">${chips}<select data-f="ul_assign"><option value="">${t("ul_other")}</option>${this._rooms.map(m => `<option value="${esc(m.key)}">${esc(m.name || m.key)}</option>`).join("")}</select></div></div>`;
    }
    return `<div class="panel"><h4>${t("ul_title")}</h4><div class="chips">${tools}</div>${detail}<div class="help">${scale}</div>
      <div class="chips"><label><input type="checkbox" data-f="ul_show"${this._showUl ? " checked" : ""}> ${t("ul_show")}</label>
        <label>${t("ul_opacity")} <input type="range" min="0.1" max="1" step="0.05" data-f="ul_opacity" value="${u.opacity}"></label>
        <label>${t("ul_close")} <input type="range" min="0" max="8" step="1" data-f="ul_close" value="${u.close_px}"></label>
        ${upload}<button data-a="ul-delete">${t("ul_delete")}</button></div></div>`;
  }
  _bindUnderlay(root, on) {
    on('[data-a="ul-pick"]', () => root.querySelector('[data-f="ul_file"]').click());
    on('[data-f="ul_file"]', el => { if (el.files && el.files[0]) this._upload(el.files[0]); }, "change");
    on('[data-a="ul-delete"]', () => this._deleteUnderlay());
    on("[data-tool]", el => { this._setTool(el.dataset.tool, true); this._render(); });
    on('[data-a="ul-calibrate"]', () => this._calibrate(Number(root.querySelector('[data-f="ul_meters"]').value)));
    on("[data-assign]", el => this._assign(el.dataset.assign));
    on('[data-f="ul_assign"]', el => this._assign(el.value), "change");
    on('[data-f="ul_show"]', el => { this._showUl = el.checked; this._render(); }, "change");
    on('[data-f="ul_opacity"]', el => { const img = root.querySelector("image.ul"); if (img) img.setAttribute("opacity", el.value); }, "input");
    on('[data-f="ul_opacity"]', el => this._saveUnderlay({ opacity: Number(el.value) }), "change");
    on('[data-f="ul_close"]', el => { this._trace = null; this._saveUnderlay({ close_px: Number(el.value) }); }, "change");
  }

  // ------------------------------------------------------------------ render
  _svgInner() {
    const vb = this._viewBox(), u = this._unit(), r = 9 * u, sw = 1.5 * u;
    const S = p => `${G.round3(p[0])},${G.round3(-p[1])}`;
    const issues = this._issues(), bad = new Set(issues.map(i => i.id));
    const ul = this._showUl && this._ul[this._floor];
    let out = ul ? this._underlaySvg(ul, u) : "";
    if (this._grid >= 0.25) {
      out += `<g class="grid">`;
      for (let x = Math.ceil(vb[0]); x < vb[0] + vb[2]; x++) out += `<line x1="${x}" y1="${vb[1]}" x2="${x}" y2="${vb[1] + vb[3]}" stroke-width="${G.round3(u * 0.5)}"/>`;
      for (let y = Math.ceil(vb[1]); y < vb[1] + vb[3]; y++) out += `<line x1="${vb[0]}" y1="${y}" x2="${vb[0] + vb[2]}" y2="${y}" stroke-width="${G.round3(u * 0.5)}"/>`;
      out += `</g>`;
    }
    for (const room of this._layout.rooms.filter(x => x.floor_id !== this._floor && x.polygon.length >= 3)) out += `<polygon class="other" points="${room.polygon.map(S).join(" ")}" stroke-width="${G.round3(sw)}" stroke-dasharray="${G.round3(4 * u)} ${G.round3(4 * u)}"/>`;
    for (const room of this._floorRooms()) {
      const sel = this._sel && this._sel.id === room.id;
      const meta = this._rooms.find(m => m.key === room.room_key);
      if (room.polygon.length >= 2) out += `<polygon class="room${sel ? " sel" : ""}${bad.has(room.id) ? " err" : ""}" data-k="room" data-id="${esc(room.id)}" tabindex="0" role="button" aria-label="${esc((meta && meta.name) || room.room_key)}" points="${room.polygon.map(S).join(" ")}" stroke-width="${G.round3(sw)}"/>`;
      if (room.polygon.length >= 3) {
        const c = G.labelPoint(room.polygon);
        const err = issues.find(i => i.id === room.id);
        out += `<text x="${G.round3(c[0])}" y="${G.round3(-c[1])}" text-anchor="middle" font-size="${G.round3(13 * u)}">${esc((meta && meta.name) || room.room_key)}</text>`;
        if (err) out += `<text class="err-text" x="${G.round3(c[0])}" y="${G.round3(-c[1] + 16 * u)}" text-anchor="middle" font-size="${G.round3(12 * u)}">${esc(this._t("e")[err.code] || err.code)}</text>`;
      }
      if (sel && this._mode === "precise") {
        room.polygon.forEach((p, i) => {
          const q = room.polygon[(i + 1) % room.polygon.length];
          out += `<circle class="mid" data-k="mid" data-id="${esc(room.id)}" data-i="${i}" cx="${G.round3((p[0] + q[0]) / 2)}" cy="${G.round3(-(p[1] + q[1]) / 2)}" r="${G.round3(r * 0.6)}"><title>${esc(this._t("add_corner"))}</title></circle>`;
          out += `<circle class="handle${this._sel.type === "vertex" && this._sel.index === i ? " sel" : ""}" data-k="v" data-id="${esc(room.id)}" data-i="${i}" cx="${G.round3(p[0])}" cy="${G.round3(-p[1])}" r="${G.round3(r)}" stroke-width="${G.round3(sw)}" tabindex="0" role="button" aria-label="${esc(this._t("corner"))} ${i + 1}"/>`;
        });
      } else if (sel && room.polygon.length >= 3) {
        const box = G.bbox([room.polygon]);
        out += `<rect class="handle" data-k="scale" data-id="${esc(room.id)}" x="${G.round3(box.maxX - r)}" y="${G.round3(-box.maxY - r)}" width="${G.round3(2 * r)}" height="${G.round3(2 * r)}" stroke-width="${G.round3(sw)}"/>`;
      }
    }
    for (const o of this._layout.openings) {
      const room = this._room(o.room_id);
      if (!room || room.floor_id !== this._floor || !(o.edge >= 0 && o.edge < room.polygon.length)) continue;
      const len = G.edgeLength(room.polygon, o.edge) || 1, w = Math.min(o.width_m || Math.min(0.9, len * 0.4), len), h = w / len / 2;
      const a = G.edgePoint(room.polygon, o.edge, Math.max(o.offset - h, 0)), b = G.edgePoint(room.polygon, o.edge, Math.min(o.offset + h, 1));
      const sel = this._sel && this._sel.type === "opening" && this._sel.id === o.id;
      out += `<line class="op${sel ? " sel" : ""}${o.kind === "door" || o.kind === "passage" ? " inner" : ""}${bad.has(o.id) ? " err" : ""}" data-k="op" data-id="${esc(o.id)}" tabindex="0" role="button" aria-label="${esc(this._t("k")[o.kind] || o.kind)}" x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke-width="${G.round3(8 * u)}"/>`;
      // both ends of the selected opening: drag to change its width (it stays centred on its position)
      if (sel) for (const [i, q] of [a, b].entries()) out += `<circle class="handle wh" data-k="ow" data-id="${esc(o.id)}" data-i="${i}" cx="${G.round3(q[0])}" cy="${G.round3(-q[1])}" r="${G.round3(r * 0.8)}" stroke-width="${G.round3(sw)}"><title>${esc(this._t("width_handle"))}</title></circle>`;
    }
    return out;
  }
  _svg() {
    return `<svg viewBox="${this._viewBox().map(G.round3).join(" ")}" role="application" aria-label="${esc(this._t("help"))}">${this._svgInner()}</svg>`;
  }
  // During a drag only the drawing changes: the <svg> element (and its pointer capture) stays.
  _renderCanvas() {
    const svg = this.shadowRoot.querySelector("svg");
    if (!svg) { this._render(); return; }
    svg.setAttribute("viewBox", this._viewBox().map(G.round3).join(" "));
    svg.innerHTML = this._svgInner();
  }
  _panel() {
    const t = k => this._t(k), sel = this._sel;
    const b = this._layout.building;
    const building = `<div class="fields"><label>${t("north")}<br><input type="number" step="0.1" min="0" max="359.9" data-f="north" value="${esc(b.north_deg)}"></label>
      <label><input type="checkbox" data-f="north_confirmed"${b.north_confirmed ? " checked" : ""}> ${t("north_confirmed")}</label></div>`;
    if (!sel) return `<div class="panel"><h4>${t("building")}</h4>${building}<div class="help">${t("none")}</div></div>`;
    if (sel.type === "opening") {
      const o = this._layout.openings.find(x => x.id === sel.id);
      if (!o) return "";
      const room = this._room(o.room_id);
      const contacts = (this._live[room && room.room_key] || {}).contact_entities || [];
      const opts = (map, value) => Object.entries(map).map(([k, v]) => `<option value="${k}"${k === value ? " selected" : ""}>${esc(v)}</option>`).join("");
      return `<div class="panel"><h4>${t("opening")}</h4><div class="fields">
        <label>${t("kind")}<br><select data-f="kind">${opts(t("k"), o.kind)}</select></label>
        <label>${t("mechanics")}<br><select data-f="mechanics">${opts(t("m"), o.mechanics)}</select></label>
        <label>${t("width")}<br><span class="wbox"><button data-w="-1" aria-label="${t("narrower")}">−</button><input type="number" step="0.05" min="0.1" data-f="width" value="${esc(o.width_m == null ? "" : o.width_m)}" placeholder="${esc(shownWidth(room, o))}"><button data-w="1" aria-label="${t("wider")}">+</button></span></label>
        <label>${t("wall")}<br><input type="number" min="1" max="${room ? room.polygon.length : 1}" data-f="edge" value="${o.edge + 1}"></label>
        <label>${t("position")}<br><input type="number" step="0.01" min="0" max="1" data-f="offset" value="${esc(o.offset)}"></label></div>
        ${T.INTERIOR_KINDS.has(o.kind) && room && !T.openingTarget(this._layout, room, o) ? `<div class="msg" role="status">${t("not_interior")}</div>` : ""}
        <div>${t("contacts")}: ${contacts.map(c => `<label><input type="checkbox" data-contact="${esc(c)}"${o.contacts.includes(c) ? " checked" : ""}> ${esc(c)}</label>`).join(" ") || "–"}</div>
        <div><button data-a="delete">${t("delete")}</button></div></div>`;
    }
    const room = this._room(sel.id);
    if (!room) return "";
    const meta = this._rooms.find(m => m.key === room.room_key);
    const area = room.polygon.length >= 3 ? Math.abs(G.signedArea(room.polygon)).toFixed(1) : "–";
    const vertices = this._mode === "precise" ? room.polygon.map((p, i) => `<div class="vertex"><span>${i + 1}</span><input type="number" step="0.05" data-vx="${i}" value="${p[0]}" aria-label="${t("x")}"><input type="number" step="0.05" data-vy="${i}" value="${p[1]}" aria-label="${t("y")}"><button data-del-v="${i}" aria-label="${t("delete")}">✕</button></div>`).join("") : "";
    const others = this._layout.rooms.filter(r => r.id !== room.id);
    const conns = this._layout.connections.filter(c => c.a === room.id || c.b === room.id);
    const name = id => { if (id === "outside") return t("outside"); const r = this._room(id); const m = r && this._rooms.find(x => x.key === r.room_key); return esc((m && m.name) || id); };
    return `<div class="panel"><h4>${esc((meta && meta.name) || room.room_key)}</h4>
      <div>${t("area")}: ${area} m² · ${t("provenance")}: ${esc(t("p")[room.provenance] || room.provenance)}</div>
      <div class="fields"><label>${t("floor")}<br><select data-f="floor">${this._layout.floors.map(f => `<option value="${esc(f.id)}"${f.id === room.floor_id ? " selected" : ""}>${esc(f.name || f.level_key || f.id)}</option>`).join("")}</select></label></div>
      ${vertices}
      <div class="bar"><button data-a="rotate">${t("rotate")}</button><button data-a="window">${t("add_window")}</button><button data-a="delete">${t("delete")}</button></div>
      <div><b>${t("connections")}</b>: ${conns.map(c => `${name(c.a === room.id ? c.b : c.a)} (${esc(t("c")[c.kind] || c.kind)}) <button data-del-c="${esc(c.id)}" aria-label="${t("delete")}">✕</button>`).join(" · ") || "–"}</div>
      <div class="bar"><select data-f="conn_to"><option value="outside">${t("outside")}</option>${others.map(r => `<option value="${esc(r.id)}">${name(r.id)}</option>`).join("")}</select>
        <select data-f="conn_kind">${Object.entries(t("c")).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select><button data-a="connect">${t("add")}</button></div></div>`;
  }
  _render() {
    const keep = editorFocus(this.shadowRoot.activeElement);  // hotfix F02: keep the focused control and caret
    const t = k => this._t(k);
    const missing = this._rooms.filter(m => !this._layout.rooms.some(r => r.room_key === m.key));
    const msg = this._msg ? `<div class="msg${this._msg.err ? " err" : ""}" role="alert">${this._msg.text}${this._msg.conflict ? ` <button data-a="export">${t("export")}</button> <button data-a="reload">${t("reload")}</button>` : ""}</div>` : "";
    const preview = this._preview ? `<div class="msg" role="status">${t("preview")}: ${this._preview.changed} ${t("changed_rooms")} <button class="primary" data-a="apply">${t("apply")}</button> <button data-a="no-apply">${t("cancel")}</button></div>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <div class="bar" role="toolbar">
        <button data-mode="quick" aria-pressed="${this._mode === "quick"}">${t("quick")}</button><button data-mode="precise" aria-pressed="${this._mode === "precise"}">${t("precise")}</button>
        <button data-a="undo" aria-label="${t("undo")}"${this._history.past.length ? "" : " disabled"}>↶</button><button data-a="redo" aria-label="${t("redo")}"${this._history.future.length ? "" : " disabled"}>↷</button>
        <button data-a="zoom-out" aria-label="${t("zoom_out")}">−</button><button data-a="zoom-in" aria-label="${t("zoom_in")}">+</button><button data-a="fit">${t("fit")}</button>
        <label>${t("grid")} <select data-f="grid">${GRIDS.map(g => `<option value="${g}"${g === this._grid ? " selected" : ""}>${g ? `${g} m` : t("off")}</option>`).join("")}</select></label>
        <label>${t("floor")} <select data-f="view_floor">${this._layout.floors.map(f => `<option value="${esc(f.id)}"${f.id === this._floor ? " selected" : ""}>${esc(f.name || f.level_key || f.id)}</option>`).join("")}</select></label>
      </div>
      <div class="bar">${missing.length ? `<select data-f="add_key">${missing.map(m => `<option value="${esc(m.key)}">${esc(m.name || m.key)}</option>`).join("")}</select><select data-f="add_template">${["rect", "l", "u"].map(k => `<option value="${k}">${t(k)}</option>`).join("")}</select><button data-a="add">${t("add_room")}</button><button data-a="missing">${t("missing")}</button>` : ""}
        <button data-a="propose">${t("propose")}</button><button data-a="export">${t("export")}</button><label><button data-a="import-btn">${t("import")}</button><input type="file" accept="application/json" data-f="import" hidden></label></div>
      <div class="bar" role="toolbar" aria-label="${t("openings_bar")}">${["window", "door", "passage"].map(k => `<button data-tool="${k}" aria-pressed="${this._tool === k}">${esc(t("tool")[k])}</button>`).join("")}</div>
      ${["window", "door", "passage"].includes(this._tool) ? `<div class="help">${esc(t("tool_help")[this._tool])}</div>` : ""}
      ${preview}${msg}
      <div class="canvas">${this._svg()}</div><div class="help">${t("help")}</div>
      ${this._panel()}${this._underlayPanel()}
      <div class="bar"><button class="primary" data-a="save"${this._busy ? " disabled" : ""}>${t("save")}</button><button data-a="cancel">${t("cancel")}</button></div>`;
    this._bind();
    restoreFocus(this.shadowRoot, keep);
  }
  _bind() {
    const root = this.shadowRoot, svg = root.querySelector("svg");
    svg.addEventListener("pointerdown", ev => this._down(ev));
    svg.addEventListener("pointermove", ev => this._move(ev));
    svg.addEventListener("pointerup", ev => this._up(ev));
    svg.addEventListener("pointercancel", ev => this._up(ev));
    svg.addEventListener("wheel", ev => { ev.preventDefault(); this._zoom(ev.deltaY > 0 ? 1.1 : 1 / 1.1); }, { passive: false });
    root.querySelectorAll("[data-mode]").forEach(el => el.addEventListener("click", () => { this._mode = el.dataset.mode; this._render(); }));
    const on = (sel, fn, type = "click") => root.querySelectorAll(sel).forEach(el => el.addEventListener(type, () => fn(el)));
    const actions = {
      undo: () => this._undo(), redo: () => this._redo(), "zoom-in": () => this._zoom(1 / 1.25), "zoom-out": () => this._zoom(1.25), fit: () => { this._fit(); this._render(); },
      add: () => this._addRoom(root.querySelector('[data-f="add_key"]').value, root.querySelector('[data-f="add_template"]').value),
      missing: () => this._propose(true), propose: () => this._propose(false), export: () => this._export(), reload: () => this._reload(),
      "import-btn": () => root.querySelector('[data-f="import"]').click(), save: () => this._save(), cancel: () => this._cancel(),
      apply: () => { const p = this._preview; this._preview = null; this._commit(l => Object.assign(l, clone(p.layout), { revision: l.revision })); },
      "no-apply": () => { this._preview = null; this._render(); },
      rotate: () => this._commit(l => { const r = l.rooms.find(x => x.id === this._sel.id); r.polygon = rotate90(r.polygon); r.provenance = "user"; }),
      window: () => this._addWindow(this._sel.id), delete: () => this._deleteSelected(),
      connect: () => {
        const to = root.querySelector('[data-f="conn_to"]').value, kind = root.querySelector('[data-f="conn_kind"]').value, from = this._sel.id;
        this._commit(l => l.connections.push({ id: `c_${from}_${to}_${Date.now().toString(36)}`, a: from, b: to, kind, confirmed: true, provenance: "user" }));
      },
    };
    on("[data-a]", el => actions[el.dataset.a] && actions[el.dataset.a]());
    on('[data-f="grid"]', el => { this._grid = Number(el.value); this._render(); }, "change");
    on('[data-f="view_floor"]', el => { this._floor = el.value; this._sel = null; this._setTool(null); this._fit(); this._render(); this._loadUnderlay(el.value); }, "change");
    this._bindUnderlay(root, on);
    on('[data-f="import"]', el => { if (el.files && el.files[0]) this._import(el.files[0]); }, "change");
    on('[data-f="north"]', el => this._commit(l => { const v = Number(el.value); l.building.north_deg = Number.isFinite(v) ? ((v % 360) + 360) % 360 : 0; }), "change");
    on('[data-f="north_confirmed"]', el => this._commit(l => { l.building.north_confirmed = el.checked; }), "change");
    on('[data-f="floor"]', el => this._commit(l => { l.rooms.find(x => x.id === this._sel.id).floor_id = el.value; }), "change");
    const openingField = (field, conv) => on(`[data-f="${field}"]`, el => this._commit(l => { const o = l.openings.find(x => x.id === this._sel.id); conv(o, el.value); o.provenance = "user"; }), "change");
    openingField("kind", (o, v) => { o.kind = v; }); openingField("mechanics", (o, v) => { o.mechanics = v; });
    openingField("width", (o, v) => { o.width_m = v === "" ? null : Number(v); });
    on("[data-w]", el => this._commit(l => {
      const o = l.openings.find(x => x.id === this._sel.id), room = l.rooms.find(r => r.id === o.room_id);
      const len = room ? G.edgeLength(room.polygon, o.edge) : 0;
      o.width_m = G.round3(Math.min(Math.max(Number(shownWidth(room, o)) + Number(el.dataset.w) * 0.05, 0.3), len || Infinity)); o.provenance = "user";
    }));
    openingField("edge", (o, v) => { o.edge = Math.max(Number(v) - 1, 0); }); openingField("offset", (o, v) => { o.offset = Number(v); });
    on("[data-contact]", el => this._commit(l => { const o = l.openings.find(x => x.id === this._sel.id); const c = el.dataset.contact; o.contacts = el.checked ? [...new Set([...o.contacts, c])] : o.contacts.filter(x => x !== c); }), "change");
    on("[data-vx],[data-vy]", el => this._commit(l => {
      const r = l.rooms.find(x => x.id === this._sel.id), i = Number(el.dataset.vx ?? el.dataset.vy), axis = el.dataset.vx != null ? 0 : 1;
      r.polygon[i][axis] = G.round3(Number(el.value)); r.provenance = "user";
    }), "change");
    on("[data-del-v]", el => { this._sel = { type: "vertex", id: this._sel.id, index: Number(el.dataset.delV) }; this._deleteSelected(); });
    on("[data-del-c]", el => this._commit(l => { l.connections = l.connections.filter(c => c.id !== el.dataset.delC); }));
  }
}

if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, FreshAirIQHouseLayoutEditor);
