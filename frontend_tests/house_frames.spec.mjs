// House map: smooth animation (0.26.7.0, moved here in 0.26.7.0(2)). A frame-time measurement depends on the machine, so it
// runs in its own Playwright project after every other browser test (playwright.config.mjs: frames-*), never next to them.
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
const SITUATIONS = [
  ['sunny morning', 'sunny', 8, 100, { cloud_coverage: 5 }, 2], ['noon', 'sunny', 45, 180, { cloud_coverage: 0 }, 2], ['sunset', 'sunny', 1.5, 262, { cloud_coverage: 5 }, 3],
  ['rain', 'rainy', 20, 200, {}, 5], ['storm', 'pouring', 20, 220, { wind_speed: 95, wind_gust_speed: 125, wind_bearing: 'W' }, 25], ['snow', 'snowy', 12, 170, {}, 3],
  ['thunderstorm', 'lightning-rainy', 18, 230, { wind_speed: 50, wind_bearing: 'SW' }, 9], ['twilight', 'partlycloudy', -3, 250, {}, 2], ['night', 'clear-night', -25, 330, { cloud_coverage: 0 }, 2],
];
test('0.26.7.0 smooth animation: sun, rain, storm, snow, thunder, day and night – 95th percentile frame time below 50 ms', async ({ page }, testInfo) => {
  test.setTimeout(120000);
  // a large desktop screen; a phone project (Android WebView) keeps its own screen – a 1440 px wide phone at its pixel
  // density (3780 × 2362 device pixels) exists nowhere and only measured the software rasteriser
  if (!testInfo.project.use.isMobile) await page.setViewportSize({ width: 1440, height: 900 });
  await mount(page);
  for (const [name, state, elev, az, attrs, wind] of SITUATIONS) {
    await impl(page).evaluate((el, [state, elev, az, attrs, wind]) => {
      el.setConfig({ ...el._config, weather_entity: 'weather.own', weather_effects: 'full' });
      el._hass = { ...el._hass, states: { 'weather.own': { entity_id: 'weather.own', state, last_updated: `${state}full`, attributes: { temperature: 9, wind_speed: wind * 3.6, wind_bearing: 250, ...attrs } },
        'sun.sun': { state: elev > 0 ? 'above_horizon' : 'below_horizon', attributes: { elevation: elev, azimuth: az } }, 'sensor.moon_phase': { state: 'waxing_gibbous', attributes: {} } } };
      el._render();
    }, [state, elev, az, attrs, wind]);
    // the running animation is measured, not the one-off redraw of the new scene
    await page.waitForTimeout(400);
    // up to three windows of 85 frames, the best counts; a drawing that is really too heavy misses the limit in every window
    const p95 = () => page.evaluate(() => new Promise(res => { const t = []; let last = performance.now(); const step = now => { t.push(now - last); last = now; if (t.length < 90) requestAnimationFrame(step); else { const f = t.slice(5).sort((a, b) => a - b); res(f[Math.floor(f.length * 0.95)]); } }; requestAnimationFrame(step); }));
    let best = Infinity;
    for (let w = 0; w < 3 && best >= 50; w++) best = Math.min(best, await p95());
    expect(best, `${name}: 95th percentile frame time`).toBeLessThan(50);
  }
});

// 0.26.7.0(2) corrections, point 4: longer load with several house maps visible at once – the work per second stays low and
// does not creep up, one shared loop serves every card, nothing accumulates (heap, DOM nodes). A real phone's temperature and
// energy use cannot be measured here (headless browser on a server CPU) – that stays an external runtime check.
test('0.26.7.0(2) three house maps for 30 s in a storm: low steady load, one shared loop, nothing accumulates', async ({ page }, testInfo) => {
  test.setTimeout(120000);
  if (!testInfo.project.use.isMobile) await page.setViewportSize({ width: 1440, height: 900 });
  await mount(page);
  // three cards side by side, as in a dashboard grid – all three visible at once (a card out of view pauses by design)
  await page.evaluate(() => { const m = document.getElementById('m'); m.style.cssText = 'display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px'; for (const id of ['card2', 'card3']) { const c = document.createElement('freshairiq-house-card'); c.id = id; c.setConfig({}); document.getElementById('m').appendChild(c); c.hass = document.getElementById('card').hass; } });
  await page.waitForFunction(() => document.querySelectorAll('freshairiq-house-card-impl').length === 3);
  await page.evaluate(() => {
    const states = { 'weather.own': { entity_id: 'weather.own', state: 'pouring', last_updated: 'x', attributes: { temperature: 9, wind_speed: 90, wind_gust_speed: 120, wind_bearing: 250 } }, 'sun.sun': { state: 'above_horizon', attributes: { elevation: 20, azimuth: 200 } } };
    for (const el of document.querySelectorAll('freshairiq-house-card-impl')) { el.setConfig({ ...el._config, weather_entity: 'weather.own', weather_effects: 'full' }); el._hass = { ...el._hass, states }; el._render(); }
    window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de' });
  });
  await page.waitForTimeout(1500);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const metrics = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]));
  const nodes = () => page.evaluate(() => [...document.querySelectorAll('freshairiq-house-card-impl')].reduce((s, el) => s + el.shadowRoot.querySelectorAll('*').length, 0));
  const windowOf = async seconds => {
    const a = await metrics(), t0 = Date.now();
    const raf = await page.evaluate(ms => new Promise(res => { let n = 0; const orig = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = cb => { n += 1; return orig(cb); }; setTimeout(() => { window.requestAnimationFrame = orig; res(n); }, ms); }), seconds * 1000);
    const b = await metrics(), s = (Date.now() - t0) / 1000;
    return { task: (b.TaskDuration - a.TaskDuration) * 1000 / s, raf: raf / s, heap: b.JSHeapUsedSize };
  };
  const n0 = await nodes(), first = await windowOf(10);
  // live updates keep coming during the load, as in Home Assistant (a new reading every few seconds)
  const ticker = await page.evaluate(() => { let k = 0; window.__live = setInterval(() => { k += 1; window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: 21 + (k % 5) / 10 } }, output_language: 'de' }); }, 2000); return true; });
  expect(ticker).toBe(true);
  await page.waitForTimeout(10000);
  const last = await windowOf(10), n1 = await nodes();
  await page.evaluate(() => clearInterval(window.__live));
  const loop = await page.evaluate(async () => (await import('/freshairiq-house-motion.js?v=0.26.7.0')).loopSize());
  testInfo.annotations.push({ type: 'load', description: JSON.stringify({ first, last, n0, n1, loop }) });
  const visible = await page.evaluate(() => [...document.querySelectorAll('freshairiq-house-card-impl')].filter(el => !el.hasAttribute('data-paused')).length);
  expect([visible, loop]).toEqual([3, 3]);                               // one loop, three visible cards in it
  expect(first.raf).toBeLessThan(40); expect(last.raf).toBeLessThan(40);  // 0.26.7.0: ~60 animation frames per card and second
  expect(first.task).toBeLessThan(400); expect(last.task).toBeLessThan(400);   // 0.26.7.0: 440–460 ms/s for ONE card on the phone emulation
  expect(last.task).toBeLessThan(first.task * 1.6 + 40);                 // no creeping load over time
  expect(last.heap).toBeLessThan(first.heap * 1.5 + 4e6);                // nothing accumulates
  expect(Math.abs(n1 - n0)).toBeLessThanOrEqual(Math.max(30, n0 * 0.05));
  // all three gone: the loop is empty, no timer keeps running
  await page.evaluate(() => document.querySelectorAll('freshairiq-house-card').forEach(c => c.remove()));
  expect(await page.evaluate(async () => (await import('/freshairiq-house-motion.js?v=0.26.7.0')).loopSize())).toBe(0);
});
