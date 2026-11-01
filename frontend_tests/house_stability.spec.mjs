// Hotfix F01/F02 (31.10.): the house map "keeps jumping up" and doubled its WebSocket subscriptions.
// F02 – reproduced cause: every render created a new <ha-card>. Home Assistant's ha-card (a Lit element) draws
// its content a microtask after it is connected; the scroll restore of the map measured the page in that
// moment (card a few pixels high) and the browser cut the page scroll back. Chromium repairs that with scroll
// anchoring, WebKit has none – the pages here switch scroll anchoring off (overflow-anchor:none) and use an
// ha-card that behaves like Home Assistant's. F01 – parallel starts, a failed channel, a disconnect during an
// await: exactly two subscriptions per shown card, none after it is removed.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { loadModule } from './harness.mjs';

const SRC = fs.readFileSync(new URL('./house.spec.mjs', import.meta.url), 'utf8');
const LAYOUT = eval(`(${SRC.slice(SRC.indexOf('const LAYOUT = ') + 15, SRC.indexOf('};\n// Room fields') + 1)})`);
const BASE_ROOM = JSON.parse(fs.readFileSync(new URL('./fixtures/house_room_payload.json', import.meta.url), 'utf8')).room;
const ROOMS = Object.fromEntries([['bad', 'Bad', 'close'], ['flur', 'Flur', 'okay'], ['wohnen', 'Wohnen', 'ventilate'], ['schlaf', 'Schlafzimmer', 'okay']]
  .map(([key, name, code]) => [key, { ...BASE_ROOM, key, name, house_aligned_action: code }]));
const HOUSE = { house_map_api: 'house_map_v1', revision: 3, layout_usable: true, rooms: {},
  wind: { available: true, from_deg: 270, to_deg: 90, speed_ms: 4, calm: false, stale: false, age_s: 60, label_de: 'W', label_en: 'W' },
  airflow: { model_level: 'wind_heuristic', openings: {}, paths: [], devices: [], pending_openings: [] } };
// Like Home Assistant's ha-card: shadow root on connect, the slot is drawn a microtask later.
const HA_CARD = `customElements.define('ha-card', class extends HTMLElement { connectedCallback() { if (!this.shadowRoot) { this.attachShadow({ mode: 'open' }); queueMicrotask(() => { this.shadowRoot.innerHTML = '<style>:host{display:block}</style><slot></slot>'; }); } } });`;

// before/after: other cards around the house map; nested: Home Assistant's view as an inner scroller.
async function mount(page, { before = 1500, after = 40, nested = false, width = 390 } = {}) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await page.setViewportSize({ width, height: 700 });
  const inner = `<div style="height:${before}px">other cards</div><main id="m"></main><div style="height:${after}px"></div>`;
  const body = nested ? `<div id="view" style="height:700px;overflow:auto;overflow-anchor:none">${inner}</div>` : inner;
  await loadModule(page, `<!doctype html><html><head><style>html,body{margin:0;overflow-anchor:none}</style><script>${HA_CARD}</script></head><body>${body}</body></html>`,
    'freshairiq-loader.js', 'freshairiq-house-card');
  await page.evaluate(async ({ LAYOUT, ROOMS }) => {
    window.__subs = {}; window.__active = 0; window.__calls = [];
    window.__ROOMS = ROOMS; window.__LAYOUT = LAYOUT;
    window.__connection = { subscribeMessage(cb, msg) { window.__active += 1; window.__subs[msg.type] = cb; return Promise.resolve(() => { window.__active -= 1; return Promise.resolve(); }); } };
    window.__callWS = async msg => {
      window.__calls.push(msg.type);
      if (msg.type === 'freshairiq/house_map/get') return { house_map_api: 'house_map_v1', entry_id: 'e1', revision: 3, layout: LAYOUT, issues: [], rooms: Object.values(ROOMS).map(r => ({ key: r.key, name: r.name })), levels: [] };
      if (msg.type === 'freshairiq/house_map/save') return { revision: msg.base_revision + 1, issues: [] };
      return {};
    };
    const card = document.createElement('freshairiq-house-card');
    card.setConfig({ animation: false });
    document.getElementById('m').appendChild(card);
    card.hass = { connection: window.__connection, callWS: window.__callWS, language: 'de', locale: { language: 'de' }, user: { is_admin: true } };
    await customElements.whenDefined('freshairiq-house-card-impl');
  }, { LAYOUT, ROOMS });
  await page.waitForFunction(() => window.__subs['freshairiq/house_map/subscribe'] && window.__active >= 2);
  await push(page, 0);
  await page.waitForTimeout(150);
  return errors;
}
const push = (page, i) => page.evaluate(({ i, HOUSE }) => {
  const rooms = { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, temperature: 20 + i / 10, name: `Bad${'e'.repeat(i % 4)}` } };
  window.__subs['freshairiq/dashboard/subscribe']({ rooms, output_language: 'de', status_text: `Stand ${'·'.repeat(i % 7)}` });
  window.__subs['freshairiq/house_map/subscribe']({ ...HOUSE, wind: { ...HOUSE.wind, from_deg: 250 + i * 3 } });
}, { i, HOUSE });
const scroller = (page, nested) => (nested ? '#view' : null);
const getY = (page, nested) => page.evaluate(sel => (sel ? document.querySelector(sel).scrollTop : window.scrollY), scroller(page, nested));
const setY = (page, nested, y) => page.evaluate(({ sel, y }) => { if (sel) document.querySelector(sel).scrollTop = y; else window.scrollTo(0, y); return sel ? document.querySelector(sel).scrollTop : window.scrollY; }, { sel: scroller(page, nested), y });
const impl = page => page.locator('freshairiq-house-card-impl');
const frame = page => impl(page).evaluate(el => { const card = [...el.shadowRoot.children].find(n => n.localName === 'ha-card'); window.__card = window.__card || card; return { same: window.__card === card, height: Math.round(el.getBoundingClientRect().height) }; });

for (const nested of [false, true]) {
  test(`F02: ten room and house pushes keep the page where the user scrolled (${nested ? 'inner view scroller' : 'page scroll'}, long page)`, async ({ page }) => {
    const errors = await mount(page, { nested, before: 2600 });
    const bottom = await setY(page, nested, 99999);  // the house map at the very end of a long view
    expect(bottom).toBeGreaterThan(2000);
    for (let i = 1; i <= 10; i += 1) {
      await push(page, i);
      await page.waitForTimeout(40);
      expect(await getY(page, nested), `push ${i}`).toBe(bottom);
      expect((await frame(page)).same).toBe(true);  // the same <ha-card>, never an empty frame
    }
    // the user scrolls while pushes keep coming: the page stays where the user put it
    for (const wanted of [1800, 2200, bottom - 50]) {
      const y = await setY(page, nested, wanted);  // where the browser really put the page
      expect(Math.abs(y - wanted)).toBeLessThan(40);
      await push(page, y); await page.waitForTimeout(30); await push(page, y + 1); await page.waitForTimeout(30);
      expect(await getY(page, nested)).toBe(y);
    }
    expect(errors).toEqual([]);
  });
}

test('F02: switching layers and floors, the room window, banners and longer texts keep the page position', async ({ page }) => {
  await mount(page, { before: 1200, after: 1500 });
  const y = await setY(page, false, 1300);
  const click = selector => impl(page).evaluate((el, s) => el.shadowRoot.querySelector(s).click(), selector);
  for (const step of ['[data-layer="temperature"]', '[data-layer="airflow"]', '[data-floor="f_og"]', '[data-floor="__all"]', '[data-floor="f_eg"]']) {
    await click(step); await page.waitForTimeout(30);
    expect(await getY(page, false), step).toBe(y);
  }
  // open the room window, pushes while it is open, close it
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(40);
  for (let i = 0; i < 3; i += 1) { await push(page, i); await page.waitForTimeout(30); }
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-close-detail]').click());
  await page.waitForTimeout(30);
  expect(await getY(page, false)).toBe(y);
  // a warning banner comes and goes (live connection disrupted), status texts change length
  await impl(page).evaluate(el => { el._failed = true; el._queue(); });
  await page.waitForTimeout(40);
  expect(await impl(page).evaluate(el => el.shadowRoot.textContent)).toContain('Live-Verbindung gestört');
  expect(await getY(page, false)).toBe(y);
  await impl(page).evaluate(el => { el._failed = false; });
  await page.evaluate(() => window.__subs['freshairiq/dashboard/subscribe']({ rooms: window.__ROOMS, output_language: 'de', status_text: 'Ein sehr langer Statustext '.repeat(6) }));
  await page.waitForTimeout(40);
  expect(await getY(page, false)).toBe(y);
  await push(page, 3); await page.waitForTimeout(40);
  expect(await getY(page, false)).toBe(y);
});

test('F02: a live push keeps the focused button, the open room window (no second showModal) and its scroll', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => { window.__modal = 0; const show = HTMLDialogElement.prototype.showModal; HTMLDialogElement.prototype.showModal = function () { window.__modal += 1; return show.call(this); }; });
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-layer="humidity"]').focus({ preventScroll: true }));
  await push(page, 1); await page.waitForTimeout(40);
  expect(await impl(page).evaluate(el => el.shadowRoot.activeElement && el.shadowRoot.activeElement.dataset.layer)).toBe('humidity');
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(40);
  await impl(page).evaluate(el => { window.__dialog = el.shadowRoot.querySelector('dialog.roomdlg'); el.shadowRoot.querySelector('[data-close-detail]').focus({ preventScroll: true }); });
  for (let i = 2; i < 6; i += 1) { await push(page, i); await page.waitForTimeout(30); }
  const state = await impl(page).evaluate(el => { const d = el.shadowRoot.querySelector('dialog.roomdlg'); return { same: d === window.__dialog, open: d.open, focus: !!(el.shadowRoot.activeElement && el.shadowRoot.activeElement.hasAttribute('data-close-detail')), text: d.textContent }; });
  expect(state).toMatchObject({ same: true, open: true, focus: true });
  expect(state.text).toContain('Bad');
  expect(await page.evaluate(() => window.__modal)).toBe(1);
  // another room replaces the window
  await impl(page).evaluate(el => { el._selected = { type: 'room', id: 'r_flur' }; el._render(); });
  expect(await page.evaluate(() => window.__modal)).toBe(2);
});

test('F02: a live update waits while a finger is on the card and follows when it is lifted', async ({ page }) => {
  await mount(page);
  const mark = () => impl(page).evaluate(el => { const m = el.shadowRoot.querySelector('.faiq-main .map'); m.__mark = (m.__mark || 0) + 1; return m.__mark; });
  await mark();
  await impl(page).evaluate(el => el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 1 })));
  await push(page, 4); await page.waitForTimeout(80);
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('.faiq-main .map').__mark)).toBe(true);  // not replaced mid-gesture
  await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointerup', { pointerId: 1 })));
  await page.waitForTimeout(80);
  expect(await impl(page).evaluate(el => !!el.shadowRoot.querySelector('.faiq-main .map').__mark)).toBe(false);  // the pending update is drawn
  expect(await impl(page).evaluate(el => el.shadowRoot.textContent)).toContain('Stand ····');
});

test('F02 editor: selecting, changing an opening, undo/redo, inputs and saving keep the page, the focus and the card frame', async ({ page }) => {
  await mount(page, { before: 1200, after: 1500 });
  await frame(page);
  const y = await setY(page, false, 1300);
  await impl(page).evaluate(el => el.shadowRoot.querySelector('[data-edit]').click());
  await page.waitForFunction(() => document.querySelector('freshairiq-house-card-impl').shadowRoot.querySelector('freshairiq-house-layout-editor'));
  await page.waitForTimeout(60);
  expect((await frame(page)).same).toBe(true);
  expect(await getY(page, false)).toBe(y);
  const editor = page.locator('freshairiq-house-layout-editor');
  await editor.evaluate(el => { el._sel = { type: 'opening', id: 'o_wohnen' }; el._render(); });
  expect(await getY(page, false)).toBe(y);
  // type a width: the field keeps the focus after the re-render
  await editor.evaluate(el => { const f = el.shadowRoot.querySelector('[data-f="width"]'); f.focus({ preventScroll: true }); f.value = '1.4'; f.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(30);
  expect(await editor.evaluate(el => el.shadowRoot.activeElement && el.shadowRoot.activeElement.dataset.f)).toBe('width');
  expect(await editor.evaluate(el => el._layout.openings.find(o => o.id === 'o_wohnen').width_m)).toBe(1.4);
  for (const action of ['[data-w="1"]', '[data-a="undo"]', '[data-a="redo"]', '[data-a="zoom-in"]', '[data-a="zoom-out"]']) {
    await editor.evaluate((el, s) => { const b = el.shadowRoot.querySelector(s); b.focus({ preventScroll: true }); b.click(); }, action);
    await page.waitForTimeout(20);
    expect(await getY(page, false), action).toBe(y);
    // the same control keeps the focus (a button that is disabled now, like redo at the end, cannot hold it)
    expect(await editor.evaluate((el, s) => { const b = el.shadowRoot.querySelector(s); return el.shadowRoot.activeElement === b || b.disabled; }, action), action).toBe(true);
  }
  // pan with the pointer keeps working and does not move the page
  const box = await editor.evaluate(el => { const r = el.shadowRoot.querySelector('svg').getBoundingClientRect(); return { x: r.x + 20, y: r.y + 20 }; });
  await page.mouse.move(box.x, box.y); await page.mouse.down(); await page.mouse.move(box.x + 30, box.y + 10, { steps: 4 }); await page.mouse.up();
  expect(await getY(page, false)).toBe(y);
  await editor.evaluate(el => el.shadowRoot.querySelector('[data-a="save"]').click());
  await page.waitForTimeout(120);
  expect(await page.evaluate(() => window.__calls.includes('freshairiq/house_map/save'))).toBe(true);
  expect((await frame(page)).same).toBe(true);
  expect(await getY(page, false)).toBe(y);
});

// ---------------------------------------------------------------------------------------- F01
// A connection whose answers the test releases one by one.
async function lifecyclePage(page) {
  const errors = await mount(page);
  await page.evaluate(() => {
    window.__gate = {};
    window.__waiting = [];
    window.__hold = type => new Promise(resolve => window.__waiting.push({ type, resolve }));
    window.__release = type => { const i = window.__waiting.findIndex(w => w.type === type); if (i >= 0) window.__waiting.splice(i, 1)[0].resolve(); };
    window.__mode = {};
    window.__live = 0;
    window.__conn2 = { subscribeMessage: async (cb, msg) => {
      if (window.__mode[msg.type] === 'hold') await window.__hold(msg.type);
      if (window.__mode[msg.type] === 'reject') throw Object.assign(new Error('sub failed'), { code: 'x' });
      window.__live += 1;
      return () => { window.__live -= 1; return Promise.reject(new Error('socket closed')); };  // HA may reject on a closed socket
    } };
    window.__ws2 = async msg => {
      if (window.__mode[msg.type] === 'hold') await window.__hold(msg.type);
      return window.__callWS(msg);
    };
    window.__make = () => {
      const el = document.createElement('freshairiq-house-card-impl');
      el.setConfig({ animation: false });
      return el;
    };
    window.__hass = { connection: window.__conn2, callWS: window.__ws2, language: 'de', user: { is_admin: false } };
  });
  return errors;
}
const live = page => page.evaluate(() => window.__live);
const settle = page => page.waitForTimeout(60);

test('F01: parallel starts (hass before and after connecting, repeated hass) give exactly two subscriptions; removal gives none', async ({ page }) => {
  const errors = await lifecyclePage(page);
  expect(await page.evaluate(() => window.__active)).toBe(2);  // the card mounted through its proxy (hass before connect)
  await page.evaluate(() => {
    const el = window.__make(); window.__el = el;
    el.hass = window.__hass;                      // before connecting: no start
    document.body.appendChild(el);                // connect: start
    el.hass = { ...window.__hass }; el.hass = { ...window.__hass }; el.connectedCallback();  // repeated setters and callbacks
  });
  await settle(page);
  expect(await live(page)).toBe(2);
  await page.evaluate(() => window.__el.remove());
  await settle(page);
  expect(await live(page)).toBe(0);
  // reconnect (the view is shown again)
  await page.evaluate(() => document.body.appendChild(window.__el));
  await settle(page);
  expect(await live(page)).toBe(2);
  await page.evaluate(() => window.__el.remove());
  await settle(page);
  expect(await live(page)).toBe(0);
  expect(errors).toEqual([]);  // a rejected unsubscribe promise is not an unhandled error
});

for (const channel of ['freshairiq/dashboard/subscribe', 'freshairiq/house_map/subscribe']) {
  test(`F01: when ${channel} fails the other channel is released; the retry gives two again`, async ({ page }) => {
    await lifecyclePage(page);
    await page.evaluate(channel => { window.__mode[channel] = 'reject'; const el = window.__make(); window.__el = el; el.hass = window.__hass; document.body.appendChild(el); }, channel);
    await settle(page);
    expect(await live(page)).toBe(0);
    expect(await page.evaluate(() => !!window.__el._retry && window.__el._failed === true)).toBe(true);
    await page.evaluate(channel => { window.__mode[channel] = 'ok'; const el = window.__el; el._start(); el._start(); }, channel);  // the retry (and a second trigger)
    await settle(page);
    expect(await live(page)).toBe(2);
    await page.evaluate(() => window.__el.remove());
    await settle(page);
    expect(await live(page)).toBe(0);
    expect(await page.evaluate(() => window.__el._retry)).toBe(null);  // no retry timer is left behind
  });
}

for (const step of ['freshairiq/house_map/get', 'freshairiq/dashboard/subscribe', 'freshairiq/house_map/subscribe']) {
  test(`F01: removed while waiting for ${step}: nothing stays subscribed`, async ({ page }) => {
    await lifecyclePage(page);
    await page.evaluate(step => { window.__mode[step] = 'hold'; const el = window.__make(); window.__el = el; el.hass = window.__hass; document.body.appendChild(el); }, step);
    await settle(page);
    await page.evaluate(() => window.__el.remove());
    await page.evaluate(step => window.__release(step), step);
    await settle(page);
    expect(await live(page)).toBe(0);
    // shown again later: exactly two
    await page.evaluate(step => { window.__mode[step] = 'ok'; document.body.appendChild(window.__el); }, step);
    await settle(page);
    expect(await live(page)).toBe(2);
  });
}

test('F01: removed while the plan proposal is computed, and several cards at once', async ({ page }) => {
  await lifecyclePage(page);
  await page.evaluate(() => {
    const getEmpty = window.__callWS;
    window.__callWS = async msg => (msg.type === 'freshairiq/house_map/get' ? { ...(await getEmpty(msg)), layout: null } : msg.type === 'freshairiq/house_map/propose' ? { layout: window.__LAYOUT } : getEmpty(msg));
    window.__mode['freshairiq/house_map/propose'] = 'hold';
    const el = window.__make(); window.__el = el; el.hass = window.__hass; document.body.appendChild(el);
  });
  await settle(page);
  await page.evaluate(() => { window.__el.remove(); window.__release('freshairiq/house_map/propose'); });
  await settle(page);
  expect(await live(page)).toBe(0);
  await page.evaluate(() => { window.__mode = {}; window.__cards = [1, 2, 3].map(() => { const el = window.__make(); el.hass = window.__hass; document.body.appendChild(el); el.hass = window.__hass; return el; }); });
  await settle(page);
  expect(await live(page)).toBe(6);  // two per card
  await page.evaluate(() => window.__cards[1].remove());
  await settle(page);
  expect(await live(page)).toBe(4);
});

// ------------------------------------------------------------------------- re-audit 31.10. (21:57 build)
// Connections that record every subscription by connection and entry, and get answers the test releases.
async function targetPage(page) {
  const errors = await mount(page);
  await page.evaluate(() => {
    window.__subsBy = {};
    window.__pending = [];
    window.__getMode = 'now';
    window.__mkConn = name => ({ name, subscribeMessage: async (cb, msg) => {
      const key = `${name}:${msg.entry_id || '-'}:${msg.type}`;
      window.__subsBy[key] = (window.__subsBy[key] || 0) + 1;
      (window.__cbs = window.__cbs || {})[key] = cb;
      return () => { window.__subsBy[key] -= 1; return Promise.resolve(); };
    } });
    window.__ws3 = msg => {
      if (msg.type !== 'freshairiq/house_map/get') return window.__callWS(msg);
      const answer = rev => ({ house_map_api: 'house_map_v1', entry_id: msg.entry_id || 'e1', revision: rev, layout: { ...window.__LAYOUT, revision: rev }, issues: [], rooms: [] });
      if (window.__getMode === 'now') return Promise.resolve(answer(window.__serverRev || 0));
      return new Promise(resolve => window.__pending.push({ msg, resolve: rev => resolve(answer(rev)) }));
    };
    window.__hassFor = conn => ({ connection: conn, callWS: window.__ws3, language: 'de', user: { is_admin: false } });
    window.__active3 = () => Object.fromEntries(Object.entries(window.__subsBy).filter(([, n]) => n));
  });
  return errors;
}
const active = page => page.evaluate(() => window.__active3());

test('re-audit F01: entry A→B, connection 1→2 and both together move the two subscriptions; normal hass updates do not resubscribe', async ({ page }) => {
  const errors = await targetPage(page);
  await page.evaluate(() => { const el = document.createElement('freshairiq-house-card-impl'); window.__el = el; el.setConfig({ entry_id: 'A' }); document.body.appendChild(el); window.__c1 = window.__mkConn('c1'); el.hass = window.__hassFor(window.__c1); });
  await page.waitForTimeout(60);
  expect(await active(page)).toEqual({ 'c1:A:freshairiq/dashboard/subscribe': 1, 'c1:A:freshairiq/house_map/subscribe': 1 });
  // twenty ordinary hass updates (same connection, new states object): nothing new
  await page.evaluate(() => { for (let i = 0; i < 20; i += 1) window.__el.hass = { ...window.__hassFor(window.__c1), states: { i } }; window.__el.setConfig({ entry_id: 'A' }); });
  await page.waitForTimeout(60);
  expect(Object.values(await page.evaluate(() => window.__subsBy)).reduce((a, b) => a + b, 0)).toBe(2);
  await page.evaluate(() => window.__el.setConfig({ entry_id: 'B' }));  // another entry, same connection
  await page.waitForTimeout(60);
  expect(await active(page)).toEqual({ 'c1:B:freshairiq/dashboard/subscribe': 1, 'c1:B:freshairiq/house_map/subscribe': 1 });
  await page.evaluate(() => { window.__c2 = window.__mkConn('c2'); window.__el.hass = window.__hassFor(window.__c2); });  // new connection, same entry
  await page.waitForTimeout(60);
  expect(await active(page)).toEqual({ 'c2:B:freshairiq/dashboard/subscribe': 1, 'c2:B:freshairiq/house_map/subscribe': 1 });
  await page.evaluate(() => { const el = window.__el; el.setConfig({ entry_id: 'A' }); el.hass = window.__hassFor(window.__mkConn('c3')); });  // both at once
  await page.waitForTimeout(60);
  expect(await active(page)).toEqual({ 'c3:A:freshairiq/dashboard/subscribe': 1, 'c3:A:freshairiq/house_map/subscribe': 1 });
  await page.evaluate(() => window.__el.remove());
  await page.waitForTimeout(40);
  expect(await active(page)).toEqual({});
  expect(errors).toEqual([]);
});

test('re-audit F01: a switch during a running start and during a failure/retry ends on the new target only', async ({ page }) => {
  await targetPage(page);
  // the first start waits for its layout answer; meanwhile entry and connection change
  await page.evaluate(() => { window.__getMode = 'hold'; const el = document.createElement('freshairiq-house-card-impl'); window.__el = el; el.setConfig({ entry_id: 'A' }); document.body.appendChild(el); el.hass = window.__hassFor(window.__mkConn('c1')); });
  await page.waitForTimeout(30);
  await page.evaluate(() => { window.__el.setConfig({ entry_id: 'B' }); window.__el.hass = window.__hassFor(window.__mkConn('c2')); });
  await page.waitForTimeout(30);
  await page.evaluate(() => { window.__getMode = 'now'; for (const p of window.__pending.splice(0)) p.resolve(0); });  // the late answers arrive
  await page.waitForTimeout(80);
  expect(await active(page)).toEqual({ 'c2:B:freshairiq/dashboard/subscribe': 1, 'c2:B:freshairiq/house_map/subscribe': 1 });
  expect(await page.evaluate(() => window.__el._layoutInfo.entry_id)).toBe('B');  // the late answer for A did not win
  // a failed start with a pending retry, then a new connection: one start there, the retry is gone
  await page.evaluate(() => { const bad = { name: 'bad', subscribeMessage: () => Promise.reject(new Error('down')) }; window.__el.hass = window.__hassFor(bad); });
  await page.waitForTimeout(60);
  expect(await page.evaluate(() => !!window.__el._retry)).toBe(true);
  expect(await active(page)).toEqual({});
  await page.evaluate(() => { window.__el.hass = window.__hassFor(window.__mkConn('c4')); });
  await page.waitForTimeout(60);
  expect(await page.evaluate(() => window.__el._retry)).toBe(null);
  expect(await active(page)).toEqual({ 'c4:B:freshairiq/dashboard/subscribe': 1, 'c4:B:freshairiq/house_map/subscribe': 1 });
});

test('re-audit F02: layout answers out of order never replace a newer revision; one request at a time', async ({ page }) => {
  await targetPage(page);
  await page.evaluate(() => { const el = document.createElement('freshairiq-house-card-impl'); window.__el = el; el.setConfig({}); document.body.appendChild(el); window.__c1 = window.__mkConn('c1'); el.hass = window.__hassFor(window.__c1); });
  await page.waitForTimeout(60);
  expect(await page.evaluate(() => window.__el._layoutInfo.revision)).toBe(0);
  const house = rev => page.evaluate(rev => window.__cbs['c1:-:freshairiq/house_map/subscribe']({ revision: rev, wind: null, rooms: {}, airflow: null }), rev);
  await page.evaluate(() => { window.__getMode = 'hold'; });
  await house(1); await house(2); await house(2); await house(2);  // repeated pushes while the first request runs
  await page.waitForTimeout(30);
  expect(await page.evaluate(() => window.__pending.length)).toBe(1);  // deduplicated
  await page.evaluate(() => window.__pending.shift().resolve(1));    // the answer for revision 1 …
  await page.waitForTimeout(30);
  expect(await page.evaluate(() => window.__pending.length)).toBe(1);  // … and revision 2 is fetched right after
  await page.evaluate(() => window.__pending.shift().resolve(2));
  await page.waitForTimeout(30);
  expect(await page.evaluate(() => window.__el._layoutInfo.revision)).toBe(2);
  // an older answer (e.g. a slow server read) does not move the layout back
  await house(3);
  await page.waitForTimeout(20);
  await page.evaluate(() => window.__pending.shift().resolve(1));
  await page.waitForTimeout(30);
  expect(await page.evaluate(() => window.__el._layoutInfo.revision)).toBe(2);
  // a request still running when the connection changes is dropped
  await house(4);
  await page.waitForTimeout(20);
  await page.evaluate(() => { const old = window.__pending.splice(0); window.__getMode = 'now'; window.__serverRev = 5; window.__el.hass = window.__hassFor(window.__mkConn('c2')); window.__old = old; });
  await page.waitForTimeout(60);
  await page.evaluate(() => { for (const p of window.__old) p.resolve(4); });
  await page.waitForTimeout(40);
  expect(await page.evaluate(() => window.__el._layoutInfo.revision)).toBe(5);
  // the editor context is not touched by a late answer
  await page.evaluate(() => { window.__el._proposal = { layout: window.__LAYOUT }; window.__el._editing = { hass: null }; });
  await page.evaluate(() => window.__cbs['c2:-:freshairiq/house_map/subscribe']({ revision: 9, wind: null, rooms: {}, airflow: null }));
  await page.waitForTimeout(30);
  expect(await page.evaluate(() => [window.__el._layoutInfo.revision, !!window.__el._proposal])).toEqual([5, true]);
});

test('re-audit F03: a finger held for 1 s or 9 s keeps every live update back until it is lifted; cancel, multi-touch, lost release', async ({ page }) => {
  await mount(page);
  const el = impl(page);
  const marked = () => el.evaluate(e => !!e.shadowRoot.querySelector('.faiq-main .map').__m);
  const mark = () => el.evaluate(e => { e.shadowRoot.querySelector('.faiq-main .map').__m = 1; });
  const y = await setY(page, false, 900);
  for (const held of [1000, 9000]) {
    await mark();
    await el.evaluate(e => e.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 5, pointerType: 'touch' })));
    await el.evaluate((e, held) => { e._gestureSeen = Date.now() - held; }, held);  // the finger has been down this long
    for (let i = 0; i < 5; i += 1) { await push(page, held + i); await page.waitForTimeout(25); }
    expect(await marked(), `${held} ms`).toBe(true);  // still the same map: nothing re-rendered under the finger
    await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointerup', { pointerId: 5, pointerType: 'touch' })));
    await page.waitForTimeout(60);
    expect(await marked()).toBe(false);  // drawn right after lifting
    expect(await getY(page, false)).toBe(y);
  }
  // touch scroll: the browser cancels the pointer, the finger stays down (touchstart without touchend) → still held
  await mark();
  await el.evaluate(e => { e.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 6, pointerType: 'touch' })); e._onDown({ type: 'touchstart' }); });
  await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 6, pointerType: 'touch' })));
  await push(page, 30); await page.waitForTimeout(40);
  expect(await marked()).toBe(true);
  // two fingers: lifting one keeps it held, lifting the last one releases
  await el.evaluate(e => e._onUp({ type: 'touchend', touches: [{}] }));
  await push(page, 31); await page.waitForTimeout(40);
  expect(await marked()).toBe(true);
  await el.evaluate(e => e._onUp({ type: 'touchend', touches: [] }));
  await page.waitForTimeout(60);
  expect(await marked()).toBe(false);
  // a release that never arrives: after a minute without any touch or pointer event the card draws again
  await mark();
  await el.evaluate(e => e.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 7, pointerType: 'touch' })));
  await push(page, 40); await page.waitForTimeout(40);
  expect(await marked()).toBe(true);
  await el.evaluate(e => { e._gestureSeen = Date.now() - 61000; });
  await push(page, 41); await page.waitForTimeout(60);
  expect(await marked()).toBe(false);
  // the page goes to the background with a finger down: released
  await mark();
  await el.evaluate(e => { e.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 8, pointerType: 'touch' })); });
  await push(page, 50); await page.waitForTimeout(30);
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await page.waitForTimeout(60);
  expect(await marked()).toBe(false);
});

test('re-audit F04: unknown forecasts show "–", known values (also 0 and negative) their number – house map and room window', async ({ page }) => {
  await mount(page);
  const hero = values => page.evaluate(values => {
    window.__subs['freshairiq/dashboard/subscribe']({ rooms: { ...window.__ROOMS, bad: { ...window.__ROOMS.bad, moisture_effect_next_5_min_ml: values.next } }, output_language: 'de', ...values.house });
  }, values);
  const read = () => impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('.kpi')].map(k => k.querySelector('.val').textContent));
  const cases = [
    [{ house: { forecast_moisture_effect_ml: null, overnight_forecast_ml: null, forecast_temperature_change_c: null }, next: null }, ['–', '–']],
    [{ house: {}, next: undefined }, ['–', '–']],
    [{ house: { forecast_moisture_effect_ml: 0, overnight_forecast_ml: 0 }, next: 0 }, ['±0 ml', '+0 ml']],
    [{ house: { forecast_moisture_effect_ml: 42, overnight_forecast_ml: 120 }, next: 12 }, ['−42 ml', '+120 ml']],
    [{ house: { forecast_moisture_effect_ml: -15, overnight_forecast_ml: 30 }, next: -4 }, ['+15 ml', '+30 ml']],
  ];
  await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('polygon.room')].find(n => n.dataset.room === 'r_bad').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(40);
  for (const [values, [forecast, night]] of cases) {
    await hero(values);
    await page.waitForTimeout(40);
    const kpis = await read();
    expect(kpis[1], JSON.stringify(values)).toBe(forecast);
    expect(kpis[2], JSON.stringify(values)).toBe(night);
    const tile = await impl(page).evaluate(el => [...el.shadowRoot.querySelectorAll('dialog .tile')].map(t => t.textContent).find(t => t.includes('Nächste 5 min')) || '');
    const next = values.next;
    expect(tile, JSON.stringify(values)).toContain(next == null ? '–' : next > 0 ? `−${next} ml` : next < 0 ? `+${-next} ml` : '±0 ml');
  }
});
