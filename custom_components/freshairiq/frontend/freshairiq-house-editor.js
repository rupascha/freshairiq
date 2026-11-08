const FAIQ_VERSION = "0.26.7.0";
// FreshAirIQ house map – floor plan editor (opened from the house card by administrators).
// Quick mode: move/scale/rotate rooms, slide openings along their wall, templates.
// Precision mode: drag/add/delete corners, numeric coordinates, snap to grid and walls.
// Floor plan template: a picture per floor behind the drawing, scale from a measured distance, north from
// the plan's arrow, rooms by tapping into them (detected locally) and windows by tapping on a wall.
// The draft lives only in this element (no re-render on hass updates); saving sends
// it with the base revision so a concurrent edit is refused instead of overwritten.

// the query of this module's own URL (version + build revision b=) reaches every module it imports
const Q = new URL(import.meta.url).search || `?v=${FAIQ_VERSION}`;
// 0.26.7.0: every contact of a room – its outside openings and its inside doors (both can be drawn on the plan)
const roomContacts = v => [...((v && v.contact_entities) || []), ...((v && v.inside_contact_entities) || [])];
// 0.26.7.0: touch screens get tap/drag wording instead of keyboard hints
const touchDevice = () => { try { return !!(window.matchMedia && window.matchMedia("(pointer: coarse)").matches); } catch (_) { return false; } };
// 0.26.7.0: a small compass rose – the plan's "up" stays up, the "N" arrow shows where north lies on the plan
// (north_deg = compass bearing of the plan's up, the same contract as the wind, sun and facade code)
const compassRose = (deg, letters = ["N", "E", "S", "W"]) => {
  // plain HTML (no second <svg> in the editor): a ring, the four directions where they lie on the plan, the "N" needle
  const at = k => { const r = -(deg - k) * Math.PI / 180; return `left:${(50 + 42 * Math.sin(r)).toFixed(1)}%;top:${(50 - 42 * Math.cos(r)).toFixed(1)}%`; };
  return `<div data-compass role="slider" aria-valuemin="0" aria-valuemax="359" aria-valuenow="${Math.round(deg)}" tabindex="0"
    style="position:relative;width:132px;height:132px;border-radius:50%;border:2px solid var(--divider-color,#9aa);touch-action:none;cursor:grab;margin:6px 0">
    ${[0, 90, 180, 270].map(k => `<span style="position:absolute;${at(k)};transform:translate(-50%,-50%);font-size:11px;opacity:.65">${letters[k / 90]}</span>`).join("")}
    <span style="position:absolute;left:50%;top:6px;transform:translateX(-50%);font-size:10px;opacity:.5">↑</span>
    <div data-compass-needle style="position:absolute;left:50%;top:50%;width:4px;height:52px;margin-left:-2px;transform-origin:50% 0;transform:rotate(${(180 - deg).toFixed(1)}deg);background:var(--primary-color,#03a9f4);border-radius:2px">
      <span style="position:absolute;left:50%;bottom:-10px;transform:translateX(-50%) rotate(${(deg - 180).toFixed(1)}deg);width:20px;height:20px;line-height:20px;border-radius:50%;text-align:center;font-size:11px;font-weight:700;color:#fff;background:var(--primary-color,#03a9f4)">N</span></div></div>`;
};
// U01: a new angle was not checked yet – a real change of north_deg withdraws the confirmation; the same angle keeps it
const setNorth = (layout, deg) => { const v = ((Number(deg) % 360) + 360) % 360; if (v !== Number(layout.building.north_deg)) layout.building.north_confirmed = false; layout.building.north_deg = v; };
// The plan's north for a pointer on the rose: north lies at ``a`` clockwise from "up", so "up" faces 360 − a.
export const northFromPointer = (dx, dy) => { const a = (Math.atan2(dx, -dy) * 180 / Math.PI + 360) % 360; return Math.round((360 - a) % 360); };
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
const V = await import(new URL(`./freshairiq-house-view.js${Q}`, import.meta.url).href);

export const EDITOR_TAG = "freshairiq-house-layout-editor";
const HISTORY = 100;
const GRIDS = [0, 0.05, 0.1, 0.25, 0.5];
const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clone = value => JSON.parse(JSON.stringify(value));

const L = {
  de: {
    // v0.26.6.1 editor hotfix: plain names, short context hints and the next sensible step
    add_cancel: "Abbrechen", tb_room: "＋ Raum", tb_window: "Fenster", tb_door: "Tür", tb_passage: "Durchgang", more: "Mehr", more_title: "Weitere Werkzeuge", close: "Schließen", msg_close: "Hinweis schließen",
    mode_label: "Bearbeitungsart", quick_title: "Schnell: ganze Räume verschieben und in der Größe ändern", precise_title: "Präzision: einzelne Ecken, Wandlängen und Winkel bearbeiten",
    hint_empty: "Noch kein Raum auf dieser Etage. Tippe auf „＋ Raum“, wähle den Raum und eine Form.",
    hint_quick: "Tippe einen Raum an, um ihn zu verschieben oder seine Größe zu ändern.",
    hint_precise: "Präzision: Raum antippen – dann Ecken ziehen. Ein Punkt in der Wandmitte fügt eine Ecke ein, eine Wand antippen zeigt Länge und Winkel.",
    hint_room_quick: "Ziehen verschiebt den Raum · das Quadrat an der Ecke ändert die Größe · für eine eigene Form „Ecken bearbeiten“.",
    hint_room_precise: "Ecken ziehen · einen Punkt in der Wandmitte antippen fügt eine Ecke ein · eine Wand antippen für Länge und Winkel.",
    hint_vertex: "Ecke {c}: ziehen oder mit den Pfeiltasten verschieben · Entf löscht die Ecke.",
    hint_wall: "Wand {w}: Länge eingeben und „Übernehmen“ – die gewählte Ecke bleibt stehen. Winkel und Sperren findest du in den Eigenschaften.",
    hint_opening: "Entlang der Wand ziehen verschiebt · die Enden ziehen ändert die Breite · in den Eigenschaften den Kontakt zuordnen.",
    hint_adding: "Raum und Form wählen, dann „Raum hinzufügen“. Der neue Raum erscheint neben den anderen.",
    hint_next_missing: "Nächster Schritt: Noch {n} Räume ohne Grundriss – über „＋ Raum“ ergänzen.",
    hint_next_windows: "Nächster Schritt: Fenster setzen – „Fenster“ wählen und auf eine Außenwand tippen.",
    hint_next_contacts: "Nächster Schritt: {n} Fenster/Türen ohne Kontakt – antippen und den Kontakt zuordnen.",
    hint_next_orphans: "Bitte prüfen: {n} Fenster/Türen nennen einen Kontakt, der in FreshAirIQ nicht mehr eingerichtet ist – antippen und den richtigen Kontakt wählen.", contact_gone: "nicht mehr eingerichtet",
    hint_next_save: "Alles eingezeichnet? Kurz prüfen und „Speichern“.", hint_done: "Grundriss vollständig. Zum Ändern einen Raum, eine Wand oder ein Fenster antippen.",
    edit_sel: "Bearbeiten", selected: "Gewählt: {name}",
    steps_title: "Dein Grundriss in sechs Schritten", start_intro: "Tippe auf „＋ Raum“, wähle den Raum und eine Form. Danach Fenster und Türen auf die Wände setzen und speichern.", step_optional: "optional", step_floor: "Etage wählen", step_rooms: "Räume einzeichnen", step_shape: "Lage und Form anpassen", step_openings: "Fenster, Türen, Durchgänge setzen", step_contacts: "Kontakte zuordnen", step_save: "Prüfen und speichern",
    new_room: "Neuer Raum", which_room: "Welcher Raum?", shape: "Form", shape_precise: "Eigene Form", shape_precise_hint: "„Eigene Form“ legt ein Rechteck an und schaltet auf Präzision: dann die Ecken an die richtige Stelle ziehen.",
    all_placed: "Alle Räume sind schon im Grundriss. Neue Räume legst du in der FreshAirIQ-Konfiguration an.",
    edit_corners: "Ecken bearbeiten", corners_done: "Ecken fertig", sec_corners: "Ecken als Zahlen", corners_hint: "x nach rechts, y nach oben, in Metern. Ein Wert wird beim Verlassen des Feldes übernommen.",
    sec_connections: "Verbindungen ohne gemeinsame Wand", conn_hint: "Für Treppen, Schächte oder Kanäle. Türen und Durchgänge zeichnest du direkt auf die Wand („Tür“, „Durchgang“).",
    sec_place: "Lage auf der Wand", sec_details: "Weitere Angaben", sec_angles: "Winkel der Ecken", sec_scale: "Maßstab festlegen", sec_building: "Gebäude und Nordrichtung", sec_template: "Grundriss-Vorlage (Bild)",
    contacts_hint: "Welcher Fenster- oder Türkontakt meldet diese Öffnung?", no_contacts: "In FreshAirIQ sind noch keine Kontakte eingerichtet.",
    corner_min: "Ein Raum braucht mindestens drei Ecken. Lösung: eine andere Ecke verschieben oder den ganzen Raum entfernen.",
    invalid_fix: "Rot markierte Räume antippen und korrigieren, dann erneut speichern.", failed_fix: "Dein Entwurf bleibt erhalten – Verbindung prüfen und erneut speichern.",
    import_fix: "Bitte eine Datei wählen, die mit „Export“ aus diesem Editor gespeichert wurde (.json).",
    room_info: "{a} m² · {p}",
    window_inside: "Dieses Fenster liegt an einer Innenwand.", window_out: "An die Außenwand setzen", windows_inside: "{n} Fenster liegen an einer Innenwand.", windows_out: "Alle an die Außenwand setzen",
    window_no_outside: "Dieser Raum hat keine freie Außenwand – bitte den Raum an den Hausrand verschieben.",
    unit_schematic: "Einh.", wall_length_units: "Länge (Plan-Einheiten, kein Maßstab)", scale_hint: "Dieser Grundriss ist schematisch – seine Längen sind keine Meter. Mit dem echten Maß dieser einen Wand bekommt der ganze Plan einen Maßstab.",
    scale_real: "Echte Länge dieser Wand (m)", scale_placeholder: "z. B. 3,85", scale_apply: "Maßstab festlegen",
    wall_length: "Länge (m)", wall_fixed: "Bleibt stehen", wall_lock: "Maß sperren", wall_locked: "Diese Wand hat ein gesperrtes Maß – erst die Sperre lösen.", airs: "lüftet", help_title: "Hilfe zur Bedienung", grp_view: "Ansicht", grp_edit: "Bearbeiten", grp_rooms: "Räume", grp_file: "Datei", panel_show: "Eigenschaften", panel_hide: "Nur Zeichnung", angle_locked: "Das ändert einen gesperrten Winkel (auch beim Einfügen oder Entfernen einer Ecke daneben) – erst die Winkelsperre lösen.",
    wall_help: "Nur diese Wand ändert ihre Länge: die gewählte Ecke bleibt stehen, die andere rückt entlang der Wand; die nächste Wand gleicht aus (die gegenüberliegende Wand behält ihr Maß). Gesperrte Maße und Winkel bleiben erhalten.",
    angle: "Winkel", corner_square: "Ecke {c} auf 90°", corner_lock: "Winkel an Ecke {c} sperren", snap90: "90° einrasten",
    blocked_wall: "Nicht möglich, ohne ein gesperrtes Maß zu ändern: Wand {w} ist gesperrt. Lösung: die Sperre von Wand {w} lösen oder die andere Ecke stehen lassen.",
    blocked_corner: "Nicht möglich, ohne einen gesperrten Winkel zu ändern: Ecke {c}. Lösung: die Winkelsperre an Ecke {c} lösen oder die andere Ecke stehen lassen.",
    corner_locked: "Der Winkel an Ecke {c} ist gesperrt – erst die Sperre lösen.",
    join: "Räume zusammenfügen", join_none: "Keine zusammenpassenden Wände gefunden – die Räume bis auf etwa 35 cm aneinanderschieben.",
    join_preview: "Vorschau: {m} gemeinsame Wände erkannt, {r} Räume verschoben (keiner verformt).", join_lengths: "Unterschiedliche Längen bleiben, wie gemessen (schematisch teilweise gemeinsam): {list}.",
    join_locked: "Nicht exakt angelegt, weil Maß oder Winkel gesperrt sind: {list}.", join_overlap: "Danach überlappen sich noch: {list} – bitte von Hand nachschieben.",
    floor_names: { basement: "Kellergeschoss", ground_floor: "Erdgeschoss", upper_floor: "Obergeschoss", attic: "Dachgeschoss", floor_3: "3. Obergeschoss", floor_4: "4. Obergeschoss" },
    wall_bad_length: "Bitte eine Länge ab 0,1 m eingeben.", wall_conflict_shape: "So entstünde eine ungültige Raumform – nichts geändert.",
    wall_conflict_overlap: "So würde der Raum in einen Nachbarraum ragen – nichts geändert. Lösung: die andere Ecke stehen lassen, den Raum erst verschieben oder danach „Räume zusammenfügen“.", wall_conflict_shared: "Die mitbewegte Wand teilt ein Nachbarraum nur zum Teil – er würde verzogen. Bitte die andere Ecke festhalten oder den Nachbarraum zuerst anpassen.", wall_conflict_opening: "Eine Tür, ein Fenster oder Durchgang passt dann nicht mehr auf seine Wand – nichts geändert.",
    door_hinge: "Türanschlag", hinges: { "": "wie bisher", left: "links", right: "rechts" }, door_swing: "Öffnet", swings: { in: "in diesen Raum", out: "zur anderen Seite" },
    interior_only: "Eine Innentür oder ein Durchgang bleibt auf der Wand, die beide Räume teilen – dorthin lässt sie sich nicht verschieben.",
    conv_door: "als Tür einzeichnen", conv_passage: "als Durchgang einzeichnen",
    quick: "Schnell", precise: "Präzision", undo: "Rückgängig", redo: "Wiederholen", zoom_in: "Vergrößern", zoom_out: "Verkleinern", fit: "Einpassen",
    grid: "Raster", off: "aus", floor: "Etage", add_room: "Raum hinzufügen", template: "Vorlage", rect: "Rechteck", l: "L-Form", u: "U-Form",
    propose: "Neu vorschlagen", missing: "Fehlende Räume ergänzen", export: "Export", import: "Import", save: "Speichern", cancel: "Verwerfen",
    saving: "Speichert …", saved: "Gespeichert", conflict: "Der Grundriss wurde inzwischen anderswo gespeichert. Bitte Entwurf exportieren und neu laden.",
    reload: "Neu laden", invalid: "Der Grundriss ist noch nicht gültig:", failed: "Speichern fehlgeschlagen", discard: "Ungespeicherte Änderungen verwerfen?",
    delete_room: "Raum aus dem Grundriss entfernen? (Die FreshAirIQ-Raumkonfiguration bleibt unverändert.)", delete: "Entfernen", rotate: "Drehen 90°", rotate_help: "„Drehen 90°“ dreht den Raum um seine Mitte gegen den Uhrzeigersinn – Fenster und Türen drehen mit. Viermal = wie vorher, ↶ macht es rückgängig.",
    add_window: "Fenster hinzufügen", add_corner: "Ecke einfügen", corner: "Ecke", x: "x (m)", y: "y (m)", area: "Fläche", room: "Raum", opening: "Öffnung",
    kind: "Art", mechanics: "Mechanik", width: "Breite (m)", contacts: "Kontakte", wall: "Wand", position: "Position", building: "Gebäude",
    north: "In welche Himmelsrichtung zeigt dein Grundriss nach oben?", north_confirmed: "Nordrichtung geprüft", north_help: "Damit weiß FreshAirIQ, aus welcher Richtung Sonne und Wind auf dein Haus treffen. Richte die Zeichnung anhand eines Lageplans oder einer Karte aus.", north_examples: "0° = oben Norden · 90° = oben Osten · 180° = oben Süden · 270° = oben Westen", north_now: "Oben zeigt ungefähr nach {dir} ({deg}°).", north_drag: "Pfeil „N“ ziehen oder den Winkel eingeben. Mit einer Grundriss-Vorlage: „Mehr“ → Nordpfeil aus der Vorlage.", north_confirmed_help: "Nur bestätigen, wenn die Richtung anhand einer verlässlichen Quelle (Lageplan, Karte, Kompass) kontrolliert wurde. Erst dann werden Fassaden, Sonne und Wind richtungsgenau berechnet.", north_keep: "Die Räume werden dabei nicht gedreht.",
    dirs: ["Norden", "Nord-Nordost", "Nordost", "Ost-Nordost", "Osten", "Ost-Südost", "Südost", "Süd-Südost", "Süden", "Süd-Südwest", "Südwest", "West-Südwest", "Westen", "West-Nordwest", "Nordwest", "Nord-Nordwest"],
    mode_help: { quick: "Schnell: ganze Räume verschieben und an der Ecke größer oder kleiner ziehen – ideal für den ersten Entwurf.", precise: "Präzision: einzelne Ecken und Wände bearbeiten – für genaue Maße, Schrägen und eigene Formen. Einen Punkt in der Wandmitte antippen fügt eine Ecke ein." },
    shape_help: "Rechteck, L- oder U-Form wählen; danach wie jeden Raum verschieben und an der Ecke in der Größe ziehen. T-förmiger Raum: Rechteck anlegen, auf „Präzision“ wechseln und an den Wandmitten Ecken einfügen und ziehen, bis die T-Form steht.",
    hint_vertex_touch: "Ecke {c}: ziehen, um sie zu verschieben · zum Löschen die Ecke in den Eigenschaften entfernen.", connections: "Verbindungen", outside: "außen", add: "Hinzufügen",
    preview: "Vorschau", apply: "Übernehmen", changed_rooms: "Räume ändern sich", provenance: "Herkunft", none: "Nichts ausgewählt – Raum, Ecke oder Öffnung antippen.",
    import_failed: "Datei konnte nicht gelesen werden", help: "Antippen: Raum, Wand, Tür oder Fenster wählen · gewählten Raum ziehen: verschieben · Ziehen auf freier Fläche: Ansicht · zwei Finger: Zoom · Öffnungen entlang der Wand ziehen · Pfeiltasten verschieben · Entf löscht",
    k: { window: "Fenster", door: "Tür", roof_window: "Dachfenster", passage: "Durchgang", vent: "Lüftungsöffnung" },
    m: { unknown: "unbekannt", turn_tilt: "Dreh-Kipp", casement: "Drehflügel", tilt_only: "nur Kipp", sliding: "Schiebe", roof: "Dach", door: "Tür", fixed_vent: "feste Öffnung" },
    c: { open_passage: "offener Durchgang", door: "Tür", stairs: "Treppe", shaft: "Schacht", duct: "Kanal" }, conn_no_wall: "keine gemeinsame Wand – Luft wird hier nicht durchgezeichnet",
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
      separator: "Tippe Anfang und Ende einer Trennlinie, z. B. quer über einen offenen Durchgang.", trace: "Tippe in einen Raum der Vorlage.", window: "Tippe auf eine Außenwand, um ein Fenster zu platzieren.",
      door: "Tippe auf eine Wand zwischen zwei Räumen, um eine Tür zu platzieren.", passage: "Tippe auf eine Wand zwischen zwei Räumen, um einen offenen Durchgang (ohne Tür) zu platzieren." },
    reason: { wall: "Das ist eine Wand – bitte in den Raum tippen.", open: "Der Bereich ist nicht geschlossen (offene Tür oder Durchgang). „Lücken schließen“ erhöhen oder eine Trennlinie ziehen.",
      small: "Der Bereich ist zu klein für einen Raum.", scale: "Bitte zuerst den Maßstab festlegen." },
    e: { E_OPENING_INTERIOR: "Innentür/Durchgang liegt nicht mehr auf einer gemeinsamen Wand", E_POLY_POINTS: "zu wenige Ecken", E_LIMIT_VERTICES: "zu viele Ecken", E_POLY_NONFINITE: "ungültige Koordinate", E_POLY_DEGENERATE: "Wand zu kurz",
      E_POLY_SELF_INTERSECT: "Wände kreuzen sich", E_POLY_AREA: "Fläche zu klein", E_ROOM_OVERLAP: "überlappt einen anderen Raum", E_FLOOR_UNKNOWN: "Etage fehlt",
      E_OPENING_ROOM: "Öffnung ohne Raum", E_OPENING_EDGE: "Öffnung liegt auf keiner Wand", E_OPENING_OFFSET: "Öffnung außerhalb der Wand", E_OPENING_WIDTH: "Öffnung breiter als die Wand" },
  },
  en: {
    // v0.26.6.1 editor hotfix: plain names, short context hints and the next sensible step
    add_cancel: "Cancel", tb_room: "+ Room", tb_window: "Window", tb_door: "Door", tb_passage: "Passage", more: "More", more_title: "More tools", close: "Close", msg_close: "Close message",
    mode_label: "Editing mode", quick_title: "Quick: move and resize whole rooms", precise_title: "Precision: edit single corners, wall lengths and angles",
    hint_empty: "No room on this floor yet. Tap “+ Room”, choose the room and a shape.",
    hint_quick: "Tap a room to move it or change its size.",
    hint_precise: "Precision: tap a room – then drag its corners. A dot in the middle of a wall adds a corner, tapping a wall shows its length and angles.",
    hint_room_quick: "Drag to move the room · drag the square at the corner to resize · for your own shape use “Edit corners”.",
    hint_room_precise: "Drag the corners · tap a dot in the middle of a wall to add a corner · tap a wall for its length and angles.",
    hint_vertex: "Corner {c}: drag it or move it with the arrow keys · Del removes the corner.",
    hint_wall: "Wall {w}: enter a length and “Apply” – the chosen corner stays in place. Angles and locks are in the properties.",
    hint_opening: "Drag along the wall to move · drag the ends to change the width · assign the contact in the properties.",
    hint_adding: "Choose the room and a shape, then “Add room”. The new room appears next to the others.",
    hint_next_missing: "Next step: {n} rooms are not drawn yet – add them with “+ Room”.",
    hint_next_windows: "Next step: place windows – choose “Window” and tap an outside wall.",
    hint_next_contacts: "Next step: {n} windows/doors have no contact – tap one and assign its contact.",
    hint_next_orphans: "Please check: {n} windows/doors name a contact that is no longer set up in FreshAirIQ – tap one and choose the right contact.", contact_gone: "no longer set up",
    hint_next_save: "Everything drawn? Check it and “Save”.", hint_done: "Floor plan complete. To change something, tap a room, a wall or a window.",
    edit_sel: "Edit", selected: "Selected: {name}",
    steps_title: "Your floor plan in six steps", start_intro: "Tap “+ Room”, choose the room and a shape. Then place windows and doors on the walls and save.", step_optional: "optional", step_floor: "Choose a floor", step_rooms: "Draw the rooms", step_shape: "Adjust position and shape", step_openings: "Place windows, doors, passages", step_contacts: "Assign contacts", step_save: "Check and save",
    new_room: "New room", which_room: "Which room?", shape: "Shape", shape_precise: "Own shape", shape_precise_hint: "“Own shape” adds a rectangle and switches to Precision: then drag the corners to the right place.",
    all_placed: "All rooms are already in the floor plan. New rooms are added in the FreshAirIQ setup.",
    edit_corners: "Edit corners", corners_done: "Corners done", sec_corners: "Corners as numbers", corners_hint: "x to the right, y upwards, in metres. A value is taken when you leave the field.",
    sec_connections: "Connections without a shared wall", conn_hint: "For stairs, shafts or ducts. Doors and passages are drawn right on the wall (“Door”, “Passage”).",
    sec_place: "Position on the wall", sec_details: "More details", sec_angles: "Corner angles", sec_scale: "Set the scale", sec_building: "Building and north", sec_template: "Floor plan template (picture)",
    contacts_hint: "Which window or door contact reports this opening?", no_contacts: "No contacts are set up in FreshAirIQ yet.",
    corner_min: "A room needs at least three corners. Fix: move another corner or remove the whole room.",
    invalid_fix: "Tap the rooms marked red and correct them, then save again.", failed_fix: "Your draft is kept – check the connection and save again.",
    import_fix: "Please choose a file saved with “Export” from this editor (.json).",
    room_info: "{a} m² · {p}",
    window_inside: "This window sits on an interior wall.", window_out: "Move to the outside wall", windows_inside: "{n} windows sit on an interior wall.", windows_out: "Move all to outside walls",
    window_no_outside: "This room has no free outside wall – please move the room to the edge of the house.",
    unit_schematic: "u", wall_length_units: "Length (plan units, no scale)", scale_hint: "This floor plan is schematic – its lengths are not metres. The real length of this one wall gives the whole plan a scale.",
    scale_real: "Real length of this wall (m)", scale_placeholder: "e.g. 3.85", scale_apply: "Set scale",
    wall_length: "Length (m)", wall_fixed: "Stays in place", wall_lock: "Lock length", wall_locked: "This wall has a locked length – unlock it first.", airs: "airs", help_title: "How to use", grp_view: "View", grp_edit: "Edit", grp_rooms: "Rooms", grp_file: "File", panel_show: "Properties", panel_hide: "Drawing only", angle_locked: "This changes a locked angle (also when a corner next to it is added or removed) – unlock the angle first.",
    wall_help: "Only this wall changes its length: the chosen corner stays, the other one moves along the wall; the next wall takes up the change (the opposite wall keeps its length). Locked lengths and angles stay.",
    angle: "Angle", corner_square: "Corner {c} to 90°", corner_lock: "Lock angle at corner {c}", snap90: "Snap to 90°",
    blocked_wall: "Not possible without changing a locked length: wall {w} is locked. Fix: unlock wall {w} or keep the other corner in place.",
    blocked_corner: "Not possible without changing a locked angle: corner {c}. Fix: unlock the angle at corner {c} or keep the other corner in place.",
    corner_locked: "The angle at corner {c} is locked – unlock it first.",
    join: "Fit rooms together", join_none: "No matching walls found – push the rooms to within about 35 cm of each other.",
    join_preview: "Preview: {m} shared walls found, {r} rooms moved (none reshaped).", join_lengths: "Different lengths stay as measured (schematically partly shared): {list}.",
    join_locked: "Not laid exactly because a length or angle is locked: {list}.", join_overlap: "Still overlapping afterwards: {list} – please adjust by hand.",
    floor_names: { basement: "Basement", ground_floor: "Ground floor", upper_floor: "Upper floor", attic: "Attic", floor_3: "3rd floor", floor_4: "4th floor" },
    wall_bad_length: "Please enter a length of at least 0.1 m.", wall_conflict_shape: "This would give an invalid room shape – nothing changed.",
    wall_conflict_overlap: "The room would reach into a neighbouring room – nothing changed. Fix: keep the other corner in place, move the room first, or use “Fit rooms together” afterwards.", wall_conflict_shared: "A neighbouring room shares only part of the wall that would move – it would be bent. Keep the other corner fixed or adjust that room first.", wall_conflict_opening: "A door, window or passage would no longer fit on its wall – nothing changed.",
    door_hinge: "Hinge side", hinges: { "": "as before", left: "left", right: "right" }, door_swing: "Opens", swings: { in: "into this room", out: "to the other side" },
    interior_only: "An interior door or passage stays on the wall both rooms share – it cannot be moved there.",
    conv_door: "draw as a door", conv_passage: "draw as a passage",
    quick: "Quick", precise: "Precision", undo: "Undo", redo: "Redo", zoom_in: "Zoom in", zoom_out: "Zoom out", fit: "Fit",
    grid: "Grid", off: "off", floor: "Floor", add_room: "Add room", template: "Template", rect: "Rectangle", l: "L shape", u: "U shape",
    propose: "Propose again", missing: "Add missing rooms", export: "Export", import: "Import", save: "Save", cancel: "Discard",
    saving: "Saving …", saved: "Saved", conflict: "The floor plan was saved elsewhere in the meantime. Please export your draft and reload.",
    reload: "Reload", invalid: "The floor plan is not valid yet:", failed: "Saving failed", discard: "Discard unsaved changes?",
    delete_room: "Remove the room from the floor plan? (FreshAirIQ's room configuration stays unchanged.)", delete: "Remove", rotate: "Rotate 90°", rotate_help: "“Rotate 90°” turns the room about its centre, anticlockwise – windows and doors turn with it. Four times = as before, ↶ undoes it.",
    add_window: "Add window", add_corner: "Insert corner", corner: "Corner", x: "x (m)", y: "y (m)", area: "Area", room: "Room", opening: "Opening",
    kind: "Kind", mechanics: "Mechanism", width: "Width (m)", contacts: "Contacts", wall: "Wall", position: "Position", building: "Building",
    north: "Which compass direction does the top of your plan face?", north_confirmed: "North direction checked", north_help: "This tells FreshAirIQ from which direction sun and wind reach your house. Align the drawing with a site plan or a map.", north_examples: "0° = top is north · 90° = top is east · 180° = top is south · 270° = top is west", north_now: "The top faces roughly {dir} ({deg}°).", north_drag: "Drag the “N” arrow or enter the angle. With a floor plan template: “More” → north arrow from the template.", north_confirmed_help: "Only confirm once the direction was checked against a reliable source (site plan, map, compass). Only then are facades, sun and wind calculated by direction.", north_keep: "The rooms are not rotated.",
    dirs: ["north", "north-northeast", "northeast", "east-northeast", "east", "east-southeast", "southeast", "south-southeast", "south", "south-southwest", "southwest", "west-southwest", "west", "west-northwest", "northwest", "north-northwest"],
    mode_help: { quick: "Quick: move whole rooms and drag a corner to make them bigger or smaller – ideal for a first draft.", precise: "Precision: edit single corners and walls – for exact sizes, slanted walls and your own shapes. Tapping a dot in the middle of a wall adds a corner." },
    shape_help: "Choose a rectangle, L or U shape; then move it like any room and drag its corner to resize. A T-shaped room: add a rectangle, switch to “Precision” and add corners at the middle of the walls, then drag them until the T stands.",
    hint_vertex_touch: "Corner {c}: drag it to move it · to delete it, remove the corner in the properties.", connections: "Connections", outside: "outside", add: "Add",
    preview: "Preview", apply: "Apply", changed_rooms: "rooms change", provenance: "Origin", none: "Nothing selected – tap a room, corner or opening.",
    import_failed: "The file could not be read", help: "Tap: choose a room, wall, door or window · drag the chosen room: move · drag empty space: view · two fingers: zoom · drag openings along the wall · arrow keys move · Del deletes",
    k: { window: "Window", door: "Door", roof_window: "Roof window", passage: "Passage", vent: "Vent" },
    m: { unknown: "unknown", turn_tilt: "Turn-tilt", casement: "Casement", tilt_only: "Tilt only", sliding: "Sliding", roof: "Roof", door: "Door", fixed_vent: "Fixed vent" },
    c: { open_passage: "open passage", door: "Door", stairs: "Stairs", shaft: "Shaft", duct: "Duct" }, conn_no_wall: "no shared wall – air is not drawn through here",
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
      separator: "Tap the start and end of a separator line, e.g. across an open passage.", trace: "Tap inside a room of the template.", window: "Tap an outside wall to place a window.",
      door: "Tap a wall between two rooms to place a door.", passage: "Tap a wall between two rooms to place an open passage (no door)." },
    reason: { wall: "That is a wall – please tap inside the room.", open: "The area is not closed (open door or passage). Increase 'Close gaps' or draw a separator.",
      small: "The area is too small for a room.", scale: "Please set the scale first." },
    e: { E_OPENING_INTERIOR: "interior door/passage is no longer on a shared wall", E_POLY_POINTS: "too few corners", E_LIMIT_VERTICES: "too many corners", E_POLY_NONFINITE: "invalid coordinate", E_POLY_DEGENERATE: "wall too short",
      E_POLY_SELF_INTERSECT: "walls cross", E_POLY_AREA: "area too small", E_ROOM_OVERLAP: "overlaps another room", E_FLOOR_UNKNOWN: "floor missing",
      E_OPENING_ROOM: "opening without room", E_OPENING_EDGE: "opening on no wall", E_OPENING_OFFSET: "opening outside its wall", E_OPENING_WIDTH: "opening wider than its wall" },
  },
};

// v0.26.6.1 editor hotfix: the texts, exported for the language checks of the tests
export const EDITOR_TEXT = L;
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
// 0.26.6.1(2): locked walls (room.locked_walls = edge indices) follow an inserted (+1) or removed (−1) corner
export const shiftLocks = (room, index, delta) => {
  if (!room || !Array.isArray(room.locked_walls)) return;
  room.locked_walls = room.locked_walls.map(i => (i > index ? i + delta : i));
};
// 0.26.6.1(10): locked angles (room.locked_corners = corner indices) follow an inserted (+1) or removed (−1) corner
export const shiftCornerLocks = (room, index, delta) => {
  if (!room || !Array.isArray(room.locked_corners)) return;
  room.locked_corners = room.locked_corners.map(i => (i > index ? i + delta : i));
};
// True when a locked wall of any room changed its length (or its room lost corners) between two layouts.
export const wallBroken = (before, after) => (after.rooms || []).some(r => {
  const old = (before.rooms || []).find(x => x.id === r.id);
  if (!old || !(r.locked_walls || []).length) return false;
  if (old.polygon.length !== r.polygon.length) {  // a corner added or removed: each locked wall must still be there unchanged
    const same = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < 0.002, n = r.polygon.length, m = old.polygon.length;
    return r.locked_walls.some(i => !old.polygon.some((p, j) => same(p, r.polygon[i]) && same(old.polygon[(j + 1) % m], r.polygon[(i + 1) % n])));
  }
  return r.locked_walls.some(i => Math.abs(G.edgeLength(old.polygon, i) - G.edgeLength(r.polygon, i)) > 0.002);
});
// Hotfix after review (F04): a locked angle is followed by its geometric corner, not only by its index – a corner
// inserted or removed elsewhere shifts the indices, and an inserted corner next to it changes the angle while the
// corner itself stays where it was. Every corner locked before must still exist (same place, or the same index
// while the corner count is unchanged, e.g. dragged) with the same angle (within 0.3°); a locked corner that is
// gone is a broken lock too.
const SAME_POINT = 0.002;
const cornerAt = (pts, p) => pts.findIndex(q => Math.hypot(q[0] - p[0], q[1] - p[1]) < SAME_POINT);
export const angleBroken = (before, after) => (before.rooms || []).some(old => {
  const r = (after.rooms || []).find(x => x.id === old.id);
  if (!r || !(old.locked_corners || []).length) return false;
  return old.locked_corners.some(i => {
    if (!(i >= 0 && i < old.polygon.length)) return false;
    let j = cornerAt(r.polygon, old.polygon[i]);
    if (j < 0 && r.polygon.length === old.polygon.length) j = i;   // the locked corner itself was moved
    return j < 0 || Math.abs(G.cornerAngle(old.polygon, i) - G.cornerAngle(r.polygon, j)) > 0.3;
  });
});
export const lockBroken = (before, after) => wallBroken(before, after) || angleBroken(before, after);
// The message for a refused change: a locked length or a locked angle
export const lockMessage = (before, after) => (wallBroken(before, after) ? "wall_locked" : "angle_locked");
// 0.26.6.1 UI hotfix (F01): the room an opening links to in a layout (null = none / outside)
export const linkOf = (layout, id) => {
  const o = (layout.openings || []).find(x => x.id === id), room = o && (layout.rooms || []).find(r => r.id === o.room_id);
  const other = room && G.openingLink(layout.rooms, room, o);
  return other ? other.id : null;
};
// An interior opening that linked two rooms and – changed itself (wall, position, width or kind) – no longer does.
// A change of the rooms around it is checked when saving (E_OPENING_INTERIOR for doors placed as interior).
export const linksLost = (before, after) => (after.openings || []).some(o => {
  const old = (before.openings || []).find(x => x.id === o.id);
  if (!old || old.room_id !== o.room_id || !(old.kind === "door" || old.kind === "passage" || old.interior === true)) return false;
  if (["edge", "offset", "width_m", "kind"].every(k => old[k] === o[k])) return false;
  const was = linkOf(before, o.id);
  return !!was && linkOf(after, o.id) !== was;
});
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

// WCAG relative luminance and contrast of rgb()/rgba() colours
const rgb = text => { const m = /rgba?\(([^)]+)\)/.exec(String(text || "")); if (!m) return null; const v = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; };
export const luminance = c => { const f = x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
export const contrast = (a, b) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
const STYLE = `
:host{--ed-bg:var(--card-background-color,var(--ha-card-background,#ffffff));--ed-fg:var(--primary-text-color,#1b1f23);--ed-muted:var(--secondary-text-color,#4a5560);--ed-line:var(--divider-color,#8c96a0);--ed-accent:var(--primary-color,#0b6ea8);--ed-on-accent:var(--text-primary-color,#ffffff);--ed-canvas:var(--secondary-background-color,#eef2f5);
display:flex;flex-direction:column;container-type:inline-size;box-sizing:border-box;height:100%;min-height:560px;background:var(--ed-bg);color:var(--ed-fg);font-size:15px;line-height:1.4}
/* v0.26.6.1: a theme whose text and background do not contrast enough gets a checked palette (see _checkContrast) */
:host([data-palette="dark"]){--ed-bg:#13202b;--ed-fg:#f2f6f9;--ed-muted:#c3ced6;--ed-line:#6b8090;--ed-canvas:#0c1720}
:host([data-palette="light"]){--ed-bg:#ffffff;--ed-fg:#1b1f23;--ed-muted:#454f59;--ed-line:#7d8892;--ed-canvas:#eef2f5}
:host([data-accent="fallback"]){--ed-accent:#0b6ea8;--ed-on-accent:#ffffff}
.bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px}
.msg,.help{flex:none}
button,select,input{font:inherit;color:inherit}
button{cursor:pointer;border-radius:14px;border:1px solid var(--ed-line);background:var(--ed-bg);color:var(--ed-fg);padding:6px 12px;min-height:44px;min-width:44px;font-size:15px}
button:hover:not(:disabled){border-color:var(--ed-accent)}
button[aria-pressed="true"]{background:var(--ed-accent);color:var(--ed-on-accent);border-color:var(--ed-accent);font-weight:700;box-shadow:inset 0 0 0 2px var(--ed-on-accent)}
button:disabled{cursor:not-allowed;opacity:.55;border-style:dashed}
button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid var(--ed-accent);outline-offset:2px}
button.primary{background:var(--ed-accent);color:var(--ed-on-accent);border-color:transparent}
select,input{background:var(--ed-bg);color:var(--ed-fg);border:1px solid var(--ed-line);border-radius:8px;padding:6px;min-height:40px;font-size:15px}
label{color:var(--ed-fg)}
.join-ghost{fill:rgba(64,200,255,.08);stroke:#40c8ff;pointer-events:none}.join-shared{stroke:#7dff9a;stroke-linecap:round;pointer-events:none}
.angles{display:grid;gap:6px;margin-top:8px}.corner-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.canvas{border-radius:12px;background:var(--ed-canvas);touch-action:none;user-select:none;-webkit-user-select:none}
.canvas:focus{outline:none}.canvas:focus-visible{outline:2px solid var(--ed-accent)}
.guide{stroke:var(--ed-accent);pointer-events:none} .wall{pointer-events:none;stroke:var(--ed-fg)} .symbol .sym{stroke:var(--ed-fg)} .symbol .halo,.symbol .gap{stroke:var(--ed-bg)}
svg{display:block;width:100%;height:100%}
.wbox{display:flex;gap:4px;align-items:center}.wbox input{width:auto;flex:1 1 4em;min-width:3.5em}
.room{fill:var(--ed-accent);fill-opacity:.18;stroke:var(--ed-fg);cursor:move}
.room.sel{fill-opacity:.32;stroke:var(--ed-accent)}
.room.err{stroke:var(--error-color,#db4437);fill:var(--error-color,#db4437);fill-opacity:.2}
.other{fill:none;stroke:var(--ed-muted);opacity:.35;pointer-events:none}
.handle{fill:var(--ed-bg);stroke:var(--ed-accent);cursor:grab}
.handle.sel{fill:var(--ed-accent)} .handle.hit{fill:transparent;stroke:none} .dot{fill:var(--ed-bg);stroke:var(--ed-accent);pointer-events:none} .dot.sel{fill:var(--ed-accent)}
.mid{fill:var(--ed-accent);opacity:.55;cursor:copy}
.op{stroke:var(--success-color,#43a047);stroke-linecap:round;cursor:ew-resize}
.op.sel{stroke:var(--warning-color,#ffa600)} .op.err{stroke:var(--error-color,#db4437)}
.conn.logical line{stroke:var(--ed-muted)} .conn .conn-mark{fill:#fff;stroke:var(--ed-fg)} .conn.loose line,.conn.loose .conn-mark{stroke:var(--warning-color,#ffa600)}
.op.inner{stroke:var(--info-color,#039be5)} .op.inner.sel{stroke:var(--warning-color,#ffa600)} .wh{cursor:ew-resize}
text{fill:var(--ed-fg);pointer-events:none}
.err-text{fill:var(--error-color,#db4437);font-weight:600}
.grid line{stroke:var(--ed-line)}
.panel{margin-top:8px;padding:12px;border:1px solid var(--ed-line);border-radius:12px;font-size:14px;display:grid;gap:10px;background:var(--ed-bg);color:var(--ed-fg)}
.panel h4{margin:0}
.fields{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,180px),1fr));gap:6px}
.vertex{display:grid;grid-template-columns:auto 1fr 1fr auto;gap:4px;align-items:center}
.msg{padding:8px;border-radius:10px;border:1px solid var(--ed-line)} .msg.err{border-color:var(--error-color,#db4437)}
.help{font-size:14px;color:var(--ed-muted)}
.ul{pointer-events:none}
.hitwall,.hitop{cursor:pointer} .wallsel{stroke:var(--ed-accent);stroke-linecap:round;pointer-events:none}
.measure{font-weight:600;paint-order:stroke;stroke:var(--ed-bg)} .measure.big{font-weight:800}
.corner{fill:var(--ed-bg);stroke:var(--ed-accent);pointer-events:none} .corner.fixed{fill:var(--ed-accent)} .cornerno{font-weight:700}
/* v0.26.6.1 editor hotfix: a fixed workspace. The drawing gets a size from the layout alone – never from the content
   of the properties, a message or a hint: messages and hints float over the drawing, the properties scroll on their own.
   data-layout (set from the editor's own size, _applyLayout): "side" = properties beside the drawing (wide editors and
   short landscape screens), otherwise below it in a fixed share; "short" = little height; "phone" = a narrow screen. */
.work{flex:1 1 auto;min-height:0;display:grid;gap:10px;grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,3fr) minmax(0,2fr)}
.work.nopanel{grid-template-rows:minmax(0,1fr) auto}.work.nopanel .aside{display:none}
.draw{position:relative;display:flex;flex-direction:column;min-height:0;min-width:0}
.canvas{flex:1 1 auto;min-height:160px}
.side{display:flex;flex-direction:column;gap:8px;min-height:0;min-width:0}
.aside{flex:1 1 auto;display:grid;grid-template-columns:minmax(0,1fr);gap:8px;align-content:start;min-height:0;overflow:auto;overscroll-behavior:contain}
.work .panel{margin-top:0}
.bar.final{flex:none;margin:0;padding:6px 0 0;background:var(--ed-bg);border-top:1px solid var(--ed-line);display:flex;gap:8px;align-items:center}
.bar.final .grow{flex:1 1 auto}
.ptoggle{display:inline-flex;align-items:center}
:host([data-layout~="side"]) .work{grid-template-columns:minmax(0,1fr) clamp(280px,34%,360px);grid-template-rows:minmax(0,1fr)}
:host([data-layout~="side"]) .work.nopanel .aside{display:grid}
:host([data-layout~="side"]) .ptoggle{display:none}
:host([data-layout~="short"]) .tools{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:thin}
:host([data-layout~="short"]) .tools>*{flex:none}
:host([data-layout~="phone"]) .tools{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px}
:host([data-layout~="phone"]) .tg-add{grid-column:1/-1;display:flex;gap:4px}
:host([data-layout~="phone"]) .tg-add>button{flex:1 1 auto;padding:6px 4px;font-size:14px;min-width:0}
:host([data-layout~="phone"]) .bar.final{gap:6px}:host([data-layout~="phone"]) .bar.final>button{padding:6px 8px}
/* toolbar: floor, mode, what can be added, more */
.tools{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin-bottom:8px;flex:none}
.tg{display:flex;gap:4px;align-items:center;flex-wrap:nowrap}
.tg-floor label{display:flex;gap:6px;align-items:center;min-width:0}.tg-floor select{min-width:0;max-width:220px}
:host([data-layout~="phone"]) .tg-floor select{max-width:none;width:100%}
.seg{display:inline-flex;border:1px solid var(--ed-line);border-radius:14px;overflow:hidden}
.seg>button{border:0;border-radius:0;margin:0}
.seg>button+button{border-left:1px solid var(--ed-line)}
.tg-add>button{white-space:nowrap}
.tools .more-btn{margin-left:auto}
/* floating over the drawing: hint and messages (top), undo/redo (bottom left), zoom (bottom right), the "more" menu */
.ov{position:absolute;z-index:2}
.ov-top{top:8px;left:8px;right:8px;display:grid;gap:6px;justify-items:start;pointer-events:none;max-height:calc(100% - 76px);overflow:auto}
.ov-top>*{pointer-events:auto;max-width:100%;box-sizing:border-box}
.hint{background:var(--ed-bg);color:var(--ed-fg);border:1px solid var(--ed-line);border-left:4px solid var(--ed-accent);border-radius:10px;padding:6px 10px;font-size:14px;box-shadow:0 1px 4px rgba(0,0,0,.18)}
.hint button{margin-left:6px}
.ov-top .msg{background:var(--ed-bg);box-shadow:0 1px 4px rgba(0,0,0,.18)}
.msg .x{float:right;margin:-4px -4px 0 8px}
.ov-bl{left:8px;bottom:8px;display:flex;gap:4px}.ov-br{right:8px;bottom:8px;display:flex;gap:4px}
.ov-bl button,.ov-br button{box-shadow:0 1px 4px rgba(0,0,0,.18)}
.menu{top:8px;right:8px;width:min(320px,calc(100% - 16px));max-height:calc(100% - 72px);overflow:auto;box-sizing:border-box;background:var(--ed-bg);color:var(--ed-fg);border:1px solid var(--ed-line);border-radius:12px;padding:10px;display:grid;gap:8px;box-shadow:0 4px 16px rgba(0,0,0,.28)}
.menu[hidden]{display:none}
.menu h4{margin:0}.menu .row{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.menu .row>button{flex:1 1 auto}
/* properties: what matters for the chosen object first, the rest in sections that open on demand */
.panel.selected{border-left:4px solid var(--ed-accent)}
.panel .sub{color:var(--ed-muted);font-size:14px}
.sec{border-top:1px solid var(--ed-line);padding-top:4px}
.sec>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-weight:700;list-style:none}
.sec>summary::-webkit-details-marker{display:none}
.sec>summary::before{content:"▸";display:inline-block;width:1.2em;color:var(--ed-muted)}
.sec[open]>summary::before{content:"▾"}
.sec>.body{display:grid;gap:8px;padding:2px 0 8px}
.checks{display:grid;gap:2px}.checks label{display:flex;gap:8px;align-items:center;min-height:44px}
.checks input{width:22px;height:22px;min-height:0;margin:0}
.danger{border-color:var(--error-color,#db4437)}
.shapes{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:6px}
.shapes button{display:grid;justify-items:center;gap:2px;padding:6px}
.shapes svg{width:40px;height:30px}.shapes svg path{fill:none;stroke:currentColor;stroke-width:2}
.steps{margin:0;padding:0;list-style:none;display:grid;gap:4px}
.steps li{display:flex;gap:8px;align-items:center;min-height:28px}
.steps .n{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;border:1px solid var(--ed-line);font-size:14px;flex:none}
.steps li.done .n{background:var(--ed-accent);color:var(--ed-on-accent);border-color:var(--ed-accent)}
.steps li.next{font-weight:700}
.panel>.sec:first-child{border-top:0;padding-top:0}
.aside .panel,.sec>.body{grid-template-columns:minmax(0,1fr)}.aside .panel>*{min-width:0}
.aside input:not([type=checkbox]),.aside select{max-width:100%;min-width:0;box-sizing:border-box}.vertex input{width:100%}
.checks label>span,.panel h4,.sub,.msg,.hint{overflow-wrap:anywhere}
input[type=checkbox]{min-height:0;width:22px;height:22px;padding:0;margin:0 6px 0 0;vertical-align:middle;accent-color:var(--ed-accent)}
label:has(>input[type=checkbox]){display:inline-flex;align-items:center;min-height:44px}
button[aria-expanded="true"].more-btn{border-color:var(--ed-accent);box-shadow:inset 0 0 0 2px var(--ed-accent)}
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
    this._open = {}; this._shape = "rect"; this._menu = false; this._adding = false;  // v0.26.6.1 editor hotfix: sections, new-room shape, menu
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
    // a field or button the user moves to takes the keyboard; a tap on the drawing gives it back (_down)
    this._onFocusIn = ev => { this._kbd = !!(ev.target && ev.target.classList && ev.target.classList.contains("canvas")); };
    this.shadowRoot.addEventListener("focusin", this._onFocusIn);
    // v0.26.6.1: the drawing follows the size of the editor (window, rotation, inspector) – the plan stays in view
    if (typeof ResizeObserver === "function") { this._resizeObs = new ResizeObserver(() => this._onResize()); this._resizeObs.observe(this); }
    this._checkContrast();
  }
  disconnectedCallback() {
    this.shadowRoot.removeEventListener("keydown", this._onKey);
    this.shadowRoot.removeEventListener("focusin", this._onFocusIn);
    if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
    for (const url of Object.values(this._ulUrl)) URL.revokeObjectURL(url);
    this._ulUrl = {}; this._ul = {}; this._pix = {};
  }
  // v0.26.6.1: text must stay readable in every Home Assistant theme – a theme whose text, muted text or accent
  // colours contrast too little with the editor background (WCAG AA: 4.5:1 for text) gets a checked palette
  _checkContrast() {
    if (typeof getComputedStyle !== "function") return;
    this.removeAttribute("data-palette"); this.removeAttribute("data-accent");
    const probe = document.createElement("span");
    probe.style.cssText = "position:absolute;visibility:hidden;color:var(--ed-fg);background:var(--ed-bg);border-color:var(--ed-muted);outline-color:var(--ed-accent);caret-color:var(--ed-on-accent)";
    this.shadowRoot.appendChild(probe);
    const read = () => { const c = getComputedStyle(probe); return [c.color, c.backgroundColor, c.borderTopColor, c.outlineColor, c.caretColor].map(rgb); };
    let [fg, bg, muted, accent, onAccent] = read();
    if (!bg || bg[3] < 0.5) bg = luminance(fg || [0, 0, 0]) > 0.5 ? [16, 24, 32, 1] : [255, 255, 255, 1];   // no opaque background: assume the opposite of the text
    if (!fg || !muted || contrast(fg, bg) < 4.5 || contrast(muted, bg) < 4.5) this.setAttribute("data-palette", luminance(bg) < 0.25 ? "dark" : "light");
    [fg, bg, muted, accent, onAccent] = read();
    if (!accent || !onAccent || contrast(onAccent, accent) < 4.5 || (bg && bg[3] >= 0.5 && contrast(accent, bg) < 3)) this.setAttribute("data-accent", "fallback");
    probe.remove();
  }
  _t(k) { return L[this._lang][k] != null ? L[this._lang][k] : k; }
  _msgWs(type, extra = {}) { const m = Object.assign({ type }, extra); if (this._entryId) m.entry_id = this._entryId; return m; }

  // ------------------------------------------------------------------ state changes
  _commit(mutator, { force = false } = {}) {
    const future = this._history.future;
    this._modeHint = false;
    this._history.push(this._layout);
    mutator(this._layout);
    const before = this._history.past[this._history.past.length - 1];
    // 0.26.6.1(2): a locked wall keeps its length; UI hotfix (F01): an interior door stays on its shared wall
    const refused = force ? null : lockBroken(before, this._layout) ? lockMessage(before, this._layout) : linksLost(before, this._layout) ? "interior_only" : null;
    if (refused) {
      this._layout = this._history.past.pop(); this._history.future = future;
      this._msg = { err: true, text: this._t(refused) }; this._render(); return;
    }
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
    // v0.26.6.1: the plan fills the drawing area of the real shape (wide or tall), with a margin – fully visible
    const a = this._aspect || 0.75, spanX = Math.max(box.maxX - box.minX, 4), spanY = Math.max(box.maxY - box.minY, 4);
    // v0.26.6.1 editor hotfix: the plan sits between the hint on top and the buttons at the bottom (both float over it)
    const svg = this.shadowRoot.querySelector("svg"), sb = svg && svg.getBoundingClientRect(), top = this.shadowRoot.querySelector(".ov-top");
    const band = sb && sb.height > 160 && sb.width > 0 ? { top: Math.min(top ? top.getBoundingClientRect().height + 8 : 0, sb.height * 0.3), bottom: Math.min(60, sb.height * 0.2), h: sb.height, w: sb.width } : null;
    const free = band ? (band.h - band.top - band.bottom) / band.w : a;
    const size = Math.max(spanX * 1.15, (spanY * 1.15) / free, spanX, spanY / a);
    const shift = band ? ((band.top - band.bottom) / 2) * (size / band.w) : 0;
    this._view = { cx: (box.minX + box.maxX) / 2, cy: (box.minY + box.maxY) / 2 + shift, size };
  }
  _viewBox() {
    if (!this._view) this._fit();
    const v = this._view, w = v.size, h = v.size * (this._aspect || 0.75);
    return [v.cx - w / 2, -v.cy - h / 2, w, h];
  }
  // v0.26.6.1: "Fit" stays on (refits when the editor is resized) until the user zooms or moves the view
  _zoom(factor) { if (!this._view) this._fit(); this._autoFit = false; this._view.size = Math.min(Math.max(this._view.size * factor, 1), 2000); this._render(); }
  // v0.26.6.1 editor hotfix: the layout follows the editor's own size – properties beside the drawing on a wide editor
  // and on a short landscape screen (844 × 390), below it in a fixed share otherwise. Nothing inside decides a size.
  _applyLayout() {
    const b = this.getBoundingClientRect();
    if (!(b.width > 0)) return;
    const short = b.height > 0 && b.height < 600, side = b.width >= 860 || (short && b.width >= 600 && b.width > b.height);
    const value = [side ? "side" : "stack", short ? "short" : "", !side && b.width < 480 ? "phone" : ""].filter(Boolean).join(" ");
    if (this.getAttribute("data-layout") !== value) this.setAttribute("data-layout", value);
  }
  _isNarrow() { const w = this.getBoundingClientRect().width; return w > 0 ? !(this.getAttribute("data-layout") || "").includes("side") : null; }
  _onResize() {
    this._applyLayout();
    this._syncAspect(true);
  }
  // the drawing's shape (height / width) for the view box; refitted while "Fit" is on
  _syncAspect(draw) {
    const svg = this.shadowRoot.querySelector("svg"), box = svg && svg.getBoundingClientRect();
    if (!box || box.width < 10 || box.height < 10) return;
    const aspect = Math.min(Math.max(box.height / box.width, 0.3), 3);
    if (Math.abs(aspect - (this._aspect || 0)) < 0.005 && (this._autoFit === false || !draw)) return;
    this._aspect = aspect;
    if (this._autoFit !== false) this._fit();
    this._renderCanvas();
  }
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
    this._kbd = true;
    const canvas = this.shadowRoot.querySelector(".canvas");
    if (canvas && this.shadowRoot.activeElement !== canvas) { try { canvas.focus({ preventScroll: true }); } catch (_) { /* old engine */ } }
    ev.currentTarget.setPointerCapture(ev.pointerId);
    this._pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
    if (this._pointers.size === 2) { this._drag = { kind: "pinch", dist: this._pinchDist(), size: this._view.size }; return; }
    const start = this._plan(ev);
    if (this._tool) { this._drag = { kind: "pan", start: [ev.clientX, ev.clientY], view: Object.assign({}, this._view), tap: start }; return; }
    if (!target) { this._drag = { kind: "pan", start: [ev.clientX, ev.clientY], view: Object.assign({}, this._view) }; return; }
    const k = target.dataset.k, id = target.dataset.id, index = Number(target.dataset.i);
    // 0.26.6.1(2): a tap chooses a room, door, window or wall; a finger moving over one that is not chosen yet (or
    // over a wall) moves the view – the plan only changes for what was chosen first (no change while scrolling)
    const touch = ev.pointerType === "touch" || ev.pointerType === "pen";
    const chosen = this._sel && this._sel.id === id && (k === "room" ? this._sel.type === "room" : k === "op" ? this._sel.type === "opening" : true);
    if (k === "wall" || (touch && (k === "room" || k === "op") && !chosen)) {
      const tapSel = k === "room" ? { type: "room", id } : this._pickAt(start);
      this._drag = { kind: "pan", start: [ev.clientX, ev.clientY], view: Object.assign({}, this._view), tapSel };
      return;
    }
    if (k === "mid") {
      if ((this._room(id).locked_walls || []).includes(index)) { this._msg = { err: true, text: this._t("wall_locked") }; this._render(); return; }
      this._history.push(this._layout);
      const r = this._room(id);
      r.polygon = insertVertex(r.polygon, index);
      this._layout.openings = shiftOpenings(this._layout.openings, id, index, 1);
      shiftLocks(r, index, 1); shiftCornerLocks(r, index, 1);
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
    if (d.kind === "pinch") { if (this._pointers.size === 2) { this._autoFit = false; this._view.size = Math.min(Math.max(d.size * d.dist / this._pinchDist(), 1), 2000); this._renderCanvas(); } return; }
    if (d.kind === "pan") {
      const u = this._unit();
      if (Math.hypot(ev.clientX - d.start[0], ev.clientY - d.start[1]) >= 8) this._autoFit = false;
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
      // 0.26.5.5: snap onto a neighbour's wall line (12 px), show the guide; never onto another room
      const others = this._floorRooms().filter(r => r.id !== base.id && r.polygon.length >= 3);
      let moved = translate(base.polygon, sx, sy);
      const snapTo = G.snapToNeighbours(moved, others, 12 * this._unit());
      moved = translate(moved, snapTo.dx, snapTo.dy).map(p => [G.round3(p[0]), G.round3(p[1])]);
      this._guides = snapTo;
      if (!others.some(r => G.polygonsOverlap(moved, r.polygon))) room.polygon = moved;
    } else if (d.kind === "v") {
      let pt = [G.round3(this._snap(base.polygon[d.index][0] + dx)), G.round3(this._snap(base.polygon[d.index][1] + dy))];
      if (this._snap90) {  // 0.26.6.1(10): near 90° the corner snaps onto the exact right angle
        const n = base.polygon.length, sn = G.snapRightAngle(base.polygon[(d.index - 1 + n) % n], pt, base.polygon[(d.index + 1) % n]);
        if (sn) pt = sn;
      }
      room.polygon[d.index] = pt;
    } else if (d.kind === "scale") {
      const box = G.bbox([base.polygon]), anchor = [box.minX, box.minY];
      const w = Math.max(box.maxX - box.minX, 0.1), h = Math.max(box.maxY - box.minY, 0.1);
      const nw = Math.max(this._snap(w + dx), 0.3), nh = Math.max(this._snap(h + dy), 0.3);
      room.polygon = scaleTo(base.polygon, anchor, nw / w, nh / h);
    } else if (d.kind === "op" || d.kind === "ow") {
      // 0.26.6.1 UI hotfix (F01): an interior door or passage only moves or widens along the wall both rooms
      // share – a position off it is not taken (no silent change into an outside door)
      const o = this._layout.openings.find(x => x.id === d.id), was = linkOf(d.before, d.id);
      const next = Object.assign({}, o);
      if (d.kind === "op") { const hit = G.nearestEdge(room.polygon, p); next.edge = hit.index; next.offset = G.round3(Math.min(Math.max(hit.t, 0.02), 0.98)); }
      else next.width_m = openingWidthAt(room.polygon, o, p, this._grid);
      if (was && (G.openingLink(this._layout.rooms, room, next) || {}).id !== was) { d.refused = true; this._renderCanvas(); return; }
      Object.assign(o, next, { provenance: "user" });
    }
    if (!isOpening) room.provenance = "user";
    this._renderCanvas();
  }
  _up(ev) {
    this._pointers.delete(ev.pointerId);
    const d = this._drag;
    this._drag = null;
    this._guides = null;
    if (d && d.tap && Math.hypot(ev.clientX - d.start[0], ev.clientY - d.start[1]) < 8) { this._toolTap(d.tap); return; }
    if (d && d.tapSel) { if (Math.hypot(ev.clientX - d.start[0], ev.clientY - d.start[1]) < 8) { this._sel = d.tapSel; this._msg = null; this._render(); } return; }
    if (!d || d.kind === "pan" || d.kind === "pinch") return;
    if (d.moved && (d.kind === "v" || d.kind === "scale") && lockBroken(d.before, this._layout)) {
      const key = lockMessage(d.before, this._layout);
      this._layout = d.before; this._history.past.pop(); this._msg = { err: true, text: this._t(key) }; this._render(); return;
    }
    if (d.refused) this._msg = { err: true, text: this._t("interior_only") };
    if (!d.moved) this._history.past.pop();
    else this._dirty = true;
    this._render(); // selection and inspector follow after the gesture
  }
  _key(ev) {
    const mod = ev.ctrlKey || ev.metaKey;
    if (mod && ev.key.toLowerCase() === "z") { ev.preventDefault(); if (ev.shiftKey) this._redo(); else this._undo(); return; }
    if (mod && ev.key.toLowerCase() === "y") { ev.preventDefault(); this._redo(); return; }
    if (ev.target && /INPUT|SELECT|TEXTAREA/.test(ev.target.tagName)) return;
    if (ev.key === "Escape") { this._sel = null; this._menu = false; this._adding = false; this._setTool(null); this._render(); return; }  // v0.26.6.1: also ends a tool
    // hotfix 0.26.6.1: geometry keys only act while the drawing has the keyboard – a button, a field or another
    // control keeps its own keys (arrows in a select, Backspace on a button) and never moves or deletes a room
    const origin = (ev.composedPath && ev.composedPath()[0]) || ev.target;
    if (!(origin && origin.closest && origin.closest(".canvas"))) return;
    if ((ev.key === "Delete" || ev.key === "Backspace") && this._sel) { ev.preventDefault(); this._deleteSelected(); return; }
    const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[ev.key];
    if (step && this._sel && (this._sel.type === "room" || this._sel.type === "vertex")) {
      ev.preventDefault();  // never scrolls the page while a room is selected
      const s = (this._grid || 0.1) * (ev.shiftKey ? 10 : 1);  // 0.26.5.5: Shift = ten grid steps
      const sel = this._sel;
      this._commit(l => {
        const r = l.rooms.find(x => x.id === sel.id);
        if (!r) return;
        if (sel.type === "vertex") r.polygon[sel.index] = [G.round3(r.polygon[sel.index][0] + step[0] * s), G.round3(r.polygon[sel.index][1] + step[1] * s)];
        else r.polygon = translate(r.polygon, step[0] * s, step[1] * s).map(p => [G.round3(p[0]), G.round3(p[1])]);
        r.provenance = "user";
      });
    }
  }
  _deleteSelected() {
    const sel = this._sel;
    if (sel.type === "vertex") {
      const room = this._room(sel.id);
      if (!room) return;
      if (room.polygon.length <= 3) { this._msg = { err: true, text: this._t("corner_min") }; this._render(); return; }  // v0.26.6.1: say why
      this._commit(l => { const r = l.rooms.find(x => x.id === sel.id); r.polygon.splice(sel.index, 1); shiftLocks(r, sel.index, -1); if (r.locked_corners) { r.locked_corners = r.locked_corners.filter(i => i !== sel.index); if (!r.locked_corners.length) delete r.locked_corners; } shiftCornerLocks(r, sel.index, -1); l.openings = shiftOpenings(l.openings, sel.id, sel.index - 1, -1).map(o => (o.room_id === sel.id ? Object.assign({}, o, { edge: Math.min(o.edge, r.polygon.length - 1) }) : o)); });
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
  _addRoom(key, shape) {
    const meta = this._rooms.find(r => r.key === key);
    if (!meta) return;
    // v0.26.6.1 editor hotfix: "own shape" starts as a rectangle in Precision mode – the corners are then dragged
    const template = TEMPLATES[shape] ? shape : "rect";
    if (shape === "precise") this._mode = "precise";
    this._adding = false;
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
      this._msg = { err: true, conflict: code === "revision_conflict", text: code === "revision_conflict" ? this._t("conflict") : `${this._t("failed")}: ${esc(err && (err.message || code))}. ${esc(this._t("failed_fix"))}` };
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
      } catch (_) { this._msg = { err: true, text: `${this._t("import_failed")}. ${this._t("import_fix")}` }; this._render(); }
    };
    reader.readAsText(file);
  }
  _cancel() {
    if (this._dirty && !window.confirm(this._t("discard"))) return;
    this.dispatchEvent(new CustomEvent("freshairiq-house-editor-done", { detail: { saved: false } }));
  }
  _issueText(issues) {
    const names = id => { const r = this._room(id); const meta = r && this._rooms.find(m => m.key === r.room_key); return esc((meta && meta.name) || id); };
    return `${this._t("invalid")}<br>${issues.slice(0, 8).map(i => `${names(i.id)}: ${esc(this._t("e")[i.code] || i.code)}`).join("<br>")}<br>${esc(this._t("invalid_fix"))}`;
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
    // v0.26.6.1 editor hotfix: one section, open while one of its tools is in use
    const wrap = body => `<div class="panel">${this._sec("template", t("sec_template"), body, !!(this._tool && !["window", "door", "passage"].includes(this._tool)) || !!this._calib || !!this._trace)}</div>`;
    if (!u) return wrap(`<div class="chips">${upload}</div><div class="help">${t("ul_hint")}</div>`);
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
    return wrap(`<div class="chips">${tools}</div>${detail}<div class="help">${scale}</div>
      <div class="chips"><label><input type="checkbox" data-f="ul_show"${this._showUl ? " checked" : ""}> ${t("ul_show")}</label>
        <label>${t("ul_opacity")} <input type="range" min="0.1" max="1" step="0.05" data-f="ul_opacity" value="${u.opacity}"></label>
        <label>${t("ul_close")} <input type="range" min="0" max="8" step="1" data-f="ul_close" value="${u.close_px}"></label>
        ${upload}<button data-a="ul-delete">${t("ul_delete")}</button></div>`);
  }
  _bindUnderlay(root, on) {
    on('[data-a="ul-pick"]', () => root.querySelector('[data-f="ul_file"]').click());
    on('[data-f="ul_file"]', el => { if (el.files && el.files[0]) this._upload(el.files[0]); }, "change");
    on('[data-a="ul-delete"]', () => this._deleteUnderlay());
    on("[data-tool]", el => { this._setTool(el.dataset.tool, true); this._adding = false; this._menu = false; this._render(); });
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
    const vb = this._viewBox(), u = this._unit(), r = 22 * u, sw = 1.5 * u;  // UI hotfix (F03): 44 px corner handles for fingers
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
    let handles = "";  // UI hotfix (F03): corner and size handles last – above the wide wall and opening touch bands
    for (const room of this._floorRooms()) {
      // UI hotfix (F03): handles only for a chosen room or corner – a chosen wall keeps its neighbours tappable
      const sel = this._sel && this._sel.id === room.id && (this._sel.type === "room" || this._sel.type === "vertex");
      const meta = this._rooms.find(m => m.key === room.room_key);
      if (room.polygon.length >= 2) out += `<polygon class="room${sel ? " sel" : ""}${bad.has(room.id) ? " err" : ""}" data-k="room" data-id="${esc(room.id)}" tabindex="0" role="button" aria-label="${esc((meta && meta.name) || room.room_key)}" points="${room.polygon.map(S).join(" ")}" stroke-width="${G.round3(sel ? sw * 2.5 : sw)}"/>`;
      if (room.polygon.length >= 3) {
        const c = G.labelPoint(room.polygon);
        const err = issues.find(i => i.id === room.id);
        out += `<text x="${G.round3(c[0])}" y="${G.round3(-c[1])}" text-anchor="middle" font-size="${G.round3(13 * u)}">${esc((meta && meta.name) || room.room_key)}</text>`;
        if (err) out += `<text class="err-text" x="${G.round3(c[0])}" y="${G.round3(-c[1] + 16 * u)}" text-anchor="middle" font-size="${G.round3(12 * u)}">${esc(this._t("e")[err.code] || err.code)}</text>`;
      }
      if (sel && this._mode === "precise") {
        room.polygon.forEach((p, i) => {
          const q = room.polygon[(i + 1) % room.polygon.length];
          handles += `<circle class="mid" data-k="mid" data-id="${esc(room.id)}" data-i="${i}" cx="${G.round3((p[0] + q[0]) / 2)}" cy="${G.round3(-(p[1] + q[1]) / 2)}" r="${G.round3(r * 0.6)}"><title>${esc(this._t("add_corner"))}</title></circle>`;
          handles += `<circle class="dot${this._sel.type === "vertex" && this._sel.index === i ? " sel" : ""}" cx="${G.round3(p[0])}" cy="${G.round3(-p[1])}" r="${G.round3(8 * u)}" stroke-width="${G.round3(sw)}"/>`
            + `<circle class="handle hit" data-k="v" data-id="${esc(room.id)}" data-i="${i}" cx="${G.round3(p[0])}" cy="${G.round3(-p[1])}" r="${G.round3(r)}" tabindex="0" role="button" aria-label="${esc(this._t("corner"))} ${i + 1}"/>`;
        });
      } else if (sel && room.polygon.length >= 3) {
        const box = G.bbox([room.polygon]);
        handles += `<rect class="handle" data-k="scale" data-id="${esc(room.id)}" x="${G.round3(box.maxX - r)}" y="${G.round3(-box.maxY - r)}" width="${G.round3(2 * r)}" height="${G.round3(2 * r)}" stroke-width="${G.round3(sw)}"/>`;
      }
    }
    // 0.26.5.5: exterior walls thick, walls shared with a neighbour thin; guides while a room snaps
    const floorRooms = this._floorRooms().filter(x => x.polygon.length >= 3);
    const floorOpenings = this._layout.openings.filter(o => floorRooms.some(r => r.id === o.room_id));
    out += V.wallsSvg(G.wallSegments(floorRooms, floorOpenings), n => G.round3(n * u));  // 0.26.6.1(2): as on the house map
    if (this._guides) {
      const g = this._guides;
      if (g.gx != null) out += `<line class="guide" x1="${G.round3(g.gx)}" y1="${G.round3(vb[1])}" x2="${G.round3(g.gx)}" y2="${G.round3(vb[1] + vb[3])}" stroke-width="${G.round3(u)}" stroke-dasharray="${G.round3(5 * u)} ${G.round3(4 * u)}"/>`;
      if (g.gy != null) out += `<line class="guide" x1="${G.round3(vb[0])}" y1="${G.round3(-g.gy)}" x2="${G.round3(vb[0] + vb[2])}" y2="${G.round3(-g.gy)}" stroke-width="${G.round3(u)}" stroke-dasharray="${G.round3(5 * u)} ${G.round3(4 * u)}"/>`;
    }
    // 0.26.6.1(2): every wall can be tapped (a wide invisible band); the chosen room or wall shows its lengths
    const fmtLen = n => `${n.toFixed(2)} ${this._unitLabel()}`;  // UI hotfix (F02): schematic units are no metres
    for (const room of floorRooms) room.polygon.forEach((p, i) => {
      const q = room.polygon[(i + 1) % room.polygon.length];
      out += `<line class="hitwall" data-k="wall" data-id="${esc(room.id)}" data-i="${i}" x1="${G.round3(p[0])}" y1="${G.round3(-p[1])}" x2="${G.round3(q[0])}" y2="${G.round3(-q[1])}" stroke="transparent" stroke-width="${G.round3(44 * u)}" pointer-events="stroke"/>`;
    });
    const measured = this._sel && (this._sel.type === "room" || this._sel.type === "vertex" || this._sel.type === "wall") ? this._room(this._sel.id) : null;
    if (measured && measured.floor_id === this._floor && measured.polygon.length >= 3) {
      const pts = measured.polygon, locked = new Set(measured.locked_walls || []);
      pts.forEach((p, i) => {
        const q = pts[(i + 1) % pts.length], one = this._sel.type === "wall";
        if (one && i !== this._sel.index) return;
        const n = V.inwardNormal(G, pts, i), m = [(p[0] + q[0]) / 2 + n[0] * 14 * u, (p[1] + q[1]) / 2 + n[1] * 14 * u];
        if (one) out += `<line class="wallsel" x1="${G.round3(p[0])}" y1="${G.round3(-p[1])}" x2="${G.round3(q[0])}" y2="${G.round3(-q[1])}" stroke-width="${G.round3(6 * u)}"/>`;
        out += `<text class="measure${one ? " big" : ""}" stroke-width="${G.round3(3 * u)}" x="${G.round3(m[0])}" y="${G.round3(-m[1] + 4 * u)}" text-anchor="middle" font-size="${G.round3((one ? 14 : 11) * u)}">${locked.has(i) ? "🔒 " : ""}${fmtLen(G.edgeLength(pts, i))}</text>`;
        if (one) [[p, i], [q, (i + 1) % pts.length]].forEach(([c, k]) => {
          out += `<circle class="corner${(this._wallFixed || "start") === (k === i ? "start" : "end") ? " fixed" : ""}" cx="${G.round3(c[0])}" cy="${G.round3(-c[1])}" r="${G.round3(9 * u)}" stroke-width="${G.round3(1.5 * u)}"/><text class="cornerno" x="${G.round3(c[0])}" y="${G.round3(-c[1] + 4 * u)}" text-anchor="middle" font-size="${G.round3(11 * u)}">${k + 1}</text>`;
        });
      });
    }
    const orphaned = new Set(this._progress().orphans);   // U02: openings naming a contact that is gone
    for (const o of this._layout.openings) {
      const room = this._room(o.room_id);
      if (!room || room.floor_id !== this._floor || !(o.edge >= 0 && o.edge < room.polygon.length)) continue;
      const len = G.edgeLength(room.polygon, o.edge) || 1, w = Math.min(o.width_m || Math.min(0.9, len * 0.4), len), h = w / len / 2;
      const a = G.edgePoint(room.polygon, o.edge, Math.max(o.offset - h, 0)), b = G.edgePoint(room.polygon, o.edge, Math.min(o.offset + h, 1));
      const sel = this._sel && this._sel.type === "opening" && this._sel.id === o.id;
      out += `<line class="op${sel ? " sel" : ""}${o.kind === "door" || o.kind === "passage" ? " inner" : ""}${bad.has(o.id) ? " err" : ""}" data-k="op" data-id="${esc(o.id)}" tabindex="0" role="button" aria-label="${esc(this._t("k")[o.kind] || o.kind)}" x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke-width="${G.round3(14 * u)}"/><line class="hitop" data-k="op" data-id="${esc(o.id)}" x1="${G.round3(a[0])}" y1="${G.round3(-a[1])}" x2="${G.round3(b[0])}" y2="${G.round3(-b[1])}" stroke="transparent" stroke-width="${G.round3(44 * u)}" pointer-events="stroke"/>`;
      const inward = V.inwardNormal(G, room.polygon, o.edge);
      out += `<g class="symbol" pointer-events="none">${V.openingSymbol(o.kind, a, b, inward, o.kind === "passage" ? "open" : "closed", n => G.round3(n * u), "#fff", o.kind === "door" ? G.doorGeometry(a, b, inward, o) : null)}</g>`;
      if (orphaned.has(o.id)) out += `<circle class="orphan" data-orphan="${esc(o.id)}" pointer-events="none" cx="${G.round3((a[0] + b[0]) / 2)}" cy="${G.round3(-(a[1] + b[1]) / 2)}" r="${G.round3(6 * u)}" fill="#ffb020" stroke="#0a1f38" stroke-width="${G.round3(1.5 * u)}"><title>${esc(this._t("contact_gone"))}</title></circle>`;
      // both ends of the selected opening: drag to change its width (it stays centred on its position)
      // v0.26.6.1: the width handles never cover the middle of a small opening – there it is moved, not widened
      const wr = Math.min(r, Math.hypot(b[0] - a[0], b[1] - a[1]) * 0.3);
      if (sel) for (const [i, q] of [a, b].entries()) out += `<circle class="dot" cx="${G.round3(q[0])}" cy="${G.round3(-q[1])}" r="${G.round3(7 * u)}" stroke-width="${G.round3(sw)}"/><circle class="handle hit wh" data-k="ow" data-id="${esc(o.id)}" data-i="${i}" cx="${G.round3(q[0])}" cy="${G.round3(-q[1])}" r="${G.round3(wr)}"><title>${esc(this._t("width_handle"))}</title></circle>`;
    }
    // Hotfix 0.26.6.1: the plan's connections, also in the editor. A connection is a logical link (dashed, its kind
    // as a symbol); where an opening already lies on the wall both rooms share it is drawn once – as that opening.
    // A door or open passage without a wall the two rooms really share is marked as not carried by the plan.
    const rooms = this._layout.rooms;
    for (const c of this._layout.connections) {
      const ra = this._room(c.a), rb = this._room(c.b);
      if (!ra || !rb || ra.floor_id !== this._floor || rb.floor_id !== this._floor || ra.polygon.length < 3 || rb.polygon.length < 3) continue;
      const drawn = this._layout.openings.some(o => (o.room_id === ra.id || o.room_id === rb.id)
        && (G.openingLink(rooms, o.room_id === ra.id ? ra : rb, o) || {}).id === (o.room_id === ra.id ? rb.id : ra.id));
      if (drawn) continue;
      const wall = G.sharedWall(ra, rb), loose = G.PHYSICAL_CONNECTIONS.has(c.kind) && !wall;
      const pa = G.labelPoint(ra.polygon), pb = G.labelPoint(rb.polygon);
      const at = wall ? [(wall.a[0] + wall.b[0]) / 2, (wall.a[1] + wall.b[1]) / 2] : [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2];
      const label = `${this._t("c")[c.kind] || c.kind}${loose ? ` – ${this._t("conn_no_wall")}` : ""}`;
      out += `<g class="conn logical k-${esc(c.kind)}${loose ? " loose" : ""}" data-connection="${esc(c.id)}" pointer-events="none" role="img" aria-label="${esc(label)}">`
        + `<line x1="${G.round3(pa[0])}" y1="${G.round3(-pa[1])}" x2="${G.round3(pb[0])}" y2="${G.round3(-pb[1])}" stroke-width="${G.round3(2.5 * u)}" stroke-dasharray="${G.round3(3 * u)} ${G.round3(6 * u)}"/>`
        + `<circle class="conn-mark" cx="${G.round3(at[0])}" cy="${G.round3(-at[1])}" r="${G.round3(12 * u)}" stroke-width="${G.round3(2 * u)}"/>`
        + `<text x="${G.round3(at[0])}" y="${G.round3(-at[1] + 4.5 * u)}" text-anchor="middle" font-size="${G.round3(12 * u)}">${V.CONNECTION_SYMBOL[c.kind] || "⇄"}</text><title>${esc(label)}</title></g>`;
    }
    // 0.26.6.1(10): the fitted plan as a preview over the drawing – rooms dashed, the walls they now share bright
    if (this._preview && this._preview.join) {
      const pr = this._preview.layout.rooms.filter(x => x.floor_id === this._floor && x.polygon.length >= 3);
      for (const r of pr) out += `<polygon class="join-ghost" points="${r.polygon.map(S).join(" ")}" stroke-width="${G.round3(2 * u)}" stroke-dasharray="${G.round3(6 * u)} ${G.round3(4 * u)}"/>`;
      for (const w of G.wallSegments(pr, []).filter(x => x.interior)) out += `<line class="join-shared" x1="${G.round3(w.a[0])}" y1="${G.round3(-w.a[1])}" x2="${G.round3(w.b[0])}" y2="${G.round3(-w.b[1])}" stroke-width="${G.round3(5 * u)}"/>`;
    }
    out += handles;
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
  // v0.26.6.1 editor hotfix: a section that opens on demand; it remembers being opened or closed by the user
  _sec(id, title, body, open = false) {
    const isOpen = this._open[id] ?? open;
    return `<details class="sec" data-sec="${esc(id)}"${isOpen ? " open" : ""}><summary>${esc(title)}</summary><div class="body">${body}</div></details>`;
  }
  _addPanel() {
    const t = k => this._t(k), missing = this._rooms.filter(m => !this._layout.rooms.some(r => r.room_key === m.key));
    const icon = d => `<svg viewBox="0 0 40 30" aria-hidden="true"><path d="${d}"/></svg>`;
    const shapes = { rect: "M4 4H36V26H4Z", l: "M4 4H36V15H20V26H4Z", u: "M4 4H36V26H27V13H13V26H4Z", precise: "M4 8L24 4L36 14L30 26L6 22Z" };
    const shapeButtons = Object.entries(shapes).map(([k, d]) => `<button data-shape="${k}" aria-pressed="${this._shape === k}">${icon(d)}${esc(k === "precise" ? t("shape_precise") : t(k))}</button>`).join("");
    const body = missing.length
      ? `<label>${t("which_room")}<br><select data-f="add_key">${missing.map(m => `<option value="${esc(m.key)}">${esc(m.name || m.key)}</option>`).join("")}</select></label>
        <div><b>${t("shape")}</b><div class="shapes" role="group" aria-label="${esc(t("shape"))}">${shapeButtons}</div></div>
        <div class="sub">${esc(t("shape_help"))}</div>
        ${this._shape === "precise" ? `<div class="sub">${t("shape_precise_hint")}</div>` : ""}
        <div class="bar"><button class="primary" data-a="add">${t("add_room")}</button><button data-a="add_close">${t("add_cancel")}</button></div>`
      : `<div class="sub">${t("all_placed")}</div><div class="bar"><button data-a="propose">${t("propose")}</button><button data-a="add_close">${t("close")}</button></div>`;
    return `<div class="panel selected"><h4>${t("new_room")}</h4>${body}</div>`;
  }
  _emptyPanel() {
    const t = k => this._t(k), b = this._layout.building, p = this._progress();
    // 0.26.7.0: a step is ticked only when its condition is shown – never because rooms merely exist
    const steps = [["step_floor", !!this._floor], ["step_rooms", p.rooms > 0 && !p.missing], ["step_shape", p.rooms > 0 && p.shaped, true],
      ["step_openings", p.windows > 0], ["step_contacts", p.assigned > 0 && !p.unassigned && !p.orphans.length], ["step_save", p.rooms > 0 && p.saved]];
    const next = steps.findIndex(([, done, optional]) => !done && !optional);
    const list = steps.map(([k, done, optional], i) => `<li class="${done ? "done" : ""}${i === next ? " next" : ""}"><span class="n">${done ? "✓" : i + 1}</span>${esc(t(k))}${optional && !done ? ` <span class="sub">(${esc(t("step_optional"))})</span>` : ""}</li>`).join("");
    const deg = ((Number(b.north_deg) || 0) % 360 + 360) % 360, dir = t("dirs")[Math.round(deg / 22.5) % 16];
    const building = `<div class="sub">${esc(t("north_help"))}</div>
      <div class="north"><b>${esc(t("north"))}</b>${compassRose(deg, this._lang === "de" ? ["N", "O", "S", "W"] : ["N", "E", "S", "W"])}
        <div class="fields"><label>°<br><input type="number" step="1" min="0" max="359.9" data-f="north" value="${esc(Math.round(deg * 10) / 10)}"></label></div>
        <div class="sub" data-north-now>${esc(t("north_now").replace("{dir}", dir).replace("{deg}", String(Math.round(deg))))} ${esc(t("north_keep"))}</div>
        <div class="sub">${esc(t("north_examples"))}</div><div class="sub">${esc(t("north_drag"))}</div></div>
      <label><input type="checkbox" data-f="north_confirmed"${b.north_confirmed ? " checked" : ""}> ${t("north_confirmed")}</label><div class="sub">${esc(t("north_confirmed_help"))}</div>`;
    return `<div class="panel"><h4>${t("steps_title")}</h4><div class="sub">${esc(t("start_intro"))}</div><ol class="steps">${list}</ol>
      ${p.missing ? `<div class="bar"><button class="primary" data-a="add_open">${t("add_room")}</button></div>` : ""}
      <div class="help">${t("none")}</div>${this._sec("building", t("sec_building"), building)}</div>`;
  }
  _panel() {
    const t = k => this._t(k), sel = this._sel;
    if (this._adding && !sel) return this._addPanel();
    if (!sel) return this._emptyPanel();
    if (sel.type === "opening") {
      const o = this._layout.openings.find(x => x.id === sel.id);
      if (!o) return "";
      const room = this._room(o.room_id);
      // hotfix after review (F01): any contact of the setup can be the sensor of a drawn opening – the room's own first,
      // then the others with the room they air (a guest WC window set up for the hall is drawn in the WC)
      const own = roomContacts(this._live[room && room.room_key]);
      const airs = c => Object.keys(this._live).filter(k => k !== (room && room.room_key) && roomContacts(this._live[k]).includes(c)).map(k => (this._rooms.find(m => m.key === k) || {}).name || k);
      const others = [...new Set(Object.values(this._live).flatMap(v => roomContacts(v)))].filter(c => !own.includes(c)).sort();
      const contacts = [...new Set([...own, ...others, ...o.contacts])];
      const opts = (map, value) => Object.entries(map).map(([k, v]) => `<option value="${k}"${k === value ? " selected" : ""}>${esc(v)}</option>`).join("");
      const meta = room && this._rooms.find(m => m.key === room.room_key);
      const known = new Set([...own, ...others]), provable = this._contactsComplete();
      const checks = contacts.map(c => { const via = own.includes(c) ? [] : airs(c), gone = provable && !known.has(c); return `<label${gone ? ' class="gone"' : ""}><input type="checkbox" data-contact="${esc(c)}"${o.contacts.includes(c) ? " checked" : ""}> <span>${esc(c)}${gone ? ` <small class="warn">⚠ ${esc(t("contact_gone"))}</small>` : ""}${via.length ? ` <small>(${esc(t("airs"))} ${esc(via.join(", "))})</small>` : ""}</span></label>`; }).join("");
      const place = `<div class="fields"><label>${t("wall")}<br><input type="number" min="1" max="${room ? room.polygon.length : 1}" data-f="edge" value="${o.edge + 1}"></label>
        <label>${t("position")}<br><input type="number" step="0.01" min="0" max="1" data-f="offset" value="${esc(o.offset)}"></label></div>`;
      const details = `<div class="fields"><label>${t("mechanics")}<br><select data-f="mechanics">${opts(t("m"), o.mechanics)}</select></label></div>`;
      return `<div class="panel selected"><h4>${esc(t("k")[o.kind] || o.kind)} · ${esc((meta && meta.name) || (room && room.room_key) || "")}</h4><div class="fields">
        <label>${t("kind")}<br><select data-f="kind">${opts(t("k"), o.kind)}</select></label>
        <label>${t("width")}<br><span class="wbox"><button data-w="-1" aria-label="${t("narrower")}">−</button><input type="number" step="0.05" min="0.1" data-f="width" value="${esc(o.width_m == null ? "" : o.width_m)}" placeholder="${esc(shownWidth(room, o))}"><button data-w="1" aria-label="${t("wider")}">+</button></span></label>
        ${o.kind === "door" ? `<label>${t("door_hinge")}<br><select data-f="door_hinge">${opts(t("hinges"), o.door_hinge || "")}</select></label>
        <label>${t("door_swing")}<br><select data-f="door_swing">${opts(t("swings"), o.door_swing || "in")}</select></label>` : ""}</div>
        ${T.INTERIOR_KINDS.has(o.kind) && room && !T.openingTarget(this._layout, room, o) ? `<div class="msg" role="status">${t("not_interior")}</div>` : ""}
        ${G.windowOnInteriorWall(this._layout.rooms, o) ? `<div class="msg" role="status">${t("window_inside")} <button data-a="window_out">${t("window_out")}</button></div>` : ""}
        ${o.kind === "passage" ? "" : `<div><b>${t("contacts")}</b><div class="sub">${t("contacts_hint")}</div><div class="checks">${checks || `<span class="sub">${t("no_contacts")}</span>`}</div></div>`}
        ${this._sec("place", t("sec_place"), place)}${this._sec("details", t("sec_details"), details)}
        <div><button class="danger" data-a="delete">${t("delete")}</button></div></div>`;
    }
    if (sel.type === "wall") return this._wallPanel(sel);
    const room = this._room(sel.id);
    if (!room) return "";
    const meta = this._rooms.find(m => m.key === room.room_key);
    const area = room.polygon.length >= 3 ? Math.abs(G.signedArea(room.polygon)).toFixed(1) : "–";
    const vertices = room.polygon.map((p, i) => `<div class="vertex"><span>${i + 1}</span><input type="number" step="0.05" data-vx="${i}" value="${p[0]}" aria-label="${t("corner")} ${i + 1} ${t("x")}"><input type="number" step="0.05" data-vy="${i}" value="${p[1]}" aria-label="${t("corner")} ${i + 1} ${t("y")}"><button data-del-v="${i}" aria-label="${t("delete")}">✕</button></div>`).join("");
    const others = this._layout.rooms.filter(r => r.id !== room.id);
    const conns = this._layout.connections.filter(c => c.a === room.id || c.b === room.id);
    const name = id => { if (id === "outside") return t("outside"); const r = this._room(id); const m = r && this._rooms.find(x => x.key === r.room_key); return esc((m && m.name) || id); };
    const connections = `<div class="sub">${t("conn_hint")}</div>
      <div>${conns.map(c => `${name(c.a === room.id ? c.b : c.a)} (${esc(t("c")[c.kind] || c.kind)})${this._convertible(c) ? ` <button data-conv-c="${esc(c.id)}">${esc(t(c.kind === "door" ? "conv_door" : "conv_passage"))}</button>` : ""} <button data-del-c="${esc(c.id)}" aria-label="${t("delete")}">✕</button>`).join(" · ") || "–"}</div>
      <div class="bar"><select data-f="conn_to" aria-label="${esc(t("connections"))}"><option value="outside">${t("outside")}</option>${others.map(r => `<option value="${esc(r.id)}">${name(r.id)}</option>`).join("")}</select>
        <select data-f="conn_kind" aria-label="${esc(t("kind"))}">${Object.entries(t("c")).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select><button data-a="connect">${t("add")}</button></div>`;
    const precise = this._mode === "precise";
    return `<div class="panel selected"><h4>${esc((meta && meta.name) || room.room_key)}</h4>
      <div class="sub">${esc(t("room_info").replace("{a}", area).replace("{p}", `${t("provenance")}: ${t("p")[room.provenance] || room.provenance}`))}</div>
      <div class="bar"><button data-a="window">${t("add_window")}</button><button data-a="rotate" title="${esc(t("rotate_help"))}">${t("rotate")}</button><button data-a="${precise ? "corners_done" : "edit_corners"}" aria-pressed="${precise}">${t(precise ? "corners_done" : "edit_corners")}</button></div>
      <div class="sub">${esc(t("rotate_help"))}</div>
      <div class="fields"><label>${t("floor")}<br><select data-f="floor">${this._layout.floors.map(f => `<option value="${esc(f.id)}"${f.id === room.floor_id ? " selected" : ""}>${esc(this._floorName(f))}</option>`).join("")}</select></label></div>
      ${precise ? this._sec("corners", t("sec_corners"), `<div class="sub">${t("corners_hint")}</div>${vertices}`) : ""}
      ${this._sec("connections", `${t("sec_connections")}${conns.length ? ` (${conns.length})` : ""}`, connections)}
      <div><button class="danger" data-a="delete">${t("delete")}</button></div></div>`;
  }
  // UI hotfix (F03): under a finger the wide touch bands of walls and openings overlap – the nearest one is meant.
  // An opening wins over the wall it lies on; of two walls on the same line the one of the room tapped into.
  _pickAt(p) {
    const rooms = this._floorRooms().filter(r => r.polygon.length >= 3), reach = 22 * this._unit();
    let wall = null;
    for (const room of rooms) room.polygon.forEach((a, i) => {
      const d = G.projectOnSegment(p, a, room.polygon[(i + 1) % room.polygon.length]).distance;
      const inside = G.pointInPolygon(p, room.polygon) === "inside";
      if (!wall || d < wall.d - 1e-6 || (Math.abs(d - wall.d) <= 1e-6 && inside && !wall.inside)) wall = { d, inside, sel: { type: "wall", id: room.id, index: i } };
    });
    let opening = null;
    for (const o of this._layout.openings) {
      const span = G.openingSpan(rooms.find(r => r.id === o.room_id), o);
      const d = span ? G.projectOnSegment(p, span[0], span[1]).distance : Infinity;
      if (d <= reach && (!opening || d < opening.d)) opening = { d, sel: { type: "opening", id: o.id } };
    }
    return opening && (!wall || opening.d <= wall.d + 2 * this._unit()) ? opening.sel : wall ? wall.sel : null;
  }
  _unitLabel() { return this._layout.building.units === "m" ? "m" : this._t("unit_schematic"); }
  // 0.26.6.1(2): a tapped wall – its length in metres, which corner stays, and an optional lock of the length
  _wallPanel(sel) {
    const t = k => this._t(k), room = this._room(sel.id);
    if (!room || !(sel.index >= 0 && sel.index < room.polygon.length)) return "";
    const meta = this._rooms.find(m => m.key === room.room_key), n = room.polygon.length, fixed = this._wallFixed || "start";
    const locked = (room.locked_walls || []).includes(sel.index), metric = this._layout.building.units === "m";
    // 0.26.6.1(10): the angles at both corners of this wall, each with "to 90°" and its own angle lock
    const ends = [sel.index, (sel.index + 1) % n], cornerLocks = new Set(room.locked_corners || []);
    const angles = ends.map((c, j) => { const a = G.cornerAngle(room.polygon, c), lockedA = cornerLocks.has(c);
      return `<div class="corner-row"><b>${t("angle")} ${t("corner")} ${c + 1}: ${a.toFixed(1).replace(".", this._lang === "de" ? "," : ".")}°</b>
        <button data-a="square" data-corner="${c}" data-keep="${j === 0 ? "out" : "in"}"${lockedA || G.isRightCorner(room.polygon, c) ? " disabled" : ""}>${t("corner_square").replace("{c}", c + 1)}</button>
        <label><input type="checkbox" data-f="corner_lock" data-corner="${c}"${lockedA ? " checked" : ""}> ${t("corner_lock").replace("{c}", c + 1)}</label></div>`; }).join("");
    const scale = `<div class="sub">${t("scale_hint")}</div><div class="fields"><label>${t("scale_real")}<br><input type="number" step="0.01" min="0.1" data-f="scale_m" placeholder="${t("scale_placeholder")}"></label></div><div class="bar"><button data-a="calibrate">${t("scale_apply")}</button></div>`;
    // v0.26.6.1 editor hotfix: length first (with the corner that stays and the lock), then angles, then the scale
    return `<div class="panel selected"><h4>${esc(t("wall"))} ${sel.index + 1} · ${esc((meta && meta.name) || room.room_key)}</h4><div class="fields">
      <label>${metric ? t("wall_length") : t("wall_length_units")}<br><input type="number" step="0.01" min="0.1" data-f="wall_len" value="${G.edgeLength(room.polygon, sel.index).toFixed(2)}"${locked ? " disabled" : ""}></label>
      <label>${t("wall_fixed")}<br><select data-f="wall_fixed"><option value="start"${fixed === "start" ? " selected" : ""}>${t("corner")} ${sel.index + 1}</option><option value="end"${fixed === "end" ? " selected" : ""}>${t("corner")} ${(sel.index + 1) % n + 1}</option></select></label>
      <label><input type="checkbox" data-f="wall_lock"${locked ? " checked" : ""}> ${t("wall_lock")}</label></div>
      <div class="bar"><button class="primary" data-a="wall_apply"${locked ? " disabled" : ""}>${t("apply")}</button></div><div class="sub">${t("wall_help")}</div>
      ${this._sec("angles", t("sec_angles"), `<div class="angles">${angles}</div>`, true)}
      ${metric ? "" : this._sec("scale", t("sec_scale"), scale)}</div>`;
  }
  // 0.26.6.1(10): a refused edit names what stands in the way (a locked wall or a locked angle) and how to solve it
  _blocked(res) {
    if (res.edge != null) return this._t("blocked_wall").replaceAll("{w}", res.edge + 1);
    if (res.corner != null) return this._t("blocked_corner").replaceAll("{c}", res.corner + 1);
    return this._t({ length: "wall_bad_length", shared: "wall_conflict_shared" }[res.error] || "wall_conflict_shape");
  }
  // Take a geometry result ({polygons}) into the plan: openings keep their place on walls that moved (or the change is
  // refused), no new overlap or invalid shape, no locked length or angle changed – else nothing changes.
  _takePolygons(res) {
    const t = k => this._t(k), fail = text => { this._msg = { err: true, text }; this._render(); return false; };
    if (res.error) return fail(this._blocked(res));
    const next = clone(this._layout);
    for (const [id, polygon] of Object.entries(res.polygons)) { const r = next.rooms.find(x => x.id === id); r.polygon = polygon; r.provenance = "user"; }
    for (let i = 0; i < next.openings.length; i++) {  // doors and windows keep their place on walls that moved, or the change is refused
      const o = next.openings[i], before = this._room(o.room_id);
      if (!res.polygons[o.room_id] || !(o.edge >= 0 && o.edge < before.polygon.length)) continue;
      const moved = G.followOpening(before.polygon, res.polygons[o.room_id], o);
      const was = G.openingLink(this._layout.rooms, before, o), now = moved && G.openingLink(next.rooms, next.rooms.find(r => r.id === o.room_id), moved);
      if (!moved || (was && (!now || now.id !== was.id))) return fail(t("wall_conflict_opening"));
      next.openings[i] = moved;
    }
    const known = new Set(this._issues().map(i => `${i.code}|${i.id}`));
    const added = G.validateLayout(next).filter(i => !known.has(`${i.code}|${i.id}`));
    if (added.length) return fail(t(added.some(i => i.code === "E_ROOM_OVERLAP") ? "wall_conflict_overlap" : "wall_conflict_shape"));
    if (lockBroken(this._layout, next)) return fail(t("wall_locked"));
    this._commit(l => { l.rooms = next.rooms; l.openings = next.openings; });
    return true;
  }
  _squareCorner(corner, keep) {
    const sel = this._sel, room = sel && this._room(sel.id);
    if (!room) return;
    if ((room.locked_corners || []).includes(corner)) { this._msg = { err: true, text: this._t("corner_locked").replace("{c}", corner + 1) }; this._render(); return; }
    this._takePolygons(G.squareCorner(this._layout, room.id, corner, keep));
  }
  // 0.26.6.1(10): fit the rooms of this floor together – shown as a preview first, saved only when applied
  _joinRooms() {
    const t = k => this._t(k), rooms = this._floorRooms(), res = G.joinRooms(rooms);
    if (!res.matches.length) { this._msg = { err: true, text: t("join_none") }; this._render(); return; }
    const layout = clone(this._layout);
    for (const r of layout.rooms) if (res.polygons[r.id]) { r.polygon = res.polygons[r.id]; r.provenance = "user"; }
    const name = id => { const r = this._room(id), m = r && this._rooms.find(x => x.key === r.room_key); return (m && m.name) || (r && r.room_key) || id; };
    const moved = rooms.filter(r => JSON.stringify(r.polygon) !== JSON.stringify(res.polygons[r.id])).length;
    const fmt = v => String(v.toFixed(2)).replace(".", this._lang === "de" ? "," : ".");
    const notes = [t("join_preview").replace("{m}", res.matches.length).replace("{r}", moved)];
    const lengths = res.conflicts.filter(c => c.code === "length_differs").map(c => `${name(c.a)} ${fmt(c.length_a)} m ↔ ${name(c.b)} ${fmt(c.length_b)} m`);
    const locks = res.conflicts.filter(c => c.code === "locked_corner").map(c => `${name(c.b)} ${t("corner")} ${c.corner + 1}`);
    const overlaps = res.conflicts.filter(c => c.code === "overlap").map(c => `${name(c.a)} / ${name(c.b)}`);
    if (lengths.length) notes.push(t("join_lengths").replace("{list}", lengths.join(", ")));
    if (locks.length) notes.push(t("join_locked").replace("{list}", locks.join(", ")));
    if (overlaps.length) notes.push(t("join_overlap").replace("{list}", overlaps.join(", ")));
    this._preview = { layout, changed: moved, join: { matches: res.matches, conflicts: res.conflicts, notes } };
    this._msg = null; this._render();
  }
  _floorName(f) {
    const names = this._t("floor_names") || {};
    return names[f.level_key] || f.name || f.level_key || f.id;  // the same rule as the house map's floor buttons
  }
  // UI hotfix (F02): a schematic plan gets a real scale from one wall the user measured – every room, opening width
  // and floor is scaled alike and the plan is metric from then on (undo restores it). Metric plans need no scale.
  _setPlanScale(metres) {
    const sel = this._sel, room = sel && this._room(sel.id), real = Number(metres);
    if (!room || this._layout.building.units === "m") return;
    const len = G.edgeLength(room.polygon, sel.index);
    if (!(real >= 0.1) || !(len > 0)) { this._msg = { err: true, text: this._t("wall_bad_length") }; this._render(); return; }
    const f = real / len;
    this._commit(l => {
      for (const r of l.rooms) r.polygon = r.polygon.map(p => [G.round3(p[0] * f), G.round3(p[1] * f)]);
      for (const o of l.openings) if (o.width_m != null) o.width_m = G.round3(o.width_m * f);
      l.building.units = "m";
    }, { force: true });  // the scale changes every length on purpose – also a locked one, in proportion
    this._fit(); this._render();
  }
  // 0.26.6.1(6): windows on a wall shared with another room are offered a move to the nearest outside wall
  _insideWindows() { return this._layout.openings.filter(o => G.windowOnInteriorWall(this._layout.rooms, o)); }
  _windowsOut(ids) {
    const moves = ids.map(id => { const o = this._layout.openings.find(x => x.id === id); return [id, o && G.exteriorSpot(this._layout.rooms, this._room(o.room_id), o)]; }).filter(([, spot]) => spot);
    if (!moves.length) { this._msg = { err: true, text: this._t("window_no_outside") }; this._render(); return; }
    this._commit(l => { for (const [id, spot] of moves) Object.assign(l.openings.find(x => x.id === id), spot, { provenance: "user" }); });
  }
  _applyWallLength(value) {
    const sel = this._sel, t = k => this._t(k), room = sel && this._room(sel.id);
    if (!room) return;
    if ((room.locked_walls || []).includes(sel.index)) { this._msg = { err: true, text: t("wall_locked") }; this._render(); return; }
    this._takePolygons(G.resizeWall(this._layout, room.id, sel.index, Number(value), this._wallFixed || "start"));
  }
  // A door or open passage of the plan's connections that can become a drawn opening: the rooms share a wall and
  // no opening links them yet (a connection and an opening are never kept twice for the same way).
  _convertible(c) {
    const a = this._room(c.a), b = this._room(c.b);
    if (!a || !b || !G.PHYSICAL_CONNECTIONS.has(c.kind) || !G.sharedWall(a, b)) return false;
    return !this._layout.openings.some(o => (o.room_id === a.id || o.room_id === b.id) && (G.openingLink(this._layout.rooms, this._room(o.room_id), o) || {}).id === (o.room_id === a.id ? b.id : a.id));
  }
  _convertConnection(id) {
    const c = this._layout.connections.find(x => x.id === id);
    if (!c || !this._convertible(c)) return;
    const a = this._room(c.a), wall = G.sharedWall(a, this._room(c.b)), mid = [(wall.a[0] + wall.b[0]) / 2, (wall.a[1] + wall.b[1]) / 2];
    const o = T.openingAt(this._layout, a.floor_id, mid, 0.3, c.kind === "door" ? "door" : "passage");
    if (!o || o.error) { this._msg = { err: true, text: this._t("no_interior") }; this._render(); return; }
    if (c.kind === "door" && Array.isArray(c.contacts)) o.contacts = [...c.contacts];  // the door keeps its contact
    this._commit(l => { l.openings.push(o); l.connections = l.connections.filter(x => x.id !== id); });
    this._sel = { type: "opening", id: o.id }; this._render();
  }
  _bindCompass(root) {
    const rose = root.querySelector("[data-compass]");
    if (!rose) return;
    const at = ev => { const r = rose.getBoundingClientRect(); return northFromPointer(ev.clientX - (r.left + r.width / 2), ev.clientY - (r.top + r.height / 2)); };
    let dragging = false, value = null;
    const show = deg => {   // live feedback while dragging; the layout changes once, on release (one undo step)
      const input = root.querySelector('[data-f="north"]'); if (input) input.value = String(deg);
      const needle = rose.querySelector("[data-compass-needle]"); if (needle) needle.style.transform = `rotate(${180 - deg}deg)`;
      const now = root.querySelector("[data-north-now]");
      if (now) now.textContent = `${this._t("north_now").replace("{dir}", this._t("dirs")[Math.round(deg / 22.5) % 16]).replace("{deg}", String(deg))} ${this._t("north_keep")}`;
    };
    rose.addEventListener("pointerdown", ev => { dragging = true; value = at(ev); show(value); try { rose.setPointerCapture(ev.pointerId); } catch (_) { /* no capture */ } ev.preventDefault(); });
    rose.addEventListener("pointermove", ev => { if (dragging) { value = at(ev); show(value); } });
    const end = () => { if (!dragging) return; dragging = false; if (value != null) this._commit(l => { setNorth(l, value); }); value = null; };
    rose.addEventListener("pointerup", end); rose.addEventListener("pointercancel", end);
    rose.addEventListener("keydown", ev => {
      const step = ev.key === "ArrowRight" || ev.key === "ArrowUp" ? 1 : ev.key === "ArrowLeft" || ev.key === "ArrowDown" ? -1 : 0;
      if (!step) return;
      ev.preventDefault();
      this._commit(l => { setNorth(l, (Number(l.building.north_deg) || 0) + step * (ev.shiftKey ? 15 : 1)); });
    });
  }
  // v0.26.6.1 editor hotfix: the hint for what is selected or active – else the next sensible step of the workflow
  // (floor → rooms → windows/doors → contacts → save). Shown quietly over the drawing, never a forced wizard.
  _contactsComplete() { return this._rooms.length > 0 && this._rooms.every(m => this._live && this._live[m.key] && Array.isArray(this._live[m.key].contact_entities)); }
  _progress() {
    const rooms = this._floorRooms().filter(r => r.polygon.length >= 3), ids = new Set(rooms.map(r => r.id));
    const openings = this._layout.openings.filter(o => ids.has(o.room_id));
    const contacts = new Set(Object.values(this._live || {}).flatMap(v => roomContacts(v)));
    const missing = this._rooms.filter(m => !this._layout.rooms.some(r => r.room_key === m.key)).length;
    const unassigned = contacts.size ? openings.filter(o => o.kind !== "passage" && !(o.contacts || []).length).length : 0;
    // U02: an assignment counts only with contacts FreshAirIQ really has (any room's – a window may air another room);
    // an opening naming a removed or renamed contact needs a check (nothing is deleted on its own)
    // "gone" is only provable while every configured room reports its contact list – missing live data is no evidence
    const orphans = this._contactsComplete() ? openings.filter(o => (o.contacts || []).some(c => !contacts.has(c))).map(o => o.id) : [];
    const assigned = openings.filter(o => (o.contacts || []).length && (o.contacts || []).every(c => contacts.has(c))).length;
    // U03: "position and shape adjusted" from the saved layout itself – a room the user drew or edited carries
    // provenance "user" (stored, part of undo/redo); proposed, traced or calculated rooms do not
    const shaped = rooms.some(r => r.provenance === "user");
    return { rooms: rooms.length, missing, windows: openings.filter(o => o.kind === "window" || o.kind === "roof_window").length, unassigned, assigned, orphans, contacts: contacts.size,
      shaped, dirty: this._dirty, saved: Number(this._revision || 0) > 0 && !this._dirty };
  }
  _hint() {
    const t = k => this._t(k), sel = this._sel;
    if (this._tool) return (t("tool_help") || {})[this._tool] || "";
    if (this._adding) return t("hint_adding");
    if (sel && sel.type === "vertex") return t(touchDevice() ? "hint_vertex_touch" : "hint_vertex").replace("{c}", sel.index + 1);
    if (sel && sel.type === "wall") return t("hint_wall").replace("{w}", sel.index + 1);
    if (sel && sel.type === "opening") return t("hint_opening");
    if (sel && sel.type === "room") return t(this._mode === "precise" ? "hint_room_precise" : "hint_room_quick");
    if (this._modeHint) return t("mode_help")[this._mode] || "";
    const p = this._progress();
    if (!p.rooms) return t("hint_empty");
    if (p.missing) return t("hint_next_missing").replace("{n}", p.missing);
    if (!p.windows) return t("hint_next_windows");
    if (p.orphans.length) return t("hint_next_orphans").replace("{n}", p.orphans.length);
    if (p.unassigned) return t("hint_next_contacts").replace("{n}", p.unassigned);
    if (p.dirty) return t("hint_next_save");
    return t(this._mode === "precise" ? "hint_precise" : "hint_done");
  }
  _selName() {
    const sel = this._sel;
    if (!sel) return "";
    const o = sel.type === "opening" && this._layout.openings.find(x => x.id === sel.id), room = this._room(o ? o.room_id : sel.id);
    const meta = room && this._rooms.find(m => m.key === room.room_key), name = (meta && meta.name) || (room && room.room_key) || "";
    if (o) return `${this._t("k")[o.kind] || o.kind} · ${name}`;
    if (sel.type === "wall") return `${this._t("wall")} ${sel.index + 1} · ${name}`;
    if (sel.type === "vertex") return `${this._t("corner")} ${sel.index + 1} · ${name}`;
    return name;
  }
  _render() {
    const keep = editorFocus(this.shadowRoot.activeElement);  // hotfix F02: keep the focused control and caret
    this._applyLayout();
    const t = k => this._t(k);
    const missing = this._rooms.filter(m => !this._layout.rooms.some(r => r.room_key === m.key));
    const close = `<button class="x" data-a="msg_close" aria-label="${esc(t("msg_close"))}">✕</button>`;
    const msg = this._msg ? `<div class="msg${this._msg.err ? " err" : ""}" role="alert">${this._msg.busy || this._busy ? "" : close}${this._msg.text}${this._msg.conflict ? ` <button data-a="export">${t("export")}</button> <button data-a="reload">${t("reload")}</button>` : ""}</div>` : "";
    const preview = this._preview ? `<div class="msg" role="status">${this._preview.join ? this._preview.join.notes.map(x => `<div>${esc(x)}</div>`).join("") : `${t("preview")}: ${this._preview.changed} ${t("changed_rooms")}`} <button class="primary" data-a="apply">${t("apply")}</button> <button data-a="no-apply">${t("cancel")}</button></div>` : "";
    const inside = this._insideWindows().length ? `<div class="msg" role="status">${t("windows_inside").replace("{n}", this._insideWindows().length)} <button data-a="windows_out">${t("windows_out")}</button></div>` : "";
    // with the properties folded away (phone), the selection stays and one tap brings its properties back
    const reopen = this._panelHidden && this._sel && this._isNarrow() ? ` <button data-a="panel_open">${t("edit_sel")}</button>` : "";
    const hint = `<div class="hint help" role="status" aria-live="polite">${this._panelHidden && this._sel ? `<b>${esc(t("selected").replace("{name}", this._selName()))}</b> · ` : ""}${esc(this._hint())}${reopen}</div>`;
    const tool = k => `<button data-tool="${k}" aria-pressed="${this._tool === k}" title="${esc(t("tool_help")[k])}">${esc(t(`tb_${k}`))}</button>`;
    const menu = `<div class="ov menu" role="dialog" aria-label="${esc(t("more_title"))}"${this._menu ? "" : " hidden"}><h4>${t("more_title")}</h4>
      <div class="row"><label>${t("grid")} <select data-f="grid">${GRIDS.map(g => `<option value="${g}"${g === this._grid ? " selected" : ""}>${g ? `${g} m` : t("off")}</option>`).join("")}</select></label><button data-a="snap90" aria-pressed="${!!this._snap90}">${t("snap90")}</button></div>
      <div class="row"><button data-a="join">${t("join")}</button></div>
      <div class="row">${missing.length ? `<button data-a="missing">${t("missing")}</button>` : ""}<button data-a="propose">${t("propose")}</button></div>
      <div class="row"><button data-a="export">${t("export")}</button><label><button data-a="import-btn">${t("import")}</button><input type="file" accept="application/json" data-f="import" hidden></label></div>
      <details class="sec hdet" data-sec="help"${this._open.help ? " open" : ""}><summary>${t("help_title")}</summary><div class="body help">${t("help")}</div></details>
      <div class="row"><button data-a="menu">${t("close")}</button></div></div>`;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <div class="tools" role="toolbar" aria-label="${esc(t("grp_edit"))}">
        <div class="tg tg-floor"><label>${t("floor")} <select data-f="view_floor">${this._layout.floors.map(f => `<option value="${esc(f.id)}"${f.id === this._floor ? " selected" : ""}>${esc(this._floorName(f))}</option>`).join("")}</select></label></div>
        <div class="tg tg-mode seg" role="group" aria-label="${esc(t("mode_label"))}"><button data-mode="quick" aria-pressed="${this._mode === "quick"}" title="${esc(t("quick_title"))}">${t("quick")}</button><button data-mode="precise" aria-pressed="${this._mode === "precise"}" title="${esc(t("precise_title"))}">${t("precise")}</button></div>
        <div class="tg tg-add" role="group" aria-label="${esc(t("openings_bar"))}"><button data-a="add_open" aria-pressed="${!!this._adding}">${t("tb_room")}</button>${["window", "door", "passage"].map(tool).join("")}<button class="more-btn" data-a="menu" aria-expanded="${!!this._menu}" aria-label="${esc(t("more_title"))}">⋯ ${t("more")}</button></div>
      </div>
      <div class="work${this._panelHidden ? " nopanel" : ""}">
        <div class="draw"><div class="canvas" tabindex="0">${this._svg()}</div>
          <div class="ov ov-top">${hint}${preview}${msg}${inside}</div>
          <div class="ov ov-bl" role="group" aria-label="${esc(t("grp_edit"))}"><button data-a="undo" aria-label="${t("undo")}" title="${t("undo")}"${this._history.past.length ? "" : " disabled"}>↶</button><button data-a="redo" aria-label="${t("redo")}" title="${t("redo")}"${this._history.future.length ? "" : " disabled"}>↷</button></div>
          <div class="ov ov-br" role="group" aria-label="${esc(t("grp_view"))}"><button data-a="zoom-out" aria-label="${t("zoom_out")}" title="${t("zoom_out")}">−</button><button data-a="zoom-in" aria-label="${t("zoom_in")}" title="${t("zoom_in")}">+</button><button data-a="fit" aria-pressed="${this._autoFit !== false}">${t("fit")}</button></div>
          ${menu}</div>
        <div class="side"><div class="aside">${this._panel()}${this._underlayPanel()}</div>
          <div class="bar final"><button class="ptoggle" data-a="panel_toggle" aria-expanded="${!this._panelHidden}">${t(this._panelHidden ? "panel_show" : "panel_hide")}</button><span class="grow"></span><button data-a="cancel">${t("cancel")}</button><button class="primary" data-a="save"${this._busy ? " disabled" : ""}>${t("save")}</button></div></div>
      </div>`;
    this._bind();
    restoreFocus(this.shadowRoot, keep);
    this._syncAspect(false);
    // 0.26.5.5: after picking a room on the drawing the arrow keys keep working – also in Safari, which does not
    // focus clicked SVG shapes: the drawing area itself holds the focus (no scrolling)
    const canvas = this.shadowRoot.querySelector(".canvas");
    if (this._kbd && canvas && !this.shadowRoot.activeElement) { try { canvas.focus({ preventScroll: true }); } catch (_) { /* old engine */ } }
  }
  _bind() {
    const root = this.shadowRoot, svg = root.querySelector("svg");
    svg.addEventListener("pointerdown", ev => this._down(ev));
    svg.addEventListener("pointermove", ev => this._move(ev));
    svg.addEventListener("pointerup", ev => this._up(ev));
    svg.addEventListener("pointercancel", ev => this._up(ev));
    svg.addEventListener("wheel", ev => { ev.preventDefault(); this._zoom(ev.deltaY > 0 ? 1.1 : 1 / 1.1); }, { passive: false });
    root.querySelectorAll("[data-mode]").forEach(el => el.addEventListener("click", () => { this._mode = el.dataset.mode; this._modeHint = !this._sel; this._render(); }));
    // v0.26.6.1 editor hotfix: a section the user opened or closed stays so across re-renders
    root.querySelectorAll(".sec>summary").forEach(el => el.addEventListener("click", () => { this._open[el.parentElement.dataset.sec] = !el.parentElement.open; }));
    const on = (sel, fn, type = "click") => root.querySelectorAll(sel).forEach(el => el.addEventListener(type, () => fn(el)));
    const actions = {
      undo: () => this._undo(), redo: () => this._redo(), "zoom-in": () => this._zoom(1 / 1.25), "zoom-out": () => this._zoom(1.25), fit: () => { this._autoFit = true; this._fit(); this._render(); },
      add: () => this._addRoom(root.querySelector('[data-f="add_key"]').value, this._shape),
      add_open: () => { this._adding = !this._adding; this._menu = false; if (this._adding) { this._sel = null; this._panelHidden = false; this._setTool(null); } this._render(); },
      add_close: () => { this._adding = false; this._render(); },
      menu: () => { this._menu = !this._menu; this._render(); }, msg_close: () => { this._msg = null; this._render(); },
      panel_open: () => { this._panelHidden = false; this._render(); },
      edit_corners: () => { this._mode = "precise"; this._render(); }, corners_done: () => { this._mode = "quick"; this._render(); },
      missing: () => this._propose(true), propose: () => this._propose(false), export: () => this._export(), reload: () => this._reload(),
      "import-btn": () => root.querySelector('[data-f="import"]').click(), save: () => this._save(), cancel: () => this._cancel(),
      apply: () => { const p = this._preview; this._preview = null; this._commit(l => Object.assign(l, clone(p.layout), { revision: l.revision })); },
      "no-apply": () => { this._preview = null; this._render(); },
      wall_apply: () => this._applyWallLength(root.querySelector('[data-f="wall_len"]').value),
      snap90: () => { this._snap90 = !this._snap90; this._render(); }, join: () => this._joinRooms(),
      panel_toggle: () => { this._panelHidden = !this._panelHidden; this._render(); },
      calibrate: () => this._setPlanScale(root.querySelector('[data-f="scale_m"]').value),
      window_out: () => this._windowsOut([this._sel.id]), windows_out: () => this._windowsOut(this._insideWindows().map(o => o.id)),
      rotate: () => this._commit(l => { const r = l.rooms.find(x => x.id === this._sel.id); r.polygon = rotate90(r.polygon); r.provenance = "user"; }),
      window: () => this._addWindow(this._sel.id), delete: () => this._deleteSelected(),
      connect: () => {
        const to = root.querySelector('[data-f="conn_to"]').value, kind = root.querySelector('[data-f="conn_kind"]').value, from = this._sel.id;
        this._commit(l => l.connections.push({ id: `c_${from}_${to}_${Date.now().toString(36)}`, a: from, b: to, kind, confirmed: true, provenance: "user" }));
      },
    };
    // the "more" menu closes after an action in it (a toggle such as "Snap to 90°" keeps it open)
    on(".menu [data-a]", el => { if (!["snap90", "menu", "import-btn"].includes(el.dataset.a)) { this._menu = false; el.closest(".menu").hidden = true; } });
    on("[data-a]", el => (el.dataset.a === "square" ? this._squareCorner(Number(el.dataset.corner), el.dataset.keep) : actions[el.dataset.a] && actions[el.dataset.a]()));
    on("[data-shape]", el => { this._shape = el.dataset.shape; this._render(); });
    on('[data-f="grid"]', el => { this._grid = Number(el.value); this._render(); }, "change");
    on('[data-f="view_floor"]', el => { this._floor = el.value; this._sel = null; this._setTool(null); this._fit(); this._render(); this._loadUnderlay(el.value); }, "change");
    this._bindUnderlay(root, on);
    on('[data-f="import"]', el => { if (el.files && el.files[0]) this._import(el.files[0]); }, "change");
    on('[data-f="north"]', el => this._commit(l => { const v = Number(el.value); setNorth(l, Number.isFinite(v) ? v : 0); }), "change");
    on('[data-f="north_confirmed"]', el => this._commit(l => { l.building.north_confirmed = el.checked; }), "change");
    this._bindCompass(root);
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
    on("[data-conv-c]", el => this._convertConnection(el.dataset.convC));
    const doorField = key => openingField(key, (o, v) => { if (v) o[key] = v; else delete o[key]; });
    doorField("door_hinge"); doorField("door_swing");
    on('[data-f="wall_fixed"]', el => { this._wallFixed = el.value; this._render(); }, "change");
    on('[data-f="corner_lock"]', el => this._commit(l => {
      const r = l.rooms.find(x => x.id === this._sel.id), c = Number(el.dataset.corner), set = new Set(r.locked_corners || []);
      if (el.checked) set.add(c); else set.delete(c);
      if (set.size) r.locked_corners = [...set].sort((x, y) => x - y); else delete r.locked_corners;
    }), "change");
    on('[data-f="wall_lock"]', el => this._commit(l => {
      const r = l.rooms.find(x => x.id === this._sel.id), i = this._sel.index, set = new Set(r.locked_walls || []);
      if (el.checked) set.add(i); else set.delete(i);
      if (set.size) r.locked_walls = [...set].sort((x, y) => x - y); else delete r.locked_walls;
    }), "change");
  }
}

if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, FreshAirIQHouseLayoutEditor);
