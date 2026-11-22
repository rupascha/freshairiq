// House map 0.26.7.0(2): the weather window and the weather at the top right, the rooms overview, a room's details, the menu,
// the calmer wind and the animation levels – checked in a real browser (fixtures and mount as in house.spec.mjs).
import { test, expect } from '@playwright/test';
// Testvermerk 0.26.7.1: motion module checks import the exact URL the card loaded (same module instance) instead of a
// hard-coded ?v= version, which silently tested a second, empty instance after every version bump.
import fs from 'node:fs';
import { loadModule, settle } from './harness.mjs';

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
  await settle(page, 120);
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
  await settle(page, 200); await impl(page).evaluate(el => el._render());
  expect((await chip()).length).toBe(2);                                      // narrow: the first two of the choice
  await page.setViewportSize({ width: 1280, height: 800 });
  await settle(page, 200);
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
  await settle(page, 80);
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await settle(page, 80);
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
  await settle(page, 80);
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
  const level = async l => { await impl(page).evaluate((el, l) => { el.setConfig({ ...el._config, animation_level: l }); el._render(); }, l); await settle(page, 150); return state(); };
  const auto = await state();
  expect([auto.level, auto.fps, auto.streams, auto.waves]).toEqual(['normal', 20, 5, 10]);      // auto on a desktop card: normal
  const intense = await level('intense'), minimal = await level('minimal'), off = await level('off');
  // Test note 0.26.7.0 UI hotfix (owner order): "intense" is lively again – more ribbons in three layers each, still 30 frames a second
  expect([intense.fps, intense.streams, intense.waves]).toEqual([30, 8, 24]);
  expect([minimal.fps, minimal.streams, minimal.waves]).toEqual([12, 3, 3]);
  expect([off.still, off.loop]).toEqual([true, false]);
  // the parts: without wind the air stands still, the rest may move; without ambient the rooms do not breathe
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: 'normal', animation_parts: ['weather', 'light'] }); el._render(); });
  await settle(page, 120);
  expect(await impl(page).evaluate(el => [!!el._windRaf, el.hasAttribute('data-no-wind'), el.hasAttribute('data-no-ambient'), el.hasAttribute('data-no-weather')])).toEqual([false, true, true, false]);
  // a phone (narrow card): auto is minimal
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: undefined, animation_parts: undefined }); });
  await page.setViewportSize({ width: 390, height: 844 }); await settle(page, 200); await impl(page).evaluate(el => el._render());
  expect((await state()).level).toBe('minimal');
  await page.setViewportSize({ width: 1280, height: 900 }); await settle(page, 200); await impl(page).evaluate(el => el._render());
  // untouched for 3 minutes: calmer; for 11 minutes: rests (still); a touch brings the chosen level back
  await impl(page).evaluate(el => { el._lastActive = Date.now() - 3 * 60e3; el._render(); });
  expect((await state()).level).toBe('minimal');
  await impl(page).evaluate(el => { el._lastActive = Date.now() - 11 * 60e3; el._render(); });
  const rest = await state();
  expect([rest.level, rest.still, rest.loop]).toEqual(['rest', true, false]);
  await impl(page).evaluate(el => el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 1 })));
  await settle(page, 150);
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
  await settle(page, 400);
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
  const lanes = await page.evaluate(async () => { const M = await import(performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/freshairiq-house-motion.js'))); const v = M.streamVariety(5, 3); const gaps = v.slice(1).map((x, i) => x.lane - v[i].lane); return { gaps, same: M.streamVariety(5, 3).map(x => x.lane).join() === v.map(x => x.lane).join() }; });
  expect(Math.max(...lanes.gaps) - Math.min(...lanes.gaps)).toBeGreaterThan(0.02); expect(lanes.same).toBe(true);
  // the streams still come from the measured direction: a wind from the north-west moves the air to the south-east (right, down)
  const flow = await impl(page).evaluate(el => { const s = el.shadowRoot.querySelector('path.stream.pass, path.stream.deflect'); const pts = s.getAttribute('d').split(/[ML ]+/).filter(Boolean).map(p => p.split(',').map(Number)); return [pts[pts.length - 1][0] - pts[0][0], pts[pts.length - 1][1] - pts[0][1]]; });
  expect(flow[0]).toBeGreaterThan(0); expect(flow[1]).toBeGreaterThan(0);
  // the air still comes in through an open window (the canvas carries only that), without bright heads
  await impl(page).evaluate(el => { const h = JSON.parse(JSON.stringify(el._house)); h.wind = { ...h.wind, from_deg: 0 }; h.airflow.openings.o_bad = { ...h.airflow.openings.o_bad, pending: false, state: 'open', pressure: 0.8 }; el._house = h; el._windSmooth = 0; el._render(); });
  await settle(page, 800);
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
  await settle(page, 300);
  // the d-attribute writes per second of the wind ribbons (0.26.7.0: ~630 for 21 ribbons at 30 frames a second)
  const writes = await impl(page).evaluate(async el => { let n = 0; const o = new MutationObserver(l => { n += l.length; }); o.observe(el.shadowRoot, { attributes: true, subtree: true, attributeFilter: ['d'] }); await new Promise(r => setTimeout(r, 2000)); o.disconnect(); return n / 2; });
  expect(writes).toBeLessThan(260);
  // a second card shares the loop: still one animation frame per due frame, two entries in it
  await page.evaluate(() => { const c = document.createElement('freshairiq-house-card'); c.id = 'card2'; c.setConfig({ animation_level: 'minimal' }); document.getElementById('m').appendChild(c); c.hass = document.getElementById('card').hass; });
  await page.waitForFunction(() => document.querySelectorAll('freshairiq-house-card-impl').length === 2);
  await settle(page, 600);
  const loop = await page.evaluate(async () => { const M = await import(performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/freshairiq-house-motion.js'))); let calls = 0; const orig = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = cb => { calls += 1; return orig(cb); }; await new Promise(r => setTimeout(r, 1000)); window.requestAnimationFrame = orig; return { calls, size: M.loopSize() }; });
  expect(loop.calls).toBeLessThan(40);                                // 0.26.7.0: ~60 per card and second
  // a window over the plan pauses it; closing it continues
  await impl(page).first().evaluate(el => { el._selected = { type: 'rooms', id: '' }; el._render(); });
  expect(await impl(page).first().evaluate(el => [el.hasAttribute('data-paused'), !!el._windRaf])).toEqual([true, false]);
  await impl(page).first().evaluate(el => el._closeDialog());
  expect(await impl(page).first().evaluate(el => [el.hasAttribute('data-paused'), !!el._windRaf])).toEqual([false, true]);
  await page.evaluate(() => { document.getElementById('card').remove(); document.getElementById('card2').remove(); });
  expect(await page.evaluate(async () => (await import(performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/freshairiq-house-motion.js')))).loopSize())).toBe(0);
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
for (const [language, text] of [['de', 'ExperimentellDie neue Grundformel inklusive der Prognosen wurde anhand von 23.000 realen Lüftungen ausgewertet und übernommen. Aktuell gibt es keine neue experimentelle Formel.'],
  ['en', 'ExperimentalThe new base formula and its forecasts were evaluated using 23,000 real ventilation sessions and have been adopted. There is currently no new experimental formula.']]) {
  test(`house map, ${language}: "Experimentell" in the forecast quality shows the note on the adopted base formula once – with and without older comparison data`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await mount(page);
    await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
    for (const comparison of [LEARNING.forecast_shadow_comparison, null]) {
      await page.evaluate(([L, language, comparison]) => {
        const data = { ...L }; if (comparison) data.forecast_shadow_comparison = comparison; else delete data.forecast_shadow_comparison;
        window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: language, ...data });
      }, [LEARNING, language, comparison]);
      await settle(page, 80);
      const read = () => impl(page).evaluate(el => { el._menuOpen = false; el._selected = { type: 'classic', id: 'learning:quality' }; el._render(); const d = el.shadowRoot.querySelector('dialog.roomdlg');
        return { notes: [...d.querySelectorAll('.faiq-shadow-test')].map(n => n.textContent.replace(/\s+/g, ' ').trim()), text: d.textContent }; });
      await read();
      await expect.poll(() => impl(page).evaluate(el => !!(el._shadow && el._shadow.shadowSection) || !!el.shadowRoot.querySelector('dialog.roomdlg .faiq-shadow-test'))).toBe(true);
      const out = await read();
      expect(out.notes).toEqual([text]);
      expect(out.text).not.toMatch(/ml MAE|Testformel|test formula|passiver Test|passive test/);
    }
  });
}

test('0.26.7.0(2) correction 3: every view behind the FreshAirIQ card\'s details – learning, forecast quality with the formula comparison, water, threshold, night, pollen, decision, last airing', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  await page.evaluate(L => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, water_in_air_ml: 312, volume_m3: 18.5 } }, output_language: 'de', total_water_ml: 4100,
    ventilation_threshold_ml: 380, overnight_forecast_ml: 160, pollen_enabled: true, pollen_index: 2.1, pollen_limit: 3, intelligent_recommendation: { kind: 'ventilate', title: 'Jetzt lüften', reasons: ['Außen trockener'] }, ...L }), LEARNING);
  await settle(page, 100);
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
  // the section "Experimentell": the note on the adopted base formula once, none of the published comparison numbers
  expect(quality.text.split('Die neue Grundformel inklusive der Prognosen wurde anhand von 23.000 realen Lüftungen ausgewertet und übernommen. Aktuell gibt es keine neue experimentelle Formel.').length).toBe(2);
  expect(quality.text).toContain('Experimentell'); expect(quality.text).not.toMatch(/ml MAE|Testformel|passiver Test/);
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
  await settle(page, 80);
  const text = await impl(page).evaluate(el => { el._selected = { type: 'room', id: 'r_bad' }; el._render(); return el.shadowRoot.querySelector('dialog.roomdlg').textContent.replace(/\s+/g, ' '); });
  for (const part of ['Theoretisch entfernbar', '≈ 410 ml', '≈ 180 ml', '0,12 €', 'Luftstromfaktor', '0,85', 'Messwerte plausibel', 'Gelernt: Dauer 12 min', 'Rückmeldung Realität', '71 %', '7 Vergleiche · Feuchtefaktor 0,93',
    'Vergleicht Produktionsmodell mit Alternativen', 'Übernahmen 2 · Rollbacks 1', 'Routine-IQ', '44 %', '31 Zeitmuster-Proben · erwartet 30 ml/h', 'Strategie-IQ', '12 Empfehlungen ausgewertet · 9 Ergebnisse',
    'Bilanz der letzten 2 Tage', '−1,55 l', 'Lüftungen', '36', '0,30 €']) expect(text, part).toContain(part);
  // a display-only room says so
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ output_language: 'de', rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, calculation_enabled: false } } }));
  await settle(page, 80);
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
  const at = async (l, idleMin) => { await impl(page).evaluate((el, [l, idleMin]) => { el.setConfig({ ...el._config, animation_level: l }); el._lastActive = Date.now() - idleMin * 60e3; el._render(); }, [l, idleMin]); await settle(page, 150);
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
  await settle(page, 400);
  expect(await impl(page).evaluate(el => [el.getAttribute('data-motion'), el._windRaf && el._windRaf.fps])).toEqual(['intense', 30]);
  // auto alone adapts: calmer after 2 minutes, resting after 10
  expect((await at(undefined, 3)).level).toBe('minimal');
  expect((await at(undefined, 11)).level).toBe('rest');
  // hidden page: paused whatever the level
  await at('intense', 0);
  await impl(page).evaluate(el => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); });
  await settle(page, 120);
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
  await settle(page, 120);
  expect(await state()).toMatchObject({ open: 1, kind: 'rooms:', back: true });
  // Escape goes back one level like the button
  await page.keyboard.press('Escape');
  await settle(page, 80);
  expect(await state()).toMatchObject({ open: 1, kind: 'menu' });
  await click('[data-close-menu]');
  expect(await state()).toMatchObject({ open: 0 });
  // Karte → Räume → Raum → Zurück → Räume → Zurück closes (no menu step that never was)
  await click('.mapbar [data-rooms]');
  expect(await state()).toMatchObject({ kind: 'rooms:', back: false });
  await click('dialog.roomdlg [data-room-open="r_bad"]');
  expect(await state()).toMatchObject({ kind: 'room:r_bad', back: true });
  await page.keyboard.press('Escape'); await settle(page, 80);
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
  await settle(page, 150);
  [x, y] = await centre(); await page.mouse.click(x, y); expect(await opened()).toBe(true); await close();
  await impl(page).evaluate(el => el.shadowRoot.querySelector('.topbar button.weather').focus());
  await page.keyboard.press('Enter'); expect(await opened()).toBe(true);
});

test('0.26.7.0 UI hotfix 5A: the weather button opens with a touch tap (phone)', async ({ browser, browserName }) => {
  // Test note 0.26.7.0 CI fix (cross-browser): Firefox has no mobile emulation (isMobile) – a touch screen of phone size there;
  // the page gets Home Assistant's viewport meta, else a mobile engine lays it out 980 px wide and WebKit's tap misses the button
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: browserName !== 'firefox' });
  const page = await ctx.newPage();
  await mount(page);
  await page.evaluate(() => { const m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width,initial-scale=1'; document.head.appendChild(m); });
  await setup(page, {}, STATES(), FORECAST);
  const [x, y] = await impl(page).evaluate(el => { const r = el.shadowRoot.querySelector('.topbar button.weather').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
  await page.touchscreen.tap(x, y);
  await settle(page, 100);
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
  await live({ outdoor_absolute_humidity: 7.536 }); await settle(page, 80);
  expect(await chip()).toEqual(['🌡️ 10,0 °C', '💧 80 %', '💧 7,5 g/m³']);
  // relative alone, absolute alone
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, weather_chip: ['humidity'] }); el._render(); });
  expect(await chip()).toEqual(['💧 80 %']);
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, weather_chip: ['abs_humidity'] }); el._render(); });
  expect(await chip()).toEqual(['💧 7,5 g/m³']);
  // the integration says nothing (older version): computed from its temperature and humidity with the same formula
  await live({ outdoor_absolute_humidity: undefined }); await settle(page, 80);
  expect(await chip()).toEqual(['💧 7,5 g/m³']);
  // invalid or unavailable: left out, never a guess
  await live({ outdoor_absolute_humidity: null, outdoor_humidity: 'unavailable' }); await settle(page, 80);
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
    await settle(page, 250);
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
  await settle(page, 200);
  const r = await impl(page).evaluate(el => ({ loop: !!el._windRaf, bar: getComputedStyle(el.shadowRoot.querySelector('.mapbar')).backgroundColor,
    side: el.shadowRoot.querySelector('.wxside') ? [el.shadowRoot.querySelector('.wxside').firstElementChild.getBoundingClientRect().top, el.shadowRoot.querySelector('.topbar').getBoundingClientRect().bottom] : null }));
  expect(r.loop).toBe(false); expect(r.bar).toBe('rgba(0, 0, 0, 0)');
  if (r.side) expect(r.side[0]).toBeGreaterThanOrEqual(r.side[1] - 1);
  // several cards: one shared loop entry each, none more
  await impl(page).evaluate(el => { el.setConfig({ ...el._config, animation_level: 'intense' }); el._render(); });
  await settle(page, 150);
  expect(await page.evaluate(async () => (await import(performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/freshairiq-house-motion.js')))).loopSize())).toBe(1);
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

test('U02 (0.26.7.1): the weather column keeps its scroll position per view across live updates', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 520 });
  await mount(page);
  await setup(page, {}, STATES('rainy'), FORECAST);
  await settle(page, 200);
  const r = await impl(page).evaluate(async el => {
    const aside = () => el.shadowRoot.querySelector('.wxside');
    if (!aside()) return { missing: true };
    const scrollable = aside().scrollHeight - aside().clientHeight;
    aside().scrollTop = Math.min(120, scrollable);
    aside().dispatchEvent(new Event('scroll'));
    const before = aside().scrollTop;
    el._render();                                                              // a live update
    const afterLive = aside().scrollTop;
    const floor = el._floor;
    el._floor = floor === 'f_eg' ? 'f_og' : 'f_eg'; el._render();             // another view starts at its own position
    const otherView = aside().scrollTop;
    el._floor = floor; el._render();                                          // and back: where it was
    return { scrollable, before, afterLive, otherView, back: aside().scrollTop };
  });
  expect(r.missing).toBeUndefined();
  expect(r.scrollable).toBeGreaterThan(40);
  expect(r.before).toBeGreaterThan(0);
  expect(r.afterLive).toBe(r.before);
  expect(r.otherView).toBe(0);
  expect(r.back).toBe(r.before);
});

test('U04 (0.26.7.1): every menu entry and a nested page go back exactly one level; Close closes; Escape like Back', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 700 });
  await mount(page, { config: { rooms_button: true } });
  await setup(page, {}, STATES('rainy'), FORECAST);
  const state = () => impl(page).evaluate(el => { const open = [...el.shadowRoot.querySelectorAll('dialog')].filter(d => d.open); const d = open[0];
    return { open: open.length, kind: d ? (d.classList.contains('menudlg') ? 'menu' : `${el._selected && el._selected.type}`) : null, back: !!(d && d.querySelector('header [data-nav-back]')),
      floor: el._floor }; });
  const click = sel => impl(page).evaluate((el, sel) => { const n = el.shadowRoot.querySelector(sel); if (!n) throw new Error(`missing ${sel}`); n.click(); }, sel);
  const floor = (await state()).floor;
  for (const item of ['[data-house-details]', '[data-weather-open]', '[data-rooms]', '[data-classic-info="learning"]', '[data-ventlog]', '[data-support]']) {
    await click('[data-menu]');
    await click(`dialog.menudlg ${item}`);
    const inside = await state();
    expect(inside, item).toMatchObject({ open: 1, back: true });
    expect(inside.kind, item).not.toBe('menu');
    await click('dialog.roomdlg [data-nav-back]');
    expect(await state(), item).toMatchObject({ open: 1, kind: 'menu', floor });   // one level: the menu, not closed
    // the same page again: Escape goes back like the button, Close closes everything
    await click(`dialog.menudlg ${item}`);
    await page.keyboard.press('Escape'); await settle(page, 60);
    expect(await state(), item).toMatchObject({ open: 1, kind: 'menu' });
    await click(`dialog.menudlg ${item}`);
    await click('dialog.roomdlg [data-close-detail]');
    expect(await state(), item).toMatchObject({ open: 0, floor });
  }
  // nested: menu → decision → a page linked inside it → Back → decision → Back → menu
  await click('[data-menu]');
  await click('dialog.menudlg [data-house-details]');
  const nested = await impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg');
    const n = d.querySelector('.body [data-moisture], .body [data-moisture-side], .body [data-room-open], .body [data-classic-info], .body [data-weather-open]');
    return n ? n.outerHTML.slice(0, 80) : null; });
  expect(nested).toContain('data-classic-info');   // the decision page links one level deeper (learning quality)
  {
    const decision = (await state()).kind;
    await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg .body').querySelector('[data-moisture], [data-moisture-side], [data-room-open], [data-classic-info], [data-weather-open]').click());
    const second = await state();
    expect(second.back, nested).toBe(true);
    await click('dialog.roomdlg [data-nav-back]');
    expect((await state()).kind, nested).toBe(decision);
    await click('dialog.roomdlg [data-nav-back]');
    expect(await state()).toMatchObject({ kind: 'menu' });
  }
  // direct entry from a room on the plan: no history, Back is not offered, Close closes
  await click('[data-close-menu]');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('svg.plan [data-room="r_wohnen"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  expect(await state()).toMatchObject({ open: 1, kind: 'room', back: false });
});

// ---- 0.26.7.2: weather animation without visible repetition, wind along the real facade, bounded load ----
const modUrl = name => `performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/${name}'))`;
const loadMods = page => page.evaluate(async src => { const [V, G, M, A, F] = await Promise.all(src.map(s => import(eval(s)))); window.__V = V; window.__G = G; window.__M = M; window.__A = A; window.__F = F; },
  [modUrl('freshairiq-house-view.js'), modUrl('freshairiq-house-geometry.js'), modUrl('freshairiq-house-motion.js'), modUrl('freshairiq-house-atmos.js'), modUrl('freshairiq-house-flow.js')]);

test('0.26.7.2 wind along the facade: rectangular and L-shaped houses, frontal and oblique wind – around the corners, no kink, never into a wall, also while swinging', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const r = await page.evaluate(() => {
    const V = window.__V, G = window.__G, M = window.__M;
    const HOUSES = {
      rect: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }],
      L: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 4], [0, 4]] }, { id: 'b', polygon: [[0, 4], [4, 4], [4, 10], [0, 10]] }],
      card: [{ id: 'b', polygon: [[0, 4], [4, 4], [4, 8], [0, 8]] }, { id: 'f', polygon: [[0, 0], [8, 0], [8, 4], [0, 4]] }, { id: 'w', polygon: [[4, 4], [10, 4], [10, 7], [7, 7], [7, 10], [4, 10]] }],
    };
    const inside = (rooms, p) => rooms.some(x => G.pointInPolygon(p, x.polygon) === 'inside');
    const dist = (rooms, p) => Math.min(...rooms.flatMap(x => x.polygon.map((q, i) => { const s = G.projectOnSegment(p, q, x.polygon[(i + 1) % x.polygon.length]); return Math.hypot(p[0] - s.point[0], p[1] - s.point[1]); })));
    const out = [];
    for (const [name, rooms] of Object.entries(HOUSES)) for (const from of [0, 45, 90, 135, 200, 270, 315]) {
      const box = G.bbox(rooms.map(x => x.polygon)), m = 5, frame = { minX: box.minX - m, minY: box.minY - m, maxX: box.maxX + m, maxY: box.maxY + m };
      const t = G.bearingVector((from + 180) % 360, 0);
      const streams = V.facadeStreams({ rooms, fromDeg: from, northDeg: 0, G, frame, variety: M.streamVariety(8, 11 + from) });
      let minClear = Infinity, maxBend = 0, wrapped = 0, downwind = 0;
      for (const s of streams) {
        // the line itself, densely: outside every room
        for (let i = 0; i < s.points.length - 1; i++) for (let k = 0; k < 4; k++) {
          const a = s.points[i], b = s.points[i + 1], p = [a[0] + (b[0] - a[0]) * k / 4, a[1] + (b[1] - a[1]) * k / 4];
          minClear = Math.min(minClear, inside(rooms, p) ? -1 : dist(rooms, p));
        }
        // the bend: the radius of every three points stays a soft curve (no kink)
        for (let i = 1; i < s.points.length - 1; i++) {
          const a = s.points[i - 1], b = s.points[i], c = s.points[i + 1], u = [b[0] - a[0], b[1] - a[1]], v = [c[0] - b[0], c[1] - b[1]];
          const lu = Math.hypot(...u), lv = Math.hypot(...v); if (lu < 1e-6 || lv < 1e-6) continue;
          maxBend = Math.max(maxBend, Math.abs(Math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])) * 180 / Math.PI);
        }
        // around a corner: while the stream stays close to the house, the wall it follows turns by 80° and more
        const wall = p => { let best = null; for (const x of rooms) x.polygon.forEach((q, i) => { const s2 = G.projectOnSegment(p, q, x.polygon[(i + 1) % x.polygon.length]);
          const d = Math.hypot(p[0] - s2.point[0], p[1] - s2.point[1]); if (!best || d < best.d) best = { d, a: Math.atan2(p[1] - s2.point[1], p[0] - s2.point[0]) }; }); return best; };
        const near = s.points.map(wall).filter(w => w.d < 2.5);
        if (near.some(w => Math.abs(Math.atan2(Math.sin(w.a - near[0].a), Math.cos(w.a - near[0].a))) >= 80 * Math.PI / 180)) wrapped += 1;
        const e = s.points[s.points.length - 1], st = s.points[0];
        if ((e[0] - st[0]) * t[0] + (e[1] - st[1]) * t[1] > 0) downwind += 1;
        // the swinging ribbon (also with the 30 % breathing of the loop): never beyond the free distance at any sample
        const f = V.waveFrame(s.points, 0.2, s.clear);
        for (const phase of [0, 0.25, 0.5, 0.75]) {
          const d = V.wavePath(f, { amp: 2.5 * 1.3, wavelength: 4, shift: 0.7, form: 0.8, pad: 0.15 }, phase);
          for (const xy of d.split(/[ML ]+/).filter(Boolean)) { const [x, y] = xy.split(',').map(Number); const p = [x, -y]; minClear = Math.min(minClear, inside(rooms, p) ? -1 : dist(rooms, p) + 1e-6); }
        }
      }
      out.push({ name, from, n: streams.length, deflect: streams.filter(s => s.kind === 'deflect').length, minClear, maxBend, wrapped, downwind });
    }
    return out;
  });
  for (const c of r) {
    const tag = `${c.name} from ${c.from}°`;
    expect(c.n, tag).toBe(8);
    expect(c.deflect, tag).toBeGreaterThan(3);                 // most gusts meet the house …
    expect(c.minClear, tag).toBeGreaterThan(0.1);              // … and never touch or cross a wall, also while swinging
    expect(c.maxBend, tag).toBeLessThan(25);                    // soft curves only
    expect(c.wrapped, tag).toBeGreaterThanOrEqual(3);           // they wind around the corners
    expect(c.downwind, tag).toBe(c.n);                          // and leave with the wind
  }
  // every gust its own way: distance, hug and release differ, lanes and lengths of a house stay as before
  const v = await page.evaluate(() => window.__M.streamVariety(6, 4));
  expect(new Set(v.map(x => Math.round(x.gap * 1000))).size).toBe(6);
  expect(new Set(v.map(x => Math.round(x.form * 1000))).size).toBe(6);
});

// the same houses and wind directions as above: the drawn ribbons (every strand of every level, several phases, the loop's breathing
// and a strong gust) keep their stroke outside the walls, also at inner and outer corners; the lines between the drawn points count,
// not only the points
async function drawnRibbons(page, HOUSES, angles) {
  await mount(page);
  await loadMods(page);
  return page.evaluate(({ HOUSES, angles }) => {
    const V = window.__V, G = window.__G, M = window.__M, F = window.__F;
    const segDist = (p, a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy, u = l2 > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0; return Math.hypot(p[0] - a[0] - dx * u, p[1] - a[1] - dy * u); };
    const o = (u, v, w) => Math.sign((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]));
    // the line between two drawn points: its distance to a wall, 0 when it crosses it
    const segSeg = (p, q, a, b) => (o(p, q, a) * o(p, q, b) < 0 && o(a, b, p) * o(a, b, q) < 0 ? 0 : Math.min(segDist(p, a, b), segDist(q, a, b), segDist(a, p, q), segDist(b, p, q)));
    // strictly inside a room (ray casting; a point on a wall is caught by the distance check above)
    const inPoly = (p, poly) => { let odd = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > p[1]) !== (yj > p[1]) && p[0] < xi + (p[1] - yi) / (yj - yi) * (xj - xi)) odd = !odd; } return odd; };
    let worst = Infinity, checked = 0, eddies = 0, eddyWorst = Infinity;
    for (const level of ['minimal', 'normal', 'intense']) for (const u of [0.02, 0.035]) for (const [name, rooms] of Object.entries(HOUSES)) for (const from of angles) {
      const px = n => n * u, motion = M.PROFILES[level];
      const box = G.bbox(rooms.map(x => x.polygon)), m = 5, frame = { minX: box.minX - m, minY: box.minY - m, maxX: box.maxX + m, maxY: box.maxY + m };
      const variety = M.streamVariety(motion.streams, 11 + from).map(v => ({ ...v, amp: v.amp * Math.pow(1.45, 0.8) * (motion.amp || 1) }));
      const lanes = V.outerLanes({ rooms, fromDeg: from, northDeg: 0, G, frame, variety, minClear: V.ribbonClear(px, motion), gusts: V.gustVariety(M.streamVariety(motion.gusts, 7 + from), 7 + from),
        gustClear: px(7), join: px(24), need: px(4.5) }), streams = lanes.streams;
      const field = F.buildField({ rooms, G, wind: { available: true, from_deg: from, speed_ms: 18, gust_ms: 28 }, northDeg: 0 }), speed = F.relativeSpeed(field);
      const waves = [];
      V.ribbonsSvg(streams, { variety, motion, px, round3: x => x, waves, phase: () => 0, frameOf: s => V.waveFrame(V.streamLine(s), px(9), s.clear, motion.pathPoints, V.streamLine(s).map(speed), s.damp, s.near) });
      const walls = rooms.flatMap(x => x.polygon.map((q, i) => [q, x.polygon[(i + 1) % x.polygon.length]]));
      for (const w of waves) {
        const half = w.geo.pad - px(2);
        for (const breath of [1, 1.3 + 0.4 * field.gust.amp]) for (const ph of [0, 0.2, 0.4, 0.6, 0.8]) {
          const P = V.wavePath(w.frame, { ...w.geo, amp: w.geo.amp * breath }, ph).split(/[ML ]+/).filter(Boolean).map(xy => { const [x, y] = xy.split(',').map(Number); return [x, -y]; });
          // (a wall further away than the stroke's half width and 40 px cannot set the least gap)
          const reach = half + px(40);
          for (let i = 0; i < P.length - 1; i++) {
            const x0 = Math.min(P[i][0], P[i + 1][0]) - reach, x1 = Math.max(P[i][0], P[i + 1][0]) + reach, y0 = Math.min(P[i][1], P[i + 1][1]) - reach, y1 = Math.max(P[i][1], P[i + 1][1]) + reach;
            for (const [a, b] of walls) if (Math.max(a[0], b[0]) >= x0 && Math.min(a[0], b[0]) <= x1 && Math.max(a[1], b[1]) >= y0 && Math.min(a[1], b[1]) <= y1) worst = Math.min(worst, (segSeg(P[i], P[i + 1], a, b) - half) / u);
          }
          for (const p of P) if (rooms.some(x => inPoly(p, x.polygon))) worst = -1;
          checked += 1;
        }
      }
      // the storm gusts (their broad stroke) and the lee's curls (their stroke, all the way they drift) stay outside the house as well
      for (const g of lanes.gusts) for (let i = 0; i < g.points.length - 1; i++) for (const [a, b] of walls) worst = Math.min(worst, (segSeg(g.points[i], g.points[i + 1], a, b) - px(5.5)) / u);
      const E = new F.LeeCurls().plan({ curls: lanes.curls, count: motion.eddies });
      for (const e of E.items) { eddies += 1; for (let x = 0; x <= 1.0001; x += 0.1) {
        const dr = e.drift * Math.pow(x, 1.3), P = e.points.map(q => [q[0] + e.dir[0] * dr, q[1] + e.dir[1] * dr]);
        for (let i = 0; i < P.length - 1; i++) for (const [a, b] of walls) eddyWorst = Math.min(eddyWorst, (segSeg(P[i], P[i + 1], a, b) - px(1.3)) / u);
        if (P.some(p => rooms.some(q => inPoly(p, q.polygon)))) eddyWorst = -1; } }
    }
    return { worst, checked, eddies, eddyWorst };
  }, { HOUSES, angles });
}

test('0.26.7.2 drawn wind ribbons: every strand, every level and phase, with breathing and gust – the stroke never reaches a wall', async ({ page }) => {
  const r = await drawnRibbons(page, {
    rect: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }],
    L: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 4], [0, 4]] }, { id: 'b', polygon: [[0, 4], [4, 4], [4, 10], [0, 10]] }],
    card: [{ id: 'b', polygon: [[0, 4], [4, 4], [4, 8], [0, 8]] }, { id: 'f', polygon: [[0, 0], [8, 0], [8, 4], [0, 4]] }, { id: 'w', polygon: [[4, 4], [10, 4], [10, 7], [7, 7], [7, 10], [4, 10]] }],
  }, [0, 45, 135, 200, 270]);
  expect(r.checked).toBeGreaterThan(2000);
  expect(r.worst).toBeGreaterThan(0.5);          // screen pixels between the edge of the stroke and the wall
  expect(r.eddies).toBeGreaterThan(20);
  expect(r.eddyWorst).toBeGreaterThan(0.5);
});

// U-shaped houses: the notch towards the wind (north), a wide one and one opening sideways, wind from the north and nearby (350°):
// no stream runs into the notch and on through its end, no drawn ribbon cuts the outside wall there
test('0.26.7.2 drawn wind ribbons around a U-shaped house: wind from 0° and 350° and nearby – no stroke cuts the wall at the end of the notch', async ({ page }) => {
  const r = await drawnRibbons(page, {
    U: [{ id: 'u', polygon: [[0, 0], [10, 0], [10, 8], [7, 8], [7, 3], [3, 3], [3, 8], [0, 8]] }],
    Uwide: [{ id: 'u', polygon: [[0, 0], [10, 0], [10, 8], [8, 8], [8, 3], [2, 3], [2, 8], [0, 8]] }],
    Uwest: [{ id: 'u', polygon: [[0, 0], [0, 10], [-8, 10], [-8, 8], [-3, 8], [-3, 2], [-8, 2], [-8, 0]] }],
  }, [0, 10, 340, 350]);
  expect(r.checked).toBeGreaterThan(1500);
  expect(r.worst).toBeGreaterThan(0.5);
  expect(r.eddies).toBeGreaterThan(10);
  expect(r.eddyWorst).toBeGreaterThan(0.5);
});

// the same houses drawn as the card draws them: the visible line of every ribbon (each at its own phase, with the loop's breathing
// and a strong gust) never crosses another ribbon's line, and no gust crosses the line of a ribbon it does not run on (a joining
// gust: of its pair) – the broad, nearly clear air mass lies over its neighbours anyway
async function drawnCrossings(page, HOUSES, angles) {
  await mount(page);
  await loadMods(page);
  return page.evaluate(({ HOUSES, angles }) => {
    const V = window.__V, G = window.__G, M = window.__M, F = window.__F;
    const o = (u, v, w) => Math.sign((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]));
    // how often drawn lines of different owners cross: [{key, skip, P}] – segments sorted into a grid, only those sharing a cell
    // are compared, each pair once (in the cell where their boxes start to overlap); ``skip``: owners a line may cross, e.g. a
    // gust's own ribbons
    const crossings = (lines, cell) => {
      const grid = new Map(), cellOf = x => Math.floor(x / cell);
      let n = 0;
      lines.forEach((l, i) => { for (let a = 0; a < l.P.length - 1; a++) {
        const P = l.P[a], Q = l.P[a + 1];
        for (let gx = cellOf(Math.min(P[0], Q[0])); gx <= cellOf(Math.max(P[0], Q[0])); gx++) for (let gy = cellOf(Math.min(P[1], Q[1])); gy <= cellOf(Math.max(P[1], Q[1])); gy++) {
          const k = gx * 100003 + gy;
          let list = grid.get(k);
          if (!list) grid.set(k, (list = []));
          list.push(i, a);
        }
      } });
      for (const [k, segs] of grid) for (let u = 0; u < segs.length; u += 2) for (let v = u + 2; v < segs.length; v += 2) {
        const A = lines[segs[u]], B = lines[segs[v]];
        if (A.key === B.key || (A.skip && A.skip.has(B.key)) || (B.skip && B.skip.has(A.key))) continue;
        const P = A.P[segs[u + 1]], Q = A.P[segs[u + 1] + 1], C = B.P[segs[v + 1]], D = B.P[segs[v + 1] + 1];
        if (cellOf(Math.max(Math.min(P[0], Q[0]), Math.min(C[0], D[0]))) * 100003 + cellOf(Math.max(Math.min(P[1], Q[1]), Math.min(C[1], D[1]))) !== k) continue;
        if (o(P, Q, C) * o(P, Q, D) < 0 && o(C, D, P) * o(C, D, Q) < 0) n++;
      }
      return n;
    };
    let crossed = 0, pairs = 0;
    for (const level of ['minimal', 'normal', 'intense']) for (const u of [0.02, 0.035]) for (const [name, rooms] of Object.entries(HOUSES)) for (const from of angles) {
      const px = n => n * u, motion = M.PROFILES[level];
      const box = G.bbox(rooms.map(x => x.polygon)), m = 5, frame = { minX: box.minX - m, minY: box.minY - m, maxX: box.maxX + m, maxY: box.maxY + m };
      const variety = M.streamVariety(motion.streams, 11 + from).map(v => ({ ...v, amp: v.amp * Math.pow(1.45, 0.8) * (motion.amp || 1) }));
      const lanes = V.outerLanes({ rooms, fromDeg: from, northDeg: 0, G, frame, variety, minClear: V.ribbonClear(px, motion), gusts: V.gustVariety(M.streamVariety(motion.gusts, 7 + from), 7 + from),
        gustClear: px(7), join: px(24), need: px(4.5) });
      const field = F.buildField({ rooms, G, wind: { available: true, from_deg: from, speed_ms: 18, gust_ms: 28 }, northDeg: 0 }), speed = F.relativeSpeed(field);
      const waves = [], owner = new Map();
      V.ribbonsSvg(lanes.streams, { variety, motion, px, round3: x => x, waves, phase: () => 0, frameOf: s => { const f = V.waveFrame(V.streamLine(s), px(9), s.clear, motion.pathPoints, V.streamLine(s).map(speed), s.damp, s.near); owner.set(f, s); return f; } });
      const lines = waves.filter(w => w.geo.line != null), all = lanes.gusts.map((g, i) => `g${i}`);
      const gusts = lanes.gusts.map((g, i) => ({ key: `g${i}`, skip: new Set([...all, ...[g.variety, g.merge ? lanes.gusts[g.merge.into].variety : -1].map(v => `r${v}`)]), P: g.points }));
      for (const set of [0, 1, 2]) for (const breath of [1, 1.3 + 0.4 * field.gust.amp]) {
        const P = lines.map((w, k) => ({ key: `r${owner.get(w.frame).variety}`, P: V.wavePath(w.frame, { ...w.geo, amp: w.geo.amp * breath }, (set * 0.29 + k * 0.137 + (w.geo.offset || 0)) % 1)
          .split(/[ML ]+/).filter(Boolean).map(xy => { const [x, y] = xy.split(',').map(Number); return [x, -y]; }) }));
        pairs += P.length * (P.length - 1) / 2;
        crossed += crossings([...P, ...gusts], px(40));
      }
    }
    return { crossed, pairs };
  }, { HOUSES, angles });
}

test('0.26.7.2 drawn ribbons and gusts together (rectangle, L, the card house): no line crosses another, at every level, phase and swing', async ({ page }) => {
  const r = await drawnCrossings(page, {
    rect: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }],
    L: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 4], [0, 4]] }, { id: 'b', polygon: [[0, 4], [4, 4], [4, 10], [0, 10]] }],
    card: [{ id: 'b', polygon: [[0, 4], [4, 4], [4, 8], [0, 8]] }, { id: 'f', polygon: [[0, 0], [8, 0], [8, 4], [0, 4]] }, { id: 'w', polygon: [[4, 4], [10, 4], [10, 7], [7, 7], [7, 10], [4, 10]] }],
  }, [0, 45, 135, 200, 270]);
  expect(r.pairs).toBeGreaterThan(5000);
  expect(r.crossed).toBe(0);
});

test('0.26.7.2 drawn ribbons and gusts together around U-shaped houses: no line crosses another, at every level, phase and swing', async ({ page }) => {
  const r = await drawnCrossings(page, {
    U: [{ id: 'u', polygon: [[0, 0], [10, 0], [10, 8], [7, 8], [7, 3], [3, 3], [3, 8], [0, 8]] }],
    Uwide: [{ id: 'u', polygon: [[0, 0], [10, 0], [10, 8], [8, 8], [8, 3], [2, 3], [2, 8], [0, 8]] }],
    Uwest: [{ id: 'u', polygon: [[0, 0], [0, 10], [-8, 10], [-8, 8], [-3, 8], [-3, 2], [-8, 2], [-8, 0]] }],
  }, [0, 10, 340, 350, 90, 270]);
  expect(r.pairs).toBeGreaterThan(5000);
  expect(r.crossed).toBe(0);
});

// 0.26.7.2 (outer wind): one ordered set of outer ways – ribbons and the gusts on them never cross, every ribbon that meets the house
// lets go of it and runs on calmly with the wind, closing in towards the wake behind the house (never away from it, never back
// against the wind); two gusts of one side join behind the house
test('0.26.7.2 outer ways: ribbons and gusts without crossing, every ribbon on to its calm run-out into the wake, two gusts joining behind the house', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const r = await page.evaluate(() => {
    const V = window.__V, G = window.__G, M = window.__M;
    const HOUSES = {
      rect: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }],
      L: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 4], [0, 4]] }, { id: 'b', polygon: [[0, 4], [4, 4], [4, 10], [0, 10]] }],
      U: [{ id: 'u', polygon: [[0, 0], [10, 0], [10, 8], [7, 8], [7, 3], [3, 3], [3, 8], [0, 8]] }],
    };
    const o = (u, v, w) => Math.sign((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]));
    const cross = (A, B) => { let n = 0; for (let a = 0; a < A.length - 1; a++) for (let b = 0; b < B.length - 1; b++) if (o(A[a], A[a + 1], B[b], B[b + 1]) * o(A[a], A[a + 1], B[b + 1], B[b]) < 0 && o(B[b], B[b + 1], A[a], A[a + 1]) * o(B[b], B[b + 1], A[a + 1], A[a]) < 0) n++; return n; };
    const segDist = (p, a, b) => { const s = G.projectOnSegment(p, a, b); return Math.hypot(p[0] - s.point[0], p[1] - s.point[1]); };
    const lineDist = (p, P) => { let m = Infinity; for (let i = 0; i < P.length - 1; i++) m = Math.min(m, segDist(p, P[i], P[i + 1])); return m; };
    const out = [];
    for (const [name, rooms] of Object.entries(HOUSES)) for (const from of [0, 30, 45, 90, 200, 315]) for (const level of ['normal', 'intense']) {
      const motion = M.PROFILES[level], px = n => n * 0.025;
      const box = G.bbox(rooms.map(x => x.polygon)), m = 5, frame = { minX: box.minX - m, minY: box.minY - m, maxX: box.maxX + m, maxY: box.maxY + m };
      const t = G.bearingVector((from + 180) % 360, 0), lon = q => q[0] * t[0] + q[1] * t[1];
      const rear = Math.max(...rooms.flatMap(x => x.polygon.map(lon))), across = q => q[0] * -t[1] + q[1] * t[0];
      const sil = rooms.flatMap(x => x.polygon.map(across)), mid = (Math.min(...sil) + Math.max(...sil)) / 2;
      const L = V.outerLanes({ rooms, fromDeg: from, northDeg: 0, G, frame, variety: M.streamVariety(motion.streams, 11 + from), minClear: V.ribbonClear(px, motion),
        gusts: V.gustVariety(M.streamVariety(motion.gusts, 7 + from), 7 + from), gustClear: px(7), join: px(24), need: px(4.5) });
      // every ribbon that meets the house lets go of it and runs on with the wind for a good stretch, behind the house towards the wake
      let worstAngle = 0, short = 0, met = 0, away = 0;
      for (const s of L.streams.filter(x => x.kind === 'deflect')) {
        met += 1;
        if (s.release < 0) { short += 1; continue; }
        let arc = 0, run = 0;
        for (let i = s.release + 1; i < s.points.length; i++) {
          const a = s.points[i - 1], b = s.points[i], l = Math.hypot(b[0] - a[0], b[1] - a[1]); arc += l;
          if (arc < 3 || l < 1e-6) continue;
          run += l; worstAngle = Math.max(worstAngle, Math.acos(Math.min(1, ((b[0] - a[0]) * t[0] + (b[1] - a[1]) * t[1]) / l)) * 180 / Math.PI);
          if (lon(a) > rear && Math.abs(across(b) - mid) > Math.abs(across(a) - mid) + 5e-3) away += 1;   // (5 mm of a 10 m house)
        }
        if (run < 2) short += 1;
      }
      // no crossing: ribbons among themselves, gusts among themselves, gusts with every ribbon
      let crossings = 0;
      for (let i = 0; i < L.streams.length; i++) for (let j = i + 1; j < L.streams.length; j++) crossings += cross(L.streams[i].points, L.streams[j].points);
      for (let i = 0; i < L.gusts.length; i++) for (let j = i + 1; j < L.gusts.length; j++) crossings += cross(L.gusts[i].points, L.gusts[j].points);
      for (const g of L.gusts) for (const s of L.streams) crossings += cross(g.points, s.points);
      const width = px(24) / 2.2;
      const joins = L.gusts.filter(g => g.merge).map(g => {
        const lead = L.gusts[g.merge.into], P = g.points, d = P.map(q => lineDist(q, lead.points));
        const before = P.filter(q => lon(q) < g.merge.lon - g.merge.blend).map(q => lineDist(q, lead.points)), last = before.slice(-6);
        let rising = 0; for (let i = 1; i < P.length; i++) if (lon(P[i]) >= g.merge.lon - g.merge.blend && d[i] > d[i - 1] + 1e-3) rising++;
        const fl = lead.fade.stops, ff = g.fade.stops, mOff = g.merge.blend / (g.merge.blend + g.merge.overlap);
        const released = Math.max(...[g, lead].map(w => lon(w.points[Math.max(0, w.points.findIndex(q => lon(q) >= g.merge.lon - g.merge.blend) - 1)])));
        return { end: d[d.length - 1], apart: Math.min(...last) / Math.min(g.width || Infinity, px(24) / 2.2), rising, behind: g.merge.lon > rear, inRun: g.merge.lon - g.merge.blend >= released - 1e-6,
          full: ff[0][1] === 1 && fl[0][1] === 1, gone: ff[ff.length - 1][1], back: fl[fl.length - 1][1],
          sum: Math.max(...fl.map(([off, a], i) => (off >= mOff - 1e-6 ? Math.abs(a + ff[i][1] - 1) : 0))), half: Math.min(...fl.map(s => s[1])) };
      });
      out.push({ tag: `${name} ${from}° ${level}`, worstAngle, short, met, away, crossings, joins, width, gusts: L.gusts.length });
    }
    return out;
  });
  let joins = 0;
  for (const c of r) {
    expect(c.crossings, c.tag).toBe(0);                          // ribbons and gusts, also in combination
    expect(c.short, c.tag).toBe(0);                              // every ribbon reaches its run-out
    expect(c.worstAngle, c.tag).toBeLessThan(30);                // and runs on calmly with the wind …
    expect(c.away, c.tag).toBe(0);                               // … behind the house towards the wake, never away from it
    expect(c.gusts, c.tag).toBe(c.tag.endsWith('intense') ? 3 : 2);
    for (const j of c.joins) {
      joins += 1;
      expect(j.end, c.tag).toBeLessThan(1e-6);                   // one way after the meeting point
      expect(j.inRun, c.tag).toBe(true);                         // in the run-out, behind the house where the drawing has room
      expect(j.apart, c.tag).toBeGreaterThan(1);                 // two gusts before (more than a stroke apart) …
      expect(j.rising, c.tag).toBe(0);                           // … coming nearer steadily …
      expect(j.full, c.tag).toBe(true);                          // … fully visible until they touch
      expect(j.half, c.tag).toBeGreaterThanOrEqual(0.5);         // the leading one never fades below half
      expect(j.sum, c.tag).toBeLessThan(0.01);                   // on the shared stretch the two add up to one gust
      expect([j.gone, j.back], c.tag).toEqual([0, 1]);           // the joined gust runs on at full strength
    }
  }
  expect(joins).toBeGreaterThan(r.length * 0.75);
  expect(r.flatMap(c => c.joins).filter(j => j.behind).length).toBeGreaterThan(joins * 0.5);
});

// the crossing once seen on the narrow card (wind from 270°, the card's house): ribbons, their drawn lines while they swing and the
// gusts on them stay apart at every level, in the narrow and in a wide drawing – and the ribbons pass the house visibly on both sides
test('0.26.7.2 wind from 270° on the card house, narrow and wide: no crossing of ribbons, drawn lines or gusts, the ribbons pass the house', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const r = await page.evaluate(() => {
    const V = window.__V, G = window.__G, M = window.__M;
    const rooms = [{ id: 'b', polygon: [[0, 4], [4, 4], [4, 8], [0, 8]] }, { id: 'f', polygon: [[0, 0], [8, 0], [8, 4], [0, 4]] }, { id: 'w', polygon: [[4, 4], [10, 4], [10, 7], [7, 7], [7, 10], [4, 10]] }];
    const o = (u, v, w) => Math.sign((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]));
    const cross = (A, B) => { let n = 0; for (let a = 0; a < A.length - 1; a++) for (let b = 0; b < B.length - 1; b++) if (o(A[a], A[a + 1], B[b], B[b + 1]) * o(A[a], A[a + 1], B[b + 1], B[b]) < 0 && o(B[b], B[b + 1], A[a], A[a + 1]) * o(B[b], B[b + 1], A[a + 1], A[a]) < 0) n++; return n; };
    const toPts = d => d.split(/[ML ]+/).filter(Boolean).map(xy => { const [x, y] = xy.split(',').map(Number); return [x, -y]; });
    const out = [];
    for (const [name, frame, u] of [['narrow', { minX: -1.6, minY: -3.258, maxX: 11.6, maxY: 13.059 }, 0.035], ['wide', { minX: -5.083, minY: -2.775, maxX: 15.083, maxY: 11.6 }, 0.022]]) for (const level of ['minimal', 'normal', 'intense']) {
      const motion = M.PROFILES[level], px = n => n * u, strength = 1.45, count = Math.max(2, Math.min(9, Math.round(motion.streams * strength)));
      const variety = M.streamVariety(count, 83).map(v => ({ ...v, amp: v.amp * Math.pow(strength, 0.8) * (motion.amp || 1) }));
      const L = V.outerLanes({ rooms, fromDeg: 270, northDeg: 0, G, frame, variety, minClear: V.ribbonClear(px, motion), gusts: V.gustVariety(M.streamVariety(motion.gusts, 101), 101), gustClear: px(7), join: px(24), need: px(4.5) });
      let centre = 0, gusts = 0, drawn = 0;
      for (let i = 0; i < L.streams.length; i++) for (let j = i + 1; j < L.streams.length; j++) centre += cross(L.streams[i].points, L.streams[j].points);
      for (const g of L.gusts) for (const s of L.streams) gusts += cross(g.points, s.points);
      const waves = [], owner = new Map();
      V.ribbonsSvg(L.streams, { variety, motion, px, round3: x => x, waves, phase: () => 0, frameOf: s => { const f = V.waveFrame(V.streamLine(s), px(9), s.clear, motion.pathPoints, null, s.damp, s.near); owner.set(f, s); return f; } });
      const lines = waves.filter(w => w.geo.line != null);
      for (const set of [0, 1, 2, 3]) for (const breath of [1, 1.6]) {
        const P = lines.map((w, k) => ({ s: owner.get(w.frame), P: toPts(V.wavePath(w.frame, { ...w.geo, amp: w.geo.amp * breath }, (set * 0.23 + k * 0.137 + (w.geo.offset || 0)) % 1)) }));
        for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) if (P[i].s !== P[j].s) drawn += cross(P[i].P, P[j].P);
      }
      // past the house and still in the drawing: ribbons that met it run on beside and behind it, on both sides
      const seen = L.streams.filter(s => s.kind === 'deflect' && s.points.some(q => q[0] > 10 && q[0] < frame.maxX && q[1] > frame.minY && q[1] < frame.maxY));
      out.push({ tag: `${name} ${level}`, n: L.streams.length, centre, gusts, drawn, past: new Set(seen.map(s => s.side)).size });
    }
    return out;
  });
  for (const c of r) {
    expect(c.n, c.tag).toBeGreaterThan(3);
    expect([c.centre, c.gusts, c.drawn], c.tag).toEqual([0, 0, 0]);
    expect(c.past, c.tag).toBe(2);
  }
});

// the join as it plays: two stretches of air in step towards one point, both fully there until they touch; on the shared stretch
// the two pictures cross-fade into one (the sum stays that of one gust), the joined gust runs on without a gap
test('0.26.7.2 two gusts join in the browser: two stretches until they touch, one gust after, no gap, second track or jump of brightness', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const r = await page.evaluate(async () => {
    const V = window.__V, G = window.__G, M = window.__M;
    const W = await import(performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/freshairiq-house-weather.js')));
    const rooms = [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }], ppu = 40, frame = { minX: -5, minY: -5, maxX: 15, maxY: 11 };
    const L = V.outerLanes({ rooms, fromDeg: 0, northDeg: 0, G, frame, variety: M.streamVariety(5, 11), gusts: V.gustVariety(M.streamVariety(3, 7), 7), gustClear: 0.2, join: 0.6 });
    const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    document.body.appendChild(svg);
    L.gusts.forEach((g, i) => { const p = document.createElementNS(ns, 'path'); p.setAttribute('d', g.points.map((q, k) => `${k ? 'L' : 'M'} ${q[0]},${-q[1]}`).join(' '));
      p.setAttribute('data-gust', i); p.setAttribute('pathLength', '100'); p.setAttribute('stroke-dasharray', '18 100'); svg.appendChild(p); });
    const run = new W.GustRunner();
    run.plan(L.gusts, ppu, () => 1);
    run.bind(svg.querySelectorAll('path[data-gust]'), false);
    const fol = run.gusts.find(g => g.lead), lead = fol.lead, gf = L.gusts[fol.i], gl = L.gusts[lead.i];
    lead.s.phase = 0; lead.s.rest = 0.5; lead.s.pace = 1;
    const pointAt = (P, x) => { let a = 0; for (let k = 1; k < P.length; k++) { const l = Math.hypot(P[k][0] - P[k - 1][0], P[k][1] - P[k - 1][1]); if (a + l >= x) { const u = (x - a) / l; return [P[k - 1][0] + (P[k][0] - P[k - 1][0]) * u, P[k - 1][1] + (P[k][1] - P[k - 1][1]) * u]; } a += l; } return null; };
    // the stroke's opacity at a point: its fade along the wind (the gradient the card draws)
    const alpha = (g, p) => { if (!g.fade) return 1; const { from, to, stops } = g.fade, ax = [to[0] - from[0], to[1] - from[1]], l2 = ax[0] * ax[0] + ax[1] * ax[1];
      const off = Math.max(0, Math.min(1, ((p[0] - from[0]) * ax[0] + (p[1] - from[1]) * ax[1]) / l2)); let k = 1; while (k < stops.length - 1 && stops[k][0] < off) k++;
      const [o0, a0] = stops[k - 1], [o1, a1] = stops[k]; return a0 + (a1 - a0) * (o1 > o0 ? Math.max(0, Math.min(1, (off - o0) / (o1 - o0))) : 0); };
    // the middle of each stretch on its own way (from the dash offset the runner wrote)
    const mid = (g, P) => { const units = g.dash - Number(g.el.getAttribute('stroke-dashoffset')) - g.dash / 2; return units > 0 && units < 100 ? pointAt(P, units / 100 * g.length / ppu) : null; };
    const frames = [];
    for (let k = 0; k < 600 && lead.s.phase < 1; k++) {
      run.step(1 / 30, 25, 0.8);
      const a = mid(lead, gl.points), b = mid(fol, gf.points);
      frames.push({ at: (lead.head - lead.dash * lead.length / 200) / ppu, a: a && alpha(gl, a), b: b && alpha(gf, b), gap: a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : null, dom: fol.el.getAttribute('opacity') });
    }
    const t = [0, -1], lon = q => q[0] * t[0] + q[1] * t[1];
    const toLon = x => { const P = gl.points; let a = 0; for (let k = 1; k < P.length; k++) { a += Math.hypot(P[k][0] - P[k - 1][0], P[k][1] - P[k - 1][1]); if (lon(P[k]) >= x) return a; } return a; };
    return { frames, contact: toLon(gf.merge.contact), meet: toLon(gf.merge.lon), end: toLon(gf.merge.lon + gf.merge.overlap), width: 0.6 / 2.2, style: true };
  });
  const { frames, contact, meet, end, width } = r;
  expect(frames.length).toBeGreaterThan(60);
  const apart = frames.filter(f => f.a != null && f.b != null && f.at < contact - width);
  expect(apart.length).toBeGreaterThan(5);
  for (const f of apart) { expect(f.a).toBeCloseTo(1, 2); expect(f.b).toBeCloseTo(1, 2); expect(f.gap).toBeGreaterThan(width * 0.99); }   // two gusts
  const shared = frames.filter(f => f.a != null && f.b != null && f.at > meet && f.at < end);
  expect(shared.length).toBeGreaterThan(3);
  for (const f of shared) { expect(f.gap).toBeLessThan(1e-3); expect(Math.abs(f.a + f.b - 1)).toBeLessThan(0.02); }       // one line, the sum of one gust
  const after = frames.filter(f => f.at > end + 0.5 && f.a != null);
  expect(after.length).toBeGreaterThan(5);
  for (const f of after) { expect(f.a).toBe(1); expect(f.b == null || f.b === 0).toBe(true); }                             // one gust runs on
  // no jump: each stretch's opacity changes steadily, and the leading one is there in every frame from its start to its end
  for (let i = 1; i < frames.length; i++) {
    if (frames[i].a != null && frames[i - 1].a != null) expect(Math.abs(frames[i].a - frames[i - 1].a)).toBeLessThan(0.12);
    if (frames[i].b != null && frames[i - 1].b != null) expect(Math.abs(frames[i].b - frames[i - 1].b)).toBeLessThan(0.12);
  }
  const seen = frames.map(f => f.a != null), first = seen.indexOf(true), last = seen.lastIndexOf(true);
  expect(seen.slice(first, last + 1).every(Boolean)).toBe(true);
  expect(frames.every(f => f.dom == null)).toBe(true);                                                                     // no fade in time on top
});

// on a narrow card: the storm's gusts run on the ribbons, two join behind the house – the card draws their fade along the wind and
// moves them in step; a sequence of pictures shows two gusts before they touch, the join and one gust running on
test('0.26.7.2 narrow card: two gusts before they touch, their join and one gust running on – a rendered sequence', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 420, height: 860 });
  await mount(page);
  let found = null;
  for (const bearing of ['W', 'NW', 'N', 'SW', 'S', 'E']) {
    await setup(page, { weather_effects: 'full', animation_level: 'intense' }, STATES('pouring', { wind_speed: 80, wind_gust_speed: 110, wind_bearing: bearing }));
    await settle(page, 300);
    found = await impl(page).evaluate(el => {
      const lanes = el._facades.kinds.outer.lanes, i = lanes.gusts.findIndex(g => g.merge);
      if (i < 0) return null;
      const elF = el.shadowRoot.querySelector(`path[data-gust="${i}"]`), elL = el.shadowRoot.querySelector(`path[data-gust="${lanes.gusts[i].merge.into}"]`);
      const grad = id => { const m = /url\(#([^)]+)\)/.exec(id || ''); return m ? el.shadowRoot.getElementById(m[1]) : null; };
      const gF = grad(elF.getAttribute('style')), gL = grad(elL.getAttribute('style'));
      return { i, stopsF: gF ? gF.querySelectorAll('stop').length : 0, stopsL: gL ? gL.querySelectorAll('stop').length : 0, inStep: el._gustRun.gusts.find(g => g.i === i).lead === el._gustRun.gusts.find(g => g.i === lanes.gusts[i].merge.into) };
    });
    if (found) break;
  }
  expect(found).not.toBeNull();
  expect(found.stopsF).toBeGreaterThan(5); expect(found.stopsL).toBeGreaterThan(5); expect(found.inStep).toBe(true);
  // the sequence: the gusts moved by the card's own runner from the start of their way past the meeting point (the loop held still)
  const shots = [];
  for (const share of [0.3, 0.5, 0.62, 0.7, 0.78, 0.9]) {
    const state = await impl(page).evaluate((el, [i, share]) => {
      el._windStop();
      const run = el._gustRun, g = run.gusts.find(x => x.i === i), lead = g.lead, lanes = el._facades.kinds.outer.lanes, merge = lanes.gusts[i].merge;
      lead.s.phase = 0; lead.s.rest = 0.5;
      const ppu = lead.length / (lanes.gusts[merge.into].points.reduce((s, q, k, P) => s + (k ? Math.hypot(q[0] - P[k - 1][0], q[1] - P[k - 1][1]) : 0), 0));
      const target = merge.at * ppu * share / 0.7;   // 0.7 of the way: the middle of the stretch at the meeting point
      lead.way = null; lead.s.phase = Math.min(1, (target + lead.dash * lead.length / 200) / ((lead.dash + 100) * lead.length / 100));
      for (const x of run.gusts) run.draw(x, false);
      return { lead: lead.head / ppu, meet: merge.at };
    }, [found.i, share]);
    shots.push(state);
    await impl(page).locator('svg.plan').screenshot({ path: testInfo.outputPath(`join-${shots.length}.png`) });
  }
  expect(shots[0].lead).toBeLessThan(shots[shots.length - 1].lead);
  expect(shots.some(s => s.lead < s.meet) && shots.some(s => s.lead > s.meet)).toBe(true);
});

// the lee's curl as one movement: it starts on the passing edge ribbon behind the house, is drawn from there onwards, drifts with the
// wind and fades – no jump between frames; at most one at "normal", two at "intense", none at "minimal" or still
test('0.26.7.2 a curl peels off the edge ribbon behind the house, drifts with the wind and fades – one movement', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await setup(page, { weather_effects: 'full', animation_level: 'intense' }, STATES('pouring', { wind_speed: 80, wind_gust_speed: 110, wind_bearing: 'W' }));
  await settle(page, 600);
  const r = await impl(page).evaluate(el => {
    const lanes = el._facades.kinds.outer.lanes, E = el._eddies, field = el._flowField, out = [];
    const e = E.items[0], el0 = el.shadowRoot.querySelector('path[data-eddy="0"]');
    const ribbon = lanes.streams.find(s => s.points[e.from] === e.points[0]);
    // a cycle in which it rolls up
    let t0 = null;
    for (let t = 0.05; t < 600 && t0 == null; t += 0.05) if (E.at(field, e, t).opacity > 0 && E.at(field, e, t - 0.05).opacity === 0) t0 = t;
    let prev = null;
    for (let k = 0; k < 400; k++) {
      const t = t0 - 0.05 + k * 0.05, s = E.at(field, e, t);
      E.step(field, t);
      const tr = /translate\(([-\d.]+) ([-\d.]+)\)/.exec(el0.getAttribute('transform')), dx = Number(tr[1]), dy = -Number(tr[2]);
      out.push({ t, op: Number(el0.getAttribute('opacity')), drawn: parseFloat(el0.getAttribute('stroke-dasharray')), along: dx * e.dir[0] + dy * e.dir[1], x: s.x });
      if (prev && prev.opacity > 0 && s.opacity === 0) break;
      prev = s;
    }
    const start = e.points[0], P = ribbon ? ribbon.points : [];
    let onRibbon = Infinity; for (let i = 0; i < P.length - 1; i++) { const a = P[i], b = P[i + 1], dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy, u = Math.max(0, Math.min(1, ((start[0] - a[0]) * dx + (start[1] - a[1]) * dy) / l2)); onRibbon = Math.min(onRibbon, Math.hypot(start[0] - a[0] - dx * u, start[1] - a[1] - dy * u)); }
    // behind the house: further along the wind than any wall
    const walls = el._facades.field.field.segs.flatMap(s => [[s.ax, s.ay], [s.ax + s.tx * s.len, s.ay + s.ty * s.len]]);
    const behind = start[0] * e.dir[0] + start[1] * e.dir[1] > Math.max(...walls.map(q => q[0] * e.dir[0] + q[1] * e.dir[1]));
    return { out, onRibbon, behind, count: E.items.length, edge: !!ribbon && ribbon === lanes.streams.filter(s => s.side === ribbon.side && s.release >= 0).sort((a, b) => a.y - b.y)[0] };
  });
  expect(r.count).toBe(2);
  expect(r.onRibbon).toBeLessThan(1e-6);                                    // it starts on the ribbon …
  expect(r.edge).toBe(true);                                                // … the innermost one of its side, the edge of the wake …
  expect(r.behind).toBe(true);                                              // … behind the house
  const live = r.out.filter(f => f.op > 0);
  expect(live.length).toBeGreaterThan(40);
  expect(live[0].drawn).toBeLessThan(15);                                   // peeling off: drawn from the ribbon onwards
  expect(Math.max(...live.map(f => f.drawn))).toBeGreaterThan(95);
  for (let i = 1; i < r.out.length; i++) {
    if (r.out[i].op > 0) expect(r.out[i].along).toBeGreaterThanOrEqual(r.out[i - 1].along - 1e-9);   // drifting with the wind, never back
    expect(Math.abs(r.out[i].op - r.out[i - 1].op)).toBeLessThan(0.05);                              // fading in and out steadily
  }
  expect(r.out[r.out.length - 1].op).toBe(0);
  expect(Math.max(...r.out.map(f => f.along))).toBeGreaterThan(0.5);
});

// the approach before and after (same houses, same wind): 0.26.7.2 before this change traced these values (first turn of the
// gusts that meet the house, least distance in front of a windward wall; mean over the streams, house of 10 m)
test('0.26.7.2 the wind turns nearer the windward wall than before, and the air slows in front and runs faster past the sides', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const BEFORE = { 'rect|270': [3.095, 1.521], 'rect|225': [2.42, 1.65], 'rect|0': [3.082, 1.859], 'rect|45': [2.4, 1.687],
    'L|270': [3.697, 1.805], 'L|225': [2.971, 1.996], 'L|0': [3.834, 2.016], 'L|45': [3.603, 2.142] };
  const r = await page.evaluate(() => {
    const V = window.__V, G = window.__G, M = window.__M, F = window.__F;
    const HOUSES = { rect: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }],
      L: [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 4], [0, 4]] }, { id: 'b', polygon: [[0, 4], [4, 4], [4, 10], [0, 10]] }] };
    const out = {};
    for (const [name, rooms] of Object.entries(HOUSES)) for (const from of [270, 225, 0, 45]) {
      const box = G.bbox(rooms.map(x => x.polygon)), m = 5, frame = { minX: box.minX - m, minY: box.minY - m, maxX: box.maxX + m, maxY: box.maxY + m };
      const t = G.bearingVector((from + 180) % 360, 0);
      const streams = V.facadeStreams({ rooms, fromDeg: from, northDeg: 0, G, frame, variety: M.streamVariety(8, 11 + from) });
      const walls = rooms.flatMap(x => x.polygon.map((q, i) => [q, x.polygon[(i + 1) % x.polygon.length]]));
      const near = p => { let best = null; for (const [a, b] of walls) { const s = G.projectOnSegment(p, a, b), d = Math.hypot(p[0] - s.point[0], p[1] - s.point[1]); if (!best || d < best.d) best = { d, a, b }; } return best; };
      const turn = [], windward = [];
      for (const s of streams.filter(x => x.kind === 'deflect')) {
        const P = s.points;
        for (let i = 1; i < P.length; i++) { const v = [P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]], l = Math.hypot(...v); if (l && (v[0] * t[0] + v[1] * t[1]) / l < Math.cos(Math.PI / 18)) { turn.push(near(P[i]).d); break; } }
        let mn = Infinity;
        for (const p of P) { const w = near(p), e = [w.b[0] - w.a[0], w.b[1] - w.a[1]], len = Math.hypot(...e), on = [e[1] / len, -e[0] / len];
          const sg = Math.sign((p[0] - w.a[0]) * on[0] + (p[1] - w.a[1]) * on[1]) || 1; if ((on[0] * t[0] + on[1] * t[1]) * sg < -0.5) mn = Math.min(mn, w.d); }
        if (mn < Infinity) windward.push(mn);
      }
      const avg = a => a.reduce((x, y) => x + y, 0) / a.length;
      out[`${name}|${from}`] = [avg(turn), avg(windward)];
    }
    // the speed of the air along a stream from the 2D flow model: in front of the windward wall below, past the sides above the wind
    const rooms = HOUSES.rect, field = F.buildField({ rooms, G, wind: { available: true, from_deg: 270, speed_ms: 8 }, northDeg: 0 }), speed = F.relativeSpeed(field);
    return { out, front: speed([-0.3, 3]), side: speed([5, 6.4]), free: speed([-12, 3]), gust: F.gustBoost(field, 0) >= 0 && F.gustBoost(null, 5) === 0 };
  });
  for (const [key, [turn, windward]] of Object.entries(r.out)) {
    expect(turn, `${key} first turn`).toBeLessThan(BEFORE[key][0] * 0.99);
    expect(windward, `${key} windward distance`).toBeLessThan(BEFORE[key][1] * 0.92);
    expect(windward, `${key} windward distance`).toBeGreaterThan(0.3);        // closer – not onto the wall
  }
  expect(r.front).toBeLessThan(0.8);
  expect(r.side).toBeGreaterThan(1.05);
  expect(r.free).toBeGreaterThan(0.9); expect(r.free).toBeLessThan(1.2);
  expect(r.gust).toBe(true);
});

test('0.26.7.2 the wind follows the animation level: eddies none at "minimal", one at "normal", two at "intense", none still; the ribbons at every level', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  const seen = {};
  for (const level of ['off', 'minimal', 'normal', 'intense']) {
    await setup(page, { weather_effects: 'full', animation_level: level }, STATES('pouring', { wind_speed: 80, wind_gust_speed: 110, wind_bearing: 'W' }));
    await settle(page, 600);
    seen[level] = await impl(page).evaluate(el => {
      const root = el.shadowRoot, eddies = [...root.querySelectorAll('path[data-eddy]')];
      const ribbons = [...root.querySelectorAll('path.wave.mid.k-deflect, path.wave.mid.k-pass')].map(p => Number(p.getAttribute('stroke-width')));
      return { eddies: eddies.length, loop: !!el._windRaf, ribbons, maxPoints: Math.max(0, ...(el._waves || []).map(w => w.frame.samples.length)) };
    });
  }
  expect(seen.off.eddies).toBe(0); expect(seen.off.loop).toBe(false);
  expect(seen.minimal.eddies).toBe(0);
  expect(seen.normal.eddies).toBe(1);
  expect(seen.intense.eddies).toBe(2);
  for (const level of ['minimal', 'normal', 'intense']) expect(seen[level].ribbons.length, level).toBeGreaterThan(1);
  for (const level of ['minimal', 'normal', 'intense']) expect(seen[level].maxPoints, level).toBeLessThanOrEqual({ minimal: 48, normal: 72, intense: 96 }[level]);
  // the eddies come and go while the loop runs (their opacity changes over time; never a jump of the drawing)
  await settle(page, 4000);
  const later = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('path[data-eddy]')].map(e => [e.getAttribute('opacity'), e.getAttribute('transform')]));
  expect(later.length).toBe(2);
  expect(later.every(([o, t]) => o != null && /translate\(/.test(t))).toBe(true);
});

test('0.26.7.2 the card traces the streams once per house, wind and drawing – a live update reuses them and never restarts the weather', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page, { config: { animation_level: 'normal' } });
  await setup(page, { weather_effects: 'full' }, STATES('pouring', { wind_speed: 80, wind_gust_speed: 110, wind_bearing: 'W' }));
  await settle(page, 400);
  const before = await impl(page).evaluate(el => {
    const cloud = el.shadowRoot.querySelector('.wxu .wx.clouds > i'), a = cloud && cloud.getAnimations()[0], c = a && a.effect.getComputedTiming();
    window.__drops = el._wx.layer.p; window.__some = el._wx.layer.p.slice(0, 60); window.__streams = el._facades.kinds.outer.lanes.streams;
    return { vb: el.shadowRoot.querySelector('svg.plan').getAttribute('viewBox'), gusts: el.shadowRoot.querySelectorAll('path[data-gust]').length, n: el._wx.layer.p.length, cloud: a ? [((c.currentIteration || 0) + c.progress) * c.duration, c.duration] : null, at: performance.now() };
  });
  expect(before.n).toBeGreaterThan(50);
  expect(before.gusts).toBeGreaterThan(0);
  // a new reading of the rooms (as Home Assistant sends every few seconds)
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: 22.3 } }, output_language: 'de' }));
  await settle(page, 120);
  const after = await impl(page).evaluate((el, at) => {
    const cloud = el.shadowRoot.querySelector('.wxu .wx.clouds > i'), a = cloud && cloud.getAnimations()[0], c = a && a.effect.getComputedTiming();
    return { vb: el.shadowRoot.querySelector('svg.plan').getAttribute('viewBox'), same: el._facades.kinds.outer.lanes.streams === window.__streams, kept: el._wx.layer.p === window.__drops && window.__some.filter(q => el._wx.layer.p.includes(q)).length >= 20, n: el._wx.layer.p.length, canvas: el._wx.canvas.isConnected,
      cloud: a ? [((c.currentIteration || 0) + c.progress) * c.duration, c.duration] : null, elapsed: performance.now() - at, loop: !!el._windRaf };
  }, before.at);
  expect([after.same, after.kept, after.canvas, after.loop]).toEqual([true, true, true, true]);   // the same ways and drops, in the same loop
  expect(Math.abs(after.n - before.n)).toBeLessThanOrEqual(2);
  // the new cloud element continues where the old one was (not from its start): same cycle, the time that passed added
  expect(after.cloud[1]).toBe(before.cloud[1]);   // the same cloud (also when the bars changed the drawing's size)
  const cycle = before.cloud[1], expected = (before.cloud[0] + after.elapsed) % cycle, got = after.cloud[0] % cycle;
  // (a restart would put it back to its start: further off than the start latency of an animation on a busy machine)
  expect(Math.min(Math.abs(got - expected), cycle - Math.abs(got - expected))).toBeLessThan(1500);
  // the traced streams are reused (no new geometry for a live update); a new wind direction traces them again
  const reuse = await impl(page).evaluate(el => { const s = el._facades.kinds.outer.lanes.streams; el._render(); const same = el._facades.kinds.outer.lanes.streams === s;
    const w = el._hass.states['weather.home']; el._hass = { ...el._hass, states: { ...el._hass.states, 'weather.home': { ...w, attributes: { ...w.attributes, wind_bearing: 'N' } } } }; el._windSmoothOwn = null;
    el._render(); return [same, el._facades.kinds.outer.lanes.streams === s]; });
  expect(reuse).toEqual([true, false]);
});

test('0.26.7.2 a new reading of the rooms keeps the flow field, the outer ways, joins, curls and the prepared gust profiles; wind or layout prepare them again', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page, { config: { animation_level: 'normal' } });
  await setup(page, { weather_effects: 'full' }, STATES('pouring', { wind_speed: 80, wind_gust_speed: 110, wind_bearing: 'W' }));
  await settle(page, 400);
  const first = await impl(page).evaluate(el => {
    window.__k = { field: el._flowField, speed: el._flow.hit.speed, ways: el._gustRun.ways, next: el._gustRun.next, streams: el._facades.kinds.outer.lanes.streams,
      lanes: el._facades.kinds.outer.lanes, links: el._gustRun.links, curls: el._facades.kinds.outer.lanes.curls };
    return { field: !!el._flowField, ways: el._gustRun.ways.length > 0 && el._gustRun.ways.every(Boolean), gusts: el.shadowRoot.querySelectorAll('path[data-gust]').length };
  });
  expect(first.field && first.ways && first.gusts > 0).toBe(true);
  const kept = el => [el._flowField === window.__k.field, el._flow.hit.speed === window.__k.speed, el._gustRun.ways === window.__k.ways, el._gustRun.next === window.__k.next,
    el._facades.kinds.outer.lanes.streams === window.__k.streams, el._facades.kinds.outer.lanes === window.__k.lanes, el._gustRun.links === window.__k.links,
    el._eddies.items.every(e => window.__k.curls.some(c => c.points === e.points))];
  // an ordinary temperature reading (twice) and an unrelated state change: nothing of the wind is prepared again
  for (const t of [22.3, 22.4]) {
    await page.evaluate(t => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: t } }, output_language: 'de' }), t);
    await settle(page, 120);
    expect(await impl(page).evaluate(kept)).toEqual([true, true, true, true, true, true, true, true]);
  }
  expect(await impl(page).evaluate(el => { el._hass = { ...el._hass, states: { ...el._hass.states, 'sensor.other': { entity_id: 'sensor.other', state: '5', attributes: {} } } }; el._render();
    return [el._flowField === window.__k.field, el._gustRun.ways === window.__k.ways]; })).toEqual([true, true]);
  // the wind's speed: a new field, its speed profile and the gusts' time tables; the traced ways stay (same direction)
  const wind = await impl(page).evaluate(el => { const w = el._hass.states['weather.home'];
    el._hass = { ...el._hass, states: { ...el._hass.states, 'weather.home': { ...w, attributes: { ...w.attributes, wind_speed: 95 } } } }; el._render();
    return [el._flowField === window.__k.field, el._gustRun.ways === window.__k.ways, el._facades.kinds.outer.lanes.streams === window.__k.streams, !!el._flowField]; });
  expect(wind).toEqual([false, false, true, true]);
  // a new direction: new outer ways, joins and curls
  const turned = await impl(page).evaluate(el => { const w = el._hass.states['weather.home'];
    el._hass = { ...el._hass, states: { ...el._hass.states, 'weather.home': { ...w, attributes: { ...w.attributes, wind_bearing: 'N' } } } }; el._windSmoothOwn = null; el._render();
    return [el._facades.kinds.outer.lanes === window.__k.lanes, el._gustRun.links === window.__k.links]; });
  expect(turned).toEqual([false, false]);
  // the layout (a saved edit): everything again
  const layout = await impl(page).evaluate(el => { window.__k = { field: el._flowField, ways: el._gustRun.ways };
    el._layoutInfo = { ...el._layoutInfo, layout: { ...el._layoutInfo.layout } }; el._render();
    return [el._flowField === window.__k.field, el._gustRun.ways === window.__k.ways, !!el._flowField]; });
  expect(layout).toEqual([false, false, true]);
});

test('0.26.7.2 single particles: new values outside the picture, sideways snow, sleet and hail by the condition, nothing for unknown weather', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const r = await page.evaluate(() => {
    const A = window.__A, cv = document.createElement('canvas'), L = new A.WeatherLayer(cv);
    L.setScene({ kind: 'rain', level: 2, slant: 20, n: 80, w: 400, h: 300, scale: 1, splash: 4 }, 1);
    const first = L.p[0], seen = new Set(), starts = [];
    const orig = L._spawn.bind(L); L._spawn = any => { const q = orig(any); starts.push([q.x, q.y, q.vy, q.len, q.a]); return q; };
    for (let i = 0; i < 400; i++) { L.frame(0.05); seen.add(L.p.map(q => q.vy.toFixed(3)).join()); }
    const fresh = starts.filter(s => s[1] < 0 || s[0] < 0 || s[0] > 400);
    // snow sways: the drawn x of one flake changes back and forth while it falls
    const S = new A.WeatherLayer(document.createElement('canvas')); S.setScene({ kind: 'snow', level: 2, slant: 0, n: 30, w: 400, h: 300, scale: 1 }, 1);
    const f = S.p[0], xs = []; for (let i = 0; i < 40; i++) { S.frame(0.05); if (S.p[0] === f) xs.push(f.x + Math.sin(f.ph + f.age * f.freq * 6.283) * f.sway); }
    const dx = xs.slice(1).map((x, i) => Math.sign(x - xs[i])).filter(Boolean);
    const kinds = ['rainy', 'pouring', 'snowy', 'snowy-rainy', 'hail', 'exceptional', 'cloudy', null].map(c => A.skyState({ condition: c }, null).precip);
    const flags = [A.skyState({ raining: true }, null).precip, A.skyState({ snowing: true }, null).precip, A.skyState({ raining: true, snowing: true }, null).precip, A.skyState({}, null).precip];
    return { replaced: !L.p.includes(first), respawned: starts.length, outside: fresh.length / Math.max(starts.length, 1), varied: new Set(starts.map(s => s[2].toFixed(1))).size,
      lens: new Set(starts.map(s => s[3].toFixed(1))).size, rings: L.rings.length <= 4, sway: dx.some((d, i) => i && d !== dx[i - 1]), kinds, flags };
  });
  expect(r.replaced).toBe(true);
  expect(r.respawned).toBeGreaterThan(40);
  expect(r.outside).toBe(1);                                    // every new particle starts outside the visible area
  expect(r.varied).toBeGreaterThan(20); expect(r.lens).toBeGreaterThan(20);   // with its own speed and length
  expect(r.rings).toBe(true);
  expect(r.sway).toBe(true);
  expect(r.kinds).toEqual(['rain', 'rain', 'snow', 'sleet', 'hail', null, null, null]);
  expect(r.flags).toEqual(['rain', 'snow', 'sleet', null]);
  // on the card: sleet and hail are drawn as such, an unknown condition draws nothing that falls
  await page.setViewportSize({ width: 1280, height: 900 });
  for (const [cond, cls] of [['snowy-rainy', 'sleet'], ['hail', 'hail'], ['exceptional', null]]) {
    await setup(page, { weather_effects: 'dynamic' }, STATES(cond));
    const got = await impl(page).evaluate(el => ['rain', 'snow', 'sleet', 'hail'].filter(k => el.shadowRoot.querySelector(`.wxu .wx.${k}`)));
    expect(got, cond).toEqual(cls ? [cls] : []);
  }
});

test('0.26.7.2 load: budgets per level and device, rain also in calm air, the switches and a hidden or removed card stop the work', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  // n: the drops in the picture's budget (after a change of level the extra ones leave the picture as they fall out of it)
  const look = () => impl(page).evaluate(el => ({ level: el.getAttribute('data-motion'), loop: !!el._windRaf, fps: el._windRaf && el._windRaf.fps, n: el._wx.layer ? el._wx.layer.p.filter(q => !q.last).length : 0,
    px: el._wx.canvas ? el._wx.canvas.width * el._wx.canvas.height : 0, css: el._wx.layer ? el._wx.layer.w * el._wx.layer.h : 0, waves: el._waves ? el._waves.length : 0,
    points: el._waves && el._waves.length ? Math.max(...el._waves.map(w => w.frame.samples.length)) : 0 }));
  const at = async (level, extra = {}, wind = { wind_speed: 80, wind_gust_speed: 110, wind_bearing: 'W' }) => { await setup(page, { weather_effects: 'full', animation_level: level, ...extra }, STATES('pouring', wind)); await settle(page, 200); return look(); };
  const calmAir = { wind_speed: 0, wind_gust_speed: 0, wind_bearing: 'W' };
  const levels = {};
  for (const l of ['minimal', 'normal', 'intense']) levels[l] = await at(l);
  const M = await page.evaluate(async src => { const m = await import(eval(src)); return { P: m.PROFILES, S: m.SMALL_CAPS }; }, modUrl('freshairiq-house-motion.js'));
  for (const [l, s] of Object.entries(levels)) {
    expect(s.n, l).toBeLessThanOrEqual(M.P[l].particles);
    expect(s.points, l).toBeLessThanOrEqual(M.P[l].pathPoints);
    expect(s.px, l).toBeLessThanOrEqual(Math.ceil(s.css * M.P[l].wxDpr * M.P[l].wxDpr) + 4);
  }
  expect(levels.minimal.n).toBeLessThan(levels.normal.n); expect(levels.normal.n).toBeLessThan(levels.intense.n);
  // a phone (coarse pointer, small screen): "intense" keeps the lower ceiling
  await page.setViewportSize({ width: 390, height: 844 }); await settle(page, 200);
  const phone = await at('intense');
  expect(phone.fps).toBe(M.S.intense.fps); expect(phone.n).toBeLessThanOrEqual(M.S.intense.particles); expect(phone.points).toBeLessThanOrEqual(M.S.intense.pathPoints);
  expect(phone.px).toBeLessThanOrEqual(Math.ceil(phone.css) + 4);
  await page.setViewportSize({ width: 1280, height: 900 }); await settle(page, 200);
  // rain in calm air: no wind ribbons, the loop still runs for the falling weather
  await impl(page).evaluate(el => { el._house = { ...el._house, wind: { ...el._house.wind, available: false, calm: true, speed_ms: 0 } }; el._payload = { ...el._payload, weather_now: { condition: 'pouring', raining: true } }; });
  const calm = await at('normal', { weather_entity: '' }, calmAir);
  expect([calm.waves, calm.loop, calm.n > 0]).toEqual([0, true, true]);
  // the weather switch off: the drops stand still (no loop for them) – the picture stays
  const still = await at('normal', { weather_entity: '', animation_parts: ['wind', 'light', 'ambient'] }, calmAir);
  expect([still.loop, still.n > 0]).toEqual([false, true]);
  // the card out of sight, covered or removed: no loop
  await at('normal', { weather_entity: '', animation_parts: undefined }, calmAir);
  for (const how of ['hidden', 'covered']) {
    await impl(page).evaluate((el, how) => { if (how === 'hidden') el._offscreen = true; else el._covered = true; el._syncPaused(); }, how);
    expect((await look()).loop, how).toBe(false);
    await impl(page).evaluate(el => { el._offscreen = false; el._covered = false; el._syncPaused(); });
    expect((await look()).loop, how).toBe(true);
  }
  const loop = await page.evaluate(async src => { const m = await import(eval(src)); document.getElementById('card').remove(); return m.loopSize(); }, modUrl('freshairiq-house-motion.js'));
  expect(loop).toBe(0);
});

test('0.26.7.2 fog, clouds, stars, rays and lightning: no grid, nothing in step, the flash not more often or brighter', async ({ page }) => {
  await mount(page);
  await loadMods(page);
  const r = await page.evaluate(() => {
    const A = window.__A, frame = { minX: 0, minY: 0, maxX: 30, maxY: 20 }, px = v => v * 0.05;
    const grab = (cond, phase, wind) => { const under = { html: '', vb: [0, -20, 30, 20], ppu: 40, t: 123.4, level: 'normal', particles: 200 };
      const svg = A.weatherSvg({ ...A.skyState({ condition: cond, thunder: cond === 'lightning-rainy' }, phase === 'night' ? { state: 'below_horizon', attributes: { elevation: -20, azimuth: 0 } } : { state: 'above_horizon', attributes: { elevation: 30, azimuth: 180 } }), directional: true },
        frame, wind, 0, px, 'm', under);
      const d = document.createElement('div'); d.innerHTML = under.html + `<svg>${svg}</svg>`; return d; };
    const wind = { available: true, from_deg: 250, speed_ms: 6 };
    const fog = [...grab('fog', 'day', wind).querySelectorAll('.wx.fog > i')], clouds = [...grab('cloudy', 'day', wind).querySelectorAll('.wx.clouds > i')];
    const stars = [...grab('clear-night', 'night', wind).querySelectorAll('.wx.stars > i')], rays = [...grab('sunny', 'day', wind).querySelectorAll('path.ray')];
    const timing = n => [n.style.animationDuration, n.style.animationDelay];
    const keyframes = A.ATMOS_STYLE.match(/@keyframes flash\{([\s\S]*?)\}\}/)[1];
    const peaks = [...keyframes.matchAll(/opacity:(\.\d+)/g)].map(m => Number(m[1])).filter(v => v > 0);
    const cycle = Number(A.ATMOS_STYLE.match(/\.wx\.flash\{[^}]*animation:flash (\d+)s/)[1]);
    // one flash = its peaks close together (a flicker): peaks less than 3 % of the cycle apart count once
    const at = [...keyframes.matchAll(/(\d+(?:\.\d+)?)%\{opacity:\.\d+\}/g)].map(m => Number(m[1]));
    const flashes = at.filter((p, i) => !i || p - at[i - 1] >= 3).length;
    return { fog: fog.map(n => [n.style.width, n.style.height, n.style.top, ...timing(n)]), clouds: clouds.map(timing), stars: stars.map(timing), rays: rays.map(n => [n.style.animationDuration, n.style.animationDelay]),
      peak: Math.max(...peaks), cycle, flashes };
  });
  const distinct = (rows, k) => new Set(rows.map(x => x[k])).size;
  expect(r.fog.length).toBeGreaterThanOrEqual(3); expect(r.fog.length).toBeLessThanOrEqual(4);
  for (const k of [0, 1, 2, 3, 4]) expect(distinct(r.fog, k), `fog ${k}`).toBe(r.fog.length);   // sizes, heights, drift and fade rhythm all differ
  expect(distinct(r.clouds, 0)).toBe(r.clouds.length); expect(distinct(r.clouds, 1)).toBe(r.clouds.length);
  expect(distinct(r.stars, 0)).toBeGreaterThan(r.stars.length * 0.8);
  expect(distinct(r.rays, 0)).toBe(r.rays.length);
  // lightning: before 0.26.7.2 one flash (two peaks) in 9 s at most .35 – now not more often, never brighter
  expect(r.peak).toBeLessThanOrEqual(0.35);
  expect(r.cycle / Math.max(r.flashes, 1)).toBeGreaterThanOrEqual(9);
});

test('0.26.7.2 lightning in "full" and "dynamic": the uneven sequence of each mode, no jump on a live update; none with "off" and reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page, { config: { animation_level: 'normal' } });
  const flash = () => impl(page).evaluate(el => {
    const n = el.shadowRoot.querySelector('.wxu .wx.flash'); if (!n) return null;
    const a = n.getAnimations()[0]; if (!a) return { name: getComputedStyle(n).animationName, running: false };
    const c = a.effect.getComputedTiming(), peaks = a.effect.getKeyframes().map(k => Number(k.opacity)).filter(v => v > 0);
    const at = a.effect.getKeyframes().filter(k => Number(k.opacity) > 0).map(k => k.offset * 100), events = at.filter((p, i) => !i || p - at[i - 1] >= 3).length;
    return { name: a.animationName, running: true, cycle: c.duration, peak: Math.max(...peaks), events, pos: ((c.currentIteration || 0) + c.progress) * c.duration, at: performance.now() };
  });
  const result = {};
  for (const [fx, name, cycle, peak] of [['dynamic', 'flash', 45000, 0.35], ['full', 'flash-soft', 65000, 0.32]]) {
    await setup(page, { weather_effects: fx }, STATES('lightning-rainy', { wind_speed: 30, wind_bearing: 'SW' }));
    await settle(page, 300);
    const a = await flash();
    expect([a.name, a.cycle, a.peak, a.events], fx).toEqual([name, cycle, peak, 5]);
    expect(a.cycle / a.events, fx).toBe(fx === 'full' ? 13000 : 9000);                       // the mode's earlier average rate
    // a live reading: the new flash layer continues in the same cycle
    await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: 22.4 } }, output_language: 'de' }));
    await settle(page, 150);
    const b = await flash(), expected = (a.pos + (b.at - a.at)) % cycle, diff = Math.abs(b.pos % cycle - expected);
    expect(b.name).toBe(name);
    expect(Math.min(diff, cycle - diff), fx).toBeLessThan(1500);
    result[fx] = true;
  }
  expect(result).toEqual({ dynamic: true, full: true });
  await setup(page, { weather_effects: 'off' }, STATES('lightning-rainy'));
  expect(await flash()).toBe(null);
  await mount(page, { reducedMotion: 'reduce', config: { animation_level: 'normal' } });
  for (const fx of ['dynamic', 'full']) {
    await setup(page, { weather_effects: fx }, STATES('lightning-rainy'));
    const r = await flash();
    expect([r.running, r.name], fx).toEqual([false, 'none']);
  }
});

// 0.26.7.2 (support diagnosis 21.11.): the airing log on the house map – its dates in Home Assistant's time zone (the export
// endpoint's), at 00:20 in Berlin "to" is the new day; a chosen period stays through a live update and both exports request it.
test.describe('0.26.7.2 airing log period', () => {
  test.use({ timezoneId: 'UTC' });
  test('dates in Home Assistant\'s time zone, the chosen period through a live update into CSV and PDF', async ({ page }) => {
    await page.clock.setFixedTime(new Date('2026-11-21T23:20:00Z'));
    await page.setViewportSize({ width: 1280, height: 800 });
    const errors = await mount(page);
    await impl(page).evaluate(el => {
      window.__api3 = [];
      el._hass = { ...el._hass, config: { time_zone: 'Europe/Berlin' }, callApi: (m, p) => {
        window.__api3.push(p); return Promise.resolve(p.includes('format=csv') ? { csv: 'a;b', filename: 'x.csv' } : { pdf_base64: btoa('%PDF-1.4'), filename: 'x.pdf' }); } };
      URL.createObjectURL = () => 'blob:x'; URL.revokeObjectURL = () => {}; HTMLAnchorElement.prototype.click = () => {};
      el._selected = null; el._menuOpen = true; el._render(); el.shadowRoot.querySelector('[data-ventlog]').click();
    });
    await expect.poll(() => impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg[open] #ventlog-export'))).toBe(true);
    const dates = () => impl(page).evaluate(el => ['ventlog-start', 'ventlog-end'].map(id => el.shadowRoot.getElementById(id).value));
    expect(await dates()).toEqual(['2026-10-23', '2026-11-22']);
    await impl(page).evaluate(el => {
      for (const [id, value] of [['ventlog-start', '2026-11-03'], ['ventlog-end', '2026-11-07']]) {
        const input = el.shadowRoot.getElementById(id); input.value = value; input.dispatchEvent(new Event('change'));
      }
    });
    await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de' }));
    await settle(page, 120);
    expect(await dates()).toEqual(['2026-11-03', '2026-11-07']);
    await impl(page).evaluate(el => el.shadowRoot.getElementById('ventlog-csv').click());
    await expect.poll(() => page.evaluate(() => window.__api3.length)).toBe(1);
    await impl(page).evaluate(el => el.shadowRoot.getElementById('ventlog-export').click());
    await expect.poll(() => page.evaluate(() => window.__api3.length)).toBe(2);
    expect(await page.evaluate(() => window.__api3)).toEqual(['freshairiq/ventilation-log/e1?start=2026-11-03&end=2026-11-07&format=csv',
      'freshairiq/ventilation-log/e1?start=2026-11-03&end=2026-11-07']);
    expect(errors).toEqual([]);
  });
});

// 0.26.7.2 (owner order 21.11.): a pure reading update changes the plan's labels and states in place – the plan, the weather and
// the wind layers stay the same nodes; a change of the floor, the layer, the house (geometry) or anything else in the update draws
// completely. Focus, scroll, quick updates, a hidden card and the shared loop.
test('0.26.7.2 a reading update in place; floor, layer, house and other changes draw anew', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const errors = await mount(page);
  await setup(page);
  await settle(page, 300);
  const live = (temperature, extra = {}, rest = {}) => page.evaluate(([temperature, extra, rest]) => window.__subs['freshairiq/dashboard/subscribe'](
    { rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature, ...extra } }, output_language: 'de', ...rest }), [temperature, extra, rest]);
  const state = () => impl(page).evaluate(el => { const r = el.shadowRoot, bad = r.querySelector('polygon.room[data-room="r_bad"]');
    return { same: r.querySelector('.stage') === window.__stage && r.querySelector('svg.plan') === window.__svg && r.querySelector('path[data-wave]') === window.__wave,
      label: bad ? bad.getAttribute('aria-label') : null, text: r.querySelector('svg.plan') ? r.querySelector('svg.plan').textContent : '',
      focus: r.activeElement ? r.activeElement.getAttribute('data-floor') : null, scroll: r.querySelector('.map').scrollTop, raf: !!el._windRaf }; });
  const mark = () => impl(page).evaluate(el => { const r = el.shadowRoot; window.__stage = r.querySelector('.stage'); window.__svg = r.querySelector('svg.plan'); window.__wave = r.querySelector('path[data-wave]'); });
  await mark();
  await impl(page).evaluate(el => { const r = el.shadowRoot, map = r.querySelector('.map'); map.style.maxHeight = '200px'; map.style.overflow = 'auto'; map.scrollTop = 40;
    r.querySelector('[data-floor]').focus(); });
  const before = await state();
  await live(21.3);
  await settle(page, 150);
  let now = await state();
  expect([now.same, now.label.includes('21.3 °C'), now.text.includes('21.3 °C'), now.focus, now.scroll, now.raf]).toEqual([true, true, true, before.focus, before.scroll, true]);
  // quick readings within one frame: the last one is shown, still in place
  await page.evaluate(() => { for (const t of [21.1, 21.2, 21.4]) window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: t } }, output_language: 'de' }); });
  await settle(page, 150);
  now = await state();
  expect([now.same, now.label.includes('21.4 °C'), now.text.includes('21.2 °C')]).toEqual([true, true, false]);
  // a room's state: a shade of the same drawing in place (the climate tint follows the reading) …
  const tint = () => impl(page).evaluate(el => el.shadowRoot.querySelector('g.climate polygon.cl').getAttribute('fill-opacity') || el.shadowRoot.querySelector('g.climate polygon.cl').getAttribute('stroke-opacity'));
  await live(23.4);                                                     // warm: the tint appears (drawn completely)
  await settle(page, 150);
  await mark();
  const tint0 = await tint();
  await live(24.1);
  await settle(page, 150);
  now = await state();
  expect([now.same, (await tint()) !== tint0, now.label.includes('24.1 °C')]).toEqual([true, true, true]);
  // … another action (other symbols on the plan) is drawn completely and shown
  await live(21.4, { action: 'Okay', house_aligned_action: 'okay' });
  await settle(page, 150);
  now = await state();
  expect([now.label === before.label, now.label.includes('21.4 °C'), now.focus]).toEqual([false, true, before.focus]);
  await mark();
  // something else in the update (outdoor values): drawn completely
  await live(21.4, { action: 'Okay', house_aligned_action: 'okay' }, { outdoor_temperature: 3.2 });
  await settle(page, 150);
  expect((await state()).same).toBe(false);
  // the house (layout, openings, air paths): drawn completely
  await mark();
  await page.evaluate(() => window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, airflow: { ...window.__HOUSE.airflow,
    openings: { ...window.__HOUSE.airflow.openings, o_wohnen: { ...window.__HOUSE.airflow.openings.o_wohnen, state: 'open', size: 'large' } } } }));
  await settle(page, 150);
  expect((await state()).same).toBe(false);
  // another layer and another floor: drawn completely; a reading there is in place again
  await mark();
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-layer="humidity"]') ? el.shadowRoot.querySelector('[data-layer="humidity"]').click() : (el._layer = 'humidity', el._render()));
  expect((await state()).same).toBe(false);
  await mark();
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-floor]').click());
  await settle(page, 150);
  expect((await state()).same).toBe(false);
  await mark();
  await live(21.2, { action: 'Okay', house_aligned_action: 'okay' }, { outdoor_temperature: 3.2 });
  await settle(page, 150);
  expect((await state()).same).toBe(true);
  // a hidden card (out of view: paused, no loop) still takes the reading; back in view it runs again
  await impl(page).evaluate(el => { el._layer = 'action'; el._chooseFloor('f_eg'); });
  await page.evaluate(() => { document.getElementById('m').style.marginTop = '4000px'; });
  await expect.poll(() => impl(page).evaluate(el => el.hasAttribute('data-paused'))).toBe(true);
  await settle(page, 300);
  await mark();
  await live(21.1, { action: 'Okay', house_aligned_action: 'okay' }, { outdoor_temperature: 3.2 });
  await settle(page, 150);
  now = await state();
  expect([now.same, now.label.includes('21.1 °C'), now.raf]).toEqual([true, true, false]);
  await page.evaluate(() => { document.getElementById('m').style.marginTop = '0px'; });
  await expect.poll(() => impl(page).evaluate(el => !el.hasAttribute('data-paused') && !!el._windRaf)).toBe(true);
  const loop = await page.evaluate(async () => (await import(performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/freshairiq-house-motion.js')))).loopSize());
  expect(loop).toBe(1);
  // an open room window: drawn completely, its values follow
  await impl(page).evaluate(el => { const r = el._layout().layout.rooms.find(x => x.room_key === 'bad'); el._selected = { type: 'room', id: r.id }; el._render(); });
  await live(21.3, { action: 'Okay', house_aligned_action: 'okay' }, { outdoor_temperature: 3.2 });
  await settle(page, 150);
  expect(await impl(page).evaluate(el => /21[.,]3\s?°C/.test(el.shadowRoot.querySelector('dialog.roomdlg[open]').textContent))).toBe(true);
  expect(errors).toEqual([]);
});

// 0.26.7.2 (owner order 21.11., third): the complete coordinator payload of a live update – readings and house values
// (temperature, humidity, total_water_ml, the removable moisture) change together and are updated in place; the scene keeps its
// nodes (plan, weather layer and canvas, wind paths, air canvas) and the loop. A wind reading that only got older stays in place;
// openings, air paths, the weather and both channels in one frame draw completely.
const FULL = (rooms, extra = {}) => ({
  freshairiq_live_api: 'dashboard_ws_v1', freshairiq_entry_id: 'e1', freshairiq_version: '0.26.7.2', output_language: 'de', status: 'ok', status_text: 'Alles im grünen Bereich',
  rooms, levels: ['ground_floor', 'upper_floor'], total_water_ml: 1840, potential_total_ml: 420, live_balance_ml: null, moisture_balance_today_ml: -260,
  recommended_duration_min: 12, remaining_duration_min: null, remaining_duration_state: null, prognosis_confidence: 72, forecast_horizon_min: 15,
  forecast_moisture_effect_ml: -210, forecast_temperature_change_c: -0.6, ventilation_threshold_ml: 300, overnight_forecast_ml: 380, night_model_samples: 9,
  effective_occupants: 2, outdoor_temperature: 6.5, outdoor_humidity: 81, outdoor_absolute_humidity: 6.1, wind_speed: 4.2, wind_bearing: 250,
  weather_now: { condition: 'rainy', raining: true, outdoor_temperature: 6.5 }, pollen_enabled: false,
  intelligent_recommendation: { kind: 'close', title: 'Bad schließen', instruction: 'Fenster im Bad schließen', room_keys: ['bad'], status: 'action' },
  night_strategy: { action: 'closed', summary: 'Nachts geschlossen lassen' }, history_summary: { days: 14 }, ...extra });
test('0.26.7.2 a complete live payload: readings and house values in place, the scene keeps its nodes', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = await mount(page);
  await setup(page, { weather_effects: 'full' });
  const send = (bad, extra = {}) => page.evaluate(([bad, extra, full]) => window.__subs['freshairiq/dashboard/subscribe'](
    eval(full)({ ...window.__ROOMS, bad: { ...window.__ROOMS.bad, ...bad } }, extra)), [bad, extra, FULL.toString()]);
  await send({});
  await settle(page, 400);
  const mark = () => impl(page).evaluate(el => { const r = el.shadowRoot;
    window.__nodes = [r.querySelector('.stage'), r.querySelector('svg.plan'), r.querySelector('.wxu'), r.querySelector('path[data-wave]'), el._wx.canvas, el._flowCanvas, r.querySelector('.moist')]; });
  const same = () => impl(page).evaluate(el => { const r = el.shadowRoot, now = [r.querySelector('.stage'), r.querySelector('svg.plan'), r.querySelector('.wxu'), r.querySelector('path[data-wave]'), el._wx.canvas, el._flowCanvas, r.querySelector('.moist')];
    return now.every((n, i) => n === window.__nodes[i]) && (!el._wx.canvas || el._wx.canvas.isConnected) && !!el._windRaf; });
  const label = () => impl(page).evaluate(el => el.shadowRoot.querySelector('polygon.room[data-room="r_bad"]').getAttribute('aria-label'));
  const chip = () => impl(page).evaluate(el => (el.shadowRoot.querySelector('.moist') || {}).textContent || '');
  const menu = () => impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.menudlg'); return { same: d === window.__menu, text: d.textContent.replace(/\s+/g, ' ') }; });
  await mark();
  await impl(page).evaluate(el => { window.__menu = el.shadowRoot.querySelector('dialog.menudlg'); });
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('path[data-wave]') && !!el._wx.canvas && !!el._windRaf)).toBe(true);
  const chip0 = await chip();
  await send({ temperature: 21.3, humidity: 57 }, { total_water_ml: 1915, potential_total_ml: 465, moisture_balance_today_ml: -300,
    status_text: 'Stand 21:30', intelligent_recommendation: { kind: 'close', title: 'Bad jetzt schließen', instruction: 'Fenster im Bad schließen', room_keys: ['bad'], status: 'action' } });
  await settle(page, 1200);                                              // the removable moisture glides to its new value
  expect(await same()).toBe(true);
  const now = await label();
  expect([now.includes('21.3 °C'), now.includes('57 %'), (await chip()) !== chip0, (await chip()).includes('465')]).toEqual([true, true, true, true]);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('svg.plan').textContent.includes('21.3 °C · 57 %'))).toBe(true);
  // the menu window carries the recommendation and the house values: it follows in place as well (a narrow card shows them only there)
  expect(await menu()).toEqual(expect.objectContaining({ same: true }));
  expect([(await menu()).text.includes('Stand 21:30'), (await menu()).text.includes('Bad jetzt schließen')]).toEqual([true, true]);
  // the house values in the house window (drawn when it opens)
  await impl(page).evaluate(el => { el._go('house', ''); });
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg[open]').textContent.replace(/\s+/g, ' '))).toContain('1915 ml');
  // an update while the window is open: its content follows (drawn completely), the window stays open
  await send({ temperature: 21.3, humidity: 57 }, { total_water_ml: 1960, potential_total_ml: 465 });
  await settle(page, 200);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg[open]').textContent.replace(/\s+/g, ' '))).toContain('1960 ml');
  await impl(page).evaluate(el => el._closeDialog());
  await settle(page, 200);
  await mark();
  // the house channel: only the age of the wind reading – in place
  await impl(page).evaluate(el => { window.__menu = el.shadowRoot.querySelector('dialog.menudlg'); });
  await page.evaluate(() => window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, wind: { ...window.__HOUSE.wind, age_s: 300 } }));
  await settle(page, 200);
  expect(await same()).toBe(true);
  expect((await menu()).same).toBe(true);
  // an opening changes: drawn completely
  const opened = () => ({ ...window.__HOUSE, wind: { ...window.__HOUSE.wind, age_s: 360 }, airflow: { ...window.__HOUSE.airflow, openings: { ...window.__HOUSE.airflow.openings, o_bad: { ...window.__HOUSE.airflow.openings.o_bad, pending: false, state: 'open' } } } });
  await page.evaluate(`window.__subs['freshairiq/house_map/subscribe']((${opened.toString()})())`);
  await settle(page, 200);
  expect(await same()).toBe(false);
  // both channels in one frame (a reading and a new air path): drawn completely, both shown
  await mark();
  await page.evaluate(([full]) => { const make = eval(full);
    window.__subs['freshairiq/dashboard/subscribe'](make({ ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: 21.1, humidity: 57 } }, { total_water_ml: 1960, potential_total_ml: 465 }));
    window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, wind: { ...window.__HOUSE.wind, age_s: 400 }, airflow: { ...window.__HOUSE.airflow, paths: [] } }); }, [FULL.toString()]);
  await settle(page, 200);
  expect([await same(), (await label()).includes('21.1 °C')]).toEqual([false, true]);
  // another weather (the weather layer's source): drawn completely
  await mark();
  await send({ temperature: 21.1, humidity: 57 }, { total_water_ml: 1960, potential_total_ml: 465, weather_now: { condition: 'snowy', raining: false, outdoor_temperature: -1 } });
  await settle(page, 200);
  expect(await same()).toBe(false);
  expect(errors).toEqual([]);
});
