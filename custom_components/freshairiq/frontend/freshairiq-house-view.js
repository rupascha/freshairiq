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
  { cls: "lo", amp: 0.9, wave: 0.82, shift: 4.2, width: 0.45 },
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
 * Closed walls: the stream runs to the wall and turns along it (downwind side). An open, confirmed outside
 * opening on that wall: the stream enters and runs to the room's centre (and on along a known air path).
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

export function windStreams({ rooms, openings, fromDeg, northDeg, G, count = 9, paths = [], frame = null }) {
  if (fromDeg == null || !rooms.length) return [];
  const t = G.bearingVector((fromDeg + 180) % 360, northDeg); // direction the air moves to
  const p = [-t[1], t[0]];
  const box = G.bbox(rooms.map(r => r.polygon));
  const c = [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2];
  const R = Math.hypot(box.maxX - box.minX, box.maxY - box.minY) / 2 || 1;
  const f = frame || { minX: box.minX - R * 0.3, minY: box.minY - R * 0.3, maxX: box.maxX + R * 0.3, maxY: box.maxY + R * 0.3 };
  const streams = [];
  for (let i = 0; i < count; i++) {
    const k = (-1 + (2 * i) / (count - 1)) * R * 0.98;
    const base = add(c, mul(p, k));
    const span = clipLine(base, t, f);  // each streak starts at the edge of the drawing
    if (!span) continue;
    const S = add(base, mul(t, span[0]));
    const exit = add(base, mul(t, span[1]));
    let best = null;
    for (const room of rooms) {
      const pts = room.polygon;
      for (let e = 0; e < pts.length; e++) {
        const hit = rayHit(S, t, pts[e], pts[(e + 1) % pts.length]);
        if (hit && (!best || hit.s < best.s)) best = { ...hit, room, edge: e };
      }
    }
    if (!best) { streams.push({ kind: "pass", points: [S, exit], curve: null }); continue; }
    const H = add(S, mul(t, best.s));
    const pts = best.room.polygon, a = pts[best.edge], b = pts[(best.edge + 1) % pts.length];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const window = openings.find(o => {
      if (o.room_id !== best.room.id || o.edge !== best.edge || !OPEN.has(o.state) || o.pending || o.target !== "outside") return false;
      const half = Math.min(o.width_m || Math.min(0.9, len * 0.4), len) / len / 2 + 0.25 / len;
      return Math.abs(best.u - o.offset) <= half;
    });
    if (window) {
      const inside = [G.labelPoint(best.room.polygon)];
      const onward = paths.find(x => x.from === window.id && x.direction === "directed");
      if (onward) for (const pt of onward.points.slice(2)) inside.push(pt);
      streams.push({ kind: "inflow", points: [S, H, ...inside], curve: null, opening: window.id, room: best.room.id, tilted: window.state === "tilted" });
      continue;
    }
    const tau = mul(sub(b, a), 1 / len);
    // head-on the air splits at the middle of the wall; at a slant it slides off downwind
    const slide = Math.abs(dot(t, tau)) < 0.35 ? dot(sub(H, c), tau) : dot(t, tau);
    const along = slide >= 0 ? tau : mul(tau, -1);
    const n = G.outwardNormal(pts, best.edge);
    const before = sub(H, mul(t, R * 0.14));
    const end = add(add(H, mul(along, R * 0.5)), mul(n, R * 0.2));  // bounces off and slides along the wall
    streams.push({ kind: "deflect", points: [S, before], curve: { from: before, ctrl: add(H, mul(n, R * 0.01)), to: end }, room: best.room.id });
  }
  return streams;
}

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
  background:linear-gradient(180deg,#0b4580,#062a52);touch-action:pan-x pan-y pinch-zoom;overflow-x:auto;-webkit-overflow-scrolling:touch}
svg.plan{display:block;width:100%;max-width:100%;height:auto;max-height:78vh;margin:0 auto}
.room{cursor:pointer;stroke:${BRAND.ink};stroke-linejoin:round}
.room:focus{outline:none;stroke:${BRAND.white}}
.room.sel{stroke:${BRAND.white}}
.t-act{fill:${TONE_COLOR.act}} .t-run{fill:${TONE_COLOR.run}} .t-close{fill:${TONE_COLOR.close}} .t-wait{fill:${TONE_COLOR.wait}}
.t-sensor{fill:${TONE_COLOR.sensor}} .t-ok{fill:${TONE_COLOR.ok}} .t-critical{fill:${TONE_COLOR.critical}}
text{pointer-events:none;font-family:inherit}
.tag rect,.tag circle{fill:${BRAND.white};stroke:${BRAND.ink}}
.tag .n{font-weight:900;fill:${BRAND.ink}} .tag .a{font-weight:800;fill:${BRAND.ink}} .tag .c{font-weight:700;fill:#24435f}
.op{stroke-linecap:round;cursor:pointer}
.op.closed{stroke:${BRAND.white}} .op.tilted{stroke:${BRAND.sky}} .op.open{stroke:${BRAND.lime}} .op.open_unspecified{stroke:${BRAND.lime};stroke-dasharray:var(--dash)}
.op.unknown,.op.no_sensor{stroke:${BRAND.slate};stroke-dasharray:var(--dot)} .op.pending{stroke:${BRAND.orange}}
.wave{fill:none;stroke-linecap:round;stroke-linejoin:round}
.wave.mid{opacity:.75}.wave.hi{opacity:.5}.wave.lo{opacity:.38}
.wave.k-pass{opacity:.32}.wave.k-pass.hi,.wave.k-pass.lo{opacity:.2}
.wave.k-inflow.mid{opacity:.95}.wave.k-inflow.tilted{opacity:.7}
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
