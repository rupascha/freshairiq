// House map 0.26.7.0(2): the weather window and the weather at the top right, the rooms overview, a room's details, the menu,
// the calmer wind and the animation levels – checked in a real browser (fixtures and mount as in house.spec.mjs).
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { loadModule } from './harness.mjs';

const LAYOUT = {
  schema_version: 1, revision: 3, building: { north_deg: 0, units: 'm', north_confirmed: true },
  floors: [{ id: 'f_eg', name: 'EG', level_key: 'ground_floor', order: 0 }, { id: 'f_og', name: 'OG', level_key: 'upper_floor', order: 1 }],
  rooms: [
    { id: 'r_bad', room_key: 'bad', floor_id: 'f_eg', polygon: [[0, 4], [4, 4], [4, 8], [0, 8]], provenance: 'user' },
    { id: 'r_flur', room_key: 'flur', floor_id: 'f_eg', polygon: [[0, 0], [8, 0], [8, 4], [0, 4]], provenance: 'config' },
    { id: 'r_wohnen', room_key: 'wohnen', floor_id: 'f_eg', polygon: [[4, 4], [10, 4], [10, 7], [7, 7], [7, 10], [4, 10]], provenance: 'user' },
    { id: 'r_schlaf', room_key: 'schlaf', floor_id: 'f_og', polygon: [[0, 0], [5, 0], [4, 4], [0, 3]], provenance: 'user' },
  ],
  openings: [
    { id: 'o_bad', room_id: 'r_bad', edge: 2, offset: 0.5, width_m: null, kind: 'window', mechanics: 'unknown', contacts: ['binary_sensor.bad_fenster'] },
    { id: 'o_wohnen', room_id: 'r_wohnen', edge: 1, offset: 0.5, width_m: 1.2, kind: 'window', mechanics: 'turn_tilt', contacts: ['sensor.wohnen_lage'] },
    { id: 'd_bad', room_id: 'r_bad', edge: 0, offset: 0.5, width_m: null, kind: 'door', mechanics: 'door', contacts: ['binary_sensor.bad_tuer'] },
    { id: 'o_schlaf', room_id: 'r_schlaf', edge: 0, offset: 0.5, width_m: null, kind: 'window', mechanics: 'unknown', contacts: ['binary_sensor.schlaf_fenster'] },
  ],
  connections: [{ id: 'c1', a: 'r_flur', b: 'r_wohnen', kind: 'open_passage', confirmed: true }], shading: [],
};
// Room fields exactly as the coordinator publishes them (checked against a real payload in ha_tests/test_house_map_026504.py).
const BASE_ROOM = JSON.parse(fs.readFileSync(new URL('./fixtures/house_room_payload.json', import.meta.url), 'utf8')).room;
const ACTION_CODE = { Close: 'close', Okay: 'okay', Ventilate: 'ventilate', Wait: 'wait' };
const room = (key, name, action, extra = {}) => ({ ...BASE_ROOM, key, name, action, house_aligned_action: ACTION_CODE[action], reason: `${name}: Grund`, ...extra });
const ROOMS = {
  bad: room('bad', 'Bad', 'Close', { house_aligned_action: 'close' }),
  flur: room('flur', 'Flur', 'Okay'),
  wohnen: room('wohnen', 'Wohnen', 'Ventilate', { contact_entities: ['sensor.wohnen_lage'] }),
  schlaf: room('schlaf', 'Schlafzimmer', 'Okay'),
};
const WIND = { available: true, reason: null, from_deg: 307, to_deg: 127, speed_ms: 5, gust_ms: null, unit: 'km/h', unit_assumed: false, calm: false,
  stale: false, age_s: 120, source: 'weather.home', label_en: 'NW', label_de: 'NW' };
const HOUSE = {
  house_map_api: 'house_map_v1', revision: 3, layout_usable: true, wind: WIND,
  rooms: { bad: { contacts: { 'binary_sensor.bad_fenster': { state: 'open_unspecified', pending: true, three_state: false, delay_s: 120 } } } },
  airflow: {
    model_level: 'wind_heuristic',
    openings: {
      o_bad: { room: 'r_bad', target: 'outside', state: 'open_unspecified', pending: true, size: 'unknown', facade_deg: 0, facade_basis: 'geometry', exposure: 'windward', angle_deg: 53, pressure: 0.6 },
      o_wohnen: { room: 'r_wohnen', target: 'outside', state: 'tilted', pending: false, size: 'small', facade_deg: 90, facade_basis: 'geometry', exposure: 'leeward', angle_deg: 143, pressure: -0.8 },
      d_bad: { room: 'r_bad', target: 'r_flur', state: 'open', pending: false, size: 'large', facade_deg: null, facade_basis: 'interior', exposure: 'interior' },
    },
    paths: [{ kind: 'cross', direction: 'directed', from: 'o_bad', to: 'o_wohnen', rooms: ['r_bad', 'r_flur', 'r_wohnen'], via: ['d_bad', 'c1'],
      confidence: 'low', basis: ['wind', 'facade', 'opening_state'], assumptions: ['no_obstacles', 'no_measured_flow'], unknowns: [] }],
    devices: [], pending_openings: ['o_bad'],
  },
};

async function mount(page, { config = {}, stored = true, admin = true, saveError = null, reducedMotion = 'no-preference' } = {}) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await page.emulateMedia({ reducedMotion });
  await loadModule(page, '<!doctype html><html><body><main id="m"></main></body></html>', 'freshairiq-loader.js', 'freshairiq-house-card');
  await page.evaluate(async ({ config, stored, admin, saveError, LAYOUT, ROOMS, HOUSE }) => {
    window.__subs = {}; window.__calls = [];
    window.__ROOMS = ROOMS; window.__HOUSE = HOUSE; window.__LAYOUT = LAYOUT;
    window.__unsubscribed = 0;
    const connection = { subscribeMessage(cb, msg) { window.__subs[msg.type] = cb; return Promise.resolve(() => { window.__unsubscribed += 1; }); } };
    const callWS = async msg => {
      window.__calls.push(JSON.parse(JSON.stringify(msg)));
      if (msg.type === 'freshairiq/house_map/get') return { house_map_api: 'house_map_v1', entry_id: 'e1', revision: stored ? 3 : 0, layout: stored ? LAYOUT : null,
        issues: [], rooms: Object.values(ROOMS).map(r => ({ key: r.key, name: r.name, floor: 'ground_floor' })), levels: ['ground_floor', 'upper_floor'] };
      if (msg.type === 'freshairiq/house_map/propose') return { house_map_api: 'house_map_v1', layout: LAYOUT, issues: [], quality: {} };
      if (msg.type === 'freshairiq/house_map/save') { if (saveError) { const e = new Error(saveError); e.code = saveError; throw e; } return { revision: msg.base_revision + 1, issues: [] }; }
      throw new Error('unexpected');
    };
    const card = document.createElement('freshairiq-house-card');
    card.id = 'card';
    card.setConfig(config);
    document.getElementById('m').appendChild(card);
    card.hass = { connection, callWS, language: 'de', locale: { language: 'de' }, user: { is_admin: admin } };
    await customElements.whenDefined('freshairiq-house-card-impl');
  }, { config, stored, admin, saveError, LAYOUT, ROOMS, HOUSE });
  await page.waitForFunction(() => window.__subs['freshairiq/house_map/subscribe']);
  await page.evaluate(() => { window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de' }); window.__subs['freshairiq/house_map/subscribe'](window.__HOUSE); });
  await page.waitForTimeout(120);
  return errors;
}
const impl = page => page.locator('freshairiq-house-card-impl');
const STATES = (cond = 'rainy', extra = {}) => ({
  'weather.home': { entity_id: 'weather.home', state: cond, last_updated: cond, attributes: { temperature: 8.5, apparent_temperature: 6.1, humidity: 88, pressure: 1003, dew_point: 6.6, uv_index: 1, wind_speed: 18, wind_gust_speed: 40, wind_bearing: 'SW', ...extra } },
  'sun.sun': { state: 'above_horizon', attributes: { elevation: 18, azimuth: 160, next_rising: '2026-11-07T06:21:00Z', next_setting: '2026-11-06T15:44:00Z' } },
});
const setup = (page, config = {}, states = STATES(), forecast = null) => impl(page).evaluate((el, [config, states, forecast]) => {
  el.setConfig({ ...el._config, weather_entity: 'weather.home', ...config });
  el._hass = { ...el._hass, states };
  if (forecast) el._forecast = forecast;
  el._render();
}, [config, states, forecast]);
const openWeather = page => impl(page).evaluate(el => { el._selected = { type: 'weather', id: '' }; el._render(); const d = el.shadowRoot.querySelector('dialog.roomdlg');
  return { facts: [...d.querySelectorAll('.fact')].map(f => f.textContent.replace(/\s+/g, ' ').trim()), big: !!d.querySelector('.now .big'), cond: !!d.querySelector('.now .cond'),
    heroIcon: !!d.querySelector('.now .ico svg'), headIcon: !!d.querySelector('header .emo svg'), text: d.textContent, panels: [...d.querySelectorAll('.wxv > section.panel')].map(s => s.className.replace('panel ', '')) }; });
const FORECAST = {
  hourly: Array.from({ length: 12 }, (_, i) => ({ datetime: new Date(Date.now() + i * 3600e3).toISOString(), temperature: 8 + Math.sin(i / 2) * 3, condition: i < 4 ? 'rainy' : 'cloudy', precipitation_probability: i < 4 ? 70 : 10 })),
  daily: Array.from({ length: 5 }, (_, i) => ({ datetime: new Date(Date.now() + i * 86400e3).toISOString(), temperature: 11 + i, templow: 3 + i, condition: ['rainy', 'cloudy', 'sunny', 'partlycloudy', 'snowy'][i], precipitation_probability: 20 * i })),
};

test('0.26.7.0(2) error A: weather values switched off never come back – only temperature means only temperature, none means none', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  await setup(page, { weather_details: ['temperature'] });
  let w = await openWeather(page);
  expect(w.facts).toEqual([]); expect(w.big).toBe(true); expect(w.cond).toBe(false);
  await setup(page, { weather_details: [] });
  w = await openWeather(page);
  expect([w.facts, w.big, w.cond, w.heroIcon]).toEqual([[], false, false, false]);
  // the card editor writes the explicit choice (also an empty one) – a card that unticks every value keeps them all off
  const written = await page.evaluate(async () => {
    const ed = document.createElement('freshairiq-house-card-editor-impl'); document.body.appendChild(ed);
    let out = null; ed.addEventListener('config-changed', ev => { out = ev.detail.config; });
    ed.setConfig({ weather_info: ['compact', 'overview', 'humidity'] }); ed.hass = { language: 'de', callWS: () => Promise.reject(new Error('x')) };
    const boxes = [...ed.querySelectorAll('[data-list="weather_details"]')];
    boxes.forEach(b => { b.checked = false; }); boxes[0].dispatchEvent(new Event('change'));
    ed.remove(); return out;
  });
  expect(written.weather_details).toEqual([]);
  expect(written.weather_info).toEqual(['compact', 'overview']);   // the values left the parts list; the parts stay
  await setup(page, { weather_info: written.weather_info, weather_details: written.weather_details });
  expect((await openWeather(page)).facts).toEqual([]);
  // a card that never chose values keeps every value (unchanged), the first 0.26.7.0 format still counts exactly
  await setup(page, { weather_info: undefined, weather_details: undefined });
  // Test note 0.26.7.0 UI hotfix (owner order): the new value "absolute humidity" belongs to "every value" – six now
  expect((await openWeather(page)).facts.length).toBe(6);   // every value the entity has (no forecast here: no chance of rain)
  await setup(page, { weather_info: ['overview', 'pressure'], weather_details: undefined });
  expect((await openWeather(page)).facts).toEqual(['Luftdruck 1003 hPa']);
});

test('0.26.7.0(2) error B: the weather condition switched off shows no symbol anywhere; on, the symbol fits the weather', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  await setup(page, { weather_details: ['temperature', 'humidity'], weather_chip: ['temperature', 'condition'] });
  const off = await openWeather(page);
  expect([off.heroIcon, off.headIcon]).toEqual([false, false]);
  expect(off.text).not.toMatch(/🌤️|☀️|🌦️/);
  const menuIcon = await impl(page).evaluate(el => { el._selected = null; el._menuOpen = true; el._render(); return el.shadowRoot.querySelector('dialog.menudlg [data-weather-open] .mi').innerHTML; });
  expect(menuIcon).not.toContain('<svg');
  await setup(page, { weather_details: ['temperature', 'condition'], weather_chip: ['temperature', 'condition'] });
  const on = await openWeather(page);
  expect([on.heroIcon, on.headIcon, on.cond]).toEqual([true, true, true]);
  // the symbol is the one of the condition: rain has drops, a clear night a moon (no sun), no condition no symbol
  const shapes = await page.evaluate(async src => { const W = await import(src);
    return { rain: (W.weatherSvg('rainy').match(/<line/g) || []).length, night: W.weatherSvg('clear-night').includes('<path'), nightSun: W.weatherSvg('clear-night').includes('stroke-linecap="round"/><circle'), none: W.weatherSvg('nonsense'), emoji: W.conditionIcon('nonsense') }; }, '/freshairiq-house-weather.js?v=0.26.7.0');
  expect(shapes.rain).toBeGreaterThanOrEqual(3); expect(shapes.night).toBe(true); expect(shapes.nightSun).toBe(false);
  expect([shapes.none, shapes.emoji]).toEqual(['', '']);
});

test('0.26.7.0(2) weather at the top right: the card chooses what shows, a narrow card shows the first ones, a tap opens the full window', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  const chip = () => impl(page).evaluate(el => { const c = el.shadowRoot.querySelector('.topbar .weather'); return c ? [...c.querySelectorAll(':scope > span')].map(s => s.textContent.trim() || (s.querySelector('svg') ? 'SVG' : '')) : null; });
  await setup(page, {});
  expect(await chip()).toEqual(['🌡️ 8,5 °C', '💧 88 %']);                    // without a choice: as before
  await setup(page, { weather_chip: ['condition', 'temperature', 'wind', 'apparent', 'pressure', 'sun', 'datetime'] });
  const all = await chip();
  expect(all[0]).toBe('SVG'); expect(all[1]).toBe('🌡️ 8,5 °C'); expect(all[2]).toMatch(/SW 18 km\/h/); expect(all.length).toBe(7);
  await setup(page, { weather_chip: [] });
  expect(await chip()).toBe(null);                                            // nothing chosen: no display there
  await setup(page, { weather_chip: ['temperature', 'humidity', 'wind', 'pressure'] });
  await page.evaluate(() => { const m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width,initial-scale=1'; document.head.appendChild(m); });   // as Home Assistant's page
  await page.setViewportSize({ width: 330, height: 700 });
  await page.waitForTimeout(200); await impl(page).evaluate(el => el._render());
  expect((await chip()).length).toBe(2);                                      // narrow: the first two of the choice
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(200);
  await impl(page).evaluate(el => { el._forecast = { hourly: [], daily: [] }; el._render(); el.shadowRoot.querySelector('[data-weather-open]').click(); });
  expect(await impl(page).evaluate(el => el._selected && el._selected.type)).toBe('weather');
});

test('0.26.7.0(2) the weather window: hero, values, sun, wind, next hours and days – what the source lacks is left out', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await setup(page, {}, STATES(), FORECAST);
  const w = await impl(page).evaluate((el, fc) => { el._selected = { type: 'weather', id: '' }; el._forecast = fc; el._render(); const d = el.shadowRoot.querySelector('dialog.roomdlg');
    return { panels: [...d.querySelectorAll('.wxv > section.panel')].map(s => s.classList[1]), facts: [...d.querySelectorAll('.fact > span')].map(s => s.textContent),
      text: d.textContent, days: d.querySelectorAll('.day').length, hourIcons: d.querySelectorAll('.hours svg g[transform]').length, hilo: !!d.querySelector('.hilo'), gust: d.textContent.includes('Böen 40 km/h'), bft: d.querySelectorAll('.bft i').length }; }, FORECAST);
  expect(w.panels).toEqual(['sun', 'wind', 'hours', 'days-p']);
  // Test note 0.26.7.0 UI hotfix (owner order): the absolute humidity is one of the window's values (computed from the entity's temperature and humidity)
  expect(w.facts).toEqual(['Gefühlt', 'Luftfeuchte', 'Absolute Feuchte', 'Taupunkt', 'Luftdruck', 'Regenrisiko', 'UV-Index']);
  expect(w.days).toBe(5); expect(w.hourIcons).toBeGreaterThan(4); expect(w.hilo).toBe(true); expect(w.gust).toBe(true); expect(w.bft).toBe(13);
  expect(w.text).toMatch(/Tageslänge/); expect(w.text).toMatch(/aus SW/);
  // a source without UV, dew point, gusts and forecasts: those parts are left out, nothing reads "–"
  await setup(page, {}, { 'weather.home': { entity_id: 'weather.home', state: 'cloudy', last_updated: 'q', attributes: { temperature: 4, humidity: 70 } }, 'sun.sun': STATES()['sun.sun'] });
  const thin = await impl(page).evaluate(el => { el._forecast = { hourly: [], daily: [] }; el._render(); const d = el.shadowRoot.querySelector('dialog.roomdlg');
    return { facts: [...d.querySelectorAll('.fact > span')].map(s => s.textContent), panels: [...d.querySelectorAll('.wxv > section.panel')].map(s => s.classList[1]), dash: [...d.querySelectorAll('.fact b, .big')].some(b => b.textContent.trim() === '–') }; });
  // Test note 0.26.7.0 UI hotfix (owner order): temperature and humidity are enough for the absolute humidity – it is shown
  expect(thin.facts).toEqual(['Luftfeuchte', 'Absolute Feuchte']); expect(thin.panels).not.toContain('hours'); expect(thin.panels).not.toContain('days-p'); expect(thin.dash).toBe(false);
});

test('0.26.7.0(2) rooms overview: the whole room card is the button (nothing beside it), every value, its floor; a tap opens the room on its floor', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page, { config: { rooms_button: true } });
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-rooms]').click());
  const list = await impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg');
    return { side: d.querySelectorAll('.rjump, .rrow > button + button').length, cards: [...d.querySelectorAll('button.rcard')].map(b => ({ name: b.querySelector('b').textContent, floor: b.querySelector('.rfloor').textContent, chev: !!b.querySelector('.chev'), vals: b.querySelector('.rvals') ? b.querySelector('.rvals').textContent : '' })),
      fits: [...d.querySelectorAll('button.rcard')].every(b => { const r = b.getBoundingClientRect(), p = d.querySelector('.body').getBoundingClientRect(); return r.left >= p.left - 1 && r.right <= p.right + 1; }) }; });
  expect(list.side).toBe(0);
  expect(list.cards.map(c => c.name)).toEqual(['Bad', 'Flur', 'Wohnen', 'Schlafzimmer']);
  expect(list.cards[0]).toMatchObject({ floor: 'Erdgeschoss', chev: true });
  expect(list.cards[0].vals).toMatch(/21,4 °C/); expect(list.cards[0].vals).toMatch(/58 %/); expect(list.cards[0].vals).toMatch(/10,9 g\/m³/); expect(list.cards[0].vals).toMatch(/Schimmel/);
  expect(list.fits).toBe(true);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('button.rcard[data-room-open="r_schlaf"]').click());
  expect(await impl(page).evaluate(el => [el._selected.type, el._floor, el.shadowRoot.querySelector('dialog.roomdlg h3').textContent, !!el.shadowRoot.querySelector('svg.plan.focus [data-outline="r_schlaf"]')])).toEqual(['room', 'f_og', 'Schlafzimmer', true]);
});

test('0.26.7.0(2) a room tapped on the plan: its outline stands out, the rest is quieter, its windows stay visible; the window tells everything the card knows', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ output_language: 'de', rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, recommendation_reasons: ['Raumluftfeuchte hoch', 'Außen trockener'], water_in_air_ml: 312, volume_m3: 18.5,
    moisture_effect_next_5_min_ml: 42, temp_next_5_min_c: 21.1, realistic_potential_ml: 120, learning_status: 'Lernt noch', comfort_target_c: 21, co2: 640, surface_rh_source: 'internal_estimate' } } }));
  await page.waitForTimeout(80);
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(80);
  const r = await impl(page).evaluate(el => { const svg = el.shadowRoot.querySelector('svg.plan'), d = el.shadowRoot.querySelector('dialog.roomdlg');
    const outline = svg.querySelector('[data-outline="r_bad"]'), all = [...svg.children], opIdx = all.findIndex(n => n.matches && n.matches('line.op'));
    return { focus: svg.classList.contains('focus'), outline: !!outline, beforeOpenings: all.indexOf(outline) < opIdx, others: getComputedStyle(svg.querySelector('polygon.room[data-room="r_flur"]')).filter, sel: getComputedStyle(svg.querySelector('polygon.room[data-room="r_bad"]')).filter,
      heads: [...d.querySelectorAll('.psec h4')].map(h => h.textContent), text: d.textContent }; });
  expect(r.focus && r.outline && r.beforeOpenings).toBe(true);
  expect(r.others).not.toBe('none'); expect(r.sel).toBe('none');
  for (const h of ['Warum?', 'Raumklima', 'Wand & Schimmel', 'Feuchte & Prognose', 'Lernen', 'Fenster & Türen', 'Raummodell']) expect(r.heads).toContain(h);
  for (const part of ['Bad: Grund', 'Raumluftfeuchte hoch', '312 ml', '640 ppm', 'Ziel 21,0 °C', '−42 ml', '≈ 120 ml', 'Lernt noch', '18,5 m³', 'geschätzt aus der Wandtemperatur']) expect(r.text).toContain(part);
  // a live update refreshes the window in place (same element, still open, scroll kept)
  const same = await impl(page).evaluate(async el => { const d = el.shadowRoot.querySelector('dialog.roomdlg'); d.querySelector('.body').scrollTop = 80; const top = d.querySelector('.body').scrollTop;
    window.__subs['freshairiq/dashboard/subscribe']({ output_language: 'de', rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: 23.2 } } });
    await new Promise(r => setTimeout(r, 120)); const d2 = el.shadowRoot.querySelector('dialog.roomdlg'); return [d2 === d, d2.open, d2.textContent.includes('23,2'), d2.querySelector('.body').scrollTop === top]; });
  expect(same).toEqual([true, true, true, true]);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-close-detail]').click());
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('svg.plan.focus, [data-outline]'))).toBe(false);
});

test('0.26.7.0(2) the menu: information, control and modes, tools and notes – everything of the card\'s details, guests, editing and support in one style', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de', potential_total_ml: 420, recommended_duration_min: 9, total_water_ml: 4100, ventilation_threshold_ml: 380,
    overnight_forecast_ml: 160, night_model_samples: 12, pollen_enabled: true, pollen_index: 2.1, pollen_limit: 3, effective_occupants: 2, intelligent_recommendation: { kind: 'ventilate', title: 'Jetzt lüften', instruction: 'Bad und Flur' },
    water_history_14d: [{ date: 'a', samples: 3, water_ml: 3900 }, { date: 'b', samples: 3, water_ml: 4200 }, { date: 'c', samples: 2, water_ml: 4000 }] }));
  await page.waitForTimeout(80);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-menu]').click());
  const m = await impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.menudlg');
    return { groups: [...d.querySelectorAll('.mgroup > h4')].map(h => h.textContent), hero: !!d.querySelector('.hero'), items: [...d.querySelectorAll('button.mitem')].map(b => [...b.attributes].find(a => a.name.startsWith('data-')).name),
      guests: d.querySelectorAll('.guest').length, layers: d.querySelectorAll('[data-layer]').length, motion: d.querySelectorAll('[data-motion-level]').length,
      fits: (() => { const r = d.querySelector('.dlg').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && d.querySelector('.body').scrollWidth <= d.querySelector('.body').clientWidth + 1; })() }; });
  expect(m.groups).toEqual(['Informationen', 'Steuerung & Modi', 'Werkzeuge', 'Hinweise']);
  expect(m.hero).toBe(true);
  // Test note 0.26.7.0(2) corrections (owner order: every view behind the card's details): learning has its own entry now
  expect(m.items).toEqual(['data-house-details', 'data-moisture', 'data-weather-open', 'data-rooms', 'data-classic-info', 'data-edit', 'data-ventlog', 'data-support']);
  // Test note 0.26.7.0 UI hotfix (owner order): "view on the plan" left the menu (the card setting decides it); the Animation area stays
  expect([m.guests, m.layers, m.motion, m.fits]).toEqual([2, 0, 5, true]);
  // more about the decision: the card's house values in the map's style
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-house-details]').click());
  const det = await impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg'); return { menu: el.shadowRoot.querySelector('dialog.menudlg').open, text: d.textContent, bars: d.querySelectorAll('.phist rect').length }; });
  expect(det.menu).toBe(false);
  for (const part of ['Jetzt lüften', '4100 ml', '380 ml', '+160 ml', '2,1', '2']) expect(det.text).toContain(part);
  expect(det.bars).toBe(3);
  // the airing log: the FreshAirIQ card's own export with its fields
  await impl(page).evaluate(el => { el._selected = null; el._menuOpen = true; el._render(); el.shadowRoot.querySelector('[data-ventlog]').click(); });
  await expect.poll(() => impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg[open] #ventlog-export') && !!el.shadowRoot.getElementById('ventlog-start'))).toBe(true);
  const calls = await page.evaluate(async () => { const el = document.querySelector('freshairiq-house-card-impl'); window.__api2 = [];
    el._hass = { ...el._hass, callApi: (m, p) => { window.__api2.push([m, p]); return Promise.resolve({ csv: 'a;b', filename: 'x.csv' }); } };
    URL.createObjectURL = () => 'blob:x'; el.shadowRoot.getElementById('ventlog-csv').click(); await new Promise(r => setTimeout(r, 100)); return window.__api2; });
  expect(calls[0][1]).toMatch(/^freshairiq\/ventilation-log\/e1\?start=.*&format=csv$/);
});

test('0.26.7.0(2) animation levels: off, minimal, normal, intense and auto; reduced motion; the parts; a long untouched card calms and rests, a touch wakes it', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  const state = () => impl(page).evaluate(el => ({ level: el.getAttribute('data-motion'), still: el.hasAttribute('data-still'), loop: !!el._windRaf, fps: el._windRaf && el._windRaf.fps,
    streams: el.shadowRoot.querySelectorAll('path.stream').length, waves: el.shadowRoot.querySelectorAll('path.wave').length, n: el._flowLayer ? el._flowLayer.n : 0 }));
  const level = async l => { await impl(page).evaluate((el, l) => { el.setConfig({ ...el._config, animation_level: l }); el._render(); }, l); await page.waitForTimeout(150); return state(); };
  const auto = await state();
  expect([auto.level, auto.fps, auto.streams, auto.waves]).toEqual(['normal', 20, 5, 10]);      // auto on a desktop card: normal
  const intense = await level('intense'), minimal = await level('minimal'), off = await level('off');
  // Test note 0.26.7.0 UI hotfix (owner order): "intense" is lively again – more ribbons in three layers each, still 30 frames a second
  expect([intense.fps, intense.streams, intense.waves]).toEqual([30, 8, 24]);
  expect([minimal.fps, minimal.streams, minimal.waves]).toEqual([12, 3, 3]);
  expect([off.still, off.loop]).toEqual([true, false]);
  // the parts: without wind the air stands still, the rest may move; without ambient the rooms do not breathe
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: 'normal', animation_parts: ['weather', 'light'] }); el._render(); });
  await page.waitForTimeout(120);
  expect(await impl(page).evaluate(el => [!!el._windRaf, el.hasAttribute('data-no-wind'), el.hasAttribute('data-no-ambient'), el.hasAttribute('data-no-weather')])).toEqual([false, true, true, false]);
  // a phone (narrow card): auto is minimal
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: undefined, animation_parts: undefined }); });
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(200); await impl(page).evaluate(el => el._render());
  expect((await state()).level).toBe('minimal');
  await page.setViewportSize({ width: 1280, height: 900 }); await page.waitForTimeout(200); await impl(page).evaluate(el => el._render());
  // untouched for 3 minutes: calmer; for 11 minutes: rests (still); a touch brings the chosen level back
  await impl(page).evaluate(el => { el._lastActive = Date.now() - 3 * 60e3; el._render(); });
  expect((await state()).level).toBe('minimal');
  await impl(page).evaluate(el => { el._lastActive = Date.now() - 11 * 60e3; el._render(); });
  const rest = await state();
  expect([rest.level, rest.still, rest.loop]).toEqual(['rest', true, false]);
  await impl(page).evaluate(el => el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 1 })));
  await page.waitForTimeout(150);
  const woke = await state();
  expect([woke.level, woke.loop]).toEqual(['normal', true]);
  // reduced motion: off, whatever the level
  await page.emulateMedia({ reducedMotion: 'reduce' }); await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: 'intense' }); el._render(); });
  expect(await state()).toMatchObject({ level: 'off', still: true, loop: false });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  // the menu's choice is kept for this card while the card's own setting stays the one it replaced
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: undefined }); el._menuOpen = true; el._render(); el.shadowRoot.querySelector('[data-motion-level="minimal"]').click(); });
  expect(await impl(page).evaluate(el => { el.setConfig({ auto_focus: 'hint' }); return el.getAttribute('data-motion'); })).toBe('minimal');
  expect(await impl(page).evaluate(el => { el.setConfig({ auto_focus: 'hint', animation_level: 'intense' }); return el.getAttribute('data-motion'); })).toBe('intense');
});

test('0.26.7.0(2) calmer wind: no two streams alike, no white strokes ("shooting stars") around the house, the strength readable, the direction kept', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await page.waitForTimeout(400);
  const r = await impl(page).evaluate(el => {
    const waves = el._waves.filter(w => w.el.classList.contains('stream'));
    const L = el._flowLayer;
    return { geo: waves.map(w => [w.geo.amp, w.geo.wavelength, w.geo.pace, w.geo.offset].map(v => Math.round(v * 1000) / 1000).join('|')),
      opacity: waves.map(w => w.el.getAttribute('stroke-opacity')), lens: waves.map(w => Math.round(w.frame.length * 100) / 100),
      sparks: L.routes.some(rt => rt.parts.some(p => 'spark' in p)), n: L.n, ink: (() => { const cv = el.shadowRoot.querySelector('canvas.flow'); if (!cv) return 0; const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data; let k = 0; for (let i = 3; i < d.length; i += 16) if (d[i]) k++; return k; })(), dir: el._outdoorWind().wind.from_deg };
  });
  expect(new Set(r.geo).size).toBe(r.geo.length);                     // every stream its own wave, pace and phase
  expect(new Set(r.opacity).size).toBeGreaterThan(1); expect(new Set(r.lens).size).toBeGreaterThan(1);
  expect(r.sparks).toBe(false);
  expect([r.n, r.ink]).toEqual([0, 0]);                                 // no white strokes around the house at all
  expect(r.dir).toBe(307);
  // the lanes are not an even grid and the streams' phases differ at the same moment
  const lanes = await page.evaluate(async () => { const M = await import('/freshairiq-house-motion.js?v=0.26.7.0'); const v = M.streamVariety(5, 3); const gaps = v.slice(1).map((x, i) => x.lane - v[i].lane); return { gaps, same: M.streamVariety(5, 3).map(x => x.lane).join() === v.map(x => x.lane).join() }; });
  expect(Math.max(...lanes.gaps) - Math.min(...lanes.gaps)).toBeGreaterThan(0.02); expect(lanes.same).toBe(true);
  // the streams still come from the measured direction: a wind from the north-west moves the air to the south-east (right, down)
  const flow = await impl(page).evaluate(el => { const s = el.shadowRoot.querySelector('path.stream.pass, path.stream.deflect'); const pts = s.getAttribute('d').split(/[ML ]+/).filter(Boolean).map(p => p.split(',').map(Number)); return [pts[pts.length - 1][0] - pts[0][0], pts[pts.length - 1][1] - pts[0][1]]; });
  expect(flow[0]).toBeGreaterThan(0); expect(flow[1]).toBeGreaterThan(0);
  // the air still comes in through an open window (the canvas carries only that), without bright heads
  await impl(page).evaluate(el => { const h = JSON.parse(JSON.stringify(el._house)); h.wind = { ...h.wind, from_deg: 0 }; h.airflow.openings.o_bad = { ...h.airflow.openings.o_bad, pending: false, state: 'open', pressure: 0.8 }; el._house = h; el._windSmooth = 0; el._render(); });
  await page.waitForTimeout(800);
  const inside = await impl(page).evaluate(el => [el._flowLayer.routes.length, el._flowLayer.stats.inside, el._flowLayer.routes.some(rt => rt.parts.some(p => 'spark' in p))]);
  expect(inside[0]).toBeGreaterThan(0); expect(inside[1]).toBeGreaterThan(0); expect(inside[2]).toBe(false);
  // the strength: a breath of air draws fewer, quieter ribbons than a storm
  const ribbons = async v => { await impl(page).evaluate((el, v) => { el._house = { ...el._house, wind: { ...el._house.wind, speed_ms: v, gust_ms: v > 15 ? v * 1.4 : null } }; el._render(); }, v); return impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('path.stream:not(.inflow)')].map(p => Number(p.getAttribute('stroke-opacity')))); };
  const calm = await ribbons(1), storm = await ribbons(22);
  expect(calm.length).toBeLessThan(storm.length);
  expect(Math.max(...calm)).toBeLessThan(Math.max(...storm));
});

test('0.26.7.0(2) performance: one loop for every card at its own pace, nothing under a window, far less work per second than 0.26.7.0', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await page.waitForTimeout(300);
  // the d-attribute writes per second of the wind ribbons (0.26.7.0: ~630 for 21 ribbons at 30 frames a second)
  const writes = await impl(page).evaluate(async el => { let n = 0; const o = new MutationObserver(l => { n += l.length; }); o.observe(el.shadowRoot, { attributes: true, subtree: true, attributeFilter: ['d'] }); await new Promise(r => setTimeout(r, 2000)); o.disconnect(); return n / 2; });
  expect(writes).toBeLessThan(260);
  // a second card shares the loop: still one animation frame per due frame, two entries in it
  await page.evaluate(() => { const c = document.createElement('freshairiq-house-card'); c.id = 'card2'; c.setConfig({ animation_level: 'minimal' }); document.getElementById('m').appendChild(c); c.hass = document.getElementById('card').hass; });
  await page.waitForFunction(() => document.querySelectorAll('freshairiq-house-card-impl').length === 2);
  await page.waitForTimeout(600);
  const loop = await page.evaluate(async () => { const M = await import('/freshairiq-house-motion.js?v=0.26.7.0'); let calls = 0; const orig = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = cb => { calls += 1; return orig(cb); }; await new Promise(r => setTimeout(r, 1000)); window.requestAnimationFrame = orig; return { calls, size: M.loopSize() }; });
  expect(loop.calls).toBeLessThan(40);                                // 0.26.7.0: ~60 per card and second
  // a window over the plan pauses it; closing it continues
  await impl(page).first().evaluate(el => { el._selected = { type: 'rooms', id: '' }; el._render(); });
  expect(await impl(page).first().evaluate(el => [el.hasAttribute('data-paused'), !!el._windRaf])).toEqual([true, false]);
  await impl(page).first().evaluate(el => el._closeDialog());
  expect(await impl(page).first().evaluate(el => [el.hasAttribute('data-paused'), !!el._windRaf])).toEqual([false, true]);
  await page.evaluate(() => { document.getElementById('card').remove(); document.getElementById('card2').remove(); });
  expect(await page.evaluate(async () => (await import('/freshairiq-house-motion.js?v=0.26.7.0')).loopSize())).toBe(0);
});

for (const [label, w, h] of [['phone portrait', 390, 844], ['phone landscape', 844, 390], ['tablet', 768, 1024], ['desktop', 1440, 900], ['narrow card', 320, 640]]) {
  test(`0.26.7.0(2) layout ${label}: weather, rooms, room, house details and menu fit the screen and scroll inside`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await mount(page, { config: { rooms_button: true } });
    await page.evaluate(() => { const m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width,initial-scale=1'; document.head.appendChild(m); });
    await setup(page, {}, STATES(), FORECAST);
    for (const sel of [{ type: 'weather', id: '' }, { type: 'rooms', id: '' }, { type: 'room', id: 'r_bad' }, { type: 'house', id: '' }, 'menu']) {
      const r = await impl(page).evaluate((el, [sel, fc]) => {
        if (sel === 'menu') { el._selected = null; el._menuOpen = true; } else { el._menuOpen = false; el._selected = sel; }
        el._forecast = fc; el._render();
        const d = el.shadowRoot.querySelector(sel === 'menu' ? 'dialog.menudlg' : 'dialog.roomdlg'), box = d.querySelector('.dlg').getBoundingClientRect(), body = d.querySelector('.body');
        return { open: d.open, inside: box.left >= -1 && box.top >= -1 && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1, sideways: body.scrollWidth - body.clientWidth, page: document.documentElement.scrollWidth - innerWidth };
      }, [sel, FORECAST]);
      expect(r, `${label} ${JSON.stringify(sel)}`).toEqual({ open: true, inside: true, sideways: expect.any(Number), page: expect.any(Number) });
      expect(r.sideways, `${label} ${JSON.stringify(sel)}`).toBeLessThanOrEqual(1);
      expect(r.page, `${label} ${JSON.stringify(sel)}`).toBeLessThanOrEqual(1);
    }
  });
}

// ---- 0.26.7.0(2) corrections -----------------------------------------------------------------------------------------
test('0.26.7.0(2) correction 1: an explicit weather_chip choice wins over older weather_sensors; weather_sensors alone stay as before', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  const chip = () => impl(page).evaluate(el => { const c = el.shadowRoot.querySelector('.topbar .weather'); return c ? [...c.querySelectorAll(':scope > span')].map(s => s.textContent.trim()) : null; });
  const states = { ...STATES(), 'sensor.outside_temp': { entity_id: 'sensor.outside_temp', state: '4.2', attributes: { unit_of_measurement: '°C', device_class: 'temperature', friendly_name: 'Außen' } } };
  await setup(page, { weather_sensors: ['sensor.outside_temp'], weather_chip: ['wind'] }, states);
  expect(await chip()).toEqual(['🍃 SW 18 km/h']);                         // the reproduced case: wind, not the sensor's temperature
  await setup(page, { weather_sensors: ['sensor.outside_temp'], weather_chip: undefined }, states);
  expect(await chip()).toEqual(['🌡️ 4,2 °C']);                             // an older card: its own sensor exactly as before
  await setup(page, { weather_sensors: 'sensor.outside_temp', weather_chip: ['temperature', 'humidity'] }, states);
  expect(await chip()).toEqual(['🌡️ 8,5 °C', '💧 88 %']);
});

test('0.26.7.0(2) correction 2: whatever the weather display shows, a tap opens the weather window; the window keeps the card\'s choice of parts', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  const open = info => impl(page).evaluate((el, info) => {
    el.setConfig({ ...el._config, weather_info: info }); el._selected = null; el._forecast = { hourly: [], daily: [] }; el._render();
    const c = el.shadowRoot.querySelector('.topbar .weather');
    if (!c) return null;
    const tag = c.tagName; c.click();
    const d = el.shadowRoot.querySelector('dialog.roomdlg');
    return { tag, open: !!(d && d.open && el._selected && el._selected.type === 'weather'), panels: d ? [...d.querySelectorAll('.wxv > section.panel')].map(s => s.classList[1]) : [] };
  }, info);
  await setup(page, {}, STATES(), FORECAST);
  expect(await open(['compact'])).toEqual({ tag: 'BUTTON', open: true, panels: [] });                       // reported case: was a <div>
  expect(await open(['compact', 'sun', 'wind'])).toEqual({ tag: 'BUTTON', open: true, panels: ['sun', 'wind'] });
  expect(await open(['compact', 'overview', 'sun', 'wind', 'hourly', 'daily'])).toMatchObject({ tag: 'BUTTON', open: true });
  expect(await open(['overview', 'sun'])).toBe(null);                                                       // no compact display: none at the top right
  expect(await open(undefined)).toMatchObject({ tag: 'BUTTON', open: true });                                // never chosen: as before
});

const LEARNING = {
  learning_components: { overall_maturity_percent: 34, stage_label: 'Lernt dein Zuhause kennen', personal_optimization_ready: false,
    components: [{ key: 'room_physics', label: 'Raumphysik', maturity_percent: 40, samples: 12, evidence_text: '5 unterschiedliche Tage', status: 'Lernt' },
      { key: 'routines', label: 'Tagesroutinen', maturity_percent: 22, samples: 9, status: 'Lernt' }, { key: 'night_model', label: 'Nachtmodell', maturity_percent: 17, samples: 20, status: 'Lernt noch' },
      { key: 'forecast_validation', label: 'Prognosevalidierung', maturity_percent: 30, samples: 14, status: 'Lernt' }] },
  forecast_backtest: { reliability: { score_percent: 71, magnitude_accuracy_percent: 64, direction_accuracy_percent: 88 }, overall: { moisture_mae_ml: 42 } },
  learning_effectiveness: { samples: 6, independent_sessions: 5, distinct_days: 3, improvement_percent: 4.5, status_label: 'Sammelt Vergleichsdaten' },
  forecast_shadow_comparison: { samples: 6, production_mae_ml: 40, candidate_mae_ml: 35, mae_difference_ml: 5, improvement_percent: 12.5, status: 'collecting' },
};
test('0.26.7.0(2) correction 3: every view behind the FreshAirIQ card\'s details – learning, forecast quality with the formula comparison, water, threshold, night, pollen, decision, last airing', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  await page.evaluate(L => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, water_in_air_ml: 312, volume_m3: 18.5 } }, output_language: 'de', total_water_ml: 4100,
    ventilation_threshold_ml: 380, overnight_forecast_ml: 160, pollen_enabled: true, pollen_index: 2.1, pollen_limit: 3, intelligent_recommendation: { kind: 'ventilate', title: 'Jetzt lüften', reasons: ['Außen trockener'] }, ...L }), LEARNING);
  await page.waitForTimeout(100);
  const view = id => impl(page).evaluate((el, id) => { el._menuOpen = false; el._selected = { type: 'classic', id }; el._render(); const d = el.shadowRoot.querySelector('dialog.roomdlg');
    return { title: d.querySelector('h3').textContent, text: d.textContent.replace(/\s+/g, ' '), links: [...d.querySelectorAll('[data-classic-info]')].map(b => b.dataset.classicInfo), rooms: [...d.querySelectorAll('[data-classic-room]')].map(b => b.dataset.classicRoom), back: !!d.querySelector('.pactions.top button'), ids: d.querySelectorAll('.classic [id]').length }; }, id);
  // the menu leads there, the house details list every view
  const menu = await impl(page).evaluate(el => { el._menuOpen = true; el._render(); return [...el.shadowRoot.querySelectorAll('dialog.menudlg [data-classic-info]')].map(b => b.dataset.classicInfo); });
  expect(menu).toEqual(['learning']);
  const house = await impl(page).evaluate(el => { el._menuOpen = false; el._selected = { type: 'house', id: '' }; el._render(); return [...el.shadowRoot.querySelectorAll('dialog.roomdlg [data-classic-info]')].map(b => b.dataset.classicInfo); });
  expect(house).toEqual(['learning:quality', 'decision', 'water', 'threshold', 'night', 'pollen', 'lastvent']);
  const learning = await view('learning');
  expect(learning.text).toContain('Aktuell lernt FreshAirIQ'); expect(learning.text).toContain('Lernt dein Zuhause kennen'); expect(learning.text).toContain('34 %');
  expect(learning.links).toEqual(expect.arrayContaining(['learning:home', 'learning:forecast', 'learning:habits', 'learning:longterm']));
  await view('learning:quality');
  await expect.poll(() => impl(page).evaluate(el => !!(el._shadow && el._shadow.shadowSection))).toBe(true);   // the card's own section module
  const quality = await view('learning:quality');
  expect(quality.text).toContain('Wie gut FreshAirIQ aktuell vorhersagt'); expect(quality.text).toContain('71 %');
  expect(quality.text).toContain('Experiment: Neue Feuchteformel (passiver Test)'); expect(quality.text).toMatch(/40 ml MAE.*35 ml MAE/);
  // Test note 0.26.7.0 UI hotfix (owner order): one Back for every window (top left in the header) replaces the view's own back link – reached from the
  // learning overview, Back returns there
  await view('learning');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg [data-classic-info="learning:quality"]').click());
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg header [data-nav-back]'))).toBe(true);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg header [data-nav-back]').click());
  expect(await impl(page).evaluate(el => el._selected.id)).toBe('learning');   // back to the learning overview
  const water = await view('water');
  expect(water.text).toContain('ml über'); expect(water.rooms).toContain('bad'); expect(water.ids).toBe(0);
  for (const id of ['threshold', 'night', 'pollen', 'decision', 'lastvent', 'learning:home', 'learning:longterm']) expect((await view(id)).text.length, id).toBeGreaterThan(40);
  // a room in a view opens the room's details in the house map
  await view('water');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg [data-classic-room="bad"]').click());
  expect(await impl(page).evaluate(el => [el._selected.type, el.shadowRoot.querySelector('dialog.roomdlg h3').textContent])).toEqual(['room', 'Bad']);
  // a learning area leads one level deeper
  await impl(page).evaluate(el => { el._selected = { type: 'classic', id: 'learning' }; el._render(); el.shadowRoot.querySelector('dialog.roomdlg [data-classic-info="learning:home"]').click(); });
  expect(await impl(page).evaluate(el => el._selected.id)).toBe('learning:home');
});

test('0.26.7.0(2) correction 3: the room details carry every value the FreshAirIQ card shows for a room', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ output_language: 'de', rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad,
    potential_ml: 410, realistic_potential_ml: 180, forecast_cost: 0.12, airflow_factor: 0.85, last_measurement_at: '2026-11-06T10:00:00Z', last_measurement_valid: true,
    learning_diagnosis: 'Learned: duration 12 min', last_learning_valid: true, last_learning_at: '2026-11-05T18:00:00Z', outcome_feedback_samples: 7, outcome_success_rate: 0.71, outcome_removed_factor: 0.93,
    shadow_learning_status: 'Vergleicht Produktionsmodell mit Alternativen', shadow_learning_promotions: 2, shadow_learning_rollbacks: 1, routine_maturity: 44, routine_source_samples: 31, routine_expected_source_ml_min: 0.5,
    strategy_maturity: 38, strategy_samples: 12, strategy_outcome_samples: 9, history_14d: [{ removed_ml: 900, sessions: 2, ventilation_minutes: 24, cost: 0.2 }, { removed_ml: 650, sessions: 1, ventilation_minutes: 12, cost: 0.1 }] } } }));
  await page.waitForTimeout(80);
  const text = await impl(page).evaluate(el => { el._selected = { type: 'room', id: 'r_bad' }; el._render(); return el.shadowRoot.querySelector('dialog.roomdlg').textContent.replace(/\s+/g, ' '); });
  for (const part of ['Theoretisch entfernbar', '≈ 410 ml', '≈ 180 ml', '0,12 €', 'Luftstromfaktor', '0,85', 'Messwerte plausibel', 'Gelernt: Dauer 12 min', 'Rückmeldung Realität', '71 %', '7 Vergleiche · Feuchtefaktor 0,93',
    'Vergleicht Produktionsmodell mit Alternativen', 'Übernahmen 2 · Rollbacks 1', 'Routine-IQ', '44 %', '31 Zeitmuster-Proben · erwartet 30 ml/h', 'Strategie-IQ', '12 Empfehlungen ausgewertet · 9 Ergebnisse',
    'Bilanz der letzten 2 Tage', '−1,55 l', 'Lüftungen', '36', '0,30 €']) expect(text, part).toContain(part);
  // a display-only room says so
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ output_language: 'de', rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, calculation_enabled: false } } }));
  await page.waitForTimeout(80);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg').textContent)).toContain('Nur anzeigen');
});

// ---------------------------------------------------------------------------------------------------------------------------
// 0.26.7.0 UI hotfix: Intensiv stays intense, the menu without "view on the plan", a correct sun arc, Back in every window,
// a weather button that takes real clicks and taps, the absolute humidity, one continuous animated surface
const W_URL = 'http://freshairiq.test/freshairiq-house-weather.js';
const SUN_REF = JSON.parse(fs.readFileSync(new URL('./fixtures/sun_reference.json', import.meta.url), 'utf8'));
const AH_REF = JSON.parse(fs.readFileSync(new URL('./fixtures/abs_humidity_reference.json', import.meta.url), 'utf8'));

test('0.26.7.0 UI hotfix 1: a chosen level stays what it is after more than 2 minutes untouched; every level is its own; auto still calms', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  const at = async (l, idleMin) => { await impl(page).evaluate((el, [l, idleMin]) => { el.setConfig({ ...el._config, animation_level: l }); el._lastActive = Date.now() - idleMin * 60e3; el._render(); }, [l, idleMin]); await page.waitForTimeout(150);
    return impl(page).evaluate(el => ({ level: el.getAttribute('data-motion'), fps: el._windRaf ? el._windRaf.fps : 0, waves: el.shadowRoot.querySelectorAll('path.wave').length, loop: !!el._windRaf })); };
  const levels = {};
  for (const l of ['off', 'minimal', 'normal', 'intense']) levels[l] = await at(l, 0);
  // all four distinguishable (frame rate and layers of air)
  expect(new Set(Object.values(levels).map(s => `${s.fps}|${s.waves}`)).size).toBe(4);
  expect(levels.intense.fps).toBeGreaterThan(levels.normal.fps); expect(levels.intense.waves).toBeGreaterThan(levels.normal.waves);
  expect(levels.intense.fps).toBeLessThanOrEqual(30);                       // lively, never the browser's 60
  // more than 2 (3, then 9) minutes without a touch: the chosen level is kept – also intense, also normal
  for (const idle of [3, 9]) {
    expect(await at('intense', idle), `intense ${idle}`).toEqual(levels.intense);
    expect(await at('normal', idle), `normal ${idle}`).toEqual(levels.normal);
  }
  // the loop keeps the level while time passes (the 5 s check inside the loop)
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: 'intense' }); el._lastActive = Date.now() - 5 * 60e3; el._levelCheck = 0; el._render(); });
  await page.waitForTimeout(400);
  expect(await impl(page).evaluate(el => [el.getAttribute('data-motion'), el._windRaf && el._windRaf.fps])).toEqual(['intense', 30]);
  // auto alone adapts: calmer after 2 minutes, resting after 10
  expect((await at(undefined, 3)).level).toBe('minimal');
  expect((await at(undefined, 11)).level).toBe('rest');
  // hidden page: paused whatever the level
  await at('intense', 0);
  await impl(page).evaluate(el => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); });
  await page.waitForTimeout(120);
  expect(await impl(page).evaluate(el => [el.hasAttribute('data-paused'), !!el._windRaf])).toEqual([true, false]);
  await impl(page).evaluate(() => { Object.defineProperty(document, 'hidden', { value: false, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); });
});

test('0.26.7.0 UI hotfix 2: the menu has no "view on the plan" any more; the card setting decides the view and the Animation area stays', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page, { config: { layer: 'humidity' } });
  const menu = await impl(page).evaluate(el => { el._menuOpen = true; el._render(); const d = el.shadowRoot.querySelector('dialog.menudlg');
    return { layers: d.querySelectorAll('[data-layer]').length, motion: d.querySelectorAll('[data-motion-level]').length, text: d.textContent, layer: el._layer }; });
  expect(menu.layers).toBe(0);
  expect(menu.text).not.toContain('Ansicht im Grundriss');
  expect(menu.motion).toBeGreaterThanOrEqual(4);
  expect(menu.layer).toBe('humidity');
  // a layer stored by the old menu no longer hides a changed card setting
  const r = await impl(page).evaluate(el => { el._layer = 'co2'; el._persist(); el.setConfig({ ...el._config, layer: 'temperature' }); el._restore && el._restore(); return el._layer; });
  expect(r).toBe('temperature');
});

test('0.26.7.0 UI hotfix 3: the sun arc – the reported 07.11. case, noon, sunset, night, polar day and night, time zones and DST, against astral', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  const res = await page.evaluate(async ([url, ref]) => {
    const W = await import(url);
    const local = (iso, tz) => new Date(iso).toLocaleTimeString('de', { hour: '2-digit', minute: '2-digit', timeZone: tz });
    // the reported case (Home Assistant's own sunrise 07:26 and sunset 16:42 local, shown at 07:59, Europe/Berlin)
    const tz = 'Europe/Berlin', now = Date.parse('2026-11-07T06:59:00Z');
    const sun = { rising: '2026-11-08T06:28:00Z', setting: '2026-11-07T15:42:00Z', elevation: 2.4 };
    const d = W.sunDay({ now, tz, sun });
    const model = { sun, hourly: [], daily: [] };
    const html = W.overviewHtml({ ...W.weatherModel({}), sun: { ...sun, azimuth: 120 }, entityId: 'weather.x', available: true }, { lang: 'de', info: ['sun'], details: [], now, tz });
    const box = document.createElement('div'); box.innerHTML = html; document.body.appendChild(box);
    const arc = box.querySelector('path.arc-path'), dot = box.querySelector('circle.sunpos'), cx = +dot.getAttribute('cx'), cy = +dot.getAttribute('cy');
    // the distance of the sun to the drawn curve (the curve sampled finely)
    let dist = Infinity; for (let i = 0; i <= 2000; i++) { const p = arc.getPointAtLength(arc.getTotalLength() * i / 2000); dist = Math.min(dist, Math.hypot(p.x - cx, p.y - cy)); }
    const labels = [...box.querySelectorAll('text.t-axis')].map(t => t.textContent.trim());
    box.remove();
    // noon and the evening: the sun at the top and at the right end; night below the horizon
    const noon = W.sunDay({ now: Date.parse('2026-11-07T11:04:00Z'), tz, sun: { rising: '2026-11-08T06:28:00Z', setting: '2026-11-07T15:42:00Z' } });
    const eve = W.sunDay({ now: Date.parse('2026-11-07T15:41:00Z'), tz, sun: { rising: '2026-11-08T06:28:00Z', setting: '2026-11-07T15:42:00Z' } });
    const night = W.sunDay({ now: Date.parse('2026-11-07T21:00:00Z'), tz, sun: { rising: '2026-11-08T06:28:00Z', setting: '2026-11-08T15:40:00Z' } });
    const dawn = W.sunDay({ now: Date.parse('2026-11-07T04:00:00Z'), tz, sun: { rising: '2026-11-07T06:26:00Z', setting: '2026-11-07T15:42:00Z' } });
    // against astral (Home Assistant's own sun library): every place and day of the fixture, with the location
    const diffs = ref.map(c => { const [y, m, dd] = c.date.split('-').map(Number); const e = W.sunEvents(c.lat, c.lon, y, m, dd);
      if (c.polar) return { id: `${c.place} ${c.date}`, ok: e.polar === c.polar };
      return { id: `${c.place} ${c.date}`, ok: !e.polar && Math.abs(e.rise - Date.parse(c.rise)) < 2 * 60e3 && Math.abs(e.set - Date.parse(c.set)) < 2 * 60e3 }; });
    const polarHtml = W.overviewHtml({ ...W.weatherModel({}), sun: { elevation: 3 }, entityId: 'weather.x', available: true }, { lang: 'de', info: ['sun'], details: [], now: Date.parse('2026-06-21T10:00:00Z'), tz: 'Europe/Oslo', geo: { lat: 69.6492, lon: 18.9553 } });
    const winterHtml = W.overviewHtml({ ...W.weatherModel({}), sun: { elevation: -3 }, entityId: 'weather.x', available: true }, { lang: 'en', info: ['sun'], details: [], now: Date.parse('2026-12-15T10:00:00Z'), tz: 'Europe/Oslo', geo: { lat: 69.6492, lon: 18.9553 } });
    // with Home Assistant's location the times are today's own (Sydney in its summer time; New York on the day DST ends)
    const syd = W.sunDay({ now: Date.parse('2026-11-07T02:00:00Z'), tz: 'Australia/Sydney', lat: -33.8688, lon: 151.2093 });
    const sydRef = ref.find(c => c.place === 'sydney' && c.date === '2026-11-07');
    return { progress: d.progress, phase: d.phase, dist, labels, rise: local(new Date(d.rise).toISOString(), tz), set: local(new Date(d.set).toISOString(), tz),
      noon: noon.progress, eve: eve.progress, night: [night.phase, night.progress], dawn: [dawn.phase, dawn.progress], diffs: diffs.filter(x => !x.ok).map(x => x.id), count: diffs.length,
      polarDay: polarHtml.includes('Polartag'), polarNight: winterHtml.includes('Polar night'), syd: [syd.phase, Math.abs(syd.rise - Date.parse(sydRef.rise)) < 3 * 60e3] };
  }, [W_URL, SUN_REF]);
  expect(res.phase).toBe('day');
  expect(res.progress).toBeGreaterThan(0.04); expect(res.progress).toBeLessThan(0.08);    // 33 min of 9 h 14 min ≈ 0.06 – just after sunrise
  expect(res.dist).toBeLessThan(0.6);                                                    // the sun lies on the drawn curve
  expect(res.labels).toEqual(['↑ 07:28', '↓ 16:42']);                                     // today's times from Home Assistant (local time)
  expect(Math.abs(res.noon - 0.5)).toBeLessThan(0.02);                                   // solar noon at the top
  expect(res.eve).toBeGreaterThan(0.99);
  expect(res.night[0]).toBe('night'); expect(res.night[1]).toBeGreaterThan(0.25); expect(res.night[1]).toBeLessThan(0.45);
  expect(res.dawn[0]).toBe('night'); expect(res.dawn[1]).toBeGreaterThan(0.8);   // 05:00, sunrise at 07:26 after a night since 16:42
  expect(res.diffs).toEqual([]); expect(res.count).toBeGreaterThanOrEqual(15);
  expect([res.polarDay, res.polarNight]).toEqual([true, true]);
  expect(res.syd).toEqual(['day', true]);
});

test('0.26.7.0 UI hotfix 3: the sun arc fits a narrow card and the side column', async ({ page }) => {
  for (const [w, h] of [[360, 780], [1440, 900]]) {
    await page.setViewportSize({ width: w, height: h });
    await mount(page);
    await setup(page, { weather_info: ['compact', 'overview', 'sun'] });
    const r = await impl(page).evaluate(el => { el._selected = { type: 'weather', id: '' }; el._render(); const s = el.shadowRoot.querySelector('dialog.roomdlg section.sun svg[viewBox="0 0 320 150"]'); const b = s.getBoundingClientRect();
      const t = [...s.querySelectorAll('text')].map(x => x.getBoundingClientRect()); return { w: b.width, inside: t.every(x => x.left >= b.left - 1 && x.right <= b.right + 1 && x.bottom <= b.bottom + 1) }; });
    expect(r.w).toBeGreaterThan(200); expect(r.inside).toBe(true);
  }
});

test('0.26.7.0 UI hotfix 4: Back in every window – one level at a time, the scroll kept, no menu step from the map, Escape like Back, one native dialog', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 420 });   // short: the rooms overview scrolls
  await mount(page, { config: { rooms_button: true } });
  const state = () => impl(page).evaluate(el => { const open = [...el.shadowRoot.querySelectorAll('dialog')].filter(d => d.open);
    const d = open[0]; return { open: open.length, kind: d ? (d.classList.contains('menudlg') ? 'menu' : `${el._selected.type}:${el._selected.id}`) : null, back: !!(d && d.querySelector('header [data-nav-back]')), close: !!(d && d.querySelector('[data-close-detail], [data-close-menu]')) }; });
  const click = sel => impl(page).evaluate((el, sel) => el.shadowRoot.querySelector(sel).click(), sel);
  // Menü → Lernen → Zurück → Menü
  await click('[data-menu]');
  expect(await state()).toMatchObject({ open: 1, kind: 'menu', back: false });
  await click('dialog.menudlg [data-classic-info="learning"]');
  expect(await state()).toEqual({ open: 1, kind: 'classic:learning', back: true, close: true });
  await click('dialog.roomdlg [data-nav-back]');
  expect(await state()).toMatchObject({ open: 1, kind: 'menu' });
  // Menü → Raumübersicht → Wohnen → Zurück → Raumübersicht (scroll kept) → Zurück → Menü
  await click('dialog.menudlg [data-rooms]');
  expect(await state()).toMatchObject({ kind: 'rooms:', back: true });
  const top = await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('dialog.roomdlg .body'); b.scrollTop = 60; return b.scrollTop; });
  expect(top).toBeGreaterThan(0);
  await click('dialog.roomdlg [data-room-open="r_wohnen"]');
  expect(await state()).toMatchObject({ kind: 'room:r_wohnen', back: true });
  await click('dialog.roomdlg [data-nav-back]');
  expect(await state()).toMatchObject({ kind: 'rooms:', back: true });
  expect(Math.abs(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg .body').scrollTop) - top)).toBeLessThanOrEqual(2);   // where the list was
  // a live update keeps the window, its history and its Back
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de' }));
  await page.waitForTimeout(120);
  expect(await state()).toMatchObject({ open: 1, kind: 'rooms:', back: true });
  // Escape goes back one level like the button
  await page.keyboard.press('Escape');
  await page.waitForTimeout(80);
  expect(await state()).toMatchObject({ open: 1, kind: 'menu' });
  await click('[data-close-menu]');
  expect(await state()).toMatchObject({ open: 0 });
  // Karte → Räume → Raum → Zurück → Räume → Zurück closes (no menu step that never was)
  await click('.mapbar [data-rooms]');
  expect(await state()).toMatchObject({ kind: 'rooms:', back: false });
  await click('dialog.roomdlg [data-room-open="r_bad"]');
  expect(await state()).toMatchObject({ kind: 'room:r_bad', back: true });
  await page.keyboard.press('Escape'); await page.waitForTimeout(80);
  expect(await state()).toMatchObject({ kind: 'rooms:', back: false });
  // a room tapped on the plan opens without history; Close closes everything
  await click('dialog.roomdlg [data-close-detail]');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('svg.plan [data-room="r_wohnen"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  expect(await state()).toMatchObject({ open: 1, kind: 'room:r_wohnen', back: false });
  // English and a touch tap
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'en' }));
  await impl(page).evaluate(el => { el._hass = { ...el._hass, language: 'en', locale: { language: 'en' } }; el._closeDialog(); el._menuOpen = true; el._render(); });
  await click('dialog.menudlg [data-classic-info="learning"]');
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg [data-nav-back]').textContent)).toContain('Back');
  const b = await impl(page).evaluate(el => { const r = el.shadowRoot.querySelector('dialog.roomdlg [data-nav-back]').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.x, r.y]; });
  expect(b[2]).toBeLessThan(640); // top left of the window
  await page.mouse.click(b[0], b[1]);
  expect(await state()).toMatchObject({ open: 1, kind: 'menu' });
});

test('0.26.7.0 UI hotfix 5A: the weather button at the top right opens with a real mouse click and keyboard, after live updates and theme changes', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  await setup(page, {}, STATES(), FORECAST);
  const centre = () => impl(page).evaluate(el => { const r = el.shadowRoot.querySelector('.topbar button.weather').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
  const opened = () => impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg'); return !!(d && d.open && el._selected && el._selected.type === 'weather'); });
  const close = () => impl(page).evaluate(el => el._closeDialog());
  // what a real pointer hits there is the button (no decorative layer above it, none that swallows the click)
  const hit = await impl(page).evaluate(el => { const r = el.shadowRoot.querySelector('.topbar button.weather').getBoundingClientRect(); const n = el.shadowRoot.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !!(n && n.closest('button.weather')); });
  expect(hit).toBe(true);
  let [x, y] = await centre(); await page.mouse.click(x, y); expect(await opened()).toBe(true); await close();
  // after live updates (new readings, house data) and a theme change the same
  await page.evaluate(() => { window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de', outdoor_temperature: 7, outdoor_humidity: 80 }); window.__subs['freshairiq/house_map/subscribe'](window.__HOUSE); });
  await impl(page).evaluate(el => { el._hass = { ...el._hass, themes: { darkMode: true, theme: 'x' } }; el.style.setProperty('--primary-color', '#ff0000'); el._render(); });
  await page.waitForTimeout(150);
  [x, y] = await centre(); await page.mouse.click(x, y); expect(await opened()).toBe(true); await close();
  await impl(page).evaluate(el => el.shadowRoot.querySelector('.topbar button.weather').focus());
  await page.keyboard.press('Enter'); expect(await opened()).toBe(true);
});

test('0.26.7.0 UI hotfix 5A: the weather button opens with a touch tap (phone)', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const page = await ctx.newPage();
  await mount(page);
  await setup(page, {}, STATES(), FORECAST);
  const [x, y] = await impl(page).evaluate(el => { const r = el.shadowRoot.querySelector('.topbar button.weather').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
  await page.touchscreen.tap(x, y);
  await page.waitForTimeout(100);
  expect(await impl(page).evaluate(el => !!(el._selected && el._selected.type === 'weather'))).toBe(true);
  await ctx.close();
});

test('0.26.7.0 UI hotfix 5B: absolute humidity (g/m³) at the top right and in the weather window – FreshAirIQ\'s value and formula, invalid values left out, old choices kept', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mount(page);
  // the browser formula is exactly the integration's (model.absolute_humidity, fixture written by the Python test)
  const drift = await page.evaluate(async ([url, ref]) => { const W = await import(url); return Math.max(...ref.map(([t, h, v]) => Math.abs(W.absoluteHumidity(t, h) - v))); }, [W_URL, AH_REF]);
  expect(drift).toBeLessThan(1e-8);
  expect(await page.evaluate(async url => { const W = await import(url); return [W.absoluteHumidity(null, 50), W.absoluteHumidity('unknown', 50), W.absoluteHumidity(20, 140), W.absoluteHumidity(80, 50), W.absoluteHumidity(20, -1)]; }, W_URL)).toEqual([null, null, null, null, null]);
  const chip = () => impl(page).evaluate(el => { const c = el.shadowRoot.querySelector('.topbar .weather'); return c ? [...c.querySelectorAll(':scope > span')].map(s => s.textContent.trim()) : []; });
  const live = extra => page.evaluate(extra => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de', outdoor_temperature: 10, outdoor_humidity: 80, ...extra }), extra);
  // without an own weather entity: FreshAirIQ's own outdoor value, combinable with relative humidity
  await impl(page).evaluate(el => el.setConfig({ ...el._config, weather_entity: undefined, weather_chip: ['temperature', 'humidity', 'abs_humidity'] }));
  await live({ outdoor_absolute_humidity: 7.536 }); await page.waitForTimeout(80);
  expect(await chip()).toEqual(['🌡️ 10,0 °C', '💧 80 %', '💧 7,5 g/m³']);
  // relative alone, absolute alone
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, weather_chip: ['humidity'] }); el._render(); });
  expect(await chip()).toEqual(['💧 80 %']);
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, weather_chip: ['abs_humidity'] }); el._render(); });
  expect(await chip()).toEqual(['💧 7,5 g/m³']);
  // the integration says nothing (older version): computed from its temperature and humidity with the same formula
  await live({ outdoor_absolute_humidity: undefined }); await page.waitForTimeout(80);
  expect(await chip()).toEqual(['💧 7,5 g/m³']);
  // invalid or unavailable: left out, never a guess
  await live({ outdoor_absolute_humidity: null, outdoor_humidity: 'unavailable' }); await page.waitForTimeout(80);
  expect(await chip()).toEqual([]);
  // an own weather entity: its temperature and humidity (8.5 °C, 88 %) – the window shows it as one of its values
  await setup(page, { weather_chip: ['abs_humidity'], weather_details: undefined, weather_info: undefined });
  expect(await chip()).toEqual(['💧 7,5 g/m³']);
  const all = await openWeather(page);
  expect(all.facts).toContain('Absolute Feuchte 7,5 g/m³');
  // °F entity converted before the formula
  await setup(page, { weather_chip: ['abs_humidity'] }, { ...STATES(), 'weather.home': { ...STATES()['weather.home'], attributes: { ...STATES()['weather.home'].attributes, temperature: 47.3, temperature_unit: '°F' } } });
  expect(await chip()).toEqual(['💧 7,5 g/m³']);
  // an older explicit choice of window values stays exactly as it was (the new value does not appear by itself)
  await setup(page, { weather_details: ['humidity'] });
  expect((await openWeather(page)).facts).toEqual(['Luftfeuchte 88 %']);
  // the editor offers it for both places
  const boxes = await page.evaluate(() => { const ed = document.createElement('freshairiq-house-card-editor-impl'); document.body.appendChild(ed); ed.hass = { language: 'de', callWS: () => Promise.reject(new Error('x')) }; ed.setConfig({});
    const r = ['weather_chip', 'weather_details'].map(k => [...ed.querySelectorAll(`[data-list="${k}"][value="abs_humidity"]`)].map(b => b.parentElement.textContent.trim())); ed.remove(); return r; });
  expect(boxes).toEqual([['Absolute Luftfeuchtigkeit (g/m³)'], ['Absolute Luftfeuchtigkeit']]);
});

for (const [label, vw, vh, cfg] of [['phone 360 × 780', 360, 780, {}], ['landscape 844 × 390', 844, 390, {}], ['tablet 768 × 1024', 768, 1024, { layout: 'info' }], ['desktop 1440 × 900', 1440, 900, {}]]) {
  test(`0.26.7.0 UI hotfix 6 ${label}: one continuous surface – the drawing reaches under both bars, no solid bar, controls over it never cover rooms, windows or doors`, async ({ page }) => {
    await page.setViewportSize({ width: vw, height: vh });
    await mount(page, { config: { rooms_button: true, ...cfg } });
    await setup(page, {}, STATES('rainy'));
    await page.waitForTimeout(250);
    const r = await impl(page).evaluate(el => {
      const R = n => n.getBoundingClientRect(), q = s => el.shadowRoot.querySelector(s);
      const svg = R(q('svg.plan')), stage = R(q('.stage')), top = q('.topbar'), bar = q('.mapbar');
      const controls = [...el.shadowRoot.querySelectorAll('.topbar .weather, .topbar .moist, .topbar .notice, .mapbar button')].map(R);
      const plan = [...el.shadowRoot.querySelectorAll('svg.plan polygon.room, svg.plan line.op, svg.plan g.symbol, svg.plan .tag')].map(R);
      const bg = n => getComputedStyle(n).backgroundColor;
      return { svg, stage, top: top ? R(top) : null, bar: R(bar), bgTop: top ? bg(top) : null, bgBar: bg(bar), controls, plan,
        sky: [...el.shadowRoot.querySelectorAll('.map g.sky rect')].map(R).reduce((a, b) => ({ t: Math.min(a.t, b.top), b: Math.max(a.b, b.bottom) }), { t: Infinity, b: -Infinity }) };
    });
    const ov = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
    expect(r.bgBar).toBe('rgba(0, 0, 0, 0)'); if (r.top) expect(r.bgTop).toBe('rgba(0, 0, 0, 0)');   // no solid blue bars
    expect(r.svg.bottom).toBeGreaterThanOrEqual(r.bar.bottom - 2);                                     // the drawing runs under the bottom bar
    if (r.top) expect(r.svg.top).toBeLessThanOrEqual(r.top.top + 2);                                   // and under the top bar
    expect(r.sky.t).toBeLessThanOrEqual(r.stage.top + 2); expect(r.sky.b).toBeGreaterThanOrEqual(r.bar.bottom - 2);   // one sky from top to bottom
    for (const c of r.controls) for (const p of r.plan) expect(ov(c, p), JSON.stringify([c, p])).toBe(false);
  });
}

test('0.26.7.0 UI hotfix 6: animation off – a still, even background without bars; side column below the top bar; no second loop', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mount(page, { config: { animation_level: 'off', rooms_button: true } });
  await setup(page, {}, STATES('sunny'));
  await page.waitForTimeout(200);
  const r = await impl(page).evaluate(el => ({ loop: !!el._windRaf, bar: getComputedStyle(el.shadowRoot.querySelector('.mapbar')).backgroundColor,
    side: el.shadowRoot.querySelector('.wxside') ? [el.shadowRoot.querySelector('.wxside').firstElementChild.getBoundingClientRect().top, el.shadowRoot.querySelector('.topbar').getBoundingClientRect().bottom] : null }));
  expect(r.loop).toBe(false); expect(r.bar).toBe('rgba(0, 0, 0, 0)');
  if (r.side) expect(r.side[0]).toBeGreaterThanOrEqual(r.side[1] - 1);
  // several cards: one shared loop entry each, none more
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: 'intense' }); el._render(); });
  await page.waitForTimeout(150);
  expect(await page.evaluate(async () => (await import('/freshairiq-house-motion.js?v=0.26.7.0')).loopSize())).toBe(1);
});

test('0.26.7.0 card settings: seven groups, every key as before, dependent options in context, outdated floors/rooms, phone width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  const r = await page.evaluate(async () => {
    const ed = document.createElement('freshairiq-house-card-editor-impl'); document.body.appendChild(ed);
    const out = []; ed.addEventListener('config-changed', ev => out.push(ev.detail.config));
    const plan = { layout: { floors: [{ id: 'f_eg', name: 'Erdgeschoss' }], rooms: [{ room_key: 'bad', floor_id: 'f_eg' }] }, rooms: [{ key: 'bad', name: 'Bad' }] };
    ed.setConfig({ title: 'Haus', auto_focus: 'off', weather_info: ['compact'], floors_visible: ['f_eg', 'f_alt'], room_overrides: { bad: ['name'], weg: ['name'] } });
    ed.hass = { language: 'de', states: { 'weather.home': {} }, callWS: () => Promise.resolve(plan) };
    await new Promise(res => setTimeout(res, 30));
    const groups = [...ed.querySelectorAll('details[data-group]')].map(d => [d.dataset.group, d.querySelector('summary b').textContent, d.open]);
    const keys = [...new Set([...ed.querySelectorAll('[data-k],[data-list]')].map(el => el.dataset.k || el.dataset.list))].sort();
    const lockHidden = ed.querySelector('[data-when="auto_focus"]').hidden, detailsHidden = ed.querySelector('[data-when="overview"]').hidden;
    // typing in one group, opening another: nothing is lost, the open groups stay open after a redraw
    const title = ed.querySelector('[data-k="title"]'); title.value = 'Neues Haus'; title.dispatchEvent(new Event('change'));
    const wx = ed.querySelector('details[data-group="wx"]'); wx.open = true; wx.dispatchEvent(new Event('toggle'));
    ed._render();
    const afterRedraw = { title: ed.querySelector('[data-k="title"]').value, wxOpen: ed.querySelector('details[data-group="wx"]').open };
    const stale = ed.querySelector('[data-stale]') ? ed.querySelector('[data-stale]').parentElement.textContent : null;
    ed.querySelector('[data-stale]').click();
    const cleaned = out[out.length - 1];
    const sel = ed.querySelector('[data-k="auto_focus"]'); sel.value = 'hint'; sel.dispatchEvent(new Event('change'));
    const lockShown = !ed.querySelector('[data-when="auto_focus"]').hidden;
    const edge = ed.getBoundingClientRect().right, wide = Math.max(...[...ed.querySelectorAll('*')].map(el => el.getBoundingClientRect().right)) - edge;
    const datalist = [...ed.querySelectorAll('#faiq-weather-entities option')].map(o => o.value);
    ed.remove();
    return { groups, keys, lockHidden, detailsHidden, afterRedraw, stale, cleaned, lockShown, wide, datalist };
  });
  // Test note (0.26.7.0 UI/theme order, UI04): the owner ordered an eighth group "Design & Farben" – the seven groups
  // and every key of them are unchanged; the group adds the key "design" (own colours only appear for "custom")
  expect(r.groups.map(g => g[1])).toEqual(['Allgemein', 'Etagen & Navigation', 'Rauminformationen', 'Wetteranzeige', 'Wetterfenster', 'Animation & Darstellung', 'Design & Farben', 'Erweitert']);
  expect(r.groups[0][2]).toBe(true);                                          // only "General" is open at first
  expect(r.keys).toEqual(['animation', 'animation_level', 'animation_parts', 'auto_focus', 'default_floor', 'design', 'entry_id', 'floor', 'floors_visible', 'layer', 'layout',
    'manual_lock_min', 'ov:bad', 'room_info', 'rooms_button', 'title', 'weather_chip', 'weather_details', 'weather_effects', 'weather_entity', 'weather_info', 'weather_sensors']);
  expect([r.lockHidden, r.detailsHidden]).toEqual([true, true]);               // in context only: lock with auto focus, values with the overview
  expect(r.afterRedraw).toEqual({ title: 'Neues Haus', wxOpen: true });
  expect(r.stale).toContain('f_alt'); expect(r.stale).toContain('weg');
  expect(r.cleaned.floors_visible).toEqual(['f_eg']); expect(r.cleaned.room_overrides).toEqual({ bad: ['name'] });
  expect(r.cleaned.title).toBe('Neues Haus');
  expect(r.lockShown).toBe(true);
  expect(r.wide).toBeLessThanOrEqual(1);                                       // nothing sticks out of the settings (phone width)
  expect(r.datalist).toEqual(['weather.home']);
});
