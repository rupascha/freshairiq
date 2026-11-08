// FreshAirIQ house map – its windows (0.26.7.0(2)): the rooms overview, a room's details, the house's details ("more about the
// decision") and the menu. Everything shown here is what FreshAirIQ publishes (the same values the FreshAirIQ dashboard card shows),
// told in the house map's own style: the sky as background, calm glass tiles, the state colours of the plan. A missing value
// leaves its place out – nothing is estimated here. The card passes itself (``c``) and its helpers (``H``).

const Q = new URL(import.meta.url).search;
const V = await import(new URL(`./freshairiq-house-view.js${Q}`, import.meta.url).href);
const W = await import(new URL(`./freshairiq-house-weather.js${Q}`, import.meta.url).href);

const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
const num = v => (v == null || v === "" || typeof v === "boolean" ? NaN : Number(v));
const fin = v => Number.isFinite(num(v));

export const TXT = {
  de: {
    rooms_open: "Details öffnen", show_on_plan: "Im Grundriss zeigen", no_data: "Noch keine Raumdaten", removable: "entfernbar", added: "würde eintragen",
    sec_why: "Warum?", sec_climate: "Raumklima", sec_wall: "Wand & Schimmel", sec_forecast: "Feuchte & Prognose", sec_air: "Luftaustausch", sec_source: "Feuchtequelle",
    sec_fan: "Ablüfter", sec_learning: "Lernen", sec_openings: "Fenster & Türen", sec_model: "Raummodell", sec_extra: "Zusatzsensoren (ohne Einfluss auf die Lüftung)",
    temp: "Temperatur", target: "Ziel", rh: "Relative Feuchte", ah: "Absolute Feuchte", water: "Wasser in der Luft", co2: "CO₂", surface: "Wandfeuchte (Oberfläche)",
    mould: "Schimmelrisiko", src_mold: "aus dem Schimmel-Indikator", src_est: "geschätzt aus der Wandtemperatur", horizon: "In {m} Minuten",
    potential: "Realistisch entfernbar", so_far: "Bisher entfernt", left: "Restzeit", exchanged: "Luft ausgetauscht", to95: "bis 95 %", passive: "Passive Lüftung (geschätzt)",
    rate: "Lernrate", samples: "Lernproben", status: "Stand", last_learn: "Letzte Lernmessung", success: "Erfolgsquote", volume: "Volumen", floor: "Etage", quality: "Datenqualität",
    q_ok: "in Ordnung", q_bad: "eingeschränkt", min: "min", not_measured: "nicht gemessen", estimate: "Schätzung", delay: "Verzögerung", s: "s", none: "Keine Kontakte zugeordnet.",
    voc: "VOC", pm25: "Feinstaub PM2.5", lux: "Helligkeit",
    theoretical: "Theoretisch entfernbar", cost: "Kosten (Prognose)", airflow: "Luftstromfaktor", last_meas: "Letzte Messung", meas_ok: "Messwerte plausibel", meas_bad: "Messwerte unplausibel",
    diag: "Letzte Lernmessung", feedback: "Rückmeldung Realität", feedback_sub: "{n} Vergleiche · Feuchtefaktor {f}", shadow: "Shadow-Lernen", shadow_sub: "Übernahmen {p} · Rollbacks {r}", rollback: "Rollback-Schutz aktiv",
    routine: "Routine-IQ", routine_sub: "{n} Zeitmuster-Proben", routine_now: "erwartet {v} ml/h", strategy: "Strategie-IQ", strategy_sub: "{n} Empfehlungen ausgewertet · {o} Ergebnisse",
    sec_days: "Bilanz der letzten {d} Tage", days_removed: "Feuchte entfernt", days_sessions: "Lüftungen", days_minutes: "Lüftungsminuten", days_cost: "Kosten",
    monitor: "Nur anzeigen: der Raum ist von Empfehlungen, Prognosen, Hausbilanz und Lernen ausgenommen.",
    more_title: "Hintergründe", learn_title: "Lernen & Prognosequalität", learn_sub: "Aktuell lernt FreshAirIQ, Prognosegüte, Formelvergleich", back: "Zurück",
    cl: { decision: ["IQ-Entscheidung", "die Gründe im Einzelnen"], water: ["Wasser in der Hausluft", "je Raum"], threshold: ["Lüftungsschwelle", "wie sie entsteht"], night: ["Nachtprognose", "Bewohner, Gäste, Nachtmodell"],
      pollen: ["Pollen", "Bewertung und Grenze"], lastvent: ["Letzte Lüftung", "Ergebnis"], "learning:quality": ["Wie gut FreshAirIQ vorhersagt", "Prognosegüte, Lernwirkung, Formelvergleich"] },
    details_title: "Mehr zur Entscheidung", decision: "Entscheidung", house_now: "Haus jetzt", water_air: "Wasser in der Hausluft", threshold: "Lüftungsschwelle",
    night: "Nachtprognose", pollen: "Pollen", pollen_off: "nicht berücksichtigt", people: "Personen zuhause", learning: "Lernstand", last_vent: "Letzte Lüftung",
    history: "Wasser in der Hausluft · letzte Tage", learn_rooms: "{n} von {m} Räumen stabil", learn_samples: "{n} Lernproben", forecast: "Prognose {m} min",
    menu_info: "Informationen", menu_control: "Steuerung & Modi", menu_tools: "Werkzeuge", menu_notes: "Hinweise", menu_details: "Mehr zur Entscheidung",
    menu_details_sub: "Empfehlung, Begründung, Hauswerte", menu_moist: "Entfernbare Feuchtigkeit", menu_moist_sub: "nach Räumen", menu_weather: "Wetter",
    menu_weather_sub: "aktuell, Sonne, Wind, Prognosen", menu_rooms: "Räume", menu_rooms_sub: "alle Räume dieser Etagen",
    menu_motion: "Animation", menu_edit: "Grundriss bearbeiten", menu_edit_sub: "Räume, Fenster, Türen", menu_support: "Support", menu_support_sub: "Diagnose, Feedback, Hilfe",
    menu_log: "Lüftungsprotokoll", menu_log_sub: "PDF oder CSV für einen Zeitraum", log_title: "Lüftungsprotokoll", log_from: "Von", log_to: "Bis", log_daily: "Pro Tag zusammenfassen",
    log_pdf: "PDF erstellen", log_csv: "CSV", log_hint: "FreshAirIQ protokolliert abgeschlossene Lüftungen lokal in Home Assistant – eine Sensordokumentation, keine rechtliche Bewertung.",
    motion: { off: "Aus", minimal: "Minimal", normal: "Normal", intense: "Intensiv", auto: "Auto", rest: "ruht (lange unberührt)" }, motion_now: "gerade: {v}",
  },
  en: {
    rooms_open: "Open details", show_on_plan: "Show on the plan", no_data: "No room data yet", removable: "removable", added: "would add",
    sec_why: "Why?", sec_climate: "Room climate", sec_wall: "Wall & mould", sec_forecast: "Moisture & forecast", sec_air: "Air exchange", sec_source: "Moisture source",
    sec_fan: "Exhaust fan", sec_learning: "Learning", sec_openings: "Windows & doors", sec_model: "Room model", sec_extra: "Extra sensors (no influence on the airing)",
    temp: "Temperature", target: "target", rh: "Relative humidity", ah: "Absolute humidity", water: "Water in the air", co2: "CO₂", surface: "Wall humidity (surface)",
    mould: "Mould risk", src_mold: "from the mould indicator", src_est: "estimated from the wall temperature", horizon: "In {m} minutes",
    potential: "Realistically removable", so_far: "Removed so far", left: "Time left", exchanged: "Air exchanged", to95: "to 95 %", passive: "Passive airing (estimated)",
    rate: "Learned rate", samples: "Learning samples", status: "State", last_learn: "Last learning measurement", success: "Success rate", volume: "Volume", floor: "Floor", quality: "Data quality",
    q_ok: "fine", q_bad: "limited", min: "min", not_measured: "not measured", estimate: "estimate", delay: "delay", s: "s", none: "No contacts assigned.",
    voc: "VOC", pm25: "Fine dust PM2.5", lux: "Brightness",
    theoretical: "Theoretically removable", cost: "Cost (forecast)", airflow: "Airflow factor", last_meas: "Last measurement", meas_ok: "readings plausible", meas_bad: "readings implausible",
    diag: "Last learning measurement", feedback: "Feedback from reality", feedback_sub: "{n} comparisons · moisture factor {f}", shadow: "Shadow learning", shadow_sub: "promotions {p} · rollbacks {r}", rollback: "rollback protection active",
    routine: "Routine IQ", routine_sub: "{n} time-pattern samples", routine_now: "expected {v} ml/h", strategy: "Strategy IQ", strategy_sub: "{n} recommendations evaluated · {o} outcomes",
    sec_days: "Balance of the last {d} days", days_removed: "Moisture removed", days_sessions: "Airings", days_minutes: "Airing minutes", days_cost: "Cost",
    monitor: "Display only: the room is excluded from recommendations, forecasts, the house balance and learning.",
    more_title: "Background", learn_title: "Learning & forecast quality", learn_sub: "What FreshAirIQ is learning now, forecast quality, formula comparison", back: "Back",
    cl: { decision: ["IQ decision", "every reason"], water: ["Water in the house air", "by room"], threshold: ["Airing threshold", "how it is set"], night: ["Night forecast", "occupants, guests, night model"],
      pollen: ["Pollen", "assessment and limit"], lastvent: ["Last airing", "its result"], "learning:quality": ["How well FreshAirIQ forecasts", "forecast quality, learning effect, formula comparison"] },
    details_title: "More about the decision", decision: "Decision", house_now: "House now", water_air: "Water in the house air", threshold: "Airing threshold",
    night: "Night forecast", pollen: "Pollen", pollen_off: "not considered", people: "People at home", learning: "Learning", last_vent: "Last airing",
    history: "Water in the house air · last days", learn_rooms: "{n} of {m} rooms stable", learn_samples: "{n} learning samples", forecast: "Forecast {m} min",
    menu_info: "Information", menu_control: "Control & modes", menu_tools: "Tools", menu_notes: "Notes", menu_details: "More about the decision",
    menu_details_sub: "recommendation, reasons, house values", menu_moist: "Removable moisture", menu_moist_sub: "by room", menu_weather: "Weather",
    menu_weather_sub: "now, sun, wind, forecasts", menu_rooms: "Rooms", menu_rooms_sub: "every room of these floors",
    menu_motion: "Animation", menu_edit: "Edit floor plan", menu_edit_sub: "rooms, windows, doors", menu_support: "Support", menu_support_sub: "diagnostics, feedback, help",
    menu_log: "Airing log", menu_log_sub: "PDF or CSV for a period", log_title: "Airing log", log_from: "From", log_to: "To", log_daily: "Summarise per day",
    log_pdf: "Create PDF", log_csv: "CSV", log_hint: "FreshAirIQ logs finished airings locally in Home Assistant – a sensor record, not a legal assessment.",
    motion: { off: "Off", minimal: "Minimal", normal: "Normal", intense: "Intense", auto: "Auto", rest: "resting (long untouched)" }, motion_now: "now: {v}",
  },
};
const tx = c => TXT[c._lang() === "de" ? "de" : "en"];
const n = (c, v, d) => (fin(v) ? num(v).toFixed(d).replace(".", c._lang() === "de" ? "," : ".") : null);
// one value tile: label, value, a quiet line below; nothing at all when the value is missing
const tile = (label, value, sub = "", cls = "") => (value == null || value === "" ? "" : `<div class="ptile tile${cls ? ` ${cls}` : ""}"><span>${esc(label)}</span><strong>${value}</strong>${sub ? `<i>${sub}</i>` : ""}</div>`);
const section = (title, body, cls = "") => (body ? `<section class="psec${cls ? ` ${cls}` : ""}"><h4>${esc(title)}</h4>${body}</section>` : "");
const grid = tiles => { const inner = tiles.filter(Boolean).join(""); return inner ? `<div class="pgrid">${inner}</div>` : ""; };
const CHEVRON = `<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5 L16 12 L9 19" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
// the learning diagnosis in the FreshAirIQ card's own wording (freshairiq-card.js, diagnosisDE)
const diagnosis = (value, lang) => (lang !== "de" ? String(value || "No learning measurement yet") : String(value || "Noch keine Lernmessung").replace(/^Learned:/, "Gelernt:").replace(/^Rejected:/, "Verworfen:").replace(/^Paused:/, "Pausiert:")
  .replace("No learning session evaluated yet", "Noch keine Lernsession ausgewertet").replace("learning disabled", "Lernmodus deaktiviert").replace("duration", "Dauer").replace("start delta", "Startdifferenz")
  .replace("humidity reduction", "Feuchteabbau").replace("learning rate", "Lernrate").replace("sample", "Probe").replace("reduction", "Abbau").replace("rate", "Rate"));
const MOULD_DOT = { "Low": "#67df92", "Slightly elevated": "#ffd27a", "Elevated": "#ffb347", "High": "#ff8f5c", "Very high": "#ff6b6b" };

// ------------------------------------------------------------------------------------------------------ the rooms overview
// Every room of the shown floors as one card: the whole card is the button (no second control beside it); name, floor, the
// recommendation in the plan's state colour, temperature, relative and absolute humidity, mould risk and the removable moisture.
export function roomsBody(c, H, layout) {
  const t = tx(c), lang = c._lang(), rows = [];
  for (const f of c._floors(layout)) {
    const items = layout.rooms.filter(r => r.floor_id === f.id).map(lr => {
      const room = c._rooms[lr.room_key], tone = H.roomTone(room), name = (room && room.name) || lr.room_key, color = V.TONE_COLOR[tone];
      if (!room) return `<button class="rrow rcard t-${tone}" data-room-open="${esc(lr.id)}" style="--tone:${color}"><span class="rtop"><b>${esc(name)}</b><span class="rfloor">${c._floorName(f)}</span>${CHEVRON}</span><span class="rsub">${esc(t.no_data)}</span></button>`;
      const ml = room.active ? num(room.result_ml) : num(room.realistic_potential_ml);
      const mould = H.T[lang].mould_short[room.mould_level];
      const vals = [
        fin(room.temperature) ? `<span class="rv"><em>🌡️</em>${n(c, room.temperature, 1)} °C</span>` : "",
        fin(room.humidity) ? `<span class="rv"><em>💧</em>${n(c, room.humidity, 0)} %</span>` : "",
        fin(room.absolute_humidity) ? `<span class="rv">${n(c, room.absolute_humidity, 1)} g/m³</span>` : "",
        mould ? `<span class="rv"><i class="mdot" style="background:${MOULD_DOT[room.mould_level] || "#cfe6ff"}"></i>${esc(c._t("mould"))}: ${esc(mould)}</span>` : "",
        Number.isFinite(ml) && Math.abs(ml) >= 1 ? `<span class="rv rml">${ml < 0 ? "+" : "≈ "}${Math.abs(Math.round(ml))} ml <small>${esc(ml < 0 ? t.added : t.removable)}</small></span>` : "",
      ].join("");
      return `<button class="rrow rcard t-${tone}" data-room-open="${esc(lr.id)}" style="--tone:${color}" aria-label="${esc(`${name}, ${c._actionWord(room)}`)}">`
        + `<span class="rtop"><b>${esc(name)}</b><span class="rfloor">${c._floorName(f)}</span>${CHEVRON}</span>`
        + `<span class="ract">${esc(c._actionWord(room))}</span><span class="rvals">${vals}</span></button>`;
    });
    if (items.length) rows.push(`<h4>${c._floorName(f)}</h4><div class="rlist">${items.join("")}</div>`);
  }
  return rows.join("") || `<p>${esc(c._t("rooms_none"))}</p>`;
}

// ------------------------------------------------------------------------------------------------------ a room's details
// What the FreshAirIQ card shows for a room, in the house map's style: the recommendation and why, the climate, wall and mould,
// moisture and forecast, the air exchange, a moisture source, the fan, learning, windows and doors, the room model, extra sensors.
export function roomBody(c, H, layout, lr, room) {
  const t = tx(c), lang = c._lang(), T = H.T[lang];
  const reasons = (Array.isArray(room.recommendation_reasons) ? room.recommendation_reasons : []).filter(Boolean).map(String);
  const monitor = room.calculation_enabled === false ? `<div class="pnote">${esc(t.monitor)}</div>` : "";
  const why = `${monitor}<div class="why"><b>${esc(c._t("reason"))}:</b> ${esc(room.reason || "–")}</div>${reasons.length ? `<ul class="reasons">${reasons.slice(0, 6).map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}`;
  const climate = grid([
    tile(t.temp, fin(room.temperature) ? `${n(c, room.temperature, 1)} °C` : null, fin(room.comfort_target_c) ? `${esc(t.target)} ${n(c, room.comfort_target_c, 1)} °C` : ""),
    tile(t.rh, fin(room.humidity) ? `${n(c, room.humidity, 0)} %` : null, fin(room.humidity_trend_pct_h) && Math.abs(num(room.humidity_trend_pct_h)) >= 1 ? `${num(room.humidity_trend_pct_h) > 0 ? "↑" : "↓"} ${n(c, Math.abs(num(room.humidity_trend_pct_h)), 0)} %/h` : ""),
    tile(t.ah, fin(room.absolute_humidity) ? `${n(c, room.absolute_humidity, 2)} g/m³` : null),
    tile(t.water, fin(room.water_in_air_ml) ? `${Math.round(num(room.water_in_air_ml))} ml` : null),
    tile(t.co2, fin(room.co2) ? `${Math.round(num(room.co2))} ppm` : null),
  ]);
  const src = room.surface_rh_source === "ha_mold_indicator" ? t.src_mold : fin(room.surface_rh) ? t.src_est : "";
  const mouldWord = T[`mould_${String(room.mould_level || "").replace(/ /g, "_").toLowerCase()}`] || T.mould_short[room.mould_level] || room.mould_level;
  const wall = grid([
    tile(t.surface, fin(room.surface_rh) ? `${n(c, room.surface_rh, 0)} %` : null, esc(src)),
    tile(t.mould, mouldWord ? `<i class="mdot" style="background:${MOULD_DOT[room.mould_level] || "#cfe6ff"}"></i>${esc(mouldWord)}` : null, H.mouldWarning(room) ? esc(c._t("mould_warn")) : "", H.mouldWarning(room) ? "warn" : ""),
  ]);
  const next = num(room.moisture_effect_next_5_min_ml), fc = num(room.forecast_moisture_effect_ml), hz = num(room.forecast_horizon_min);
  const sign = v => `${v > 0 ? "−" : v < 0 ? "+" : "±"}${Math.abs(Math.round(v))} ml`;
  const target = num(room.session_target_min ?? room.session_recommended_duration_min), elapsed = num(room.session_elapsed_min);
  const forecast = grid([
    // re-audit F04: an unknown forecast reads "–" (never a made-up 0) – this one tile always stands, the others leave their place
    tile(c._t("tile_next5"), Number.isFinite(next) ? sign(next) : "–", fin(room.temp_next_5_min_c) ? `${n(c, room.temp_next_5_min_c, 1)} °C` : ""),
    Number.isFinite(fc) && Number.isFinite(hz) && hz !== 5 ? tile(t.horizon.replace("{m}", Math.round(hz)), sign(fc), fin(room.forecast_temperature_change_c) ? `${num(room.forecast_temperature_change_c) > 0 ? "+" : ""}${n(c, room.forecast_temperature_change_c, 1)} °C` : "") : "",
    room.active ? tile(t.so_far, fin(room.result_ml) ? `${num(room.result_ml) < 0 ? "+" : "≈ "}${Math.abs(Math.round(num(room.result_ml)))} ml` : null) : tile(t.potential, fin(room.realistic_potential_ml) ? `${num(room.realistic_potential_ml) < 0 ? "+" : "≈ "}${Math.abs(Math.round(num(room.realistic_potential_ml)))} ml` : null),
    room.active && Number.isFinite(target) && Number.isFinite(elapsed) ? tile(t.left, `${Math.max(0, Math.ceil(target - elapsed))} ${esc(t.min)}`) : "",
    // 0.26.7.0(2) parity with the FreshAirIQ card: the theoretical amount and the forecast's cost
    fin(room.potential_ml) ? tile(t.theoretical, `${num(room.potential_ml) < 0 ? "+" : "≈ "}${Math.abs(Math.round(num(room.potential_ml)))} ml`) : "",
    fin(room.forecast_cost) && num(room.forecast_cost) > 0 ? tile(t.cost, `${n(c, room.forecast_cost, 2)} €`) : "",
  ]);
  const ax = room.air_exchange || {}, pv = num(room.passive_ventilation_estimated_ml);
  const air = grid([
    room.active && fin(ax.exchanged_percent) ? tile(t.exchanged, `${Math.round(num(ax.exchanged_percent))} %`, fin(ax.minutes_to_95) && num(ax.exchanged_percent) < 95 ? `${esc(t.to95)}: ${Math.max(1, Math.round(num(ax.minutes_to_95)))} ${esc(t.min)}` : esc(t.estimate)) : "",
    room.passive_ventilation_active && Number.isFinite(pv) ? tile(t.passive, `≈ ${Math.round(pv)} ml`) : "",
  ]);
  const source = room.moisture_source_active ? `<div class="pnote">💧 <b>${esc(room.moisture_source_label || c._t("source_on"))}</b>${room.moisture_source_message ? ` – ${esc(room.moisture_source_message)}` : ""}${fin(room.moisture_source_rate_ml_min) ? ` · ${n(c, room.moisture_source_rate_ml_min, 1)} ml/min` : ""}</div>` : "";
  const fan = room.fan_automation ? grid([tile(c._t("tile_fan"), esc(room.fan_automation.label || "–"), esc(H.fanCountdown(room.fan_automation, Date.now(), k => c._t(k), lang)))]) : "";
  const learning = grid([
    tile(t.samples, fin(room.learning_samples) ? String(Math.round(num(room.learning_samples))) : null, room.learning_status ? esc(room.learning_status) : ""),
    tile(t.rate, fin(room.learned_exchange_rate_per_min) ? `${n(c, room.learned_exchange_rate_per_min, 3)}/min` : null),
    tile(t.last_learn, room.last_learning_at ? esc(new Date(room.last_learning_at).toLocaleString(lang, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: W.haTimeZone(c._hass) })) : null),
    tile(t.success, fin(room.outcome_success_rate) ? `${Math.round(num(room.outcome_success_rate) * (num(room.outcome_success_rate) <= 1 ? 100 : 1))} %` : null),
    // 0.26.7.0(2) parity with the FreshAirIQ card: feedback from reality, shadow learning, routine and strategy
    num(room.outcome_feedback_samples) > 0 ? tile(t.feedback, `${Math.round(num(room.outcome_success_rate) * (num(room.outcome_success_rate) <= 1 ? 100 : 1)) || 0} %`, esc(t.feedback_sub.replace("{n}", Math.round(num(room.outcome_feedback_samples))).replace("{f}", n(c, fin(room.outcome_removed_factor) ? room.outcome_removed_factor : 1, 2)))) : "",
    room.shadow_learning_status ? tile(t.shadow, esc(room.shadow_rollback_active ? t.rollback : room.shadow_learning_status), esc(t.shadow_sub.replace("{p}", Math.round(num(room.shadow_learning_promotions) || 0)).replace("{r}", Math.round(num(room.shadow_learning_rollbacks) || 0)))) : "",
    fin(room.routine_maturity) ? tile(t.routine, `${n(c, room.routine_maturity, 0)} %`, esc(t.routine_sub.replace("{n}", Math.round(num(room.routine_source_samples) || 0)) + (fin(room.routine_expected_source_ml_min) ? ` · ${t.routine_now.replace("{v}", Math.round(num(room.routine_expected_source_ml_min) * 60))}` : ""))) : "",
    fin(room.strategy_maturity) ? tile(t.strategy, `${n(c, room.strategy_maturity, 0)} %`, esc(t.strategy_sub.replace("{n}", Math.round(num(room.strategy_samples) || 0)).replace("{o}", Math.round(num(room.strategy_outcome_samples) || 0)))) : "",
  ]);
  const diagText = room.learning_diagnosis ? `<div class="pnote${room.last_learning_valid === false ? " bad" : room.last_learning_valid === true ? " good" : ""}"><b>${esc(t.diag)}:</b> ${esc(diagnosis(room.learning_diagnosis, lang))}</div>` : "";
  const hist = Array.isArray(room.history_14d) ? room.history_14d : [];
  const sum = hist.reduce((a, x) => ({ removed: a.removed + (num(x.removed_ml) || 0), sessions: a.sessions + (num(x.sessions) || 0), mins: a.mins + (num(x.ventilation_minutes) || 0), cost: a.cost + (num(x.cost) || 0) }), { removed: 0, sessions: 0, mins: 0, cost: 0 });
  const days = hist.length ? grid([
    tile(t.days_removed, `${sum.removed > 0 ? "−" : sum.removed < 0 ? "+" : "±"}${n(c, Math.abs(sum.removed) / 1000, 2)} l`), tile(t.days_sessions, String(Math.round(sum.sessions))),
    tile(t.days_minutes, String(Math.round(sum.mins))), sum.cost > 0 ? tile(t.days_cost, `${n(c, sum.cost, 2)} €`) : "",
  ]) : "";
  const live = c._house && c._house.rooms ? c._house.rooms[lr.room_key] : null;
  const orient = room.contact_orientations || {};
  const contacts = live ? Object.entries(live.contacts || {}).map(([id, ct]) => {
    const name = (c._hass && c._hass.states && c._hass.states[id] && c._hass.states[id].attributes && c._hass.states[id].attributes.friendly_name) || id;
    const state = ct.pending ? c._t("st_pending") : c._t(`st_${ct.state}`), open = ["open", "tilted", "open_unspecified"].includes(ct.state);
    return `<li class="${open ? "open" : ""}"><span>${esc(name)}</span><b>${esc(state)}</b>${ct.delay_s ? `<i>${esc(t.delay)} ${ct.delay_s} ${esc(t.s)}</i>` : ""}${orient[id] != null ? `<i>${esc(String(orient[id]))}</i>` : ""}</li>`;
  }).join("") : "";
  const floor = (layout.floors || []).find(f => f.id === lr.floor_id);
  const model = grid([tile(t.floor, floor ? c._floorName(floor) : null), tile(t.volume, fin(room.volume_m3) ? `${n(c, room.volume_m3, 1)} m³` : null), tile(t.quality, room.data_quality ? esc(room.data_quality === "ok" ? t.q_ok : t.q_bad) : null),
    tile(t.airflow, fin(room.airflow_factor) ? n(c, room.airflow_factor, 2) : null),
    tile(t.last_meas, room.last_measurement_at ? esc(new Date(room.last_measurement_at).toLocaleString(lang, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: W.haTimeZone(c._hass) })) : null, room.last_measurement_valid === false ? esc(t.meas_bad) : room.last_measurement_valid === true ? esc(t.meas_ok) : "", room.last_measurement_valid === false ? "warn" : "")]);
  const extra = grid([
    room.voc_configured ? tile(t.voc, room.voc_available ? n(c, room.voc, 0) : "–") : "",
    room.pm25_configured ? tile(t.pm25, room.pm25_available ? `${n(c, room.pm25, 1)} µg/m³` : "–") : "",
    room.illuminance_configured ? tile(t.lux, room.illuminance_available ? `${n(c, room.illuminance, 0)} lx` : "–") : "",
  ]);
  return section(t.sec_why, why, "why-s") + section(t.sec_climate, climate) + section(t.sec_wall, wall) + section(t.sec_forecast, forecast) + section(t.sec_air, air)
    + section(t.sec_source, source) + section(t.sec_fan, fan) + section(t.sec_learning, `${learning}${diagText}`) + section(t.sec_days.replace("{d}", hist.length), days)
    + section(t.sec_openings, contacts ? `<ul class="contacts">${contacts}</ul>` : `<p class="pmuted">${esc(t.none)}</p>`) + section(t.sec_model, model) + section(t.sec_extra, extra)
    + `<div class="pactions"><button class="small" data-room-jump="${esc(lr.id)}">⌖ ${esc(t.show_on_plan)}</button></div>`;
}

// ------------------------------------------------------------------------------------------------- more about the decision
// The house as the FreshAirIQ card's details tell it: the recommendation with its reason, removable moisture and the forecast,
// the water in the house air (with its last days), the airing threshold, the night forecast, pollen, people at home, learning
// and the last airing.
export function houseBody(c, H, layout) {
  const t = tx(c), p = c._payload || {}, lang = c._lang();
  const rec = p.intelligent_recommendation && typeof p.intelligent_recommendation === "object" ? p.intelligent_recommendation : {};
  const tone = H.heroTone(rec), f = c._moistureFacts();
  const decision = rec.title ? `<div class="bubble" data-tone="${tone}" style="border-left:8px solid ${V.TONE_COLOR[tone]}"><span class="emo">${V.TONE_EMOJI[tone]}</span><div>${esc(rec.title)}${rec.instruction || rec.summary ? `<small>${esc(rec.instruction || rec.summary)}</small>` : ""}</div></div>` : "";
  const reasons = (Array.isArray(rec.reasons) ? rec.reasons : []).filter(Boolean).map(String);
  const rooms = Object.values(c._rooms || {}).filter(r => r && typeof r === "object" && r.calculation_enabled !== false && r.data_quality === "ok");
  const samples = rooms.reduce((s, r) => s + (num(r.learning_samples) || 0), 0), stable = rooms.filter(r => num(r.learning_samples) >= 25).length;
  const hz = num(p.forecast_horizon_min), fcm = num(p.forecast_moisture_effect_ml), night = num(p.overnight_forecast_ml);
  const sign = v => `${v > 0 ? "−" : v < 0 ? "+" : "±"}${Math.abs(Math.round(v))} ml`;
  const now = grid([
    f ? tile(c._t(f.live ? "moist_so_far" : "moist_now"), f.amount <= -1 ? `+${Math.abs(f.amount)} ml` : `≈ ${Math.max(f.amount, 0)} ml`, f.minutes != null ? `⏱ ${f.minutes} ${esc(c._t("min_short"))}` : "") : "",
    Number.isFinite(fcm) ? tile(t.forecast.replace("{m}", Number.isFinite(hz) ? Math.round(hz) : 5), sign(fcm), fin(p.forecast_temperature_change_c) ? `${num(p.forecast_temperature_change_c) > 0 ? "+" : ""}${n(c, p.forecast_temperature_change_c, 1)} °C` : "") : "",
    tile(t.water_air, fin(p.total_water_ml) ? `${Math.round(num(p.total_water_ml))} ml` : null),
    tile(t.threshold, fin(p.ventilation_threshold_ml) ? `${Math.round(num(p.ventilation_threshold_ml))} ml` : null),
    tile(t.night, Number.isFinite(night) ? `+${Math.round(night)} ml` : null, fin(p.night_model_samples) ? esc(t.learn_samples.replace("{n}", Math.round(num(p.night_model_samples)))) : ""),
    p.pollen_enabled != null ? tile(t.pollen, p.pollen_enabled ? (fin(p.pollen_index) ? n(c, p.pollen_index, 1) : "–") : esc(t.pollen_off), p.pollen_enabled && fin(p.pollen_limit) ? `${lang === "de" ? "Grenze" : "limit"} ${n(c, p.pollen_limit, 1)}` : "", p.pollen_blocked ? "warn" : "") : "",
    tile(t.people, fin(p.effective_occupants) ? n(c, p.effective_occupants, num(p.effective_occupants) % 1 ? 1 : 0) : null),
    rooms.length ? tile(t.learning, esc(t.learn_rooms.replace("{n}", stable).replace("{m}", rooms.length)), esc(t.learn_samples.replace("{n}", Math.round(samples)))) : "",
  ]);
  const hist = (Array.isArray(p.water_history_14d) ? p.water_history_14d : []).filter(x => x && x.samples > 0 && fin(x.water_ml)).slice(-14);
  let chart = "";
  if (hist.length >= 2) {
    const max = Math.max(...hist.map(x => num(x.water_ml)), 1), w = 300, h = 70, bw = w / hist.length;
    chart = `<svg class="phist" viewBox="0 0 ${w} ${h + 14}" role="img" aria-label="${esc(t.history)}">${hist.map((x, i) => { const bh = Math.max(2, (num(x.water_ml) / max) * h); return `<rect x="${(i * bw + 2).toFixed(1)}" y="${(h - bh).toFixed(1)}" width="${(bw - 4).toFixed(1)}" height="${bh.toFixed(1)}" rx="3"><title>${esc(x.date || "")} · ${(num(x.water_ml) / 1000).toFixed(2)} l</title></rect>`; }).join("")}</svg>`;
  }
  const last = p.last_ventilation && typeof p.last_ventilation === "object" ? p.last_ventilation : null;
  const lastTxt = last ? [last.room_name || last.room, fin(last.duration_min) ? `${Math.round(num(last.duration_min))} ${t.min}` : null, fin(last.removed_ml) ? `≈ ${Math.round(num(last.removed_ml))} ml` : null].filter(Boolean).join(" · ") : "";
  return `${decision}${reasons.length ? `<ul class="reasons">${reasons.slice(0, 6).map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}`
    + section(t.house_now, now) + section(t.history, chart) + section(t.last_vent, lastTxt ? `<div class="pnote">${esc(lastTxt)}</div>` : "")
    // 0.26.7.0(2): every view behind the FreshAirIQ card's details, drawn by the card's own functions (classicBody)
    + section(t.more_title, `<div class="mlist">${["learning:quality", "decision", "water", "threshold", "night", "pollen", "lastvent"].map(k => classicItem(k, t)).join("")}</div>`);
}

// ---------------------------------------------------------------------------------------------------------------- the menu
// Grouped like a small app: information (details, moisture, weather, rooms), control and modes (guests, the animation), tools
// (edit, airing log, support) and the notes about the drawing. 0.26.7.0 UI hotfix: the view on the plan (action, temperature,
// humidity, CO₂, air paths, quality) is set in the card's settings only – the menu no longer repeats it; the chosen view stays.
export function menuBody(c, H, layout, notes) {
  const t = tx(c), admin = !!(c._hass && c._hass.user && c._hass.user.is_admin), m = c._motionNow || c._motion();
  const item = (attrs, icon, label, sub) => `<button class="mitem" ${attrs}><span class="mi">${icon}</span><span class="mt"><b>${esc(label)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</span>${CHEVRON}</button>`;
  const wx = c._weatherModel(), wxIcon = c._details().includes("condition") && W.hasSymbol(wx.condition) ? W.weatherSvg(wx.condition, { size: 26 }) : "🌡️";
  const info = [
    item("data-house-details", "📊", t.menu_details, t.menu_details_sub),
    c._moistureFacts() ? item("data-moisture", "💧", t.menu_moist, t.menu_moist_sub) : "",
    c._info().includes("overview") ? item("data-weather-open", wxIcon, t.menu_weather, t.menu_weather_sub) : "",
    item("data-rooms", "▦", t.menu_rooms, t.menu_rooms_sub),
    item('data-classic-info="learning"', "🧠", t.learn_title, t.learn_sub),
  ].join("");
  const levels = ["auto", "off", "minimal", "normal", "intense"], chosen = H.chosenLevel(c._config);
  const motion = `<div class="row" role="radiogroup" aria-label="${esc(t.menu_motion)}">${levels.map(l => `<button class="small" data-motion-level="${l}" role="radio" aria-checked="${l === chosen}" aria-pressed="${l === chosen}">${esc(t.motion[l])}</button>`).join("")}</div>`
    + `<div class="legend">${esc(t.motion_now.replace("{v}", t.motion[m.level] || m.level))}</div>`;
  const tools = [
    admin ? item("data-edit", "✏️", t.menu_edit, t.menu_edit_sub) : "",
    item("data-ventlog", "📄", t.menu_log, t.menu_log_sub),
    item("data-support", "🛟", t.menu_support, t.menu_support_sub),
  ].join("");
  // the decision of the house and its key figures first (what the FreshAirIQ card shows on top), then the ways deeper
  return `<section class="mgroup"><h4>${esc(t.menu_info)}</h4>${c._hero(layout)}<div class="mlist">${info}</div></section>`
    + `<section class="mgroup"><h4>${esc(t.menu_control)}</h4>${c._guests()}<h5>${esc(t.menu_motion)}</h5>${motion}</section>`
    + `<section class="mgroup"><h4>${esc(t.menu_tools)}</h4><div class="mlist">${tools}</div></section>`
    + (notes.length ? `<section class="mgroup"><h4>${esc(t.menu_notes)}</h4>${notes.map(x => `<div class="legend">${esc(x)}</div>`).join("")}</section>` : "");
}

// ------------------------------------------------------------------------------------- the FreshAirIQ card's own views
// "Aktuell lernt FreshAirIQ", the learning areas, "Wie gut FreshAirIQ aktuell vorhersagt" with the passive formula comparison,
// water, threshold, night, pollen, decision and the last airing: the FreshAirIQ card computes and words them (its _infoPanel,
// _learningComponentsCard, _learningPanel – the same data, the same rules, the same texts, English through its own tables);
// the house map only gives them its look and its navigation.
const CL_ICON = { learning: "🧠", "learning:quality": "🎯", "learning:home": "🏠", "learning:forecast": "📈", "learning:habits": "🧭", "learning:longterm": "🍃", decision: "💡", water: "💧", threshold: "📏", night: "🌙", pollen: "🌼", lastvent: "🪟" };
const classicItem = (k, t) => `<button class="mitem" data-classic-info="${k}"><span class="mi">${CL_ICON[k] || "•"}</span><span class="mt"><b>${esc(t.cl[k][0])}</b><small>${esc(t.cl[k][1])}</small></span>${CHEVRON}</button>`;
export const classicIcon = k => CL_ICON[k] || CL_ICON[String(k).split(":")[0]] || "•";
// ``html`` from the card host
export function classicBody(c, html) {
  // 0.26.7.0 UI hotfix: "Back" is in every window's head now (one history for the whole house map)
  return `<div class="classic">${html || `<p class="pmuted">–</p>`}</div>`;
}

// ----------------------------------------------------------------------------------------------------------- the airing log
// The FreshAirIQ card's own export (freshairiq-card-data.js _exportVentilationLog) – the same fields and ids, in the map's style
export function ventLogBody(c) {
  const t = tx(c), end = new Date(), start = new Date(end.getTime() - 30 * 86400000), iso = d => d.toISOString().slice(0, 10);
  return `<p class="pmuted">${esc(t.log_hint)}</p><div class="pgrid"><label class="field"><b>${esc(t.log_from)}</b><input type="date" id="ventlog-start" value="${iso(start)}"></label>`
    + `<label class="field"><b>${esc(t.log_to)}</b><input type="date" id="ventlog-end" value="${iso(end)}"></label></div>`
    + `<label class="pcheck"><input type="checkbox" id="ventlog-daily"> ${esc(t.log_daily)}</label>`
    + `<div class="row"><button id="ventlog-export">📄 ${esc(t.log_pdf)}</button><button id="ventlog-csv" class="small">${esc(t.log_csv)}</button></div>`;
}

export const PANELS_STYLE = `
/* 0.26.7.0(2): the windows of the house map – one style with the plan */
.rlist{display:grid;gap:8px}
button.rcard{display:grid;gap:6px;width:100%;text-align:left;padding:10px 12px 10px 14px;border-radius:16px;border:1px solid var(--fq-line2,rgba(201,243,255,.18));border-left:7px solid var(--tone,#7cc8f0);
  background:var(--fq-surface,rgba(2,16,36,.42));background:linear-gradient(100deg,color-mix(in srgb,var(--tone,#7cc8f0) 18%,transparent),var(--fq-surface,rgba(2,16,36,.42)) 55%);color:inherit;font:inherit;cursor:pointer;min-height:56px;box-shadow:0 2px 10px rgba(0,8,20,.18)}
button.rcard:hover{border-color:var(--fq-line2,rgba(201,243,255,.4))}button.rcard:focus-visible{outline:3px solid var(--fq-focus,#ffd27a);outline-offset:2px}
button.rcard.t-close,button.rcard.t-critical{box-shadow:0 0 0 1px var(--tone) inset,0 2px 12px rgba(0,8,20,.22)}
.rcard .rtop{display:flex;align-items:center;gap:8px;min-width:0}.rcard .rtop b{font-size:15px;font-weight:900;overflow-wrap:anywhere;flex:1 1 auto;min-width:0}
.rcard .rfloor{flex:none;font-size:11px;font-weight:800;padding:2px 8px;border-radius:999px;background:var(--fq-surface,rgba(2,16,36,.5));border:1px solid var(--fq-line2,rgba(201,243,255,.2));color:var(--fq-muted,#cfe6ff)}
.rcard .chev{flex:none;width:18px;height:18px;opacity:.65}
.rcard .ract{justify-self:start;font-weight:800;font-size:13px;padding:2px 10px;border-radius:999px;background:var(--fq-surface,rgba(2,16,36,.5));background:color-mix(in srgb,var(--tone,#7cc8f0) 30%,var(--fq-surface,rgba(2,16,36,.5)))}
.rcard .rvals{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;font-weight:700;color:var(--fq-soft,#e6f3ff)}.rcard .rv em{font-style:normal;margin-right:3px}
.rcard .rml{color:var(--fq-good,#bff0d3)}.rcard .rml small{font-weight:700;color:var(--fq-muted2,#a9cbe6)}.rcard .rsub{font-size:12px;opacity:.85}
.mdot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle;box-shadow:0 0 0 1.5px var(--fq-surface,rgba(2,16,36,.5))}
.dlg:not(.dark) button.rcard{background:rgba(255,255,255,.75);color:#0a1f38}
.psec{display:grid;gap:8px;padding:12px 14px;border-radius:18px;background:var(--fq-surface,rgba(2,16,36,.3));border:1px solid var(--fq-line2,rgba(201,243,255,.14))}
.psec h4{margin:0;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--fq-muted,#cfe6ff)}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));gap:8px}
.ptile,.ptile.tile{display:grid;gap:2px;padding:9px 12px;border-radius:14px;background:var(--fq-surface,rgba(2,16,36,.36));border:1px solid var(--fq-line2,rgba(201,243,255,.16));min-width:0}
.ptile span{font-size:12px;font-weight:700;color:var(--fq-muted,#cfe6ff)}.ptile strong{font-size:17px;font-weight:900;color:var(--fq-strong,#fff);overflow-wrap:anywhere}.ptile i{font-style:normal;font-size:12px;color:var(--fq-muted2,#a9cbe6)}
.ptile.warn{border-color:#ff8f5c;box-shadow:0 0 0 1px #ff8f5c inset}
.why-s .why{font-size:14px;line-height:1.45;background:var(--fq-surface,rgba(2,16,36,.38));color:var(--fq-strong,#fff);border:1px solid var(--fq-line2,rgba(201,243,255,.2));box-shadow:none;border-radius:12px;padding:10px 12px}.reasons{margin:0;padding-left:18px;display:grid;gap:3px;font-size:13px;color:var(--fq-soft,#e6f3ff)}
.contacts{list-style:none;margin:0;padding:0;display:grid;gap:6px}.contacts li{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;padding:7px 10px;border-radius:12px;background:var(--fq-surface,rgba(2,16,36,.32))}
.contacts li span{flex:1 1 auto;min-width:0;overflow-wrap:anywhere}.contacts li i{font-style:normal;font-size:12px;color:var(--fq-muted2,#a9cbe6)}.contacts li.open b{color:var(--fq-good,#9ff0bf)}
.pnote{font-size:13px;line-height:1.45}.pmuted{margin:0;font-size:13px;color:var(--fq-muted,#cfe6ff)}.pactions{display:flex;flex-wrap:wrap;gap:8px}
.phist rect{fill:#5cc2ff;opacity:.8}.mgroup .hero{margin:0}
.mgroup{display:grid;gap:8px;padding:12px 14px;border-radius:18px;background:var(--fq-surface,rgba(2,16,36,.3));border:1px solid var(--fq-line2,rgba(201,243,255,.14))}
.mgroup h4{margin:0;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--fq-muted,#cfe6ff)}.mgroup h5{margin:6px 0 0;font-size:12px;color:var(--fq-muted,#cfe6ff)}
.mlist{display:grid;gap:6px}
button.mitem{display:flex;align-items:center;gap:12px;width:100%;min-height:52px;padding:8px 12px;border-radius:14px;border:1px solid var(--fq-line2,rgba(201,243,255,.16));background:var(--fq-surface,rgba(2,16,36,.4));color:inherit;font:inherit;text-align:left;cursor:pointer}
button.mitem:hover{border-color:var(--fq-line2,rgba(201,243,255,.4))}button.mitem:focus-visible{outline:3px solid var(--fq-focus,#ffd27a);outline-offset:2px}
.mitem .mi{flex:none;display:grid;place-items:center;width:34px;height:34px;border-radius:12px;background:var(--fq-line2,rgba(201,243,255,.1));font-size:18px}.mitem .mi svg{width:26px;height:26px}
.mitem .mt{display:grid;flex:1 1 auto;min-width:0;overflow-wrap:anywhere}.mitem .mt b{font-size:15px}.mitem .mt small{font-size:12px;color:var(--fq-muted2,#a9cbe6)}.mitem .chev{width:18px;height:18px;opacity:.6;flex:none}
.pcheck{display:flex;gap:8px;align-items:center;min-height:40px;font-size:14px}
.field input[type=date]{min-height:40px;border-radius:10px;border:1px solid var(--fq-line2,rgba(201,243,255,.3));background:var(--fq-surface,rgba(2,16,36,.4));color:inherit;padding:0 10px;font:inherit}
/* 0.26.7.0 UI hotfix: "Back" at the top left of every window that was opened from another one */
header .navback{flex:none;align-self:center;min-height:40px;min-width:44px;padding:0 12px;margin-right:4px;border-radius:999px;border:2px solid var(--fq-surface,rgba(2,16,36,.55));background:rgba(255,255,255,.92);color:#0a1f38;font:inherit;font-weight:900;font-size:14px;cursor:pointer}
header .navback:focus-visible{outline:3px solid var(--fq-focus,#ffd27a);outline-offset:2px}
/* the FreshAirIQ card's own views in the house map's look */
.pactions.top{margin-bottom:2px}
.classic{display:grid;gap:10px;font-size:14px;line-height:1.45;color:var(--fq-soft,#e6f3ff)}
.classic section,.classic .learning-overview-card{display:grid;gap:10px;margin:0;padding:0;background:none;border:0}
.classic h2,.classic h3{margin:0;font-size:18px;font-weight:900;color:var(--fq-strong,#fff)}.classic p{margin:0}.classic .muted,.classic small{color:var(--fq-muted2,#a9cbe6);font-size:12px}
.classic .tiny,.classic .info-kicker{font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:var(--fq-muted,#cfe6ff)}
.classic ha-icon{--mdc-icon-size:20px;color:var(--fq-icon,#9fe0ff)}
.classic .learning-overview-hero,.classic .learning-group-hero,.classic .longterm-hero{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:18px;background:var(--fq-surface,rgba(2,16,36,.34));border:1px solid var(--fq-line2,rgba(201,243,255,.16))}
.classic .learning-overview-title{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}.classic .learning-overview-title span{font-weight:800;color:var(--fq-focus,#ffd27a)}
.classic .learning-kpis,.classic .learning-quality-grid,.classic .info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
.classic .learning-kpis>div,.classic .learning-quality-grid>div,.classic .info-grid>div,.classic .learning-detail-card,.classic .season-card,.classic .breakdown-row,.classic .learning-overview-note,.classic .history,.classic .summary{display:grid;gap:3px;padding:9px 12px;border-radius:14px;background:var(--fq-surface,rgba(2,16,36,.36));border:1px solid var(--fq-line2,rgba(201,243,255,.16));min-width:0;overflow-wrap:anywhere}
.classic .learning-kpis b,.classic .learning-quality-grid b,.classic .info-grid b{font-size:17px;font-weight:900;color:var(--fq-strong,#fff)}
.classic i{display:block;height:5px;border-radius:3px;background:var(--fq-track,rgba(255,255,255,.12));overflow:hidden;font-style:normal}.classic i em{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#7cc8f0,var(--fq-good,#bff0d3))}
.classic .learning-areas,.classic .learning-detail-list,.classic .breakdown{display:grid;gap:6px}
.classic .learning-area{display:grid;grid-template-columns:auto 1fr auto auto;gap:10px;align-items:center;width:100%;min-height:52px;padding:8px 12px;border-radius:14px;border:1px solid var(--fq-line2,rgba(201,243,255,.16));background:var(--fq-surface,rgba(2,16,36,.4));color:inherit;font:inherit;text-align:left;cursor:pointer}
.classic .learning-area-copy{display:grid;min-width:0}.classic .learning-area-score{display:grid;gap:3px;min-width:64px;text-align:right}
.classic .learning-detail-card{grid-template-columns:auto 1fr}.classic .learning-detail-head{display:flex;justify-content:space-between;gap:8px}
.classic .breakdown-row{grid-template-columns:1fr auto;cursor:pointer}.classic .breakdown-row span{grid-column:1/-1;color:var(--fq-muted2,#a9cbe6);font-size:12px}
.classic .learning-overview-note{grid-template-columns:auto 1fr}.classic .faiq-shadow-test{border-color:rgba(255,210,122,.35)}
.classic [data-classic-info],.classic [data-classic-room]{cursor:pointer}
.classic .learning-now{display:flex;gap:10px;align-items:center;width:100%;min-height:52px;padding:8px 12px;border-radius:14px;border:1px solid rgba(255,210,122,.35);background:var(--fq-surface,rgba(2,16,36,.4));color:inherit;font:inherit;text-align:left;box-shadow:none;cursor:pointer}
.classic .learning-now span{display:grid;flex:1 1 auto;min-width:0}.classic .learning-area-head{display:grid;gap:2px}.classic .learning-area-head span{color:var(--fq-muted2,#a9cbe6);font-size:12px}
/* how much moves (freshairiq-house-motion.js): "minimal" keeps only the weather's own slow motion (clouds, rain, snow) – no
   breathing rooms, glowing rims, mist, plumes, light rays or flashes; each part can be switched off on its own */
:host([data-motion="minimal"]) .room,:host([data-motion="minimal"]) .rim,:host([data-motion="minimal"]) .cl,:host([data-motion="minimal"]) .steam path,
:host([data-motion="minimal"]) .plume:not(.fade),:host([data-motion="minimal"]) .particles,:host([data-motion="minimal"]) .floorbtn.pulse,
:host([data-motion="minimal"]) .wx.flash,:host([data-motion="minimal"]) .wx.sunlight .ray,:host([data-motion="minimal"]) .wx.stars > *,:host([data-motion="minimal"]) .wx.world *,:host([data-motion="minimal"]) .wx.splash>svg,:host([data-motion="minimal"]) .wx.sweep>*{animation:none}
:host([data-motion="minimal"]) .wx.clouds > *{animation-duration:140s}
:host([data-no-weather]) .wx .fall,:host([data-no-weather]) .wx.clouds > *,:host([data-no-weather]) .wx.fog > *,:host([data-no-weather]) .wx.world *,:host([data-no-weather]) .wx.splash>svg,:host([data-no-weather]) .wx.sweep>*{animation:none}
:host([data-no-light]) .wx.flash,:host([data-no-light]) .wx.sunlight .ray,:host([data-no-light]) .wx.stars > *{animation:none}
:host([data-no-ambient]) .room,:host([data-no-ambient]) .rim,:host([data-no-ambient]) .cl,:host([data-no-ambient]) .steam path,:host([data-no-ambient]) .plume:not(.fade),
:host([data-no-ambient]) .particles,:host([data-no-ambient]) .fan .blades,:host([data-no-ambient]) .floorbtn.pulse{animation:none}
/* "intense": livelier weather and light – quicker clouds and rain, stronger sun rays, a livelier flash in a thunderstorm */
:host([data-motion="intense"]) .wx.clouds > *{animation-duration:calc(var(--cloud-dur,60s) * .6)}
:host([data-motion="intense"]) .wx.sunlight .ray{fill-opacity:calc(var(--ray-o,.07) * 1.6)}
:host([data-motion="intense"]) .wx .fall{animation-duration:calc(var(--fall-dur,.55s) * .85 * var(--k,1))}
/* the room chosen on the plan: its outline drawn clearly, the rest of the floor quieter (windows and doors stay visible) */
svg.plan.focus polygon.room:not(.sel){filter:saturate(.55) brightness(.72)}
svg.plan.focus polygon.room.sel{stroke:#fff;stroke-opacity:1}
.sel-outline{fill:none;stroke:#ffffff;stroke-linejoin:round;pointer-events:none}
.sel-glow{fill:none;stroke:#ffd27a;stroke-opacity:.55;stroke-linejoin:round;pointer-events:none;filter:url(#glow)}
`;
