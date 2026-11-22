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
  if (pointInPolygon(interiorPoint(first), second) === "inside" || pointInPolygon(interiorPoint(second), first) === "inside") return true;
  return flushOverlap(first, second);
};
// Both rooms run along one wall stretch with their insides on the same side – a flush overlap that crosses no wall
// (two 4 m squares 30 cm into each other along a common side). Touching at a wall or a corner is no overlap.
export const flushOverlap = (first, second) => {
  for (let i = 0; i < first.length; i++) {
    const a = first[i], b = first[(i + 1) % first.length], len = dist(a, b);
    if (len < EPS) continue;
    const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len, own = outwardNormal(first, i);
    for (let j = 0; j < second.length; j++) {
      const c = second[j], d = second[(j + 1) % second.length];
      if (Math.abs((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) > EPS || Math.abs((d[0] - a[0]) * uy - (d[1] - a[1]) * ux) > EPS) continue;
      const tc = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy, td = (d[0] - a[0]) * ux + (d[1] - a[1]) * uy;
      if (Math.min(len, Math.max(tc, td)) - Math.max(0, Math.min(tc, td)) <= EPS) continue;
      const other = outwardNormal(second, j);
      if (own[0] * other[0] + own[1] * other[1] > 0) return true;
    }
  }
  return false;
};
export const edgePoint = (pts, index, offset) => {
  const a = pts[index], b = pts[(index + 1) % pts.length];
  return [a[0] + (b[0] - a[0]) * offset, a[1] + (b[1] - a[1]) * offset];
};
export const edgeLength = (pts, index) => dist(pts[index], pts[(index + 1) % pts.length]);
// Hotfix after review (F03): the outward side follows the polygon's real orientation – a room drawn clockwise has
// its outside on the other side of each wall than one drawn counter-clockwise (corner indices stay as drawn).
export const outwardNormal = (pts, index) => {
  const a = pts[index], b = pts[(index + 1) % pts.length], len = dist(a, b) || 1, s = signedArea(pts) < 0 ? -1 : 1;
  return [s * (b[1] - a[1]) / len, -s * (b[0] - a[0]) / len];
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
    // 0.26.6.0 UI hotfix: placed as interior, it must stay on a wall shared with another room (as house_layout.validate)
    if (opening.interior === true && !openingLink((layout.rooms || []).filter(r => valid.has(r.id)), room, opening)) { issues.push(issue("E_OPENING_INTERIOR", "opening", opening.id)); continue; }
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

// 0.26.5.5: walls. Each edge of a room is cut into parts – shared with another room of the same floor
// (interior: both walls on one line within WALL_TOLERANCE, overlapping by more than WALL_TOLERANCE) or not
// (exterior). A corner point alone or a wall a little apart is no shared wall.
// A partition wall the user confirmed between two rooms (room.partitions = [{room, thickness_m, wall, other_wall}],
// the editor's "take as shared wall"): the two confirmed walls – this room's ``wall``, the other room's
// ``other_wall`` – are one wall within its thickness + WALL_TOLERANCE for walls, doors and passages
// (house_layout.partition_tolerance). Every other wall of the pair keeps WALL_TOLERANCE. It never makes a way for air.
export const MAX_PARTITION = 0.5;
export const partitionsBetween = (a, b) => {
  const out = [];
  for (const [own, other, flip] of [[a, b, false], [b, a, true]]) for (const item of (own && own.partitions) || []) {
    const t = Number(item && item.thickness_m);
    if (!item || item.room !== (other && other.id) || !(t > 0 && t <= MAX_PARTITION) || !Number.isInteger(item.wall) || !Number.isInteger(item.other_wall)) continue;
    out.push(flip ? { wa: item.other_wall, wb: item.wall, t } : { wa: item.wall, wb: item.other_wall, t });
  }
  return out;
};
// ``ea`` / ``eb``: the walls in question (null = any wall of that room)
export const partitionTol = (a, b, ea = null, eb = null) => {
  const hit = partitionsBetween(a, b).filter(p => (ea == null || p.wa === ea) && (eb == null || p.wb === eb));
  return hit.length ? Math.max(...hit.map(p => p.t)) + WALL_TOLERANCE : WALL_TOLERANCE;
};
export const wallParts = (rooms, room) => {
  const pts = room.polygon || [], out = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length], len = dist(a, b);
    if (len < EPS) continue;
    const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len;
    const off = p => Math.abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux), along = p => (p[0] - a[0]) * ux + (p[1] - a[1]) * uy;
    const shared = [];
    for (const other of rooms) {
      if (other.id === room.id || other.floor_id !== room.floor_id || !Array.isArray(other.polygon) || other.polygon.length < 3) continue;
      other.polygon.forEach((c, j) => {
        const d = other.polygon[(j + 1) % other.polygon.length], tol = partitionTol(room, other, i, j);
        if (off(c) > tol || off(d) > tol) return;
        const lo = Math.max(Math.min(along(c), along(d)), 0), hi = Math.min(Math.max(along(c), along(d)), len);
        if (hi - lo > WALL_TOLERANCE) shared.push([lo, hi]);
      });
    }
    shared.sort((x, y) => x[0] - y[0]);
    const merged = [];
    for (const s of shared) { const last = merged[merged.length - 1]; if (last && s[0] <= last[1] + EPS) last[1] = Math.max(last[1], s[1]); else merged.push(s.slice()); }
    const at = t => [a[0] + ux * t, a[1] + uy * t];
    let pos = 0;
    for (const [lo, hi] of merged) {
      if (lo - pos > EPS) out.push({ edge: i, a: at(pos), b: at(lo), interior: false });
      out.push({ edge: i, a: at(lo), b: at(hi), interior: true });
      pos = hi;
    }
    if (len - pos > EPS) out.push({ edge: i, a: at(pos), b: b.slice(), interior: false });
  }
  return out;
};
// Snap a moved room to the walls of its neighbours: the smallest x and y shift (each within ``tol``) that puts
// one of its corners on the line of a neighbour's corner. Returns the shift and the guide lines (x / y or null).
export const snapToNeighbours = (polygon, others, tol) => {
  let best = { dx: 0, gx: null, ex: tol }, bestY = { dy: 0, gy: null, ey: tol };
  for (const other of others) for (const q of other.polygon || []) for (const p of polygon) {
    const ex = Math.abs(q[0] - p[0]), ey = Math.abs(q[1] - p[1]);
    if (ex < best.ex) best = { dx: q[0] - p[0], gx: q[0], ex };
    if (ey < bestY.ey) bestY = { dy: q[1] - p[1], gy: q[1], ey };
  }
  return { dx: best.dx, dy: bestY.dy, gx: best.gx, gy: bestY.gy };
};
// Hotfix 0.26.6.0: the room on the other side of an opening – only when the whole span of the opening lies on
// that room's wall (same floor, 5 cm). The rule of house_layout.opening_neighbour and of the editor
// (openingTarget); it is computed from the current geometry, so a room moved later never keeps a stale target.
export const openingLink = (rooms, room, o) => {
  const pts = room && room.polygon;
  if (!Array.isArray(pts) || pts.length < 3 || !(o.edge >= 0 && o.edge < pts.length)) return null;
  const len = edgeLength(pts, o.edge) || 1, half = Math.min(Math.max(o.width_m || Math.min(0.9, len * 0.4), 0), len) / len / 2;
  const offset = Number.isFinite(Number(o.offset)) ? Number(o.offset) : 0.5, lo = Math.max(offset - half, 0), hi = Math.min(offset + half, 1);
  const samples = [0, 1, 2, 3, 4].map(k => edgePoint(pts, o.edge, lo + (hi - lo) * k / 4));
  return rooms.find(other => other.id !== room.id && other.floor_id === room.floor_id && Array.isArray(other.polygon) && other.polygon.length >= 3
    && samples.every(p => other.polygon.some((c, i) => onSegment(c, other.polygon[(i + 1) % other.polygon.length], p, partitionTol(room, other, o.edge, i))))) || null;
};
// A wall two rooms really share: the longest common stretch, at least as long as the narrowest opening (0.3).
// A shared corner, a few centimetres or a wall on another floor is none.
export const MIN_SHARED_WALL = 0.3;
export const sharedWall = (a, b) => {
  const walls = wallParts([a, b], a).filter(w => w.interior).sort((x, y) => dist(y.a, y.b) - dist(x.a, x.b));
  return walls.length && dist(walls[0].a, walls[0].b) >= MIN_SHARED_WALL ? walls[0] : null;
};
// Connection kinds that are a way through the wall the two rooms share; stairs, shafts and ducts are not.
export const PHYSICAL_CONNECTIONS = new Set(["door", "open_passage"]);
// Where air passes from room a to room b: an opening whose whole span lies on the wall a and b share (the one
// named by ``via`` first), else – for a door or open passage in the plan's connections – the middle of the wall
// they really share. ``n`` points from a to b. null: no physical way between them – air never goes through a wall.
export const passage = (layout, aId, bId, via = null) => {
  const rooms = layout.rooms || [], openings = layout.openings || [];
  const a = rooms.find(r => r.id === aId), b = rooms.find(r => r.id === bId);
  if (!a || !b) return null;
  const between = o => {
    if (!o || (o.room_id !== aId && o.room_id !== bId)) return false;
    const own = o.room_id === aId ? a : b, other = own === a ? b : a, link = openingLink(rooms, own, o);
    return !!link && link.id === other.id;  // a stored target alone (also a stale one) is no way through
  };
  const named = openings.find(o => o.id === via);
  for (const o of between(named) ? [named, ...openings.filter(between)] : openings.filter(between)) {
    const r = o.room_id === aId ? a : b;
    const n = outwardNormal(r.polygon, o.edge);
    return { at: edgePoint(r.polygon, o.edge, o.offset), n: r === a ? n : [-n[0], -n[1]] };
  }
  const linked = (layout.connections || []).some(c => PHYSICAL_CONNECTIONS.has(c.kind) && ((c.a === aId && c.b === bId) || (c.a === bId && c.b === aId)));
  const wall = linked ? sharedWall(a, b) : null;
  if (!wall) return null;
  return { at: [(wall.a[0] + wall.b[0]) / 2, (wall.a[1] + wall.b[1]) / 2], n: outwardNormal(a.polygon, wall.edge) };
};
// The route of an air path {from, to, rooms, via, kind}: the outside opening it enters by, each room's middle,
// straight through the passage between two rooms, and the outside opening it leaves by – plus ``outside``
// plan units beyond it, so the air visibly streams out again. ``strict``: the route ends where two rooms have
// no passage (wind streams); otherwise that step is drawn straight (the air-path layer is a hypothesis).
export const airRoute = (layout, path, { outside = 0, strict = false, step = 0.35 } = {}) => {
  const rooms = layout.rooms || [], openings = layout.openings || [];
  const wallOf = id => {
    const o = openings.find(x => x.id === id), r = o && rooms.find(x => x.id === o.room_id);
    return r && o.edge >= 0 && o.edge < r.polygon.length ? { at: edgePoint(r.polygon, o.edge, o.offset), n: outwardNormal(r.polygon, o.edge) } : null;
  };
  const centre = id => { const r = rooms.find(x => x.id === id); return r ? labelPoint(r.polygon) : null; };
  const points = [];
  let complete = true;
  const start = path.from ? wallOf(path.from) : null;
  if (start) points.push(start.at);
  const ids = path.rooms || [];
  for (let i = 0; i < ids.length; i++) {
    const c = centre(ids[i]);
    if (!c) { complete = false; break; }
    points.push(c);
    if (i === ids.length - 1) break;
    const p = passage(layout, ids[i], ids[i + 1], (path.via || [])[i]);
    if (p) points.push([p.at[0] - p.n[0] * step, p.at[1] - p.n[1] * step], p.at, [p.at[0] + p.n[0] * step, p.at[1] + p.n[1] * step]);
    else if (strict) { complete = false; break; }
  }
  const end = complete && path.to && path.to !== path.from && !String(path.kind || "").startsWith("exhaust") ? wallOf(path.to) : null;
  if (end) {
    points.push(end.at);
    if (outside > 0) points.push([end.at[0] + end.n[0] * outside, end.at[1] + end.n[1] * outside]);
  }
  return { points, complete, exits: !!end && outside > 0 };
};

// ---------------------------------------------------------------------------- 0.26.6.0(2): walls, openings, wall lengths
const onLineOf = (a, b, p, tol) => {
  const len = dist(a, b);
  return len > EPS && Math.abs((p[0] - a[0]) * (b[1] - a[1]) - (p[1] - a[1]) * (b[0] - a[0])) / len <= tol;
};
// The parts of segment a→b that none of ``segments`` (lying on its line) covers.
const uncovered = (a, b, segments, tol = WALL_TOLERANCE) => {
  const len = dist(a, b);
  if (len < EPS) return [];
  const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len, along = p => (p[0] - a[0]) * ux + (p[1] - a[1]) * uy;
  const cover = segments.filter(([p, q]) => onLineOf(a, b, p, tol) && onLineOf(a, b, q, tol))
    .map(([p, q]) => [Math.max(Math.min(along(p), along(q)), 0), Math.min(Math.max(along(p), along(q)), len)])
    .filter(([lo, hi]) => hi - lo > EPS).sort((x, y) => x[0] - y[0]);
  const out = [];
  let pos = 0;
  for (const [lo, hi] of cover) { if (lo - pos > EPS) out.push([pos, lo]); pos = Math.max(pos, hi); }
  if (len - pos > EPS) out.push([pos, len]);
  return out.map(([lo, hi]) => [[a[0] + ux * lo, a[1] + uy * lo], [a[0] + ux * hi, a[1] + uy * hi]]);
};
// The span of an opening on its wall (the drawn width everywhere: stored, else min(0.9, 40 % of the wall)).
export const openingSpan = (room, o) => {
  const pts = room && room.polygon;
  if (!Array.isArray(pts) || pts.length < 3 || !(o.edge >= 0 && o.edge < pts.length)) return null;
  const len = edgeLength(pts, o.edge) || 1, half = Math.min(Math.max(o.width_m || Math.min(0.9, len * 0.4), 0), len) / len / 2;
  const offset = Number.isFinite(Number(o.offset)) ? Number(o.offset) : 0.5;
  return [edgePoint(pts, o.edge, Math.max(offset - half, 0)), edgePoint(pts, o.edge, Math.min(offset + half, 1))];
};
// Every wall line of one floor – the same for the house map and the editor: exterior walls (thick), a wall two
// rooms share drawn once (thin, also where it is shared only partly), and an open passage or a door as a real gap
// in the wall on both sides (exact width and position; a moved or removed one closes the wall again).
export const wallSegments = (rooms, openings = []) => {
  const drawable = rooms.filter(r => Array.isArray(r.polygon) && r.polygon.length >= 3);
  const gaps = [];
  for (const o of openings) {
    if (o.kind !== "passage" && o.kind !== "door") continue;
    const span = openingSpan(drawable.find(r => r.id === o.room_id), o);
    if (span) gaps.push(span);
  }
  const shared = [], out = [];
  // an interior part may be one side of a partition wall: a door's gap reaches across its thickness
  const confirmed = drawable.some(r => (r.partitions || []).length);
  const thick = (room, edge) => (confirmed ? Math.max(WALL_TOLERANCE, ...drawable.filter(r => r.id !== room.id).map(r => partitionTol(room, r, edge))) : WALL_TOLERANCE);
  for (const room of drawable) for (const w of wallParts(drawable, room)) {
    const reach = w.interior ? thick(room, w.edge) : WALL_TOLERANCE;
    const open = uncovered(w.a, w.b, gaps, reach);
    for (const [a, b] of w.interior ? open.flatMap(([p, q]) => uncovered(p, q, shared)) : open) {
      out.push({ edge: w.edge, room: room.id, a, b, interior: w.interior });
      if (w.interior) shared.push([a, b]);
    }
  }
  return out;
};
// Change the length of wall ``edge`` of room ``roomId`` to ``length``; corner ``fixed`` ("start" = polygon[edge],
// "end" = the next corner) stays. The wall at the moving corner is shifted parallel (direction and length kept), so
// a rectangle stays a rectangle and nothing else is bent; corners of other rooms on the same floor that lie on the
// moving corner or the shifted wall move along – a shared wall stays shared. Returns {polygons: {id: polygon}} or
// {error}; the caller checks the result (shape, overlaps, locked walls, openings) before taking it.
// ---------------------------------------------------------------------- 0.26.6.0(10): measuring room by room
// Locks are separate properties: a locked LENGTH (room.locked_walls = edge indices) keeps a wall's length but lets it
// move and turn; a locked ANGLE (room.locked_corners = corner indices) keeps the angle at a corner; everything else is
// free geometry. An edit moves as little as possible and never changes a locked value – or it is refused with the
// wall or corner that stands in the way.
// The angle inside the room at corner i in degrees (0–360: the inner corner of an L or U shape is 270°).
export const cornerAngle = (pts, i) => {
  const n = pts.length, a = pts[(i - 1 + n) % n], v = pts[i], b = pts[(i + 1) % n];
  const u = [a[0] - v[0], a[1] - v[1]], w = [b[0] - v[0], b[1] - v[1]], lu = Math.hypot(u[0], u[1]), lw = Math.hypot(w[0], w[1]);
  if (lu < EPS || lw < EPS) return 0;
  const open = Math.acos(Math.min(Math.max((u[0] * w[0] + u[1] * w[1]) / (lu * lw), -1), 1)) * 180 / Math.PI;
  let area = 0;
  for (let k = 0; k < n; k++) area += pts[k][0] * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * pts[k][1];
  const turn = (v[0] - a[0]) * (b[1] - v[1]) - (v[1] - a[1]) * (b[0] - v[0]);
  return turn * area < 0 ? 360 - open : open;
};
// A right corner: 90° outside corner or 270° inner corner of an L or U shape.
export const isRightCorner = (pts, i, tol = 0.05) => { const a = cornerAngle(pts, i); return Math.abs(a - 90) < tol || Math.abs(a - 270) < tol; };
// Move corner ``idx`` by ``delta`` while ``anchor`` stays. Walking away from the anchor (``step`` +1/−1), the next
// wall takes up the change – unless its length or the angle at one of its ends is locked: then the next corner moves
// along (that stretch keeps its shape) and the wall after it takes up the change. Reaching the anchor: refused.
export const carryCorner = (pts, idx, delta, step, anchor, lockedEdges = new Set(), lockedCorners = new Set()) => {
  const n = pts.length, moved = [idx];
  let k = idx;
  for (let guard = 0; guard < n; guard++) {
    const next = (k + step + n) % n, e = step > 0 ? k : next;
    if (!lockedEdges.has(e) && !lockedCorners.has(k) && !lockedCorners.has(next)) break;
    if (next === anchor) return { error: "locked", edge: lockedEdges.has(e) ? e : null, corner: lockedCorners.has(next) ? next : lockedCorners.has(k) ? k : null };
    moved.push(next); k = next;
  }
  const out = pts.map(p => p.slice());
  for (const i of moved) out[i] = [round3(out[i][0] + delta[0]), round3(out[i][1] + delta[1])];
  return { pts: out, moved };
};
const roomLocks = room => [new Set(room.locked_walls || []), new Set(room.locked_corners || [])];
// Change the length of wall ``edge`` only: corner ``fixed`` ("start" = polygon[edge], "end" = the next corner)
// stays, the other end moves along the wall's own direction; the next wall (away from the fixed corner) takes up the
// change – the opposite wall of a rectangle keeps its length (the room may stop being a rectangle). Locked lengths
// and angles are carried (see carryCorner). Other rooms are not changed; the editor refuses a clash with them.
// Returns {polygons} or {error, edge?, corner?}.
export const resizeWall = (layout, roomId, edge, length, fixed = "start") => {
  const room = (layout.rooms || []).find(r => r.id === roomId);
  const pts = room && room.polygon, n = pts ? pts.length : 0;
  if (!room || n < 3 || !(edge >= 0 && edge < n)) return { error: "wall" };
  if (!(Number(length) >= 0.1)) return { error: "length" };
  const i0 = edge, i1 = (edge + 1) % n;
  const F = fixed === "end" ? i1 : i0, M = fixed === "end" ? i0 : i1, step = fixed === "end" ? -1 : 1;
  const old = dist(pts[F], pts[M]);
  if (old < EPS) return { error: "wall" };
  const k = Number(length) / old, target = [pts[F][0] + (pts[M][0] - pts[F][0]) * k, pts[F][1] + (pts[M][1] - pts[F][1]) * k];
  const [lockedEdges, lockedCorners] = roomLocks(room);
  lockedEdges.delete(edge);
  const res = carryCorner(pts, M, [target[0] - pts[M][0], target[1] - pts[M][1]], step, F, lockedEdges, lockedCorners);
  if (res.error) return res;
  return { polygons: { [room.id]: res.pts } };   // neighbouring rooms are never moved along (a clash is refused)
};
// The wall made ``length`` long by moving the end wall at its free end in parallel (both of its corners alike): every
// angle stays, the wall after it takes up the change. Triangles have no such end wall – resizeWall then.
export const stretchWall = (layout, roomId, edge, length, fixed = "start") => {
  const room = (layout.rooms || []).find(r => r.id === roomId);
  const pts = room && room.polygon, n = pts ? pts.length : 0;
  if (n < 4 || !(edge >= 0 && edge < n) || !(Number(length) >= 0.1)) return resizeWall(layout, roomId, edge, length, fixed);
  const i1 = (edge + 1) % n, F = fixed === "end" ? i1 : edge, M = fixed === "end" ? edge : i1, N = fixed === "end" ? (M - 1 + n) % n : (M + 1) % n;
  const old = dist(pts[F], pts[M]);
  if (old < EPS) return { error: "wall" };
  const k = (Number(length) - old) / old, d = [(pts[M][0] - pts[F][0]) * k, (pts[M][1] - pts[F][1]) * k];
  return { polygons: { [room.id]: pts.map((p, i) => (i === M || i === N ? [round3(p[0] + d[0]), round3(p[1] + d[1])] : p.slice())) } };
};
// Make the angle at corner ``corner`` exactly 90° (an inner corner of an L or U shape: 270°): the wall ``keep`` ("in" = the wall ending at the corner, "out" =
// the wall starting there) keeps its direction, the other wall turns about the corner and keeps its length; the wall
// after it takes up the change (locks are carried). Only this corner is changed – no other corner is squared.
export const squareCorner = (layout, roomId, corner, keep = "in") => {
  const room = (layout.rooms || []).find(r => r.id === roomId);
  const pts = room && room.polygon, n = pts ? pts.length : 0;
  if (!room || n < 3 || !(corner >= 0 && corner < n)) return { error: "wall" };
  const V = pts[corner], prev = (corner - 1 + n) % n, next = (corner + 1) % n;
  const [lockedEdges, lockedCorners] = roomLocks(room);
  if (isRightCorner(pts, corner)) return { polygons: { [room.id]: pts.map(p => p.slice()) } };
  if (lockedCorners.has(corner)) return { error: "locked", corner, edge: null };
  const fixedDir = keep === "in" ? [V[0] - pts[prev][0], V[1] - pts[prev][1]] : [pts[next][0] - V[0], pts[next][1] - V[1]];
  const W = keep === "in" ? next : prev, cur = [pts[W][0] - V[0], pts[W][1] - V[1]], len = Math.hypot(cur[0], cur[1]), fl = Math.hypot(fixedDir[0], fixedDir[1]);
  if (len < EPS || fl < EPS) return { error: "wall" };
  const opts = [[-fixedDir[1] / fl, fixedDir[0] / fl], [fixedDir[1] / fl, -fixedDir[0] / fl]];
  const dir = opts.reduce((b, o) => (o[0] * cur[0] + o[1] * cur[1] > b[0] * cur[0] + b[1] * cur[1] ? o : b));
  const target = [V[0] + dir[0] * len, V[1] + dir[1] * len];
  lockedEdges.delete(keep === "in" ? corner : prev);   // the turning wall keeps its length anyway
  lockedCorners.delete(W);
  const res = carryCorner(pts, W, [target[0] - pts[W][0], target[1] - pts[W][1]], keep === "in" ? 1 : -1, corner, lockedEdges, lockedCorners);
  if (res.error) return res;
  if ((room.locked_corners || []).includes(W) && Math.abs(cornerAngle(res.pts, W) - cornerAngle(pts, W)) > 0.3) return { error: "locked", corner: W, edge: null };
  return { polygons: { [room.id]: res.pts } };
};
// During a corner drag: when the angle there is within ``tol`` degrees of 90°, the corner is placed on the circle
// over its two neighbours (Thales) where the angle is exactly 90° – the nearest such point.
export const snapRightAngle = (prev, point, next, tol = 6) => {
  const u = [prev[0] - point[0], prev[1] - point[1]], w = [next[0] - point[0], next[1] - point[1]], lu = Math.hypot(u[0], u[1]), lw = Math.hypot(w[0], w[1]);
  if (lu < EPS || lw < EPS) return null;
  const ang = Math.acos(Math.min(Math.max((u[0] * w[0] + u[1] * w[1]) / (lu * lw), -1), 1)) * 180 / Math.PI;
  if (Math.abs(ang - 90) > tol) return null;
  const c = [(prev[0] + next[0]) / 2, (prev[1] + next[1]) / 2], r = dist(prev, next) / 2, d = dist(c, point);
  if (d < EPS) return null;
  return [round3(c[0] + (point[0] - c[0]) * r / d), round3(c[1] + (point[1] - c[1]) * r / d)];
};

// ---------------------------------------------------------------------- 0.26.6.0(10): fitting rooms together
// Rooms measured one by one and pushed close to each other are fitted into one house: walls that face each other
// (nearly parallel, opposite sides, overlapping along the wall, at most ``tol`` apart – a gap or an overlap) are
// matched; every room moves as a whole (no room is scaled or bent, every measured length and angle stays) so that
// the matched walls meet, and corners that are close along the wall line up. A corner may then be laid onto the
// partner wall only where neither of its walls nor its angle is locked (small angle differences). What cannot be
// matched exactly is reported – nothing is changed silently. The rooms stay rooms of their own.
const JOIN_ANGLE = Math.sin(6 * Math.PI / 180);
export const joinRooms = (rooms, { tol = 0.35, anchorId = null } = {}) => {
  const list = rooms.filter(r => Array.isArray(r.polygon) && r.polygon.length >= 3).map(r => ({ ...r, polygon: r.polygon.map(p => p.slice()) }));
  const matches = [];
  for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
    const A = list[i], B = list[j];
    if (partitionTol(A, B) > WALL_TOLERANCE) continue;   // a confirmed partition wall stays as thick as it is
    for (let ea = 0; ea < A.polygon.length; ea++) {
      const a0 = A.polygon[ea], a1 = A.polygon[(ea + 1) % A.polygon.length], la = dist(a0, a1);
      if (la < 0.2) continue;
      const u = [(a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la], na = outwardNormal(A.polygon, ea);
      for (let eb = 0; eb < B.polygon.length; eb++) {
        const b0 = B.polygon[eb], b1 = B.polygon[(eb + 1) % B.polygon.length], lb = dist(b0, b1);
        if (lb < 0.2) continue;
        const v = [(b1[0] - b0[0]) / lb, (b1[1] - b0[1]) / lb], nb = outwardNormal(B.polygon, eb);
        if (Math.abs(u[0] * v[1] - u[1] * v[0]) > JOIN_ANGLE || na[0] * nb[0] + na[1] * nb[1] > -0.95) continue;
        const sa = [0, la], sb = [(b0[0] - a0[0]) * u[0] + (b0[1] - a0[1]) * u[1], (b1[0] - a0[0]) * u[0] + (b1[1] - a0[1]) * u[1]].sort((x, y) => x - y);
        const overlap = Math.min(sa[1], sb[1]) - Math.max(sa[0], sb[0]);
        if (overlap < Math.min(0.3, 0.3 * Math.min(la, lb))) continue;
        const mid = [(b0[0] + b1[0]) / 2, (b0[1] + b1[1]) / 2], gap = (mid[0] - a0[0]) * na[0] + (mid[1] - a0[1]) * na[1];
        if (Math.abs(gap) > tol) continue;
        // the corners closest along the wall: lined up when they are near each other
        const ends = [[sb[0] - sa[0], 0], [sb[1] - sa[1], 1]].sort((x, y) => Math.abs(x[0]) - Math.abs(y[0]));
        matches.push({ a: A.id, b: B.id, ea, eb, n: na, u, gap, slide: Math.abs(ends[0][0]) <= tol ? ends[0][0] : null, la, lb, overlap });
      }
    }
  }
  // one partner wall per wall and partner room (a long hall wall may meet several rooms)
  const best = new Map();
  for (const m of matches.sort((x, y) => Math.abs(x.gap) - Math.abs(y.gap))) {
    const ka = `${m.a}|${m.ea}|${m.b}`, kb = `${m.b}|${m.eb}|${m.a}`;
    if (best.has(ka) || best.has(kb)) continue;
    best.set(ka, m); best.set(kb, m);
  }
  const used = [...new Set(best.values())];
  const area = r => { let s = 0; const p = r.polygon; for (let i = 0; i < p.length; i++) { const q = p[(i + 1) % p.length]; s += p[i][0] * q[1] - q[0] * p[i][1]; } return Math.abs(s) / 2; };
  const anchor = anchorId || (list.length ? list.reduce((b, r) => (area(r) > area(b) ? r : b)).id : null);
  const t = Object.fromEntries(list.map(r => [r.id, [0, 0]]));
  // rigid moves, first across the walls (the gaps close exactly), then – only in a direction no matched wall of that
  // room fixes – along the walls to line up corners (lightly: these wishes may contradict each other)
  const step = (m, dir, off, k, free) => {
    const ta = t[m.a], tb = t[m.b], r = (tb[0] - ta[0]) * dir[0] + (tb[1] - ta[1]) * dir[1] + off;
    const da = free ? free(m.a, dir) : dir, db = free ? free(m.b, dir) : dir;
    const wa = m.a === anchor || !da ? 0 : m.b === anchor || !db ? 1 : 0.5, wb = m.b === anchor || !db ? 0 : 1 - wa;
    if (da) { ta[0] += da[0] * r * wa * k; ta[1] += da[1] * r * wa * k; }
    if (db) { tb[0] -= db[0] * r * wb * k; tb[1] -= db[1] * r * wb * k; }
    return Math.abs(r);
  };
  for (let round = 0; round < 800; round++) { let worst = 0; for (const m of used) worst = Math.max(worst, step(m, m.n, m.gap, 0.9)); if (worst < 1e-5) break; }
  const normals = {};
  for (const m of used) for (const id of [m.a, m.b]) (normals[id] = normals[id] || []).push(m.n);
  const freeDir = (id, dir) => {
    const ns = normals[id] || [];
    if (ns.some(a => ns.some(b => Math.abs(a[0] * b[1] - a[1] * b[0]) > 0.2))) return null;   // fixed in two directions
    if (!ns.length) return dir;
    const f = [-ns[0][1], ns[0][0]], d = f[0] * dir[0] + f[1] * dir[1];
    return Math.abs(d) < 0.2 ? null : [f[0] * Math.sign(d), f[1] * Math.sign(d)];
  };
  for (let round = 0; round < 400; round++) for (const m of used) if (m.slide != null) step(m, m.u, m.slide, 0.25, freeDir);
  const a0 = t[anchor] || [0, 0];
  for (const r of list) { const d = [t[r.id][0] - a0[0], t[r.id][1] - a0[1]]; r.polygon = r.polygon.map(p => [round3(p[0] + d[0]), round3(p[1] + d[1])]); }
  // what is left after the rigid moves (a slightly different angle): lay free corners onto the partner wall
  const conflicts = [], byId = Object.fromEntries(list.map(r => [r.id, r]));
  for (const m of used) {
    const A = byId[m.a], B = byId[m.b];
    const p0 = A.polygon[m.ea], p1 = A.polygon[(m.ea + 1) % A.polygon.length];
    for (const idx of [m.eb, (m.eb + 1) % B.polygon.length]) {
      const q = B.polygon[idx], L0 = dist(p0, p1), off = Math.abs((q[0] - p0[0]) * (p1[1] - p0[1]) - (q[1] - p0[1]) * (p1[0] - p0[0])) / (L0 || 1);
      const pr = { distance: off };   // the distance to the partner wall's LINE (a corner past its end is not off it)
      if (pr.distance <= 0.002 || pr.distance > tol) continue;
      const n = B.polygon.length, locked = new Set(B.locked_walls || []), corners = new Set(B.locked_corners || []);
      if (locked.has(idx) || locked.has((idx - 1 + n) % n) || corners.has(idx)) { conflicts.push({ code: "locked_corner", a: m.a, b: m.b, wall_a: m.ea, wall_b: m.eb, corner: idx, distance: round3(pr.distance) }); continue; }
      // project onto the wall line
      const L = dist(p0, p1), tt = ((q[0] - p0[0]) * (p1[0] - p0[0]) + (q[1] - p0[1]) * (p1[1] - p0[1])) / (L * L);
      const proj = [p0[0] + (p1[0] - p0[0]) * tt, p0[1] + (p1[1] - p0[1]) * tt];
      B.polygon[idx] = [round3(proj[0]), round3(proj[1])];
    }
    // walls meant to be the same wall (lengths within 0.5 m) but measured differently – shown, kept as measured
    if (Math.abs(m.la - m.lb) > 0.005 && Math.abs(m.la - m.lb) <= 0.5) conflicts.push({ code: "length_differs", a: m.a, b: m.b, wall_a: m.ea, wall_b: m.eb, length_a: round3(m.la), length_b: round3(m.lb), info: true });
  }
  for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
    if (polygonsOverlap(list[i].polygon, list[j].polygon)) conflicts.push({ code: "overlap", a: list[i].id, b: list[j].id });
  }
  return { polygons: Object.fromEntries(list.map(r => [r.id, r.polygon])), matches: used.map(m => ({ a: m.a, b: m.b, wall_a: m.ea, wall_b: m.eb, gap: round3(m.gap) })), conflicts, anchor };
};
// An opening on a wall whose ends moved: it keeps its distance from the end that stayed (else its relative place).
export const followOpening = (oldPts, newPts, o) => {
  const n = oldPts.length, a0 = oldPts[o.edge], b0 = oldPts[(o.edge + 1) % n], a1 = newPts[o.edge], b1 = newPts[(o.edge + 1) % n];
  const l0 = dist(a0, b0), l1 = dist(a1, b1);
  if (l1 < EPS) return null;
  let offset = o.offset;
  if (dist(a0, a1) < EPS) offset = (o.offset * l0) / l1;
  else if (dist(b0, b1) < EPS) offset = 1 - ((1 - o.offset) * l0) / l1;
  const half = Math.min(o.width_m || Math.min(0.9, l1 * 0.4), l1) / l1 / 2;
  if ((o.width_m || 0) > l1 + WALL_TOLERANCE || offset - half < -EPS || offset + half > 1 + EPS) return null;  // no longer fits
  return { ...o, offset: round3(offset) };
};
// Door symbol attributes: which end of the opening carries the hinge, and to which side the leaf opens.
// ``inward`` points into the room the door belongs to. Without attributes: hinge at the wall's start, into the room.
export const doorGeometry = (a, b, inward, o = {}) => {
  const right = [-inward[1], inward[0]];  // facing the wall from inside the room
  const bRight = (b[0] - a[0]) * right[0] + (b[1] - a[1]) * right[1] > 0;
  const hingeAtB = o.door_hinge === "right" ? bRight : o.door_hinge === "left" ? !bRight : false;
  const swing = o.door_swing === "out" ? [-inward[0], -inward[1]] : inward;
  return hingeAtB ? { hinge: b, free: a, swing } : { hinge: a, free: b, swing };
};
// 0.26.6.0(6): a window on a wall the room shares with another room (e.g. placed by a proposal that found no free
// outside wall, or a room moved later) – it belongs on an outside wall.
export const windowOnInteriorWall = (rooms, o) => {
  if (o.kind !== "window") return false;
  const room = rooms.find(r => r.id === o.room_id);
  return !!(room && openingLink(rooms, room, o));
};
// The nearest outside wall of the same room (to where the opening is now), the opening centred on its free stretch
// and no wider than it. Returns {edge, offset, width_m} or null when the room has no outside wall.
export const exteriorSpot = (rooms, room, o) => {
  const pts = room && room.polygon;
  if (!Array.isArray(pts) || pts.length < 3) return null;
  const neighbours = rooms.filter(r => r.floor_id === room.floor_id);
  const span = openingSpan(room, o), at = span ? [(span[0][0] + span[1][0]) / 2, (span[0][1] + span[1][1]) / 2] : labelPoint(pts);
  let best = null;
  for (const w of wallParts(neighbours, room).filter(x => !x.interior)) {
    const partLen = dist(w.a, w.b);
    if (partLen < 0.3) continue;
    const width = o.width_m ? Math.min(o.width_m, partLen) : Math.min(0.9, partLen * 0.8);
    const d = projectOnSegment(at, w.a, w.b).distance;  // the nearest outside wall …
    const centre = [(w.a[0] + w.b[0]) / 2, (w.a[1] + w.b[1]) / 2];  // … and the middle of its free stretch
    if (!best || d < best.d) {
      const edgeLen = edgeLength(pts, w.edge) || 1;
      best = { d, edge: w.edge, offset: round3(dist(pts[w.edge], centre) / edgeLen), width_m: o.width_m ? round3(width) : (o.width_m ?? null) };
    }
  }
  return best && { edge: best.edge, offset: best.offset, width_m: best.width_m };
};
// ---------------------------------------------------------------------------- 0.26.6.0(7): labels inside the room
// The stretches of a horizontal line y that lie inside the polygon (even–odd rule): [[x0, x1], …].
export const scanSpans = (pts, y) => {
  const xs = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    if ((a[1] <= y && b[1] > y) || (b[1] <= y && a[1] > y)) xs.push(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]));
  }
  xs.sort((p, q) => p - q);
  const out = [];
  for (let i = 0; i + 1 < xs.length; i += 2) out.push([xs[i], xs[i + 1]]);
  return out;
};
const intersectSpans = (first, second) => {
  const out = [];
  for (const [a0, a1] of first) for (const [b0, b1] of second) { const lo = Math.max(a0, b0), hi = Math.min(a1, b1); if (hi > lo) out.push([lo, hi]); }
  return out;
};
// The parts of the stretches that no block [{minX, maxX, minY, maxY}] covering the band y0..y1 takes away.
const withoutBlocks = (spans, blocks, y0, y1) => {
  let out = spans;
  for (const b of blocks) {
    if (b.maxY <= y0 || b.minY >= y1) continue;
    out = out.flatMap(([a, c]) => [[a, Math.min(c, b.minX)], [Math.max(a, b.maxX), c]].filter(([p, q]) => q > p));
  }
  return out;
};
// Where a label block of height ``h`` fits best inside the room: the widest stretch that is inside on the block's
// top, bottom and three lines between (an L- or U-shaped room is not measured by its bounding box), ``pad`` kept
// from the walls. Returns {x, y, w} – centre and free width – or null when the block is taller than the room.
// 0.26.6.0(7): ``blocks`` (door swings, open sashes) are kept free as well.
export const labelSpot = (pts, h, pad = 0, blocks = []) => {
  const box = bbox([pts]), lp = labelPoint(pts);
  const lo = box.minY + pad + h / 2, hi = box.maxY - pad - h / 2;
  if (hi < lo) return null;
  const ys = [Math.min(Math.max(lp[1], lo), hi)];
  for (let k = 0; k <= 16; k++) ys.push(lo + (hi - lo) * k / 16);
  let best = null;
  for (const y of ys) {
    let spans = scanSpans(pts, y - h / 2 + 1e-9);
    for (const t of [-0.25, 0, 0.25, 0.5 - 1e-9]) spans = intersectSpans(spans, scanSpans(pts, y + t * h));
    if (blocks.length) spans = withoutBlocks(spans, blocks, y - h / 2 - pad, y + h / 2 + pad);
    for (const [a, b] of spans) {
      const w = b - a - 2 * pad;
      if (w <= 0) continue;
      const score = w - 0.05 * Math.hypot((a + b) / 2 - lp[0], y - lp[1]);  // the widest, then the nearest to the centre
      if (!best || score > best.score) best = { x: (a + b) / 2, y, w, score };
    }
  }
  return best && { x: best.x, y: best.y, w: best.w };
};

// ---------------------------------------------------------------------- floor plan check: gaps, overlaps, steps
// Two walls facing each other across a parallel gap: [{ea, eb, gap, lo, hi}] (lo/hi along A's wall, in m).
const facingWalls = (A, B) => {
  const out = [];
  for (let ea = 0; ea < A.polygon.length; ea++) {
    const a0 = A.polygon[ea], a1 = A.polygon[(ea + 1) % A.polygon.length], la = dist(a0, a1);
    if (la < 0.2) continue;
    const u = [(a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la], na = outwardNormal(A.polygon, ea);
    for (let eb = 0; eb < B.polygon.length; eb++) {
      const b0 = B.polygon[eb], b1 = B.polygon[(eb + 1) % B.polygon.length], lb = dist(b0, b1);
      if (lb < 0.2) continue;
      const v = [(b1[0] - b0[0]) / lb, (b1[1] - b0[1]) / lb], nb = outwardNormal(B.polygon, eb);
      if (Math.abs(u[0] * v[1] - u[1] * v[0]) > JOIN_ANGLE || na[0] * nb[0] + na[1] * nb[1] > -0.95) continue;
      const sb = [(b0[0] - a0[0]) * u[0] + (b0[1] - a0[1]) * u[1], (b1[0] - a0[0]) * u[0] + (b1[1] - a0[1]) * u[1]];
      const lo = Math.max(0, Math.min(...sb)), hi = Math.min(la, Math.max(...sb));
      if (hi - lo < 0.3) continue;
      const mid = [(b0[0] + b1[0]) / 2, (b0[1] + b1[1]) / 2];
      out.push({ ea, eb, gap: (mid[0] - a0[0]) * na[0] + (mid[1] - a0[1]) * na[1], lo, hi, la, lb, sb, u, na, a0 });
    }
  }
  return out;
};
// The walls of a floor that face each other ({"a|b|wall a|wall b": gap}) – to see whether a change opens a joint
// where two rooms touched (also one within WALL_TOLERANCE).
export const wallContacts = rooms => {
  const out = new Map(), list = rooms.filter(r => Array.isArray(r.polygon) && r.polygon.length >= 3);
  for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
    if (list[i].floor_id !== list[j].floor_id) continue;
    for (const f of facingWalls(list[i], list[j])) out.set(`${list[i].id}|${list[j].id}|${f.ea}|${f.eb}`, f.gap);
  }
  return out;
};
export const opensJoint = (before, after, tol = 0.01) => {
  const now = wallContacts(after);
  return [...wallContacts(before)].some(([k, g]) => Math.abs(g) <= tol && now.has(k) && Math.abs(now.get(k)) > tol);
};
// The partition walls of a floor as filled areas between both rooms' walls ({a, b, polygon}).
export const partitionFills = rooms => {
  const out = [], list = rooms.filter(r => Array.isArray(r.polygon) && r.polygon.length >= 3);
  for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
    const A = list[i], B = list[j];
    if (!partitionsBetween(A, B).length || A.floor_id !== B.floor_id) continue;
    for (const f of facingWalls(A, B)) {
      const tol = partitionTol(A, B, f.ea, f.eb);
      if (tol <= WALL_TOLERANCE || f.gap <= EPS || f.gap > tol) continue;
      const at = (t, k) => [f.a0[0] + f.u[0] * t + f.na[0] * k, f.a0[1] + f.u[1] * t + f.na[1] * k];
      out.push({ a: A.id, b: B.id, polygon: [at(f.lo, 0), at(f.hi, 0), at(f.hi, f.gap), at(f.lo, f.gap)].map(p => [round3(p[0]), round3(p[1])]) });
    }
  }
  return out;
};
// What the plan check marks between two rooms of one floor:
//  overlap – the rooms overlap (``depth``: the smallest move that separates them);
//  gap     – two walls face each other a little apart (``gap`` in m, at most ``maxGap``) – a joint or a partition wall
//            not confirmed yet (a confirmed partition of that thickness is no finding);
//  step    – two rooms share a wall that ends level at one end but ``step`` apart at the other, where both rooms'
//            end walls face the same way (e.g. 5.60 m and 5.00 m along one facade): marked, never evened out.
export const planFindings = (rooms, { maxGap = 0.5, maxStep = 1.0 } = {}) => {
  const list = rooms.filter(r => Array.isArray(r.polygon) && r.polygon.length >= 3), out = [];
  const boxes = new Map(list.map(r => [r.id, bbox([r.polygon])]));
  for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
    const A = list[i], B = list[j], ba = boxes.get(A.id), bb = boxes.get(B.id);
    if (A.floor_id !== B.floor_id || ba.minX > bb.maxX + maxGap || bb.minX > ba.maxX + maxGap || ba.minY > bb.maxY + maxGap || bb.minY > ba.maxY + maxGap) continue;
    if (polygonsOverlap(A.polygon, B.polygon)) {
      const at = [(Math.max(ba.minX, bb.minX) + Math.min(ba.maxX, bb.maxX)) / 2, (Math.max(ba.minY, bb.minY) + Math.min(ba.maxY, bb.maxY)) / 2];
      const depth = Math.min(ba.maxX - bb.minX, bb.maxX - ba.minX, ba.maxY - bb.minY, bb.maxY - ba.minY);
      out.push({ code: "overlap", id: `overlap|${A.id}|${B.id}`, a: A.id, b: B.id, depth: round3(depth), at: at.map(round3) });
      continue;
    }
    const walls = facingWalls(A, B), tolOf = f => partitionTol(A, B, f.ea, f.eb);
    // every joint on its own (a U-shaped room may face its neighbour twice), named by its two walls
    const gaps = walls.filter(f => { const tol = tolOf(f); return f.gap > WALL_TOLERANCE && f.gap <= maxGap && !(tol > WALL_TOLERANCE && Math.abs(f.gap - (tol - WALL_TOLERANCE)) <= WALL_TOLERANCE); })
      .sort((x, y) => x.gap - y.gap);
    for (const gap of gaps) {
      const m = (gap.lo + gap.hi) / 2, at = [gap.a0[0] + gap.u[0] * m + gap.na[0] * gap.gap / 2, gap.a0[1] + gap.u[1] * m + gap.na[1] * gap.gap / 2];
      out.push({ code: "gap", id: `gap|${A.id}|${B.id}|${gap.ea}|${gap.eb}`, a: A.id, b: B.id, wall_a: gap.ea, wall_b: gap.eb, gap: round3(gap.gap), n: gap.na.map(round3), at: at.map(round3) });
    }
    for (const f of walls.filter(w => Math.abs(w.gap) <= Math.max(WALL_TOLERANCE, tolOf(w)))) {
      const step = wallRunStep(list, A, f, maxStep);
      if (step && !out.some(x => x.id === step.id || x.key === step.key)) out.push(step);
    }
  }
  return out;
};
// A step along one wall line: the walls of every room on each side of the line that continue each other form one
// run (rows of rooms, e.g. 2.00 + 1.50 + 2.10 m against 2.05 + 0.90 + 2.05 m). Both runs end level at one end and
// ``step`` apart at the other, where the end walls of both runs face the same way – marked, never evened out. The
// offer: the end room of the shorter run reaches the longer one (``fixes``: extend) or the other way (shorten).
const wallRunStep = (list, A, f, maxStep) => {
  const side = (sign, offset) => {
    const items = [];
    for (const r of list) {
      if (r.floor_id !== A.floor_id) continue;
      r.polygon.forEach((p, e) => {
        const q = r.polygon[(e + 1) % r.polygon.length], n = outwardNormal(r.polygon, e);
        const off = x => (x[0] - f.a0[0]) * f.na[0] + (x[1] - f.a0[1]) * f.na[1] - offset, along = x => (x[0] - f.a0[0]) * f.u[0] + (x[1] - f.a0[1]) * f.u[1];
        if (dist(p, q) < EPS || Math.abs(off(p)) > WALL_TOLERANCE || Math.abs(off(q)) > WALL_TOLERANCE || (n[0] * f.na[0] + n[1] * f.na[1]) * sign < 0.95) return;
        const tp = along(p), tq = along(q);
        items.push({ room: r.id, edge: e, lo: Math.min(tp, tq), hi: Math.max(tp, tq), startAtLo: tp <= tq, polygon: r.polygon });
      });
    }
    items.sort((x, y) => x.lo - y.lo);
    const runs = [];
    for (const it of items) { const last = runs[runs.length - 1]; if (last && it.lo <= last.hi + WALL_TOLERANCE) { last.hi = Math.max(last.hi, it.hi); last.items.push(it); } else runs.push({ lo: it.lo, hi: it.hi, items: [it] }); }
    return runs;
  };
  const own = side(1, 0).find(r => r.items.some(it => it.room === A.id && it.edge === f.ea)), other = side(-1, f.gap).find(r => r.lo < f.hi && r.hi > f.lo);
  if (!own || !other) return null;
  const ends = [[other.lo - own.lo, 0], [other.hi - own.hi, 1]];
  const level = ends.find(([d]) => Math.abs(d) <= 0.02), off = ends.find(([d]) => Math.abs(d) > 0.02 && Math.abs(d) <= maxStep);
  if (!level || !off) return null;
  const k = off[1];
  // the room at the step on each side, its wall on the line and the wall that ends the run there
  const endOf = run => {
    const it = run.items.reduce((b, x) => (k ? (x.hi > b.hi ? x : b) : (x.lo < b.lo ? x : b)));
    const n = it.polygon.length, endAtStart = (k === 0) === it.startAtLo;   // the corner at the step is polygon[edge]
    return { ...it, endWall: endAtStart ? (it.edge - 1 + n) % n : (it.edge + 1) % n, fixed: endAtStart ? "end" : "start", length: dist(it.polygon[it.edge], it.polygon[(it.edge + 1) % n]) };
  };
  const ea = endOf(own), eb = endOf(other), oa = outwardNormal(ea.polygon, ea.endWall), ob = outwardNormal(eb.polygon, eb.endWall);
  if (oa[0] * ob[0] + oa[1] * ob[1] < 0.95) return null;
  const la = own.hi - own.lo, lb = other.hi - other.lo, diff = Math.abs(off[0]), [short, long] = la < lb ? [ea, eb] : [eb, ea];
  const pa = k ? own.hi : own.lo, pb = k ? other.hi : other.lo, m = (pa + pb) / 2;
  const at = [f.a0[0] + f.u[0] * m + f.na[0] * f.gap / 2, f.a0[1] + f.u[1] * m + f.na[1] * f.gap / 2];
  const names = run => [...new Set(run.items.map(it => it.room))];
  return { code: "step", id: `step|${ea.room}|${eb.room}|${ea.edge}`, key: `${names(own).join(",")}|${names(other).join(",")}|${k}`, a: ea.room, b: eb.room, wall_a: ea.edge, wall_b: eb.edge,
    rooms_a: names(own), rooms_b: names(other), length_a: round3(la), length_b: round3(lb), step: round3(diff), longer: la > lb ? ea.room : eb.room, at: at.map(round3),
    fixes: [{ kind: "extend", room: short.room, wall: short.edge, length: round3(short.length + diff), fixed: short.fixed },
      { kind: "shorten", room: long.room, wall: long.edge, length: round3(long.length - diff), fixed: long.fixed }] };
};
// The smallest straight move of room ``id`` that ends its overlap with room ``otherId`` without touching any
// other room of its floor ({dx, dy}) – null when every such move would hit another room.
export const separation = (rooms, id, otherId) => {
  const A = rooms.find(r => r.id === id), B = rooms.find(r => r.id === otherId);
  if (!A || !B) return null;
  const a = bbox([A.polygon]), b = bbox([B.polygon]);
  const moves = [[b.minX - a.maxX, 0], [b.maxX - a.minX, 0], [0, b.minY - a.maxY], [0, b.maxY - a.minY]].sort((x, y) => Math.hypot(...x) - Math.hypot(...y));
  for (const [dx, dy] of moves) {
    const moved = A.polygon.map(p => [round3(p[0] + dx), round3(p[1] + dy)]);
    if (!rooms.some(r => r.id !== id && r.floor_id === A.floor_id && Array.isArray(r.polygon) && r.polygon.length >= 3 && polygonsOverlap(moved, r.polygon))) return { dx: round3(dx), dy: round3(dy) };
  }
  return null;
};
// ---------------------------------------------------------------------- a new or removed corner on a wall
const drawnWidth = (len, o) => Math.min(Math.max(o.width_m || Math.min(0.9, len * 0.4), 0), len);
// A corner inserted on wall ``index`` of ``room`` at ``ts`` (0–1 along it): the openings of that wall keep their
// place – each moves to the part it lies on, with its drawn width – and later walls shift by one. An opening the
// new corner would cut is not moved: {blocked: [ids], free: [[lo, hi], …]} names the stretches (0–1) where a corner fits.
export const splitOpenings = (openings, room, index, ts = 0.5) => {
  const pts = room.polygon, len = edgeLength(pts, index), cut = ts * len, out = [], blocked = [], taken = [];
  for (const o of openings) {
    if (o.room_id !== room.id) { out.push(o); continue; }
    if (o.edge > index) { out.push({ ...o, edge: o.edge + 1 }); continue; }
    if (o.edge !== index) { out.push(o); continue; }
    const w = drawnWidth(len, o), c = (Number.isFinite(Number(o.offset)) ? Number(o.offset) : 0.5) * len, lo = c - w / 2, hi = c + w / 2;
    taken.push([lo, hi]);
    const width = o.width_m == null ? round3(w) : o.width_m;
    if (hi <= cut + 0.01) out.push({ ...o, width_m: width, offset: round3(c / cut) });
    else if (lo >= cut - 0.01) out.push({ ...o, edge: index + 1, width_m: width, offset: round3((c - cut) / (len - cut)) });
    else { blocked.push(o.id); out.push(o); }
  }
  if (!blocked.length) return { openings: out };
  const free = [];
  let pos = 0.1;
  for (const [lo, hi] of taken.sort((x, y) => x[0] - y[0])) { if (lo - 0.05 - pos >= 0.2) free.push([pos, lo - 0.05]); pos = Math.max(pos, hi + 0.05); }
  if (len - 0.1 - pos >= 0.2) free.push([pos, len - 0.1]);
  return { blocked, free: free.map(([lo, hi]) => [round3(lo / len), round3(hi / len)]) };
};
// Corner ``k`` of ``room`` removed: the openings of the two walls that become one keep their place on the new wall.
export const mergeOpenings = (openings, room, k) => {
  const pts = room.polygon, n = pts.length, prev = (k - 1 + n) % n;
  const next = pts.filter((_, i) => i !== k), merged = k === 0 ? n - 2 : k - 1;
  const a = next[merged], b = next[(merged + 1) % next.length], len = dist(a, b) || 1;
  return openings.map(o => {
    if (o.room_id !== room.id) return o;
    if (o.edge === prev || o.edge === k) {
      const old = edgeLength(pts, o.edge), c = edgePoint(pts, o.edge, Number.isFinite(Number(o.offset)) ? Number(o.offset) : 0.5);
      const t = projectOnSegment(c, a, b).t;
      return { ...o, edge: merged, offset: round3(t), width_m: o.width_m == null ? round3(drawnWidth(old, o)) : o.width_m };
    }
    return { ...o, edge: o.edge > k ? o.edge - 1 : o.edge };
  });
};
