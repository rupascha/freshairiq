// 0.26.7.0 UI/theme order: every house map window in one style, the design modes (FreshAirIQ / Home Assistant theme /
// custom), contrast in light, dark and custom themes, phones to desktops. Fixture and mount as in house.spec.mjs.
import { test, expect } from '@playwright/test';
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
const push = (page, extra) => page.evaluate(x => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, ...x }), extra);
const SHOTS = process.env.FAIQ_SHOTS || '';

// every window of the house map: [name, selection, payload extra]
const DIALOGS = [
  ['moisture_idle', { type: 'moisture' }, { status: 'ventilate', potential_total_ml: 1947.4, live_balance_ml: 0, recommended_duration_min: 12, remaining_duration_min: 12, prognosis_confidence: 70 }],
  ['moisture_live', { type: 'moisture' }, 'live'],
  ['rooms', { type: 'rooms' }], ['room', { type: 'room', id: 'r_bad' }], ['room_nodata', { type: 'room', id: 'r_flur' }, 'nodata'],
  ['weather', { type: 'weather' }], ['house', { type: 'house' }], ['ventlog', { type: 'ventlog' }], ['classic', { type: 'classic', id: 'learning' }],
  ['support', { type: 'support' }], ['opening', { type: 'opening', id: 'o_bad' }], ['path', { type: 'path', id: 0 }], ['menu', 'menu'],
];
async function openDialog(page, [, sel, extra]) {
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  if (extra === 'live') await page.evaluate(() => { const r = window.__ROOMS; window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...r, bad: { ...r.bad, active: true, result_ml: 120, session_target_min: 12, session_elapsed_min: 5 } }, status: 'ventilate', potential_total_ml: 1500, live_balance_ml: 121.6, recommended_duration_min: 12, remaining_duration_min: 7 }); });
  else if (extra && typeof extra === 'object') await push(page, extra);
  if (extra === 'nodata') await impl(page).evaluate(el => { const r = { ...el._rooms }; delete r.flur; el._rooms = r; });
  await settle(page, 150);
  if (sel === 'menu') await impl(page).evaluate(el => el._openMenu());
  else await impl(page).evaluate((el, sel) => { el._nav = []; el._menuOpen = false; el._selected = sel; el._render(); }, sel);
  await settle(page, 250);
  return impl(page).locator(sel === 'menu' ? 'dialog.menudlg[open] .dlg' : 'dialog.roomdlg[open] .dlg');
}

test('probe: screenshots of every window (only with FAIQ_SHOTS)', async ({ page }) => {
  test.skip(!SHOTS, 'documentation run only');
  await page.setViewportSize({ width: 820, height: 1000 });
  await mount(page);
  for (const d of DIALOGS) {
    const dlg = await openDialog(page, d);
    await dlg.screenshot({ path: `${SHOTS}/${d[0]}.png` });
    await impl(page).evaluate(el => { el._selected = null; el._menuOpen = false; el._render(); });
  }
});

// ---- the contrast of every text in a window, measured on the computed styles (gradients: every stop counts) ----
async function scanWindow(page, selector) {
  return impl(page).evaluate((el, selector) => {
    const root = el.shadowRoot.querySelector(selector);
    if (!root) return { missing: true };
    const num = x => (x.endsWith('%') ? Number(x.slice(0, -1)) / 100 : Number(x));
    const parse = s => {
      let m = /rgba?\(([^)]+)\)/.exec(s);
      if (m) { const v = m[1].split(/[ ,/]+/).filter(Boolean).map(num); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; }
      m = /color\(srgb ([^)]+)\)/.exec(s);
      if (m) { const v = m[1].split(/[ /]+/).filter(Boolean).map(num); return [v[0] * 255, v[1] * 255, v[2] * 255, v.length > 3 ? v[3] : 1]; }
      return null;
    };
    const colours = s => (String(s).match(/rgba?\([^)]+\)|color\(srgb [^)]+\)/g) || []).map(parse).filter(Boolean);
    const lum = c => { const f = x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
    const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const over = (t, b) => { const a = t[3]; return [0, 1, 2].map(i => t[i] * a + b[i] * (1 - a)).concat(1); };
    const backgrounds = node => {
      const layers = [];
      for (let x = node; x; x = x.parentElement) {
        const cs = getComputedStyle(x), img = colours(cs.backgroundImage), bc = parse(cs.backgroundColor);
        if (img.length) layers.push({ grad: img });
        if (bc && bc[3] > 0) layers.push({ color: bc });
        if (x === root) break;
      }
      let cands = [[255, 255, 255, 1]];
      for (const l of layers.reverse()) cands = l.color ? cands.map(c => over(l.color, c)) : cands.flatMap(c => l.grad.map(g => over(g, c)));
      return cands;
    };
    const opacity = node => { let o = 1; for (let x = node; x; x = x.parentElement) { o *= Number(getComputedStyle(x).opacity); if (x === root) break; } return o; };
    const bad = [], seen = new Set();
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let t = walker.nextNode(); t; t = walker.nextNode()) {
      const n = t.parentElement;
      if (!n || seen.has(n) || !/[\p{L}\p{N}]/u.test(t.textContent) || n.closest('svg')) continue;
      seen.add(n);
      const cs = getComputedStyle(n), box = n.getBoundingClientRect();
      if (!box.width || !box.height || cs.visibility === 'hidden' || n.closest('[disabled]')) continue;
      const fg = parse(cs.color), op = opacity(n), size = parseFloat(cs.fontSize), weight = Number(cs.fontWeight) || 400;
      const need = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      const worst = Math.min(...backgrounds(n).map(bg => ratio(over([fg[0], fg[1], fg[2], fg[3] * op], bg), bg)));
      if (worst < need - 0.005) bad.push(`${n.tagName.toLowerCase()}.${n.className || ''} "${t.textContent.trim().slice(0, 28)}" ${worst.toFixed(2)} < ${need}${globalThis.FAIQ_DEBUG ? ` fg=${cs.color} op=${op} bgs=${JSON.stringify(backgrounds(n).map(b => b.map(Math.round)))}` : ''}`);
    }
    const foot = root.querySelector('.foot button'), dlgBg = backgrounds(root)[0];
    const btn = foot ? (() => { const cs = getComputedStyle(foot); return Math.max(ratio(parse(cs.backgroundColor), dlgBg), ratio(parse(cs.borderTopColor), dlgBg)); })() : null;
    const box = root.getBoundingClientRect(), close = foot && foot.getBoundingClientRect();
    return { bad, button: btn, white: lum(dlgBg) > 0.8 && !getComputedStyle(root).backgroundImage.includes('gradient'), classes: root.className,
      box: { left: box.left, top: box.top, right: box.right, bottom: box.bottom }, close: close && { top: close.top, bottom: close.bottom, left: close.left, right: close.right, w: close.width, h: close.height },
      vw: innerWidth, vh: innerHeight, hscroll: [...root.querySelectorAll('*')].filter(x => x.scrollWidth > x.clientWidth + 2 && ['auto', 'scroll'].includes(getComputedStyle(x).overflowX)).map(x => x.className).slice(0, 5) };
  }, selector);
}
const selectorOf = d => (d[1] === 'menu' ? 'dialog.menudlg[open] .dlg' : 'dialog.roomdlg[open] .dlg');
const closeAll = page => impl(page).evaluate(el => { el._selected = null; el._menuOpen = false; el._render(); });
const setTheme = (page, vars) => page.evaluate(vars => { const s = document.documentElement.style; for (const [k, v] of Object.entries(vars)) s.setProperty(k, v); }, vars);

// Home Assistant's default themes (the values of its frontend) and an unusual one
const HA_THEMES = {
  light: { '--card-background-color': '#ffffff', '--ha-card-background': '#ffffff', '--primary-background-color': '#fafafa', '--primary-text-color': '#212121', '--secondary-text-color': '#727272', '--primary-color': '#03a9f4', '--text-primary-color': '#ffffff', '--divider-color': 'rgba(0,0,0,.12)' },
  dark: { '--card-background-color': '#1c1c1c', '--ha-card-background': '#1c1c1c', '--primary-background-color': '#111111', '--primary-text-color': '#e1e1e1', '--secondary-text-color': '#9b9b9b', '--primary-color': '#03a9f4', '--text-primary-color': '#ffffff', '--divider-color': 'rgba(225,225,225,.12)' },
  // black text on a dark blue card and a yellow accent with white text: unreadable as given – the card must fix it
  custom: { '--card-background-color': '#06305c', '--ha-card-background': '#06305c', '--primary-background-color': '#021a33', '--primary-text-color': '#000000', '--secondary-text-color': '#1b2b3b', '--primary-color': '#ffd400', '--text-primary-color': '#ffffff', '--divider-color': '#0a3d70', '--ha-card-border-radius': '4px', '--ha-card-border-width': '3px' },
  // a transparent (glass) dashboard
  glass: { '--card-background-color': 'rgba(255,255,255,0.12)', '--ha-card-background': 'rgba(255,255,255,0.12)', '--primary-background-color': '#26323a', '--primary-text-color': '#ffffff', '--secondary-text-color': '#d0d6da', '--primary-color': '#7fd1ff', '--text-primary-color': '#0a1f38', '--divider-color': 'rgba(255,255,255,.25)', '--ha-card-backdrop-filter': 'blur(12px)' },
};
const DESIGNS = [
  ['freshairiq', {}, null], ['ha light', { design: 'ha' }, 'light'], ['ha dark', { design: 'ha' }, 'dark'], ['ha custom theme', { design: 'ha' }, 'custom'], ['ha glass', { design: 'ha' }, 'glass'],
  ['custom light', { design: 'custom', design_dialog: '#f4f1e8', design_background: '#ffffff', design_accent: '#7a3cff', design_border: 2, design_radius: 6 }, 'light'],
  ['custom dark', { design: 'custom', design_dialog: '#20232a', design_accent: '#ffd400', design_text: 'light' }, 'dark'],
  ['custom unreadable choice', { design: 'custom', design_dialog: '#f0f0f0', design_text: 'light', design_accent: '#fafafa' }, 'light'],
  ['custom transparent', { design: 'custom', design_background: 'transparent', design_dialog: '#0b2f57' }, 'glass'],
];

test('UI01/UI02: every window of the house map has the blue house map style (FreshAirIQ design) – moisture before and while airing, opening, air path, room without data, support, menu', async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 1000 });
  await mount(page);
  for (const d of DIALOGS) {
    await openDialog(page, d);
    const r = await scanWindow(page, selectorOf(d));
    expect(r.classes, d[0]).toContain('dark'); expect(r.classes, d[0]).toContain('world');
    expect(r.white, d[0]).toBe(false);                      // before: the moisture, opening and air-path windows were white
    await closeAll(page);
  }
});

for (const [name, config, theme] of DESIGNS) {
  test(`UI03: contrast in every window – ${name}${theme ? `, ${theme} theme` : ''}: text 4.5:1 (large 3:1), the close button 3:1`, async ({ page }) => {
    await page.setViewportSize({ width: 820, height: 1000 });
    await mount(page, { config });
    if (theme) { await setTheme(page, HA_THEMES[theme]); await impl(page).evaluate(el => el._applyDesign()); }
    await page.evaluate(() => { globalThis.FAIQ_DEBUG = true; });
    const failures = [];
    for (const d of DIALOGS) {
      await openDialog(page, d);
      const r = await scanWindow(page, selectorOf(d));
      if (r.bad.length) failures.push(`${d[0]}: ${r.bad.join(' | ')}`);
      if (r.button != null && r.button < 3) failures.push(`${d[0]}: close button ${r.button.toFixed(2)}`);
      await closeAll(page);
    }
    expect(failures).toEqual([]);
    // the meaning of the plan never changes with a design: the room states keep their colours
    const fills = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].map(p => `${p.getAttribute('class')}:${getComputedStyle(p).fill}`));
    expect(fills.length).toBeGreaterThan(0);
    // nothing of a design is set in the FreshAirIQ design: the look of every older card
    if (name === 'freshairiq') expect(await impl(page).evaluate(el => [el.hasAttribute('data-design'), el.hasAttribute('data-scheme'), (el.getAttribute('style') || '').includes('--fq-')])).toEqual([false, false, false]);
  });
}

test('UI04: the state colours of the plan are the same in every design', async ({ page }) => {
  await mount(page);
  const fills = () => impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room, .rim')].map(p => `${p.getAttribute('class')}|${p.getAttribute('fill') || ''}|${getComputedStyle(p).fill}|${getComputedStyle(p).stroke}`).join(';'));
  const base = await fills();
  for (const [, config, theme] of DESIGNS.slice(1)) {
    if (theme) await setTheme(page, HA_THEMES[theme]);
    await impl(page).evaluate((el, c) => el.setConfig(c), config);
    await settle(page, 80);
    expect(await fills()).toBe(base);
  }
});

test('probe: screenshots of the designs and themes (only with FAIQ_SHOTS)', async ({ page }) => {
  test.skip(!SHOTS, 'documentation run only');
  await page.setViewportSize({ width: 820, height: 1000 });
  for (const [name, config, theme] of DESIGNS.filter(d => ['freshairiq', 'ha light', 'ha dark', 'ha custom theme', 'ha glass', 'custom light'].includes(d[0]))) {
    await mount(page, { config });
    if (theme) { await setTheme(page, HA_THEMES[theme]); await impl(page).evaluate(el => el._applyDesign()); }
    for (const d of DIALOGS.filter(x => ['moisture_live', 'rooms', 'room', 'menu', 'house', 'classic'].includes(x[0]))) {
      const dlg = await openDialog(page, d);
      await dlg.screenshot({ path: `${SHOTS}/${name.replace(/ /g, '_')}__${d[0]}.png` });
      await closeAll(page);
    }
  }
});

// ---- UI04: the design settings – editor, saving and loading, switching at runtime, several cards ----
const implN = (page, i) => page.locator('freshairiq-house-card-impl').nth(i);
const designOf = loc => loc.evaluate(el => ({ design: el.getAttribute('data-design'), scheme: el.getAttribute('data-scheme'),
  vars: Object.fromEntries([...el.style].filter(k => k.startsWith('--fq-')).map(k => [k, el.style.getPropertyValue(k)])) }));

test('UI04: "Design & colours" in the card editor – choose, own colours, readability notes, back to the default; the saved config gives the same look after a reload', async ({ page }) => {
  await mount(page);
  const run = (fn, arg) => page.evaluate(fn, arg);
  await run(async () => {
    const ed = document.createElement('freshairiq-house-card-editor'); ed.id = 'ed'; document.body.appendChild(ed);
    ed.setConfig({ auto_focus: 'hint' }); ed.hass = { language: 'de', locale: { language: 'de' } };
    await customElements.whenDefined('freshairiq-house-card-editor-impl'); await new Promise(r => setTimeout(r, 50));
    window.__seen = []; ed.addEventListener('config-changed', e => window.__seen.push(e.detail.config));
  });
  const inner = () => "document.getElementById('ed').querySelector('freshairiq-house-card-editor-impl') || document.getElementById('ed')";
  const change = (sel, value) => run(([root, sel, value]) => { const r = eval(root); const el = r.querySelector(sel); if (el.type === 'checkbox') el.checked = value; else el.value = value; el.dispatchEvent(new Event('change')); }, [inner(), sel, value]);
  const text = () => run(root => eval(root).textContent, inner());
  expect(await text()).toContain('Design & colours');                                   // (the editor follows the browser language here)
  expect(await run(root => eval(root).querySelector('[data-k="design"]').value, inner())).toBe('freshairiq');
  expect(await run(root => !!eval(root).querySelector('[data-k="design_accent"]'), inner())).toBe(false);      // own colours only for "custom"
  await change('[data-k="design"]', 'custom');
  expect((await run(() => window.__seen.at(-1))).design).toBe('custom');
  await change('[data-k="design_dialog"]', '#f0f0f0');
  await change('[data-k="design_text"]', 'light');                                          // white text on a light window
  expect(await run(root => [...eval(root).querySelectorAll('[data-design-issue]')].map(e => e.dataset.designIssue), inner())).toContain('text_contrast');
  await change('[data-k="design_text"]', 'auto');
  await change('[data-k="design_accent"]', '#7a3cff');
  await change('[data-k="design_radius"]', '6');
  await change('[data-design-glass]', true);
  const saved = await run(() => window.__seen.at(-1));
  expect(saved).toEqual({ auto_focus: 'hint', design: 'custom', design_dialog: '#f0f0f0', design_accent: '#7a3cff', design_radius: 6, design_background: 'transparent' });
  expect(await run(root => eval(root).querySelectorAll('[data-design-issue]').length, inner())).toBe(0);
  // what Lovelace stored is loaded again after a restart: the same design on a fresh card
  await impl(page).evaluate((el, c) => el.setConfig(c), saved);
  const d = await designOf(impl(page));
  expect([d.design, d.scheme, d.vars['--fq-radius'], d.vars['--fq-card-bg'], d.vars['--fq-accent-d']]).toEqual(['custom', 'light', '6px', 'transparent', 'rgb(122,60,255)']);
  // back to the FreshAirIQ design: the option disappears from the config, nothing of the design stays on the card
  await change('[data-k="design"]', 'freshairiq');
  const back = await run(() => window.__seen.at(-1));
  expect(back.design).toBeUndefined();
  await impl(page).evaluate((el, c) => el.setConfig(c), back);
  expect(await designOf(impl(page))).toEqual({ design: null, scheme: null, vars: {} });
});

test('UI04: two house maps with different designs stay independent; a design switched at runtime and a theme switched in Home Assistant change only their own card', async ({ page }) => {
  await mount(page, { config: { design: 'ha' } });
  await setTheme(page, HA_THEMES.light);
  await page.evaluate(() => { const c = document.createElement('freshairiq-house-card'); c.id = 'card2'; c.setConfig({ design: 'custom', design_dialog: '#20232a', design_accent: '#ffd400' }); document.getElementById('m').appendChild(c); c.hass = document.getElementById('card').hass; });
  await page.waitForFunction(() => document.querySelectorAll('freshairiq-house-card-impl').length === 2);
  await settle(page, 150);
  await implN(page, 0).evaluate(el => el._applyDesign());
  const first = await designOf(implN(page, 0)), second = await designOf(implN(page, 1));
  expect([first.design, first.scheme, second.design, second.scheme]).toEqual(['ha', 'light', 'custom', 'dark']);
  // Home Assistant switches to its dark theme: the HA card follows (new hass.themes), the custom card does not change
  await setTheme(page, HA_THEMES.dark);
  await page.evaluate(() => { const c = document.getElementById('card'); c.hass = { ...c.hass, themes: { darkMode: true } }; });
  await settle(page, 150);
  expect((await designOf(implN(page, 0))).scheme).toBe('dark');
  expect(await designOf(implN(page, 1))).toEqual(second);
  // the first card goes back to the FreshAirIQ design at runtime; the second keeps its own
  await implN(page, 0).evaluate(el => el.setConfig({}));
  expect(await designOf(implN(page, 0))).toEqual({ design: null, scheme: null, vars: {} });
  expect(await designOf(implN(page, 1))).toEqual(second);
  // nothing global: the page and Home Assistant's own variables carry no FreshAirIQ design value
  expect(await page.evaluate(() => [...document.documentElement.style].filter(k => k.startsWith('--fq-')).length)).toBe(0);
});

// ---- UI05: phones, tablets, desktops and narrow columns – every window fits, scrolls and can be closed ----
const VIEWPORTS = [['iPhone portrait', 390, 844], ['iPhone landscape', 844, 390], ['small tablet', 768, 1024], ['desktop', 1280, 800], ['narrow column', 1280, 800, 300]];
const LONG = 'Badezimmer mit Dachschräge und Gästebereich im Nordflügel';
for (const [name, w, h, column] of VIEWPORTS) {
  test(`UI05: ${name} (${w}×${h}${column ? `, card ${column} px` : ''}) – every window inside the screen, nothing cut off sideways, close always reachable, long names wrap`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await mount(page);
    if (column) await page.evaluate(c => { document.getElementById('m').style.width = `${c}px`; }, column);
    // long room names and entity ids (German; the English texts are checked in the next test)
    await page.evaluate(long => { const r = window.__ROOMS; window.__ROOMS = { ...r, bad: { ...r.bad, name: long, contact_entities: ['binary_sensor.badezimmer_dachschraege_fenster_nordfluegel_links_oben'] } }; }, LONG);
    const problems = [];
    for (const d of DIALOGS) {
      await openDialog(page, d);
      const r = await scanWindow(page, selectorOf(d));
      if (r.box.left < -1 || r.box.top < -1 || r.box.right > r.vw + 1 || r.box.bottom > r.vh + 1) problems.push(`${d[0]}: window outside ${JSON.stringify(r.box)}`);
      if (!r.close || r.close.top < -1 || r.close.bottom > r.vh + 1 || r.close.left < -1 || r.close.right > r.vw + 1) problems.push(`${d[0]}: close button not reachable ${JSON.stringify(r.close)}`);
      else if (r.close.h < 40 || r.close.w < 44) problems.push(`${d[0]}: close button too small ${r.close.w}×${r.close.h}`);
      if (r.hscroll.length) problems.push(`${d[0]}: sideways scrolling in ${r.hscroll.join(',')}`);
      const overflow = await impl(page).evaluate((el, s) => { const root = el.shadowRoot.querySelector(s), body = root.querySelector('.body');
        return { page: document.scrollingElement.scrollWidth > innerWidth + 1, body: body ? body.scrollWidth > body.clientWidth + 1 : false, scrolls: body ? body.scrollHeight > body.clientHeight + 1 && ['auto', 'scroll'].includes(getComputedStyle(body).overflowY) || body.scrollHeight <= body.clientHeight + 1 : true }; }, selectorOf(d));
      if (overflow.page) problems.push(`${d[0]}: the page scrolls sideways`);
      if (overflow.body) problems.push(`${d[0]}: content wider than the window`);
      if (!overflow.scrolls) problems.push(`${d[0]}: long content cannot scroll`);
      await closeAll(page);
    }
    expect(problems).toEqual([]);
  });
}

// ---- UI06/UI07: the moisture window explains itself – before and while airing, 0 ml right after opening; DE and EN ----
test('UI06/UI07: removable moisture – short explanation before and while airing, why the rooms differ, why 0 ml can show, the full text folded; German and English names as the sensors', async ({ page }) => {
  await mount(page);
  const read = () => impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg[open] .dlg');
    return { title: d.querySelector('h3').textContent, intro: (d.querySelector('[data-moist-intro]') || {}).textContent || '', zero: !!d.querySelector('[data-moist-zero]'),
      more: d.querySelector('details.more') ? [d.querySelector('details.more summary').textContent, d.querySelector('details.more').open, d.querySelector('details.more').textContent] : null,
      tiles: [...d.querySelectorAll('.tile .l')].map(x => x.textContent), heading: (d.querySelector('h4') || {}).textContent || '' }; });
  await openDialog(page, DIALOGS[0]);
  let r = await read();
  expect(r.title).toBe('Entfernbare Feuchtigkeit');                                   // the sensor's name (before: "Entfernbare Feuchte")
  expect(r.intro).toContain('Hier siehst du, wie viel Feuchtigkeit FreshAirIQ voraussichtlich in der empfohlenen Lüftungszeit aus den berechneten Räumen entfernen kann.');
  expect(r.intro).toContain('alle berechneten Räume mit gültigen Messwerten');
  expect(r.tiles).toEqual(['Jetzt entfernbar', 'Empfohlene Lüftungszeit', 'Prognosesicherheit']);
  expect(r.more[0]).toBe('Mehr zur Berechnung'); expect(r.more[1]).toBe(false);          // folded, nothing lost
  expect(r.more[2]).toContain('Sensor „Entfernbare Feuchtigkeit“'); expect(r.more[2]).toContain('nicht für ein vollständiges Austrocknen');
  // right after the airing started: nothing measured yet – the reason is shown at once
  await page.evaluate(() => { const r = window.__ROOMS; window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...r, bad: { ...r.bad, active: true, result_ml: 0, session_target_min: 12, session_elapsed_min: 0 } }, status: 'ventilate', potential_total_ml: 1500, live_balance_ml: 0, recommended_duration_min: 12, remaining_duration_min: 12 }); });
  await settle(page, 300);
  r = await read();
  expect(r.intro).toContain('Hier siehst du die bisher geschätzte Feuchteabgabe der aktuell lüftenden Räume. Der Wert wird anhand neuer Messungen aktualisiert.');
  expect(r.intro).toContain('nur die Räume, die gerade gelüftet werden');
  expect(r.zero).toBe(true);
  expect(r.tiles).toEqual(['Bisher entfernt', 'Restzeit', 'Prognosesicherheit']);
  expect(r.heading).toBe('Nach Räumen');
  // later in the airing the reason moves into the folded part
  await page.evaluate(() => { const r = window.__ROOMS; window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...r, bad: { ...r.bad, active: true, result_ml: 80, session_target_min: 12, session_elapsed_min: 4 } }, status: 'ventilate', potential_total_ml: 1500, live_balance_ml: 80, recommended_duration_min: 12, remaining_duration_min: 8 }); });
  await settle(page, 300);
  r = await read();
  expect(r.zero).toBe(false); expect(r.more[2]).toContain('0 ml');
  // English: the same structure and the sensor's English name
  await impl(page).evaluate(el => { el._hass = { ...el._hass, language: 'en', locale: { language: 'en' } }; el._roomsLang = null; el._render(); });
  await settle(page, 200);
  r = await read();
  expect(r.title).toBe('Removable moisture');
  expect(r.intro).toContain('This shows the estimated moisture given off so far by the rooms being aired right now.');
  expect(r.tiles).toEqual(['Removed so far', 'Time left', 'Forecast confidence']);
  expect(r.more[0]).toBe('More about the calculation');
});

// ---- UI08: the window shows the values FreshAirIQ delivers – no own calculation ----
test('UI08: removable moisture – the values of the payload: removable, added, removed so far, over target, missing confidence, rounding', async ({ page }) => {
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  const tiles = () => impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('dialog.roomdlg[open] .tile')].map(t => `${t.querySelector('.l').textContent}=${t.querySelector('.v').textContent.trim()}`));
  const show = async payload => { await page.evaluate(p => window.__subs['freshairiq/dashboard/subscribe'](p), payload); await settle(page, 250);
    await impl(page).evaluate(el => { el._nav = []; el._selected = { type: 'moisture' }; el._render(); }); await settle(page, 150); return tiles(); };
  const rooms = await page.evaluate(() => window.__ROOMS);
  expect(await show({ rooms, status: 'ventilate', potential_total_ml: 1947.4, recommended_duration_min: 12, prognosis_confidence: 70.4 })).toEqual(['Jetzt entfernbar=≈ 1947 ml', 'Empfohlene Lüftungszeit=12 Min.', 'Prognosesicherheit=70 %']);
  expect(await show({ rooms, status: 'ok', potential_total_ml: -230, recommended_duration_min: 9 })).toEqual(['Jetzt entfernbar=+230 ml', 'Empfohlene Lüftungszeit=9 Min.', 'Prognosesicherheit=–']);
  const on = { ...rooms, bad: { ...rooms.bad, active: true, result_ml: 121.6 } };
  expect(await show({ rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: 321.6, recommended_duration_min: 12, remaining_duration_min: 4.2 })).toEqual(['Bisher entfernt=≈ 322 ml', 'Restzeit=5 Min.', 'Prognosesicherheit=–']);
  expect(await show({ rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: -40, recommended_duration_min: 12, remaining_duration_min: 4 })).toEqual(['Bisher entfernt=+40 ml', 'Restzeit=4 Min.', 'Prognosesicherheit=–']);
  expect(await show({ rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: 50, recommended_duration_min: 12, remaining_duration_min: -3.2 })).toEqual(['Bisher entfernt=≈ 50 ml', 'Über Ziel=+4 Min.', 'Prognosesicherheit=–']);
  // room values as delivered; the house value is their sum (coordinator_house) – a rounding difference is named, never hidden
  const two = { ...rooms, bad: { ...rooms.bad, active: true, result_ml: 50.4 }, wohnen: { ...rooms.wohnen, active: true, result_ml: 30.3 } };
  await show({ rooms: two, status: 'ventilate', potential_total_ml: 900, live_balance_ml: 80.7, recommended_duration_min: 12, remaining_duration_min: 6 });
  const list = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('dialog.roomdlg[open] .rrow')].map(r => r.textContent.replace(/\s+/g, ' ').trim()).concat(el.shadowRoot.querySelector('dialog.roomdlg[open] .legend').textContent));
  expect(list.length).toBe(3);                                                        // only the two rooms being aired
  expect(list[0]).toContain('≈ 50 ml'); expect(list[1]).toContain('≈ 30 ml');
  expect(list[2]).toContain('≈ 81 ml'); expect(list[2]).toContain('1 ml Unterschied');
});

test('UI05/UI08: a running airing updates the open window in place – the values change, the window and its scroll position stay', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 480 });
  await mount(page);
  // sixteen rooms airing: the window is longer than the screen on every tested device (the WebView profile keeps its own
  // screen height), so it has to scroll
  await page.evaluate(() => { const r = window.__ROOMS, on = (x, ml) => ({ ...x, active: true, result_ml: ml, session_target_min: 12, session_elapsed_min: 5 });
    const more = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`raum${i}`, on({ ...r.flur, key: `raum${i}`, name: `Raum ${i + 1}` }, 10 + i)]));
    window.__ROOMS = { bad: on(r.bad, 120), flur: on(r.flur, 60), wohnen: on(r.wohnen, 90), schlaf: on(r.schlaf, 40), ...more }; });
  await openDialog(page, DIALOGS[1]);
  expect(await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('dialog.roomdlg[open] .body'); return b.scrollHeight > b.clientHeight + 120; })).toBe(true);
  const body = sel => impl(page).evaluate((el, s) => { const b = el.shadowRoot.querySelector('dialog.roomdlg[open] .body'); return s === 'top' ? b.scrollTop : b.textContent; }, sel);
  await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('dialog.roomdlg[open] .body'); b.scrollTop = 120; });
  const before = await body('top');
  expect(before).toBeGreaterThan(0);
  await page.evaluate(() => { const r = window.__ROOMS; window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...r, bad: { ...r.bad, result_ml: 180, session_elapsed_min: 7 } }, status: 'ventilate', potential_total_ml: 1500, live_balance_ml: 556, recommended_duration_min: 12, remaining_duration_min: 5 }); });   // the sum of the rooms, as the coordinator publishes it
  await settle(page, 1200);
  expect(await body('text')).toContain('556 ml'); expect(await body('text')).toContain('180 ml');
  expect(await body('top')).toBe(before);
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg[open]'))).toBe(true);
});
