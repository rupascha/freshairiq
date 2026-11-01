// FreshAirIQ house map – plan geometry, validation and wind helpers.
// Mirrors custom_components/freshairiq/house_layout.py and house_wind.py so the
// editor can check a drawing before it is saved (the server validates again).
// Plan coordinates: metres, x to the right, y UP; north_deg = compass bearing of "up".

export const EPS = 1e-6;
export const WALL_TOLERANCE = 0.05;
export const LIMITS = { floors: 30, rooms: 200, vertices: 64, openings: 800, connections: 800, coordinate: 10000 };
export const OPENING_KINDS = ["window", "door", "roof_window", "passage", "vent"];
export const OPENING_MECHANICS = ["unknown", "turn_tilt", "casement", "tilt_only", "sliding", "roof", "door", "fixed_vent"];
export const CONNECTION_KINDS = ["open_passage", "door", "stairs", "shaft", "duct"];

export const signedArea = pts => {
  let total = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length];
    total += x1 * y2 - x2 * y1;
  }
  return total / 2;
};
export const ccw = pts => (signedArea(pts) >= 0 ? pts.map(p => [p[0], p[1]]) : pts.slice().reverse().map(p => [p[0], p[1]]));
const orient = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
export const onSegment = (a, b, p, tol = EPS) => {
  if (Math.abs(orient(a, b, p)) > tol * Math.max(1, dist(a, b))) return false;
  return Math.min(a[0], b[0]) - tol <= p[0] && p[0] <= Math.max(a[0], b[0]) + tol && Math.min(a[1], b[1]) - tol <= p[1] && p[1] <= Math.max(a[1], b[1]) + tol;
};
export const segmentsCross = (a, b, c, d) => {
  const d1 = orient(c, d, a), d2 = orient(c, d, b), d3 = orient(a, b, c), d4 = orient(a, b, d);
  return ((d1 > EPS && d2 < -EPS) || (d1 < -EPS && d2 > EPS)) && ((d3 > EPS && d4 < -EPS) || (d3 < -EPS && d4 > EPS));
};
export const selfIntersects = pts => {
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n];
    for (let j = i + 1; j < n; j++) {
      if ((j + 1) % n === i || (i + 1) % n === j) continue;
      const c = pts[j], d = pts[(j + 1) % n];
      if (segmentsCross(a, b, c, d) || onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b)) return true;
    }
  }
  return false;
};
export const pointInPolygon = (p, pts) => {
  let inside = false;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    if (onSegment(a, b, p, WALL_TOLERANCE / 10)) return "boundary";
    if ((a[1] > p[1]) !== (b[1] > p[1])) {
      const x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]);
      if (p[0] < x) inside = !inside;
    }
  }
  return inside ? "inside" : "outside";
};
export const interiorPoint = pts => {
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[(i - 1 + n) % n], b = pts[i], c = pts[(i + 1) % n];
    if (orient(a, b, c) <= EPS) continue;
    const centre = [(a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3];
    if (pointInPolygon(centre, pts) === "inside") return centre;
  }
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
};
// Label anchor: area centroid when it lies inside (convex/most rooms), otherwise an inside point (L/U shapes).
export const labelPoint = pts => {
  const area = signedArea(pts);
  if (Math.abs(area) > EPS) {
    let cx = 0, cy = 0;
    for (let i = 0; i < pts.length; i++) {
      const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length], f = x1 * y2 - x2 * y1;
      cx += (x1 + x2) * f; cy += (y1 + y2) * f;
    }
    const c = [cx / (6 * area), cy / (6 * area)];
    if (pointInPolygon(c, pts) === "inside") return c;
  }
  return interiorPoint(pts);
};
export const polygonsOverlap = (first, second) => {
  for (let i = 0; i < first.length; i++)
    for (let j = 0; j < second.length; j++)
      if (segmentsCross(first[i], first[(i + 1) % first.length], second[j], second[(j + 1) % second.length])) return true;
  if (first.some(p => pointInPolygon(p, second) === "inside") || second.some(p => pointInPolygon(p, first) === "inside")) return true;
  return pointInPolygon(interiorPoint(first), second) === "inside" || pointInPolygon(interiorPoint(second), first) === "inside";
};
export const edgePoint = (pts, index, offset) => {
  const a = pts[index], b = pts[(index + 1) % pts.length];
  return [a[0] + (b[0] - a[0]) * offset, a[1] + (b[1] - a[1]) * offset];
};
export const edgeLength = (pts, index) => dist(pts[index], pts[(index + 1) % pts.length]);
export const outwardNormal = (pts, index) => {
  const a = pts[index], b = pts[(index + 1) % pts.length], len = dist(a, b) || 1;
  return [(b[1] - a[1]) / len, -(b[0] - a[0]) / len];
};
export const normalBearing = (normal, northDeg) => ((Math.atan2(normal[0], normal[1]) * 180 / Math.PI + northDeg) % 360 + 360) % 360;
export const edgeBearing = (pts, index, northDeg) => normalBearing(outwardNormal(pts, index), northDeg);
// Plan direction (unit vector, y up) of a compass bearing.
export const bearingVector = (bearing, northDeg) => {
  const r = (bearing - northDeg) * Math.PI / 180;
  return [Math.sin(r), Math.cos(r)];
};
export const projectOnSegment = (p, a, b) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], len2 = dx * dx + dy * dy || 1;
  const t = Math.min(Math.max(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2, 0), 1);
  const q = [a[0] + dx * t, a[1] + dy * t];
  return { t, point: q, distance: dist(p, q) };
};
export const nearestEdge = (pts, p) => {
  let best = { index: 0, t: 0.5, distance: Infinity };
  for (let i = 0; i < pts.length; i++) {
    const proj = projectOnSegment(p, pts[i], pts[(i + 1) % pts.length]);
    if (proj.distance < best.distance) best = { index: i, t: proj.t, distance: proj.distance, point: proj.point };
  }
  return best;
};
export const bbox = polygons => {
  const pts = polygons.flat();
  if (!pts.length) return { minX: 0, minY: 0, maxX: 10, maxY: 10 };
  return { minX: Math.min(...pts.map(p => p[0])), minY: Math.min(...pts.map(p => p[1])), maxX: Math.max(...pts.map(p => p[0])), maxY: Math.max(...pts.map(p => p[1])) };
};
export const snap = (value, grid) => (grid > 0 ? Math.round(value / grid) * grid : value);
export const round3 = v => Math.round(v * 1000) / 1000;

const issue = (code, object, id, index) => (index === undefined ? { code, object, id } : { code, object, id, index });
export const validatePolygon = room => {
  const pts = room.polygon || [];
  if (pts.length < 3) return [issue("E_POLY_POINTS", "room", room.id)];
  if (pts.length > LIMITS.vertices) return [issue("E_LIMIT_VERTICES", "room", room.id)];
  if (pts.some(p => !Number.isFinite(p[0]) || !Number.isFinite(p[1]) || Math.abs(p[0]) > LIMITS.coordinate || Math.abs(p[1]) > LIMITS.coordinate)) return [issue("E_POLY_NONFINITE", "room", room.id)];
  for (let i = 0; i < pts.length; i++) if (edgeLength(pts, i) < WALL_TOLERANCE) return [issue("E_POLY_DEGENERATE", "room", room.id, i)];
  if (selfIntersects(pts)) return [issue("E_POLY_SELF_INTERSECT", "room", room.id)];
  if (Math.abs(signedArea(pts)) < WALL_TOLERANCE) return [issue("E_POLY_AREA", "room", room.id)];
  return [];
};
export const validateLayout = layout => {
  const issues = [];
  const floors = new Set((layout.floors || []).map(f => f.id));
  const valid = new Map();
  for (const room of layout.rooms || []) {
    if (!floors.has(room.floor_id)) issues.push(issue("E_FLOOR_UNKNOWN", "room", room.id));
    const own = validatePolygon(room);
    issues.push(...own);
    if (!own.length) valid.set(room.id, room);
  }
  const rooms = [...valid.values()];
  for (let i = 0; i < rooms.length; i++)
    for (let j = i + 1; j < rooms.length; j++)
      if (rooms[i].floor_id === rooms[j].floor_id && polygonsOverlap(rooms[i].polygon, rooms[j].polygon)) issues.push(issue("E_ROOM_OVERLAP", "room", rooms[j].id));
  for (const opening of layout.openings || []) {
    const room = (layout.rooms || []).find(r => r.id === opening.room_id);
    if (!room) { issues.push(issue("E_OPENING_ROOM", "opening", opening.id)); continue; }
    if (!valid.has(room.id)) continue;
    if (!Number.isInteger(opening.edge) || opening.edge < 0 || opening.edge >= room.polygon.length) { issues.push(issue("E_OPENING_EDGE", "opening", opening.id)); continue; }
    if (!(opening.offset >= 0 && opening.offset <= 1)) issues.push(issue("E_OPENING_OFFSET", "opening", opening.id));
    else if (opening.width_m != null && (opening.width_m <= 0 || opening.width_m > edgeLength(room.polygon, opening.edge) + WALL_TOLERANCE)) issues.push(issue("E_OPENING_WIDTH", "opening", opening.id));
  }
  return issues;
};

// ---------------------------------------------------------------------------- wind (custom sensors)
export const POINTS_EN = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
export const POINTS_DE = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const TO_MS = { "m/s": 1, "km/h": 1 / 3.6, mph: 0.44704, kn: 0.514444, kt: 0.514444, knots: 0.514444, "ft/s": 0.3048 };
export const parseBearing = value => {
  if (value == null || typeof value === "boolean") return null;
  const text = String(value).trim().toUpperCase();
  const idx = POINTS_EN.indexOf(text) >= 0 ? POINTS_EN.indexOf(text) : POINTS_DE.indexOf(text);
  if (idx >= 0) return idx * 22.5;
  const number = Number(text.replace(",", "."));
  if (!text || !Number.isFinite(number) || number < 0 || number > 360) return null;
  return number % 360;
};
export const speedMs = (value, unit) => {
  const number = Number(value);
  if (value == null || value === "" || typeof value === "boolean" || !Number.isFinite(number) || number < 0) return null;
  if (!unit) return number / 3.6;
  const factor = TO_MS[String(unit).trim().toLowerCase()];
  return factor == null ? null : number * factor;
};
export const compass = (bearing, language) => (bearing == null ? null : (language === "de" ? POINTS_DE : POINTS_EN)[Math.floor(((bearing % 360) + 11.25) / 22.5) % 16]);
export const angleBetween = (a, b) => { const d = Math.abs((((a - b) % 360) + 360) % 360); return d > 180 ? 360 - d : d; };
// Smooth a changing bearing (shortest way round) so the arrow does not spin on gusts.
export const smoothBearing = (previous, next, factor = 0.35) => {
  if (previous == null) return next;
  if (next == null) return previous;
  const delta = ((next - previous + 540) % 360) - 180;
  return ((previous + delta * factor) % 360 + 360) % 360;
};
