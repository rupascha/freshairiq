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
// 0.26.7.2: what falls – by the reported condition (sleet and hail as such); without one by the summary's flags; else nothing
const PRECIP = { rainy: "rain", pouring: "rain", "lightning-rainy": "rain", snowy: "snow", "snowy-rainy": "sleet", hail: "hail" };
const precipKind = (condition, w) => PRECIP[condition] || (w.raining === true && w.snowing === true ? "sleet" : w.raining === true ? "rain" : w.snowing === true ? "snow" : null);
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
    rain: w.raining === true, snow: w.snowing === true, thunder: w.thunder === true, precip: precipKind(condition, w),
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
// 0.26.7.2: further fields of ``under`` – t: the card's animation clock in seconds (every loop starts where it already is, so a
// live update never restarts the weather), level: the motion level, particles: the most drops or flakes at once, precipLevel:
// 1–3 when the weather model grades the precipitation, seed: the floor's own random sequence. Rain, snow, sleet and hail are single particles on the card's weather
// canvas (WeatherLayer); weatherSvg leaves their description in ``under.fall``.
const pctX = (u, x) => r3(((x - u.vb[0]) / u.vb[2]) * 100), pctY = (u, y) => r3(((y - u.vb[1]) / u.vb[3]) * 100);
const pctW = (u, w) => r3((w / u.vb[2]) * 100), pctH = (u, h) => r3((h / u.vb[3]) * 100);
// a box in percent of the drawing for an svg-space rectangle (x, y top-left, w, h)
export const underBox = (u, x, y, w, h) => `left:${pctX(u, x)}%;top:${pctY(u, y)}%;width:${pctW(u, w)}%;height:${pctH(u, h)}%`;
// a loop of ``cycle`` seconds that continues at the card's clock ``t`` (plus its own offset 0..1): a negative delay
export const loopDelay = (t, cycle, offset = 0) => r3(-((((Number(t) || 0) + offset * cycle) % cycle + cycle) % cycle));
const SPEED = { minimal: 0.55, normal: 1, intense: 1.35 };
export function weatherSvg(sky, frame, wind, northDeg, px, mask, under = null) {
  if (!sky) return "";
  const W = frame.maxX - frame.minX, H = frame.maxY - frame.minY, c = [(frame.minX + frame.maxX) / 2, (frame.minY + frame.maxY) / 2], R = Math.hypot(W, H) / 2;
  // 0.26.7.2: ``under.seed`` (the card's floor) keeps every cloud, wisp and star the same when only the drawing's size changes
  const rnd = seq(under && Number.isFinite(under.seed) ? under.seed : Math.round(W * 1000 + H * 7));
  const windOk = wind && wind.available && wind.from_deg != null;
  const to = windOk ? bearing((Number(wind.from_deg) + 180) % 360, northDeg) : [0, -1];
  const speed = windOk ? clamp(num(wind.speed_ms) || 0, 0, 20) : 0;
  const t = under ? Number(under.t) || 0 : 0, pace = under ? SPEED[under.level] || 1 : 1;
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
      // 0.26.7.2: every ray its own breath (length of its cycle, its phase and a slightly uneven spread) – no wave through the fan
      for (let i = 0; i < 5; i++) {
        const ang = Math.atan2(k[1], k[0]) + (i - 2) * 0.16 + (rnd() - 0.5) * 0.05, half = 0.03 + rnd() * 0.012, dur = r3(11 + rnd() * 9);
        const p1 = [s[0] + Math.cos(ang - half) * L, s[1] + Math.sin(ang - half) * L], p2 = [s[0] + Math.cos(ang + half) * L, s[1] + Math.sin(ang + half) * L];
        out += `<path class="ray" d="M ${P(s)} L ${P(p1)} L ${P(p2)} Z" style="animation-duration:${dur}s;animation-delay:${loopDelay(t, dur, rnd())}s"/>`;
      }
    }
    out += "</g>";
  }
  // stars at night: many when clear, a few between the clouds of a partly cloudy night, none when overcast
  const starCount = sky.phase !== "night" ? 0 : sky.clouds === 0 && sky.clear ? 34 : sky.clouds > 0 && sky.clouds < 0.6 ? 12 : 0;
  if (starCount) {
    // 0.26.7.2: every star its own rhythm (3.4–7.8 s) – no group twinkling in step
    const star = () => { const dur = r3(3.4 + rnd() * 4.4); return [dur, loopDelay(t, dur, rnd())]; };
    if (under) {
      under.html += `<div class="wx stars">${Array.from({ length: starCount }, () => { const x = frame.minX + rnd() * W, y = -(frame.minY + rnd() * H), d = r3(2 * (0.8 + rnd() * 1.1) * px(1) * under.ppu), [dur, delay] = star();
        return `<i style="left:${pctX(under, x)}%;top:${pctY(under, y)}%;width:${d}px;height:${d}px;margin:-${r3(d / 2)}px 0 0 -${r3(d / 2)}px;animation-duration:${dur}s;animation-delay:${delay}s"></i>`; }).join("")}</div>`;
    } else out += `<g class="wx stars">${Array.from({ length: starCount }, () => { const cx = r3(frame.minX + rnd() * W), cy = r3(-(frame.minY + rnd() * H)), r = px(0.8 + rnd() * 1.1), [dur, delay] = star();
      return `<circle cx="${cx}" cy="${cy}" r="${r}" style="animation-duration:${dur}s;animation-delay:${delay}s"/>`; }).join("")}</g>`;
  }
  // cloud shadows drifting with the wind
  if (sky.clouds > 0) {
    if (under) {
      // 0.26.7.2: each cloud passes the whole scene with the wind and comes back from outside – its own size, height, speed and
      // a direction a little off the wind's; every pass starts and ends outside the picture
      const n = sky.clouds > 0.6 ? 5 : 3, diag = Math.hypot(W, H), dir = [to[0], -to[1]];
      let g = '<div class="wx clouds">';
      for (let i = 0; i < n; i++) {
        const x = frame.minX + (0.1 + 0.8 * rnd()) * W, y = frame.minY + ((i + 0.15 + 0.7 * rnd()) / n) * H, rx = W * (0.15 + 0.12 * rnd()), ry = H * (0.07 + 0.06 * rnd());
        const turn = (rnd() - 0.5) * 0.5, cs = Math.cos(turn), sn = Math.sin(turn), dv = [dir[0] * cs - dir[1] * sn, dir[0] * sn + dir[1] * cs];
        const reach = (diag + rx * 1.3) * under.ppu, v = Math.max(W * under.ppu * (0.006 + 0.0025 * speed) * (0.75 + 0.55 * rnd()) * pace, 1);
        const dur = r3(2 * reach / v);
        g += `<i style="${underBox(under, x - rx * 1.15, -y - ry * 1.15, rx * 2.3, ry * 2.3)};--dx:${r3(dv[0] * reach)}px;--dy:${r3(dv[1] * reach)}px;animation-duration:${dur}s;animation-delay:${loopDelay(t, dur, rnd())}s"></i>`;
      }
      under.html += `${g}</div>`;
    } else {
      const n = sky.clouds > 0.6 ? 4 : 2, drift = [to[0] * W * 0.25, -to[1] * W * 0.25];
      let g = `<g class="wx clouds" style="--dx:${r3(drift[0])}px;--dy:${r3(drift[1])}px">`;
      for (let i = 0; i < n; i++) {
        const x = frame.minX + (0.15 + 0.7 * rnd()) * W, y = frame.minY + (0.1 + 0.8 * rnd()) * H, rx = W * (0.16 + 0.1 * rnd()), ry = H * (0.08 + 0.05 * rnd());
        g += `<ellipse cx="${r3(x)}" cy="${r3(-y)}" rx="${r3(rx)}" ry="${r3(ry)}" filter="url(#soft)" style="animation-delay:-${r3(i * 11)}s"/>`;
      }
      out += `${g}</g>`;
    }
  }
  if (sky.fog && under) {
    // 0.26.7.2: a few soft wisps instead of fixed bands – each its own size and height, drifting on its own way with the wind and
    // thinning and thickening in its own, unrelated rhythm
    const n = under.small ? 3 : 4, dir = windOk ? [to[0], -to[1]] : [1, 0];
    let g = '<div class="wx fog">';
    for (let i = 0; i < n; i++) {
      const w = W * (0.45 + 0.45 * rnd()), h = H * (0.12 + 0.13 * rnd()), x = frame.minX - W * 0.15 + rnd() * (W * 1.3 - w), y = frame.minY + ((i + 0.2 + 0.6 * rnd()) / n) * H;
      const far = W * under.ppu * (0.05 + 0.08 * rnd()), turn = (rnd() - 0.5) * 0.9, dv = [dir[0] * Math.cos(turn) - dir[1] * Math.sin(turn), dir[0] * Math.sin(turn) + dir[1] * Math.cos(turn)];
      const d = r3((34 + rnd() * 36) / pace), f = r3(19 + rnd() * 24);
      g += `<i style="${underBox(under, x, -y - h / 2, w, h)};--dx:${r3(dv[0] * far)}px;--dy:${r3(dv[1] * far * 0.4)}px;animation-duration:${d}s,${f}s;animation-delay:${loopDelay(t, 2 * d, rnd())}s,${loopDelay(t, 2 * f, rnd())}s"></i>`;
    }
    under.html += `${g}</div>`;
  } else if (sky.fog) {
    out += `<g class="wx fog">${[0.25, 0.5, 0.78].map((k, i) => `<rect x="${r3(frame.minX - W * 0.2)}" y="${r3(-(frame.minY + k * H) - H * 0.06)}" width="${r3(W * 1.4)}" height="${r3(H * 0.12)}" rx="${r3(H * 0.06)}" filter="url(#soft)" style="animation-delay:-${i * 9}s"/>`).join("")}</g>`;
  }
  // rain, snow, sleet and hail fall slanted by the wind (schematic, about 5° per m/s, at most 40°; hail heavier, less slanted)
  const kind = sky.precip || (sky.rain ? "rain" : sky.snow ? "snow" : null);
  if (kind) {
    const slant = clamp(speed * 5, 0, 40) * (kind === "hail" ? 0.7 : 1) * Math.sign(to[0] || 0);
    const cls = { rain: "rain", snow: "snow", sleet: "sleet", hail: "hail" }[kind];
    if (under) {
      // 0.26.7.2: single drops and flakes on the card's weather canvas – no tile, no repeating sheet. Their number follows the
      // strength (the graded amount, else heavy rain = 3) and the area, limited by the motion level's budget.
      const level = clamp(Number(under.precipLevel) || (sky.condition === "pouring" ? 3 : 2), 1, 3);
      const wpx = W * under.ppu, hpx = H * under.ppu, area = clamp((wpx * hpx) / (900 * 600), 0.4, 1);
      const per = { rain: 1, sleet: 0.85, snow: 0.6, hail: 0.5 }[kind], budget = Math.max(0, Number(under.particles) || 0);
      const n = Math.round(budget * per * area * [0, 0.45, 0.75, 1][level]);
      under.fall = { kind, level, slant: r3(slant), n, w: r3(wpx), h: r3(hpx), scale: r3(clamp(Math.sqrt(under.ppu * px(1)), 0.75, 1.6)) };
      under.html += `<div class="wx ${cls}" data-tilt="${r3(-slant)}" data-level="${level}"></div>`;
    } else out += `<g class="wx ${cls}" data-tilt="${r3(-slant)}"></g>`;
  }
  // 0.26.7.2: the flash comes at uneven moments in a long cycle – on average not more often, never brighter than before; the cycle of
  // the weather mode (``under.flash``: "full" or "dynamic", see FLASH)
  if (sky.thunder && under) under.html += `<div class="wx flash" style="${underBox(under, frame.minX, -frame.maxY, W, H)};animation-delay:${loopDelay(t, (FLASH[under.flash] || FLASH.dynamic).cycle)}s"></div>`;
  else if (sky.thunder) out += `<rect class="wx flash" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}"/>`;
  return out ? `<g class="weather" data-weather="${sky.condition || ""}" mask="url(#${mask})" pointer-events="none">${out}</g>` : "";
}

// 0.26.7.2: the falling weather on one canvas per card, under the plan. Every drop, flake or hail stone is a particle of its own:
// its start, speed, size, brightness and life are drawn at random, and when it has fallen out of the picture or its life is over it
// starts again outside the picture with new values – nothing repeats, there is no tile and no sheet. Rings where rain lands
// (``splash``) come and go the same way. The card drives ``frame(dt)`` from its one shared loop (freshairiq-house-motion.js) at the
// motion level's frame rate; ``still()`` draws a single picture. A new scene (a live update) keeps every running particle.
const FALL = {
  rain: { v: [260, 380], len: [11, 21], a: [0.3, 0.75], r: [0, 0], life: [0.9, 1.7] },
  hail: { v: [300, 430], len: [0, 0], a: [0.55, 0.9], r: [1.2, 2.1], life: [0.8, 1.4] },
  snow: { v: [26, 58], len: [0, 0], a: [0.5, 0.9], r: [1.1, 2.7], life: [1.1, 2.2] },
  flake: { v: [60, 110], len: [0, 0], a: [0.45, 0.8], r: [1, 2.1], life: [1, 1.8] },   // wet flakes in sleet
};
const BUCKETS = 4;
// One weather canvas per card (``own`` keeps {canvas, layer}; ``under``: see weatherSvg), put into the drawing's precipitation or ring layer after every redraw:
// the particles stay where they are. The canvas covers the drawing at its real screen size (measured once per drawing, not per frame).
// ``motion``: the level's profile – wxDpr and wxPixels limit the canvas resolution (on a large drawing below one pixel per CSS pixel)
export function bindWeather(own, map, under, motion, still) {
  const dpr = Math.min((typeof window !== "undefined" && window.devicePixelRatio) || 1, motion.wxDpr || 1);
  const fall = under && (under.fall || (under.splash ? { kind: null, n: 0, level: 0, slant: 0, scale: 1, w: 1, h: 1 } : null));
  const scene = fall ? { ...fall, splash: under.splash || 0 } : null;
  const host = map && map.querySelector(":scope > .wxu > .wx.rain, :scope > .wxu > .wx.snow, :scope > .wxu > .wx.sleet, :scope > .wxu > .wx.hail, :scope > .wxu > .wx.splash");
  if (!scene || !host) { if (own.canvas) own.canvas.remove(); if (own.layer) own.layer.setScene(null); return; }
  if (!own.canvas) { own.canvas = document.createElement("canvas"); own.canvas.className = "wxfx"; own.canvas.setAttribute("aria-hidden", "true"); }
  host.appendChild(own.canvas);
  if (!own.layer) own.layer = new WeatherLayer(own.canvas);
  const fresh = !own.layer.scene, svg = map.querySelector("svg.plan"), box = svg ? svg.getBoundingClientRect() : null;
  own.layer.setScene(box && box.width > 0 && box.height > 0 ? { ...scene, w: box.width, h: box.height } : scene, dpr, motion.wxPixels);
  if (still || fresh) own.layer.still();
}
export class WeatherLayer {
  constructor(canvas) {
    this.cv = canvas; this.ctx = null; this.p = []; this.rings = []; this.scene = null; this.w = 0; this.h = 0; this.dpr = 1;
    this.rnd = seq((Math.random() * 4294967296) >>> 0);
  }
  get active() { return !!(this.scene && (this.scene.n > 0 || this.scene.splash > 0)); }
  // scene: {kind, level, slant, n, w, h, scale, splash}; dpr: the canvas resolution allowed by the motion level
  setScene(scene, dpr = 1, maxPixels = 0) {
    const prev = this.scene;
    this.scene = scene && (scene.n > 0 || scene.splash > 0) ? scene : null;
    if (!this.scene) { this.p = []; this.rings = []; this.boxes = null; this.clear(); return; }
    const w = Math.max(1, Math.round(scene.w)), h = Math.max(1, Math.round(scene.h));
    const d = r3(Math.max(0.4, Math.min(Math.max(1, Math.min(dpr, 3)), maxPixels > 0 ? Math.sqrt(maxPixels / (w * h)) : 3)));
    if (w !== this.w || h !== this.h || d !== this.dpr) {
      // a new size moves every particle with the picture (no new start)
      const kx = this.w ? w / this.w : 1, ky = this.h ? h / this.h : 1;
      for (const q of this.p) { q.x *= kx; q.y *= ky; }
      for (const q of this.rings) { q.x *= kx; q.y *= ky; }
      this.w = w; this.h = h; this.dpr = d;
      this.cv.width = Math.round(w * d); this.cv.height = Math.round(h * d);
      this.ctx = null; this.boxes = null;
    }
    const want = scene.n;
    if (!prev || !this.p.length) { this.p = []; for (let i = 0; i < want; i++) this.p.push(this._spawn(true)); }
    else if (this.p.length < want) { while (this.p.length < want) this.p.push(this._spawn(false)); }
    else if (this.p.length > want) { for (let i = want; i < this.p.length; i++) this.p[i].last = true; }   // they leave when they fall out
    if (!(scene.splash > 0)) this.rings = [];
  }
  _pick(range) { return range[0] + this.rnd() * (range[1] - range[0]); }
  _spawn(anywhere) {
    const s = this.scene, r = this.rnd, kind = s.kind === "sleet" ? (r() < 0.62 ? "rain" : "flake") : s.kind;
    const F = FALL[kind] || FALL.rain, lvl = [0.85, 0.85, 1, 1.18][s.level] || 1, k = s.scale || 1;
    const vy = this._pick(F.v) * lvl * (kind === "rain" && s.kind === "sleet" ? 0.8 : 1) * Math.sqrt(k);
    const tan = Math.tan(Math.abs(s.slant) * Math.PI / 180) * Math.sign(s.slant), vx = vy * tan;
    const life = this._pick(F.life) * (this.h + 40) / vy;
    // a new particle starts above the picture or – with a slant – beyond its upwind side; at the very start anywhere in it
    const reach = Math.abs(tan) * this.h, x0 = tan > 0 ? -reach : 0, span = this.w + reach;
    const q = { kind, x: x0 + r() * span, y: anywhere ? -20 + r() * (this.h + 20) : -10 - r() * this.h * 0.25, vx, vy, age: anywhere ? r() * life * 0.7 : 0, life,
      len: this._pick(F.len) * k, rad: this._pick(F.r) * k, a: this._pick(F.a), sway: kind === "snow" || kind === "flake" ? (4 + r() * 12) * k : 0, freq: 0.35 + r() * 0.6, ph: r() * 6.283 };
    return q;
  }
  frame(dt) {
    if (!this.scene) return;
    const r = this.rnd, w = this.w, h = this.h;
    for (let i = 0; i < this.p.length; i++) {
      const q = this.p[i];
      q.age += dt; q.x += q.vx * dt; q.y += q.vy * dt;
      if (q.age >= q.life || q.y - q.len > h + 4 || (q.vx > 0 && q.x > w + 20) || (q.vx < 0 && q.x < -20)) {
        if (q.last) { this.p.splice(i, 1); i -= 1; continue; }
        if (this.scene.splash > 0 && q.kind === "rain" && q.y > 0 && q.y < h && this.rings.length < this.scene.splash && r() < 0.35) this._ring(q.x, q.y);
        this.p[i] = this._spawn(false);
      }
    }
    if (this.scene.splash > 0) {
      for (let i = this.rings.length - 1; i >= 0; i--) { const g = this.rings[i]; g.age += dt; if (g.age >= g.life) this.rings.splice(i, 1); }
      if (this.rings.length < this.scene.splash && r() < dt * this.scene.splash * 0.9) this._ring(r() * w, r() * h);
    }
    this.draw();
  }
  _ring(x, y) { const k = this.scene.scale || 1; this.rings.push({ x, y, r0: (2 + this.rnd() * 2) * k, r1: (6 + this.rnd() * 6) * k, age: 0, life: 0.9 + this.rnd() * 0.8, a: 0.35 + this.rnd() * 0.25 }); }
  // one picture without motion (reduced motion, the animation or the weather part off): particles and a few rings where they are
  still() {
    if (!this.scene) return;
    if (this.scene.splash > 0 && !this.rings.length) for (let i = 0; i < this.scene.splash; i++) { this._ring(this.rnd() * this.w, this.rnd() * this.h); this.rings[i].age = this.rings[i].life * 0.4; }
    this.draw();
  }
  clear() { if (this.ctx || this.cv.width) { const c = this.cv.getContext("2d"); if (c) { c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.cv.width, this.cv.height); } } }
  draw() {
    const c = this.ctx || (this.ctx = this.cv.getContext("2d"));
    if (!c) return;
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    // only where something was drawn last time is cleared (the canvas is mostly empty), the whole picture after a new size or scene
    const old = this.boxes;
    if (old && old.length < 2400) for (let i = 0; i < old.length; i += 4) c.clearRect(old[i], old[i + 1], old[i + 2], old[i + 3]);
    else c.clearRect(0, 0, this.w, this.h);
    const boxes = this.spare || [], k = this.scene.scale || 1;   // two lists in turn: no new garbage per frame
    boxes.length = 0; this.spare = old; this.boxes = boxes;
    // one pass sorts the particles into a few brightness steps; one path per step (a handful of draw calls per frame)
    const groups = {}, fadeOf = q => Math.min(1, (q.life - q.age) / 0.25, q.age / 0.12 + 0.3);
    for (const q of this.p) {
      const a = q.a * Math.max(0, fadeOf(q));
      if (a <= 0.02) continue;
      const key = q.kind + Math.min(BUCKETS - 1, Math.floor(a * BUCKETS / 0.9));
      (groups[key] || (groups[key] = [])).push(q);
    }
    for (const type of ["rain", "flake", "snow", "hail"]) {
      for (let b = 0; b < BUCKETS; b++) {
        const list = groups[type + b];
        if (!list) continue;
        c.beginPath();
        for (const q of list) {
          if (type === "rain") {
            const l = q.len / Math.hypot(q.vx, q.vy), x2 = q.x - q.vx * l, y2 = q.y - q.vy * l, m = 2 + 2 * k;
            c.moveTo(q.x, q.y); c.lineTo(x2, y2);
            boxes.push(Math.min(q.x, x2) - m, Math.min(q.y, y2) - m, Math.abs(q.x - x2) + 2 * m, Math.abs(q.y - y2) + 2 * m);
          } else {
            const x = q.x + (q.sway ? Math.sin(q.ph + q.age * q.freq * 6.283) * q.sway : 0), m = q.rad + 2;
            c.moveTo(x + q.rad, q.y); c.arc(x, q.y, q.rad, 0, 6.2832);
            boxes.push(x - m, q.y - m, 2 * m, 2 * m);
          }
        }
        const alpha = r3((b + 0.6) * 0.9 / BUCKETS);
        if (type === "rain") { c.strokeStyle = `rgba(207,234,255,${alpha})`; c.lineWidth = (1 + b * 0.12) * k; c.lineCap = "round"; c.stroke(); }
        else { c.fillStyle = type === "hail" ? `rgba(232,246,255,${alpha})` : `rgba(255,255,255,${alpha})`; c.fill(); }
      }
    }
    if (this.rings.length) {
      c.lineWidth = 1;
      for (const g of this.rings) {
        const x = g.age / g.life, rr = g.r0 + (g.r1 - g.r0) * x;
        c.strokeStyle = `rgba(216,239,255,${r3(g.a * (1 - x))})`;
        c.beginPath(); c.arc(g.x, g.y, rr, 0, 6.2832); c.stroke();
        boxes.push(g.x - rr - 2, g.y - rr - 2, 2 * rr + 4, 2 * rr + 4);
      }
    }
  }
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

// 0.26.7.2: the flash's uneven sequence – five flashes (some with a flicker) at uneven moments of one long cycle; [percent, opacity].
// Each weather mode keeps its earlier average rate and brightness: "dynamic" five in 45 s at most .35 (before: one in 9 s), "full"
// five in 65 s at most .32 (before: one in 13 s). A live update continues in the same cycle (``under.flash``, loopDelay).
const FLASH_STEPS = [[11.5, 0], [12, 0.35], [12.6, 0], [13.1, 0.2], [13.8, 0], [31, 0], [31.5, 0.28], [32.3, 0], [52, 0], [52.4, 0.33], [53, 0], [53.4, 0.18], [54.2, 0],
  [70, 0], [70.6, 0.24], [71.4, 0], [90.5, 0], [91, 0.3], [91.7, 0]];
export const FLASH = { dynamic: { cycle: 45, peak: 0.35 }, full: { cycle: 65, peak: 0.32 } };
export const flashKeyframes = (name, peak) => `@keyframes ${name}{0%,100%{opacity:0}${FLASH_STEPS.map(([p, o]) => `${p}%{opacity:${r3(o * peak / 0.35)}}`).join("")}}`;
// CSS of the atmosphere layer. All loops are slow; paused when the card is hidden or the animation is off, and none
// with "reduce motion".
export const ATMOS_STYLE = `
/* 0.26.7.0 UI hotfix: only the drawing's decorative layers – the weather button at the top right (button.weather) stays clickable */
svg .sky,svg .weather,svg .climate,svg .plume,svg .fan,svg .steam{pointer-events:none}
/* the canvas of the incoming air carries the class "flow" too: never the dash animation of the drawn flows (it kept the page busy every frame) */
.map canvas.flow{position:absolute;pointer-events:none;display:block;z-index:2;animation:none}
.wx.sunlight .ray{fill:url(#wx-ray);fill-opacity:.07;animation:rays 14s ease-in-out infinite}
@keyframes rays{0%,100%{fill-opacity:.04}50%{fill-opacity:.11}}
.wx.stars > *{fill:#fff;animation:twinkle 5s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.35}50%{opacity:.95}}
.wx.clouds > *{fill:#021024;fill-opacity:.22;animation:drift 60s ease-in-out infinite alternate}
@keyframes drift{from{transform:translate(calc(var(--dx) * -1),calc(var(--dy) * -1))}to{transform:translate(var(--dx),var(--dy))}}
.wx.fog > *{fill:#e8f2fa;fill-opacity:.16;animation:fogdrift 40s ease-in-out infinite alternate}
@keyframes fogdrift{from{transform:translateX(-4%)}to{transform:translateX(4%)}}
/* 0.26.7.2: a flash at uneven moments (FLASH_STEPS) – "dynamic": 5 in 45 s, never brighter than .35 */
.wx.flash{fill:#eef6ff;opacity:0;animation:flash ${FLASH.dynamic.cycle}s linear infinite}
${flashKeyframes("flash", FLASH.dynamic.peak)}
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
.map .wxu .wx>i{position:absolute;display:block}
/* 0.26.7.2: clouds pass with the wind and come back from outside the picture; fog wisps drift and thin out on their own; the rain,
   snow, sleet and hail are single particles on one canvas (WeatherLayer) */
.map .wxu .wx.clouds>i{border-radius:50%;background:radial-gradient(closest-side,rgba(2,16,36,.22),rgba(2,16,36,.2) 70%,rgba(2,16,36,0));will-change:transform;animation:cloudpass 120s linear infinite}
@keyframes cloudpass{from{transform:translate(calc(var(--dx) * -1),calc(var(--dy) * -1))}to{transform:translate(var(--dx),var(--dy))}}
.map .wxu .wx.fog>i{border-radius:50%;background:radial-gradient(closest-side,rgba(232,242,250,.17),rgba(232,242,250,.11) 55%,rgba(232,242,250,0));will-change:transform,opacity;animation:wisp 50s ease-in-out infinite alternate,wispfade 30s ease-in-out infinite alternate}
@keyframes wisp{from{transform:translate(calc(var(--dx) * -1),calc(var(--dy) * -1))}to{transform:translate(var(--dx),var(--dy))}}
@keyframes wispfade{from{opacity:.55}to{opacity:1}}
.map .wxu canvas.wxfx{position:absolute;left:0;top:0;width:100%;height:100%;display:block}
/* 0.26.7.2: the wind's ribbons and the storm's gusts around the house: their own layer under the plan, repainted alone */
.map .wxu>svg.wxair{position:absolute;left:0;top:0;width:100%;height:100%;display:block;will-change:transform}
.map .wxu .wx.stars>i{border-radius:50%;background:#fff}
.map .wxu .wx.flash{background:#eef6ff}
.map svg.plan{position:relative;z-index:1;will-change:transform}
:host([data-paused]) .wx,:host([data-paused]) .wx *,:host([data-paused]) .cl,:host([data-paused]) .steam path,:host([data-paused]) .plume,:host([data-paused]) .particles,:host([data-paused]) .fan .blades{animation-play-state:paused}
:host([data-still]) .wx,:host([data-still]) .wx *,:host([data-still]) .cl,:host([data-still]) .steam path,:host([data-still]) .plume:not(.fade),:host([data-still]) .particles,:host([data-still]) .fan .blades{animation:none}
:host([data-still]) .steam path{opacity:.6} :host([data-still]) .wx.flash{opacity:.1}
@media (prefers-reduced-motion:reduce){.wx,.wx *,.wx.sunlight .ray,.wx.stars > *,.wx.clouds > *,.wx.fog > *,.cl,.cl.mist,.cl.mist.falling,.cl.mist.rising,.steam path,.plume:not(.fade),.particles,.fan .blades{animation:none}.steam path{opacity:.6}.wx.flash{opacity:.1}}
`;
