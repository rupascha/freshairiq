// FreshAirIQ house map – look & feel: brand colours, comic style, wind streams, hero header, room dialog.
// Pure presentation helpers; all values come from FreshAirIQ's published data (no decisions here).

export const BRAND = {
  night: "#031a33", deep: "#06305c", panel: "#0a3a6b", ink: "#021024", cyan: "#00d8f0", sky: "#4fc3ff",
  ice: "#c9f3ff", leaf: "#39e07a", lime: "#a6ff4d", sun: "#ffc93c", orange: "#ff9f43", coral: "#ff5d5d", slate: "#7d8ca3", white: "#f4fbff",
};
export const TONE_COLOR = { act: BRAND.leaf, run: BRAND.cyan, close: BRAND.orange, wait: BRAND.sun, sensor: BRAND.slate, ok: "#1d6f8f", critical: BRAND.coral };
export const TONE_EMOJI = { act: "💨", run: "🌬️", close: "🪟", wait: "⏳", sensor: "🔧", ok: "✅", critical: "⚠️" };

const r3 = v => Math.round(v * 1000) / 1000;
const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// 0.26.6.0(6/7): room surfaces by state. 0.26.6.0(7): one calm, deep family of surfaces – a room at rest is a quiet
// blue-slate, a waiting room only a shade warmer (no longer yellow); the state speaks through the soft inner rim, the
// capsule and the climate layer on top (temperature, humidity, mould risk). Top-to-bottom gradient; ``text`` is the
// readable label colour on that surface (contrast ≥ 4:1 to both stops).
export const ROOM_TONES = {
  ok: { top: "#2b6584", bottom: "#21516c", text: "light" },
  sensor: { top: "#56637a", bottom: "#465166", text: "light" },
  wait: { top: "#3d5f80", bottom: "#324f6c", text: "light" },
  run: { top: "#21708f", bottom: "#1a5c78", text: "light", rim: "#bff1ff" },
  act: { top: "#22705a", bottom: "#1b5a49", text: "light", rim: "#c4f7d8" },
  close: { top: "#8a5232", bottom: "#734327", text: "light", rim: "#ffd9b8" },
  critical: { top: "#93404a", bottom: "#7a333c", text: "light", rim: "#ffd0d0" },
};
export function roomDefs(px) {
  return Object.entries(ROOM_TONES).map(([k, v]) => `<linearGradient id="rf-${k}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${v.top}"/><stop offset="1" stop-color="${v.bottom}"/></linearGradient>`).join("")
    + `<pattern id="rf-hatch" width="${px(12)}" height="${px(12)}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="${px(12)}" stroke="#ffffff" stroke-opacity=".22" stroke-width="${px(4)}"/></pattern>`;
}
// Animation time of one stream dash cycle: stronger wind = faster streams (schematic, not a measured speed).
export const streamSeconds = speedMs => Math.min(Math.max(7 / ((Number(speedMs) || 0) + 1), 0.45), 5);

// ---- soft wind waves (owner request 31.10.): translucent ribbons whose waves travel along each stream.
// The phase is advanced by the card from its own clock and survives every redraw, so the animation never
// restarts and has no loop seam (the wave is periodic in the phase).
// A stream as one polyline in plan coordinates (the closing curve of a deflected stream sampled).
export function streamLine(stream, steps = 12) {
  const pts = stream.points.map(p => [p[0], p[1]]);
  if (stream.curve) {
    const p0 = pts[pts.length - 1], c = stream.curve.ctrl, p2 = stream.curve.to;
    for (let k = 1; k <= steps; k++) {
      const t = k / steps, u = 1 - t;
      pts.push([u * u * p0[0] + 2 * u * t * c[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * c[1] + t * t * p2[1]]);
    }
  }
  return pts;
}
// Indices of the points that keep a polyline's shape within ``tol`` (Douglas–Peucker), first and last included.
function bendKeys(line, tol) {
  const keep = new Uint8Array(line.length), stack = [[0, line.length - 1]];
  keep[0] = keep[line.length - 1] = 1;
  while (stack.length) {
    const [a, b] = stack.pop(), A = line[a], B = line[b], dx = B[0] - A[0], dy = B[1] - A[1], len = Math.hypot(dx, dy);
    let worst = -1, at = -1;
    for (let i = a + 1; i < b; i++) {
      const P = line[i], d = len > 1e-9 ? Math.abs((P[0] - A[0]) * dy - (P[1] - A[1]) * dx) / len : Math.hypot(P[0] - A[0], P[1] - A[1]);
      if (d > worst) { worst = d; at = i; }
    }
    if (worst > tol) { keep[at] = 1; stack.push([a, at], [at, b]); }
  }
  const keys = [];
  keep.forEach((k, i) => { if (k) keys.push(i); });
  return keys;
}
// Even samples along a polyline with smoothed normals: [{p, s, n}], s = distance from the start.
// 0.26.7.2: ``clear`` (optional, one value per point of ``line``): the free distance to the facade there – each sample keeps it
// as ``c`` (wavePath never swings a ribbon further than that, so no wave reaches into a wall); ``maxPoints`` limits the samples.
// ``speed`` (optional, one value per point of ``line``): the air's speed there relative to the free wind (the 2D flow model) – each
// sample keeps it as ``v`` and a travel coordinate ``u`` (the distance weighted by 1/v, scaled to the same length): a wave drawn
// along ``u`` runs slower and bunches where the air slows in front of the house and runs faster past its sides.
export function waveFrame(line, step, clear = null, maxPoints = 0, speed = null, damp = null, near = null) {
  const out = [];
  let total = 0;
  if (maxPoints > 1) {
    let length = 0, count = 1;
    const fine = step / 12;
    for (let i = 0; i < line.length - 1; i++) length += Math.hypot(line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1]);
    step = Math.max(step, length / (maxPoints - 1));
    for (let i = 0; i < line.length - 1; i++) { const len = Math.hypot(line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1]); if (len >= 1e-9) count += Math.max(1, Math.ceil(len / step)); }
    // a densely traced line (more samples than allowed): at most ``maxPoints`` samples. The bends are kept (Douglas–Peucker keys,
    // the tolerance grows until they leave room), the rest goes evenly by length between them – an even chord across a bend would
    // cut the corner of a notch the line itself passes at a distance.
    if (count > maxPoints && length > 0) {
      const cum = [0];
      for (let i = 1; i < line.length; i++) cum.push(cum[i - 1] + Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]));
      let keys = [0, line.length - 1];
      for (let tol = fine, round = 0; round < 24; round++, tol *= 1.5) {
        keys = bendKeys(line, tol);
        if (keys.length <= maxPoints - 8) break;
      }
      if (keys.length > maxPoints) keys = [0, line.length - 1];
      const extra = maxPoints - keys.length;
      let i = 0;
      const at = s => {
        while (i < line.length - 2 && cum[i + 1] < s) i += 1;
        const seg = cum[i + 1] - cum[i], u = seg > 1e-9 ? Math.min(Math.max((s - cum[i]) / seg, 0), 1) : 0, a = line[i], b = line[i + 1];
        const q = { p: [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u], s };
        if (clear) q.c = clear[i] + (clear[i + 1] - clear[i]) * u;
        if (speed) q.v = speed[i] + (speed[i + 1] - speed[i]) * u;
        if (damp) q.a = damp[i] + (damp[i + 1] - damp[i]) * u;
        if (near) q.r = near[i] + (near[i + 1] - near[i]) * u;
        return q;
      };
      for (let k = 0; k < keys.length - 1; k++) {
        const s0 = cum[keys[k]], span = cum[keys[k + 1]] - s0;
        const m = Math.round(extra * cum[keys[k + 1]] / length) - Math.round(extra * s0 / length);
        for (let t = 0; t <= m; t++) out.push(at(s0 + span * t / (m + 1)));
      }
      out.push(at(length));
      total = length;
    }
  }
  const resampled = out.length > 0;
  for (let i = 0; !resampled && i < line.length - 1; i++) {
    const a = line[i], b = line[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len < 1e-9) continue;
    const n = Math.max(1, Math.ceil(len / step));
    for (let k = out.length ? 1 : 0; k <= n; k++) {
      const q = { p: [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n], s: total + len * k / n };
      if (clear) q.c = clear[i] + (clear[i + 1] - clear[i]) * k / n;
      if (speed) q.v = speed[i] + (speed[i + 1] - speed[i]) * k / n;
      if (damp) q.a = damp[i] + (damp[i + 1] - damp[i]) * k / n;
      if (near) q.r = near[i] + (near[i + 1] - near[i]) * k / n;
      out.push(q);
    }
    total += len;
  }
  out.forEach((q, i) => {
    const a = out[Math.max(i - 2, 0)].p, b = out[Math.min(i + 2, out.length - 1)].p;
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    q.n = [-(b[1] - a[1]) / len, (b[0] - a[0]) / len];
  });
  if (speed && out.length > 1) {
    let u = 0;
    out.forEach((q, i) => { if (i) u += (q.s - out[i - 1].s) * 2 / (Math.max(q.v, 0.05) + Math.max(out[i - 1].v, 0.05)); q.u = u; });
    const k = u > 0 ? total / u : 1;
    for (const q of out) q.u *= k;
  }
  return { samples: out, length: total };
}
// One wave strand at ``phase`` (cycles): the offset follows sin(2π(s/λ − phase) + shift) and fades to 0 at
// both ends, so a strand starts and ends calmly on its stream. Returns "M x,y L x,y …" in SVG coordinates.
// 0.26.7.2: ``form`` (0..1) adds a second harmonic – every gust its own wave shape; ``pad``: the half width of the strand, kept
// free in front of a wall (see waveFrame ``clear``)
export function wavePath(frame, { amp, wavelength, shift = 0, form = 0, pad = 0, line = pad }, phase) {
  const L = frame.length || 1, ramp = Math.min(L * 0.18, wavelength), f2 = form * 0.4, norm = 1 / (1 + f2);
  return frame.samples.map((q, i) => {
    const env = Math.min(1, q.s / ramp, (L - q.s) / ramp), x = 2 * Math.PI * ((q.u ?? q.s) / wavelength - phase) + shift;
    let top = amp * Math.max(env, 0) * (q.a ?? 1);
    // the wall: the strand's own half width stays free; the next ribbon: the visible line's half width (``line``) stays within half
    // the way to it (``line`` null: the broad, nearly clear air mass, which lies over its neighbours anyway). The swing gets smaller
    // there, it is never cut flat.
    if (q.c != null || (q.r != null && line != null)) top = Math.min(Math.abs(top), Math.max(Math.min(q.c != null ? q.c - pad : Infinity, q.r != null && line != null ? q.r - line : Infinity), 0));
    const off = top * (Math.sin(x) + f2 * Math.sin(2 * x + 1.3)) * norm;
    return `${i ? "L" : "M"} ${r3(q.p[0] + q.n[0] * off)},${r3(-(q.p[1] + q.n[1] * off))}`;
  }).join(" ");
}
// Three strands per stream like layered air ribbons: middle (the stream itself) and two lighter companions.
export const WAVE_STRANDS = [
  { cls: "mid", amp: 1, wave: 1, shift: 0, width: 1 },
  { cls: "hi", amp: 0.75, wave: 1.38, shift: 2.1, width: 0.6 },
  { cls: "lo", amp: 1.6, wave: 0.6, shift: 4.2, width: 6 },   // order 8: a broad, nearly transparent air mass
];

// The widest decorative ribbon's half width with a margin (plan units) – the least distance its stream keeps from the walls: the
// broad air mass (from "normal" on) is the widest strand; ``px`` turns screen pixels into plan units.
export const ribbonClear = (px, motion) => px(4.5 * 1.35 * (motion.strands >= 2 ? 6 : 1) / 2 + 4);
const RIBBON_COLORS = { mid: "#bfe9ff", hi: "#e6f7ff", lo: "#7cc8f0" };
// The ribbons of all streams as SVG: {inflow, behind} – the incoming air over the rooms, the rest behind the house. Each stream gets
// the strands of the animation level (the stream itself; from "normal" on a broad, nearly transparent air mass; at "intense" a
// bright companion). ``frameOf(stream)``: its wave samples; ``waves`` collects {frame, geo} for the card's loop; ``phase(geo)``:
// the wave phase now. Every strand keeps its own half width free in front of a wall (``pad``).
export function ribbonsSvg(streams, { variety, motion, px, round3, waves, phase, frameOf }) {
  let inflow = "", behind = "";
  const strands = motion.strands >= 3 ? WAVE_STRANDS : motion.strands >= 2 ? [WAVE_STRANDS[0], WAVE_STRANDS[2]] : [WAVE_STRANDS[0]];
  streams.forEach(s => {
    const frame = frameOf(s);
    if (frame.samples.length < 2) return;
    const first = frame.samples[0].p, last = frame.samples[frame.samples.length - 1].p;
    const vr = s.variety != null && variety[s.variety] ? variety[s.variety] : { amp: 1, wave: 1, pace: 1, offset: 0, opacity: 0.85, width: 1 };
    const base = (s.kind === "inflow" ? (s.tilted ? 5 : 7) : 4.5) * (s.kind === "inflow" ? 1 : vr.width);
    let line = "";
    strands.forEach((st, j) => {
      const index = waves.length;
      const geo = { amp: px(6.5) * st.amp * vr.amp * (s.kind === "pass" ? 0.8 : 1), wavelength: px(175) * st.wave * vr.wave, shift: st.shift + index * 0.37, pace: vr.pace, offset: vr.offset,
        form: vr.form || 0, pad: px(base * st.width / 2 + 2), line: st.cls === "lo" ? null : px(base / 2 + 1) };
      waves.push({ frame, geo });
      const gid = `wg${index}`, color = s.kind === "inflow" && j === 0 ? BRAND.white : RIBBON_COLORS[st.cls];
      const endOpacity = s.kind === "inflow" && !s.exits ? 1 : 0;  // air streaming out fades outside the house
      line += `<linearGradient id="${gid}" gradientUnits="userSpaceOnUse" x1="${round3(first[0])}" y1="${round3(-first[1])}" x2="${round3(last[0])}" y2="${round3(-last[1])}"><stop offset="0" stop-color="${color}" stop-opacity="0"/><stop offset=".2" stop-color="${color}"/><stop offset=".8" stop-color="${color}"/><stop offset="1" stop-color="${color}" stop-opacity="${endOpacity}"/></linearGradient>`;
      const cls = `${j === 0 ? `stream ${s.kind} ` : ""}wave ${st.cls} k-${s.kind}${s.tilted ? " tilted" : ""}${s.exits ? " exits" : ""}`;
      line += `<path class="${cls}" data-wave="${index}" d="${wavePath(frame, geo, phase(geo))}" stroke="url(#${gid})" stroke-width="${px(base * st.width)}"${s.kind === "inflow" ? "" : ` stroke-opacity="${round3(vr.opacity)}"`}${s.kind === "inflow" && j === 0 && !s.exits ? ' marker-end="url(#ahc)"' : ""}/>`;
    });
    // order 8: the fine particles of the incoming air are drawn on the canvas air layer (freshairiq-house-flowlayer.js)
    if (s.kind === "inflow") inflow += line; else behind += line;
  });
  return { inflow, behind };
}

const OPEN = new Set(["open", "tilted", "open_unspecified"]);
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
const mul = (a, k) => [a[0] * k, a[1] * k];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1];

function rayHit(S, t, a, b) {
  const e = sub(b, a), den = t[0] * e[1] - t[1] * e[0];
  if (Math.abs(den) < 1e-9) return null;
  const w = sub(a, S);
  const s = (w[0] * e[1] - w[1] * e[0]) / den, u = (w[0] * t[1] - w[1] * t[0]) / den;
  return s > 1e-6 && u >= 0 && u <= 1 ? { s, u } : null;
}

// Part of the line base + s·dir inside the frame {minX,minY,maxX,maxY} (slab method), or null.
function clipLine(base, dir, f) {
  let lo = -Infinity, hi = Infinity;
  for (const [o, d, min, max] of [[base[0], dir[0], f.minX, f.maxX], [base[1], dir[1], f.minY, f.maxY]]) {
    if (Math.abs(d) < 1e-9) { if (o < min || o > max) return null; continue; }
    const a = (min - o) / d, b = (max - o) / d;
    lo = Math.max(lo, Math.min(a, b)); hi = Math.min(hi, Math.max(a, b));
  }
  return lo < hi ? [lo, hi] : null;
}
const smoothstep = x => { const v = Math.min(Math.max(x, 0), 1); return v * v * (3 - 2 * v); };
const unit = v => { const l = Math.hypot(v[0], v[1]); return l > 1e-12 ? [v[0] / l, v[1] / l] : null; };

// 0.26.7.2: the house's real outside contour (G.wallSegments, outer wall parts only) as a soft distance field. The distance is a
// soft minimum over all outside walls, so its lines of equal distance are rounded at every corner – also in the inner corner of an
// L-shaped house, where the plain distance would have a kink – and never further from the house than the real distance.
// at(x, y): {d, n, room, coh, span} – the distance, the unit direction away from the house, the room of the nearest wall, how much
// the near walls agree on that direction and how far the nearest wall point lies from that wall's ends.
export function facadeField(rooms, G) {
  const segs = [];
  for (const w of G.wallSegments(rooms, [])) {
    if (w.interior) continue;
    const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1], len = Math.hypot(dx, dy);
    if (len > 1e-6) segs.push({ ax: w.a[0], ay: w.a[1], tx: dx / len, ty: dy / len, len, room: w.room });
  }
  const box = G.bbox(rooms.map(r => r.polygon));
  const c = [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2], R = Math.hypot(box.maxX - box.minX, box.maxY - box.minY) / 2 || 1;
  const soft = R * 0.07;   // about the distance the streams keep: an inner corner is rounded as wide as they pass it
  // a narrow notch (a U's courtyard, a recess): the streams pass over its opening as over a wall – the air in it stays nearly still –
  // instead of diving in and out of it; an open angle (an L) is no notch and keeps its walls. Only for the distance: ``inside`` and
  // ``crosses`` know the real walls.
  const ends = segs.flatMap(s => [[s.ax, s.ay], [s.ax + s.tx * s.len, s.ay + s.ty * s.len]]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]), hull = [];
  for (const pass of [ends, ends.slice().reverse()]) {
    const start = hull.length;
    for (const q of pass) { while (hull.length >= start + 2 && cross(hull[hull.length - 2], hull[hull.length - 1], q) <= 1e-9) hull.pop(); hull.push(q); }
    hull.pop();
  }
  const wallDist = (x, y) => Math.min(...segs.map(s => { const u = Math.min(Math.max((x - s.ax) * s.tx + (y - s.ay) * s.ty, 0), s.len); return Math.hypot(x - s.ax - s.tx * u, y - s.ay - s.ty * u); }));
  const near = segs.slice();
  hull.forEach((h0, i) => {
    // the corners lying on this edge of the hull split it: each opening between two of them is checked on its own
    const h1 = hull[(i + 1) % hull.length], L = Math.hypot(h1[0] - h0[0], h1[1] - h0[1]);
    if (L < 1e-6) return;
    const tx = (h1[0] - h0[0]) / L, ty = (h1[1] - h0[1]) / L, on = [0, L];
    for (const q of ends) { const u = (q[0] - h0[0]) * tx + (q[1] - h0[1]) * ty; if (u > 1e-6 && u < L - 1e-6 && Math.abs((q[0] - h0[0]) * ty - (q[1] - h0[1]) * tx) < 1e-6) on.push(u); }
    on.sort((a, b) => a - b);
    for (let k = 0; k < on.length - 1; k++) {
      const len = on[k + 1] - on[k], ax = h0[0] + tx * on[k], ay = h0[1] + ty * on[k];
      if (len > 1e-6 && len < R && wallDist(ax + tx * len / 2, ay + ty * len / 2) > len * 0.05) near.push({ ax, ay, tx, ty, len, room: null });
    }
  });
  const hits = new Float64Array(near.length * 3);   // reused: the field is asked thousands of times while the ways are traced
  const at = (x, y) => {
    let m = Infinity;
    let mid = 0;
    for (let k = 0; k < near.length; k++) {
      const s = near[k], u = Math.min(Math.max((x - s.ax) * s.tx + (y - s.ay) * s.ty, 0), s.len);
      const vx = x - (s.ax + s.tx * u), vy = y - (s.ay + s.ty * u), d = Math.sqrt(vx * vx + vy * vy);
      hits[k * 3] = d; hits[k * 3 + 1] = vx; hits[k * 3 + 2] = vy;
      if (d < m) { m = d; mid = Math.min(u, s.len - u); }
    }
    let sw = 0, gx = 0, gy = 0, room = null, best = Infinity;
    for (let i = 0; i < hits.length; i += 3) {
      const d = hits[i];
      if (d - m > soft * 8) continue;
      const w = Math.exp(-(d - m) / soft);
      sw += w; if (d > 1e-9) { gx += w * hits[i + 1] / d; gy += w * hits[i + 2] / d; }
      if (d < best && near[i / 3].room != null) { best = d; room = near[i / 3].room; }
    }
    const n = unit([gx, gy]) || unit([x - c[0], y - c[1]]) || [0, 1];
    // coh: how much the near walls agree on the way out – 1 in front of a wall and around an outer corner, less in an inner one
    // span: how far the nearest wall point lies from the wall's ends (0 at a corner)
    return { d: sw > 0 ? m - soft * Math.log(sw) : m, n, room, coh: sw > 0 ? Math.hypot(gx, gy) / sw : 1, span: mid };
  };
  // inside the house (even–odd over the outside walls): ``at`` measures only the distance, not the side
  const inside = (x, y) => {
    let odd = false;
    for (const s of segs) {
      const y0 = s.ay, y1 = s.ay + s.ty * s.len;
      if ((y0 > y) !== (y1 > y) && x < s.ax + (y - y0) / (y1 - y0) * s.tx * s.len) odd = !odd;
    }
    return odd;
  };
  // does the way p → q cross an outside wall
  const crosses = (p, q) => segs.some(s => {
    const bx = s.ax + s.tx * s.len, by = s.ay + s.ty * s.len;
    const o = (ux, uy, vx, vy, wx, wy) => Math.sign((vx - ux) * (wy - uy) - (vy - uy) * (wx - ux));
    return o(p[0], p[1], q[0], q[1], s.ax, s.ay) * o(p[0], p[1], q[0], q[1], bx, by) < 0 && o(s.ax, s.ay, bx, by, p[0], p[1]) * o(s.ax, s.ay, bx, by, q[0], q[1]) < 0;
  });
  return { segs, box, c, R, at, inside, crosses };
}

// One stream from S in the wind direction t: in free air it keeps the wind; near the house it turns softly before it arrives,
// keeps its own distance (``gap``) along the facade and winds around the corners. As soon as the way along the wind passes the rest
// of the house on its side (the last edge there), it lets go and runs on with the wind – keeping its distance to the house's outline
// (``env``: down a step of the facade, closing in towards the wake behind it), turning softly (the bend limit below) and never
// wrapping around the back of the house. Returns the points, their clearance, whether (and at which room) it met the house, the
// side it took and where it let go (``release``, an index of ``points``; -1 when it never did).
// 0.26.7.2: on the windward facade the air comes closer before it turns aside: the stream's own distance shrinks there (``facing``:
// how much the nearest wall faces the wind) and the turn starts nearer the wall. Only the part beyond ``minClear`` (the drawn
// ribbon's half width with its margin) shrinks, so the widest ribbon stays outside the house and the streams keep their order
// and their own distances there.
const WINDWARD_CLOSER = 0.5, WINDWARD_LATER = 0.5;
function traceStream(F, S, t, f, v, limit, d0, minClear = 0, env = null) {
  const R = F.R, h = R / 45, reach0 = R * (0.24 + 0.15 * v.hug);
  // only in front of a windward wall: an inner corner (the walls disagree on the way out) and the turn around an outer corner keep
  // the full distance, so the air comes closer where it meets the facade and passes the corners in the same wide curves as before
  const facing = here => Math.min(Math.max(-(t[0] * here.n[0] + t[1] * here.n[1]), 0), 1) * (1 - smoothstep((0.985 - (here.coh ?? 1)) / 0.12))
    * smoothstep((here.span ?? R) / (R * 0.12));
  const dLoc = here => minClear + Math.max(d0 - minClear, 0) * (1 - WINDWARD_CLOSER * facing(here));
  const reachAt = here => dLoc(here) + reach0 * (1 - WINDWARD_LATER * facing(here));
  const hugMax = R * (2.6 + 1.4 * v.hug);   // a stream that never finds the free wind (a deep notch) ends there
  const maxTurn = 0.2, margin = h * 2;   // radians per step: the tightest bend stays a soft curve
  const pts = [[S[0], S[1]]];
  let pos = [S[0], S[1]], dir = [t[0], t[1]], touched = false, free = false, side = 0, hugged = 0, room = null, contacts = 0, met = false, release = -1;
  let travelled = 0, after = 0, seen = false;
  // how far the house reaches along the wind: a free run is checked that far (and a little beyond)
  let lonMax = -Infinity;
  for (const s of F.segs) lonMax = Math.max(lonMax, s.ax * t[0] + s.ay * t[1], (s.ax + s.tx * s.len) * t[0] + (s.ay + s.ty * s.len) * t[1]);
  const runsFree = (p, thr) => {
    const far = lonMax - (p[0] * t[0] + p[1] * t[1]) + R * 0.25, stepLen = R / 12;
    for (let k = 1, n = Math.ceil(far / stepLen); k <= n; k++) {
      const x = p[0] + t[0] * k * stepLen, y = p[1] + t[1] * k * stepLen;
      if (F.inside(x, y) || F.at(x, y).d < thr) return false;
    }
    return true;
  };
  let wsd = 1, hold = 0;   // released: the side of the wake and the distance kept to the house's outline (envelope)
  const want = (q, state) => {
    if (!state.touched) return state.free && env ? env.steer(q, wsd, hold) : t;
    const here = F.at(q[0], q[1]), d = here.d, dl = dLoc(here), reach = reachAt(here);
    let n = here.n, tau = [-n[1] * state.side, n[0] * state.side];
    // a wall ahead (the inner corner of an L): the stream starts to turn before it gets there
    const look = d0 * 1.2 + R * 0.12, ahead = F.at(q[0] + tau[0] * look, q[1] + tau[1] * look);
    if (ahead.d < d) { const wa = smoothstep((d - ahead.d) / (d0 * 0.8)); n = unit([n[0] * (1 - wa) + ahead.n[0] * wa, n[1] * (1 - wa) + ahead.n[1] * wa]) || n; tau = [-n[1] * state.side, n[0] * state.side]; }
    const err = (dl - d) / dl;
    const k = Math.max(-0.8, Math.min(0.8, 1.4 * err));
    const along = unit([tau[0] + n[0] * k, tau[1] + n[1] * k]) || tau;
    const w = smoothstep((reach - d) / (reach - dl));
    const out = unit([t[0] * (1 - w) + along[0] * w, t[1] * (1 - w) + along[1] * w]) || along;
    return guard(out, d, n, tau, dl);
  };
  // never towards a wall it is already close to (this wins over the bend limit below)
  const guard = (out, d, n, tau, dl = d0) => {
    if (d >= dl * 0.65) return out;
    const vn = out[0] * n[0] + out[1] * n[1];
    return vn < 0 ? unit([out[0] - n[0] * vn * 1.2, out[1] - n[1] * vn * 1.2]) || tau : out;
  };
  const steps = Math.ceil((Math.abs(f.maxX - f.minX) + Math.abs(f.maxY - f.minY)) * 3 / h);
  for (let i = 0; i < steps; i++) {
    const here = F.at(pos[0], pos[1]), tn = t[0] * here.n[0] + t[1] * here.n[1];
    if (!touched && !free && contacts < 3 && here.d < reachAt(here) && (tn < -0.02 || here.d < dLoc(here) * 1.3)) {
      touched = true; met = true; contacts += 1; hugged = 0; room = room || here.room;
      const tp = [-here.n[1], here.n[0]], a = tp[0] * t[0] + tp[1] * t[1];
      // the side of the house it passes is given by its lane (``v.lat``: -1/1 of the split at the stagnation point), so the streams keep
      // their order – none crosses another in a recess facing the wind; along the wall that way and a little downwind
      if (v.lat) side = Math.sign(tp[0] * (v.lat * -t[1] + 0.6 * t[0]) + tp[1] * (v.lat * t[0] + 0.6 * t[1])) || 1;
      else side = Math.abs(a) > 0.2 ? Math.sign(a) : Math.sign((pos[0] - F.c[0]) * tp[0] + (pos[1] - F.c[1]) * tp[1]) || 1;
    }
    if (touched) {
      if (here.d < d0 * 1.5) hugged += h;
      // past the last edge on its side: from here the way along the wind stays clear of the house
      if (dir[0] * t[0] + dir[1] * t[1] > 0.2 && runsFree(pos, Math.max(minClear, Math.min(here.d, dLoc(here)) * 0.85))) {
        touched = false; free = true; release = pts.length - 1;
        if (env) { wsd = env.side(pos); hold = env.hold(pos, wsd); }
      }
      else if (hugged >= hugMax) break;
    }
    const state = { touched, side, free };
    const k1 = want(pos, state), mid = [pos[0] + k1[0] * h / 2, pos[1] + k1[1] * h / 2];
    let next = want(mid, state);
    // the bend per step is limited – no hard kink, whatever the field says
    const turn = Math.atan2(dir[0] * next[1] - dir[1] * next[0], dir[0] * next[0] + dir[1] * next[1]);
    // (past the last edge it turns into the wind calmly, in a wide arc)
    const bend = free ? maxTurn * 0.4 : maxTurn;
    if (i > 0 && Math.abs(turn) > bend) { const a = Math.sign(turn) * bend, cs = Math.cos(a), sn = Math.sin(a); next = [dir[0] * cs - dir[1] * sn, dir[0] * sn + dir[1] * cs]; }
    if (touched) next = guard(next, here.d, here.n, [-here.n[1] * side, here.n[0] * side], dLoc(here));
    // never through a wall: a stream that may not turn aside again (a deep notch used up its contacts) ends in front of it
    const ahead = [pos[0] + next[0] * h, pos[1] + next[1] * h];
    if ((!touched && !free && tn < 0 && here.d < Math.max(minClear, dLoc(here) * 0.6)) || (F.inside && (F.inside(ahead[0], ahead[1]) || F.crosses(pos, ahead)))) break;
    dir = next; pos = ahead; travelled += h;
    pts.push(pos);
    const inside = pos[0] >= f.minX && pos[0] <= f.maxX && pos[1] >= f.minY && pos[1] <= f.maxY;
    if (inside) seen = true;
    // out of the drawing: the stream ends – unless it is still beside the house (a tight drawing), then it may swing out a little
    const outBy = Math.max(f.minX - pos[0], pos[0] - f.maxX, f.minY - pos[1], pos[1] - f.maxY);
    if (seen && outBy > (touched || (free && after < R) ? R * 0.6 : margin)) break;
    if (!met && travelled >= limit) break;
    if (free) { after += h; if (after >= R * (2.5 + 1.5 * v.end)) break; }   // straight on with the wind to the edge of the drawing (or far beyond the house)
  }
  // a light smoothing of the traced line with every point kept clear of the facade (pushed out, smoothed again, pushed out)
  const smoothLine = () => { for (let i = 1; i < pts.length - 1; i++) pts[i] = [(pts[i - 1][0] + 2 * pts[i][0] + pts[i + 1][0]) / 4, (pts[i - 1][1] + 2 * pts[i][1] + pts[i + 1][1]) / 4]; };
  const keepOut = () => { for (const q of pts) { const at = F.at(q[0], q[1]), lim = Math.max(minClear, dLoc(at) * 0.6); if (at.d < lim) { q[0] += at.n[0] * (lim - at.d); q[1] += at.n[1] * (lim - at.d); } } };
  for (let round = 0; round < 6; round++) { smoothLine(); smoothLine(); keepOut(); }
  const keep = Math.max(1, Math.ceil(pts.length / 160));
  let line = [];
  for (let i = 0; i < pts.length; i += keep) line.push(pts[i]);
  if (line[line.length - 1] !== pts[pts.length - 1]) line.push(pts[pts.length - 1]);
  // smoothing and pushing out must not carry a point across a thin wing: the line ends before the first one that would
  if (F.inside) {
    const cut = line.findIndex((q, i) => F.inside(q[0], q[1]) || (i > 0 && F.crosses(line[i - 1], q)));
    if (cut >= 0) line = line.slice(0, cut);
  }
  const at = release < 0 ? -1 : Math.floor(release / keep);
  return { points: line, clear: line.map(q => F.at(q[0], q[1]).d), met, room, side, release: at < line.length - 1 ? at : -1 };
}

// 0.26.7.2: the decorative streams around the house – each the same gust from the edge of the drawing past the house: it turns
// before the wall, follows the real outside contour at its own distance, winds around the corners and runs on with the wind past
// the last edge on its side, closing in towards the wake behind the house (envelope). Pure; the card keeps the result until the
// house, the wind or the drawing really change.
// ``variety`` (freshairiq-house-motion.js streamVariety) gives each its own lane, length, distance and way around the house (an
// entry's ``clear`` replaces ``minClear`` for that way, ``gust`` marks a storm gust's way); without it ``count`` streams are spread
// evenly. Each stream also carries its lane, its side (-1/1), its distance from the split (``y``) and where it let go (``release``).
// ``minClear`` (plan units): the least distance any point of a stream keeps from the outside walls – the half width of the widest
// ribbon drawn on it with its margin (the card passes it from its stroke widths and scale)
export function facadeStreams({ rooms, fromDeg, northDeg, G, count = 7, frame = null, variety = null, field = null, minClear = 0 }) {
  if (fromDeg == null || !rooms.length) return [];
  const t = G.bearingVector((fromDeg + 180) % 360, northDeg), p = [-t[1], t[0]];
  const F = field || facadeField(rooms, G), c = F.c, R = F.R;
  const f = frame || { minX: F.box.minX - R * 0.3, minY: F.box.minY - R * 0.3, maxX: F.box.maxX + R * 0.3, maxY: F.box.maxY + R * 0.3 };
  // the silhouette the wind sees: a stream from further out passes the house further out, as in a flow around a body (the streams
  // keep their order and do not bundle on the facade); its own ``gap`` varies that distance a little
  let latMin = Infinity, latMax = -Infinity;
  for (const s of F.segs) for (const q of [[s.ax, s.ay], [s.ax + s.tx * s.len, s.ay + s.ty * s.len]]) { const l = (q[0] - c[0]) * p[0] + (q[1] - c[1]) * p[1]; latMin = Math.min(latMin, l); latMax = Math.max(latMax, l); }
  const half = Math.max((latMax - latMin) / 2, R * 0.1), mid = (latMin + latMax) / 2;
  // where the wind divides: the middle of the house's windward-most part (a corner in oblique wind, the middle of a facing wall)
  let lonMin = Infinity, sLo = Infinity, sHi = -Infinity;
  const ends = F.segs.flatMap(s => [[s.ax, s.ay], [s.ax + s.tx * s.len, s.ay + s.ty * s.len]]);
  for (const q of ends) lonMin = Math.min(lonMin, (q[0] - c[0]) * t[0] + (q[1] - c[1]) * t[1]);
  for (const q of ends) if ((q[0] - c[0]) * t[0] + (q[1] - c[1]) * t[1] < lonMin + R * 0.06) { const l = (q[0] - c[0]) * p[0] + (q[1] - c[1]) * p[1]; sLo = Math.min(sLo, l); sHi = Math.max(sHi, l); }
  const split = (sLo + sHi) / 2;
  const env = envelope(F, t, p, mid);
  const total = variety ? variety.length : count;
  const lanes = [];
  for (let i = 0; i < total; i++) {
    const v = variety ? variety[i] : { lane: total > 1 ? -1 + (2 * i) / (total - 1) : 0, start: 0, end: 1, gap: 0.5, hug: 0.5, release: 0.5 };
    // the distance it keeps grows with how far out it comes on its side (from the middle of the silhouette – the streams of one side
    // lie in order around the house; one beside the silhouette passes it further out, as in a flow around a body)
    const lat = v.lane * R * 0.98, y = Math.abs(lat - split), side = lat < split ? -1 : 1, ys = side * (lat - mid);
    // (never nearer than the widest ribbon allows – before the spacing below, so two ways never share that least distance)
    lanes.push({ i, v, lat, y, side, d0: Math.max(R * (0.07 + 0.02 * v.gap) + 0.55 * Math.max(0, (ys + Math.sqrt(ys * ys + 4 * half * half)) / 2 - half), (v.clear ?? minClear) * 1.15) });
  }
  // neighbours of one side never closer than 3.5 % of the half diagonal
  for (const sd of [-1, 1]) for (const gust of [false, true]) {
    const own = lanes.filter(l => l.side === sd && !!l.v.gust === gust).sort((a, b) => a.y - b.y);
    for (let k = 1; k < own.length; k++) own[k].d0 = Math.max(own[k].d0, own[k - 1].d0 + R * 0.035);
  }
  // traced from the split outwards; a way that would cross one already laid moves outwards (a larger distance of its own) and is
  // traced again – it is never cut at the facade
  const out = [];
  const crossing = (pts, laid) => {
    const box = boxOf(pts);
    for (const q of laid) {
      const qb = boxOf(q.points);
      if (box[2] < qb[0] || qb[2] < box[0] || box[3] < qb[1] || qb[3] < box[1]) continue;
      if (firstCrossing(pts, q.points) >= 0) return true;
      // (a way lying on another one counts as well)
      for (let k = 0; k < pts.length; k += 2) if (nearest(pts[k], [q], R * 0.01) < R * 0.01) return true;
    }
    return false;
  };
  for (const { i, v, lat: lane, y, side, d0 } of lanes.slice().sort((a, b) => a.y - b.y)) {
    let lat = lane, base = add(c, mul(p, lat)), span = clipLine(base, t, f);  // each streak starts at the edge of the drawing
    if (!span) continue;
    // a drawing so tight that a stream starts beside the house (past its windward-most point): it starts where it would pass the
    // house, displaced as if it had come from further upwind – outside the streams nearer the split
    if (span[0] > lonMin) {
      const out2 = side > 0 ? Math.max(lat, latMax + d0) : Math.min(lat, latMin - d0);
      if (out2 !== lat) { const b2 = add(c, mul(p, out2)), s2 = clipLine(b2, t, f); if (s2) { lat = out2; base = b2; span = s2; } }
    }
    const spanLen = span[1] - span[0];
    const S = add(base, mul(t, span[0] + (variety ? v.start * spanLen * 0.2 : 0)));   // its own start: never all at the same edge
    const mc = v.clear ?? minClear;
    let s = null;
    for (let k = 0; k < 7; k++) {
      s = traceStream(F, S, t, f, { ...v, lat: side }, spanLen, Math.max(d0 + R * 0.05 * k, mc * 1.15), mc, env);
      if (!crossing(s.points, out)) break;
    }
    if (s.points.length < 2) continue;
    out.push({ kind: s.met ? "deflect" : "pass", points: s.points, clear: s.clear, curve: null, room: s.room, variety: variety ? i : undefined, lane: lat, y, side, release: s.release });
  }
  out.sort((a, b) => (a.variety ?? 0) - (b.variety ?? 0));
  return out;
}

// The house's outline across the wind, seen from the wake's middle line (``mid``): on each side how far it reaches out at a point
// along the wind, its steps eased to a slope of at most WAKE_SLOPE, and behind the house no less than (1 - WAKE_CLOSE) of its
// widest reach. A released stream keeps its distance to this outline, so it glides down a step of the facade and closes in towards
// the wake behind the house in a wide, calm arc – the streams of a side keep their order, those of the two sides stay apart.
const WAKE_SLOPE = 0.5, WAKE_CLOSE = 0.55;
function envelope(F, t, p, mid) {
  const c = F.c, lonOf = q => q[0] * t[0] + q[1] * t[1], step = F.R / 30;
  const pts = [];
  for (const g of F.segs) for (let k = 0, n = Math.max(1, Math.ceil(g.len / step)); k <= n; k++) {
    const q = [g.ax + g.tx * g.len * k / n, g.ay + g.ty * g.len * k / n];
    pts.push([lonOf(q), (q[0] - c[0]) * p[0] + (q[1] - c[1]) * p[1] - mid]);
  }
  // on a grid along the wind (eased both ways, a step's margin on top), looked up per traced step
  const dx = F.R / 60, lo = Math.min(...pts.map(q => q[0])) - F.R * 2, n = Math.ceil((Math.max(...pts.map(q => q[0])) + F.R * 2 - lo) / dx) + 1;
  const grid = {}, floor = {};
  for (const sd of [-1, 1]) {
    const e = new Float64Array(n).fill(-Infinity);
    for (const q of pts) { const i = Math.round((q[0] - lo) / dx); e[i] = Math.max(e[i], sd * q[1]); }
    for (let i = 1; i < n; i++) e[i] = Math.max(e[i], e[i - 1] - WAKE_SLOPE * dx);
    for (let i = n - 2; i >= 0; i--) e[i] = Math.max(e[i], e[i + 1] - WAKE_SLOPE * dx);
    floor[sd] = (1 - WAKE_CLOSE) * Math.max(0, ...pts.map(q => sd * q[1]));
    grid[sd] = e.map(x => Math.max(x + WAKE_SLOPE * dx, floor[sd]));
  }
  const at = (lon, sd) => {
    const x = (lon - lo) / dx, i = Math.floor(x);
    if (i < 0 || i >= n - 1) return floor[sd];
    return grid[sd][i] + (grid[sd][i + 1] - grid[sd][i]) * (x - i);
  };
  return {
    // the released stream's distance to the outline where it lets go
    hold: (q, sd) => Math.max(sd * ((q[0] - c[0]) * p[0] + (q[1] - c[1]) * p[1] - mid) - at(lonOf(q), sd), 0),
    // the way along the wind that keeps that distance, turning by at most WAKE_SLOPE across the wind
    steer: (q, sd, hold) => {
      const l = (q[0] - c[0]) * p[0] + (q[1] - c[1]) * p[1] - mid, k = Math.max(-WAKE_SLOPE, Math.min(WAKE_SLOPE, (sd * (at(lonOf(q), sd) + hold) - l) * 3 / F.R));
      return unit([t[0] + p[0] * k, t[1] + p[1] * k]) || t;
    },
    side: q => Math.sign((q[0] - c[0]) * p[0] + (q[1] - c[1]) * p[1] - mid) || 1,
  };
}

// 0.26.7.2: the outer ways of the wind ribbons and the storm gusts, in one order around the house (facadeStreams: no way crosses
// another, each runs on with the wind past the house and closes in towards the wake behind it). Ribbons: every point keeps its
// swing within half the way to the next ribbon (``near``) and within the wall's distance (``clear``), and the swing calms down
// behind the house (``damp``). Gusts run on the ribbons' ways (``gusts``: their variety – its length is their number): two on
// neighbouring ribbons of one side join behind the house – the outer one is led onto the inner one's way in the run-out until the
// two touch and run on as one (``merge`` on the outer one: the gust it joins; ``fade`` on both: the stroke's opacity along the
// wind, so the two pictures cross-fade into one only on the shared stretch); a third runs on the other side. ``join``: about two
// stroke widths of a gust. ``curls``: where an edge ribbon lets go behind the house, the short open curl it may roll into (clear of
// the house by ``need`` all the time it drifts).
export function outerLanes({ rooms, fromDeg, northDeg, G, frame = null, variety, gusts = null, minClear = 0, gustClear = 0, join = 0, need = 0, field = null }) {
  if (fromDeg == null || !rooms.length) return { streams: [], gusts: [], curls: [] };
  const F = field || facadeField(rooms, G), R = F.R, t = G.bearingVector((fromDeg + 180) % 360, northDeg);
  const streams = untangle(facadeStreams({ rooms, fromDeg, northDeg, G, frame, variety, field: F, minClear }));
  for (const s of streams) {
    const others = streams.filter(o => o !== s);
    // (a neighbour further than twice the wall's distance, or than 0.6 of the half diagonal, never limits a swing)
    // ``near``: half the way to the next ribbon – the visible line of each ribbon swings within it, so two never cross; the broad,
    // nearly clear air mass around it only keeps its own half width from the walls (``clear``)
    s.near = s.points.map(q => nearest(q, others, R * 0.6) / 2);
  }
  let rear = -Infinity;
  for (const g of F.segs) rear = Math.max(rear, g.ax * t[0] + g.ay * t[1], (g.ax + g.tx * g.len) * t[0] + (g.ay + g.ty * g.len) * t[1]);
  // the swing calms down behind the house (not along its sides)
  for (const s of streams) s.damp = s.points.map(q => 1 - 0.45 * smoothstep((q[0] * t[0] + q[1] * t[1] - rear) / (R * 1.2)));
  return { streams, gusts: gustWays(streams, (gusts || []).length, join, R, t, rear, frame), curls: leeCurls(streams, F, t, need) };
}
const arcs = pts => pts.reduce((acc, q, k) => { acc.push(k ? acc[k - 1] + Math.hypot(q[0] - pts[k - 1][0], q[1] - pts[k - 1][1]) : 0); return acc; }, []);
function segPoint(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy, u = l2 > 1e-12 ? Math.min(Math.max(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2, 0), 1) : 0;
  return [a[0] + dx * u, a[1] + dy * u];
}
// the distance from p to the nearest of the other ways (a way whose box lies further away than the nearest so far is skipped)
const BOXES = new WeakMap();
const boxOf = pts => {
  let b = BOXES.get(pts);
  if (!b) { b = pts.reduce((x, q) => [Math.min(x[0], q[0]), Math.min(x[1], q[1]), Math.max(x[2], q[0]), Math.max(x[3], q[1])], [Infinity, Infinity, -Infinity, -Infinity]); BOXES.set(pts, b); }
  return b;
};
function nearest(p, others, limit = Infinity) {
  let m = limit;
  for (const o of others) {
    const box = boxOf(o.points);
    if (Math.max(box[0] - p[0], p[0] - box[2], box[1] - p[1], p[1] - box[3]) > m) continue;
    for (let k = 0; k < o.points.length - 1; k++) {
      const a = o.points[k], b = o.points[k + 1];
      if (Math.min(a[0], b[0]) - m > p[0] || Math.max(a[0], b[0]) + m < p[0] || Math.min(a[1], b[1]) - m > p[1] || Math.max(a[1], b[1]) + m < p[1]) continue;
      const q = segPoint(p, a, b);
      m = Math.min(m, Math.hypot(p[0] - q[0], p[1] - q[1]));
    }
  }
  return m;
}
// the first segment of A that crosses B, or -1
function firstCrossing(A, B) {
  const o = (u, v, w) => Math.sign((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]));
  for (let a = 0; a < A.length - 1; a++) {
    const P = A[a], Q = A[a + 1], x0 = Math.min(P[0], Q[0]), x1 = Math.max(P[0], Q[0]), y0 = Math.min(P[1], Q[1]), y1 = Math.max(P[1], Q[1]);
    for (let b = 0; b < B.length - 1; b++) {
      const C = B[b], D = B[b + 1];
      if (Math.max(C[0], D[0]) < x0 || Math.min(C[0], D[0]) > x1 || Math.max(C[1], D[1]) < y0 || Math.min(C[1], D[1]) > y1) continue;
      if (o(P, Q, C) * o(P, Q, D) < 0 && o(C, D, P) * o(C, D, Q) < 0) return a;
    }
  }
  return -1;
}
// order kept: a way that would cross one nearer the split (rare, at a step of the facade) ends before it
function untangle(list) {
  const o = (u, v, w) => Math.sign((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]));
  const kept = [];
  const apart = (A, B, C, D) => Math.max(A[0], B[0]) < Math.min(C[0], D[0]) || Math.max(C[0], D[0]) < Math.min(A[0], B[0]) || Math.max(A[1], B[1]) < Math.min(C[1], D[1]) || Math.max(C[1], D[1]) < Math.min(A[1], B[1]);
  for (const s of list.slice().sort((a, b) => a.y - b.y)) {
    let cut = s.points.length;
    const sb = boxOf(s.points);
    for (const q of kept) {
      const qb = boxOf(q.points);
      if (sb[2] < qb[0] || qb[2] < sb[0] || sb[3] < qb[1] || qb[3] < sb[1]) continue;
      for (let a = 0; a < Math.min(cut, s.points.length) - 1; a++) for (let b = 0; b < q.points.length - 1; b++) {
        const A = s.points[a], B = s.points[a + 1], C = q.points[b], D = q.points[b + 1];
        if (!apart(A, B, C, D) && o(A, B, C) * o(A, B, D) < 0 && o(C, D, A) * o(C, D, B) < 0) { cut = Math.min(cut, a); break; }
      }
    }
    if (cut < s.points.length) {
      if (cut < 3) continue;
      Object.assign(s, { points: s.points.slice(0, cut), clear: s.clear.slice(0, cut), release: s.release < cut - 1 ? s.release : -1 });
    }
    kept.push(s);
  }
  return list.filter(s => kept.includes(s));
}
// The gusts' ways on the ribbons. A pair: two neighbouring ribbons of one side that let go of the house, apart in the run-out by
// at least two strokes where there are such (else the widest apart), meeting where the drawing (``frame``) shows it. The outer one runs on its own ribbon past the house, then
// (blend ``B``, along the wind) onto the inner one's way, meeting it behind the house: the two strokes touch, lie on each other at the meeting point
// and share the last stretch (``O``), where the outer one fades out and the inner one takes over its full strength – one gust runs on
// with the wind. Both ways start equally far before the meeting point (the shorter is drawn out upwind), so they arrive together.
function gustWays(streams, count, join, R, t, rear = -Infinity, frame = null) {
  if (!(count > 0)) return [];
  const lon = q => q[0] * t[0] + q[1] * t[1];
  const width = join / 2.2;   // a gust's stroke
  const own = sd => streams.filter(s => s.side === sd && s.kind === "deflect" && s.release >= 0).sort((a, b) => a.y - b.y);
  const runOut = s => s.points.slice(s.release);
  // a ribbon's point in its run-out at a given distance along the wind (on its own points; beyond its end straight on)
  const along = s => x => {
    const P = s.points;
    for (let i = P.length - 2; i >= Math.max(s.release, 0); i--) {   // from the far end: the run-out first
      const a = lon(P[i]), b = lon(P[i + 1]);
      if (a <= x && x <= b) { const u = b > a ? (x - a) / (b - a) : 0; return [P[i][0] + (P[i + 1][0] - P[i][0]) * u, P[i][1] + (P[i + 1][1] - P[i][1]) * u]; }
    }
    const r = P[P.length - 1], l0 = lon(r);
    return [r[0] + t[0] * (x - l0), r[1] + t[1] * (x - l0)];
  };
  const copy = s => ({ kind: s.kind, points: s.points.map(q => [q[0], q[1]]), side: s.side, y: s.y, lane: s.lane, release: s.release, variety: s.variety });
  // where a pair may begin to join: both have turned into the wind; how far apart they run there and how much room is left
  const plan = (lead, fol) => {
    const lonB0 = Math.max(lon(lead.points[lead.release]), lon(fol.points[fol.release])) + R * 0.3, lonEnd = lon(lead.points[lead.points.length - 1]);
    const a = along(fol)(lonB0), b = along(lead)(lonB0);
    // (where they would meet: well inside the drawing, so the join is seen – see join2 for the same place)
    const room = lonEnd - lonB0, m = along(lead)(Math.min(Math.max(lonB0 + Math.min(R * 0.6, room * 0.6), rear + R * 0.1), lonEnd - Math.min(R * 0.35, room * 0.35))), e = R * 0.1;
    const seen = !frame || (m[0] > frame.minX + e && m[0] < frame.maxX - e && m[1] > frame.minY + e && m[1] < frame.maxY - e);
    return { lead, fol, lonB0, lonEnd, room, gap: Math.hypot(a[0] - b[0], a[1] - b[1]), behind: lonEnd - Math.max(lonB0, rear), seen };
  };
  const pairs = [];
  for (const sd of [-1, 1]) {
    const o = own(sd);
    for (let k = 1; k < o.length; k++) {
      const c = plan(o[k - 1], o[k]);
      if (!(c.room > R * 0.3) || c.gap < 0.75 * width) continue;   // two gusts that already run on each other do not join
      // clearly two (two strokes apart), room to join behind the house, then the closest of those
      const score = (c.gap >= 2 * width ? 20 : 0) + (c.seen ? 15 : 0) + (c.behind > R * 0.5 ? 10 : 0) - c.gap;
      pairs.push({ ...c, score });
    }
  }
  pairs.sort((a, b) => b.score - a.score);
  // one pair joins: the best whose joined way crosses no ribbon
  const join2 = pair => {
    const { lead, fol, lonB0, lonEnd, room, gap } = pair;
    // a tight drawing (a narrow card) leaves the ribbons little room: the two gusts are drawn narrower there, so they run as two until
    // they touch (``width`` on both, plan units)
    const w = Math.min(width, gap / 1.6);
    // the blend in the run-out of both, the meeting point behind the house where the drawing has room for it (``rear``: how
    // far the house reaches along the wind) and on a point of the leading ribbon, the shared stretch before that ribbon ends
    const B = Math.min(R * 0.6, room * 0.6), O = Math.min(R * 0.35, room * 0.35);
    const want = Math.min(Math.max(lonB0 + B, rear + R * 0.1), lonEnd - O);
    const run = lead.points.slice(lead.release), fits = run.filter(q => lon(q) >= lonB0 + B && lon(q) <= lonEnd - O * 0.5);
    const meet = (fits.length ? fits : run).reduce((m, q) => (Math.abs(lon(q) - want) < Math.abs(lon(m) - want) ? q : m)), lonM = lon(meet);
    const L = copy(lead), Fw = copy(fol), onLead = along(lead), onFol = along(fol);
    {
      // its own way up to the blend, then towards the leading way point by point along the wind, then the shared stretch
      // (it leaves its ribbon at one of the ribbon's own points: the two lines only touch there)
      const pts = fol.points.filter(q => lon(q) <= lonM - B), n = Math.max(8, Math.ceil(B / (R / 30)));
      // (its distance to the leading ribbon only ever shrinks, also where the two ribbons close in towards the wake unequally)
      const foot = q => { let best = null, m = Infinity; for (let i = 0; i < lead.points.length - 1; i++) { const f = segPoint(q, lead.points[i], lead.points[i + 1]), d = Math.hypot(q[0] - f[0], q[1] - f[1]); if (d < m) { m = d; best = f; } } return [best, m]; };
      let gapNow = foot(pts.length ? pts[pts.length - 1] : onFol(lonM - B))[1];
      const gaps = [[lonM - B, gapNow]];
      for (let k = 1; k <= n; k++) {
        const x = lonM - B + B * k / n, u = smoothstep(k / n), a = onFol(x), [b, l] = foot(a), ab = sub(a, b);
        gapNow = k === n ? 0 : Math.min(gapNow, l * (1 - u));
        gaps.push([x, gapNow]);
        pts.push(k === n ? meet : l > 1e-9 ? [b[0] + ab[0] / l * gapNow, b[1] + ab[1] / l * gapNow] : b);
      }
      const gapAt = x => { for (let k = 1; k < gaps.length; k++) if (x <= gaps[k][0]) { const [x0, g0] = gaps[k - 1], [x1, g1] = gaps[k]; return g0 + (g1 - g0) * Math.min(Math.max((x - x0) / (x1 - x0), 0), 1); } return 0; };
      // the shared stretch: the leading way's own points (one line, not two lying almost on each other)
      for (const q of lead.points.slice(lead.release)) if (lon(q) > lonM + 1e-9 && lon(q) <= lonM + O) pts.push(q);
      // equally far before the meeting point on both ways
      const toMeet = P => {
        const A = arcs(P);
        for (let i = 1; i < P.length; i++) {
          const a = lon(P[i - 1]), b = lon(P[i]);
          if (b >= lonM - 1e-9 && a < lonM && Math.min(a, b) > lonB0 - R) return A[i - 1] + (A[i] - A[i - 1]) * (b > a ? (lonM - a) / (b - a) : 1);
        }
        return A[A.length - 1];
      };
      // the shorter is drawn out upwind (along the wind's line); where that would cross a ribbon, the longer starts later instead
      const mF = toMeet(pts), mL = toMeet(L.points), up = [-t[0], -t[1]];
      const free = (P, by) => { const e = [P[0], [P[0][0] + up[0] * by, P[0][1] + up[1] * by]]; return !streams.some(o => firstCrossing(e, o.points) >= 0); };
      if (mF < mL) { if (free(pts, mL - mF)) Fw.points = extend(pts, mL - mF, up); else { Fw.points = pts; L.points = cutStart(L.points, mL - mF); } }
      else if (mL < mF) { if (free(L.points, mF - mL)) { Fw.points = pts; L.points = extend(L.points, mF - mL, up); } else Fw.points = cutStart(pts, mF - mL); }
      else Fw.points = pts;
      // the strokes' opacity along the wind: full while apart, both at half where they lie on each other at the meeting point, then
      // the leading one back to full and the joining one out – the sum stays that of one gust
      const from = onLead(lonM - B), to = onLead(lonM + O), span = B + O, stopsL = [], stopsF = [];
      const k = gaps.findIndex(([, g]) => g <= w), contact = k <= 0 ? lonM - B : gaps[k - 1][0] + (gaps[k][0] - gaps[k - 1][0]) * (gaps[k - 1][1] - w) / Math.max(gaps[k - 1][1] - gaps[k][1], 1e-12);
      // full up to the point where they touch (a stop of its own there), then in small steps
      const xs = [lonM - B, contact, ...Array.from({ length: 20 }, (_, k) => contact + (lonM + O - contact) * (k + 1) / 20)];
      for (const x of xs) {
        const off = r3((x - (lonM - B)) / span);
        if (x <= lonM) { const f = 1 - 0.5 * (1 - Math.min(gapAt(x) / w, 1)); stopsL.push([off, r3(f)]); stopsF.push([off, r3(f)]); }
        else { const u = smoothstep((x - lonM) / O); stopsL.push([off, r3(0.5 + 0.5 * u)]); stopsF.push([off, r3(0.5 - 0.5 * u)]); }
      }
      L.fade = { from, to, stops: stopsL };
      Fw.fade = { from, to, stops: stopsF };
      if (w < width) L.width = Fw.width = w;
      Fw.merge = { into: 0, at: Math.max(mF, mL), blend: B, overlap: O, contact, lon: lonM };
      if (streams.some(o => o !== lead && o !== fol && (firstCrossing(Fw.points, o.points) >= 0 || firstCrossing(L.points, o.points) >= 0))) return null;
      return [L, Fw];
    }
  };
  const ways = [];
  let pair = null;
  for (const c of count >= 2 ? pairs : []) { const j = join2(c); if (j) { ways.push(...j); pair = c; break; } }
  // single gusts: the innermost ribbon of each side that let go, then any other
  const used = new Set(ways.length ? [pair.lead, pair.fol] : []);
  const rest = [...own(pair ? -pair.lead.side : -1).slice(0, 1), ...own(pair ? pair.lead.side : 1).slice(0, 1), ...streams.filter(s => s.kind === "deflect"), ...streams];
  for (const s of rest) { if (ways.length >= count) break; if (!used.has(s)) { used.add(s); ways.push(copy(s)); } }
  return ways;
}
// a way drawn out upwind (along ``dir``, else along its first stretch)
function extend(pts, by, dir = null) {
  if (!(by > 1e-9)) return pts;
  const d = dir ? [-dir[0], -dir[1]] : unit(sub(pts[1], pts[0])) || [1, 0];
  return [[pts[0][0] - d[0] * by, pts[0][1] - d[1] * by], ...pts];
}
function cutStart(pts, len) {
  if (!(len > 1e-9)) return pts;
  const arc = arcs(pts), k = arc.findIndex(a => a >= len);
  if (k <= 0) return pts;
  const u = (len - arc[k - 1]) / Math.max(arc[k] - arc[k - 1], 1e-9), a = pts[k - 1], b = pts[k];
  return [[a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u], ...pts.slice(k)];
}
// The curl of an edge ribbon in the lee: from a point of the innermost ribbon of a side shortly after it let go of the house, an
// open curl of about three quarters of a turn towards the wake (its radius shrinking), placed where it stays ``need`` clear of
// the house all the time it drifts downwind (``drift``).
function leeCurls(streams, F, t, need) {
  const out = [], R = F.R, drift = R * 0.45;
  let lonMax = -Infinity;
  for (const g of F.segs) lonMax = Math.max(lonMax, g.ax * t[0] + g.ay * t[1], (g.ax + g.tx * g.len) * t[0] + (g.ay + g.ty * g.len) * t[1]);
  for (const sd of [-1, 1]) {
    const s = streams.filter(x => x.side === sd && x.kind === "deflect" && x.release >= 0).sort((a, b) => a.y - b.y)[0];
    if (!s) continue;
    const P = s.points, rel = P[s.release];
    const turn = Math.sign(t[0] * (F.c[1] - rel[1]) - t[1] * (F.c[0] - rel[0])) || -sd;
    let found = null;
    // only behind the house: from the point where the ribbon has passed its rear
    for (const ahead of [0.05, 0.25, 0.5, 0.8]) {
      const k = P.findIndex((q, i) => i >= s.release && q[0] * t[0] + q[1] * t[1] >= lonMax + ahead * R);
      if (k < 0 || k >= P.length - 1) break;
      for (const size of [1, 0.75, 0.55]) {
        const r0 = R * 0.13 * size, n = 30, total = 1.45 * Math.PI, dphi = total / n;
        let hd = unit(sub(P[k + 1], P[k])) || t, pos = P[k];
        const pts = [pos];
        for (let j = 1; j <= n; j++) {
          const r = r0 * (1 - 0.5 * j / n), cs = Math.cos(turn * dphi), sn = Math.sin(turn * dphi);
          hd = [hd[0] * cs - hd[1] * sn, hd[0] * sn + hd[1] * cs];
          pos = [pos[0] + hd[0] * r * dphi, pos[1] + hd[1] * r * dphi];
          pts.push(pos);
        }
        const ok = [0, 0.5, 1].every(x => pts.every(q => { const a = q[0] + t[0] * drift * x, b = q[1] + t[1] * drift * x; return !F.inside(a, b) && F.at(a, b).d >= need; }));
        if (ok) { found = { points: pts, dir: [t[0], t[1]], drift, side: sd, from: k }; break; }
      }
      if (found) break;
    }
    if (found) out.push(found);
  }
  return out;
}
// The storm gusts' lanes from a streamVariety: two close ones on one side of the house (they bunch at its side and join), a single
// one on the other side; nearer the wall than the ribbons, each its own start.
export function gustVariety(base, seed = 1) {
  const sd = Math.round(Math.abs(seed)) % 2 ? 1 : -1, lanes = [sd * 0.3, sd * 0.5, -sd * 0.42];
  return base.map((v, i) => ({ ...v, lane: base.length === 1 ? sd * 0.4 : lanes[i % 3] + (v.lane - Math.round(v.lane)) * 0.03, gap: v.gap * 0.4,
    hug: 0.45 + 0.55 * v.hug, start: v.start * 0.5, end: 1 }));
}

// 0.26.7.2: the card's store of the outer ways (ribbons, gusts, curls) per floor: kept until the house, the wind direction (whole
// degrees), the plan's north, the drawing, the number of ribbons or gusts or the scale's distances change – a reading of the rooms
// reuses them – and their wave samples per ribbon.
export class FacadeCache {
  constructor(G) { this.G = G; this.kinds = {}; this.field = null; this.frames = new WeakMap(); }
  // makeVariety(): {streams, gusts} – the variety of the ribbons and of the gusts (built only when they have to be traced again)
  // distances (plan units: ``minClear`` of the ribbons, ``gustClear``, ``join``, ``need``, see outerLanes) are kept in steps of
  // 1/100 of the house, so a slightly different card width does not trace again
  outer({ layout, floorId, rooms, bearing, north, frame, count, seed, gusts = 0, minClear = 0, gustClear = 0, join = 0, need = 0 }, makeVariety) {
    const G = this.G, deg = ((Math.round(Number(bearing)) % 360) + 360) % 360, box = [frame.minX, frame.minY, frame.maxX, frame.maxY].map(G.round3).join(",");
    if (!this.field || this.field.layout !== layout || this.field.floorId !== floorId) this.field = { layout, floorId, field: facadeField(rooms, G) };
    const unitR = this.field.field.R / 100, q = x => Math.ceil((Number(x) || 0) / unitR) * unitR, d = [minClear, gustClear, join, need].map(q);
    const key = `${floorId}|${deg}|${north}|${box}|${count}|${seed}|${gusts}|${d.map(G.round3).join(",")}`, hit = this.kinds.outer;
    if (hit && hit.layout === layout && hit.key === key) return hit.lanes;
    const v = makeVariety();
    const lanes = outerLanes({ rooms, fromDeg: deg, northDeg: north, G, frame, variety: v.streams, gusts: gusts ? v.gusts : null, field: this.field.field,
      minClear: d[0], gustClear: d[1], join: d[2], need: d[3] });
    this.kinds.outer = { layout, key, lanes };
    return lanes;
  }
  // ``speed``: {key, of(point)} – the relative speed of the air along the stream from the 2D flow model (computed once per stream)
  frame(stream, step, maxPoints, speed = null) {
    const key = `${this.G.round3(step)}|${maxPoints}|${speed ? speed.key : ""}`, hit = this.frames.get(stream);
    if (hit && hit.key === key) return hit.frame;
    const line = streamLine(stream);
    const fits = a => (a && a.length === line.length ? a : null);
    const frame = waveFrame(line, step, stream.clear || null, maxPoints, speed ? line.map(p => speed.of(p)) : null, fits(stream.damp), fits(stream.near));
    this.frames.set(stream, { key, frame });
    return frame;
  }
}

/**
 * Schematic wind streams around the drawn floor.
 * rooms: [{id, polygon}], openings: [{id, room_id, edge, offset, width_m, state, pending}], G: geometry module.
 * Returns [{kind: "pass"|"deflect"|"inflow", points:[[x,y]...], curve:{from,ctrl,to}|null, opening, room}] in plan coordinates.
 * The decorative streams follow the outside walls (facadeStreams; ``decorative`` passes them when already traced). Separately,
 * every open, confirmed outside opening the wind presses on (published facade pressure ≥ INLET_PRESSURE) gets its own inflow:
 * from the upwind edge to the window, into the room and – only along a published directed air path – on and out (Hotfix (9) F02/F03).
 */
export function windStreams({ rooms, openings, fromDeg, northDeg, G, count = 7, paths = [], frame = null, variety = null, field = null, decorative = null }) {  // 0.26.6.0(7): 7 streams, no crowding
  if (fromDeg == null || !rooms.length) return [];
  const streams = (decorative || facadeStreams({ rooms, fromDeg, northDeg, G, count, frame, variety, field })).slice();
  const t = G.bearingVector((fromDeg + 180) % 360, northDeg); // direction the air moves to
  const box = G.bbox(rooms.map(r => r.polygon));
  const R = Math.hypot(box.maxX - box.minX, box.maxY - box.minY) / 2 || 1;
  const f = frame || { minX: box.minX - R * 0.3, minY: box.minY - R * 0.3, maxX: box.maxX + R * 0.3, maxY: box.maxY + R * 0.3 };
  // Hotfix (9) F02/F03: the air enters at every open, confirmed outside opening the wind presses on – taken from the
  // published opening state and facade pressure (house_airflow: pressure ≥ INLET_PRESSURE), never from where a
  // decorative streak happens to cross the wall. It leaves the house only along a directed air path FreshAirIQ
  // published (cross ventilation); without one it stays in the room (no invented outlet).
  for (const o of openings) {
    const room = rooms.find(r => r.id === o.room_id);
    if (!room || o.target !== "outside" || !OPEN.has(o.state) || o.pending || !(o.edge >= 0 && o.edge < room.polygon.length)) continue;
    if (!(Number(o.pressure) >= INLET_PRESSURE)) continue;
    const pts = room.polygon, W = G.edgePoint(pts, o.edge, o.offset), n = G.outwardNormal(pts, o.edge);
    const back = clipLine(W, t, f), blocked = rooms.some(r => r.polygon.some((q, e) => { const h = rayHit(W, mul(t, -1), q, r.polygon[(e + 1) % r.polygon.length]); return h && h.s > 1e-3; }));
    // from the upwind edge of the drawing straight to the window; a window in a sheltered corner is reached along its normal
    const S = back && !blocked ? add(W, mul(t, back[0])) : add(W, mul(n, R * 0.45));
    const inside = [G.labelPoint(pts)];
    const onward = paths.find(x => x.from === o.id && x.direction === "directed" && Array.isArray(x.points) && x.points.length > 2);
    let exits = false;
    if (onward) { inside.length = 0; for (const pt of onward.points.slice(1)) inside.push(pt); exits = !!onward.exits; }   // the path starts at this window
    streams.push({ kind: "inflow", points: [S, W, ...inside], curve: null, opening: o.id, room: room.id, tilted: o.state === "tilted", exits });
  }
  return streams;
}
// The facade pressure from which an open outside opening counts as an inlet (house_airflow.INLET_PRESSURE).
export const INLET_PRESSURE = 0.3;

export const STYLE = `
:host{display:block}
ha-card{display:block;position:relative;overflow:hidden;padding:14px;border-radius:26px;color:${BRAND.white};
  background:radial-gradient(circle at 85% -10%,rgba(0,216,240,.28),transparent 45%),radial-gradient(circle at -10% 110%,rgba(57,224,122,.18),transparent 40%),linear-gradient(160deg,${BRAND.deep},${BRAND.night});
  border:3px solid ${BRAND.ink};box-shadow:0 0 0 2px rgba(0,216,240,.35),0 14px 34px rgba(0,0,0,.35);
  font-family:"Nunito","Baloo 2",ui-rounded,"SF Pro Rounded","Segoe UI",system-ui,sans-serif}
.hero{display:grid;gap:10px}
.brand{display:flex;align-items:center;gap:10px}
.brand svg{width:40px;height:40px;flex:none;filter:drop-shadow(0 0 8px rgba(0,216,240,.6))}
.title{font-size:20px;font-weight:900;letter-spacing:.2px;line-height:1.1}
.status{font-size:13px;opacity:.85}
.bubble{position:relative;display:flex;gap:10px;align-items:center;padding:10px 14px;border-radius:20px;background:${BRAND.white};color:${BRAND.ink};
  border:3px solid ${BRAND.ink};box-shadow:4px 4px 0 ${BRAND.ink};font-weight:800;font-size:15px}
.bubble:after{content:"";position:absolute;left:26px;bottom:-12px;border:9px solid transparent;border-top-color:${BRAND.ink};border-bottom:0}
.bubble .emo{font-size:26px}
.bubble small{display:block;font-weight:600;font-size:12px;opacity:.8}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:4px}
.kpi{padding:9px 11px;border-radius:18px;background:${BRAND.panel};border:3px solid ${BRAND.ink};box-shadow:4px 4px 0 ${BRAND.ink};display:flex;gap:8px;align-items:center}
.kpi .lbl{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:${BRAND.ice};opacity:.9}
.kpi .val{font-size:20px;font-weight:900;line-height:1.15}
.kpi .sub{font-size:12px;opacity:.85}
.kpi svg{width:46px;height:46px;flex:none}
.good{color:${BRAND.lime}} .bad{color:${BRAND.orange}}
.row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
button{font:inherit;font-weight:800;cursor:pointer;border-radius:999px;border:3px solid ${BRAND.ink};background:${BRAND.panel};color:${BRAND.white};
  padding:6px 14px;min-height:40px;box-shadow:3px 3px 0 ${BRAND.ink};transition:transform .08s}
button:active{transform:translate(2px,2px);box-shadow:1px 1px 0 ${BRAND.ink}}
button[aria-pressed="true"]{background:${BRAND.cyan};color:${BRAND.ink}}
button.small{min-height:34px;padding:4px 11px;font-size:13px}
.badge{display:inline-block;margin-left:6px;min-width:20px;padding:0 6px;border-radius:999px;background:${BRAND.orange};color:${BRAND.ink};font-size:12px;border:2px solid ${BRAND.ink}}
.notice{margin-top:8px;padding:7px 12px;border-radius:14px;font-size:13px;font-weight:700;background:rgba(0,216,240,.12);border:2px dashed rgba(0,216,240,.55)}
.notice.warn{background:rgba(255,159,67,.14);border-color:${BRAND.orange}}
.map{position:relative;margin-top:12px;border-radius:22px;border:3px solid ${BRAND.ink};box-shadow:5px 5px 0 ${BRAND.ink};overflow:hidden;
  background:linear-gradient(180deg,#0f4479,#072a4f);touch-action:pan-x pan-y pinch-zoom;overflow-x:auto;-webkit-overflow-scrolling:touch}
svg.plan{display:block;width:100%;max-width:100%;height:auto;max-height:78vh;margin:0 auto}
.room{cursor:pointer;stroke:transparent;stroke-linejoin:round}
.room:focus{outline:none;stroke:${BRAND.white}}
.room.sel{stroke:${BRAND.white}}
.t-act:not(.room){fill:${TONE_COLOR.act}} .t-run:not(.room){fill:${TONE_COLOR.run}} .t-close:not(.room){fill:${TONE_COLOR.close}} .t-wait:not(.room){fill:${TONE_COLOR.wait}}
.t-sensor:not(.room){fill:${TONE_COLOR.sensor}} .t-ok:not(.room){fill:${TONE_COLOR.ok}} .t-critical:not(.room){fill:${TONE_COLOR.critical}}
text{pointer-events:none;font-family:inherit}
.tag{pointer-events:none} .tag text{paint-order:stroke;stroke-linejoin:round}
.tag .n{font-weight:900} .tag .a{font-weight:800} .tag .c{font-weight:700}
.tag .pill{fill:rgba(2,16,36,.74);stroke:rgba(255,255,255,.22)} .tag .pill-t{fill:${BRAND.white};stroke:none;font-weight:800}
.tag .dot{fill:rgba(2,16,36,.74);stroke:rgba(255,255,255,.55)}
.rim{fill:none;pointer-events:none} .hatch{pointer-events:none}
@keyframes rimglow{0%,100%{stroke-opacity:.35}50%{stroke-opacity:.8}}
.rim.r-act,.rim.r-close,.rim.r-critical{animation:rimglow 3.2s ease-in-out infinite}
:host([data-paused]) .rim.r-act,:host([data-paused]) .rim.r-close,:host([data-paused]) .rim.r-critical,:host([data-still]) .rim.r-act,:host([data-still]) .rim.r-close,:host([data-still]) .rim.r-critical{animation:none}
@media (prefers-reduced-motion:reduce){.rim.r-act,.rim.r-close,.rim.r-critical{animation:none}}
.op{stroke-linecap:round;cursor:pointer}
.op.closed{stroke:${BRAND.white}} .op.tilted{stroke:${BRAND.sky}} .op.open{stroke:${BRAND.lime}} .op.open_unspecified{stroke:${BRAND.lime};stroke-dasharray:var(--dash)}
.op.unknown,.op.no_sensor{stroke:${BRAND.slate};stroke-dasharray:var(--dot)} .op.pending{stroke:${BRAND.orange}}
.wave{fill:none;stroke-linecap:round;stroke-linejoin:round}
.wave.mid{opacity:.26}.wave.hi{opacity:.16}.wave.lo{opacity:.07}  /* order 8: soft veils – the canvas threads carry the detail; the third strand is a broad, nearly clear air mass */
.wave.k-pass{opacity:.2}.wave.k-pass.hi{opacity:.12}.wave.k-pass.lo{opacity:.05}
/* order 9: the air layers follow the weather – softer and warmer in the sun, fuller in a storm */
svg[data-mood="sunny"] .wave.mid{opacity:.18}svg[data-mood="sunny"] .wave.hi{opacity:.12}svg[data-mood="sunny"] .wave{stroke:#fff6df}
svg[data-mood="storm"] .wave.mid{opacity:.36}svg[data-mood="storm"] .wave.hi{opacity:.24}svg[data-mood="storm"] .wave.lo{opacity:.11}
svg[data-mood="lively"] .wave.mid{opacity:.3}
.wave.k-inflow.mid{opacity:.24}.wave.k-inflow.tilted{opacity:.18}.wave.k-inflow.lo{opacity:.09}
.eddy{fill:none;stroke:#cfeeff;stroke-linecap:round}  /* 0.26.7.2: a soft eddy in the wake, its opacity set by the card's loop */
.flow{animation:flow var(--dur,2s) linear infinite}
@keyframes flow{to{stroke-dashoffset:calc(var(--dashlen) * -1)}}
@media (prefers-reduced-motion:reduce){.flow{animation:none}}
:host([data-paused]) .flow{animation-play-state:paused}
.splash{fill:none;stroke:${BRAND.white};stroke-linecap:round;opacity:.85}
.path{fill:none;stroke:${BRAND.lime};stroke-linecap:round;stroke-linejoin:round;cursor:pointer}
.path.low{stroke-dasharray:var(--dash)} .path.exhaust{stroke:${BRAND.orange}}
.conn{stroke:${BRAND.ice};stroke-dasharray:var(--dot);fill:none;opacity:.6}
.legend{font-size:12px;opacity:.8;margin-top:8px}
.floorhead{margin:12px 0 0;font-size:15px;font-weight:900}
.overview svg.plan{max-height:46vh}
dialog{border:none;padding:0;background:transparent;max-width:min(560px,94vw);width:100%;color:${BRAND.ink}}
dialog::backdrop{background:rgba(2,16,36,.55);backdrop-filter:blur(2px)}
.dlg{border-radius:26px;border:4px solid ${BRAND.ink};box-shadow:7px 7px 0 ${BRAND.ink};background:${BRAND.white};overflow:hidden;
  font-family:"Nunito","Baloo 2",ui-rounded,"SF Pro Rounded","Segoe UI",system-ui,sans-serif}
.dlg header{display:flex;align-items:center;gap:12px;padding:14px 16px;border-bottom:4px solid ${BRAND.ink}}
.dlg header .emo{font-size:36px}
.dlg h3{margin:0;font-size:21px;font-weight:900}
.dlg header .act{font-size:15px;font-weight:800}
.dlg .body{padding:14px 16px;display:grid;gap:12px;max-height:70vh;overflow:auto}
.dlg .why{padding:10px 12px;border-radius:16px;background:#e8f8ff;border:3px solid ${BRAND.ink};font-weight:700}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px}
.tile{padding:8px 10px;border-radius:14px;border:3px solid ${BRAND.ink};background:#f1fbff}
.tile .l{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;color:#24435f}
.tile .v{font-size:18px;font-weight:900}
.tile .s{font-size:12px;color:#24435f}
.dlg ul{margin:0;padding-left:18px}
.dlg .foot{display:flex;justify-content:flex-end;padding:0 16px 14px}
.dlg button{background:${BRAND.cyan};color:${BRAND.ink}}
.hint{font-size:12px;color:#24435f}
/* 0.26.5.5: plan first – bar with wind, layers and menu below the plan; walls, opening symbols, logical links */
/* 0.26.6: the plan fills the card; the menu button lies on it at the bottom right, warnings at the top left */
ha-card.plan-first{padding:0}
.plan-first .stage{position:relative}
.plan-first .map{margin:0;border:0;border-radius:0;box-shadow:none}
.plan-first .floorhead{margin:0;padding:10px 14px 4px;background:#0b4580}
/* 0.26.6.0(7): a slim bar above the plan – notes left, local weather right */
.topbar{display:flex;flex-wrap:wrap;align-items:flex-start;gap:8px;padding:10px 10px 4px;background:#0b4580}
/* 0.26.7.0 UI hotfix: one continuous animated surface – no solid bars. The drawing (sky, weather, wind) reaches under the bars,
   which lie over it; only their controls take clicks and carry their own semi-transparent, high-contrast backgrounds */
.plan-first .stage{background:linear-gradient(180deg,var(--sky-top,#0f4479),var(--sky-bottom,#072a4f))}
.plan-first .stage.over>.topbar,.plan-first .stage.over>.mapbar{position:absolute;left:0;right:0;z-index:2;background:transparent;pointer-events:none}
.plan-first .stage.over>.topbar{top:0} .plan-first .stage.over>.mapbar{bottom:0}
.plan-first .stage.over svg.plan{max-height:calc(78vh + var(--bar-top,0px) + var(--bar-bottom,0px))}
.plan-first .stage.over>.topbar>*,.plan-first .stage.over>.mapbar>*{pointer-events:auto}
.plan-first .stage.over>.mapbar .floors{pointer-events:none} .plan-first .stage.over>.mapbar .floors>*{pointer-events:auto}
.plan-first .stage.over>.topbar .warns{pointer-events:none} .plan-first .stage.over>.topbar .warns>*{pointer-events:auto}
.plan-first .stage.over>.topbar .notice{background:rgba(2,16,36,.72);border-color:rgba(0,216,240,.7)} .plan-first .stage.over .weather,.plan-first .stage.over .moist{background:rgba(2,16,36,.66)}
.topbar .warns{flex:1 1 auto;min-width:0;display:grid;justify-items:start;gap:6px} .topbar .notice{margin:0}
.moist{display:inline-flex;max-width:100%;gap:10px;align-items:center;min-height:30px;padding:3px 12px;border-radius:999px;background:rgba(2,16,36,.55);border:2px solid rgba(201,243,255,.35);box-shadow:none;color:${BRAND.white};font-weight:800;font-size:13px;white-space:nowrap}
.moist b{font-variant-numeric:tabular-nums}
.moist .added{color:#ffb4ad}
.weather{margin-left:auto;flex:none;display:flex;gap:10px;align-items:center;padding:4px 12px;border-radius:999px;background:rgba(2,16,36,.55);border:2px solid rgba(201,243,255,.35);font-weight:800;font-size:13px;white-space:nowrap}
/* UI hotfix: floors (left) and menu (right) in a bar at the card's bottom edge, below the plan – never over it */
.mapbar{display:flex;align-items:flex-end;gap:8px;padding:6px 10px 10px;background:#062a52}
.floors{flex:1 1 auto;min-width:0;display:flex;flex-wrap:wrap;gap:6px}
.floorbtn{min-height:34px;padding:3px 11px;font-size:12.5px;background:${BRAND.white};color:${BRAND.ink}}
.floorbtn.pulse{position:relative}
.floorbtn.p-act{--pulse:${TONE_COLOR.act}} .floorbtn.p-close{--pulse:${TONE_COLOR.close}} .floorbtn.p-critical{--pulse:${TONE_COLOR.critical}}
.floorbtn.pulse{animation:floorpulse 1.8s ease-in-out infinite;box-shadow:3px 3px 0 ${BRAND.ink},0 0 0 3px var(--pulse)}
@keyframes floorpulse{0%,100%{box-shadow:3px 3px 0 ${BRAND.ink},0 0 0 3px var(--pulse)}50%{box-shadow:3px 3px 0 ${BRAND.ink},0 0 0 8px transparent}}
.floorbtn.pulse:after{content:"";position:absolute;top:-5px;right:-5px;width:12px;height:12px;border-radius:50%;background:var(--pulse);border:2px solid ${BRAND.ink}}
:host([data-paused]) .floorbtn.pulse,:host([data-still]) .floorbtn.pulse{animation:none}
@media (prefers-reduced-motion:reduce){.floorbtn.pulse{animation:none}}
.dlg.dark{background:${BRAND.night};color:var(--fq-fg,${BRAND.white})}
.dlg.dark .body h4{margin:10px 0 4px;font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--fq-muted,${BRAND.ice})}
.dlg.dark button{background:var(--fq-btn,${BRAND.panel});color:var(--fq-btn-fg,${BRAND.white})} .dlg.dark button[aria-pressed="true"],.dlg.dark .foot button{background:var(--fq-accent,${BRAND.cyan});color:var(--fq-on-accent,${BRAND.ink})}
/* UI order (0.26.7.0): the tiles, hints and lists of every window in the house map's dark style – readable on its sky */
.dlg.dark .tile{background:var(--fq-surface,rgba(2,16,36,.36));border:1px solid var(--fq-line2,rgba(201,243,255,.18));color:inherit;min-width:0;overflow-wrap:anywhere}
.dlg.dark .tile .l{color:var(--fq-muted,#cfe6ff)} .dlg.dark .tile .s,.dlg.dark .hint{color:var(--fq-muted2,#a9cbe6)}
.dlg.dark .why{background:var(--fq-surface,rgba(2,16,36,.38));color:inherit;border:1px solid var(--fq-line2,rgba(201,243,255,.2));box-shadow:none}
.dlg.dark .body p{margin:0}.dlg.dark .lead{font-size:14px;font-weight:700;line-height:1.45}.dlg.dark .body li{overflow-wrap:anywhere}
.dlg.dark details.more{border-radius:14px;background:var(--fq-surface,rgba(2,16,36,.3));border:1px solid var(--fq-line2,rgba(201,243,255,.14));padding:8px 12px}
.dlg.dark details.more summary{cursor:pointer;min-height:40px;display:flex;align-items:center;font-weight:800}
.dlg.dark details.more summary:focus-visible{outline:3px solid var(--fq-focus,#ffd27a);outline-offset:2px}
.dlg.dark .hint2,.dlg.dark .legend{font-size:12px;opacity:.85}
.diag-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.diag-actions button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;text-align:center;min-height:64px;padding:8px 6px;border-radius:16px;font-size:clamp(12px,3.4vw,14px);line-height:1.25;white-space:normal;overflow-wrap:anywhere;margin:0}
.diag-actions button b,.diag-actions button span:not(.ico){display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.diag-actions button ha-icon,.diag-actions button .ico{flex:none;--mdc-icon-size:18px;font-size:16px;line-height:1.3}
dialog .dlg{display:flex;flex-direction:column;max-height:calc(100vh - 24px);max-height:calc(100dvh - 24px)}
dialog .dlg header,dialog .dlg .foot{flex:none} dialog .dlg .body{flex:1 1 auto;min-height:0;overscroll-behavior:contain}
.dlg .field{display:grid;gap:4px;margin-top:6px} .dlg textarea,.dlg select{font:inherit;width:100%;box-sizing:border-box;border-radius:12px;border:3px solid ${BRAND.ink};padding:8px;background:${BRAND.white};color:${BRAND.ink}}
.dlg.dark button:disabled{opacity:.55;cursor:not-allowed}
.fab{flex:none;margin-left:auto;min-height:34px;padding:3px 12px;font-size:13px;background:${BRAND.white};color:${BRAND.ink}}
.fab[aria-expanded="true"]{background:${BRAND.cyan}}
.menu{margin-top:10px;padding:12px;border-radius:20px;background:rgba(2,16,36,.35);border:3px solid ${BRAND.ink}}
.plan-first .menu{margin:0;border-radius:0;border:0;border-top:3px solid ${BRAND.ink};padding:4px 14px 14px}
.menu[hidden]{display:none}
.menu h4{margin:10px 0 4px;font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:${BRAND.ice}}
.guest{display:flex;align-items:center;gap:6px;font-weight:700}
.wall{pointer-events:none}
.symbol .sym{stroke:${BRAND.white}} .symbol .halo{stroke:${BRAND.ink}} .symbol .gap{stroke:${BRAND.night}}
.conn.logical line{stroke:${BRAND.ice};stroke-dasharray:var(--dot);opacity:.75} .conn.logical text{pointer-events:none}
.source circle{fill:${BRAND.white};stroke:${BRAND.ink}}
.conn-mark circle{fill:${BRAND.white};stroke:${BRAND.ink}} .conn-mark{pointer-events:none} .op{stroke-opacity:.6}
@keyframes breathe{0%,100%{fill-opacity:1}50%{fill-opacity:.72}}
.room{animation:rest 11s ease-in-out infinite}
@keyframes rest{0%,100%{fill-opacity:1}50%{fill-opacity:.94}}
.room.t-run,.room.t-close,.room.t-critical{animation:breathe 4s ease-in-out infinite}
:host([data-paused]) .room,:host([data-still]) .room{animation:none}
@media (prefers-reduced-motion:reduce){.room,.room.t-run,.room.t-close,.room.t-critical{animation:none}}
`;

export const LOGO = `<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M6 24 24 8l18 16" fill="none" stroke="${BRAND.ice}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M11 21v19h26V21" fill="none" stroke="${BRAND.ice}" stroke-width="4.5" stroke-linejoin="round"/>
<path d="M3 27h16c4 0 4-5 0-5M5 33h20c4 0 4 5 0 5" fill="none" stroke="${BRAND.cyan}" stroke-width="3.5" stroke-linecap="round"/>
<path d="M28 39c0-9 6-14 14-15-1 9-6 15-14 15z" fill="${BRAND.leaf}" stroke="${BRAND.ink}" stroke-width="1.5"/></svg>`;

// Wind dial: the arrow points where the air moves to; it turns with the (smoothed) wind and the plan's north.
export function windDial(fromDeg, northDeg, speedMs) {
  const turning = fromDeg == null ? "" : `<g style="transform:rotate(${r3((fromDeg + 180 - northDeg) % 360)}deg);transform-origin:24px 24px;transition:transform .8s">
    <path d="M24 6 31 20h-4.5v18h-5V20H17z" fill="${BRAND.cyan}" stroke="${BRAND.ink}" stroke-width="2" stroke-linejoin="round"/></g>`;
  const dur = streamSeconds(speedMs);
  return `<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="21" fill="${BRAND.deep}" stroke="${BRAND.ink}" stroke-width="3"/>
    <circle cx="24" cy="24" r="17" fill="none" stroke="${BRAND.cyan}" stroke-width="1.5" stroke-dasharray="3 5" class="${fromDeg == null ? "" : "flow"}" style="--dur:${r3(dur * 2)}s;--dashlen:8"/>
    <text x="24" y="9.5" text-anchor="middle" font-size="7" font-weight="900" fill="${BRAND.coral}" style="transform:rotate(${r3(-northDeg)}deg);transform-origin:24px 24px">N</text>${turning}</svg>`;
}

export const escHtml = esc;

// Home Assistant weather conditions in plain words.
const CONDITIONS = {
  de: { "clear-night": "klare Nacht", cloudy: "bewölkt", exceptional: "Unwetter", fog: "Nebel", hail: "Hagel", lightning: "Gewitter", "lightning-rainy": "Gewitter mit Regen",
    partlycloudy: "teils bewölkt", pouring: "Starkregen", rainy: "Regen", snowy: "Schnee", "snowy-rainy": "Schneeregen", sunny: "sonnig", windy: "windig", "windy-variant": "windig, bewölkt" },
  en: { "clear-night": "clear night", cloudy: "cloudy", exceptional: "severe weather", fog: "fog", hail: "hail", lightning: "thunderstorm", "lightning-rainy": "thunderstorm with rain",
    partlycloudy: "partly cloudy", pouring: "pouring rain", rainy: "rain", snowy: "snow", "snowy-rainy": "sleet", sunny: "sunny", windy: "windy", "windy-variant": "windy, cloudy" },
};
export const conditionText = (condition, language) => (CONDITIONS[language === "de" ? "de" : "en"][String(condition || "")] || String(condition || ""));

// 0.26.5.5: walls and openings drawn where they really are (house map and editor).
// Exterior wall parts are thick, interior ones thin; a symbol per opening kind, readable without colour:
// window = double line (open: sashes swung out, tilted: a small wedge), door = gap + door leaf with its
// swing arc, passage = a real gap with two jambs, vent = short dashes.
const w3 = v => Math.round(v * 1000) / 1000;
const WP = p => `${w3(p[0])},${w3(-p[1])}`;
// The symbol of a connection kind (house map and editor, hotfix 0.26.6.0).
export const CONNECTION_SYMBOL = { open_passage: "⇄", door: "🚪", stairs: "🪜", shaft: "⇵", duct: "〰" };
// A confirmed partition wall (G.partitionFills): the space between both rooms drawn as wall – never as air.
export function partitionSvg(fills, color = "#0a1f38") {
  return fills.map(f => `<polygon class="pwall" data-partition="${f.a}|${f.b}" points="${f.polygon.map(WP).join(" ")}" fill="${color}" fill-opacity="0.78" pointer-events="none"/>`).join("");
}
export function wallsSvg(parts, px, color = "#0a1f38") {  // 0.26.6.0(7): slimmer, softer walls
  return parts.map(w => `<line class="wall ${w.interior ? "inner" : "outer"}" x1="${w3(w.a[0])}" y1="${w3(-w.a[1])}" x2="${w3(w.b[0])}" y2="${w3(-w.b[1])}" stroke="${color}" stroke-width="${px(w.interior ? 1.8 : 4.5)}" stroke-linecap="round" stroke-opacity="${w.interior ? 0.7 : 0.9}"/>`).join("");
}
// a, b: ends of the opening on its wall; inward: unit normal into the room; state: open/tilted/closed/…
// 0.26.6.0(2): the geometry is drawn light with a dark rim (``halo``), so it reads on dark and light rooms alike;
// the state keeps its own colour band (the card's line.op). Doors and passages are real gaps in the wall
// (G.wallSegments), so only a window still covers the wall line. ``door`` (G.doorGeometry): hinge, free end and the
// side the leaf opens to; without it the hinge is at a and the leaf opens into the room (as before).
export function openingSymbol(kind, a, b, inward, state, px, background = BRAND.night, door = null, { arc = true } = {}) {  // 0.26.6.0(10): arc only in the editor
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, u = [(b[0] - a[0]) / len, (b[1] - a[1]) / len];
  const at = (p, k, n) => [p[0] + u[0] * k + inward[0] * n, p[1] + u[1] * k + inward[1] * n];
  const seg = (p, q, w, cls, extra = "") => `<line class="halo" x1="${w3(p[0])}" y1="${w3(-p[1])}" x2="${w3(q[0])}" y2="${w3(-q[1])}" stroke="${BRAND.ink}" stroke-width="${px(w + 2.4)}" stroke-linecap="round"${extra}/>`
    + `<line class="${cls}" x1="${w3(p[0])}" y1="${w3(-p[1])}" x2="${w3(q[0])}" y2="${w3(-q[1])}" stroke="${BRAND.white}" stroke-width="${px(w)}" stroke-linecap="round"${extra}/>`;
  const open = state === "open" || state === "open_unspecified";
  if (kind === "passage") {
    const j = len * 0.08;
    return `${seg(at(a, 0, -j), at(a, 0, j), 2.6, "sym jamb")}${seg(at(b, 0, -j), at(b, 0, j), 2.6, "sym jamb")}`;
  }
  if (kind === "door") {
    // the leaf turns on its hinge: open 90° to its side, closed lying in the opening; the swing as a dashed arc
    const d = door || { hinge: a, free: b, swing: inward };
    const H = d.hinge, E = d.free, s = d.swing, O = [H[0] + s[0] * len, H[1] + s[1] * len];
    const e = [(E[0] - H[0]) / len, (E[1] - H[1]) / len], sweep = e[0] * s[1] - e[1] * s[0] > 0 ? 0 : 1;
    // 0.26.6.0(6): the swing is a quiet hint – hairline, finely dashed, half transparent with a faint rim – the leaf
    // carries the door
    const path = `M ${WP(E)} A ${w3(len)} ${w3(len)} 0 0 ${sweep} ${WP(O)}`;
    const arcs = `<path class="halo" d="${path}" fill="none" stroke="${BRAND.ink}" stroke-opacity=".15" stroke-width="${px(2)}"/>`
      + `<path class="sym arc" d="${path}" fill="none" stroke="${BRAND.white}" stroke-opacity=".35" stroke-width="${px(1)}" stroke-dasharray="${px(2.5)} ${px(3)}"/>`;
    return `${arc ? arcs : ""}${seg(H, open ? O : E, 2.6, "sym leaf")}`;
  }
  const gap = `<line class="sym gap" x1="${w3(a[0])}" y1="${w3(-a[1])}" x2="${w3(b[0])}" y2="${w3(-b[1])}" stroke="${background}" stroke-width="${px(8)}"/>`;
  if (kind === "vent") return `${gap}${seg(a, b, 2.6, "sym vent", ` stroke-dasharray="${px(3)} ${px(3)}"`)}`;
  // window / roof window: two parallel panes in the wall
  const dd = px(2.6);
  let out = `${gap}${seg(at(a, 0, -dd), at(b, 0, -dd), 1.4, "sym pane")}${seg(at(a, 0, dd), at(b, 0, dd), 1.4, "sym pane")}`;
  if (open) out += seg(a, at(a, len * 0.25, len * 0.45), 2, "sym sash") + seg(b, at(b, -len * 0.25, len * 0.45), 2, "sym sash");
  else if (state === "tilted") out += `<path class="halo" d="M ${WP(a)} L ${WP(at(a, len / 2, len * 0.22))} L ${WP(b)}" fill="none" stroke="${BRAND.ink}" stroke-width="${px(4)}"/><path class="sym tilt" d="M ${WP(a)} L ${WP(at(a, len / 2, len * 0.22))} L ${WP(b)}" fill="none" stroke="${BRAND.white}" stroke-width="${px(1.6)}"/>`;
  return out;
}
// unit normal of edge ``index`` pointing into the room (rooms are drawn counter-clockwise or not – both work)
export function inwardNormal(G, polygon, index) {
  const n = G.outwardNormal(polygon, index), m = G.edgePoint(polygon, index, 0.5);
  const probe = [m[0] - n[0] * 0.05, m[1] - n[1] * 0.05];
  return G.pointInPolygon(probe, polygon) === "inside" ? [-n[0], -n[1]] : n;
}
// 0.26.7.2 (house card, a reading update): the changes from the drawn content (o) to the new one (n), collected for the live
// nodes (l) – or false, the card draws anew. The weather layer and the moving wind paths run on their own clock and are left as
// they are; canvases belong to the layers.
export const morph = (o, n, l, out) => {
  if (o.isEqualNode(n)) return true;
  if (!l || (o.nodeType !== 11 && l.nodeName !== o.nodeName) || o.nodeName !== n.nodeName || o.childNodes.length !== n.childNodes.length) return false;
  if (o.nodeType === 3) return out.push(() => { l.data = n.data; });
  if (o.nodeType === 1) {
    if (o.matches(".wxu,[data-wave],[data-gust],[data-eddy]")) return true;
    for (const a of new Set([...o.getAttributeNames(), ...n.getAttributeNames()])) { const v = n.getAttribute(a); if (o.getAttribute(a) !== v) out.push(() => (v == null ? l.removeAttribute(a) : l.setAttribute(a, v))); }
  }
  const kids = [...l.childNodes].filter(c => c.nodeName !== "CANVAS");
  return kids.length === o.childNodes.length && kids.every((k, i) => morph(o.childNodes[i], n.childNodes[i], k, out));
};
