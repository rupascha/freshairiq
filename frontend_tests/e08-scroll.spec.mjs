import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';


async function mountRooms(page, count, { spacer = 0, wrap = '' } = {}) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  const card = wrap ? `<div id="wrap" style="${wrap}"><freshairiq-card id="card"></freshairiq-card></div>` : '<freshairiq-card id="card"></freshairiq-card>';
  await loadCard(page, `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><main>${spacer ? `<div style="height:${spacer}px">other dashboard cards</div>` : ''}${card}<div style="height:1200px"></div></main></body></html>`);
  await page.evaluate(({ count }) => {
    const rooms = {};
    for (let i = 0; i < count; i++) {
      rooms[`room_${i}`] = { key: `room_${i}`, name: `Raum ${i + 1}`, calculation_enabled: true, data_quality: 'ok',
        temperature: 21.2, humidity: 61, absolute_humidity: 11.0, action: i % 3 === 0 ? 'Ventilate' : 'Okay',
        potential_ml: 120 + i, surface_rh: 72, mould_level: 'Low', active: false };
    }
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      freshairiq_transport: 'status_v2', rooms, room_sort_order: Object.keys(rooms), diagnostics: { retention_days: 30 } } };
    const card = document.getElementById('card');
    card.setConfig({});
    card.hass = { states: { [status.entity_id]: status } };
  }, { count });
  await page.waitForTimeout(80);
  return errors;
}

const listTop = page => page.locator('#card .subdialog').evaluate(el => el.scrollTop);
const roomOffset = (page, key) => page.locator('#card').evaluate((card, key) => {
  const sub = card.shadowRoot.querySelector('.subdialog');
  const room = card.shadowRoot.querySelector(`.subdialog article.room[data-room="${key}"]`);
  return room ? Math.round(room.getBoundingClientRect().top - sub.getBoundingClientRect().top) : null;
}, key);

async function openLowRoomAndGoBack(page, key, { rerender = false } = {}) {
  const room = page.locator(`.subdialog article.room[data-room="${key}"]`);
  await room.scrollIntoViewIfNeeded();
  await page.waitForTimeout(50);
  const before = await listTop(page);
  const offsetBefore = await roomOffset(page, key);
  expect(before).toBeGreaterThan(200);
  await room.click();
  await expect(page.locator('.subdialog .room-detail h3')).toBeVisible();
  await page.locator('.subdialog').evaluate(el => { el.scrollTop = 400; });
  await page.waitForTimeout(50);
  if (rerender) {
    await page.locator('freshairiq-card').evaluate(card => { card.hass = { ...card._hass }; card._render(); });
    await page.waitForTimeout(50);
  }
  await page.locator('#info-back').click();
  await expect(page.locator('.subdialog article.room').first()).toBeVisible();
  await page.waitForTimeout(400);
  return { before, after: await listTop(page), offsetBefore, offsetAfter: await roomOffset(page, key) };
}

for (const [label, width, height] of [['iPhone', 390, 844], ['Desktop', 1440, 900]]) {
  test(`E08 ${label}: back from room details restores the room list position`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const errors = await mountRooms(page, 30);
    await page.locator('#rooms').click();
    await expect(page.locator('.subdialog article.room')).toHaveCount(30);
    const first = await openLowRoomAndGoBack(page, 'room_24');
    expect(first.after).toBe(first.before);
    expect(first.offsetAfter).toBe(first.offsetBefore);
    const second = await openLowRoomAndGoBack(page, 'room_28', { rerender: true });
    expect(second.after).toBe(second.before);
    expect(second.offsetAfter).toBe(second.offsetBefore);
    expect(errors).toEqual([]);
  });
}

async function pushLiveUpdate(page) {
  // Home Assistant replaces the state objects on every coordinator update.
  await page.locator('freshairiq-card').evaluate(card => {
    const old = card._hass.states['sensor.freshairiq_status'];
    const rooms = Object.fromEntries(Object.entries(old.attributes.rooms).map(([k, r]) => [k, { ...r, humidity: r.humidity + 1 }]));
    card.hass = { states: { ...card._hass.states, [old.entity_id]: { ...old, attributes: { ...old.attributes, rooms } } } };
  });
  await page.waitForTimeout(120);
}

for (const [label, width, height] of [['iPhone', 390, 844], ['Desktop', 1440, 900]]) {
  test(`E08 ${label}: the opened room stays anchored when the list changed meanwhile`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const errors = await mountRooms(page, 30);
    await page.locator('#rooms').click();
    const room = page.locator('.subdialog article.room[data-room="room_24"]');
    await room.scrollIntoViewIfNeeded();
    await page.locator('.subdialog').evaluate(el => { el.scrollTop += 37; });
    await page.waitForTimeout(50);
    const offsetBefore = await roomOffset(page, 'room_24');
    await room.click();
    await expect(page.locator('.subdialog .room-detail h3')).toBeVisible();
    // Two rooms above the opened one disappear (e.g. deleted in another tab).
    await page.locator('freshairiq-card').evaluate(card => {
      const old = card._hass.states['sensor.freshairiq_status'];
      const rooms = { ...old.attributes.rooms }; delete rooms.room_1; delete rooms.room_2;
      card.hass = { states: { ...card._hass.states, [old.entity_id]: { ...old, attributes: { ...old.attributes, rooms, room_sort_order: Object.keys(rooms) } } } };
    });
    await page.waitForTimeout(120);
    await page.locator('#info-back').click();
    await page.waitForTimeout(400);
    expect(await roomOffset(page, 'room_24')).toBe(offsetBefore);
    // A later live update must not pull the list back to the old position.
    await page.locator('.subdialog').evaluate(el => { el.scrollTop -= 120; });
    await page.waitForTimeout(50);
    const userTop = await listTop(page);
    await pushLiveUpdate(page);
    expect(await listTop(page)).toBe(userTop);
    expect(errors).toEqual([]);
  });

  test(`E08 ${label}: two card instances keep separate list positions`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const errors = await mountRooms(page, 30);
    await page.evaluate(() => {
      const first = document.getElementById('card');
      const second = document.createElement('freshairiq-card');
      second.id = 'card2';
      first.after(second);
      second.setConfig({});
      second.hass = first._hass;
    });
    const second = page.locator('#card2');
    await second.locator('#rooms').click();
    await second.locator('.subdialog').evaluate(el => { el.scrollTop = 600; });
    await page.waitForTimeout(50);
    await second.locator('#info-close').click();
    await page.locator('#card #rooms').click();
    expect(await page.locator('#card .subdialog').evaluate(el => el.scrollTop)).toBe(0);
    expect(errors).toEqual([]);
  });

  test(`E08 ${label}: room overview keeps its position across live updates and repeated rooms`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const errors = await mountRooms(page, 30);
    await page.locator('#rooms').click();
    for (const key of ['room_20', 'room_27', 'room_23']) {
      const room = page.locator(`.subdialog article.room[data-room="${key}"]`);
      await room.scrollIntoViewIfNeeded();
      await page.waitForTimeout(50);
      const before = await listTop(page);
      await room.click();
      await expect(page.locator('.subdialog .room-detail h3')).toBeVisible();
      await pushLiveUpdate(page);
      await page.locator('#info-back').click();
      await page.waitForTimeout(300);
      expect(await listTop(page)).toBe(before);
      await pushLiveUpdate(page);
      expect(await listTop(page)).toBe(before);
    }
    expect(errors).toEqual([]);
  });
}

// iOS 18 (Safari and the companion app, 2026-10-17): WebKit can drop a scroll
// position written into a freshly inserted overflow container, so "Back" from a
// room landed at the top of the list. Emulate that: every newly inserted room
// list is reset to 0 right after the card restored it (microtask after insert).
test('E08 iOS: back from a room restores the list even when WebKit drops the first scroll write', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await mountRooms(page, 30);
  await page.locator('#rooms').click();
  await expect(page.locator('.subdialog article.room')).toHaveCount(30);
  await page.locator('#card').evaluate(card => {
    new MutationObserver(records => {
      for (const record of records) for (const node of record.addedNodes) {
        const list = node.querySelector ? (node.matches?.('.subdialog') ? node : node.querySelector('.subdialog')) : null;
        if (list && list.querySelector('article.room')) list.scrollTop = 0;
      }
    }).observe(card.shadowRoot, { childList: true, subtree: true });
  });
  const result = await openLowRoomAndGoBack(page, 'room_24');
  expect(result.before).toBeGreaterThan(200);
  expect(Math.abs(result.after - result.before)).toBeLessThanOrEqual(2);
  expect(Math.abs(result.offsetAfter - result.offsetBefore)).toBeLessThanOrEqual(2);
  // a later live update keeps the restored position
  await page.locator('freshairiq-card').evaluate(card => { card.hass = { ...card._hass }; card._render(); });
  await page.waitForTimeout(400);
  expect(Math.abs(await listTop(page) - result.before)).toBeLessThanOrEqual(2);
  expect(errors).toEqual([]);
});

test('E08 iOS: scrolling right after Back is not pulled back', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mountRooms(page, 30);
  await page.locator('#rooms').click();
  const room = page.locator('.subdialog article.room[data-room="room_24"]');
  await room.scrollIntoViewIfNeeded();
  await room.click();
  await expect(page.locator('.subdialog .room-detail h3')).toBeVisible();
  await page.locator('#info-back').click();
  await expect(page.locator('.subdialog article.room').first()).toBeVisible();
  // the user touches and scrolls to the top immediately after Back
  await page.locator('.subdialog').evaluate(el => {
    el.dispatchEvent(new Event('touchstart', { bubbles: true }));
    el.scrollTop = 0;
  });
  await page.waitForTimeout(400);
  expect(await listTop(page)).toBe(0);
});

// 0.26.5.4 (support case support-ff65eea96f68094a0640aec0): after switching from
// card_mod to UIX every dialog appeared inside the card and the lowest room of
// the room overview was cut off. A backdrop-filter or transform on ha-card or on
// a parent makes it the containing block of position:fixed; the dialogs now live
// in the browser's top layer and always cover the screen.
const LAYOUTS = [
  ['normal card', '', ''],
  ['card with backdrop-filter', '', 'blur(18px)'],
  ['card in a container with transform and overflow', 'transform:translateZ(0);overflow:hidden;height:360px', ''],
];
const coversScreen = (page, selector) => page.locator('#card').evaluate((card, selector) => {
  const box = card.shadowRoot.querySelector(selector).getBoundingClientRect();
  return Math.round(box.top) === 0 && Math.round(box.left) === 0 && Math.round(box.height) === innerHeight && Math.round(box.width) === innerWidth;
}, selector);
const openOverlays = page => page.locator('#card').evaluate(card => card.shadowRoot.querySelectorAll('.modal,.submodal,.explain-backdrop').length);

for (const [label, width, height] of [['iPhone', 390, 844], ['Desktop', 1440, 900]]) {
  for (const [layout, wrap, blur] of LAYOUTS) {
    test(`overlays ${label}, ${layout}: room overview, last room, details and support cover the screen`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      const errors = await mountRooms(page, 30, { wrap });
      if (blur) await page.locator('#card').evaluate((card, blur) => { card.shadowRoot.querySelector('ha-card').style.backdropFilter = blur; }, blur);
      await page.locator('#rooms').click();
      await expect(page.locator('.subdialog article.room')).toHaveCount(30);
      expect(await coversScreen(page, '.submodal')).toBe(true);
      // the last room can be reached and opened by a real click
      const last = page.locator('.subdialog article.room[data-room="room_29"]');
      await last.scrollIntoViewIfNeeded();
      await page.waitForTimeout(50);
      const before = await listTop(page);
      await last.click();
      await expect(page.locator('.subdialog .room-detail h3')).toHaveText(/^(Raum|Room) 30$/);
      expect(await coversScreen(page, '.submodal')).toBe(true);
      await page.locator('.subdialog').evaluate(el => { el.scrollTop = el.scrollHeight; });
      await pushLiveUpdate(page);  // a live update keeps the dialog on screen
      expect(await coversScreen(page, '.submodal')).toBe(true);
      await page.locator('#info-back').click();
      await page.waitForTimeout(400);
      expect(await listTop(page)).toBe(before);
      await page.locator('#info-close').click();
      expect(await openOverlays(page)).toBe(0);  // closed overlays are removed
      // details window and support view
      await page.locator('#details').click();
      expect(await coversScreen(page, '.modal')).toBe(true);
      await page.locator('#close').click();
      expect(await openOverlays(page)).toBe(0);
      await page.locator('#card').evaluate(card => { card._info = 'support'; card._render(); });
      await page.waitForTimeout(80);
      expect(await coversScreen(page, '.submodal')).toBe(true);
      await page.locator('.subdialog').evaluate(el => { el.scrollTop = el.scrollHeight; });
      await page.waitForTimeout(50);
      const bottom = await page.locator('.subdialog').evaluate(el => Math.round(el.getBoundingClientRect().bottom));
      expect(bottom).toBeLessThanOrEqual(height);
      await page.locator('#info-close').click();
      expect(await openOverlays(page)).toBe(0);
      expect(errors).toEqual([]);
    });
  }
}

test('overlays Android WebView: a trusted touch swipe scrolls the room list inside a transformed, clipped container', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'android-webview', 'Trusted touch swipe uses the Chromium Android WebView project');
  const errors = await mountRooms(page, 30, { wrap: 'transform:translateZ(0);overflow:hidden;height:360px' });
  await page.locator('#card').evaluate(card => { card.shadowRoot.querySelector('ha-card').style.backdropFilter = 'blur(18px)'; });
  await page.locator('#rooms').click();
  const dialog = page.locator('.subdialog');
  const box = await dialog.boundingBox();
  const x = box.x + box.width / 2;
  const startY = box.y + box.height - 60;
  const endY = box.y + 80;
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y: startY, id: 1, radiusX: 4, radiusY: 4, force: 1 }] });
  for (let i = 1; i <= 8; i++) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: startY + ((endY - startY) * i / 8), id: 1, radiusX: 4, radiusY: 4, force: 1 }] });
    await page.waitForTimeout(18);
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForTimeout(180);
  expect(await dialog.evaluate(el => el.scrollTop)).toBeGreaterThan(100);
  expect(await coversScreen(page, '.submodal')).toBe(true);
  expect(errors).toEqual([]);
});
