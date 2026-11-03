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
  // 0.26.6.0(2): no "action on another floor" notice any more (owner request) – the upper floor's button pulses
  expect(await shadowText(page)).not.toContain('Handlung auf anderer Etage');
  expect(await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('.floors [data-floor="f_og"]'); return b && [b.dataset.action, b.classList.contains('pulse')]; })).toEqual(['close', true]);
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

test('every floor is shown on its own (no all-floors overview any more); removing the card ends both subscriptions', async ({ page }) => {
  await mount(page);
  // UI hotfix 0.26.6.0 (owner request): "All floors" is gone – several floors at once = the card several times
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('[data-floor="__all"]'))).toBe(false);
  expect((await q(page, 'polygon.room')).length).toBe(3);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-floor="f_og"]').click());
  await page.waitForTimeout(50);
  expect((await q(page, 'polygon.room')).length).toBe(1);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelectorAll('svg[role="group"]').length)).toBe(1);
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

// ------------------------------------------------------------------ 0.26.5.5 (02.11.): editor keys, walls, openings, plan-first card
const geo = page => page.evaluate(async () => { window.G = await import('/freshairiq-house-geometry.js?v=t'); return true; });

test('editor: tap a room, arrow keys move it (Shift = 10 steps), the page does not scroll, undo, save, reload', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const editor = await openEditor(page);
  await page.evaluate(() => { const s = document.createElement('div'); s.style.height = '2000px'; document.body.appendChild(s); });
  await editor.locator('svg').scrollIntoViewIfNeeded();
  const y0 = await page.evaluate(() => window.scrollY);
  const box = await editor.evaluate(el => { const r = el.shadowRoot.querySelector('polygon[data-id="r_bad"]').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
  await page.mouse.click(box.x, box.y);
  expect(await editor.evaluate(el => [el._sel && el._sel.id, el.shadowRoot.activeElement && el.shadowRoot.activeElement.className])).toEqual(['r_bad', 'canvas']);
  const first = () => editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_bad').polygon[0]);
  const before = await first();
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('Shift+ArrowUp');
  expect(await first()).toEqual([before[0] - 0.1, before[1] + 1]);
  expect(await page.evaluate(() => window.scrollY)).toBe(y0);   // arrows never scroll the page with a room selected
  expect(await editor.evaluate(el => el.shadowRoot.activeElement && el.shadowRoot.activeElement.className)).toBe('canvas');  // kept after re-render
  await page.keyboard.press('Control+z');
  expect(await first()).toEqual([before[0] - 0.1, before[1]]);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout);
  expect(saved.rooms.find(r => r.id === 'r_bad').polygon[0]).toEqual([before[0] - 0.1, before[1]]);
  // reloaded from the saved layout: the moved room is there
  const again = await page.evaluate(layout => { const ed = document.createElement('freshairiq-house-layout-editor'); document.body.appendChild(ed);
    ed.setup({ layout, revision: 4, rooms: [], liveRooms: {}, language: 'de', floor: 'f_eg' }); return ed._layout.rooms.find(r => r.id === 'r_bad').polygon[0]; }, saved);
  expect(again).toEqual([before[0] - 0.1, before[1]]);
});

test('walls: shared stretch = interior, corner or a gap above 5 cm = exterior, partial walls are split; snapping onto a neighbour', async ({ page }) => {
  await mount(page);
  await geo(page);
  const out = await page.evaluate(() => {
    const room = (id, poly) => ({ id, floor_id: 'f', polygon: poly });
    const a = room('a', [[0, 0], [4, 0], [4, 3], [0, 3]]);
    const parts = other => window.G.wallParts([a, other], a).filter(w => w.interior).map(w => [w.a.map(v => +v.toFixed(3)), w.b.map(v => +v.toFixed(3))]);
    return {
      flush: parts(room('b', [[4, 0], [7, 0], [7, 3], [4, 3]])),
      gap4: parts(room('b', [[4.04, 0], [7, 0], [7, 3], [4.04, 3]])).length,
      gap12: parts(room('b', [[4.12, 0], [7, 0], [7, 3], [4.12, 3]])).length,
      corner: parts(room('b', [[4, 3], [6, 3], [6, 5], [4, 5]])).length,
      partial: parts(room('b', [[4, 1], [6, 1], [6, 2], [4, 2]])),
      other_floor: window.G.wallParts([a, { ...room('b', [[4, 0], [7, 0], [7, 3], [4, 3]]), floor_id: 'g' }], a).filter(w => w.interior).length,
      exterior: window.G.wallParts([a, room('b', [[4, 1], [6, 1], [6, 2], [4, 2]])], a).filter(w => !w.interior).length,
      snap: window.G.snapToNeighbours([[4.08, 0.03], [6, 0.03], [6, 3.03], [4.08, 3.03]], [a], 0.15),
    };
  });
  expect(out.flush).toEqual([[[4, 0], [4, 3]]]);
  expect(out.gap4).toBe(1);
  expect(out.gap12).toBe(0);
  expect(out.corner).toBe(0);              // a shared corner point is no shared wall
  expect(out.partial).toEqual([[[4, 1], [4, 2]]]);
  expect(out.other_floor).toBe(0);
  expect(out.exterior).toBe(5);            // the east wall is split: below and above the neighbour stay exterior
  expect(out.snap.dx).toBeCloseTo(-0.08, 6);
  expect(out.snap.dy).toBeCloseTo(-0.03, 6);
  expect(out.snap.gx).toBe(4);
  expect([0, 3]).toContain(out.snap.gy);   // both wall lines are 3 cm away – either guide is right
});

test('editor: dragging a room next to another snaps it onto the shared wall with a guide; it never overlaps', async ({ page }) => {
  const editor = await openEditor(page);
  // the hall (0..8 × 0..4) and the bath (0..4 × 4..8) share y = 4; move the bath 0.3 m up with the pointer, then back near the wall
  const at = (x, y) => editor.evaluate((el, p) => { const svg = el.shadowRoot.querySelector('svg'); const m = svg.getScreenCTM(); const q = svg.createSVGPoint(); q.x = p[0]; q.y = -p[1]; const r = q.matrixTransform(m); return { x: r.x, y: r.y }; }, [x, y]);
  const start = await at(2, 6), near = await at(2.04, 5.93), into = await at(2, 5.0);
  await page.mouse.move(start.x, start.y); await page.mouse.down();
  await page.mouse.move(near.x, near.y, { steps: 4 });
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('line.guide').length)).toBeGreaterThan(0);
  await page.mouse.up();
  const bath = await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_bad').polygon);
  expect(bath[0]).toEqual([0, 4]);          // snapped back onto the shared wall line exactly
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('line.guide').length)).toBe(0);
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('line.wall.inner').length)).toBeGreaterThan(0);
  // dragging it into the hall is refused (it stays where it was)
  await page.mouse.move(start.x, start.y); await page.mouse.down(); await page.mouse.move(into.x, into.y, { steps: 4 }); await page.mouse.up();
  const after = await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_bad').polygon);
  expect(after[0][1]).toBeGreaterThanOrEqual(4);
});

test('openings: door, passage and window get their own symbol in the editor and – after saving – on the house map', async ({ page }) => {
  const editor = await openEditor(page);
  const kinds = await editor.evaluate(async el => {
    el._setTool('passage'); await el._toolTap([6, 4.05]);
    el._setTool('window'); await el._toolTap([10, 5.5]);
    el._setTool(null); el._render();
    return [...el.shadowRoot.querySelectorAll('g.symbol')].map(g => [...g.querySelectorAll('.sym')].map(s => s.getAttribute('class')).join(' '));
  });
  expect(kinds.some(k => k.includes('arc') && k.includes('leaf'))).toBe(true);   // door: leaf + swing
  expect(kinds.some(k => k.includes('jamb'))).toBe(true);                         // passage: a gap with jambs
  expect(kinds.some(k => k.includes('pane'))).toBe(true);                         // window: panes
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(100);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout);
  expect(saved.openings.filter(o => o.kind === 'passage').length).toBe(1);
  // the house map draws the saved openings with the same symbols
  await page.evaluate(layout => { window.__LAYOUT2 = layout; }, saved);
  const card = await impl(page).evaluate(async el => { el._layoutInfo = { ...el._layoutInfo, layout: window.__LAYOUT2, revision: 4 }; el._render();
    // order 10 (owner request): the house map shows the door leaf without its swing arc – the arc is drawn in the editor only
    return { door: !!el.shadowRoot.querySelector('g.symbol.k-door .leaf') && !el.shadowRoot.querySelector('g.symbol.k-door .arc'), passage: !!el.shadowRoot.querySelector('g.symbol.k-passage .jamb'), window: !!el.shadowRoot.querySelector('g.symbol.k-window .pane') }; });
  expect(card).toEqual({ door: true, passage: true, window: true });
});

test('house map: walls, a logical connection without an opening, the moisture source; open/tilted windows differ', async ({ page }) => {
  await mount(page);
  const out = await impl(page).evaluate(el => {
    el._rooms = { ...el._rooms, bad: { ...el._rooms.bad, moisture_source_active: true, moisture_source_label: 'Dusche' } };
    el._render();
    const sr = el.shadowRoot;
    return { inner: sr.querySelectorAll('line.wall.inner').length, outer: sr.querySelectorAll('line.wall.outer').length,
      marks: [...sr.querySelectorAll('g.conn-mark')].length, source: sr.querySelector('g.source') && sr.querySelector('g.source').getAttribute('aria-label'),
      sash: !!sr.querySelector('g.symbol.k-window .sash'), tilt: !!sr.querySelector('g.symbol.k-window .tilt') };
  });
  expect(out.inner).toBeGreaterThan(0);
  expect(out.outer).toBeGreaterThan(out.inner);
  expect(out.marks).toBe(1);        // the hall–living open passage is a logical link without a drawn opening
  expect(out.source).toBe('Dusche');
  expect(out.tilt).toBe(true);      // the tilted living-room window
  // a logical connection whose rooms have no opening between them gets a marker; it is no door symbol
  const marks = await impl(page).evaluate(el => {
    const layout = { ...el._layoutInfo.layout, connections: [...el._layoutInfo.layout.connections, { id: 'cx', a: 'r_bad', b: 'r_wohnen', kind: 'door', confirmed: true },
      { id: 'cy', a: 'r_bad', b: 'r_flur', kind: 'door', confirmed: true }] };  // bath–hall: the door opening d_bad draws it already
    el._layoutInfo = { ...el._layoutInfo, layout }; el._render();
    return [...el.shadowRoot.querySelectorAll('g.conn-mark')].map(g => g.getAttribute('class')).sort();
  });
  expect(marks).toEqual(['conn-mark k-door', 'conn-mark k-open_passage']);  // not drawn twice where an opening links the rooms
});

test('house map: plan first – the menu holds details, floors, guests, support and editing; guests change the real setting', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  // 0.26.6.0(2): the menu is a <dialog> – closed it hides its content like [hidden] did
  const sr = sel => impl(page).evaluate((el, s) => { const n = el.shadowRoot.querySelector(s); const d = n && n.closest('dialog'); return n ? { hidden: n.closest('[hidden]') !== null || (!!d && !d.open) } : null; }, sel);
  expect(await sr('.hero')).toEqual({ hidden: true });           // the former header is in the menu
  expect(await sr('svg.plan')).toEqual({ hidden: false });       // the plan is what you see
  // 0.26.6: no wind tile, no bar and no text around the plan – the plan fills the card, the menu button lies on it
  // at the bottom right, the layers and the notes are in the menu
  expect(await sr('.windchip')).toBe(null);
  expect(await sr('.dock')).toBe(null);
  expect(await sr('[data-layer]')).toEqual({ hidden: true });
  expect(await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.legend, .notice')].every(n => n.closest('dialog.menudlg')))).toBe(true);  // 0.26.6.0(2): the menu window
  const box = await impl(page).evaluate(el => {
    const r = s => el.shadowRoot.querySelector(s).getBoundingClientRect();
    const c = r('ha-card'), m = r('.map'), b = r('[data-menu]');
    const bar = r('.mapbar');
    return { edges: [m.left - c.left, c.right - m.right, m.top - c.top].map(v => Math.round(v)), bar: [Math.round(bar.top - m.bottom), Math.round(c.bottom - bar.bottom)],
      onBar: b.right <= c.right && b.top >= bar.top && b.bottom <= bar.bottom && b.left > c.left + c.width / 2 };
  });
  expect(box.edges.every(v => v >= 0 && v <= 3)).toBe(true);   // only the card's own border
  // UI hotfix 0.26.6.0: the menu button sits at the bottom right in a bar below the plan – never over it
  expect(box.bar.every(v => v >= 0 && v <= 3)).toBe(true);
  expect(box.onBar).toBe(true);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-menu]').click());
  expect(await sr('.hero')).toEqual({ hidden: false });
  for (const s of ['[data-support]', '[data-edit]', '.guest', '[data-layer]', '.legend']) expect(await sr(s), s).toEqual({ hidden: false });
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.menudlg [data-floor]'))).toBe(false);  // 0.26.6.0(2): floors are on the plan
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-close-menu]').click());
  // guests: the integration's own number settings
  await page.evaluate(() => { window.__svc = []; const el = document.querySelector('freshairiq-house-card-impl');
    el._hass = { ...el._hass, entities: { 'number.freshairiq_gaeste': { entity_id: 'number.freshairiq_gaeste', platform: 'freshairiq', translation_key: 'guest_adults' } },
      callService: (d, s, data) => { window.__svc.push([d, s, data]); return Promise.resolve(); } };
    el._payload = { ...el._payload, guest_adults: 1 }; el._render(); });
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-guest="adults"][data-delta="1"]').click());
  expect(await page.evaluate(() => window.__svc)).toEqual([['number', 'set_value', { entity_id: 'number.freshairiq_gaeste', value: 2 }]]);
  expect(await impl(page).evaluate(el => !el.shadowRoot.querySelector('[data-guest="children"]'))).toBe(true);  // no setting found: shown, not changeable
  // support: Home Assistant's page of the integration (diagnostics download)
  // 0.26.6.0(2): support opens its own window over the house map – no jump to the integration page any more
  const path = await page.evaluate(() => location.pathname);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-support]').click());
  await expect.poll(() => impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg[open] #diagnostics-send'))).toBe(true);
  expect(await page.evaluate(() => location.pathname)).toBe(path);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('house map: rooms breathe only while airing is shown and animation is allowed', async ({ page }) => {
  await mount(page, { config: { animation: false } });
  const anim = () => impl(page).evaluate(el => getComputedStyle([...el.shadowRoot.querySelectorAll('polygon.room')].find(p => p.classList.contains('t-close'))).animationName);
  expect(await anim()).toBe('none');
  await impl(page).evaluate(el => el.setConfig({ animation: true }));
  await page.waitForTimeout(50);
  expect(await anim()).toBe('breathe');
});

test('house map 0.26.6: air moves only through passages between rooms and streams out of the open window', async ({ page }) => {
  await mount(page);
  await geo(page);
  const out = await page.evaluate(({ LAYOUT, HOUSE }) => {
    const r = p => p.map(q => q.map(v => +v.toFixed(2)));
    const path = HOUSE.airflow.paths[0];
    const route = window.G.airRoute(LAYOUT, path, { outside: 2, strict: true });
    // every step of the route stays in one room – except where it passes a door or passage, or leaves by the window
    const inside = q => LAYOUT.rooms.filter(x => x.floor_id === 'f_eg' && window.G.pointInPolygon(q, x.polygon) === 'inside').map(x => x.id);
    const steps = route.points.slice(0, -1).map((a, i) => { const b = route.points[i + 1]; return inside([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]); });
    const noLink = { ...LAYOUT, connections: [] };
    return {
      points: r(route.points), complete: route.complete, exits: route.exits, steps,
      strict: window.G.airRoute(noLink, path, { strict: true }),   // flur and wohnen not connected: the stream ends in the hall
      loose: window.G.airRoute(noLink, path).points.length,        // the air-path layer draws that step straight
      door: window.G.passage(LAYOUT, 'r_bad', 'r_flur', 'd_bad'), passage: window.G.passage(LAYOUT, 'r_flur', 'r_wohnen', 'c1'),
      none: window.G.passage(LAYOUT, 'r_bad', 'r_wohnen'),
    };
  }, { LAYOUT, HOUSE });
  expect(out.door).toEqual({ at: [2, 4], n: [0, -1] });          // the bath door, from the bath into the hall
  expect(out.passage).toEqual({ at: [6, 4], n: [0, 1] });        // the open passage: middle of the shared wall
  expect(out.none).toBe(null);                                   // bath and living room: no passage – never through the wall
  expect(out.points[0]).toEqual([2, 8]);                         // in by the bath window
  expect(out.points.slice(2, 5)).toEqual([[2, 4.35], [2, 4], [2, 3.65]]);
  expect(out.points.slice(6, 9)).toEqual([[6, 3.65], [6, 4], [6, 4.35]]);
  expect(out.points.slice(-2)).toEqual([[10, 5.5], [12, 5.5]]);  // out of the living-room window, 2 m beyond it
  expect(out.complete && out.exits).toBe(true);
  expect(out.steps.slice(1, -1).every(ids => ids.length === 1 || ids.length === 0)).toBe(true);
  expect(out.steps.at(-1)).toEqual([]);                          // the last step is outside the house
  expect(out.strict.complete).toBe(false);
  expect(out.strict.points.at(-1).map(v => +v.toFixed(2))).toEqual([4, 2]);
  expect(out.loose).toBeGreaterThan(out.strict.points.length);
  // Hotfix (9) F03 (expectation corrected): a room with a windward and a leeward window lets the air out of the other
  // window only along the directed path FreshAirIQ published for it (house_airflow cross path) – before, any second
  // open window was taken as the outlet without such a path. Here the published path is given.
  const solo = await page.evaluate(async () => {
    const V = await import('/freshairiq-house-view.js?v=t');
    const rooms = [{ id: 'a', polygon: [[0, 0], [4, 0], [4, 4], [0, 4]] }];
    const openings = [{ id: 'n', room_id: 'a', edge: 2, offset: 0.5, width_m: 1.2, state: 'open', target: 'outside', pressure: 1 },
      { id: 's', room_id: 'a', edge: 0, offset: 0.5, width_m: 1.2, state: 'open', target: 'outside', pressure: -1 }];
    const route = window.G.airRoute({ rooms: rooms.map(r => ({ ...r, floor_id: 'f' })), openings: openings.map(o => ({ ...o, kind: 'window' })), connections: [] },
      { from: 'n', to: 's', rooms: ['a'], via: [], direction: 'directed' }, { outside: 1.2, strict: true });
    const paths = [{ from: 'n', to: 's', direction: 'directed', points: route.points, exits: route.exits }];
    const s = V.windStreams({ rooms, openings, fromDeg: 0, northDeg: 0, G: window.G, count: 5, paths }).find(x => x.kind === 'inflow');
    return s && { exits: s.exits, last: s.points.at(-1).map(v => +v.toFixed(2)) };
  });
  expect(solo.exits).toBe(true);
  expect(solo.last[1]).toBeLessThan(0);                          // south of the room, outside
  // on the card: the inflow fades outside the house instead of ending with an arrow in the room
  const card = await impl(page).evaluate(el => {
    const ops = { ...el._house.airflow.openings, o_bad: { ...el._house.airflow.openings.o_bad, pending: false, state: 'open' } };
    el._house = { ...el._house, wind: { ...el._house.wind, from_deg: 0 }, airflow: { ...el._house.airflow, openings: ops } };
    el._windSmooth = 0; el._render();
    const s = el.shadowRoot.querySelector('path.stream.inflow');
    if (!s) return null;
    const last = s.getAttribute('d').trim().split(/[ML]/).filter(Boolean).at(-1).trim().split(',').map(Number);
    const grad = el.shadowRoot.querySelector(s.getAttribute('stroke').slice(4, -1)).querySelectorAll('stop');
    return { cls: s.getAttribute('class'), marker: s.getAttribute('marker-end'), x: last[0], end: grad[grad.length - 1].getAttribute('stop-opacity') };
  });
  expect(card.cls).toContain('exits');
  expect(card.marker).toBe(null);
  expect(card.x).toBeGreaterThan(10.5);                          // beyond the east wall of the living room
  expect(card.end).toBe('0');
});

// ---- hotfix 0.26.6.0 -------------------------------------------------------------------------------------
const SHARED_WALLS = JSON.parse(fs.readFileSync(new URL('./fixtures/shared_walls.json', import.meta.url), 'utf8'));

test('hotfix 0.26.6.0 (5): air passes only where both rooms share a wall – same cases as pytest, also after a move', async ({ page }) => {
  await mount(page);
  await geo(page);
  const out = await page.evaluate(FX => FX.cases.map(c => {
    const layout = { rooms: [{ id: 'a', floor_id: 'f', polygon: FX.room_a }, { id: 'b', floor_id: c.floor_b || 'f', polygon: c.b }],
      openings: c.opening ? [{ id: 'o', room_id: 'a', ...c.opening }] : [],
      connections: c.connection ? [{ id: 'c', a: 'a', b: 'b', kind: c.connection }] : [] };
    const p = window.G.passage(layout, 'a', 'b', c.opening ? 'o' : 'c');
    return [c.name, p ? p.at.map(v => +v.toFixed(3)) : null];
  }), SHARED_WALLS);
  expect(out).toEqual(SHARED_WALLS.cases.map(c => [c.name, c.passage]));
  // the card's own plan: the hall is moved away from the bath – the stored door target is stale, the stream stops
  const moved = await page.evaluate(({ LAYOUT, HOUSE }) => {
    const shift = { ...LAYOUT, rooms: LAYOUT.rooms.map(r => (r.id === 'r_flur' ? { ...r, polygon: r.polygon.map(([x, y]) => [x, y - 3]) } : r)),
      openings: LAYOUT.openings.map(o => (o.id === 'd_bad' ? { ...o, target: 'r_flur' } : o)) };
    const route = window.G.airRoute(shift, HOUSE.airflow.paths[0], { outside: 2, strict: true });
    return { door: window.G.passage(shift, 'r_bad', 'r_flur', 'd_bad'), complete: route.complete, last: route.points.at(-1).map(v => +v.toFixed(2)) };
  }, { LAYOUT, HOUSE });
  expect(moved.door).toBe(null);
  expect(moved.complete).toBe(false);
  expect(moved.last).toEqual([2, 6]);                           // ends in the bath: never through the wall
});

test('hotfix 0.26.6.0 (2): the editor shows the plan connections – logical links apart from drawn openings, never twice', async ({ page }) => {
  const editor = await openEditor(page);
  const marks = () => editor.evaluate(el => [...el.shadowRoot.querySelectorAll('g.conn')].map(g => [g.dataset.connection, g.getAttribute('class')]).sort());
  // c1 (hall – living, open passage, no drawn opening) is shown as a logical link
  expect(await marks()).toEqual([['c1', 'conn logical k-open_passage']]);
  const ops = await editor.evaluate(el => el.shadowRoot.querySelectorAll('line.op').length);
  await editor.evaluate(el => {
    el._commit(l => l.connections.push({ id: 'cd', a: 'r_bad', b: 'r_flur', kind: 'door', confirmed: true },   // the door d_bad is on that wall
      { id: 'cs', a: 'r_bad', b: 'r_wohnen', kind: 'stairs', confirmed: true }));
  });
  expect(await marks()).toEqual([['c1', 'conn logical k-open_passage'], ['cs', 'conn logical k-stairs']]);  // the door is drawn once – as the opening
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('line.op').length)).toBe(ops);           // no extra door symbol
  // the living room is moved away: its open passage has no wall any more and is marked as such
  await editor.evaluate(el => el._commit(l => { const r = l.rooms.find(x => x.id === 'r_wohnen'); r.polygon = r.polygon.map(([x, y]) => [x + 5, y + 5]); }));
  const loose = await editor.evaluate(el => { const g = el.shadowRoot.querySelector('g.conn[data-connection="c1"]'); return [g.getAttribute('class'), g.getAttribute('aria-label')]; });
  expect(loose[0]).toContain('loose');
  expect(loose[1]).toContain('keine gemeinsame Wand');
  // the links take no taps: dragging a room still works where a link is drawn
  expect(await editor.evaluate(el => [...el.shadowRoot.querySelectorAll('g.conn')].every(g => g.getAttribute('pointer-events') === 'none'))).toBe(true);
});

test('hotfix 0.26.6.0 (3): arrow keys and Delete change the plan only while the drawing has the keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const editor = await openEditor(page);
  await page.evaluate(() => { window.confirm = () => true; });
  await editor.locator('svg').scrollIntoViewIfNeeded();
  const box = await editor.evaluate(el => { const r = el.shadowRoot.querySelector('polygon[data-id="r_bad"]').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
  await page.mouse.click(box.x, box.y);
  const plan = () => editor.evaluate(el => JSON.stringify(el._layout.rooms.map(r => [r.id, r.polygon])));
  const before = await plan();
  // a button, a field and a select have the keyboard: nothing in the plan changes
  for (const sel of ['[data-a="save"]', 'input', 'select']) {
    const found = await editor.evaluate((el, s) => { const n = el.shadowRoot.querySelector(s); if (n) n.focus(); return !!n && el.shadowRoot.activeElement === n; }, sel);
    if (!found) continue;
    for (const key of ['ArrowLeft', 'ArrowUp', 'Shift+ArrowRight', 'Delete', 'Backspace']) await page.keyboard.press(key);
    expect(await plan(), sel).toBe(before);
  }
  expect(await editor.evaluate(el => el._sel && el._sel.id)).toBe('r_bad');
  // back on the drawing: the arrow moves the room
  await page.mouse.click(box.x, box.y);
  await page.keyboard.press('ArrowLeft');
  expect(await plan()).not.toBe(before);
});

test('hotfix 0.26.6.0 (4): guests use the dashboard mapping of this config entry and stay within 0–20', async ({ page }) => {
  await mount(page);
  const run = (entry, states, delta = 1, kind = 'adults') => impl(page).evaluate((el, { entry, states, delta, kind }) => {
    const calls = [];
    el._config = { ...el._config, entry_id: entry };
    el._hass = { ...el._hass, states, entities: {}, callService: (d, s, data) => { calls.push([d, s, data]); return Promise.resolve(); } };
    el._setGuests(kind, delta);
    return { entity: el._guestEntity(kind), calls };
  }, { entry, states, delta, kind });
  const num = (id, entry, key, state) => ({ [id]: { entity_id: id, state: String(state), attributes: { freshairiq_entry_id: entry, freshairiq_entity_key: key, friendly_name: 'renamed' } } });
  const two = { ...num('number.haus_a_gaeste', 'e1', 'guest_adults', 3), ...num('number.haus_b_gaeste', 'e2', 'guest_adults', 7), ...num('number.haus_a_kinder', 'e1', 'guest_children', 0) };
  // the entity of this card's entry (renamed entity ids still work), never the other house
  expect(await run('e1', two)).toEqual({ entity: 'number.haus_a_gaeste', calls: [['number', 'set_value', { entity_id: 'number.haus_a_gaeste', value: 4 }]] });
  expect((await run('e2', two)).calls).toEqual([['number', 'set_value', { entity_id: 'number.haus_b_gaeste', value: 8 }]]);
  // the range of the setting: 0–20, nothing is sent at a limit
  expect((await run('e1', { ...two, ...num('number.haus_a_gaeste', 'e1', 'guest_adults', 20) })).calls).toEqual([]);
  expect((await run('e1', { ...two, ...num('number.haus_a_gaeste', 'e1', 'guest_adults', 20) }, -1)).calls[0][2].value).toBe(19);
  expect((await run('e1', two, -1, 'children')).calls).toEqual([]);
  expect((await run('e1', { ...two, ...num('number.haus_a_gaeste', 'e1', 'guest_adults', 37) }, 1)).calls[0][2].value).toBe(20);
  // no entry known (no card setting, no layout answer) and two FreshAirIQ entries: shown only, never the wrong house
  const none = await impl(page).evaluate((el, states) => {
    el._config = { ...el._config, entry_id: undefined }; el._layoutInfo = { ...el._layoutInfo, entry_id: null }; el._hass = { ...el._hass, states, entities: {} };
    return el._guestEntity('adults'); }, two);
  expect(none).toBe(null);
  // the layout answer names the entry when the card setting does not
  const fromLayout = await impl(page).evaluate((el, states) => {
    el._config = { ...el._config, entry_id: undefined }; el._layoutInfo = { ...el._layoutInfo, entry_id: 'e2' }; el._hass = { ...el._hass, states, entities: {} };
    return el._guestEntity('adults'); }, two);
  expect(fromLayout).toBe('number.haus_b_gaeste');
});

// ---- 0.26.6.0(2): house map look, floors on the plan, menu and support windows, touch editor ----------------
const wallsOf = (page, host) => page.evaluate(sel => {
  const root = sel === 'card' ? document.querySelector('freshairiq-house-card-impl').shadowRoot : document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor').shadowRoot;
  return [...root.querySelectorAll('line.wall')].map(l => `${l.classList.contains('inner') ? 'in' : 'out'} ${['x1', 'y1', 'x2', 'y2'].map(a => (+l.getAttribute(a)).toFixed(2)).join(' ')}`).sort();
}, host);

test('0.26.6.0(2) D1/D5: the house map and the editor draw the very same walls; a door or passage is a real gap on both sides', async ({ page }) => {
  await mount(page);
  await impl(page).evaluate(el => { el._layoutInfo.layout.openings.push({ id: 'p1', room_id: 'r_flur', edge: 2, offset: 0.25, width_m: 1, kind: 'passage', mechanics: 'unknown', contacts: [] }); el._render(); });
  const card = await wallsOf(page, 'card');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-edit]').click());
  await page.waitForFunction(() => document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor'));
  await page.waitForTimeout(80);
  expect(await wallsOf(page, 'editor')).toEqual(card);   // D1: one classification for both views
  // the room outlines no longer draw walls: no stroke, no per-room shadow filter on the house map
  await impl(page).evaluate(el => el._openEditor && (el._editing = null));
  await geo(page);
  const gap = await page.evaluate(() => {
    const rooms = [{ id: 'flur', floor_id: 'f', polygon: [[0, 0], [8, 0], [8, 4], [0, 4]] }, { id: 'wohn', floor_id: 'f', polygon: [[4, 4], [10, 4], [10, 7], [7, 7], [7, 10], [4, 10]] }];
    const onTop = (segs, lo, hi) => segs.filter(s => Math.abs(s.a[1] - 4) < 1e-6 && Math.abs(s.b[1] - 4) < 1e-6)
      .some(s => Math.max(Math.min(s.a[0], s.b[0]), lo) < Math.min(Math.max(s.a[0], s.b[0]), hi) - 1e-6);
    const pass = { id: 'p', room_id: 'flur', edge: 2, offset: 0.25, width_m: 1, kind: 'passage' };   // x 5.5 … 6.5 on y = 4
    const withGap = window.G.wallSegments(rooms, [pass]);
    const moved = window.G.wallSegments(rooms, [{ ...pass, offset: 0.4 }]);                          // x 4.3 … 5.3
    const none = window.G.wallSegments(rooms, []);
    const len = segs => segs.filter(s => s.interior).reduce((sum, s) => sum + Math.hypot(s.b[0] - s.a[0], s.b[1] - s.a[1]), 0);
    return { gapCovered: onTop(withGap, 5.5, 6.5), sideCovered: onTop(withGap, 4.0, 5.5) && onTop(withGap, 6.5, 8), movedOld: onTop(moved, 5.5, 6.5), movedNew: onTop(moved, 4.3, 5.3),
      closed: onTop(none, 5.5, 6.5), interior: [len(withGap), len(none)].map(v => +v.toFixed(3)) };
  });
  expect(gap.gapCovered).toBe(false);    // no wall line under the passage – from either room
  expect(gap.sideCovered).toBe(true);
  expect([gap.movedOld, gap.movedNew]).toEqual([true, false]);   // moved: the old place is wall again
  expect(gap.closed).toBe(true);         // removed: the wall is closed
  expect(gap.interior).toEqual([3, 4]);  // the shared wall (4 m) once, minus the 1 m passage
});

test('0.26.6.0(2) D2: partly shared walls of different room shapes are split once, without overlaps or gaps', async ({ page }) => {
  await mount(page);
  await geo(page);
  const out = await page.evaluate(() => {
    const rooms = [
      { id: 'a', floor_id: 'f', polygon: [[0, 0], [4, 0], [4, 3], [0, 3]] },
      { id: 'b', floor_id: 'f', polygon: [[4, 1], [7, 1], [7, 2.5], [6, 2.5], [6, 4], [4, 4]] },   // L-shape on x = 4 from 1 to 4
      { id: 'c', floor_id: 'f', polygon: [[4, -1], [6, -1], [6, 0.4], [4, 0.4]] },                // x = 4 from −1 to 0.4
    ];
    const segs = window.G.wallSegments(rooms, []);
    const onX4 = segs.filter(s => Math.abs(s.a[0] - 4) < 1e-6 && Math.abs(s.b[0] - 4) < 1e-6).map(s => [Math.min(s.a[1], s.b[1]), Math.max(s.a[1], s.b[1]), s.interior]).sort((p, q) => p[0] - q[0]);
    return onX4.map(([lo, hi, i]) => [+lo.toFixed(3), +hi.toFixed(3), i]);
  });
  // x = 4 from −1 to 4: c alone (−1 … 0) outside, a|c (0 … 0.4) inside, a alone (0.4 … 1) outside,
  // a|b (1 … 3) inside, b alone (3 … 4) outside – each stretch exactly once, end to end
  expect(out).toEqual([[-1, 0, false], [0, 0.4, true], [0.4, 1, false], [1, 3, true], [3, 4, false]]);
});

test('0.26.6.0(2) D3/D4: doors look the same inside and outside; every symbol reads on every room colour', async ({ page }) => {
  await mount(page);
  const out = await impl(page).evaluate(el => {
    el._layoutInfo.layout.openings.push({ id: 'd_out', room_id: 'r_flur', edge: 0, offset: 0.3, width_m: 0.9, kind: 'door', mechanics: 'door', contacts: [] });
    el._render();
    const shape = g => [...g.children].map(n => `${n.tagName}.${n.getAttribute('class')}`).join(' ');
    const doors = [...el.shadowRoot.querySelectorAll('g.symbol.k-door')];
    const lone = [...el.shadowRoot.querySelectorAll('g.symbol line.sym:not(.gap), g.symbol path.sym')].filter(n => !(n.previousElementSibling && n.previousElementSibling.classList.contains('halo')));
    return { shapes: doors.map(shape), lone: lone.length, colours: [...el.shadowRoot.querySelectorAll('g.symbol .sym:not(.gap)')].map(n => getComputedStyle(n).stroke) };
  });
  expect(out.shapes.length).toBe(2);
  expect(out.shapes[0]).toBe(out.shapes[1]);          // interior and exterior door: one symbol
  expect(out.lone).toBe(0);                            // every light line has its dark rim
  expect(new Set(out.colours)).toEqual(new Set(['rgb(244, 251, 255)']));
  // contrast: light symbol or its dark rim against every room colour ≥ 3:1
  const lum = hex => { const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
  const ratio = (x, y) => { const [a, b] = [lum(x), lum(y)].sort((p, q) => q - p); return (a + 0.05) / (b + 0.05); };
  for (const fill of ['#39e07a', '#00d8f0', '#ff9f43', '#ffc93c', '#7d8ca3', '#1d6f8f', '#ff5d5d', '#031a33']) {
    expect(Math.max(ratio('#f4fbff', fill), ratio('#021024', fill)), fill).toBeGreaterThanOrEqual(3);
  }
});

test('0.26.6.0(2) D11: door hinge and swing – drawn on the right side, kept through save and reload', async ({ page }) => {
  const editor = await openEditor(page);
  await geo(page);
  // the swing arc is a quarter circle around the hinge for every combination
  const arcs = await page.evaluate(async () => {
    const V = await import('/freshairiq-house-view.js?v=t');
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); document.body.appendChild(svg);
    const a = [0, 0], b = [1, 0], inward = [0, 1], out = [];
    for (const door_hinge of [undefined, 'left', 'right']) for (const door_swing of [undefined, 'in', 'out']) {
      const d = window.G.doorGeometry(a, b, inward, { door_hinge, door_swing });
      svg.innerHTML = V.openingSymbol('door', a, b, inward, 'closed', n => n * 0.01, '#000', d);
      const arc = svg.querySelector('path.arc'), mid = arc.getPointAtLength(arc.getTotalLength() / 2);
      out.push({ door_hinge, door_swing, hinge: d.hinge, side: Math.sign(-mid.y), r: +Math.hypot(mid.x - d.hinge[0], -mid.y - d.hinge[1]).toFixed(3) });
    }
    return out;
  });
  for (const a of arcs) expect(a.r, JSON.stringify(a)).toBe(1);                       // centred on the hinge
  for (const a of arcs) expect(a.side, JSON.stringify(a)).toBe(a.door_swing === 'out' ? -1 : 1);
  // inside the room (inward = +y) facing the wall: the right hand is −x, so "right" puts the hinge at a = (0, 0)
  expect(arcs.filter(a => a.door_hinge === 'right').every(a => a.hinge[0] === 0)).toBe(true);
  expect(arcs.filter(a => a.door_hinge === 'left').every(a => a.hinge[0] === 1)).toBe(true);
  expect(arcs.filter(a => !a.door_hinge).every(a => a.hinge[0] === 0)).toBe(true);    // older plans: as before
  // the door's window in the editor: hinge, swing, width and position, then save and open again
  await editor.evaluate(el => { el._sel = { type: 'opening', id: 'd_bad' }; el._render(); });
  const set = async (field, value) => editor.evaluate((el, [f, v]) => { const n = el.shadowRoot.querySelector(`[data-f="${f}"]`); n.value = v; n.dispatchEvent(new Event('change')); }, [field, value]);
  await set('door_hinge', 'right'); await set('door_swing', 'out'); await set('width', '0.8'); await set('offset', '0.4');
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout.openings.find(o => o.id === 'd_bad'));
  expect([saved.door_hinge, saved.door_swing, saved.width_m, saved.offset]).toEqual(['right', 'out', 0.8, 0.4]);
  const again = await page.evaluate(layout => { const ed = document.createElement('freshairiq-house-layout-editor'); document.body.appendChild(ed);
    ed.setup({ layout, revision: 4, rooms: [], liveRooms: {}, language: 'de', floor: 'f_eg' }); ed._sel = { type: 'opening', id: 'd_bad' }; ed._render();
    return ['door_hinge', 'door_swing'].map(f => ed.shadowRoot.querySelector(`[data-f="${f}"]`).value); },
  await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout));
  expect(again).toEqual(['right', 'out']);
  // "as before" removes the attribute again – no silent change of older doors
  await set('door_hinge', '');
  expect(await editor.evaluate(el => 'door_hinge' in el._layout.openings.find(o => o.id === 'd_bad'))).toBe(false);
});

// Order 10 (owner request, expectations changed): a wall length changes that wall only – the corner that stays is kept,
// the other corner moves along the wall and the NEXT wall takes up the change (the opposite wall keeps its length, the room
// may stop being a rectangle); neighbouring rooms are never moved along – a clash with them is refused with an explanation.
// Before, both corners moved (the opposite wall changed too) and a shared wall dragged the neighbour along.
test('0.26.6.0(2) D10: wall length – fixed corner, shared walls move along, lock, conflicts, undo and redo', async ({ page }) => {
  await mount(page);
  await geo(page);
  const pure = await page.evaluate(() => {
    const A = { id: 'a', floor_id: 'f', polygon: [[0, 0], [4, 0], [4, 3], [0, 3]] }, B = { id: 'b', floor_id: 'f', polygon: [[4, 0], [7, 0], [7, 3], [4, 3]] };
    const C = { id: 'c', floor_id: 'f', polygon: [[6, 0], [8, 0], [8, 3], [6, 3]] }, slant = { id: 's', floor_id: 'f', polygon: [[0, 0], [3, 4], [0, 4]] };
    return {
      shared: window.G.resizeWall({ rooms: [A, B] }, 'a', 0, 5, 'start'),     // the shared wall x = 4 moves to 5, B follows
      fixedEnd: window.G.resizeWall({ rooms: [A] }, 'a', 0, 3, 'end'),       // (4, 0) stays, the left wall moves
      slanted: window.G.resizeWall({ rooms: [slant] }, 's', 0, 10, 'start'), // a 5 m slanted wall becomes 10 m
      bad: window.G.resizeWall({ rooms: [A] }, 'a', 0, 0.05, 'start'),
      overlap: (() => { const r = window.G.resizeWall({ rooms: [A, C] }, 'a', 0, 7, 'start'); return window.G.polygonsOverlap(r.polygons.a, C.polygon); })(),
    };
  });
  expect(pure.shared.polygons).toEqual({ a: [[0, 0], [5, 0], [4, 3], [0, 3]] });     // only this wall; B is not moved
  expect(pure.fixedEnd.polygons.a).toEqual([[1, 0], [4, 0], [4, 3], [0, 3]]);
  expect(pure.slanted.polygons.s[1]).toEqual([6, 8]);
  expect(pure.bad).toEqual({ error: 'length' });
  expect(pure.overlap).toBe(true);   // the editor refuses this (below)
  // in the editor: tap the bath's top wall, 3 m with the right corner fixed
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-edit]').click());
  await page.waitForFunction(() => document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor'));
  const editor = page.locator('freshairiq-house-layout-editor');
  const bath = () => editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_bad').polygon);
  const original = await bath();
  const apply = (index, len, fixed = 'start') => editor.evaluate((el, [i, l, f]) => {
    el._sel = { type: 'wall', id: 'r_bad', index: i }; el._wallFixed = f; el._render();
    el.shadowRoot.querySelector('[data-f="wall_len"]').value = String(l);
    el.shadowRoot.querySelector('[data-a="wall_apply"]').click();
    return el._msg ? el._msg.text : null;
  }, [index, len, fixed]);
  expect(await editor.evaluate(el => { el._sel = { type: 'wall', id: 'r_bad', index: 2 }; el._render(); return [el.shadowRoot.querySelector('[data-f="wall_len"]').value, el.shadowRoot.querySelectorAll('text.measure').length, el.shadowRoot.querySelectorAll('circle.corner').length]; }))
    .toEqual(['4.00', 1, 2]);   // the length on the drawing and both corners numbered
  expect(await apply(2, 3)).toBe(null);
  expect(await bath()).toEqual([[0, 4], [4, 4], [4, 8], [1, 8]]);   // the bottom wall keeps its 4 m
  expect(await editor.evaluate(el => { const o = el._layout.openings.find(x => x.id === 'o_bad'); return [o.edge, o.offset]; })).toEqual([2, 0.667]);  // the window keeps its place
  // growing into the neighbouring room is refused with a message, nothing changed
  const before = await bath();
  expect(await apply(2, 5, 'end')).toContain('Nachbarraum');
  expect(await bath()).toEqual(before);
  // lock the length: changing it, dragging a corner of it or the size handle is refused
  await editor.evaluate(el => { el._sel = { type: 'wall', id: 'r_bad', index: 2 }; el._render(); const c = el.shadowRoot.querySelector('[data-f="wall_lock"]'); c.checked = true; c.dispatchEvent(new Event('change')); });
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_bad').locked_walls)).toEqual([2]);
  expect(await editor.evaluate(el => [el.shadowRoot.querySelector('[data-f="wall_len"]').disabled, el.shadowRoot.querySelector('text.measure').textContent])).toEqual([true, '🔒 3.00 m']);
  const keyed = await editor.evaluate(el => { el._sel = { type: 'vertex', id: 'r_bad', index: 3 }; el._commit(l => { l.rooms.find(r => r.id === 'r_bad').polygon[3] = [0.5, 8]; }); return el._msg && el._msg.text; });
  expect(keyed).toContain('gesperrtes Maß');
  expect(await bath()).toEqual(before);
  // undo / redo walk through the length change and the lock
  await editor.evaluate(el => el._undo());   // the lock
  await editor.evaluate(el => el._undo());   // the length
  expect(await bath()).toEqual(original);
  await editor.evaluate(el => el._redo());
  expect(await bath()).toEqual(before);
  // saved as it is
  await editor.evaluate(el => el._redo());
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout.rooms.find(r => r.id === 'r_bad'));
  expect([saved.polygon, saved.locked_walls]).toEqual([before, [2]]);
});

test('0.26.6.0(2) D10b: a logical connection can become a drawn door once – never twice', async ({ page }) => {
  const editor = await openEditor(page);
  await editor.evaluate(el => { el._sel = { type: 'room', id: 'r_flur' }; el._render(); });
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('[data-conv-c="c1"]').length)).toBe(1);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-conv-c="c1"]').click());
  const after = await editor.evaluate(el => ({ conns: el._layout.connections.map(c => c.id), op: el._layout.openings.filter(o => o.kind === 'passage').map(o => [o.room_id, o.edge]) }));
  expect(after.conns).toEqual([]);                  // the connection became the passage …
  expect(after.op.length).toBe(1);                  // … and exists once
  await editor.evaluate(el => { el._sel = { type: 'room', id: 'r_flur' }; el._render(); });
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('[data-conv-c]').length)).toBe(0);
});

test('0.26.6.0(2) D6/D7: floors as buttons on the plan; a floor pulses only when it needs an action', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => localStorage.clear());
  const buttons = () => impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.stage .floors [data-floor]')].map(b => [b.dataset.floor, b.dataset.action || null]));
  expect(await buttons()).toEqual([['f_og', null]]);   // the floor shown is not offered; UI hotfix: no "All floors"
  const room = patch => page.evaluate(p => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, schlaf: { ...window.__ROOMS.schlaf, ...p } } }), patch);
  for (const [patch, action] of [
    [{ action: 'Close', house_aligned_action: 'close' }, 'close'], [{ action: 'Ventilate', house_aligned_action: 'ventilate' }, 'act'],
    [{ action: 'Wait', house_aligned_action: 'wait' }, null], [{ action: 'Okay', house_aligned_action: 'okay' }, null],
    [{ action: 'Okay', house_aligned_action: 'okay', mould_level: 'Very high' }, 'critical'], [{ action: 'Okay', house_aligned_action: 'okay', mould_level: null }, null],
  ]) {
    await room(patch); await page.waitForTimeout(60);
    expect((await buttons())[0], JSON.stringify(patch)).toEqual(['f_og', action]);   // and it ends by itself
  }
  await room({ action: 'Close', house_aligned_action: 'close' }); await page.waitForTimeout(60);
  const anim = () => impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('.floorbtn.pulse'); return [getComputedStyle(b).animationName, getComputedStyle(b, '::after').content]; });
  expect((await anim())[0]).toBe('floorpulse');
  expect(await shadowText(page)).not.toContain('Handlung auf anderer Etage');
  // change floors: the list follows, the choice is kept
  await impl(page).evaluate(el => el.shadowRoot.querySelector('.floors [data-floor="f_og"]').click());
  expect(await buttons()).toEqual([['f_eg', 'close']]);   // the bath downstairs needs closing
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('freshairiq-house:default')).floor)).toBe('f_og');
});

test('0.26.6.0(2) D7b: with reduced motion the floor button does not pulse but keeps a static mark', async ({ page }) => {
  await mount(page, { reducedMotion: 'reduce' });
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, schlaf: { ...window.__ROOMS.schlaf, action: 'Close', house_aligned_action: 'close' } } }));
  await page.waitForTimeout(60);
  const s = await impl(page).evaluate(el => { const b = el.shadowRoot.querySelector('.floorbtn.pulse'); return [getComputedStyle(b).animationName, getComputedStyle(b, '::after').content, getComputedStyle(b).boxShadow.includes('rgb(255, 159, 67)')]; });
  expect(s).toEqual(['none', '""', true]);
});

test('0.26.6.0(2) D8/D9: the menu is a real window without a jump; support opens its own window with the dashboard support functions', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 });
  await mount(page);
  await page.evaluate(() => { const s = document.createElement('div'); s.style.height = '1500px'; document.body.prepend(s); window.scrollTo(0, 900); });
  const y = await page.evaluate(() => window.scrollY);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-menu]').click());
  const menu = () => impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.menudlg'); return { open: d.open, modal: d.matches(':modal'), layers: d.querySelectorAll('[data-layer]').length, floors: d.querySelectorAll('[data-floor]').length }; });
  expect(await menu()).toEqual({ open: true, modal: true, layers: 6, floors: 0 });
  expect(await page.evaluate(() => window.scrollY)).toBe(y);
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de', status_text: 'neu' }));
  await page.waitForTimeout(60);
  expect((await menu()).open).toBe(true);                         // a live update keeps it open
  expect(await page.evaluate(() => window.scrollY)).toBe(y);
  // support: its own window, the dashboard card's functions (required description, sending through the API)
  await page.evaluate(() => { window.__alerts = []; window.alert = m => window.__alerts.push(String(m)); window.__api = [];
    const el = document.querySelector('freshairiq-house-card-impl');
    el._hass = { ...el._hass, callApi: (method, path, body) => { window.__api.push([method, path, body]); return Promise.resolve(path === 'freshairiq/support-diagnostics' ? { accepted: true, cooldown_until: new Date(Date.now() + 3600e3).toISOString(), support_case_id: 'FAIQ-1' } : { registered: true }); } }; });
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-support]').click());
  await expect.poll(() => impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg[open] #diagnostics-send'))).toBe(true);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.menudlg').open)).toBe(false);
  expect(await page.evaluate(() => location.pathname)).not.toContain('/config/integrations');
  await impl(page).evaluate(el => el.shadowRoot.getElementById('diagnostics-send').click());
  await page.waitForTimeout(40);
  expect((await page.evaluate(() => window.__alerts))[0]).toContain('Bitte beschreibe den Fehler');   // the description is required
  await impl(page).evaluate(el => { el.shadowRoot.getElementById('diagnostics-message').value = 'Die Hauskarte zeigt falsche Wände'; });
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de' }));
  await page.waitForTimeout(60);
  expect(await impl(page).evaluate(el => el.shadowRoot.getElementById('diagnostics-message').value)).toBe('Die Hauskarte zeigt falsche Wände');  // kept during live updates
  await impl(page).evaluate(el => el.shadowRoot.getElementById('diagnostics-send').click());
  await expect.poll(() => page.evaluate(() => window.__api.filter(c => c[1] === 'freshairiq/support-diagnostics').length)).toBe(1);
  expect(await page.evaluate(() => window.__api.find(c => c[1] === 'freshairiq/support-diagnostics'))).toEqual(['POST', 'freshairiq/support-diagnostics', { message: 'Die Hauskarte zeigt falsche Wände' }]);
  await expect.poll(() => page.evaluate(() => window.__alerts.join(' '))).toContain('Support-ID: FAIQ-1');
  // feedback through the same function as the dashboard card (entry from the layout answer)
  await impl(page).evaluate(el => { el.shadowRoot.getElementById('feedback-message').value = 'Etagenknopf super'; el.shadowRoot.getElementById('feedback-send').click(); });
  await expect.poll(() => page.evaluate(() => (window.__api.find(c => c[1].startsWith('freshairiq/feedback/')) || [])[1])).toBe('freshairiq/feedback/e1');
});

test.describe('0.26.6.0(2) D12: touch editing on a phone', () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });
  test('a tap chooses, a finger over unchosen things moves the view only, two fingers zoom, the chosen room moves', async ({ page }) => {
    const editor = await openEditor(page);
    await editor.locator('svg').scrollIntoViewIfNeeded();
    const cdp = await page.context().newCDPSession(page);
    const touch = async (type, points) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: points.map(([x, y], id) => ({ x, y, id })) });
    const centre = id => editor.evaluate((el, i) => { const r = el.shadowRoot.querySelector(`polygon[data-id="${i}"]`).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }, id);
    const plan = () => editor.evaluate(el => JSON.stringify(el._layout.rooms.map(r => r.polygon)));
    const view = () => editor.evaluate(el => ({ ...el._view }));
    const swipe = async ([x, y], dx, dy) => { await touch('touchStart', [[x, y]]); for (let k = 1; k <= 5; k++) await touch('touchMove', [[x + dx * k / 5, y + dy * k / 5]]); await touch('touchEnd', []); };
    const before = await plan();
    const scrollX = await page.evaluate(() => window.scrollX);
    // a finger over the hall (not chosen): the view moves, the plan does not
    const v0 = await view();
    await swipe(await centre('r_flur'), 60, 20);
    expect(await plan()).toBe(before);
    expect((await view()).cx).not.toBe(v0.cx);
    expect(await editor.evaluate(el => el._sel)).toBe(null);
    // a tap chooses the bath
    const [bx, by] = await centre('r_bad');
    await page.touchscreen.tap(bx, by);
    expect(await editor.evaluate(el => el._sel)).toEqual({ type: 'room', id: 'r_bad' });
    expect(await plan()).toBe(before);
    // a tap on a wall chooses the wall and shows its length
    const wall = await editor.evaluate(el => { const l = el.shadowRoot.querySelector('line.hitwall[data-id="r_bad"][data-i="3"]'); const r = l.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
    await page.touchscreen.tap(wall[0], wall[1]);
    expect(await editor.evaluate(el => [el._sel, !!el.shadowRoot.querySelector('[data-f="wall_len"]')])).toEqual([{ type: 'wall', id: 'r_bad', index: 3 }, true]);
    // two fingers zoom, nothing in the plan changes
    const s0 = (await view()).size;
    await touch('touchStart', [[150, 400], [250, 400]]);
    for (let k = 1; k <= 5; k++) await touch('touchMove', [[150 - k * 12, 400], [250 + k * 12, 400]]);
    await touch('touchEnd', []);
    expect((await view()).size).toBeLessThan(s0);
    expect(await plan()).toBe(before);
    // the chosen room moves with the finger
    await page.touchscreen.tap(...(await centre('r_bad')));
    await swipe(await centre('r_bad'), -40, 0);
    expect(await plan()).not.toBe(before);
    expect(await page.evaluate(() => window.scrollX)).toBe(scrollX);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  });
});

// ---- 0.26.6.0 UI hotfix: floors per card instance, bar below the plan, support buttons, F01–F03 -------------
const addSecondCard = (page, config) => page.evaluate(async cfg => {
  const first = document.getElementById('card');
  const card = document.createElement('freshairiq-house-card');
  card.id = 'card2'; card.setConfig(cfg); document.getElementById('m').appendChild(card); card.hass = first.hass;
  await new Promise(r => setTimeout(r, 300));
}, config);
const cardImpl = (page, i) => page.locator('freshairiq-house-card-impl').nth(i);
const shownFloor = (page, i) => cardImpl(page, i).evaluate(el => el._floor);
const floorButtons = (page, i) => cardImpl(page, i).evaluate(el => [...el.shadowRoot.querySelectorAll('.floors [data-floor]')].map(b => b.dataset.floor));

test('UI hotfix 1–3: no "All floors"; two cards show different floors independently, each keeps its own choice', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => localStorage.clear());
  await addSecondCard(page, { floor: 'upper_floor' });
  expect(await page.locator('freshairiq-house-card-impl').count()).toBe(2);
  expect([await shownFloor(page, 0), await shownFloor(page, 1)]).toEqual(['f_eg', 'f_og']);   // the second card's start floor
  for (const i of [0, 1]) expect(await cardImpl(page, i).evaluate(el => !!el.shadowRoot.querySelector('[data-floor="__all"]') || el.shadowRoot.textContent.includes('Alle Etagen'))).toBe(false);
  expect([await floorButtons(page, 0), await floorButtons(page, 1)]).toEqual([['f_og'], ['f_eg']]);
  // switching the first card never switches the second (and the other way round)
  await cardImpl(page, 0).evaluate(el => el.shadowRoot.querySelector('[data-floor="f_og"]').click());
  expect([await shownFloor(page, 0), await shownFloor(page, 1)]).toEqual(['f_og', 'f_og']);
  await cardImpl(page, 1).evaluate(el => el.shadowRoot.querySelector('[data-floor="f_eg"]').click());
  expect([await shownFloor(page, 0), await shownFloor(page, 1)]).toEqual(['f_og', 'f_eg']);
  // each choice is kept apart (stored per card instance) – a reload brings both back as they were
  const stored = await page.evaluate(() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('freshairiq-house')).map(k => [k, JSON.parse(localStorage.getItem(k)).floor])));
  expect(stored).toEqual({ 'freshairiq-house:default': 'f_og', 'freshairiq-house:default:upper_floor': 'f_eg' });
  // an "all floors" choice stored by an older version falls back to the card's start floor
  await page.evaluate(() => localStorage.setItem('freshairiq-house:default:upper_floor', JSON.stringify({ floor: '__all' })));
  await page.evaluate(() => document.getElementById('card2').remove());
  await addSecondCard(page, { floor: 'upper_floor' });
  expect(await shownFloor(page, 1)).toBe('f_og');
});

const overlaps = (a, b) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
for (const [w, h] of [[320, 568], [375, 667], [390, 844], [820, 1180]]) {
  test(`UI hotfix 4/5: floor and menu buttons never cover the plan at ${w}×${h}; the wind stays visible below the house`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await mount(page);
    // many floors: six storeys with one room each, the first one shown
    await impl(page).evaluate(el => {
      const lay = el._layoutInfo.layout, names = ['basement', 'ground_floor', 'upper_floor', 'attic', 'floor_3', 'floor_4'];
      for (let i = 2; i < 6; i++) { lay.floors.push({ id: `f${i}`, name: `Etage ${i}`, level_key: names[i], order: i }); lay.rooms.push({ id: `r${i}`, room_key: `x${i}`, floor_id: `f${i}`, polygon: [[0, 0], [5, 0], [5, 4], [0, 4]], provenance: 'user' }); }
      el._floor = 'f_eg'; el._render();
    });
    await page.waitForTimeout(150);
    const out = await impl(page).evaluate(el => {
      const R = n => n.getBoundingClientRect();
      const plan = [...el.shadowRoot.querySelectorAll('svg.plan polygon.room, svg.plan .tag, svg.plan line.op, svg.plan line.wall, svg.plan g.symbol')].map(R);
      const buttons = [...el.shadowRoot.querySelectorAll('.floors button, [data-menu]')].map(R);
      const card = R(el.shadowRoot.querySelector('ha-card')), bar = R(el.shadowRoot.querySelector('.mapbar'));
      const house = plan.reduce((b, r) => ({ bottom: Math.max(b.bottom, r.bottom) }), { bottom: -Infinity });
      const waves = [...el.shadowRoot.querySelectorAll('svg.plan path.wave')].map(R);
      return { plan, buttons, card, bar, houseBottom: house.bottom, windBelow: waves.some(r => r.bottom > house.bottom + 4 && r.top < bar.top),
        count: buttons.length, overflowX: document.documentElement.scrollWidth - window.innerWidth };
    });
    expect(out.count).toBe(6);   // five other floors and the menu
    for (const b of out.buttons) {
      for (const p of out.plan) expect(overlaps(b, p), JSON.stringify([b, p])).toBe(false);
      expect(b.left >= out.card.left && b.right <= out.card.right && b.bottom <= out.card.bottom).toBe(true);  // inside the card
    }
    expect(out.bar.top).toBeGreaterThanOrEqual(out.houseBottom);   // a free zone between the house and the bar
    expect(out.card.bottom - out.bar.bottom).toBeLessThanOrEqual(4);  // the bar is the bottom edge of the card
    expect(out.windBelow).toBe(true);                                 // wind streams run in that zone
    expect(out.overflowX).toBeLessThanOrEqual(1);
  });
}

test('UI hotfix 6/7: the support buttons stand side by side, readable; export and sending still work; the window scrolls and closes on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 520 });
  await mount(page);
  await page.evaluate(() => { window.__api = []; window.__alerts = []; window.alert = m => window.__alerts.push(String(m)); window.__downloads = [];
    const el = document.querySelector('freshairiq-house-card-impl');
    URL.createObjectURL = () => 'blob:x'; URL.revokeObjectURL = () => {};
    const click = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { window.__downloads.push(this.download); };
    el._hass = { ...el._hass,
      callApi: (method, path, body) => { window.__api.push([method, path, body]); return Promise.resolve(path === 'freshairiq/support-diagnostics' ? { accepted: true, cooldown_until: new Date(Date.now() + 3600e3).toISOString(), support_case_id: 'FAIQ-7' } : path === 'freshairiq/diagnostics' && method === 'GET' ? { ok: 1 } : { registered: true }); },
      callApiRaw: () => Promise.resolve({ ok: true, headers: { get: () => 'application/zip' }, blob: () => Promise.resolve(new Blob(['zip'])) }) }; });
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-menu]').click());
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-support]').click());
  await expect.poll(() => impl(page).evaluate(el => !!el.shadowRoot.querySelector('dialog.roomdlg[open] #diagnostics-send'))).toBe(true);
  const look = await impl(page).evaluate(el => {
    const a = el.shadowRoot.getElementById('diagnostics-export'), b = el.shadowRoot.getElementById('diagnostics-send'), ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const clipped = n => [...n.querySelectorAll('b, span')].some(x => x.scrollWidth > x.clientWidth + 1 || x.scrollHeight > x.clientHeight + 1);   // text and icon
    const body = el.shadowRoot.querySelector('dialog.roomdlg .body');
    return { row: Math.abs(ra.top - rb.top) < 1 && rb.left >= ra.right + 6, sameW: Math.abs(ra.width - rb.width) <= 1, sameH: Math.abs(ra.height - rb.height) <= 1,
      style: ['fontSize', 'borderRadius', 'paddingTop'].every(k => getComputedStyle(a)[k] === getComputedStyle(b)[k]), centred: getComputedStyle(a).textAlign === 'center',
      clipped: clipped(a) || clipped(b), overflow: body.scrollWidth - body.clientWidth, scrolls: getComputedStyle(body).overflowY === 'auto' };   // scrolls when it is longer than the window
  });
  expect(look, JSON.stringify(look)).toEqual({ row: true, sameW: true, sameH: true, style: true, centred: true, clipped: false, overflow: 0, scrolls: true });
  // the close button stays reachable while the content scrolls (also with a smaller visible area, e.g. the keyboard)
  for (const height of [520, 360]) {
    await page.setViewportSize({ width: 320, height });
    const foot = await impl(page).evaluate(el => { const r = el.shadowRoot.querySelector('dialog.roomdlg [data-close-detail]').getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight; });
    expect(foot, `height ${height}`).toBe(true);
  }
  await page.setViewportSize({ width: 320, height: 520 });
  // export: the dashboard card's export (zip through Home Assistant), sending: description required, then sent
  await impl(page).evaluate(el => el.shadowRoot.getElementById('diagnostics-export').click());
  await expect.poll(() => page.evaluate(() => window.__downloads.length)).toBe(1);
  expect(await page.evaluate(() => window.__downloads[0])).toMatch(/^FreshAirIQ-diagnostics-.*\.zip$/);
  await impl(page).evaluate(el => el.shadowRoot.getElementById('diagnostics-send').click());
  await expect.poll(() => page.evaluate(() => window.__alerts.length)).toBe(1);
  expect(await page.evaluate(() => window.__alerts[0])).toContain('Bitte beschreibe den Fehler');
  await impl(page).evaluate(el => { el.shadowRoot.getElementById('diagnostics-message').value = 'Etagenknöpfe liegen über dem Bad'; el.shadowRoot.getElementById('diagnostics-send').click(); });
  await expect.poll(() => page.evaluate(() => window.__api.filter(c => c[1] === 'freshairiq/support-diagnostics').length)).toBe(1);
  await expect.poll(() => page.evaluate(() => window.__alerts.join(' '))).toContain('Support-ID: FAIQ-7');
  // while sending the button shows its state (dashboard card logic) and is the same size as before
  const busy = await impl(page).evaluate(el => el.shadowRoot.getElementById('diagnostics-send').textContent);
  expect(busy).toMatch(/Erfolgreich gesendet|Diagnosedaten/);
});

test('UI hotfix 8 (F01): an interior door is not moved onto an outside wall – while dragging, in the panel, on save and reload', async ({ page }) => {
  const editor = await openEditor(page);
  // a door placed with the interior tool between bath and hall carries the interior mark
  const placed = await editor.evaluate(async el => {
    const T = await import('/freshairiq-house-trace.js?v=t');
    const o = T.openingAt(el._layout, 'f_eg', [1, 4], 0.6, 'door');
    el._commit(l => l.openings.push(o)); return { id: o.id, interior: o.interior, edge: o.edge };
  });
  expect(placed.interior).toBe(true);
  // drag it towards the bath's outside wall (left, x = 0): the position off the shared wall is not taken
  await editor.evaluate((el, id) => { el._sel = { type: 'opening', id }; el._render(); }, placed.id);
  await editor.locator('svg').scrollIntoViewIfNeeded();
  const pts = await editor.evaluate((el, id) => {
    const svg = el.shadowRoot.querySelector('svg'), m = svg.getScreenCTM(), P = (x, y) => { const p = svg.createSVGPoint(); p.x = x; p.y = -y; const q = p.matrixTransform(m); return [q.x, q.y]; };
    return { from: P(1, 4), to: P(0, 6) };
  }, placed.id);
  await page.mouse.move(...pts.from); await page.mouse.down(); await page.mouse.move(...pts.to, { steps: 6 }); await page.mouse.up();
  const after = await editor.evaluate((el, id) => { const o = el._layout.openings.find(x => x.id === id); return { edge: o.edge, msg: el._msg && el._msg.text }; }, placed.id);
  expect(after.edge).toBe(placed.edge);
  expect(after.msg).toContain('beide Räume teilen');
  // the wall field in the panel cannot move it there either
  await editor.evaluate(el => { const n = el.shadowRoot.querySelector('[data-f="edge"]'); n.value = '4'; n.dispatchEvent(new Event('change')); });
  expect(await editor.evaluate((el, id) => el._layout.openings.find(x => x.id === id).edge, placed.id)).toBe(placed.edge);
  // a plan where it is off the shared wall (e.g. imported) is refused on save, frontend like backend
  await geo(page);
  const codes = await editor.evaluate((el, id) => { const lay = JSON.parse(JSON.stringify(el._layout)); lay.openings.find(x => x.id === id).edge = 3; return window.G.validateLayout(lay).map(i => i.code); }, placed.id);
  expect(codes).toContain('E_OPENING_INTERIOR');
  // saved and loaded again: still on the shared wall with its mark
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(id => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout.openings.find(o => o.id === id), placed.id);
  expect([saved.edge, saved.interior]).toEqual([placed.edge, true]);
});

test('UI hotfix 9 (F02): metric plans show metres; schematic plans show plan units and get a scale from one measured wall', async ({ page }) => {
  const editor = await openEditor(page);
  const wall = () => editor.evaluate(el => { el._sel = { type: 'wall', id: 'r_bad', index: 2 }; el._render();
    return { label: el.shadowRoot.querySelector('[data-f="wall_len"]').closest('label').textContent.trim(), measure: el.shadowRoot.querySelector('text.measure').textContent, scale: !!el.shadowRoot.querySelector('[data-f="scale_m"]') }; });
  expect(await wall()).toEqual({ label: 'Länge (m)', measure: '4.00 m', scale: false });   // metric: as before
  await editor.evaluate(el => { el._layout.building.units = 'schematic'; el._render(); });
  const s = await wall();
  expect(s.measure).toBe('4.00 Einh.');
  expect(s.label).toContain('Plan-Einheiten');
  expect(s.scale).toBe(true);
  // the bath's top wall really is 3.2 m: every length is scaled alike, the plan is metric from then on
  const before = await editor.evaluate(el => JSON.parse(JSON.stringify(el._layout)));
  await editor.evaluate(el => { el.shadowRoot.querySelector('[data-f="scale_m"]').value = '3.2'; el.shadowRoot.querySelector('[data-a="calibrate"]').click(); });
  const after = await editor.evaluate(el => ({ units: el._layout.building.units, bad: el._layout.rooms.find(r => r.id === 'r_bad').polygon, flur: el._layout.rooms.find(r => r.id === 'r_flur').polygon, w: el._layout.openings.find(o => o.id === 'o_wohnen').width_m }));
  expect(after.units).toBe('m');
  expect(after.bad).toEqual([[0, 3.2], [3.2, 3.2], [3.2, 6.4], [0, 6.4]]);
  expect(after.flur).toEqual([[0, 0], [6.4, 0], [6.4, 3.2], [0, 3.2]]);
  expect(after.w).toBe(0.96);
  expect(await wall()).toMatchObject({ measure: '3.20 m', scale: false });
  await editor.evaluate(el => el._undo());
  expect(await editor.evaluate(el => el._layout)).toEqual(before);   // undo restores the schematic plan
  // in a schematic plan a length is entered in plan units (no metres are claimed)
  await editor.evaluate(el => { el._sel = { type: 'wall', id: 'r_bad', index: 2 }; el._wallFixed = 'start'; el._render(); el.shadowRoot.querySelector('[data-f="wall_len"]').value = '3'; el.shadowRoot.querySelector('[data-a="wall_apply"]').click(); });
  // order 10: only this wall changes (the opposite wall keeps its length)
  expect(await editor.evaluate(el => [el._layout.building.units, el._layout.rooms.find(r => r.id === 'r_bad').polygon])).toEqual(['schematic', [[0, 4], [4, 4], [4, 8], [1, 8]]]);
});

test.describe('UI hotfix 10 (F03): touch targets', () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });
  test('walls, doors and corners have ≥ 44 px targets; the nearest of neighbouring objects is chosen', async ({ page }) => {
    const editor = await openEditor(page);
    await editor.locator('svg').scrollIntoViewIfNeeded();
    const sizes = await editor.evaluate(el => {
      const u = el._unit(); el._sel = { type: 'room', id: 'r_bad' }; el._mode = 'precise'; el._render();
      const px = n => +(Number(n) / u).toFixed(1);
      return { wall: px(el.shadowRoot.querySelector('line.hitwall').getAttribute('stroke-width')), op: px(el.shadowRoot.querySelector('line.hitop').getAttribute('stroke-width')),
        corner: px(2 * el.shadowRoot.querySelector('circle.handle[data-k="v"]').getAttribute('r')), cornerOnTop: (() => { const c = el.shadowRoot.querySelector('circle.handle[data-k="v"]'), r = c.getBoundingClientRect(); return el.shadowRoot.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === c; })() };
    });
    expect(sizes.wall).toBeGreaterThanOrEqual(44);
    expect(sizes.op).toBeGreaterThanOrEqual(44);
    expect(sizes.corner).toBeGreaterThanOrEqual(44);
    expect(sizes.cornerOnTop).toBe(true);   // the corner handle stays reachable above the wide wall bands
    await editor.evaluate(el => { el._sel = null; el._mode = 'quick'; el._render(); });
    const at = (x, y) => editor.evaluate((el, [px, py]) => { const svg = el.shadowRoot.querySelector('svg'), p = svg.createSVGPoint(); p.x = px; p.y = -py; const q = p.matrixTransform(svg.getScreenCTM()); return [q.x, q.y]; }, [x, y]);
    const tapAt = async (x, y) => { const [cx, cy] = await at(x, y); await page.touchscreen.tap(cx, cy); return editor.evaluate(el => el._sel); };
    // on the bath's bottom wall: at the door → the door, beside it → the wall; from the bath's side → the bath's wall
    expect(await tapAt(2, 4.05)).toEqual({ type: 'opening', id: 'd_bad' });
    expect(await tapAt(3.6, 4.1)).toEqual({ type: 'wall', id: 'r_bad', index: 0 });
    expect(await tapAt(3.6, 3.9)).toEqual({ type: 'wall', id: 'r_flur', index: 2 });   // the same wall line, tapped from the hall
    // near the bath's corner: the closer of the two walls
    expect(await tapAt(0.12, 6)).toEqual({ type: 'wall', id: 'r_bad', index: 3 });
    expect(await tapAt(3.5, 7.88)).toEqual({ type: 'wall', id: 'r_bad', index: 2 });
    expect(await tapAt(2, 7.88)).toEqual({ type: 'opening', id: 'o_bad' });   // the window on that wall
    // no change to the plan from any of these taps
    expect(await editor.evaluate(el => el._history.past.length)).toBe(0);
  });
});

// ---- 0.26.6.0(6): room surfaces and labels, calm door swing, windows on interior walls ------------------------
const WC_LAYOUT = layout => ({ ...layout,
  rooms: [...layout.rooms, { id: 'r_wc', room_key: 'wc', floor_id: 'f_eg', polygon: [[8, 0], [10, 0], [10, 2], [8, 2]], provenance: 'user' }],
  // the guest WC window sits on the wall the WC shares with the hall (as a proposal without a free outside wall left it)
  openings: [...layout.openings, { id: 'o_wc', room_id: 'r_wc', edge: 3, offset: 0.5, width_m: 0.52, kind: 'window', mechanics: 'unknown', contacts: ['binary_sensor.wc_fenster'], provenance: 'unplaced' }] });

test('0.26.6.0(6) 1/2: a window on an interior wall is found and moved to the outside wall – editor, house map, save and reload', async ({ page }) => {
  await mount(page);
  await geo(page);
  await impl(page).evaluate((el, lay) => { el._layoutInfo = { ...el._layoutInfo, layout: lay }; el._render(); }, WC_LAYOUT(LAYOUT));
  expect(await page.evaluate(lay => window.G.windowOnInteriorWall(lay.rooms, lay.openings.find(o => o.id === 'o_wc')), WC_LAYOUT(LAYOUT))).toBe(true);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-edit]').click());
  await page.waitForFunction(() => document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor'));
  const editor = page.locator('freshairiq-house-layout-editor');
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('1 Fenster liegen an einer Innenwand');
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="windows_out"]').click());
  const moved = await editor.evaluate(el => el._layout.openings.find(o => o.id === 'o_wc'));
  expect([moved.edge, moved.offset, moved.width_m]).toEqual([0, 0.5, 0.52]);   // the nearest outside wall, centred, same width
  expect(await editor.evaluate(el => el.shadowRoot.textContent.includes('an einer Innenwand'))).toBe(false);
  expect(await editor.evaluate(el => el._history.past.length)).toBe(1);        // one step, undoable
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout);
  const o = saved.openings.find(x => x.id === 'o_wc');
  expect([o.edge, o.offset]).toEqual([0, 0.5]);
  expect(await page.evaluate(lay => window.G.windowOnInteriorWall(lay.rooms, lay.openings.find(x => x.id === 'o_wc')), saved)).toBe(false);
  // the house map with the saved plan: the window on the outside wall (y = 0) of the WC
  const line = await impl(page).evaluate((el, lay) => { el._editing = null; el._layoutInfo = { ...el._layoutInfo, layout: lay }; el._render();
    const l = el.shadowRoot.querySelector('line.op[data-opening="o_wc"]'); return ['x1', 'y1', 'x2', 'y2'].map(a => +(+l.getAttribute(a)).toFixed(2)); }, saved);
  expect(line[1]).toBe(0); expect(line[3]).toBe(0);
  expect(line[0]).toBeGreaterThan(8); expect(line[2]).toBeLessThan(10);
  // a window can also be moved on its own from its panel
  const one = await page.evaluate(async lay => {
    const ed = document.createElement('freshairiq-house-layout-editor'); document.body.appendChild(ed);
    ed.setup({ layout: lay, revision: 4, rooms: [], liveRooms: {}, language: 'de', floor: 'f_eg' });
    ed._sel = { type: 'opening', id: 'o_wc' }; ed._render();
    const had = !!ed.shadowRoot.querySelector('[data-a="window_out"]');
    ed.shadowRoot.querySelector('[data-a="window_out"]').click();
    return { had, edge: ed._layout.openings.find(x => x.id === 'o_wc').edge };
  }, WC_LAYOUT(LAYOUT));
  expect(one).toEqual({ had: true, edge: 0 });
});

// Order 10 (owner request): the swing arc is drawn in the editor only – the same quiet hint as before is checked there;
// on the house map the door keeps its leaf, without the arc
test('0.26.6.0(6) 3: the door swing is a quiet hint – thin, dashed, translucent – and still there', async ({ page }) => {
  await mount(page);
  expect(await impl(page).evaluate(el => [!!el.shadowRoot.querySelector('g.symbol.k-door line.leaf'), !!el.shadowRoot.querySelector('g.symbol.k-door path.arc')])).toEqual([true, false]);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-edit]').click());
  await page.waitForFunction(() => document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor'));
  const d = await page.locator('freshairiq-house-layout-editor').evaluate(el => {
    const g = [...el.shadowRoot.querySelectorAll('g.symbol')].find(x => x.querySelector('path.arc')), arc = g.querySelector('path.arc'), leaf = g.querySelector('line.leaf');
    return { arc: +arc.getAttribute('stroke-width'), leaf: +leaf.getAttribute('stroke-width'), opacity: +arc.getAttribute('stroke-opacity'), dash: !!arc.getAttribute('stroke-dasharray'), length: arc.getTotalLength(),
      rim: +(arc.previousElementSibling && arc.previousElementSibling.getAttribute('stroke-opacity')) };
  });
  expect(d.arc).toBeLessThanOrEqual(d.leaf / 2.5);   // a hairline next to the door leaf
  expect(d.opacity).toBeLessThanOrEqual(0.6);
  expect(d.rim).toBeLessThanOrEqual(0.3);
  expect(d.dash).toBe(true);
  expect(d.length).toBeGreaterThan(0);               // still visible
});

test('0.26.6.0(6) 4–8: no white boxes; labels readable and inside the room; size-dependent; the surface follows the state', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  const look = () => impl(page).evaluate(el => {
    const out = {};
    for (const p of el.shadowRoot.querySelectorAll('polygon.room')) {
      const id = p.dataset.room, rb = p.getBoundingClientRect(), tag = [...el.shadowRoot.querySelectorAll('.tag')].find(t => { const r = t.getBoundingClientRect(); return r.left >= rb.left - 1 && r.right <= rb.right + 1 && r.top >= rb.top - 1 && r.bottom <= rb.bottom + 1; });
      const rim = el.shadowRoot.querySelector(`polygon.rim[clip-path="url(#rc-${id})"]`);
      out[id] = { fill: p.getAttribute('fill'), inside: !!tag, big: (() => { const svg = el.shadowRoot.querySelector('svg.plan'), k = Number(svg.getAttribute('viewBox').split(' ')[2]) / svg.getBoundingClientRect().width, b = p.getBBox(); return b.width / k >= 120 && b.height / k >= 96; })(), rows: tag ? [...tag.querySelectorAll('text')].map(t => t.getAttribute('class')) : [],
        rim: !!rim, rimAnim: rim ? getComputedStyle(rim).animationName : null, hatch: !!el.shadowRoot.querySelector('polygon.hatch'),
        name: tag && tag.querySelector('text.n') ? tag.querySelector('text.n').getAttribute('fill') : null };
    }
    out.whiteBoxes = [...el.shadowRoot.querySelectorAll('.tag rect, .tag circle')].filter(n => ['rgb(244, 251, 255)', 'rgb(255, 255, 255)'].includes(getComputedStyle(n).fill)).length;
    return out;
  });
  let s = await look();
  expect(s.whiteBoxes).toBe(0);                                   // 4: the white boxes are gone
  // 5/6: every label sits inside its room; the large rooms carry name, state and readings, the bath name and state
  for (const id of ['r_bad', 'r_flur', 'r_wohnen']) expect(s[id].inside, id).toBe(true);
  // 0.26.6.0(7): readings are shown where they fit into the room's real outline (checked in the outline test) – name and
  // state always; the large hall carries the readings
  for (const id of ['r_bad', 'r_flur', 'r_wohnen']) expect(s[id].rows.slice(0, 2), id).toEqual(['n', 'a pill-t']);
  expect(s.r_flur.rows).toEqual(['n', 'a pill-t', 'c']);
  // 7: the surface follows the state – close (rim), act (rim), ok (calm, no rim)
  expect([s.r_bad.fill, s.r_wohnen.fill, s.r_flur.fill]).toEqual(['url(#rf-close)', 'url(#rf-act)', 'url(#rf-ok)']);
  expect([s.r_bad.rim, s.r_wohnen.rim, s.r_flur.rim]).toEqual([true, true, false]);
  expect(s.r_bad.rimAnim).toBe('rimglow');
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, action: 'Wait', house_aligned_action: 'wait' }, flur: { ...window.__ROOMS.flur, mould_level: 'Very high' } } }));
  await page.waitForTimeout(80);
  s = await look();
  expect([s.r_bad.fill, s.r_bad.rim, s.r_flur.fill, s.r_flur.hatch]).toEqual(['url(#rf-wait)', false, 'url(#rf-critical)', true]);
  // a tiny room shows only its state symbol
  const tiny = await impl(page).evaluate(el => { el._layoutInfo.layout.rooms.push({ id: 'r_tiny', room_key: 'flur', floor_id: 'f_eg', polygon: [[10.5, 0], [11.2, 0], [11.2, 0.6], [10.5, 0.6]], provenance: 'user' }); el._render();
    return [...el.shadowRoot.querySelectorAll('.tag')].some(t => t.querySelector('circle.dot') && !t.querySelector('text.n')); });
  expect(tiny).toBe(true);
  // 8: the label colour reads on its surface (contrast of text to both gradient stops ≥ 4:1)
  const V = await page.evaluate(async () => (await import('/freshairiq-house-view.js?v=t')).ROOM_TONES);
  const lum = hex => { const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
  const ratio = (x, y) => { const [a, b] = [lum(x), lum(y)].sort((p, q) => q - p); return (a + 0.05) / (b + 0.05); };
  for (const [tone, t] of Object.entries(V)) for (const stop of [t.top, t.bottom]) expect(ratio(t.text === 'dark' ? '#021024' : '#f4fbff', stop), `${tone} ${stop}`).toBeGreaterThanOrEqual(4);
});

test('0.26.6.0(6) 7b: with reduced motion the state rim does not glow and the rooms do not breathe', async ({ page }) => {
  await mount(page, { reducedMotion: 'reduce' });
  expect(await impl(page).evaluate(el => getComputedStyle(el.shadowRoot.querySelector('polygon.rim')).animationName)).toBe('none');
  expect(await impl(page).evaluate(el => getComputedStyle(el.shadowRoot.querySelector('polygon.room.t-close')).animationName)).toBe('none');
});

// ---- 0.26.6.0(7): every label inside its room's real outline; the local weather top right ----------------------
const LSHAPES = JSON.parse(fs.readFileSync(new URL('./fixtures/house_ground_floor_l_shapes.json', import.meta.url), 'utf8'));
const labelsOutside = page => impl(page).evaluate(el => {
  const svg = el.shadowRoot.querySelector('svg.plan'), inv = svg.getScreenCTM().inverse(), P = (x, y) => { const p = svg.createSVGPoint(); p.x = x; p.y = y; const q = p.matrixTransform(inv); return [q.x, -q.y]; };
  const inside = (pt, poly) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) c = !c; } return c; };
  const rooms = el._layoutInfo.layout.rooms.filter(r => r.floor_id === el._floor), tags = [...svg.querySelectorAll('.tag')], bad = [];
  rooms.forEach((r, i) => {
    const tag = tags[i]; if (!tag || tag.querySelector('circle.dot')) return;   // the state dot of a tiny room is the exception
    for (const n of tag.querySelectorAll('text, rect')) {
      const b = n.getBoundingClientRect();
      for (const [x, y] of [[b.left, b.top], [b.right, b.top], [b.left, b.bottom], [b.right, b.bottom]]) if (!inside(P(x, y), r.polygon)) { bad.push(`${r.id}: ${n.textContent || n.getAttribute('class')}`); break; }
    }
  });
  return { bad: [...new Set(bad)], dots: tags.filter(t => t.querySelector('circle.dot')).length, rooms: rooms.length };
});
const useLShapes = page => impl(page).evaluate((el, real) => {
  const lay = el._layoutInfo.layout; lay.rooms = [...real.rooms, lay.rooms.find(r => r.floor_id === 'f_og')]; lay.openings = []; lay.connections = [];
  const names = { schlaf: 'Schlafzimmer', kind: 'Kinderzimmer', badz: 'Badezimmer', arbeit: 'Arbeitszimmer', flureg: 'Flur EG', wc: 'Gäste WC', wohnkueche: 'Wohnküche' };
  for (const [k, n] of Object.entries(names)) el._rooms[k] = { ...el._rooms.flur, key: k, name: n, action: 'Wait', house_aligned_action: k === 'badz' || k === 'wohnkueche' ? 'ventilate_possible_hold' : 'wait' };
  el._render();
}, LSHAPES);

for (const width of [320, 390, 820]) {
  test(`0.26.6.0(7): names, states and readings stay inside the room's outline (L-shapes, small rooms) at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    let out = await labelsOutside(page);
    expect(out.bad).toEqual([]);                       // the L-shaped living room included
    await useLShapes(page);
    await page.waitForTimeout(80);
    out = await labelsOutside(page);
    expect(out.bad).toEqual([]);
    expect(out.rooms).toBe(7);
    // where the guest WC is too small for text it shows its state dot – at least 18 px across
    const dots = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.tag circle.dot')].map(c => c.getBoundingClientRect().width));
    for (const d of dots) expect(d).toBeGreaterThanOrEqual(18);
  });
}

test('0.26.6.0(7): local weather top right – FreshAirIQ outdoor values or own sensors – never over the plan', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  const chip = () => impl(page).evaluate(el => { const w = el.shadowRoot.querySelector('.weather'); if (!w) return null;
    const r = w.getBoundingClientRect(), card = el.shadowRoot.querySelector('ha-card').getBoundingClientRect(), plan = el.shadowRoot.querySelector('svg.plan').getBoundingClientRect();
    return { text: w.textContent, right: card.right - r.right < 20, top: r.top - card.top < 20, abovePlan: r.bottom <= plan.top + 1 }; });
  expect(await chip()).toBe(null);   // nothing known yet: nothing invented
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, outdoor_temperature: 7.43, outdoor_humidity: 86.4, weather_now: { outdoor_temperature: 7.4 } }));
  await page.waitForTimeout(60);
  expect(await chip()).toEqual({ text: '🌡️ 7,4 °C💧 86 %', right: true, top: true, abovePlan: true });
  // own sensors instead (the card option weather_sensors)
  await impl(page).evaluate(el => {
    el._hass = { ...el._hass, states: { 'sensor.garten_t': { entity_id: 'sensor.garten_t', state: '5.27', attributes: { unit_of_measurement: '°C', device_class: 'temperature', friendly_name: 'Garten' } },
      'sensor.garten_h': { entity_id: 'sensor.garten_h', state: '91.2', attributes: { unit_of_measurement: '%', device_class: 'humidity' } }, 'sensor.weg': { entity_id: 'sensor.weg', state: 'unavailable', attributes: {} } } };
    el._config = { ...el._config, weather_sensors: 'sensor.garten_t, sensor.garten_h, sensor.weg' }; el._render();
  });
  expect((await chip()).text).toBe('🌡️ 5,3 °C💧 91 %');   // an unavailable sensor is left out
  // the card settings carry the option
  const cfg = await page.evaluate(async () => {
    const ed = document.createElement('freshairiq-house-card-editor-impl') || null; if (!customElements.get('freshairiq-house-card-editor-impl')) return 'no editor';
    let seen = null; ed.addEventListener('config-changed', e => { seen = e.detail.config; }); ed.setConfig({}); document.body.appendChild(ed);
    const input = ed.querySelector('[data-k="weather_sensors"]'); input.value = 'sensor.a'; input.dispatchEvent(new Event('change')); return seen;
  });
  expect(cfg).toEqual({ weather_sensors: 'sensor.a' });
});

// ---- 0.26.6.0(7) (order 7): labels with readings, an atmosphere instead of a grid, climate, air and weather -------
const push = (page, extra) => page.evaluate(x => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, ...x }), extra);
// the windward bath window confirmed open: the wind streams in (inflow with particles)
const windward = page => impl(page).evaluate(el => {
  const ops = { ...el._house.airflow.openings, o_bad: { ...el._house.airflow.openings.o_bad, pending: false, state: 'open' } };
  el._house = { ...el._house, wind: { ...el._house.wind, from_deg: 0 }, airflow: { ...el._house.airflow, openings: ops } };
  el._windSmooth = 0; el._render();
});
const atmos = page => impl(page).evaluate(el => {
  const sr = el.shadowRoot, svg = sr.querySelector('svg.plan'), all = [...svg.querySelectorAll('*')];
  const first = sel => all.findIndex(n => n.matches(sel));
  return { grid: !!sr.querySelector('#grid') || !!svg.querySelector('[fill="url(#grid)"]'), sky: svg.querySelectorAll('g.sky rect').length,
    weather: svg.querySelector('g.weather') ? [...svg.querySelectorAll('g.weather .wx')].map(n => n.getAttribute('class').replace('wx ', '')) : null,
    mask: svg.querySelector('g.weather') ? svg.querySelector('g.weather').getAttribute('mask') : null,
    weatherBeforeRooms: first('g.weather') < first('polygon.room'), shadowFilter: svg.querySelector('g.house-shadow').getAttribute('filter'),
    skyTop: svg.querySelector('#sky stop').getAttribute('stop-color') };
});

test('order 7 / 2: no background grid – a sky; no weather drawn without weather data', async ({ page }) => {
  await mount(page);
  const s = await atmos(page);
  expect(s.grid).toBe(false);
  expect(s.sky).toBe(3);                         // ground colour, sky gradient, depth vignette
  expect(s.weather).toBe(null);                  // nothing known: nothing made up
  expect(s.shadowFilter).toBe('url(#soft)');      // a soft shadow instead of the hard comic offset
  expect(s.skyTop).toBe('#0f4479');               // without sun.sun: no day or night is assumed
});

test('order 7 / 5: weather around the house only from Home Assistant data – rain, snow, fog, clouds, thunder, sun, night', async ({ page }) => {
  await mount(page);
  const cases = [
    [{ condition: 'rainy', raining: true }, null, ['clouds', 'rain']],
    [{ condition: 'snowy', snowing: true }, null, ['clouds', 'snow']],
    [{ condition: 'fog' }, null, ['clouds', 'fog']],
    [{ condition: 'lightning-rainy', raining: true, thunder: true }, null, ['clouds', 'rain', 'flash']],
    [{ condition: 'sunny' }, { state: 'above_horizon', attributes: { elevation: 32, azimuth: 160 } }, ['sunlight']],
    [{ condition: 'sunny' }, null, null],                                   // sunny, but where the sun is is unknown: no rays
    [{ condition: 'clear-night' }, { state: 'below_horizon', attributes: { elevation: -20, azimuth: 340 } }, ['stars']],
    [{ condition: 'partlycloudy' }, { state: 'above_horizon', attributes: { elevation: 2, azimuth: 250 } }, ['sunlight', 'clouds']],  // twilight glow
  ];
  for (const [now, sun, expected] of cases) {
    await impl(page).evaluate((el, sun) => { el._hass = { ...el._hass, states: sun ? { 'sun.sun': { entity_id: 'sun.sun', ...sun } } : {} }; }, sun);
    await push(page, { weather_now: now });
    await page.waitForTimeout(60);
    const s = await atmos(page);
    expect(s.weather, JSON.stringify(now)).toEqual(expected);
    if (expected) { expect(s.mask).toBe('url(#wx-out)'); expect(s.weatherBeforeRooms).toBe(true); }   // never over rooms and labels
    if (sun && sun.attributes.elevation < -6) expect(s.skyTop).toBe('#0a1630');   // night (owner request: night more visible – darker night sky, was #0c1a36)                      // night
  }
  // rain falls slanted with the wind (5 m/s → 25°); calm → straight
  await push(page, { weather_now: { condition: 'rainy', raining: true } });
  await page.waitForTimeout(60);
  const tilt = () => impl(page).evaluate(el => el.shadowRoot.querySelector('g.wx.rain').getAttribute('transform').match(/rotate\(([-\d.]+)/)[1]);
  expect(Math.abs(Number(await tilt()))).toBeCloseTo(25, 0);
  await page.evaluate(() => window.__subs['freshairiq/house_map/subscribe']({ ...window.__HOUSE, revision: 3, wind: { ...window.__HOUSE.wind, speed_ms: 0 } }));
  await page.waitForTimeout(60);
  expect(Number(await tilt())).toBe(0);
});

test('order 7 / 3: the rooms show their climate at rest – warm/cool, humid (rising)/dry, mould risk, moisture source, fan', async ({ page }) => {
  await mount(page);
  await push(page, { rooms: { ...await page.evaluate(() => window.__ROOMS),
    bad: { ...await page.evaluate(() => window.__ROOMS.bad), temperature: 25, humidity: 76, humidity_trend_pct_h: 6, mould_level: 'High', moisture_source_active: true,
      configured_actuators: { mechanical_exhaust_active: true } },
    flur: { ...await page.evaluate(() => window.__ROOMS.flur), temperature: 17.5, humidity: 30, humidity_trend_pct_h: 0, mould_level: 'Low' },
    wohnen: { ...await page.evaluate(() => window.__ROOMS.wohnen), temperature: 21, humidity: 50, humidity_trend_pct_h: 0, mould_level: 'Slightly elevated' } } });
  await page.waitForTimeout(80);
  const cl = await impl(page).evaluate(el => Object.fromEntries([...el.shadowRoot.querySelectorAll('g.climate')].map(g => [g.getAttribute('clip-path').slice(5, -1),
    [...g.children].map(n => n.getAttribute('class'))])));
  expect(cl['rc-r_bad']).toEqual(['cl warm', 'cl mist rising', 'cl mould m-3', 'steam']);
  expect(cl['rc-r_flur']).toEqual(['cl cool', 'cl dry']);
  expect(cl['rc-r_wohnen']).toEqual(['cl mould m-1']);                       // neutral climate: only the slight mould risk
  const fan = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('g.fan')].map(f => f.getAttribute('aria-label')));
  expect(fan).toEqual(['Ablüfter läuft']);
  // rising humidity is also written next to the reading
  expect(await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.tag text.c')].some(t => t.textContent.includes('% ↑')))).toBe(true);
  // stale readings: no climate is shown (nothing invented)
  await push(page, { rooms: { ...await page.evaluate(() => window.__ROOMS), bad: { ...await page.evaluate(() => window.__ROOMS.bad), temperature: 26, humidity: 80, data_quality: 'stale', mould_level: 'Low' } } });
  await page.waitForTimeout(80);
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('g.climate[clip-path="url(#rc-r_bad)"]'))).toBe(false);
  const A = await page.evaluate(async () => { const A = await import('/freshairiq-house-atmos.js?v=t');
    return [A.roomClimate({ temperature: 21.9, humidity: 58 }), A.roomClimate({ temperature: 25, humidity: 80, humidity_trend_pct_h: 2.9 }), A.roomClimate(null),
      A.skyState({}, null), A.skyState({ condition: 'clear-night' }, null).phase, A.skyState({ condition: 'sunny' }, { state: 'above_horizon', attributes: {} }).phase]; });
  // order 8 (requirement: a measured drying is shown): roomClimate also reports `falling`
  expect(A[0]).toEqual({ temp: 0, humid: 0, dry: 0, rising: false, falling: false, mould: 0, source: false, fan: false });
  expect([A[1].temp, A[1].humid, A[1].rising]).toEqual([1, 1, false]);
  expect(A[2]).toBe(null);
  expect([A[3].phase, A[3].rain, A[3].clouds, A[3].azimuth]).toEqual([null, false, 0, null]);
  expect([A[4], A[5]]).toEqual(['night', 'day']);
});

test('order 7 / 4: fresh air at open windows – deep when open, short when tilted, none while unconfirmed, fading after closing', async ({ page }) => {
  await mount(page);
  const plumes = () => impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('g.plume')].map(g => `${g.dataset.plume} ${g.getAttribute('class')}`));
  expect(await plumes()).toEqual(['o_wohnen plume tilted']);                 // o_bad is still pending (opening delay)
  // particles travel with every inflow stream into the room
  await windward(page);
  await page.waitForTimeout(80);
  // order 8 (requirement change): the particles of the incoming air moved from SVG dots to the canvas air layer – one
  // route of threads per inflow stream
  const parts = await impl(page).evaluate(el => ({ particles: el._flowLayer.routes.length, inflow: el.shadowRoot.querySelectorAll('path.stream.inflow').length }));
  expect(parts.inflow).toBeGreaterThan(0);
  expect(parts.particles).toBe(parts.inflow);
  expect(await plumes()).toEqual(['o_bad plume', 'o_wohnen plume tilted']);
  const set = state => impl(page).evaluate((el, state) => {
    const ops = { ...el._house.airflow.openings, o_bad: { ...el._house.airflow.openings.o_bad, state: 'closed' }, o_wohnen: { ...el._house.airflow.openings.o_wohnen, state } };
    el._house = { ...el._house, airflow: { ...el._house.airflow, openings: ops } }; el._render(); }, state);
  await set('open');
  await page.waitForTimeout(80);
  expect(await plumes()).toEqual(['o_bad plume fade', 'o_wohnen plume']);   // the bath window was just closed
  await set('closed');
  await page.waitForTimeout(80);
  expect(await plumes()).toEqual(['o_bad plume fade', 'o_wohnen plume fade']);   // the air fades out instead of vanishing
  await impl(page).evaluate(el => { el._airSeen.o_wohnen.at -= 5000; el._airSeen.o_bad.at -= 5000; el._render(); });
  expect(await plumes()).toEqual([]);
});

test('order 7 / 1: Schlafzimmer and Badezimmer keep their readings; labels avoid door swings; the guest WC has an understandable label', async ({ page }) => {
  for (const width of [390, 820]) {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await useLShapes(page);
    await page.waitForTimeout(80);
    const rows = await impl(page).evaluate(el => {
      const rooms = el._layoutInfo.layout.rooms.filter(r => r.floor_id === el._floor), tags = [...el.shadowRoot.querySelectorAll('.tag')];
      return Object.fromEntries(rooms.map((r, i) => [r.room_key, { rows: [...tags[i].querySelectorAll('text')].map(t => t.getAttribute('class').split(' ')[0]), names: [...tags[i].querySelectorAll('text.n')].map(t => t.textContent), title: (tags[i].querySelector('title') || {}).textContent }]));
    });
    for (const key of ['schlaf', 'badz']) expect(rows[key].rows.filter(c => c === 'c').length, `${key} @${width}`).toBeGreaterThanOrEqual(1);
    // order 8 (requirement: names as complete as possible): the full name may also stand in two rows, after the state symbol
    const wcName = rows.wc.names.join(' ').replace(/^\S+\s(?=\S)/u, m => (/[A-Za-zÄÖÜäöü]/.test(m) ? m : ''));
    expect(rows.wc.names.length === 0 || ['WC', 'Gäste WC'].includes(wcName), JSON.stringify(rows.wc)).toBe(true);
    expect(rows.wc.title).toBe('Gäste WC');                                   // the full name is always there
    expect((await labelsOutside(page)).bad).toEqual([]);
  }
  // order 10: the house map draws no swing arc any more (editor only) – a label never lies on the door leaf
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  const hit = await impl(page).evaluate(el => {
    const arc = el.shadowRoot.querySelector('g.symbol.k-door line.leaf').getBoundingClientRect();
    return [...el.shadowRoot.querySelectorAll('.tag text, .tag rect')].filter(n => { const b = n.getBoundingClientRect(); return b.left < arc.right && b.right > arc.left && b.top < arc.bottom && b.bottom > arc.top; }).length;
  });
  expect(hit).toBe(0);
  const short = await page.evaluate(async () => { const m = await import('/freshairiq-house-card.js?v=t'); return ['Gäste-WC', 'Gäste WC', 'Kinderzimmer Nord', 'Badezimmer', 'Abstellraum Keller'].map(m.shortName); });
  expect(short).toEqual(['WC', 'WC', 'Nord', 'Badezimmer', 'Abstellraum Keller']);
});

test('order 7 / 10: weather, climate and air pause with the card, stop with "reduce motion" and with the animation off', async ({ page }) => {
  const anim = sel => impl(page).evaluate((el, sel) => { const n = el.shadowRoot.querySelector(sel); return n ? { name: getComputedStyle(n).animationName, state: getComputedStyle(n).animationPlayState } : null; }, sel);
  const busy = async () => { await windward(page); await push(page, { weather_now: { condition: 'snowy', snowing: true }, rooms: { ...await page.evaluate(() => window.__ROOMS), bad: { ...await page.evaluate(() => window.__ROOMS.bad), humidity: 80, moisture_source_active: true } } });
    await expect.poll(() => impl(page).evaluate(el => !!el.shadowRoot.querySelector('.wx .fall') && !!el.shadowRoot.querySelector('.steam path'))).toBe(true); };   // under load: wait for the drawing, not a fixed time
  await mount(page);
  await busy();
  // order 8: 'path.particles' moved to the canvas air layer – its pause and stillness are checked in 'order 8 / 9'
  for (const sel of ['.wx .fall', '.cl.mist', '.steam path', 'g.plume']) expect((await anim(sel)).name, sel).not.toBe('none');
  await impl(page).evaluate(el => el.setAttribute('data-paused', ''));
  for (const sel of ['.wx .fall', '.cl.mist', '.steam path', 'g.plume']) expect((await anim(sel)).state, sel).toBe('paused');
  await mount(page, { reducedMotion: 'reduce' });
  await busy();
  for (const sel of ['.wx .fall', '.cl.mist', '.steam path', 'g.plume', 'polygon.room']) expect((await anim(sel)).name, sel).toBe('none');
  await mount(page, { config: { animation: false } });
  await busy();
  for (const sel of ['.wx .fall', '.cl.mist', 'g.plume', 'polygon.room']) expect((await anim(sel)).name, sel).toBe('none');
});

test('order 7 / 7+10: a calm palette (no yellow rooms), slim walls, and 40 rooms with weather draw quickly', async ({ page }) => {
  await mount(page);
  const V = await page.evaluate(async () => (await import('/freshairiq-house-view.js?v=t')).ROOM_TONES);
  const sat = hex => { const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)); return (Math.max(...c) - Math.min(...c)) / Math.max(...c); };
  const hue = hex => { const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255), mx = Math.max(r, g, b), d = mx - Math.min(r, g, b);
    return d === 0 ? 0 : ((mx === r ? (g - b) / d % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4) * 60 + 360) % 360; };
  for (const [tone, t] of Object.entries(V)) expect(hue(t.top) > 35 && hue(t.top) < 75 && sat(t.top) > 0.3, `${tone} is no yellow`).toBe(false);
  for (const tone of ['ok', 'wait', 'sensor']) expect(sat(V[tone].top), tone).toBeLessThan(0.7);   // calm base surfaces
  expect(V.wait.top).not.toBe(V.close.top);
  const walls = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('line.wall.outer')].map(l => l.getBoundingClientRect()).map(b => Math.min(b.width, b.height)).filter(v => v > 0));
  expect(Math.max(...walls)).toBeLessThanOrEqual(6);
  const ms = await impl(page).evaluate(el => {
    const lay = el._layoutInfo.layout;
    for (let i = 0; i < 40; i++) { lay.rooms.push({ id: `p${i}`, room_key: i % 2 ? 'bad' : 'flur', floor_id: 'f_eg', polygon: [[12 + (i % 8) * 3, (i >> 3) * 3], [15 + (i % 8) * 3, (i >> 3) * 3], [15 + (i % 8) * 3, 3 + (i >> 3) * 3], [12 + (i % 8) * 3, 3 + (i >> 3) * 3]], provenance: 'user' }); }
    el._payload = { ...el._payload, weather_now: { condition: 'rainy', raining: true } };
    const t0 = performance.now(); el._render(); return performance.now() - t0;
  });
  expect(ms).toBeLessThan(1500);
});

test('order 7 / night: night and twilight from sun.sun – dim veil over the rooms under the labels, stars by cloud cover, none by day', async ({ page }) => {
  await mount(page);
  const look = async (sun, condition) => {
    await impl(page).evaluate((el, sun) => { el._hass = { ...el._hass, states: sun ? { 'sun.sun': { entity_id: 'sun.sun', ...sun } } : {} }; }, sun);
    await push(page, { weather_now: { condition } });
    await page.waitForTimeout(60);
    return impl(page).evaluate(el => {
      const svg = el.shadowRoot.querySelector('svg.plan'), all = [...svg.querySelectorAll('*')], veil = svg.querySelector('g.night-veil');
      return { veil: veil ? veil.getAttribute('class') : null, polys: veil ? veil.querySelectorAll('polygon').length : 0, rooms: svg.querySelectorAll('polygon.room').length,
        underLabels: veil ? all.indexOf(veil) < all.findIndex(n => n.matches('.tag')) && all.indexOf(veil) < all.findIndex(n => n.matches('line.wall')) : null,
        stars: svg.querySelectorAll('.wx.stars circle').length };
    });
  };
  const night = { state: 'below_horizon', attributes: { elevation: -25, azimuth: 0 } };
  let s = await look(night, 'clear-night');
  expect([s.veil, s.polys === s.rooms, s.underLabels, s.stars]).toEqual(['night-veil night', true, true, 34]);
  expect((await look(night, 'partlycloudy')).stars).toBe(12);
  expect((await look(night, 'cloudy')).stars).toBe(0);
  s = await look({ state: 'above_horizon', attributes: { elevation: 1, azimuth: 250 } }, 'cloudy');
  expect(s.veil).toBe('night-veil twilight');
  s = await look({ state: 'above_horizon', attributes: { elevation: 30, azimuth: 180 } }, 'sunny');
  expect([s.veil, s.stars]).toEqual([null, 0]);
  expect((await look(null, 'clear-night')).veil).toBe('night-veil night');   // HA's own night condition
  expect((await look(null, 'sunny')).veil).toBe(null);                       // unknown: no night is assumed
  // labels stay readable at night: light text on the veiled surface
  await look(night, 'clear-night');
  expect(await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.tag text.n')].every(t => t.getAttribute('fill') === '#f4fbff'))).toBe(true);
});

// ---- 0.26.6.0 (order 8): regression – readings and full names in small rooms with doors and windows ------------
// Cause: the 8th build kept the swing of every door and the sash area of every window (also closed ones) free; in
// small rooms only the poorest label variants were left (no readings, "Arbeitszim…", "Bad…").
const L_OPENINGS = [
  { id: 'w_sz', room_id: 'r_sz', edge: 3, offset: 0.5, width_m: 1.2, kind: 'window', contacts: [] },
  { id: 'w_kz', room_id: 'r_kz', edge: 2, offset: 0.5, width_m: 1.2, kind: 'window', contacts: [] },
  { id: 'w_bz', room_id: 'r_bz', edge: 1, offset: 0.5, width_m: 0.8, kind: 'window', contacts: [] },
  { id: 'w_az', room_id: 'r_az', edge: 3, offset: 0.5, width_m: 1.0, kind: 'window', contacts: [] },
  { id: 'd_az', room_id: 'r_az', edge: 1, offset: 0.5, width_m: 0.9, kind: 'door', contacts: [] },
  { id: 'd_kz', room_id: 'r_kz', edge: 0, offset: 0.3, width_m: 0.9, kind: 'door', contacts: [] },
  { id: 'd_bz', room_id: 'r_bz', edge: 3, offset: 0.5, width_m: 0.8, kind: 'door', contacts: [] },
  { id: 'd_sz', room_id: 'r_sz', edge: 1, offset: 0.7, width_m: 0.9, kind: 'door', contacts: [] },
];
for (const width of [360, 390, 430, 820]) {
  test(`order 8 / 1: Arbeits-, Kinder- and Badezimmer keep readings and full names with doors and windows at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await useLShapes(page);
    const rows = await impl(page).evaluate((el, ops) => {
      el._layoutInfo.layout.openings = ops;
      for (const k of ['arbeit', 'kind', 'badz']) el._rooms[k] = { ...el._rooms[k], action: 'Ventilate', house_aligned_action: 'ventilate_possible_hold' };
      el._render();
      const rooms = el._layoutInfo.layout.rooms.filter(r => r.floor_id === el._floor), tags = [...el.shadowRoot.querySelectorAll('.tag')];
      return Object.fromEntries(rooms.map((r, i) => [r.room_key, { names: [...tags[i].querySelectorAll('text.n')].map(t => t.textContent), readings: tags[i].querySelectorAll('text.c').length }]));
    }, L_OPENINGS);
    for (const key of ['schlaf', 'kind', 'badz', 'arbeit', 'flureg', 'wohnkueche']) {
      expect(rows[key].readings, `${key} @${width}`).toBeGreaterThanOrEqual(1);
      expect(rows[key].names.join(' '), `${key} @${width}`).not.toContain('…');
    }
    const full = n => n.join('').replace(/^\S+\s/, '').replace('-', '');   // without the state symbol, rows joined
    expect(full(rows.arbeit.names)).toBe('Arbeitszimmer');
    expect(full(rows.badz.names)).toBe('Badezimmer');
    expect((await labelsOutside(page)).bad).toEqual([]);
  });
}

test('order 8 / 1b: compound names break sensibly; closed windows take no label space', async ({ page }) => {
  await mount(page);
  const out = await page.evaluate(async () => { const m = await import('/freshairiq-house-card.js?v=t');
    return ['Arbeitszimmer', 'Badezimmer', 'Wohnküche', 'Flur EG', 'Gäste-WC', 'Bad', 'Küche', 'Hauswirtschaftsraum'].map(m.splitName); });
  expect(out).toEqual([['Arbeits-', 'zimmer'], ['Bade-', 'zimmer'], ['Wohn-', 'küche'], ['Flur', 'EG'], ['Gäste-', 'WC'], null, null, ['Hauswirtschafts-', 'raum']]);
  const blocks = await impl(page).evaluate(el => {
    const lay = el._layoutInfo.layout, rooms = lay.rooms.filter(r => r.floor_id === 'f_eg');
    const ops = state => lay.openings.map(o => ({ ...o, state: o.kind === 'window' ? state : 'closed' }));
    return [el._labelBlocks(rooms, ops('closed'), n => n).length, el._labelBlocks(rooms, ops('tilted'), n => n).length, el._labelBlocks(rooms, ops('open'), n => n).length];
  });
  expect(blocks[0]).toBe(blocks[1]);                 // closed and tilted windows: only the door swings
  expect(blocks[2]).toBeGreaterThan(blocks[0]);      // open sashes are kept free
});
// ---- order 8: the wind field, the visible air and the moisture corner ----------------------------------------
const flowModule = async page => { await geo(page); return page.evaluate(async () => { window.__F = await import('/freshairiq-house-flow.js?v=0.26.6.0'); return true; }); };
const setWind = (page, wind) => impl(page).evaluate((el, wind) => { el._house = { ...el._house, wind: { ...el._house.wind, ...wind } }; if (wind.from_deg != null) el._windSmooth = wind.from_deg; el._render(); }, wind);

test('order 8 / 2: the wind field – slowed and turned at windward walls, calmer wake, nothing inside, no wind without data', async ({ page }) => {
  await mount(page);
  await flowModule(page);
  const r = await page.evaluate(() => {
    const F = window.__F, G = window.G, rooms = [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }];
    const field = F.buildField({ rooms, G, wind: { available: true, from_deg: 0, speed_ms: 5 }, northDeg: 0 });   // from north: air moves south
    const v = (x, y) => F.velocity(field, x, y, 0, [], 0);
    const free = v(-30, 30), front = v(5, 6.3), wake = v(5, -4), inside = v(5, 3);
    const none = F.buildField({ rooms, G, wind: { available: false, from_deg: 0, speed_ms: 5 }, northDeg: 0 });
    return { vis: field.vis, free, front, wake, inside, none, cls: [0, 1, 4, 9].map(F.strengthClass) };
  });
  expect(r.inside).toBe(null);
  expect(r.none).toBe(null);                                         // no wind data: no wind is drawn
  expect(r.cls).toEqual(['calm', 'weak', 'moderate', 'strong']);
  expect(Math.hypot(...r.free) / r.vis).toBeGreaterThan(0.8);        // undisturbed far away
  expect(Math.abs(r.front[1]) / r.vis).toBeLessThan(0.35);           // in front of the north wall: hardly any air into it …
  expect(Math.abs(r.front[0]) / r.vis).toBeGreaterThan(0.15);        // … it is turned along the wall
  expect(Math.hypot(...r.wake)).toBeLessThan(Math.hypot(...r.free)); // calmer behind the house
});

test('order 8 / 2.2–2.4: eddies come and go at the separating corners, stronger with stronger wind; gusts are events, measured when known', async ({ page }) => {
  await mount(page);
  await flowModule(page);
  const r = await page.evaluate(() => {
    const F = window.__F, G = window.G, rooms = [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }];
    const f = s => F.buildField({ rooms, G, wind: { available: true, from_deg: 270, speed_ms: s }, northDeg: 0 });
    const share = field => { let on = 0; for (let t = 0; t < 240; t += 0.5) if (F.eddiesAt(field, t).length) on++; return on / 480; };
    const peak = field => { let m = 0; for (let t = 0; t < 240; t += 0.5) for (const e of F.eddiesAt(field, t)) m = Math.max(m, Math.abs(e.gamma) / field.vis); return m; };
    const weak = f(2), mod = f(5), strong = f(10), calm = f(0.2);
    // the air turns around an eddy
    let t = 0; for (; t < 240; t += 0.5) if (F.eddiesAt(mod, t).some(e => e.life > 0.4 && e.life < 0.6)) break;
    const e = F.eddiesAt(mod, t).find(x => x.life > 0.4 && x.life < 0.6), d = e.rc * 0.8;
    const around = [[d, 0], [0, d], [-d, 0], [0, -d]].map(([dx, dy]) => { const v = F.velocity(mod, e.x + dx, e.y + dy, t, [e], 0), w = F.velocity(mod, e.x + dx, e.y + dy, t, [], 0); return v && w ? (dx * (v[1] - w[1]) - dy * (v[0] - w[0])) : 0; });
    const gusts = []; for (let t = 0; t < 120; t += 0.25) gusts.push(F.gustAt(mod, t));
    const measured = F.buildField({ rooms, G, wind: { available: true, from_deg: 270, speed_ms: 5, gust_ms: 9 }, northDeg: 0 });
    return { shares: [share(weak), share(mod), share(strong), share(calm)], peaks: [peak(weak), peak(mod), peak(strong)], corners: mod.corners.length,
      spin: around.every(x => Math.sign(x) === Math.sign(around[0]) && x !== 0), gustMax: Math.max(...gusts), gustQuiet: gusts.filter(g => g === 0).length / gusts.length,
      gust: [mod.gust.measured, mod.gust.amp, measured.gust.measured, +measured.gust.amp.toFixed(2), calm.gust.amp] };
  });
  expect(r.corners).toBe(2);
  expect(r.shares[3]).toBe(0);                                  // calm: no eddies
  for (const sh of r.shares.slice(0, 3)) { expect(sh).toBeGreaterThan(0); expect(sh).toBeLessThan(1); }   // occasional, never permanent
  expect(r.peaks[2]).toBeGreaterThan(r.peaks[0]);                // stronger wind: stronger eddies
  expect(r.spin).toBe(true);                                     // the air really turns around the eddy
  expect(r.gustMax).toBeGreaterThan(0.8);                        // a gust rises to its peak …
  expect(r.gustQuiet).toBeGreaterThan(0.4);                      // … and most of the time there is none
  expect(r.gust).toEqual([false, 0.15, true, 0.8, 0]);           // decorative 15 % without a measured gust; measured 9 / 5 m/s
});

test('order 8 / 3: the route through the house is narrow at the window and the doors and widens in the rooms; tilted is narrower', async ({ page }) => {
  await mount(page);
  await flowModule(page);
  const r = await page.evaluate(() => {
    const F = window.__F, G = window.G;
    const rooms = [{ id: 'a', polygon: [[0, 0], [6, 0], [6, 5], [0, 5]] }, { id: 'b', polygon: [[6, 0], [12, 0], [12, 5], [6, 5]] }];
    const pts = [[-8, 2.5], [0, 2.5], [3, 2.5], [6, 2.5], [9, 2.5], [12, 2.5], [16, 2.5]];
    const open = F.routeProfile(pts, rooms, G, { openingHalf: 0.45, step: 0.1 }), tilt = F.routeProfile(pts, rooms, G, { openingHalf: 0.45, tilted: true, step: 0.1 });
    const at = (p, x) => p.frame.reduce((b, q) => (Math.abs(q.p[0] - x) < Math.abs(b.p[0] - x) ? q : b));
    return { necks: open.necks.length, win: at(open, 0).w, room: at(open, 3).w, door: at(open, 6).w, room2: at(open, 9).w, tiltWin: at(tilt, 0).w, tiltRoom: at(tilt, 3).w,
      inside: F.routePoint(open, 17, 0.9)[2] };
  });
  expect(r.necks).toBe(3);                                      // into the house, from room to room, out again
  expect(r.win).toBeLessThan(0.6);
  expect(r.room).toBeGreaterThan(r.win * 2.5);                  // fans out in the room
  expect(r.door).toBeLessThan(r.room / 2);                      // narrows at the door
  expect(r.room2).toBeGreaterThan(r.door * 2);
  expect(r.tiltWin).toBeLessThan(r.win);
  expect(r.inside).toBe(1);
});

const canvasState = page => impl(page).evaluate(el => {
  const cv = el.shadowRoot.querySelector('canvas.flow'), svg = el.shadowRoot.querySelector('svg.plan');
  if (!cv) return null;
  const a = cv.getBoundingClientRect(), b = svg.getBoundingClientRect(), ctx = cv.getContext('2d'), data = ctx.getImageData(0, 0, cv.width, cv.height).data;
  let ink = 0; for (let i = 3; i < data.length; i += 16) if (data[i] > 0) ink++;
  // label boxes stay clear
  const L = el._flowLayer; let onLabels = 0;
  for (const box of L.clearPx) { const d = ctx.getImageData(Math.max(0, box.x + 4), Math.max(0, box.y + 4), Math.max(1, box.w - 8), Math.max(1, box.h - 8)).data; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) onLabels++; }
  return { over: Math.abs(a.left - b.left) < 1.5 && Math.abs(a.top - b.top) < 1.5 && Math.abs(a.width - b.width) < 1.5, ink, onLabels, n: L.n, routes: L.routes.map(r => r.parts.length), fading: L.fading.length, inside: L.stats.inside, t: L.t, cls: L.field && L.field.cls };
});

test('order 8 / 2+3: the canvas air lies exactly over the plan, draws threads outside, keeps labels clear, flows in through an open window', async ({ page }) => {
  const errors = await mount(page);
  await page.waitForTimeout(1200);
  let s = await canvasState(page);
  expect(s.over).toBe(true);
  expect(s.ink).toBeGreaterThan(50);                            // threads are drawn
  expect(s.onLabels).toBe(0);                                   // never over a name, state or value
  expect(s.routes).toEqual([]);                                 // windows closed or unconfirmed: no air in the house
  await windward(page);
  await page.waitForTimeout(1500);
  s = await canvasState(page);
  expect(s.routes.length).toBeGreaterThan(0);
  expect(s.inside).toBeGreaterThan(0);                          // threads inside the rooms
  expect(s.onLabels).toBe(0);
  // after closing the air fades out over a few seconds
  await impl(page).evaluate(el => { const ops = { ...el._house.airflow.openings, o_bad: { ...el._house.airflow.openings.o_bad, state: 'closed' }, o_wohnen: { ...el._house.airflow.openings.o_wohnen, state: 'closed' } }; el._house = { ...el._house, airflow: { ...el._house.airflow, openings: ops } }; el._render(); });
  s = await canvasState(page);
  expect([s.routes.length, s.fading > 0]).toEqual([0, true]);
  await page.waitForTimeout(4600);
  expect((await canvasState(page)).fading).toBe(0);
  expect(errors).toEqual([]);
});

test('order 8 / 2.4: wind strength changes the density; no wind data – no air layer; tilted lets less air in', async ({ page }) => {
  await mount(page);
  const n = [];
  for (const speed of [1.5, 5, 11]) { await setWind(page, { speed_ms: speed, from_deg: 307 }); n.push((await canvasState(page)).n); }
  expect(n[0]).toBeLessThan(n[1]); expect(n[1]).toBeLessThan(n[2]);
  await setWind(page, { available: false });
  expect(await canvasState(page)).toBe(null);
  await setWind(page, { available: true, from_deg: 0, speed_ms: 5 });
  await impl(page).evaluate(el => { const ops = { ...el._house.airflow.openings, o_bad: { ...el._house.airflow.openings.o_bad, pending: false, state: 'tilted' } }; el._house = { ...el._house, airflow: { ...el._house.airflow, openings: ops } }; el._render(); });
  const tilted = (await canvasState(page)).routes;
  await windward(page);
  const open = (await canvasState(page)).routes;
  expect(Math.max(...tilted)).toBeLessThan(Math.max(...open));
});

test('order 8 / 9: the air pauses with the card and stands still with reduced motion or the animation off; 40 rooms stay fast', async ({ page }) => {
  await mount(page);
  await page.waitForTimeout(300);
  await impl(page).evaluate(el => el.setAttribute('data-paused', ''));
  const t0 = (await canvasState(page)).t; await page.waitForTimeout(400);
  expect((await canvasState(page)).t).toBe(t0);                 // paused: the air does not move on
  await mount(page, { reducedMotion: 'reduce' });
  await page.waitForTimeout(300);
  const a = await canvasState(page); await page.waitForTimeout(500); const b = await canvasState(page);
  expect(a.ink).toBeGreaterThan(0);                             // a calm, still picture of the streamlines …
  expect([b.t, b.ink]).toEqual([a.t, a.ink]);                   // … that does not move
  await mount(page, { config: { animation: false } });
  await page.waitForTimeout(300);
  const c = await canvasState(page); await page.waitForTimeout(400);
  expect((await canvasState(page)).t).toBe(c.t);
  await mount(page);
  const ms = await impl(page).evaluate(el => {
    const lay = el._layoutInfo.layout;
    for (let i = 0; i < 40; i++) lay.rooms.push({ id: `q${i}`, room_key: 'flur', floor_id: 'f_eg', polygon: [[12 + (i % 8) * 3, (i >> 3) * 3], [15 + (i % 8) * 3, (i >> 3) * 3], [15 + (i % 8) * 3, 3 + (i >> 3) * 3], [12 + (i % 8) * 3, 3 + (i >> 3) * 3]], provenance: 'user' });
    el._render();
    const L = el._flowLayer, t0 = performance.now(); for (let k = 0; k < 20; k++) L.frame(0.033); return (performance.now() - t0) / 20;
  });
  expect(ms).toBeLessThan(40);                                  // per frame, generous for a shared test machine
});

// Order 9 (owner requirement change): "removable now" top left must be exactly the FreshAirIQ card's value. The
// order-8 expectations (theoretical house value, 5-minute rounding, room sum fallback) are replaced by this
// comparison against the rendered dashboard card – the house map now calls the card's own function (removableNow).
const classicFacts = (page, payload) => page.evaluate(async payload => {
  // the real FreshAirIQ dashboard card class (the very module file the house map loads), under a test tag
  if (!customElements.get('faiq-classic-test')) customElements.define('faiq-classic-test', (await import('/freshairiq-card.js?v=0.26.6.0')).FreshAirIQCard);
  let card = document.getElementById('classic');
  if (!card) { card = document.createElement('faiq-classic-test'); card.id = 'classic'; document.body.appendChild(card); card.setConfig({ dashboard_variant: 'iq' }); }
  card.hass = { states: { 'sensor.freshairiq_status': { entity_id: 'sensor.freshairiq_status', state: String(payload.status || 'ok'),
    attributes: { freshairiq_transport: 'status_v2', freshairiq_entry_id: 'e1', room_sort_order: Object.keys(payload.rooms || {}), night_start_hour: '23:59', night_end_hour: '00:00', ...payload } } }, language: 'de', locale: { language: 'de' } };
  await new Promise(r => setTimeout(r, 150));
  const facts = card.shadowRoot && card.shadowRoot.querySelector('.ai-compact .ai-facts');
  return facts ? facts.textContent.replace(/\s+/g, ' ').trim() : 'NOFACTS';
}, payload);
const houseFacts = page => impl(page).evaluate(el => { const c = el.shadowRoot.querySelector('.moist'); return c ? c.textContent.replace(/\s+/g, ' ').trim() : null; });
const numbers = text => (String(text || '').match(/\d+/g) || []).map(Number);

test('order 9 / 1: removable now top left is exactly the FreshAirIQ card value – idle, airing, waiting, nothing, missing', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));   // the card module the house map uses
  const rooms = await page.evaluate(() => window.__ROOMS);
  const cases = [
    ['idle, ventilate', { rooms, status: 'ventilate', potential_total_ml: 1947.4, live_balance_ml: 0, recommended_duration_min: 12, remaining_duration_min: 12, prognosis_confidence: 70 }, '💧 ≈ 1947 ml ⏱ in 12 Min.'],
    ['rounding', { rooms, status: 'ventilate', potential_total_ml: 1946.5, recommended_duration_min: 7.4 }, '💧 ≈ 1947 ml ⏱ in 7 Min.'],
    // Hotfix (9) F01: this case expected "so far ≈ 322 ml" for a balance of −321.6 ml – moisture was ADDED (the card's
    // own balance shows +322 ml); the expectation was wrong and is corrected here
    ['airing, moisture added', { rooms: { ...rooms, bad: { ...rooms.bad, active: true } }, status: 'ventilate', potential_total_ml: 1500, live_balance_ml: -321.6, recommended_duration_min: 12, remaining_duration_min: 4.2 }, '💧 bisher +322 ml eingetragen ⏱ noch 5 Min.'],
    ['airing, moisture removed', { rooms: { ...rooms, bad: { ...rooms.bad, active: true } }, status: 'ventilate', potential_total_ml: 1500, live_balance_ml: 321.6, recommended_duration_min: 12, remaining_duration_min: 4.2 }, '💧 bisher ≈ 322 ml ⏱ noch 5 Min.'],
    // Hotfix (9) F07: here a room must close, so the IQ view's decision is "close", not "wait", and it shows the time;
    // the order-9 expectation ("possible", no time) came from the house map's own narrower wait check – corrected
    ['waiting while a room must close', { rooms, status: 'wait', intelligent_recommendation: { kind: 'wait', status: 'wait', title: 'Noch nicht lüften' }, potential_total_ml: 97, recommended_duration_min: 9 }, '💧 ≈ 97 ml ⏱ in 9 Min.'],
    // Hotfix (9) F01: negative potential is no "0 ml" – airing would add moisture (as the card's own value says)
    ['outside wetter', { rooms, status: 'ok', potential_total_ml: -230, recommended_duration_min: 9 }, '💧 +230 ml würde eingetragen'],
  ];
  for (const [name, payload, expected] of cases) {
    await push(page, payload);
    await page.waitForTimeout(1000);                                  // after the gliding transition
    const house = await houseFacts(page), classic = await classicFacts(page, payload);
    expect(house, name).toBe(expected);
    // the same amount (and time where the card shows one) as the FreshAirIQ card
    const amount = numbers(house)[0];
    if (amount >= 1) expect(classic, name).toContain(`${amount} ml`); else expect(classic, name).not.toMatch(/\d+ ml/);
    const minutes = numbers(house)[1];
    if (minutes != null) expect(numbers(classic), name).toContain(minutes);   // a shown time is the card's time
    expect(numbers(classic), name).toContain(amount >= 1 ? amount : numbers(classic)[0]);
  }
  // nothing computed yet (no house values in the payload): nothing is shown – no invented value
  await push(page, { rooms });
  await page.waitForTimeout(200);
  expect(await houseFacts(page)).toBe(null);
});

test('order 9 / 1b: several floors – the house value counts each room once (no own sum by floor); explanation names the time link', async ({ page }) => {
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  const rooms = await page.evaluate(() => window.__ROOMS);
  const payload = { rooms: { ...rooms, bad: { ...rooms.bad, potential_ml: 300 }, schlaf: { ...rooms.schlaf, potential_ml: 900 } }, status: 'ventilate', potential_total_ml: 812, recommended_duration_min: 10 };
  await push(page, payload);
  await page.waitForTimeout(1000);
  for (const floor of ['f_eg', 'f_og']) {                               // the same value whichever floor is shown
    await impl(page).evaluate((el, f) => el._chooseFloor(f), floor);
    await page.waitForTimeout(100);
    expect(await houseFacts(page), floor).toBe('💧 ≈ 812 ml ⏱ in 10 Min.');
  }
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-moisture]').click());
  const dlg = await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg[open]').textContent);
  expect(dlg).toContain('Jetzt entfernbar');
  expect(dlg).toContain('derselbe Wert wie auf der FreshAirIQ-Karte');
  expect(dlg).toContain('die Menge gilt also für genau diese Zeit');
  expect(dlg).toContain('alle Etagen, jeder Raum einmal');
  // readable on a phone: the info bar stays one line, above the plan, apart from the weather
  await impl(page).evaluate(el => el._closeDialog());
  await page.setViewportSize({ width: 360, height: 780 });
  await push(page, { ...payload, outdoor_temperature: 6.2, outdoor_humidity: 81 });
  await page.waitForTimeout(300);
  const bar = await impl(page).evaluate(el => { const m = el.shadowRoot.querySelector('.moist').getBoundingClientRect(), w = el.shadowRoot.querySelector('.weather').getBoundingClientRect(), p = el.shadowRoot.querySelector('svg.plan').getBoundingClientRect();
    return { apart: m.right <= w.left + 1 || m.bottom <= w.top + 1, above: m.bottom <= p.top + 1, oneLine: m.height < 40, font: parseFloat(getComputedStyle(el.shadowRoot.querySelector('.moist')).fontSize) }; });
  expect(bar, JSON.stringify(bar)).toMatchObject({ apart: true, above: true, oneLine: true });
  expect(bar.font).toBeGreaterThanOrEqual(12);
});

// ---- order 9: the wind's character follows the real weather -------------------------------------------------
test('order 9 / 3: wind moods from Home Assistant data – sunny light, neutral calm, rain denser, lively, storm epic', async ({ page }) => {
  await mount(page);
  await flowModule(page);
  const r = await page.evaluate(() => {
    const F = window.__F, G = window.G, rooms = [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 6], [0, 6]] }];
    const m = (o) => F.windMood(o).name;
    const table = [
      m({ speed: 3, condition: 'sunny', phase: 'day' }), m({ speed: 3, condition: 'partlycloudy', phase: 'day' }), m({ speed: 3, condition: 'sunny', phase: 'night' }),
      m({ speed: 3, condition: 'cloudy', phase: 'day' }), m({ speed: 4, condition: 'rainy', raining: true }), m({ speed: 5, condition: 'windy' }),
      m({ speed: 8, condition: 'cloudy' }), m({ speed: 12, condition: 'cloudy' }), m({ speed: 6, gust: 18, condition: 'cloudy' }),
      m({ speed: 7, condition: 'lightning-rainy', thunder: true, raining: true }), m({ speed: 2, condition: 'lightning', thunder: true }), m({ speed: 3 }),
      m({ speed: 8, condition: 'sunny', phase: 'day' }),
    ];
    const build = (speed, mood, gust) => F.buildField({ rooms, G, wind: { available: true, from_deg: 270, speed_ms: speed, gust_ms: gust }, northDeg: 0, mood: F.windMood(mood) });
    const sunny = build(5, { speed: 5, condition: 'sunny', phase: 'day' }), neutral = build(5, { speed: 5, condition: 'cloudy' }), storm = build(13, { speed: 13 });
    const peak = f => { let x = 0; for (let t = 0; t < 240; t += 0.5) for (const e of F.eddiesAt(f, t)) x = Math.max(x, Math.abs(e.gamma) / f.vis); return x; };
    const measured = build(5, { speed: 5, condition: 'sunny', phase: 'day' }, 9);
    return { table, density: [sunny.density, neutral.density, storm.density], eddy: [sunny.eddyChance, neutral.eddyChance, storm.eddyChance], peak: [peak(sunny), peak(neutral), peak(storm)],
      vis: [sunny.vis, neutral.vis], fade: [sunny.mood.fade, storm.mood.fade], warm: sunny.mood.colors[2], cool: storm.mood.colors[2],
      gust: [sunny.gust.amp, neutral.gust.amp, storm.gust.amp, measured.gust.measured, +measured.gust.amp.toFixed(2)] };
  });
  expect(r.table).toEqual(['sunny', 'sunny', 'neutral', 'neutral', 'rain', 'lively', 'lively', 'storm', 'storm', 'storm', 'neutral', 'neutral', 'lively']);
  expect(r.density[0]).toBeLessThan(r.density[1]); expect(r.density[2]).toBeGreaterThan(r.density[1]);      // fewer, lighter threads in the sun; dense in a storm
  expect(r.eddy[0]).toBeLessThan(r.eddy[1]); expect(r.eddy[2]).toBe(1);                                      // gentle in the sun, every chance in a storm
  expect(r.peak[0]).toBeLessThan(r.peak[1]); expect(r.peak[2]).toBeGreaterThan(r.peak[1] * 1.3);             // storm eddies roll much stronger
  expect(r.vis[0]).toBeLessThan(r.vis[1]);                                                                   // the same wind glides more calmly in the sun
  expect(r.fade[0]).toBeLessThan(r.fade[1]);                                                                 // long soft trails vs short crisp ones
  expect(r.warm).toMatch(/^rgba\(255,25\d,24\d/); expect(r.cool).toMatch(/^rgba\(240,248,255/);              // warm white vs cool white
  expect(r.gust).toEqual([0.08, 0.15, 0.35, true, 0.8]);                                                     // decorative by mood; a measured gust always wins
});

test('order 9 / 4: the scene follows the weather together – mood on the map and the air layer; labels stay clear; the recommendation look is unchanged', async ({ page }) => {
  await mount(page);
  const rooms = await page.evaluate(() => window.__ROOMS);
  const look = async (weather, wind, sun) => {
    await impl(page).evaluate((el, sun) => { el._hass = { ...el._hass, states: sun ? { 'sun.sun': { entity_id: 'sun.sun', ...sun } } : {} }; }, sun);
    await push(page, { rooms, weather_now: weather });
    await setWind(page, wind);
    await page.waitForTimeout(900);
    const c = await canvasState(page);
    return { mood: await impl(page).evaluate(el => el.shadowRoot.querySelector('svg.plan').dataset.mood), layer: await impl(page).evaluate(el => el._flowLayer.field && el._flowLayer.field.mood.name),
      fills: await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].map(p => `${p.getAttribute('class')} ${p.getAttribute('fill')}`).join('|')), onLabels: c.onLabels, ink: c.ink };
  };
  const day = { state: 'above_horizon', attributes: { elevation: 35, azimuth: 180 } };
  const sunny = await look({ condition: 'sunny' }, { speed_ms: 3, from_deg: 250 }, day);
  const cloudy = await look({ condition: 'cloudy' }, { speed_ms: 4, from_deg: 250 }, day);
  const rain = await look({ condition: 'rainy', raining: true }, { speed_ms: 5, from_deg: 250 }, day);
  const storm = await look({ condition: 'lightning-rainy', raining: true, thunder: true }, { speed_ms: 14, gust_ms: 24, from_deg: 250 }, day);
  expect([sunny.mood, cloudy.mood, rain.mood, storm.mood]).toEqual(['sunny', 'neutral', 'rain', 'storm']);
  expect([sunny.layer, cloudy.layer, rain.layer, storm.layer]).toEqual(['sunny', 'neutral', 'rain', 'storm']);
  for (const s of [sunny, cloudy, rain, storm]) { expect(s.onLabels).toBe(0); expect(s.ink).toBeGreaterThan(0); }   // readable in every weather
  expect(new Set([sunny.fills, cloudy.fills, rain.fills, storm.fills]).size).toBe(1);                              // the weather never changes a room's state
  // missing wind data: no wind and no mood-driven air, whatever the weather says
  await setWind(page, { available: false });
  expect(await canvasState(page)).toBe(null);
});

// ---- Hotfix (9): seven findings of the independent review ---------------------------------------------------
// The house map takes amount, time, session and wait state from the card's own _iqFacts; these cases render the
// real IQ view (classicFacts) and the house map with the same payload and compare what each one shows.
const sameAsCard = async (page, name, payload, expected) => {
  await push(page, payload);
  await page.waitForTimeout(1000);
  const house = await houseFacts(page), card = await classicFacts(page, payload);
  if (expected !== undefined) expect(house, name).toBe(expected);
  const amount = numbers(house)[0];
  if (amount >= 1) expect(card, name).toContain(`${amount} ml`);
  expect(house.includes('+'), `${name}: sign`).toBe(card.includes('+') && /\+\d+ ml/.test(card));   // moisture added: "+" on both
  const houseTime = /⏱/.test(house), cardTime = /\d+ min/.test(card);
  if (houseTime) { expect(cardTime, `${name}: time`).toBe(true); expect(numbers(card), name).toContain(numbers(house)[1]); }
  return { house, card };
};

test('hotfix (9) F01: signs – moisture added while airing and air that would add moisture are never shown as removed', async ({ page }) => {
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  const rooms = await page.evaluate(() => window.__ROOMS), on = { ...rooms, bad: { ...rooms.bad, active: true } };
  await sameAsCard(page, 'live −321.6', { rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: -321.6, recommended_duration_min: 12, remaining_duration_min: 6 }, '💧 bisher +322 ml eingetragen ⏱ noch 6 Min.');
  await sameAsCard(page, 'live +321.6', { rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: 321.6, recommended_duration_min: 12, remaining_duration_min: 6 }, '💧 bisher ≈ 322 ml ⏱ noch 6 Min.');
  await sameAsCard(page, 'potential −230', { rooms, status: 'ok', potential_total_ml: -230, recommended_duration_min: 9 }, '💧 +230 ml würde eingetragen');
  // the card's own balance view (classic panel) says the same: + is moisture added
  const { card } = await sameAsCard(page, 'live −40', { rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: -40, recommended_duration_min: 12, remaining_duration_min: 6 });
  expect(card).toContain('+40 ml');
  const nothing = await sameAsCard(page, 'live 0.3', { rooms: on, status: 'ventilate', potential_total_ml: 900, live_balance_ml: 0.3, recommended_duration_min: 12, remaining_duration_min: 6 });
  expect(nothing.house).toBe('💧 bisher ≈ 0 ml ⏱ noch 6 Min.');                     // no success claimed for nothing
});

test('hotfix (9) F05: a session counts until its final measurement on both cards – airing, finalising, done, a new airing', async ({ page }) => {
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  const rooms = await page.evaluate(() => window.__ROOMS);
  const base = { status: 'ventilate', potential_total_ml: 700, recommended_duration_min: 12 };
  const steps = [
    ['airing', { ...rooms, bad: { ...rooms.bad, active: true } }, { live_balance_ml: 210, remaining_duration_min: 3 }, '💧 bisher ≈ 210 ml ⏱ noch 3 Min.'],
    ['final measurement', { ...rooms, bad: { ...rooms.bad, active: true, session_finalization_pending: true } }, { live_balance_ml: 240, remaining_duration_min: 1 }, '💧 bisher ≈ 240 ml ⏱ noch 1 Min.'],
    ['done', rooms, { live_balance_ml: 0, remaining_duration_min: 12 }, '💧 ≈ 700 ml ⏱ in 12 Min.'],
    ['new airing', { ...rooms, flur: { ...rooms.flur, active: true } }, { live_balance_ml: 15, remaining_duration_min: 11.2 }, '💧 bisher ≈ 15 ml ⏱ noch 12 Min.'],
  ];
  for (const [name, r, extra, expected] of steps) await sameAsCard(page, name, { rooms: r, ...base, ...extra }, expected);
});

test('hotfix (9) F06: a remaining time below zero is time over the target, never "left"', async ({ page }) => {
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  const rooms = await page.evaluate(() => window.__ROOMS), on = { ...rooms, bad: { ...rooms.bad, active: true } };
  const over = await sameAsCard(page, 'over', { rooms: on, status: 'ventilate', potential_total_ml: 700, live_balance_ml: 300, recommended_duration_min: 12, remaining_duration_min: -3 }, '💧 bisher ≈ 300 ml ⏱ 3 Min. über Ziel');
  expect(over.card).toContain('+3 min');                                               // the IQ view: over target, not "3 min left"
  expect(over.card).not.toContain('übrig');
  await sameAsCard(page, 'on target', { rooms: on, status: 'ventilate', potential_total_ml: 700, live_balance_ml: 300, recommended_duration_min: 12, remaining_duration_min: 0.2 }, '💧 bisher ≈ 300 ml');
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-moisture]').click());
  // the explanation window names the over-run too
  await push(page, { rooms: on, status: 'ventilate', potential_total_ml: 700, live_balance_ml: 300, recommended_duration_min: 12, remaining_duration_min: -3 });
  await page.waitForTimeout(150);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelector('dialog.roomdlg[open]').textContent)).toContain('Über Ziel');
});

test('hotfix (9) F07: wait, pollen, night strategy, a delayed release and a running session – the time is shown exactly where the IQ view shows it', async ({ page }) => {
  await mount(page);
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  const rooms = await page.evaluate(() => window.__ROOMS);
  const calm = Object.fromEntries(Object.entries(rooms).map(([k, r]) => [k, { ...r, action: 'Okay', house_aligned_action: 'okay' }]));
  const vent = { ...calm, wohnen: { ...calm.wohnen, action: 'Ventilate', house_aligned_action: 'ventilate_later' } };
  const cases = [
    ['house waits', { rooms: vent, status: 'wait', intelligent_recommendation: { kind: 'wait', status: 'wait', title: 'Noch nicht lüften' } }, false],
    ['pollen wait', { rooms: vent, status: 'wait', intelligent_recommendation: { kind: 'pollen_wait', title: 'Pollen' } }, false],
    ['pollen warning (card shows its time)', { rooms: vent, status: 'pollen_warning', pollen_blocked: true }, true],
    ['night strategy holds', { rooms: vent, status: 'ok', night_strategy: { primary: true, action: 'keep_closed' } }, false],
    ['night strategy airs now', { rooms: vent, status: 'ok', night_strategy: { primary: true, action: 'pre_ventilate' } }, true],
    ['ventilate', { rooms: vent, status: 'ventilate' }, true],
    ['waiting, but a session runs', { rooms: { ...vent, bad: { ...vent.bad, active: true } }, status: 'wait', intelligent_recommendation: { kind: 'wait', status: 'wait' }, live_balance_ml: 120, remaining_duration_min: 4 }, true],
  ];
  for (const [name, payload, timeShown] of cases) {
    const r = await sameAsCard(page, name, { potential_total_ml: 640, recommended_duration_min: 9, ...payload });
    expect(/⏱/.test(r.house), `${name}: house time`).toBe(timeShown);
    expect(/\d+ min/.test(r.card), `${name}: card time`).toBe(timeShown);
    if (!timeShown && !payload.live_balance_ml) expect(r.house, name).toContain('möglich');
  }
});

test('hotfix (9) F02/F03: every pressed open window gets its air wherever it sits on the wall; an outlet only along a published path', async ({ page }) => {
  await mount(page);
  await geo(page);
  const r = await page.evaluate(async () => {
    const V = await import('/freshairiq-house-view.js?v=t'), G = window.G;
    const rooms = [{ id: 'a', polygon: [[0, 0], [10, 0], [10, 4], [0, 4]] }];
    const win = (id, edge, offset, pressure, state = 'open') => ({ id, room_id: 'a', edge, offset, width_m: 0.9, state, target: 'outside', pressure });
    const inflow = (openings, paths = []) => V.windStreams({ rooms, openings, fromDeg: 0, northDeg: 0, G, paths }).filter(s => s.kind === 'inflow');
    // F02: the same north wall, the window at many places – always its own inflow, ending at the window
    const offsets = [0.05, 0.13, 0.27, 0.41, 0.5, 0.63, 0.77, 0.9, 0.97].map(off => { const s = inflow([win('n', 2, off, 0.9)]); const w = G.edgePoint(rooms[0].polygon, 2, off);
      return s.length === 1 && Math.hypot(s[0].points[1][0] - w[0], s[0].points[1][1] - w[1]) < 1e-6; });
    // no inflow without confirmed opening, wind pressure or with the window on the lee side
    const none = [inflow([{ ...win('n', 2, 0.5, 0.9), pending: true }]).length, inflow([win('n', 2, 0.5, null)]).length, inflow([win('s', 0, 0.5, -0.9)]).length, inflow([win('n', 2, 0.5, 0.9, 'closed')]).length];
    const tilted = inflow([win('n', 2, 0.5, 0.9, 'tilted')])[0].tilted;
    // F03: two windows on the same facade – each gets air, neither is made the other's outlet
    const same = inflow([win('n1', 2, 0.2, 0.9), win('n2', 2, 0.8, 0.9)]);
    // opposite facades without a published path: no invented cross flow; with the published path: out of the other
    const opposite = inflow([win('n', 2, 0.5, 0.9), win('s', 0, 0.5, -0.9)]);
    const route = G.airRoute({ rooms: rooms.map(x => ({ ...x, floor_id: 'f' })), openings: [win('n', 2, 0.5, 0.9), win('s', 0, 0.5, -0.9)].map(o => ({ ...o, kind: 'window' })), connections: [] },
      { from: 'n', to: 's', rooms: ['a'], via: [], direction: 'directed' }, { outside: 1, strict: true });
    const published = inflow([win('n', 2, 0.5, 0.9), win('s', 0, 0.5, -0.9)], [{ from: 'n', to: 's', direction: 'directed', points: route.points, exits: route.exits }]);
    return { offsets, none, tilted, same: same.map(s => [s.opening, s.exits]), opposite: opposite.map(s => [s.opening, s.exits]), published: published.map(s => [s.opening, s.exits, +s.points.at(-1)[1].toFixed(2)]) };
  });
  expect(r.offsets.every(Boolean)).toBe(true);
  expect(r.none).toEqual([0, 0, 0, 0]);
  expect(r.tilted).toBe(true);
  expect(r.same).toEqual([['n1', false], ['n2', false]]);
  expect(r.opposite).toEqual([['n', false]]);
  expect(r.published).toEqual([['n', true, -1]]);
});

test('hotfix (9) F02: on the card the canvas air enters at the window wherever it sits on the windward wall', async ({ page }) => {
  await mount(page);
  const count = [];
  for (const offset of [0.12, 0.5, 0.88]) {
    count.push(await impl(page).evaluate((el, offset) => {
      el._layoutInfo.layout.openings = el._layoutInfo.layout.openings.map(o => (o.id === 'o_bad' ? { ...o, offset } : o));
      const ops = { ...el._house.airflow.openings, o_bad: { ...el._house.airflow.openings.o_bad, pending: false, state: 'open' } };
      el._house = { ...el._house, wind: { ...el._house.wind, from_deg: 0 }, airflow: { ...el._house.airflow, openings: ops } }; el._windSmooth = 0; el._render();
      return { streams: el.shadowRoot.querySelectorAll('path.stream.inflow').length, routes: el._flowLayer.routes.length };
    }, offset));
  }
  for (const c of count) expect(c.streams >= 1 && c.routes === c.streams).toBe(true);
});

// ---- 0.26.6.0(10): editor – one wall at a time, 90° corners, locks, fitting rooms together; sun; door swings --------
const JOIN = JSON.parse(fs.readFileSync(new URL('./fixtures/house_join_rooms.json', import.meta.url), 'utf8'));
const wallPanel = (editor, id, index) => editor.evaluate((el, [id, index]) => { el._floor = el._layout.rooms.find(r => r.id === id).floor_id; el._sel = { type: 'wall', id, index }; el._msg = null; el._render(); }, [id, index]);
const setWall = (editor, len, fixed = 'start') => editor.evaluate((el, [len, fixed]) => {
  el._wallFixed = fixed; el._render(); el.shadowRoot.querySelector('[data-f="wall_len"]').value = String(len);
  el.shadowRoot.querySelector('[data-a="wall_apply"]').click(); return el._msg ? el._msg.text : null;
}, [len, fixed]);
const tick = (editor, field, corner = null) => editor.evaluate((el, [field, corner]) => {
  const box = el.shadowRoot.querySelector(`[data-f="${field}"]${corner == null ? '' : `[data-corner="${corner}"]`}`); box.checked = !box.checked; box.dispatchEvent(new Event('change'));
}, [field, corner]);
const lengths = p => p.map((q, i) => { const r = p[(i + 1) % p.length]; return +Math.hypot(r[0] - q[0], r[1] - q[1]).toFixed(3); });

test('order 10 A: one wall changes alone – the opposite wall keeps its length, the room may stop being a rectangle; saved as drawn', async ({ page }) => {
  const editor = await openEditor(page);
  const before = await roomPoints(editor, 'r_bad');                       // 4 × 4, wall 0 = bottom (y = 4)
  await wallPanel(editor, 'r_bad', 2);                                     // the top wall (y = 8), the left corner moves
  expect(await setWall(editor, 3.4)).toBe(null);
  const after = await roomPoints(editor, 'r_bad');
  expect(lengths(after)[0]).toBe(lengths(before)[0]);                      // the opposite wall keeps 4 m
  expect(lengths(after)[2]).toBe(3.4);
  expect(after.slice(0, 3)).toEqual(before.slice(0, 3));                   // only the moving corner left its place
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_flur').polygon)).toEqual(LAYOUT.rooms[1].polygon);  // no neighbour moved
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout.rooms.find(r => r.id === 'r_bad').polygon);
  expect(saved).toEqual(after);                                            // not squared back on save
});

test('order 10 B: lock wall after wall – a change that would break a lock is refused, the wall is named with a way out, locks stay', async ({ page }) => {
  const editor = await openEditor(page);
  for (const w of [1, 2, 3]) { await wallPanel(editor, 'r_schlaf', w); await tick(editor, 'wall_lock'); }
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_schlaf').locked_walls)).toEqual([1, 2, 3]);
  const before = await roomPoints(editor, 'r_schlaf');
  await wallPanel(editor, 'r_schlaf', 0);
  const msg = await setWall(editor, 4);
  expect(msg).toContain('Wand 4');                                         // names the locked wall …
  expect(msg).toContain('Lösung');                                         // … and how to solve it
  expect(await roomPoints(editor, 'r_schlaf')).toEqual(before);            // nothing changed silently
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_schlaf').locked_walls)).toEqual([1, 2, 3]);
  // a locked length elsewhere is carried along: wall 2 keeps its length while wall 1 changes
  await wallPanel(editor, 'r_schlaf', 3); await tick(editor, 'wall_lock');   // unlock wall 4
  await wallPanel(editor, 'r_schlaf', 0);
  expect(await setWall(editor, 4)).toBe(null);
  const after = await roomPoints(editor, 'r_schlaf');
  expect(lengths(after)[0]).toBe(4);
  for (const w of [1, 2]) expect(lengths(after)[w]).toBeCloseTo(lengths(before)[w], 2);
  // a locked angle is its own lock: squaring the neighbouring corner that would bend it is refused and named
  await editor.evaluate(el => el._undo());
  await wallPanel(editor, 'r_schlaf', 1); await tick(editor, 'corner_lock', 2);
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_schlaf').locked_corners)).toEqual([2]);
  await editor.evaluate(el => el._squareCorner(1, 'in'));
  expect(await editor.evaluate(el => el._msg && el._msg.text)).toContain('Ecke 3');
  expect(await roomPoints(editor, 'r_schlaf')).toEqual(before);
  await editor.evaluate(el => el._squareCorner(2, 'in'));
  expect(await editor.evaluate(el => el._msg && el._msg.text)).toContain('Winkel an Ecke 3 ist gesperrt');
  // undo walks back through the angle lock, then the length lock
  await editor.evaluate(el => el._undo());
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_schlaf').locked_corners)).toBe(undefined);
});

test('order 10 C: a corner to 90° on request, angles shown, optional 90° snapping while dragging – never all rooms squared', async ({ page }) => {
  const editor = await openEditor(page);
  await geo(page);
  const others = await editor.evaluate(el => el._layout.rooms.filter(r => r.id !== 'r_schlaf').map(r => r.polygon));
  await wallPanel(editor, 'r_schlaf', 1);                                  // wall 2: corners 2 and 3
  const angles = () => editor.evaluate(el => [...el.shadowRoot.querySelectorAll('.corner-row b')].map(b => b.textContent));
  expect(await angles()).toEqual(['Winkel Ecke 2: 76,0°', 'Winkel Ecke 3: 90,0°']);
  expect(await editor.evaluate(el => [...el.shadowRoot.querySelectorAll('[data-a="square"]')].map(b => b.disabled))).toEqual([false, true]);   // already square
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="square"][data-corner="1"]').click());
  const sq = await roomPoints(editor, 'r_schlaf');
  expect(await page.evaluate(p => +window.G.cornerAngle(p, 1).toFixed(2), sq)).toBe(90);
  expect(lengths(sq)[1]).toBeCloseTo(Math.hypot(1, 4), 2);                 // the wall turned, its length stayed
  expect((await angles())[0]).toBe('Winkel Ecke 2: 90,0°');
  expect(await editor.evaluate(el => el._layout.rooms.filter(r => r.id !== 'r_schlaf').map(r => r.polygon))).toEqual(others);   // no other room squared
  // L shapes: the reflex corner of the L room is shown as 270° and left alone
  await wallPanel(editor, 'r_wohnen', 2);
  expect((await angles())[1]).toBe('Winkel Ecke 4: 270,0°');
  expect(await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="square"][data-corner="3"]').disabled)).toBe(true);   // already right
  // an inner corner that is a little off is squared back to 270° – the L stays an L
  const bent = await page.evaluate(() => window.G.squareCorner({ rooms: [{ id: 'l', polygon: [[4, 4], [10, 4], [10, 7], [7.3, 7], [7, 10], [4, 10]] }] }, 'l', 3, 'in').polygons.l);
  expect(await page.evaluate(p => +window.G.cornerAngle(p, 3).toFixed(2), bent)).toBe(270);
  // 90° snapping while dragging a corner – only when switched on
  const drag = async snap => {
    await editor.evaluate((el, snap) => { el._snap90 = snap; el._mode = 'precise'; el._floor = 'f_eg'; el._sel = { type: 'room', id: 'r_bad' }; el._render(); }, snap);
    await editor.locator('svg').scrollIntoViewIfNeeded();
    const pts = await editor.evaluate(el => { const svg = el.shadowRoot.querySelector('svg'), m = svg.getScreenCTM(), P = (x, y) => { const p = svg.createSVGPoint(); p.x = x; p.y = -y; const q = p.matrixTransform(m); return [q.x, q.y]; }; return { from: P(4, 8), to: P(3.9, 8.2) }; });
    await page.mouse.move(...pts.from); await page.mouse.down(); await page.mouse.move(...pts.to, { steps: 6 }); await page.mouse.up();
    const p = await roomPoints(editor, 'r_bad');
    await editor.evaluate(el => el._undo());
    return page.evaluate(p => window.G.cornerAngle(p, 2), p);
  };
  expect(await editor.evaluate(el => { el._render(); return el.shadowRoot.querySelector('[data-a="snap90"]').getAttribute('aria-pressed'); })).toBe('false');
  expect(Math.abs(await drag(false) - 90)).toBeGreaterThan(0.5);
  expect(Math.abs(await drag(true) - 90)).toBeLessThan(0.2);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="snap90"]').click());
  expect(await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="snap90"]').getAttribute('aria-pressed'))).toBe('false');   // toggled off again
});

test('order 10 D/E: rooms fitted together – preview first, locked lengths kept, shared walls drawn once, the door links both rooms in the editor and on the map', async ({ page }) => {
  const editor = await openEditor(page);
  await geo(page);
  await editor.evaluate((el, L) => { el._layout = JSON.parse(JSON.stringify(L)); el._floor = 'f_eg'; el._sel = null; el._render(); }, JOIN.layout);
  const link = () => editor.evaluate(el => { const r = el._layout.rooms.find(x => x.id === 'r_wohn'); const l = window.G.openingLink(el._layout.rooms, r, el._layout.openings.find(o => o.id === 'd_wk')); return l && l.id; });
  expect(await link()).toBe(null);                                         // 14 cm apart: the door leads nowhere yet
  // cancelled preview: nothing changes
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="join"]').click());
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('polygon.join-ghost').length)).toBe(3);
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('line.join-shared').length)).toBeGreaterThan(0);
  const notes = await editor.evaluate(el => el._preview.join.notes);
  expect(notes[0]).toBe('Vorschau: 3 gemeinsame Wände erkannt, 2 Räume verschoben (keiner verformt).');
  expect(notes[1]).toContain('4,00 m ↔ kueche 3,92 m');
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="no-apply"]').click());
  const polys = () => editor.evaluate(el => Object.fromEntries(el._layout.rooms.map(r => [r.id, r.polygon])));
  expect(await polys()).toEqual(Object.fromEntries(JOIN.layout.rooms.map(r => [r.id, r.polygon])));
  // applied: exactly the shared result (the same as the Python check), locks kept, the door now links both rooms
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="join"]').click());
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="apply"]').click());
  expect(await polys()).toEqual(JOIN.joined);
  for (const r of JOIN.layout.rooms) expect(lengths(JOIN.joined[r.id]).filter((_, i) => (r.locked_walls || []).includes(i))).toEqual(lengths(r.polygon).filter((_, i) => (r.locked_walls || []).includes(i)));
  expect(await link()).toBe('r_kueche');
  expect(await editor.evaluate(el => window.G.validateLayout(el._layout))).toEqual([]);
  const walls = await wallsOf(page, 'editor');
  expect(walls.filter(w => w.startsWith('in')).length).toBeGreaterThanOrEqual(3);
  expect(new Set(walls).size).toBe(walls.length);                          // no wall drawn twice
  // the window stays on an outside wall
  expect(await editor.evaluate(el => window.G.windowOnInteriorWall(el._layout.rooms, el._layout.openings.find(o => o.id === 'w_k')))).toBe(false);
  // undo / redo
  await editor.evaluate(el => el._undo());
  expect(await polys()).toEqual(Object.fromEntries(JOIN.layout.rooms.map(r => [r.id, r.polygon])));
  await editor.evaluate(el => el._redo());
  expect(await polys()).toEqual(JOIN.joined);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/save').layout);
  expect(Object.fromEntries(saved.rooms.map(r => [r.id, r.polygon]))).toEqual(JOIN.joined);
  expect(saved.rooms.map(r => r.locked_walls)).toEqual(JOIN.layout.rooms.map(r => r.locked_walls));
  // the live map draws the same walls from the saved plan; pulled apart again, the door links nothing
  await impl(page).evaluate((el, L) => { el._editing = null; el._layoutInfo = { ...el._layoutInfo, layout: L }; el._floor = 'f_eg'; el._render(); }, saved);
  expect(await wallsOf(page, 'card')).toEqual(walls);
  const apart = await page.evaluate(L => { const rooms = L.rooms.map(r => (r.id === 'r_kueche' ? { ...r, polygon: r.polygon.map(p => [p[0] + 1, p[1]]) } : r));
    return window.G.openingLink(rooms, rooms[0], L.openings[0]); }, saved);
  expect(apart).toBe(null);
  // nothing close enough: an explanation instead of a preview
  await openEditor(page);
  expect(await editor.evaluate(el => { el._floor = 'f_og'; el._render(); el.shadowRoot.querySelector('[data-a="join"]').click(); return [el._preview, el._msg && el._msg.text]; }))
    .toEqual([null, 'Keine zusammenpassenden Wände gefunden – die Räume bis auf etwa 35 cm aneinanderschieben.']);
});

test('order 10 F: door swings only in the editor – the map keeps the leaf and its state, and a closed door blocks no label space', async ({ page }) => {
  await mount(page);
  const blocks = state => impl(page).evaluate((el, state) => {
    const L = el._layoutInfo.layout, rooms = L.rooms.filter(r => r.floor_id === 'f_eg');
    return el._labelBlocks(rooms, L.openings.filter(o => o.id === 'd_bad').map(o => ({ ...o, state })), 1).length;
  }, state);
  expect([await blocks('closed'), await blocks('open')]).toEqual([0, 1]);   // only the open leaf takes space
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelectorAll('g.symbol.k-door path.arc').length)).toBe(0);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelectorAll('g.symbol.k-door line.leaf').length)).toBeGreaterThan(0);
  const editor = await openEditor(page);
  expect(await editor.evaluate(el => el.shadowRoot.querySelectorAll('path.arc').length)).toBeGreaterThan(0);
});

test('order 10 G: the sun moves on within the day – redrawn in 2° steps, on its side by north, without confirmed north no side is faked', async ({ page }) => {
  await mount(page);
  await push(page, { rooms: await page.evaluate(() => window.__ROOMS), weather_now: { condition: 'sunny' } });
  await impl(page).evaluate(el => { window.__renders = 0; const r = el._render.bind(el); el._render = (...a) => { window.__renders += 1; return r(...a); }; });
  const sunAt = async (az, elev, other = 'off') => {
    await impl(page).evaluate((el, [az, elev, other]) => { el.hass = { ...el._hass, states: { 'sun.sun': { entity_id: 'sun.sun', state: elev > 0 ? 'above_horizon' : 'below_horizon', attributes: { azimuth: az, elevation: elev } }, 'light.x': { state: other } } }; }, [az, elev, other]);
    await page.waitForTimeout(60);
    return impl(page).evaluate(el => { const c = el.shadowRoot.querySelector('.wx.sunlight circle'); return { sun: c && [+c.getAttribute('cx'), +c.getAttribute('cy')], day: !!el.shadowRoot.querySelector('.wx.daylight'), renders: window.__renders }; });
  };
  const east = await sunAt(90, 30);
  const start = east.renders;
  expect((await sunAt(90, 30, 'on')).renders).toBe(start);                // another entity changed: no redraw
  expect((await sunAt(90.6, 30.4)).renders).toBe(start);                  // below 2°: no redraw
  const later = await sunAt(120, 30);
  expect(later.renders).toBeGreaterThan(start);                            // same phase, sun moved on: redrawn
  expect(later.sun).not.toEqual(east.sun);
  const higher = await sunAt(120, 45);
  expect(higher.renders).toBeGreaterThan(later.renders);                   // elevation counts too
  const west = await sunAt(270, 30);
  expect(Math.sign(west.sun[0] - east.sun[0])).toBe(-1);                   // north up: the evening sun stands on the left (west)
  // the plan turned (north to the right): the same sun on another side of the drawing
  await impl(page).evaluate(el => { el._layoutInfo.layout.building.north_deg = 90; el._render(); });
  const turned = await sunAt(270, 30.01);
  expect(turned.sun).not.toEqual(west.sun);
  // north not confirmed: soft daylight from above, no sun disc or rays on a side that might be wrong
  await impl(page).evaluate(el => { el._layoutInfo.layout.building.north_confirmed = false; el._render(); });
  const unsure = await sunAt(200, 40);
  expect([unsure.sun, unsure.day]).toEqual([null, true]);
  expect(await impl(page).evaluate(el => el.shadowRoot.querySelectorAll('.wx path.ray').length)).toBe(0);
  // night: neither
  const night = await sunAt(0, -20);
  expect([night.sun, night.day]).toEqual([null, false]);
});

test('order 10 6.1: floors carry readable names in the editor like on the map – internal ids stay', async ({ page }) => {
  const editor = await openEditor(page);
  const names = lang => editor.evaluate((el, lang) => { el._lang = lang; el._layout.floors = el._layout.floors.map(f => ({ ...f, name: f.level_key })); el._render();
    return [...el.shadowRoot.querySelectorAll('[data-f="view_floor"] option')].map(o => [o.value, o.textContent]); }, lang);
  expect(await names('de')).toEqual([['f_eg', 'Erdgeschoss'], ['f_og', 'Obergeschoss']]);
  expect(await names('en')).toEqual([['f_eg', 'Ground floor'], ['f_og', 'Upper floor']]);
  expect(await editor.evaluate(el => el._layout.floors.map(f => [f.id, f.level_key]))).toEqual([['f_eg', 'ground_floor'], ['f_og', 'upper_floor']]);
  const map = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.floors [data-floor]')].map(b => b.textContent.trim()));
  for (const m of map) expect(['Erdgeschoss', 'Obergeschoss']).toContain(m);
});

// ---- hotfix after the independent review (F01–F04) ---------------------------------------------------------------
const JOIN_CW = JSON.parse(fs.readFileSync(new URL('./fixtures/house_join_rooms_cw.json', import.meta.url), 'utf8'));

test('review F04: a locked angle is protected when corners are added or removed – followed by its corner, not its index', async ({ page }) => {
  const editor = await openEditor(page);
  // the reported case: 90° locked at corner 2; a corner inserted next to it makes it 63.43° – refused
  const pure = await page.evaluate(async () => {
    const E = await import('/freshairiq-house-editor.js?v=r');
    const L = (polygon, locked_corners) => ({ rooms: [{ id: 'a', polygon, locked_corners }] });
    const sq = L([[0, 0], [4, 0], [4, 4], [0, 4]], [1]);
    const G = await import('/freshairiq-house-geometry.js?v=r');
    const bent = [[0, 0], [4, 0], [3, 2], [4, 4], [0, 4]];
    return {
      angle: +G.cornerAngle(bent, 1).toFixed(2),
      inserted: E.angleBroken(sq, L(bent, [1])),
      insertedOtherWall: E.angleBroken(sq, L([[0, 0], [4, 0], [4, 4], [2, 4], [0, 4]], [1])),    // straight corner on another wall
      shiftedIndex: E.angleBroken(L([[0, 0], [4, 0], [4, 4], [0, 4]], [2]), L([[0, 0], [2, 0], [4, 0], [4, 4], [0, 4]], [2])),   // index not shifted: still the right corner
      removedNeighbour: E.angleBroken(sq, L([[0, 0], [4, 0], [0, 4]], [1])),
      removedItself: E.angleBroken(sq, L([[0, 0], [4, 4], [0, 4]], [])),
      draggedItself: E.angleBroken(sq, L([[0, 0], [5, 0], [4, 4], [0, 4]], [1])),
      message: [E.lockMessage(sq, L(bent, [1])), E.lockMessage({ rooms: [{ id: 'a', polygon: [[0, 0], [4, 0], [4, 4], [0, 4]], locked_walls: [0] }] }, { rooms: [{ id: 'a', polygon: [[0, 0], [5, 0], [4, 4], [0, 4]], locked_walls: [0] }] })],
    };
  });
  expect(pure).toEqual({ angle: 63.43, inserted: true, insertedOtherWall: false, shiftedIndex: false, removedNeighbour: true, removedItself: true, draggedItself: true, message: ['angle_locked', 'wall_locked'] });
  // in the editor: lock the bath's corner 3 (4, 8); its interior door is taken out first – it has its own rule
  // (an interior door stays on its shared wall), which would refuse removing the corner it sits next to
  await editor.evaluate(el => { el._layout.openings = el._layout.openings.filter(o => o.id !== 'd_bad'); el._render(); });
  const bath = () => roomPoints(editor, 'r_bad');
  await wallPanel(editor, 'r_bad', 1); await tick(editor, 'corner_lock', 2);
  expect(await editor.evaluate(el => el._layout.rooms.find(r => r.id === 'r_bad').locked_corners)).toEqual([2]);
  const before = await bath();
  // a corner added on the wall next to it and moved – refused, nothing changed
  const insertAndMove = await editor.evaluate(el => {
    el._mode = 'precise'; el._sel = { type: 'room', id: 'r_bad' }; el._render();
    el._commit(l => { const r = l.rooms.find(x => x.id === 'r_bad'); r.polygon.splice(2, 0, [3.6, 6]); r.locked_corners = [3]; });
    return el._msg && el._msg.text;
  });
  expect(insertAndMove).toContain('gesperrten Winkel');
  expect(await bath()).toEqual(before);
  // the neighbouring corner removed – refused; the locked corner removed – refused
  for (const index of [1, 2]) {
    const text = await editor.evaluate((el, index) => { el._sel = { type: 'vertex', id: 'r_bad', index }; el._deleteSelected(); return el._msg && el._msg.text; }, index);
    expect(text, `delete ${index}`).toContain('gesperrten Winkel');
    expect(await bath()).toEqual(before);
  }
  // a corner removed that does not touch it: allowed – the lock moves with its corner (index 2 → 1)
  expect(await editor.evaluate(el => { el._sel = { type: 'vertex', id: 'r_bad', index: 0 }; el._deleteSelected(); return el._msg && el._msg.text; })).toBe(null);
  const after = await editor.evaluate(el => { const r = el._layout.rooms.find(x => x.id === 'r_bad'); return [r.polygon, r.locked_corners]; });
  expect(after).toEqual([[[4, 4], [4, 8], [0, 8]], [1]]);
  // a straight corner inserted mid-wall elsewhere (indices shift) and the plan saved and reloaded keeps the lock on (4, 8)
  await editor.evaluate(el => el._undo());
  await editor.evaluate(el => { el._mode = 'precise'; el._sel = { type: 'room', id: 'r_bad' }; el._render(); const mid = [...el.shadowRoot.querySelectorAll('circle.mid')].find(c => c.dataset.id === 'r_bad' && c.dataset.i === '0');
    mid.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 })); el.shadowRoot.querySelector('svg').dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerId: 1 })); });
  const inserted = await editor.evaluate(el => { const r = el._layout.rooms.find(x => x.id === 'r_bad'); return [r.polygon.length, r.polygon[r.locked_corners[0]]]; });
  expect(inserted).toEqual([5, [4, 8]]);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.filter(c => c.type === 'freshairiq/house_map/save').at(-1).layout.rooms.find(r => r.id === 'r_bad'));
  expect(saved.polygon[saved.locked_corners[0]]).toEqual([4, 8]);
});

test('review F03: fitting rooms together works for rooms drawn clockwise – same house, corner order, windows and locks kept', async ({ page }) => {
  const editor = await openEditor(page);
  await geo(page);
  // the reported case: two rectangles 15 cm apart, the second clockwise
  const repro = await page.evaluate(() => {
    const A = { id: 'a', polygon: [[0, 0], [4, 0], [4, 3], [0, 3]] };
    return [[[4.15, 0], [7, 0], [7, 3], [4.15, 3]], [[4.15, 0], [4.15, 3], [7, 3], [7, 0]]].map(p => {
      const r = window.G.joinRooms([A, { id: 'b', polygon: p }]); return [r.matches.length, r.polygons.b]; });
  });
  expect(repro).toEqual([[1, [[4, 0], [6.85, 0], [6.85, 3], [4, 3]]], [1, [[4, 0], [4, 3], [6.85, 3], [6.85, 0]]]]);
  // the clockwise fixture in the editor: preview, apply, the same result as computed for pytest
  await editor.evaluate((el, L) => { el._layout = JSON.parse(JSON.stringify(L)); el._floor = 'f_eg'; el._sel = null; el._render(); }, JOIN_CW.layout);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="join"]').click());
  expect(await editor.evaluate(el => el._preview.join.notes[0])).toBe('Vorschau: 3 gemeinsame Wände erkannt, 2 Räume verschoben (keiner verformt).');
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="apply"]').click());
  const res = await editor.evaluate(el => ({ polys: Object.fromEntries(el._layout.rooms.map(r => [r.id, r.polygon])), issues: window.G.validateLayout(el._layout),
    door: (window.G.openingLink(el._layout.rooms, el._layout.rooms.find(r => r.id === 'r_wohn'), el._layout.openings.find(o => o.id === 'd_wk')) || {}).id,
    windowInside: window.G.windowOnInteriorWall(el._layout.rooms, el._layout.openings.find(o => o.id === 'w_k')),
    windowFacing: Math.round(window.G.edgeBearing(el._layout.rooms.find(r => r.id === 'r_kueche').polygon, el._layout.openings.find(o => o.id === 'w_k').edge, 0)),
    locks: el._layout.rooms.map(r => r.locked_walls) }));
  expect(res.polys).toEqual(JOIN_CW.joined);
  expect([res.issues, res.door, res.windowInside, res.windowFacing]).toEqual([[], 'r_kueche', false, 90]);
  expect(res.locks).toEqual(JOIN_CW.layout.rooms.map(r => r.locked_walls));
  // the same house as the counter-clockwise fixture, corner by corner (in its own order)
  for (const id of Object.keys(JOIN.joined)) expect([...res.polys[id]].sort().join('|'), id).toBe([...JOIN.joined[id]].sort().join('|'));
  const walls = await wallsOf(page, 'editor');
  expect(walls.filter(w => w.startsWith('in')).length).toBeGreaterThanOrEqual(3);
  expect(new Set(walls).size).toBe(walls.length);
});

test('review F01: a window drawn in one room can carry the sensor another room airs by – chosen in the editor, saved, live state on the map', async ({ page }) => {
  const editor = await openEditor(page);
  // the bath window: its own room has no contact list here; the living room's contact is offered with the room it airs
  const offered = await editor.evaluate(el => { el._sel = { type: 'opening', id: 'o_bad' }; el._render();
    return [...el.shadowRoot.querySelectorAll('[data-contact]')].map(b => [b.dataset.contact, b.checked, b.parentElement.textContent.trim()]); });
  expect(offered).toContainEqual(['sensor.wohnen_lage', false, 'sensor.wohnen_lage (lüftet Wohnen)']);
  expect(offered).toContainEqual(['binary_sensor.bad_fenster', true, 'binary_sensor.bad_fenster']);
  await editor.evaluate(el => { const b = el.shadowRoot.querySelector('[data-contact="sensor.wohnen_lage"]'); b.checked = true; b.dispatchEvent(new Event('change')); });
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(80);
  const saved = await page.evaluate(() => window.__calls.filter(c => c.type === 'freshairiq/house_map/save').at(-1).layout.openings.find(o => o.id === 'o_bad'));
  expect([saved.room_id, saved.contacts]).toEqual(['r_bad', ['binary_sensor.bad_fenster', 'sensor.wohnen_lage']]);
  // on the map: the opening's window shows the sensor's live state from the room that airs by it
  const rows = await impl(page).evaluate((el, contacts) => {
    el._editing = null;
    el._layoutInfo.layout.openings = el._layoutInfo.layout.openings.map(o => (o.id === 'o_bad' ? { ...o, contacts } : o));
    el._house = { ...el._house, rooms: { ...el._house.rooms, wohnen: { contacts: { 'sensor.wohnen_lage': { state: 'tilted', pending: false } } } } };
    el._selected = { type: 'opening', id: 'o_bad' }; el._render();
    return [...el.shadowRoot.querySelectorAll('li')].map(li => li.textContent);
  }, saved.contacts);
  expect(rows).toContain('sensor.wohnen_lage: gekippt');
  expect(rows.some(r => r.startsWith('binary_sensor.bad_fenster: '))).toBe(true);
});
