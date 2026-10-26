// 0.26.5.4 (community): the room tile shows how much of the room air the running
// airing has replaced and how long it takes to 95 % – display only.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

async function mount(page, room, language = 'de', view = 'rooms') {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(({ room, language, view }) => {
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      freshairiq_transport: 'status_v2', freshairiq_entry_id: 'entry1', freshairiq_version: '0.26.5.4', output_language: language,
      rooms: { schlaf: room }, room_sort_order: ['schlaf'] } };
    const card = document.getElementById('card');
    card.setConfig({ dashboard_variant: 'classic' });
    card.hass = { states: { [status.entity_id]: status }, language, locale: { language } };
    card._info = view;
    card._render();
  }, { room, language, view });
  await page.waitForTimeout(200);
  return errors;
}

const bedroom = extra => ({ key: 'schlaf', name: 'Schlafzimmer', calculation_enabled: true, data_quality: 'ok', temperature: 20,
  humidity: 55, absolute_humidity: 9.5, action: 'Continue ventilating', potential_ml: 30, surface_rh: 65, mould_level: 'Low', ...extra });

const tile = (page, where = 'article.room') => page.locator('#card').evaluate((card, where) => {
  const node = card.shadowRoot.querySelector(`${where} .air-exchange`);
  return node ? node.textContent : null;
}, where);

test('the tile shows the exchanged share and the time to 95 % while airing', async ({ page }) => {
  const errors = await mount(page, bedroom({ active: true, air_exchange: { exchanged_percent: 62, minutes_to_95: 8.6, estimate: true } }));
  expect(await tile(page)).toBe('Luftaustausch 62 % · bis 95 % noch ca. 9 min · Schätzung');
  expect(errors).toEqual([]);
});

test('practically complete, and nothing without an airing', async ({ page }) => {
  await mount(page, bedroom({ active: true, air_exchange: { exchanged_percent: 96, minutes_to_95: 0, estimate: false } }));
  expect(await tile(page)).toBe('Luftaustausch 96 % · praktisch vollständig');
  await mount(page, bedroom({ active: false, air_exchange: null }));
  expect(await tile(page)).toBe(null);
});

test('English dashboards get the English line', async ({ page }) => {
  await mount(page, bedroom({ active: true, air_exchange: { exchanged_percent: 30, minutes_to_95: 20.2, estimate: false } }), 'en');
  expect(await tile(page)).toBe('Air exchange 30 % · about 20 min to 95 %');
});

test('the opened room shows the same line under its recommendation', async ({ page }) => {
  const errors = await mount(page, bedroom({ active: true, air_exchange: { exchanged_percent: 62, minutes_to_95: 8.6, estimate: false } }), 'de', 'room:schlaf');
  expect(await tile(page, '.room-detail .room-iq-hero')).toBe('Luftaustausch 62 % · bis 95 % noch ca. 9 min');
  expect(errors).toEqual([]);
});
