// 0.26.5.3 (community: recorder load): the card receives the dashboard state over
// the live channel freshairiq/dashboard/subscribe; the status sensor carries only
// a summary. Older status sensors with the full attributes keep working.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

async function mount(page, { fail = false } = {}) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(({ fail }) => {
    window.__subs = [];
    window.__unsubscribed = 0;
    const connection = {
      subscribeMessage(callback, message) {
        window.__subs.push({ callback, message });
        if (fail) return Promise.reject(new Error('unknown command'));
        return Promise.resolve(() => { window.__unsubscribed += 1; });
      },
    };
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      status: 'ok', status_text: 'Alles gut', freshairiq_transport: 'status_v2', freshairiq_live_api: 'dashboard_ws_v1',
      freshairiq_entry_id: 'entry1', freshairiq_version: '0.26.5.3', output_language: 'de',
    } };
    window.__room = name => ({ key: 'bad', name, calculation_enabled: true, data_quality: 'ok', temperature: 21, humidity: 64,
      absolute_humidity: 11.8, action: 'Ventilate', potential_ml: 140, surface_rh: 78, mould_level: 'Low', active: false });
    window.__payload = name => ({ ...status.attributes, rooms: { bad: window.__room(name) }, room_sort_order: ['bad'],
      intelligent_recommendation: { kind: 'ventilate', title: 'Jetzt lüften', room_keys: ['bad'] } });
    const card = document.getElementById('card');
    card.setConfig({ dashboard_variant: 'classic' });
    card.hass = { states: { [status.entity_id]: status }, connection, language: 'de' };
  }, { fail });
  await page.waitForTimeout(80);
  return errors;
}

const text = page => page.locator('#card').evaluate(card => card.shadowRoot.textContent);
const roomName = page => page.locator('#card').evaluate(card => {
  const status = card._statusEntity();
  return status && status.attributes.rooms ? status.attributes.rooms.bad.name : null;
});

test('the card subscribes once and renders what the live channel pushes', async ({ page }) => {
  const errors = await mount(page);
  expect(await page.evaluate(() => window.__subs.map(s => s.message))).toEqual([{ type: 'freshairiq/dashboard/subscribe', entry_id: 'entry1' }]);
  expect(await text(page)).toContain('wartet');  // nothing pushed yet
  expect(await roomName(page)).toBe(null);
  await page.evaluate(() => window.__subs[0].callback(window.__payload('Badezimmer')));
  await page.waitForTimeout(80);
  expect(await text(page)).not.toContain('wartet');
  expect(await roomName(page)).toBe('Badezimmer');
  // a new push re-renders; the subscription is not repeated
  await page.evaluate(() => window.__subs[0].callback(window.__payload('Duschbad')));
  await page.waitForTimeout(80);
  expect(await roomName(page)).toBe('Duschbad');
  await page.evaluate(() => { const card = document.getElementById('card'); card.hass = { ...card._hass }; card._render(); });
  expect(await page.evaluate(() => window.__subs.length)).toBe(1);
  // leaving the dashboard ends the subscription; coming back subscribes again
  await page.evaluate(() => { const card = document.getElementById('card'); const parent = card.parentNode; parent.removeChild(card); window.__card = card; });
  expect(await page.evaluate(() => window.__unsubscribed)).toBe(1);
  await page.evaluate(() => { document.querySelector('main').appendChild(window.__card); window.__card._render(); });
  expect(await page.evaluate(() => window.__subs.length)).toBe(2);
  expect(errors).toEqual([]);
});

test('an open room view is updated live by a push', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => window.__subs[0].callback(window.__payload('Badezimmer')));
  await page.waitForTimeout(80);
  await page.locator('#card').evaluate(card => { card._info = 'rooms'; card._render(); });
  await page.evaluate(() => window.__subs[0].callback(window.__payload('Gästebad')));
  await page.waitForTimeout(150);
  expect(await page.locator('#card').evaluate(card => card.shadowRoot.querySelector('.subdialog').textContent)).toContain('Gästebad');
});

test('a failed subscription is retried later and the card stays usable', async ({ page }) => {
  const errors = await mount(page, { fail: true });
  await page.waitForTimeout(50);
  // 0.26.5.4 (audit S13): no longer an empty "wartet" card – the limited view with a notice
  expect(await text(page)).toContain('Live-Verbindung zu FreshAirIQ gestört');
  await page.locator('#card').evaluate(card => card._render());
  expect(await page.evaluate(() => window.__subs.length)).toBe(1);  // no retry storm
  await page.locator('#card').evaluate(card => { card._liveRetryAt = 0; card._render(); });
  expect(await page.evaluate(() => window.__subs.length)).toBe(2);
  expect(errors).toEqual([]);
});


// 0.26.5.4 (audit S13): without the live channel the card shows what the status sensor and the
// room entities still carry, says so, and returns to the full view with the first live push.
test('without the live channel the card shows the rooms from their entities with a notice', async ({ page }) => {
  const errors = await mount(page, { fail: true });
  await page.evaluate(() => {
    const card = document.getElementById('card');
    const room = { entity_id: 'sensor.bad_aktion', state: 'ventilate', attributes: { freshairiq_transport: 'room_v2', freshairiq_entry_id: 'entry1',
      freshairiq_room_key: 'bad', freshairiq_room_payload: window.__room('Badezimmer') } };
    card.hass = { ...card._hass, states: { ...card._hass.states, [room.entity_id]: room } };
    card._invalidateEntityCaches(); card._render();  // the room entity exists from the start in Home Assistant
  });
  await page.waitForTimeout(80);
  const visible = () => page.locator('#card').evaluate(card => card.shadowRoot.querySelector('ha-card').innerText);
  expect(await visible()).toContain('Live-Verbindung zu FreshAirIQ gestört');
  expect(await visible()).toContain('Badezimmer');
  expect(await page.locator('#card').evaluate(card => card._statusEntity().attributes.freshairiq_live_unavailable)).toBe(true);
  // the retry succeeds: full view, no notice
  await page.evaluate(() => {
    const card = document.getElementById('card');
    card._hass.connection.subscribeMessage = (callback, message) => { window.__subs.push({ callback, message }); return Promise.resolve(() => {}); };
    card._liveRetryAt = 0; card._render();
  });
  await page.evaluate(() => window.__subs[window.__subs.length - 1].callback(window.__payload('Duschbad')));
  await page.waitForTimeout(80);
  expect(await visible()).not.toContain('Live-Verbindung zu FreshAirIQ gestört');
  expect(await roomName(page)).toBe('Duschbad');
  expect(errors).toEqual([]);
});

test('a Home Assistant without the live command shows the limited view in English', async ({ page }) => {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(() => {
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: { status: 'ok', status_text: 'All good', freshairiq_transport: 'status_v2',
      freshairiq_live_api: 'dashboard_ws_v1', freshairiq_entry_id: 'entry1', output_language: 'en' } };
    const card = document.getElementById('card');
    card.setConfig({});
    card.hass = { states: { [status.entity_id]: status }, connection: {}, language: 'en' };
  });
  await page.waitForTimeout(300);
  expect(await page.locator('#card').evaluate(card => card.shadowRoot.querySelector('ha-card').innerText)).toContain('Live connection to FreshAirIQ disrupted');
  expect(errors).toEqual([]);
});


// 0.26.5.4 (audit F04): a payload of another FreshAirIQ entry is no working live channel – the notice stays
test('the notice stays when only a payload of another entry is left', async ({ page }) => {
  const errors = await mount(page);
  await page.evaluate(() => window.__subs[0].callback(window.__payload('Badezimmer')));  // entry1 works
  await page.waitForTimeout(80);
  await page.evaluate(() => {
    const card = document.getElementById('card');
    const status = card._hass.states['sensor.freshairiq_status'];
    const replaced = { ...status, attributes: { ...status.attributes, freshairiq_entry_id: 'entry2' } };
    card._hass.connection.subscribeMessage = (callback, message) => { window.__subs.push({ callback, message }); return Promise.reject(new Error('gone')); };
    card.hass = { ...card._hass, states: { 'sensor.freshairiq_status': replaced } };
  });
  await page.waitForTimeout(150);
  expect(await page.locator('#card').evaluate(card => card._statusEntity().attributes.freshairiq_live_unavailable)).toBe(true);
  expect(await page.locator('#card').evaluate(card => card.shadowRoot.querySelector('ha-card').innerText)).toContain('Live-Verbindung zu FreshAirIQ gestört');
  expect(errors).toEqual([]);
});
