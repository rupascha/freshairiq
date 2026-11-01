// Optional house map card (custom:freshairiq-house-card): canonical room states on a free
// floor plan, wind, honest opening states, air-path hypothesis, floor focus and the editor.
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
const shadowText = page => impl(page).evaluate(el => el.shadowRoot.textContent);
const q = (page, selector) => impl(page).evaluate((el, s) => [...el.shadowRoot.querySelectorAll(s)].map(n => ({ cls: n.getAttribute('class'), label: n.getAttribute('aria-label'), points: n.getAttribute('points') })), selector);

test('rooms show the canonical action as word, icon and tone; free shapes are drawn', async ({ page }) => {
  const errors = await mount(page);
  const rooms = await q(page, 'polygon.room');
  expect(rooms.length).toBe(3);  // ground floor: bath, hall, L-shaped living room
  const bad = rooms.find(r => r.label.startsWith('Bad'));
  expect(bad.cls).toContain('t-close');
  expect(bad.label).toContain('Schließen');
  expect(rooms.find(r => r.label.startsWith('Wohnen')).points.split(' ').length).toBe(6);  // L shape kept
  expect(await shadowText(page)).toContain('Wind aus');
  expect(await shadowText(page)).toContain('Wind aus 307°');
  expect(await shadowText(page)).toContain('NW · 18 km/h');
  expect(errors).toEqual([]);
});

test('a mould warning never shows green; a critical one wins over the action colour, the action word stays', async ({ page }) => {
  await mount(page);
  // audit (10) P0: only the published mould_level is available per room (no limit fields)
  await page.evaluate(() => {
    window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS,
      flur: { ...window.__ROOMS.flur, surface_rh: 82, mould_level: 'High' },
      schlaf: { ...window.__ROOMS.schlaf, surface_rh: 72, mould_level: 'Elevated' },
      wohnen: { ...window.__ROOMS.wohnen, action: 'Okay', house_aligned_action: 'okay', surface_rh: 95, mould_level: 'Very high' } } });
  });
  await page.waitForTimeout(80);
  const rooms = await q(page, 'polygon.room');
  expect(rooms.find(r => r.label.startsWith('Flur')).cls).not.toContain('t-ok');
  const wohnen = rooms.find(r => r.label.startsWith('Wohnen'));
  expect(wohnen.cls).toContain('t-critical');
  expect(wohnen.label).toContain('In Ordnung');  // the canonical action is not overridden
  await impl(page).evaluate(el => { const p = [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_wohnen'); p.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  await page.waitForTimeout(50);
  expect(await shadowText(page)).toContain('Schimmelrisiko-Hinweis');
});

test('binary open is "kind unknown", a delayed contact is "confirmation running", tilt differs from open', async ({ page }) => {
  await mount(page);
  const ops = await q(page, 'line.op');
  const bad = ops.find(o => o.label.includes('Bestätigung läuft'));
  expect(bad.cls).toContain('open_unspecified');
  expect(bad.cls).toContain('pending');
  expect(ops.find(o => o.cls.includes('tilted'))).toBeTruthy();
  expect(ops.some(o => o.cls.split(' ').includes('open') && o.label.includes('ganz offen') && o.cls.includes('closed'))).toBe(false);
});

test('air paths are a marked estimate and stop animating with reduced motion', async ({ page }) => {
  await mount(page, { config: { layer: 'airflow' }, reducedMotion: 'reduce' });
  expect(await shadowText(page)).toContain('Schätzung');
  const paths = await q(page, 'polyline.path');
  expect(paths.length).toBe(1);
  const animation = await impl(page).evaluate(el => getComputedStyle(el.shadowRoot.querySelector('polyline.path')).animationName);
  expect(animation).toBe('none');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('polyline.path').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(50);
  const detail = await shadowText(page);
  expect(detail).toContain('Querlüftung (vermutet)');
  expect(detail).toContain('keine gemessene Strömung');
});

test('without wind data there is no wind arrow and no invented direction', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, wind: { ...window.__HOUSE.wind, available: false, reason: 'no_direction', from_deg: null }, airflow: null }));
  await page.waitForTimeout(80);
  expect(await shadowText(page)).toContain('Keine Windrichtung');
  expect((await q(page, 'line.windarrow')).length).toBe(0);
});

test('tapping a room explains it with the canonical reason; names are escaped', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, flur: { ...window.__ROOMS.flur, name: '<img src=x onerror="window.__xss=1">' } } }));
  await page.waitForTimeout(80);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelectorAll('img').length)).toBe(0);
  await impl(page).evaluate(el => { const p = [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad'); p.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); });
  await page.waitForTimeout(50);
  expect(await shadowText(page)).toContain('Bad: Grund');
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
});

test('floor focus: auto switches on a new action elsewhere, a manual choice is respected, hint only hints', async ({ page }) => {
  await mount(page, { config: { auto_focus: 'auto' } });
  await page.evaluate(() => localStorage.clear());
  const closeUpstairs = () => page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, schlaf: { ...window.__ROOMS.schlaf, action: 'Close', house_aligned_action: 'close' } } }));
  await closeUpstairs();
  await page.waitForTimeout(80);
  expect((await q(page, 'polygon.room')).map(r => r.label.split(',')[0])).toEqual(['Schlafzimmer']);
  // the user goes back down: stays there although the upper floor still needs action
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('[data-floor]')].find(b => b.textContent.startsWith('Erdgeschoss')).click());
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS }));
  await closeUpstairs();
  await page.waitForTimeout(80);
  expect((await q(page, 'polygon.room')).length).toBe(3);
  expect(await shadowText(page)).toContain('Auto-Fokus pausiert bis');
});

test('hint mode keeps the floor and offers the other one', async ({ page }) => {
  await mount(page, { config: { auto_focus: 'hint' } });
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, schlaf: { ...window.__ROOMS.schlaf, action: 'Close', house_aligned_action: 'close' } } }));
  await page.waitForTimeout(80);
  expect((await q(page, 'polygon.room')).length).toBe(3);
  expect(await shadowText(page)).toContain('Handlung auf anderer Etage');
});

test('first run without a stored plan shows the proposal as such', async ({ page }) => {
  await mount(page, { stored: false });
  expect(await shadowText(page)).toContain('Automatischer Vorschlag – noch nicht gespeichert');
  expect(await page.evaluate(() => window.__calls.map(c => c.type))).toContain('freshairiq/house_map/propose');
});

test('only administrators can open the editor', async ({ page }) => {
  await mount(page, { admin: false });
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('[data-edit]'))).toBe(false);
});

async function openEditor(page, options = {}) {
  await mount(page, options);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-edit]').click());
  await page.waitForFunction(() => document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor'));
  await page.waitForTimeout(80);
  return page.locator('freshairiq-house-layout-editor');
}
const roomPoints = (editor, id) => editor.evaluate((el, id) => el._layout.rooms.find(r => r.id === id).polygon, id);

test('editor: drag a room, undo, insert a corner, blocked save on overlap, save with revision', async ({ page }) => {
  const editor = await openEditor(page);
  const before = await roomPoints(editor, 'r_bad');
  const box = await editor.evaluate(el => { const r = el.shadowRoot.querySelector('polygon[data-id="r_bad"]').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
  await page.mouse.move(box.x, box.y); await page.mouse.down(); await page.mouse.move(box.x - 40, box.y, { steps: 5 }); await page.mouse.up();
  const moved = await roomPoints(editor, 'r_bad');
  expect(moved[0][0]).toBeLessThan(before[0][0]);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="undo"]').click());
  expect(await roomPoints(editor, 'r_bad')).toEqual(before);
  // precision: a corner is inserted in the middle of a wall
  await editor.evaluate(el => { el._sel = { type: 'room', id: 'r_bad' }; el._mode = 'precise'; el._render(); el.shadowRoot.querySelector('circle.mid').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 })); el.shadowRoot.querySelector('svg').dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerId: 1 })); });
  expect((await roomPoints(editor, 'r_bad')).length).toBe(5);
  // overlapping rooms cannot be saved; the problem is named at the room
  await editor.evaluate(el => { el._commit(l => { l.rooms.find(r => r.id === 'r_bad').polygon = [[1, 1], [3, 1], [3, 3], [1, 3]]; }); el.shadowRoot.querySelector('[data-a="save"]').click(); });
  await page.waitForTimeout(50);
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('überlappt einen anderen Raum');
  expect(await page.evaluate(() => window.__calls.filter(c => c.type === 'freshairiq/house_map/save').length)).toBe(0);
  await editor.evaluate(el => { el._undo(); el.shadowRoot.querySelector('[data-a="save"]').click(); });
  await page.waitForTimeout(80);
  const save = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save'));
  expect(save.base_revision).toBe(3);
  expect(save.layout.rooms.find(r => r.id === 'r_bad').polygon.length).toBe(5);
});

test('editor: a concurrent save is reported, not overwritten; hass updates keep the draft', async ({ page }) => {
  const editor = await openEditor(page, { saveError: 'revision_conflict' });
  await editor.evaluate(el => el._commit(l => { l.building.north_deg = 42; }));
  await impl(page).evaluate(el => { el.hass = { ...el.hass }; });  // HA pushes new states while editing
  expect(await editor.evaluate(el => el._layout.building.north_deg)).toBe(42);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const text = await editor.evaluate(el => el.shadowRoot.textContent);
  expect(text).toContain('anderswo gespeichert');
  expect(await editor.evaluate(el => !!el.shadowRoot.querySelector('[data-a="reload"]'))).toBe(true);
});

test('editor helpers: templates, rotation, history and opening bookkeeping', async ({ page }) => {
  await mount(page);
  const result = await page.evaluate(async () => {
    const m = await import('/freshairiq-house-editor.js?v=0.26.5.4');
    const G = await import('/freshairiq-house-geometry.js?v=0.26.5.4');
    const h = new m.History(2);
    h.push({ a: 1 }); h.push({ a: 2 }); h.push({ a: 3 });
    const undone = h.undo({ a: 4 });
    return {
      l: G.validatePolygon({ id: 'x', polygon: m.TEMPLATES.l(4, 4) }).length, u: G.validatePolygon({ id: 'y', polygon: m.TEMPLATES.u(6, 5) }).length,
      rot: m.rotate90([[0, 0], [2, 0], [2, 1], [0, 1]]), undone, past: h.past.length, redo: h.redo({ a: 3 }),
      shifted: m.shiftOpenings([{ room_id: 'r', edge: 2 }, { room_id: 'r', edge: 0 }, { room_id: 'q', edge: 3 }], 'r', 1, 1).map(o => o.edge),
      changed: m.changedRooms({ rooms: [{ room_key: 'a', polygon: [[0, 0]] }] }, { rooms: [{ room_key: 'a', polygon: [[1, 0]] }, { room_key: 'b', polygon: [] }] }),
    };
  });
  expect(result.l).toBe(0); expect(result.u).toBe(0);
  expect(result.rot).toEqual([[1.5, -0.5], [1.5, 1.5], [0.5, 1.5], [0.5, -0.5]]);
  expect(result.undone).toEqual({ a: 3 }); expect(result.past).toBe(1); expect(result.redo).toEqual({ a: 4 });
  expect(result.shifted).toEqual([3, 0, 3]); expect(result.changed).toBe(1);
});

test('geometry and wind helpers agree with the server rules', async ({ page }) => {
  await mount(page);
  const r = await page.evaluate(async () => {
    const G = await import('/freshairiq-house-geometry.js?v=0.26.5.4');
    const sq = [[0, 0], [4, 0], [4, 4], [0, 4]];
    return {
      bearings: [0, 1, 2, 3].map(i => Math.round(G.edgeBearing(sq, i, 0))), rotated: Math.round(G.edgeBearing(sq, 2, 307.5) * 10) / 10,
      cross: G.validatePolygon({ id: 'c', polygon: [[0, 0], [4, 4], [4, 0], [0, 4]] })[0].code,
      overlap: G.validateLayout({ floors: [{ id: 'f' }], rooms: [{ id: 'a', floor_id: 'f', polygon: sq }, { id: 'b', floor_id: 'f', polygon: [[1, 1], [3, 1], [3, 3], [1, 3]] }], openings: [] })[0].code,
      parse: ['NW', 'nno', '307.5', 'unknown', null, 361].map(G.parseBearing), speed: [G.speedMs(18, 'km/h'), G.speedMs(10, 'Bft'), G.speedMs(36, null)],
      label: [G.compass(307, 'de'), G.compass(100, 'de'), G.compass(100, 'en')], smooth: Math.round(G.smoothBearing(350, 10, 0.5)),
      ccw: G.ccw([[0, 0], [0, 4], [4, 4], [4, 0]])[0], inside: G.pointInPolygon([3, 4], [[0, 0], [6, 0], [6, 5], [4, 5], [4, 2], [2, 2], [2, 5], [0, 5]]),
    };
  });
  expect(r.bearings).toEqual([180, 90, 0, 270]);
  expect(r.rotated).toBe(307.5);
  expect(r.cross).toBe('E_POLY_SELF_INTERSECT');
  expect(r.overlap).toBe('E_ROOM_OVERLAP');
  expect(r.parse).toEqual([315, 22.5, 307.5, null, null, null]);
  expect(r.speed[0]).toBeCloseTo(5); expect(r.speed[1]).toBe(null); expect(r.speed[2]).toBeCloseTo(10);
  expect(r.label).toEqual(['NW', 'O', 'E']); expect(r.smooth).toBe(0);
  expect(r.ccw).toEqual([4, 0]); expect(r.inside).toBe('outside');
});

test('the Lovelace editor emits config-changed; the classic card is untouched by the house map', async ({ page }) => {
  await mount(page);
  const out = await page.evaluate(async () => {
    const ed = document.createElement('freshairiq-house-card-editor');
    document.body.appendChild(ed);
    ed.setConfig({ auto_focus: 'hint' });
    ed.hass = { language: 'de' };
    await customElements.whenDefined('freshairiq-house-card-editor-impl');
    await new Promise(r => setTimeout(r, 50));
    const inner = ed.querySelector('freshairiq-house-card-editor-impl') || ed;
    let seen = null;
    ed.addEventListener('config-changed', e => { seen = e.detail.config; });
    const select = inner.querySelector('[data-k="auto_focus"]');
    select.value = 'auto'; select.dispatchEvent(new Event('change'));
    return { seen, classic: !!customElements.get('freshairiq-card'), cards: window.customCards.map(c => c.type) };
  });
  expect(out.seen).toEqual({ auto_focus: 'auto' });
  expect(out.classic).toBe(true);
  expect(out.cards).toEqual(['freshairiq-card', 'freshairiq-house-card']);
});

test('the all-floors overview shows every floor; removing the card ends both subscriptions', async ({ page }) => {
  await mount(page);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-floor="__all"]').click());
  await page.waitForTimeout(50);
  expect((await q(page, 'polygon.room')).length).toBe(4);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelectorAll('svg[role="group"]').length)).toBe(2);
  await page.evaluate(() => document.getElementById('card').remove());
  expect(await page.evaluate(() => window.__unsubscribed)).toBe(2);
});

test('a 40-room house with 160 openings renders within budget', async ({ page }) => {
  await mount(page);
  const ms = await page.evaluate(async () => {
    const rooms = [], openings = [], live = {};
    for (let i = 0; i < 40; i++) {
      const x = (i % 8) * 4, y = Math.floor(i / 8) * 4, id = `r${i}`;
      rooms.push({ id, room_key: `k${i}`, floor_id: 'f_eg', polygon: [[x, y], [x + 4, y], [x + 4, y + 4], [x, y + 4]], provenance: 'user' });
      for (let e = 0; e < 4; e++) openings.push({ id: `o${i}_${e}`, room_id: id, edge: e, offset: 0.5, width_m: null, kind: 'window', mechanics: 'unknown', contacts: [] });
      live[`k${i}`] = { key: `k${i}`, name: `Raum ${i}`, action: i % 3 ? 'Okay' : 'Ventilate', data_quality: 'ok', temperature: 21, humidity: 55 };
    }
    const el = document.querySelector('freshairiq-house-card-impl');
    el._layoutInfo = { revision: 9, layout: { ...window.__LAYOUT, rooms, openings, connections: [] } };
    el._rooms = live;
    const started = performance.now();
    for (let n = 0; n < 5; n++) el._render();
    return (performance.now() - started) / 5;
  });
  expect(await q(page, 'polygon.room').then(r => r.length)).toBe(40);
  expect(ms).toBeLessThan(250);  // per full render on a desktop-class runner
});

// Redesign (owner feedback 28.10.): wind streams instead of an arrow, a hero with the house data, a room dialog.
const streamsOf = page => impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('path.stream')].map(p => ({
  kind: p.getAttribute('class').split(' ')[1], d: p.getAttribute('d') })));

test('wind streams: bounce off closed walls, enter through a confirmed open window, none without wind', async ({ page }) => {
  await mount(page);
  // o_bad (north wall of the bath) is open but its delay still runs: no air "comes in" yet
  let streams = await streamsOf(page);
  expect(streams.length).toBeGreaterThan(4);
  expect(streams.some(s => s.kind === 'deflect')).toBe(true);
  expect(streams.some(s => s.kind === 'inflow')).toBe(false);
  // the delay is over: the north wind now enters through the bath window
  await page.evaluate(() => {
    const h = JSON.parse(JSON.stringify(window.__HOUSE));
    h.wind = { ...h.wind, from_deg: 0, label_de: 'N' }; h.airflow.openings.o_bad.pending = false; h.revision = 3;
    window.__subs['freshairiq/house_map/subscribe'](h);
    const el = document.querySelector('freshairiq-house-card-impl'); el._windSmooth = 0; el._render();
  });
  streams = await streamsOf(page);
  expect(streams.filter(s => s.kind === 'inflow').length).toBeGreaterThan(0);
  // every stream starts inside the drawing
  const inside = await impl(page).evaluate(el => {
    const svg = el.shadowRoot.querySelector('svg.plan');
    const [x, y, w, h] = svg.getAttribute('viewBox').split(' ').map(Number);
    return [...svg.querySelectorAll('path.stream')].every(p => { const [sx, sy] = p.getAttribute('d').split(' ')[1].split(',').map(Number); return sx >= x && sx <= x + w && sy >= y && sy <= y + h; });
  });
  expect(inside).toBe(true);
  await page.evaluate(() => window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, revision: 3, wind: { ...window.__HOUSE.wind, available: false, reason: 'calm', calm: true } }));
  await page.waitForTimeout(80);
  expect((await streamsOf(page)).length).toBe(0);
});

test('stronger wind makes the streams faster', async ({ page }) => {
  await mount(page);
  const seconds = async speed => {
    await page.evaluate(v => window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, revision: 3, wind: { ...window.__HOUSE.wind, speed_ms: v } }), speed);
    await page.waitForTimeout(80);
    return impl(page).evaluate(el => parseFloat(el.shadowRoot.querySelector('svg.plan').style.getPropertyValue('--dur')));
  };
  const calmish = await seconds(1), strong = await seconds(12);
  expect(strong).toBeLessThan(calmish);
  const V = await page.evaluate(async () => { const m = await import('/freshairiq-house-view.js?v=0.26.5.4'); return [m.streamSeconds(0), m.streamSeconds(5), m.streamSeconds(30)]; });
  expect(V[0]).toBeGreaterThan(V[1]); expect(V[1]).toBeGreaterThan(V[2]); expect(V[2]).toBeGreaterThanOrEqual(0.45);
});

test('the hero shows the house data: recommendation, forecast for the set horizon, night, outdoors', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de', status_text: 'Alles gut',
    forecast_horizon_min: 15, forecast_moisture_effect_ml: 180, forecast_temperature_change_c: -0.6, overnight_forecast_ml: 240,
    weather_now: { outdoor_temperature: 11.4, condition: 'cloudy' }, intelligent_recommendation: { kind: 'ventilate', title: 'Jetzt lüften', instruction: 'Bad und Flur' } }));
  await page.waitForTimeout(80);
  const text = await shadowText(page);
  for (const part of ['Jetzt lüften', 'Bad und Flur', 'Prognose 15 min', '−180 ml', '-0.6 °C', '+240 ml', '11.4 °C', 'bewölkt', 'Alles gut']) expect(text).toContain(part);
});

test('a tap on a room opens the detail window; closing it returns to the map', async ({ page }) => {
  await mount(page);
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(80);
  const open = await impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg'); return d && d.open && d.textContent; });
  expect(open).toContain('Bad: Grund');
  expect(open).toContain('Fenster & Türen');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-close-detail]').click());
  await page.waitForTimeout(50);
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg'))).toBe(false);
});

test('room labels stay readable: at least 12 px on screen, also on a phone', async ({ page }) => {
  await mount(page);
  for (const width of [760, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.waitForTimeout(150);
    await impl(page).evaluate(el => el._render());
    const smallest = await impl(page).evaluate(el => {
      const svg = el.shadowRoot.querySelector('svg.plan'), scale = svg.getBoundingClientRect().width / Number(svg.getAttribute('viewBox').split(' ')[2]);
      return Math.min(...[...svg.querySelectorAll('.tag text')].map(t => Number(t.getAttribute('font-size')) * scale));
    });
    expect(smallest, `width ${width}`).toBeGreaterThanOrEqual(12);
  }
});

test('the room window shows the exhaust fan with its follow-up countdown or the latest stop', async ({ page }) => {
  await mount(page);
  const r = await page.evaluate(async () => {
    const m = await import('/freshairiq-house-card.js?v=0.26.5.4');
    const t = k => ({ fan_left: 'Nachlauf noch {m} min', fan_limit: 'spätestens aus {t}' })[k];
    const now = Date.parse('2026-10-28T12:00:00Z');
    return [
      m.fanCountdown({ follow_up_until: '2026-10-28T12:03:10Z' }, now, t, 'de'),
      m.fanCountdown({ follow_up_until: '2026-10-28T11:59:00Z', runtime_limit_at: '2026-10-28T12:30:00Z' }, now, t, 'de').startsWith('spätestens aus'),
      m.fanCountdown({ follow_up_until: null, runtime_limit_at: '2026-10-28T11:00:00Z' }, now, t, 'de'),
      m.fanCountdown(null, now, t, 'de'),
    ];
  });
  expect(r).toEqual(['Nachlauf noch 4 min', true, '', '']);
});

// Community hotfix: on a phone the plan fits the card (no sideways overflow), stays centred, and a live
// update keeps where the user scrolled in the room window.
test('the plan fits a phone without sideways scrolling and live updates keep the scroll position', async ({ page }) => {
  await mount(page);
  // like Home Assistant's page (mobile browsers lay out at 980 px without it)
  await page.evaluate(() => { const m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width,initial-scale=1'; document.head.appendChild(m); });
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(120);
    await impl(page).evaluate(el => el._render());
    const box = await impl(page).evaluate(el => {
      const map = el.shadowRoot.querySelector('.map'), svg = map.querySelector('svg.plan');
      const m = map.getBoundingClientRect(), s = svg.getBoundingClientRect();
      return { overflow: map.scrollWidth - map.clientWidth, left: s.left - m.left, right: m.right - s.right, svg: s.width, map: m.width };
    });
    expect(box.overflow, `width ${width}`).toBeLessThanOrEqual(1);
    expect(box.svg, `width ${width}`).toBeLessThanOrEqual(box.map + 1);
    expect(Math.abs(box.left - box.right), `centred at ${width}`).toBeLessThanOrEqual(8);
  }
  await page.setViewportSize({ width: 390, height: 260 });  // the room window scrolls
  await impl(page).evaluate(el => { const p = [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_wohnen'); p.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  await page.waitForTimeout(80);
  const before = await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('.dlg .body'); b.scrollTop = 60; return b.scrollTop; });
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de' }));
  await page.waitForTimeout(120);
  const after = await impl(page).evaluate(el => el.shadowRoot.querySelector('.dlg .body').scrollTop);
  expect(before).toBeGreaterThan(0);
  expect(after).toBe(before);
});

// ---- owner request 31.10.: soft wind waves without any cut; interior doors/passages; opening widths ----
const waveState = page => impl(page).evaluate(el => ({
  phase: el._windPhase || 0,
  waves: el.shadowRoot.querySelectorAll('path.wave').length,
  streams: el.shadowRoot.querySelectorAll('path.stream').length,
  cssAnimations: [...el.shadowRoot.querySelectorAll('path.wave')].reduce((n, p) => n + p.getAnimations().length, 0),
  d: (el.shadowRoot.querySelector('path.wave') || { getAttribute: () => '' }).getAttribute('d'),
}));

test('wind: soft wave strands per stream, driven by the card clock (no CSS animation that could restart)', async ({ page }) => {
  await mount(page);
  const a = await waveState(page);
  expect(a.streams).toBeGreaterThan(4);
  expect(a.waves).toBe(a.streams * 3);
  expect(a.cssAnimations).toBe(0);
  await page.waitForTimeout(400);
  const b = await waveState(page);
  expect(b.d).not.toBe(a.d);  // the waves move
});

test('wind: new data and a full redraw continue the waves where they were', async ({ page }) => {
  await mount(page);
  await page.waitForTimeout(500);
  const result = await impl(page).evaluate(el => {
    const before = el._windPhase, node = el.shadowRoot.querySelector('path.wave');
    const h = JSON.parse(JSON.stringify(window.__HOUSE)); h.revision = 4; h.wind = { ...h.wind, speed_ms: 6 };
    window.__subs['freshairiq/house_map/subscribe'](h);
    el._render();  // a full redraw right away
    const after = el._windPhase, fresh = el.shadowRoot.querySelector('path.wave');
    return { before, after, replaced: fresh !== node, first: fresh.getAttribute('d') };
  });
  expect(result.replaced).toBe(true);           // the element is new …
  expect(result.before).toBeGreaterThan(0);
  expect(result.after).toBeCloseTo(result.before, 6);  // … and starts at the phase the old one had
  await page.waitForTimeout(300);
  expect((await waveState(page)).phase).not.toBeCloseTo(result.after, 3);  // and keeps moving
});

test('wind: the wave is periodic in its phase (no seam) and calm at both ends of a stream', async ({ page }) => {
  await mount(page);
  const out = await page.evaluate(async () => {
    const V = await import('/freshairiq-house-view.js?v=wave');
    const frame = V.waveFrame([[0, 0], [10, 0], [10, 6]], 0.25);
    const geo = { amp: 0.3, wavelength: 2, shift: 1 };
    const nums = d => d.split(/[ML ,]+/).filter(Boolean).map(Number);
    const p0 = nums(V.wavePath(frame, geo, 0)), p1 = nums(V.wavePath(frame, geo, 1)), half = nums(V.wavePath(frame, geo, 0.5));
    return { seam: Math.max(...p0.map((v, i) => Math.abs(v - p1[i]))), moves: Math.max(...p0.map((v, i) => Math.abs(v - half[i]))),
      start: p0.slice(0, 2), end: p0.slice(-2) };
  });
  expect(out.seam).toBeLessThan(0.002);
  expect(out.moves).toBeGreaterThan(0.1);
  // the strand starts and ends on its stream (the offset fades to zero)
  expect(Math.abs(out.start[0]) + Math.abs(out.start[1])).toBeLessThan(1e-9);
  expect(Math.abs(out.end[0] - 10) + Math.abs(out.end[1] + 6)).toBeLessThan(1e-9);
});

test('wind: reduced motion and a switched-off animation keep the waves still', async ({ page }) => {
  await mount(page, { reducedMotion: 'reduce' });
  const a = await waveState(page);
  await page.waitForTimeout(300);
  const b = await waveState(page);
  expect(a.waves).toBeGreaterThan(0);
  expect(b.d).toBe(a.d);
  expect(b.phase).toBe(0);
});

test('editor: interior door and passage on a shared wall; an outside wall is refused', async ({ page }) => {
  const editor = await openEditor(page);
  const out = await editor.evaluate(async el => {
    const count = () => el._layout.openings.length;
    const n0 = count();
    el._setTool('door'); await el._toolTap([2.6, 4.02]);  // wall between bath and hall
    const door = el._layout.openings[el._layout.openings.length - 1];
    el._setTool('passage'); await el._toolTap([6, 4.05]);  // wall between hall and living room
    const passage = el._layout.openings[el._layout.openings.length - 1];
    el._setTool('door'); await el._toolTap([0.02, 6]);  // outside wall of the bath
    return { added: count() - n0, door: { kind: door.kind, width: door.width_m, room: door.room_id, mech: door.mechanics },
      passage: { kind: passage.kind, width: passage.width_m }, msg: el.shadowRoot.textContent, tools: [...el.shadowRoot.querySelectorAll('[data-tool]')].map(b => b.dataset.tool) };
  });
  expect(out.added).toBe(2);
  expect(out.door).toEqual({ kind: 'door', width: 0.9, room: expect.any(String), mech: 'door' });
  expect(out.passage).toEqual({ kind: 'passage', width: 1 });
  expect(out.msg).toContain('keine Innenwand');
  expect(out.tools).toEqual(expect.arrayContaining(['window', 'door', 'passage']));
});

test('editor: the width of a door or window is set by dragging its ends or with − / +', async ({ page }) => {
  const editor = await openEditor(page);
  await editor.evaluate(el => { el._sel = { type: 'opening', id: 'd_bad' }; el._render(); });
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('circle.wh').length)).toBe(2);
  const width = () => editor.evaluate(el => el._layout.openings.find(o => o.id === 'd_bad').width_m);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-w="1"]').click());
  expect(await width()).toBeCloseTo(0.95, 3);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-w="-1"]').click());
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-w="-1"]').click());
  expect(await width()).toBeCloseTo(0.85, 3);
  // drag the right end outwards along the wall
  const grown = await editor.evaluate(el => {
    const handle = [...el.shadowRoot.querySelectorAll('circle.wh')].sort((a, b) => b.getBoundingClientRect().x - a.getBoundingClientRect().x)[0];
    const r = handle.getBoundingClientRect(), svg = el.shadowRoot.querySelector('svg');
    const x = r.x + r.width / 2, y = r.y + r.height / 2;
    handle.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: x, clientY: y, pointerId: 1 }));
    svg.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: x + 40, clientY: y, pointerId: 1 }));
    svg.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: x + 40, clientY: y, pointerId: 1 }));
    return el._layout.openings.find(o => o.id === 'd_bad').width_m;
  });
  expect(grown).toBeGreaterThan(0.85);
  expect(grown).toBeLessThanOrEqual(4);
  const V = await page.evaluate(async () => {
    const E = await import('/freshairiq-house-editor.js?v=w');
    const poly = [[0, 0], [4, 0], [4, 3], [0, 3]];
    return [E.openingWidthAt(poly, { edge: 0, offset: 0.5 }, [3, 0.2]), E.openingWidthAt(poly, { edge: 0, offset: 0.9 }, [0, 0]),
      E.openingWidthAt(poly, { edge: 0, offset: 0.5 }, [2.05, 0]), E.openingWidthAt(poly, { edge: 0, offset: 0.5 }, [3.04, 0], 0.1)];
  });
  expect(V).toEqual([2, 0.8, 0.3, 2.1]);  // symmetric · stays inside its wall · at least 0.3 m · on the grid
});

// ---- hotfix 31.10.: one interior-wall rule for editor and air paths (F01/F05); wind stops and resumes (F04) ----
const INTERIOR = JSON.parse(fs.readFileSync(new URL('./fixtures/interior_openings.json', import.meta.url), 'utf8'));

test('editor: interior openings follow the same rule as the air paths (shared fixture with pytest)', async ({ page }) => {
  await mount(page);
  const out = await page.evaluate(async FX => {
    const T = await import('/freshairiq-house-trace.js?v=contract');
    return FX.cases.map(c => {
      const layout = { rooms: [{ id: 'a', room_key: 'a', floor_id: 'f', polygon: FX.room_a }, { id: 'b', room_key: 'b', floor_id: 'f', polygon: c.b }] };
      const target = T.openingTarget(layout, layout.rooms[0], { edge: c.opening.edge, offset: c.opening.offset, width_m: c.opening.width_m });
      return [c.name, target ? target.id : null];
    });
  }, INTERIOR);
  expect(out).toEqual(INTERIOR.cases.map(c => [c.name, c.target]));
});

test('editor: a door or passage is only placed where both rooms really share a wall', async ({ page }) => {
  await mount(page);
  const out = await page.evaluate(async () => {
    const T = await import('/freshairiq-house-trace.js?v=place');
    const A = [[0, 0], [2, 0], [2, 2], [0, 2]];
    const at = (b, p, kind = 'passage', maxDist = 0.6) => {
      const o = T.openingAt({ rooms: [{ id: 'a', room_key: 'a', floor_id: 'f', polygon: A }, { id: 'b', room_key: 'b', floor_id: 'f', polygon: b }] }, 'f', p, maxDist, kind);
      return o && !o.error ? { width: o.width_m, offset: o.offset, room: o.room_id } : o;
    };
    const gap = g => [[2 + g, 0], [4 + g, 0], [4 + g, 2], [2 + g, 2]];
    return {
      g0: at(gap(0), [2, 1]), g4: at(gap(0.04), [2, 1]), g12: at(gap(0.12), [2, 1]), g26: at(gap(0.26), [2, 1]),
      corner: at([[2, 2], [4, 2], [4, 4], [2, 4]], [2, 1.99], 'passage', 0.1),
      short: at([[2, 1.4], [4, 1.4], [4, 3], [2, 3]], [2, 1.9], 'door'),     // 0.6 m shared: a narrower door that fits
      tiny: at([[2, 1.8], [4, 1.8], [4, 3], [2, 3]], [2, 1.9], 'door'),      // 0.2 m shared: too short
      window: at(gap(0.26), [2, 1], 'window'),
    };
  });
  expect(out.g0).toEqual({ width: 1, offset: 0.5, room: 'a' });
  expect(out.g4.width).toBe(1);
  for (const key of ['g12', 'g26', 'corner', 'tiny']) expect(out[key], key).toEqual({ error: 'no_interior_wall' });
  expect(out.short).toEqual({ width: 0.6, offset: 0.85, room: 'a' });  // centred on the shared 1.4 … 2.0 m
  expect(out.window.width).toBeNull();  // windows are not bound to an interior wall
});

test('editor: a door widened beyond the shared wall is shown as an outside opening', async ({ page }) => {
  const editor = await openEditor(page);
  const text = await editor.evaluate(el => {
    el._commit(l => { l.openings.push({ id: 'p_x', room_id: 'r_bad', edge: 0, offset: 0.5, width_m: 0.9, kind: 'passage', mechanics: 'unknown', contacts: [], provenance: 'user' }); });
    el._sel = { type: 'opening', id: 'p_x' }; el._render();
    const inside = el.shadowRoot.textContent.includes('zählt als Außenöffnung');
    el._commit(l => { l.rooms.find(r => r.id === 'r_flur').polygon = [[0, -1], [8, -1], [8, 3.8], [0, 3.8]]; });  // hall moved 20 cm away
    el._render();
    return { inside, outside: el.shadowRoot.textContent.includes('zählt als Außenöffnung') };
  });
  expect(text).toEqual({ inside: false, outside: true });
});

test('wind: switching the animation off stops the loop at once, on again continues the same phase', async ({ page }) => {
  await mount(page);
  await page.waitForTimeout(250);
  const off = await impl(page).evaluate(el => { const before = el._windPhase; el.setConfig({ ...el._config, animation: false }); return { before, raf: el._windRaf }; });
  expect(off.raf).toBeNull();
  await page.waitForTimeout(300);
  const still = await impl(page).evaluate(el => ({ phase: el._windPhase, raf: el._windRaf }));
  expect(still.phase).toBe(off.before);  // nothing moved while off
  expect(still.raf).toBeNull();
  await impl(page).evaluate(el => el.setConfig({ ...el._config, animation: true }));
  await page.waitForTimeout(300);
  const on = await impl(page).evaluate(el => ({ phase: el._windPhase, raf: !!el._windRaf }));
  expect(on.raf).toBe(true);
  expect(on.phase).not.toBe(off.before);  // continues from where it stopped
});

test('wind: "reduce motion" switched while shown stops it, leaving the card stops it, one loop per card', async ({ page }) => {
  await mount(page);
  await page.waitForTimeout(200);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForTimeout(150);
  const reduced = await impl(page).evaluate(el => ({ raf: el._windRaf, phase: el._windPhase }));
  expect(reduced.raf).toBeNull();
  await page.waitForTimeout(200);
  expect(await impl(page).evaluate(el => el._windPhase)).toBe(reduced.phase);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.waitForTimeout(250);
  expect(await impl(page).evaluate(el => !!el._windRaf && el._windPhase !== undefined)).toBe(true);
  // a redraw never starts a second loop
  const frames = await impl(page).evaluate(async el => {
    let calls = 0; const orig = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = cb => { calls += 1; return orig(cb); };
    el._render(); el._render(); el._render();
    await new Promise(r => setTimeout(r, 200));
    window.requestAnimationFrame = orig;
    return calls;
  });
  expect(frames).toBeLessThan(20);  // ~30 per second for one loop in 200 ms (+ the render queue), not three loops
  const left = await impl(page).evaluate(el => { const host = el.parentNode; el.remove(); const raf = el._windRaf; host.appendChild(el); return raf; });
  expect(left).toBeNull();
});

// Re-audit 31.10. (D01/D02): every house-aligned code and recommendation kind the backend publishes is drawn
// with its own word, symbol and colour – rooms from the backend-derived fixture (tests/test_display_semantics_026505.py).
const SEMANTICS = JSON.parse(fs.readFileSync(new URL('./fixtures/display_semantics.json', import.meta.url), 'utf8')).scenarios;
const feed = (page, scenario, language) => page.evaluate(({ s, language }) => {
  window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, ...s.rooms }, intelligent_recommendation: s.recommendation, output_language: language });
}, { s: SEMANTICS[scenario], language });

for (const [language, held, monitored] of [['de', '⏳ Lüften möglich · noch warten', '🌬️ Daueröffnung überwachen'],
                                           ['en', '⏳ Airing possible · wait for now', '🌬️ Long opening monitored']]) {
  test(`house map: ventilate_later and monitor_open have their own words, symbol and tone (${language})`, async ({ page }) => {
    const errors = await mount(page);
    await feed(page, 'ventilate_later', language);
    await page.waitForTimeout(80);
    let rooms = await q(page, 'polygon.room');
    const wohnen = rooms.find(r => r.label.startsWith('Wohnen'));
    expect(wohnen.label).toContain(held);
    expect(wohnen.cls).toContain('t-wait');
    await feed(page, 'monitor_open', language);
    await page.waitForTimeout(80);
    rooms = await q(page, 'polygon.room');
    const bad = rooms.find(r => r.label.startsWith('Bad'));
    expect(bad.label).toContain(monitored);
    expect(bad.cls).toContain('t-run');
    expect(bad.cls).not.toContain('t-close');  // the physical "Close" is not shown while the house tolerates the opening
    for (const r of rooms) expect(r.label).not.toMatch(/Unbekannt|Unknown/);
    await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    await page.waitForTimeout(50);
    expect(await shadowText(page)).toContain(monitored.slice(3));  // the room window says the same
    // a normal close and a protection close keep the close colour and word
    for (const scenario of ['close', 'protection_close']) {
      await feed(page, scenario, language);
      await page.waitForTimeout(60);
      const closing = (await q(page, 'polygon.room')).find(r => r.label.startsWith('Bad'));
      expect(closing.cls).toContain('t-close');
      expect(closing.label).toContain(language === 'de' ? '🪟 Schließen' : '🪟 Close');
    }
    expect(errors).toEqual([]);
  });
}

test('house map hero: every backend recommendation kind has its symbol and colour, warnings never a green check', async ({ page }) => {
  await mount(page);
  const expected = { ventilate: ['💨', 'act'], continue: ['🌬️', 'run'], close: ['🪟', 'close'], wait: ['⏳', 'wait'], prepare: ['⏳', 'wait'],
    pollen_wait: ['⏳', 'wait'], sensor: ['🔧', 'sensor'], okay: ['✅', 'ok'] };
  const severity = { pollen_wait: 'warning', sensor: 'danger', close: 'warning', wait: 'warning', ventilate: 'good', continue: 'good' };
  const borders = {};
  for (const [kind, [emoji, tone]] of Object.entries(expected)) {
    await page.evaluate(({ kind, severity }) => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de',
      intelligent_recommendation: { kind, severity, title: 'Vorerst geschlossen lassen' } }), { kind, severity: severity[kind] || 'neutral' });
    await page.waitForTimeout(40);
    const bubble = await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('.bubble'); return { emo: b.querySelector('.emo').textContent, tone: b.dataset.tone, border: b.style.borderLeftColor }; });
    expect(bubble.emo, kind).toBe(emoji);
    expect(bubble.tone, kind).toBe(tone);
    expect(bubble.border, kind).not.toBe('');
    borders[kind] = bubble.border;
  }
  // status colour: pollen, sensor and prepare are not drawn in the "all good" colour
  for (const kind of ['pollen_wait', 'sensor', 'prepare']) expect(borders[kind], kind).not.toBe(borders.okay);
  expect(borders.close).not.toBe(borders.ventilate);
  // an okay published with a warning and an unknown future kind are never a plain green check
  for (const rec of [{ kind: 'okay', severity: 'warning' }, { kind: 'something_new', severity: 'neutral' }]) {
    await page.evaluate(rec => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de',
      intelligent_recommendation: { ...rec, title: 'Hinweis' } }), rec);
    await page.waitForTimeout(40);
    expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('.bubble .emo').textContent)).not.toBe('✅');
  }
});
