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
  expect(await text(page)).toContain('wartet');
  await page.locator('#card').evaluate(card => card._render());
  expect(await page.evaluate(() => window.__subs.length)).toBe(1);  // no retry storm
  await page.locator('#card').evaluate(card => { card._liveRetryAt = 0; card._render(); });
  expect(await page.evaluate(() => window.__subs.length)).toBe(2);
  expect(errors).toEqual([]);
});
