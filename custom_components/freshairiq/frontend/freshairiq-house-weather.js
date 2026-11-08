// FreshAirIQ house map – the weather world (0.26.7.0). Pure presentation of Home Assistant data: the weather entity
// (state, attributes, its forecasts through weather/subscribe_forecast), sun.sun, the FreshAirIQ weather summary and the
// wind of the house map. Every effect and every number follows a value that is really there; a missing value draws
// nothing and shows "–" – nothing is made up. The weather animation is kept apart from the ventilation logic: it reads
// the same published data, it never feeds anything back.

const r3 = v => Math.round(v * 1000) / 1000;
const num = v => (v == null || v === "" || typeof v === "boolean" ? NaN : Number(v));
const fin = v => Number.isFinite(num(v));
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
const P = p => `${r3(p[0])},${r3(-p[1])}`;
const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const seq = seed => { let x = seed >>> 0 || 1; return () => ((x = (x * 1664525 + 1013904223) >>> 0) / 4294967296); };

export const EFFECT_LEVELS = ["off", "subtle", "dynamic", "full"];
// 0.26.7.0: the parts of the weather information a card can choose one by one – the views (compact chip, overview,
// forecasts, wind, sun, date/time, compass) and the single values of the present weather
export const WEATHER_DETAILS = ["condition", "temperature", "apparent", "humidity", "abs_humidity", "pressure", "rain_chance", "dew_point", "uv"];
export const WEATHER_INFO = ["compact", "overview", "hourly", "daily", "wind", "sun", "datetime", "compass", ...WEATHER_DETAILS];
// the information shown when a card says nothing: as before (the compact chip), plus the overview behind it
export const DEFAULT_WEATHER_INFO = ["compact", "overview", "hourly", "daily", "wind", "sun", "datetime", ...WEATHER_DETAILS];
// A card configured before the single values existed lists none of them: it keeps every value (unchanged behaviour)
export const detailsOf = info => { const chosen = WEATHER_DETAILS.filter(k => info.includes(k)); return chosen.length ? chosen : WEATHER_DETAILS.slice(); };
const list = v => (v == null ? [] : (Array.isArray(v) ? v : String(v).split(","))).map(x => String(x).trim()).filter(Boolean);
// 0.26.7.0(2): the single values of the present weather as the card's own decision. ``weather_details`` (written by the card
// editor, also empty) is taken exactly – nothing switched off ever comes back by itself. Without it: the values listed in
// ``weather_info`` (the first 0.26.7.0 format) exactly, and a card that never chose any keeps every value (as before).
export function detailsFor(config = {}) {
  if (config.weather_details != null) return list(config.weather_details).filter(k => WEATHER_DETAILS.includes(k));
  return detailsOf(config.weather_info == null ? [] : list(config.weather_info));
}
// The small weather display at the top right of the house map: what it shows directly (``weather_chip``, in this order). Without
// a choice it shows what it always did – outdoor temperature and humidity. An empty choice shows no chip (the weather window
// stays one tap away in the menu).
export const CHIP_ITEMS = ["temperature", "condition", "humidity", "abs_humidity", "wind", "rain", "apparent", "pressure", "sun", "datetime"];
export const DEFAULT_CHIP = ["temperature", "humidity"];
export const chipFor = (config = {}) => (config.weather_chip == null ? DEFAULT_CHIP.slice() : list(config.weather_chip).filter(k => CHIP_ITEMS.includes(k)));
// how many chip items fit the card's width: a narrow card shows the first ones of the choice (the rest is in the window)
export const chipRoom = width => (!(width > 0) ? 9 : width < 340 ? 2 : width < 460 ? 3 : width < 640 ? 4 : 9);
// Home Assistant's time zone for dates and times: the server's (hass.config.time_zone) unless the user's profile asks for
// the browser's ("local"); undefined = the browser's own zone
export function haTimeZone(hass) {
  const pref = hass && hass.locale && hass.locale.time_zone, server = hass && hass.config && hass.config.time_zone;
  if (pref === "local" || !server) return undefined;
  try { new Intl.DateTimeFormat("en", { timeZone: server }); return server; } catch (_) { return undefined; }
}
export const LAYOUTS = ["auto", "focus", "info"];

// ------------------------------------------------------------------------------------------------------- units
// Home Assistant reports wind in the unit of the weather entity (wind_speed_unit) or of a sensor
// (unit_of_measurement): km/h, m/s, mph, kn, ft/s. Unknown units give no value.
const WIND = { "m/s": 1, "km/h": 1 / 3.6, "kmh": 1 / 3.6, "mph": 0.44704, "kn": 0.514444, "kt": 0.514444, "knots": 0.514444, "ft/s": 0.3048, "bft": null };
export function windToMs(value, unit) {
  const v = num(value), k = WIND[String(unit || "").trim().toLowerCase()];
  return Number.isFinite(v) && v >= 0 && k ? v * k : null;
}
// pressure in hPa from hPa, mbar, Pa, kPa, inHg, mmHg, psi
const PRESSURE = { hpa: 1, mbar: 1, mb: 1, pa: 0.01, kpa: 10, inhg: 33.8639, mmhg: 1.33322, psi: 68.9476, bar: 1000 };
export function pressureToHpa(value, unit) {
  const v = num(value), k = PRESSURE[String(unit || "hPa").trim().toLowerCase()];
  return Number.isFinite(v) && k ? v * k : null;
}
// Beaufort number from m/s (WMO limits)
const BFT = [0.3, 1.6, 3.4, 5.5, 8, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7];
export const beaufort = ms => (Number.isFinite(ms) ? BFT.findIndex(limit => ms < limit) === -1 ? 12 : BFT.findIndex(limit => ms < limit) : null);
// The wind's level for the picture: calm (< 0.5 m/s), light (< 3.4, Bft 0–2), fresh (< 8, Bft 3–4), strong (< 17.2, Bft 5–7),
// storm (Bft 8+ or a measured gust of 20 m/s and more). Unknown speed: null – drawn calm, never as wind.
export function windLevel(ms, gustMs = null) {
  if (!Number.isFinite(ms)) return null;
  if (ms >= 17.2 || (Number.isFinite(gustMs) && gustMs >= 20)) return "storm";
  return ms < 0.5 ? "calm" : ms < 3.4 ? "light" : ms < 8 ? "fresh" : "strong";
}
// compass point of a bearing (16 points)
const POINTS = { de: ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"], en: ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"] };
// A wind direction in degrees from a number, a numeric text or a 16-point compass text in English or German ("NW", "SSW",
// "NNO", "O"); anything else (and numbers outside 0–360) gives null – never a guessed direction
const TEXT_BEARING = Object.fromEntries([...POINTS.en.map((p, i) => [p, i * 22.5]), ...POINTS.de.map((p, i) => [p, i * 22.5])]);
export function parseBearing(value) {
  if (value == null || typeof value === "boolean") return null;
  if (typeof value === "string") {
    const text = value.trim().toUpperCase();
    if (text in TEXT_BEARING) return TEXT_BEARING[text];
    if (!/^[-+]?\d+([.,]\d+)?$/.test(text)) return null;
    value = Number(text.replace(",", "."));
  }
  const v = Number(value);
  return Number.isFinite(v) && v >= 0 && v <= 360 ? v % 360 : null;
}
export const compassPoint = (deg, lang = "en") => (fin(deg) ? POINTS[lang === "de" ? "de" : "en"][Math.round(((num(deg) % 360) + 360) % 360 / 22.5) % 16] : null);

// ----------------------------------------------------------------------------------------------- conditions
const CLOUD = { sunny: 0, "clear-night": 0, partlycloudy: 0.45, cloudy: 0.9, fog: 0.8, rainy: 0.85, pouring: 0.95, "lightning-rainy": 0.95, lightning: 0.9,
  snowy: 0.85, "snowy-rainy": 0.9, hail: 0.9, windy: 0.2, "windy-variant": 0.6, exceptional: 0.9 };
// Cloud cover 0..1: the entity's cloud_coverage (%) when it has one, else from its condition; null when neither says it.
export function cloudCover(attrs, condition) {
  const pct = num(attrs && attrs.cloud_coverage);
  if (Number.isFinite(pct)) return clamp(pct / 100, 0, 1);
  const c = CLOUD[String(condition || "")];
  return c == null ? null : c;
}
// Precipitation strength 0 (none) … 3 (heavy). Graded by the amount only where the source gives one (the current hour of the
// hourly forecast, mm/h); otherwise by the reported condition: rainy = moderate, pouring = heavy. Never invented.
export function precipitation(condition, mmPerHour = null) {
  const c = String(condition || ""), mm = num(mmPerHour);
  const kind = ["snowy"].includes(c) ? "snow" : c === "snowy-rainy" ? "sleet" : c === "hail" ? "hail" : ["rainy", "pouring", "lightning-rainy"].includes(c) ? "rain" : null;
  if (!kind) return { kind: null, level: 0, graded: false };
  if (Number.isFinite(mm) && mm >= 0) return { kind, level: mm === 0 ? 1 : mm < 0.5 ? 1 : mm < 4 ? 2 : 3, graded: true };
  return { kind, level: c === "pouring" ? 3 : 2, graded: false };
}

// --------------------------------------------------------------------------------------------- sun and light
// Continuous daylight from the real sun elevation (sun.sun): colour temperature and strength change with the sun, cloud
// cover dims it. Key points (elevation in degrees) – deep night, astronomical twilight, sunset, golden hour, day, noon.
const SKY_KEYS = [
  [-18, ["#050d1f", "#01050c"]], [-6, ["#1a2350", "#0a1430"]], [0, ["#4a3b74", "#1d2650"]], [6, ["#7a6a9a", "#2a4b7a"]],
  [15, ["#3f86b5", "#174b78"]], [35, ["#2c78a8", "#123f68"]],
];
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, t) => `#${hex(a).map((v, i) => Math.round(v + (hex(b)[i] - v) * t).toString(16).padStart(2, "0")).join("")}`;
export function skyColors(elevation, cover = 0) {
  if (!Number.isFinite(elevation)) return null;
  const e = clamp(elevation, -18, 35);
  let i = SKY_KEYS.findIndex(([k]) => k >= e); if (i <= 0) i = 1;
  const [e0, c0] = SKY_KEYS[i - 1], [e1, c1] = SKY_KEYS[i], t = (e - e0) / (e1 - e0 || 1);
  const grey = ["#59646f", "#2b333c"], k = clamp(Number(cover) || 0, 0, 1) * (e > 0 ? 0.65 : 0.3);
  return [mix(mix(c0[0], c1[0], t), grey[0], k), mix(mix(c0[1], c1[1], t), grey[1], k)];
}
// The light of the sun on the house. warmth: 0 white … 1 deep gold; strength: 0 … 1 (0 below the horizon or overcast);
// shadow: the direction and relative length of the house's shadow on the plan (away from the sun, cot(elevation)),
// only when the plan's north is confirmed – otherwise null (no light from a side that might be wrong).
export function sunLight({ elevation, azimuth, cover = null, northDeg = 0, directional = true } = {}) {
  if (!Number.isFinite(elevation)) return null;
  const up = elevation > 0, c = cover == null ? 0 : clamp(cover, 0, 1);
  const warmth = up ? clamp(1 - (elevation - 2) / 28, 0, 1) : elevation > -6 ? 1 : 0;
  const strength = up ? clamp(Math.sin(elevation * Math.PI / 180) * 1.6, 0.15, 1) * (1 - 0.85 * c) : 0;
  let shadow = null;
  if (up && Number.isFinite(azimuth) && directional && strength > 0.08 && c < 0.7) {   // no hard shadow under a closed cloud deck
    const a = (azimuth + 180 - northDeg) * Math.PI / 180, length = clamp(1 / Math.tan(Math.max(elevation, 4) * Math.PI / 180), 0.15, 4);
    shadow = { dx: Math.sin(a), dy: Math.cos(a), length, opacity: clamp(0.18 + 0.5 * strength, 0.15, 0.6) };
  }
  const color = mix("#fff6dc", "#ffad5c", warmth);
  return { up, warmth, strength, color, shadow };
}
// unit vector on the plan for a compass bearing on a plan whose north is ``northDeg`` (plan y points up)
export const planVector = (deg, northDeg = 0) => { const a = (deg - northDeg) * Math.PI / 180; return [r3(Math.sin(a)), r3(Math.cos(a))]; };

// 0.26.7.0 UI hotfix: absolute humidity in g/m³ – exactly FreshAirIQ's own formula (model.absolute_humidity, Magnus) and the
// range in which the integration computes its outdoor value (coordinator_decision); anything else gives null (never a guess)
export function absoluteHumidity(tempC, rh) {
  if (!fin(tempC) || !fin(rh)) return null;
  const t = num(tempC), h = num(rh);
  if (!(t > -30 && t < 60 && h >= 0 && h <= 100)) return null;
  return 216.7 * ((h / 100) * (6.112 * Math.exp((17.62 * t) / (243.12 + t)))) / (273.15 + t);
}
// ----------------------------------------------------------------------------------------------- the model
// One picture of the weather from what is available. Every field is null when its source says nothing.
// Wind sources: with a weather entity chosen in the card (``own``) speed, gusts and direction come from that entity; a value
// it does not give is taken from FreshAirIQ's own wind (the integration's weather entity, ``wind``) – the only fallback, and
// named per value in ``windSource`` ("entity" / "freshairiq" / null). Without an own entity FreshAirIQ's wind comes first.
// ``outdoor``: FreshAirIQ's outdoor reading ({temperature, humidity, absolute_humidity}) for the absolute humidity – first unless
// the card names its own weather entity (then that entity's temperature and humidity, FreshAirIQ's value only as the fallback)
export function weatherModel({ entityId = null, entity = null, weatherNow = null, sun = null, wind = null, hourly = null, daily = null, moon = null, now = Date.now(), own = false, outdoor = null } = {}) {
  const a = (entity && entity.attributes) || {}, wn = weatherNow || {};
  const state = entity && entity.state && !["unknown", "unavailable"].includes(entity.state) ? String(entity.state) : null;
  const condition = state || (wn.condition ? String(wn.condition) : null);
  const tempUnit = a.temperature_unit || "°C";
  const temperature = fin(a.temperature) ? num(a.temperature) : fin(wn.outdoor_temperature) ? num(wn.outdoor_temperature) : null;
  const unit = a.wind_speed_unit || "km/h";   // Home Assistant's weather default when an entity names no unit
  const fromEntity = { speed: state ? windToMs(a.wind_speed, unit) : null, gust: state ? windToMs(a.wind_gust_speed, unit) : null, bearing: state ? parseBearing(a.wind_bearing) : null };
  const fromHouse = { speed: wind && fin(wind.speed_ms) ? num(wind.speed_ms) : null, gust: wind && fin(wind.gust_ms) ? num(wind.gust_ms) : null, bearing: wind ? parseBearing(wind.from_deg) : null };
  const pick = k => { const order = own ? [["entity", fromEntity], ["freshairiq", fromHouse]] : [["freshairiq", fromHouse], ["entity", fromEntity]]; const hit = order.find(([, v]) => v[k] != null); return hit ? [hit[1][k], hit[0]] : [null, null]; };
  const [windMs, speedSrc] = pick("speed"), [gustMs, gustSrc] = pick("gust"), [bearing, bearingSrc] = pick("bearing");
  const rows = Array.isArray(hourly) ? hourly.filter(r => r && r.datetime) : [];
  const nowRow = rows.find(r => Math.abs(Date.parse(r.datetime) - now) < 3600000) || null;
  const sa = (sun && sun.attributes) || {};
  const sunElev = fin(sa.elevation) ? num(sa.elevation) : null;
  const cover = cloudCover(a, condition);
  const o = outdoor || {}, ownT = state && fin(a.temperature) ? (/F/i.test(tempUnit) ? (num(a.temperature) - 32) * 5 / 9 : num(a.temperature)) : null;
  const fromOwn = absoluteHumidity(ownT, a.humidity);
  const fromFaiq = fin(o.absolute_humidity) && num(o.absolute_humidity) >= 0 && num(o.absolute_humidity) < 100 ? num(o.absolute_humidity) : absoluteHumidity(o.temperature, o.humidity);
  const absHumidity = own ? (fromOwn ?? fromFaiq) : (fromFaiq ?? fromOwn);
  return {
    entityId, available: !!state || !!wn.condition || temperature != null,
    condition, temperature, tempUnit,
    apparent: fin(a.apparent_temperature) ? num(a.apparent_temperature) : null,
    humidity: fin(a.humidity) ? num(a.humidity) : null,
    absHumidity, absSource: absHumidity == null ? null : absHumidity === fromOwn && (own || fromFaiq == null) ? "entity" : "freshairiq",
    pressure: pressureToHpa(a.pressure, a.pressure_unit),
    dewPoint: fin(a.dew_point) ? num(a.dew_point) : null,
    uv: fin(a.uv_index) ? num(a.uv_index) : null,
    windMs, gustMs, bearing, level: windLevel(windMs, gustMs), windSource: { speed: speedSrc, gust: gustSrc, bearing: bearingSrc }, own: !!own,
    cover, precip: precipitation(condition, nowRow && nowRow.precipitation != null ? nowRow.precipitation : null),
    rainChance: nowRow && fin(nowRow.precipitation_probability) ? num(nowRow.precipitation_probability) : null,
    thunder: ["lightning", "lightning-rainy"].includes(condition) || wn.thunder === true,
    fog: condition === "fog", frost: wn.frost === true || (temperature != null && tempUnit === "°C" && temperature <= 0),
    sun: { elevation: sunElev, azimuth: fin(sa.azimuth) ? num(sa.azimuth) : null, rising: sa.next_rising || null, setting: sa.next_setting || null,
      phase: sunElev == null ? (sun && sun.state === "above_horizon" ? "day" : sun && sun.state === "below_horizon" ? "night" : null) : sunElev >= 6 ? "day" : sunElev > -6 ? "twilight" : "night" },
    hourly: rows.slice(0, 24), daily: Array.isArray(daily) ? daily.filter(r => r && r.datetime).slice(0, 7) : [],
    moon: moon && moon.state && !["unknown", "unavailable"].includes(moon.state) ? String(moon.state) : null,
  };
}

// ------------------------------------------------------------------------------------ shared forecast subscriptions
// Several house maps on one or more dashboards share one subscription per weather entity and forecast type (no second
// background process, no extra requests). Home Assistant pushes new forecasts; nothing is polled.
// 0.26.7.0: per Home Assistant connection – cards on another connection (another tab's socket, a reconnect with a new
// connection object, a second Home Assistant) never share a subscription of a connection they do not use.
const SUBS = new Map();
let connectionIds = new WeakMap(), nextConnection = 1;
const connectionId = c => { if (!connectionIds.has(c)) connectionIds.set(c, nextConnection++); return connectionIds.get(c); };
export function subscribeForecast(connection, entityId, type, listener) {
  if (!connection || typeof connection.subscribeMessage !== "function" || !entityId) return () => {};
  const key = `${connectionId(connection)}|${entityId}|${type}`;
  let sub = SUBS.get(key);
  if (!sub) {
    sub = { listeners: new Set(), last: null, unsub: null, connection, closed: false };
    SUBS.set(key, sub);
    connection.subscribeMessage(msg => { sub.last = (msg && msg.forecast) || []; for (const fn of sub.listeners) { try { fn(sub.last); } catch (_) { /* a card's own problem */ } } },
      { type: "weather/subscribe_forecast", forecast_type: type, entity_id: entityId })
      .then(unsub => { if (sub.closed) { try { Promise.resolve(unsub()).catch(() => {}); } catch (_) { /* gone */ } } else sub.unsub = unsub; },
        () => { sub.failed = true; for (const fn of sub.listeners) { try { fn(null); } catch (_) { /* ignore */ } } });
  }
  sub.listeners.add(listener);
  if (sub.last) listener(sub.last);
  return () => {
    sub.listeners.delete(listener);
    if (sub.listeners.size || SUBS.get(key) !== sub) return;
    sub.closed = true; SUBS.delete(key);
    if (sub.unsub) { try { Promise.resolve(sub.unsub()).catch(() => {}); } catch (_) { /* gone */ } }
  };
}
export const forecastSubscriptions = () => SUBS.size;   // for the tests: no subscription is left behind
export const forecastSubscriptionKeys = () => [...SUBS.keys()];

// --------------------------------------------------------------------------------------- the world around the house
// The extra layers of the "full" weather world, drawn in the free space around the house (``mask`` keeps them off the
// rooms) or as a soft light over the whole scene that never covers labels (they are drawn later). ``level``: subtle /
// dynamic / full; "subtle" and "dynamic" add nothing here (the existing atmosphere stays as it was).
export function worldDefs(model, light, px) {
  if (!light) return "";
  return `<radialGradient id="wx-ambient" cx=".5" cy=".5" r=".75"><stop offset=".25" stop-color="${light.color}" stop-opacity="${r3(0.12 * light.strength)}"/><stop offset="1" stop-color="${light.color}" stop-opacity="0"/></radialGradient>`;
}
// ``under``: see freshairiq-house-atmos.js weatherSvg – the storm's gusts move in the composed layer under the plan
export function worldSvg({ model, light, frame, rooms, northDeg = 0, px, mask, small = false, under = null }) {
  if (!model) return "";
  const W = frame.maxX - frame.minX, H = frame.maxY - frame.minY, rnd = seq(Math.round(W * 997 + H * 13));
  // ``moving``: the animated parts, unmasked – they lie behind the opaque rooms anyway, and a masked layer would have to be
  // composed anew in every frame (measured: 60 → 30 fps in a thunderstorm on a software-rendered browser)
  let out = "", moving = "";
  // sunlight warms the garden around the house: strength and colour from the sun's elevation and the clouds
  if (light && light.up && light.strength > 0.05) out += `<rect class="wx ambient" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}" fill="url(#wx-ambient)"/>`;
  // a darker, heavier sky under thunderstorm or storm (never over the rooms)
  if (model.thunder || model.level === "storm" || (model.precip.level >= 3)) out += `<rect class="wx gloom" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}" fill="#020814" fill-opacity="${model.thunder ? 0.32 : 0.22}"/>`;
  // fog: a veil that takes the distance away – denser towards the edge of the scene
  if (model.fog) out += `<rect class="wx haze" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}" fill="#dfe9f2" fill-opacity=".14"/>`;
  // frost: a cool, quiet light (an illustration – no measured frost layer)
  if (model.frost && !model.precip.kind) out += `<rect class="wx frost" x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}" fill="#bfe6ff" fill-opacity=".08"/>`;
  // rain on the ground: soft rings where drops land (moderate and heavy rain only)
  if (model.precip.kind === "rain" && model.precip.level >= 2) {
    // two groups that fade in turn (opacity only – cheap to draw, smooth also on weak devices); a few rings only: twice as
    // many measured 30 instead of 60 fps in a storm on a large, software-rendered screen
    const n = (small ? 4 : 6) * (model.precip.level - 1), ring = () => `<circle cx="${r3(frame.minX + rnd() * W)}" cy="${r3(-(frame.minY + rnd() * H))}" r="${px(3 + rnd() * 3)}" stroke-width="${px(1)}"/>`;
    if (under) {   // every ring a tiny element of its own that fades (composed – no sheet over the whole scene)
      const one = cls => { const x = frame.minX + rnd() * W, y = -(frame.minY + rnd() * H), d = r3(2 * (3 + rnd() * 3) * px(1) * under.ppu);
        return `<i class="${cls}" style="left:${r3(((x - under.vb[0]) / under.vb[2]) * 100)}%;top:${r3(((y - under.vb[1]) / under.vb[3]) * 100)}%;width:${d}px;height:${d}px;margin:-${r3(d / 2)}px 0 0 -${r3(d / 2)}px"></i>`; };
      under.html += `<div class="wx splash">${Array.from({ length: Math.ceil(n / 2) }, () => one("ring-a")).join("")}${Array.from({ length: Math.floor(n / 2) }, () => one("ring-b")).join("")}</div>`;
    } else moving += `<g class="wx splash"><g class="ring-a">${Array.from({ length: Math.ceil(n / 2) }, ring).join("")}</g><g class="ring-b">${Array.from({ length: Math.floor(n / 2) }, ring).join("")}</g></g>`;
  }
  // storm: broad gusts sweep across the garden in the wind's direction
  if ((model.level === "storm" || model.level === "strong") && Number.isFinite(model.bearing)) {
    const to = planVector((model.bearing + 180) % 360, northDeg), ang = Math.atan2(-to[1], to[0]) * 180 / Math.PI;
    const c = [(frame.minX + frame.maxX) / 2, (frame.minY + frame.maxY) / 2];
    if (under) {
      const box = `left:${r3(((frame.minX - under.vb[0]) / under.vb[2]) * 100)}%;top:${r3(((-frame.maxY - under.vb[1]) / under.vb[3]) * 100)}%;width:${r3((W / under.vb[2]) * 100)}%;height:${r3((H / under.vb[3]) * 100)}%`;
      under.html += `<div class="wxarea" style="${box}"><div class="wx sweep${model.level === "storm" ? " storm" : ""}" data-tilt="${r3(ang)}" style="left:-25%;top:-25%;width:150%;height:150%;transform:rotate(${r3(ang)}deg)">`
        + [0.3, 0.55, 0.8].map((k, i) => `<i style="left:-50%;width:50%;top:${r3(16.7 + k * 66.6)}%;height:${r3(Math.max(4, px(10) * under.ppu))}px;animation-delay:-${i * 1.7}s"></i>`).join("") + "</div></div>";
    } else moving += `<g class="wx sweep${model.level === "storm" ? " storm" : ""}" transform="rotate(${r3(ang)} ${r3(c[0])} ${r3(-c[1])})">${[0.3, 0.55, 0.8].map((k, i) => `<rect x="${r3(c[0] - W)}" y="${r3(-c[1] - H / 2 + k * H)}" width="${r3(W * 0.5)}" height="${px(10)}" rx="${px(5)}" style="animation-delay:-${i * 1.7}s"/>`).join("")}</g>`;
  }
  // the moon: only with a moon-phase entity (Home Assistant's moon integration) – an illustration of its phase in the
  // corner of the sky, never a calculated position
  if (model.moon && model.sun.phase === "night") {
    const lit = { new_moon: 0, waxing_crescent: 0.25, first_quarter: 0.5, waxing_gibbous: 0.75, full_moon: 1, waning_gibbous: 0.75, last_quarter: 0.5, waning_crescent: 0.25 }[model.moon];
    if (lit != null && lit > 0) {
      const r = px(small ? 11 : 15), x = frame.maxX - px(34), y = frame.maxY - px(34), waning = model.moon.startsWith("waning") || model.moon === "last_quarter";
      const off = (1 - lit) * 2 * r * (waning ? 1 : -1);
      out += `<g class="wx moon" role="img" aria-label="moon"><clipPath id="wx-moon"><circle cx="${r3(x)}" cy="${r3(-y)}" r="${r3(r)}"/></clipPath>`
        + `<circle cx="${r3(x)}" cy="${r3(-y)}" r="${r3(r)}" fill="#f4f1de" fill-opacity=".92"/>${lit < 1 ? `<circle cx="${r3(x + off)}" cy="${r3(-y)}" r="${r3(r)}" fill="#0a1630" clip-path="url(#wx-moon)"/>` : ""}</g>`;
    }
  }
  // a plain rectangle keeps the moving parts inside the drawing (a clip is cheap, unlike the mask)
  const clip = `<clipPath id="wx-frame"><rect x="${r3(frame.minX)}" y="${r3(-frame.maxY)}" width="${r3(W)}" height="${r3(H)}"/></clipPath>`;
  return (moving ? `${clip}<g class="weather world moving" clip-path="url(#wx-frame)" pointer-events="none">${moving}</g>` : "") + (out ? `<g class="weather world" mask="url(#${mask})" pointer-events="none">${out}</g>` : "");
}
// the house's own shadow, cast away from the sun (its length follows the sun's elevation)
export const shadowOffset = (light, px, span) => (light && light.shadow ? [r3(light.shadow.dx * Math.min(light.shadow.length, 2.5) * span * 0.025 + px(2)), r3(-light.shadow.dy * Math.min(light.shadow.length, 2.5) * span * 0.025 + px(2)), light.shadow.opacity] : null);

export const WORLD_STYLE = `
.wx.ambient{pointer-events:none}
.wx.splash circle{fill:none;stroke:#d8efff;stroke-opacity:.55}.wx.splash g,.map .wxu .wx.splash>i{animation:splash 1.6s ease-in-out infinite alternate;will-change:opacity}.map .wxu .wx.splash>i{border-radius:50%;border:1px solid rgba(216,239,255,.55)}.wx.splash .ring-b{animation-delay:-1.6s}
.wx.sweep > *{fill:#e9f6ff;fill-opacity:.07;animation:sweep 6s linear infinite}.map .wxu .wx.sweep>i{border-radius:999px;background:rgba(233,246,255,.07);will-change:transform}.map .wxu .wx.sweep.storm>i{background:rgba(233,246,255,.12)}.wx.sweep.storm > *{fill-opacity:.12;animation-duration:3.2s}
.wx.haze{animation:haze 30s ease-in-out infinite alternate}
@keyframes splash{0%{opacity:.85}100%{opacity:.08}}
@keyframes sweep{0%{transform:translateX(0)}100%{transform:translateX(200%)}}
@keyframes haze{0%{fill-opacity:.1}100%{fill-opacity:.18}}
:host([data-paused]) .wx.world *,:host([data-paused]) .wxv *{animation-play-state:paused}
:host([data-still]) .wx.world *,:host([data-still]) .wxv *{animation:none}
@media (prefers-reduced-motion:reduce){.wx.world *,.wx.splash g,.wx.sweep > *,.wx.haze,.wxv *{animation:none}}
/* the weather window and the side column (0.26.7.0(2)): one world with the house map – its sky, its light, calm glass panels */
.wxv{display:grid;gap:12px;color:#fff;min-width:0}
.wxv .sub{color:#d6ecff;font-size:13px}
.wxv svg{display:block;max-width:100%;height:auto;overflow:visible}
.wxv .panel{display:grid;gap:8px;padding:12px 14px;border-radius:18px;background:rgba(2,16,36,.34);border:1px solid rgba(201,243,255,.16);min-width:0}
.wxv h4{margin:0;display:flex;align-items:center;gap:8px;font-size:12px;color:#cfe6ff;letter-spacing:.08em;text-transform:uppercase;font-weight:900}
.wxv h4 svg{width:18px;height:18px;flex:none}
.wxv .now{position:relative;display:grid;grid-template-columns:auto 1fr;gap:4px 16px;align-items:center;padding:16px 18px;border-radius:22px;overflow:hidden;
  background:radial-gradient(120% 140% at 0% 0%,var(--wx-glow,rgba(255,210,122,.32)),transparent 60%),linear-gradient(160deg,rgba(255,255,255,.10),rgba(2,16,36,.30));border:1px solid rgba(201,243,255,.22)}
.wxv .now.solo{grid-template-columns:1fr}
.wxv .now .ico{display:block;width:92px;height:92px;filter:drop-shadow(0 6px 14px rgba(0,8,20,.45))}
.wxv .now .ico svg{width:100%;height:100%}
.wxv .big{font-size:46px;font-weight:900;line-height:1;letter-spacing:-.02em}.wxv .big small{font-size:20px;font-weight:800;margin-left:2px;opacity:.85}
.wxv .cond{font-weight:800;font-size:17px;margin-top:4px}
.wxv .hilo{display:flex;gap:12px;font-weight:800;font-size:13px;color:#e8f4ff}.wxv .hilo b{font-weight:900}
.wxv .facts{display:grid;grid-template-columns:repeat(auto-fill,minmax(122px,1fr));gap:8px}
.wxv .fact{display:grid;gap:2px;padding:9px 12px;border-radius:14px;background:rgba(2,16,36,.34);border:1px solid rgba(201,243,255,.16);font-size:12px;font-weight:700;color:#cfe6ff;min-width:0}
.wxv .fact b{font-size:17px;font-weight:900;color:#fff}.wxv .fact i{font-style:normal;font-size:11px;color:#a9cbe6}
.wxv .fact .meter{height:4px;border-radius:2px;background:rgba(255,255,255,.12);overflow:hidden}.wxv .fact .meter span{display:block;height:100%;border-radius:2px;background:linear-gradient(90deg,#7cc8f0,#bfe9ff)}
.wxv .t-axis{fill:#cfe6ff;font-size:11px;font-weight:700}.wxv .t-val{fill:#fff;font-size:12px;font-weight:900}
.wxv .curve{fill:none;stroke:#ffd27a;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}
.wxv .curve-fill{fill:url(#wxv-temp);opacity:.32}.wxv .bar{fill:#5cc2ff;opacity:.8}.wxv .grid-l{stroke:rgba(201,243,255,.1);stroke-width:1}
.wxv .nowmark{stroke:rgba(255,255,255,.45);stroke-width:1.2;stroke-dasharray:2 3}
.wxv .arc-path{fill:none;stroke:rgba(255,236,170,.28);stroke-width:2.2;stroke-dasharray:2 5}.wxv .arc-night{fill:none;stroke:rgba(150,165,220,.28);stroke-width:1.6;stroke-dasharray:2 5}.wxv .arc-done{fill:none;stroke:url(#wxv-sunline);stroke-width:3;stroke-linecap:round}
.wxv .horizon{stroke:rgba(201,243,255,.32);stroke-width:1.5}.wxv .sky-band{fill:url(#wxv-sunsky);opacity:.55}
.wxv .sunpos{fill:#ffd65c;filter:drop-shadow(0 0 8px rgba(255,214,92,.9))}.wxv .sunpos.below{fill:#8fa0c8;filter:none}
.wxv .sunfacts{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;font-weight:800}.wxv .sunfacts span{color:#cfe6ff;font-weight:700}
.wxv .days{display:grid;gap:2px}
.wxv .day{display:grid;grid-template-columns:3.4em 28px 2.6em minmax(16px,1fr) 2.6em 3em;gap:6px;align-items:center;font-size:13px;font-weight:800;padding:5px 2px;border-bottom:1px solid rgba(201,243,255,.08)}
.wxv .day:last-child{border-bottom:0}.wxv .day .lo{color:#a9cbe6;text-align:right}.wxv .day .rain{color:#8fd3ff;font-size:12px;text-align:right}
.wxv .day svg{width:26px;height:26px}
.wxv .range{position:relative;height:6px;border-radius:3px;background:rgba(255,255,255,.1)}.wxv .range i{position:absolute;top:0;bottom:0;border-radius:3px;background:linear-gradient(90deg,#7cc8f0,#ffd27a,#ff8f5c)}
.wxv .range b{position:absolute;top:-3px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:#fff;box-shadow:0 0 0 2px rgba(2,16,36,.6)}
.wxv .windrow{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.wxv .rose{width:124px;height:124px;flex:none}.wxv .rose .ring{fill:rgba(2,16,36,.32);stroke:rgba(201,243,255,.28);stroke-width:1.2}
.wxv .rose .tick{stroke:rgba(201,243,255,.35);stroke-width:1}.wxv .rose .tick.major{stroke:rgba(201,243,255,.7);stroke-width:1.6}
.wxv .rose text{fill:#cfe6ff;font-size:10px;font-weight:900}.wxv .rose .arrow{fill:url(#wxv-arrow)}.wxv .rose .hub{fill:#0b2747;stroke:rgba(201,243,255,.4)}
.wxv .rose .spd{fill:#fff;font-size:15px}.wxv .rose .unit{fill:#a9cbe6;font-size:8px}
.wxv .bft{display:grid;grid-template-columns:repeat(13,1fr);gap:2px;width:100%;max-width:220px}.wxv .bft i{height:6px;border-radius:2px;background:rgba(255,255,255,.12)}
.wxv .bft i.on{background:linear-gradient(90deg,#7cc8f0,#ffd27a)}.wxv .bft i.cur{background:#ffd27a;box-shadow:0 0 6px rgba(255,210,122,.8)}
.wxv .windtxt{display:grid;gap:4px;min-width:0}.wxv .windtxt .w-big{font-size:24px;font-weight:900}
.wxv.compact .now{padding:12px 14px}.wxv.compact .now .ico{width:64px;height:64px}.wxv.compact .big{font-size:34px}.wxv.compact .rose{width:96px;height:96px}
.wxv .ico svg .float{animation:wxfloat 6s ease-in-out infinite}.wxv .ico svg .drift{animation:wxdrift 9s ease-in-out infinite alternate}
@keyframes wxfloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-2px)}}
@keyframes wxdrift{0%{transform:translateX(-1.5px)}100%{transform:translateX(1.5px)}}
:host([data-motion="off"]) .wxv *,:host([data-motion="minimal"]) .wxv *,:host([data-rest]) .wxv *{animation:none}
`;

// --------------------------------------------------------------------------------------------- weather symbols
// 0.26.7.0(2): one calm illustration language for the whole house map (window, chip, forecasts, menu) instead of emoji – drawn
// shapes in the map's own colours. A condition Home Assistant does not name draws nothing (no invented symbol).
const IC = { sun: "#ffd27a", core: "#ffc552", moon: "#f3efd9", cloud: "#eef6fc", back: "#c3d5e4", dark: "#8ea6bc", rain: "#62c6ff", snow: "#ffffff", bolt: "#ffd65c", fog: "#d6e4ef", wind: "#d4ecff" };
const sunG = (cx, cy, r) => `<g class="float"><circle cx="${cx}" cy="${cy}" r="${r * 1.7}" fill="${IC.sun}" opacity=".16"/>${Array.from({ length: 8 }, (_, i) => { const a = i * Math.PI / 4, c = Math.cos(a), s = Math.sin(a); return `<line x1="${r3(cx + c * r * 1.45)}" y1="${r3(cy + s * r * 1.45)}" x2="${r3(cx + c * r * 1.95)}" y2="${r3(cy + s * r * 1.95)}" stroke="${IC.sun}" stroke-width="${r3(r * 0.28)}" stroke-linecap="round"/>`; }).join("")}<circle cx="${cx}" cy="${cy}" r="${r}" fill="${IC.core}"/></g>`;
const moonG = (cx, cy, r) => `<g class="float"><circle cx="${cx}" cy="${cy}" r="${r * 1.6}" fill="${IC.moon}" opacity=".1"/><path d="M ${r3(cx + r * 0.35)} ${r3(cy - r)} A ${r} ${r} 0 1 0 ${r3(cx + r)} ${r3(cy + r * 0.45)} A ${r3(r * 0.78)} ${r3(r * 0.78)} 0 1 1 ${r3(cx + r * 0.35)} ${r3(cy - r)} Z" fill="${IC.moon}"/></g>`;
const cloudG = (x, y, s, fill, cls = "drift") => `<g class="${cls}"><path transform="translate(${x} ${y}) scale(${s})" d="M10 30 H38 A9 9 0 0 0 38 12 A13 13 0 0 0 13.5 14.5 A8 8 0 0 0 10 30 Z" fill="${fill}"/></g>`;
const dropsG = (n, color = IC.rain, y0 = 44) => Array.from({ length: n }, (_, i) => { const x = 18 + i * (28 / Math.max(n - 1, 1)); return `<line x1="${r3(x)}" y1="${y0}" x2="${r3(x - 3)}" y2="${y0 + 9}" stroke="${color}" stroke-width="3" stroke-linecap="round"/>`; }).join("");
const flakesG = (n, y0 = 46) => Array.from({ length: n }, (_, i) => `<circle cx="${r3(19 + i * (26 / Math.max(n - 1, 1)))}" cy="${y0 + (i % 2) * 6}" r="2.6" fill="${IC.snow}"/>`).join("");
const boltG = `<path d="M33 34 L25 48 H31 L28 58 L40 42 H34 L37 34 Z" fill="${IC.bolt}"/>`;
const fogG = `<g stroke="${IC.fog}" stroke-width="3.2" stroke-linecap="round"><line x1="12" y1="44" x2="50" y2="44"/><line x1="17" y1="51" x2="46" y2="51" opacity=".75"/><line x1="12" y1="58" x2="38" y2="58" opacity=".5"/></g>`;
const windG = `<g fill="none" stroke="${IC.wind}" stroke-width="3.2" stroke-linecap="round" class="drift"><path d="M8 26 H40 A6 6 0 1 0 34 20"/><path d="M8 36 H50 A6 6 0 1 1 44 42"/><path d="M14 46 H30" opacity=".6"/></g>`;
const SYMBOL = {
  sunny: n => (n ? moonG(32, 32, 14) : sunG(32, 32, 12)),
  "clear-night": () => `${moonG(30, 32, 14)}<circle cx="50" cy="16" r="1.6" fill="#fff"/><circle cx="12" cy="18" r="1.2" fill="#fff" opacity=".8"/>`,
  partlycloudy: n => `${n ? moonG(24, 22, 10) : sunG(24, 22, 9)}${cloudG(12, 22, 1, IC.cloud)}`,
  cloudy: () => `${cloudG(20, 10, 0.78, IC.back)}${cloudG(6, 20, 1.05, IC.cloud)}`,
  fog: () => `${cloudG(8, 4, 1, IC.back)}${fogG}`,
  rainy: () => `${cloudG(8, 8, 1.05, IC.cloud)}${dropsG(3)}`,
  pouring: () => `${cloudG(8, 8, 1.05, IC.dark)}${dropsG(5)}`,
  lightning: () => `${cloudG(8, 4, 1.05, IC.dark)}${boltG}`,
  "lightning-rainy": () => `${cloudG(8, 4, 1.05, IC.dark)}${boltG}${dropsG(2, IC.rain, 46)}`,
  snowy: () => `${cloudG(8, 8, 1.05, IC.cloud)}${flakesG(4)}`,
  "snowy-rainy": () => `${cloudG(8, 8, 1.05, IC.cloud)}${dropsG(2)}${flakesG(2, 52)}`,
  hail: () => `${cloudG(8, 8, 1.05, IC.back)}${Array.from({ length: 4 }, (_, i) => `<circle cx="${18 + i * 9}" cy="${48 + (i % 2) * 6}" r="3" fill="#e8f6ff" stroke="#9fd6ff"/>`).join("")}`,
  windy: () => windG,
  "windy-variant": () => `${cloudG(14, 0, 0.9, IC.back)}${windG}`,
  exceptional: () => `<path d="M32 10 L56 52 H8 Z" fill="#ffb347"/><rect x="29.5" y="24" width="5" height="16" rx="2.5" fill="#1b2a3a"/><circle cx="32" cy="46" r="3" fill="#1b2a3a"/>`,
};
export const hasSymbol = condition => !!SYMBOL[String(condition || "")];
// the symbol as an <svg> (``size`` px) or as a group inside another drawing (``at`` = [x, y] of its top-left corner)
export function weatherSvg(condition, { size = 28, night = false, at = null, label = "" } = {}) {
  const draw = SYMBOL[String(condition || "")];
  if (!draw) return "";
  const body = draw(!!night);
  if (at) return `<g transform="translate(${r3(at[0])} ${r3(at[1])}) scale(${r3(size / 64)})" aria-hidden="true">${body}</g>`;
  return `<svg class="wxi" viewBox="0 0 64 64" width="${size}" height="${size}" ${label ? `role="img" aria-label="${esc(label)}"` : 'aria-hidden="true"'}>${body}</svg>`;
}
// the glow of the hero by condition (warm sun, cool rain, deep night)
const GLOW = { sunny: "rgba(255,206,110,.42)", partlycloudy: "rgba(255,214,140,.28)", "clear-night": "rgba(150,160,255,.28)", rainy: "rgba(92,194,255,.3)", pouring: "rgba(70,150,230,.34)",
  "lightning-rainy": "rgba(170,140,255,.32)", lightning: "rgba(170,140,255,.32)", snowy: "rgba(220,240,255,.34)", "snowy-rainy": "rgba(200,230,255,.3)", fog: "rgba(214,228,239,.26)", cloudy: "rgba(200,216,230,.22)" };

// --------------------------------------------------------------------------------------------- the overview
const TXT = {
  de: { now: "Jetzt", feels: "Gefühlt", humidity: "Luftfeuchte", pressure: "Luftdruck", wind: "Wind", gust: "Böen", rain: "Regen", dew: "Taupunkt", uv: "UV-Index", abs_humidity: "Absolute Feuchte", abs_humidity_out: "Absolute Luftfeuchtigkeit außen",
    rain_chance: "Regenrisiko", today: "Heute", day_length: "Tageslänge", sun_now: "Sonnenhöhe", below: "unter dem Horizont", next_rise: "Nächster Aufgang", polar_day: "Polartag – die Sonne geht heute nicht unter", polar_night: "Polarnacht – die Sonne geht heute nicht auf",
    uv_level: ["niedrig", "mäßig", "hoch", "sehr hoch", "extrem"], dry: "trocken", humid: "feucht",
    wind_fallback: "Wind teilweise aus FreshAirIQ (fehlt in der gewählten Wetterquelle)", hourly: "Nächste Stunden", daily: "Nächste Tage", sun: "Sonne", sunrise: "Aufgang", sunset: "Untergang", from: "aus", calm: "windstill",
    no_entity: "Keine Wetterentität – nur die Außenwerte von FreshAirIQ. In den Karteneinstellungen lässt sich eine Wetterentität wählen.",
    unavailable: "Die Wetterquelle ist gerade nicht verfügbar.", no_forecast: "Diese Wetterquelle liefert keine Vorhersage.", illus: "Darstellung, keine Messung",
    level: { calm: "windstill", light: "leichter Wind", fresh: "frischer Wind", strong: "starker Wind", storm: "Sturm" },
    cond: { "clear-night": "Klare Nacht", cloudy: "Bewölkt", exceptional: "Unwetter", fog: "Nebel", hail: "Hagel", lightning: "Gewitter", "lightning-rainy": "Gewitter mit Regen",
      partlycloudy: "Teils bewölkt", pouring: "Starkregen", rainy: "Regen", snowy: "Schnee", "snowy-rainy": "Schneeregen", sunny: "Sonnig", windy: "Windig", "windy-variant": "Windig, bewölkt" } },
  en: { now: "Now", feels: "Feels like", humidity: "Humidity", pressure: "Pressure", wind: "Wind", gust: "Gusts", rain: "Rain", dew: "Dew point", uv: "UV index", abs_humidity: "Absolute humidity", abs_humidity_out: "Outdoor absolute humidity",
    rain_chance: "Chance of rain", today: "Today", day_length: "Day length", sun_now: "Sun elevation", below: "below the horizon", next_rise: "Next sunrise", polar_day: "Polar day – the sun does not set today", polar_night: "Polar night – the sun does not rise today",
    uv_level: ["low", "moderate", "high", "very high", "extreme"], dry: "dry", humid: "humid",
    wind_fallback: "Wind partly from FreshAirIQ (missing in the chosen weather source)", hourly: "Next hours", daily: "Next days", sun: "Sun", sunrise: "Sunrise", sunset: "Sunset", from: "from", calm: "calm",
    no_entity: "No weather entity – only FreshAirIQ's outdoor values. A weather entity can be chosen in the card settings.",
    unavailable: "The weather source is unavailable right now.", no_forecast: "This weather source gives no forecast.", illus: "illustration, not a measurement",
    level: { calm: "calm", light: "light wind", fresh: "fresh breeze", strong: "strong wind", storm: "storm" },
    cond: { "clear-night": "Clear night", cloudy: "Cloudy", exceptional: "Severe weather", fog: "Fog", hail: "Hail", lightning: "Thunderstorm", "lightning-rainy": "Thunderstorm with rain",
      partlycloudy: "Partly cloudy", pouring: "Heavy rain", rainy: "Rain", snowy: "Snow", "snowy-rainy": "Sleet", sunny: "Sunny", windy: "Windy", "windy-variant": "Windy and cloudy" } },
};
export const weatherText = lang => TXT[lang === "de" ? "de" : "en"];
const ICON = { "clear-night": "🌙", cloudy: "☁️", exceptional: "⚠️", fog: "🌫️", hail: "🌨️", lightning: "🌩️", "lightning-rainy": "⛈️", partlycloudy: "⛅", pouring: "🌧️", rainy: "🌦️", snowy: "❄️", "snowy-rainy": "🌨️", sunny: "☀️", windy: "🍃", "windy-variant": "🌬️" };
// the emoji of a condition (text contexts such as an aria label); an unknown condition gives "" – never a stand-in symbol
export const conditionIcon = c => ICON[String(c || "")] || "";
const fmt = (v, d, lang) => (v == null || !Number.isFinite(v) ? "–" : v.toFixed(d).replace(".", lang === "de" ? "," : "."));
// every date and time in Home Assistant's time zone (``tz``, see haTimeZone; undefined = the browser's)
const time = (iso, lang, opts, tz) => { const t = Date.parse(iso || ""); return Number.isFinite(t) ? new Date(t).toLocaleTimeString(lang, { ...(opts || { hour: "2-digit", minute: "2-digit" }), timeZone: tz }) : "–"; };
const isNight = model => model.condition === "clear-night" || model.sun.phase === "night";
const HEAD = { sun: sunG(32, 32, 12), hours: `<g fill="none" stroke="#cfe6ff" stroke-width="5" stroke-linecap="round"><circle cx="32" cy="32" r="22"/><path d="M32 18 V32 L42 38"/></g>`,
  days: `<g fill="none" stroke="#cfe6ff" stroke-width="5" stroke-linejoin="round"><rect x="10" y="14" width="44" height="40" rx="6"/><path d="M10 26 H54 M22 8 V18 M42 8 V18"/></g>`, wind: windG };
const head = (key, text) => `<h4><svg viewBox="0 0 64 64" aria-hidden="true">${HEAD[key] || ""}</svg>${esc(text)}</h4>`;

// ---- the sun's day (0.26.7.0 UI hotfix). The arc is the course of the day: sunrise at the left end, sunset at the right end;
// by day the sun stands on the arc at the share of the daylight already gone, at night it travels a second, lower arc back from
// sunset to the next sunrise. Sunrise and sunset come from Home Assistant's location (hass.config latitude/longitude) by the
// NOAA sunrise equation for the shown day in Home Assistant's time zone (checked against astral, the library of Home
// Assistant's sun integration: ha_tests/test_sun_reference_026700.py); without a location from sun.sun's next_rising /
// next_setting. Polar day and polar night are named as such – never a made-up time.
const DAY = 86400000, RAD = Math.PI / 180, J1970 = 2440587.5;
// sunrise and sunset (ms, UTC) of the calendar day y-m-d at a place; { polar: "day" | "night" } when the sun does not rise or set
// the sun's declination (rad) and the equation of time (min) at a Julian day – NOAA's solar calculator
function solarAt(jd) {
  const T = (jd - 2451545) / 36525, om = (125.04 - 1934.136 * T) * RAD;
  const L0 = ((280.46646 + T * (36000.76983 + T * 0.0003032)) % 360) * RAD, M = (357.52911 + T * (35999.05029 - 0.0001537 * T)) * RAD;
  const e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T);
  const C = Math.sin(M) * (1.914602 - T * (0.004817 + 0.000014 * T)) + Math.sin(2 * M) * (0.019993 - 0.000101 * T) + Math.sin(3 * M) * 0.000289;
  const lambda = (L0 / RAD + C - 0.00569 - 0.00478 * Math.sin(om)) * RAD;
  const eps = (23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60 + 0.00256 * Math.cos(om)) * RAD;
  const yv = Math.tan(eps / 2) ** 2;
  const eqt = 4 / RAD * (yv * Math.sin(2 * L0) - 2 * e * Math.sin(M) + 4 * e * yv * Math.sin(M) * Math.cos(2 * L0) - 0.5 * yv * yv * Math.sin(4 * L0) - 1.25 * e * e * Math.sin(2 * M));
  return { dec: Math.asin(Math.sin(eps) * Math.sin(lambda)), eqt };
}
// sunrise and sunset (ms, UTC) of the calendar day y-m-d at a place; { polar: "day" | "night" } when the sun does not rise or set.
// Each event is computed with the sun's position at the event itself (a few iterations), as the reference does.
export function sunEvents(lat, lon, y, m, d) {
  if (!fin(lat) || !fin(lon)) return null;
  const la = num(lat) * RAD, lo = num(lon), base = Date.UTC(y, m - 1, d, 12) - lo / 360 * DAY;
  const at = t => solarAt(t / DAY + J1970);
  const cosW = s => (Math.sin(-0.833 * RAD) - Math.sin(la) * Math.sin(s.dec)) / (Math.cos(la) * Math.cos(s.dec));
  const n0 = at(base), noon = base - n0.eqt * 60000, c0 = cosW(at(noon));
  if (c0 > 1) return { polar: "night" };
  if (c0 < -1) return { polar: "day" };
  const event = sign => {
    let t = noon + sign * Math.acos(c0) / RAD / 360 * DAY;
    for (let i = 0; i < 4; i++) { const s = at(t), c = clamp(cosW(s), -1, 1); t = base - s.eqt * 60000 + sign * Math.acos(c) / RAD / 360 * DAY; }
    return t;
  };
  return { rise: event(-1), set: event(1), noon };
}
// the calendar day of ``t`` in the time zone ``tz`` (undefined = the browser's)
const ymd = (t, tz) => { const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(t)).map(x => [x.type, x.value])); return [Number(p.year), Number(p.month), Number(p.day)]; };
const shiftDay = ([y, m, d], k) => { const t = new Date(Date.UTC(y, m - 1, d + k)); return [t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate()]; };
// the shown day: { rise, set, prevSet, nextRise, polar, phase: "day" | "night", progress 0..1 } – or null without any source
export function sunDay({ now = Date.now(), tz = undefined, lat = null, lon = null, sun = {} } = {}) {
  const today = ymd(now, tz);
  if (fin(lat) && fin(lon)) {
    const t = sunEvents(lat, lon, ...today);
    if (t.polar) return { polar: t.polar, phase: t.polar === "day" ? "day" : "night", progress: 0.5 };
    const y = sunEvents(lat, lon, ...shiftDay(today, -1)), n = sunEvents(lat, lon, ...shiftDay(today, 1));
    return place({ rise: t.rise, set: t.set, prevSet: y && !y.polar ? y.set : t.set - DAY, nextRise: n && !n.polar ? n.rise : t.rise + DAY, now });
  }
  // without a location: Home Assistant's next sunrise and sunset (both in the future) give today's
  const nr = Date.parse(sun.rising || ""), ns = Date.parse(sun.setting || "");
  if (!Number.isFinite(nr) || !Number.isFinite(ns)) return null;
  if (ns < nr) return place({ rise: nr - DAY, set: ns, prevSet: ns - DAY, nextRise: nr, now });   // the sun is up (it sets before it rises again)
  const sameDay = ymd(nr, tz).join() === today.join();                                             // before dawn: today's sunrise still ahead
  return sameDay ? place({ rise: nr, set: ns, prevSet: ns - DAY, nextRise: nr + DAY, now }) : place({ rise: nr - DAY, set: ns - DAY, prevSet: ns - DAY, nextRise: nr, now });
}
function place(d) {
  const { rise, set, prevSet, nextRise, now } = d;
  if (now >= rise && now <= set) return { ...d, phase: "day", progress: (now - rise) / (set - rise) };
  return now < rise ? { ...d, phase: "night", progress: clamp((now - prevSet) / (rise - prevSet), 0, 1) } : { ...d, phase: "night", progress: clamp((now - set) / (nextRise - set), 0, 1) };
}
// the arc: the sun's point for a day share p (0 sunrise … 1 sunset) and a night share q (0 sunset … 1 sunrise) – the same
// geometry draws the curves and places the sun, so the sun always lies on its line
export const ARC = { w: 320, h: 150, cx: 160, base: 92, r: 118, ry: 72, ryNight: 26 };
export const dayPoint = p => { const a = Math.PI * (1 - clamp(p, 0, 1)); return [ARC.cx + Math.cos(a) * ARC.r, ARC.base - Math.sin(a) * ARC.ry]; };
export const nightPoint = q => { const a = Math.PI * clamp(q, 0, 1); return [ARC.cx + Math.cos(a) * ARC.r, ARC.base + Math.sin(a) * ARC.ryNight]; };
function sunArc(model, T, lang, tz, now, geo) {
  const s = model.sun, day = sunDay({ now, tz, lat: geo && geo.lat, lon: geo && geo.lon, sun: s });
  if (!day && s.elevation == null) return "";
  const { w, h, cx, base, r, ry, ryNight } = ARC, L = cx - r, R = cx + r;
  const fmtT = t => (Number.isFinite(t) ? time(new Date(t).toISOString(), lang, null, tz) : "–");
  let marker = "", done = "", facts = [], labels = "";
  if (day && day.polar) {
    const p = day.phase === "day" ? dayPoint(0.5) : nightPoint(0.5);
    marker = `<circle class="sunpos${day.phase === "day" ? "" : " below"}" cx="${r3(p[0])}" cy="${r3(p[1])}" r="${day.phase === "day" ? 10 : 7}"/>`;
    if (day.phase === "day") done = `<path class="arc-done" d="M ${L} ${base} A ${r} ${ry} 0 0 1 ${R} ${base}"/>`;
    facts.push(`<div><b>${esc(day.polar === "day" ? T.polar_day : T.polar_night)}</b></div>`);
  } else if (day) {
    const p = day.phase === "day" ? dayPoint(day.progress) : nightPoint(day.progress);
    if (day.phase === "day") done = `<path class="arc-done" d="M ${L} ${base} A ${r} ${ry} 0 0 1 ${r3(p[0])} ${r3(p[1])}"/>`;
    marker = `<circle class="sunpos${day.phase === "day" ? "" : " below"}" data-progress="${r3(day.progress)}" data-phase="${day.phase}" cx="${r3(p[0])}" cy="${r3(p[1])}" r="${day.phase === "day" ? 10 : 7}"/>`;
    labels = `<text class="t-axis" x="${L + 4}" y="${base + 40}" text-anchor="middle">↑ ${esc(fmtT(day.rise))}</text><text class="t-axis" x="${R - 4}" y="${base + 40}" text-anchor="middle">↓ ${esc(fmtT(day.set))}</text>`;
    const len = day.set - day.rise;
    facts.push(`<div><span>${esc(T.day_length)}</span> ${Math.floor(len / 3600000)} h ${Math.round((len % 3600000) / 60000)} min</div>`);
    if (day.phase === "night") facts.push(`<div><span>${esc(T.next_rise)}</span> ${esc(fmtT(now > day.set ? day.nextRise : day.rise))}</div>`);
  }
  if (s.elevation != null) facts.push(`<div><span>${esc(T.sun_now)}</span> ${s.elevation > 0 ? `${fmt(s.elevation, 0, lang)}°` : esc(T.below)}</div>`);
  const aria = day && !day.polar ? `${T.sunrise} ${fmtT(day.rise)} · ${T.sunset} ${fmtT(day.set)}` : day ? (day.polar === "day" ? T.polar_day : T.polar_night) : T.sun;
  return `<section class="panel sun">${head("sun", T.sun)}<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(aria)}">
    <defs><linearGradient id="wxv-sunline" x1="0" x2="1"><stop offset="0" stop-color="#ff9a5c"/><stop offset=".5" stop-color="#ffe08a"/><stop offset="1" stop-color="#ff9a5c"/></linearGradient>
    <linearGradient id="wxv-sunsky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd27a" stop-opacity=".22"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></linearGradient></defs>
    <path class="sky-band" d="M ${L} ${base} A ${r} ${ry} 0 0 1 ${R} ${base} Z"/><path class="arc-path" d="M ${L} ${base} A ${r} ${ry} 0 0 1 ${R} ${base}"/>
    <path class="arc-night" d="M ${R} ${base} A ${r} ${ryNight} 0 0 1 ${L} ${base}"/>${done}
    <line class="horizon" x1="4" y1="${base}" x2="${w - 4}" y2="${base}"/>${marker}${labels}</svg>
    <div class="sunfacts">${facts.join("")}</div></section>`;
}
// the next hours: a soft temperature curve, rain as bars with their chance, the symbol of each step, now marked
function hourlyChart(model, lang, T, tz, max = 12) {
  const rows = model.hourly.filter(r => fin(r.temperature)).slice(0, max);
  if (rows.length < 2) return "";
  const w = 340, h = 168, top = 54, bottom = 116, temps = rows.map(r => num(r.temperature));
  const lo = Math.min(...temps), hi = Math.max(...temps), span = Math.max(hi - lo, 2);
  const X = i => 16 + i * ((w - 32) / (rows.length - 1)), Y = v => bottom - ((v - lo) / span) * (bottom - top);
  const pts = rows.map((r, i) => [X(i), Y(num(r.temperature))]);
  // a calm curve through every value (a monotone cubic: no overshoot above or below the real temperatures)
  const line = pts.map((p, i) => { if (!i) return `M ${r3(p[0])} ${r3(p[1])}`; const a = pts[i - 1], dx = (p[0] - a[0]) / 3; return `C ${r3(a[0] + dx)} ${r3(a[1])} ${r3(p[0] - dx)} ${r3(p[1])} ${r3(p[0])} ${r3(p[1])}`; }).join(" ");
  const fill = `${line} L ${r3(X(rows.length - 1))} ${bottom} L ${r3(X(0))} ${bottom} Z`;
  const night = isNight(model);
  let out = `<section class="panel hours">${head("hours", T.hourly)}<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(T.hourly)}"><defs><linearGradient id="wxv-temp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd27a"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></linearGradient></defs>`
    + `<line class="grid-l" x1="8" y1="${bottom}" x2="${w - 8}" y2="${bottom}"/><line class="nowmark" x1="${r3(X(0))}" y1="34" x2="${r3(X(0))}" y2="${bottom}"/>`
    + `<path class="curve-fill" d="${fill}"/><path class="curve" d="${line}"/>`;
  const every = rows.length > 8 ? 2 : 1;
  rows.forEach((r, i) => {
    const p = num(r.precipitation_probability), mm = num(r.precipitation);
    if (Number.isFinite(p) && p >= 5) out += `<rect class="bar" x="${r3(X(i) - 5)}" y="${r3(bottom + 6 + 18 * (1 - p / 100))}" width="10" height="${r3(18 * p / 100)}" rx="2.5"><title>${Math.round(p)} %${Number.isFinite(mm) ? ` · ${fmt(mm, 1, lang)} mm` : ""}</title></rect>`;
    if (i % every === 0) out += `<text class="t-val" x="${r3(X(i))}" y="${r3(Y(num(r.temperature)) - 9)}" text-anchor="middle">${Math.round(num(r.temperature))}°</text>`
      + weatherSvg(r.condition, { size: 20, night, at: [X(i) - 10, 6] })
      + `<text class="t-axis" x="${r3(X(i))}" y="${h - 4}" text-anchor="middle">${esc(time(r.datetime, lang, { hour: "2-digit" }, tz))}</text>`;
  });
  return `${out}</svg></section>`;
}
function dailyRows(model, lang, T, tz) {
  const rows = model.daily.filter(r => fin(r.temperature));
  if (!rows.length) return "";
  const lows = rows.map(r => (fin(r.templow) ? num(r.templow) : num(r.temperature))), lo = Math.min(...lows, ...(model.temperature != null ? [model.temperature] : [])), hi = Math.max(...rows.map(r => num(r.temperature)), ...(model.temperature != null ? [model.temperature] : [])), span = Math.max(hi - lo, 1);
  return `<section class="panel days-p">${head("days", T.daily)}<div class="days">${rows.map((r, i) => {
    const day = new Date(Date.parse(r.datetime)).toLocaleDateString(lang, { weekday: "short", timeZone: tz }), low = lows[i], high = num(r.temperature);
    const p = num(r.precipitation_probability), dot = i === 0 && model.temperature != null && model.temperature >= low - 3 && model.temperature <= high + 3 ? `<b style="left:${r3(clamp((model.temperature - lo) / span * 100, 0, 100))}%"></b>` : "";
    return `<div class="day"><span>${esc(day)}</span><span>${weatherSvg(r.condition, { size: 26 })}</span><span class="lo">${Math.round(low)}°</span><span class="range"><i style="left:${r3((low - lo) / span * 100)}%;right:${r3(100 - (high - lo) / span * 100)}%"></i>${dot}</span><span>${Math.round(high)}°</span><span class="rain">${Number.isFinite(p) && p >= 5 ? `${Math.round(p)} %` : ""}</span></div>`;
  }).join("")}</div></section>`;
}
// the wind as a compass rose: the arrow points where the air goes (it comes from the named direction), the speed in its middle,
// the Beaufort scale as a calm bar
function windRose(model, lang, T, compact) {
  if (model.windMs == null && model.bearing == null) return "";
  const s = 124, c = s / 2, b = model.bearing, ro = 50;
  const ticks = Array.from({ length: 16 }, (_, i) => { const a = i * Math.PI / 8, major = i % 4 === 0, r1 = major ? ro - 7 : ro - 4; return `<line class="tick${major ? " major" : ""}" x1="${r3(c + Math.sin(a) * r1)}" y1="${r3(c - Math.cos(a) * r1)}" x2="${r3(c + Math.sin(a) * ro)}" y2="${r3(c - Math.cos(a) * ro)}"/>`; }).join("");
  const arrow = b == null ? "" : `<g transform="rotate(${r3(b + 180)} ${c} ${c})"><path class="arrow" d="M ${c} ${c - 44} L ${c + 9} ${c - 24} L ${c + 3} ${c - 25} L ${c + 3} ${c + 36} L ${c - 3} ${c + 36} L ${c - 3} ${c - 25} L ${c - 9} ${c - 24} Z"/></g>`;
  const speed = model.windMs == null ? "–" : fmt(model.windMs * 3.6, 0, lang), bft = model.windMs == null ? null : beaufort(model.windMs);
  const labels = ["N", lang === "de" ? "O" : "E", "S", "W"].map((n, i) => `<text x="${r3(c + Math.sin(i * Math.PI / 2) * (ro + 8))}" y="${r3(c - Math.cos(i * Math.PI / 2) * (ro + 8) + 3.5)}" text-anchor="middle">${n}</text>`).join("");
  return `<section class="panel wind">${head("wind", T.wind)}<div class="windrow"><svg class="rose" viewBox="0 0 ${s} ${s}" role="img" aria-label="${esc(`${T.wind} ${b == null ? "" : `${T.from} ${compassPoint(b, lang)}`} ${speed} km/h`)}">
    <defs><linearGradient id="wxv-arrow" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe08a"/><stop offset="1" stop-color="#ff9a5c" stop-opacity=".5"/></linearGradient></defs>
    <circle class="ring" cx="${c}" cy="${c}" r="${ro}"/>${ticks}${labels}${arrow}<circle class="hub" cx="${c}" cy="${c}" r="17"/>
    <text class="spd" x="${c}" y="${c + 4}" text-anchor="middle">${esc(speed)}</text><text class="unit" x="${c}" y="${c + 12}" text-anchor="middle">km/h</text></svg>
    <div class="windtxt"><div class="w-big">${b == null ? esc(model.level ? T.level[model.level] : "–") : `${esc(T.from)} ${esc(compassPoint(b, lang))}`}</div>
    <div class="sub">${b == null ? "" : `${Math.round(b)}°`}${model.gustMs != null ? `${b == null ? "" : " · "}${T.gust} ${fmt(model.gustMs * 3.6, 0, lang)} km/h` : ""}</div>
    ${bft == null ? "" : `<div class="sub">${model.level ? esc(T.level[model.level]) : ""} · Bft ${bft}</div><div class="bft" aria-hidden="true">${Array.from({ length: 13 }, (_, i) => `<i class="${i < bft ? "on" : i === bft ? "cur" : ""}"></i>`).join("")}</div>`}
    ${model.own && Object.values(model.windSource || {}).includes("freshairiq") ? `<div class="sub" data-wind-fallback>${esc(T.wind_fallback)}</div>` : ""}</div></div></section>`;
}
const uvWord = (v, T) => T.uv_level[v < 3 ? 0 : v < 6 ? 1 : v < 8 ? 2 : v < 11 ? 3 : 4];
// The weather window: the present moment as the hero, then its values as calm tiles, the sun's day, the wind, the next hours and
// the next days – only what the card shows and only what the source really has (a missing value leaves its place out).
// ``details``: the single values the card shows (detailsFor); ``compact``: the side column of a wide house map.
export function overviewHtml(model, { lang = "en", info = DEFAULT_WEATHER_INFO, details = null, compact = false, now = Date.now(), forecastFailed = false, tz = undefined, geo = null } = {}) {
  const T = weatherText(lang), on = k => info.includes(k), show = details || detailsOf(info);
  if (!model) return "";
  const cond = model.condition ? (T.cond[model.condition] || model.condition) : null;
  const today = model.daily.length ? model.daily[0] : null, hiT = today && fin(today.temperature) ? num(today.temperature) : null, loT = today && fin(today.templow) ? num(today.templow) : null;
  const tile = (label, value, extra = "") => `<div class="fact"><span>${esc(label)}</span> <b>${value}</b>${extra}</div>`;
  const facts = [
    show.includes("apparent") && model.apparent != null ? tile(T.feels, `${fmt(model.apparent, 1, lang)} ${esc(model.tempUnit)}`) : null,
    show.includes("humidity") && model.humidity != null ? tile(T.humidity, `${Math.round(model.humidity)} %`, `<div class="meter"><span style="width:${r3(clamp(model.humidity, 0, 100))}%"></span></div>`) : null,
    show.includes("abs_humidity") && model.absHumidity != null ? tile(T.abs_humidity, `${fmt(model.absHumidity, 1, lang)} g/m³`) : null,
    show.includes("dew_point") && model.dewPoint != null ? tile(T.dew, `${fmt(model.dewPoint, 1, lang)} ${esc(model.tempUnit)}`) : null,
    show.includes("pressure") && model.pressure != null ? tile(T.pressure, `${Math.round(model.pressure)} hPa`) : null,
    show.includes("rain_chance") && model.rainChance != null ? tile(T.rain_chance, `${Math.round(model.rainChance)} %`) : null,
    show.includes("uv") && model.uv != null ? tile(T.uv, fmt(model.uv, 0, lang), ` <i>${esc(uvWord(model.uv, T))}</i>`) : null,
  ].filter(Boolean);
  const date = on("datetime") ? `<div class="sub">${esc(new Date(now).toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long", timeZone: tz }))} · ${esc(new Date(now).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit", timeZone: tz }))}</div>` : "";
  const big = show.includes("temperature") && model.temperature != null ? `<div class="big">${fmt(model.temperature, 1, lang)}<small> ${esc(model.tempUnit)}</small></div>` : "";
  const hilo = show.includes("temperature") && (hiT != null || loT != null) ? `<div class="hilo">${hiT != null ? `<span>↑ <b>${Math.round(hiT)}°</b></span>` : ""}${loT != null ? `<span>↓ <b>${Math.round(loT)}°</b></span>` : ""}</div>` : "";
  // 0.26.7.0(2) error B: the condition switched off draws no symbol at all – no fixed stand-in
  const icon = show.includes("condition") && hasSymbol(model.condition) ? `<span class="ico" aria-hidden="true">${weatherSvg(model.condition, { size: compact ? 64 : 92, night: isNight(model) })}</span>` : "";
  const heroInner = `${big}${show.includes("condition") && cond ? `<div class="cond">${esc(cond)}</div>` : ""}${hilo}${date}`;
  let out = icon || heroInner ? `<div class="now${icon ? "" : " solo"}" style="--wx-glow:${GLOW[model.condition] || "rgba(201,243,255,.18)"}">${icon}<div>${heroInner}</div></div>` : "";
  if (facts.length) out += `<div class="facts">${facts.join("")}</div>`;
  if (!model.entityId) out += `<div class="sub">${esc(T.no_entity)}</div>`;
  else if (!model.available) out += `<div class="sub">${esc(T.unavailable)}</div>`;
  if (on("sun")) out += sunArc(model, T, lang, tz, now, geo);
  if (on("wind")) out += windRose(model, lang, T, compact);
  if (on("hourly")) out += hourlyChart(model, lang, T, tz, compact ? 8 : 12);
  if (on("daily") && !compact) out += dailyRows(model, lang, T, tz);
  if (model.entityId && (on("hourly") || on("daily")) && !model.hourly.length && !model.daily.length && forecastFailed) out += `<div class="sub">${esc(T.no_forecast)}</div>`;
  return `<div class="wxv${compact ? " compact" : ""}">${out}</div>`;
}
// The items of the small weather display at the top right (``items`` from chipFor, in the card's order): each [key, html, title].
// ``outdoor``: FreshAirIQ's own outdoor reading (temperature, humidity) – used first unless the card names its own entity.
export function chipItems(model, { items = DEFAULT_CHIP, lang = "en", tz = undefined, outdoor = {}, own = false, now = Date.now() } = {}) {
  const T = weatherText(lang), out = [];
  const temp = !own && fin(outdoor.temperature) ? num(outdoor.temperature) : model && model.temperature != null ? model.temperature : fin(outdoor.temperature) ? num(outdoor.temperature) : null;
  const hum = !own && fin(outdoor.humidity) ? num(outdoor.humidity) : model && model.humidity != null ? model.humidity : fin(outdoor.humidity) ? num(outdoor.humidity) : null;
  for (const key of items) {
    if (key === "temperature" && temp != null) out.push([key, `🌡️ ${fmt(temp, 1, lang)} °C`, lang === "de" ? "Außentemperatur" : "Outdoor temperature"]);
    else if (key === "condition" && model && hasSymbol(model.condition)) out.push([key, weatherSvg(model.condition, { size: 18, night: isNight(model), label: T.cond[model.condition] || model.condition }), T.cond[model.condition] || model.condition]);
    else if (key === "humidity" && hum != null) out.push([key, `💧 ${Math.round(hum)} %`, lang === "de" ? "Luftfeuchte außen" : "Outdoor humidity"]);
    else if (key === "abs_humidity" && model && model.absHumidity != null) out.push([key, `💧 ${fmt(model.absHumidity, 1, lang)} g/m³`, T.abs_humidity_out]);
    else if (key === "wind" && model && model.windMs != null) out.push([key, `🍃 ${model.bearing != null ? `${esc(compassPoint(model.bearing, lang))} ` : ""}${fmt(model.windMs * 3.6, 0, lang)} km/h`, T.wind]);
    else if (key === "rain" && model && (model.rainChance != null || model.precip.kind)) out.push([key, `☔ ${model.rainChance != null ? `${Math.round(model.rainChance)} %` : esc(T.cond[model.condition] || T.rain)}`, T.rain_chance]);
    else if (key === "apparent" && model && model.apparent != null) out.push([key, `${esc(T.feels)} ${fmt(model.apparent, 0, lang)}°`, T.feels]);
    else if (key === "pressure" && model && model.pressure != null) out.push([key, `${Math.round(model.pressure)} hPa`, T.pressure]);
    else if (key === "sun" && model && model.sun.elevation != null) { const up = model.sun.elevation > 0, at = up ? model.sun.setting : model.sun.rising; if (at) out.push([key, `${up ? "☀️ ↓" : "🌅 ↑"} ${esc(time(at, lang, null, tz))}`, up ? T.sunset : T.sunrise]); }
    else if (key === "datetime") out.push([key, esc(`${new Date(now).toLocaleDateString(lang, { weekday: "short", timeZone: tz })} ${new Date(now).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit", timeZone: tz })}`), lang === "de" ? "Datum und Uhrzeit" : "Date and time"]);
  }
  return out;
}
// A small compass rose on the plan: where north is on this drawing (the plan's own rotation)
export function compassSvg(northDeg, at, px, lang) {
  const r = px(15), n = planVector(0, northDeg), x = at[0], y = at[1];
  return `<g class="compass" role="img" aria-label="${lang === "de" ? "Norden" : "North"}"><circle cx="${r3(x)}" cy="${r3(-y)}" r="${r3(r)}" fill="rgba(2,16,36,.55)" stroke="rgba(201,243,255,.5)" stroke-width="${px(1.5)}"/>`
    + `<path d="M ${P([x + n[0] * r * 0.8, y + n[1] * r * 0.8])} L ${P([x - n[1] * r * 0.28, y + n[0] * r * 0.28])} L ${P([x + n[1] * r * 0.28, y - n[0] * r * 0.28])} Z" fill="#ff8f5c"/>`
    + `<text x="${r3(x + n[0] * r * 1.55)}" y="${r3(-(y + n[1] * r * 1.55) + px(4))}" text-anchor="middle" font-size="${px(11)}" font-weight="900" fill="#fff">N</text></g>`;
}
