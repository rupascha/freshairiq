// FreshAirIQ house map – wind field (0.26.6.0, order 8). A modelled, analytic picture of the air around the house,
// not a measurement and not a CFD simulation: a uniform wind from the measured direction and speed that is slowed in
// front of the windward wall, turned along the outside walls, sped up past the corners, calmed in the wake and
// occasionally rolled into soft eddies (Lamb–Oseen vortices) behind the corners where the flow separates. Gusts are
// events with a rise, a peak and a decay – sized by the measured gust when Home Assistant reports one, otherwise a
// small, decorative variation. Pure functions; the card draws the result (freshairiq-house-flowlayer.js).

const TAU = Math.PI * 2;
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
const smooth = t => { const x = clamp(t, 0, 1); return x * x * (3 - 2 * x); };
// a stable pseudo-random number in [0, 1) for integers (same plan, same wind → same picture)
export const hash = (a, b = 0) => { let h = (a * 374761393 + b * 668265263) >>> 0; h = ((h ^ (h >>> 13)) * 1274126177) >>> 0; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };

// Wind strength classes (m/s): calm, weak, moderate, strong – they set density, speed and how lively the eddies are.
export const strengthClass = speed => (!(speed > 0.5) ? "calm" : speed < 3 ? "weak" : speed < 7 ? "moderate" : "strong");
const CLASS = {
  calm: { density: 0.18, eddies: 0, gustEvery: 0 },
  weak: { density: 0.45, eddies: 0.25, gustEvery: 26 },
  moderate: { density: 0.75, eddies: 0.6, gustEvery: 18 },
  strong: { density: 1, eddies: 0.95, gustEvery: 11 },
};

// Order 9: the character of the wind follows the real weather – not only its speed. From Home Assistant data only:
// mean wind and measured gust (m/s), the HA weather condition, rain/thunder (FreshAirIQ weather summary) and day /
// night (sun.sun). sunny: light, soft, warm-white, few gentle eddies · neutral: calm and even · rain: denser, cooler,
// a little more lively · lively: more layers and eddies · storm: bundled, fast, crisp, large rolling eddies.
const STORM_CONDITIONS = new Set(["exceptional", "lightning", "lightning-rainy", "hail"]);
const MOODS = {
  sunny: { density: 0.8, vis: 0.85, eddy: 0.4, gamma: 0.7, bend: 1.25, meander: 0.8, fade: 0.04, width: 0.95, colors: ["rgba(255,247,226,.2)", "rgba(255,250,236,.38)", "rgba(255,253,244,.58)"], spark: "rgba(255,247,222,.45)", gust: 0.08 },
  neutral: { density: 1, vis: 1, eddy: 1, gamma: 1, bend: 1, meander: 1, fade: 0, width: 1.05, colors: ["rgba(214,238,255,.22)", "rgba(226,244,255,.42)", "rgba(240,250,255,.66)"], spark: "rgba(250,253,255,.5)", gust: 0.15 },
  rain: { density: 1.1, vis: 1.08, eddy: 1.1, gamma: 1.1, bend: 1, meander: 1.1, fade: 0.075, width: 1.05, colors: ["rgba(196,220,240,.22)", "rgba(210,230,246,.4)", "rgba(226,240,252,.6)"], spark: "rgba(236,246,255,.45)", gust: 0.2 },
  lively: { density: 1.15, vis: 1.12, eddy: 1.25, gamma: 1.2, bend: 1.15, meander: 1.25, fade: 0.08, width: 1.1, colors: ["rgba(210,234,255,.24)", "rgba(224,242,255,.46)", "rgba(242,250,255,.72)"], spark: "rgba(252,254,255,.55)", gust: 0.22 },
  storm: { density: 1.4, vis: 1.3, eddy: 1.6, gamma: 1.7, bend: 1.5, meander: 1.8, fade: 0.11, width: 1.25, colors: ["rgba(196,222,255,.28)", "rgba(216,236,255,.52)", "rgba(240,248,255,.8)"], spark: "rgba(255,255,255,.65)", gust: 0.35 },
};
export function windMood({ speed = 0, gust = null, condition = null, raining = false, thunder = false, phase = null } = {}) {
  const g = Number(gust) > 0 ? Number(gust) : 0, c = String(condition || "");
  let name = "neutral";
  if (speed >= 11 || g >= 17 || (STORM_CONDITIONS.has(c) && speed >= 6) || (thunder && speed >= 6)) name = "storm";
  else if (speed >= 7 || g >= 12 || c === "windy" || c === "windy-variant") name = "lively";
  else if (raining || c === "rainy" || c === "pouring" || c === "snowy-rainy") name = "rain";
  else if ((c === "sunny" || c === "partlycloudy") && phase !== "night" && phase !== "twilight") name = "sunny";
  const style = { ...MOODS[name] };
  if (phase === "night") style.colors = style.colors.map(x => x.replace(/,(\.\d+)\)$/, (m, a) => `,${(Number(a) * 0.8).toFixed(2)})`));   // at night a little dimmer
  return { name, ...style };
}

/**
 * Build the field for one floor.
 * rooms: [{id, polygon}] (plan coordinates), G: geometry module, wind: {from_deg, speed_ms, gust_ms, available},
 * northDeg: plan north. Returns null without a usable wind (nothing is invented).
 */
export function buildField({ rooms, G, wind, northDeg = 0, mood = null }) {
  if (!wind || !wind.available || wind.from_deg == null || !rooms.length) return null;
  const speed = Math.max(0, Number(wind.speed_ms) || 0);
  const dir = G.bearingVector((Number(wind.from_deg) + 180) % 360, northDeg);   // where the air moves to
  const perp = [-dir[1], dir[0]];
  const box = G.bbox(rooms.map(r => r.polygon));
  const c = [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2];
  const L = Math.max(box.maxX - box.minX, box.maxY - box.minY, 1);
  // outside walls with their outward normal
  const segs = [];
  for (const w of G.wallSegments(rooms, [])) {
    if (w.interior) continue;
    const room = rooms.find(r => r.id === w.room);
    const n = G.outwardNormal(room.polygon, w.edge), d = [w.b[0] - w.a[0], w.b[1] - w.a[1]], len = Math.hypot(d[0], d[1]);
    if (len > 1e-6) segs.push({ a: w.a, b: w.b, n, t: [d[0] / len, d[1] / len], len });
  }
  // the extent across the wind and along it (the silhouette the wind sees)
  let latMin = Infinity, latMax = -Infinity, lonMax = -Infinity;
  for (const s of segs) for (const p of [s.a, s.b]) {
    const lat = (p[0] - c[0]) * perp[0] + (p[1] - c[1]) * perp[1], lon = (p[0] - c[0]) * dir[0] + (p[1] - c[1]) * dir[1];
    if (lat < latMin) { latMin = lat; } if (lat > latMax) { latMax = lat; } if (lon > lonMax) lonMax = lon;
  }
  // flow separates at the two silhouette corners; there the eddies roll up (on the side away from the house)
  const corners = [];
  for (const [lat, side] of [[latMin, -1], [latMax, 1]]) {
    let best = null;
    for (const s of segs) for (const p of [s.a, s.b]) {
      const l = (p[0] - c[0]) * perp[0] + (p[1] - c[1]) * perp[1], lon = (p[0] - c[0]) * dir[0] + (p[1] - c[1]) * dir[1];
      if (Math.abs(l - lat) < L * 0.02 && (!best || lon > best.lon)) best = { p, lon };
    }
    if (best) corners.push({ p: best.p, side });
  }
  const cls = strengthClass(speed);
  const gustMeasured = Number(wind.gust_ms) > speed + 0.3;
  const md = mood || windMood({ speed, gust: wind.gust_ms });
  return {
    dir, perp, c, L, segs, corners, speed, cls, box, halfWidth: Math.max((latMax - latMin) / 2, L * 0.2), lee: lonMax,
    rooms: rooms.map(r => r.polygon), roomBoxes: rooms.map(r => G.bbox([r.polygon])), G,
    // gust size: the measured gust relative to the mean wind, else a small decorative variation (flagged)
    // a measured gust sets the size; without one only a small decorative variation that suits the mood
    gust: { measured: gustMeasured, amp: gustMeasured ? clamp(Number(wind.gust_ms) / Math.max(speed, 0.5) - 1, 0.1, 1.2) : (cls === "calm" ? 0 : md.gust), every: CLASS[cls].gustEvery },
    density: CLASS[cls].density * md.density, eddyChance: Math.min(CLASS[cls].eddies * md.eddy, 1), mood: md,
    // how fast the drawn air travels: plan units per second (schematic, grows with the measured speed)
    vis: L * (0.05 + 0.022 * Math.min(speed, 15)) * md.vis,
  };
}

// The gust envelope at time t (s): 0 most of the time, one rising–peaking–decaying wave every few tens of seconds.
export function gustAt(field, t) {
  if (!field || !field.gust.every) return 0;
  const P = field.gust.every, k = Math.floor(t / P), tau = t - k * P - hash(k, 7) * P * 0.35, life = P * 0.45;
  if (tau < 0 || tau > life) return 0;
  const x = tau / life;
  return Math.pow(Math.sin(Math.PI * Math.min(1, x * 1.25)), 2) * (x < 0.8 ? 1 : 1 - (x - 0.8) / 0.2);
}
// The eddies alive at time t: [{x, y, gamma, rc, life}] – occasional, not at every corner all the time; larger and
// faster with stronger wind and during a gust.
export function eddiesAt(field, t) {
  const out = [];
  if (!field || !field.eddyChance) return out;
  const rc = field.L * (0.07 + 0.05 * field.eddyChance), period = 16 - 9 * field.eddyChance, life = period * 0.7;
  field.corners.forEach((corner, i) => {
    for (const k of [Math.floor(t / period), Math.floor(t / period) - 1]) {
      if (hash(k, i + 11) > field.eddyChance) continue;          // this time no eddy at this corner
      const tau = t - k * period - hash(k, i + 3) * period * 0.25;
      if (tau < 0 || tau > life) continue;
      const x = tau / life, env = Math.pow(Math.sin(Math.PI * x), 2), g = 1 + gustAt(field, t) * field.gust.amp;
      const drift = field.vis * tau * 0.35;                       // it travels slowly downstream while it lives
      const at = [corner.p[0] + field.dir[0] * (rc * 1.2 + drift) + field.perp[0] * corner.side * rc * 0.9,
        corner.p[1] + field.dir[1] * (rc * 1.2 + drift) + field.perp[1] * corner.side * rc * 0.9];
      const m = field.mood ? field.mood.gamma : 1;                // storm: larger, stronger rolls; sunny: gentle
      out.push({ x: at[0], y: at[1], rc: rc * (0.8 + 0.5 * x) * g * (0.75 + 0.25 * m), gamma: -corner.side * env * g * field.vis * rc * 5.5 * m, life: x });
    }
  });
  return out;
}
// 0.26.7.0: a narrow gap between two drawn rooms (a wall drawn twice, rooms not snapped together) is part of the house as
// well – the air never runs through such a joint. Only points close to two different rooms count, so the air still passes
// right along every outside wall.
export const GAP_TOLERANCE = 0.35;   // plan units (metres)
const nearRoom = (G, p, pts, tol) => pts.some((a, i) => { const q = G.projectOnSegment(p, a, pts[(i + 1) % pts.length]); return Math.hypot(p[0] - q.point[0], p[1] - q.point[1]) < tol; });
export const insideHouse = (field, x, y) => {
  if (field.rooms.some(p => field.G.pointInPolygon([x, y], p) === "inside")) return true;
  const tol = field.gap == null ? GAP_TOLERANCE : field.gap, boxes = field.roomBoxes;
  if (!(tol > 0) || !boxes) return false;
  let near = 0;
  for (let i = 0; i < field.rooms.length; i++) {
    const b = boxes[i];
    if (x < b.minX - tol || x > b.maxX + tol || y < b.minY - tol || y > b.maxY + tol) continue;
    if (nearRoom(field.G, [x, y], field.rooms[i], tol) && ++near >= 2) return true;
  }
  return false;
};

// Velocity (plan units per second) at (x, y) and time t; null inside the house. ``eddies`` may be passed in when it
// was computed once for a whole frame.
export function velocity(field, x, y, t, eddies = null, gust = null) {
  if (insideHouse(field, x, y)) return null;
  const g = 1 + (gust == null ? gustAt(field, t) : gust) * field.gust.amp;
  const { dir, perp, c, L, vis } = field;
  const rx = x - c[0], ry = y - c[1], lon = rx * dir[0] + ry * dir[1], lat = rx * perp[0] + ry * perp[1];
  // a slow, large-scale meander: air layers that curve and change their bend over time
  // sunny: long, smooth curves; storm: tighter bundles that bend more and change faster
  const mb = field.mood ? field.mood.bend : 1, mm = field.mood ? field.mood.meander : 1;
  const bend = 0.16 * mb * Math.sin(lon / (L * 0.9 / mm) - t * 0.23 * mm + lat / (L * 1.7)) + 0.07 * mb * Math.sin(lat / (L * 0.45) + t * 0.11 * mm);
  let vx = (dir[0] + perp[0] * bend) * vis * g, vy = (dir[1] + perp[1] * bend) * vis * g;
  // the nearest outside wall: slow down in front of it, turn along it, speed up past it
  let best = null;
  for (const s of field.segs) {
    const px = x - s.a[0], py = y - s.a[1], u = clamp((px * s.t[0] + py * s.t[1]) / s.len, 0, 1);
    const qx = s.a[0] + s.t[0] * s.len * u, qy = s.a[1] + s.t[1] * s.len * u, d = Math.hypot(x - qx, y - qy);
    if (!best || d < best.d) best = { d, s, u };
  }
  if (best) {
    const D = L * 0.42, w = smooth(1 - best.d / D);   // the threads begin to bend well before the wall
    if (w > 0) {
      const n = best.s.n, vn = vx * n[0] + vy * n[1];
      if (vn < 0) {                                          // heading for the wall: the normal part fades out …
        const facing = clamp(-(dir[0] * n[0] + dir[1] * n[1]), 0, 1);
        vx -= n[0] * vn * w; vy -= n[1] * vn * w;
        const slow = 1 - 0.45 * w * facing;                  // … the air slows in front of a windward wall …
        const side = (best.u - 0.5) >= 0 ? 1 : -1;            // … and splits towards the nearer end of the wall
        const split = w * facing * 0.55 * vis * g;
        vx = vx * slow + best.s.t[0] * side * split; vy = vy * slow + best.s.t[1] * side * split;
      } else {
        const boost = 1 + 0.35 * w;                          // a little faster along the walls and past the corners
        vx *= boost; vy *= boost;
      }
    }
  }
  // the calmer wake behind the house
  if (lon > 0 && Math.abs(lat) < field.halfWidth * 1.15) {
    const k = Math.exp(-Math.max(0, lon - field.lee) / (L * 1.3)) * smooth(1 - Math.abs(lat) / (field.halfWidth * 1.15));
    vx *= 1 - 0.55 * k; vy *= 1 - 0.55 * k;
  }
  // eddies behind the corners
  for (const e of eddies || eddiesAt(field, t)) {
    const dx = x - e.x, dy = y - e.y, r2 = dx * dx + dy * dy + 1e-9;
    const f = e.gamma / TAU * (1 - Math.exp(-r2 / (e.rc * e.rc))) / r2;
    vx += -dy * f; vy += dx * f;
  }
  return [vx, vy];
}

// ---------------------------------------------------------------------------------------------- air in the house
// A route through the house (an inflow stream: from the edge of the drawing to the open window, through the room and
// the doors, out of the other window) as evenly sampled points with the half width the air may take there: narrow at
// the window and at every passage between rooms, widening inside a room (within its walls), wide out in the open.
// openingHalf: half width of the window (plan units); tilted: a tilted window lets less air in.
export function routeProfile(points, rooms, G, { openingHalf, tilted = false, step }) {
  const frame = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len < 1e-9) continue;
    const n = Math.max(1, Math.ceil(len / step));
    for (let k = frame.length ? 1 : 0; k <= n; k++) frame.push({ p: [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n], s: total + len * k / n });
    total += len;
  }
  if (frame.length < 2) return null;
  const roomOf = p => rooms.findIndex(r => G.pointInPolygon(p, r.polygon) !== "outside");   // on a wall: the first room
  frame.forEach(q => { q.room = roomOf(q.p); });
  // the narrow places: where the route enters the house and wherever it passes from one room into another
  const necks = [];
  for (let i = 1; i < frame.length; i++) if (frame[i].room !== frame[i - 1].room) necks.push((frame[i].s + frame[i - 1].s) / 2);
  const half = openingHalf * (tilted ? 0.55 : 1);
  frame.forEach((q, i) => {
    const a = frame[Math.max(i - 1, 0)].p, b = frame[Math.min(i + 1, frame.length - 1)].p, l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    q.n = [-(b[1] - a[1]) / l, (b[0] - a[0]) / l];
    let clear = half * 6;                                     // out in the open
    if (q.room >= 0) {                                        // inside: up to the nearest wall of the room
      const pts = rooms[q.room].polygon;
      clear = Infinity;
      for (let e = 0; e < pts.length; e++) clear = Math.min(clear, G.projectOnSegment(q.p, pts[e], pts[(e + 1) % pts.length]).distance);
      clear *= 0.85;
    }
    const neck = necks.reduce((m, s) => Math.min(m, half + Math.abs(q.s - s) * 0.9), Infinity);
    q.w = Math.max(Math.min(clear, neck), half * 0.4);
  });
  return { frame, length: total, necks };
}
// Position on a route at distance s with lateral place u (−1 … 1).
export function routePoint(profile, s, u) {
  const f = profile.frame;
  let lo = 0, hi = f.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (f[m].s <= s) lo = m; else hi = m; }
  const a = f[lo], b = f[hi], k = b.s > a.s ? clamp((s - a.s) / (b.s - a.s), 0, 1) : 0;
  const w = a.w + (b.w - a.w) * k, n = [a.n[0] + (b.n[0] - a.n[0]) * k, a.n[1] + (b.n[1] - a.n[1]) * k];
  return [a.p[0] + (b.p[0] - a.p[0]) * k + n[0] * u * w, a.p[1] + (b.p[1] - a.p[1]) * k + n[1] * u * w, a.room];
}
