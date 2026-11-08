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
// Even samples along a polyline with smoothed normals: [{p, s, n}], s = distance from the start.
export function waveFrame(line, step) {
  const out = [];
  let total = 0;
  for (let i = 0; i < line.length - 1; i++) {
    const a = line[i], b = line[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len < 1e-9) continue;
    const n = Math.max(1, Math.ceil(len / step));
    for (let k = out.length ? 1 : 0; k <= n; k++) out.push({ p: [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n], s: total + len * k / n });
    total += len;
  }
  out.forEach((q, i) => {
    const a = out[Math.max(i - 2, 0)].p, b = out[Math.min(i + 2, out.length - 1)].p;
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    q.n = [-(b[1] - a[1]) / len, (b[0] - a[0]) / len];
  });
  return { samples: out, length: total };
}
// One wave strand at ``phase`` (cycles): the offset follows sin(2π(s/λ − phase) + shift) and fades to 0 at
// both ends, so a strand starts and ends calmly on its stream. Returns "M x,y L x,y …" in SVG coordinates.
export function wavePath(frame, { amp, wavelength, shift = 0 }, phase) {
  const L = frame.length || 1, ramp = Math.min(L * 0.18, wavelength);
  return frame.samples.map((q, i) => {
    const env = Math.min(1, q.s / ramp, (L - q.s) / ramp);
    const off = amp * Math.max(env, 0) * Math.sin(2 * Math.PI * (q.s / wavelength - phase) + shift);
    return `${i ? "L" : "M"} ${r3(q.p[0] + q.n[0] * off)},${r3(-(q.p[1] + q.n[1] * off))}`;
  }).join(" ");
}
// Three strands per stream like layered air ribbons: middle (the stream itself) and two lighter companions.
export const WAVE_STRANDS = [
  { cls: "mid", amp: 1, wave: 1, shift: 0, width: 1 },
  { cls: "hi", amp: 0.75, wave: 1.38, shift: 2.1, width: 0.6 },
  { cls: "lo", amp: 1.6, wave: 0.6, shift: 4.2, width: 6 },   // order 8: a broad, nearly transparent air mass
];

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

/**
 * Schematic wind streams around the drawn floor.
 * rooms: [{id, polygon}], openings: [{id, room_id, edge, offset, width_m, state, pending}], G: geometry module.
 * Returns [{kind: "pass"|"deflect"|"inflow", points:[[x,y]...], curve:{from,ctrl,to}|null, opening, room}] in plan coordinates.
 * Walls turn every decorative stream along them (downwind side). Separately, every open, confirmed outside opening
 * the wind presses on (published facade pressure ≥ INLET_PRESSURE) gets its own inflow: from the upwind edge to the
 * window, into the room and – only along a published directed air path – on and out (Hotfix (9) F02/F03).
 */
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

// 0.26.7.0(2): ``variety`` (freshairiq-house-motion.js streamVariety) gives each decorative stream its own lane across the house
// and its own length – no even grid of identical streaks; without it the streams are spread evenly as before.
export function windStreams({ rooms, openings, fromDeg, northDeg, G, count = 7, paths = [], frame = null, variety = null }) {  // 0.26.6.0(7): 7 streams, no crowding
  if (fromDeg == null || !rooms.length) return [];
  const t = G.bearingVector((fromDeg + 180) % 360, northDeg); // direction the air moves to
  const p = [-t[1], t[0]];
  const box = G.bbox(rooms.map(r => r.polygon));
  const c = [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2];
  const R = Math.hypot(box.maxX - box.minX, box.maxY - box.minY) / 2 || 1;
  const f = frame || { minX: box.minX - R * 0.3, minY: box.minY - R * 0.3, maxX: box.maxX + R * 0.3, maxY: box.maxY + R * 0.3 };
  const streams = [];
  const total = variety ? variety.length : count;
  for (let i = 0; i < total; i++) {
    const v = variety ? variety[i] : null;
    const k = (v ? v.lane : -1 + (2 * i) / (count - 1)) * R * 0.98;
    const base = add(c, mul(p, k));
    const span = clipLine(base, t, f);  // each streak starts at the edge of the drawing
    if (!span) continue;
    const spanLen = span[1] - span[0];
    const S = add(base, mul(t, span[0] + (v ? v.start * spanLen * 0.35 : 0)));      // its own start: never all at the same edge
    const exit = add(base, mul(t, span[0] + (v ? Math.max(v.end, v.start + 0.3) * spanLen : spanLen)));
    let best = null;
    for (const room of rooms) {
      const pts = room.polygon;
      for (let e = 0; e < pts.length; e++) {
        const hit = rayHit(S, t, pts[e], pts[(e + 1) % pts.length]);
        if (hit && (!best || hit.s < best.s)) best = { ...hit, room, edge: e };
      }
    }
    if (!best) { streams.push({ kind: "pass", points: [S, exit], curve: null, variety: i }); continue; }
    const H = add(S, mul(t, best.s));
    const pts = best.room.polygon, a = pts[best.edge], b = pts[(best.edge + 1) % pts.length];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const tau = mul(sub(b, a), 1 / len);
    // head-on the air splits at the middle of the wall; at a slant it slides off downwind
    const slide = Math.abs(dot(t, tau)) < 0.35 ? dot(sub(H, c), tau) : dot(t, tau);
    const along = slide >= 0 ? tau : mul(tau, -1);
    const n = G.outwardNormal(pts, best.edge);
    const before = sub(H, mul(t, R * 0.14));
    const end = add(add(H, mul(along, R * 0.3)), mul(n, R * 0.16));  // bounces off and slides along the wall (short: no overlap)
    streams.push({ kind: "deflect", points: [S, before], curve: { from: before, ctrl: add(H, mul(n, R * 0.01)), to: end }, room: best.room.id, variety: i });
  }
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
