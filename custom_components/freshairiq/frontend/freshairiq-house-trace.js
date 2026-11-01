// FreshAirIQ house map – room detection on an uploaded floor plan (runs locally in the browser).
// Tap inside a room on the template: the enclosed area between dark wall lines becomes a polygon.
// Steps: grey scale → automatic threshold (Otsu) → wall mask (+ closing small gaps, + user separator
// lines) → flood fill from the tapped pixel → outer contour → simplification → straightening of
// near-horizontal/vertical walls → metres via the calibrated scale. No library, no upload anywhere.

export const toGray = ({ data, width, height }) => {
  const gray = new Uint8Array(width * height);
  for (let i = 0, j = 0; i < gray.length; i++, j += 4) {
    const a = data[j + 3] / 255;  // transparent = white paper
    gray[i] = Math.round((0.299 * data[j] + 0.587 * data[j + 1] + 0.114 * data[j + 2]) * a + 255 * (1 - a));
  }
  return gray;
};

export const otsu = gray => {
  const hist = new Array(256).fill(0);
  for (const v of gray) hist[v]++;
  const total = gray.length;
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, best = 0, threshold = 127;
  for (let i = 0; i < 256; i++) {
    wB += hist[i];
    if (!wB) continue;
    const wF = total - wB;
    if (!wF) break;
    sumB += i * hist[i];
    const mB = sumB / wB, mF = (sum - sumB) / wF, between = wB * wF * (mB - mF) ** 2;
    if (between > best) { best = between; threshold = i; }
  }
  return threshold;
};

// Square max filter (separable) – thickens walls by r pixels to close small gaps.
const dilate = (mask, w, h, r) => {
  if (r <= 0) return mask;
  const tmp = new Uint8Array(mask.length), out = new Uint8Array(mask.length);
  for (let y = 0; y < h; y++) {
    let run = 0;
    for (let x = -r; x < w + r; x++) {
      const add = x + r < w && mask[y * w + x + r], drop = x - r - 1 >= 0 && mask[y * w + x - r - 1];
      run += (add ? 1 : 0) - (drop ? 1 : 0);
      if (x >= 0 && x < w) tmp[y * w + x] = run > 0 ? 1 : 0;
    }
  }
  for (let x = 0; x < w; x++) {
    let run = 0;
    for (let y = -r; y < h + r; y++) {
      const add = y + r < h && tmp[(y + r) * w + x], drop = y - r - 1 >= 0 && tmp[(y - r - 1) * w + x];
      run += (add ? 1 : 0) - (drop ? 1 : 0);
      if (y >= 0 && y < h) out[y * w + x] = run > 0 ? 1 : 0;
    }
  }
  return out;
};

const drawLine = (mask, w, h, [x0, y0, x1, y1], thick) => {
  const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1);
  for (let i = 0; i <= steps; i++) {
    const cx = Math.round(x0 + ((x1 - x0) * i) / steps), cy = Math.round(y0 + ((y1 - y0) * i) / steps);
    for (let dy = -thick; dy <= thick; dy++) for (let dx = -thick; dx <= thick; dx++) {
      const x = cx + dx, y = cy + dy;
      if (x >= 0 && y >= 0 && x < w && y < h) mask[y * w + x] = 1;
    }
  }
};

export const wallMask = (gray, w, h, { threshold, closePx = 2, walls = [] } = {}) => {
  const t = threshold == null ? otsu(gray) : threshold;
  const raw = new Uint8Array(w * h);
  for (let i = 0; i < raw.length; i++) raw[i] = gray[i] <= t ? 1 : 0;
  for (const line of walls) drawLine(raw, w, h, line, 1);
  return { raw, closed: dilate(raw, w, h, closePx), threshold: t };
};

export const flood = (mask, w, h, sx, sy) => {
  const region = new Uint8Array(w * h);
  const seed = sy * w + sx;
  if (sx < 0 || sy < 0 || sx >= w || sy >= h || mask[seed]) return { region, count: 0, border: false };
  const stack = [seed];
  region[seed] = 1;
  let count = 0, border = false;
  while (stack.length) {
    const i = stack.pop(), x = i % w, y = (i - x) / w;
    count++;
    if (x === 0 || y === 0 || x === w - 1 || y === h - 1) border = true;
    for (const j of [i - 1, i + 1, i - w, i + w]) {
      if (j < 0 || j >= w * h || region[j] || mask[j]) continue;
      if ((j === i - 1 && x === 0) || (j === i + 1 && x === w - 1)) continue;
      region[j] = 1; stack.push(j);
    }
  }
  return { region, count, border };
};

// Moore neighbour tracing of the outer boundary of a 4-connected region.
export const contour = (region, w, h) => {
  let start = -1;
  for (let i = 0; i < region.length; i++) if (region[i]) { start = i; break; }
  if (start < 0) return [];
  const at = (x, y) => x >= 0 && y >= 0 && x < w && y < h && region[y * w + x] === 1;
  const dirs = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  const sx = start % w, sy = (start - sx) / w;
  const pts = [[sx, sy]];
  let x = sx, y = sy, dir = 6;
  for (let guard = 0; guard < region.length * 4; guard++) {
    let found = false;
    for (let k = 0; k < 8; k++) {
      const d = (dir + 6 + k) % 8, nx = x + dirs[d][0], ny = y + dirs[d][1];
      if (at(nx, ny)) { x = nx; y = ny; dir = d; found = true; break; }
    }
    if (!found || (x === sx && y === sy)) break;
    pts.push([x, y]);
  }
  return pts;
};

// Ramer–Douglas–Peucker on an open chain (first and last point are kept).
const rdp = (chain, eps) => {
  const keep = new Uint8Array(chain.length);
  keep[0] = 1; keep[chain.length - 1] = 1;
  const stack = [[0, chain.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    const [x1, y1] = chain[a], [x2, y2] = chain[b], len = Math.hypot(x2 - x1, y2 - y1) || 1;
    let best = -1, dmax = 0;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs((x2 - x1) * (y1 - chain[i][1]) - (x1 - chain[i][0]) * (y2 - y1)) / len;
      if (d > dmax) { dmax = d; best = i; }
    }
    if (dmax > eps) { keep[best] = 1; stack.push([a, best], [best, b]); }
  }
  return chain.filter((_, i) => keep[i]);
};

// Closed ring: split at the point farthest from the start, simplify both halves as open chains.
export const simplify = (pts, eps) => {
  if (pts.length < 4) return pts.slice();
  let far = 0, fd = -1;
  pts.forEach((p, i) => { const d = Math.hypot(p[0] - pts[0][0], p[1] - pts[0][1]); if (d > fd) { fd = d; far = i; } });
  const first = rdp(pts.slice(0, far + 1), eps), second = rdp([...pts.slice(far), pts[0]], eps);
  return dedupe([...first.slice(0, -1), ...second.slice(0, -1)]);
};
const dedupe = pts => pts.filter((p, i) => { const q = pts[(i + pts.length - 1) % pts.length]; return Math.hypot(p[0] - q[0], p[1] - q[1]) > 0.5; });

// Walls drawn almost horizontal/vertical (within tolDeg) become exactly so; slanted walls stay slanted.
export const straighten = (pts, tolDeg = 8) => {
  const out = pts.map(p => [p[0], p[1]]);
  const tol = Math.tan((tolDeg * Math.PI) / 180);
  for (let i = 0; i < out.length; i++) {
    const a = out[i], b = out[(i + 1) % out.length], dx = b[0] - a[0], dy = b[1] - a[1];
    if (Math.abs(dy) <= Math.abs(dx) * tol) { const m = (a[1] + b[1]) / 2; a[1] = m; b[1] = m; }
    else if (Math.abs(dx) <= Math.abs(dy) * tol) { const m = (a[0] + b[0]) / 2; a[0] = m; b[0] = m; }
  }
  return dedupe(out);
};

const area = pts => Math.abs(pts.reduce((s, p, i) => { const q = pts[(i + 1) % pts.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0)) / 2;

/**
 * Detect the room around a tapped image pixel.
 * image: {data, width, height}; seed: [x, y] in image pixels; scale: metres per pixel (null = not calibrated).
 * Returns {ok, reason, pixels, plan, areaM2}; reasons: "wall" (tapped a wall), "open" (area leaks to the
 * edge – close the gap or draw a separator), "small" (too small to be a room), "scale" (calibrate first).
 */
export const detectRoom = (image, seed, { scale = null, closePx = 2, walls = [], threshold = null } = {}) => {
  const { width: w, height: h } = image;
  const gray = toGray(image);
  const mask = wallMask(gray, w, h, { threshold, closePx, walls });
  const sx = Math.round(seed[0]), sy = Math.round(seed[1]);
  if (mask.closed[sy * w + sx]) return { ok: false, reason: "wall" };
  const fill = flood(mask.closed, w, h, sx, sy);
  if (fill.border || fill.count > w * h * 0.6) return { ok: false, reason: "open" };
  if (fill.count < Math.max(80, w * h * 0.0005)) return { ok: false, reason: "small" };
  // give back the margin the gap-closing took from the room (only into non-wall pixels)
  const grown = closePx > 0 ? dilate(fill.region, w, h, closePx).map((v, i) => (v && !mask.raw[i] ? 1 : 0)) : fill.region;
  const ring = contour(grown, w, h);
  const eps = Math.max(1.5, Math.sqrt(fill.count) * 0.02);
  const pixels = straighten(simplify(ring, eps));
  if (pixels.length < 3) return { ok: false, reason: "small" };
  if (!scale) return { ok: false, reason: "scale", pixels };
  const plan = pixels.map(([x, y]) => [Math.round(x * scale * 1000) / 1000, Math.round((h - y) * scale * 1000) / 1000]);
  return { ok: true, pixels, plan, areaM2: Math.round(area(pixels) * scale * scale * 10) / 10 };
};

// Which configured room could this area be? Area against length × width or volume ÷ height (2.5 m if unknown).
export const matchRooms = (areaM2, rooms, taken = []) => rooms
  .filter(r => !taken.includes(r.key))
  .map(r => {
    const expected = Number(r.length) > 0 && Number(r.width) > 0 ? Number(r.length) * Number(r.width)
      : Number(r.volume) > 0 ? Number(r.volume) / (Number(r.height) > 0 ? Number(r.height) : 2.5) : null;
    const fit = expected ? Math.max(0, 1 - Math.abs(areaM2 - expected) / Math.max(areaM2, expected)) : null;
    return { key: r.key, name: r.name || r.key, expected: expected ? Math.round(expected * 10) / 10 : null, fit };
  })
  .sort((a, b) => (b.fit ?? -1) - (a.fit ?? -1) || String(a.name).localeCompare(String(b.name)));

// Downscale a picture for storage/detection: longest side at most maxSide, JPEG for photos.
export const scaledSize = (w, h, maxSide = 2000) => {
  const k = Math.min(1, maxSide / Math.max(w, h));
  return [Math.max(1, Math.round(w * k)), Math.max(1, Math.round(h * k))];
};

// ------------------------------------------------------------------ template ↔ plan
// The template lies with its lower left corner at the plan origin: x = u·s, y = (H − v)·s (plan y points up).
// Before calibration a provisional scale shows it about 15 m wide; detection waits for the real scale.
export const PROVISIONAL_WIDTH_M = 15;
export const displayScale = u => (u && u.scale_m_per_px > 0 ? u.scale_m_per_px : PROVISIONAL_WIDTH_M / Math.max((u && u.width) || 1, 1));
export const toImage = (u, p) => { const s = displayScale(u); return [p[0] / s, u.height - p[1] / s]; };
export const toPlan = (u, q) => { const s = displayScale(u); return [q[0] * s, (u.height - q[1]) * s]; };
export const scaleFromCalibration = (a, b, meters) => {
  const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
  return d >= 2 && meters > 0 ? meters / d : null;
};
// An arrow drawn on the template from a to b points north (image coordinates, y down). "Up" on the plan
// then has the compass bearing 360° − (clockwise angle of the arrow from "up").
export const northFromArrow = (a, b) => {
  const dx = b[0] - a[0], dy = a[1] - b[1];
  if (Math.hypot(dx, dy) < 2) return null;
  const angle = (Math.atan2(dx, dy) * 180) / Math.PI;
  return Math.round((((360 - angle) % 360) + 360) % 360 * 10) / 10;
};

const r3 = v => Math.round(v * 1000) / 1000;
const signed = pts => pts.reduce((s, p, i) => { const q = pts[(i + 1) % pts.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0) / 2;
const project = (p, a, b) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], len2 = dx * dx + dy * dy || 1;
  const t = Math.min(Math.max(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2, 0), 1);
  return { t, distance: Math.hypot(a[0] + dx * t - p[0], a[1] + dy * t - p[1]) };
};
export const nearestWall = (polygon, p) => polygon.reduce((best, a, i) => {
  const hit = project(p, a, polygon[(i + 1) % polygon.length]);
  return hit.distance < best.distance ? { index: i, t: hit.t, distance: hit.distance } : best;
}, { index: 0, t: 0.5, distance: Infinity });

// Outward direction of wall i (unit vector), whatever the winding of the polygon.
const outward = (polygon, i) => {
  const a = polygon[i], b = polygon[(i + 1) % polygon.length], k = signed(polygon) >= 0 ? 1 : -1;
  const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
  return [(k * dy) / len, (-k * dx) / len];
};
const boxOf = pts => { const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]); return [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs) || 1, Math.max(...ys) - Math.min(...ys) || 1]; };
// Where an opening of the old outline belongs on the new one: same facade direction (within 45°),
// same relative place in the room; any wall only if no wall faces that way any more.
const moveOpening = (old, polygon, o) => {
  const a = old[o.edge], b = old[(o.edge + 1) % old.length];
  if (!a || !b) return { index: 0, t: 0.5 };
  const n = outward(old, o.edge), ob = boxOf(old), nb = boxOf(polygon);
  const x = a[0] + (b[0] - a[0]) * o.offset, y = a[1] + (b[1] - a[1]) * o.offset;
  const p = [nb[0] + ((x - ob[0]) / ob[2]) * nb[2], nb[1] + ((y - ob[1]) / ob[3]) * nb[3]];
  const facing = polygon.map((_, i) => i).filter(i => { const m = outward(polygon, i); return m[0] * n[0] + m[1] * n[1] > Math.SQRT1_2; });
  const pick = facing.length ? facing : polygon.map((_, i) => i);
  return pick.reduce((best, i) => {
    const hit = project(p, polygon[i], polygon[(i + 1) % polygon.length]);
    return hit.distance < best.distance ? { index: i, t: hit.t, distance: hit.distance } : best;
  }, { index: 0, t: 0.5, distance: Infinity });
};

/**
 * Put a detected outline into the layout as the room `key` on `floorId` (provenance "traced").
 * An existing outline is replaced; its openings move to the wall facing the same way, at the same
 * relative place, so window contacts, settings and the facade direction survive. Returns the room id.
 */
export const assignTraced = (layout, { key, floorId, plan }) => {
  const polygon = (signed(plan) >= 0 ? plan : plan.slice().reverse()).map(p => [r3(p[0]), r3(p[1])]);
  let room = layout.rooms.find(r => r.room_key === key);
  if (!room) { room = { id: `r_${key}`, room_key: key, floor_id: floorId, polygon: [], provenance: "traced" }; layout.rooms.push(room); }
  const old = room.polygon;
  for (const o of layout.openings.filter(x => x.room_id === room.id)) {
    const hit = moveOpening(old, polygon, o);
    o.edge = hit.index; o.offset = r3(Math.min(Math.max(hit.t, 0.02), 0.98));
  }
  Object.assign(room, { floor_id: floorId, polygon, provenance: "traced" });
  return room.id;
};

// Tap next to a wall: a new opening on the nearest wall of the nearest room of that floor (within maxDist m).
// A door or passage belongs on an interior wall: its whole span must lie on another room's wall – the same
// rule and tolerance as house_layout.opening_neighbour, so the editor and FreshAirIQ's air paths agree.
// A shared corner or a wall a few centimetres away is no interior wall ({ error: "no_interior_wall" }).
export const INTERIOR_KINDS = new Set(["door", "passage"]);
export const WALL_TOLERANCE = 0.05;  // = house_layout.WALL_TOLERANCE
const DEFAULT_WIDTH = { window: null, door: 0.9, passage: 1.0 };
const MIN_INTERIOR_WIDTH = 0.3;
const onSegment = (a, b, p, tol) => {  // = house_layout._on_segment
  const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
  if (Math.abs(cross) > tol * Math.max(1, Math.hypot(b[0] - a[0], b[1] - a[1]))) return false;
  return p[0] >= Math.min(a[0], b[0]) - tol && p[0] <= Math.max(a[0], b[0]) + tol && p[1] >= Math.min(a[1], b[1]) - tol && p[1] <= Math.max(a[1], b[1]) + tol;
};
// Points along the whole span of an opening (width as drawn: stored, else min(0.9, 40 % of the wall)).
export const openingSamples = (polygon, o, count = 5) => {
  const a = polygon[o.edge], b = polygon[(o.edge + 1) % polygon.length], len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const half = Math.min(Math.max(o.width_m || Math.min(0.9, len * 0.4), 0), len) / len / 2;
  const offset = Number.isFinite(Number(o.offset)) ? Number(o.offset) : 0.5;
  const lo = Math.max(offset - half, 0), hi = Math.min(offset + half, 1);
  return Array.from({ length: count }, (_, k) => { const t = lo + (hi - lo) * k / (count - 1); return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]; });
};
// The room on the other side of an opening, or null (= outside).
export const openingTarget = (layout, room, o) => layout.rooms.find(other => other.id !== room.id && other.floor_id === room.floor_id
  && other.polygon.length >= 3 && openingSamples(room.polygon, o).every(p => other.polygon.some((a, i) => onSegment(a, other.polygon[(i + 1) % other.polygon.length], p, WALL_TOLERANCE)))) || null;
// Stretches (in m along wall a→b) where another room of the floor has a wall on the same line.
const sharedStretches = (layout, room, a, b) => {
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len;
  const off = p => Math.abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux), along = p => (p[0] - a[0]) * ux + (p[1] - a[1]) * uy;
  const out = [];
  for (const other of layout.rooms) {
    if (other.id === room.id || other.floor_id !== room.floor_id || other.polygon.length < 3) continue;
    other.polygon.forEach((c, i) => {
      const d = other.polygon[(i + 1) % other.polygon.length];
      if (off(c) > WALL_TOLERANCE || off(d) > WALL_TOLERANCE) return;
      const lo = Math.max(Math.min(along(c), along(d)), 0), hi = Math.min(Math.max(along(c), along(d)), len);
      if (hi - lo > 1e-6) out.push([lo, hi]);
    });
  }
  return out;
};
export const openingAt = (layout, floorId, p, maxDist = 0.6, kind = "window") => {
  let best = null;
  for (const room of layout.rooms.filter(r => r.floor_id === floorId && r.polygon.length >= 3)) {
    const hit = nearestWall(room.polygon, p);
    if (hit.distance <= maxDist && (!best || hit.distance < best.distance)) best = Object.assign({ room }, hit);
  }
  if (!best) return null;
  const a = best.room.polygon[best.index], b = best.room.polygon[(best.index + 1) % best.room.polygon.length];
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  let offset = r3(Math.min(Math.max(best.t, 0.02), 0.98));
  let width = DEFAULT_WIDTH[kind] == null ? null : r3(Math.min(DEFAULT_WIDTH[kind], len));
  if (INTERIOR_KINDS.has(kind)) {
    // fit the opening onto the shared stretch under the tap (narrower if the stretch is shorter)
    const at = best.t * len, stretch = sharedStretches(layout, best.room, a, b).find(([lo, hi]) => at >= lo - WALL_TOLERANCE && at <= hi + WALL_TOLERANCE);
    if (!stretch || stretch[1] - stretch[0] < MIN_INTERIOR_WIDTH) return { error: "no_interior_wall" };
    width = r3(Math.min(width, stretch[1] - stretch[0]));
    offset = r3(Math.min(Math.max(at, stretch[0] + width / 2), stretch[1] - width / 2) / len);
  }
  const opening = { id: `o_${best.room.room_key}_${Date.now().toString(36)}`, room_id: best.room.id, edge: best.index, offset,
    width_m: width, kind, mechanics: kind === "door" ? "door" : "unknown", contacts: [], provenance: "user" };
  if (INTERIOR_KINDS.has(kind) && !openingTarget(layout, best.room, opening)) return { error: "no_interior_wall" };
  return opening;
};

// ------------------------------------------------------------------ browser side (canvas)
const loadImage = src => new Promise((resolve, reject) => {
  const img = new Image();
  img.onload = () => resolve(img); img.onerror = () => reject(new Error("image"));
  img.src = src;
});
const draw = (img, w, h) => {
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h);  // transparent PNG = white paper
  ctx.drawImage(img, 0, 0, w, h);
  return { canvas, ctx };
};
// A picked file → downscaled JPEG for storage ({mime, data (base64), width, height}). PDF is not supported.
export const encodeFile = async (file, maxSide = 2000, maxChars = 2_900_000) => {
  if (!/^image\/(png|jpeg|webp)$/.test(file.type || "")) throw new Error("type");
  const url = URL.createObjectURL(file);
  try {
    const img = await loadImage(url);
    const [w, h] = scaledSize(img.naturalWidth, img.naturalHeight, maxSide);
    if (w < 16 || h < 16) throw new Error("size");
    const { canvas } = draw(img, w, h);
    for (const quality of [0.9, 0.8, 0.65, 0.5]) {
      const data = canvas.toDataURL("image/jpeg", quality).split(",")[1];
      if (data.length <= maxChars) return { mime: "image/jpeg", data, width: w, height: h };
    }
    throw new Error("large");
  } finally { URL.revokeObjectURL(url); }
};
// The stored template → pixels for detection at a smaller working size (factor k = working / stored).
export const pixelsOf = async (src, width, height, maxSide = 1000) => {
  const img = await loadImage(src);
  const [w, h] = scaledSize(width, height, maxSide);
  const { ctx } = draw(img, w, h);
  return { image: ctx.getImageData(0, 0, w, h), k: w / width };
};
