// FreshAirIQ house map – atmosphere (0.26.6.0(7)): sky and weather around the house, the room climate at rest and
// fresh air at open windows. Pure presentation: every effect follows a published value (room readings, model
// states named as such, Home Assistant weather and sun.sun). Without a value nothing is drawn – no weather is made up.

const r3 = v => Math.round(v * 1000) / 1000;
const P = p => `${r3(p[0])},${r3(-p[1])}`;
const num = v => (v == null || v === "" || typeof v === "boolean" ? NaN : Number(v));
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
// a fixed sequence of "random" numbers: the same plan always looks the same, a redraw never jumps
const seq = seed => { let x = seed >>> 0 || 1; return () => ((x = (x * 1664525 + 1013904223) >>> 0) / 4294967296); };

export const MOULD_LEVELS = ["Low", "Slightly elevated", "Elevated", "High", "Very high"];

// ---------------------------------------------------------------------------------------------- room climate
// What a room's readings say, as 0..1 strengths. Stale or missing readings give nothing (no invented climate).
// temp: −1 cool … +1 warm (20–22 °C is neutral), humid: from 60 % RH, dry: below 35 % RH, rising: humidity trend
// ≥ 3 %/h, mould: index of the model's mould risk level, source: detected moisture source, fan: exhaust fan running.
export function roomClimate(room) {
  if (!room) return null;
  const ok = room.data_quality == null || room.data_quality === "ok";
  const t = num(room.temperature), rh = num(room.humidity), trend = num(room.humidity_trend_pct_h);
  const temp = ok && Number.isFinite(t) ? clamp((t - 21) / 4, -1, 1) : 0;
  const actuators = room.configured_actuators || {};
  return {
    temp: Math.abs(temp) < 0.25 ? 0 : temp,
    humid: ok && Number.isFinite(rh) ? clamp((rh - 58) / 22, 0, 1) : 0,
    dry: ok && Number.isFinite(rh) ? clamp((38 - rh) / 13, 0, 1) : 0,
    rising: ok && Number.isFinite(trend) && trend >= 3,
    falling: ok && Number.isFinite(trend) && trend <= -3,   // order 8: a measured drying (e.g. while airing)
    mould: Math.max(0, MOULD_LEVELS.indexOf(String(room.mould_level || ""))),
    source: !!room.moisture_source_active,
    fan: actuators.mechanical_exhaust_active === true,
  };
}
// Shared paint for the climate layer (one set per plan).
export function climateDefs(px) {
  return `<radialGradient id="cl-warm" cx=".5" cy=".55" r=".75"><stop offset="0" stop-color="#ffb37a" stop-opacity=".9"/><stop offset="1" stop-color="#ff8f5a" stop-opacity="0"/></radialGradient>`
    + `<radialGradient id="cl-cool" cx=".5" cy=".45" r=".75"><stop offset="0" stop-color="#9fdcff" stop-opacity=".9"/><stop offset="1" stop-color="#6fb8ff" stop-opacity="0"/></radialGradient>`
    + `<pattern id="cl-mist" width="${px(46)}" height="${px(34)}" patternUnits="userSpaceOnUse"><ellipse cx="${px(12)}" cy="${px(10)}" rx="${px(14)}" ry="${px(6)}" fill="#eaf6ff" fill-opacity=".3"/><ellipse cx="${px(34)}" cy="${px(26)}" rx="${px(12)}" ry="${px(5)}" fill="#eaf6ff" fill-opacity=".22"/></pattern>`
    + `<filter id="cl-blur" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="${px(3.5)}"/></filter>`
    + `<pattern id="cl-dry" width="${px(9)}" height="${px(9)}" patternUnits="userSpaceOnUse"><circle cx="${px(2)}" cy="${px(2)}" r="${px(0.9)}" fill="#ffe2a8"/><circle cx="${px(6.5)}" cy="${px(6)}" r="${px(0.7)}" fill="#ffe2a8"/></pattern>`
    + `<pattern id="cl-mould" width="${px(11)}" height="${px(11)}" patternUnits="userSpaceOnUse"><circle cx="${px(3)}" cy="${px(3)}" r="${px(1.8)}" fill="#b6d36c"/><circle cx="${px(8)}" cy="${px(7)}" r="${px(1.3)}" fill="#8fb14f"/><circle cx="${px(4)}" cy="${px(9)}" r="${px(0.9)}" fill="#cfe68e"/></pattern>`;
}
const MOULD_OPACITY = [0, 0.3, 0.45, 0.62, 0.78];
// The climate of one room, clipped to it (``clip`` = id of the room's clipPath). ``at`` is a free spot in the room
// for the moisture source / fan symbols' surroundings (steam rises above the source symbol).
export function climateSvg(c, pts, clip, px, source = null) {
  if (!c) return "";
  const poly = (cls, fill, opacity, extra = "") => `<polygon class="cl ${cls}" points="${pts.map(P).join(" ")}" fill="${fill}" fill-opacity="${r3(opacity)}"${extra}/>`;
  let out = "";
  if (c.temp > 0) out += poly("warm", "url(#cl-warm)", 0.12 + 0.3 * c.temp);
  if (c.temp < 0) out += poly("cool", "url(#cl-cool)", 0.12 + 0.3 * -c.temp);
  if (c.humid > 0) out += poly(`mist${c.rising ? " rising" : c.falling ? " falling" : ""}`, "url(#cl-mist)", 0.3 + 0.6 * c.humid, ' filter="url(#cl-blur)"');
  if (c.dry > 0) out += poly("dry", "url(#cl-dry)", 0.18 + 0.32 * c.dry);
  if (c.mould > 0) out += `<polygon class="cl mould m-${c.mould}" points="${pts.map(P).join(" ")}" fill="none" stroke="url(#cl-mould)" stroke-opacity="${MOULD_OPACITY[c.mould]}" stroke-width="${px(8 + 4 * c.mould)}"/>`;
  if (c.source && source) {
    const [x, y] = source, wisp = k => `M ${r3(x + px(k))},${r3(-y - px(10))} c ${px(-7)},${px(-9)} ${px(7)},${px(-15)} 0,${px(-26)}`;
    out += `<g class="steam">${[-6, 0, 6].map((k, i) => `<path d="${wisp(k)}" style="animation-delay:-${i * 0.9}s" stroke-width="${px(2.2)}"/>`).join("")}</g>`;
  }
  return out ? `<g class="climate" clip-path="url(#${clip})" pointer-events="none">${out}</g>` : "";
}
// A slowly turning fan where an exhaust fan really runs (configured_actuators.mechanical_exhaust_active).
export function fanSvg(at, px, label) {
  const blade = a => `<path d="M 0,0 C ${px(2)},${px(-4)} ${px(7)},${px(-8)} ${px(3)},${px(-10)} C ${px(-1)},${px(-11)} ${px(-3)},${px(-5)} 0,0z" transform="rotate(${a})"/>`;
  return `<g class="fan" role="img" aria-label="${label}" transform="translate(${r3(at[0])} ${r3(-at[1])})"><circle r="${px(13)}" stroke-width="${px(1.5)}"/><g class="blades">${[0, 120, 240].map(blade).join("")}</g></g>`;
}

// ------------------------------------------------------------------------------------------ air at the windows
const OPEN = new Set(["open", "open_unspecified"]);
// A soft cone of fresh air reaching into the room from an open (deep) or tilted (short) outside opening.
// ``fading``: the opening was just closed – the air fades out instead of vanishing.
export function plumeSvg(id, a, b, inward, state, px, clip, fading = false) {
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, tilted = state === "tilted";
  const depth = len * (tilted ? 0.9 : 1.7), spread = tilted ? 0.15 : 0.35, u = [(b[0] - a[0]) / len, (b[1] - a[1]) / len];
  const far = (p, side) => [p[0] + inward[0] * depth + u[0] * side * len * spread, p[1] + inward[1] * depth + u[1] * side * len * spread];
  const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], tip = [m[0] + inward[0] * depth, m[1] + inward[1] * depth];
  const gid = `pl-${id}`;
  return `<g class="plume${tilted ? " tilted" : ""}${fading ? " fade" : ""}" data-plume="${id}" clip-path="url(#${clip})" pointer-events="none">`
    + `<linearGradient id="${gid}" gradientUnits="userSpaceOnUse" x1="${r3(m[0])}" y1="${r3(-m[1])}" x2="${r3(tip[0])}" y2="${r3(-tip[1])}"><stop offset="0" stop-color="#e9fbff" stop-opacity=".75"/><stop offset=".55" stop-color="#9be7ff" stop-opacity=".28"/><stop offset="1" stop-color="#9be7ff" stop-opacity="0"/></linearGradient>`
    + `<path d="M ${P(a)} L ${P(far(a, -1))} Q ${P(tip)} ${P(far(b, 1))} L ${P(b)} Z" fill="url(#${gid})"/></g>`;
}
export const isOpenState = state => OPEN.has(state) || state === "tilted";

// --------------------------------------------------------------------------------------------- sky and weather
const CLOUDY = new Set(["cloudy", "partlycloudy", "windy-variant", "rainy", "pouring", "lightning", "lightning-rainy", "snowy", "snowy-rainy", "hail", "fog", "exceptional"]);
const SUNNY = new Set(["sunny", "partlycloudy", "windy", "clear-night"]);
// The situation around the house from verified Home Assistant data only: the FreshAirIQ weather summary
// (weather_now: condition, raining, snowing, thunder) and – when the sun.sun entity exists – the sun's elevation and
// azimuth. Day, twilight or night is null when neither sun.sun nor a night condition says it.
export function skyState(weatherNow, sun) {
  const w = weatherNow || {}, condition = w.condition ? String(w.condition) : null;
  const elevation = sun ? num(sun.attributes && sun.attributes.elevation) : NaN, azimuth = sun ? num(sun.attributes && sun.attributes.azimuth) : NaN;
  let phase = null;
  if (Number.isFinite(elevation)) phase = elevation >= 6 ? "day" : elevation > -6 ? "twilight" : "night";
  else if (sun && (sun.state === "above_horizon" || sun.state === "below_horizon")) phase = sun.state === "above_horizon" ? "day" : "night";
  else if (condition === "clear-night") phase = "night";
  return {
    phase, condition, azimuth: Number.isFinite(azimuth) ? azimuth : null, elevation: Number.isFinite(elevation) ? elevation : null,
    rain: w.raining === true, snow: w.snowing === true, thunder: w.thunder === true,
    fog: condition === "fog", clouds: condition && CLOUDY.has(condition) ? (condition === "partlycloudy" ? 0.45 : 0.85) : 0,
    clear: !!condition && SUNNY.has(condition),
  };
}
const SKY = {
  day: ["#2c78a8", "#123f68"], twilight: ["#3b3f74", "#16294d"], night: ["#0a1630", "#02070f"], unknown: ["#0f4479", "#072a4f"],
};
export const skyPalette = phase => SKY[phase || "unknown"] || SKY.unknown;   // 0.26.7.0: the same sky beside the plan
export function skyDefs(sky, px, colors = null) {
  // 0.26.7.0: a weather world may pass the sky's colours from the sun's real elevation (freshairiq-house-weather.js)
  const [top, bottom] = colors || SKY[(sky && sky.phase) || "unknown"];
  const muted = sky && sky.clouds >= 0.8 ? 0.55 : 1;
  return `<linearGradient id="sky" x1="0" y1="0" x2=".35" y2="1"><stop offset="0" stop-color="${top}" stop-opacity="${muted}"/><stop offset="1" stop-color="${bottom}"/></linearGradient>`
    + `<radialGradient id="sky-depth" cx=".5" cy=".5" r=".7"><stop offset=".35" stop-color="#ffffff" stop-opacity=".07"/><stop offset="1" stop-color="#000814" stop-opacity=".35"/></radialGradient>`
    + `<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="${px(7)}"/></filter>`;
}
// The background: sky gradient and a soft depth vignette (no technical grid).
export function skyBackground(vb) {
  const rect = fill => `<rect x="${r3(vb[0])}" y="${r3(vb[1])}" width="${r3(vb[2])}" height="${r3(vb[3])}" fill="${fill}"/>`;
  return `<g class="sky" pointer-events="none">${rect("#072a4f")}${rect("url(#sky)")}${rect("url(#sky-depth)")}</g>`;
}
// Unit vector in plan coordinates for a compass bearing (0° = north) on a plan whose north is ``northDeg``.
const bearing = (deg, northDeg) => { const a = (deg - northDeg) * Math.PI / 180; return [Math.sin(a), Math.cos(a)]; };
// Weather effects in the free space around the house (``mask`` hides them over the house), behind the rooms.
// frame: {minX, minY, maxX, maxY} in plan coordinates; wind: {from_deg, speed_ms, available}.
// ``under`` (0.26.7.0 UI hotfix, optional): {html, vb, ppu} – the large moving layers (clouds, rain and snow, fog, stars, the
// flash) are written as HTML into ``under.html`` instead of the drawing. They lie in a layer under the plan (its rooms are opaque and
// cover them, no mask needed) and move by transform and opacity only, which the browser composes without painting the drawing anew
// (measured at 1440 px, software rendering: rain 50–67 → 33 ms per frame at the 95th percentile). ``vb``: the drawing's viewBox,
// ``ppu``: screen pixels per plan unit.
const pctX = (u, x) => r3(((x - u.vb[0]) / u.vb[2]) * 100), pctY = (u, y) => r3(((y - u.vb[1]) / u.vb[3]) * 100);
const pctW = (u, w) => r3((w / u.vb[2]) * 100), pctH = (u, h) => r3((h / u.vb[3]) * 100);
// a box in percent of the drawing for an svg-space rectangle (x, y top-left, w, h)
export const underBox = (u, x, y, w, h) => `left:${pctX(u, x)}%;top:${pctY(u, y)}%;width:${pctW(u, w)}%;height:${pctH(u, h)}%`;
export function weatherSvg(sky, frame, wind, northDeg, px, mask, under = null) {
  if (!sky) return "";
  const W = frame.maxX - frame.minX, H = frame.maxY - frame.minY, c = [(frame.minX + frame.maxX) / 2, (frame.minY + frame.maxY) / 2], R = Math.hypot(W, H) / 2;
  const rnd = seq(Math.round(W * 1000 + H * 7));
  const windOk = wind && wind.available && wind.from_deg != null;
  const to = windOk ? bearing((Number(wind.from_deg) + 180) % 360, northDeg) : [0, -1];
  const speed = windOk ? clamp(num(wind.speed_ms) || 0, 0, 20) : 0;
  let out = "";
  // 0.26.6.0(10): without a confirmed north the sun's side on the plan is unknown – a soft, even daylight from above
  // (no sun disc, no rays), never light from a side that might be wrong
  if (sky.azimuth != null && sky.directional === false && (sky.phase === "day" || sky.phase === "twilight") && (sky.phase === "twilight" || sky.clear)) {
    const warm = sky.phase === "twilight" ? "#ff9e6b" : "#fff1b8";
    out += `<linearGradient id="wx-day" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${warm}" stop-opacity=".22"/><stop offset=".6" stop-color="${warm}" stop-opacity="0"/></linearGradient>`
      + `<g class="wx daylight"><rect x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}" fill="url(#wx-day)"/></g>`;
  }
  // sun or the glow of twilight on the sun's side (sun.sun azimuth); stars on a clear night
  if (sky.azimuth != null && sky.directional !== false && (sky.phase === "day" || sky.phase === "twilight") && (sky.phase === "twilight" || sky.clear)) {
    const d = bearing(sky.azimuth, northDeg), s = [c[0] + d[0] * R * 0.95, c[1] + d[1] * R * 0.95];
    const warm = sky.phase === "twilight" ? "#ff9e6b" : "#fff1b8";
    out += `<radialGradient id="wx-sun" gradientUnits="userSpaceOnUse" cx="${r3(s[0])}" cy="${r3(-s[1])}" r="${r3(R * 0.9)}"><stop offset="0" stop-color="${warm}" stop-opacity=".55"/><stop offset="1" stop-color="${warm}" stop-opacity="0"/></radialGradient>`
      + `<g class="wx sunlight"><circle cx="${r3(s[0])}" cy="${r3(-s[1])}" r="${r3(R * 0.9)}" fill="url(#wx-sun)"/>`;
    if (sky.phase === "day") {  // a few soft rays from the sun into the garden, fading before they reach the house
      const L = R * 0.75, k = [c[0] - s[0], c[1] - s[1]], kl = Math.hypot(k[0], k[1]) || 1, e = [s[0] + k[0] / kl * L, s[1] + k[1] / kl * L];
      out += `<linearGradient id="wx-ray" gradientUnits="userSpaceOnUse" x1="${r3(s[0])}" y1="${r3(-s[1])}" x2="${r3(e[0])}" y2="${r3(-e[1])}"><stop offset="0" stop-color="#fff4c9"/><stop offset="1" stop-color="#fff4c9" stop-opacity="0"/></linearGradient>`;
      for (let i = 0; i < 5; i++) {
        const ang = Math.atan2(k[1], k[0]) + (i - 2) * 0.16, half = 0.035;
        const p1 = [s[0] + Math.cos(ang - half) * L, s[1] + Math.sin(ang - half) * L], p2 = [s[0] + Math.cos(ang + half) * L, s[1] + Math.sin(ang + half) * L];
        out += `<path class="ray" d="M ${P(s)} L ${P(p1)} L ${P(p2)} Z" style="animation-delay:-${i * 2.3}s"/>`;
      }
    }
    out += "</g>";
  }
  // stars at night: many when clear, a few between the clouds of a partly cloudy night, none when overcast
  const starCount = sky.phase !== "night" ? 0 : sky.clouds === 0 && sky.clear ? 34 : sky.clouds > 0 && sky.clouds < 0.6 ? 12 : 0;
  if (starCount) {
    if (under) {
      under.html += `<div class="wx stars">${Array.from({ length: starCount }, () => { const x = frame.minX + rnd() * W, y = -(frame.minY + rnd() * H), d = r3(2 * (0.8 + rnd() * 1.1) * px(1) * under.ppu);
        return `<i style="left:${pctX(under, x)}%;top:${pctY(under, y)}%;width:${d}px;height:${d}px;margin:-${r3(d / 2)}px 0 0 -${r3(d / 2)}px;animation-delay:-${r3(rnd() * 5)}s"></i>`; }).join("")}</div>`;
    } else out += `<g class="wx stars">${Array.from({ length: starCount }, (_, i) => `<circle cx="${r3(frame.minX + rnd() * W)}" cy="${r3(-(frame.minY + rnd() * H))}" r="${px(0.8 + rnd() * 1.1)}" style="animation-delay:-${r3(rnd() * 5)}s"/>`).join("")}</g>`;
  }
  // cloud shadows drifting with the wind
  if (sky.clouds > 0) {
    const n = sky.clouds > 0.6 ? 4 : 2, drift = [to[0] * W * 0.25, -to[1] * W * 0.25];
    const k = under ? under.ppu : 1;
    let g = under ? `<div class="wx clouds" style="--dx:${r3(drift[0] * k)}px;--dy:${r3(drift[1] * k)}px">` : `<g class="wx clouds" style="--dx:${r3(drift[0])}px;--dy:${r3(drift[1])}px">`;
    for (let i = 0; i < n; i++) {
      const x = frame.minX + (0.15 + 0.7 * rnd()) * W, y = frame.minY + (0.1 + 0.8 * rnd()) * H, rx = W * (0.16 + 0.1 * rnd()), ry = H * (0.08 + 0.05 * rnd());
      // HTML: a soft ellipse (its fading edge stands for the blur of the drawing's version)
      g += under ? `<i style="${underBox(under, x - rx * 1.15, -y - ry * 1.15, rx * 2.3, ry * 2.3)};animation-delay:-${r3(i * 11)}s"></i>`
        : `<ellipse cx="${r3(x)}" cy="${r3(-y)}" rx="${r3(rx)}" ry="${r3(ry)}" filter="url(#soft)" style="animation-delay:-${r3(i * 11)}s"/>`;
    }
    if (under) under.html += `${g}</div>`; else out += `${g}</g>`;
  }
  if (sky.fog && under) {
    under.html += `<div class="wx fog">${[0.25, 0.5, 0.78].map((k, i) => `<i style="${underBox(under, frame.minX - W * 0.2, -(frame.minY + k * H) - H * 0.09, W * 1.4, H * 0.18)};animation-delay:-${i * 9}s"></i>`).join("")}</div>`;
  } else if (sky.fog) {
    out += `<g class="wx fog">${[0.25, 0.5, 0.78].map((k, i) => `<rect x="${r3(frame.minX - W * 0.2)}" y="${r3(-(frame.minY + k * H) - H * 0.06)}" width="${r3(W * 1.4)}" height="${r3(H * 0.12)}" rx="${r3(H * 0.06)}" filter="url(#soft)" style="animation-delay:-${i * 9}s"/>`).join("")}</g>`;
  }
  // rain and snow fall slanted by the wind (schematic, about 5° per m/s, at most 40°)
  if (sky.rain || sky.snow) {
    const slant = clamp(speed * 5, 0, 40) * Math.sign(to[0] || 0), tile = px(sky.snow && !sky.rain ? 44 : 34);
    const big = { x: frame.minX - W * 0.5, y: -(frame.maxY + H * 0.5) - tile, w: W * 2, h: H * 2 + tile };
    const marks = sky.rain
      ? Array.from({ length: 5 }, () => { const x = rnd() * tile, y = rnd() * tile; return `<line x1="${r3(x)}" y1="${r3(y)}" x2="${r3(x)}" y2="${r3(y + px(7))}" stroke="#cfeaff" stroke-opacity=".55" stroke-width="${px(1.1)}" stroke-linecap="round"/>`; }).join("")
      : Array.from({ length: 4 }, () => `<circle cx="${r3(rnd() * tile)}" cy="${r3(rnd() * tile)}" r="${px(1.3 + rnd())}" fill="#ffffff" fill-opacity=".8"/>`).join("");
    if (under) {
      // One tile drawn once (screen pixels) with the slant inside it; the sheet only moves – along the slant by exactly one step of
      // the tile grid, so the loop is seamless – and is never rotated (a rotated layer is resampled in every frame).
      const T = Math.max(8, Math.round(tile * under.ppu)), sl = Math.tan(Math.abs(slant) * Math.PI / 180), dir = Math.sign(slant) || 1;
      const k = sl < 0.05 ? 1 : Math.min(20, Math.ceil(1 / sl)), Tw = sl < 0.05 ? T : Math.round(k * T * sl), tx = sl < 0.05 ? 0 : dir * Tw, ty = k * T;
      const L = 7 * T / 34, mark = (x, y) => sky.rain
        ? `<line x1="${r3(x)}" y1="${r3(y)}" x2="${r3(x + (sl < 0.05 ? 0 : dir * L * sl))}" y2="${r3(y + L)}" stroke="#cfeaff" stroke-opacity=".55" stroke-width="${r3(1.1 * T / 34)}" stroke-linecap="round"/>`
        : `<circle cx="${r3(x)}" cy="${r3(y)}" r="${r3((1.3 + rnd()) * T / 44)}" fill="#ffffff" fill-opacity=".8"/>`;
      const n = Math.max(1, Math.round((sky.rain ? 5 : 4) * Tw / T));
      let m = "";
      for (let i = 0; i < n; i++) { const x = rnd() * Tw, y = rnd() * T; for (const [ox, oy] of [[0, 0], [-Tw, 0], [Tw, 0], [0, -T], [-Tw, -T], [Tw, -T]]) m += mark(x + ox, y + oy); }
      const tileSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="${Tw}" height="${T}">${m}</svg>`;
      under.html += `<div class="wxarea" style="${underBox(under, frame.minX, -frame.maxY, W, H)}"><div class="wx ${sky.rain ? "rain" : "snow"}" data-tilt="${r3(-slant)}">`
        + `<div class="fall" style="--tile:${ty}px;--tx:${tx}px;--k:${k};left:-${Tw}px;right:-${Tw}px;top:-${ty}px;background-size:${Tw}px ${T}px;background-image:url('data:image/svg+xml,${encodeURIComponent(tileSvg)}')"></div></div></div>`;
    } else out += `<pattern id="wx-fall" width="${r3(tile)}" height="${r3(tile)}" patternUnits="userSpaceOnUse">${marks}</pattern>`
      + `<g class="wx ${sky.rain ? "rain" : "snow"}" transform="rotate(${r3(-slant)} ${r3(c[0])} ${r3(-c[1])})"><rect class="fall" x="${r3(big.x)}" y="${r3(big.y)}" width="${r3(big.w)}" height="${r3(big.h)}" fill="url(#wx-fall)" style="--tile:${r3(tile)}px"/></g>`;
  }
  if (sky.thunder && under) under.html += `<div class="wx flash" style="${underBox(under, frame.minX, -frame.maxY, W, H)}"></div>`;
  else if (sky.thunder) out += `<rect class="wx flash" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}"/>`;
  return out ? `<g class="weather" data-weather="${sky.condition || ""}" mask="url(#${mask})" pointer-events="none">${out}</g>` : "";
}
// The mask that keeps weather off the house (rooms widened by a margin).
// Night and twilight over the house (from sun.sun only): the rooms lie in a cool, dim light – a soft veil from the
// top that leaves walls, symbols and labels above it untouched (they stay fully readable).
export function nightVeil(sky, rooms) {
  if (!sky || (sky.phase !== "night" && sky.phase !== "twilight")) return "";
  const night = sky.phase === "night";
  return `<linearGradient id="nv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${night ? "#1b2f5c" : "#3a2d55"}" stop-opacity="${night ? 0.42 : 0.18}"/><stop offset="1" stop-color="#030a18" stop-opacity="${night ? 0.5 : 0.2}"/></linearGradient>`
    + `<g class="night-veil ${sky.phase}" pointer-events="none" fill="url(#nv)">${rooms.map(r => `<polygon points="${r.polygon.map(P).join(" ")}"/>`).join("")}</g>`;
}
export function weatherMask(id, frame, rooms, px) {
  return `<mask id="${id}" maskUnits="userSpaceOnUse" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(frame.maxX - frame.minX)}" height="${r3(frame.maxY - frame.minY)}">`
    + `<rect x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(frame.maxX - frame.minX)}" height="${r3(frame.maxY - frame.minY)}" fill="#fff"/>`
    + `<g fill="#000" stroke="#000" stroke-width="${px(16)}" stroke-linejoin="round">${rooms.map(r => `<polygon points="${r.polygon.map(P).join(" ")}"/>`).join("")}</g></mask>`;
}

// CSS of the atmosphere layer. All loops are slow; paused when the card is hidden or the animation is off, and none
// with "reduce motion".
export const ATMOS_STYLE = `
/* 0.26.7.0 UI hotfix: only the drawing's decorative layers – the weather button at the top right (button.weather) stays clickable */
svg .sky,svg .weather,svg .climate,svg .plume,svg .fan,svg .steam{pointer-events:none}
.map canvas.flow{position:absolute;pointer-events:none;display:block;z-index:2}
.wx.sunlight .ray{fill:url(#wx-ray);fill-opacity:.07;animation:rays 14s ease-in-out infinite}
@keyframes rays{0%,100%{fill-opacity:.04}50%{fill-opacity:.11}}
.wx.stars > *{fill:#fff;animation:twinkle 5s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.35}50%{opacity:.95}}
.wx.clouds > *{fill:#021024;fill-opacity:.22;animation:drift 60s ease-in-out infinite alternate}
@keyframes drift{from{transform:translate(calc(var(--dx) * -1),calc(var(--dy) * -1))}to{transform:translate(var(--dx),var(--dy))}}
.wx.fog > *{fill:#e8f2fa;fill-opacity:.16;animation:fogdrift 40s ease-in-out infinite alternate}
@keyframes fogdrift{from{transform:translateX(-4%)}to{transform:translateX(4%)}}
.wx .fall{animation:fall calc(.55s * var(--k,1)) linear infinite}
.wx.snow .fall{animation-duration:calc(5s * var(--k,1))}
@keyframes fall{from{transform:translate(0,0)}to{transform:translate(var(--tx,0px),var(--tile))}}
.wx.flash{fill:#eef6ff;opacity:0;animation:flash 9s linear infinite}
@keyframes flash{0%,90%,93%,95%,100%{opacity:0}91%{opacity:.35}94%{opacity:.22}}
.cl.mist{animation:mist 9s ease-in-out infinite}
.cl.mist.rising{animation-duration:4.5s}
.cl.mist.falling{animation:clearing 7s ease-in-out infinite}
@keyframes clearing{0%,100%{opacity:.75}50%{opacity:.45}}
@keyframes mist{0%,100%{opacity:.8}50%{opacity:1}}
.cl.mould{stroke-linejoin:round}
.steam path{fill:none;stroke:#eaf6ff;stroke-linecap:round;opacity:0;animation:steam 2.7s ease-out infinite}
@keyframes steam{0%{opacity:0;transform:translateY(0)}35%{opacity:.75}100%{opacity:0;transform:translateY(-6%)}}
.plume{animation:plume 3.6s ease-in-out infinite}
.plume.tilted{opacity:.7}
@keyframes plume{0%,100%{opacity:.7}50%{opacity:1}}
.plume.fade{animation:plumefade 3s ease-out forwards}
@keyframes plumefade{from{opacity:.9}to{opacity:0}}
.particles{fill:none;stroke:#f2fdff;stroke-linecap:round;opacity:.8;animation:flow var(--dur,2s) linear infinite}
.fan circle{fill:rgba(2,16,36,.6);stroke:rgba(234,246,255,.6)} .fan .blades{fill:#eaf6ff;animation:spin 2.4s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 0.26.7.0 UI hotfix: the moving weather in its own layer under the plan (see weatherSvg, under) – composed, never repainted */
.map .wxu{position:absolute;left:0;top:0;width:100%;height:100%;overflow:hidden;pointer-events:none;z-index:0}
.map .wxu>svg.wxsky{position:absolute;left:0;top:0;width:100%;height:100%;display:block}
.map .wxu .wx,.map .wxu .wxarea{position:absolute;left:0;top:0;width:100%;height:100%}
.map .wxu .wxarea{overflow:hidden}
.map .wxu .fall{position:absolute;bottom:0;background-repeat:repeat;will-change:transform}
.map .wxu .wx>i{position:absolute;display:block}
.map .wxu .wx.clouds>i{border-radius:50%;background:radial-gradient(closest-side,rgba(2,16,36,.22),rgba(2,16,36,.2) 70%,rgba(2,16,36,0));will-change:transform}
.map .wxu .wx.fog>i{border-radius:50%;background:radial-gradient(closest-side,rgba(232,242,250,.16),rgba(232,242,250,.12) 60%,rgba(232,242,250,0));will-change:transform}
.map .wxu .wx.stars>i{border-radius:50%;background:#fff}
.map .wxu .wx.flash{background:#eef6ff}
.map svg.plan{position:relative;z-index:1;will-change:transform}
:host([data-paused]) .wx,:host([data-paused]) .wx *,:host([data-paused]) .cl,:host([data-paused]) .steam path,:host([data-paused]) .plume,:host([data-paused]) .particles,:host([data-paused]) .fan .blades{animation-play-state:paused}
:host([data-still]) .wx,:host([data-still]) .wx *,:host([data-still]) .cl,:host([data-still]) .steam path,:host([data-still]) .plume:not(.fade),:host([data-still]) .particles,:host([data-still]) .fan .blades{animation:none}
:host([data-still]) .steam path{opacity:.6} :host([data-still]) .wx.flash{opacity:.1}
@media (prefers-reduced-motion:reduce){.wx,.wx *,.wx .fall,.wx.sunlight .ray,.wx.stars > *,.wx.clouds > *,.wx.fog > *,.cl,.cl.mist,.cl.mist.falling,.cl.mist.rising,.steam path,.plume:not(.fade),.particles,.fan .blades{animation:none}.steam path{opacity:.6}.wx.flash{opacity:.1}}
`;
